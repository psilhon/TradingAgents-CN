"""
TradingCalendarService — A 股交易日历 mongo 缓存 + 项目铁律「自动刷新仅在
A 股交易日盘中执行」的统一判断入口。

OpenSpec change: trading-calendar
Spec: openspec/specs/trading-calendar/spec.md (after archive)

设计要点：
- 数据源：akshare `tool_trade_date_hist_sina()` 一次拉 1990–下一年所有交易日
- 存储：mongo `trading_calendar` 仅存交易日（不存非交易日）。是否交易日 =
  collection 是否存在该 date 文档
- API：
  - `is_trading_day(d)` 异步，带 LRU 内存缓存
  - `is_intraday_now()` 组合 is_trading_day + 时段判断（9:30–11:30 / 13:00–15:00）
  - `sync_year(year)` 拉年度日历入库
- 复用 `app/utils/trading_time.is_strict_trading_time` 做时段判断（已存在），
  本 service 只负责加节假日识别
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time as dtime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.database import get_mongo_db

logger = logging.getLogger(__name__)


class TradingCalendarService:
    """A 股交易日历 mongo 缓存 + 综合判断服务。"""

    COLLECTION_NAME = "trading_calendar"

    # 内存缓存最大条数 — 超出后 FIFO evict 最早 256 条（保守策略）
    _CACHE_MAX = 2048
    _CACHE_EVICT_BATCH = 256

    def __init__(self, db: AsyncIOMotorDatabase | None = None) -> None:
        self._db = db
        self._tz = ZoneInfo(settings.TIMEZONE)
        # date_str -> bool 内存缓存（仅在 mongo 已 sync 该年数据时填充）
        self._cache: dict[str, bool] = {}

    @property
    def db(self) -> AsyncIOMotorDatabase:
        if self._db is None:
            self._db = get_mongo_db()
        return self._db

    async def ensure_index(self) -> None:
        """启动时 ensure unique index on `date` + 普通 index on `year`."""
        try:
            await self.db[self.COLLECTION_NAME].create_index("date", unique=True)
            await self.db[self.COLLECTION_NAME].create_index("year")
        except Exception as e:
            logger.debug(f"ensure_index on trading_calendar: {e}")

    async def sync_year(self, year: int) -> dict[str, int]:
        """从 akshare 拉年度交易日历 upsert 到 mongo。

        akshare `tool_trade_date_hist_sina()` 返回单列 'trade_date'，覆盖
        1990–下一年所有交易日。本方法过滤指定 year 后 upsert。

        返回 `{year, total, inserted, updated}` 状态字典。失败时保留旧数据，
        log warning 不抛。
        """
        import asyncio

        try:
            df = await asyncio.to_thread(self._fetch_calendar)
        except Exception as e:
            logger.warning(f"TradingCalendar.sync_year({year}) akshare 调用失败: {e}")
            return {"year": year, "total": 0, "inserted": 0, "updated": 0}

        if df is None or df.empty:
            logger.warning(f"TradingCalendar.sync_year({year}) akshare 返回空")
            return {"year": year, "total": 0, "inserted": 0, "updated": 0}

        # 过滤本年 + 转 str
        target_dates: list[str] = []
        for raw in df["trade_date"]:
            d_str = str(raw).strip()[:10]  # YYYY-MM-DD
            if d_str.startswith(f"{year}-"):
                target_dates.append(d_str)

        if not target_dates:
            logger.warning(f"TradingCalendar.sync_year({year}) akshare 不含 {year} 数据")
            return {"year": year, "total": 0, "inserted": 0, "updated": 0}

        inserted = updated = 0
        for d_str in target_dates:
            try:
                result = await self.db[self.COLLECTION_NAME].update_one(
                    {"date": d_str},
                    {"$set": {"date": d_str, "year": year}},
                    upsert=True,
                )
                if result.upserted_id is not None:
                    inserted += 1
                elif result.modified_count > 0:
                    updated += 1
            except Exception as e:
                logger.warning(f"TradingCalendar.sync_year upsert {d_str} 失败: {e}")

        # 同步后清掉内存缓存（新数据可能影响 is_trading_day 结果）
        self._cache.clear()

        logger.info(
            f"✅ TradingCalendar.sync_year({year}): "
            f"total={len(target_dates)} inserted={inserted} updated={updated}"
        )
        return {
            "year": year,
            "total": len(target_dates),
            "inserted": inserted,
            "updated": updated,
        }

    @staticmethod
    def _fetch_calendar():
        """同步调用 akshare（被 asyncio.to_thread 包装）."""
        import akshare as ak
        return ak.tool_trade_date_hist_sina()

    async def is_trading_day(self, d: date | None = None) -> bool:
        """查询指定日期是否交易日。默认 today (按 settings.TIMEZONE)."""
        if d is None:
            d = datetime.now(self._tz).date()

        d_str = d.isoformat()

        # 内存缓存命中
        if d_str in self._cache:
            return self._cache[d_str]

        # mongo 查询
        try:
            doc = await self.db[self.COLLECTION_NAME].find_one({"date": d_str})
            is_trading = doc is not None
            # 仅在 mongo 已 sync 该年数据时缓存（避免启动初期 sync 还未完成时
            # 把"暂时为空"误缓存成 false）
            if await self._has_data_for_year(d.year):
                self._set_cache(d_str, is_trading)
            return is_trading
        except Exception as e:
            logger.warning(f"is_trading_day({d_str}) 查询失败: {e}")
            # fallback：保守判断 weekday() < 5（不识别节假日，但比抛错好）
            return d.weekday() < 5

    async def _has_data_for_year(self, year: int) -> bool:
        """检查 mongo 是否有指定年份的数据。"""
        cnt = await self.db[self.COLLECTION_NAME].count_documents({"year": year})
        return cnt > 0

    def _set_cache(self, d_str: str, value: bool) -> None:
        """FIFO 限制：超过 _CACHE_MAX 条时 evict 最早 _CACHE_EVICT_BATCH 条。"""
        if len(self._cache) >= self._CACHE_MAX:
            for k in list(self._cache.keys())[: self._CACHE_EVICT_BATCH]:
                self._cache.pop(k, None)
        self._cache[d_str] = value

    async def is_intraday_now(self) -> bool:
        """综合判断：当前是否「A 股交易日 + 盘中时段」.

        盘中时段定义（与 app/utils/trading_time.is_strict_trading_time 对齐）：
        - 上午：9:30–11:30
        - 下午：13:00–15:00

        非盘中时段（午休 11:30–13:00 / 早晚 / 周末 / 节假日）返回 False。
        """
        now = datetime.now(self._tz)

        # 1. 节假日 / 周末判断
        if not await self.is_trading_day(now.date()):
            return False

        # 2. 盘中时段判断（含午休排除）
        t = now.time()
        morning_start = dtime(9, 30)
        morning_end = dtime(11, 30)
        afternoon_start = dtime(13, 0)
        afternoon_end = dtime(15, 0)

        return (morning_start <= t <= morning_end) or (
            afternoon_start <= t <= afternoon_end
        )

    async def get_today_status(self) -> dict[str, Any]:
        """前端使用：返回今日完整状态."""
        now = datetime.now(self._tz)
        today = now.date()
        is_td = await self.is_trading_day(today)
        is_intra = await self.is_intraday_now()

        # 找下一个交易日（最多向前查 30 天）
        next_td: str | None = None
        for i in range(1, 31):
            d = today + timedelta(days=i)
            if await self.is_trading_day(d):
                next_td = d.isoformat()
                break

        return {
            "date": today.isoformat(),
            "is_trading_day": is_td,
            "is_intraday": is_intra,
            "next_trading_day": next_td,
        }


_trading_calendar_service: TradingCalendarService | None = None


def get_trading_calendar_service() -> TradingCalendarService:
    """Module-level singleton accessor."""
    global _trading_calendar_service
    if _trading_calendar_service is None:
        _trading_calendar_service = TradingCalendarService()
    return _trading_calendar_service


__all__: list[Any] = [
    "TradingCalendarService",
    "get_trading_calendar_service",
]
