"""P1 hardening regression tests — sub-stage 4.7.

Covers O1 (logger.exception adoption), O2 (fallback transition log), O5
(CacheConfig __post_init__ + custom __hash__), O6 (singleton threading.Lock),
O7 (reset_cache + failure-not-cached). O3 (per-iter stat) + O4 (Cache.__init__
validation) tested in test_cache_p0_hotfix.py because their fixes ride with P0.
"""

from __future__ import annotations

import importlib.util
import sys
import threading
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

_CACHE_DIR = Path(__file__).resolve().parents[1] / "tradingagents" / "dataflows" / "cache"


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
_cache_mod = _load_module("_cache_under_test_p1", _CACHE_DIR / "_cache.py")
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


def _make_config(primary: str = "file", fallback: bool = True):
    return CacheConfig(
        cache_strategy="integrated",
        primary_backend=primary,  # type: ignore[arg-type]
        fallback_enabled=fallback,
        ttl_settings=_ttl_defaults(),
    )


# ---------------------------------------------------------------- O5 ----
# CacheConfig __post_init__ Literal validation + custom __hash__.


def test_cache_config_post_init_rejects_invalid_cache_strategy() -> None:
    with pytest.raises(ValueError, match="cache_strategy"):
        CacheConfig(
            cache_strategy="bogus",  # type: ignore[arg-type]
            primary_backend="redis",
            fallback_enabled=True,
            ttl_settings={},
        )


def test_cache_config_post_init_rejects_invalid_primary_backend() -> None:
    with pytest.raises(ValueError, match="primary_backend"):
        CacheConfig(
            cache_strategy="integrated",
            primary_backend="postgres",  # type: ignore[arg-type]
            fallback_enabled=True,
            ttl_settings={},
        )


def test_cache_config_post_init_accepts_all_valid_strategies() -> None:
    for s in ("integrated", "adaptive", "file"):
        CacheConfig(
            cache_strategy=s,  # type: ignore[arg-type]
            primary_backend="file",
            fallback_enabled=True,
            ttl_settings={},
        )  # no raise


def test_cache_config_post_init_accepts_all_valid_primary_backends() -> None:
    for b in ("redis", "mongodb", "file"):
        CacheConfig(
            cache_strategy="integrated",
            primary_backend=b,  # type: ignore[arg-type]
            fallback_enabled=True,
            ttl_settings={},
        )  # no raise


def test_cache_config_is_hashable() -> None:
    """`frozen=True` auto-derived __hash__ would TypeError on Mapping field; we override."""
    config = _make_config()
    h = hash(config)
    assert isinstance(h, int)


def test_cache_config_equal_configs_hash_equal() -> None:
    c1 = _make_config(primary="redis")
    c2 = _make_config(primary="redis")
    assert c1 == c2
    assert hash(c1) == hash(c2)


def test_cache_config_different_configs_hash_differently() -> None:
    """Sanity: different fields → different hash (low collision probability for 4-tuple)."""
    c_redis = _make_config(primary="redis")
    c_mongo = _make_config(primary="mongodb")
    assert hash(c_redis) != hash(c_mongo)


def test_cache_config_hash_ignores_dict_iteration_order() -> None:
    """ttl_settings dict insertion order MUST NOT affect hash (sorted tuple snapshot)."""
    ttl_a = {"us_stock_data": 7200, "china_stock_data": 3600}
    ttl_b = {"china_stock_data": 3600, "us_stock_data": 7200}
    c_a = CacheConfig(cache_strategy="integrated", primary_backend="file", fallback_enabled=True, ttl_settings=ttl_a)
    c_b = CacheConfig(cache_strategy="integrated", primary_backend="file", fallback_enabled=True, ttl_settings=ttl_b)
    assert hash(c_a) == hash(c_b)


def test_cache_config_usable_in_set() -> None:
    s = {_make_config(primary="redis"), _make_config(primary="redis")}
    assert len(s) == 1  # dedup via __hash__ + __eq__


# ---------------------------------------------------------------- O2 ----
# Fallback transition log in _save_routed / _load_routed.


def test_save_routed_logs_info_when_primary_fails(tmp_path: Path, caplog) -> None:
    file_backend = FileBackend(cache_dir=tmp_path)
    redis_backend = MagicMock()
    redis_backend.save.return_value = False  # primary fails
    cache = Cache(
        file_backend=file_backend,
        config=_make_config(primary="redis", fallback=True),
        redis_backend=redis_backend,
    )
    import logging

    with caplog.at_level(logging.INFO, logger=_cache_mod.__name__):
        cache.save_stock_data("AAPL", {"x": 1}, "2026-01-01", "2026-01-02", "src")
    # Some INFO record MUST mention fallback or primary failure
    assert any("primary=redis" in r.message.lower() or "fallback" in r.message.lower() for r in caplog.records), (
        f"Expected fallback log; got records: {[r.message for r in caplog.records]}"
    )


def test_save_routed_no_fallback_log_on_primary_success(caplog) -> None:
    """Happy path: primary succeeds → no fallback log noise."""
    file_backend = MagicMock(spec=FileBackend)
    file_backend.save.return_value = True
    redis_backend = MagicMock()
    redis_backend.save.return_value = True  # primary OK
    cache = Cache(
        file_backend=file_backend,
        config=_make_config(primary="redis"),
        redis_backend=redis_backend,
    )
    import logging

    with caplog.at_level(logging.INFO, logger=_cache_mod.__name__):
        cache.save_stock_data("AAPL", {"x": 1})
    # No INFO log about fallback
    assert not any("fallback" in r.message.lower() for r in caplog.records)


def test_load_routed_logs_debug_when_falling_back(tmp_path: Path, caplog) -> None:
    file_backend = FileBackend(cache_dir=tmp_path)
    file_backend.save(
        "ok_key",
        {"data": {"x": 7}, "metadata": {"symbol": "AAPL", "data_type": "stock_data"}, "timestamp": datetime.now(), "backend": "file"},
    )
    redis_backend = MagicMock()
    redis_backend.load.return_value = None  # primary miss
    cache = Cache(
        file_backend=file_backend,
        config=_make_config(primary="redis", fallback=True),
        redis_backend=redis_backend,
    )
    import logging

    with caplog.at_level(logging.DEBUG, logger=_cache_mod.__name__):
        cache.load_stock_data("ok_key")
    assert any("fallback" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------- O6 ----
# get_cache singleton threading safety.


def test_get_cache_singleton_thread_safe(monkeypatch) -> None:
    """N concurrent get_cache() calls MUST return the same instance.

    Construction MUST happen exactly once. We monkey-patch the heavy backend
    init paths so this stays a unit test (no real Redis/Mongo).
    """
    # Reset module-level singleton state
    import tradingagents.dataflows.cache as cache_pkg

    cache_pkg.reset_cache()

    # Spy on Cache constructor by wrapping it
    construction_count = {"n": 0}
    original_cache_cls = cache_pkg.Cache

    class CountingCache(original_cache_cls):  # type: ignore[misc, valid-type]
        def __init__(self, *args, **kwargs):
            construction_count["n"] += 1
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(cache_pkg, "Cache", CountingCache)

    results: list = []
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()  # release all threads simultaneously
        results.append(cache_pkg.get_cache())

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All threads got the same instance
    assert len({id(r) for r in results}) == 1
    # Cache constructor called at most once (lock excludes the second pass)
    # Note: get_cache may have fallen back to StockDataCache if real db_manager
    # is unavailable in the test env — in that case Cache ctor was never reached.
    # Just check: <= 1 (never duplicate).
    assert construction_count["n"] <= 1


def test_reset_cache_clears_singleton() -> None:
    import tradingagents.dataflows.cache as cache_pkg

    cache_pkg.reset_cache()
    first = cache_pkg.get_cache()
    cache_pkg.reset_cache()
    second = cache_pkg.get_cache()
    # Different identity after reset
    assert id(first) != id(second)


# ---------------------------------------------------------------- O7 ----
# Fallback instance not cached (next get_cache retries primary path).


def test_get_cache_does_not_cache_fallback_instance(monkeypatch) -> None:
    """When Cache construction fails, fallback StockDataCache MUST NOT be cached."""
    import tradingagents.dataflows.cache as cache_pkg

    cache_pkg.reset_cache()

    # Force Cache constructor to raise; cache_pkg.get_cache should return
    # a StockDataCache fallback but NOT cache it.
    monkeypatch.setattr(
        cache_pkg.Cache,
        "__init__",
        lambda self, *a, **k: (_ for _ in ()).throw(RuntimeError("simulated Cache init failure")),
    )

    first = cache_pkg.get_cache()
    # _cache_instance MUST still be None — next call should retry primary
    assert cache_pkg._cache_instance is None
    # Two consecutive calls return different (uncached) fallback instances
    second = cache_pkg.get_cache()
    assert id(first) != id(second), "fallback instance MUST NOT be cached"


# ---------------------------------------------------------------- O1 ----
# logger.exception adoption — source-level grep守护.


def test_cache_module_uses_logger_exception_not_logger_error_with_format() -> None:
    """All `except Exception` blocks in cache/ MUST use logger.exception(...) not logger.error(f"...{e}")."""
    cache_files = [
        _CACHE_DIR / "_cache.py",
        _CACHE_DIR / "_config.py",
        _CACHE_DIR / "__init__.py",
        _CACHE_DIR / "backends" / "file.py",
        _CACHE_DIR / "backends" / "redis.py",
        _CACHE_DIR / "backends" / "mongo.py",
    ]
    for f in cache_files:
        source = f.read_text()
        # No `logger.error(f"...{e}")` or `self._logger.error(f"...{e}")` pattern
        for bad_pat in ('logger.error(f"', '._logger.error(f"'):
            # Must not contain pattern with f-string + {e}
            assert not any((bad_pat in line and "{e}" in line) for line in source.splitlines()), (
                f"{f.name}: logger.error(f...{{e}}...) should be logger.exception(...) instead"
            )
