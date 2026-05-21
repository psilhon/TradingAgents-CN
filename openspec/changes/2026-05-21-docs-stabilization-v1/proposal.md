## Why

v1.3.0 收口后项目进入**功能固化阶段**：22 个 stable capability spec + 38 archived changes 已经把"功能事实"沉淀到 `openspec/specs/`，但 `docs/` 下仍堆着 ~220 个 markdown，绝大多数是**开发期过程文档**（`docs/bugfix/` 10、`docs/fixes/` 30+、`docs/tech_reviews/` 8、`docs/development/` 15、`docs/configuration/` 26、`docs/deployment/` 14 等）和**上游遗产**（Docker / embedded python / 上游分支策略 / Streamlit 路径），与 fork 当前的"原生 brew + FastAPI + Vue + Apple Silicon + 端口 54300-54309"现状大面积脱节。

后果：
1. **AI prime context 被噪声污染**——subagent 启动会扫一遍 docs/，撞到上游 Docker 文档就会重复试错。
2. **新 contributor 找不到入口**——`docs/README.md` 是上游版本，没有 fork 视角；用户视角 / 二开视角 / AI prime 视角混在一起。
3. **功能事实双源**——`docs/architecture/`、`docs/design/`、`docs/improvements/` 与 `openspec/specs/` 同时声称是"功能 SSOT"，互相漂移。

固化阶段需要把 docs/ 折叠成**「角色化入口 + archive 隔离过程性文档」**的稳定参考层，并明确把"功能事实"让位给 `openspec/specs/`。

## What Changes

### 改动 1：新建顶层角色化入口 — `docs/README.md`（fork 视角覆盖上游）

四节：用户 / 二开 / 运维 / AI prime，每节 3-5 条链接，全部指向**已有**真实文件。
- 用户：`USAGE.md` + `openspec/specs/` 功能总览
- 二开：`ai-context/` + `openspec/specs/` + `CLAUDE.md`
- 运维：新建 `operations.md`（端口 / 备份 / 数据迁移 / 日志位置）
- AI prime：`CLAUDE.md` + `ai-context/project-structure.md` + `ai-context/architecture.md`

明确声明：**功能事实以 `openspec/specs/` 为准**；docs/ai-context/ 只描述跨 capability 的横切关系；docs/ 其余目录为参考资料 / 归档。

### 改动 2：建 archive 隔离层 — `docs/archive/{dev-history,legacy-upstream}/`

**`docs/archive/dev-history/`**（fork 自己的开发过程产物，已不再维护）：
- `docs/bugfix/` (10)
- `docs/fixes/` (30+)
- `docs/tech_reviews/` (8)
- `docs/changes/` (5 + DEPRECATION_NOTICE)
- `docs/improvements/` (6)
- `docs/analysis/` (9)
- `docs/implementation/` (2)
- `docs/migration/` (2)
- `docs/summary/` (3)
- `docs/integration/` (3)

**`docs/archive/legacy-upstream/`**（上游遗产，与 fork 路径冲突）：
- `docs/deployment/` (14，Docker / embedded python / portable)
- `docs/development/` (15，上游分支策略 / DEVELOPMENT_SETUP)
- `docs/community/`、`docs/survey/`、`docs/agents/`（上游营销 / 调研产物，fork 用不到）
- 根目录散落的上游 narrative：`DOCKER_REGISTRY_STRATEGY.md` / `BUILD_GUIDE.md` / `QUICK_BUILD_REFERENCE.md` / `SETTINGS_MERGE.md` / `SILICONFLOW_SETUP_GUIDE.md` / `MODEL_RECOMMENDATION_UI_UPDATE.md` / `CONFIG_VALIDATION_FIX_SUMMARY.md` / `ENHANCED_HISTORY_FEATURES_SUMMARY.md` / `GITHUB_BRANCH_PROTECTION.md` 等

**注**：`docs/architecture/` 和 `docs/design/` **不在本 change 范围**——这两个目录被 `openspec/specs/repository-scope/spec.md` Req「文档范围」列为「具体保留」（功能性技术参考），且 `CLAUDE.md` 列为「完全不动」。即便部分内容已被 OpenSpec spec 替代，本 change 也不动它们；后续可单独开 change 走 `repository-scope` spec MODIFY 流程评估。

**`docs/archive/` 顶层现有 5 个 flat 文件**（`AUTHENTICATION_FIX_SUMMARY.md` / `BACKEND_STARTUP.md` / `FIXES_SUMMARY.md` / `README-ORIGINAL.md` / `SOLUTION_SUMMARY.md`，2026-05-05 由 `refactor: 整理项目根目录结构` 引入）：本 change 把它们 mv 到 `docs/archive/dev-history/` 子目录下（属 fork 自己的 fix summary 性质），并在 `docs/archive/README.md` 顶层写一份导览。

每个 archive 子目录写一行 README：**「冻结于 fork v1.3.0，未来不更新；功能事实见 `openspec/specs/`，narrative 见 `docs/ai-context/`」**。

### 改动 3：fork 视角参考文档刷新

- `docs/ai-context/architecture.md`：新增「v1.3.0 已固化 capability 列表」小节，22 条逐项链接 `openspec/specs/<id>/spec.md`，让本文件变成 architecture → capability 索引。
- `docs/ai-context/project-structure.md`：归档完成后同步更新顶层 docs/ 目录清单（删 ~15 个已 mv 的目录引用）。
- `docs/USAGE.md`：顶部加 SSOT 指针；补**功能使用矩阵**（Dashboard / Watchlist / Paper Account / Daily Recommendation / 各分析师），每行链 capability spec + 用户操作要点。
- **新建** `docs/operations.md`：备份 / 数据迁移 / 日志位置 / 端口段位 / 原生服务管理——从 `docs/maintenance/` + `docs/data-audit-2026-05-17.md` 提炼可复用部分。
- **重写** `docs/QUICK_START.md` 为 fork 版本：原生服务 + `just up` 一条龙；删 Docker / embedded python 路径；现 fork 视角 QUICK_START 不存在，用户被迫读 USAGE.md。

### 改动 4：CLAUDE.md / 规则层小幅更新

- 项目 CLAUDE.md「AI 上下文入口」段增一句：**"功能事实以 `openspec/specs/` 为准，docs/ai-context 只描述跨 capability 的横切关系；docs/ 其它目录默认为参考资料或归档"**。
- 同段调整 prime 优先级链路，把 `docs/README.md`（fork 视角入口）放第 1 位。
- 不动 fork-patch 清单（本 change 只新增 fork-local 文件 + 移动现有 docs，不触碰 pyproject.toml / vite.config.ts 等 patched 段）。

### 改动 5：新 capability `documentation-structure`

锁定四件事：
1. **角色化入口必须存在**（user / operator / developer / AI prime 四个 entrypoint，不可缺）
2. **功能事实 SSOT 唯一性**——`openspec/specs/` 是功能事实唯一来源，docs/ 不再声称是 SSOT
3. **archive 目录冻结约定**——挪入 `docs/archive/` 的内容不再维护，需在子目录 README 明确冻结版本
4. **release 时的文档维护节奏**——每次 release 必须同步更新 `docs/CHANGELOG.md` + `docs/ai-context/architecture.md` capability 列表 + `docs/USAGE.md` 功能矩阵

## Capabilities

- **新建** `documentation-structure`（独立锁定文档分层 + 角色化入口 + archive 约定 + 维护节奏）

## Impact

**改动文件**：
- 顶层新增 / 重写 4 个文件：`docs/README.md`（新建/覆盖）、`docs/operations.md`（新建）、`docs/QUICK_START.md`（重写覆盖上游）、`docs/archive/{dev-history,legacy-upstream}/README.md`（各 1）
- 更新 4 个 fork 自维护文件：`docs/USAGE.md`、`docs/ai-context/architecture.md`、`docs/ai-context/project-structure.md`、`CLAUDE.md`
- `git mv` ~150 个 .md 文件到 archive 子目录（按目录粒度分 sub-task，每个目录一次 commit）
- 1 个新 spec 文件：`specs/documentation-structure/spec.md`
- 1 个 CHANGELOG entry

**零触碰**：
- `app/` / `frontend/`（专有授权代码）
- `tradingagents/` 主代码
- `pyproject.toml` / `vite.config.ts` / `.pre-commit-config.yaml` / `.github/workflows/ci.yml` / `.gitignore`（fork-patch 段全部不动）
- `openspec/specs/` 已有 22 个 spec（本 change 仅新增 `documentation-structure`，不修改既有）
- `tests/` / CI / hook 配置

**视觉变化**：
- `docs/` 顶层 + 一级子目录文件数从 ~220 降到 ~30-40
- 新 contributor 进入项目第一眼看到的是 `docs/README.md` 的四节入口
- AI prime 链路缩短：`CLAUDE.md` → `docs/README.md` → 对应角色入口 → 真实文件

**API breaking change**：无（纯文档结构）

**风险**：低
- 所有挪动都是 `git mv`，git 历史完整保留
- 任何被 mv 的文档都可以从 git log 找回；archive 目录仍在仓库内，只是移位
- 未来上游 cherry-pick 可能撞到 archive 路径下的文件——cherry-pick 时按需处理（OPTIONAL，文档冲突一般合并双方即可，且 fork 已声明不再批量 sync upstream，频率极低）
- pre-commit hook 不扫 `.md`、pytest 不依赖 `docs/`，归档动作不会挂 hook
- 顶层 `docs/README.md` 覆盖上游版本——已属"fork patch 清单"扩展，需在 CLAUDE.md fork patch 清单段记录

**收益**：
- AI prime context 噪声降低 80%（按文件数估算）
- 角色化入口让 onboarding 路径明确
- 功能事实 SSOT 唯一性彻底落地（`openspec/specs/` 单一来源）
- 维护节奏写进规则，release 时不易遗漏文档同步
- 后续 v1.4+ 新功能只需更新「architecture.md capability 列表 + USAGE 功能矩阵 + openspec spec」三处，不再撒文档到处
