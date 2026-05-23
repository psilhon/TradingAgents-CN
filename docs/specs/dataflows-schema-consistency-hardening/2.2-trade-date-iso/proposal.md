# 2.2 — trade_date 格式统一（yyyymmdd → yyyy-mm-dd ISO 8601）

## Why

跨 collection trade_date 格式不一致（mongo shell 实测）：

| Collection | trade_date 格式 | 写入者 |
|---|---|---|
| `market_quotes` | `"20260521"` (yyyymmdd, 8-digit) | `quotes_ingestion_service.py` |
| `stock_daily_quotes` | `"2026-05-22"` (yyyy-mm-dd, ISO) | tushare/akshare provider |
| `stock_basic_info` | (varies / `last_trade_date` field) | basics_sync_service |

下游 reader 需要按 collection 用不同 parser → 跨 collection join / aggregate 需要 ad-hoc normalize。

**canonical 选 yyyy-mm-dd (ISO 8601)**：

- 国际标准，直接 `datetime.strptime("%Y-%m-%d")` 可解析
- stock_daily_quotes 5.5M+ docs 已用 ISO 形式（按数据量重力归位 ISO）
- mongo 端 sort / range 字典序与时间序一致（yyyymmdd 也能但 ISO 更易读）

**保留 yyyymmdd 的位置**：tushare API 输入参数（`api.daily_basic(trade_date="20260521")` 是上游 API 约束）—— 我们只统一**入库 schema**，不破上游 API 调用。

## What Changes

### `app/services/quotes_ingestion_service.py`

- 加 helper `_to_iso_date(raw: str) -> str` —— 接受 yyyymmdd / yyyy-mm-dd / datetime，统一返 yyyy-mm-dd
- `_bulk_upsert` 内调 `_to_iso_date(trade_date)` 后写入 mongo
- 4 处 `strftime("%Y%m%d")` 保留（这些值用于 fallback `trade_date` 计算，传入 `_bulk_upsert` 后再 normalize；保留 yyyymmdd 形式因为 manager `find_latest_trade_date_with_fallback()` 也是 yyyymmdd（tushare API 兼容））

### Migration script `scripts/migrations/2.2_trade_date_iso.js`

- 扫 `market_quotes` (含可能其它 collection) `trade_date` 字段，匹配 `^\d{8}$` (yyyymmdd) 模式
- aggregation pipeline `$concat` 把 `"20260521"` → `"2026-05-21"`
- dry-run default + sanity check + idempotent

### spec delta

`docs/specs/dataflows-schema-consistency/spec.md` Requirement「trade_date canonical ISO 8601 格式」+ 2 个 Scenario **已就位**（capability spec 已包含），本 sub-stage 直接落实。

## Impact

### Code 变化

| 文件 | 行数变化 |
|---|---|
| `quotes_ingestion_service.py` | +12（helper + 1 行调用） |
| `scripts/migrations/2.2_trade_date_iso.js` | +60 (new) |
| `tests/test_trade_date_iso.py` | +90 (new) |

### 行为变化

- market_quotes 写入：每条 doc trade_date 是 yyyy-mm-dd（如 `"2026-05-21"`）
- mongo collections 跨 collection trade_date 格式一致
- 跨 collection join 无需 ad-hoc normalize：`db.market_quotes.find({trade_date: "2026-05-21"})` 直接命中

### 用户 / callsite

零破坏：

- tushare API 调用保持 yyyymmdd 输入（上游约束不变）
- mongo reader 取 yyyy-mm-dd 字段（与现有 `stock_daily_quotes` 一致）
- 前端展示 / LLM prompt 不区分（均为字符串）

### 风险

低-中：

- migration 数据写入不可逆 — 备份建议 / dry-run 验证
- 漏 normalize 一处 → 新 docs yyyymmdd 形式入库，违反 spec scenario
- mongo aggregation pipeline `$concat` 在 5854 docs 上跑很快，不会卡库

## Out of Scope

- 后缀统一（stage 2.1）
- stock_basic_info full_symbol (stage 2.3)
- tushare API 输入参数格式（保持上游 yyyymmdd 约定）
