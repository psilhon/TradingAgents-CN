## ADDED Requirements

### Requirement: 项目铁律 — 自动刷新 MUST 仅在 A 股交易日盘中执行

本项目所有自动刷新内容（scheduler jobs / 前端 setInterval polling）MUST 仅在 A 股交易日盘中（工作日 9:25–15:00 且非节假日）真正执行 fetch + write，盘外（周末 / 节假日 / 非交易时段）MUST 跳过。

判断 SHOULD 通过 `TradingCalendarService.is_intraday_now()` 统一接口，不允许各 service 自行实现 hardcoded `weekday() + 时段` 判断。

#### Scenario: 工作日盘中

- **WHEN** 工作日 9:25–15:00 且当日 `db.trading_calendar.is_trading == true`
- **THEN** `is_intraday_now()` 返回 True
- **AND** scheduler job / 前端 polling 真正执行 fetch

#### Scenario: 周末

- **WHEN** 周六或周日任意时间
- **THEN** `is_intraday_now()` 返回 False
- **AND** scheduler job body / 前端 polling 跳过 fetch（早 return）

#### Scenario: 节假日（春节 / 国庆等）

- **WHEN** 工作日（周一–周五）但 `db.trading_calendar.is_trading == false`（如春节假期 2/15）
- **THEN** `is_intraday_now()` 返回 False
- **AND** 不调用 akshare，不写 mongo

#### Scenario: 工作日盘外时段

- **WHEN** 工作日 0:00–9:25 或 15:01–23:59（非盘中时段）
- **THEN** `is_intraday_now()` 返回 False
- **AND** 不刷新

### Requirement: 交易日历 mongo 数据源

`db.trading_calendar` collection MUST 存储 A 股完整交易日历，schema 锁定 3 字段：

- `date`: 字符串 YYYY-MM-DD（如 "2026-01-02"）
- `is_trading`: bool（true=交易日，false=休市/节假日/周末）
- `year`: int（2026），冗余字段方便查询

`date` MUST 有 unique index；`year` MUST 有普通 index 用于年度同步快速 upsert。

#### Scenario: 数据完整性

- **WHEN** 系统正常运行
- **THEN** `db.trading_calendar` 当年应有 365 / 366 条记录（含交易日 + 非交易日），其中 is_trading=true 约 ~250 条

#### Scenario: 数据源

- **WHEN** `sync_year(year)` 被调用
- **THEN** 调用 akshare `tool_trade_date_hist_sina()` 拉历史交易日列表
- **AND** 把当年所有日期（包括非交易日）upsert 到 mongo
- **AND** 失败时保留旧数据，logger.warning 记录

### Requirement: 启动时与年度自动同步

`TradingCalendarService` MUST 满足：

- **启动时检查**：backend 启动钩子检查 `db.trading_calendar` 是否有当年 + 下一年（如可能）数据；缺失则 `asyncio.create_task` 异步同步（不阻塞启动）
- **年度同步**：`CronTrigger(month=12, day=31, hour=20)` 每年 12/31 晚上 20:00 同步下一年日历
- **手动同步入口**：service 提供 `sync_year(year: int)` 方法供手动触发 / 测试

#### Scenario: 启动时缺当年数据

- **WHEN** backend 启动
- **AND** `db.trading_calendar.count_documents({year: 2026}) == 0`
- **THEN** 启动钩子触发 `asyncio.create_task(sync_year(2026))` 异步同步
- **AND** 不阻塞 FastAPI 启动

#### Scenario: 12/31 年度自动同步

- **WHEN** 每年 12 月 31 日 20:00（任意时区，按 backend timezone）
- **THEN** scheduler cron job 触发 `sync_year(明年)`
- **AND** 同步成功后 mongo 含明年完整日历

### Requirement: TradingCalendarService API

`TradingCalendarService` MUST 暴露以下方法供其他模块调用：

- `is_trading_day(d: date) -> bool`：查指定日期是否交易日（带 LRU 内存缓存 TTL 1 小时）
- `is_intraday_now() -> bool`：当前是否「交易日 + 盘中时段」综合判断
- `get_today_status() -> dict`：返回 `{date, is_trading_day, is_intraday, next_trading_day}`，前端使用
- `sync_year(year: int) -> dict`：拉 akshare 同步年度日历，返回 `{year, total, inserted, updated}`

`is_trading_day` 单次查询 MUST < 5ms（依赖 mongo unique index + 内存缓存）。

#### Scenario: API 性能

- **WHEN** `is_trading_day(today)` 被频繁调用（每秒多次）
- **THEN** 第一次查 mongo（< 5ms），后续 1 小时内命中内存缓存（< 0.1ms）

#### Scenario: API 失败降级

- **WHEN** `is_trading_day(d)` 查询时 mongo 没有该日期记录（异常情况）
- **THEN** logger.warning 记录
- **AND** fallback 用 `weekday() < 5` 简单判断（保守降级）
- **AND** 不抛 exception 阻塞调用方
