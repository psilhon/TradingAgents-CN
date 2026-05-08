"""market_overview_prewarm_service: 盘中 prewarm in-memory 全市场快照.

OpenSpec change 2026-05-08-realtime-trading-data-flow Requirement
"market_overview_prewarm_service MUST 盘中周期 prewarm in-memory 全市场快照"
覆盖 4 个 scenario：
1. 盘中 prewarm 让 hot-path 永远命中 cache
2. 盘外 prewarm 静默
3. prewarm 与 mongo sync 解耦
4. in-memory cache 冷启动空时 hot-path 不阻塞
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest


def _make_fake_quotes_service(cache: dict[str, dict[str, Any]] | None = None, cache_ts: float = 0.0):
    """Build a fake QuotesService with controllable _cache / _cache_ts / _ensure_cache."""

    class _FakeQS:
        def __init__(self):
            self._cache = cache if cache is not None else {}
            self._cache_ts = cache_ts
            self.ensure_calls: int = 0

        async def _ensure_cache(self) -> dict[str, dict[str, Any]]:
            self.ensure_calls += 1
            return self._cache

    return _FakeQS()


def _make_fake_calendar(is_intraday: bool):
    class _FakeCalendar:
        async def is_intraday_now(self) -> bool:
            return is_intraday

    return _FakeCalendar()


@pytest.mark.unit
def test_compute_overview_aggregates_from_cache(monkeypatch) -> None:
    """Scenario 1: cache 有数据 → hot-path 聚合成功，带 as_of_ts/staleness_seconds."""
    import app.services.market_overview_prewarm_service as mod
    from app.services.market_overview_prewarm_service import MarketOverviewPrewarmService

    cache_ts = time.time() - 5  # 5s stale
    cache = {
        "000001": {"close": 12.34, "pct_chg": 9.6, "amount": 1.0e8},  # limit_up (>= 9.5)
        "000002": {"close": 8.0, "pct_chg": -9.7, "amount": 5.0e7},  # limit_down (<= -9.5)
        "600036": {"close": 35.10, "pct_chg": 1.2, "amount": 2.0e8},  # advance
        "600519": {"close": 1750.0, "pct_chg": -0.5, "amount": 8.0e7},  # decline
        "002594": {"close": 200.0, "pct_chg": 0.0, "amount": 3.0e7},  # neither (=0)
    }
    fake_qs = _make_fake_quotes_service(cache=cache, cache_ts=cache_ts)
    monkeypatch.setattr(mod, "get_quotes_service", lambda: fake_qs, raising=True)

    async def _run() -> None:
        svc = MarketOverviewPrewarmService()
        result = await svc.compute_overview()
        assert result["limit_up"] == 1
        assert result["limit_down"] == 1
        assert result["advance"] == 2  # 9.6, 1.2
        assert result["decline"] == 2  # -9.7, -0.5
        assert result["total"] == 5
        # 成交额合计单位为亿
        expected_total = round((1.0e8 + 5.0e7 + 2.0e8 + 8.0e7 + 3.0e7) / 1e8, 0)
        assert result["amount_total"] == expected_total
        assert result["as_of_ts"] is not None
        assert 4.0 < result["staleness_seconds"] < 10.0  # ≈ 5s
        # MUST NOT call _ensure_cache from hot-path
        assert fake_qs.ensure_calls == 0

    asyncio.run(_run())


@pytest.mark.unit
def test_compute_overview_empty_cache_returns_null_fields(monkeypatch) -> None:
    """Scenario 4: cache 空 → 返回 null 字段，不阻塞等待 prewarm."""
    import app.services.market_overview_prewarm_service as mod
    from app.services.market_overview_prewarm_service import MarketOverviewPrewarmService

    fake_qs = _make_fake_quotes_service(cache={}, cache_ts=0.0)
    monkeypatch.setattr(mod, "get_quotes_service", lambda: fake_qs, raising=True)

    async def _run() -> None:
        svc = MarketOverviewPrewarmService()
        result = await svc.compute_overview()
        assert result["limit_up"] is None
        assert result["limit_down"] is None
        assert result["advance"] is None
        assert result["decline"] is None
        assert result["amount_total"] is None
        assert result["total"] == 0
        assert result["as_of_ts"] is None
        assert result["staleness_seconds"] is None
        # MUST NOT trigger _ensure_cache（不阻塞）
        assert fake_qs.ensure_calls == 0

    asyncio.run(_run())


@pytest.mark.unit
def test_prewarm_loop_intraday_calls_ensure_cache(monkeypatch) -> None:
    """Scenario 1: 盘中一轮 prewarm → 调 QuotesService._ensure_cache 一次."""
    import app.services.market_overview_prewarm_service as mod
    from app.services.market_overview_prewarm_service import MarketOverviewPrewarmService

    fake_qs = _make_fake_quotes_service(cache={}, cache_ts=0.0)
    monkeypatch.setattr(mod, "get_quotes_service", lambda: fake_qs, raising=True)
    monkeypatch.setattr(
        "app.services.trading_calendar_service.get_trading_calendar_service",
        lambda: _make_fake_calendar(is_intraday=True),
        raising=True,
    )

    async def _run() -> None:
        svc = MarketOverviewPrewarmService(interval_seconds=0.05, fetch_timeout_seconds=1.0)
        await svc._prewarm_once()
        assert fake_qs.ensure_calls == 1

    asyncio.run(_run())


@pytest.mark.unit
def test_prewarm_loop_off_hours_skips(monkeypatch) -> None:
    """Scenario 2: 盘外一轮 prewarm → 不调 _ensure_cache."""
    import app.services.market_overview_prewarm_service as mod
    from app.services.market_overview_prewarm_service import MarketOverviewPrewarmService

    fake_qs = _make_fake_quotes_service(cache={}, cache_ts=0.0)
    monkeypatch.setattr(mod, "get_quotes_service", lambda: fake_qs, raising=True)
    monkeypatch.setattr(
        "app.services.trading_calendar_service.get_trading_calendar_service",
        lambda: _make_fake_calendar(is_intraday=False),
        raising=True,
    )

    async def _run() -> None:
        svc = MarketOverviewPrewarmService(interval_seconds=0.05, fetch_timeout_seconds=1.0)
        await svc._prewarm_once()
        assert fake_qs.ensure_calls == 0

    asyncio.run(_run())


@pytest.mark.unit
def test_prewarm_loop_timeout_does_not_crash(monkeypatch) -> None:
    """Scenario 3 (decoupling): prewarm 超时不抛异常，loop 可继续."""
    import app.services.market_overview_prewarm_service as mod
    from app.services.market_overview_prewarm_service import MarketOverviewPrewarmService

    class _SlowQS:
        def __init__(self):
            self._cache = {}
            self._cache_ts = 0.0
            self.ensure_calls = 0

        async def _ensure_cache(self):
            self.ensure_calls += 1
            await asyncio.sleep(2.0)
            return {}

    slow_qs = _SlowQS()
    monkeypatch.setattr(mod, "get_quotes_service", lambda: slow_qs, raising=True)
    monkeypatch.setattr(
        "app.services.trading_calendar_service.get_trading_calendar_service",
        lambda: _make_fake_calendar(is_intraday=True),
        raising=True,
    )

    async def _run() -> None:
        svc = MarketOverviewPrewarmService(interval_seconds=0.05, fetch_timeout_seconds=0.1)
        # MUST NOT raise
        await svc._prewarm_once()
        assert slow_qs.ensure_calls == 1  # 调用了一次但被 wait_for 取消

    asyncio.run(_run())


@pytest.mark.unit
def test_get_prewarm_service_singleton() -> None:
    from app.services.market_overview_prewarm_service import get_prewarm_service

    a = get_prewarm_service()
    b = get_prewarm_service()
    assert a is b
