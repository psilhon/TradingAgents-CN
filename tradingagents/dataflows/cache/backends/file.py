"""FileBackend — filesystem `Backend` implementation.

Persists envelope dicts as gzip(JSON) files under `{cache_dir}/{key}.json.gz`,
using the `_serialize.py` envelope format (gzip-compressed JSON with tagged
encoding for `datetime` and `pandas.DataFrame` values).

Single-responsibility: file IO only. Builds nothing, routes nothing, decides
nothing about TTL — the cache layer above (`Cache` in `_cache.py`) owns
those concerns.

Implements `Backend` Protocol (`_protocol.py`).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
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

        **Atomic write (4.8+)**: writes go to a sibling temp file
        `{cache_dir}/.{key}.json.gz.tmp.{pid}` first, then `os.replace`
        atomically renames to the final path. If the process is killed mid-
        write (SIGKILL / OOM / disk full), the final path either stays absent
        or shows the prior complete envelope — never truncated bytes that
        would fail gzip decode on the next read.

        Tmp filename specifics:
        - Leading `.` keeps `glob("*.json.gz")` (e.g. in `Cache.get_cache_stats`)
          from picking up in-flight writes.
        - `.{pid}` suffix lets multiple processes write *different* keys
          concurrently without colliding on the same tmp name. (Same-key
          races within one process aren't a concern — Cache is constructed
          once per worker and methods aren't reentrant on the same key.)
        - POSIX guarantees `os.replace` is atomic on same-filesystem rename
          (project targets macOS/Linux only, so no Windows special-case).
        """
        del ttl_seconds  # accepted per Protocol; no-op for file backend
        cache_file = self._cache_dir / f"{key}.json.gz"
        tmp_file = self._cache_dir / f".{key}.json.gz.tmp.{os.getpid()}"
        try:
            try:
                with open(tmp_file, "wb") as f:
                    f.write(encode_envelope(envelope))
                # `with` block has closed the file → safe to replace
                os.replace(tmp_file, cache_file)
                self._logger.debug(f"file backend save: {key}")
                return True
            except Exception:
                self._logger.exception(f"file backend save failed for {key}")
                return False
        finally:
            # Best-effort cleanup. On success, `os.replace` already consumed
            # tmp_file → unlink raises FileNotFoundError, swallowed by
            # missing_ok. On failure, tmp_file may still exist with partial
            # bytes — unlink keeps the cache_dir from accumulating zombie
            # `.tmp.*` files over time.
            try:
                tmp_file.unlink(missing_ok=True)
            except OSError:
                self._logger.exception(f"file backend tmp cleanup failed for {key}")

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
        except Exception:
            self._logger.exception(f"file backend load failed for {key}")
            return None

    def clear(self, max_age_days: int) -> None:
        """Delete `*.json.gz` files older than `max_age_days` (0 = all)."""
        cutoff = datetime.now() - timedelta(days=max_age_days)
        cleared = 0
        try:
            for f in self._cache_dir.glob("*.json.gz"):
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    if max_age_days == 0 or mtime < cutoff:
                        f.unlink()
                        cleared += 1
                except FileNotFoundError:
                    # Concurrent deletion — skip this file, not the whole walk.
                    continue
                except Exception:
                    self._logger.exception(f"file backend clear skip {f}")
        except Exception:
            self._logger.exception("file backend clear walk failed")
        if cleared:
            self._logger.info(f"file backend cleared {cleared} files (>{max_age_days}d)")
