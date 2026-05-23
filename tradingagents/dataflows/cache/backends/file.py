"""FileBackend — filesystem `Backend` implementation.

Persists envelope dicts as gzip(JSON) files under `{cache_dir}/{key}.json.gz`,
per the `_serialize.py` envelope format established by stage 2
(`cache-pickle-replacement`).

Single-responsibility: file IO only. Builds nothing, routes nothing, decides
nothing about TTL. The caller (`AdaptiveCacheSystem` in 4.1, future unified
`Cache` class in 4.4) owns those concerns.

Implements `Backend` Protocol (`_protocol.py`).
"""

from __future__ import annotations

import logging
from pathlib import Path

from tradingagents.dataflows.cache._serialize import decode_envelope, encode_envelope


class FileBackend:
    """Filesystem backend — gzip(JSON) envelopes under `cache_dir`."""

    def __init__(self, cache_dir: Path | str) -> None:
        self._logger = logging.getLogger(__name__)
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def cache_dir(self) -> Path:
        """Directory where envelopes are persisted (read-only)."""
        return self._cache_dir

    def save(self, key: str, envelope: dict, ttl_seconds: int | None = None) -> bool:
        """Persist `envelope` under `key` as `{cache_dir}/{key}.json.gz`.

        `ttl_seconds` is accepted to satisfy the Backend Protocol but ignored —
        the filesystem has no native TTL. Expiry is enforced by the cache layer
        above via envelope timestamp + TTL config.
        """
        del ttl_seconds  # accepted per Protocol; no-op for file backend
        try:
            cache_file = self._cache_dir / f"{key}.json.gz"
            with open(cache_file, "wb") as f:
                f.write(encode_envelope(envelope))
            self._logger.debug(f"file backend save: {key}")
            return True
        except Exception as e:
            self._logger.error(f"file backend save failed for {key}: {e}")
            return False

    def load(self, key: str) -> dict | None:
        """Load envelope at `{cache_dir}/{key}.json.gz`, or None on miss."""
        cache_file = self._cache_dir / f"{key}.json.gz"
        if not cache_file.exists():
            return None
        try:
            with open(cache_file, "rb") as f:
                envelope = decode_envelope(f.read())
            self._logger.debug(f"file backend load: {key}")
            return envelope
        except Exception as e:
            self._logger.error(f"file backend load failed for {key}: {e}")
            return None
