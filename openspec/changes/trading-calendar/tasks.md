# trading-calendar — Tasks

## 1. 调研现状

- [ ] 1.1 确认 akshare 拉交易日历的接口：测试 `ak.tool_trade_date_hist_sina()` 返回字段（dataframe schema）
- [ ] 1.2 确认 backend 当前调用 `is_trading_day` 的地方（grep `weekday\|9:25\|15:00`），列出需要替换的 site
- [ ] 1.3 确认前端 polling 的地方，列出需要加 is_intraday guard 的 site

## 2. TradingCalendarService

- [ ] 2.1 新建 `app/services/trading_calendar_service.py`
- [ ] 2.2 实现 `sync_year(year: int) -> dict`：akshare 调用 + 写 mongo upsert（带 unique index ensure）
- [ ] 2.3 实现 `is_trading_day(d: date) -> bool`：查 mongo，带 LRU 内存缓存（TTL 1 小时）
- [ ] 2.4 实现 `is_intraday_now() -> bool`：is_trading_day(today) and 9:25 ≤ now ≤ 15:00
- [ ] 2.5 实现 `get_today_status() -> dict`：`{date, is_trading_day, is_intraday, next_trading_day}`
- [ ] 2.6 启动时 ensure_index：`code` 唯一 + `year` 普通索引
- [ ] 2.7 单测 `tests/test_trading_calendar_service.py`：mock akshare + mock mongo，覆盖 sync / is_trading_day / 节假日判断 / 时段判断 / 缓存命中

## 3. scheduler 注册

- [ ] 3.1 在 `app/services/scheduler_service.py` 加 `_register_trading_calendar_jobs()`
- [ ] 3.2 启动时：检查 `db.trading_calendar.count_documents({year: {$in: [当年, 下一年]}})`，缺失则 `asyncio.create_task(sync_year)` fire-and-forget
- [ ] 3.3 注册年度同步 cron：`CronTrigger(month=12, day=31, hour=20)` 同步下一年
- [ ] 3.4 在 `_setup_event_listeners` 末尾调用 `_register_trading_calendar_jobs`（与 realtime quote jobs 一致模式）

## 4. 替换现有 hardcoded guard

- [ ] 4.1 修改 `app/services/scheduler_service.py:_run_realtime_quote_sync_intraday`：
  从 `weekday() < 5 and time(9,25) <= now <= time(15,0)` 改为
  `await get_trading_calendar_service().is_intraday_now()`
- [ ] 4.2 修改 `app/routers/market.py:get_market_overview`：返回值加 `is_intraday: bool` 字段
- [ ] 4.3 capability spec `paper-realtime-quotes` 的「盘中 guard」requirement 更新为引用 `trading-calendar.is_intraday_now()`（在 archive 时同步修订该 spec）

## 5. 前端 polling guard

- [ ] 5.1 `frontend/src/api/market.ts`: MarketOverview interface 加 `is_intraday: boolean`
- [ ] 5.2 `frontend/src/views/Dashboard/index.vue`: `startMarketOverviewPolling` 的 setInterval 内加判断：
  `if (!marketOverview.value?.is_intraday) return`
- [ ] 5.3 数据保持上一次成功值（盘外不清空 marketOverview）

## 6. 收口验证

- [ ] 6.1 `just ci` 全绿
- [ ] 6.2 实测 backend 启动：日志显示 trading_calendar sync + 2 个 job 注册
- [ ] 6.3 mongo `trading_calendar` collection 当年数据齐全（~250 条 trading days）
- [ ] 6.4 手动触发 `is_intraday_now()` 确认周末返回 False / 工作日盘中 True
- [ ] 6.5 前端 Dashboard 盘外刷新时 setInterval 跳过（看 console.log 或加调试）
- [ ] 6.6 `docs/CHANGELOG.md [Unreleased]` 加本 change entry
- [ ] 6.7 archive change → `openspec/changes/archive/2026-05-08-trading-calendar/`
- [ ] 6.8 应用 spec → `openspec/specs/trading-calendar/spec.md`
- [ ] 6.9 修订 `openspec/specs/paper-realtime-quotes/spec.md` 的「盘中频率 guard」requirement，引用 `trading-calendar.is_intraday_now()`
