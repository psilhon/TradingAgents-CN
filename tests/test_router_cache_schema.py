"""Router-side schema contract test — sub-stage 4.7 T3.

`app/routers/cache.py` reads specific keys from `cache.get_cache_stats()`
and `cache.get_cache_backend_info()` return dicts. This test enforces the
contract from the producer side without mounting the FastAPI app (the
router is in `app/` which is proprietary-licensed; we read it to discover
which keys it depends on, then assert those keys exist in the new Cache).

Catches the silent-zero regression: if a future refactor renames or drops
a stats key, this test fails immediately instead of letting the admin UI
show 0 for everything.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CACHE_DIR = _REPO_ROOT / "tradingagents" / "dataflows" / "cache"
_ROUTER_PATH = _REPO_ROOT / "app" / "routers" / "cache.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_load_module("tradingagents.dataflows.cache._serialize", _CACHE_DIR / "_serialize.py")
_config_mod = _load_module("tradingagents.dataflows.cache._config", _CACHE_DIR / "_config.py")
CacheConfig = _config_mod.CacheConfig
_load_module("tradingagents.dataflows.cache.backends._protocol", _CACHE_DIR / "backends" / "_protocol.py")
_load_module("tradingagents.dataflows.cache.backends.file", _CACHE_DIR / "backends" / "file.py")
_load_module("tradingagents.dataflows.cache.backends.redis", _CACHE_DIR / "backends" / "redis.py")
_load_module("tradingagents.dataflows.cache.backends.mongo", _CACHE_DIR / "backends" / "mongo.py")
_backends_pkg = _load_module("tradingagents.dataflows.cache.backends", _CACHE_DIR / "backends" / "__init__.py")
FileBackend = _backends_pkg.FileBackend
_cache_mod = _load_module("_cache_under_test_router", _CACHE_DIR / "_cache.py")
Cache = _cache_mod.Cache


def _ttl_defaults() -> dict[str, int]:
    return {
        "us_stock_data": 7200,
        "us_news": 21600,
        "us_fundamentals": 86400,
        "china_stock_data": 3600,
        "china_news": 14400,
        "china_fundamentals": 43200,
    }


def _populated_cache(tmp_path: Path) -> Cache:
    cache = Cache(
        file_backend=FileBackend(cache_dir=tmp_path),
        config=CacheConfig(
            cache_strategy="integrated",
            primary_backend="file",
            fallback_enabled=True,
            ttl_settings=_ttl_defaults(),
        ),
    )
    # Write at least one of each data_type so per-type counts are non-zero
    cache.save_stock_data("AAPL", {"v": 1}, "2026-01-01", "2026-01-02", "src")
    cache.save_fundamentals_data("AAPL", "<report>", "finnhub")
    # News data_type write — bypass the (absent) public API; build envelope directly.
    news_env = {
        "data": "news body",
        "metadata": {"symbol": "AAPL", "data_type": "news_data"},
        "timestamp": datetime.now(),
        "backend": "file",
    }
    cache.file_backend.save("news_test_key", news_env)
    return cache


def _router_consumed_stats_fields() -> set[str]:
    """Discover which keys `app/routers/cache.py` reads from `stats.get(...)`."""
    source = _ROUTER_PATH.read_text()
    return set(re.findall(r"stats\.get\('([^']+)'", source))


def test_get_cache_stats_satisfies_router_contract(tmp_path: Path) -> None:
    """Every key the router reads from stats MUST be in Cache.get_cache_stats() return."""
    router_keys = _router_consumed_stats_fields()
    assert router_keys, "test discovery failed: router doesn't read any stats.get keys"

    cache = _populated_cache(tmp_path)
    stats = cache.get_cache_stats()

    missing = router_keys - set(stats.keys())
    assert not missing, (
        f"Router reads stats.get({missing!r}) but Cache.get_cache_stats() doesn't emit them. "
        f"Stats dict keys produced: {sorted(stats.keys())}"
    )


def test_get_cache_stats_router_required_fields_have_correct_types(tmp_path: Path) -> None:
    """Specifically verify the 5 fields the router uses for the admin UI response."""
    cache = _populated_cache(tmp_path)
    stats = cache.get_cache_stats()

    # Field names from app/routers/cache.py:38-43
    assert isinstance(stats["total_files"], int)
    assert stats["total_files"] >= 3  # we wrote 3 envelopes
    assert isinstance(stats["total_size"], int)
    assert stats["total_size"] > 0
    assert stats["stock_data_count"] == 1
    assert stats["fundamentals_count"] == 1
    assert stats["news_count"] == 1


def test_get_cache_backend_info_satisfies_router_contract(tmp_path: Path) -> None:
    """`app/routers/cache.py:189` falls back gracefully when method missing —
    but should still get a usable dict from the new Cache."""
    cache = _populated_cache(tmp_path)
    info = cache.get_cache_backend_info()
    assert isinstance(info, dict)
    # Router doesn't strictly enforce specific keys here (it returns the dict
    # as-is in the response), but the dict MUST contain primary_backend so the
    # admin UI can display the active backend.
    assert "primary_backend" in info


def test_router_uses_no_undiscovered_stats_keys() -> None:
    """Sanity: this test's regex actually catches the keys the router reads."""
    keys = _router_consumed_stats_fields()
    # Hard-coded expected set from app/routers/cache.py:38-43 — if router changes
    # this assertion catches it and forces a deliberate update.
    expected_minimum = {"total_files", "total_size", "stock_data_count", "news_count", "fundamentals_count"}
    missing_from_discovery = expected_minimum - keys
    assert not missing_from_discovery, f"Regex failed to discover router fields {missing_from_discovery}; update test discovery logic."
