## 1. 删 workflow + 更 spec — commit 1

- [x] 1.1 `git rm .github/workflows/upstream-sync-check.yml`
- [x] 1.2 验证仓库内不再有任何 cron / 自动 push 的 workflow（grep `upstream` 仅命中 `uv sync` 字面，非真实 upstream sync）
- [x] 1.3 `ruff check` + `pyright` 仍 0 errors
- [x] 1.4 commit

## 2. 收口

- [x] 2.1 docs/CHANGELOG.md 加 `### Removed` 条目
- [x] 2.2 commit + archive
