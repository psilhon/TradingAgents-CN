## 1. pyproject 加 pytest dev dep + 删孤立 test — commit 1

- [ ] 1.1 编辑 `pyproject.toml` 加 `[project.optional-dependencies] dev = ["pytest>=8", "pytest-asyncio>=1.0"]`
- [ ] 1.2 `git rm` 13 个孤立 test 文件（全部依赖已删 `web/` 模块）
- [ ] 1.3 验证 `.venv/bin/python -m pytest --collect-only 2>&1 | tail -2` 不再报 INTERNALERROR
- [ ] 1.4 验证 `uvx ruff check .` 仍 0 errors（不要因 pyproject 改动引入新 ruff issue）
- [ ] 1.5 commit `feat(pytest): add pytest dev dep + remove 13 orphan tests (web/ dependents)`

## 2. 收口

- [ ] 2.1 更新 `docs/CHANGELOG.md` `[Unreleased]` 加 `### Added` + `### Removed` 段
- [ ] 2.2 commit `docs: changelog for pytest-baseline`
- [ ] 2.3 push（用户 1-click）
- [ ] 2.4 `openspec archive pytest-baseline --yes`
