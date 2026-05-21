## 0. Phase 0 cross-check（pre-plan-checklist 已过 — 既有项目骨架全在位）

- [x] 0.1 既有项目骨架（CLAUDE.md / docs/ai-context/ / CHANGELOG / USAGE / .gitignore / ci.yml / .pre-commit-config.yaml）全部 ✅
- [x] 0.2 fork-patch 不动清单（pyproject.toml / vite.config.ts / .pre-commit-config.yaml / ci.yml / .gitignore patch 段）—— 本 change 零触碰
- [x] 0.3 license boundary：本 change 零触碰 `app/` / `frontend/` / `tradingagents/`
- [x] 0.4 端口段位 + loopback 不变（本 change 不改网络配置）
- [x] 0.5 HARD-GATE：本地 commit 允许；push 到 `feat/**` 分支需对话期再说
- [x] 0.6 guard-proprietary hook marker `openspec/changes/.implementing` 在 Phase 1 第一个 task 写为 `2026-05-21-docs-stabilization-v1`

## 1. OpenSpec scaffolding + .implementing marker — commit 1

- [x] 1.1 创建 `openspec/changes/2026-05-21-docs-stabilization-v1/` 目录
- [x] 1.2 写 `proposal.md`
- [x] 1.3 写 `tasks.md`（本文件）
- [x] 1.4 写 `specs/documentation-structure/spec.md`（新 capability，ADDED Requirements）
- [ ] 1.5 写 `openspec/changes/.implementing` = `2026-05-21-docs-stabilization-v1`
- [ ] 1.6 commit（仅 OpenSpec 文件 + .implementing marker）

## 2. archive 目录骨架 + README 占位 + 处理顶层 5 个 flat 文件 — commit 2

> 目的：先建好 archive 目录结构 + 冻结声明 README，再做 `git mv`，确保 mv 后立即有合规约定可读。
> 同时处理 `docs/archive/` 顶层已有 5 个 flat 文件（2026-05-05 由 `refactor: 整理项目根目录结构` 引入）。

- [ ] 2.1 `mkdir -p docs/archive/dev-history docs/archive/legacy-upstream`
- [ ] 2.2 写 `docs/archive/README.md`（顶层导览）：声明本目录用途（冻结归档区）+ 介绍两个子目录 `dev-history/` / `legacy-upstream/` 的分类标准 + 链接到 `openspec/specs/` 为功能 SSOT
- [ ] 2.3 写 `docs/archive/dev-history/README.md`：冻结声明（冻结于 fork v1.3.x，冻结日期 2026-05-21，不再更新，功能事实见 `openspec/specs/`）+ 子目录索引（含从顶层 mv 进来的 5 个 flat 文件 + bugfix / fixes / tech_reviews / changes / improvements / analysis / implementation / migration / summary / integration，每条一行描述）
- [ ] 2.4 写 `docs/archive/legacy-upstream/README.md`：冻结声明（同上）+ 子目录索引（deployment / development / community / survey / agents / 根目录散落的上游 narrative 列表）+ 与 fork 当前实践的对照表（如 deployment/EMBEDDED_PYTHON_GUIDE.md → openspec/specs/native-local-deployment/spec.md）
- [ ] 2.5 `git mv` 顶层 5 个 flat 文件到 `dev-history/`：
  - [ ] 2.5.1 `git mv docs/archive/AUTHENTICATION_FIX_SUMMARY.md docs/archive/dev-history/`
  - [ ] 2.5.2 `git mv docs/archive/BACKEND_STARTUP.md docs/archive/dev-history/`
  - [ ] 2.5.3 `git mv docs/archive/FIXES_SUMMARY.md docs/archive/dev-history/`
  - [ ] 2.5.4 `git mv docs/archive/README-ORIGINAL.md docs/archive/dev-history/`
  - [ ] 2.5.5 `git mv docs/archive/SOLUTION_SUMMARY.md docs/archive/dev-history/`
- [ ] 2.6 commit（archive 目录骨架 + 3 个 README + 5 个 flat 文件 mv）

## 3. git mv 归档过程性文档到 `docs/archive/dev-history/` — commit 3-12

> 每个目录一次 commit，便于回滚 + 审查；每次 commit 前 `git status` 确认改动只含 `git mv`。
>
> **wholesale archive 决策标准**：每个目录 mv 前执行 `grep -r "docs/<dir>" docs/ai-context/ docs/USAGE.md openspec/specs/ CLAUDE.md` 验证**没有任何当前 SSOT 文档引用该目录**。命中即停下来逐文件评估，零命中再 wholesale mv。所有命中的引用必须改成新路径或删除。
>
> **共同 rationale**：以下 10 个目录的内容均为 fork 开发过程一次性产物（dated bugfix notes / 一次性 fix summary / 已完成的设计评审 / 已完成的实施计划 / 已完成的 migration 记录），不是用户 / 二开持续查阅的参考资料；其规则性事实已被 22 个 stable capability spec 覆盖。

- [ ] 3.1 grep 引用预检：`grep -rEn "docs/(bugfix|fixes|tech_reviews|changes|improvements|analysis|implementation|migration|summary|integration)/" docs/ai-context/ docs/USAGE.md docs/README.md openspec/specs/ CLAUDE.md 2>/dev/null` → 输出零命中或全部命中已记录待 Phase 6 修；若命中数 > 5 则停下来重新评估范围
- [ ] 3.2 `git mv docs/bugfix docs/archive/dev-history/bugfix` → commit 3（10 文件）
- [ ] 3.3 `git mv docs/fixes docs/archive/dev-history/fixes` → commit 4（38 文件）
  - mv 前抽样验证 3 个文件名（`API_PATH_FIX.md` / `NEWS_SYNC_SCHEDULER_SETUP.md` / `tdx_removal.md`）是否为一次性 fix notes → 头部含日期 / "已修复" / 一次性结论 ✓
- [ ] 3.4 `git mv docs/tech_reviews docs/archive/dev-history/tech_reviews` → commit 5（8 文件）
- [ ] 3.5 `git mv docs/changes docs/archive/dev-history/changes` → commit 6（5 文件 + DEPRECATION_NOTICE）
- [ ] 3.6 `git mv docs/improvements docs/archive/dev-history/improvements` → commit 7（6 文件）
- [ ] 3.7 `git mv docs/analysis docs/archive/dev-history/analysis` → commit 8（9 文件）
- [ ] 3.8 `git mv docs/implementation docs/archive/dev-history/implementation` → commit 9（2 文件）
- [ ] 3.9 `git mv docs/migration docs/archive/dev-history/migration` → commit 10（2 文件）
- [ ] 3.10 `git mv docs/summary docs/archive/dev-history/summary` → commit 11（3 文件）
- [ ] 3.11 `git mv docs/integration docs/archive/dev-history/integration` → commit 12（3 文件）
- [ ] 3.12 每次 commit message 用统一格式：`docs(archive): freeze docs/<dir> under archive/dev-history/`
- [ ] 3.13 全部 mv 完后 `git log --follow docs/archive/dev-history/bugfix/2025-10-26-ps-calculation-fix.md` 验证历史可追溯

## 4. git mv 归档上游遗产到 `docs/archive/legacy-upstream/` — commit 13-18

- [ ] 4.1 `git mv docs/deployment docs/archive/legacy-upstream/deployment` → commit 13
- [ ] 4.2 `git mv docs/development docs/archive/legacy-upstream/development` → commit 14
- [ ] 4.3 `git mv docs/community docs/archive/legacy-upstream/community` → commit 15
- [ ] 4.4 `git mv docs/survey docs/archive/legacy-upstream/survey` → commit 16
- [ ] 4.5 `git mv docs/agents docs/archive/legacy-upstream/agents` → commit 17
- [ ] 4.6 移动根目录散落的上游 narrative 文件（按文件粒度，**逐个**确认非 fork 自维护后再 mv）→ commit 18：
  - [ ] 4.6.1 `git mv docs/BUILD_GUIDE.md docs/archive/legacy-upstream/`
  - [ ] 4.6.2 `git mv docs/QUICK_BUILD_REFERENCE.md docs/archive/legacy-upstream/`
  - [ ] 4.6.3 `git mv docs/DOCKER_REGISTRY_STRATEGY.md docs/archive/legacy-upstream/`
  - [ ] 4.6.4 `git mv docs/SETTINGS_MERGE.md docs/archive/legacy-upstream/`
  - [ ] 4.6.5 `git mv docs/SILICONFLOW_SETUP_GUIDE.md docs/archive/legacy-upstream/`
  - [ ] 4.6.6 `git mv docs/MODEL_RECOMMENDATION_UI_UPDATE.md docs/archive/legacy-upstream/`
  - [ ] 4.6.7 `git mv docs/CONFIG_VALIDATION_FIX_SUMMARY.md docs/archive/legacy-upstream/`
  - [ ] 4.6.8 `git mv docs/ENHANCED_HISTORY_FEATURES_SUMMARY.md docs/archive/legacy-upstream/`
  - [ ] 4.6.9 `git mv docs/GITHUB_BRANCH_PROTECTION.md docs/archive/legacy-upstream/`
  - [ ] 4.6.10 `git mv docs/API_KEY_MANAGEMENT_ANALYSIS.md docs/archive/legacy-upstream/`
  - [ ] 4.6.11 `git mv docs/API_KEY_TESTING_GUIDE.md docs/archive/legacy-upstream/`
  - [ ] 4.6.12 `git mv docs/ANALYST_DATA_CONFIGURATION.md docs/archive/legacy-upstream/`
  - [ ] 4.6.13 `git mv docs/LLM_ADAPTER_TEMPLATE.py docs/archive/legacy-upstream/`（错放位置的 Python 文件）
  - [ ] 4.6.14 `git mv docs/CNAME docs/archive/legacy-upstream/`（GitHub Pages 上游配置，fork 不用）
- [ ] 4.7 **不在本 change 范围**：`docs/architecture/` 和 `docs/design/` 不动
  - 理由：`openspec/specs/repository-scope/spec.md` Req「文档范围」line 91 把 `docs/architecture/` 列为「具体保留」（功能性技术参考）；`CLAUDE.md` line 110 同样列为「完全不动」
  - 即便部分文件（如 `architecture/API_ARCHITECTURE_UPGRADE.md` / `architecture/DATA_SOURCE_REFACTOR.md`）已被 OpenSpec spec 替代，本 change 也不动；后续单独开 change 走 `repository-scope` spec MODIFY 流程评估
- [ ] 4.8 评估其他存疑目录（**不归档**保留）：
  - `docs/architecture/` / `docs/design/`（见 4.7 — repository-scope spec 保护）
  - `docs/api/` / `docs/configuration/` / `docs/data/` / `docs/frontend/` / `docs/guides/` / `docs/llm/` / `docs/usage/` / `docs/troubleshooting/` / `docs/faq/` / `docs/maintenance/` / `docs/overview/` / `docs/examples/` / `docs/features/` / `docs/security/` / `docs/technical/` / `docs/technical-debt/` / `docs/localization/` / `docs/config/` —— 用户 / 二开仍可能查阅的参考资料
  - `docs/superpowers/`（含 `plans/` / `specs/` 子目录）—— superpowers skill 输出物，性质类似 openspec/，**原地保留不动**
  - 根目录散落但 fork 仍维护：`docs/USAGE.md` / `docs/CHANGELOG.md` / `docs/code-review-2026-05-05.md` / `docs/data-audit-2026-05-17.md` / `docs/test_environment_setup.md` / `docs/error-handling-improvement.md` / `docs/google-ai-base-url-support.md` / `docs/import_config_with_script.md` / `docs/frontend-auth-optimization.md` / `docs/time_estimation_optimization.md` / `docs/database_setup.md`
- [ ] 4.9 commit message 统一：`docs(archive): freeze legacy upstream <dir>` / `docs(archive): freeze upstream narrative under root`

## 5. 顶层 fork 视角入口 — commit 19

- [ ] 5.1 写 `docs/README.md`（fork 视角，**覆盖**上游 docs/README.md）：
  - 头部 SSOT 声明（功能事实 = openspec/specs/，narrative = docs/ai-context/）
  - 4 个角色入口章节（用户 / 二开 / 运维 / AI prime），每节 3-5 条链接
  - 链接全部指向**已存在**文件（包括即将在 Phase 6/7 写的 `operations.md` / 重写后的 `QUICK_START.md`——这两个文件已在本 commit 同步写好后再 commit）
- [ ] 5.2 写 `docs/operations.md`（新建）：
  - 端口段位（54300-54309）
  - 原生服务管理（mongo / redis 启停 / 配置位置）
  - 数据备份 / 恢复（DATABASE_BACKUP_RESTORE.md 引用 + 实操命令）
  - 日志位置 / tail 命令
  - 提炼 `docs/maintenance/mongodb_index_optimization.md` + `docs/data-audit-2026-05-17.md` 可复用部分
- [ ] 5.3 重写 `docs/QUICK_START.md`（**覆盖**上游版本，fork 视角）：
  - 首次部署 = `./scripts/setup-native.sh`
  - 日常 = `just up` / `just down` / `just status`
  - 一条龙跑通 CLI demo / web demo 的最短路径
  - 不含 Docker / embedded python 路径
- [ ] 5.4 commit 三个文件一起（属同一逻辑组：fork 视角入口三件套）

## 6. ai-context + USAGE 刷新 — commit 20

- [ ] 6.1 改 `docs/ai-context/architecture.md`：
  - 新增「v1.3.x 已固化 capability 列表」小节，按 `ls openspec/specs/` 真实列表生成 22 条，每条 `- [capability-name](../../openspec/specs/<name>/spec.md) — 一句话描述`
  - 已有架构描述不动；新增小节放在文件末尾或合适位置
- [ ] 6.2 改 `docs/ai-context/project-structure.md`：
  - 删除已 mv 到 archive 的顶层目录引用
  - 新增 `docs/archive/` 章节，标注「冻结归档区，详见子目录 README」
  - 调整 docs/ 顶层目录树
- [ ] 6.3 改 `docs/USAGE.md`：
  - 顶部加 SSOT 指针段（一句话："功能事实见 openspec/specs/；本文是面向用户的操作指引"）
  - 补功能使用矩阵表格（| 功能 | 描述 | 对应 capability spec | 使用入口 |），按 capability 列出 Dashboard / Watchlist / Paper Account / Daily Recommendation / Portfolio / Analysts 等用户可见功能
  - **修正 line 12 `git remote add upstream` 与 fork 独立分叉模式冲突**：把第 12 行的赤裸 `git remote add upstream` 指令改写为"如果需要 cherry-pick 上游某条 commit 时临时加 remote，用完即删"的形式（参考文件 line 101-109 已有的正确表述），或直接删除——`repository-scope` spec 已明确不再定期 sync upstream
- [ ] 6.4 commit

## 7. CLAUDE.md / 规则层小幅更新 — commit 21

- [ ] 7.1 改项目 `CLAUDE.md`：
  - 「AI 上下文入口」段：把 `docs/README.md` 放第 1 位（fork 视角入口）；`docs/operations.md` 加入清单（运维角色 prime）；调整后续优先级
  - 增一句："**功能事实以 `openspec/specs/` 为准，docs/ai-context 描述跨 capability 的横切关系；docs/ 其它目录默认为参考资料或归档**"
  - 「Fork patch 清单」段：`docs/README.md` 加入清单（fork 视角覆盖上游版本）+ `docs/QUICK_START.md` 加入清单（同）+ `docs/operations.md` 加入清单（新建 fork-local 文件）
  - 「完全不动」段无需改动（本 change 不动 `docs/architecture/` 和 `docs/design/`）
- [ ] 7.2 验证 CLAUDE.md 仍在合理体量（50-150 行目标内，必要时不删旧内容只追加）
- [ ] 7.3 commit

## 8. CHANGELOG entry — commit 22

- [ ] 8.1 `docs/CHANGELOG.md` `[Unreleased]` 段加 `### Added` + `### Changed`：
  - Added：`docs/README.md` fork 视角入口 / `docs/operations.md` 运维手册 / `docs/archive/` 归档区 / 新 capability `documentation-structure`
  - Changed：`docs/QUICK_START.md` 重写为 fork 视角 / `docs/ai-context/architecture.md` 增 capability 索引 / `docs/USAGE.md` 增功能矩阵 / 约 150 个过程文档归档到 `docs/archive/`
  - 简述固化阶段定位变化（功能事实 SSOT 唯一化）
- [ ] 8.2 commit

## 9. 验证 + Archive — commit 23

- [ ] 9.1 `just ci` 通过（lint + typecheck + test）—— 预期：本 change 零代码改动，CI 应不受影响
- [ ] 9.2 `cd frontend && npm run type-check` 0 errors —— 预期：不受影响
- [ ] 9.3 链接死链检查：手动验证 `docs/README.md` / `docs/ai-context/architecture.md` 中所有 markdown 链接指向真实文件（用 `find` + grep 验证存在性）
- [ ] 9.4 grep 验证：archive 路径下不含 fork 仍依赖的真实事实文件（即不能 mv 错文件）
  - `grep -r "docs/archive" docs/ai-context/ docs/USAGE.md docs/operations.md docs/README.md` 命中应仅指向 archive 引用而非内容
- [ ] 9.5 git 历史验证：随机抽 5 个 mv 后的文件跑 `git log --follow`，确认原路径历史完整
- [ ] 9.6 删除 `openspec/changes/.implementing` marker
- [ ] 9.7 Archive change：mv `openspec/changes/2026-05-21-docs-stabilization-v1/` → `openspec/changes/archive/2026-05-21-docs-stabilization-v1/`
- [ ] 9.8 Spec sync：mv `openspec/changes/archive/2026-05-21-docs-stabilization-v1/specs/documentation-structure/spec.md` → `openspec/specs/documentation-structure/spec.md`（新 capability，无合并冲突；`## Purpose` 段已在 Phase 1 写好，不需补）
- [ ] 9.9 commit archive + spec sync（commit 25）
- [ ] 9.10 给 finishing report + 问用户 push / tag 决策（commit 26 = 本 change 不出现，只是 finishing 动作）

## 不在本 change 范围（明确 YAGNI）

- 删除归档文件（保留全部 git 历史；archive 目录仍在仓库内）
- 重写 `docs/configuration/` / `docs/llm/` / `docs/data/` 等保留目录的内容（仅评估是否归档，不动内容）
- 改写 `tradingagents/` Apache 2.0 主代码注释 / docstring
- 改 `frontend/src/` 或 `app/` 任何内容（专有授权）
- 改 pyproject.toml / vite.config.ts / pre-commit / CI / gitignore 任何 fork-patch 段
- 改 `openspec/specs/` 已有 22 个 spec 任何内容（仅新增 `documentation-structure`）
- `docs/CHANGELOG.md` 历史 entry 改写（只加新 entry）
- 上游 cherry-pick 流程文档（fork 已声明独立分叉，无需此流程文档）
- 多语言文档（fork 用 zh-CN，不维护 en）
- 实际 release v1.3.1 / v1.4——本 change 只更新文档结构，release 决策另议

## 文档维护节奏检查（按 Requirement 4）

本 change archive 时 MUST 同步更新：

- [x] `docs/CHANGELOG.md`：Phase 8 已含
- [x] `docs/ai-context/architecture.md`：Phase 6.1 已含（capability 索引）—— 但本 change 不新增 capability 之外，capability 索引会含 `documentation-structure` 本身
- [x] `docs/USAGE.md`：Phase 6.3 已含（SSOT 指针 + 功能矩阵）—— 本 change 不新增用户可见功能，功能矩阵只涵盖已固化 capability
- [x] `docs/ai-context/known-issues.md`：本 change 不引入 / 不解决已知问题，**显式标注无需更新**
