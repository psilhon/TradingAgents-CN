## ADDED Requirements

### Requirement: index_quotes_daily collection schema

mongo collection `index_quotes_daily` MUST 持久化指数日 K 数据（本 change 仅沪深 300）。

schema：
- `symbol`: 字符串（如 "000300"）
- `date`: 字符串 YYYY-MM-DD
- `close`: 收盘价
- `pct_chg`: 涨跌幅（%）
- `open` / `high` / `low` / `volume` / `amount`: 标准 K 线字段

索引：unique compound `(symbol, date)`，普通 `symbol`。

#### Scenario: 沪深 300 历史数据

- **WHEN** scheduler 触发 `sync_index_history(symbol="000300", days=365)`
- **THEN** akshare `index_zh_a_hist` 拉最近 365 天日 K
- **AND** upsert 到 `index_quotes_daily`，约 250 条交易日记录

### Requirement: stock_indicators collection schema

mongo collection `stock_indicators` MUST 缓存「自选股 ∪ paper 持仓」codes 的 PE/PB 等估值指标。

schema：
- `code`: 6 位股票代码
- `date`: 字符串 YYYY-MM-DD（最新可用日期）
- `pe_ttm`: 滚动市盈率
- `pb`: 市净率
- `total_mv`: 总市值（可选，亿元）

索引：unique compound `(code, date)`，普通 `code`。

#### Scenario: 仅缓存目标 codes

- **WHEN** sync 触发
- **THEN** 只拉「自选股 ∪ paper 持仓」codes 的 indicator
- **AND** 不全市场拉 5500+ 只（akshare 单股调用，全市场太慢）

#### Scenario: 数据时效

- **WHEN** 工作日 17:30 cron 触发
- **THEN** 当日 indicator 数据写入
- **AND** mongo 文档 date 为最近一个交易日

### Requirement: PortfolioRiskService 数学公式

`PortfolioRiskService` MUST 实现以下 4 个核心方法，公式严格符合金融标准：

- `calc_beta(user_id, days=60) -> (beta, tag) | None`
- `calc_var(user_id, confidence=0.95, days=252) -> (amount, pct) | None`
- `calc_weighted_pe(user_id) -> float | None`
- `calc_weighted_pb(user_id) -> float | None`

#### Scenario: Beta 公式

- **GIVEN** account_returns / hs300_returns 各 60 个对齐日期
- **WHEN** calc_beta 执行
- **THEN** beta = numpy.cov(account_returns, hs300_returns)[0][1] / numpy.var(hs300_returns)
- **AND** tag 按 beta 值映射：
  - β > 1.3 → "高弹性"（红）
  - 1.0 < β ≤ 1.3 → "中高弹性"（橙）
  - 0.7 < β ≤ 1.0 → "中性"（蓝）
  - β ≤ 0.7 → "防御"（绿）

#### Scenario: Beta 数据不足

- **WHEN** account snapshot 不足 60 天
- **THEN** calc_beta 返回 None
- **AND** 前端显示 `—`

#### Scenario: VaR 历史模拟法

- **GIVEN** account_returns 252 天序列 + 当前账户 equity = E
- **WHEN** calc_var(confidence=0.95) 执行
- **THEN** var_pct = numpy.percentile(account_returns, 5)（5% 分位数）
- **AND** var_amount = E × var_pct（负数表示亏损）
- **AND** 返回 `(amount, pct)`：例 `(-4820, -0.0208)`

#### Scenario: 加权 PE 公式

- **GIVEN** 持仓 [{code, mkt_value}] + indicators {code: {pe, pb}}
- **WHEN** calc_weighted_pe 执行
- **THEN** weighted_pe = Σ(pe_i × mkt_value_i) / Σ(mkt_value_i)
- **AND** 仅纳入 pe 字段非 null 的持仓（缺 pe 的跳过）
- **AND** 全部缺失 → 返回 None

#### Scenario: 边界 — 空持仓

- **WHEN** paper 账户无任何 CN 持仓
- **THEN** calc_weighted_pe / calc_weighted_pb 返回 None
- **AND** calc_var 返回 None（无市值无意义）

### Requirement: API endpoint

提供 `GET /api/paper/portfolio_metrics` 供前端 Dashboard 使用。

返回 schema：

```json
{
  "success": true,
  "data": {
    "beta": {
      "value": 1.12,
      "tag": "中高弹性"
    },
    "var": {
      "amount": -4820,            // 元
      "pct": -0.0208              // 小数
    },
    "weighted_pe": 18.4,
    "weighted_pb": 2.1
  }
}
```

任一字段计算失败时其值为 null（前端显示 `—`）。

#### Scenario: 数据缺失部分指标

- **WHEN** 账户 snapshot 不足 60 天但有持仓 + indicators 数据
- **THEN** beta / var = null，weighted_pe / weighted_pb 仍正常计算

### Requirement: 同步频率

`portfolio-fundamentals` 数据 sync 频率：

- **沪深 300 日 K**：工作日 17:30 cron 增量同步（仅最新 1-3 天）
- **个股 indicators**：工作日 17:30 cron 同步「自选股 ∪ 持仓」codes（每 code 拉最新一条）
- **启动时检查**：`index_quotes_daily` 当年数据缺则触发全量同步

复用 capability `trading-calendar` 的工作日判断（周末 / 节假日不触发）。

#### Scenario: 周末停跑

- **WHEN** 周六 / 周日
- **THEN** sync cron 不触发（cron `day_of_week='mon-fri'`）

#### Scenario: 节假日停跑

- **WHEN** 工作日但当日非交易日（春节 / 国庆等）
- **THEN** cron job body guard `is_trading_day(today)` 返回 False，直接 return
- **AND** 不调用 akshare
