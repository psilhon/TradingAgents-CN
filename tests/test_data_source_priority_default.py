"""mongodb_cache_adapter._get_data_source_priority 默认顺序测试.

OpenSpec backlog G "Tushare 主源 + 多源 fallback chain" 验证：
- 默认顺序 MUST 是 ["tushare", "akshare", "baostock"]（tushare 主源）
- mongo system_configs 缺失时降级到默认顺序，不抛
- mongo system_configs 存在时按数据库配置（priority 字段降序）
"""

from __future__ import annotations

import logging

import pytest


class _FakeMongoCollection:
    def __init__(self, doc):
        self._doc = doc

    def find_one(self, query=None, sort=None):
        return self._doc


class _FakeMongoDB:
    def __init__(self, system_configs_doc=None):
        self._doc = system_configs_doc

    @property
    def system_configs(self):
        return _FakeMongoCollection(self._doc)


@pytest.mark.unit
def test_default_priority_when_db_empty(caplog) -> None:
    """mongo system_configs 缺失 → 默认顺序 tushare > akshare > baostock."""
    from tradingagents.dataflows.cache.mongodb_cache_adapter import MongoDBCacheAdapter

    adapter = MongoDBCacheAdapter.__new__(MongoDBCacheAdapter)
    adapter.db = _FakeMongoDB(system_configs_doc=None)  # 空 db

    with caplog.at_level(logging.DEBUG):
        priority = adapter._get_data_source_priority("000001")

    assert priority == ["tushare", "akshare", "baostock"], f"默认顺序 MUST tushare > akshare > baostock, 实际 {priority!r}"


@pytest.mark.unit
def test_default_priority_when_db_is_none() -> None:
    """db is None（连接没起来）→ 默认顺序，不抛."""
    from tradingagents.dataflows.cache.mongodb_cache_adapter import MongoDBCacheAdapter

    adapter = MongoDBCacheAdapter.__new__(MongoDBCacheAdapter)
    adapter.db = None

    priority = adapter._get_data_source_priority("000001")
    assert priority == ["tushare", "akshare", "baostock"]


@pytest.mark.unit
def test_db_config_overrides_default() -> None:
    """mongo system_configs 含 enabled 数据源 → 按 priority 降序排，覆盖默认."""
    from tradingagents.dataflows.cache.mongodb_cache_adapter import MongoDBCacheAdapter

    # 用户配置：akshare 主（priority=100），tushare 次（priority=50），baostock 关闭
    config_doc = {
        "is_active": True,
        "version": 1,
        "data_source_configs": [
            {"type": "akshare", "enabled": True, "priority": 100, "market_categories": ["a_shares"]},
            {"type": "tushare", "enabled": True, "priority": 50, "market_categories": ["a_shares"]},
            {"type": "baostock", "enabled": False, "priority": 10, "market_categories": ["a_shares"]},
        ],
    }
    adapter = MongoDBCacheAdapter.__new__(MongoDBCacheAdapter)
    adapter.db = _FakeMongoDB(system_configs_doc=config_doc)

    priority = adapter._get_data_source_priority("000001")
    # akshare 优先级最高（100）→ 第一；tushare 次之（50）→ 第二；baostock 关闭 → 不出现
    assert priority == ["akshare", "tushare"], f"DB 配置应覆盖默认，按 priority 降序，实际 {priority!r}"


@pytest.mark.unit
def test_no_warning_spam_when_db_empty(caplog) -> None:
    """空 db 时 log 级别应是 debug（不是 warning）—— 避免每次查 priority 都 spam.

    历史 bug：error.log 反复出现 "数据库中没有找到数据源配置" warning，
    每次 _get_data_source_priority 调用都打一次（agent 路径每股票多次）.
    """
    from tradingagents.dataflows.cache.mongodb_cache_adapter import MongoDBCacheAdapter

    adapter = MongoDBCacheAdapter.__new__(MongoDBCacheAdapter)
    adapter.db = _FakeMongoDB(system_configs_doc=None)

    # 仅捕获 WARNING 级别
    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            adapter._get_data_source_priority("000001")

    spam_warnings = [r for r in caplog.records if "数据库中没有找到数据源配置" in r.message and r.levelno >= logging.WARNING]
    assert spam_warnings == [], f"空 db fallback 不应在 WARNING 级别 spam（应降到 debug/info），实际收到 {len(spam_warnings)} 条 warning"
