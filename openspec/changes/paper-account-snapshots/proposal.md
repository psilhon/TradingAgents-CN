# paper-account-snapshots

> 每日 paper 账户 equity 时间序列持久化 + 性能聚合服务（TWRR / Sharpe / 当前&最大回撤 / 月度收益）—— 接管 Dashboard Tier 3 的 5 处 mock 数据。

## Why

Dashboard 模拟账户卡片当前 5 处 Tier 3 字段是 hardcoded mock：

| 字段 | mock 值 | 真实需要 |
|---|---|---|
| 90 天资产曲线 sparkline | 11 个静态 SVG 点 | 90 天每日 equity 时间序列 |
| TWRR | `+18.6%` | 时间加权收益率（排除现金注入影响） |
| Sharpe | `1.42` | 年化超额收益率 / 年化波动率 |
| 当前回撤 | `−3.2%` | (now − peak) / peak |
| 最大回撤 | `−8.5%` | max(peak_t − trough_t) / peak_t |
| 月度收益柱图 | 7 个 mock 月柱 | 按月聚合的账户收益 |

这些都依赖**账户净值时间序列**——当前 paper_accounts collection 只存当前快照，没有历史轨迹。需要每日写一条 snapshot 文档持久化。

代码中所有 5 处 mock 都标了 `// TODO: paper-account-snapshots OpenSpec change` 注释。

## What Changes

### 后端

- **新建 mongo collection `paper_account_snapshots`**：
  - schema: `{user_id, date(YYYY-MM-DD), equity, cash, positions_value, realized_pnl, unrealized_pnl}`
  - unique index on `(user_id, date)`，普通 index on `user_id`
  - 每日交易日 16:00（盘后 1 小时）+ 启动时缺当日数据自动补一条
- **新建 `app/services/paper_snapshot_service.py`**：
  - `take_snapshot(user_id) -> dict`：基于当前 paper_accounts + paper_positions 算 equity，写入 snapshot
  - `get_snapshots(user_id, days)`：返回最近 N 天时间序列
- **新建 `app/services/paper_performance_service.py`**：
  - `calc_twrr(user_id, days)`：时间加权收益率（基于 snapshot 序列）
  - `calc_sharpe(user_id, days, rf=0.02)`：年化 Sharpe（rf=2% 无风险利率默认）
  - `calc_drawdowns(user_id, days)`：返回 `{current_drawdown, max_drawdown}`
  - `calc_monthly_returns(user_id, months)`：按月聚合 `[{month, return_pct}, ...]`
  - `get_overview(user_id)`：聚合所有指标 + sparkline points
- **新建 endpoints**：
  - `GET /api/paper/snapshots?days=N` 返回时间序列
  - `GET /api/paper/performance` 返回聚合指标 + sparkline 点
- **scheduler 注册**：
  - 盘后 16:00 cron job：遍历活跃 paper users → take_snapshot
  - 启动时检查当日 snapshot 缺则补（异步 fire-and-forget）
  - 复用 `trading_calendar.is_intraday_now()` 判断（盘后兜底允许，盘外不调）

### 前端

- **新建 `frontend/src/api/paperPerformance.ts`** + interface
- **修改 `frontend/src/views/Dashboard/index.vue`**：
  - 删 `mockSparklineLine` / `mockSparklineFill` / `mockMonthBars` mock 数据
  - 调 `paperPerformanceApi.getOverview()` 获取真实数据
  - 5 处 Tier 3 字段绑定真实数据
  - 数据加载失败时 fallback 显示 `—`（不再用 mock 数字）
  - 删 `// TODO: paper-account-snapshots` 注释（5 处）

### 测试

- `tests/test_paper_snapshot_service.py`：mock paper_accounts + paper_positions，验证 snapshot 计算
- `tests/test_paper_performance_service.py`：构造时间序列 mock，验证 TWRR / Sharpe / drawdown / monthly_returns 计算
- 数学正确性单测覆盖：
  - TWRR 公式：连续期间的几何平均
  - Sharpe：年化收益超过 rf 后除以年化 σ × √252
  - drawdown 边界：单调上升 0 / 单调下降 100% / V 字形

## Out of Scope

- **历史回填**：只从今天开始记录，不补 2025/2024 历史（用户 paper 账户从今年开始的）
- **多账户分户对比**：单 user 只看自己账户
- **港股 / 美股 snapshot**：本 change 只处理 CN equity；HK/US 后续单独立项
- **按 currency 分账户曲线**：只算 CNY 总值
- **Sortino / Calmar / 信息比率**等扩展指标：先做 4 个核心
- **手动 snapshot 触发 endpoint**：仅 cron + 启动时自动；调试用 service 直接调
- **快照修复 / 删除 endpoint**：写错了从 mongo 直接修

## Impact

**改动范围**：
- 新建 `app/services/paper_snapshot_service.py`（~80 行）
- 新建 `app/services/paper_performance_service.py`（~150 行，4 个数学计算）
- 修改 `app/services/scheduler_service.py`（+30 行 job 注册 + 启动 hook）
- 修改 `app/routers/paper.py`（+30 行 2 个新 endpoint）
- 新建 `frontend/src/api/paperPerformance.ts`（~30 行）
- 修改 `frontend/src/views/Dashboard/index.vue`（替换 5 处 mock，约 −20 / +30 行）
- 新建 2 个 tests/test_*.py（共 ~150 行）

**风险**：低
- 数学计算（TWRR / Sharpe）有标准公式，单测可严格验证
- snapshot 写入失败不影响其他 job
- 启动时缺当日补一条逻辑：如果今天还没收盘也写一条 → 用户当天看 sparkline 有点
- 不可逆：无（mongo 文档可直接清）

**收益**：
- Dashboard Tier 3 字段切真实，专业感拉满
- 为后续 portfolio-fundamentals（Beta / VaR）提供日收益序列基础
- 可视化用户长期持仓表现（不仅当前快照）
- 月度柱图 + sparkline 支持"复盘"使用场景

## 依赖与时序

**前置**：capability `trading-calendar`（已落地）— scheduler job 用 `is_intraday_now()` + 交易日判断

**后续**：capability `portfolio-fundamentals` 会复用 snapshot 算账户日收益（用于 Beta 计算）
