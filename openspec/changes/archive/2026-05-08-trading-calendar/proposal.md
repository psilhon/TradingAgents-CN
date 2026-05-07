# trading-calendar

> A 股交易日历 mongo 缓存 + 项目级铁律：所有自动刷新 MUST 仅在 A 股交易日盘中执行，盘外（周末 / 节假日 / 非交易时段）不刷新。

## Why

**项目级新规则（用户明确提出）**：本项目所有自动刷新内容（market overview / paper realtime quotes / dashboard polling 等）的范围 **MUST 限定在 A 股交易日盘中时间**，其他时间无需刷新。

当前现状两个缺陷：

1. **缺统一交易日判断**：`paper-realtime-quotes-job` 用 hardcoded `weekday() < 5 and 9:25 <= now <= 15:00` 判断盘中，**不识别节假日**。春节 / 国庆 / 清明等假期周一到周五，cron 仍触发 + akshare 调用，浪费资源 + 拉的是隔日陈数据。

2. **没有交易日历数据源**：mongo 没有 `trading_calendar` collection，前端 / 后端都无法判断"今天是否交易日"。

**新约束的正式落地**需要：

- 一个全局可查询的交易日历（mongo `trading_calendar`）
- 一个统一的 `is_intraday_now() / should_refresh()` helper
- 现有 scheduler job 和前端 polling 都改用此 helper（替代 hardcoded 时段）
- 自动维护：每年 12/31 同步下一年日历

## What Changes

### 后端 — 新建 capability `trading-calendar`

- **新建 `app/services/trading_calendar_service.py`**：
  - `sync_year(year: int) -> dict`：调 akshare `tool_trade_date_hist_sina()` 拉年度交易日历，写入 `db.trading_calendar`
  - `is_trading_day(d: date) -> bool`：查 mongo（带内存 LRU 缓存）
  - `is_intraday_now() -> bool`：综合判断「今天是交易日 + 当前 9:25–15:00」
  - `should_refresh() -> bool`：alias of `is_intraday_now()`，scheduler / polling 调用入口
  - `get_today_status() -> dict`：返回 `{date, is_trading_day, is_intraday, next_open}`，前端用

- **`mongo trading_calendar` collection schema**：
  - `{date: "2026-01-02" (str YYYY-MM-DD), is_trading: bool, year: 2026}`
  - unique index on `date`，普通 index on `year`

- **`app/services/scheduler_service.py`** 注册 2 个 job：
  - **启动时检查**：当年 + 下一年（如果存在）日历是否齐全，缺失时立即同步一次（async fire-and-forget）
  - **年度同步**：`CronTrigger(month=12, day=31, hour=20)` 每年 12/31 晚上 20:00 同步下一年日历

- **修改现有 jobs 的盘中 guard**（applies to capability `paper-realtime-quotes`）：
  - `paper-realtime-quotes-job` 的 `_run_realtime_quote_sync_intraday` body 内
    `weekday() < 5 and 9:25 <= now <= 15:00` 替换为 `await trading_calendar.is_intraday_now()`
  - 节假日（如春节）即使是周一周五也不刷

### 前端

- **`app/routers/market.py`** `GET /api/market/overview` 返回值加 `is_intraday: bool` 字段
- **`frontend/src/views/Dashboard/index.vue`** `setInterval` polling 之前先判断 `marketOverview.is_intraday`：
  - 是 → 正常 5 min 刷新
  - 否 → 跳过本次刷新（节流到下次工作日）
  - 数据保持上一次成功的快照（`marketOverview.value` 不清空）

### 测试

- `tests/test_trading_calendar_service.py`：mock akshare + mock mongo，覆盖 sync_year / is_trading_day / is_intraday_now / 节假日判断 / 缓存命中

## Out of Scope

- **港股 / 美股交易日历**：本 change 只覆盖 A 股（沪深北）。港股美股日历后续单独立项
- **盘前 / 盘后竞价时段**（9:15–9:25 / 15:00–15:30）：不算盘中，不刷新
- **临时停牌处理**：交易日历只标 is_trading 整体状态，单股停牌不在此 capability
- **半日交易（圣诞前）**：A 股没有，US/HK 才有，本 change 不处理
- **历史日历回填**：只同步当年 + 下一年，不补 2020–2025 历史（用户没回看历史需求）
- **数据源 fallback**：仅用 akshare `tool_trade_date_hist_sina()`，失败则保留旧 mongo 数据。多源 fallback 作 follow-up

## Impact

**改动范围**：
- 新建 `app/services/trading_calendar_service.py`（~120 行）
- 修改 `app/services/scheduler_service.py`（+30 行，2 个 job + 启动检查）
- 修改 `app/services/realtime_quote_sync_service.py` / `app/routers/market.py`（替换 guard + 加 is_intraday 字段，~10 行）
- 修改 `frontend/src/views/Dashboard/index.vue`（polling guard，~10 行）
- 修改 `frontend/src/api/market.ts`（MarketOverview 加 is_intraday 字段）
- 新增 `tests/test_trading_calendar_service.py`（~80 行）
- 新建 `openspec/specs/trading-calendar/spec.md`

**风险**：低
- akshare `tool_trade_date_hist_sina` 是稳定接口，单次拉年度日历快（~1 秒）
- 启动时缺失自动同步，不阻塞启动（async fire-and-forget）
- 12/31 年度同步失败 → mongo 保留上一年数据，下次启动 retry
- 不可逆动作：无（只是 mongo upsert 日期文档）

**收益**：
- **节假日不再误触发刷新**（春节 / 国庆等长假期间 scheduler 静默 + 前端 polling 跳过）
- **akshare 调用次数降低 ~30%**（按全年节假日 + 周末算，盘中实际触发时间减少）
- **未来扩展点**：所有新增 polling / scheduler job 都用同一个 `should_refresh()` helper，统一行为
- **修复隐性 bug**：当前 hardcoded 9:25–15:00 包含 11:30–13:00 午休（实际仍在刷新但这段时间 akshare 也是同一份数据，浪费）—— 本 change 暂不处理午休，但留 follow-up 接口
