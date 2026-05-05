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

