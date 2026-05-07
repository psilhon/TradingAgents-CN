## ADDED Requirements

### Requirement: 实时行情刷新范围 MUST 限定在自选股 ∪ paper 持仓

`RealtimeQuoteSyncService.sync_favorites_and_paper_positions` MUST 只刷「自选股 codes ∪ paper 持仓 codes」并集，禁止全市场刷。

理由：避免 akshare rate limit + 降低 mongo 写入压力。个人用户场景下两者并集通常 < 100 只。

#### Scenario: 自选股 + paper 持仓代码并集

- **WHEN** scheduled job 触发 `sync_favorites_and_paper_positions`
- **THEN** 收集 `db.user_favorites` 中所有用户的股票代码（user-scope 不分用户）
- **AND** 收集 `db.paper_positions` 中所有持仓代码
- **AND** 取并集去重
- **AND** 仅对该集合调 akshare 批量行情接口

#### Scenario: 禁止刷全市场

- **WHEN** 任何代码路径需要实时行情
- **THEN** 不得调用 akshare 全市场快照接口（`stock_zh_a_spot()` 或 `stock_zh_a_spot_em()` 不带过滤）
- **AND** 不得遍历 `stock_basic_info` 全部 5500+ 只入 `market_quotes`

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

### Requirement: akshare 调用 MUST batch + timeout + 失败降级

调用 akshare 实时行情 MUST：

- 按批次切分，单批 ≤ 50 只
- 每批 timeout 30s
- 单批失败 → log warning，跳过该批，继续下一批（不阻塞 scheduler，不抛）
- 整体失败统计返回 `{total, fetched, updated, errors}` 字典

#### Scenario: rate limit 降级

- **WHEN** akshare 单批调用抛异常或超时
- **THEN** logger.warning 记录 batch codes + error
- **AND** 跳过本批继续下一批
- **AND** 不让异常冒泡到 scheduler（job 不能 fail）

#### Scenario: 空目标

- **WHEN** 自选股 ∪ paper 持仓 = 空集
- **THEN** sync 函数直接返回 `{total: 0, fetched: 0, updated: 0, errors: 0}`
- **AND** 不调用 akshare
- **AND** 不写 market_quotes
