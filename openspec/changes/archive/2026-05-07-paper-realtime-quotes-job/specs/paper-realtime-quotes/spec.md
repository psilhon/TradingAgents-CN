## ADDED Requirements

### Requirement: market_quotes 写入范围 MUST 限定在自选股 ∪ paper 持仓

`RealtimeQuoteSyncService.sync_favorites_and_paper_positions` MUST 只把「自选股 codes ∪ paper 持仓 (market=CN) codes」并集**写入** `market_quotes` collection，不得整库 5500+ 只全部写入。

理由：避免 mongo 写入压力 + 让 `market_quotes` 集合保持小而准（只覆盖真正需要查的 codes）。个人用户场景下两者并集通常 < 100 只。

底层 fetch 实现 MAY 复用 `app/services/quotes_service.py` 的 `QuotesService`（用 `ak.stock_zh_a_spot_em()` 一次性拉全市场 + 30s TTL 内存缓存），其 in-memory cache 是合理优化（akshare 单次调用对 server 友好），但写到 mongo 的 codes 必须经过过滤。

#### Scenario: 自选股 + paper 持仓代码并集

- **WHEN** scheduled job 触发 `sync_favorites_and_paper_positions`
- **THEN** 收集 `db.user_favorites` 所有文档的 `favorite_stocks[].stock_code`（user-scope 不分用户）
- **AND** 收集 `db.paper_positions` 中 `market == "CN"` 的所有 `code`
- **AND** 取并集去重得到 target codes
- **AND** 调 `QuotesService.get_quotes(target_codes)` 拿行情
- **AND** 仅对 target codes 写入 `market_quotes`

#### Scenario: 禁止整库写入

- **WHEN** scheduler job 执行
- **THEN** 不得遍历 `stock_basic_info` 全部 5500+ 只 upsert 到 `market_quotes`
- **AND** 不得直接把 `QuotesService` 内存缓存里的全部 5500+ 行写入 mongo
- **AND** mongo `market_quotes` 文档总数 SHOULD ≈ 自选股数 + paper 持仓数（< 100）

#### Scenario: 单 code on-demand 不允许触发独立全市场拉取

- **WHEN** 任何代码路径（如 `_get_last_price` fallback）需要单 code 行情
- **THEN** 不得为该单 code 独立调用 `stock_zh_a_spot_em()` 触发全市场拉取
- **AND** 应等待 scheduler job 下次触发 / 复用 `QuotesService` 已有缓存

### Requirement: 刷新频率 MUST 工作日盘中每 30 秒 + 盘后每日一次

scheduler 注册的行情刷新 job MUST 满足：

- **盘中高频**：工作日 9:25–15:00 每 30 秒一次（开盘前 5 min 提前热身，覆盖到收盘 15:00）
- **盘后兜底**：工作日 17:00 一次（保留收盘价，避免盘中最后一次未拉到）
- 周末和节假日**不**触发（job body 内 `datetime.weekday() < 5` 判断）
- 30 秒颗粒 APScheduler `CronTrigger` 不支持，盘中 job MUST 用 `IntervalTrigger(seconds=30)` + job body 时间窗 guard 组合
- 防重叠：`max_instances=1` + `coalesce=True`（前一次未跑完时跳过本次触发）
- 单次执行 < 30 秒（avoid coalesce 累积）

#### Scenario: 盘中高频

- **WHEN** 工作日 9:25–15:00 任意 30 秒间隔触发
- **THEN** 真正执行 `sync_favorites_and_paper_positions`
- **AND** 单次 fetch+upsert < 30 秒完成（防止 coalesce）

#### Scenario: 盘外早 return

- **WHEN** 工作日 0:00–9:25 或 15:01–23:59
- **THEN** IntervalTrigger 仍触发，但 job body 第一行判断后直接 return
- **AND** 不调用 akshare，不写 mongo

#### Scenario: 盘后兜底

- **WHEN** 工作日 17:00
- **THEN** CronTrigger 触发一次行情刷新（拿当日收盘价）

#### Scenario: 周末停跑

- **WHEN** 周六（weekday=5）/ 周日（weekday=6）任意时间
- **THEN** IntervalTrigger 触发，job body guard 检测 weekday >= 5，直接 return
- **AND** 17:00 CronTrigger 周末不注册（`day_of_week='mon-fri'`）

#### Scenario: 防重叠

- **WHEN** 上一次 sync 还未完成（持续 > 30s），下一次 IntervalTrigger 又到
- **THEN** APScheduler 跳过本次触发（max_instances=1）
- **AND** 不并发跑两份 sync

### Requirement: market_quotes schema 锁定 5 个字段

`market_quotes` collection 文档 MUST 至少包含：

- `code`: 股票代码（字符串，如 "000776"）
- `symbol`: 与 code 相同（兼容旧调用）
- `close`: 最新收盘价（float, > 0）
- `volume`: 成交量（int，可为 None）
- `updated_at`: 最后更新时间（ISODate）

`code` 字段 MUST 有 unique index，service 启动时 `ensure_index`。

#### Scenario: upsert 路径

- **WHEN** akshare 返回某股票实时报价
- **THEN** 用 `db.market_quotes.update_one({code: X}, {$set: {...}}, upsert=True)`
- **AND** 文档至少含上述 5 字段
- **AND** 不写入 close <= 0 的记录（akshare 异常返回时）

### Requirement: 调用 akshare 行情 MUST 复用 QuotesService 的 TTL 缓存

`RealtimeQuoteSyncService` MUST 通过 `QuotesService.get_quotes(codes)` 拿行情，**不**直接调用 `ak.stock_zh_a_spot_em()`。

理由：
- 30 秒 IntervalTrigger 间隔 + QuotesService 30s TTL 完美对齐——上次 sync 拿到的全市场快照下次还在缓存里
- 避免双重内存缓存竞争
- 失败降级 / 列名兼容已经在 `QuotesService` 内部处理

`RealtimeQuoteSyncService.sync_favorites_and_paper_positions` MUST 满足：

- 单次执行总耗时 < 30 秒（防 IntervalTrigger 重叠 / coalesce 累积）
- `QuotesService.get_quotes` 失败时（返回空 dict）→ logger.warning 记录 + 直接返回，不抛
- 整体返回 `{total, fetched, updated, errors}` 状态字典

#### Scenario: 复用 QuotesService

- **WHEN** sync 需要拿行情数据
- **THEN** 调用 `get_quotes_service().get_quotes(target_codes)`
- **AND** 不直接 import akshare 或调用 `stock_zh_a_spot_em`

#### Scenario: 失败降级

- **WHEN** `QuotesService.get_quotes` 返回空 dict（akshare 失败 / 网络异常）
- **THEN** logger.warning 记录 sync 失败原因 + target_codes 数量
- **AND** 返回 `{total, fetched: 0, updated: 0, errors: total}`
- **AND** 不让异常冒泡到 scheduler（job 不能 fail）

#### Scenario: 空目标

- **WHEN** 自选股 ∪ paper 持仓 = 空集
- **THEN** sync 函数直接返回 `{total: 0, fetched: 0, updated: 0, errors: 0}`
- **AND** 不调用 `QuotesService`
- **AND** 不写 `market_quotes`
