# 2.3 — stock_basic_info full_symbol invariant 守护

## Why

audit-2026-05-23 复检时初判 `stock_basic_info` 5846 docs **没有 full_symbol** —— 但深入查发现 grep 命中的 `ts_code` 字段（已废弃 alias）才是 5846 个 null，而 **`full_symbol` 字段实际全部存在且全为 `.SH/.SZ/.BJ` canonical 形式**：

```
mongo> db.stock_basic_info.countDocuments({})                                  → 5846
mongo> db.stock_basic_info.countDocuments({full_symbol: {$exists: true}})      → 5846
mongo> db.stock_basic_info.countDocuments({full_symbol: /\.(SH|SZ|BJ)$/})      → 5846
mongo> db.stock_basic_info.countDocuments({full_symbol: /\.SS$/})              → 0
```

Writer 端两个 service 都已实施：

- `app/services/basics_sync_service.py:265-280` → `_generate_full_symbol(code)` + `"full_symbol": full_symbol` 写入 doc
- `app/services/multi_source_basics_sync_service.py:259-281` → 同模式（`ts_code` 优先，缺时走 `_generate_full_symbol`）

stage 2.1 后这些 helper 也已返回 `.SH/.SZ/.BJ` canonical。

**本 stage 实质工作 = spec invariant 测试守护 + audit script**（writer 改造 + migration 不需要）。

## What Changes

### `tests/test_stock_basic_info_full_symbol.py` (新建)

- **source-level 守护**：grep `basics_sync_service.py` + `multi_source_basics_sync_service.py` 含 `"full_symbol": full_symbol` 写入；防止未来 writer refactor 漏写
- **behavior 守护**：调用 `BasicsSyncService._generate_full_symbol("600519")` 返 `"600519.SH"` 等（其它 code 类型）

### `scripts/migrations/2.3_audit_full_symbol.js` (新建)

仅 audit，不写库：

- 扫 `stock_basic_info` 内 `full_symbol` 字段缺失或不符合 `^\d{6}\.(SH|SZ|BJ)$` 的 doc 数
- 报告（无 `--write` flag 始终 dry-run only）
- 给定阈值：若缺失/异常 doc > 0 则非 0 exit，可用作 CI gate

### spec delta

`docs/specs/dataflows-schema-consistency/spec.md` Requirement「stock_basic_info 必含 full_symbol」+ Scenario **已就位**（capability spec 已含），本 sub-stage 直接落实测试守护。

## Impact

### Code 变化

| 文件 | 行数 |
|---|---|
| `tests/test_stock_basic_info_full_symbol.py` | +60 |
| `scripts/migrations/2.3_audit_full_symbol.js` | +50 (audit-only) |

### 行为变化

零变化 — writer 已就位 + 数据已 canonical。本 stage 加 spec invariant 测试 + audit script 防回归。

### 用户 / callsite

零破坏。

### 风险

低：纯测试 + audit script，不改业务代码。

## Out of Scope

- 后缀统一（stage 2.1）
- trade_date 格式（stage 2.2）
- 给现有 docs 重新生成 full_symbol（数据已 canonical，无需）
