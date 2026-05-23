"""`Backend` Protocol — minimal pluggable interface for cache storage backends.

Defined per `docs/specs/dataflow-caching/spec.md` Requirement "Backend Protocol
接口". `save` accepts an optional `ttl_seconds` for backends with native TTL
support (Redis `setex` / Mongo `expires_at`); FileBackend accepts the
parameter for Protocol conformance but ignores it (filesystems have no
native TTL — expiry is enforced by the cache layer above via timestamp
checks). `clear(max_age_days)` lets each backend purge aged entries with
backend-specific semantics (see method docstring).

Backends MUST:
- Treat envelopes as opaque dicts. Do not inspect `timestamp` / `backend` /
  `data` / `metadata` fields; serialize via `_serialize.py` and persist as-is.
  (MongoBackend is the documented exception — it interprets `data` to drive
  doc-typed schema; see its spec Requirement.)
- Return `False` (save) / `None` (load) on any failure path. Never raise to
  the caller — the cache layer above relies on falsy returns to trigger
  fallback to the next backend.

Backends MUST NOT:
- Build envelopes (timestamp / backend tag are caller-filled).
- Make routing or fallback decisions.
- Interpret the `ttl_seconds` parameter beyond the backend's own TTL
  mechanism (no caching-policy decisions).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Backend(Protocol):
    """Pluggable cache storage backend."""

    def save(self, key: str, envelope: dict, ttl_seconds: int | None = None) -> bool:
        """Persist envelope dict under `key` with optional native TTL.

        `ttl_seconds=None` means "no native expiry" — the file backend
        ignores it, Redis uses `set` instead of `setex`, Mongo omits
        `expires_at`. Non-None values trigger backend-native TTL.

        Returns True on success, False on any failure (must not raise).
        """
        ...

    def load(self, key: str) -> dict | None:
        """Load envelope dict for `key`.

        Returns the envelope dict on hit, None on miss / failure
        (must not raise).
        """
        ...

    def clear(self, max_age_days: int) -> None:
        """Clear cached entries older than `max_age_days` (0 = clear all).

        Backend-specific semantics:
        - File: delete `*.json.gz` whose mtime predates the cutoff
        - Redis: `max_age_days=0` calls `flushdb()`; non-zero is a no-op
          (Redis enforces native TTL itself)
        - Mongo: `max_age_days=0` calls `delete_many({})`; non-zero
          calls `delete_many({"timestamp": {"$lt": cutoff}})`

        Must not raise.
        """
        ...
