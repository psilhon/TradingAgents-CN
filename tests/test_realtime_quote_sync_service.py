"""
Tests for RealtimeQuoteSyncService — 覆盖：
- codes 去重（自选股 ∪ paper 持仓 CN）
- market != CN 的持仓被过滤
- upsert payload 字段正确
- QuotesService 失败 / 返回空时的降级
- 空 codes 时不调 QuotesService
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.realtime_quote_sync_service import RealtimeQuoteSyncService


class _AsyncCursor:
    """模拟 motor `find()` 返回的 async cursor。"""

    def __init__(self, docs: list[dict[str, Any]]):
        self._docs = list(docs)

    def __aiter__(self):
        async def _gen():
            for doc in self._docs:
                yield doc

        return _gen()


class _FakeCollection:
    def __init__(self, docs: list[dict[str, Any]] | None = None):
        self.docs = docs or []
        self.upsert_calls: list[dict[str, Any]] = []

    def find(self, query: dict[str, Any] | None = None, *args, **kwargs):
        # 简化的 mongo query 模拟：仅支持平铺 key=value 等值匹配（足够本测试用）
        if not query:
            return _AsyncCursor(self.docs)
        filtered = [d for d in self.docs if all(d.get(k) == v for k, v in query.items())]
        return _AsyncCursor(filtered)

    async def update_one(self, query, update, upsert=False):
        self.upsert_calls.append({"query": query, "update": update, "upsert": upsert})

    async def create_index(self, *args, **kwargs):
        return None


class _FakeDB:
    def __init__(self, collections: dict[str, _FakeCollection]):
        self._collections = collections

    def __getitem__(self, name: str) -> _FakeCollection:
        return self._collections[name]


def _build_db(
    favorites: list[dict[str, Any]] | None = None,
    positions: list[dict[str, Any]] | None = None,
    market_quotes: list[dict[str, Any]] | None = None,
) -> _FakeDB:
    return _FakeDB(
        {
            "user_favorites": _FakeCollection(favorites or []),
            "paper_positions": _FakeCollection(positions or []),
            "market_quotes": _FakeCollection(market_quotes or []),
        }
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_target_codes_dedupes_favorites_and_positions():
    db = _build_db(
        favorites=[
            {
                "user_id": "u1",
                "favorite_stocks": [{"stock_code": "000776"}, {"stock_code": "002428"}],
            },
            {
                "user_id": "u2",
                "favorite_stocks": [{"stock_code": "002428"}, {"stock_code": "603009"}],
            },
        ],
        positions=[
            {"user_id": "u1", "code": "000776", "market": "CN"},
            {"user_id": "u2", "code": "601318", "market": "CN"},
        ],
    )
    svc = RealtimeQuoteSyncService(db=db)  # type: ignore[arg-type]

    codes = await svc._collect_target_codes()

    assert codes == {"000776", "002428", "603009", "601318"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collect_target_codes_filters_non_cn_paper_positions():
    db = _build_db(
        favorites=[],
        positions=[
            {"user_id": "u1", "code": "000776", "market": "CN"},
            {"user_id": "u1", "code": "0700", "market": "HK"},
            {"user_id": "u1", "code": "AAPL", "market": "US"},
        ],
    )
    svc = RealtimeQuoteSyncService(db=db)  # type: ignore[arg-type]

    codes = await svc._collect_target_codes()

    # 仅 CN 的 000776 被收集
    assert codes == {"000776"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_empty_codes_skips_quotes_service():
    db = _build_db(favorites=[], positions=[])
    svc = RealtimeQuoteSyncService(db=db)  # type: ignore[arg-type]

    fake_quotes = MagicMock()
    fake_quotes.get_quotes_targeted = AsyncMock()

    with patch(
        "app.services.realtime_quote_sync_service.get_quotes_service",
        return_value=fake_quotes,
    ):
        result = await svc.sync_favorites_and_paper_positions()

    assert result == {"total": 0, "fetched": 0, "updated": 0, "errors": 0}
    fake_quotes.get_quotes_targeted.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_quotes_service_failure_returns_errors():
    db = _build_db(
        favorites=[{"user_id": "u1", "favorite_stocks": [{"stock_code": "000776"}]}],
        positions=[],
    )
    svc = RealtimeQuoteSyncService(db=db)  # type: ignore[arg-type]

    fake_quotes = MagicMock()
    fake_quotes.get_quotes_targeted = AsyncMock(return_value={})  # 模拟 sina 失败
    fake_quotes.get_quotes = AsyncMock(return_value={})  # 全市场快照也失败

    with patch(
        "app.services.realtime_quote_sync_service.get_quotes_service",
        return_value=fake_quotes,
    ):
        result = await svc.sync_favorites_and_paper_positions()

    assert result == {"total": 1, "fetched": 0, "updated": 0, "errors": 1}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_upserts_valid_quotes_to_market_quotes():
    db = _build_db(
        favorites=[{"user_id": "u1", "favorite_stocks": [{"stock_code": "000776"}]}],
        positions=[
            {"user_id": "u1", "code": "002428", "market": "CN"},
        ],
    )
    svc = RealtimeQuoteSyncService(db=db)  # type: ignore[arg-type]

    fake_quotes = MagicMock()
    fake_quotes.get_quotes_targeted = AsyncMock(
        return_value={
            "000776": {"close": 21.17, "pct_chg": 1.5, "amount": 12000.0},
            "002428": {"close": 80.20, "pct_chg": 2.3, "amount": 50000.0},
        }
    )

    with patch(
        "app.services.realtime_quote_sync_service.get_quotes_service",
        return_value=fake_quotes,
    ):
        result = await svc.sync_favorites_and_paper_positions()

    assert result["total"] == 2
    assert result["fetched"] == 2
    assert result["updated"] == 2
    assert result["errors"] == 0

    upsert_calls = db["market_quotes"].upsert_calls  # type: ignore[index]
    assert len(upsert_calls) == 2

    # 验证 upsert payload schema
    for call in upsert_calls:
        assert call["upsert"] is True
        set_payload = call["update"]["$set"]
        assert set_payload["code"] in {"000776", "002428"}
        assert set_payload["symbol"] == set_payload["code"]
        assert isinstance(set_payload["close"], float)
        assert set_payload["close"] > 0
        assert "updated_at" in set_payload


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_skips_invalid_close_prices():
    db = _build_db(
        favorites=[
            {
                "user_id": "u1",
                "favorite_stocks": [
                    {"stock_code": "000776"},
                    {"stock_code": "002428"},
                    {"stock_code": "603009"},
                ],
            }
        ],
        positions=[],
    )
    svc = RealtimeQuoteSyncService(db=db)  # type: ignore[arg-type]

    fake_quotes = MagicMock()
    fake_quotes.get_quotes_targeted = AsyncMock(
        return_value={
            "000776": {"close": 21.17},  # ✅ 有效
            "002428": {"close": None},  # ✗ None 跳过
            "603009": {"close": 0.0},  # ✗ 0 跳过
        }
    )

    with patch(
        "app.services.realtime_quote_sync_service.get_quotes_service",
        return_value=fake_quotes,
    ):
        result = await svc.sync_favorites_and_paper_positions()

    upsert_calls = db["market_quotes"].upsert_calls  # type: ignore[index]
    assert len(upsert_calls) == 1
    assert upsert_calls[0]["update"]["$set"]["code"] == "000776"
    assert result["updated"] == 1
    assert result["errors"] == 2  # total 3 − updated 1
