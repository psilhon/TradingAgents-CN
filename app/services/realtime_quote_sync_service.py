"""
RealtimeQuoteSyncService — 周期性把「自选股 ∪ paper 持仓 (CN only)」的 A 股
实时收盘价 upsert 到 mongo `market_quotes` collection，供 paper 模拟交易
`_get_last_price` 和 Dashboard 持仓显示读取。

OpenSpec change: paper-realtime-quotes-job
Spec: openspec/specs/paper-realtime-quotes/spec.md (after archive)

设计要点：
- 复用 `app.services.quotes_service.QuotesService`（已有 ak.stock_zh_a_spot_em()
  + 30s TTL 内存缓存）拿行情，不直接调 akshare
- 只把 target codes（自选股 ∪ paper 持仓 CN）upsert 到 mongo，不把全市场
  5500+ 只都写入
- 失败降级：QuotesService 返回空时 log warn + 返回错误统计，不抛
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_mongo_db, get_redis_client
from app.services.quotes_service import get_quotes_service

logger = logging.getLogger(__name__)


class RealtimeQuoteSyncService:
    """周期同步 A 股实时行情入 mongo `market_quotes` + redis publish quote 事件."""

    COLLECTION_NAME = "market_quotes"
    QUOTE_CHANNEL_PREFIX = "channel:quote:"

    def __init__(self, db: AsyncIOMotorDatabase | None = None) -> None:
        self._db = db
        # OpenSpec realtime-trading-data-flow Req "变化的 code 才 publish"：
        # 维护上次 publish 的 (close, pct_chg) 元组，下轮比较，无变化不发
        self._last_published: dict[str, tuple[Optional[float], Optional[float]]] = {}
        # redis publish 失败时只 warning 一次，避免 spam
        self._publish_failed: bool = False

    @property
    def db(self) -> AsyncIOMotorDatabase:
        if self._db is None:
            self._db = get_mongo_db()
        return self._db

    async def ensure_index(self) -> None:
        """启动时 ensure unique index on `code`. 重复调用幂等。"""
        try:
            await self.db[self.COLLECTION_NAME].create_index("code", unique=True)
        except Exception as e:
            # 已存在 index 时 motor 会抛，吞掉 — index 已存在即算成功
            logger.debug(f"ensure_index on market_quotes.code: {e}")

    async def _collect_target_codes(self) -> set[str]:
        """收集「自选股 ∪ paper 持仓 (market=CN)」codes 并集去重。

        - `db.user_favorites`: 文档 `{user_id, favorite_stocks: [{stock_code,...}]}`
        - `db.paper_positions`: 文档 `{user_id, code, market, ...}`，仅取 market=CN
        """
        codes: set[str] = set()

        # 1. 自选股
        async for doc in self.db["user_favorites"].find({}, {"favorite_stocks.stock_code": 1, "_id": 0}):
            for fav in doc.get("favorite_stocks", []) or []:
                code = fav.get("stock_code")
                if code:
                    codes.add(str(code).strip())

        # 2. paper 持仓（仅 A 股）
        async for pos in self.db["paper_positions"].find({"market": "CN"}, {"code": 1, "_id": 0}):
            code = pos.get("code")
            if code:
                codes.add(str(code).strip())

        return codes

    async def sync_favorites_and_paper_positions(self) -> dict[str, int]:
        """周期触发入口：抓 target codes → 调 QuotesService → upsert mongo。

        返回 `{total, fetched, updated, errors}` 状态字典。
        - total: target codes 总数
        - fetched: QuotesService 返回的有效行情条数
        - updated: 成功 upsert 到 mongo 的条数
        - errors: 失败条数（fetched 为 0 时全 total 算 error）
        """
        target_codes = await self._collect_target_codes()
        total = len(target_codes)

        # Scenario: 空目标 → 直接返回
        if total == 0:
            logger.info("RealtimeQuoteSync: 自选股 ∪ paper 持仓 = 空集，跳过")
            return {"total": 0, "fetched": 0, "updated": 0, "errors": 0}

        # 调 QuotesService 拿行情（内部 30s TTL 缓存，akshare batch 已封装）
        quotes_service = get_quotes_service()
        quotes = await quotes_service.get_quotes(list(target_codes))

        # Scenario: QuotesService 失败 → 全错误
        if not quotes:
            logger.warning(f"RealtimeQuoteSync: QuotesService 返回空 dict, total={total} 全部失败")
            return {"total": total, "fetched": 0, "updated": 0, "errors": total}

        fetched = len(quotes)
        updated = 0
        now = datetime.now(timezone.utc)

        # Upsert 到 market_quotes + 变化时 redis publish
        for code, quote in quotes.items():
            close = quote.get("close")
            pct_chg = quote.get("pct_chg")
            amount = quote.get("amount")
            # 守卫：close 为 None 或 ≤ 0 跳过（不写脏数据）
            if close is None or close <= 0:
                continue

            try:
                await self.db[self.COLLECTION_NAME].update_one(
                    {"code": code},
                    {
                        "$set": {
                            "code": code,
                            "symbol": code,
                            "close": float(close),
                            "pct_chg": float(pct_chg) if pct_chg is not None else None,
                            "amount": float(amount) if amount is not None else None,
                            "volume": amount,  # 兼容旧字段名（akshare 返回成交额）
                            "updated_at": now,
                        }
                    },
                    upsert=True,
                )
                updated += 1
            except Exception as e:
                logger.warning(f"RealtimeQuoteSync: upsert {code} 失败: {e}")
                continue

            # 变化检测：与上次 publish 的 (close, pct_chg) 比较，仅变化才发
            current = (
                float(close),
                float(pct_chg) if pct_chg is not None else None,
            )
            if self._last_published.get(code) != current:
                self._last_published[code] = current
                await self._publish_quote_event(code, close, pct_chg, amount, now)

        errors = total - updated
        logger.info(f"RealtimeQuoteSync: total={total} fetched={fetched} updated={updated} errors={errors}")
        return {
            "total": total,
            "fetched": fetched,
            "updated": updated,
            "errors": errors,
        }

    async def _publish_quote_event(
        self,
        code: str,
        close: Any,
        pct_chg: Any,
        amount: Any,
        ts: datetime,
    ) -> None:
        """Redis publish quote 事件 to `channel:quote:{code}`.

        OpenSpec realtime-trading-data-flow: redis 不可用时 logger.warning
        一次（throttle，避免 spam），不抛——sync 主流程必须继续。
        """
        try:
            r = get_redis_client()
            payload = json.dumps(
                {
                    "code": code,
                    "close": float(close),
                    "pct_chg": float(pct_chg) if pct_chg is not None else None,
                    "amount": float(amount) if amount is not None else None,
                    "as_of_ts": ts.isoformat(),
                }
            )
            await r.publish(f"{self.QUOTE_CHANNEL_PREFIX}{code}", payload)
            if self._publish_failed:
                logger.info("RealtimeQuoteSync: redis publish 已恢复")
                self._publish_failed = False
        except Exception as e:
            if not self._publish_failed:
                logger.warning(f"RealtimeQuoteSync: redis publish 失败 {e!r}（后续静默直到恢复）")
                self._publish_failed = True


_realtime_quote_sync_service: RealtimeQuoteSyncService | None = None


def get_realtime_quote_sync_service() -> RealtimeQuoteSyncService:
    """Module-level singleton accessor."""
    global _realtime_quote_sync_service
    if _realtime_quote_sync_service is None:
        _realtime_quote_sync_service = RealtimeQuoteSyncService()
    return _realtime_quote_sync_service


__all__: list[Any] = [
    "RealtimeQuoteSyncService",
    "get_realtime_quote_sync_service",
]
