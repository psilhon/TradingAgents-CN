"""`Backend` Protocol — minimal pluggable interface for cache storage backends.

Defined per `docs/specs/dataflow-caching/spec.md` Requirement "Backend Protocol
接口" (sub-stage 4.1).

The 4.1 protocol intentionally exposes only `save` / `load`. `list_keys` /
`delete` will be added when 4.2 (Redis / Mongo backends) or 4.4 (unified
`Cache` class) actually need them — deferring keeps the surface area tight
and avoids speculative methods that lock-in design decisions before there's
a real consumer.

Backends MUST:
- Treat envelopes as opaque dicts. Do not inspect `timestamp` / `backend` /
  `data` / `metadata` fields; serialize via `_serialize.py` and persist as-is.
- Return `False` (save) / `None` (load) on any failure path. Never raise to
  the caller — the cache layer above relies on falsy returns to trigger
  fallback to the next backend.

Backends MUST NOT:
- Build envelopes (timestamp / backend tag are caller-filled).
- Make routing or fallback decisions.
- Check TTL / cache validity (the cache layer owns that).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Backend(Protocol):
    """Pluggable cache storage backend."""

    def save(self, key: str, envelope: dict) -> bool:
        """Persist envelope dict under `key`.

        Returns True on success, False on any failure (must not raise).
        """
        ...

    def load(self, key: str) -> dict | None:
        """Load envelope dict for `key`.

        Returns the envelope dict on hit, None on miss / failure
        (must not raise).
        """
        ...
