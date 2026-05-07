# paper-account-snapshots — Tasks (archived 2026-05-08)

## 1. 调研现状

- [x] 1.1 paper_accounts schema：含 `cash`/`realized_pnl` dict 按 currency 分（CNY/HKD/USD）；`take_snapshot` 仅取 CNY
- [x] 1.2 paper_positions：`{user_id, code, market, quantity, avg_cost}`，price 通过 `_get_last_price(code, market)` 拿
- [x] 1.3 numpy 2.3.0 已在 .venv（用于 std/var/percentile）

## 2. PaperSnapshotService

- [x] 2.1 新建 `app/services/paper_snapshot_service.py`
- [x] 2.2 `take_snapshot(user_id)`：算 equity = cash[CNY] + Σ positions[CN].mkt_value，upsert 到 mongo
- [x] 2.3 `take_snapshots_for_all_users()`：遍历 paper_accounts.distinct("user_id")
- [x] 2.4 `get_snapshots(user_id, days=90)`：返回升序时间序列
- [x] 2.5 ensure_index：unique compound `(user_id, date)` + 普通 `user_id`

## 3. PaperPerformanceService

- [x] 3.1 新建 `app/services/paper_performance_service.py`
- [x] 3.2 `_calc_daily_returns` helper：(E_t / E_{t-1}) - 1，跳过 prev=0
- [x] 3.3 `calc_twrr`：连乘 (1+r) - 1，N<2 返回 None
- [x] 3.4 `calc_sharpe(rf=0.02)`：年化超额收益 / 年化波动率 ×√252，std=0/N<2 返回 None
- [x] 3.5 `calc_drawdowns`：扫一次得到 current + max
- [x] 3.6 `calc_monthly_returns`：按月分组 (month, return_pct)
- [x] 3.7 `get_overview` 聚合 + `_sample_sparkline_points` 等距 11 点
- [x] 3.8 单测 17 cases 全过：TWRR / Sharpe std=0 / drawdown V 字形 + 复杂 / monthly / sparkline

## 4. Scheduler 注册

- [x] 4.1 `_register_paper_snapshot_jobs()` in scheduler_service
- [x] 4.2 cron `day_of_week='mon-fri', hour=16, minute=0` + `max_instances=1, coalesce=True`
- [x] 4.3 启动时 `_ensure_paper_snapshot_today` async：仅交易日 + 缺则补一条

## 5. API endpoints

- [x] 5.1 `GET /api/paper/snapshots?days=N` (default 90)
- [x] 5.2 `GET /api/paper/performance` 返回 `{twrr, sharpe, current_drawdown, max_drawdown, monthly_returns, sparkline_points}`

## 6. 前端集成

- [x] 6.1 `frontend/src/api/paperPerformance.ts`：interface + getPerformance()
- [x] 6.2 Dashboard 替换 5 处 mock：sparklineLinePoints / sparklineFillPoints computed (动态 viewBox 130x50 normalize) / monthly_returns / TWRR / Sharpe / 当前 + 最大回撤
- [x] 6.3 加 formatPctSigned helper 统一格式化（0.186 → "+18.60%"）
- [x] 6.4 数据缺失（< 2 snapshots）所有字段显示 `—`

## 7. 收口验证

- [x] 7.1 `just ci` 全绿（48 unit tests passed，新增 17 个 paper_performance）
- [x] 7.2 backend 启动：日志 `Added job "paper 账户净值每日快照"` + `paper 账户快照 cron 已添加：工作日 16:00` + `启动检查：2026-05-08 已有 1 条快照`
- [x] 7.3 mongo `paper_account_snapshots` 1 条今日数据（启动 hook 触发）
- [ ] 7.4 GET /api/paper/performance 验证（依赖 ≥ 2 天数据，第一天显示 null —— 用户实际使用 N+1 天后能看到真实数字）
- [ ] 7.5 前端 Dashboard Tier 3 字段显示真实（同上：第一天「—」预期）
- [x] 7.6 `docs/CHANGELOG.md [Unreleased]` 加 entry
- [x] 7.7 archive change → `openspec/changes/archive/2026-05-08-paper-account-snapshots/`
- [x] 7.8 应用 spec → `openspec/specs/paper-account-snapshots/spec.md`
