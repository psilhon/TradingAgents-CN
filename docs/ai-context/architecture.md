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
| `docker-compose.yml` | 不动（端口走 `docker-compose.override.yml`）|
| `docs/` | 上游加新文档无冲突；fork 加的 `CHANGELOG.md` `USAGE.md` `ai-context/` 上游不会改 |
