## 1. 批量 git mv → tests/_legacy/ — commit 1

- [x] 1.1 创建 `tests/_legacy/` + README
- [x] 1.2 git mv 60 个 lifecycle-named 文件（`test_*_fix/quick/simple/final/debug.py`）
- [x] 1.3 git mv 顶层 prefix scripts（`debug_*` / `quick_*` / `simple_*` / `final_*` / `verify_*` / `check_*` / `analyze_*` / `demo_*`）
- [x] 1.4 git mv 非 `test_*.py` 命名脚本（`testgoogle.py` / `akshare_*_test.py` / `fundamentals_analyst_clean.py` 等）
- [x] 1.5 git mv 3 个 ticker-numbered (`test_300750_*` / `test_002027_*` / `test_000002_*`)
- [x] 1.6 总计 87 个文件移到 `tests/_legacy/`
- [x] 1.7 `pyproject.toml` 加 `_legacy` 到 `norecursedirs`
- [x] 1.8 `pytest --collect-only` = 477 tests，0 来自 _legacy（之前 644）
- [x] 1.9 ruff + pyright 0 errors
- [x] 1.10 pytest -m unit 仍 12 pass
- [x] 1.11 commit

## 2. 收口

- [x] 2.1 docs/CHANGELOG.md `### Changed` 条目
- [x] 2.2 archive
