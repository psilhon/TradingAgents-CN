## Why

Phase 0 + 后续 4 个 OpenSpec change 实施过程中，**端口 / IP binding 类问题撞墙 4 次**：
1. 端口段位约定第一次落地（docker compose ports merge 是 append 不是 replace）
2. 5173 vite 例外（我擅自破例）
3. .env API_PORT/PORT/ALLOWED_ORIGINS 漏改
4. loopback 规定后 vite.config.ts hardcode `0.0.0.0` / proxy 8000 撞墙

**根因**（自我检讨）：
- 反应式排查 vs 主动审计（用户指出才查）
- 配置层次（CLI / env / config / hardcode / docker-compose / 上游代码）没在最初列出
- 不熟工具（docker compose merge 语义 / vite host 优先级）撞墙后才学
- 不用 lsof 立即验证（先改再启动再看 log，本末倒置）
- 对"专有授权"过度避让（绕了 3 次才妥协改 vite.config.ts）

本 change 把"撞墙学到的"系统化为**工具 + 文档**，把"反应式"变"主动式"：
- `just audit-ports` / `just audit-binds` 一键扫描 binding 状态
- CLAUDE.md「Fork patch 清单」段：明确"必须 patch 的上游 tracked 文件"区分
- coding-standards.md「配置层次表」：6 层优先级 + 改哪层影响什么

## What Changes

- **ADDED**：`justfile` 加 `audit-ports` + `audit-binds` 两个 task（lsof / nc / grep 一键审计）
- **ADDED**：`CLAUDE.md`「Fork patch 清单」段：列所有"为对齐 fork 端口段位 / loopback 必须改的上游文件"，区分"原则不改"vs"端口/binding 必改"
- **ADDED**：`docs/ai-context/coding-standards.md`「配置层次表」段：6 层（CLI / env / vite.config.ts / pyproject.toml / docker-compose / 上游 hardcode）+ 优先级 + 影响范围 + 改完必跑哪个 audit task

无 BREAKING change（仅新增工具 + 文档，无现有行为变更）。

## Capabilities

### New Capabilities

- `audit-tooling`：定义 binding/port 相关审计工具的存在性 + 调用规范

### Modified Capabilities

无。

## Impact

**改动文件**：3 个
- `justfile` (+2 task)
- `CLAUDE.md` (+15-20 行 「Fork patch 清单」段)
- `docs/ai-context/coding-standards.md` (+20-30 行 「配置层次表」段)

**风险**：

- ⚠️ CLAUDE.md 当前 ~149 行，加段后 ~170 行，**超过 50-150 行模板建议** —— 后续可考虑把"已知坑"段移到 `docs/ai-context/known-issues.md`，但本次不做
- 无 runtime 影响（纯文档 + just task 增加）

**收益**：

- 下次端口 / binding 改动后跑 `just audit-binds` 一键发现违规（避免重复撞墙）
- 新会话 AI 助手 prime 时读 coding-standards.md「配置层次表」立刻理解项目 binding 全栈
- Fork 维护者改上游文件时 CLAUDE.md「Fork patch 清单」明确告知"哪些必改 / 哪些不动"
