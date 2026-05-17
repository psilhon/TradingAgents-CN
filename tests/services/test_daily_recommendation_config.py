"""每日推荐配置 save_config 校验单元测试。"""

import json

import pytest

from app.services import daily_recommendation_service as drs

pytestmark = pytest.mark.unit


def _valid_config() -> dict:
    return {
        "enabled": True,
        "screening": {
            "conditions": [
                {"field": "pe", "operator": "between", "value": [0, 40]},
                {"field": "roe", "operator": ">=", "value": 2},
            ],
            "order_by": "pe",
            "order_direction": "asc",
            "limit": 5,
        },
        "analysis": {"research_depth": "标准", "market_type": "A股"},
    }


class TestSaveConfigValidation:
    def test_valid_config_written(self, tmp_path, monkeypatch):
        target = tmp_path / "daily_recommendation.json"
        monkeypatch.setattr(drs, "_CONFIG_PATH", target)
        drs.save_config(_valid_config())
        written = json.loads(target.read_text(encoding="utf-8"))
        assert written["screening"]["limit"] == 5
        assert written["screening"]["conditions"][0]["field"] == "pe"

    def test_enabled_must_be_bool(self):
        cfg = _valid_config()
        cfg["enabled"] = "yes"
        with pytest.raises(ValueError, match="enabled"):
            drs.save_config(cfg)

    def test_limit_out_of_range(self):
        cfg = _valid_config()
        cfg["screening"]["limit"] = 0
        with pytest.raises(ValueError, match="limit"):
            drs.save_config(cfg)
        cfg["screening"]["limit"] = 99
        with pytest.raises(ValueError, match="limit"):
            drs.save_config(cfg)

    def test_bad_order_direction(self):
        cfg = _valid_config()
        cfg["screening"]["order_direction"] = "up"
        with pytest.raises(ValueError, match="order_direction"):
            drs.save_config(cfg)

    def test_unknown_condition_field(self):
        cfg = _valid_config()
        cfg["screening"]["conditions"] = [{"field": "no_such_field", "operator": ">=", "value": 1}]
        with pytest.raises(ValueError, match="字段"):
            drs.save_config(cfg)

    def test_operator_not_supported_by_field(self):
        cfg = _valid_config()
        cfg["screening"]["conditions"] = [{"field": "pe", "operator": "contains", "value": "x"}]
        with pytest.raises(ValueError, match="操作符"):
            drs.save_config(cfg)

    def test_bad_research_depth(self):
        cfg = _valid_config()
        cfg["analysis"]["research_depth"] = "超深"
        with pytest.raises(ValueError, match="research_depth"):
            drs.save_config(cfg)
