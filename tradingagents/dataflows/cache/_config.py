"""`CacheConfig` — single source of truth for cache layer backend configuration.

Defined per `docs/specs/dataflow-caching/spec.md` Requirement "CacheConfig 单一
来源" (sub-stage 4.3).

Frozen dataclass. Replaces the dict-via-`db_manager.get_config()["cache"]`
indirection + module-level `TA_CACHE_STRATEGY` env read. Constructors:

- direct: `CacheConfig(cache_strategy=..., primary_backend=..., ...)` — for
  unit tests where you want to dictate exact backend behavior without
  threading mocks through the db_manager
- factory: `CacheConfig.from_environment(db_manager)` — production path; reads
  `TA_CACHE_STRATEGY` env each call (NOT cached at module load) and derives
  `primary_backend` from `db_manager.is_redis_available()` /
  `is_mongodb_available()`

Out of scope (per 4.3 proposal):
- `TA_USE_APP_CACHE` — dataflow data-source priority switch, orthogonal to
  cache backend selection
- `cache_dir` / Mongo `db_name` / `collection_name` — constructor args, not
  configuration
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal

_logger = logging.getLogger(__name__)

CacheStrategy = Literal["integrated", "adaptive", "file"]
PrimaryBackend = Literal["redis", "mongodb", "file"]

_VALID_STRATEGIES: frozenset[str] = frozenset({"integrated", "adaptive", "file"})
_DEFAULT_STRATEGY: CacheStrategy = "integrated"

# TTL defaults — byte-for-byte match with pre-4.3 db_manager.get_config()["cache"]["ttl_settings"].
# Wrapped in MappingProxyType so the default field value is itself immutable (frozen dataclass
# only freezes the field assignment, not the underlying mutable container).
_DEFAULT_TTL_SETTINGS: Mapping[str, int] = MappingProxyType(
    {
        # 美股数据 TTL（秒）
        "us_stock_data": 7200,  # 2 小时
        "us_news": 21600,  # 6 小时
        "us_fundamentals": 86400,  # 24 小时
        # A 股数据 TTL（秒）
        "china_stock_data": 3600,  # 1 小时
        "china_news": 14400,  # 4 小时
        "china_fundamentals": 43200,  # 12 小时
    }
)


@dataclass(frozen=True)
class CacheConfig:
    """Cache layer backend configuration — single source of truth."""

    cache_strategy: CacheStrategy
    primary_backend: PrimaryBackend
    fallback_enabled: bool
    ttl_settings: Mapping[str, int] = field(default_factory=lambda: _DEFAULT_TTL_SETTINGS)

    @classmethod
    def from_environment(cls, db_manager: Any) -> CacheConfig:
        """Construct from env + db_manager runtime detection.

        - `cache_strategy`: env `TA_CACHE_STRATEGY`; invalid values fall back
          to `"integrated"` (logged at WARNING).
        - `primary_backend`: derived from `db_manager.is_redis_available()` /
          `is_mongodb_available()` — redis preferred, then mongo, then file.
        - `fallback_enabled`: hardcoded `True` (matches pre-4.3 behavior).
        - `ttl_settings`: `_DEFAULT_TTL_SETTINGS` (matches pre-4.3 byte-level).
        """
        strategy_raw = os.getenv("TA_CACHE_STRATEGY", _DEFAULT_STRATEGY)
        if strategy_raw not in _VALID_STRATEGIES:
            _logger.warning(f"TA_CACHE_STRATEGY={strategy_raw!r} is not in {_VALID_STRATEGIES}; falling back to {_DEFAULT_STRATEGY!r}")
            strategy: CacheStrategy = _DEFAULT_STRATEGY
        else:
            strategy = strategy_raw  # type: ignore[assignment]

        if db_manager.is_redis_available():
            primary: PrimaryBackend = "redis"
        elif db_manager.is_mongodb_available():
            primary = "mongodb"
        else:
            primary = "file"

        return cls(
            cache_strategy=strategy,
            primary_backend=primary,
            fallback_enabled=True,
            ttl_settings=_DEFAULT_TTL_SETTINGS,
        )
