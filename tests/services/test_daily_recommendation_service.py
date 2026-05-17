"""
Tests for daily_recommendation_service.load_config()
"""

from unittest.mock import patch

import pytest

import app.services.daily_recommendation_service as svc


@pytest.mark.unit
def test_load_config_returns_expected_keys():
    """load_config() reads config/daily_recommendation.json and returns a dict
    with the required top-level keys."""
    config = svc.load_config()
    assert isinstance(config, dict)
    assert "enabled" in config
    assert "screening" in config
    assert "analysis" in config


@pytest.mark.unit
def test_load_config_enabled_is_true():
    """The bundled config has enabled=True."""
    config = svc.load_config()
    assert config["enabled"] is True


@pytest.mark.unit
def test_load_config_screening_structure():
    """screening block contains the expected fields."""
    config = svc.load_config()
    screening = config["screening"]
    assert "conditions" in screening
    assert "order_by" in screening
    assert "order_direction" in screening
    assert "limit" in screening
    assert screening["limit"] == 5


@pytest.mark.unit
def test_load_config_missing_file_returns_safe_default(tmp_path):
    """When the config file does not exist, load_config() returns a safe
    default dict with enabled=False and the required top-level keys."""
    missing_path = tmp_path / "nonexistent.json"
    with patch.object(svc, "_CONFIG_PATH", missing_path):
        config = svc.load_config()
    assert isinstance(config, dict)
    assert config["enabled"] is False
    assert "screening" in config
    assert "analysis" in config


@pytest.mark.unit
def test_load_config_malformed_file_returns_safe_default(tmp_path):
    """When the config file contains invalid JSON, load_config() returns the
    safe default instead of raising."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ not valid json }")
    with patch.object(svc, "_CONFIG_PATH", bad_file):
        config = svc.load_config()
    assert config["enabled"] is False
    assert "screening" in config
    assert "analysis" in config
