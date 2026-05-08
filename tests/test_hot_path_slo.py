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
def test_market_overview_with_cache_does_not_call_akshare(monkeypatch) -> None:
    """cache 已有数据时，hot-path 同样 MUST NOT 调 _fetch_spot_akshare."""
    import time

    import app.routers.market as market_router_mod
    from app.services.quotes_service import QuotesService, get_quotes_service

    fetch_spy_calls: list[int] = []

    def _spy_fetch(self):
        fetch_spy_calls.append(1)
        return {}

    monkeypatch.setattr(QuotesService, "_fetch_spot_akshare", _spy_fetch, raising=True)

    class _FakeCalendar:
        async def is_intraday_now(self) -> bool:
            return True

    monkeypatch.setattr(market_router_mod, "get_trading_calendar_service", lambda: _FakeCalendar(), raising=True)

    real_qs = get_quotes_service()
    real_qs._cache = {
        "000001": {"close": 12.34, "pct_chg": 9.6, "amount": 1.0e8},
        "600036": {"close": 35.10, "pct_chg": -0.5, "amount": 8.0e7},
    }
    real_qs._cache_ts = time.time() - 10

    async def _run() -> None:
        result = await market_router_mod.get_market_overview(_user={"id": "u1"})
        assert result["success"] is True
        assert result["data"]["total"] == 2
        assert result["data"]["as_of_ts"] is not None
        assert fetch_spy_calls == [], "warm cache 路径同样不应调 _fetch_spot_akshare"

    asyncio.run(_run())
