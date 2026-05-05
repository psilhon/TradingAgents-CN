## Why

`lint-cleanup-baseline` change 治理后剩 870 issues，其中含 **19 个真 bug**（runtime 可能崩或行为异常）：

- **F821 undefined-name (14)**：调用未定义的名字，跑到该代码路径会 NameError
- **F811 redefined-while-unused (5)**：同一 symbol 被 import 两次，第一次 import 实际 dead code（覆盖前没用过），文件维护者意图不明（可能错 import 错误模块）

这些必须**优先修**——其它 870 issue 中的 800+ 都是代码风格 / 复杂度问题，不影响运行。

## What Changes

按 rule code 分 2 commit：

- **F821 修复**（14 处，全在 tests/ + 3 个 tradingagents/ 文件）：
  - `tests/quick_redis_test.py` × 3 + `tests/test_redis_performance.py` × 4 → 加 `import os`
  - `tests/test_fundamentals_tracking.py:96` + `tests/test_simple_tracking.py` × 2 → 加 logger 定义/import
  - `tradingagents/agents/utils/google_tool_handler.py:612` → 加 `import traceback`
  - `tradingagents/dataflows/data_source_manager.py:1861` → 加 `get_database_manager` import（找正确模块）
  - `tradingagents/utils/logging_init.py:46/85` → 加 `import logging` + 修 logger 定义

- **F811 修复**（5 处，全在 tradingagents/ 文件）：每处删 ruff 标的 "previous definition"（unused 的 import）
  - `tradingagents/agents/utils/agent_utils.py:11`
  - `tradingagents/config/config_manager.py:36`
  - `tradingagents/dataflows/data_source_manager.py:2137`
  - `tradingagents/graph/trading_graph.py:18`
  - `tradingagents/utils/tool_logging.py:14`

每 commit 后验证：核心模块 import + backend `/api/health` 200。

无 BREAKING change（修真 bug，不引入新行为）。

## Capabilities

### Modified Capabilities

无（沿用 `lint-policy` capability，不新加 / 不 MODIFY 既有 spec）。

## Impact

**改动文件**：
- 5 tests/ files
- 6 tradingagents/ files

**风险**：
- ⚠️ data_source_manager.py 加 `get_database_manager` import 需找正确模块（grep 项目）
- ⚠️ logging_init.py 修 logger 定义可能改变日志行为——需 `python -c "import tradingagents.utils.logging_init"` 验证
- 其它修复都是简单 import 添加 / 删除，低风险

**收益**：
- 19 个真 bug 消除
- 治理后 870 → 851 issues
- F821/F811 不再混在 lint warning 里干扰真问题诊断
