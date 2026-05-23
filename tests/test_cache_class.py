"""新 Cache 类单元测试 — sub-stage 4.4 cache-unified-class.

`Cache` 取代 IntegratedCacheManager + AdaptiveCacheSystem 包装层 + 路由层，
吸收 envelope 构建 / primary backend 路由 / fallback 降级 / TTL 推断。

依赖拓扑：_serialize → _config + backends/{_protocol,file,redis,mongo} → _cache
逐个 spec_from_file_location 加载到 sys.modules 跳过 dataflows 包 init 副作用。
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

_CACHE_DIR = Path(__file__).resolve().parents[1] / "tradingagents" / "dataflows" / "cache"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# 依赖按拓扑序加载到 sys.modules
_load_module("tradingagents.dataflows.cache._serialize", _CACHE_DIR / "_serialize.py")
_config_mod = _load_module("tradingagents.dataflows.cache._config", _CACHE_DIR / "_config.py")
CacheConfig = _config_mod.CacheConfig

_load_module("tradingagents.dataflows.cache.backends._protocol", _CACHE_DIR / "backends" / "_protocol.py")
_load_module("tradingagents.dataflows.cache.backends.file", _CACHE_DIR / "backends" / "file.py")
_load_module("tradingagents.dataflows.cache.backends.redis", _CACHE_DIR / "backends" / "redis.py")
_load_module("tradingagents.dataflows.cache.backends.mongo", _CACHE_DIR / "backends" / "mongo.py")
# backends/__init__.py re-exports FileBackend / RedisBackend / MongoBackend / Backend
_backends_pkg = _load_module("tradingagents.dataflows.cache.backends", _CACHE_DIR / "backends" / "__init__.py")
FileBackend = _backends_pkg.FileBackend

# 最后加载 _cache.py — 它的绝对 import 命中 sys.modules
_cache_mod = _load_module("_cache_under_test", _CACHE_DIR / "_cache.py")
Cache = _cache_mod.Cache


# --- Helpers ---


def _default_ttl_settings() -> dict[str, int]:
    return {
        "us_stock_data": 7200,
        "us_news": 21600,
        "us_fundamentals": 86400,
        "china_stock_data": 3600,
        "china_news": 14400,
        "china_fundamentals": 43200,
    }


def _make_config(primary: str = "file", fallback: bool = True, strategy: str = "integrated"):
    return CacheConfig(
        cache_strategy=strategy,
        primary_backend=primary,  # type: ignore[arg-type]
        fallback_enabled=fallback,
        ttl_settings=_default_ttl_settings(),
    )


# --- 构造 + 注入 ---


def test_construct_with_file_backend_only(tmp_path: Path) -> None:
    file_backend = FileBackend(cache_dir=tmp_path)
    config = _make_config(primary="file")
    cache = Cache(file_backend=file_backend, config=config)
    # redis / mongo 默认 None
    assert cache is not None


def test_construct_with_all_backends(tmp_path: Path) -> None:
    file_backend = FileBackend(cache_dir=tmp_path)
    redis_backend = MagicMock()
    mongo_backend = MagicMock()
    config = _make_config(primary="redis")
    cache = Cache(file_backend=file_backend, config=config, redis_backend=redis_backend, mongo_backend=mongo_backend)
    assert cache is not None


# --- save_stock_data + load_stock_data round-trip (primary=file) ---


def test_save_load_stock_data_roundtrip(tmp_path: Path) -> None:
    file_backend = FileBackend(cache_dir=tmp_path)
    cache = Cache(file_backend=file_backend, config=_make_config(primary="file"))
    cache_key = cache.save_stock_data("AAPL", {"price": 150}, "2026-01-01", "2026-01-02", "test_source")
    assert cache_key != "" and cache_key is not None
    loaded = cache.load_stock_data(cache_key)
    assert loaded == {"price": 150}


def test_cache_key_deterministic(tmp_path: Path) -> None:
    file_backend = FileBackend(cache_dir=tmp_path)
    cache = Cache(file_backend=file_backend, config=_make_config(primary="file"))
    key1 = cache.save_stock_data("AAPL", {"x": 1}, "2026-01-01", "2026-01-02", "src")
    key2 = cache.save_stock_data("AAPL", {"x": 2}, "2026-01-01", "2026-01-02", "src")
    assert key1 == key2  # 同 symbol+dates+source → 同 cache_key


# --- 路由 ---


def test_routes_to_redis_when_primary_redis() -> None:
    file_backend = MagicMock(spec=FileBackend)
    file_backend.save.return_value = True
    redis_backend = MagicMock()
    redis_backend.save.return_value = True
    cache = Cache(
        file_backend=file_backend,
        config=_make_config(primary="redis"),
        redis_backend=redis_backend,
    )
    cache.save_stock_data("AAPL", {"x": 1}, "2026-01-01", "2026-01-02", "src")
    assert redis_backend.save.called
    assert not file_backend.save.called


def test_routes_to_mongo_when_primary_mongodb() -> None:
    file_backend = MagicMock(spec=FileBackend)
    file_backend.save.return_value = True
    mongo_backend = MagicMock()
    mongo_backend.save.return_value = True
    cache = Cache(
        file_backend=file_backend,
        config=_make_config(primary="mongodb"),
        mongo_backend=mongo_backend,
    )
    cache.save_stock_data("AAPL", {"x": 1}, "2026-01-01", "2026-01-02", "src")
    assert mongo_backend.save.called
    assert not file_backend.save.called


# --- fallback ---


def test_fallback_enabled_when_primary_fails(tmp_path: Path) -> None:
    file_backend = FileBackend(cache_dir=tmp_path)  # 用真 backend 让 fallback 写真文件
    redis_backend = MagicMock()
    redis_backend.save.return_value = False  # 主后端失败
    cache = Cache(
        file_backend=file_backend,
        config=_make_config(primary="redis", fallback=True),
        redis_backend=redis_backend,
    )
    cache_key = cache.save_stock_data("AAPL", {"x": 1}, "2026-01-01", "2026-01-02", "src")
    assert cache_key != ""  # 返非空（fallback 成功）
    # 真 file_backend 应有文件写入
    assert any(tmp_path.glob("*.json.gz"))


def test_fallback_disabled_when_primary_fails() -> None:
    file_backend = MagicMock(spec=FileBackend)
    file_backend.save.return_value = True
    redis_backend = MagicMock()
    redis_backend.save.return_value = False
    cache = Cache(
        file_backend=file_backend,
        config=_make_config(primary="redis", fallback=False),
        redis_backend=redis_backend,
    )
    cache_key = cache.save_stock_data("AAPL", {"x": 1}, "2026-01-01", "2026-01-02", "src")
    assert cache_key == ""  # 返空字符串（fallback 关闭）
    assert not file_backend.save.called


# --- load 路由 + fallback ---


def test_load_routes_to_primary_redis_hit() -> None:
    file_backend = MagicMock(spec=FileBackend)
    redis_backend = MagicMock()
    redis_backend.load.return_value = {"data": {"x": 99}, "metadata": {}, "timestamp": datetime.now(), "backend": "redis"}
    cache = Cache(
        file_backend=file_backend,
        config=_make_config(primary="redis"),
        redis_backend=redis_backend,
    )
    result = cache.load_stock_data("any_key")
    assert result == {"x": 99}
    assert not file_backend.load.called


def test_load_falls_back_to_file_on_primary_miss(tmp_path: Path) -> None:
    file_backend = FileBackend(cache_dir=tmp_path)
    # 先写入 file_backend
    file_backend.save("fallback_key", {"data": {"x": 7}, "metadata": {}, "timestamp": datetime.now(), "backend": "file"})

    redis_backend = MagicMock()
    redis_backend.load.return_value = None  # primary miss
    cache = Cache(
        file_backend=file_backend,
        config=_make_config(primary="redis", fallback=True),
        redis_backend=redis_backend,
    )
    result = cache.load_stock_data("fallback_key")
    assert result == {"x": 7}


# --- find_cached_stock_data ---


def test_find_cached_stock_data_after_save(tmp_path: Path) -> None:
    file_backend = FileBackend(cache_dir=tmp_path)
    cache = Cache(file_backend=file_backend, config=_make_config(primary="file"))
    cache.save_stock_data("AAPL", {"x": 1}, "2026-01-01", "2026-01-02", "src")
    # find 同 args 应找到（max_age_hours 默认应足够大）
    found = cache.find_cached_stock_data("AAPL", "2026-01-01", "2026-01-02", "src", max_age_hours=24)
    assert found is not None and found != ""


def test_find_cached_stock_data_returns_none_when_missing(tmp_path: Path) -> None:
    file_backend = FileBackend(cache_dir=tmp_path)
    cache = Cache(file_backend=file_backend, config=_make_config(primary="file"))
    found = cache.find_cached_stock_data("MSFT", "2026-01-01", "2026-01-02", "src", max_age_hours=24)
    assert found is None


# --- fundamentals_data 同 stock_data 模式 ---


def test_save_load_fundamentals_data_roundtrip(tmp_path: Path) -> None:
    file_backend = FileBackend(cache_dir=tmp_path)
    cache = Cache(file_backend=file_backend, config=_make_config(primary="file"))
    cache_key = cache.save_fundamentals_data("AAPL", "<fundamentals_report>", "finnhub")
    assert cache_key != ""
    loaded = cache.load_fundamentals_data(cache_key)
    assert loaded == "<fundamentals_report>"


def test_find_cached_fundamentals_data_after_save(tmp_path: Path) -> None:
    file_backend = FileBackend(cache_dir=tmp_path)
    cache = Cache(file_backend=file_backend, config=_make_config(primary="file"))
    cache.save_fundamentals_data("AAPL", "<report>", "finnhub")
    found = cache.find_cached_fundamentals_data("AAPL", "finnhub", max_age_hours=24)
    assert found is not None


# --- is_cache_valid TTL ---


def test_is_cache_valid_fresh_within_ttl(tmp_path: Path) -> None:
    file_backend = FileBackend(cache_dir=tmp_path)
    cache = Cache(file_backend=file_backend, config=_make_config(primary="file"))
    cache_key = cache.save_stock_data("AAPL", {"x": 1}, "2026-01-01", "2026-01-02", "src")
    # 刚 save 完，envelope.timestamp = now，远在 TTL 内
    assert cache.is_cache_valid(cache_key, symbol="AAPL", data_type="stock_data") is True


def test_is_cache_valid_stale_beyond_ttl(tmp_path: Path) -> None:
    file_backend = FileBackend(cache_dir=tmp_path)
    cache = Cache(file_backend=file_backend, config=_make_config(primary="file"))
    # 直接写一个 timestamp 远过期的 envelope
    cache_key = "stale_key"
    stale_envelope = {
        "data": {"x": 1},
        "metadata": {"symbol": "AAPL", "data_type": "stock_data"},
        "timestamp": datetime.now() - timedelta(hours=25),  # 美股 stock_data TTL=7200s=2h
        "backend": "file",
    }
    file_backend.save(cache_key, stale_envelope)
    # 美股 symbol（AAPL 非 6 位数字）→ market="us" → TTL=us_stock_data=7200s=2h
    assert cache.is_cache_valid(cache_key, symbol="AAPL", data_type="stock_data") is False


# --- get_cache_stats / get_cache_backend_info ---


def test_get_cache_stats_returns_dict(tmp_path: Path) -> None:
    file_backend = FileBackend(cache_dir=tmp_path)
    cache = Cache(file_backend=file_backend, config=_make_config(primary="file"))
    stats = cache.get_cache_stats()
    assert isinstance(stats, dict)
    # 保留 app/routers/cache.py 消费的字段
    assert "primary_backend" in stats or "backend_info" in stats


def test_get_cache_backend_info_returns_dict(tmp_path: Path) -> None:
    file_backend = FileBackend(cache_dir=tmp_path)
    cache = Cache(file_backend=file_backend, config=_make_config(primary="file"))
    info = cache.get_cache_backend_info()
    assert isinstance(info, dict)
    assert info.get("primary_backend") == "file"
    assert "fallback_enabled" in info


# --- clear_old_cache ---


def test_clear_old_cache_removes_aged_files(tmp_path: Path) -> None:
    import os

    file_backend = FileBackend(cache_dir=tmp_path)
    cache = Cache(file_backend=file_backend, config=_make_config(primary="file"))
    cache.save_stock_data("OLD", {"x": 1}, "2024-01-01", "2024-01-02", "src")
    # 把文件 mtime 改到 100 天前
    for f in tmp_path.glob("*.json.gz"):
        old_ts = (datetime.now() - timedelta(days=100)).timestamp()
        os.utime(f, (old_ts, old_ts))
    # max_age_days=7 应清掉 100 天前的文件
    cache.clear_old_cache(max_age_days=7)
    assert not any(tmp_path.glob("*.json.gz"))


def test_clear_old_cache_preserves_fresh_files(tmp_path: Path) -> None:
    file_backend = FileBackend(cache_dir=tmp_path)
    cache = Cache(file_backend=file_backend, config=_make_config(primary="file"))
    cache.save_stock_data("FRESH", {"x": 1}, "2026-01-01", "2026-01-02", "src")
    cache.clear_old_cache(max_age_days=7)
    # 文件刚创建，不应被删
    assert any(tmp_path.glob("*.json.gz"))


# --- 4.8 E3: typed dispatch helper (公开方法 → _save_typed / _find_typed) ---


def test_save_methods_dispatch_through_save_typed(tmp_path: Path) -> None:
    """Public `save_stock_data` / `save_fundamentals_data` MUST funnel through `_save_typed`.

    Spy on `_save_typed`, exercise both public methods, verify each was
    routed with the expected `data_type` + identity-field shape.
    Failing this means a future refactor accidentally re-duplicated the
    dispatch logic — defeating the 4.8 dedup goal.
    """
    file_backend = FileBackend(cache_dir=tmp_path)
    cache = Cache(file_backend=file_backend, config=_make_config(primary="file"))

    original = cache._save_typed
    calls: list[dict] = []

    def spy(symbol, data, data_type, id_fields):
        calls.append({"symbol": symbol, "data_type": data_type, "id_fields": dict(id_fields)})
        return original(symbol, data, data_type, id_fields)

    cache._save_typed = spy  # type: ignore[method-assign]

    cache.save_stock_data("AAPL", {"x": 1}, "2024-01-01", "2024-12-31", "yfinance")
    cache.save_fundamentals_data("AAPL", {"y": 2}, "finnhub")

    assert len(calls) == 2, f"expected 2 dispatch calls, got {len(calls)}"

    # stock_data path
    assert calls[0]["data_type"] == "stock_data"
    assert calls[0]["id_fields"] == {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "data_source": "yfinance",
    }

    # fundamentals_data path — no start_date/end_date in id_fields (preserves
    # metadata shape; envelope.metadata MUST NOT carry empty-string date columns)
    assert calls[1]["data_type"] == "fundamentals_data"
    assert calls[1]["id_fields"] == {"data_source": "finnhub"}


def test_find_methods_dispatch_through_find_typed(tmp_path: Path) -> None:
    """Public `find_cached_*` MUST funnel through `_find_typed`."""
    file_backend = FileBackend(cache_dir=tmp_path)
    cache = Cache(file_backend=file_backend, config=_make_config(primary="file"))

    original = cache._find_typed
    calls: list[dict] = []

    def spy(symbol, data_type, id_fields, max_age_hours=None):
        calls.append({"symbol": symbol, "data_type": data_type, "id_fields": dict(id_fields), "max_age_hours": max_age_hours})
        return original(symbol, data_type, id_fields, max_age_hours)

    cache._find_typed = spy  # type: ignore[method-assign]

    cache.find_cached_stock_data("AAPL", "2024-01-01", "2024-12-31", "yfinance")
    cache.find_cached_fundamentals_data("AAPL", "finnhub", max_age_hours=12)

    assert len(calls) == 2
    assert calls[0]["data_type"] == "stock_data"
    assert calls[0]["id_fields"]["start_date"] == "2024-01-01"
    assert calls[1]["data_type"] == "fundamentals_data"
    assert calls[1]["max_age_hours"] == 12
    assert "start_date" not in calls[1]["id_fields"]


def test_load_methods_dispatch_through_load_typed(tmp_path: Path) -> None:
    """Public `load_*` MUST funnel through `_load_typed` (the dedup target)."""
    file_backend = FileBackend(cache_dir=tmp_path)
    cache = Cache(file_backend=file_backend, config=_make_config(primary="file"))

    cache.save_stock_data("AAPL", {"x": 1}, "2024-01-01", "2024-12-31", "yfinance")
    cache.save_fundamentals_data("AAPL", {"y": 2}, "finnhub")

    original = cache._load_typed
    call_count = {"n": 0}

    def spy(cache_key):
        call_count["n"] += 1
        return original(cache_key)

    cache._load_typed = spy  # type: ignore[method-assign]

    # Look up cache_keys to feed into load_*; both should route via _load_typed
    stock_key = cache.find_cached_stock_data("AAPL", "2024-01-01", "2024-12-31", "yfinance")
    fund_key = cache.find_cached_fundamentals_data("AAPL", "finnhub")
    assert stock_key is not None
    assert fund_key is not None

    cache.load_stock_data(stock_key)
    cache.load_fundamentals_data(fund_key)

    assert call_count["n"] == 2, f"expected 2 _load_typed calls (1 per public load_*), got {call_count['n']}"
