"""Cache 公开 API None-safe 兼容性测试 — sub-stage 4.5.

4.4 写 Cache 时部分公开方法签名不接受 None，导致 callsite 真实形式（如
`data_source_manager._save_to_cache(start_date: str | None = None)` 透传到
`cache.save_stock_data`）产生与 4.4 前 IntegratedCacheManager 不一致的 cache_key
（"None" 字面量 vs `or ""` normalize 到 ""）。

本测试守护：所有 start_date / end_date / data_source MUST 接受 None + 内部
normalize 到默认值（"" / "" / "default"），生成的 cache_key 字节级与
IntegratedCacheManager 等价。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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


# 依赖按拓扑序加载（与 test_cache_class.py 同模式）
_load_module("tradingagents.dataflows.cache._serialize", _CACHE_DIR / "_serialize.py")
_config_mod = _load_module("tradingagents.dataflows.cache._config", _CACHE_DIR / "_config.py")
CacheConfig = _config_mod.CacheConfig
_load_module("tradingagents.dataflows.cache.backends._protocol", _CACHE_DIR / "backends" / "_protocol.py")
_load_module("tradingagents.dataflows.cache.backends.file", _CACHE_DIR / "backends" / "file.py")
_load_module("tradingagents.dataflows.cache.backends.redis", _CACHE_DIR / "backends" / "redis.py")
_load_module("tradingagents.dataflows.cache.backends.mongo", _CACHE_DIR / "backends" / "mongo.py")
_backends_pkg = _load_module("tradingagents.dataflows.cache.backends", _CACHE_DIR / "backends" / "__init__.py")
FileBackend = _backends_pkg.FileBackend
_cache_mod = _load_module("_cache_under_test_4_5", _CACHE_DIR / "_cache.py")
Cache = _cache_mod.Cache


def _make_config(primary: str = "file", fallback: bool = True):
    return CacheConfig(
        cache_strategy="integrated",
        primary_backend=primary,  # type: ignore[arg-type]
        fallback_enabled=fallback,
        ttl_settings={"us_stock_data": 7200, "us_fundamentals": 86400},
    )


# --- save_stock_data None-safe ---


def test_save_stock_data_accepts_none_start_end_source(tmp_path: Path) -> None:
    """callsite `_save_to_cache(start_date: str | None = None)` 直接透传到 save_stock_data."""
    cache = Cache(file_backend=FileBackend(cache_dir=tmp_path), config=_make_config(primary="file"))
    cache_key = cache.save_stock_data("AAPL", {"x": 1}, None, None, None)
    assert cache_key != ""  # MUST 不 raise + 返非空 key


def test_save_stock_data_none_args_match_default_args(tmp_path: Path) -> None:
    """关键回归：None 入参 cache_key MUST 与 ("","","default") 字节级一致."""
    cache = Cache(file_backend=FileBackend(cache_dir=tmp_path), config=_make_config(primary="file"))
    key_with_none = cache.save_stock_data("AAPL", {"x": 1}, None, None, None)
    # 清掉缓存避免 dup file
    for f in tmp_path.glob("*.json.gz"):
        f.unlink()
    key_with_defaults = cache.save_stock_data("AAPL", {"x": 2}, "", "", "default")
    assert key_with_none == key_with_defaults, f"None-safe cache_key 漂移：None args → {key_with_none}, default args → {key_with_defaults}"


def test_save_stock_data_omitting_optional_args_works(tmp_path: Path) -> None:
    """callsite `foreign_stock_service.py:230` 形式：save_stock_data(symbol=..., data=..., data_source=...) 不传 start/end."""
    cache = Cache(file_backend=FileBackend(cache_dir=tmp_path), config=_make_config(primary="file"))
    cache_key = cache.save_stock_data(symbol="HK700", data={"x": 1}, data_source="hk_realtime_quote")
    assert cache_key != ""


# --- save_fundamentals_data 默认 data_source 兼容性 ---


def test_save_fundamentals_data_default_source_is_default_not_unknown(tmp_path: Path) -> None:
    """关键回归：4.4 写的默认 'unknown' 与 IntegratedCacheManager 的 'default' 不一致.

    save_fundamentals_data(symbol, data) cache_key MUST 与 data_source="default" 字节级相同.
    """
    cache = Cache(file_backend=FileBackend(cache_dir=tmp_path), config=_make_config(primary="file"))
    key_no_source = cache.save_fundamentals_data("AAPL", "<report>")
    for f in tmp_path.glob("*.json.gz"):
        f.unlink()
    key_default = cache.save_fundamentals_data("AAPL", "<report>", "default")
    assert key_no_source == key_default, f"save_fundamentals_data 默认 data_source 漂移：unset → {key_no_source}, 'default' → {key_default}"


def test_save_fundamentals_data_explicit_none_normalizes_to_default(tmp_path: Path) -> None:
    """显式传 None MUST normalize 到 'default'，与不传等价."""
    cache = Cache(file_backend=FileBackend(cache_dir=tmp_path), config=_make_config(primary="file"))
    key_with_none = cache.save_fundamentals_data("AAPL", "<report>", None)
    for f in tmp_path.glob("*.json.gz"):
        f.unlink()
    key_default = cache.save_fundamentals_data("AAPL", "<report>", "default")
    assert key_with_none == key_default


# --- find_cached_* None-safe ---


def test_find_cached_stock_data_with_only_symbol(tmp_path: Path) -> None:
    """callsite 仅传 symbol（其它 optional 全 None）MUST 不 raise."""
    cache = Cache(file_backend=FileBackend(cache_dir=tmp_path), config=_make_config(primary="file"))
    # 先 save 一份，再 find
    cache.save_stock_data("AAPL", {"x": 1})
    # 仅 symbol 调用（其它默认 None）
    found = cache.find_cached_stock_data("AAPL")
    assert found is not None


def test_find_cached_fundamentals_data_with_none_source(tmp_path: Path) -> None:
    """find_cached_fundamentals_data(symbol, data_source=None) MUST 走 'default'."""
    cache = Cache(file_backend=FileBackend(cache_dir=tmp_path), config=_make_config(primary="file"))
    cache.save_fundamentals_data("AAPL", "<report>")  # 默认 'default'
    found = cache.find_cached_fundamentals_data("AAPL", data_source=None)
    assert found is not None, "find_cached_fundamentals_data(data_source=None) MUST 与 save 默认对齐"


# --- cache_key 字节级回归：本 fork 历史 IntegratedCacheManager 写入的 cache 应能被新 Cache 找到 ---


def test_legacy_cache_key_match_with_or_empty_normalization(tmp_path: Path) -> None:
    """字节级回归：模拟 IntegratedCacheManager `or ""` 路径生成的 cache_key 应与新 Cache None 路径一致."""
    import hashlib

    # IntegratedCacheManager.adaptive_cache.save_data 内部经 _get_cache_key
    # 拼 f"{symbol}_{start_date or ''}_{end_date or ''}_{data_source}_{data_type}"
    legacy_key = hashlib.md5(b"AAPL___finnhub_stock_data").hexdigest()

    cache = Cache(file_backend=FileBackend(cache_dir=tmp_path), config=_make_config(primary="file"))
    new_key = cache.save_stock_data("AAPL", {"x": 1}, None, None, "finnhub")
    assert new_key == legacy_key, (
        f"历史 cache_key 兼容性破坏：legacy md5(AAPL___finnhub_stock_data) = {legacy_key} ≠ 新 Cache 路径 {new_key}"
    )
