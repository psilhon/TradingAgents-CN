# dataflows-schema-consistency Specification

## Purpose

锁定多源 (akshare / tushare / baostock / sina_hq) 写入 mongo collection (market_quotes / stock_basic_info / stock_daily_quotes / market_indices) 时 schema 的一致性约束。data-audit-2026-05-17 后续衍生发现：cross-collection schema 漂移——同 doc 内 `.SS` (Yahoo Finance / ISO 风格) vs `.SH` (tushare 国内风格) 后缀共存，trade_date 跨 collection 格式不统一 (`"20260521"` vs `"2026-05-22"`)，stock_basic_info 缺 `full_symbol` 字段。

本 capability 由 `dataflows-schema-consistency-hardening` epic 起头，分 3 stage 收敛：

- **2.1 交易所后缀统一**：canonical `.SH/.SZ/.BJ`（tushare 风格），移除所有 `.SS` 生成 + 简化 reader 端 `.replace(".SS", "")` defensive code
- **2.2 trade_date 格式统一**：canonical `"yyyy-mm-dd"` (ISO 8601)，跨 collection 一致
- **2.3 stock_basic_info 加 full_symbol**：与其他 collection schema 对齐

不在范围：业务逻辑正确性、cache 层契约、HTTP reliability。

## Requirements

### Requirement: A 股交易所后缀 canonical 形式

`tradingagents/dataflows/` + `app/services/` + `app/worker/` 所有写库代码 MUST 用 `.SH` (上海) / `.SZ` (深圳) / `.BJ` (北京) 后缀，禁止 `.SS` (Yahoo Finance / ISO 风格)。

**理由**：

- tushare 是核心数据源，原生返回 `.SH/.SZ` 风格
- 9+ reader 文件已用 `.replace(".SS", "")` 做 defensive normalize（表明 `.SS` 是 reader 不想处理的"杂质"）
- ISO 6166 / Yahoo `.SS` 风格仅在导出 / 外部 API 兼容时使用，不应入库

允许例外：

- 历史 `.XSHE` (深圳 ISO) / `.XSHG` (上海 ISO) tag 在 unified_news_tool 等下游消费的 normalize 链可保留（这些是行业标准 ISIN-style，与本约束正交）

#### Scenario: 写库代码 grep 无 `.SS` 后缀生成

- **WHEN** 在 `app/services/` + `app/worker/` + `tradingagents/dataflows/providers/` 全目录 grep `f".*\\.SS"` / `"\\.SS"` / `+ '\\.SS'` 等字面后缀拼接
- **THEN** 命中数 MUST = 0（除测试 / 注释 / docstring 内字面引用）
- **AND** 所有生成后缀的位置 MUST 用 `.SH` / `.SZ` / `.BJ`

#### Scenario: mongo collections 内 `.SS` 后缀实际数据 = 0

- **WHEN** 跑 migration 后 `db.market_quotes.countDocuments({full_symbol: /\.SS$/})`
- **THEN** MUST = 0
- **AND** 同样 `db.stock_basic_info` / `db.stock_daily_quotes` 内 `.SS` 后缀计数 MUST = 0

#### Scenario: 同 doc 不存在 .SS / .SH 双后缀字段冲突

- **WHEN** 任一 market_quotes doc 同时含 `full_symbol` 和 `ts_code` 字段
- **THEN** 两个字段的后缀 MUST 相同（`.SH` / `.SZ` / `.BJ`），不允许一个 `.SS` 一个 `.SH`

### Requirement: trade_date canonical ISO 8601 格式

所有 mongo collection 内 `trade_date` 字段 MUST 用 `"yyyy-mm-dd"` (ISO 8601 dash) 格式，禁止 `"yyyymmdd"` (无 dash 8-digit) 形式。

**理由**：

- ISO 8601 是国际标准，可直接 `datetime.strptime("%Y-%m-%d")`
- stock_daily_quotes 已用 ISO 格式（5.5M+ docs），market_quotes 不同步导致 join / aggregate 需额外 normalize
- `db.collection.find({trade_date: "2026-05-22"})` 比 `"20260522"` 可读性高

允许例外：

- 数据源 raw 返回值（tushare API 用 yyyymmdd / akshare 用 yyyy-mm-dd 等）—— writer 入库前 MUST normalize

#### Scenario: 写库代码统一 trade_date 格式

- **WHEN** 任一 writer 写入 `trade_date` 字段
- **THEN** 字符串值 MUST 匹配正则 `^\d{4}-\d{2}-\d{2}$`
- **AND** MUST NOT 匹配 `^\d{8}$` (无 dash 形式)

#### Scenario: mongo collections trade_date 实际数据格式一致

- **WHEN** 跑 migration 后 `db.market_quotes.countDocuments({trade_date: /^\d{8}$/})`
- **THEN** MUST = 0
- **AND** 同样 `db.stock_basic_info` / `db.market_indices` 内 yyyymmdd 形式计数 MUST = 0

### Requirement: stock_basic_info 必含 full_symbol

`stock_basic_info` collection 每 doc MUST 含 `full_symbol` 字段（`.SH/.SZ/.BJ` 后缀）—— 与 `market_quotes` / `stock_daily_quotes` schema 对齐，让跨 collection join / lookup 可走单一 key。

理由：

- 当前 5846 docs 全无 dot 后缀（grep 验证），跨 collection 查询需 ad-hoc `code + market` 计算
- 用户实际 query 路径都期望 `full_symbol` (`SELECT * FROM stock_basic_info WHERE full_symbol IN [...]`)
- 写库代码已经能拿到交易所信息（`market_info.exchange`），加 field 是 schema 对齐 not 业务变更

#### Scenario: stock_basic_info schema 含 full_symbol

- **WHEN** `db.stock_basic_info.countDocuments({full_symbol: {$exists: true, $regex: /^\d{6}\.(SH|SZ|BJ)$/}})`
- **THEN** MUST == `db.stock_basic_info.countDocuments({})`（每 doc 都有）

### Requirement: dataflows 读取端简化（移除 .replace(".SS", "")）

writer 端统一 `.SH/.SZ/.BJ` 后，reader 端 `.replace(".SS", "")` defensive normalize 可移除（保留 `.XSHE/.XSHG` 等历史外部标签的 normalize）。

#### Scenario: reader 端简化

- **WHEN** 在 `tradingagents/` 全目录 grep `.replace(".SS", "")` 命中
- **THEN** stage 2.1 完成后 MUST = 0（writer 端已统一，reader 无需 defensive）
- **AND** `.replace(".XSHE", "")` / `.replace(".XSHG", "")` 等外部标签 normalize MAY 保留
