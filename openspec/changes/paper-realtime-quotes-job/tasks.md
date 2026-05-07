# paper-realtime-quotes-job — Tasks

## 1. 调研现状

- [ ] 1.1 确认 favorites collection schema：collection 名 / 文档结构 / 读取路径
- [ ] 1.2 确认 paper_positions 字段（user_id / code / market 已知）
- [ ] 1.3 确认 akshare 批量行情 API 可用性：测 `ak.stock_zh_a_spot_em()` 是否能按代码列表过滤；如不能，评估 `ak.stock_bid_ask_em(symbol=code)` 单股循环成本
- [ ] 1.4 确认 `_get_last_price` 不再需要修改（已经查 `market_quotes` 优先）

## 2. 实施 service

- [ ] 2.1 新建 `app/services/realtime_quote_sync_service.py`：定义 class `RealtimeQuoteSyncService` 含 `fetch_quotes_for_codes` / `sync_favorites_and_paper_positions` 两方法
- [ ] 2.2 实现 `_collect_target_codes(db) -> set[str]`：自选股 + paper 持仓 codes 取并集去重
- [ ] 2.3 实现 `fetch_quotes_for_codes(codes: list[str]) -> list[dict]`：调 akshare batch（按批次切分，单批 ≤ 50 只）；timeout = 30s/批；失败 log warn 后跳过
- [ ] 2.4 实现 `sync_favorites_and_paper_positions() -> dict`：返回 `{total, fetched, updated, errors}` 状态字典
- [ ] 2.5 mongo upsert 到 `market_quotes`：`{code, symbol, close, volume, updated_at}`，`code` 唯一索引（service 启动时 ensure_index）
- [ ] 2.6 单测 `tests/test_realtime_quote_sync_service.py`：mock akshare + mock mongo，覆盖 (a) codes 去重 (b) batch 切分 (c) upsert payload (d) akshare 失败降级 (e) 空 codes 时不调 akshare

## 3. 注册 scheduler job

- [ ] 3.1 在 `app/services/scheduler_service.py` 加 `register_realtime_quote_sync_jobs()`（注册 2 个 job）
- [ ] 3.2 注册盘中高频 job：
   - trigger: `IntervalTrigger(seconds=30)`
   - job 配置: `max_instances=1, coalesce=True, misfire_grace_time=10`
   - job body 第一行 guard：`if not (date.today().weekday() < 5 and time(9,25) <= now <= time(15,0)): return`
- [ ] 3.3 注册盘后 cron job：`CronTrigger(day_of_week='mon-fri', hour=17, minute=0)`
- [ ] 3.4 启动时 ensure index on `market_quotes.code`（`unique=True`）
- [ ] 3.5 在 `app/main.py` 启动钩子调用注册函数（或现有 init_scheduler 入口加一行）
- [ ] 3.6 验证单次 fetch+upsert < 30s（防止 coalesce 累积）

## 4. 收口验证

- [ ] 4.1 `just ci` 通过（lint + format + pyright + pytest）
- [ ] 4.2 实际启动 backend：`just dev-restart`，日志看到 `Added job '自选股+持仓行情刷新'`
- [ ] 4.3 手动触发一次：调用 `RealtimeQuoteSyncService.sync_favorites_and_paper_positions()` 验证 `market_quotes` 被写入
- [ ] 4.4 验证 `_get_last_price("000776", "CN")` 返回非 None
- [ ] 4.5 前端 Dashboard 持仓行显示真实 `last_price` / `unrealized_pnl`（不再 ¥0.00）
- [ ] 4.6 `docs/CHANGELOG.md [Unreleased]` 加本 change entry
- [ ] 4.7 archive change → `openspec/changes/archive/2026-05-XX-paper-realtime-quotes-job/`
- [ ] 4.8 应用 spec → `openspec/specs/paper-realtime-quotes/spec.md`
