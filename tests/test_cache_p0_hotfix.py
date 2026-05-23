"""P0 hotfix regression tests — sub-stage 4.7.

Covers F1-F8 from the post-4.6 code-review (fundamentals kwarg + data_type
suffix, load/find_cached TTL enforcement, is_cache_valid envelope metadata,
get_cache_stats fields, Backend.clear cross-backend, MongoBackend UTC,
metadata_dir compat property).

Module loading follows the established `spec_from_file_location` pattern so
the package-level dataflows side effects don't fire on import.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _naive_utcnow() -> datetime:
    """Naive UTC datetime — what PyMongo returns by default. Used to simulate the
    backend's view of stored datetimes in tests; production code MUST NOT use
    naive datetimes (see MongoBackend._utcnow)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
_mongo_mod = _load_module("tradingagents.dataflows.cache.backends.mongo", _CACHE_DIR / "backends" / "mongo.py")
MongoBackend = _mongo_mod.MongoBackend
_backends_pkg = _load_module("tradingagents.dataflows.cache.backends", _CACHE_DIR / "backends" / "__init__.py")
FileBackend = _backends_pkg.FileBackend
RedisBackend = _backends_pkg.RedisBackend
_cache_mod = _load_module("_cache_under_test_p0", _CACHE_DIR / "_cache.py")
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


def _make_file_cache(tmp_path: Path):
    return Cache(file_backend=FileBackend(cache_dir=tmp_path), config=_make_config(primary="file"))


# ---------------------------------------------------------------- F7 ----
# Cache key byte-compatible with historical IntegratedCacheManager.


def test_save_fundamentals_data_byte_compat_with_legacy_md5(tmp_path: Path) -> None:
    """save_fundamentals_data MUST hash data_type='fundamentals_data' (with _data suffix)."""
    cache = _make_file_cache(tmp_path)
    new_key = cache.save_fundamentals_data("AAPL", "<report>", "finnhub")
    legacy_key = hashlib.md5(b"AAPL___finnhub_fundamentals_data").hexdigest()
    assert new_key == legacy_key


def test_find_cached_fundamentals_data_byte_compat(tmp_path: Path) -> None:
    cache = _make_file_cache(tmp_path)
    cache.save_fundamentals_data("AAPL", "<report>", "finnhub")
    found = cache.find_cached_fundamentals_data("AAPL", "finnhub")
    expected = hashlib.md5(b"AAPL___finnhub_fundamentals_data").hexdigest()
    assert found == expected


# ---------------------------------------------------------------- F2 ----
# load_stock_data / load_fundamentals_data MUST enforce TTL.


def test_load_stock_data_returns_none_when_stale(tmp_path: Path) -> None:
    cache = _make_file_cache(tmp_path)
    cache_key = cache.save_stock_data("AAPL", {"x": 1}, "2026-01-01", "2026-01-02", "src")
    # Force the file mtime way old by writing an envelope with old timestamp
    stale_env = {
        "data": {"x": 1},
        "metadata": {"symbol": "AAPL", "data_type": "stock_data"},
        "timestamp": datetime.now() - timedelta(hours=25),  # us_stock_data TTL=2h
        "backend": "file",
    }
    cache.file_backend.save(cache_key, stale_env)
    assert cache.load_stock_data(cache_key) is None


def test_load_fundamentals_data_returns_none_when_stale(tmp_path: Path) -> None:
    cache = _make_file_cache(tmp_path)
    cache_key = cache.save_fundamentals_data("AAPL", "<report>", "finnhub")
    stale_env = {
        "data": "<report>",
        "metadata": {"symbol": "AAPL", "data_type": "fundamentals_data"},
        "timestamp": datetime.now() - timedelta(hours=25),  # us_fundamentals TTL=24h
        "backend": "file",
    }
    cache.file_backend.save(cache_key, stale_env)
    assert cache.load_fundamentals_data(cache_key) is None


def test_find_cached_stock_data_default_ttl_when_max_age_none(tmp_path: Path) -> None:
    """find_cached_*(max_age_hours=None) MUST apply default TTL — not return arbitrarily old key."""
    cache = _make_file_cache(tmp_path)
    cache_key = cache.save_stock_data("AAPL", {"x": 1}, "2026-01-01", "2026-01-02", "src")
    stale_env = {
        "data": {"x": 1},
        "metadata": {
            "symbol": "AAPL",
            "data_type": "stock_data",
            "start_date": "2026-01-01",
            "end_date": "2026-01-02",
            "data_source": "src",
        },
        "timestamp": datetime.now() - timedelta(hours=25),
        "backend": "file",
    }
    cache.file_backend.save(cache_key, stale_env)
    found = cache.find_cached_stock_data("AAPL", "2026-01-01", "2026-01-02", "src")
    assert found is None


def test_load_stock_data_fresh_within_ttl_returns_data(tmp_path: Path) -> None:
    """Ensure F2 doesn't over-invalidate fresh entries."""
    cache = _make_file_cache(tmp_path)
    cache_key = cache.save_stock_data("AAPL", {"x": 1}, "2026-01-01", "2026-01-02", "src")
    # Just-written envelope, well within us_stock_data TTL (2h)
    assert cache.load_stock_data(cache_key) == {"x": 1}


# ---------------------------------------------------------------- F6 ----
# is_cache_valid reads envelope.metadata.data_type/symbol first.


def test_is_cache_valid_reads_envelope_metadata_for_a_share_fundamentals(tmp_path: Path) -> None:
    """A-share fundamentals envelope, 6h old, is_cache_valid(no args) MUST return True.

    pre-4.7 bug: default symbol → market='us' + data_type='stock_data' → TTL=7200s
    → 6h-old entry judged STALE (wrong); should consult envelope.metadata.symbol
    ('000001') + data_type ('fundamentals_data') → TTL=43200s (12h) → 6h is fresh.
    """
    cache = _make_file_cache(tmp_path)
    cache_key = "test_a_share_fund"
    env = {
        "data": "<a_share_report>",
        "metadata": {"symbol": "000001", "data_type": "fundamentals_data"},
        "timestamp": datetime.now() - timedelta(hours=6),
        "backend": "file",
    }
    cache.file_backend.save(cache_key, env)
    # Without symbol/data_type args, envelope metadata decides
    assert cache.is_cache_valid(cache_key) is True


def test_is_cache_valid_envelope_overrides_caller_args(tmp_path: Path) -> None:
    cache = _make_file_cache(tmp_path)
    cache_key = "k"
    env = {
        "data": 1,
        "metadata": {"symbol": "000001", "data_type": "fundamentals_data"},
        "timestamp": datetime.now() - timedelta(hours=6),
        "backend": "file",
    }
    cache.file_backend.save(cache_key, env)
    # Even if caller wrongly says symbol='AAPL'/data_type='stock_data',
    # the envelope wins.
    assert cache.is_cache_valid(cache_key, symbol="AAPL", data_type="stock_data") is True


# ---------------------------------------------------------------- F3 ----
# get_cache_stats includes total_size + per-type counts the router reads.


def test_get_cache_stats_has_router_required_fields(tmp_path: Path) -> None:
    cache = _make_file_cache(tmp_path)
    cache.save_stock_data("AAPL", {"a": 1}, "2026-01-01", "2026-01-02", "s")
    cache.save_stock_data("MSFT", {"b": 2}, "2026-01-01", "2026-01-02", "s")
    cache.save_fundamentals_data("AAPL", "<r>", "finnhub")
    stats = cache.get_cache_stats()
    # Pre-existing fields kept
    assert stats["total_files"] >= 3
    assert stats["total_size_bytes"] > 0
    # 4.7 修订: legacy alias + per-type counts
    assert stats["total_size"] == stats["total_size_bytes"]
    assert stats["stock_data_count"] == 2
    assert stats["fundamentals_count"] == 1
    assert stats["news_count"] == 0


def test_get_cache_stats_survives_concurrent_unlink(tmp_path: Path) -> None:
    """One f.stat() FileNotFoundError MUST NOT abort the whole walk (F3 + O3 overlap)."""
    cache = _make_file_cache(tmp_path)
    for i in range(3):
        cache.save_stock_data(f"S{i}", {"v": i}, "2026-01-01", "2026-01-02", "s")
    # Delete one file mid-test
    files = list(tmp_path.glob("*.json.gz"))
    files[0].unlink()
    # Stats should not raise; should count the survivors
    stats = cache.get_cache_stats()
    assert stats["total_files"] >= 1  # at least the survivors counted


# ---------------------------------------------------------------- F8 ----
# Backend Protocol clear method + cross-backend dispatch.


def test_file_backend_clear_deletes_aged_files(tmp_path: Path) -> None:
    fb = FileBackend(cache_dir=tmp_path)
    fb.save("k1", {"data": "x"})
    # Age the file
    import os

    old_ts = (datetime.now() - timedelta(days=100)).timestamp()
    for f in tmp_path.glob("*.json.gz"):
        os.utime(f, (old_ts, old_ts))
    fb.clear(max_age_days=7)
    assert not any(tmp_path.glob("*.json.gz"))


def test_file_backend_clear_zero_deletes_all(tmp_path: Path) -> None:
    fb = FileBackend(cache_dir=tmp_path)
    fb.save("k", {"data": "x"})
    fb.clear(max_age_days=0)
    assert not any(tmp_path.glob("*.json.gz"))


def test_redis_backend_clear_flushes_when_zero() -> None:
    client = MagicMock()
    rb = RedisBackend(redis_client=client)
    rb.clear(0)
    assert client.flushdb.called


def test_redis_backend_clear_noop_when_nonzero() -> None:
    client = MagicMock()
    rb = RedisBackend(redis_client=client)
    rb.clear(7)
    assert not client.flushdb.called


def test_redis_backend_clear_no_client_returns_silently() -> None:
    rb = RedisBackend(redis_client=None)
    rb.clear(0)  # MUST NOT raise


def test_mongo_backend_clear_zero_calls_delete_many_empty_filter() -> None:
    client = MagicMock()
    collection = MagicMock()
    collection.delete_many.return_value = MagicMock(deleted_count=5)
    client.__getitem__.return_value.__getitem__.return_value = collection
    mb = MongoBackend(mongodb_client=client)
    mb.clear(0)
    assert collection.delete_many.called
    assert collection.delete_many.call_args[0][0] == {}


def test_mongo_backend_clear_nonzero_filters_by_timestamp() -> None:
    client = MagicMock()
    collection = MagicMock()
    collection.delete_many.return_value = MagicMock(deleted_count=2)
    client.__getitem__.return_value.__getitem__.return_value = collection
    mb = MongoBackend(mongodb_client=client)
    mb.clear(7)
    assert collection.delete_many.called
    filter_arg = collection.delete_many.call_args[0][0]
    assert "timestamp" in filter_arg
    assert "$lt" in filter_arg["timestamp"]


def test_cache_clear_old_cache_dispatches_to_all_backends(tmp_path: Path) -> None:
    """cache.clear_old_cache(0) MUST call file + redis + mongo clear."""
    fb = FileBackend(cache_dir=tmp_path)
    rb = MagicMock()
    mb = MagicMock()
    config = CacheConfig(
        cache_strategy="integrated",
        primary_backend="redis",
        fallback_enabled=True,
        ttl_settings=_ttl_defaults(),
    )
    cache = Cache(file_backend=fb, config=config, redis_backend=rb, mongo_backend=mb)
    cache.clear_old_cache(0)
    assert rb.clear.called
    assert rb.clear.call_args[0][0] == 0
    assert mb.clear.called
    assert mb.clear.call_args[0][0] == 0


# ---------------------------------------------------------------- F4 ----
# MongoBackend timezone-aware UTC + unknown data_type delete.


def test_mongo_backend_save_writes_utc_aware_timestamps() -> None:
    client = MagicMock()
    collection = MagicMock()
    client.__getitem__.return_value.__getitem__.return_value = collection
    mb = MongoBackend(mongodb_client=client)
    envelope = {
        "data": {"x": 1},
        "metadata": {},
        "timestamp": datetime.now(),
        "backend": "mongodb",
    }
    mb.save("k", envelope, ttl_seconds=3600)
    doc = collection.replace_one.call_args[0][1]
    # Both timestamp and expires_at MUST be tz-aware UTC
    assert doc["timestamp"].tzinfo is not None
    assert doc["expires_at"].tzinfo is not None
    assert doc["timestamp"].tzinfo.utcoffset(None) == timedelta(0)
    assert doc["expires_at"].tzinfo.utcoffset(None) == timedelta(0)


def test_mongo_backend_load_handles_naive_expires_at_as_utc() -> None:
    """PyMongo defaults to naive UTC; backend MUST normalize before comparison."""
    client = MagicMock()
    collection = MagicMock()
    # find_one returns a doc with naive expires_at — simulate pymongo's default
    naive_expired = _naive_utcnow() - timedelta(hours=1)
    collection.find_one.return_value = {
        "_id": "k",
        "data": '{"x": 1}',
        "data_type": "json",
        "metadata": {},
        "timestamp": _naive_utcnow() - timedelta(hours=2),
        "expires_at": naive_expired,
        "backend": "mongodb",
    }
    client.__getitem__.return_value.__getitem__.return_value = collection
    mb = MongoBackend(mongodb_client=client)
    # The naive UTC expires_at is in the past → MUST treat as expired
    result = mb.load("k")
    assert result is None
    assert collection.delete_one.called


def test_mongo_backend_load_unknown_data_type_deletes_doc() -> None:
    client = MagicMock()
    collection = MagicMock()
    collection.find_one.return_value = {
        "_id": "k",
        "data": "garbage",
        "data_type": "future_schema_v99",
        "metadata": {},
        "timestamp": _naive_utcnow(),
        "expires_at": _naive_utcnow() + timedelta(hours=1),
        "backend": "mongodb",
    }
    client.__getitem__.return_value.__getitem__.return_value = collection
    mb = MongoBackend(mongodb_client=client)
    assert mb.load("k") is None
    # Unknown data_type MUST be deleted to prevent zombie accumulation (4.7 修订)
    assert collection.delete_one.called
    assert collection.delete_one.call_args[0][0] == {"_id": "k"}


# ---------------------------------------------------------------- F5 ----
# metadata_dir property exists; glob returns empty silently.


def test_cache_metadata_dir_property_exists(tmp_path: Path) -> None:
    cache = _make_file_cache(tmp_path)
    # MUST NOT raise AttributeError (the bug under default TA_CACHE_STRATEGY=integrated)
    md = cache.metadata_dir
    assert isinstance(md, Path)


def test_cache_metadata_dir_glob_returns_empty(tmp_path: Path) -> None:
    """`_try_get_old_cache` style `self.cache.metadata_dir.glob('*_meta.json')` MUST be safe."""
    cache = _make_file_cache(tmp_path)
    files = list(cache.metadata_dir.glob("*_meta.json"))
    assert files == []  # No legacy metadata in new Cache layout


# ---------------------------------------------------------------- F7 + F1 ----
# Combined: TTL strip + Cache.__init__ validation.


def test_get_ttl_seconds_strips_data_suffix(tmp_path: Path) -> None:
    """_get_ttl_seconds('AAPL', 'fundamentals_data') MUST map to us_fundamentals=86400."""
    cache = _make_file_cache(tmp_path)
    assert cache._get_ttl_seconds("AAPL", "fundamentals_data") == 86400
    assert cache._get_ttl_seconds("AAPL", "news_data") == 21600
    assert cache._get_ttl_seconds("AAPL", "stock_data") == 7200  # no strip
    assert cache._get_ttl_seconds("000001", "fundamentals_data") == 43200
    assert cache._get_ttl_seconds("000001", "news_data") == 14400


def test_cache_init_rejects_missing_redis_backend(tmp_path: Path) -> None:
    fb = FileBackend(cache_dir=tmp_path)
    config = CacheConfig(
        cache_strategy="integrated",
        primary_backend="redis",
        fallback_enabled=True,
        ttl_settings=_ttl_defaults(),
    )
    with pytest.raises(ValueError, match="primary_backend='redis'"):
        Cache(file_backend=fb, config=config, redis_backend=None)


def test_cache_init_rejects_missing_mongo_backend(tmp_path: Path) -> None:
    fb = FileBackend(cache_dir=tmp_path)
    config = CacheConfig(
        cache_strategy="integrated",
        primary_backend="mongodb",
        fallback_enabled=True,
        ttl_settings=_ttl_defaults(),
    )
    with pytest.raises(ValueError, match="primary_backend='mongodb'"):
        Cache(file_backend=fb, config=config, mongo_backend=None)
