"""quote_snapshot_reader: 持仓 / 自选股的 mongo `market_quotes` hot-path 读

按 OpenSpec change 2026-05-08-realtime-trading-data-flow Requirement 1：
hot-path 端点 MUST NOT 在用户请求路径同步触发上游行情拉取；持仓 / 自选股
快照读 mongo `market_quotes`，缺漏 code 返回 None 不触发 fetch。

每条记录带 `last_price_as_of`（doc.updated_at），顶层 `as_of_ts`
取所有有效记录的 min `last_price_as_of`（"最 stale 的那条"反映整体 freshness）。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest


def _make_fake_db(docs: list[dict]):
    """Build a minimal fake mongo db that returns `docs` from market_quotes.find()."""

    class _FakeCursor:
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

    class _FakeColl:
        def __init__(self, items):
            self._items = items
            self.find_calls: list[tuple] = []

        def find(self, query, projection=None):
            self.find_calls.append((query, projection))
            # filter by $in code list to mimic mongo
            in_codes = (query or {}).get("code", {}).get("$in", [])
            matched = [d for d in self._items if d.get("code") in in_codes]
            return _FakeCursor(matched)

    class _FakeDB:
        def __init__(self, items):
            self._coll = _FakeColl(items)

        def __getitem__(self, name):
            assert name == "market_quotes"
            return self._coll

    return _FakeDB(docs)


@pytest.mark.unit
def test_read_quotes_returns_records_with_last_price_as_of(monkeypatch) -> None:
    import app.services.quote_snapshot_reader as mod
    from app.services.quote_snapshot_reader import QuoteSnapshotReader

    ts1 = datetime(2026, 5, 8, 9, 30, 0, tzinfo=timezone.utc)
    ts2 = datetime(2026, 5, 8, 9, 30, 30, tzinfo=timezone.utc)
    fake_db = _make_fake_db(
        [
            {"code": "000001", "close": 12.34, "pct_chg": 0.5, "amount": 1.2e8, "updated_at": ts1},
            {"code": "600036", "close": 35.10, "pct_chg": -0.2, "amount": 8.5e7, "updated_at": ts2},
        ]
    )
    monkeypatch.setattr(mod, "get_mongo_db", lambda: fake_db, raising=True)

    async def _run() -> None:
        reader = QuoteSnapshotReader()
        result = await reader.read_quotes(["000001", "600036", "002594"])

        assert set(result["quotes"].keys()) == {"000001", "600036", "002594"}
        assert result["quotes"]["000001"] == {
            "close": 12.34,
            "pct_chg": 0.5,
            "amount": 1.2e8,
            "last_price_as_of": ts1.isoformat(),
        }
        assert result["quotes"]["600036"]["last_price_as_of"] == ts2.isoformat()
        # 缺漏 code 返回 None 占位
        assert result["quotes"]["002594"] == {
            "close": None,
            "pct_chg": None,
            "amount": None,
            "last_price_as_of": None,
        }
        # 顶层 as_of_ts = min(last_price_as_of)，忽略 None
        assert result["as_of_ts"] == ts1.isoformat()

    asyncio.run(_run())


@pytest.mark.unit
def test_read_quotes_empty_codes_returns_empty(monkeypatch) -> None:
    import app.services.quote_snapshot_reader as mod
    from app.services.quote_snapshot_reader import QuoteSnapshotReader

    fake_db = _make_fake_db([])
    monkeypatch.setattr(mod, "get_mongo_db", lambda: fake_db, raising=True)

    async def _run() -> None:
        reader = QuoteSnapshotReader()
        result = await reader.read_quotes([])
        assert result == {"quotes": {}, "as_of_ts": None}

    asyncio.run(_run())


@pytest.mark.unit
def test_read_quotes_all_missing_returns_null_as_of_ts(monkeypatch) -> None:
    import app.services.quote_snapshot_reader as mod
    from app.services.quote_snapshot_reader import QuoteSnapshotReader

    fake_db = _make_fake_db([])  # mongo 空
    monkeypatch.setattr(mod, "get_mongo_db", lambda: fake_db, raising=True)

    async def _run() -> None:
        reader = QuoteSnapshotReader()
        result = await reader.read_quotes(["000001", "600036"])
        assert result["quotes"]["000001"]["close"] is None
        assert result["quotes"]["000001"]["last_price_as_of"] is None
        # 全缺漏时顶层 as_of_ts 是 None
        assert result["as_of_ts"] is None

    asyncio.run(_run())


@pytest.mark.unit
def test_read_quotes_strips_and_normalizes_codes(monkeypatch) -> None:
    """空白 / 重复 / 空字符串 codes 应被剥离."""
    import app.services.quote_snapshot_reader as mod
    from app.services.quote_snapshot_reader import QuoteSnapshotReader

    ts = datetime(2026, 5, 8, 9, 30, 0, tzinfo=timezone.utc)
    fake_db = _make_fake_db([{"code": "000001", "close": 12.34, "pct_chg": 0.5, "amount": 1.2e8, "updated_at": ts}])
    monkeypatch.setattr(mod, "get_mongo_db", lambda: fake_db, raising=True)

    async def _run() -> None:
        reader = QuoteSnapshotReader()
        result = await reader.read_quotes(["  000001  ", "000001", "", "  "])
        # 空白 / 重复 / 空字符串均被剥离，剩下 000001 一个
        assert set(result["quotes"].keys()) == {"000001"}

    asyncio.run(_run())


@pytest.mark.unit
def test_get_quote_snapshot_reader_singleton() -> None:
    from app.services.quote_snapshot_reader import get_quote_snapshot_reader

    a = get_quote_snapshot_reader()
    b = get_quote_snapshot_reader()
    assert a is b
