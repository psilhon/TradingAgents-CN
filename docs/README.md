# TradingAgents-CN 文档中心 (fork v1.3.0)

> **fork 视角文档入口**——本文件由 `psilhon/TradingAgents-CN` 维护，覆盖上游版本。
> 上游原版 README 备份见 [`archive/legacy-upstream/README-ORIGINAL.md`](archive/legacy-upstream/README-ORIGINAL.md)。

## SSOT 声明

- **功能事实** = [`openspec/specs/`](../openspec/specs/) — 22 个 stable capability spec，项目功能事实的**唯一来源**
- **跨 capability 横切关系** = [`ai-context/`](ai-context/) — architecture / project-structure / coding-standards / known-issues
- **本目录其它内容** = 参考资料 / 归档；本目录下任何文档若与 `openspec/specs/` 冲突，**以 spec 为准**

## 四角色入口

### 👤 用户（想用这个工具分析股票）

- [`USAGE.md`](USAGE.md) — fork 维护者 / 二开者使用手册（区别于上游 README）
- [`QUICK_START.md`](QUICK_START.md) — 5 分钟跑通：原生服务 + `just up` 一条龙
- [`openspec/specs/`](../openspec/specs/) — 完整功能事实，按 capability 浏览（watchlist / paper-account / daily-recommendation / 等）
- [`CHANGELOG.md`](CHANGELOG.md) — fork 自身版本变更历史（不含上游 commits）
- [`faq/`](faq/) — 常见问题

### 🛠 二开者（想读懂代码 / 加功能）

- [`ai-context/project-structure.md`](ai-context/project-structure.md) — 顶层目录 + 入口文件清单
- [`ai-context/architecture.md`](ai-context/architecture.md) — 三层架构 + 多智能体编排 + 数据源链 + LLM 抽象 + capability 索引
- [`ai-context/coding-standards.md`](ai-context/coding-standards.md) — fork 特有 lint/typecheck/排除约定 + 二开原则
- [`ai-context/known-issues.md`](ai-context/known-issues.md) — fork 撞过的坑 + 上游遗留
- [`code-review-2026-05-05.md`](code-review-2026-05-05.md) — 大型架构 review 待办（cache 层 / 反向 import / agent state / company resolver）
- [`data-audit-2026-05-17.md`](data-audit-2026-05-17.md) — 2026-05 数据正确性审计 + Phase 3 防复发计划
- [`openspec/specs/`](../openspec/specs/) — 22 个 capability spec（每条独立、可单读）
- [项目根 `CLAUDE.md`](../CLAUDE.md) — fork 项目级 AI 助手规则（端口段位 / fork-patch 清单 / 命令速查 / 永恒约定）

### ⚙️ 运维者（部署 / 备份 / 故障排查）

- [`operations.md`](operations.md) — 端口段位 / 原生服务管理 / 备份恢复 / 日志位置（fork 一站式运维手册）
- [`troubleshooting/`](troubleshooting/) — 故障排查清单
- [`maintenance/`](maintenance/) — mongodb 索引优化 / cherry-pick 流程
- [`guides/DATABASE_BACKUP_RESTORE.md`](guides/DATABASE_BACKUP_RESTORE.md) — 数据库备份与恢复
- [`security/`](security/) — secret / API key 处理规范

### 🤖 AI 助手 prime context（启动新会话）

按以下优先级加载：

1. [项目根 `CLAUDE.md`](../CLAUDE.md) — 必读
2. [`README.md`](README.md)（本文件） — 入口与 SSOT 边界
3. [`ai-context/project-structure.md`](ai-context/project-structure.md)
4. [`ai-context/coding-standards.md`](ai-context/coding-standards.md)
5. [`ai-context/architecture.md`](ai-context/architecture.md)
6. [`USAGE.md`](USAGE.md) — 用户视角验证
7. [`CHANGELOG.md`](CHANGELOG.md) — fork 自身改动历史
8. [`ai-context/known-issues.md`](ai-context/known-issues.md) — 按需查
9. [`openspec/specs/`](../openspec/specs/) — 按 capability 按需查

## 保留参考目录

仍持续维护、可作为参考资料（**非 SSOT**）：

| 目录 | 用途 |
|---|---|
| [`configuration/`](configuration/) | 各 LLM 厂家配置 / API key 优先级 / 缓存配置 / 代理配置 |
| [`llm/`](llm/) | LLM 集成指南 / 模型目录 / 模型筛选 / pricing |
| [`data/`](data/) | 数据源接入说明（caching / data-processing / tushare / tongdaxin） |
| [`guides/`](guides/) | 各类指南（installation / 各市场分析 / scheduled tasks / websocket / pdf export 等） |
| [`api/`](api/) | API 限制说明 |
| [`architecture/`](architecture/) | 架构技术参考（functional 内容，OpenSpec spec 化后逐步沉淀） |
| [`design/`](design/) | 设计文档（功能性技术参考） |
| [`frontend/`](frontend/) | 前端组件 / dashboard 布局 / 多源同步说明 |
| [`features/`](features/) | 新闻分析 / 工具调用等功能说明 |
| [`overview/`](overview/) | 项目总览 / 安装 / 快速入门 |
| [`technical/`](technical/) | LLM 厂家适配技术报告 |
| [`technical-debt/`](technical-debt/) | 技术债务清单 |
| [`localization/`](localization/) | 中文社媒数据集成 |
| [`security/`](security/) | secret / 鉴权改进 |
| [`troubleshooting/`](troubleshooting/) | 故障排查 |
| [`maintenance/`](maintenance/) | 维护手册（mongodb / cherry-pick） |
| [`examples/`](examples/) | 用法示例 |
| [`usage/`](usage/) | 投资分析指南 / web UI 详细指南 |
| [`faq/`](faq/) | 常见问题 |
| [`config/`](config/) | 错误日志分离 / 配置架构 |
| [`images/`](images/) | 文档插图 |
| [`superpowers/`](superpowers/) | superpowers skill 输出物（plans / specs） |

## 归档区

| 目录 | 内容 |
|---|---|
| [`archive/dev-history/`](archive/dev-history/README.md) | fork 自己的开发过程产物（bugfix / fixes / tech_reviews / changes / improvements / analysis / implementation / migration / summary / integration）—— **冻结于 v1.3.x** |
| [`archive/legacy-upstream/`](archive/legacy-upstream/README.md) | 上游遗产（deployment / development / community / survey / agents + 根目录散落的上游 narrative）—— **冻结于 v1.3.x** |

## 永远从哪里开始

不知道从哪儿读？答案永远是这两个：

1. [项目根 `CLAUDE.md`](../CLAUDE.md)
2. 本文件四角色入口
