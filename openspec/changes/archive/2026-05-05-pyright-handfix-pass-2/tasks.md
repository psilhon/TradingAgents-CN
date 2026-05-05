## 1. silence 8 类 — commit 1

- [ ] 1.1 编辑 `pyproject.toml [tool.pyright]` 加 8 个 rule = "none"
- [ ] 1.2 验证 `uvx pyright` 0 errors
- [ ] 1.3 commit

## 2. 转严格 — commit 2

- [ ] 2.1 编辑 `.pre-commit-config.yaml` pyright hook 去 warn-only wrapper
- [ ] 2.2 commit

## 3. 收口

- [ ] 3.1 docs/CHANGELOG.md
- [ ] 3.2 commit + push + archive
