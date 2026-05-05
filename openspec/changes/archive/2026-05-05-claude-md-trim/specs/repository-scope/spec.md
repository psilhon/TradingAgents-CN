## MODIFIED Requirements

### Requirement: 文档范围 — fork 自维护，不含上游历史叙述

`docs/` 目录 SHALL 只含本 fork 维护的文档。上游历史 release notes / blog / 学习中心残留 MUST 删除。

`CLAUDE.md` SHALL 控制在 **50-175 行**（fork 项目实际复杂度高于通用 50-150 模板，本 spec 放宽 25 行）。长尾 / 历史性 / 阅读频率低的内容（典型如"已知坑"清单）MUST 外置到 `docs/ai-context/<topic>.md`，CLAUDE.md 仅留 1 行指引链接。

具体保留：

- `docs/CHANGELOG.md`（fork 自己的 changelog）
- `docs/USAGE.md`（fork 维护者使用手册）
- `docs/ai-context/` 目录（AI prime context；可含 `known-issues.md` 等长尾外置内容）
- `docs/architecture/` / `docs/api/` / `docs/configuration/` 等技术参考文档（功能性，非历史叙述）

具体删除：

- `docs/releases/`（上游 release notes，fork 不发 release）
- `docs/blog/`（上游 blog post，叙述性历史）
- `docs/learning/`（学习中心 docs）
- `docs/paper/`（学习中心 paper 资源 / 或模拟交易设计 paper — 用户决策"全删"）
- `docs/blog/2025-11-15-learning-center-and-compliance-updates.md`（学习中心专题，已被 docs/blog 整目录删覆盖）
- 各种 Windows-only 故障排查 docs（合并入"Requirement: 平台支持范围"）

#### Scenario: docs 子目录范围

- **WHEN** `ls docs/` 不含 `releases` / `blog` / `learning` / `paper` 子目录
- **AND** `find docs -name "*windows*" -iname "*portable*"` 命中 0
- **THEN** 范围合规

#### Scenario: CLAUDE.md 行数控制

- **WHEN** `wc -l CLAUDE.md`
- **THEN** 输出行数 ≤ 175
- **AND** 不含详细的"已知坑"清单（仅 1 行指引到 `docs/ai-context/known-issues.md`）

#### Scenario: 已知坑外置位置

- **WHEN** 用户或 AI 助手寻找"已知坑 / 踩过的坑"信息
- **THEN** `docs/ai-context/known-issues.md` 存在并含完整清单
- **AND** CLAUDE.md「AI 上下文入口」段或类似位置含指引"已知坑：见 docs/ai-context/known-issues.md"
