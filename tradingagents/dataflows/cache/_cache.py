"""`Cache` — unified cache public API (sub-stage 4.4).

Replaces the two-layer wrapping (`IntegratedCacheManager` boolean-branch on
`use_adaptive` + `AdaptiveCacheSystem` primary/fallback routing) with a single
class that owns envelope construction, primary-backend routing, fallback
selection, and TTL inference.

Old classes (`IntegratedCacheManager` / `AdaptiveCacheSystem`) remain available
with a DeprecationWarning on construction — they're removed in 4.6 after an
observation window.

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
        # A 股代码：6 位纯数字
        market = "china" if (len(symbol) == 6 and symbol.isdigit()) else "us"
        ttl_key = f"{market}_{data_type}"
        return self.config.ttl_settings.get(ttl_key, 7200)

    @staticmethod
    def _is_fresh(cache_time: datetime | None, ttl_seconds: int) -> bool:
        if cache_time is None:
            return False
        return datetime.now() < cache_time + timedelta(seconds=ttl_seconds)

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
        """Save via primary backend; fall back to file if enabled."""
        primary = self._primary_backend()
        # Primary 写：file 后端是 primary 时直接走 file，不再 fallback（同实例）
        if primary is self.file_backend:
            return self.file_backend.save(key, envelope, ttl_seconds=ttl_seconds)
        # Primary 是 redis / mongo
        if primary is not None:
            ok = primary.save(key, envelope, ttl_seconds=ttl_seconds)
            if ok:
                return True
        # Primary 失败或不可用 → 视 fallback_enabled 决定是否降级到 file
        if self.config.fallback_enabled:
            return self.file_backend.save(key, envelope, ttl_seconds=ttl_seconds)
        return False

    def _load_routed(self, key: str) -> dict | None:
        """Load via primary backend; fall back to file if enabled and primary miss."""
        primary = self._primary_backend()
        if primary is self.file_backend:
            return self.file_backend.load(key)
        if primary is not None:
            env = primary.load(key)
            if env is not None:
                return env
        if self.config.fallback_enabled and primary is not self.file_backend:
            return self.file_backend.load(key)
        return None

    # ----- public API: stock_data -----

    def save_stock_data(
        self,
        symbol: str,
        data: Any,
        start_date: str = "",
        end_date: str = "",
        data_source: str = "default",
    ) -> str:
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
        # Optional explicit max_age_hours overrides config TTL
        if max_age_hours is not None:
            if not self._is_fresh(env.get("timestamp"), max_age_hours * 3600):
                return None
        return cache_key

    # ----- public API: fundamentals_data -----

    def save_fundamentals_data(
        self,
        symbol: str,
        data: Any,
        data_source: str = "unknown",
    ) -> str:
        cache_key = self._get_cache_key(symbol, "", "", data_source, "fundamentals")
        metadata = {
            "symbol": symbol,
            "data_source": data_source,
            "data_type": "fundamentals",
        }
        envelope = {
            "data": data,
            "metadata": metadata,
            "timestamp": datetime.now(),
            "backend": self.config.primary_backend,
        }
        ttl_seconds = self._get_ttl_seconds(symbol, "fundamentals")
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
        return env.get("data")

    def find_cached_fundamentals_data(
        self,
        symbol: str,
        data_source: str | None = None,
        max_age_hours: int | None = None,
    ) -> str | None:
        cache_key = self._get_cache_key(symbol, "", "", data_source or "unknown", "fundamentals")
        env = self._load_routed(cache_key)
        if env is None:
            return None
        if max_age_hours is not None:
            if not self._is_fresh(env.get("timestamp"), max_age_hours * 3600):
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
        # 默认 stock_data TTL；symbol 决定 market
        ttl_seconds = self._get_ttl_seconds(symbol or "", data_type or "stock_data")
        return self._is_fresh(env.get("timestamp"), ttl_seconds)

    # ----- public API: stats + info -----

    def get_cache_stats(self) -> dict[str, Any]:
        # file backend 文件目录统计（与 4.4 前 AdaptiveCacheSystem.get_cache_stats 同源）
        cache_dir = self.file_backend.cache_dir
        total_files = 0
        total_size_bytes = 0
        try:
            for f in cache_dir.glob("*.json.gz"):
                total_files += 1
                total_size_bytes += f.stat().st_size
        except Exception as e:
            self._logger.warning(f"cache stats walk failed: {e}")
        return {
            "primary_backend": self.config.primary_backend,
            "fallback_enabled": self.config.fallback_enabled,
            "total_files": total_files,
            "total_size_bytes": total_size_bytes,
            "total_size_mb": round(total_size_bytes / (1024 * 1024), 2),
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
        cache_dir = self.file_backend.cache_dir
        cutoff = datetime.now() - timedelta(days=max_age_days)
        cleared = 0
        try:
            for f in cache_dir.glob("*.json.gz"):
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    if mtime < cutoff:
                        f.unlink()
                        cleared += 1
                except Exception as e:
                    self._logger.warning(f"clear_old_cache skip {f}: {e}")
        except Exception as e:
            self._logger.warning(f"clear_old_cache walk failed: {e}")
        if cleared:
            self._logger.info(f"cleared {cleared} aged cache files (>{max_age_days}d)")
