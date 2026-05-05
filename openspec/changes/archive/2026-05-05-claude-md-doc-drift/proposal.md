## Why

`docs/code-review-2026-05-05.md` Tier 1 第 4 条：项目级 CLAUDE.md 多处与现状漂移：

1. **line 8**：`pyproject.toml 标 1.0.0-preview，未对齐` — 已对齐至 `v1.1.0`（v1.1.0 release 时 bump 过）
2. **line 9**：`Phase 0 完成；下一动作 = Phase 1 立项第一个 OpenSpec change` — 实际已沉淀 20+ archived changes + 7 个 stable specs，远超 Phase 0
3. **line 41-50**：声称"3 个 docker-compose 变体"（`docker-compose.yml` / `docker-compose.hub.nginx.yml` / `docker-compose.hub.nginx.arm.yml`），但后两个**不存在**（仅 `docker-compose.yml` + `docker-compose.override.yml`）
4. **line 45**：image tag `tradingagents-backend:v1.0.0-preview` — 已改 `v1.1.0`
5. **line 73**：pyproject "70+ 直接依赖含 motor/streamlit/fastapi/uvicorn" — `streamlit` 和 `chainlit` 已在 `stable-v1-cleanup` 中删除
6. **line 81 / 91**：`pre-commit hook 处于 WARN-ONLY 模式` — 实际已转 STRICT（OpenSpec change `ruff-strict-mode-enable` + `pyright-handfix-pass-2` + `pytest-marker-strict` 完成）

CLAUDE.md 是 AI 助手 / 新会话 prime context 入口，漂移内容会误导后续工作。

## What Changes

- **MODIFIED** `CLAUDE.md`：6 处漂移修正
  - 项目身份段：版本对齐 `v1.1.0`、阶段更新为"v1.1.0 已发布，进入持续维护 + review-driven 改进期"
  - 命令速查段：删除不存在的 hub.nginx compose 变体描述、image tag 改 `v1.1.0`
  - 项目特殊约定段：删 streamlit/chainlit 残留描述、`pre-commit hook STRICT 模式`（不是 WARN-ONLY）
  - Fork patch 清单：`pre-commit-config.yaml` 描述改 STRICT

无 spec delta（这是把 CLAUDE.md 文档对齐到既有 specs 已锁定的现实）。

## Capabilities

无新增 / 修改 capability。

## Impact

**改动文件**：CLAUDE.md
**风险**：极低
**收益**：消除 AI 助手 / 新会话 prime context 误导
