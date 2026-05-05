## 1. 调宽 pyright 配置 — commit 1

- [ ] 1.1 编辑 `pyproject.toml [tool.pyright]` 删除 `strict = ["tradingagents"]` 行
- [ ] 1.2 验证 `uvx pyright` 错误数从 ~9,955 降到 ~1,224（85%+ 削减）
- [ ] 1.3 验证 `uvx ruff check .` 仍 0 errors
- [ ] 1.4 commit `chore(pyright): drop strict tradingagents config (9955 → ~1224, -87%)`

## 2. 收口

- [ ] 2.1 更新 `docs/CHANGELOG.md` `[Unreleased]` 加 `### Changed` 段
- [ ] 2.2 commit `docs: changelog for pyright-cleanup-baseline`
- [ ] 2.3 push（用户 1-click）
- [ ] 2.4 `openspec archive pyright-cleanup-baseline --yes`
