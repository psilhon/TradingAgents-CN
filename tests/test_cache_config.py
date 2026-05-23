"""CacheConfig 单元测试 — sub-stage 4.3 cache-config-dataclass.

`CacheConfig` 是 cache 层 backend 配置的单一来源（frozen dataclass）。本测试
覆盖构造 + 不可变 + `from_environment` 工厂的三路径分支 + `TA_CACHE_STRATEGY`
env 解析。
"""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

_CACHE_DIR = Path(__file__).resolve().parents[1] / "tradingagents" / "dataflows" / "cache"
_CONFIG_PATH = _CACHE_DIR / "_config.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_config_mod = _load_module("_cache_config_under_test", _CONFIG_PATH)
CacheConfig = _config_mod.CacheConfig


# --- 构造 + 字段 ---


def test_construct_with_all_fields() -> None:
    config = CacheConfig(
        cache_strategy="integrated",
        primary_backend="redis",
        fallback_enabled=True,
        ttl_settings={"us_stock_data": 7200, "china_stock_data": 3600},
    )
    assert config.cache_strategy == "integrated"
    assert config.primary_backend == "redis"
    assert config.fallback_enabled is True
    assert config.ttl_settings["us_stock_data"] == 7200


# --- 不可变（frozen=True） ---


def test_config_is_frozen() -> None:
    config = CacheConfig(
        cache_strategy="integrated",
        primary_backend="redis",
        fallback_enabled=True,
        ttl_settings={},
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.primary_backend = "file"  # type: ignore[misc]


def test_config_is_frozen_for_all_fields() -> None:
    config = CacheConfig(
        cache_strategy="integrated",
        primary_backend="redis",
        fallback_enabled=True,
        ttl_settings={},
    )
    for field in ("cache_strategy", "primary_backend", "fallback_enabled", "ttl_settings"):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(config, field, None)


# --- from_environment 后端推断三路径 ---


def _mock_db_manager(redis_available: bool, mongodb_available: bool) -> MagicMock:
    m = MagicMock()
    m.is_redis_available.return_value = redis_available
    m.is_mongodb_available.return_value = mongodb_available
    return m


def test_from_environment_redis_available_picks_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TA_CACHE_STRATEGY", raising=False)
    config = CacheConfig.from_environment(_mock_db_manager(redis_available=True, mongodb_available=True))
    assert config.primary_backend == "redis"


def test_from_environment_only_mongodb_picks_mongodb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TA_CACHE_STRATEGY", raising=False)
    config = CacheConfig.from_environment(_mock_db_manager(redis_available=False, mongodb_available=True))
    assert config.primary_backend == "mongodb"


def test_from_environment_neither_picks_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TA_CACHE_STRATEGY", raising=False)
    config = CacheConfig.from_environment(_mock_db_manager(redis_available=False, mongodb_available=False))
    assert config.primary_backend == "file"


# --- TA_CACHE_STRATEGY env 解析 ---


def test_cache_strategy_default_integrated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TA_CACHE_STRATEGY", raising=False)
    config = CacheConfig.from_environment(_mock_db_manager(True, True))
    assert config.cache_strategy == "integrated"


def test_cache_strategy_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TA_CACHE_STRATEGY", "file")
    config = CacheConfig.from_environment(_mock_db_manager(True, True))
    assert config.cache_strategy == "file"


def test_cache_strategy_adaptive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TA_CACHE_STRATEGY", "adaptive")
    config = CacheConfig.from_environment(_mock_db_manager(True, True))
    assert config.cache_strategy == "adaptive"


def test_cache_strategy_invalid_value_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TA_CACHE_STRATEGY", "garbage_value_not_in_enum")
    # MUST NOT raise — fallback 默认 "integrated"
    config = CacheConfig.from_environment(_mock_db_manager(True, True))
    assert config.cache_strategy == "integrated"


# --- ttl_settings 默认值字节级匹配 ---


_EXPECTED_TTL_SETTINGS = {
    "us_stock_data": 7200,
    "us_news": 21600,
    "us_fundamentals": 86400,
    "china_stock_data": 3600,
    "china_news": 14400,
    "china_fundamentals": 43200,
}


def test_ttl_settings_has_all_6_standard_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TA_CACHE_STRATEGY", raising=False)
    config = CacheConfig.from_environment(_mock_db_manager(True, False))
    for key in _EXPECTED_TTL_SETTINGS:
        assert key in config.ttl_settings, f"ttl_settings 缺少标准 key: {key}"


def test_ttl_settings_default_values_match_pre_4_3_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """字节级守护：与 4.3 前 db_manager.get_config()['cache']['ttl_settings'] 等价."""
    monkeypatch.delenv("TA_CACHE_STRATEGY", raising=False)
    config = CacheConfig.from_environment(_mock_db_manager(True, False))
    for key, expected in _EXPECTED_TTL_SETTINGS.items():
        assert config.ttl_settings[key] == expected, f"ttl_settings[{key}] = {config.ttl_settings[key]} 与 {expected} 漂移"


# --- fallback_enabled 默认 ---


def test_fallback_enabled_default_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """与 4.3 前 db_manager 硬编码 True 一致."""
    monkeypatch.delenv("TA_CACHE_STRATEGY", raising=False)
    config = CacheConfig.from_environment(_mock_db_manager(True, False))
    assert config.fallback_enabled is True


# --- 源码洁净度 ---


def test_config_module_does_not_import_pickle_or_pandas() -> None:
    source = _CONFIG_PATH.read_text()
    assert "import pickle" not in source, "_config.py MUST NOT import pickle"
    assert "import pandas" not in source, "_config.py MUST NOT import pandas（纯配置模块）"


# --- env 隔离守护 ---


def test_env_is_read_at_from_environment_call_not_module_load(monkeypatch: pytest.MonkeyPatch) -> None:
    """关键回归：4.3 前 cache/__init__.py 模块级 os.getenv 是 import 时一次性读
    需要确认 from_environment 是 call 时读，不是 module load 时 cache."""
    monkeypatch.setenv("TA_CACHE_STRATEGY", "file")
    config1 = CacheConfig.from_environment(_mock_db_manager(True, True))
    assert config1.cache_strategy == "file"

    monkeypatch.setenv("TA_CACHE_STRATEGY", "integrated")
    config2 = CacheConfig.from_environment(_mock_db_manager(True, True))
    assert config2.cache_strategy == "integrated"  # 第二次调用应读新 env 值


# --- 注入路径（spec scenario：AdaptiveCacheSystem 应支持 config 注入） ---
# 该 scenario 在 test_cache_config.py 不验证（属 adaptive.py 集成测试范围）；
# 这里只验证 CacheConfig 本身可直接 mock 构造（unit 测试可不经 from_environment）.


def test_config_can_be_constructed_directly_for_testing() -> None:
    config = CacheConfig(
        cache_strategy="file",
        primary_backend="file",
        fallback_enabled=False,
        ttl_settings={"us_stock_data": 100},
    )
    # 直接构造的 config 任何字段都是可读
    assert config.cache_strategy == "file"
    assert config.fallback_enabled is False
    assert config.ttl_settings == {"us_stock_data": 100}


def test_imports_isolated_from_dataflows_pkg() -> None:
    """_config.py MUST 不 import dataflows / cache 包内其它模块（避免循环 + 副作用）."""
    source = _CONFIG_PATH.read_text()
    assert "from tradingagents.dataflows" not in source, "_config.py MUST NOT import dataflows 内模块"
    assert "from .adaptive" not in source
    assert "from .integrated" not in source
    assert "from .backends" not in source
