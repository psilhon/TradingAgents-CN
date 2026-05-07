# paper-account-snapshots — Tasks

## 1. 调研现状

- [ ] 1.1 确认 paper_accounts schema（已知含 cash dict / realized_pnl）+ 当前 user_id 列表
- [ ] 1.2 确认 paper_positions 字段（已知，price 通过 _get_last_price 拿）
- [ ] 1.3 评估 numpy 是否已在 .venv（用于 std/var 计算）

## 2. PaperSnapshotService

- [ ] 2.1 新建 `app/services/paper_snapshot_service.py`
- [ ] 2.2 实现 `take_snapshot(user_id) -> dict`：
   - 算 equity = cash[CNY] + sum(positions[CN].quantity × last_price)
   - upsert 到 `paper_account_snapshots`，主键 `(user_id, date_utc8)`
- [ ] 2.3 实现 `take_snapshots_for_all_users()`：遍历 paper_accounts collection 所有 user
- [ ] 2.4 实现 `get_snapshots(user_id, days)`：返回近 N 天 [{date, equity, cash, positions_value}, ...]
- [ ] 2.5 启动时 ensure_index：unique on (user_id, date) + 普通 on user_id

## 3. PaperPerformanceService

- [ ] 3.1 新建 `app/services/paper_performance_service.py`
- [ ] 3.2 `calc_daily_returns(snapshots)` helper：从 equity 序列算日收益率 r_t = (E_t / E_{t-1}) - 1
- [ ] 3.3 `calc_twrr(snapshots)`：连乘 (1 + r_t) − 1，返回累计收益率
- [ ] 3.4 `calc_sharpe(snapshots, rf=0.02)`：年化超额收益 / 年化波动率
   - mean(r) × 252 − rf 除以 std(r) × sqrt(252)
   - 若 std = 0 返回 None
- [ ] 3.5 `calc_drawdowns(snapshots)`：扫一次得到 `{current_drawdown, max_drawdown}`
- [ ] 3.6 `calc_monthly_returns(snapshots)`：按月分组 → 每月 return = (E_last / E_first) − 1，返回 [{month: "2026-04", return_pct: 4.8}, ...]
- [ ] 3.7 `get_overview(user_id)` 聚合 + sparkline 取 90 天 equity 等距 11 点
- [ ] 3.8 单测覆盖数学正确性：
   - 边界：0 snapshot / 1 snapshot 返回 None
   - TWRR：[100, 110, 121] → 21%
   - Sharpe：std=0 case
   - drawdown：单调升 / 单调降 / V 字形

## 4. Scheduler 注册

- [ ] 4.1 `_register_paper_snapshot_jobs()` in `scheduler_service.py`
- [ ] 4.2 cron: `day_of_week='mon-fri', hour=16, minute=0`（盘后 1h，等行情入库稳定）
   - 配 `max_instances=1, coalesce=True`
- [ ] 4.3 启动时 ensure_index + 检查当日 snapshot 缺则触发（仅交易日，async）

## 5. API endpoints

- [ ] 5.1 `GET /api/paper/snapshots?days=N` (default 90)
- [ ] 5.2 `GET /api/paper/performance` 返回 `{twrr, sharpe, current_drawdown, max_drawdown, monthly_returns, sparkline_points}`
- [ ] 5.3 路由注册（已有 paper router 直接加 endpoint）

## 6. 前端集成

- [ ] 6.1 `frontend/src/api/paperPerformance.ts`：interface + `getPerformance()`
- [ ] 6.2 `frontend/src/views/Dashboard/index.vue`：
   - 替换 mockSparklineLine / mockSparklineFill 为 sparkline_points 渲染
   - 替换 mockMonthBars 为 monthly_returns
   - TWRR / Sharpe / 当前&最大回撤 KPI 绑真实数据
   - 数据缺失（404 / null）→ 显示 `—`
- [ ] 6.3 删 5 处 `// TODO: paper-account-snapshots OpenSpec change` 注释

## 7. 收口验证

- [ ] 7.1 `just ci` 全绿
- [ ] 7.2 backend 启动：日志显示 snapshot job 注册 + 启动时补当日
- [ ] 7.3 mongo `paper_account_snapshots` 至少 1 条今日数据
- [ ] 7.4 GET /api/paper/performance 返回非 null
- [ ] 7.5 前端 Dashboard 显示真实 TWRR / Sharpe / drawdown
- [ ] 7.6 `docs/CHANGELOG.md [Unreleased]` 加 entry
- [ ] 7.7 archive change → `openspec/changes/archive/2026-05-08-paper-account-snapshots/`
- [ ] 7.8 应用 spec → `openspec/specs/paper-account-snapshots/spec.md`
