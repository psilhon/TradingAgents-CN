# docs/archive — 冻结归档区

本目录用于隔离**不再维护**的过程性文档与上游遗产。挪入本目录的文件保留 git 历史完整可追溯（通过 `git log --follow`），但不再随项目演进更新。

## 子目录分类

| 目录 | 用途 |
|---|---|
| [`dev-history/`](dev-history/README.md) | fork 自己的开发过程产物：一次性 bugfix 记录 / 设计评审 / 实施计划 / migration 记录 / fix summary。冻结于 fork v1.3.x。 |
| [`legacy-upstream/`](legacy-upstream/README.md) | 上游遗产，与 fork 当前路径冲突：Docker / embedded python / portable 部署 / 上游分支策略 / 上游营销文档 / 上游原版 README 备份。冻结于 fork v1.3.x。 |

## 仍然需要找当前事实？

- **功能事实** → [`openspec/specs/`](../../openspec/specs/) — 22 个 stable capability spec，项目功能事实唯一来源
- **架构 / 横切关系** → [`docs/ai-context/`](../ai-context/) — project-structure / coding-standards / architecture / known-issues
- **用户操作** → [`docs/USAGE.md`](../USAGE.md)
- **快速启动** → [`docs/QUICK_START.md`](../QUICK_START.md)
- **运维 / 备份 / 端口** → [`docs/operations.md`](../operations.md)
- **变更历史** → [`docs/CHANGELOG.md`](../CHANGELOG.md)

## 不要引用本目录作为当前事实

本目录文档的截止日期定格在 fork v1.3.x。AI 助手 / 开发者引用任何 archive 内容时，必须明确"该文档已冻结"并查找对应 capability spec 验证当前事实。
