# audit-tooling Specification

## Purpose
TBD - created by archiving change binding-audit-tooling. Update Purpose after archive.
## Requirements
### Requirement: 端口审计 just task 必须存在

`justfile` MUST 提供 `audit-ports` task，一键检查所有 5430x 端口的实际 binding 状态（lsof + nc）。

`audit-ports` 输出 MUST 包含：
- 每个 5430x 端口的 LISTEN 进程 + 绑定地址（127.0.0.1 vs * vs 0.0.0.0）
- 标记违规：任何绑定 `*` 或 `0.0.0.0` 的端口（违反 loopback 规定）

#### Scenario: 全栈正常时跑 just audit-ports

- **WHEN** mongo + redis + backend + vite 全部跑且全绑 127.0.0.1
- **AND** 用户在仓库根执行 `just audit-ports`
- **THEN** 输出 5 行 LISTEN 状态（mongo 54302 / redis 54303 / backend 54301 / vite 54300）
- **AND** 全部标记 ✓ 合规
- **AND** exit code 0

#### Scenario: 某服务绑 0.0.0.0 时跑

- **WHEN** 某服务（如 vite 用 `--host 0.0.0.0` 启动）绑 *:54300
- **AND** 用户执行 `just audit-ports`
- **THEN** 该端口标记 ⚠️ 违规
- **AND** exit code 非 0（可被 CI 检测）

### Requirement: Binding 文件审计 just task 必须存在

`justfile` MUST 提供 `audit-binds` task，一键 grep fork-local tracked 文件中的 `0.0.0.0` / 上游 hardcode 端口违规。

`audit-binds` 检查范围：CLAUDE.md / docs/USAGE.md / docs/ai-context/* / docker-compose.override.yml / .env / pyproject.toml / frontend/vite.config.ts。

#### Scenario: fork-local 文件无违规时跑

- **WHEN** 所有 fork-local 文件中 `0.0.0.0` 仅出现在叙述性文本（如 "禁止绑 0.0.0.0"）
- **AND** 端口数字仅段位 5430x 或合法叙述
- **THEN** `just audit-binds` 报告 0 违规

#### Scenario: vite.config.ts hardcode 0.0.0.0 时

- **WHEN** `frontend/vite.config.ts` 含 `host: '0.0.0.0'` 配置项（不是注释）
- **THEN** `just audit-binds` 标记该行违规
- **AND** exit code 非 0

### Requirement: CLAUDE.md 必须含 Fork patch 清单

`CLAUDE.md` MUST 含「Fork patch 清单」段，列举所有"必须 patch 的上游 tracked 文件"（典型如 `frontend/vite.config.ts` 的 host/port/proxy），与"完全不动的上游代码"明确区分。

新加上游 tracked 文件改动时，开发者 MUST 先读此清单决定改不改。

#### Scenario: AI 助手或开发者 review 是否要改 frontend/vite.config.ts

- **WHEN** 开发者考虑修改 `frontend/vite.config.ts`
- **AND** 打开 `CLAUDE.md` 找「Fork patch 清单」段
- **THEN** 文档明确说明 vite.config.ts 是"端口/binding 必改"的 fork-local 必 patch 文件
- **AND** 列出已 patch 的字段（host / port / proxy.target / strictPort / hmr.host）

### Requirement: coding-standards.md 必须含配置层次表

`docs/ai-context/coding-standards.md` MUST 含「配置层次表」段，列举 binding / port 配置的 6 个层次（CLI args / env vars / vite.config.ts / pyproject.toml / docker-compose / 上游 hardcode 代码）+ 优先级 + 改哪层影响什么 + 改完必跑哪个 audit task。

#### Scenario: 新会话 AI 助手 prime context 时读到层次表

- **WHEN** AI 助手新会话读 `docs/ai-context/coding-standards.md` 作为 prime
- **THEN** 文档提供清晰的 6 层配置优先级表
- **AND** 每层标注影响范围（如"CLI 临时覆盖"vs".env 持久"vs"vite.config.ts 全 fork"）
- **AND** 标注改完后必跑的 audit task 名（`just audit-ports` / `just audit-binds`）

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

### Requirement: 数据健康审计脚本 MUST tracked 于 scripts/

数据正确性审计脚本 MUST 作为 tracked 文件存在于 `scripts/data_audit.js`，MUST NOT 是 `/tmp` 下的一次性产物。

脚本 MUST 能直连 MongoDB 检查关键集合（`stock_basic_info` 等）的字段完整率与数值合理性（neg / zero / null / NaN），用于迁移后验证与定期复核数据健康。

理由：data-audit 2026-05-17 的审计脚本是 `/tmp/data_audit.js` 一次性产物，重启即丢，无法定期复核数据健康，也无法作为 Phase 3 迁移后的验证工具。

#### Scenario: 审计脚本在版本库

- **WHEN** 在仓库扫描数据审计脚本
- **THEN** `scripts/data_audit.js` 是 tracked 文件
- **AND** 不依赖 `/tmp` 下的临时副本

#### Scenario: 运行数据健康检查

- **WHEN** 执行 `mongosh <连接串> --quiet --file scripts/data_audit.js`
- **THEN** 输出各关键集合的字段完整率 + 数值合理性报告
- **AND** 报告标记低覆盖率字段与数学异常值（负 `ps` / 量级失真 `pe` 等）

