## 1. F811 修复（5 处删重复 import）— commit 1

- [ ] 1.1 `tradingagents/agents/utils/agent_utils.py:11` 删 `from tradingagents.utils.logging_init import get_logger`（保留 line 14 from logging_manager）
- [ ] 1.2 `tradingagents/config/config_manager.py:36` 删 `from tradingagents.utils.logging_init import get_logger`（保留 line 39 from logging_manager）
- [ ] 1.3 `tradingagents/dataflows/data_source_manager.py:2137` 删第一处 `def get_data_source_manager`（保留 line 2198 的）
- [ ] 1.4 `tradingagents/graph/trading_graph.py:18` 删 unused get_logger import（保留 line 21）
- [ ] 1.5 `tradingagents/utils/tool_logging.py:14` 同上
- [ ] 1.6 验证：`uvx ruff check . --select F811` Found 0 errors
- [ ] 1.7 验证：`.venv/bin/python -c "import tradingagents.graph.trading_graph; import tradingagents.config.config_manager; import tradingagents.agents.utils.agent_utils; import tradingagents.utils.tool_logging; import tradingagents.dataflows.data_source_manager"` 全 OK
- [ ] 1.8 验证：backend 重启 + `/api/health` 200
- [ ] 1.9 commit `fix(lint): F811 remove duplicate get_logger / get_data_source_manager imports`

## 2. F821 修复（14 处加 missing import）— commit 2

- [ ] 2.1 `tests/quick_redis_test.py` 文件顶部加 `import os`
- [ ] 2.2 `tests/test_redis_performance.py` 文件顶部加 `import os`
- [ ] 2.3 `tests/test_fundamentals_tracking.py` 文件顶部加 `from tradingagents.utils.logging_manager import get_logger; logger = get_logger(__name__)`（看上下文确定 logger 来源）
- [ ] 2.4 `tests/test_simple_tracking.py` 同上
- [ ] 2.5 `tradingagents/agents/utils/google_tool_handler.py` 加 `import traceback`
- [ ] 2.6 `tradingagents/dataflows/data_source_manager.py:1861` grep 确定 `get_database_manager` 来源 + 加正确 import
- [ ] 2.7 `tradingagents/utils/logging_init.py` 加 `import logging` + 修 line 85 logger 定义（看上下文）
- [ ] 2.8 验证：`uvx ruff check . --select F821` Found 0 errors
- [ ] 2.9 验证：核心模块 import smoke + backend `/api/health` 200
- [ ] 2.10 commit `fix(lint): F821 add missing imports (os/traceback/logging/logger)`

## 3. 收口

- [ ] 3.1 跑 `uvx ruff check . --statistics` 看 870 → 851
- [ ] 3.2 更新 `docs/CHANGELOG.md` `[Unreleased]` 加 `### Fixed` 段
- [ ] 3.3 commit `docs: changelog for lint-handfix-pass-1`
- [ ] 3.4 push（用户 1-click）
- [ ] 3.5 `openspec archive lint-handfix-pass-1 --yes`（MODIFY base spec lint-policy 加 真 bug 优先 + F811 修法）
