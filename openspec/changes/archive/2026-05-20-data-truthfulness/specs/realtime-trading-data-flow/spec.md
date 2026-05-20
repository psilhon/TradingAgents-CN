## MODIFIED Requirements

### Requirement: hot-path 端点 MUST NOT 在用户请求路径同步触发上游行情拉取，MUST 保证聚合的数据时效一致

任何对外暴露给前端 / agent 的实时数据 endpoint（包括但不限于 `/api/market/overview` / `/api/paper/account` / `/api/paper/positions` / `/api/paper/performance` / 自选股价格查询 / 持仓 PnL 查询）MUST 仅从**已物化的快照**读取数据，不得在请求处理路径上同步调用 akshare / tushare / baostock 等外部行情源；MUST 保证 p99 < 50ms。

**已物化的快照分两类**（按数据规模分层存储）：

1. **持仓 / 自选股快照**（限定 codes，通常 < 100 只）：mongo `market_quotes` collection。由 `paper-realtime-quotes` capability 的 3s sync job 写入。
2. **全市场聚合 / 详细数据**（5500+ 只）：mongo `market_quotes` 的全表数据，由 `quotes_ingestion_service` 周期写入；或 in-memory `QuotesService._cache` 由 `market_overview_prewarm_service` 维护。

**全市场聚合 endpoint（如 `/api/market/overview`）MUST 按当日 `updated_at` 过滤** —— `$match: { updated_at: { $gte: <today_cn_start_utc> } }`，或在 in-memory 聚合时按 per-item `updated_at` 字段过滤。MUST NOT 直接对全集 `cache.values()` 累加（跨日累加是数据造假事故来源，详 data-quality-gate）。

理由：交易系统的"实时"由后台定频 sync / prewarm 维护；hot path 的 SLO 是 p99 < 50ms。任何让用户请求路径同步等待外部 HTTP 的实现，在外部源 p99 不可控时会直接拖垮 UI（实测 akshare cold p99 = 110s）。

mongo aggregate vs in-memory cache 不是互斥要求 —— 实现方可任选；mongo 单机本地 5500 doc `$facet` aggregate 实测 < 50ms，与 cache 路径性能相当。**约束在于结果层（延迟 + 时效一致性），不在机制层**。

允许的"间接调用"：APScheduler / asyncio background task 路径下的 `realtime_quote_sync_service`（写 mongo）/ `market_overview_prewarm_service`（写 in-memory）/ `quotes_ingestion_service` 等持续向 hot snapshot 写入。这些不在用户请求路径上。

#### Scenario: market overview 路径不阻塞等待 akshare

- **WHEN** client 请求 `GET /api/market/overview`
- **THEN** 实现 MUST 仅从已物化快照（mongo `market_quotes` aggregate 或 in-memory cache）聚合
- **AND** MUST NOT 在请求路径触发任何 `akshare`/`tushare`/`baostock` 调用（即便 cache 为空也不触发——返回 staleness_seconds=null + total=0 而非阻塞等待）
- **AND** p99 响应时间 < 50ms

#### Scenario: market overview 聚合 MUST 按当日 updated_at 过滤

- **WHEN** `compute_overview()` 计算涨停 / 跌停 / 上涨 / 下跌 / 成交额合计
- **THEN** 实现 MUST 限定数据时间戳 `updated_at >= 当前 CN tz 日历日 00:00:00`
- **AND** MUST NOT 把昨日 / 更早日期的 quote 一起累加（这会导致 28595 亿成交额 / 137 涨停家数 这类跨日污染事故）
- **AND** 当日无数据时，limit_up / limit_down / amount_total 等字段 MUST 返回 `null` 或 `0`，MUST NOT 用历史数据填补

#### Scenario: paper account 不调 akshare

- **WHEN** client 请求 `GET /api/paper/account`
- **THEN** 持仓 last_price MUST 从 mongo `market_quotes` 直接读取
- **AND** MUST NOT 触发任何 akshare/tushare/baostock 同步调用
