"""端到端集成测试：realtime_quote_sync publish → /ws/quotes subscribe 真 round-trip.

OpenSpec change 2026-05-08-realtime-trading-data-flow Section 9.7（follow-up
变正式集成测试）：用 in-memory fake redis（共享 channel queues）模拟两端通过
同一个 redis 实例 publish/subscribe，验证：

1. realtime_quote_sync_service.sync_favorites_and_paper_positions() 触发 publish
2. 一个 PubSub subscriber 收到对应 channel:quote:{code} 消息
3. payload schema 完整（code/close/pct_chg/amount/as_of_ts）

不引入 fakeredis 依赖（保持 dev dep 干净）；这是 mark=integration 的 test，与
单元 mock 测试互补.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

# =============== In-memory fake redis with real pubsub semantics ===============


class _FakePubSub:
    """模拟 redis-py asyncio.Redis().pubsub() 行为：subscribe + listen + close."""

    def __init__(self, broker: _FakeRedisBroker) -> None:
        self._broker = broker
        self._queue: asyncio.Queue = asyncio.Queue()
        self._subscribed_channels: set[str] = set()
        self._closed = False

    async def subscribe(self, *channels: str) -> None:
        for ch in channels:
            self._broker._subscribers.setdefault(ch, []).append(self._queue)
            self._subscribed_channels.add(ch)

    async def unsubscribe(self, *channels) -> None:
        targets = list(channels) if channels else list(self._subscribed_channels)
        for ch in targets:
            subs = self._broker._subscribers.get(ch, [])
            if self._queue in subs:
                subs.remove(self._queue)
            self._subscribed_channels.discard(ch)

    async def listen(self):
        # async generator over pubsub messages（兼容 redis-py 协议）
        while not self._closed:
            try:
                msg = await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            yield msg

    async def close(self) -> None:
        self._closed = True
        await self.unsubscribe()


class _FakeRedisBroker:
    """共享 broker：一个进程内的 fake redis."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    async def publish(self, channel: str, payload: str) -> int:
        subs = self._subscribers.get(channel, [])
        msg = {"type": "message", "channel": channel, "data": payload}
        for q in subs:
            await q.put(msg)
        return len(subs)

    def pubsub(self) -> _FakePubSub:
        return _FakePubSub(self)


# =============== Fixtures ===============


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
            return _Cursor([])

        async def update_one(self, filter, update, upsert=False):
            upserts.append((filter.get("code"), update.get("$set", {})))

            class _R:
                upserted_id = None
                modified_count = 1
                matched_count = 1

            return _R()

        async def create_index(self, *args, **kwargs):
            return "ok"

    class _DB:
        def __getitem__(self, name):
            return _Coll(name)

    return _DB(), upserts


def _make_fake_quotes_service(quotes: dict[str, dict[str, Any]]):
    class _FakeQS:
        async def get_quotes(self, codes):
            return {c: quotes[c] for c in codes if c in quotes}

    return _FakeQS()


# =============== Tests ===============


@pytest.mark.integration
def test_publish_subscribe_roundtrip_single_code(monkeypatch) -> None:
    """单 code: sync 触发 publish → 一个 subscriber 真收到 channel:quote:{code} 消息."""
    import app.services.realtime_quote_sync_service as sync_mod
    from app.services.realtime_quote_sync_service import RealtimeQuoteSyncService

    broker = _FakeRedisBroker()
    monkeypatch.setattr(sync_mod, "get_redis_client", lambda: broker, raising=True)
    quotes = {"000001": {"close": 12.34, "pct_chg": 0.5, "amount": 1.0e8}}
    monkeypatch.setattr(sync_mod, "get_quotes_service", lambda: _make_fake_quotes_service(quotes), raising=True)
    fake_db, _upserts = _make_fake_db(["000001"])

    received: list[dict] = []

    async def _run() -> None:
        # 1. subscriber 启动 + subscribe
        pubsub = broker.pubsub()
        await pubsub.subscribe("channel:quote:000001")

        async def _listener():
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    received.append(json.loads(msg["data"]))
                    if len(received) >= 1:
                        return

        listener_task = asyncio.create_task(_listener())

        # 2. 触发 publisher
        svc = RealtimeQuoteSyncService(db=fake_db)
        result = await svc.sync_favorites_and_paper_positions()
        assert result["updated"] == 1

        # 3. 等 subscriber 收到（最多 1s）
        await asyncio.wait_for(listener_task, timeout=1.0)
        await pubsub.close()

        # 4. 验证 payload
        assert len(received) == 1
        payload = received[0]
        assert payload["code"] == "000001"
        assert payload["close"] == 12.34
        assert payload["pct_chg"] == 0.5
        assert payload["amount"] == 1.0e8
        assert "as_of_ts" in payload and "T" in payload["as_of_ts"]

    asyncio.run(_run())


@pytest.mark.integration
def test_publish_subscribe_only_subscribed_channels(monkeypatch) -> None:
    """subscriber 只 subscribe 一个 channel，其他 code 的 publish 不应被收到."""
    import app.services.realtime_quote_sync_service as sync_mod
    from app.services.realtime_quote_sync_service import RealtimeQuoteSyncService

    broker = _FakeRedisBroker()
    monkeypatch.setattr(sync_mod, "get_redis_client", lambda: broker, raising=True)
    quotes = {
        "000001": {"close": 12.34, "pct_chg": 0.5, "amount": 1.0e8},
        "600036": {"close": 35.10, "pct_chg": -0.3, "amount": 8.0e7},
    }
    monkeypatch.setattr(sync_mod, "get_quotes_service", lambda: _make_fake_quotes_service(quotes), raising=True)
    fake_db, _upserts = _make_fake_db(["000001", "600036"])

    received: list[dict] = []

    async def _run() -> None:
        pubsub = broker.pubsub()
        # 只 subscribe 000001，不 subscribe 600036
        await pubsub.subscribe("channel:quote:000001")

        async def _listener():
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    received.append(json.loads(msg["data"]))

        listener_task = asyncio.create_task(_listener())

        # publisher 同时 publish 2 个 code
        svc = RealtimeQuoteSyncService(db=fake_db)
        await svc.sync_favorites_and_paper_positions()

        # 给 listener 一点时间收消息
        await asyncio.sleep(0.2)
        await pubsub.close()
        listener_task.cancel()
        try:
            await listener_task
        except (asyncio.CancelledError, Exception):
            pass

        # 只收到 000001（不收 600036，因为 subscriber 没 subscribe 它）
        assert len(received) == 1
        assert received[0]["code"] == "000001"

    asyncio.run(_run())
