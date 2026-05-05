## Why

`docs/code-review-2026-05-05.md` 第 2 个 critical 发现：226 个 test 文件中标 `unit` marker 的 = **0 个**，pre-commit hook `pytest -m unit` 永远 collect 0 测试 → exit 5（被 wrapper 视为合法）→ **测试体系实际完全不在 CI 流水线里**。

review 推荐 10 个候选纯 mock 文件。**实测**：5 个 fully passing 立即标 unit；剩余 5 个含 stale mock 失败（mock 行为已与当前 service 实现漂移），不在本 change 修复——作为 follow-up backlog 立。

## What Changes

- **MODIFIED** 5 个 fully-passing test 文件顶部加 `pytestmark = pytest.mark.unit`：
  - `tests/middleware/test_trace_id.py` (1 test)
  - `tests/services/test_screening_roe_field.py` (2 tests)
  - `tests/test_provider_keys.py` (5 tests)
  - `tests/test_normalize_provider_keys_script.py` (2 tests)
  - `tests/unit/tools/analysis/test_indicators_uil.py` (2 tests)
  - **共 12 个 unit test，pre-commit hook `pytest -m unit` 从 collect 0 → 12 passed**
- **MODIFIED** `lint-policy` spec：新增 requirement "纯 mock / 纯函数 test 必须显式标 unit"

### 不在本 change 修复（follow-up backlog）

5 个 stale mock 失败 test 文件——审计标"纯 mock"成立，但 mock 行为已与当前 service 漂移：
- `tests/dataflows/test_realtime_metrics.py`：`MockDB` 缺 `market_quotes` / `stock_basic_info` 属性
- `tests/services/test_quotes_backfill.py`：`_FakeColl` 缺 `find` 方法
- `tests/services/test_quotes_ingestion_and_enrichment.py`：同类 mock drift
- `tests/services/test_scheduler_quotes_job.py`：同类 mock drift
- `tests/test_tushare_unified/test_tushare_sync_service.py`：部分 test mock drift

这些是**真 bug**——mock 漂移意味着 service 实现已变更但 test 未跟上，应作 `tests-fix-stale-mocks` change 单独修。

## Capabilities

### Modified Capabilities

- `lint-policy`：新增 unit-marker 适用判据 + scenario

## Impact

**改动文件**：5 个 test 文件 + 1 个 spec
**风险**：低——只加 marker
**收益**：pre-commit pytest hook 从"collect 0"→ 实际跑 12 个 unit test
