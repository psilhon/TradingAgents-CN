import pytest

from app.services.simple_analysis_service import _resolve_api_key_for_provider

# 测试用 placeholder，明显非真凭据：低 entropy + 全大写 SNAKE_CASE。
# gitleaks generic-api-key 不会触发，仍然能验证优先级解析逻辑。
_FAKE_ENV_KEY = "FAKE_ENV_KEY_DEEPSEEK"
_FAKE_MODEL_KEY = "FAKE_MODEL_KEY_DEEPSEEK"
_FAKE_PROVIDER_KEY = "FAKE_PROVIDER_KEY_DEEPSEEK"


@pytest.mark.unit
def test_file_source_uses_env_key_over_database_keys(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", _FAKE_ENV_KEY)

    api_key, source = _resolve_api_key_for_provider(
        provider="deepseek",
        model_api_key=_FAKE_MODEL_KEY,
        provider_api_key=_FAKE_PROVIDER_KEY,
        config_sot="file",
    )

    assert api_key == _FAKE_ENV_KEY
    assert source == "环境变量"


@pytest.mark.unit
def test_hybrid_source_uses_database_key_only_when_env_missing(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    api_key, source = _resolve_api_key_for_provider(
        provider="deepseek",
        model_api_key=_FAKE_MODEL_KEY,
        provider_api_key=_FAKE_PROVIDER_KEY,
        config_sot="hybrid",
    )

    assert api_key == _FAKE_MODEL_KEY
    assert source == "模型配置"


@pytest.mark.unit
def test_db_source_preserves_legacy_database_priority(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", _FAKE_ENV_KEY)

    api_key, source = _resolve_api_key_for_provider(
        provider="deepseek",
        model_api_key=_FAKE_MODEL_KEY,
        provider_api_key=_FAKE_PROVIDER_KEY,
        config_sot="db",
    )

    assert api_key == _FAKE_MODEL_KEY
    assert source == "模型配置"
