## Purpose

锁定 fork 进入功能固化阶段后的文档分层规则：

1. **角色化入口必须存在**——`docs/README.md` 提供用户 / 二开 / 运维 / AI prime 四角色入口，覆盖上游版本。
2. **功能事实 SSOT 唯一性**——`openspec/specs/` 是项目功能事实唯一来源，`docs/` 不再声称是功能 SSOT。
3. **archive 目录冻结约定**——挪入 `docs/archive/` 的内容停止维护，需在子目录 README 明示冻结版本 + 日期。
4. **文档维护节奏内嵌 release 流程**——每次 release 必须同步更新 CHANGELOG / architecture / USAGE / known-issues（按需），并通过 OpenSpec change tasks.md 的 archive phase checkbox 强制 surface。

## ADDED Requirements

### Requirement: 角色化入口必须存在

`docs/README.md` MUST 是 fork 视角的文档入口（覆盖上游版本），并 MUST 提供**四个角色入口**：

1. **用户入口**：链接到 `docs/USAGE.md` + 功能矩阵 + `openspec/specs/` 功能总览
2. **二开入口**：链接到 `docs/ai-context/` + `openspec/specs/` + `CLAUDE.md` + `docs/code-review-2026-05-05.md`
3. **运维入口**：链接到 `docs/operations.md`（端口段位 / 备份 / 数据迁移 / 日志位置 / 原生服务）
4. **AI prime 入口**：链接到 `CLAUDE.md` → `docs/ai-context/project-structure.md` → `docs/ai-context/architecture.md` → `docs/ai-context/known-issues.md`

`docs/README.md` MUST 在头部明确声明：**「功能事实以 `openspec/specs/` 为准；docs/ai-context/ 描述跨 capability 的横切关系；docs/ 其它目录默认为参考资料或归档」**。

理由：subagent-driven 模式下入口模糊 → 每个 subagent 自己摸路径 → 重复试错 + 撞上游遗产。四角色明确分流后 prime 路径单一。

#### Scenario: 新 contributor 打开 docs/README.md

- **WHEN** 新 contributor 第一次打开 `docs/README.md`
- **THEN** 在前 50 行内看到 4 个角色入口（用户 / 二开 / 运维 / AI prime）
- **AND** 每节给出 3-5 条 markdown 链接，全部指向**已存在**的真实文件
- **AND** 明确告知功能事实在 `openspec/specs/`，不在 `docs/architecture/` 或 `docs/design/`

#### Scenario: AI 助手按 CLAUDE.md 指引 prime

- **WHEN** AI 助手按 `CLAUDE.md` 中的「AI 上下文入口」段加载文档
- **THEN** 优先级第 1 位是 `docs/README.md`（fork 视角入口）
- **AND** 顺序读到 `ai-context/project-structure.md` → `coding-standards.md` → `architecture.md` → `known-issues.md`
- **AND** 不会被 `docs/` 顶层散落的上游 narrative（`BUILD_GUIDE.md` / `DOCKER_REGISTRY_STRATEGY.md` 等）干扰——这些已 mv 到 `archive/legacy-upstream/`

### Requirement: 功能事实 SSOT 唯一性

**`openspec/specs/` MUST 是项目功能事实的唯一来源（SSOT）**。

- `docs/` 下任何目录 MUST NOT 声称是"功能规格""设计 SSOT""架构事实"——只能作为**叙述层 / narrative**（解释跨 capability 关系、提供上下文、记录历史）
- `docs/ai-context/architecture.md` MUST 包含「v1.3.x 已固化 capability 列表」小节，每条 capability 链接到对应 `openspec/specs/<id>/spec.md`，本文件定位为 **architecture → capability 索引**而非独立的功能描述源
- `docs/USAGE.md` 功能矩阵 MUST 在每行末尾给出对应 capability spec 链接
- 历史的 `docs/architecture/` / `docs/design/` 中与 capability 重叠的内容 MUST 标注「内容已被 `openspec/specs/<id>` 替代」或挪到 `archive/legacy-upstream/`

理由：v1.3.0 之前功能事实散布在 `docs/design/`、`docs/architecture/`、`docs/improvements/`、`docs/changes/` 多处，互相漂移；OpenSpec 38 个 archived changes 已经把事实集中沉淀，必须明确单一 SSOT。

#### Scenario: 找 watchlist 限量 10 支的权威说明

- **WHEN** AI 或开发者想确认"watchlist 数量上限是 10 支"是否仍然成立
- **THEN** 查 `openspec/specs/watchlist-management/spec.md`，找到 Requirement「Watchlist 数量上限 10 支」 + Scenario
- **AND** 不需要查 `docs/changes/` 或 `docs/design/` 寻找设计源

#### Scenario: docs/ai-context/architecture.md 含 capability 索引

- **WHEN** 打开 `docs/ai-context/architecture.md`
- **THEN** 含一节「v1.3.x capability 一览」
- **AND** 列出当前 `openspec/specs/` 下所有 capability，每条一行 + 链接到 spec.md
- **AND** 索引外的内容只描述跨 capability 横切关系（多智能体编排 / 三层架构 / 数据流），不重复描述单一 capability 的规则

#### Scenario: 新增 capability 后文档同步

- **WHEN** 项目新增 capability X（通过 OpenSpec change archive）
- **THEN** 同一次 release 必须在 `docs/ai-context/architecture.md` capability 列表加一行链接
- **AND** 若 X 是用户可见功能，必须在 `docs/USAGE.md` 功能矩阵加一行
- **AND** `docs/CHANGELOG.md` 对应 release entry 提到 capability X

### Requirement: archive 目录冻结约定

`docs/archive/` 子目录用于隔离**不再维护**的文档：

- **`docs/archive/dev-history/`**：fork 自己的开发过程产物（一次性 bugfix 记录、tech review、设计探索、过程分析、已完成的实施计划）
- **`docs/archive/legacy-upstream/`**：上游遗产，与 fork 当前路径冲突（Docker / embedded python / portable / 上游分支策略 / 上游营销文档）

每个 archive 子目录 MUST 在根目录有一份 `README.md`，明确：
1. 冻结版本（"冻结于 fork v1.3.x"）
2. 冻结日期
3. 不再更新的声明
4. 指向当前真实事实的链接（`openspec/specs/` + `docs/ai-context/`）

挪入 archive 的内容 MUST 通过 `git mv` 保留 git 历史，不允许 `rm` + `add` 丢失 blame。

理由：仓库内保留历史而非删除有两方面收益——git blame 可追溯 + 未来上游 cherry-pick 撞冲突时还能找到对应文件位置；但必须明示"已冻结"避免读者误以为是当前事实。

#### Scenario: 打开 archive 子目录

- **WHEN** 打开 `docs/archive/dev-history/` 或 `docs/archive/legacy-upstream/`
- **THEN** 第一眼看到 `README.md`
- **AND** README 头部 5 行内明确"冻结版本 + 冻结日期 + 不再更新"
- **AND** 给出 1-2 条链接指向当前 SSOT

#### Scenario: git blame 仍可追溯

- **WHEN** 对 `docs/archive/dev-history/bugfix/2025-10-26-ps-calculation-fix.md` 执行 `git log --follow`
- **THEN** 完整历史可见，含原路径 `docs/bugfix/2025-10-26-ps-calculation-fix.md` 的所有 commit
- **AND** archive 操作的 commit message 明确说明"docs(archive): freeze dev-history under archive/"

#### Scenario: archive 内容被误当作当前事实

- **WHEN** AI 或开发者引用 `docs/archive/legacy-upstream/deployment/EMBEDDED_PYTHON_GUIDE.md` 作为部署建议来源
- **THEN** 因 README 已声明冻结 + 指向 `openspec/specs/native-local-deployment/`，错误引用应被自我纠正
- **AND** 后续提示 / review 应指出"该文档已冻结，参见 native-local-deployment spec"

### Requirement: 文档维护节奏内嵌 release 流程

每次 fork release（minor / patch）MUST 同步更新以下 4 处文档：

1. `docs/CHANGELOG.md`：新版本 entry（Added / Changed / Fixed / Removed 分段）
2. `docs/ai-context/architecture.md`：若本 release 新增 capability，更新 capability 索引列表
3. `docs/USAGE.md`：若本 release 新增用户可见功能，更新功能矩阵
4. `docs/ai-context/known-issues.md`：若本 release 暴露 / 修复已知问题，对应增删

OpenSpec change archive 流程 MUST 在 task list 中包含「同步上述 4 处文档」的检查项，archive 前必须勾选完成。

`CLAUDE.md` 项目级文件 MUST 在 release/finishing 段反映此约定。

理由：固化阶段最容易踩的坑是"代码改了 spec 改了，docs 忘了同步"——把同步检查内嵌到 OpenSpec archive 流程里强制 surface。

#### Scenario: 新功能 release 时 architecture.md 同步

- **WHEN** 完成一个新功能的 OpenSpec change apply（spec 已 mv 到 `openspec/specs/`）
- **AND** 准备 release v1.X.Y
- **THEN** release commit 前 `docs/ai-context/architecture.md` 的 capability 列表已加新条目并链接到对应 spec
- **AND** `docs/USAGE.md` 功能矩阵已对应更新（若是用户可见功能）
- **AND** `docs/CHANGELOG.md` 对应 release entry 已写

#### Scenario: tasks.md 含文档同步检查

- **WHEN** 阅读 `2026-05-21-docs-stabilization-v1` 之后创建的任意 OpenSpec change 的 `tasks.md`
- **THEN** archive phase（最后一个 phase）含「同步 architecture.md / USAGE.md / CHANGELOG.md / known-issues.md（按需）」的 checkbox
- **AND** 没勾选完毕不能 mv spec → archive
- **AND** 本 Requirement 不追溯到本 change 之前已 archived 的 38 个 change

#### Scenario: 仅 bugfix 不动 capability 时

- **WHEN** 本次 release 只是 bugfix，没新 capability、没用户可见功能变化
- **THEN** 至少 `docs/CHANGELOG.md` 必须有 entry
- **AND** architecture.md / USAGE.md 不需更新（在 task 中显式标注"无需更新"而非沉默跳过）
