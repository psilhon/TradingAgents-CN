"""MarketOverviewPrewarmService: 盘中周期 prewarm + hot-path overview 聚合.

OpenSpec change `2026-05-20-data-truthfulness` Requirement (capability
realtime-trading-data-flow)：`/api/market/overview` hot-path 的约束在结果层
（p99 < 50ms + 聚合数据点 MUST 同属当前 CN tz 日历日），不在机制层。

compute_overview 改为对 mongo `market_quotes` 执行 `$match: updated_at >=
today_cn_start` + `$facet` aggregate —— 直接从 source of truth 算，避免
原 in-memory `QuotesService._cache.values()` 不过滤时间引入的跨日污染
（2026-05-20 撞过 28595 亿成交额事故：今日 + 昨日 + 10 天前 quote 一锅煮）。

实测本地 mongo 5500 doc aggregate ~20ms，远低于 SLO < 50ms。

prewarm_loop 体系保留，给其它消费者（quotes_service.get_quotes 等）维护
in-memory cache 时效；本入口不再依赖 cache。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from datetime import time as dtime
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.database import get_mongo_db
from app.services.quotes_service import get_quotes_service

logger = logging.getLogger(__name__)


def _today_cn_start_utc() -> datetime:
    """当前 CN tz 日历日 00:00:00 对应的 UTC datetime。

    mongo `market_quotes.updated_at` 是 UTC datetime，用这个边界做 $match。
    """
    tz = ZoneInfo(settings.TIMEZONE)
    now_cn = datetime.now(tz)
    start_cn = datetime.combine(now_cn.date(), dtime(0, 0, 0), tzinfo=tz)
    return start_cn.astimezone(timezone.utc)


class MarketOverviewPrewarmService:
    """盘中周期 prewarm（其它路径用 cache）+ hot-path overview 聚合（走 mongo）."""

    def __init__(
        self,
        interval_seconds: float = 30.0,
        fetch_timeout_seconds: float = 30.0,
    ) -> None:
        self._interval = interval_seconds
        self._fetch_timeout = fetch_timeout_seconds
        self._stopping = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def compute_overview(self) -> dict[str, Any]:
        """mongo `market_quotes` 当日 aggregate 全市场概况。hot-path 入口.

        约束（capability realtime-trading-data-flow + data-quality-gate）：
        - MUST 按 updated_at >= today_cn_start 过滤，禁止跨日累加
        - MUST p99 < 50ms（本地 mongo 单机 5500 doc 实测 ~20ms）
        - 当日无数据时 MUST 返回 null/0，MUST NOT 用历史填补
        """
        today_start = _today_cn_start_utc()

        try:
            db = get_mongo_db()
            pipeline = [
                {"$match": {"updated_at": {"$gte": today_start}}},
                {
                    "$facet": {
                        "limit_up": [
                            {"$match": {"pct_chg": {"$gte": 9.5}}},
                            {"$count": "n"},
                        ],
                        "limit_down": [
                            {"$match": {"pct_chg": {"$lte": -9.5}}},
                            {"$count": "n"},
                        ],
                        "advance": [
                            {"$match": {"pct_chg": {"$gt": 0}}},
                            {"$count": "n"},
                        ],
                        "decline": [
                            {"$match": {"pct_chg": {"$lt": 0}}},
                            {"$count": "n"},
                        ],
                        "amount_sum": [{"$group": {"_id": None, "sum": {"$sum": "$amount"}}}],
                        "max_updated": [{"$group": {"_id": None, "ts": {"$max": "$updated_at"}}}],
                        "total": [{"$count": "n"}],
                    }
                },
            ]
            agg = await db["market_quotes"].aggregate(pipeline).to_list(1)
        except Exception as e:
            logger.warning(f"compute_overview mongo aggregate 失败: {e!r}")
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

        if not agg:
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

        r = agg[0]
        total = (r["total"][0]["n"] if r.get("total") else 0) or 0
        # 当日无任何数据 → 全部字段返 null（pl. data-quality-gate Req 3：缺数据 MUST 不用历史填补）
        if total == 0:
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

        max_updated = r["max_updated"][0]["ts"] if r.get("max_updated") else None
        as_of_ts = max_updated.isoformat() if isinstance(max_updated, datetime) else None
        staleness = None
        if isinstance(max_updated, datetime):
            now_utc = datetime.now(timezone.utc)
            mu = max_updated if max_updated.tzinfo else max_updated.replace(tzinfo=timezone.utc)
            staleness = (now_utc - mu).total_seconds()

        amount_sum = r["amount_sum"][0]["sum"] if r.get("amount_sum") else 0.0

        return {
            "limit_up": (r["limit_up"][0]["n"] if r.get("limit_up") else 0) or 0,
            "limit_down": (r["limit_down"][0]["n"] if r.get("limit_down") else 0) or 0,
            "advance": (r["advance"][0]["n"] if r.get("advance") else 0) or 0,
            "decline": (r["decline"][0]["n"] if r.get("decline") else 0) or 0,
            "amount_total": round((amount_sum or 0.0) / 1e8, 0),
            "total": total,
            "as_of_ts": as_of_ts,
            "staleness_seconds": staleness,
        }

    # 保留 prewarm 体系给其它消费者（quotes_service.get_quotes 走 cache 路径等）维护
    # 时效。本入口 compute_overview 不再依赖 cache。

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


_service: MarketOverviewPrewarmService | None = None


def get_prewarm_service() -> MarketOverviewPrewarmService:
    global _service
    if _service is None:
        _service = MarketOverviewPrewarmService()
    return _service
