# docs/archive/legacy-upstream — 上游遗产（冻结）

**冻结版本**：fork v1.3.x
**冻结日期**：2026-05-21
**维护状态**：不再更新

本目录归档的是上游 `hsliuping/TradingAgents-CN` 遗留的文档，**与 fork 当前实践冲突**或**fork 用不到**：Docker 部署 / embedded python / portable installer / 上游分支策略 / 上游营销文档 / 上游原版 README 备份等。

fork 已在 `openspec/specs/repository-scope/spec.md` 声明独立分叉模式，不再批量 sync upstream；这些内容保留 git 历史以便 cherry-pick 时还能找到对应文件位置，但不应作为当前指导。

## fork 当前实践对照表

| 上游路径 | fork 当前替代 |
|---|---|
| `deployment/EMBEDDED_PYTHON_GUIDE.md` / `deployment/PORTABLE_FAQ.md` / `deployment/portable-*.md` | `openspec/specs/native-local-deployment/spec.md` + `scripts/setup-native.sh` + `scripts/dev.sh` |
| `deployment/DOCKER_LOGS_GUIDE.md` / Docker 相关 | 不适用——fork 用 Apple Silicon 原生 brew，零 Docker |
| `deployment/SIMPLE_DEPLOYMENT_GUIDE.md` / 启动脚本 | `docs/QUICK_START.md`（fork 版本） + `just up` |
| `development/BRANCH_GUIDE.md` / `BRANCH_MANAGEMENT_STRATEGY.md` | 不适用——fork 独立分叉，无上游同步流程 |
| `development/DEVELOPMENT_SETUP.md` / `DEVELOPMENT_WORKFLOW.md` | `docs/USAGE.md` § 1 + `docs/ai-context/coding-standards.md` + `justfile` |
| `community/CALL_FOR_TESTERS*.md` | 不适用——fork 是个人项目 |
| `survey/USER_SURVEY_2025.md` 等 | 不适用 |
| `agents/` 上游 marketing 内容 | 不适用 |
| 根目录 `DOCKER_REGISTRY_STRATEGY.md` / `BUILD_GUIDE.md` / `QUICK_BUILD_REFERENCE.md` | 不适用——fork 零 Docker |
| 根目录 `GITHUB_BRANCH_PROTECTION.md` | 不适用——fork 单分支策略 |
| 根目录 `MODEL_RECOMMENDATION_UI_UPDATE.md` / `SETTINGS_MERGE.md` | 已被现行 settings 系统替代，见 `openspec/specs/` |
| 根目录 `SILICONFLOW_SETUP_GUIDE.md` / `API_KEY_*.md` / `ANALYST_DATA_CONFIGURATION.md` | 当前 `docs/configuration/` 保留维护版本 |
| 根目录 `CONFIG_VALIDATION_FIX_SUMMARY.md` / `ENHANCED_HISTORY_FEATURES_SUMMARY.md` | 一次性 summary，已冻结 |
| `README-ORIGINAL.md` | 上游原版 README 备份；fork 现行 README 在仓库根 `README.md` |

## 当前事实在哪

- **fork 当前部署 / 运维**：[`docs/QUICK_START.md`](../../QUICK_START.md) + [`docs/operations.md`](../../operations.md) + [`openspec/specs/native-local-deployment/spec.md`](../../../openspec/specs/native-local-deployment/spec.md)
- **fork 独立分叉策略**：[`openspec/specs/repository-scope/spec.md`](../../../openspec/specs/repository-scope/spec.md)
- **配置仍然维护版**：[`docs/configuration/`](../../configuration/)（未归档；fork 保留并按需更新）

## 子目录索引

| 名称 | 文件数 | 来源 |
|---|---|---|
| `deployment/` | 14 | 上游 Docker / embedded python / portable 部署文档 |
| `development/` | 15 | 上游分支策略 / DEVELOPMENT_SETUP / 上游 workflow |
| `community/` | 4 | 上游 CALL_FOR_TESTERS 营销文档 |
| `survey/` | 4 | 上游 USER_SURVEY 调研文档 |
| `agents/` | 1 | 上游 agents 营销 |
| 顶层 flat 文件 | 15+ | 根目录散落的上游 narrative（详见对照表） |

## 引用注意

`fork-patch-guard` skill 已知本目录冻结。引用任何 archive 内容时务必明确"内容已冻结，参见 fork 当前实践对照表"。
