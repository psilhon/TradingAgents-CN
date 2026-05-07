# paper-realtime-quotes-job — Tasks (archived 2026-05-07)

## 1. 调研现状

- [x] 1.1 favorites schema：`db.user_favorites` 单文档/用户 + `favorite_stocks: [{stock_code,...}]` 嵌套数组
- [x] 1.2 paper_positions schema：`{user_id, code, market, quantity, avg_cost, name?, ...}`，需 filter `market="CN"`
- [x] 1.3 **重要发现**：已有 `app/services/quotes_service.py` `QuotesService` 用 `ak.stock_zh_a_spot_em()` + 30s TTL 内存缓存。复用比新写更经济，spec #1 / #4 已修订反映这一现实
- [x] 1.4 `_get_last_price` 不需要改：已经查 `market_quotes` 优先，市场有数据后自然生效

## 2. 实施 service

- [x] 2.1 新建 `app/services/realtime_quote_sync_service.py`：定义 class `RealtimeQuoteSyncService`
- [x] 2.2 实现 `_collect_target_codes(db) -> set[str]`：自选股 + paper 持仓 (CN only) codes 取并集去重
- [x] 2.3 实现 `sync_favorites_and_paper_positions() -> dict`：调 `QuotesService.get_quotes(target_codes)` + upsert 到 `market_quotes`，返回 `{total, fetched, updated, errors}` 状态字典
- [x] 2.4 mongo upsert：`{code, symbol, close, volume, updated_at}`，`code` 唯一索引（service 启动时 ensure_index）
- [x] 2.5 单测 `tests/test_realtime_quote_sync_service.py` 6 cases，全过：codes 去重 / market=CN filter / upsert payload / QuotesService 失败降级 / 空 codes 跳过 / close ≤ 0 跳过

## 3. 注册 scheduler job

- [x] 3.1 在 `app/services/scheduler_service.py` 加 `_register_realtime_quote_sync_jobs()`（在 `_setup_event_listeners` 末尾调用）
- [x] 3.2 注册盘中高频 job：`IntervalTrigger(seconds=30)` + `max_instances=1, coalesce=True, misfire_grace_time=10` + job body guard `weekday() < 5 and time(9,25) <= now <= time(15,0)`
- [x] 3.3 注册盘后 cron job：`CronTrigger(day_of_week='mon-fri', hour=17, minute=0)`
- [x] 3.4 启动时 ensure unique index on `market_quotes.code`（`asyncio.create_task(_ensure_market_quotes_index())`）
- [x] 3.5 在 `app/main.py` 启动钩子调用 `get_scheduler_service()` 触发 `SchedulerService.__init__` 注册 jobs（关键修复：lazy singleton 不会自动 init）
- [x] 3.6 实测单次 fetch+upsert：fetched=3 时 ~12 秒（QuotesService 第一次拉全市场），后续 30s TTL 缓存命中瞬时

## 4. 收口验证

- [x] 4.1 `just ci` 全绿（lint + format + pyright + 24 unit tests passed）
- [x] 4.2 实测 backend 启动：日志显示 `Added job "自选股+持仓行情刷新（盘中）"` + `Added job "自选股+持仓行情刷新（盘后）"` + `market_quotes.code unique index 已 ensure`
- [x] 4.3 手动触发：`Result: {'total': 3, 'fetched': 3, 'updated': 3, 'errors': 0}`
- [x] 4.4 `_get_last_price` 验证：`000776=21.17 / 002428=80.2 / 603009=49.2`（不再 None）
- [ ] 4.5 前端 Dashboard 持仓行显示真实 `last_price` / `unrealized_pnl`（用户实际使用时验证，本会话内未截图确认）
- [x] 4.6 `docs/CHANGELOG.md [Unreleased]` 已加本 change entry
- [x] 4.7 archive change → `openspec/changes/archive/2026-05-07-paper-realtime-quotes-job/`
- [x] 4.8 应用 spec → `openspec/specs/paper-realtime-quotes/spec.md`
