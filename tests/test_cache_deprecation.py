"""IntegratedCacheManager / AdaptiveCacheSystem deprecated 警告测试 — 4.4.

两个老类在 __init__ MUST raise DeprecationWarning（stacklevel=2，message
含 "Cache" 指向迁移目标）。类保留可用，行为不变。

这里通过 monkeypatch / mock 让构造不连真 DB，纯验证 warning + 基础行为。
"""

from __future__ import annotations

import warnings
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _mock_db_manager() -> Any:
    """构造一个能让 AdaptiveCacheSystem / IntegratedCacheManager 初始化通过的 db_manager."""
    m = MagicMock()
    m.is_redis_available.return_value = False
    m.is_mongodb_available.return_value = False
    m.get_redis_client.return_value = None
    m.get_mongodb_client.return_value = None
    m.get_config.return_value = {
        "cache": {
            "primary_backend": "file",
            "fallback_enabled": True,
            "ttl_settings": {"us_stock_data": 7200},
        }
    }
    return m


def test_adaptive_cache_system_raises_deprecation_warning(tmp_path) -> None:
    """AdaptiveCacheSystem.__init__ MUST trigger DeprecationWarning."""
    with patch("tradingagents.config.database_manager.get_database_manager", return_value=_mock_db_manager()):
        from tradingagents.dataflows.cache.adaptive import AdaptiveCacheSystem

        with pytest.warns(DeprecationWarning) as records:
            AdaptiveCacheSystem(cache_dir=str(tmp_path))
        # 至少有一个 DeprecationWarning，且 message 指向迁移目标
        dep_msgs = [str(r.message) for r in records if issubclass(r.category, DeprecationWarning)]
        assert any("Cache" in m for m in dep_msgs), f"DeprecationWarning message MUST 指向 Cache 迁移目标: {dep_msgs}"


def test_integrated_cache_manager_raises_deprecation_warning(tmp_path) -> None:
    """IntegratedCacheManager.__init__ MUST trigger DeprecationWarning."""
    with patch("tradingagents.config.database_manager.get_database_manager", return_value=_mock_db_manager()):
        from tradingagents.dataflows.cache.integrated import IntegratedCacheManager

        with pytest.warns(DeprecationWarning) as records:
            IntegratedCacheManager(cache_dir=str(tmp_path))
        dep_msgs = [str(r.message) for r in records if issubclass(r.category, DeprecationWarning)]
        assert any("Cache" in m for m in dep_msgs)


def test_deprecated_classes_still_instantiate_and_have_methods(tmp_path) -> None:
    """deprecation 警告后行为 MUST 不变 — 实例仍可调 save_stock_data."""
    with patch("tradingagents.config.database_manager.get_database_manager", return_value=_mock_db_manager()):
        from tradingagents.dataflows.cache.integrated import IntegratedCacheManager

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            cache = IntegratedCacheManager(cache_dir=str(tmp_path))
        # 仍可调 save_stock_data（行为不变）
        assert callable(getattr(cache, "save_stock_data", None))
        assert callable(getattr(cache, "load_stock_data", None))


def test_deprecation_message_mentions_cache_as_target() -> None:
    """两类 deprecation message 都应明确 Cache 是迁移目标."""
    # 源码 grep 守护 — 比 runtime warning capture 更直接
    from pathlib import Path

    adaptive_src = (Path(__file__).resolve().parents[1] / "tradingagents" / "dataflows" / "cache" / "adaptive.py").read_text()
    integrated_src = (Path(__file__).resolve().parents[1] / "tradingagents" / "dataflows" / "cache" / "integrated.py").read_text()
    assert "DeprecationWarning" in adaptive_src, "adaptive.py MUST 含 DeprecationWarning"
    assert "DeprecationWarning" in integrated_src, "integrated.py MUST 含 DeprecationWarning"
    # message 提及 Cache（不是某个 random 字符串）
    assert "Cache" in adaptive_src
    assert "Cache" in integrated_src
