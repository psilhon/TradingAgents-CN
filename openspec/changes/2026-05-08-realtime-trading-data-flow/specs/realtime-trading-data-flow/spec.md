## ADDED Requirements

### Requirement: hot-path 端点 MUST NOT 在用户请求路径同步触发上游行情拉取

任何对外暴露给前端 / agent 的实时数据 endpoint（包括但不限于 `/api/market/overview` / `/api/paper/account` / `/api/paper/positions` / `/api/paper/performance` / 自选股价格查询 / 持仓 PnL 查询）MUST 仅从 mongo `market_quotes` collection（或其聚合）读取数据，不得在请求处理路径上同步调用 akshare / tushare / baostock 等外部行情源。

理由：交易系统的"实时"由后台定频 sync + push 推送保证；hot path 的 SLO 是 p99 < 50ms。任何让用户请求路径同步等待外部 HTTP 的实现，在外部源 p99 不可控时会直接拖垮 UI（实测 akshare cold p99 = 110s）。

允许的"间接调用"：APScheduler / asyncio background task 路径下的 `realtime_quote_sync_service` / `quotes_ingestion_service` 持续向 mongo 写入。这些不在用户请求路径上。

#### Scenario: market overview 不调 akshare

- **WHEN** client 请求 `GET /api/market/overview`
- **THEN** 实现 MUST 仅从 mongo `market_quotes` 聚合
- **AND** MUST NOT 调用 `ak.stock_zh_a_spot_em()` 或 `QuotesService.get_market_overview()` 触发上游 fetch
- **AND** p99 响应时间 < 50ms（mongo 命中索引）

#### Scenario: paper account 不调 akshare

- **WHEN** client 请求 `GET /api/paper/account` / `/api/paper/positions` / `/api/paper/performance`
- **THEN** 持仓 last_price 查询路径 MUST 仅读 mongo `market_quotes`
- **AND** mongo 缺漏的 code 返回 `last_price=null` + `last_price_as_of=null`，不 fallback 触发外部 fetch
- **AND** p99 响应时间 < 100ms（含 PnL 聚合计算）

#### Scenario: 上游源仅在 worker / scheduler 路径出现

- **WHEN** code review / lint
- **THEN** `app/routers/**/*.py` MUST NOT import 或同步调用 `akshare` / `tushare` / `baostock`
- **AND** `_fetch_spot_akshare` / `ak.stock_zh_a_spot_em` 调用栈 MUST 仅出现在 `app/services/realtime_quote_sync_service.py` / `app/services/quotes_ingestion_service.py` / `app/worker/**` / APScheduler job

### Requirement: 所有实时数据响应 MUST 透出 as_of_ts 与 staleness_seconds

任何返回行情 / 持仓 / PnL 的 endpoint，响应顶层 MUST 包含：

- `as_of_ts: string`，ISO8601（含时区，建议 UTC + 'Z'）—— 该响应所反映数据的最新时刻
- `staleness_seconds: float`—— `now - as_of_ts` 的秒数（server 端计算，单调递增）

包含多个数据点的响应（如 `paper_positions` 数组），每条记录 MUST 额外带 `last_price_as_of: string | null`；顶层 `as_of_ts` 取所有 records `last_price_as_of` 的 **min**（"最 stale 的那条"，反映整体 freshness）。

理由：金融决策依赖时效。UI / agent / 量化策略 必须能区分"30s 前的价"和"3 分钟前的价"。无 `as_of_ts` 透出 = 用户基于不知何时的 stale price 做决定 = dangerous。

#### Scenario: market overview 带 as_of_ts

- **WHEN** `GET /api/market/overview` 返回
- **THEN** 响应 JSON 顶层有 `as_of_ts` 字段（ISO8601 字符串）
- **AND** 顶层有 `staleness_seconds` 字段（float，server 端 `now - as_of_ts`）
- **AND** `as_of_ts` 取 mongo `market_quotes.updated_at` 的 max

#### Scenario: paper positions 每条带 last_price_as_of

- **WHEN** `GET /api/paper/positions` 返回
- **THEN** 每个 position 对象有 `last_price_as_of: string | null`
- **AND** 顶层 `as_of_ts` = min(positions.last_price_as_of)（忽略 null）
- **AND** 所有 last_price 缺漏（全 null）时，顶层 `as_of_ts = null` 且 `staleness_seconds = null`

#### Scenario: 时区与格式

- **WHEN** 任何 `as_of_ts` 字段
- **THEN** 格式 MUST 为 ISO8601 + 时区后缀（`Z` 或 `+08:00`），不允许 naive datetime
- **AND** 推荐 UTC（`Z`）；client 自行渲染本地时间

### Requirement: WebSocket /ws/quotes MUST 提供按 code 订阅的实时推送

后端 MUST 提供 `WebSocket /ws/quotes` endpoint，支持 client：

- **subscribe**：`{"type": "subscribe", "codes": ["000001", "600036"]}` → 后端订阅 redis `channel:quote:{code}`，每次后台 sync upsert 后将变化的 code 推送给该 ws，payload `{"type": "quote", "data": {code, close, pct_chg, amount, as_of_ts}}`
- **subscribe_pnl**：`{"type": "subscribe_pnl"}` → 后端订阅 redis `channel:pnl:{user_id}`（user_id 从 ws 连接时的 token_data.sub 取，**不允许 client 指定**），收到 PnL 计算结果时推送 `{"type": "pnl", "data": {...}}`
- **unsubscribe**：`{"type": "unsubscribe", "codes": ["000001"]}` → 取消对应订阅
- **ping/pong**：每 30s 心跳；client 60s 不响应则 server 主动 close

ws 连接 MUST 走 token auth（与 `/ws/notifications` 同模式）；user_id MUST 从 token 取，不允许 hardcode 或从 query string。

#### Scenario: 订阅自选股推送

- **WHEN** client 连接 `/ws/quotes` 后发 `{"type": "subscribe", "codes": ["000001"]}`
- **AND** 后台 `realtime_quote_sync_service` 完成一次 sync，`000001` 的 close 变化
- **THEN** 后端 redis publish `channel:quote:000001`
- **AND** 该 ws 收到 `{"type": "quote", "data": {"code": "000001", "close": ..., "pct_chg": ..., "amount": ..., "as_of_ts": "..."}}`
- **AND** 推送延迟 < 100ms（redis pub → ws send）

#### Scenario: 订阅 PnL 强制 user-scoped

- **WHEN** client 连接 `/ws/quotes` 时 token sub = `user_A`
- **AND** client 发 `{"type": "subscribe_pnl"}`
- **THEN** 后端订阅 `channel:pnl:user_A`（不允许参数指定别的 user_id）
- **AND** 即便 client 发 `{"type": "subscribe_pnl", "user_id": "user_B"}` 也只订自己的（user_A）

#### Scenario: 心跳与超时

- **WHEN** ws 连接已建立 60s 无来自 client 的任何消息（含 ping）
- **THEN** server MUST 主动 close（code 1001 或 1011）
- **AND** 释放 redis pubsub subscription（避免泄漏）

### Requirement: PnL stream service MUST 盘中每 ≤ 3s 推送变化的 PnL

`pnl_stream_service` MUST 提供 lifecycle background task `pnl_stream_loop`，盘中（按 `trading-calendar.is_intraday_now()` 判定）每 ≤ 3s 一轮：

1. 查询 `paper_positions.distinct("user_id")` 拿所有有 active position 的 user
2. 对每个 user 算 PnL：`unrealized = Σ (last_price - avg_cost) * qty`，`equity = cash + Σ qty * last_price`，last_price 来自 `quote_snapshot_reader`（mongo）
3. 与上一轮该 user 的 PnL 对比：unrealized diff > 0.01 或 equity diff > 0.01 → publish `channel:pnl:{user_id}` payload `{type: "pnl", data: {positions: [...], total_unrealized, total_realized, total_equity, as_of_ts}}`
4. 单 user 单轮重算 < 50ms（mongo 索引齐 + 通常持仓 < 50 只）

盘外（`is_intraday_now() == False`）MUST 不跑（不浪费 CPU + 价格不会变）。

PnL 计算 MUST 服务端做，不允许前端拿 last_price 自己 × position 算（避免前端竞态 + 不一致）。

#### Scenario: 盘中变化才 publish

- **WHEN** `pnl_stream_loop` 第二轮算出 user_A unrealized = 1000.50，第一轮是 1000.49
- **THEN** abs(diff) = 0.01 NOT > 0.01，NOT publish
- **WHEN** 第三轮 unrealized = 1001.00
- **THEN** abs(diff) = 0.50 > 0.01，publish `channel:pnl:user_A`

#### Scenario: 盘外 noop

- **WHEN** 当前时间 周末 / 节假日 / 11:30-13:00 午休 / 15:00 后
- **AND** `is_intraday_now() == False`
- **THEN** `pnl_stream_loop` MUST sleep 30s 跳过，不算 PnL 不 publish
- **AND** logger 不 spam（每次 loop 仅 debug 级日志）

#### Scenario: as_of_ts 反映持仓中最 stale 的价

- **WHEN** user_A 持有 000001（last_price_as_of = 09:30:00）和 600036（last_price_as_of = 09:30:30）
- **THEN** publish 的 PnL payload `as_of_ts == 09:30:00`（min）

### Requirement: GET /api/market/freshness MUST 暴露数据时效给 UI 角标

提供 `GET /api/market/freshness` endpoint（认证后可读），返回当前 mongo `market_quotes` 的时效摘要：

```json
{
  "as_of_ts": "2026-05-08T09:33:21Z",
  "staleness_seconds": 12.4,
  "is_intraday": true,
  "last_successful_sync_at": "2026-05-08T09:33:21Z",
  "sync_running": true,
  "sla_threshold_seconds": 90,
  "breach": false
}
```

字段：

- `as_of_ts`: mongo `market_quotes.updated_at` 的 max
- `staleness_seconds`: now - as_of_ts
- `is_intraday`: 来自 `trading-calendar.is_intraday_now()`
- `last_successful_sync_at`: 取自 `sync_status` collection 的最近一条 `realtime_quote_sync` job 完成时间
- `sync_running`: 当前是否有 sync 在进行中
- `sla_threshold_seconds`: SLA 阈值（默认 90 = 3 个 30s sync 周期）
- `breach`: `is_intraday and staleness_seconds > sla_threshold_seconds`

UI MAY 用此 endpoint 渲染角标（绿 / 黄 / 红）。

#### Scenario: 盘中 freshness 正常

- **WHEN** 盘中 sync 正常运行，最近一次 update 5s 前
- **THEN** `staleness_seconds ≈ 5`，`breach == false`，`sync_running` 反映实际状态

#### Scenario: 盘外不触发 breach

- **WHEN** 周末或盘后
- **AND** mongo 数据是 12 小时前的
- **THEN** `is_intraday == false`，`breach == false`（盘外 stale 是预期行为）

#### Scenario: 盘中 SLA 违反

- **WHEN** 盘中 sync job 卡住或失败 3+ 周期
- **AND** `staleness_seconds > 90`
- **THEN** `breach == true`
- **AND** `quote_freshness_monitor` 同步写一条 `system_logs` 事件 `kind="quote_staleness_breach"`

### Requirement: realtime_quote_sync_service MUST 在 mongo upsert 后发布 redis quote 事件

`app/services/realtime_quote_sync_service.py` 在每次 sync 周期完成 mongo `market_quotes` upsert 后，MUST 对每个变化的 code（与上次相比 close 或 pct_chg 任一变化）通过 redis 发布 `channel:quote:{code}` 事件。

payload 必须 JSON 序列化：

```json
{"code": "000001", "close": 12.34, "pct_chg": 0.5, "amount": 1.2e8, "as_of_ts": "2026-05-08T09:33:21Z"}
```

redis 不可用 / publish 异常时 MUST `logger.warning` 不抛（不阻塞 sync 主流程）。pubsub 通道命名固定：

- `channel:quote:{code}`：行情更新（`{code}` 是 6 位 A 股代码）
- `channel:pnl:{user_id}`：PnL 更新（user_id 即 mongo `paper_accounts.user_id`）

不得复用其他通道名（避免与 `/ws/notifications` 既有 pub/sub 冲突）。

#### Scenario: 变化的 code 才 publish

- **WHEN** sync 拉到 100 只 codes，其中 30 只 close 或 pct_chg 与上次比有变化
- **THEN** redis 收到 30 次 `channel:quote:*` publish
- **AND** 70 只无变化的 code 不 publish

#### Scenario: redis 宕机降级

- **WHEN** redis 容器停掉
- **AND** sync job 触发
- **THEN** mongo upsert 仍正常完成
- **AND** publish 失败 logger.warning 一次（不每条 publish 都 spam）
- **AND** 整体 sync job 仍标记为 success（不算失败）

### Requirement: 旧字段兼容 / 渐进迁移

为不破坏前端现有 polling 行为，**所有响应 schema 变更 MUST 是 additive**：

- 新增 `as_of_ts` / `staleness_seconds` / `last_price_as_of` 字段
- **不删** 既有响应字段（`success` / `data` / `message` / 业务字段）
- **不改** 既有字段类型与含义

前端可分阶段迁移：先继续 polling（享受新字段渲染时效）→ 再切 ws 订阅（享受 push 推送）。

#### Scenario: 旧前端不破

- **WHEN** 前端代码未更新（仍按旧 schema 解析）
- **AND** 调 `GET /api/market/overview`
- **THEN** 返回的 JSON 含所有旧字段（`limit_up` / `limit_down` / `advance` / `decline` / `amount_total` / `total` / `is_intraday`）
- **AND** 新增字段（`as_of_ts` / `staleness_seconds`）作为额外字段存在
- **AND** 前端 JSON.parse 不报错，旧渲染逻辑继续工作
