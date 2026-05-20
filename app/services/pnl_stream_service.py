"""PnLStreamService: 盘中 PnL 服务端聚合 + 增量推送.

OpenSpec change `2026-05-08-realtime-trading-data-flow` Requirement
"PnL stream service MUST 盘中每 ≤ 3s 推送变化的 PnL"。

设计：
- compute_pnl(user_id) → 拉 paper_accounts.cash + paper_positions(market=CN) +
  quote_snapshot_reader.read_quotes 拼装实时 PnL，返回带 as_of_ts
- scan_and_publish_once() → 盘中扫所有 active CN positions 的 user，重算 PnL，
  与上次 diff (unrealized 或 equity abs > 0.01) 才 publish channel:pnl:{user_id}
- pnl_stream_loop() lifecycle task：每 interval（默认 3s）一轮 scan
- 盘外（trading-calendar.is_intraday_now() == False）noop（不查 db、不算、不 publish）
- redis 故障 throttle warning（同 realtime_quote_sync_service 模式）
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from app.core.database import get_mongo_db, get_redis_client
from app.services.quote_snapshot_reader import get_quote_snapshot_reader

logger = logging.getLogger(__name__)

PNL_CHANNEL_PREFIX = "channel:pnl:"
PNL_DIFF_THRESHOLD = 0.01  # unrealized / equity abs diff > 0.01 才 publish


def _within_threshold(
    current: tuple[float | None, float | None],
    last: tuple[float | None, float | None],
) -> bool:
    """Diff 检查 — 任一字段从 None 变为非 None（或反之）视为有变化，需 publish.

    None 表示 partial quote coverage（quote 缺失），状态变化用户可见，
    必须 publish 给前端做视觉降级切换。
    """
    for cur, prev in zip(current, last):
        if (cur is None) != (prev is None):
            return False  # None / non-None 状态变化 → 有变化
        if cur is None and prev is None:
            continue  # 都是 None → 无变化
        # 两边都是 float，正常 diff
        if abs(cur - prev) > PNL_DIFF_THRESHOLD:  # type: ignore[operator]
            return False
    return True  # 所有字段在阈值内 → 无实质变化


def _aggregate_pnl_positions(
    positions: list[dict[str, Any]],
    quotes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Pure helper: aggregate per-position PnL from positions + quotes snapshot.

    capability data-quality-gate Req 3 + change 2026-05-20-paper-null-quote-handling.

    返回 {
        position_records: [{code, quantity, avg_cost, last_price, last_price_as_of,
                            market_value: float|None, unrealized_pnl: float|None}],
        total_unrealized: float | None,  # None when any quote missing (partial)
        positions_value: float | None,   # None when any quote missing (partial)
        quote_coverage: {has_quote, missing, missing_codes, partial},
    }

    缺 quote 时该 position market_value/unrealized_pnl=None，整体聚合 partial → None
    （切断 ws push 广播假 0 的污染路径，前端可凭 partial flag 做视觉降级）。
    """
    position_records: list[dict[str, Any]] = []
    positions_value_acc = 0.0
    total_unrealized_acc = 0.0
    missing_codes: list[str] = []
    has_quote = 0
    for p in positions:
        code = str(p.get("code", "")).strip()
        qty = int(p.get("quantity", 0) or 0)
        avg_cost = float(p.get("avg_cost", 0.0) or 0.0)
        q = quotes.get(code) or {}
        last_price = q.get("close")
        last_price_as_of = q.get("last_price_as_of")
        if last_price is None:
            mkt_value: float | None = None
            unrealized: float | None = None
            missing_codes.append(code)
        else:
            mkt_value = round(float(last_price) * qty, 2)
            unrealized = round((float(last_price) - avg_cost) * qty, 2)
            positions_value_acc += mkt_value
            total_unrealized_acc += unrealized
            has_quote += 1
        position_records.append(
            {
                "code": code,
                "quantity": qty,
                "avg_cost": avg_cost,
                "last_price": float(last_price) if last_price is not None else None,
                "last_price_as_of": last_price_as_of,
                "market_value": mkt_value,
                "unrealized_pnl": unrealized,
            }
        )

    partial = len(missing_codes) > 0
    return {
        "position_records": position_records,
        # partial 时整体 None — 不允许部分合成误导前端
        "positions_value": None if partial else round(positions_value_acc, 2),
        "total_unrealized": None if partial else round(total_unrealized_acc, 2),
        "quote_coverage": {
            "has_quote": has_quote,
            "missing": len(missing_codes),
            "missing_codes": missing_codes,
            "partial": partial,
        },
    }


class PnLStreamService:
    """盘中 PnL 聚合 + 推送."""

    def __init__(
        self,
        interval_seconds: float = 3.0,
    ) -> None:
        self._interval = interval_seconds
        # _last_pnl[user_id] = (total_unrealized, total_equity)
        # 任一字段可能 None（partial quote coverage），diff 比较时显式处理
        self._last_pnl: dict[str, tuple[float | None, float | None]] = {}
        self._publish_failed = False
        self._stopping = asyncio.Event()
        self._task: Optional[asyncio.Task] = None

    async def compute_pnl(self, user_id: str) -> dict[str, Any]:
        """计算指定 user 的实时 PnL.

        返回：
            {
                "user_id": str,
                "positions": [{code, quantity, avg_cost, last_price, mkt_value, unrealized_pnl, last_price_as_of}],
                "total_unrealized": float,
                "total_realized": float,
                "total_equity": float,
                "as_of_ts": str | None,
            }

        约束（OpenSpec realtime-trading-data-flow）：
        - hot-path 路径，MUST NOT 触发外部 fetch
        - last_price 全部来自 quote_snapshot_reader（mongo `market_quotes`）
        - as_of_ts = min(last_price_as_of)，全 None 时为 None
        """
        db = get_mongo_db()
        account = await db["paper_accounts"].find_one({"user_id": user_id})
        cash_cny = 0.0
        realized_cny = 0.0
        if account:
            cash_val = account.get("cash") or {}
            if isinstance(cash_val, dict):
                cash_cny = float(cash_val.get("CNY", 0.0) or 0.0)
            else:
                cash_cny = float(cash_val or 0.0)
            pnl_val = account.get("realized_pnl") or {}
            if isinstance(pnl_val, dict):
                realized_cny = float(pnl_val.get("CNY", 0.0) or 0.0)
            else:
                realized_cny = float(pnl_val or 0.0)

        positions: list[dict[str, Any]] = []
        async for p in db["paper_positions"].find({"user_id": user_id, "market": "CN"}):
            positions.append(p)

        codes = [str(p.get("code", "")).strip() for p in positions]
        codes = [c for c in codes if c]

        reader = get_quote_snapshot_reader()
        snapshot = await reader.read_quotes(codes)
        quotes = snapshot["quotes"]

        # null-quote 处理：partial coverage 时 positions_value/total_unrealized
        # 整体 None（不允许部分合成；ws push payload 透出 quote_coverage 让前端
        # 做视觉降级）。capability data-quality-gate Req 3 Scenario "后端 service
        # 缺上游数据 MUST 返 None"。
        aggregates = _aggregate_pnl_positions(positions, quotes)
        positions_value = aggregates["positions_value"]
        total_unrealized = aggregates["total_unrealized"]
        # equity 在 positions_value=None 时也 None（公式分量缺失不可信）
        total_equity: float | None = None if positions_value is None else round(cash_cny + positions_value, 2)
        return {
            "user_id": user_id,
            "positions": aggregates["position_records"],
            "total_unrealized": total_unrealized,
            "total_realized": round(realized_cny, 2),
            "total_equity": total_equity,
            "quote_coverage": aggregates["quote_coverage"],
            "as_of_ts": snapshot.get("as_of_ts"),
        }

    async def scan_and_publish_once(self) -> None:
        """单轮扫描所有 active CN positions 的 user，diff > 0.01 才 publish."""
        # 盘外 guard
        try:
            from app.services.trading_calendar_service import get_trading_calendar_service

            if not await get_trading_calendar_service().is_intraday_now():
                logger.debug("PnLStream: 盘外，跳过扫描")
                return
        except Exception as e:
            logger.debug(f"PnLStream: trading_calendar guard 失败，保守跳过: {e}")
            return

        db = get_mongo_db()
        try:
            user_ids = await db["paper_positions"].distinct("user_id", {"market": "CN"})
        except Exception as e:
            logger.warning(f"PnLStream: distinct user_id 失败 {e!r}")
            return

        for user_id in user_ids or []:
            try:
                pnl = await self.compute_pnl(user_id)
            except Exception as e:
                logger.warning(f"PnLStream: compute_pnl({user_id}) 失败 {e!r}")
                continue

            current: tuple[float | None, float | None] = (
                pnl["total_unrealized"],
                pnl["total_equity"],
            )
            last = self._last_pnl.get(user_id)
            if last is not None and _within_threshold(current, last):
                continue  # 无实质变化，不 publish

            self._last_pnl[user_id] = current
            await self._publish_pnl(user_id, pnl)

    async def _publish_pnl(self, user_id: str, pnl: dict[str, Any]) -> None:
        try:
            r = get_redis_client()
            payload = json.dumps(pnl, ensure_ascii=False)
            await r.publish(f"{PNL_CHANNEL_PREFIX}{user_id}", payload)
            if self._publish_failed:
                logger.info("PnLStream: redis publish 已恢复")
                self._publish_failed = False
        except Exception as e:
            if not self._publish_failed:
                logger.warning(f"PnLStream: redis publish 失败 {e!r}（后续静默直到恢复）")
                self._publish_failed = True

    async def pnl_stream_loop(self) -> None:
        """Lifecycle background task：每 interval 秒一轮 scan_and_publish_once."""
        logger.info(f"PnLStream: 启动 pnl_stream_loop, interval={self._interval}s")
        try:
            while not self._stopping.is_set():
                try:
                    await self.scan_and_publish_once()
                except Exception as e:
                    logger.warning(f"PnLStream: scan_and_publish_once 异常 {e!r}")
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            logger.info("PnLStream: pnl_stream_loop 被取消")
            raise

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopping.clear()
            self._task = asyncio.create_task(self.pnl_stream_loop(), name="pnl_stream")

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass


_service: Optional[PnLStreamService] = None


def get_pnl_stream_service() -> PnLStreamService:
    global _service
    if _service is None:
        _service = PnLStreamService()
    return _service
