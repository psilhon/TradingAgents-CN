"""RedisBackend — Redis `Backend` implementation.

Persists envelopes as gzip(JSON) bytes via `_serialize.encode_envelope`. Uses
`setex` when `ttl_seconds` is provided (the common path — Redis cache should
have a TTL) and falls back to plain `set` otherwise.

A `redis_client=None` instance is a valid no-op backend — both `save` and
`load` return falsy without touching the network. This keeps the constructor
side-effect-free; the cache layer above decides whether to attempt Redis at
all by checking `db_manager.get_redis_client()`.

Implements `Backend` Protocol (`_protocol.py`).
"""

from __future__ import annotations

import logging
from typing import Any

from tradingagents.dataflows.cache._serialize import decode_envelope, encode_envelope


class RedisBackend:
    """Redis backend — gzip(JSON) envelope bytes."""

    def __init__(self, redis_client: Any | None) -> None:
        self._logger = logging.getLogger(__name__)
        self._client = redis_client

    def save(self, key: str, envelope: dict, ttl_seconds: int | None = None) -> bool:
        """Persist `envelope` under `key`; use `setex` if TTL given else `set`."""
        if self._client is None:
            return False
        try:
            payload = encode_envelope(envelope)
            if ttl_seconds is not None:
                self._client.setex(key, ttl_seconds, payload)
            else:
                self._client.set(key, payload)
            self._logger.debug(f"redis backend save: {key} (ttl={ttl_seconds})")
            return True
        except Exception:
            self._logger.exception(f"redis backend save failed for {key}")
            return False

    def load(self, key: str) -> dict | None:
        """Load envelope for `key`, or None on miss / decode failure."""
        if self._client is None:
            return None
        try:
            raw = self._client.get(key)
            if not raw:
                return None
            envelope = decode_envelope(raw)
            self._logger.debug(f"redis backend load: {key}")
            return envelope
        except Exception:
            self._logger.exception(f"redis backend load failed for {key}")
            return None

    def clear(self, max_age_days: int) -> None:
        """Flush Redis DB when `max_age_days=0`; no-op otherwise.

        Redis enforces TTL natively (via `setex`), so per-entry age-based
        cleanup is not needed for non-zero `max_age_days` — entries
        self-expire. `max_age_days=0` issues `flushdb()` to clear all keys
        in the current DB.
        """
        if self._client is None:
            return
        if max_age_days != 0:
            self._logger.debug(f"redis backend clear no-op for max_age_days={max_age_days} (TTL self-managed)")
            return
        try:
            self._client.flushdb()
            self._logger.info("redis backend flushed entire DB (max_age_days=0)")
        except Exception:
            self._logger.exception("redis backend flushdb failed")
