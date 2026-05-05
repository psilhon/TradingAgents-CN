## 1. silence 7 类 — commit 1

- [ ] 1.1 编辑 `pyproject.toml [tool.pyright]` 加 7 个 rule = "none"（reportAttributeAccessIssue / reportFunctionMemberAccess / reportReturnType / reportMissingModuleSource / reportUnsupportedDunderAll / reportOperatorIssue / reportAssignmentType）
- [ ] 1.2 验证 `uvx pyright` 错误数从 1,224 降到 ~830（-32%）
- [ ] 1.3 验证 `uvx ruff check .` 仍 0 errors
- [ ] 1.4 commit

## 2. 收口

- [ ] 2.1 更新 docs/CHANGELOG.md
- [ ] 2.2 commit
- [ ] 2.3 push
- [ ] 2.4 archive
