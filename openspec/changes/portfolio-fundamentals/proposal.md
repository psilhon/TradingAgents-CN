# portfolio-fundamentals

> 持仓组合估值与风险指标：Beta（vs 沪深 300）+ VaR（历史模拟法）+ 加权 PE/PB —— 接管 Dashboard Tier 4 的 4 处 mock 数据。

## Why

Dashboard 模拟账户卡片当前 4 处 Tier 4 字段是 hardcoded mock：

| 字段 | mock 值 | 真实需要 |
|---|---|---|
| Beta | `1.12 中高弹性` | 账户日收益相对沪深 300 协方差 / 大盘方差 |
| VaR (1D, 95%) | `−¥4,820` | 历史模拟法：过去 N 天日收益 5% 分位数 × 账户市值 |
| 加权 PE | `18.4×` | Σ(PE_i × MV_i) / ΣMV_i |
| 加权 PB | `2.1×` | Σ(PB_i × MV_i) / ΣMV_i |

依赖三类外部数据（mongo 当前都没有）：

1. **沪深 300 指数日 K 历史**（akshare `index_zh_a_hist(symbol="000300")`）
2. **个股 PE / PB**（akshare `stock_a_indicator_lg(symbol)` 历史指标）
3. **账户日收益序列**（来自 `paper-account-snapshots` change，作前置依赖）

代码中所有 4 处 mock 标了 `// TODO: Tier 4 — 等外部行情/基本面数据接入` 注释。

## What Changes

### 后端

- **新建 mongo collection `index_quotes_daily`**：
  - schema: `{symbol("000300"), date, close, pct_chg, ...}`
  - unique compound `(symbol, date)`，普通 `symbol`
  - 数据源：akshare `index_zh_a_hist` 拉历史

- **新建 mongo collection `stock_indicators`**：
  - schema: `{code, date, pe_ttm, pb, total_mv, ...}`
  - unique compound `(code, date)`，普通 `code`
  - 数据源：akshare `stock_a_indicator_lg(symbol)`
  - 仅缓存「自选股 ∪ paper 持仓」codes（不存全市场，避免 5500+ × 历史天数）

- **新建 `app/services/index_data_service.py`**：
  - `sync_index_history(symbol, days=365)`：拉沪深 300 历史 K 入 mongo
  - `get_index_returns(symbol, days)`：返回最近 N 天日收益序列

- **新建 `app/services/stock_indicator_service.py`**：
  - `sync_indicators_for_codes(codes)`：拉指定股票最新 PE/PB
  - `get_latest_indicators(codes)`：返回 `{code: {pe, pb}, ...}`

- **新建 `app/services/portfolio_risk_service.py`**：
  - `calc_beta(user_id, days=60)`：账户日收益 vs 沪深 300，cov/var
  - `calc_var(user_id, confidence=0.95, days=252)`：历史模拟法 VaR
  - `calc_weighted_pe(user_id)`：基于持仓 + 指标
  - `calc_weighted_pb(user_id)`：同上
  - `get_portfolio_metrics(user_id)`：聚合 4 项 + Beta tag (`低/中低/中/中高/高弹性`)

- **新建 endpoint**：
  - `GET /api/paper/portfolio_metrics` 返回聚合指标

- **scheduler 注册**：
  - 工作日盘后 17:30 cron：sync_index_history（增量）+ sync_indicators_for_codes（自选股 ∪ 持仓）
  - 启动时检查 `index_quotes_daily` 缺当前年数据则补
  - 配 `is_intraday_now()` guard 避免周末 / 节假日触发

### 前端

- **新建 `frontend/src/api/portfolioMetrics.ts`** + interface
- **修改 `frontend/src/views/Dashboard/index.vue`**：
  - 删 4 处 Tier 4 mock（Beta / VaR / 加权 PE / 加权 PB）
  - 调 `portfolioMetricsApi.get()` 拿真实数据
  - Beta tag chip 颜色按数值映射：β>1.3 红「高弹性」/ 1.0-1.3 橙「中高弹性」/ 0.7-1.0 蓝「中性」/ <0.7 绿「防御」
  - 加载失败 → 全显 `—`
  - 删 `// TODO: Tier 4` 注释

### 测试

- `tests/test_portfolio_risk_service.py`：
  - calc_beta：mock 账户 + HS300 收益 → 验证公式 cov/var
  - calc_var：mock 收益分布 → 5% 分位数验证
  - calc_weighted_pe：mock 持仓 + indicators → 加权平均验证
  - 边界：snapshot < 2 / indicators 缺失 / HS300 数据空 → 返回 None
  - Beta tag 映射

## Out of Scope

- **多指数对比**（创业板指 / 上证 50 / 中证 500）：仅沪深 300 一个 benchmark
- **参数法 VaR**（正态假设）：仅历史模拟法
- **蒙特卡洛 VaR**：太重，本 change 不做
- **CVaR / Expected Shortfall**：扩展指标
- **Sortino / 信息比率 / 最大单日跌幅**：作 follow-up
- **港股 / 美股**：本 change 仅 A 股
- **个股 PE/PB 历史趋势**：仅取最新一日
- **行业暴露分析**（板块敞口）：作 follow-up，需要更多基础面数据

## Impact

**改动范围**：
- 新建 4 个 service（index_data / stock_indicator / portfolio_risk + 共用 helper）共 ~300 行
- 修改 `app/services/scheduler_service.py`（+30 行 sync job）
- 修改 `app/routers/paper.py`（+15 行 endpoint）
- 新建 `frontend/src/api/portfolioMetrics.ts`（~30 行）
- 修改 `frontend/src/views/Dashboard/index.vue`（替换 4 处 mock，~20 行）
- 新增 1 个 tests/test_portfolio_risk_service.py（~150 行）

**风险**：中
- akshare `stock_a_indicator_lg` 单股调用，自选股 + 持仓 < 100 只时可控；但每只股票一次 ~1s，盘后同步可能 ~1-2 min
- 沪深 300 历史 K 一次拉 365 天 ~1s，可接受
- VaR 历史模拟需至少 60 天账户 snapshot 才有意义，前 60 天显示 `—`
- akshare 接口偶尔变更字段名（已有 favorites_service 列名兼容经验）
- 数学计算 NaN 守卫：std=0 / 持仓为空 / indicator 缺失等边界要单测覆盖

**收益**：
- 账户卡片 4 处 Tier 4 切真实，专业感登顶
- 用户能"科学评估" paper 策略：β 太高？VaR 超预算？估值过高（PE > 30）？
- 为后续行业暴露 / 风险归因 / 因子分析等高级功能铺数据基础

## 依赖与时序

**前置**：
- capability `paper-account-snapshots`（**必须先落地**）— calc_beta / calc_var 依赖账户日收益序列
- capability `trading-calendar`（已落地）— scheduler guard

**时序约束**：本 change MUST 在 `paper-account-snapshots` archived 后才开始 Phase 2 实施。

**后续**：行业敞口 / 风险归因等高级 capability 可基于本 change 数据扩展。
