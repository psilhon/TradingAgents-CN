## 1. pyproject 加 marker — commit 1

- [ ] 1.1 编辑 `pyproject.toml [tool.pytest.ini_options]` 加 `markers` 列表
- [ ] 1.2 编辑 `tests/conftest.py` 加 `pytest_collection_modifyitems` auto-mark hook
- [ ] 1.3 给 1-2 个公认 unit test 文件加 `@pytest.mark.unit`（让 hook 至少跑几个 baseline）
- [ ] 1.4 验证 `.venv/bin/pytest -m unit --collect-only` 显示 unit test
- [ ] 1.5 commit

## 2. pre-commit pytest hook 转严格 — commit 2

- [ ] 2.1 编辑 `.pre-commit-config.yaml` pytest hook entry 改 `uv run --no-sync pytest -m unit -p no:cacheprovider`，去 warn-only wrapper
- [ ] 2.2 commit

## 3. 收口

- [ ] 3.1 docs/CHANGELOG.md
- [ ] 3.2 commit + push + archive
