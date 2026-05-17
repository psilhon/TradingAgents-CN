"""
StockIndicatorService — 自选股 + paper 持仓的 PE/PB 等估值指标缓存。

OpenSpec change: portfolio-fundamentals
Spec: openspec/specs/portfolio-fundamentals/spec.md (after archive)

数据源：akshare `stock_zh_valuation_baidu(symbol, indicator, period)` 按指标
返回个股历史 PE/PB 序列，取最新一条 upsert 到 mongo `stock_indicators`。

注意：仅缓存「自选股 ∪ paper 持仓」codes（< 100 只），不刷全市场避免 5500+
× 每只 1s 单股 API 调用慢。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_mongo_db

logger = logging.getLogger(__name__)


class StockIndicatorService:
    COLLECTION_NAME = "stock_indicators"

    def __init__(self, db: AsyncIOMotorDatabase | None = None) -> None:
        self._db = db

    @property
    def db(self) -> AsyncIOMotorDatabase:
        if self._db is None:
            self._db = get_mongo_db()
        return self._db

    async def ensure_index(self) -> None:
        """unique compound (code, date) + 普通 code."""
        try:
            await self.db[self.COLLECTION_NAME].create_index(
                [("code", 1), ("date", 1)], unique=True
            )
            await self.db[self.COLLECTION_NAME].create_index("code")
        except Exception as e:
            logger.debug(f"ensure_index on stock_indicators: {e}")

    async def _collect_target_codes(self) -> set[str]:
        """收集「自选股 ∪ paper 持仓 (CN only)」codes 并集去重."""
        codes: set[str] = set()
        async for doc in self.db["user_favorites"].find(
            {}, {"favorite_stocks.stock_code": 1, "_id": 0}
        ):
            for fav in doc.get("favorite_stocks", []) or doc.get("favorites", []) or []:
                code = fav.get("stock_code")
                if code:
                    codes.add(str(code).strip())
        async for pos in self.db["paper_positions"].find(
            {"market": "CN"}, {"code": 1, "_id": 0}
        ):
            code = pos.get("code")
            if code:
                codes.add(str(code).strip())
        return codes

    async def sync_indicators_for_codes(self, codes: set[str] | None = None) -> dict[str, int]:
        """循环调 akshare 拉指定 codes 的最新 PE/PB，upsert 到 mongo.

        参数 codes：默认自动收集自选股 + paper 持仓。
        akshare 单股调用慢（~0.5-1s/code），按需调度（盘后 17:30 cron）。
        """
        if codes is None:
            codes = await self._collect_target_codes()
        total = len(codes)
        if total == 0:
            logger.info("sync_indicators_for_codes: target codes 为空，跳过")
            return {"total": 0, "fetched": 0, "updated": 0, "errors": 0}

        fetched = updated = errors = 0
        for code in codes:
            try:
                row = await asyncio.to_thread(self._fetch_latest_indicator, code)
                if row is None:
                    continue
                doc = {
                    "code": code,
                    "date": row["date"],
                    "pe_ttm": row.get("pe_ttm"),
                    "pb": row.get("pb"),
                }
                await self.db[self.COLLECTION_NAME].update_one(
                    {"code": code, "date": row["date"]},
                    {"$set": doc},
                    upsert=True,
                )
                fetched += 1
                updated += 1
            except Exception as e:
                errors += 1
                logger.debug(f"sync_indicators {code} 失败: {e}")

        logger.info(
            f"✅ sync_indicators_for_codes: total={total} fetched={fetched} "
            f"updated={updated} errors={errors}"
        )
        return {
            "total": total,
            "fetched": fetched,
            "updated": updated,
            "errors": errors,
        }

    @staticmethod
    def _fetch_latest_indicator(code: str) -> dict[str, Any] | None:
        """同步调 akshare 拉单股最新 PE/PB.

        akshare 1.18.x 移除了 `stock_a_indicator_lg`，改用
        `stock_zh_valuation_baidu(symbol, indicator, period)`：按指标返回
        (date, value) 历史序列，分别取「市盈率(TTM)」「市净率」最新一行。
        """
        import akshare as ak

        pe_df = ak.stock_zh_valuation_baidu(
            symbol=code, indicator="市盈率(TTM)", period="近一年"
        )
        if pe_df is None or pe_df.empty:
            return None
        pe_last = pe_df.iloc[-1]
        d_raw = pe_last.get("date")
        if d_raw is None:
            return None

        pb_df = ak.stock_zh_valuation_baidu(
            symbol=code, indicator="市净率", period="近一年"
        )
        pb_value = None
        if pb_df is not None and not pb_df.empty:
            pb_value = _safe_float(pb_df.iloc[-1].get("value"))

        return {
            "date": str(d_raw)[:10],
            "pe_ttm": _safe_float(pe_last.get("value")),
            "pb": pb_value,
        }

    async def get_latest_indicators(self, codes: list[str]) -> dict[str, dict[str, float | None]]:
        """返回 {code: {pe, pb}, ...}（取每个 code 最新一条文档）.

        缺失的 code 不在返回 dict 里。
        """
        result: dict[str, dict[str, float | None]] = {}
        for code in codes:
            doc = await self.db[self.COLLECTION_NAME].find_one(
                {"code": code},
                {"pe_ttm": 1, "pb": 1, "_id": 0},
                sort=[("date", -1)],
            )
            if doc:
                result[code] = {
                    "pe": doc.get("pe_ttm"),
                    "pb": doc.get("pb"),
                }
        return result


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        import math
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except Exception:
        return None


_stock_indicator_service: StockIndicatorService | None = None


def get_stock_indicator_service() -> StockIndicatorService:
    global _stock_indicator_service
    if _stock_indicator_service is None:
        _stock_indicator_service = StockIndicatorService()
    return _stock_indicator_service


__all__: list[Any] = ["StockIndicatorService", "get_stock_indicator_service"]
