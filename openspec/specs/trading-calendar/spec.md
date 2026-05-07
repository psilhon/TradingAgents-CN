# trading-calendar Specification

## Purpose
TBD - created by archiving change trading-calendar. Update Purpose after archive.
## Requirements
### Requirement: 项目铁律 — 自动刷新 MUST 仅在 A 股交易日盘中执行

本项目所有自动刷新内容（scheduler jobs / 前端 setInterval polling）MUST 仅在 A 股交易日盘中（工作日 9:30–11:30 / 13:00–15:00 且非节假日）真正执行 fetch + write，盘外（周末 / 节假日 / 非交易时段）MUST 跳过。

判断 SHOULD 通过 `TradingCalendarService.is_intraday_now()` 统一接口，不允许各 service 自行实现 hardcoded `weekday() + 时段` 判断。

#### Scenario: 工作日盘中

- **WHEN** 工作日 9:30–11:30 或 13:00–15:00 且当日 `db.trading_calendar` 含该日期文档
- **THEN** `is_intraday_now()` 返回 True
- **AND** scheduler job / 前端 polling 真正执行 fetch

#### Scenario: 周末

- **WHEN** 周六或周日任意时间
- **THEN** `is_intraday_now()` 返回 False
- **AND** scheduler job body / 前端 polling 跳过 fetch（早 return）

#### Scenario: 节假日（春节 / 国庆等）

- **WHEN** 工作日（周一–周五）但 `db.trading_calendar` 该日期文档不存在（如春节 2/17 / 国庆 10/1）
- **THEN** `is_intraday_now()` 返回 False
- **AND** 不调用 akshare，不写 mongo

#### Scenario: 工作日盘外时段

- **WHEN** 工作日 0:00–9:30 / 11:30–13:00（午休） / 15:01–23:59
- **THEN** `is_intraday_now()` 返回 False
- **AND** 不刷新

### Requirement: 交易日历 mongo 数据源

`db.trading_calendar` collection MUST 仅存储 A 股交易日（不存非交易日），schema 锁定 2 字段：

- `date`: 字符串 YYYY-MM-DD（如 "2026-01-02"）
- `year`: int（2026），冗余字段方便按年查询/同步

`date` MUST 有 unique index；`year` MUST 有普通 index 用于年度同步快速 upsert。

判断逻辑：「是否交易日」= 该日期文档是否存在（`find_one({date: X}) is not None`）。

#### Scenario: 数据完整性

- **WHEN** 系统正常运行
- **THEN** `db.trading_calendar` 当年应有约 ~250 条交易日记录（2026 实测 242 条）
- **AND** 节假日 / 周末**不**在 collection 中

#### Scenario: 数据源

- **WHEN** `sync_year(year)` 被调用
- **THEN** 调用 akshare `tool_trade_date_hist_sina()` 拉历史交易日列表（覆盖 1990–下一年）
- **AND** 按年过滤后 upsert 到 mongo
- **AND** 失败时保留旧数据，logger.warning 记录，不抛 exception

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

- **WHEN** 每年 12 月 31 日 20:00（按 backend timezone Asia/Shanghai）
- **THEN** scheduler cron job 触发 `sync_year(明年)`
- **AND** 同步成功后 mongo 含明年完整日历

### Requirement: TradingCalendarService API

`TradingCalendarService` MUST 暴露以下方法供其他模块调用：

- `is_trading_day(d: date) -> bool`：查指定日期是否交易日（带 FIFO dict 缓存 max 2048 条）
- `is_intraday_now() -> bool`：当前是否「交易日 + 盘中时段」综合判断
- `get_today_status() -> dict`：返回 `{date, is_trading_day, is_intraday, next_trading_day}`，前端使用
- `sync_year(year: int) -> dict`：拉 akshare 同步年度日历，返回 `{year, total, inserted, updated}`

`is_trading_day` 单次查询 MUST < 5ms（依赖 mongo unique index + 内存缓存）。

#### Scenario: API 性能

- **WHEN** `is_trading_day(today)` 被频繁调用（每秒多次）
- **THEN** 第一次查 mongo（< 5ms），后续命中内存缓存（< 0.1ms）

#### Scenario: API 失败降级

- **WHEN** `is_trading_day(d)` 查询时 mongo 查询异常
- **THEN** logger.warning 记录
- **AND** fallback 用 `d.weekday() < 5` 简单判断（保守降级，不识别节假日但比抛错好）
- **AND** 不抛 exception 阻塞调用方

#### Scenario: 缓存策略

- **WHEN** `is_trading_day(d)` 查询时 mongo 该年数据已 sync（count_documents > 0）
- **THEN** 结果（True 或 False）写入内存缓存
- **WHEN** mongo 该年数据未 sync（count = 0，启动初期）
- **THEN** 不缓存（避免误把"暂时为空"缓存成 false），让下次再查
