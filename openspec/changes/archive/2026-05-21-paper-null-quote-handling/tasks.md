## 0. Phase 1 cross-check（pre-plan-checklist 已过）

- [x] 0.1 既有项目骨架对账（CLAUDE.md / docs/ai-context/* / CHANGELOG / USAGE / .gitignore / .github/workflows）全部 ✅
- [x] 0.2 fork-patch 不动清单确认（pyproject.toml / vite.config.ts / .pre-commit-config.yaml / ci.yml / .gitignore patch 段）
- [x] 0.3 license boundary 确认（用户在本对话明确授权 `app/` + `frontend/src/` 改动）
- [x] 0.4 端口段位 + loopback 不变（本 change 不改网络配置）
- [x] 0.5 HARD-GATE 合规：本地 commit + 本地 tag，**不 push**（用户最后批准）
- [x] 0.6 guard-proprietary hook 演化为支持 `openspec/changes/.implementing` marker 文件——marker 已写 `2026-05-20-paper-null-quote-handling`

## 1. OpenSpec scaffolding — commit 1

- [ ] 1.1 创建 `openspec/changes/2026-05-20-paper-null-quote-handling/` 目录（已建）
- [ ] 1.2 写 `proposal.md`（已建）
- [ ] 1.3 写 `tasks.md`（本文件）
- [ ] 1.4 写 `specs/paper-account-snapshots/spec.md`（MODIFIED equity 公式 + ADDED Snapshot 写入闸门 Requirement）
- [ ] 1.5 写 `specs/data-quality-gate/spec.md`（MODIFIED Requirement 3，扩 2 新 Scenario）
- [ ] 1.6 commit（仅 OpenSpec 文件）

## 2. C4 — 后端 paper.py null 严格化（RED→GREEN）— commit 2

- [ ] 2.1 **RED**：写 `tests/test_paper_null_quote_contract.py`（pytest -m unit）
  - test_get_account_partial_quote_coverage：全 null `_get_last_price` → `positions_value=None`, `equity=None`, `quote_coverage.missing > 0`
  - test_get_account_full_quote_coverage：所有 quote 都有 → 行为不变（regression guard）
  - test_get_account_mixed：部分 null → `positions_value_by_currency` 不含 None；`missing_codes` 列出
  - test_list_positions_market_value_nullable：缺 quote 时 `market_value=None`（非 0）
  - 跑 `uv run pytest -m unit tests/test_paper_null_quote_contract.py` 确认 5 个 test 全 FAIL（基线）
- [ ] 2.2 **GREEN**：改 `app/routers/paper.py`
  - `get_account` (line 316)：`mkt_value = None if last is None else round(last * qty, 2)`；条件聚合 positions_value_by_currency；新增 `quote_coverage` dict 字段；equity 在 positions_value=None 时也为 None
  - `list_positions` (line 556)：`mkt = None if last is None else round(last * qty, 2)`；response item market_value 直接传 None
  - response schema Pydantic 模型更新（如适用）
- [ ] 2.3 跑 `uv run pytest -m unit tests/test_paper_null_quote_contract.py` 确认 5 个 test PASS
- [ ] 2.4 跑 `uv run pytest -m unit` 确认无既有 test 回归
- [ ] 2.5 `uvx ruff check` / `uvx ruff format --check` / `uvx pyright` 0 errors
- [ ] 2.6 commit

## 3. C5 — pnl_stream_service null 严格化 — commit 3

- [ ] 3.1 **RED**：写 `tests/test_pnl_stream_null_quote_contract.py`
  - test_compute_payload_full_null：所有 position last_price=None → payload `total_unrealized=None`, `positions_value=None`, 每个 position `market_value=None / unrealized_pnl=None`
  - test_compute_payload_mixed：部分 null → 聚合跳过 None；`quote_coverage` 字段正确
  - test_compute_payload_no_null_regression：全 quote 正常 → 数值正确
- [ ] 3.2 **GREEN**：改 `app/services/pnl_stream_service.py:104-117`
  - `mkt_value = None / unrealized = None` 替代 `0.0`
  - 聚合 `positions_value += ...` / `total_unrealized += ...` 加 None guard
  - 顶层 payload 新增 `quote_coverage`
  - position_records 字段 `market_value` / `unrealized_pnl` 保留 None
- [ ] 3.3 跑 `uv run pytest -m unit tests/test_pnl_stream_null_quote_contract.py` PASS
- [ ] 3.4 lint + typecheck 0 errors
- [ ] 3.5 commit

## 4. 写入闸门 — paper_snapshot_service partial 标志 — commit 4

- [ ] 4.1 **RED**：写 `tests/test_paper_snapshot_partial_contract.py`
  - test_take_snapshot_full_quote：所有 position 有 quote → 文档 `partial=false`, `missing_quote_codes=[]`, `positions_value` 数值正确
  - test_take_snapshot_partial_quote：部分 position 缺 quote → 文档 `partial=true`, `missing_quote_codes=[code, ...]`, `positions_value=None`, `equity=None`
  - test_take_snapshot_all_missing：所有 quote 都缺 → 同上 partial=true
  - test_backward_compat_read：写一条无 `partial` 字段的旧文档 → service 读出来按 partial=False 处理（不报错）
- [ ] 4.2 **GREEN**：改 `app/services/paper_snapshot_service.py`
  - `take_snapshot` 收集 missing_codes list
  - 文档 schema：写入时显式 `"partial": bool` + `"missing_quote_codes": list[str]`
  - `positions_value` / `equity` 在 partial=True 时写 None
  - read path 处加 backward compat：`doc.get("partial", False)` 不直接 `doc["partial"]`
- [ ] 4.3 PASS + lint + typecheck
- [ ] 4.4 commit

## 5. PaperPerformanceService 跳过 partial 日期 — commit 5

- [ ] 5.1 **RED**：扩 `tests/test_paper_snapshot_partial_contract.py`（或新 `tests/test_paper_performance_partial_skip.py`）
  - test_calc_twrr_skips_partial：snapshot 序列含 partial=true 日期 → daily_returns 不含跨这些日期的 return
  - test_calc_sharpe_skips_partial：partial 日期不参与 mean/std 计算
  - test_calc_drawdowns_skips_partial：partial 日期不计入 peak / current
  - test_calc_monthly_returns_skips_partial：partial 日期不参与月度聚合
  - test_too_few_valid_snapshots_returns_none：过滤后 < 2 时返 None / 空列表
- [ ] 5.2 **GREEN**：改 `app/services/paper_performance_service.py`
  - 每个 calc_X 方法入口先 `snapshots = [s for s in snapshots if not s.get("partial", False)]`
  - len(snapshots) < 2 时返 None / []
- [ ] 5.3 PASS + lint + typecheck
- [ ] 5.4 commit

## 6. W2 — portfolio_risk_service Beta inner-join — commit 6

- [ ] 6.1 **RED**：写 `tests/test_portfolio_risk_beta_inner_join.py`
  - test_beta_disjoint_dates_returns_none：账户日期 / 指数日期完全不重合 → Beta=None
  - test_beta_small_intersection_returns_none：交集 < 30 天 → Beta=None
  - test_beta_full_overlap_baseline：完全重合 → Beta 数值与既有实现一致（regression guard）
  - test_beta_partial_overlap_uses_intersection_only：部分重合 → 用 inner-join 序列，不补 0.0
- [ ] 6.2 **GREEN**：改 `app/services/portfolio_risk_service.py:80`
  - 替换 `aligned.append(0.0)` 兜底 → 同步过滤 account_returns 和 index_returns，仅保留交集日期
  - 交集 < 30 天 return None
- [ ] 6.3 PASS + lint + typecheck
- [ ] 6.4 commit

## 7. W3 — stocks.py K 线 OHLC nullable — commit 7

- [ ] 7.1 **RED**：写 `tests/test_stocks_kline_ohlc_nullable.py`
  - test_kline_complete_doc：mongo 文档完整 → 字段数值正确
  - test_kline_missing_open：缺 open 字段 → `item.open=None`（非 0）
  - test_kline_missing_all_ohlc：全缺 → 全字段 None
  - test_kline_missing_volume：缺 volume → `volume=None`
- [ ] 7.2 **GREEN**：改 `app/routers/stocks.py`
  - 加 helper `_safe_float(v) -> float | None: return None if v is None else float(v)`
  - line 545-549, 616-621 改用 `_safe_float(row.get("open"))` 等（无 default 0）
  - response schema 字段类型 `Optional[float]`
- [ ] 7.3 PASS + lint + typecheck
- [ ] 7.4 commit

## 8. C1 — Dashboard formatMoney + computed nullable — commit 8

- [ ] 8.1 **RED**：写 `frontend/src/utils/__tests__/format-money.spec.ts`
  - 用 vitest（如未配则用最简 ts assertion script + node 跑；项目 frontend/package.json 无 vitest，先 inspect 用什么）
  - 测试用例：`formatMoney(null)='—'`, `formatMoney(undefined)='—'`, `formatMoney(NaN)='—'`, `formatMoney(0)='0.00'`, `formatMoney(0.5)='0.50'`, `formatMoney(1234.56)='1,234.56'`
  - **若 frontend 无 test runner，task 8.1 降级为人工 review + 嵌入 dev console 验证**（在 tasks.md 末尾说明）
- [ ] 8.2 **GREEN**：改 `frontend/src/views/Dashboard/index.vue:899-902`
  - `formatMoney = (value: number | null | undefined): string => { if (value == null || Number.isNaN(value)) return '—'; return value.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',') }`
  - 提取 formatMoney 到 `frontend/src/utils/format.ts`（更易复用 + test）
- [ ] 8.3 模板里所有 `¥{{ formatMoney(...) }}` 改 `{{ formatCurrency(...) }}`（formatter 内置 ¥/$/HK$，避免 `¥—` 视觉）；或保留 `¥` 前缀但 `v-if` 守卫
- [ ] 8.4 Dashboard computed (lines 684-714) 改 nullable 返回：
  - `successRate`: 返 `number | null`，t=0 时返 null
  - `totalEquity`: 返 `number | null`
  - `positionRatio`: 返 `number | null`
  - `realizedPnl`: 返 `number | null`
  - `pnlRate`: 返 `string | null`
- [ ] 8.5 模板对应位置 `v-if` 守卫显示「—」
- [ ] 8.6 `cd frontend && npm run type-check` 0 errors
- [ ] 8.7 commit

## 9. C2 + C3 — PaperTrading HK/USD + 浮盈守卫 — commit 9

- [ ] 9.1 **GREEN**：改 `frontend/src/views/PaperTrading/index.vue:65-86`
  - HK tab 整段 `v-if="account.cash?.HKD != null"`，缺则渲染"未启用美股账户，点击启用..."占位
  - USD tab 同上
  - 内部 `?.HKD || 0` 改 `?.HKD ?? null`
- [ ] 9.2 改 lines 142-143 浮盈表达式：
  - `<template v-if="row.last_price != null">` 包裹原表达式
  - `<span v-else class="muted">—</span>`
- [ ] 9.3 `fmtAmount` 检查 null（line ~411-414 已支持，验证）
- [ ] 9.4 `frontend/src/api/paper.ts` 类型定义：position dataclass `last_price?: number | null`；account `quote_coverage?: ...`
- [ ] 9.5 `cd frontend && npm run type-check` 0 errors
- [ ] 9.6 commit

## 10. W1 — Dashboard computed fall-back nullable（已在 task 8 内）

- (与 task 8.4 合并；本节作占位记录闭环)

## 11. CHANGELOG hotfix 段 — commit 10

- [ ] 11.1 `docs/CHANGELOG.md` `[Unreleased]` 加 `### [1.3.1] - 2026-05-20 — data-truthfulness hotfix`
- [ ] 11.2 列 5 critical fixes + 3 warning fixes + 2 spec delta + 6 contract test 增量
- [ ] 11.3 commit

## 12. 验证 + 收口

- [ ] 12.1 `just ci` 通过（lint + typecheck + test 全过）
- [ ] 12.2 `scripts/check-data-truthfulness.sh` 跑全仓 0 命中（既有 grep 防线无回归）
- [ ] 12.3 `git log --oneline -20` 确认 10 个 commit 顺序符合 RED→GREEN 节奏
- [ ] 12.4 删除 `openspec/changes/.implementing` marker（自动恢复 guard-proprietary 硬拦截）
- [ ] 12.5 给出最终 finishing 报告（commit 列表 + 测试结果 + 用户决策点：是否打 v1.3.1 tag / push）

## 不在本 change 范围

- mongo 旧 snapshot 文档（v1.3.0 release 之后到本 fix 之前那段时间产生的）回填脚本 → 留 follow-up change
- `data-truthfulness:allow` 注释豁免机制扩展到后端 .py 文件 → 留 follow-up
- 前端 vitest / jest 测试框架接入 → 留 follow-up（本 change 用 type-check + 人工 review 替代前端 unit test）
- `tradingagents/` 核心层的数据源 adapter 异常吞抑反模式审计 → 已在 data-audit Phase 3 计划中

## 测试覆盖小结

| 区域 | 文件 | 触发 marker |
|---|---|---|
| paper account null contract | `tests/test_paper_null_quote_contract.py` | `@pytest.mark.unit` |
| pnl_stream null contract | `tests/test_pnl_stream_null_quote_contract.py` | `@pytest.mark.unit` |
| snapshot partial 闸门 | `tests/test_paper_snapshot_partial_contract.py` | `@pytest.mark.unit` |
| performance partial skip | `tests/test_paper_performance_partial_skip.py`（或并入上一个）| `@pytest.mark.unit` |
| Beta inner-join | `tests/test_portfolio_risk_beta_inner_join.py` | `@pytest.mark.unit` |
| K 线 OHLC nullable | `tests/test_stocks_kline_ohlc_nullable.py` | `@pytest.mark.unit` |
| formatMoney 边界 | `frontend/src/utils/__tests__/format-money.spec.ts`（或人工 review）| - |

所有 backend test 必须 `@pytest.mark.unit`，pre-push hook (`uv run --no-sync pytest -m unit`) 会阻塞 push 直到全 PASS。
