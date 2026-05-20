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


def _make_fake_mongo_db(facet_result: dict | None):
    """Build fake mongo db whose `["market_quotes"].aggregate(...).to_list(...)` returns
    a synthesized $facet result. None → empty aggregate (no docs match)."""

    class _FakeAggregateCursor:
        def __init__(self, result):
            self._result = result

        async def to_list(self, _length):
            return [self._result] if self._result is not None else []

    class _FakeCollection:
        def __init__(self, result):
            self._result = result
            self.aggregate_calls = []

        def aggregate(self, pipeline, **kwargs):
            self.aggregate_calls.append(pipeline)
            return _FakeAggregateCursor(self._result)

    class _FakeDB:
        def __init__(self, result):
            self._coll = _FakeCollection(result)

        def __getitem__(self, name):
            assert name == "market_quotes", f"unexpected collection access: {name}"
            return self._coll

    return _FakeDB(facet_result)


@pytest.mark.unit
def test_compute_overview_aggregates_from_mongo(monkeypatch) -> None:
    """capability data-truthfulness change 2026-05-20：compute_overview 改 mongo
    aggregate（不再用 cache），$facet 返回结果被正确映射。"""
    import app.services.market_overview_prewarm_service as mod
    from app.services.market_overview_prewarm_service import MarketOverviewPrewarmService

    # 模拟 mongo $facet 聚合结果
    facet_result = {
        "limit_up": [{"n": 1}],
        "limit_down": [{"n": 1}],
        "advance": [{"n": 2}],
        "decline": [{"n": 2}],
        "amount_sum": [{"_id": None, "sum": 1.0e8 + 5.0e7 + 2.0e8 + 8.0e7 + 3.0e7}],
        "max_updated": [{"_id": None, "ts": _utcnow_recent()}],
        "total": [{"n": 5}],
    }
    fake_db = _make_fake_mongo_db(facet_result)
    monkeypatch.setattr(mod, "get_mongo_db", lambda: fake_db, raising=True)

    async def _run() -> None:
        svc = MarketOverviewPrewarmService()
        result = await svc.compute_overview()
        assert result["limit_up"] == 1
        assert result["limit_down"] == 1
        assert result["advance"] == 2
        assert result["decline"] == 2
        assert result["total"] == 5
        expected_total = round((1.0e8 + 5.0e7 + 2.0e8 + 8.0e7 + 3.0e7) / 1e8, 0)
        assert result["amount_total"] == expected_total
        assert result["as_of_ts"] is not None
        assert result["staleness_seconds"] is not None
        # 验证 aggregate 调用的 pipeline 含 today filter
        pipeline = fake_db["market_quotes"].aggregate_calls[0]
        assert pipeline[0]["$match"]["updated_at"]["$gte"] is not None

    asyncio.run(_run())


@pytest.mark.unit
def test_compute_overview_empty_aggregate_returns_null_fields(monkeypatch) -> None:
    """capability data-truthfulness：当日无数据时 compute_overview MUST 返 null/0
    字段（不允许用历史数据填补）。"""
    import app.services.market_overview_prewarm_service as mod
    from app.services.market_overview_prewarm_service import MarketOverviewPrewarmService

    # $facet 返回所有桶都空
    facet_result = {
        "limit_up": [],
        "limit_down": [],
        "advance": [],
        "decline": [],
        "amount_sum": [],
        "max_updated": [],
        "total": [],
    }
    fake_db = _make_fake_mongo_db(facet_result)
    monkeypatch.setattr(mod, "get_mongo_db", lambda: fake_db, raising=True)

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

    asyncio.run(_run())


@pytest.mark.unit
def test_compute_overview_mongo_error_returns_null(monkeypatch) -> None:
    """mongo aggregate 抛异常时 compute_overview MUST 返 null/0，不抛."""
    import app.services.market_overview_prewarm_service as mod
    from app.services.market_overview_prewarm_service import MarketOverviewPrewarmService

    def _raise_mongo_db():
        raise RuntimeError("MongoDB 未初始化")

    monkeypatch.setattr(mod, "get_mongo_db", _raise_mongo_db, raising=True)

    async def _run() -> None:
        svc = MarketOverviewPrewarmService()
        result = await svc.compute_overview()
        assert result["limit_up"] is None
        assert result["total"] == 0

    asyncio.run(_run())


def _utcnow_recent():
    """Return a UTC datetime ~5s ago, for max_updated mock."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0)


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
