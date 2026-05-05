## ADDED Requirements

### Requirement: tests/ 不得含 lifecycle-named ad-hoc 脚本

`tests/` 顶层（不含子目录如 `tests/unit/` / `tests/integration/`）MUST NOT 含以下命名形式的文件：

- `test_*_fix.py` / `test_*_quick.py` / `test_*_simple.py` / `test_*_final.py` / `test_*_debug.py`（暴露 bug 修复 / 调试生命周期）
- `debug_*.py` / `quick_*.py` / `simple_*.py` / `final_*.py` / `verify_*.py` / `check_*.py` / `analyze_*.py` / `demo_*.py`（明显的调试 / 验证 / 分析脚本）
- 不符合 `test_*.py` 命名约定的 Python 文件（pytest 默认 collect 不到，徒增噪音）

历史已存在的此类脚本归档到 `tests/_legacy/`（在 `pyproject.toml [tool.pytest.ini_options] norecursedirs` 排除）。新代码 SHALL NOT 加此类文件，bug 修复 / 调试需要的脚本应放在 `scripts/` 或个人本地不入库。

#### Scenario: tests/ 顶层 lifecycle 文件检查

- **WHEN** `find tests -maxdepth 1 -type f -name "*.py" | grep -E "(_fix|_quick|_simple|_final|_debug)\.py$"`
- **THEN** 命中数 MUST = 0

#### Scenario: tests/ 顶层 debug/quick/simple/final 命名

- **WHEN** `find tests -maxdepth 1 -type f -name "*.py" | grep -E "^tests/(debug_|quick_|simple_|final_|verify_|check_|analyze_|demo_)"`
- **THEN** 命中数 MUST = 0

#### Scenario: _legacy 子目录不在 pytest collect 范围

- **WHEN** 执行 `pytest --collect-only`
- **THEN** 收集结果 MUST NOT 含任何 `tests/_legacy/` 路径下的文件
- **AND** `pyproject.toml [tool.pytest.ini_options] norecursedirs` MUST 含 `_legacy`
