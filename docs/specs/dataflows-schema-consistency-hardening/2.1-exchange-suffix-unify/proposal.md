# 2.1 — 交易所后缀统一（`.SS → .SH`）

## Why

A 股交易所后缀全仓存在两种风格共存：

- **`.SS` (Yahoo Finance / ISO 6166)** — `app/services/basics_sync_service.py:413` / `multi_source_basics_sync_service.py:398` / `stock_data_service.py:295/373` + `tradingagents/dataflows/providers/china/baostock.py:495` + `akshare.py:510` 共 **6 个 writer** 主动生成
- **`.SH` (tushare 国内主流)** — tushare adapter 等 writer 用，也是 mongo 内 `ts_code` 字段的实际值

漂移症状：**market_quotes 同 doc 内 `full_symbol="600519.SS"` + `ts_code="600519.SH"` 同时存在**（mongo shell 实测确认）。下游 9 个 reader 用 `.replace(".SS", "")` defensive normalize 兼容（`tradingagents/tools/unified_news_tool.py:125,212` / `agents/utils/agent_utils.py:1186,1229` / `utils/news_filter_integration.py:150,158` / `dataflows/news/realtime_news.py:324,724`）。

## What Changes

### Writer 端（6 处 `.SS → .SH`）

| 文件 | line | 改动 |
|---|---|---|
| `app/services/basics_sync_service.py` | 413 | `f"{code}.SS"` → `f"{code}.SH"` |
| `app/services/multi_source_basics_sync_service.py` | 398 | 同 |
| `app/services/stock_data_service.py` | 295, 373 | 同 |
| `tradingagents/dataflows/providers/china/baostock.py` | 495 | 同 |
| `tradingagents/dataflows/providers/china/akshare.py` | 510 | 同 |

每处的上下文是上海证券交易所映射 — 600/601/603/688 开头股票码统一 → `.SH`。深圳已经在用 `.SZ`，北京已经在用 `.BJ`。

### Reader 端（9 处 `.replace(".SS", "")` 移除）

writer 统一后 reader 不再需要 defensive，简化：

| 文件 | 处理 |
|---|---|
| `tradingagents/tools/unified_news_tool.py:125, 212` | 删 `.replace(".SS", "")` |
| `tradingagents/agents/utils/agent_utils.py:1186, 1229` | 删 `.replace(".SS", "")` |
| `tradingagents/utils/news_filter_integration.py:150, 158` | 从 suffix 检查列表删 `.SS` + 删 `.replace(".SS", "")` |
| `tradingagents/dataflows/news/realtime_news.py:324, 724` | 删 `.replace(".SS", "")` + 从 list 删 `.SS` |

保留：`.XSHE` / `.XSHG` 历史外部标签 normalize（与 ISO ISIN style 兼容，仍可能从外部 input 流入）。

### Migration script

`scripts/migrations/2.1_unify_exchange_suffix.js` mongoshell 脚本：

```javascript
// dry-run mode by default; pass --eval "DRY_RUN=false; load(...)" to commit
const DRY_RUN = (typeof DRY_RUN !== "undefined") ? DRY_RUN : true;

print("=== 2.1 Migration: .SS → .SH ===");
print("DRY_RUN:", DRY_RUN);

for (const coll of ["market_quotes", "stock_basic_info", "stock_daily_quotes"]) {
  for (const field of ["full_symbol", "ts_code", "symbol"]) {
    const matchCount = db[coll].countDocuments({[field]: /\.SS$/});
    if (matchCount === 0) continue;
    print(`  ${coll}.${field}: ${matchCount} docs with .SS suffix`);
    if (!DRY_RUN) {
      const result = db[coll].updateMany(
        {[field]: /\.SS$/},
        [{$set: {[field]: {$concat: [
          {$substr: ["$" + field, 0, {$subtract: [{$strLenCP: "$" + field}, 3]}]},
          ".SH"
        ]}}}]
      );
      print(`    updated: ${result.modifiedCount}`);
    }
  }
}
print("Done.");
```

dry-run 默认 + idempotent（重跑无副作用）。HARD-GATE：用户 1-click 显式跑 `mongosh ... --eval "DRY_RUN=false; load('scripts/migrations/2.1_unify_exchange_suffix.js')"`。

### 测试

`tests/test_exchange_suffix_unify.py` 新建：

- **source-level grep**：6 writer 文件不含 `.SS` 字面生成 + 9 reader 文件不含 `.replace(".SS", "")`
- **行为测试**：
  - mock akshare.py / baostock.py 的 `_to_baostock_code` / `_get_full_symbol` 助手，断 600519 → `"600519.SH"`（非 `.SS`）
  - basics_sync 对 600 开头 code 返 `.SH` 后缀

## Impact

### Code 变化

| 类别 | 文件数 | 净行数 |
|---|---|---|
| Writer 改 `.SS → .SH` | 6 | 0（字符替换） |
| Reader 简化删 `.replace` | 4 文件 / 9 处 | -9 |
| Migration script | 1 (`scripts/migrations/`) | +40 |
| 测试 | 1 (`tests/`) | +60 |

合计 ~12 个文件改动，净 +90 行。

### 行为变化

- writer 写入：所有 A 股上海 code → `.SH` (canonical)
- reader 读取：移除 defensive normalize，依赖 schema invariant
- 跨 collection lookup：同后缀，可走单一 key
- LLM / 前端：拿到 canonical `.SH` 形式，不再需要 case-by-case 处理

### 用户 / callsite

零破坏：

- reader 简化是删除冗余代码，没有新行为
- `.SS` → `.SH` 是 schema invariant 不破——历史 `.SS` 数据经 migration 已统一

### 风险

中：

- migration 是 mongo 写库，**不可逆**——必须先 dry-run 验证 matchCount，再用户 1-click 跑 production
- 漏掉一个 reader normalize 删除：会有 reader 期望 `.SS` 但 collection 全是 `.SH` —— 测试 + grep 守护

## Out of Scope

- trade_date 格式 (stage 2.2)
- stock_basic_info full_symbol (stage 2.3)
- US / HK 后缀（separate collection / 不同 suffix domain）
- `.XSHE` / `.XSHG` 历史外部标签（保留兼容）
