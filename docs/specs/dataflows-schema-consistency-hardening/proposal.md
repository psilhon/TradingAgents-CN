# dataflows-schema-consistency-hardening Epic

## Why

`docs/data-audit-2026-05-17.md` 报的 P0 数据陈旧问题（market_quotes 9 天前 / pre_close 100% null）后续已被 data-audit-phase3 + sina_hq 切换修复消除。复检（2026-05-23 mongoshell）发现实际剩余的 P1 是 **cross-collection schema 漂移**：

| Finding | 现状 |
|---|---|
| 同 doc 双后缀冲突 | market_quotes 同 doc 含 `full_symbol="600519.SS"` (Yahoo 风格) + `ts_code="600519.SH"` (tushare 风格) |
| 跨 collection trade_date 格式不一致 | market_quotes `"20260521"` (yyyymmdd) vs stock_daily_quotes `"2026-05-22"` (yyyy-mm-dd) |
| stock_basic_info 缺 full_symbol | 5846 docs 全无 `.suffix`（only `code`/`symbol`），跨 collection lookup 需 ad-hoc 计算 |

历史根因——akshare/baostock provider 用 `.SS` Yahoo 风格 + tushare 用 `.SH` 国内风格 + sina_hq 用第三种；9+ reader 文件用 `.replace(".SS", "")` defensive normalize 兼容。立 epic 一次性收敛 schema 到 canonical（tushare 风格 `.SH/.SZ/.BJ` + ISO 8601 trade_date）。

## What Changes

### 新建 capability spec `docs/specs/dataflows-schema-consistency/spec.md`

4 Requirement + 6 Scenario：

- **A 股交易所后缀 canonical 形式**：`.SH/.SZ/.BJ`，禁止 `.SS`
- **trade_date canonical ISO 8601 格式**：`yyyy-mm-dd`
- **stock_basic_info 必含 full_symbol**
- **dataflows 读取端简化**：移除 `.replace(".SS", "")`

### 3 个 sub-stage

#### 2.1 — 交易所后缀统一（`.SS → .SH`）

`app/services/` + `app/worker/` + `tradingagents/dataflows/providers/` 内 6 个 writer 生成位置改 `.SS → .SH`：

- `app/services/basics_sync_service.py:413`
- `app/services/multi_source_basics_sync_service.py:398`
- `app/services/stock_data_service.py:295, 373`
- `tradingagents/dataflows/providers/china/baostock.py:495`
- `tradingagents/dataflows/providers/china/akshare.py:510`

reader 端简化：9 处 `.replace(".SS", "")` 移除（保留 `.XSHE` / `.XSHG` 历史外部标签）。

migration：`scripts/migration_2.1_unify_exchange_suffix.js` 一次性 `$set` 替换 mongo 内现有 `.SS` 数据。

工作量：1 天 + migration 跑 + 验证。

#### 2.2 — trade_date 格式统一（`yyyymmdd → yyyy-mm-dd`）

market_quotes 4 个 writer 改格式 + migration。

工作量：1 天。

#### 2.3 — stock_basic_info 加 full_symbol

写库时根据 `market_info.exchange` 派生 `full_symbol`，migration 给现有 5846 docs 补字段。

工作量：半天。

## Impact

### Code 变化

总计 ~20 个文件改动（6 writer + 9 reader 简化 + 3-4 sync service + helpers + tests）。

### Spec

`docs/specs/dataflows-schema-consistency/spec.md` 新建（4 Requirement + 6 Scenario）。

### 数据 migration

3 个 mongoshell migration script（每 sub-stage 1 个）落 `scripts/migrations/`：

- `2.1_unify_exchange_suffix.js` — 替换 `.SS → .SH` 在 market_quotes / stock_basic_info / stock_daily_quotes
- `2.2_trade_date_iso.js` — 替换 yyyymmdd → yyyy-mm-dd 
- `2.3_basics_full_symbol.js` — 给 stock_basic_info 加 full_symbol

每个 script 有 dry-run mode + idempotent 重跑。

### 测试

每 sub-stage 加：

- source-level grep 守护（writer 不再生成 deprecated 形式）
- mongo-level data check（migration 后 collection 内 0 命中 deprecated 形式）

### 用户 / callsite

- 读取端无破坏（reader normalize 在 schema 统一后变 no-op，删除是清理 not 行为变更）
- LLM 提示词 / 前端展示：`.SH` 形式作为 canonical，下游可统一

### 风险

中：

- migration 是 mongo 写库，不可逆（备份/快照建议）
- 4 个 sync service 改 schema 后下次 sync 写入 canonical 形式，已有 docs 在 migration 后也统一——transition 期混合数据短暂可能
- HARD-GATE：migration 涉及 `updateMany` —— 必须明确每次 user 1-click 跑

### Push 策略

每 sub-stage 独立 commit + push + migration 由用户 1-click 跑。

## Out of Scope

- 业务逻辑修复（属各 sync service 自身 capability）
- 跨 collection foreign key 约束（mongo 无 FK，不引入 enforcement）
- 上游数据源格式调整（akshare/baostock 上游不动）
- US / HK 市场 schema 统一（本 epic 仅 A 股；US/HK 后缀分别 `.US/.HK`，已 separate collection `market_quotes_us` / `market_quotes_hk`）
