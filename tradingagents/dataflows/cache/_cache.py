"""`Cache` — unified cache public API.

Single facade that owns envelope construction, primary-backend routing,
fallback selection, TTL inference, and persistence-format-specific tagging
(stock_data vs fundamentals_data vs news_data). Three pluggable backends
(File / Redis / Mongo) implement the `Backend` Protocol for actual storage.

Cache key formula:

    md5(f"{symbol}_{start_date}_{end_date}_{data_source}_{data_type}")

with `data_type` ∈ {"stock_data", "news_data", "fundamentals_data"} — the
`_data` suffix on the non-stock variants is required for byte-compat with
existing cache entries written by earlier versions. TTL lookup strips the
`_data` suffix because the configured TTL keys use the stem form
(`us_fundamentals`, `china_news`, etc.).

Defined per `docs/specs/dataflow-caching/spec.md` Requirement "统一 Cache 类
（公开 API 单一实现）".
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any

from tradingagents.dataflows.cache._config import CacheConfig
from tradingagents.dataflows.cache.backends import FileBackend, MongoBackend, RedisBackend


class Cache:
    """Unified cache facade with pluggable backends + fallback."""

    def __init__(
        self,
        file_backend: FileBackend,
        config: CacheConfig,
        redis_backend: RedisBackend | None = None,
        mongo_backend: MongoBackend | None = None,
    ) -> None:
        # Refuse mis-wired instances at construction time — silent fallback
        # would mask the misconfiguration until a cache-hit-rate alarm fires.
        if config.primary_backend == "redis" and redis_backend is None:
            raise ValueError(
                "Cache config.primary_backend='redis' but redis_backend is None; "
                "either provide a RedisBackend instance or change primary_backend"
            )
        if config.primary_backend == "mongodb" and mongo_backend is None:
            raise ValueError(
                "Cache config.primary_backend='mongodb' but mongo_backend is None; "
                "either provide a MongoBackend instance or change primary_backend"
            )

        self._logger = logging.getLogger(__name__)
        self.file_backend = file_backend
        self.redis_backend = redis_backend
        self.mongo_backend = mongo_backend
        self.config = config

    # ----- internal helpers -----

    @staticmethod
    def _get_cache_key(
        symbol: str,
        start_date: str = "",
        end_date: str = "",
        data_source: str = "default",
        data_type: str = "stock_data",
    ) -> str:
        key_data = f"{symbol}_{start_date}_{end_date}_{data_source}_{data_type}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_ttl_seconds(self, symbol: str, data_type: str = "stock_data") -> int:
        # A-share code: 6 pure digits → china market; otherwise us.
        market = "china" if (len(symbol) == 6 and symbol.isdigit()) else "us"
        # Cache keys carry data_type values with a "_data" suffix
        # ("fundamentals_data", "news_data") so existing cache entries
        # remain readable. The configured TTL keys (_DEFAULT_TTL_SETTINGS)
        # use the stem form ("us_fundamentals", "china_news"). Strip the
        # suffix here so fundamentals/news get their configured TTL instead
        # of the 7200s default.
        stem = data_type[:-5] if data_type.endswith("_data") and data_type != "stock_data" else data_type
        ttl_key = f"{market}_{stem}"
        return self.config.ttl_settings.get(ttl_key, 7200)

    @staticmethod
    def _is_fresh(cache_time: datetime | None, ttl_seconds: int) -> bool:
        if cache_time is None:
            return False
        # Normalize tz-aware (e.g. from MongoBackend UTC) vs naive (file/redis
        # backends still use naive local time) for comparison. Treat naive
        # values as the same wall clock as `datetime.now()`.
        if cache_time.tzinfo is not None:
            from datetime import timezone as _tz

            now = datetime.now(_tz.utc)
        else:
            now = datetime.now()
        return now < cache_time + timedelta(seconds=ttl_seconds)

    def _envelope_is_fresh(self, env: dict) -> bool:
        """Check if an envelope is still within its configured TTL.

        Reads `metadata.symbol` and `metadata.data_type` from the envelope
        to derive the correct TTL bucket — this is the canonical freshness
        check for entries loaded via `load_*` / `find_cached_*`. Falls back
        to a 2h TTL if metadata is missing so a malformed envelope is treated
        as stale rather than indefinitely fresh.
        """
        metadata = env.get("metadata") or {}
        symbol = metadata.get("symbol", "")
        data_type = metadata.get("data_type", "stock_data")
        ttl_seconds = self._get_ttl_seconds(symbol, data_type)
        return self._is_fresh(env.get("timestamp"), ttl_seconds)

    def _primary_backend(self) -> Any:
        """Return the configured primary backend instance, or None if unavailable."""
        name = self.config.primary_backend
        if name == "redis":
            return self.redis_backend
        if name == "mongodb":
            return self.mongo_backend
        if name == "file":
            return self.file_backend
        return None

    def _save_routed(self, key: str, envelope: dict, ttl_seconds: int) -> bool:
        """Save via primary backend; fall back to file if enabled.

        Emits an INFO log when the primary failed and the file fallback is
        engaged so operators can tell when the configured primary backend
        silently dropped out of the write path.
        """
        primary = self._primary_backend()
        # File primary: direct write, no fallback (would be a same-instance retry).
        if primary is self.file_backend:
            return self.file_backend.save(key, envelope, ttl_seconds=ttl_seconds)
        # Redis / Mongo primary
        if primary is not None:
            ok = primary.save(key, envelope, ttl_seconds=ttl_seconds)
            if ok:
                return True
            self._logger.info(f"cache save: primary={self.config.primary_backend} returned False; using file fallback")
        else:
            self._logger.info(f"cache save: primary={self.config.primary_backend} backend unavailable; using file fallback")
        # Primary failed or unavailable → fall back to file if enabled
        if self.config.fallback_enabled:
            return self.file_backend.save(key, envelope, ttl_seconds=ttl_seconds)
        return False

    def _load_routed(self, key: str) -> dict | None:
        """Load via primary backend; fall back to file if enabled and primary miss.

        Emits a DEBUG log when fallback fires — verbose enough to debug a
        cache-coherence issue, quiet enough not to flood under normal use
        (miss is common; promoting to INFO would be noisy).
        """
        primary = self._primary_backend()
        if primary is self.file_backend:
            return self.file_backend.load(key)
        if primary is not None:
            env = primary.load(key)
            if env is not None:
                return env
        if self.config.fallback_enabled and primary is not self.file_backend:
            self._logger.debug(f"cache load: primary={self.config.primary_backend} miss for {key}; trying file fallback")
            return self.file_backend.load(key)
        return None

    # ----- public API: stock_data -----

    def save_stock_data(
        self,
        symbol: str,
        data: Any,
        start_date: str | None = None,
        end_date: str | None = None,
        data_source: str | None = None,
    ) -> str:
        # Normalize None → defaults. Some real callers (e.g.
        # `data_source_manager._save_to_cache`) pass `start_date: str | None`
        # straight through, and f-string formatting of `None` would otherwise
        # leak the literal string "None" into the cache key.
        start_date = start_date or ""
        end_date = end_date or ""
        data_source = data_source or "default"
        cache_key = self._get_cache_key(symbol, start_date, end_date, data_source, "stock_data")
        metadata = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "data_source": data_source,
            "data_type": "stock_data",
        }
        envelope = {
            "data": data,
            "metadata": metadata,
            "timestamp": datetime.now(),
            "backend": self.config.primary_backend,
        }
        ttl_seconds = self._get_ttl_seconds(symbol, "stock_data")
        ok = self._save_routed(cache_key, envelope, ttl_seconds)
        if ok:
            self._logger.debug(f"cache save stock_data: {symbol} -> {cache_key}")
            return cache_key
        self._logger.warning(f"cache save stock_data failed: {symbol}")
        return ""

    def load_stock_data(self, cache_key: str) -> Any | None:
        env = self._load_routed(cache_key)
        if env is None:
            return None
        if not self._envelope_is_fresh(env):
            return None
        return env.get("data")

    def find_cached_stock_data(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        data_source: str | None = None,
        max_age_hours: int | None = None,
    ) -> str | None:
        cache_key = self._get_cache_key(
            symbol,
            start_date or "",
            end_date or "",
            data_source or "default",
            "stock_data",
        )
        env = self._load_routed(cache_key)
        if env is None:
            return None
        # max_age_hours, if given, overrides the configured TTL. Otherwise we
        # enforce the same TTL the load path uses, so callers don't get a
        # cache_key back for an envelope `load_stock_data` would then reject.
        if max_age_hours is not None:
            if not self._is_fresh(env.get("timestamp"), max_age_hours * 3600):
                return None
        elif not self._envelope_is_fresh(env):
            return None
        return cache_key

    # ----- public API: fundamentals_data -----

    def save_fundamentals_data(
        self,
        symbol: str,
        data: Any,
        data_source: str | None = None,
    ) -> str:
        # data_type carries the "_data" suffix so cache keys stay readable
        # across upgrades. TTL lookup strips the suffix (see _get_ttl_seconds).
        data_source = data_source or "default"
        cache_key = self._get_cache_key(symbol, "", "", data_source, "fundamentals_data")
        metadata = {
            "symbol": symbol,
            "data_source": data_source,
            "data_type": "fundamentals_data",
        }
        envelope = {
            "data": data,
            "metadata": metadata,
            "timestamp": datetime.now(),
            "backend": self.config.primary_backend,
        }
        ttl_seconds = self._get_ttl_seconds(symbol, "fundamentals_data")
        ok = self._save_routed(cache_key, envelope, ttl_seconds)
        if ok:
            self._logger.debug(f"cache save fundamentals_data: {symbol} -> {cache_key}")
            return cache_key
        self._logger.warning(f"cache save fundamentals_data failed: {symbol}")
        return ""

    def load_fundamentals_data(self, cache_key: str) -> Any | None:
        env = self._load_routed(cache_key)
        if env is None:
            return None
        if not self._envelope_is_fresh(env):
            return None
        return env.get("data")

    def find_cached_fundamentals_data(
        self,
        symbol: str,
        data_source: str | None = None,
        max_age_hours: int | None = None,
    ) -> str | None:
        cache_key = self._get_cache_key(symbol, "", "", data_source or "default", "fundamentals_data")
        env = self._load_routed(cache_key)
        if env is None:
            return None
        if max_age_hours is not None:
            if not self._is_fresh(env.get("timestamp"), max_age_hours * 3600):
                return None
        elif not self._envelope_is_fresh(env):
            return None
        return cache_key

    # ----- public API: is_cache_valid -----

    def is_cache_valid(
        self,
        cache_key: str,
        symbol: str | None = None,
        data_type: str | None = None,
    ) -> bool:
        env = self._load_routed(cache_key)
        if env is None:
            return False
        # Prefer the envelope's recorded metadata so we pick the right TTL
        # bucket regardless of what the caller passes. Caller-provided symbol
        # / data_type are fallbacks for envelopes missing metadata (which
        # shouldn't happen for entries we wrote ourselves).
        metadata = env.get("metadata") or {}
        effective_symbol = metadata.get("symbol") or symbol or ""
        effective_data_type = metadata.get("data_type") or data_type or "stock_data"
        ttl_seconds = self._get_ttl_seconds(effective_symbol, effective_data_type)
        return self._is_fresh(env.get("timestamp"), ttl_seconds)

    # ----- public API: metadata_dir compatibility -----

    @property
    def metadata_dir(self):
        """Compat shim for callers that used to access `StockDataCache.metadata_dir`.

        Older callsites in `optimized_china_data._try_get_old_cache` /
        `providers/us/optimized._try_get_old_cache` do `self.cache.metadata_dir.glob("*_meta.json")`
        to scan for legacy double-file metadata entries. The new Cache stores
        envelopes inline (no separate `_meta.json`), so we return a Path
        pointing at a never-created subdirectory — the glob yields nothing
        and the callers' `try / except` paths degrade gracefully to None
        (the "use stale cache as last-ditch fallback" feature is silently
        disabled under the new Cache; restoring it is a future sub-stage).
        """
        return self.file_backend.cache_dir / ".compat_empty_metadata"

    # ----- public API: stats + info -----

    def get_cache_stats(self) -> dict[str, Any]:
        """File backend directory stats + per-type counts.

        Counts only `*.json.gz` entries written by the file backend; redis /
        mongo entries are not included because there's no cheap way to size
        them per data_type without round-tripping each key. Per-type counts
        decode each envelope's metadata.data_type — O(N) per stats call, but
        the endpoint is hit interactively, not in hot paths.

        Field names match the historical `app/routers/cache.py:32-46`
        contract (`total_size`, `stock_data_count`, `news_count`,
        `fundamentals_count`) so the admin UI sees real numbers instead of
        silent zeros.
        """
        cache_dir = self.file_backend.cache_dir
        total_files = 0
        total_size_bytes = 0
        stock_data_count = 0
        news_count = 0
        fundamentals_count = 0
        for f in cache_dir.glob("*.json.gz"):
            # Per-file try so one concurrently-deleted entry doesn't abort
            # the whole walk.
            try:
                total_files += 1
                total_size_bytes += f.stat().st_size
                try:
                    env = self.file_backend.load(f.stem.removesuffix(".json"))
                    if env is not None:
                        meta_dt = (env.get("metadata") or {}).get("data_type", "")
                        if meta_dt == "stock_data":
                            stock_data_count += 1
                        elif meta_dt == "news_data":
                            news_count += 1
                        elif meta_dt == "fundamentals_data":
                            fundamentals_count += 1
                except Exception:
                    # Couldn't decode envelope — count it as a file but not
                    # in any per-type bucket; the file is still on disk.
                    self._logger.debug(f"cache stats: envelope decode skip {f.name}")
            except FileNotFoundError:
                # Concurrent unlink between glob and stat — skip, continue walk
                total_files -= 1
                continue
            except Exception:
                self._logger.exception(f"cache stats skip {f.name}")
        return {
            "primary_backend": self.config.primary_backend,
            "fallback_enabled": self.config.fallback_enabled,
            "total_files": total_files,
            # Both keys point at the same number — `total_size_bytes` is the
            # explicit-unit name; `total_size` is the legacy alias the admin
            # router reads (kept for backwards compatibility with the
            # `app/routers/cache.py` schema contract).
            "total_size": total_size_bytes,
            "total_size_bytes": total_size_bytes,
            "total_size_mb": round(total_size_bytes / (1024 * 1024), 2),
            # Per-type counts decode each envelope's metadata.data_type.
            "stock_data_count": stock_data_count,
            "news_count": news_count,
            "fundamentals_count": fundamentals_count,
            "cache_dir": str(cache_dir),
            "backend_info": self.get_cache_backend_info(),
        }

    def get_cache_backend_info(self) -> dict[str, Any]:
        return {
            "primary_backend": self.config.primary_backend,
            "fallback_enabled": self.config.fallback_enabled,
            "cache_strategy": self.config.cache_strategy,
            "redis_available": self.redis_backend is not None,
            "mongodb_available": self.mongo_backend is not None,
        }

    # ----- public API: clear_old_cache -----

    def clear_old_cache(self, max_age_days: int = 7) -> None:
        """Clear aged cache across all configured backends.

        Delegates per-backend cleanup via the Backend Protocol's `clear`
        method so Redis (flushdb on max_age_days=0) and Mongo (delete_many)
        are touched, not just file storage. The `/api/cache/clear` admin
        endpoint relies on this multi-backend dispatch for its "清空所有
        缓存" guarantee.
        """
        # File backend: always
        try:
            self.file_backend.clear(max_age_days)
        except Exception:
            self._logger.exception("clear_old_cache: file backend clear failed")
        # Redis backend: optional
        if self.redis_backend is not None:
            try:
                self.redis_backend.clear(max_age_days)
            except Exception:
                self._logger.exception("clear_old_cache: redis backend clear failed")
        # Mongo backend: optional
        if self.mongo_backend is not None:
            try:
                self.mongo_backend.clear(max_age_days)
            except Exception:
                self._logger.exception("clear_old_cache: mongo backend clear failed")
