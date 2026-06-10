# architecture.md

> AI prime context — 架构摘要 + 二开关注点。
> **本文件描述跨 capability 的横切关系**；单一 capability 的功能事实 SSOT 见 [`docs/specs/`](../specs/)（2026-05-23 起新事实）→ 回退 [`openspec/specs/`](../../openspec/specs/)（2026-05-23 前冻结档案；下文「capability 索引」的 23 条仍在此）。
> 详细补充见 [`../architecture/`](../architecture/) 技术参考目录。

## 三层 + 数据存储 + LLM 抽象

```
┌─────────────────────────────────────────────────────────────┐
│  frontend/  (Vue 3 + Vite + Element Plus)        :54300     │  专有
│  └─ HTTP REST + WebSocket → backend                         │
├─────────────────────────────────────────────────────────────┤
│  app/  (FastAPI + Uvicorn)                       :54301     │  专有
│  ├─ routers/      HTTP API                                  │
│  ├─ services/     业务逻辑                                  │
│  ├─ schemas/      Pydantic 模型                             │
│  ├─ middleware/   认证 / CORS / 日志                        │
│  └─ worker/       apscheduler 定时任务                      │
│             ↓ 调用                                          │
├─────────────────────────────────────────────────────────────┤
│  tradingagents/  (LangGraph 多智能体核心)        Apache 2.0 │  ⭐
│  ├─ graph/trading_graph.py    多智能体编排入口              │
│  ├─ agents/                   分析师 / 研究员 / 交易员 / 风控│
│  ├─ dataflows/                数据源适配层                  │
│  └─ llm/                      LLM provider 适配层           │
│             ↓ 读                                            │
├─────────────────────────────────────────────────────────────┤
│  数据 / 缓存                                                │
│  ├─ MongoDB 7.0   股票数据 / 用户 / analysis 结果  :54302   │
│  └─ Redis 8       缓存 / 会话 / SSE 通知            :54303   │
└─────────────────────────────────────────────────────────────┘
```

## 多智能体编排（`tradingagents/graph/trading_graph.py`）

LangGraph 状态机驱动多个专业 agent 协同分析：

```
analyst  →  researcher  →  trader  →  risk_manager
   ↑__________(辩论 / debate rounds)__________|
```

- 每个 agent 有独立 prompt + 工具集
- 状态在 graph 节点间传递
- 支持 `max_debate_rounds` 控制深度

## 数据源链（多级降级）

```python
# 以 akshare A 股实时行情为例：
stock_bid_ask_em
  ↓ fail
stock_zh_a_spot
  ↓ fail
stock_zh_a_spot_em
  ↓ fail
stock_zh_a_hist
```

- 任何一级失败自动降级到下一级
- 同步状态会落库到 `market_quotes` 表
- 详见 `tradingagents/dataflows/`

## 实时数据流 SLO 模型（OpenSpec `realtime-trading-data-flow`）

金融工程视角：交易系统的"实时"由 **后台定频 sync + push 推送** 维护，**hot-path 永远不在用户请求路径同步触发外部行情拉取**（akshare p99 110s，不可控）。

### 双 hot snapshot 路径

| 数据类 | 存储 | 写入 | 读取 |
|---|---|---|---|
| 持仓 / 自选股近实时价（< 100 codes） | mongo `market_quotes` | `realtime_quote_sync_service` 30s sync（既有 `paper-realtime-quotes`） | `quote_snapshot_reader.read_quotes()` |
| 全市场聚合（5500+ 只涨跌停 / 成交额） | in-memory `QuotesService._cache` | `market_overview_prewarm_service` 盘中 30s prewarm | `market_overview_prewarm_service.compute_overview()` |

> 为什么分两路：`paper-realtime-quotes` capability 锁定 `market_quotes` 写入范围 ≤ 100 codes（防止 5500 行整库写压），全市场聚合不能从 mongo 来——必须用 in-memory 路径，由 prewarm 服务维护时效。

### Push 推送链路

```
┌─────────────────────┐    upsert mongo + redis publish     ┌─────────────────┐
│ realtime_quote_sync │ ───────────────────────────────────► │ redis pubsub    │
│   (30s scheduled)   │  channel:quote:{code}                │  fan-out         │
└─────────────────────┘                                       └────────┬────────┘
                                                                       │
┌─────────────────────┐    publish channel:pnl:{user_id}              │
│ pnl_stream_service  │ ───────────────────────────────────────────────►
│   (3s loop)         │  diff > 0.01 才 publish                       │
└─────────┬───────────┘                                                ▼
          │ compute_pnl                                       ┌─────────────────┐
          ▼                                                   │ /ws/quotes WS   │
   mongo paper_positions                                      │ (per connection │
   + quote_snapshot_reader                                    │  pubsub task)   │
                                                              └─────────┬───────┘
                                                                        │
                                                              {"type":"quote"|"pnl"}
                                                                        ▼
                                                                   前端 UI
```

### SLO 表

| 数据类 | SLO（pX） | 当前实现 | 监控 |
|---|---|---|---|
| 持仓 last price | < 1s 推送 / < 30s 入库 | mongo 30s sync + redis publish + ws push | `/api/market/freshness` `breach` |
| 实时 PnL | < 3s 推送 | `pnl_stream_service` 3s loop + redis publish | (同上) |
| 自选股最新价 | < 1s 推送 | 同持仓 | (同上) |
| 大盘涨跌停 / 成交额 | < 30s | in-memory prewarm 30s + hot-path ≤ 50ms 读 cache | `/api/market/freshness` |
| 数据时效透出 | 必须 | 所有 hot-path 响应带 `as_of_ts` + `staleness_seconds` | (前端角标) |

### Hot-path 路径约束（capability spec 强制）

- `app/routers/**/*.py` MUST NOT import 或同步调 `akshare` / `tushare` / `baostock`
- `_fetch_spot_akshare` / `ak.stock_zh_a_spot_em` 调用栈 MUST 仅出现在 service / worker / scheduler / prewarm 路径
- 所有持仓 / 行情响应顶层 MUST 含 `as_of_ts: str | null` + `staleness_seconds: float | null`
- WebSocket `/ws/quotes` `subscribe_pnl` MUST 强制 `user_id = token_data.sub`，不允许 client 指定别人的

### Lifecycle background tasks（在 `app/main.py` lifespan）

| Task | Interval | 数据流 | 盘外行为 |
|---|---|---|---|
| `market_overview_prewarm_service.prewarm_loop` | 30s | 调 `QuotesService._ensure_cache()` 让 in-memory cache 永远 fresh | sleep（不调 akshare） |
| `pnl_stream_service.pnl_stream_loop` | 3s | 扫所有 active CN positions，diff > 0.01 才 redis publish | sleep（不查 db） |
| `quote_freshness_monitor.monitor_loop` | 60s | mongo `market_quotes.updated_at` max 检查；盘中超 SLA 写 `system_logs` | 不写 logs（盘外 stale 是预期） |

### 失败模式 + degrade

| 失败 | 表现 | Degrade |
|---|---|---|
| akshare 慢 / 超时 | prewarm 当轮超时 wait_for + warning | hot-path 仍读上轮 cache（可能 stale，UI 角标变红警告） |
| redis 宕 | publish 失败 throttle warning | sync mongo upsert 仍成功；ws 拒连或心跳超时；前端 fallback 30s polling |
| mongo `market_quotes` 空 | `as_of_ts=null / staleness=null` | UI 显示"等待数据"；breach=False（避免空库 spam） |
| trading-calendar 异常 | 保守判 not intraday | prewarm/pnl/monitor loop sleep；不刷新 |

## LLM provider 抽象

| Provider | 库 | env key |
|---|---|---|
| OpenAI | `langchain-openai` | `OPENAI_API_KEY` |
| Anthropic | `langchain-anthropic` | `ANTHROPIC_API_KEY` |
| Google AI | `langchain-google-genai` | `GOOGLE_API_KEY` |
| 阿里通义 | `dashscope` | `DASHSCOPE_API_KEY` |
| DeepSeek | OpenAI 兼容 | `DEEPSEEK_API_KEY` + `DEEPSEEK_BASE_URL` |
| 聚合渠道 | OpenAI 兼容 | `AIHUBMIX_API_KEY`、`ONEAPI_API_KEY`、`SILICONFLOW_API_KEY` 等 |

加新 provider：抄 [`archive/legacy-upstream/LLM_ADAPTER_TEMPLATE.py`](../archive/legacy-upstream/LLM_ADAPTER_TEMPLATE.py)（模板已冻结到 archive，但内容仍可参考），落到 `tradingagents/llm/<provider>/`。详细规则见 [`openspec/specs/llm-abstraction/spec.md`](../../openspec/specs/llm-abstraction/spec.md)。

## 配置中心（前端可视化）

`app/services/` 实现配置中心 API；前端 `frontend/src/views/config/` 展示。运行时切换 LLM / 数据源 provider，无需重启。

## 二开关注点

| 想做什么 | 改哪里 | 风险 |
|---|---|---|
| 改 agent 行为 / 加新 agent | `tradingagents/agents/` | 🟢 |
| 加新数据源 | `tradingagents/dataflows/` + `tradingagents/llm/`（如需）| 🟢 |
| 加新 LLM provider | `tradingagents/llm/<name>/` + `langchain-*` 依赖 | 🟢 加依赖要更新 pyproject |
| 改 graph 编排顺序 / 新加节点 | `tradingagents/graph/trading_graph.py` | 🟡 影响所有 analysis 流程 |
| 改后端 API 契约 | `app/routers/` `app/schemas/` | 🟡 专有授权 + 上游同步冲突高 |
| 改前端 UI | `frontend/src/` | 🟡 专有授权 + Vue/JS 知识 |
| 改 DB schema | MongoDB（无 migrations，直接 collection 改）| 🔴 数据迁移自己负责 |

## v1.3.x 已固化 capability 索引

> **本节是 architecture.md 到 [`openspec/specs/`](../../openspec/specs/)（2026-05-23 前冻结档案）的索引**——单一 capability 的 Requirements / Scenarios 见各 `spec.md`，本表只给一句话定位。

| Capability | 一句话定位 | Spec |
|---|---|---|
| `audit-tooling` | 审计脚本（数据真实性 / 端口绑定 / 数据一致性）固化为 `just audit-*` 同源命令 | [spec](../../openspec/specs/audit-tooling/spec.md) |
| `daily-recommendation` | 每日推荐多配置目录化（`config/daily_recommendations/<id>.json`），支持多策略并行 | [spec](../../openspec/specs/daily-recommendation/spec.md) |
| `data-quality-gate` | mock 数据 / `Math.random` / 同步 fallback 禁止入库，写入路径必须经数据真实性闸门 | [spec](../../openspec/specs/data-quality-gate/spec.md) |
| `dataflow-integrity` | dataflow 模块禁反向依赖、禁同步阻塞、禁 hot-path import akshare | [spec](../../openspec/specs/dataflow-integrity/spec.md) |
| `dataflow-performance` | dataflow 性能 SLA（缓存命中 / 单次 sync 耗时上限） | [spec](../../openspec/specs/dataflow-performance/spec.md) |
| `favorites-performance` | 自选股 panel 性能（批量获取 / 防过频刷新） | [spec](../../openspec/specs/favorites-performance/spec.md) |
| `frontend-navigation` | 前端路由 + 导航栏 + 顶部菜单约束（Element Plus menu / Vue Router 4） | [spec](../../openspec/specs/frontend-navigation/spec.md) |
| `license-boundary` | `app/` / `frontend/` 专有授权代码改动边界（个人学习可读可改，商业部署需授权） | [spec](../../openspec/specs/license-boundary/spec.md) |
| `lint-policy` | pre-commit STRICT 模式（ruff/format/pyright 阻塞 + pytest -m unit pre-push 阻塞） | [spec](../../openspec/specs/lint-policy/spec.md) |
| `llm-abstraction` | LLM provider 统一抽象（langchain-* + dashscope + OpenAI 兼容渠道） | [spec](../../openspec/specs/llm-abstraction/spec.md) |
| `loopback-binding-policy` | 所有对外服务强制 `127.0.0.1` loopback；禁止 `0.0.0.0` 监听 | [spec](../../openspec/specs/loopback-binding-policy/spec.md) |
| `native-local-deployment` | 原生 Homebrew mongo + redis 部署（不用 Docker）；端口段位 54300-54309 | [spec](../../openspec/specs/native-local-deployment/spec.md) |
| `paper-account-snapshots` | 模拟账户日切快照（每日凌晨写 KPI / 收益曲线） | [spec](../../openspec/specs/paper-account-snapshots/spec.md) |
| `paper-realtime-quotes` | 持仓 / 自选股近实时价（mongo `market_quotes` ≤ 100 codes，30s sync） | [spec](../../openspec/specs/paper-realtime-quotes/spec.md) |
| `portfolio-fundamentals` | 组合 / 持仓基本面字段（PE / PB / market cap / industry） | [spec](../../openspec/specs/portfolio-fundamentals/spec.md) |
| `realtime-trading-data-flow` | 实时数据流 SLO 模型 + push 推送链路（双 hot snapshot + redis pubsub + WS） | [spec](../../openspec/specs/realtime-trading-data-flow/spec.md) |
| `repository-scope` | fork 独立分叉模式 / 仅 macOS Apple Silicon 支持 / 文档保留范围 | [spec](../../openspec/specs/repository-scope/spec.md) |
| `secret-handling` | secret / API key 处理约束（不打印不上传 / `.env` gitignored / Claude 不读不写） | [spec](../../openspec/specs/secret-handling/spec.md) |
| `theme-management` | 前端主题切换（亮/暗模式 / 全局变量） | [spec](../../openspec/specs/theme-management/spec.md) |
| `trading-calendar` | 交易日历（A 股 / 港股 / 美股；判断 intraday / 节假日） | [spec](../../openspec/specs/trading-calendar/spec.md) |
| `user-workflow-stability` | 用户核心流程稳定性约束（注册 → 登录 → Dashboard → 分析 → 报告路径不可中断） | [spec](../../openspec/specs/user-workflow-stability/spec.md) |
| `watchlist-management` | 自选股管理（上限 10 支 / 滚动 / 排序模式 / 拖拽自定义顺序持久化） | [spec](../../openspec/specs/watchlist-management/spec.md) |
| `documentation-structure` | 文档分层（角色化入口 / SSOT 唯一性 / archive 冻结 / release 维护节奏） | [spec](../../openspec/specs/documentation-structure/spec.md) |

> 新增 capability 时，本表必须同步加一行——见 `documentation-structure` Req 4「文档维护节奏内嵌 release 流程」。

## 上游同步关注点（fork 独立分叉模式）

fork 已声明**独立分叉**（参见 [`repository-scope` spec](../../openspec/specs/repository-scope/spec.md)），不再批量 `git pull upstream/main`。需要上游某项功能 / 修复时手动 cherry-pick 单独决策引入。

罕用 cherry-pick 操作见 [`../operations.md` § 上游 cherry-pick](../operations.md#上游-cherry-pick-罕用)。如果撞冲突涉及 fork-patch 文件（vite.config.ts / pyproject.toml / .pre-commit-config.yaml / ci.yml / .gitignore），参考项目 `CLAUDE.md` § Fork patch 清单。
