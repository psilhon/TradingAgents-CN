"""QuoteFreshnessMonitor: 实时行情数据时效监控.

OpenSpec change `2026-05-08-realtime-trading-data-flow` Requirement
"GET /api/market/freshness MUST 暴露数据时效给 UI 角标"。

提供：
- get_freshness() → 当前 mongo `market_quotes.updated_at` max + staleness
  + is_intraday + breach 标志，给 UI 角标渲染（绿/黄/红）
- check_and_log_breach() → 盘中超过 SLA（默认 90s = 3 个 30s sync 周期）时
  写 system_logs `kind="quote_staleness_breach"` 事件 + logger.warning
- monitor_loop() lifecycle task：盘中 60s 一轮 check（盘外不查）

盘外（trading-calendar.is_intraday_now() == False）即便 12h stale 也
NOT breach（盘外不刷新是预期，不是事故）。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.database import get_mongo_db

logger = logging.getLogger(__name__)


class QuoteFreshnessMonitor:
    """市场行情数据时效监控."""

    BREACH_KIND = "quote_staleness_breach"

    def __init__(
        self,
        sla_threshold_seconds: float = 90.0,
        check_interval_seconds: float = 60.0,
    ) -> None:
        self._sla = sla_threshold_seconds
        self._interval = check_interval_seconds
        self._stopping = asyncio.Event()
        self._task: Optional[asyncio.Task] = None

    async def _query_latest_updated_at(self) -> Optional[datetime]:
        """查询 mongo `market_quotes.updated_at` 的 max."""
        db = get_mongo_db()
        try:
            cursor = db["market_quotes"].find({}, {"_id": 0, "updated_at": 1}).sort("updated_at", -1).limit(1)
            docs = await cursor.to_list(1)
            if not docs:
                return None
            ts = docs[0].get("updated_at")
            if ts is None:
                return None
            if isinstance(ts, datetime):
                return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
            return None
        except Exception as e:
            logger.warning(f"QuoteFreshnessMonitor: 查询 latest updated_at 失败 {e!r}")
            return None

    async def _is_intraday(self) -> bool:
        try:
            from app.services.trading_calendar_service import get_trading_calendar_service

            return bool(await get_trading_calendar_service().is_intraday_now())
        except Exception as e:
            logger.debug(f"QuoteFreshnessMonitor: is_intraday_now 异常 {e!r}")
            return False

    async def _is_sync_running(self) -> bool:
        """prewarm task 是否在跑（最简代理：lifecycle task 状态）."""
        try:
            from app.services.market_overview_prewarm_service import get_prewarm_service

            svc = get_prewarm_service()
            t = getattr(svc, "_task", None)
            return bool(t is not None and not t.done())
        except Exception:
            return False

    async def get_freshness(self) -> dict[str, Any]:
        """返回时效摘要 dict（hot-path 端点用）.

        字段：
            as_of_ts: str | None ISO8601
            staleness_seconds: float | None
            is_intraday: bool
            last_successful_sync_at: str | None  (现取 == as_of_ts)
            sync_running: bool
            sla_threshold_seconds: float
            breach: bool
        """
        latest = await self._query_latest_updated_at()
        is_intraday = await self._is_intraday()
        sync_running = await self._is_sync_running()

        if latest is None:
            return {
                "as_of_ts": None,
                "staleness_seconds": None,
                "is_intraday": is_intraday,
                "last_successful_sync_at": None,
                "sync_running": sync_running,
                "sla_threshold_seconds": self._sla,
                "breach": False,  # 无数据不算 breach（避免空库 spam）
            }

        now = datetime.now(timezone.utc)
        staleness = (now - latest).total_seconds()
        as_of_iso = latest.isoformat()
        breach = is_intraday and staleness > self._sla

        return {
            "as_of_ts": as_of_iso,
            "staleness_seconds": staleness,
            "is_intraday": is_intraday,
            "last_successful_sync_at": as_of_iso,
            "sync_running": sync_running,
            "sla_threshold_seconds": self._sla,
            "breach": breach,
        }

    async def check_and_log_breach(self) -> None:
        """周期 check：盘中 stale > SLA 时写 system_logs + logger.warning."""
        info = await self.get_freshness()
        if not info["breach"]:
            return

        # 盘中 SLA 违反
        message = f"market_quotes 数据时效超过 SLA：staleness={info['staleness_seconds']:.1f}s > {info['sla_threshold_seconds']}s"
        logger.warning(f"⚠️ QuoteFreshnessMonitor: {message}")
        try:
            db = get_mongo_db()
            await db["system_logs"].insert_one(
                {
                    "kind": self.BREACH_KIND,
                    "timestamp": datetime.now(timezone.utc),
                    "as_of_ts": info["as_of_ts"],
                    "staleness_seconds": info["staleness_seconds"],
                    "sla_threshold_seconds": info["sla_threshold_seconds"],
                    "is_intraday": info["is_intraday"],
                    "sync_running": info["sync_running"],
                    "message": message,
                }
            )
        except Exception as e:
            logger.warning(f"QuoteFreshnessMonitor: 写 system_logs 失败 {e!r}")

    async def monitor_loop(self) -> None:
        """Lifecycle background task：每 interval 秒一轮 check_and_log_breach."""
        logger.info(f"QuoteFreshnessMonitor: 启动 monitor_loop, interval={self._interval}s")
        try:
            while not self._stopping.is_set():
                try:
                    await self.check_and_log_breach()
                except Exception as e:
                    logger.warning(f"QuoteFreshnessMonitor: check 异常 {e!r}")
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            logger.info("QuoteFreshnessMonitor: monitor_loop 被取消")
            raise

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopping.clear()
            self._task = asyncio.create_task(self.monitor_loop(), name="quote_freshness_monitor")

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass


_monitor: Optional[QuoteFreshnessMonitor] = None


def get_freshness_monitor() -> QuoteFreshnessMonitor:
    global _monitor
    if _monitor is None:
        _monitor = QuoteFreshnessMonitor()
    return _monitor
