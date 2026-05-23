"""Cache backends — pluggable storage layer for `AdaptiveCacheSystem`.

Each backend implements the `Backend` Protocol (`_protocol.py`): a thin
bytes-in / bytes-out layer that takes envelope dicts and persists them to a
specific medium (filesystem, Redis, MongoDB, ...).

Backends MUST NOT contain routing / fallback / TTL logic — those belong to
the cache layer above (`AdaptiveCacheSystem` today, unified `Cache` class
in stage 4.4).

sub-stage 4.1 introduces `Backend` + `FileBackend`. Redis / Mongo backends
follow in 4.2.
"""

from __future__ import annotations

from ._protocol import Backend
from .file import FileBackend

__all__ = ["Backend", "FileBackend"]
