"""
Tests for daily_recommendation_service.load_config()
"""

import json
import logging
from unittest.mock import patch

import pytest

import app.services.daily_recommendation_service as svc

# ---------------------------------------------------------------------------
# Real-config smoke test (plan-mandated: proves the shipped JSON is loadable)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_config_reads_real_config_file():
    """load_config() can read config/daily_recommendation.json and returns a
    dict with the three required top-level keys."""
    config = svc.load_config()
    assert isinstance(config, dict)
    assert "enabled" in config
    assert "screening" in config
    assert "analysis" in config


# ---------------------------------------------------------------------------
# Value-parsing tests — isolated against a fixture JSON, not the shipped file
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_config_parses_values_correctly(tmp_path):
    """load_config() correctly parses all expected fields from a known JSON
    fixture, exercised in isolation from the shipped config file."""
    fixture = {
        "enabled": True,
        "screening": {
            "conditions": [],
            "order_by": "market_cap",
            "order_direction": "desc",
            "limit": 5,
        },
        "analysis": {
            "research_depth": "标准",
            "market_type": "A股",
        },
    }
    fixture_path = tmp_path / "daily_recommendation.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    with patch.object(svc, "_CONFIG_PATH", fixture_path):
        config = svc.load_config()

    assert config["enabled"] is True

    screening = config["screening"]
    assert "conditions" in screening
    assert screening["order_by"] == "market_cap"
    assert screening["order_direction"] == "desc"
    assert screening["limit"] == 5

    analysis = config["analysis"]
    assert analysis["research_depth"] == "标准"
    assert analysis["market_type"] == "A股"


# ---------------------------------------------------------------------------
# Error-path / safe-default tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_config_missing_file_returns_safe_default(tmp_path, caplog):
    """When the config file does not exist, load_config() returns a safe
    default dict with enabled=False and logs a warning."""
    missing_path = tmp_path / "nonexistent.json"
    with caplog.at_level(logging.WARNING), patch.object(svc, "_CONFIG_PATH", missing_path):
        config = svc.load_config()
    assert isinstance(config, dict)
    assert config["enabled"] is False
    assert "screening" in config
    assert "analysis" in config
    assert caplog.records, "expected a warning log record but none was emitted"
    assert any(r.levelno == logging.WARNING for r in caplog.records)


@pytest.mark.unit
def test_load_config_malformed_file_returns_safe_default(tmp_path, caplog):
    """When the config file contains invalid JSON, load_config() returns the
    safe default instead of raising, and logs a warning."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ not valid json }")
    with caplog.at_level(logging.WARNING), patch.object(svc, "_CONFIG_PATH", bad_file):
        config = svc.load_config()
    assert config["enabled"] is False
    assert "screening" in config
    assert "analysis" in config
    assert caplog.records, "expected a warning log record but none was emitted"
    assert any(r.levelno == logging.WARNING for r in caplog.records)
