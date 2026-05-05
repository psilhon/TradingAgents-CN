## 1. 创建 docs/ai-context/known-issues.md — commit 1

- [ ] 1.1 新建 `docs/ai-context/known-issues.md`，把 CLAUDE.md 当前「已知坑」段（line 170-179）原样拷贝过去 + 加 doc header
- [ ] 1.2 编辑 `CLAUDE.md` 删除「已知坑」段（line 170-179）
- [ ] 1.3 编辑 `CLAUDE.md`「AI 上下文入口」段补 1 行：`已知坑（fork 撞过的坑 + 上游遗留）：docs/ai-context/known-issues.md`
- [ ] 1.4 验证 `wc -l CLAUDE.md` ≤ 150
- [ ] 1.5 commit `docs(claude-md): trim known-issues to docs/ai-context/known-issues.md`

## 2. 收口

- [ ] 2.1 更新 `docs/CHANGELOG.md` `[Unreleased]` 加 `### Changed` 段
- [ ] 2.2 commit `docs: changelog for claude-md-trim`
- [ ] 2.3 push（用户 1-click HARD-GATE）
- [ ] 2.4 `openspec archive claude-md-trim --yes`（会 MODIFY base spec repository-scope 的「文档范围」Requirement）
