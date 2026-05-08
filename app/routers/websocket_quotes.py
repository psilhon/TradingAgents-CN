"""WebSocket /ws/quotes endpoint — 实时行情 + PnL 推送.

OpenSpec change `2026-05-08-realtime-trading-data-flow` Requirement
"WebSocket /ws/quotes MUST 提供按 code 订阅的实时推送"。

客户端协议：

- `{"type": "subscribe", "codes": ["000001", "600036"]}`
  → 后端订阅 redis `channel:quote:{code}`，每次 quote 事件推送
    `{"type": "quote", "data": {code, close, pct_chg, amount, as_of_ts}}`

- `{"type": "subscribe_pnl"}`
  → 后端订阅 `channel:pnl:{user_id}`（user_id MUST 从 token 取，
    不允许 client 指定别人的）；推送 `{"type": "pnl", "data": {...}}`

- `{"type": "unsubscribe", "codes": [...]}` → 取消对应 quote 订阅

- `{"type": "ping"}` → 收到 `{"type": "pong", ...}`

Server 主动 30s 心跳；client 60s 不来消息 server close（避免连接泄漏）.

Auth：URL `?token=<jwt>`，与 /ws/notifications 同模式.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Set

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.database import get_redis_client
from app.services.auth_service import AuthService

router = APIRouter()
logger = logging.getLogger("webapi.websocket")

QUOTE_CHANNEL_PREFIX = "channel:quote:"
PNL_CHANNEL_PREFIX = "channel:pnl:"
HEARTBEAT_INTERVAL_SECONDS = 30
RECEIVE_TIMEOUT_SECONDS = 60


def _decode_channel(channel) -> Optional[str]:
    if isinstance(channel, bytes):
        try:
            return channel.decode("utf-8")
        except Exception:
            return None
    if isinstance(channel, str):
        return channel
    return None


def _decode_payload(data) -> Optional[dict]:
    if isinstance(data, bytes):
        try:
            data = data.decode("utf-8")
        except Exception:
            return None
    if not isinstance(data, str):
        return None
    try:
        parsed = json.loads(data)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


@router.websocket("/ws/quotes")
async def websocket_quotes_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    """实时行情 + PnL 推送（subscribe / subscribe_pnl / unsubscribe / ping）."""
    # 1. Token auth
    token_data = AuthService.verify_token(token)
    if not token_data:
        await websocket.close(code=1008, reason="Unauthorized")
        return
    user_id = token_data.sub
    if not user_id:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    await websocket.accept()
    logger.info(f"✅ [WS-Quotes] 新连接 user={user_id}")

    # 2. Establish redis pubsub for this connection
    try:
        redis = get_redis_client()
        pubsub = redis.pubsub()
    except Exception as e:
        logger.warning(f"❌ [WS-Quotes] redis 不可用: {e!r}")
        await websocket.send_json({"type": "error", "data": {"message": "redis 不可用"}})
        await websocket.close(code=1011)
        return

    await websocket.send_json(
        {
            "type": "connected",
            "data": {"user_id": user_id, "timestamp": datetime.now(timezone.utc).isoformat()},
        }
    )

    subscribed_channels: Set[str] = set()
    listener_task: Optional[asyncio.Task] = None
    heartbeat_task: Optional[asyncio.Task] = None

    async def _pubsub_listener() -> None:
        """从 pubsub 拿消息 → 路由到 ws send_json."""
        try:
            async for msg in pubsub.listen():
                if msg.get("type") != "message":
                    continue
                channel = _decode_channel(msg.get("channel"))
                payload = _decode_payload(msg.get("data"))
                if channel is None or payload is None:
                    continue
                if channel.startswith(QUOTE_CHANNEL_PREFIX):
                    await websocket.send_json({"type": "quote", "data": payload})
                elif channel.startswith(PNL_CHANNEL_PREFIX):
                    await websocket.send_json({"type": "pnl", "data": payload})
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug(f"[WS-Quotes] pubsub listener exit: {e!r}")

    async def _heartbeat() -> None:
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                await websocket.send_json({"type": "heartbeat", "data": {"timestamp": datetime.now(timezone.utc).isoformat()}})
            except Exception:
                break

    listener_task = asyncio.create_task(_pubsub_listener(), name=f"ws-quotes-listener-{user_id}")
    heartbeat_task = asyncio.create_task(_heartbeat(), name=f"ws-quotes-heartbeat-{user_id}")

    try:
        while True:
            # 接收 client 消息（带超时，60s 无消息 close 避免泄漏）
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=RECEIVE_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                logger.info(f"⏱️ [WS-Quotes] user={user_id} 接收超时，主动关闭")
                break
            except WebSocketDisconnect:
                logger.info(f"🔌 [WS-Quotes] client 主动断开 user={user_id}")
                break

            try:
                msg = json.loads(data)
            except Exception:
                await websocket.send_json({"type": "error", "data": {"message": "invalid JSON"}})
                continue

            if not isinstance(msg, dict):
                await websocket.send_json({"type": "error", "data": {"message": "message MUST be JSON object"}})
                continue

            mtype = msg.get("type")
            if mtype == "subscribe":
                codes = msg.get("codes") or []
                channels = [f"{QUOTE_CHANNEL_PREFIX}{str(c).strip()}" for c in codes if isinstance(c, str) and c.strip()]
                new_channels = [c for c in channels if c not in subscribed_channels]
                if new_channels:
                    try:
                        await pubsub.subscribe(*new_channels)
                        subscribed_channels.update(new_channels)
                    except Exception as e:
                        logger.warning(f"[WS-Quotes] subscribe failed: {e!r}")
                        await websocket.send_json({"type": "error", "data": {"message": "subscribe failed"}})
                        continue
                await websocket.send_json(
                    {
                        "type": "subscribed",
                        "data": {
                            "codes": sorted(
                                c[len(QUOTE_CHANNEL_PREFIX) :] for c in subscribed_channels if c.startswith(QUOTE_CHANNEL_PREFIX)
                            )
                        },
                    }
                )

            elif mtype == "subscribe_pnl":
                # user_id 强制取 token_data.sub；client 不能指定别人的
                channel = f"{PNL_CHANNEL_PREFIX}{user_id}"
                if channel not in subscribed_channels:
                    try:
                        await pubsub.subscribe(channel)
                        subscribed_channels.add(channel)
                    except Exception as e:
                        logger.warning(f"[WS-Quotes] subscribe_pnl failed: {e!r}")
                        await websocket.send_json({"type": "error", "data": {"message": "subscribe_pnl failed"}})
                        continue
                await websocket.send_json({"type": "subscribed_pnl", "data": {"user_id": user_id}})

            elif mtype == "unsubscribe":
                codes = msg.get("codes") or []
                channels = [f"{QUOTE_CHANNEL_PREFIX}{str(c).strip()}" for c in codes if isinstance(c, str) and c.strip()]
                to_remove = [c for c in channels if c in subscribed_channels]
                if to_remove:
                    try:
                        await pubsub.unsubscribe(*to_remove)
                    except Exception as e:
                        logger.warning(f"[WS-Quotes] unsubscribe failed: {e!r}")
                    for c in to_remove:
                        subscribed_channels.discard(c)
                await websocket.send_json({"type": "unsubscribed", "data": {"removed_count": len(to_remove)}})

            elif mtype == "ping":
                await websocket.send_json({"type": "pong", "data": {"timestamp": datetime.now(timezone.utc).isoformat()}})

            else:
                await websocket.send_json({"type": "error", "data": {"message": f"unknown type {mtype!r}"}})

    finally:
        for t in (listener_task, heartbeat_task):
            if t is not None and not t.done():
                t.cancel()
        for t in (listener_task, heartbeat_task):
            if t is not None:
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
        try:
            await pubsub.unsubscribe()
            await pubsub.close()
        except Exception as e:
            logger.debug(f"[WS-Quotes] pubsub cleanup: {e!r}")
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info(f"🔌 [WS-Quotes] 断开 user={user_id}")
