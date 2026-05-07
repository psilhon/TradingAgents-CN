# trading-calendar — Tasks (archived 2026-05-08)

## 1. 调研现状

- [x] 1.1 akshare `ak.tool_trade_date_hist_sina()` 返回 8797 条 trade_date（1990-12-19–2026-12-31），单列字符串 YYYY-MM-DD。仅交易日（不含非交易日），可简化 schema 为「存在即交易日」
- [x] 1.2 grep `weekday\|9:25\|15:00` 找到现有调用点：`app/utils/trading_time.py` (5 个 sync 函数) / `app/services/scheduler_service.py` realtime quote intraday guard / `app/routers/stocks.py` / `app/worker/tushare_sync_service.py` 等。本 change 仅替换 `paper-realtime-quotes-job` 的 guard，其他点作 follow-up
- [x] 1.3 前端 polling 加 guard 的 site：`Dashboard market-overview-panel` 一处

## 2. TradingCalendarService

- [x] 2.1 新建 `app/services/trading_calendar_service.py`
- [x] 2.2 实现 `sync_year(year)`：akshare 调用 + 按年过滤 + mongo upsert，返回 `{year, total, inserted, updated}`
- [x] 2.3 实现 `is_trading_day(d)`：mongo find_one + FIFO dict 缓存（max 2048 条）；fallback 到 weekday() < 5 当 mongo 异常
- [x] 2.4 实现 `is_intraday_now()`：综合判断 is_trading_day(today) + 时段（9:30–11:30 / 13:00–15:00）；午休排除
- [x] 2.5 实现 `get_today_status()`：返回 `{date, is_trading_day, is_intraday, next_trading_day}`，向前查最多 30 天找下一个交易日
- [x] 2.6 启动时 `ensure_index()`：date unique + year 普通 index
- [x] 2.7 单测 `tests/test_trading_calendar_service.py` 7 cases 全过：mongo 命中 / 节假日识别 / 缓存策略 / sync 过滤年份 / akshare 失败降级 / get_today_status

## 3. scheduler 注册

- [x] 3.1 加 `_register_trading_calendar_jobs()` 到 `_setup_event_listeners` 末尾（与 realtime quote jobs 一致 pattern）
- [x] 3.2 启动时 `asyncio.create_task(_ensure_trading_calendar_synced())`：检查当年 + 下一年缺失则 sync（fire-and-forget 不阻塞）
- [x] 3.3 注册年度 cron：`CronTrigger(month=12, day=31, hour=20)` 每年 12/31 20:00 同步下一年
- [x] 3.4 启动时 `ensure_index` on trading_calendar collection

## 4. 替换现有 hardcoded guard

- [x] 4.1 `app/services/scheduler_service.py:_run_realtime_quote_sync_intraday`：从 hardcoded `weekday()<5 + 9:25-15:00` 替换为 `await get_trading_calendar_service().is_intraday_now()`，配 fallback to weekday 当 trading_calendar 异常
- [x] 4.2 `app/routers/market.py:get_market_overview` 返回值加 `is_intraday: bool` 字段
- [ ] 4.3 spec `paper-realtime-quotes` 修订：「盘中频率 guard」requirement 引用 `trading-calendar.is_intraday_now()`（在 archive 时同步修订该 spec）

## 5. 前端 polling guard

- [x] 5.1 `frontend/src/api/market.ts`: MarketOverview interface 加 `is_intraday: boolean`
- [x] 5.2 `frontend/src/views/Dashboard/index.vue:startMarketOverviewPolling`: setInterval 内加 `if (!marketOverview.value?.is_intraday) return`
- [x] 5.3 数据保持上一次成功值（marketOverview.value 不清空 — onError 时直接返回）

## 6. 收口验证

- [x] 6.1 `just ci` 全绿（lint + format + pyright + 31 unit tests passed）
- [x] 6.2 实测 backend 启动：日志显示 `Added job "交易日历年度同步（次年）"` + `启动检查：trading_calendar 2026 年已有 242 条交易日`
- [x] 6.3 mongo `trading_calendar` 当年数据齐全（242 条 = 2026 全年交易日）
- [x] 6.4 验证 API：is_trading_day(2026-05-08 Fri)=True / 2026-05-09 Sat=False / 2026-10-01 国庆=False / 2026-02-17 春节假=False；get_today_status() 含 next_trading_day=2026-05-11
- [ ] 6.5 前端 Dashboard 盘外刷新跳过（用户实际使用时验证，本会话内未截图确认；HMR 已推）
- [x] 6.6 `docs/CHANGELOG.md [Unreleased]` 已加本 change entry
- [x] 6.7 archive change → `openspec/changes/archive/2026-05-08-trading-calendar/`
- [x] 6.8 应用 spec → `openspec/specs/trading-calendar/spec.md`
- [x] 6.9 修订 `openspec/specs/paper-realtime-quotes/spec.md`「盘中频率 guard」requirement，引用 `trading-calendar.is_intraday_now()`
