"""
IndexDataService — 沪深 300 等指数历史日 K 缓存。

OpenSpec change: portfolio-fundamentals
Spec: openspec/specs/portfolio-fundamentals/spec.md (after archive)

数据源：akshare `index_zh_a_hist(symbol, period="daily", start_date, end_date)`。
mongo collection `index_quotes_daily` 持久化，PortfolioRiskService.calc_beta 用。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_mongo_db

logger = logging.getLogger(__name__)


class IndexDataService:
    COLLECTION_NAME = "index_quotes_daily"

    def __init__(self, db: AsyncIOMotorDatabase | None = None) -> None:
        self._db = db

    @property
    def db(self) -> AsyncIOMotorDatabase:
        if self._db is None:
            self._db = get_mongo_db()
        return self._db

    async def ensure_index(self) -> None:
        """unique compound (symbol, date) + 普通 symbol."""
        try:
            await self.db[self.COLLECTION_NAME].create_index(
                [("symbol", 1), ("date", 1)], unique=True
            )
            await self.db[self.COLLECTION_NAME].create_index("symbol")
        except Exception as e:
            logger.debug(f"ensure_index on index_quotes_daily: {e}")

    async def sync_index_history(self, symbol: str = "000300", days: int = 365) -> dict[str, int]:
        """从 akshare 拉指数历史日 K，upsert 到 mongo.

        返回 `{symbol, total, inserted, updated, errors}` 状态字典。
        """
        end = date.today()
        start = end - timedelta(days=days)

        try:
            df = await asyncio.to_thread(self._fetch_index_hist, symbol, start, end)
        except Exception as e:
            logger.warning(f"sync_index_history({symbol}) akshare 失败: {e}")
            return {"symbol": symbol, "total": 0, "inserted": 0, "updated": 0, "errors": 1}

        if df is None or df.empty:
            logger.warning(f"sync_index_history({symbol}) akshare 返回空")
            return {"symbol": symbol, "total": 0, "inserted": 0, "updated": 0, "errors": 0}

        # 兼容 akshare 列名
        date_col = next(
            (c for c in ["日期", "trade_date", "date"] if c in df.columns), None
        )
        close_col = next((c for c in ["收盘", "close"] if c in df.columns), None)
        pct_col = next((c for c in ["涨跌幅", "pct_chg"] if c in df.columns), None)
        if not date_col or not close_col:
            logger.warning(
                f"sync_index_history 列名缺失: date={date_col}, close={close_col}"
            )
            return {"symbol": symbol, "total": 0, "inserted": 0, "updated": 0, "errors": 1}

        inserted = updated = errors = 0
        for _, row in df.iterrows():
            try:
                d_raw = row.get(date_col)
                if d_raw is None:
                    continue
                d_str = str(d_raw)[:10]  # YYYY-MM-DD
                close_v = float(row.get(close_col))
                pct_v = (
                    float(row.get(pct_col))
                    if pct_col and row.get(pct_col) is not None
                    else None
                )
                doc = {
                    "symbol": symbol,
                    "date": d_str,
                    "close": close_v,
                    "pct_chg": pct_v,
                }
                result = await self.db[self.COLLECTION_NAME].update_one(
                    {"symbol": symbol, "date": d_str},
                    {"$set": doc},
                    upsert=True,
                )
                if result.upserted_id is not None:
                    inserted += 1
                elif result.modified_count > 0:
                    updated += 1
            except Exception as e:
                errors += 1
                logger.debug(f"index upsert {symbol} 失败: {e}")

        total = len(df)
        logger.info(
            f"✅ sync_index_history({symbol}): "
            f"total={total} inserted={inserted} updated={updated} errors={errors}"
        )
        return {
            "symbol": symbol,
            "total": total,
            "inserted": inserted,
            "updated": updated,
            "errors": errors,
        }

    @staticmethod
    def _fetch_index_hist(symbol: str, start: date, end: date):
        """同步调用 akshare（被 asyncio.to_thread 包装）."""
        import akshare as ak
        return ak.index_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
        )

    async def get_index_returns(
        self, symbol: str = "000300", days: int = 60
    ) -> list[float]:
        """返回最近 N 个交易日的日收益率序列（小数，按 date 升序）.

        从 close 序列算 r_t = (C_t / C_{t-1}) - 1（不依赖 pct_chg 列，自算更稳）。
        """
        cursor = (
            self.db[self.COLLECTION_NAME]
            .find({"symbol": symbol}, {"date": 1, "close": 1, "_id": 0})
            .sort("date", -1)
            .limit(days + 1)  # 多拿一条算第一个 return
        )
        docs = await cursor.to_list(None)
        docs.sort(key=lambda d: d.get("date", ""))

        closes = [float(d.get("close", 0)) for d in docs if d.get("close") is not None]
        if len(closes) < 2:
            return []

        returns: list[float] = []
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            if prev <= 0:
                continue
            returns.append((closes[i] / prev) - 1.0)
        return returns

    async def get_index_dates(self, symbol: str = "000300", days: int = 60) -> list[str]:
        """返回与 get_index_returns 对齐的日期列表（升序）。"""
        cursor = (
            self.db[self.COLLECTION_NAME]
            .find({"symbol": symbol}, {"date": 1, "_id": 0})
            .sort("date", -1)
            .limit(days + 1)
        )
        docs = await cursor.to_list(None)
        dates = sorted(d.get("date", "") for d in docs if d.get("date"))
        # returns 长度 = closes - 1，所以 dates 也要去第一个
        return dates[1:] if dates else []


_index_data_service: IndexDataService | None = None


def get_index_data_service() -> IndexDataService:
    global _index_data_service
    if _index_data_service is None:
        _index_data_service = IndexDataService()
    return _index_data_service


__all__: list[Any] = ["IndexDataService", "get_index_data_service"]
