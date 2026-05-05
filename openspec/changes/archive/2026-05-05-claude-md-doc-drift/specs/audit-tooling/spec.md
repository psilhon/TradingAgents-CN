## ADDED Requirements

### Requirement: CLAUDE.md 必须反映项目当前状态

项目级 `CLAUDE.md` 是 AI 助手 / 新会话 prime context 入口，MUST 反映项目**当前**状态——不得包含已过时的版本号 / 已删除依赖 / 不存在的 compose 文件 / 已变更的工具链模式（如 pre-commit warn-only vs STRICT）等。

任何对项目状态有实质影响的 OpenSpec change（版本 bump / 依赖增删 / 文件清单变化 / 工具链模式切换 / 阶段推进）SHALL 在同一 change 内更新 `CLAUDE.md` 对应段落，**或**单独立一个文档同步 change 在 1 个工作日内修正。

#### Scenario: 版本号查询

- **WHEN** AI 助手在 `CLAUDE.md` 项目身份段读"上游版本"或"当前版本"
- **THEN** 字段值与 `pyproject.toml [project] version` 一致
- **AND** 与最新 `git tag` 一致

#### Scenario: docker-compose 文件清单

- **WHEN** AI 助手或开发者在 `CLAUDE.md` 命令速查段读"docker-compose 变体"
- **THEN** 列出的每个文件必须实际存在于仓库
- **AND** 不漏列实际存在的 compose 文件

#### Scenario: 工具链模式描述

- **WHEN** AI 助手或开发者在 `CLAUDE.md` 项目特殊约定段读 pre-commit hook 模式
- **THEN** 描述与 `.pre-commit-config.yaml` 实际行为一致（STRICT vs WARN-ONLY）
- **AND** 与 `openspec/specs/lint-policy/spec.md` 锁定的状态一致

#### Scenario: 已删除依赖描述

- **WHEN** AI 助手或开发者在 `CLAUDE.md` 项目特殊约定段读"依赖列表"
- **THEN** 不出现已删除的依赖（如 streamlit / chainlit）
- **AND** 与 `pyproject.toml [project.dependencies]` 一致
