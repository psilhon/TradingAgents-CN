# tests/_legacy/

**这个目录是 v1.1.0 之前的 ad-hoc 脚本归档**——不在 CI / pre-commit pytest 跑，只为保留 git history 供后续查阅。

## 入选标准

下列命名形式的文件已批量移到这里（OpenSpec change `tests-cleanup-debug-scripts`）：

- 暴露 bug 修复 / 调试生命周期：`test_*_fix.py` / `test_*_quick.py` / `test_*_simple.py` / `test_*_final.py` / `test_*_debug.py`
- 明显是调试 / 验证 / 分析脚本：`debug_*.py` / `quick_*.py` / `simple_*.py` / `final_*.py` / `verify_*.py` / `check_*.py` / `analyze_*.py` / `demo_*.py` / `testgoogle.py` / `akshare_*_test.py` 等
- ticker-编号命名：`test_300750_*.py` / `test_002027_*.py` / `test_000002_*.py` 等
- 部分纯 `try/except + print` 脚本（无 `def test_*`，pytest collect 不到）

## 为何不直接删

- 部分脚本含有用的代码片段或调用模式可参考
- git 删除等同移动+保留 history（git log 仍可见），但工作树干净对 review 更友好

## 如何使用

需要恢复某个文件到 `tests/`：`git mv tests/_legacy/foo.py tests/foo.py`，然后按现行规范（标 `pytest.mark.unit` / `integration` 等）补 marker。

## CI 行为

`pyproject.toml [tool.pytest.ini_options] norecursedirs = ["config", "_legacy"]`——pytest 默认不扫描此目录。

## 不应往这里加新文件

新代码请遵循 `openspec/specs/lint-policy/spec.md` 的"tests/ 不得含 lifecycle-named ad-hoc 脚本" requirement。bug 修复 / 调试需要的临时脚本放在 `scripts/` 或个人本地不入库。
