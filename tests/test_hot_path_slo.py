"""hot-path SLO 单测：router 路径 MUST NOT 同步触发上游行情拉取.

OpenSpec change 2026-05-08-realtime-trading-data-flow Requirement 1
Scenario "上游源仅在 worker / scheduler / prewarm 路径出现"。

通过 spy `QuotesService._fetch_spot_akshare` + 调 router 函数验证：
hot-path（market overview / paper account 路径）不在请求路径调 akshare。
"""

from __future__ import annotations

import asyncio

import pytest


@pytest.mark.unit
def test_market_overview_router_does_not_call_akshare(monkeypatch) -> None:
    """`/api/market/overview` 路径 MUST NOT 调 _fetch_spot_akshare."""
    import app.routers.market as market_router_mod
    from app.services.quotes_service import QuotesService

    fetch_spy_calls: list[int] = []

    def _spy_fetch(self):
        fetch_spy_calls.append(1)
        return {}

    monkeypatch.setattr(QuotesService, "_fetch_spot_akshare", _spy_fetch, raising=True)

    # 让 trading_calendar 不抛
    class _FakeCalendar:
        async def is_intraday_now(self) -> bool:
            return True

    monkeypatch.setattr(market_router_mod, "get_trading_calendar_service", lambda: _FakeCalendar(), raising=True)

    # 重置 QuotesService singleton 状态，模拟"prewarm 还没跑过任何一轮"
    from app.services.quotes_service import get_quotes_service

    real_qs = get_quotes_service()
    real_qs._cache = {}
    real_qs._cache_ts = 0.0

    async def _run() -> None:
        result = await market_router_mod.get_market_overview(_user={"id": "u1"})
        assert result["success"] is True
        # cache 空时 hot-path 返回 null 字段（不阻塞等待）
        assert result["data"]["total"] == 0
        assert result["data"]["as_of_ts"] is None
        # 关键断言：hot-path 路径 MUST NOT 调 _fetch_spot_akshare
        assert fetch_spy_calls == [], f"hot-path 不应调 _fetch_spot_akshare，被调 {len(fetch_spy_calls)} 次"

    asyncio.run(_run())


@pytest.mark.unit
def test_market_overview_with_mongo_aggregate_does_not_call_akshare(monkeypatch) -> None:
    """capability data-truthfulness change 2026-05-20：hot-path 改 mongo aggregate
    后，warm mongo 路径同样 MUST NOT 触发 _fetch_spot_akshare（SLO 不变）。"""
    from datetime import datetime, timezone

    import app.routers.market as market_router_mod
    import app.services.market_overview_prewarm_service as prewarm_mod
    from app.services.quotes_service import QuotesService

    fetch_spy_calls: list[int] = []

    def _spy_fetch(self):
        fetch_spy_calls.append(1)
        return {}

    monkeypatch.setattr(QuotesService, "_fetch_spot_akshare", _spy_fetch, raising=True)

    class _FakeCalendar:
        async def is_intraday_now(self) -> bool:
            return True

    monkeypatch.setattr(market_router_mod, "get_trading_calendar_service", lambda: _FakeCalendar(), raising=True)

    # mock mongo $facet aggregate 结果（2 条今日 quote）
    facet_result = {
        "limit_up": [{"n": 1}],
        "limit_down": [],
        "advance": [{"n": 1}],
        "decline": [{"n": 1}],
        "amount_sum": [{"_id": None, "sum": 1.0e8 + 8.0e7}],
        "max_updated": [{"_id": None, "ts": datetime.now(timezone.utc)}],
        "total": [{"n": 2}],
    }

    class _FakeCursor:
        async def to_list(self, _length):
            return [facet_result]

    class _FakeColl:
        def aggregate(self, pipeline, **kwargs):
            return _FakeCursor()

    class _FakeDB:
        def __getitem__(self, name):
            return _FakeColl()

    monkeypatch.setattr(prewarm_mod, "get_mongo_db", lambda: _FakeDB(), raising=True)

    async def _run() -> None:
        result = await market_router_mod.get_market_overview(_user={"id": "u1"})
        assert result["success"] is True
        assert result["data"]["total"] == 2
        assert result["data"]["as_of_ts"] is not None
        assert fetch_spy_calls == [], "warm mongo aggregate 路径不应调 _fetch_spot_akshare"

    asyncio.run(_run())
