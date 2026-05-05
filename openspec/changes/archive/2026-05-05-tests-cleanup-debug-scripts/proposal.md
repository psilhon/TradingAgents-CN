## Why

`docs/code-review-2026-05-05.md` Tier 2 第 6 条：`tests/` 顶层有 **~80+ 个 ad-hoc 脚本**——`test_*_fix.py` / `test_*_quick.py` / `test_*_simple.py` / `test_*_final.py` / `test_*_debug.py` / `debug_*.py` / `quick_*.py` / `simple_*.py` / `final_*.py` / `verify_*.py` / `check_*.py` / `analyze_*.py`：

- 命名暴露生命周期（修 bug 时新增、修完不清理）
- 17+ 个文件无任何 `def test_*` / `class Test*`，纯 `try/except + print` 脚本，pytest collect 不到
- 多数 import 已删除模块（如 `enhanced_stock_list_fetcher`）—— skip 或失败
- 与正式 test 混在一起拉低 review 信噪比 + 拖慢 collect

实测：78 个 lifecycle-named files + 26 个非 `test_*.py` 命名 ≈ 总数 ~100 个文件。

## What Changes

- **MOVED** ~100 个 ad-hoc 脚本 → `tests/_legacy/`（保留 git history，不删除——可能含有用的代码片段）
- **MODIFIED** `pyproject.toml [tool.pytest.ini_options]`：加 `_legacy` 到 `norecursedirs`
- **NEW** `tests/_legacy/README.md`：说明这是 pre-v1.1.0 历史 ad-hoc 脚本归档区，不在 CI 跑
- **MODIFIED** `lint-policy` spec：加 requirement "tests/ 不得含 lifecycle-named 脚本"

## Capabilities

### Modified Capabilities

- `lint-policy`：禁止新增 `_fix` / `_quick` / `_simple` / `_final` / `_debug` 命名的 ad-hoc 脚本到 tests/

## Impact

**改动文件**：~100 个文件移动 + 1 个 pyproject + 1 个新 README
**风险**：低——文件移动保留 history，`norecursedirs` 排除后不影响 collect
**收益**：tests/ 顶层从 ~225 个 → ~125 个文件；review 信噪比提升；collect 速度提升
