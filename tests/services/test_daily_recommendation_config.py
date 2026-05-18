"""每日推荐多配置 CRUD、校验与 legacy 迁移单元测试。"""

import json

import pytest

from app.services import daily_recommendation_service as drs

pytestmark = pytest.mark.unit


def _valid_config() -> dict:
    return {
        "name": "测试配置",
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


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """把配置目录与 legacy 文件路径指向隔离的 tmp_path。"""
    target = tmp_path / "daily_recommendations"
    monkeypatch.setattr(drs, "_CONFIG_DIR", target)
    monkeypatch.setattr(drs, "_LEGACY_CONFIG_PATH", tmp_path / "daily_recommendation.json")
    return target


@pytest.mark.usefixtures("config_dir")
class TestConfigCrud:
    def test_create_generates_id_and_writes_file(self, config_dir):
        stored = drs.create_config(_valid_config())
        assert len(stored["id"]) == 8
        path = config_dir / f"{stored['id']}.json"
        assert path.exists()
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert on_disk["name"] == "测试配置"
        assert on_disk["id"] == stored["id"]

    def test_list_configs_sorted_by_name(self):
        drs.create_config({**_valid_config(), "name": "配置B"})
        drs.create_config({**_valid_config(), "name": "配置A"})
        names = [c["name"] for c in drs.list_configs()]
        assert names == ["配置A", "配置B"]

    def test_list_configs_empty_when_no_dir(self):
        assert drs.list_configs() == []

    def test_load_config_roundtrip(self):
        config_id = drs.create_config(_valid_config())["id"]
        loaded = drs.load_config(config_id)
        assert loaded["name"] == "测试配置"
        assert loaded["id"] == config_id

    def test_load_config_missing_raises(self):
        with pytest.raises(FileNotFoundError):
            drs.load_config("deadbeef")

    def test_load_config_rejects_path_traversal(self):
        with pytest.raises(ValueError, match="非法配置 id"):
            drs.load_config("../secret")

    def test_update_config_overwrites_and_keeps_id(self):
        config_id = drs.create_config(_valid_config())["id"]
        drs.update_config(config_id, {**_valid_config(), "name": "改名后"})
        reloaded = drs.load_config(config_id)
        assert reloaded["name"] == "改名后"
        assert reloaded["id"] == config_id

    def test_update_missing_raises(self):
        with pytest.raises(FileNotFoundError):
            drs.update_config("deadbeef", _valid_config())

    def test_delete_config_removes_file(self):
        config_id = drs.create_config(_valid_config())["id"]
        drs.delete_config(config_id)
        assert drs.list_configs() == []

    def test_delete_missing_raises(self):
        with pytest.raises(FileNotFoundError):
            drs.delete_config("deadbeef")


@pytest.mark.usefixtures("config_dir")
class TestValidation:
    def test_name_required_non_empty(self):
        cfg = _valid_config()
        cfg["name"] = "   "
        with pytest.raises(ValueError, match="name"):
            drs.create_config(cfg)

    def test_name_must_be_string(self):
        cfg = _valid_config()
        cfg["name"] = 123
        with pytest.raises(ValueError, match="name"):
            drs.create_config(cfg)

    def test_limit_out_of_range(self):
        cfg = _valid_config()
        cfg["screening"]["limit"] = 0
        with pytest.raises(ValueError, match="limit"):
            drs.create_config(cfg)
        cfg["screening"]["limit"] = 99
        with pytest.raises(ValueError, match="limit"):
            drs.create_config(cfg)

    def test_bad_order_direction(self):
        cfg = _valid_config()
        cfg["screening"]["order_direction"] = "up"
        with pytest.raises(ValueError, match="order_direction"):
            drs.create_config(cfg)

    def test_unknown_condition_field(self):
        cfg = _valid_config()
        cfg["screening"]["conditions"] = [{"field": "no_such_field", "operator": ">=", "value": 1}]
        with pytest.raises(ValueError, match="字段"):
            drs.create_config(cfg)

    def test_operator_not_supported_by_field(self):
        cfg = _valid_config()
        cfg["screening"]["conditions"] = [{"field": "pe", "operator": "contains", "value": "x"}]
        with pytest.raises(ValueError, match="操作符"):
            drs.create_config(cfg)

    def test_bad_research_depth(self):
        cfg = _valid_config()
        cfg["analysis"]["research_depth"] = "超深"
        with pytest.raises(ValueError, match="research_depth"):
            drs.create_config(cfg)

    def test_stray_keys_dropped_on_create(self):
        # enabled 字段已移除；客户端传来的 enabled / id 应被丢弃
        cfg = _valid_config()
        cfg["enabled"] = True
        cfg["id"] = "client-supplied-id"
        stored = drs.create_config(cfg)
        assert "enabled" not in stored
        assert stored["id"] != "client-supplied-id"
        assert set(stored) == {"id", "name", "screening", "analysis"}


@pytest.mark.usefixtures("config_dir")
class TestLegacyMigration:
    def test_migrate_legacy_config(self):
        legacy = drs._LEGACY_CONFIG_PATH
        legacy.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "screening": {
                        "conditions": [],
                        "order_by": "pe",
                        "order_direction": "asc",
                        "limit": 5,
                    },
                    "analysis": {"research_depth": "标准", "market_type": "A股"},
                }
            ),
            encoding="utf-8",
        )
        drs.migrate_legacy_config()

        configs = drs.list_configs()
        assert len(configs) == 1
        assert configs[0]["name"] == "默认配置"
        assert "enabled" not in configs[0]
        assert not legacy.exists()

    def test_migrate_idempotent_when_dir_not_empty(self):
        drs.create_config(_valid_config())
        legacy = drs._LEGACY_CONFIG_PATH
        legacy.write_text(json.dumps({"screening": {}, "analysis": {}}), encoding="utf-8")
        drs.migrate_legacy_config()
        # 目录非空 -> 不迁移、不触碰 legacy 文件
        assert len(drs.list_configs()) == 1
        assert legacy.exists()

    def test_migrate_noop_when_no_legacy_file(self):
        drs.migrate_legacy_config()
        assert drs.list_configs() == []
