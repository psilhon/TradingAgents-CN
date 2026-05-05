## MODIFIED Requirements

### Requirement: Fork 独立分叉模式

本仓库 SHALL 是 `hsliuping/TradingAgents-CN` 的**独立分叉**，**不再定期** `git pull upstream/main`。任何上游新功能 / 修复都通过手动 cherry-pick 单独决策引入，不批量 merge。

CLAUDE.md / docs/USAGE.md MUST 反映此状态——不在文档中建议配置 `upstream` remote 或定期同步流程。

仓库 MUST NOT 包含任何自动化 upstream sync 的 GitHub Actions workflow / cron job / 定时任务，包括但不限于：定时 fetch upstream、自动 `git push origin main`、自动 `gh issue create` 通知 sync 状态。

#### Scenario: AI 助手或新开发者读 CLAUDE.md

- **WHEN** AI 助手或新开发者打开 `CLAUDE.md` 寻找"如何与上游同步"
- **THEN** 文档明确说明本 fork 是独立分叉，不应建议 `git remote add upstream` 或 `git merge upstream/main`
- **AND** 不出现"定期同步上游"相关流程

#### Scenario: 仓库内不存在自动化 sync workflow

- **WHEN** 在 `.github/workflows/` 目录 grep `upstream` / `sync`
- **THEN** 命中数为 0
- **AND** 任何 workflow 文件 MUST NOT 含 `git push origin main` / `gh issue create` 等自动外部写入动作（CI lint+test 不属此列）
