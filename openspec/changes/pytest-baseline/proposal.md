## Why

`stable-v1-cleanup` 删 streamlit `web/` 后，**13 个 tests/ 文件成孤儿**——它们 `from web.utils.* import ...`，import 时 ModuleNotFoundError + sys.exit(1)，让 pytest 跑不起来（429 tests collected + 9 errors，部分 error 直接 INTERNALERROR 让 pytest 退出）。

同时 `pyproject.toml` 没含 pytest dev dependency，新机器 clone 后 `uv sync` 装不上 pytest，`uv run --no-sync pytest` 失败。

本 change scope 是**让 pytest 能干净 collection**——pytest 装到 pyproject dev dep + 删 13 个孤立 test。**不转严格**（429 tests 大量需 `.env` LLM key / Tushare token / 网络，runtime fail 率高，待后续 marker-based 治理 change）。

## What Changes

- **MODIFIED** `pyproject.toml`：加 `[project.optional-dependencies] dev = ["pytest>=8", "pytest-asyncio>=1.0"]`（dev extras）
- **REMOVED** 13 个孤立 test 文件（全部 `from web.*` import）：
  - tests/test_risk_assessment.py / test_dataframe_fix.py / test_web_fix.py / test_format_fix.py / test_web_hk.py / test_progress.py / test_enhanced_analysis_history.py / test_import_fix.py / test_mongodb_check.py / test_validation_fix.py / test_pypandoc_functionality.py / debug_web_issue.py / test_fix.py

无 BREAKING change（删的是无法运行的 dead test；pytest 加 dep 是新增）。

## Capabilities

### Modified Capabilities

- `lint-policy`：MODIFY「lint 治理过程保持 warn-only」Requirement 加"pytest 转严格需 marker-based 隔离 env-依赖 test，本 change 不做"

## Impact

**改动文件**：14（pyproject 1 + 删 13 test）
**est commit 数**：2（实施 1 + 收口 1）+ archive
**风险**：低（删的全是无法 collection 的 dead test）
**收益**：
- pytest collection 干净（429 → ?，去掉 collection-error 文件后剩可 collect 的）
- 新机器 clone 后 `uv sync --extra dev` 自动装 pytest
- 后续可立 `pytest-strict-marker-mode` change 设计 marker 体系（unit / integration / requires_env）+ 转严格
