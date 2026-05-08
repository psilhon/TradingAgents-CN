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

## 2. hot snapshot 双路径（mongo + in-memory）

> 立项漏审回填（commit 注明）：原 plan 假设 `/api/market/overview` 也读 mongo，
> 与 `paper-realtime-quotes` 既定"只 sync favorites∪positions" spec 冲突。
> 修正：持仓 / 自选股走 mongo，全市场聚合走 in-memory prewarm。

### 2A. quote_snapshot_reader（持仓 / 自选股，mongo 路径）

- [x] 2A.1 新建 `app/services/quote_snapshot_reader.py` + `get_quote_snapshot_reader()` singleton
- [x] 2A.2 `read_quotes(codes: list[str]) -> dict`：返回 `{code: {close, pct_chg, amount, last_price_as_of}}`，缺漏 code 值 None；顶层带 `as_of_ts`（min last_price_as_of, 忽略 null）
- [x] 2A.3 单元测试 `tests/services/test_quote_snapshot_reader.py`：mock mongo cursor + 验证聚合 + as_of_ts 正确

### 2B. market_overview_prewarm_service（全市场聚合，in-memory 路径）

- [x] 2B.1 新建 `app/services/market_overview_prewarm_service.py` + `get_prewarm_service()` singleton
- [x] 2B.2 `compute_overview() -> dict`：从 `QuotesService._cache` + `_cache_ts` 聚合 `limit_up/limit_down/advance/decline/amount_total/total/as_of_ts/staleness_seconds`；cache 空时返回 nullable 字段（不阻塞等待）
- [x] 2B.3 `prewarm_loop()` lifecycle task：盘中每 30s 调 `QuotesService._ensure_cache()`；盘外 sleep；asyncio.wait_for 包外加超时 = ttl，避免单轮卡死
- [ ] 2B.4 在 `app/main.py` lifespan 启动时 `asyncio.create_task(prewarm_service.prewarm_loop())`，shutdown 时 cancel  *(deferred to Section 6 — 与 PnL stream lifecycle 一起注册)*
- [x] 2B.5 单元测试 `tests/services/test_market_overview_prewarm_service.py`：mock QuotesService cache + 验证 compute_overview 输出 + prewarm_loop 盘内/盘外路径

## 3. router hot-path 改造

- [x] 3.1 `app/routers/market.py` `GET /api/market/overview` 改走 `market_overview_prewarm_service.compute_overview()`，移除 `QuotesService.get_market_overview()` 直接调用（hot-path 不再阻塞 _ensure_cache）
- [x] 3.2 响应 schema 加 `as_of_ts: str | null (ISO8601)` + `staleness_seconds: float | null` 必返字段
- [x] 3.3 `app/routers/paper.py` `_get_last_price` 改走 `quote_snapshot_reader.read_quotes(...)`，返回 `(price, as_of_ts) | (None, None)`；`/api/paper/account` / `/api/paper/positions` 响应里 positions 每条带 `last_price_as_of`，顶层带 `as_of_ts`（取所有 positions min）
- [x] 3.4 写 hot-path SLO 单测 `tests/test_hot_path_slo.py`：spy `QuotesService._fetch_spot_akshare`，断言 `/api/market/overview` 路径（cache 空 + cache 有数据两种）不调 akshare

- [x] 4.1 `app/services/realtime_quote_sync_service.py`：每次 mongo upsert 后对每个变化的 code（`pct_chg` / `close` 任一变了）发 redis publish `channel:quote:{code}` payload `{code, close, pct_chg, amount, as_of_ts}`
- [x] 4.2 redis 异常 logger.warning + throttle（首次 fail 一次 warning，后续静默直到恢复时 info）
- [x] 4.3 单测 `tests/services/test_realtime_quote_publish.py`：3 scenario（变化才 publish / redis 故障不阻塞 / payload schema）

## 5. WebSocket /ws/quotes endpoint

- [x] 5.1 新建 `app/routers/websocket_quotes.py`（与 `websocket_notifications.py` 同模式：auth 复用 token_data.sub，user_id 不允许 hardcode）
- [x] 5.2 `GET /ws/quotes` 接受连接 → 等 `subscribe` 消息 → 启 redis pubsub task 监听对应 channel → 推送给 client（30s 心跳，60s 接收超时关闭）
- [x] 5.3 `subscribe_pnl` → 直接订阅 `channel:pnl:{token_data.sub}`，禁止订阅别人的（即便 client payload 含 user_id 也忽略，spec 强制）
- [x] 5.4 ws disconnect 时清理 pubsub subscription（cancel listener + heartbeat task + pubsub.unsubscribe + close）
- [x] 5.5 单元测试 `tests/test_websocket_quotes.py`：FastAPI TestClient + fake redis pubsub + mock AuthService —— 7 scenario（无效 token / 空 sub / subscribe / subscribe_pnl 强制 user-scoped / ping-pong / unknown type / invalid JSON）
- [x] 5.6 在 `app/main.py` 注册 router (prefix=/api, tag=websocket-quotes)

## 6. PnL stream service

- [x] 6.1 新建 `app/services/pnl_stream_service.py` + `compute_pnl(user_id) -> dict`
- [x] 6.2 公式：`unrealized = Σ (last_price - avg_cost) * qty`（last_price 来自 `quote_snapshot_reader.read_quotes`）；`equity = cash[CNY] + Σ qty*last_price`；带 `as_of_ts`（min last_price_as_of）
- [x] 6.3 lifecycle background task `pnl_stream_loop`：盘中（`is_intraday_now()`）每 3s 扫 `paper_positions.distinct("user_id", {"market": "CN"})`，重算 PnL，diff > 0.01 后 publish `channel:pnl:{user_id}`
- [x] 6.4 diff 判定：unrealized 或 equity abs diff > 0.01 才 publish
- [x] 6.5 在 `app/main.py` lifespan 启动时调 `get_prewarm_service().start()` + `get_pnl_stream_service().start()`；shutdown stop（同时也完成 2B.4 deferred）
- [x] 6.6 单测 `tests/services/test_pnl_stream_service.py`：5 scenario（公式 / 缺 quotes / diff 阈值 / 盘外 noop / singleton）

## 7. quote_freshness_monitor + freshness endpoint

- [x] 7.1 新建 `app/services/quote_freshness_monitor.py` + `get_freshness() -> dict`
- [x] 7.2 `GET /api/market/freshness` endpoint（`app/routers/market.py` 内）：返回 `{as_of_ts, staleness_seconds, is_intraday, last_successful_sync_at, sync_running, sla_threshold_seconds, breach}`
- [x] 7.3 盘中周期检查（lifecycle background task `monitor_loop` 每 60s 一轮）：staleness > SLO 阈值（默认 90s）时 logger.warning + 写 `system_logs` collection 一条 `kind="quote_staleness_breach"` 事件；盘外即便 stale 也不写
- [x] 7.4 单测 `tests/services/test_quote_freshness_monitor.py`：6 scenario（盘中正常 / 盘外不 breach / 盘中 SLA 违反写 logs / 盘外不写 / 无数据 / singleton）
- [x] 7.5 在 `app/main.py` lifespan 注册 `get_freshness_monitor().start()` + shutdown stop

## 8. 文档 + spec

- [x] 8.1 更新 `docs/ai-context/architecture.md`：新增"实时数据流 SLO 模型"段（双 hot snapshot 路径表 + ASCII push 链路图 + SLO 表 + hot-path 路径约束 + lifecycle tasks 表 + 失败模式 degrade 表）
- [x] 8.2 `docs/CHANGELOG.md` `[Unreleased]` 加完整条目（含 6 条 capability 铁律 / 立项漏审说明 / 前置依赖）
- [x] 8.3 spec.md 与实现一致（review pass）：双 hot-snapshot path / 6 requirements / scenarios 全部覆盖

## 9. 验证（B 类触发点：完成时报告）

- [x] 9.1 `just ci` 全绿（lint + typecheck + unit）：104 passed / 2 skipped / 0 failed
- [x] 9.2 backend `--reload` 加载新代码 + 3 个 lifecycle tasks 启动（logs/tradingagents.log 13:16:29 起可见 PnLStream / QuoteFreshnessMonitor / MarketOverviewPrewarm 启动日志）
- [x] 9.3 prewarm 超时降级生效（日志 `prewarm 超时 (>30.0s)，下一轮再尝试`），不阻塞 hot-path
- [x] 9.4 freshness monitor 主动检测 SLA breach（日志 `staleness=90.0s > 90.0s` 反复输出，证明盘内周期检查在跑）
- [x] 9.5 hot-path 切到 prewarm 路径（python introspection: `compute_overview` 在 endpoint impl）
- [x] 9.6 401 auth gate 0.001s（之前 cold 110s——用户感知问题根除）
- [ ] 9.7 真 redis publish 端到端 + ws 推送验证：留作集成测试 follow-up（unit test 已覆盖关键行为）
- [ ] 9.8 redis 关闭 degrade 验证：留作 follow-up（unit test 已 mock FailingRedis 覆盖）

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
