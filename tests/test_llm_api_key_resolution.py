import pytest

from app.services.simple_analysis_service import _resolve_api_key_for_provider


@pytest.mark.unit
def test_file_source_uses_env_key_over_database_keys(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env-key-1234567890")

    api_key, source = _resolve_api_key_for_provider(
        provider="deepseek",
        model_api_key="sk-model-key-1234567890",
        provider_api_key="sk-provider-key-1234567890",
        config_sot="file",
    )

    assert api_key == "sk-env-key-1234567890"
    assert source == "环境变量"


@pytest.mark.unit
def test_hybrid_source_uses_database_key_only_when_env_missing(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    api_key, source = _resolve_api_key_for_provider(
        provider="deepseek",
        model_api_key="sk-model-key-1234567890",
        provider_api_key="sk-provider-key-1234567890",
        config_sot="hybrid",
    )

    assert api_key == "sk-model-key-1234567890"
    assert source == "模型配置"


@pytest.mark.unit
def test_db_source_preserves_legacy_database_priority(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env-key-1234567890")

    api_key, source = _resolve_api_key_for_provider(
        provider="deepseek",
        model_api_key="sk-model-key-1234567890",
        provider_api_key="sk-provider-key-1234567890",
        config_sot="db",
    )

    assert api_key == "sk-model-key-1234567890"
    assert source == "模型配置"
