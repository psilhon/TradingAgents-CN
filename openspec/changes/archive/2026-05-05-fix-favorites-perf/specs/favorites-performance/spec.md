## ADDED Requirements

### Requirement: favorites GET 不得同步调用外部数据源 API

`GET /api/favorites/` MUST 完全依赖 mongo collection（`user_favorites` / `users.favorite_stocks` / `stock_basic_info` / `market_quotes`），**不得**在请求路径上同步调用 AKShare / Tushare / 等外部数据源 API。

`market_quotes` 中没有的 stock_code，`current_price` / `change_percent` 字段返回 `None`，前端显示 `-`。worker 后台（`quotes_ingest_service`）按 30s 间隔自动 sync `market_quotes`，下次 GET 自动可用。

#### Scenario: favorites GET 性能 SLO

- **WHEN** 用户有 N 个自选股（N < 50）
- **AND** GET `/api/favorites/`
- **THEN** 响应耗时 < 2s（即使 N 个全部不在 `market_quotes`）
- **AND** 不触发 AKShare `stock_zh_a_spot_em` 全市场拉取
- **AND** backend log 不含 "AKShare spot 拉取完成" 来自 favorites trace_id

#### Scenario: 新加的自选股 current_price 为 None

- **WHEN** 用户刚添加新自选股 X
- **AND** worker 还未 sync X 到 `market_quotes`（< 30s 内）
- **AND** GET `/api/favorites/`
- **THEN** 返回包含 X 的列表
- **AND** X 的 `current_price` 为 `None`（前端显示 `-`）
- **AND** 30s 后再 GET，X 的 `current_price` 自动有值（worker 已 sync）

#### Scenario: frontend 雪崩不再触发 backend 慢路径

- **WHEN** frontend 在短时间发起 10+ GET `/api/favorites/`（用户多 tab / 重试）
- **THEN** 每个请求耗时 < 2s
- **AND** backend 不出现 60s 串行 lock 等待
