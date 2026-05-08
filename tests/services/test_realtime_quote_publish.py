"""realtime_quote_sync_service redis publish 行为测试.

OpenSpec change 2026-05-08-realtime-trading-data-flow Requirement
"realtime_quote_sync_service MUST 在 mongo upsert 后发布 redis quote 事件"
覆盖 2 个 scenario：
1. 变化的 code 才 publish（与上次 close/pct_chg 比较，无变化不 spam）
2. redis 宕机降级（mongo upsert 仍正常完成 + logger.warning 不 spam）
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

import pytest


def _make_fake_quotes_service(quotes: dict[str, dict[str, float]]):
    class _FakeQS:
        async def get_quotes(self, codes):
            return {c: quotes[c] for c in codes if c in quotes}

    return _FakeQS()


def _make_fake_db(target_codes: list[str]):
    upserts: list[tuple[str, dict]] = []

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

    class _Coll:
        def __init__(self, name):
            self.name = name

        def find(self, query=None, projection=None):
            if self.name == "user_favorites":
                return _Cursor([{"favorite_stocks": [{"stock_code": c} for c in target_codes]}])
            elif self.name == "paper_positions":
                return _Cursor([])
            else:
                return _Cursor([])

        async def update_one(self, filter, update, upsert=False):
            code = filter.get("code")
            doc = update.get("$set", {})
            upserts.append((code, doc))

            class _R:
                upserted_id = None
                modified_count = 1
                matched_count = 1

            return _R()

        async def create_index(self, *args, **kwargs):
            return "ok"

    class _DB:
        def __init__(self):
            pass

        def __getitem__(self, name):
            return _Coll(name)

    return _DB(), upserts


class _FakeRedis:
    def __init__(self):
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, payload: str):
        self.published.append((channel, payload))


class _FailingRedis:
    def __init__(self):
        self.publish_attempts = 0

    async def publish(self, channel: str, payload: str):
        self.publish_attempts += 1
        raise ConnectionError("redis down")


@pytest.mark.unit
def test_publish_only_on_change(monkeypatch) -> None:
    """Scenario 1: 同 code 第二次 sync 行情未变 → 不 publish."""
    import app.services.realtime_quote_sync_service as mod
    from app.services.realtime_quote_sync_service import RealtimeQuoteSyncService

    fake_redis = _FakeRedis()
    monkeypatch.setattr(mod, "get_redis_client", lambda: fake_redis, raising=True)

    quotes_round_1 = {
        "000001": {"close": 12.34, "pct_chg": 0.5, "amount": 1.0e8},
        "600036": {"close": 35.10, "pct_chg": -0.3, "amount": 8.0e7},
    }
    monkeypatch.setattr(mod, "get_quotes_service", lambda: _make_fake_quotes_service(quotes_round_1), raising=True)

    fake_db, _upserts = _make_fake_db(["000001", "600036"])

    async def _run() -> None:
        svc = RealtimeQuoteSyncService(db=fake_db)
        # 第一轮：两个 code 都是新值 → 都 publish
        result = await svc.sync_favorites_and_paper_positions()
        assert result["updated"] == 2
        assert len(fake_redis.published) == 2
        ch1, p1 = fake_redis.published[0]
        assert ch1.startswith("channel:quote:")
        payload1 = json.loads(p1)
        assert "code" in payload1 and "close" in payload1 and "pct_chg" in payload1
        assert "as_of_ts" in payload1

        # 第二轮：相同 quotes → 不应再 publish
        fake_redis.published.clear()
        result2 = await svc.sync_favorites_and_paper_positions()
        assert result2["updated"] == 2  # mongo 仍 upsert（覆盖 ts）
        assert len(fake_redis.published) == 0, "无变化不应 publish"

        # 第三轮：000001 close 变了 → 只 publish 000001
        quotes_round_3 = {
            "000001": {"close": 12.50, "pct_chg": 1.8, "amount": 1.1e8},
            "600036": {"close": 35.10, "pct_chg": -0.3, "amount": 8.0e7},
        }
        monkeypatch.setattr(
            mod,
            "get_quotes_service",
            lambda: _make_fake_quotes_service(quotes_round_3),
            raising=True,
        )
        fake_redis.published.clear()
        result3 = await svc.sync_favorites_and_paper_positions()
        assert result3["updated"] == 2
        assert len(fake_redis.published) == 1
        ch3, _p3 = fake_redis.published[0]
        assert ch3 == "channel:quote:000001"

    asyncio.run(_run())


@pytest.mark.unit
def test_redis_failure_does_not_break_sync(monkeypatch, caplog) -> None:
    """Scenario 2: redis publish 异常 → mongo upsert 仍成功，logger.warning 一次不 spam."""
    import logging

    import app.services.realtime_quote_sync_service as mod
    from app.services.realtime_quote_sync_service import RealtimeQuoteSyncService

    failing_redis = _FailingRedis()
    monkeypatch.setattr(mod, "get_redis_client", lambda: failing_redis, raising=True)

    quotes = {
        "000001": {"close": 12.34, "pct_chg": 0.5, "amount": 1.0e8},
        "600036": {"close": 35.10, "pct_chg": -0.3, "amount": 8.0e7},
        "002594": {"close": 200.0, "pct_chg": 1.5, "amount": 5.0e7},
    }
    monkeypatch.setattr(mod, "get_quotes_service", lambda: _make_fake_quotes_service(quotes), raising=True)

    fake_db, upserts = _make_fake_db(["000001", "600036", "002594"])

    async def _run() -> None:
        svc = RealtimeQuoteSyncService(db=fake_db)
        with caplog.at_level(logging.WARNING, logger="app.services.realtime_quote_sync_service"):
            result = await svc.sync_favorites_and_paper_positions()

        # mongo 仍成功
        assert result["updated"] == 3
        assert len(upserts) == 3

        # publish 失败：redis 被调过 ≥ 1 次（由 throttle 决定）
        assert failing_redis.publish_attempts >= 1
        # logger.warning 被发了**至多一次**（不 spam）—— 第二/三个 code publish 时静默
        publish_warnings = [r for r in caplog.records if "redis publish" in r.message]
        assert len(publish_warnings) <= 1, f"redis 失败 warning 不应 spam，实际 {len(publish_warnings)}"

    asyncio.run(_run())


@pytest.mark.unit
def test_publish_payload_schema(monkeypatch) -> None:
    """publish payload schema：含 code/close/pct_chg/amount/as_of_ts."""
    import app.services.realtime_quote_sync_service as mod
    from app.services.realtime_quote_sync_service import RealtimeQuoteSyncService

    fake_redis = _FakeRedis()
    monkeypatch.setattr(mod, "get_redis_client", lambda: fake_redis, raising=True)

    quotes = {"000001": {"close": 12.34, "pct_chg": 0.5, "amount": 1.0e8}}
    monkeypatch.setattr(mod, "get_quotes_service", lambda: _make_fake_quotes_service(quotes), raising=True)

    fake_db, _ = _make_fake_db(["000001"])

    async def _run() -> None:
        svc = RealtimeQuoteSyncService(db=fake_db)
        await svc.sync_favorites_and_paper_positions()
        assert len(fake_redis.published) == 1
        channel, payload_str = fake_redis.published[0]
        assert channel == "channel:quote:000001"
        payload = json.loads(payload_str)
        assert payload["code"] == "000001"
        assert payload["close"] == 12.34
        assert payload["pct_chg"] == 0.5
        assert payload["amount"] == 1.0e8
        # as_of_ts ISO8601 with timezone
        assert "T" in payload["as_of_ts"]
        # parseable
        datetime.fromisoformat(payload["as_of_ts"])

    asyncio.run(_run())
