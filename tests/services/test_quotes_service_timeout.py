"""QuotesService 盘内 fetch 超时降级测试.

Root cause: 盘内冷启动时 `_ensure_cache` 直调 `_fetch_spot_akshare()`
（asyncio.to_thread）拉 ak.stock_zh_a_spot_em()，无超时无降级。akshare
偶尔慢到 30-110s，导致 /api/market/overview 阻塞 60-110s（lock 串行的并发
请求也跟着等同样时间）。

修复：盘内 fetch 加 wait_for 超时；超时/异常时
- 有旧 cache → 沿用 stale data（不更新 ts，下次 ttl 后再尝试）
- 无旧 cache → 降级到 mongo `market_quotes` 历史快照
"""

from __future__ import annotations

import asyncio
import time

import pytest


@pytest.mark.unit
def test_intraday_fetch_timeout_falls_back_to_mongo(monkeypatch) -> None:
    """盘内 cold start：akshare 慢于 timeout 时，降级到 mongo 快照."""
    from app.services.quotes_service import QuotesService

    def _slow_fetch(self):
        # 1s > timeout(0.5s) 即可触发 wait_for 超时；
        # 不写 30s 是因为 asyncio.to_thread 无法 cancel sync sleep，
        # 测试得等 thread 自己跑完才能退出。
        time.sleep(1.0)
        return {"000001": {"close": 10.0, "pct_chg": 0.5, "amount": 1.0e8}}

    monkeypatch.setattr(QuotesService, "_fetch_spot_akshare", _slow_fetch, raising=True)

    class _FakeCalendar:
        async def is_intraday_now(self) -> bool:
            return True

    monkeypatch.setattr(
        "app.services.trading_calendar_service.get_trading_calendar_service",
        lambda: _FakeCalendar(),
        raising=True,
    )

    async def _fake_load_mongo(self):
        return {"600000": {"close": 9.7, "pct_chg": -0.3, "amount": 5.0e7}}

    monkeypatch.setattr(QuotesService, "_load_cache_from_mongo", _fake_load_mongo, raising=True)

    async def _run() -> None:
        svc = QuotesService(ttl_seconds=30, fetch_timeout_seconds=0.5)
        t0 = time.monotonic()
        cache = await svc._ensure_cache()
        elapsed = time.monotonic() - t0
        assert elapsed < 5.0, f"timeout 降级失败，实际耗时 {elapsed:.2f}s"
        assert cache == {"600000": {"close": 9.7, "pct_chg": -0.3, "amount": 5.0e7}}, "cold + akshare 超时应降级到 mongo 快照"

    asyncio.run(_run())


@pytest.mark.unit
def test_intraday_fetch_timeout_serves_stale_cache(monkeypatch) -> None:
    """盘内：cache 已有 stale 内容时 fetch 超时，沿用 stale 不读 mongo."""
    from app.services.quotes_service import QuotesService

    def _slow_fetch(self):
        # 1s > timeout(0.5s) 即可触发 wait_for 超时；
        # 不写 30s 是因为 asyncio.to_thread 无法 cancel sync sleep，
        # 测试得等 thread 自己跑完才能退出。
        time.sleep(1.0)
        return {}

    monkeypatch.setattr(QuotesService, "_fetch_spot_akshare", _slow_fetch, raising=True)

    class _FakeCalendar:
        async def is_intraday_now(self) -> bool:
            return True

    monkeypatch.setattr(
        "app.services.trading_calendar_service.get_trading_calendar_service",
        lambda: _FakeCalendar(),
        raising=True,
    )

    mongo_called: list[int] = []

    async def _fake_load_mongo(self):
        mongo_called.append(1)
        return {}

    monkeypatch.setattr(QuotesService, "_load_cache_from_mongo", _fake_load_mongo, raising=True)

    async def _run() -> None:
        svc = QuotesService(ttl_seconds=30, fetch_timeout_seconds=0.5)
        svc._cache = {"600000": {"close": 9.0, "pct_chg": 0.1, "amount": 1.0e8}}
        svc._cache_ts = 0.0  # 强制 ttl 过期
        t0 = time.monotonic()
        cache = await svc._ensure_cache()
        elapsed = time.monotonic() - t0
        assert elapsed < 5.0, f"timeout 降级失败，实际耗时 {elapsed:.2f}s"
        assert cache == {"600000": {"close": 9.0, "pct_chg": 0.1, "amount": 1.0e8}}, "stale cache 路径应沿用旧数据"
        assert mongo_called == [], "stale cache 路径不应再读 mongo"
        assert svc._cache_ts == 0.0, "stale 降级不应刷新 _cache_ts（确保下次 ttl 后还会尝试）"

    asyncio.run(_run())


@pytest.mark.unit
def test_intraday_fetch_success_within_timeout(monkeypatch) -> None:
    """盘内：akshare 在 timeout 内返回时，正常更新 cache（不被 wait_for 影响）."""
    from app.services.quotes_service import QuotesService

    def _fast_fetch(self):
        return {"000001": {"close": 10.0, "pct_chg": 0.5, "amount": 1.0e8}}

    monkeypatch.setattr(QuotesService, "_fetch_spot_akshare", _fast_fetch, raising=True)

    class _FakeCalendar:
        async def is_intraday_now(self) -> bool:
            return True

    monkeypatch.setattr(
        "app.services.trading_calendar_service.get_trading_calendar_service",
        lambda: _FakeCalendar(),
        raising=True,
    )

    async def _run() -> None:
        svc = QuotesService(ttl_seconds=30, fetch_timeout_seconds=0.5)
        cache = await svc._ensure_cache()
        assert cache == {"000001": {"close": 10.0, "pct_chg": 0.5, "amount": 1.0e8}}
        assert svc._cache_ts > 0.0

    asyncio.run(_run())
