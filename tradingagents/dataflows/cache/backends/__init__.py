"""Cache backends — pluggable storage layer for the unified `Cache` class.

Each backend implements the `Backend` Protocol (`_protocol.py`): a thin
bytes-in / bytes-out layer that takes envelope dicts and persists them to a
specific medium (filesystem, Redis, MongoDB, ...).

Backends MUST NOT contain routing / fallback / TTL logic — those belong to
the cache layer above (the `Cache` class in `_cache.py`).
"""

from __future__ import annotations

from ._protocol import Backend
from .file import FileBackend
from .mongo import MongoBackend
from .redis import RedisBackend

__all__ = ["Backend", "FileBackend", "MongoBackend", "RedisBackend"]
