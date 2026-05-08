"""quote_freshness_monitor 测试.

OpenSpec change 2026-05-08-realtime-trading-data-flow Requirement
"GET /api/market/freshness MUST 暴露数据时效给 UI 角标" 关键 scenario：

1. 盘中 freshness 正常（staleness < threshold，breach=False）
2. 盘外不触发 breach（is_intraday=False，无论多 stale 都 breach=False）
3. 盘中 SLA 违反（staleness > threshold + 写 system_logs 事件）
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest


def _make_fake_db(latest_ts, system_logs_inserts: list[dict]):
    class _MarketQuotesColl:
        def find(self, query=None, projection=None):
            self._latest = latest_ts

            class _Cursor:
                def __init__(self, ts):
                    self._ts = ts

                def sort(self, *args, **kwargs):
                    return self

                def limit(self, n):
                    return self

                async def to_list(self, length):
                    if self._ts is None:
                        return []
                    return [{"updated_at": self._ts}]

            return _Cursor(latest_ts)

    class _SystemLogsColl:
        async def insert_one(self, doc):
            system_logs_inserts.append(doc)

            class _R:
                inserted_id = "fake-id"

            return _R()

    class _DB:
        def __getitem__(self, name):
            if name == "market_quotes":
                return _MarketQuotesColl()
            if name == "system_logs":
                return _SystemLogsColl()
            raise KeyError(name)

    return _DB()


def _make_fake_calendar(is_intraday: bool):
    class _C:
        async def is_intraday_now(self) -> bool:
            return is_intraday

    return _C()


@pytest.mark.unit
def test_get_freshness_intraday_normal(monkeypatch) -> None:
    """盘中 staleness < threshold → breach=False."""
    import app.services.quote_freshness_monitor as mod
    from app.services.quote_freshness_monitor import QuoteFreshnessMonitor

    # 5 秒前的 updated_at
    ts = datetime.now(timezone.utc) - timedelta(seconds=5)
    inserts: list[dict] = []
    monkeypatch.setattr(mod, "get_mongo_db", lambda: _make_fake_db(ts, inserts), raising=True)
    monkeypatch.setattr(
        "app.services.trading_calendar_service.get_trading_calendar_service",
        lambda: _make_fake_calendar(True),
        raising=True,
    )

    async def _run() -> None:
        m = QuoteFreshnessMonitor(sla_threshold_seconds=90)
        result = await m.get_freshness()
        assert result["as_of_ts"] is not None
        assert 4.0 < result["staleness_seconds"] < 8.0
        assert result["is_intraday"] is True
        assert result["sla_threshold_seconds"] == 90
        assert result["breach"] is False
        assert result["sync_running"] in (True, False)  # placeholder field

    asyncio.run(_run())


@pytest.mark.unit
def test_get_freshness_off_hours_not_breach(monkeypatch) -> None:
    """盘外即便 stale 12 小时也 breach=False."""
    import app.services.quote_freshness_monitor as mod
    from app.services.quote_freshness_monitor import QuoteFreshnessMonitor

    ts = datetime.now(timezone.utc) - timedelta(hours=12)
    inserts: list[dict] = []
    monkeypatch.setattr(mod, "get_mongo_db", lambda: _make_fake_db(ts, inserts), raising=True)
    monkeypatch.setattr(
        "app.services.trading_calendar_service.get_trading_calendar_service",
        lambda: _make_fake_calendar(False),
        raising=True,
    )

    async def _run() -> None:
        m = QuoteFreshnessMonitor(sla_threshold_seconds=90)
        result = await m.get_freshness()
        assert result["is_intraday"] is False
        assert result["breach"] is False  # 盘外即便 12h stale 也不 breach

    asyncio.run(_run())


@pytest.mark.unit
def test_check_and_log_breach_writes_system_logs(monkeypatch) -> None:
    """盘中 stale > threshold → check_and_log_breach 写一条 system_logs 事件."""
    import app.services.quote_freshness_monitor as mod
    from app.services.quote_freshness_monitor import QuoteFreshnessMonitor

    ts = datetime.now(timezone.utc) - timedelta(seconds=120)  # 2 min stale
    inserts: list[dict] = []
    monkeypatch.setattr(mod, "get_mongo_db", lambda: _make_fake_db(ts, inserts), raising=True)
    monkeypatch.setattr(
        "app.services.trading_calendar_service.get_trading_calendar_service",
        lambda: _make_fake_calendar(True),
        raising=True,
    )

    async def _run() -> None:
        m = QuoteFreshnessMonitor(sla_threshold_seconds=90)
        await m.check_and_log_breach()
        assert len(inserts) == 1
        doc = inserts[0]
        assert doc["kind"] == "quote_staleness_breach"
        assert doc["staleness_seconds"] > 90
        assert "timestamp" in doc

    asyncio.run(_run())


@pytest.mark.unit
def test_check_and_log_breach_off_hours_noop(monkeypatch) -> None:
    """盘外 stale 不写 system_logs（盘外 stale 是预期）."""
    import app.services.quote_freshness_monitor as mod
    from app.services.quote_freshness_monitor import QuoteFreshnessMonitor

    ts = datetime.now(timezone.utc) - timedelta(hours=12)
    inserts: list[dict] = []
    monkeypatch.setattr(mod, "get_mongo_db", lambda: _make_fake_db(ts, inserts), raising=True)
    monkeypatch.setattr(
        "app.services.trading_calendar_service.get_trading_calendar_service",
        lambda: _make_fake_calendar(False),
        raising=True,
    )

    async def _run() -> None:
        m = QuoteFreshnessMonitor(sla_threshold_seconds=90)
        await m.check_and_log_breach()
        assert len(inserts) == 0  # 盘外不写

    asyncio.run(_run())


@pytest.mark.unit
def test_get_freshness_no_data(monkeypatch) -> None:
    """market_quotes 空 → as_of_ts=None / staleness=None / breach=False."""
    import app.services.quote_freshness_monitor as mod
    from app.services.quote_freshness_monitor import QuoteFreshnessMonitor

    inserts: list[dict] = []
    monkeypatch.setattr(mod, "get_mongo_db", lambda: _make_fake_db(None, inserts), raising=True)
    monkeypatch.setattr(
        "app.services.trading_calendar_service.get_trading_calendar_service",
        lambda: _make_fake_calendar(True),
        raising=True,
    )

    async def _run() -> None:
        m = QuoteFreshnessMonitor(sla_threshold_seconds=90)
        result = await m.get_freshness()
        assert result["as_of_ts"] is None
        assert result["staleness_seconds"] is None
        assert result["breach"] is False  # 无数据不算 breach（避免空库时 spam alert）

    asyncio.run(_run())


@pytest.mark.unit
def test_get_freshness_monitor_singleton() -> None:
    from app.services.quote_freshness_monitor import get_freshness_monitor

    a = get_freshness_monitor()
    b = get_freshness_monitor()
    assert a is b
