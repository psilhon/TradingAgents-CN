"""WebSocket /ws/quotes endpoint 单元测试.

OpenSpec change 2026-05-08-realtime-trading-data-flow Requirement
"WebSocket /ws/quotes MUST 提供按 code 订阅的实时推送" 关键 scenario：

1. 拒绝无 token / 错误 token（1008 close）
2. subscribe → pubsub.subscribe 被调，channel = `channel:quote:{code}`
3. subscribe_pnl → pubsub.subscribe channel = `channel:pnl:{user_id from token}`
   即便 client payload 含 `user_id` 也忽略，只用 token_data.sub（user-scoped 强制）
4. unsubscribe / ping / pong / unknown type 消息处理

不测真 redis 连接（mock pubsub）；不测 lifespan / 心跳 timing.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _FakePubSub:
    def __init__(self):
        self.subscribed: list[tuple[str, ...]] = []
        self.unsubscribed: list[tuple[str, ...]] = []

    async def subscribe(self, *channels: str) -> None:
        self.subscribed.append(channels)

    async def unsubscribe(self, *channels: str) -> None:
        self.unsubscribed.append(channels)

    async def listen(self):
        # 不发任何 pubsub 消息（避免影响 receive 循环）；保持挂起
        import asyncio

        await asyncio.Event().wait()
        yield {}  # never reached

    async def close(self):
        pass


class _FakeRedis:
    def __init__(self):
        self.last_pubsub: _FakePubSub | None = None

    def pubsub(self) -> _FakePubSub:
        ps = _FakePubSub()
        self.last_pubsub = ps
        return ps


def _build_app(monkeypatch, fake_redis: _FakeRedis, sub: str | None = "user_A"):
    """Build a mini FastAPI app with /api prefix for ws_quotes router."""
    import app.routers.websocket_quotes as ws_mod

    monkeypatch.setattr(ws_mod, "get_redis_client", lambda: fake_redis, raising=True)

    # Mock token verification
    def _fake_verify(_token: str):
        if _token == "BAD_TOKEN":
            return None
        return SimpleNamespace(sub=sub) if sub is not None else SimpleNamespace(sub=None)

    monkeypatch.setattr(ws_mod.AuthService, "verify_token", staticmethod(_fake_verify), raising=True)

    app = FastAPI()
    app.include_router(ws_mod.router, prefix="/api")
    return app


@pytest.mark.unit
def test_ws_quotes_rejects_invalid_token(monkeypatch) -> None:
    """无效 token → 1008 close (Unauthorized)."""
    fake_redis = _FakeRedis()
    app = _build_app(monkeypatch, fake_redis)
    client = TestClient(app)

    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        # TestClient ws_connect 在 close code 1008 时抛 WebSocketDisconnect
        with client.websocket_connect("/api/ws/quotes?token=BAD_TOKEN") as ws:
            ws.receive_text()  # 期望立即 close


@pytest.mark.unit
def test_ws_quotes_rejects_empty_sub(monkeypatch) -> None:
    """token 解析成功但 sub 为空 → 1008 close."""
    fake_redis = _FakeRedis()
    app = _build_app(monkeypatch, fake_redis, sub=None)
    client = TestClient(app)

    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/ws/quotes?token=GOOD_TOKEN") as ws:
            ws.receive_text()


@pytest.mark.unit
def test_ws_quotes_subscribe_calls_pubsub(monkeypatch) -> None:
    """subscribe codes → pubsub.subscribe 被调，channel = channel:quote:{code}."""
    fake_redis = _FakeRedis()
    app = _build_app(monkeypatch, fake_redis, sub="user_A")
    client = TestClient(app)

    with client.websocket_connect("/api/ws/quotes?token=GOOD_TOKEN") as ws:
        connected = ws.receive_json()
        assert connected["type"] == "connected"
        assert connected["data"]["user_id"] == "user_A"

        ws.send_json({"type": "subscribe", "codes": ["000001", "600036"]})
        ack = ws.receive_json()
        assert ack["type"] == "subscribed"
        assert sorted(ack["data"]["codes"]) == ["000001", "600036"]

    pubsub = fake_redis.last_pubsub
    assert pubsub is not None
    # subscribe 被调一次，channels 含两条
    flat = [ch for batch in pubsub.subscribed for ch in batch]
    assert "channel:quote:000001" in flat
    assert "channel:quote:600036" in flat


@pytest.mark.unit
def test_ws_quotes_subscribe_pnl_user_scoped(monkeypatch) -> None:
    """subscribe_pnl MUST 强制使用 token_data.sub，忽略 client 指定的 user_id."""
    fake_redis = _FakeRedis()
    app = _build_app(monkeypatch, fake_redis, sub="user_A")
    client = TestClient(app)

    with client.websocket_connect("/api/ws/quotes?token=GOOD_TOKEN") as ws:
        ws.receive_json()  # connected
        # 即便 client payload 试图传 user_id="user_B"，server 也只订自己的
        ws.send_json({"type": "subscribe_pnl", "user_id": "user_B"})
        ack = ws.receive_json()
        assert ack["type"] == "subscribed_pnl"
        assert ack["data"]["user_id"] == "user_A"

    pubsub = fake_redis.last_pubsub
    assert pubsub is not None
    flat = [ch for batch in pubsub.subscribed for ch in batch]
    assert "channel:pnl:user_A" in flat
    # 关键：MUST NOT subscribe 别人的 channel
    assert "channel:pnl:user_B" not in flat


@pytest.mark.unit
def test_ws_quotes_ping_pong(monkeypatch) -> None:
    """ping → pong 简单往返."""
    fake_redis = _FakeRedis()
    app = _build_app(monkeypatch, fake_redis, sub="user_A")
    client = TestClient(app)

    with client.websocket_connect("/api/ws/quotes?token=GOOD_TOKEN") as ws:
        ws.receive_json()  # connected
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"
        assert "timestamp" in pong["data"]


@pytest.mark.unit
def test_ws_quotes_unknown_type_returns_error(monkeypatch) -> None:
    """未知 message type → error 响应."""
    fake_redis = _FakeRedis()
    app = _build_app(monkeypatch, fake_redis, sub="user_A")
    client = TestClient(app)

    with client.websocket_connect("/api/ws/quotes?token=GOOD_TOKEN") as ws:
        ws.receive_json()  # connected
        ws.send_json({"type": "garbage"})
        err = ws.receive_json()
        assert err["type"] == "error"
        assert "unknown type" in err["data"]["message"]


@pytest.mark.unit
def test_ws_quotes_invalid_json_returns_error(monkeypatch) -> None:
    """非 JSON 文本 → error 响应（不 crash）."""
    fake_redis = _FakeRedis()
    app = _build_app(monkeypatch, fake_redis, sub="user_A")
    client = TestClient(app)

    with client.websocket_connect("/api/ws/quotes?token=GOOD_TOKEN") as ws:
        ws.receive_json()  # connected
        ws.send_text("not-json")
        err = ws.receive_json()
        assert err["type"] == "error"
        assert "invalid JSON" in err["data"]["message"]
