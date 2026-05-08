# realtime-trading-data-flow — Tasks

> 对应 [proposal.md](./proposal.md) / [spec.md](./specs/realtime-trading-data-flow/spec.md)
>
> 实施阶段：**Phase 2 执行**（subagent-driven 优先；A/B 触发点见 dev-phases.md）

## 前置（必须在本 change 任何 task 开始前完成）

- [ ] 0.1 把 4 个 router 的 security 加固改动 commit（`config.py` / `multi_source_sync.py` / `sync.py` / `websocket_notifications.py` + `tests/test_review_security_fixes.py`）+ CI 绿
- [ ] 0.2 hotfix change（`quotes_service.py` 加 timeout + 新增 `tests/services/test_quotes_service_timeout.py`）合入或单独 commit + CI 绿
- [ ] 0.3 确认 `paper-realtime-quotes` capability 当前 30s sync job 在跑（`logger.info` 看到 sync 日志）

## 1. 调研 + 契约确认

- [ ] 1.1 grep `_get_last_price` / `quotes_service` 所有调用点；确认 hot path（router）vs scheduler/worker path 边界，列入 design notes
- [ ] 1.2 确认 mongo `market_quotes` 当前 schema：`{code, symbol, close, pct_chg, amount, updated_at, ...}`；缺字段在本 change 1.3 加
- [ ] 1.3 ensure_index（启动时）：`market_quotes.updated_at` 普通索引（freshness monitor 用 max 查询）
- [ ] 1.4 redis pub/sub 通道命名约定写入 spec：`channel:quote:{code}` / `channel:pnl:{user_id}`
- [ ] 1.5 拟定 ws 协议草案（client→server: `{type:"subscribe"|"subscribe_pnl"|"unsubscribe", codes?:[]}`，server→client: `{type:"quote"|"pnl"|"error", data, as_of_ts}`），写入 spec

## 2. quote_snapshot_reader（hot path 改读 mongo）

- [ ] 2.1 新建 `app/services/quote_snapshot_reader.py` + `get_quote_snapshot_reader()` singleton
- [ ] 2.2 `read_market_overview() -> dict`：直接从 mongo `market_quotes` 聚合 `limit_up/limit_down/advance/decline/amount_total/total/as_of_ts/staleness_seconds`
- [ ] 2.3 `read_quotes(codes) -> dict`：返回 `{code: {close, pct_chg, amount, last_price_as_of}}`，缺漏 code 值 None
- [ ] 2.4 单元测试 `tests/services/test_quote_snapshot_reader.py`：mock mongo cursor，验证聚合 + as_of_ts 正确

## 3. router hot-path 改造

- [ ] 3.1 `app/routers/market.py` `GET /api/market/overview` 改走 `quote_snapshot_reader.read_market_overview()`，移除 `QuotesService.get_market_overview()` 调用
- [ ] 3.2 响应 schema 加 `as_of_ts: str (ISO8601)` + `staleness_seconds: float` 必返字段
- [ ] 3.3 `app/routers/paper.py` `_get_last_price` 改返回 `(price, as_of_ts) | (None, None)`；`/api/paper/account` / `/api/paper/positions` / `/api/paper/performance` 响应里 positions 每条带 `last_price_as_of`，顶层带 `as_of_ts`（取所有 positions min）
- [ ] 3.4 写 hot-path SLO 单测：mock mongo，断言 `/api/market/overview` 走完不调 akshare（spy on `_fetch_spot_akshare`），p99 路径 < 50ms（用 timeit profile 记录）

## 4. realtime_quote_sync_service 加 redis publish

- [ ] 4.1 `app/services/realtime_quote_sync_service.py`：每次 mongo upsert 后对每个变化的 code（`pct_chg` / `close` 任一变了）发 redis publish `channel:quote:{code}` payload `{code, close, pct_chg, amount, as_of_ts}`
- [ ] 4.2 redis 异常 logger.warning 不抛（不阻塞 sync 主流程）
- [ ] 4.3 单测 `tests/services/test_realtime_quote_sync_service.py` 加 publish 路径 mock 验证

## 5. WebSocket /ws/quotes endpoint

- [ ] 5.1 新建 `app/routers/websocket_quotes.py`（与 `websocket_notifications.py` 同模式：auth 复用 token_data.sub，user_id 不允许 hardcode）
- [ ] 5.2 `GET /ws/quotes` 接受连接 → 等 `subscribe` 消息 → 启 redis pubsub task 监听对应 channel → 推送给 client
- [ ] 5.3 `subscribe_pnl` → 直接订阅 `channel:pnl:{token_data.sub}`，禁止订阅别人的（spec 强制）
- [ ] 5.4 ws disconnect 时清理 pubsub subscription
- [ ] 5.5 集成测试 `tests/integration/test_ws_quotes.py`：起测试 redis（或 fakeredis）+ 模拟 publish + 验证 client 收到

## 6. PnL stream service

- [ ] 6.1 新建 `app/services/pnl_stream_service.py` + `compute_pnl(user_id) -> dict`
- [ ] 6.2 公式：`unrealized = Σ (last_price - avg_cost) * qty`（last_price 来自 `quote_snapshot_reader.read_quotes`）；`equity = cash + Σ qty*last_price`；带 `as_of_ts`（取所有 positions min `last_price_as_of`）
- [ ] 6.3 lifecycle background task `pnl_stream_loop`：盘中（`is_intraday_now()`）每 3s 扫描 `paper_positions.distinct("user_id")`，重算 PnL，与上次 diff 后 publish `channel:pnl:{user_id}`
- [ ] 6.4 与上次 diff 判定：close diff > 0.001 或 unrealized diff > 0.01；只 publish 变化的
- [ ] 6.5 在 `app/main.py` lifespan 启动 / 注册 `pnl_stream_loop` 为 asyncio.Task（非 APScheduler，因为是 long-running loop）
- [ ] 6.6 单测 `tests/services/test_pnl_stream_service.py`：mock positions + quotes，验证 PnL 公式 + diff 逻辑

## 7. quote_freshness_monitor + freshness endpoint

- [ ] 7.1 新建 `app/services/quote_freshness_monitor.py` + `get_freshness() -> dict`
- [ ] 7.2 `GET /api/market/freshness` endpoint（`app/routers/market.py` 内）：返回 `{as_of_ts, staleness_seconds, is_intraday, last_successful_sync_at, sync_running}`
- [ ] 7.3 盘中周期检查（APScheduler `IntervalTrigger(seconds=60)`）：staleness > SLO 阈值（默认 90s）时 logger.warning + 写 `system_logs` collection 一条 `kind="quote_staleness_breach"` 事件
- [ ] 7.4 单测 `tests/services/test_quote_freshness_monitor.py`

## 8. 文档 + spec

- [ ] 8.1 更新 `docs/ai-context/architecture.md`：新增"实时数据流 SLO 模型"段
  - ASCII 图：scheduler 30s → mongo `market_quotes` → redis pub → ws push → UI（虚线 fallback：UI polling → mongo read）
  - SLO 表（数据类 / 可接受延迟 / 当前实现路径 / 监控指标）
  - 失败模式 + degrade 行为
- [ ] 8.2 `docs/CHANGELOG.md` `[Unreleased]` 加：
  ```
  ### Added
  - hot-path mongo snapshot reader（/api/market/overview / paper.* 永不调 akshare）
  - WebSocket /ws/quotes：实时行情 + PnL 推送
  - 响应 freshness 透出（as_of_ts / staleness_seconds）
  - GET /api/market/freshness：数据时效角标 endpoint
  ```
- [ ] 8.3 confirm spec.md 与实现一致（self-review）

## 9. 验证（B 类触发点：完成时报告）

- [ ] 9.1 `just ci` 全绿（lint + typecheck + unit）
- [ ] 9.2 启动 backend，curl `/api/market/overview` p99 < 50ms（连续 100 次，用 hyperfine / 自写脚本量）
- [ ] 9.3 启动 backend，curl `/api/market/freshness` 返回合理 staleness
- [ ] 9.4 启动 backend + 手动模拟 `realtime_quote_sync_service` 跑一次，redis-cli `SUBSCRIBE channel:quote:000001` 看到 publish
- [ ] 9.5 用 `wscat` 连 `/ws/quotes`，subscribe + 验证收到 quote 推送
- [ ] 9.6 手动新建 paper position 后等 3s，subscribe_pnl 收到 PnL 推送
- [ ] 9.7 关 redis 容器，验证 hot path（market overview / paper account）仍 200（degrade 到 polling）+ ws 拒连或心跳超时

## 10. Phase 3 finishing（A 类触发点：等用户授权 push）

- [ ] 10.1 本地 commit（hotfix 风格，commit per 大功能 task：reader / sync publish / ws / pnl / freshness / docs）
- [ ] 10.2 finishing 报告：列建议 commit message、push 目标分支（feature/realtime-trading-data-flow）、是否打 tag、follow-up 项（前端订阅切换 / tushare 主源 / 港股 us hot path）
- [ ] 10.3 等用户授权后再 push
- [ ] 10.4 archive change 到 `openspec/changes/archive/2026-05-08-realtime-trading-data-flow/`
- [ ] 10.5 spec 移到 `openspec/specs/realtime-trading-data-flow/spec.md`

## 不在范围（follow-up）

- 前端 Vue 订阅 `/ws/quotes` 替换 30s polling（专有授权代码，独立改动）
- Tushare 主源切换 + 多源 fallback chain
- sync 颗粒升级 30s → 1-3s
- 港股 / 美股 hot path 改造
- 真实券商 API 接入（监管 + 风控合规另立项）
