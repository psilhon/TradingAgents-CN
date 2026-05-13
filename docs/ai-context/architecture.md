# architecture.md

> AI prime context — 架构摘要 + 二开关注点。详细见上游 `docs/STRUCTURE.md` + `docs/architecture/`。

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
│  ├─ MongoDB 4.4   股票数据 / 用户 / analysis 结果  :54302   │
│  └─ Redis 7       缓存 / 会话 / SSE 通知            :54303   │
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

加新 provider：抄 `docs/LLM_ADAPTER_TEMPLATE.py`，落到 `tradingagents/llm/<provider>/`。

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

## 上游同步关注点（fork 维护）

| 文件类型 | 同步策略 |
|---|---|
| `tradingagents/` | 通常无冲突（你不会跟上游同时改同函数）|
| `app/` `frontend/` | **大概率冲突**（上游主开发区），优先 rebase 而非 merge |
| `pyproject.toml` | 注意 [tool.*] 段（fork 加的）vs 依赖列表（上游改的）|
| `config/mongod.conf` `config/redis.conf` | fork 加，不会冲突；改端口需同步 `.env` 和业务代码 |
| `docs/` | 上游加新文档无冲突；fork 加的 `CHANGELOG.md` `USAGE.md` `ai-context/` 上游不会改 |
