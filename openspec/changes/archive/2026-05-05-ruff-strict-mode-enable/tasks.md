## 1. 改 .pre-commit-config.yaml — commit 1

- [ ] 1.1 编辑 `.pre-commit-config.yaml`：
  - `ruff-check` hook entry 改回 `uv run --no-sync ruff check`（去 bash wrapper）
  - `ruff-format` hook entry 改回 `uv run --no-sync ruff format --check`
  - `pyright` + `pytest` hook 保留 warn-only bash wrapper
  - 顶部注释从"全 WARN-ONLY"改为"分阶段严格：ruff 严格 / pyright/pytest warn-only"
- [ ] 1.2 验证 ruff 仍 0 errors：`uvx ruff check .`
- [ ] 1.3 commit `feat(lint): enable strict mode for ruff (pyright/pytest still warn-only)`

## 2. 收口

- [ ] 2.1 更新 `docs/CHANGELOG.md` `[Unreleased]` 加 `### Changed` 段
- [ ] 2.2 commit `docs: changelog for ruff-strict-mode-enable`
- [ ] 2.3 push（用户 1-click）
- [ ] 2.4 `openspec archive ruff-strict-mode-enable --yes`
