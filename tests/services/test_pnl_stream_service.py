"""pnl_stream_service: 盘中 PnL 服务端聚合 + 增量推送测试.

OpenSpec change 2026-05-08-realtime-trading-data-flow Requirement
"PnL stream service MUST 盘中每 ≤ 3s 推送变化的 PnL"。

3 个 scenario：
- 盘中变化才 publish（diff > 0.01）
- 盘外 noop（不算 PnL 不 publish）
- as_of_ts = min(positions.last_price_as_of)，全 None 时为 None
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest


def _make_async_iter(items):
    class _Cursor:
        def __init__(self, items):
            self._items = list(items)

        def __aiter__(self):
            self._iter = iter(self._items)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration as e:
                raise StopAsyncIteration from e

    return _Cursor(items)


def _make_fake_db(account: dict, positions: list[dict]):
    class _Coll:
        def __init__(self, name: str):
            self.name = name

        async def find_one(self, query, projection=None):
            if self.name == "paper_accounts":
                return account
            return None

        def find(self, query=None, projection=None):
            if self.name == "paper_positions":
                return _make_async_iter(positions)
            return _make_async_iter([])

        async def distinct(self, field, query=None):
            if self.name == "paper_positions" and field == "user_id":
                return list({p["user_id"] for p in positions})
            return []

    class _DB:
        def __getitem__(self, name):
            return _Coll(name)

    return _DB()


def _make_fake_reader(quotes: dict[str, dict[str, Any]], as_of_ts: str | None):
    class _Reader:
        async def read_quotes(self, codes):
            return {
                "quotes": {
                    c: quotes.get(
                        c,
                        {
                            "close": None,
                            "pct_chg": None,
                            "amount": None,
                            "last_price_as_of": None,
                        },
                    )
                    for c in codes
                },
                "as_of_ts": as_of_ts,
            }

    return _Reader()


class _FakeRedis:
    def __init__(self):
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, payload: str):
        self.published.append((channel, payload))


@pytest.mark.unit
def test_compute_pnl_formula(monkeypatch) -> None:
    """compute_pnl(user_id)：unrealized + equity + as_of_ts 公式正确."""
    import app.services.pnl_stream_service as mod
    from app.services.pnl_stream_service import PnLStreamService

    account = {
        "user_id": "user_A",
        "cash": {"CNY": 100_000.0, "HKD": 0.0, "USD": 0.0},
        "realized_pnl": {"CNY": 500.0, "HKD": 0.0, "USD": 0.0},
    }
    positions = [
        {"user_id": "user_A", "code": "000001", "market": "CN", "quantity": 1000, "avg_cost": 10.0},
        {"user_id": "user_A", "code": "600036", "market": "CN", "quantity": 500, "avg_cost": 30.0},
    ]
    monkeypatch.setattr(mod, "get_mongo_db", lambda: _make_fake_db(account, positions), raising=True)
    monkeypatch.setattr(
        mod,
        "get_quote_snapshot_reader",
        lambda: _make_fake_reader(
            {
                "000001": {
                    "close": 12.0,
                    "pct_chg": 0.5,
                    "amount": 1.0e8,
                    "last_price_as_of": "2026-05-08T09:30:00+00:00",
                },
                "600036": {
                    "close": 35.0,
                    "pct_chg": -0.3,
                    "amount": 8.0e7,
                    "last_price_as_of": "2026-05-08T09:30:30+00:00",
                },
            },
            as_of_ts="2026-05-08T09:30:00+00:00",
        ),
        raising=True,
    )

    async def _run() -> None:
        svc = PnLStreamService()
        pnl = await svc.compute_pnl("user_A")
        # unrealized = (12-10)*1000 + (35-30)*500 = 2000 + 2500 = 4500
        assert pnl["total_unrealized"] == 4500.0
        # equity = cash + Σ qty*close = 100000 + 12*1000 + 35*500 = 100000 + 12000 + 17500
        assert pnl["total_equity"] == 129_500.0
        assert pnl["total_realized"] == 500.0
        # as_of_ts = min（最 stale）
        assert pnl["as_of_ts"] == "2026-05-08T09:30:00+00:00"
        assert len(pnl["positions"]) == 2

    asyncio.run(_run())


@pytest.mark.unit
def test_compute_pnl_missing_quotes_yields_null_as_of(monkeypatch) -> None:
    """positions 全缺 quotes 时：as_of_ts = None；unrealized 用 0 占位."""
    import app.services.pnl_stream_service as mod
    from app.services.pnl_stream_service import PnLStreamService

    account = {
        "user_id": "user_A",
        "cash": {"CNY": 100_000.0, "HKD": 0.0, "USD": 0.0},
        "realized_pnl": {"CNY": 0.0},
    }
    positions = [
        {"user_id": "user_A", "code": "000001", "market": "CN", "quantity": 1000, "avg_cost": 10.0},
    ]
    monkeypatch.setattr(mod, "get_mongo_db", lambda: _make_fake_db(account, positions), raising=True)
    monkeypatch.setattr(mod, "get_quote_snapshot_reader", lambda: _make_fake_reader({}, as_of_ts=None), raising=True)

    async def _run() -> None:
        svc = PnLStreamService()
        pnl = await svc.compute_pnl("user_A")
        assert pnl["as_of_ts"] is None
        assert pnl["total_unrealized"] == 0.0
        # equity = cash 因为 close = None 时 mkt_value=0
        assert pnl["total_equity"] == 100_000.0

    asyncio.run(_run())


@pytest.mark.unit
def test_publish_only_on_significant_diff(monkeypatch) -> None:
    """diff abs <= 0.01 不 publish；> 0.01 才 publish."""
    import app.services.pnl_stream_service as mod
    from app.services.pnl_stream_service import PnLStreamService

    account = {
        "user_id": "user_A",
        "cash": {"CNY": 100_000.0},
        "realized_pnl": {"CNY": 0.0},
    }
    positions = [
        {"user_id": "user_A", "code": "000001", "market": "CN", "quantity": 1000, "avg_cost": 10.0},
    ]

    fake_redis = _FakeRedis()
    monkeypatch.setattr(mod, "get_redis_client", lambda: fake_redis, raising=True)
    monkeypatch.setattr(mod, "get_mongo_db", lambda: _make_fake_db(account, positions), raising=True)

    # 强制盘内（避免 test 时段 dependent flakiness——trading_calendar 默认会
    # 走 mongo 查询，未 init 时 fallback 到 weekday + 时段，盘外时段会让本
    # test fail）
    class _IntradayCalendar:
        async def is_intraday_now(self) -> bool:
            return True

    monkeypatch.setattr(
        "app.services.trading_calendar_service.get_trading_calendar_service",
        lambda: _IntradayCalendar(),
        raising=True,
    )

    # 第一轮：close=12.00 → unrealized=2000, equity=112000
    monkeypatch.setattr(
        mod,
        "get_quote_snapshot_reader",
        lambda: _make_fake_reader(
            {
                "000001": {
                    "close": 12.00,
                    "pct_chg": 0.5,
                    "amount": 1.0e8,
                    "last_price_as_of": "2026-05-08T09:30:00+00:00",
                }
            },
            as_of_ts="2026-05-08T09:30:00+00:00",
        ),
        raising=True,
    )

    async def _run() -> None:
        svc = PnLStreamService()

        # 第一轮：从未 publish 过，必然 publish
        await svc.scan_and_publish_once()
        assert len(fake_redis.published) == 1
        ch1, p1 = fake_redis.published[0]
        assert ch1 == "channel:pnl:user_A"
        payload1 = json.loads(p1)
        assert payload1["total_unrealized"] == 2000.0

        fake_redis.published.clear()

        # 第二轮：close 完全相同 → diff = 0，不 publish
        await svc.scan_and_publish_once()
        assert len(fake_redis.published) == 0, "无变化不应 publish"

        # 第三轮：close 升 0.001 → unrealized diff = 1.0 > 0.01 → publish
        monkeypatch.setattr(
            mod,
            "get_quote_snapshot_reader",
            lambda: _make_fake_reader(
                {
                    "000001": {
                        "close": 12.001,
                        "pct_chg": 0.5,
                        "amount": 1.0e8,
                        "last_price_as_of": "2026-05-08T09:30:30+00:00",
                    }
                },
                as_of_ts="2026-05-08T09:30:30+00:00",
            ),
            raising=True,
        )
        await svc.scan_and_publish_once()
        assert len(fake_redis.published) == 1

    asyncio.run(_run())


@pytest.mark.unit
def test_off_hours_noop(monkeypatch) -> None:
    """盘外 scan_and_publish_once 不算 PnL 不 publish."""
    import app.services.pnl_stream_service as mod
    from app.services.pnl_stream_service import PnLStreamService

    fake_redis = _FakeRedis()
    monkeypatch.setattr(mod, "get_redis_client", lambda: fake_redis, raising=True)

    # 盘外 calendar
    class _OffHoursCalendar:
        async def is_intraday_now(self) -> bool:
            return False

    monkeypatch.setattr(
        "app.services.trading_calendar_service.get_trading_calendar_service",
        lambda: _OffHoursCalendar(),
        raising=True,
    )

    db_called = []

    def _spy_db():
        db_called.append(1)
        return _make_fake_db({}, [])

    monkeypatch.setattr(mod, "get_mongo_db", _spy_db, raising=True)

    async def _run() -> None:
        svc = PnLStreamService()
        await svc.scan_and_publish_once()
        assert len(fake_redis.published) == 0
        # 盘外不查 db（直接跳过）
        assert db_called == []

    asyncio.run(_run())


@pytest.mark.unit
def test_get_pnl_stream_service_singleton() -> None:
    from app.services.pnl_stream_service import get_pnl_stream_service

    a = get_pnl_stream_service()
    b = get_pnl_stream_service()
    assert a is b
