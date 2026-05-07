import json

import pytest

from app.core.unified_config import ConfigPaths, UnifiedConfigManager
from app.models.config import LLMConfig, SystemConfig


@pytest.fixture
def isolated_manager(tmp_path):
    manager = UnifiedConfigManager()
    manager.paths = ConfigPaths(root_config_dir=tmp_path)
    manager.paths.models_json = tmp_path / "models.json"
    manager.paths.settings_json = tmp_path / "settings.json"
    return manager


@pytest.mark.unit
def test_export_mongodb_snapshot_writes_legacy_json_without_secrets(isolated_manager):
    isolated_manager._save_json_file(
        isolated_manager.paths.settings_json,
        {
            "research_depth": "标准",
            "quick_api_key": "should-not-export",
            "deep_api_key": "should-not-export",
        },
    )
    system_config = SystemConfig(
        config_name="test",
        config_type="system",
        llm_configs=[
            LLMConfig(
                provider="qwen",
                model_name="qwen-plus",
                api_key="secret",
                api_base="https://dashscope.example/v1",
                max_tokens=8192,
                temperature=0.3,
                timeout=120,
                retry_times=2,
                capability_level=4,
                features=["tool_calling"],
            )
        ],
        default_llm="qwen-plus",
        system_settings={
            "quick_analysis_model": "qwen-plus",
            "deep_analysis_model": "qwen-plus",
        },
    )

    assert isolated_manager.export_mongodb_snapshot(system_config) is True

    models = json.loads(isolated_manager.paths.models_json.read_text())
    settings = json.loads(isolated_manager.paths.settings_json.read_text())

    assert models == [
        {
            "provider": "qwen",
            "model_name": "qwen-plus",
            "model_display_name": None,
            "api_key": "",
            "base_url": "https://dashscope.example/v1",
            "max_tokens": 8192,
            "temperature": 0.3,
            "timeout": 120,
            "retry_times": 2,
            "enabled": True,
            "description": None,
            "model_category": None,
            "custom_endpoint": None,
            "enable_memory": False,
            "enable_debug": False,
            "priority": 0,
            "input_price_per_1k": None,
            "output_price_per_1k": None,
            "currency": "CNY",
            "capability_level": 4,
            "suitable_roles": ["both"],
            "features": ["tool_calling"],
            "recommended_depths": ["快速", "基础", "标准"],
            "performance_metrics": None,
        }
    ]
    assert settings["research_depth"] == "标准"
    assert settings["quick_analysis_model"] == "qwen-plus"
    assert settings["quick_think_llm"] == "qwen-plus"
    assert settings["deep_analysis_model"] == "qwen-plus"
    assert settings["deep_think_llm"] == "qwen-plus"
    assert settings["default_model"] == "qwen-plus"
    assert settings["llm_provider"] == "qwen"
    assert settings["backend_url"] == "https://dashscope.example/v1"
    assert "quick_api_key" not in settings
    assert "deep_api_key" not in settings


@pytest.mark.unit
def test_get_llm_configs_reads_enhanced_fields_from_snapshot(isolated_manager):
    isolated_manager._save_json_file(
        isolated_manager.paths.models_json,
        [
            {
                "provider": "deepseek",
                "model_name": "deepseek-chat",
                "model_display_name": "DeepSeek Chat",
                "api_key": "ignored",
                "base_url": "https://deepseek.example/v1",
                "max_tokens": 16000,
                "temperature": 0.2,
                "timeout": 90,
                "retry_times": 4,
                "enabled": True,
                "capability_level": 5,
                "suitable_roles": ["deep_analysis"],
                "features": ["tool_calling", "reasoning"],
                "recommended_depths": ["标准", "深度"],
                "performance_metrics": {"speed": 3, "cost": 4, "quality": 5},
            }
        ],
        "models",
    )

    configs = isolated_manager.get_llm_configs()

    assert len(configs) == 1
    config = configs[0]
    assert config.provider == "deepseek"
    assert config.model_name == "deepseek-chat"
    assert config.model_display_name == "DeepSeek Chat"
    assert config.api_key == ""
    assert config.api_base == "https://deepseek.example/v1"
    assert config.timeout == 90
    assert config.retry_times == 4
    assert config.capability_level == 5
    assert config.suitable_roles == ["deep_analysis"]
    assert config.features == ["tool_calling", "reasoning"]
    assert config.recommended_depths == ["标准", "深度"]
    assert config.performance_metrics == {"speed": 3, "cost": 4, "quality": 5}


@pytest.mark.unit
def test_save_system_settings_removes_legacy_runtime_keys(isolated_manager):
    isolated_manager._save_json_file(
        isolated_manager.paths.settings_json,
        {
            "quick_api_key": "old-secret",
            "deep_api_key": "old-secret",
            "research_depth": "快速",
        },
        "settings",
    )

    assert isolated_manager.save_system_settings({"quick_analysis_model": "deepseek-chat"}) is True

    settings = json.loads(isolated_manager.paths.settings_json.read_text())
    assert "quick_api_key" not in settings
    assert "deep_api_key" not in settings
    assert settings["quick_analysis_model"] == "deepseek-chat"
