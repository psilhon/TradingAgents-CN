"""MarketOverviewPrewarmService: 盘中周期 prewarm in-memory 全市场快照.

OpenSpec change `2026-05-08-realtime-trading-data-flow` 的全市场聚合
hot-path：5500+ 只 A 股的涨跌停 / 成交额聚合统计 不能从 mongo `market_quotes`
来（既有 `paper-realtime-quotes` capability 锁了它的写入范围在 < 100 codes），
所以走 in-memory `QuotesService._cache`。

为了让 hot-path 永远命中 cache、不被 akshare 慢调用阻塞用户请求，本服务
提供 lifecycle background task `prewarm_loop`：盘中每 N 秒异步调
`QuotesService._ensure_cache()` 让内存快照保持 fresh；akshare 慢只阻塞
后台 task，不阻塞 router。

`compute_overview()` 是 hot-path 入口，直接读 `QuotesService._cache` 聚合。
cache 空（首启 / prewarm 还未跑过任何一轮）时返回 null 字段——MUST NOT
阻塞等待。
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from datetime import datetime, timezone
from typing import Any, Optional

from app.services.quotes_service import get_quotes_service

logger = logging.getLogger(__name__)


def _ts_to_iso(ts: float) -> Optional[str]:
    if ts <= 0:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class MarketOverviewPrewarmService:
    """盘中周期 prewarm + hot-path overview 聚合."""

    def __init__(
        self,
        interval_seconds: float = 30.0,
        fetch_timeout_seconds: float = 30.0,
    ) -> None:
        self._interval = interval_seconds
        self._fetch_timeout = fetch_timeout_seconds
        self._stopping = asyncio.Event()
        self._task: Optional[asyncio.Task] = None

    async def compute_overview(self) -> dict[str, Any]:
        """从 in-memory `QuotesService._cache` 聚合全市场概况。hot-path 入口.

        cache 空时返回 nullable 字段（MUST NOT 阻塞触发上游 fetch）.
        """
        qs = get_quotes_service()
        cache = qs._cache
        cache_ts = qs._cache_ts

        if not cache:
            return {
                "limit_up": None,
                "limit_down": None,
                "advance": None,
                "decline": None,
                "amount_total": None,
                "total": 0,
                "as_of_ts": None,
                "staleness_seconds": None,
            }

        limit_up = limit_down = advance = decline = 0
        amount_total: float = 0.0
        for q in cache.values():
            pct = q.get("pct_chg")
            amt = q.get("amount")
            if pct is not None and not (isinstance(pct, float) and math.isnan(pct)):
                if pct >= 9.5:
                    limit_up += 1
                elif pct <= -9.5:
                    limit_down += 1
                if pct > 0:
                    advance += 1
                elif pct < 0:
                    decline += 1
            if amt is not None and not (isinstance(amt, float) and math.isnan(amt)):
                amount_total += amt

        return {
            "limit_up": limit_up,
            "limit_down": limit_down,
            "advance": advance,
            "decline": decline,
            "amount_total": round(amount_total / 1e8, 0),
            "total": len(cache),
            "as_of_ts": _ts_to_iso(cache_ts),
            "staleness_seconds": (time.time() - cache_ts) if cache_ts > 0 else None,
        }

    async def _prewarm_once(self) -> None:
        """单轮 prewarm：盘内调 _ensure_cache + 超时降级；盘外跳过."""
        try:
            from app.services.trading_calendar_service import get_trading_calendar_service

            if not await get_trading_calendar_service().is_intraday_now():
                logger.debug("MarketOverviewPrewarm: 盘外，跳过 prewarm")
                return
        except Exception as e:
            logger.debug(f"trading_calendar guard 失败，保守跳过 prewarm: {e}")
            return

        qs = get_quotes_service()
        try:
            await asyncio.wait_for(qs._ensure_cache(), timeout=self._fetch_timeout)
            logger.debug(f"MarketOverviewPrewarm: 完成 prewarm，cache={len(qs._cache)} 条")
        except asyncio.TimeoutError:
            logger.warning(f"MarketOverviewPrewarm: prewarm 超时 (>{self._fetch_timeout}s)，下一轮再尝试")
        except Exception as e:
            logger.warning(f"MarketOverviewPrewarm: prewarm 异常 {e!r}，下一轮再尝试")

    async def prewarm_loop(self) -> None:
        """Lifecycle background task：每 interval 秒一轮 _prewarm_once。

        在 app/main.py lifespan 启动时 asyncio.create_task() 注册；shutdown 时
        cancel + await（_stopping 提供 graceful 退出信号）。
        """
        logger.info(f"MarketOverviewPrewarm: 启动 prewarm_loop, interval={self._interval}s, fetch_timeout={self._fetch_timeout}s")
        try:
            while not self._stopping.is_set():
                await self._prewarm_once()
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            logger.info("MarketOverviewPrewarm: prewarm_loop 被取消")
            raise

    def start(self) -> None:
        """启动 lifecycle task（幂等）."""
        if self._task is None or self._task.done():
            self._stopping.clear()
            self._task = asyncio.create_task(self.prewarm_loop(), name="market_overview_prewarm")

    async def stop(self) -> None:
        """优雅停止：set _stopping + cancel + await 等待退出."""
        self._stopping.set()
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass


_service: Optional[MarketOverviewPrewarmService] = None


def get_prewarm_service() -> MarketOverviewPrewarmService:
    global _service
    if _service is None:
        _service = MarketOverviewPrewarmService()
    return _service
