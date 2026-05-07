# portfolio-fundamentals — Tasks

> **前置依赖**：`paper-account-snapshots` 必须先 archived。本 change 的 calc_beta / calc_var 依赖账户日收益序列。

## 1. 调研现状

- [ ] 1.1 测 akshare `index_zh_a_hist(symbol="000300", period="daily", start_date, end_date)` 返回字段
- [ ] 1.2 测 akshare `stock_a_indicator_lg(symbol="002428")` 返回 PE/PB 字段（注意是 dataframe 时间序列，取最新一行）
- [ ] 1.3 numpy 已在 .venv（用于 cov / var / percentile 计算）

## 2. IndexDataService

- [ ] 2.1 新建 `app/services/index_data_service.py`
- [ ] 2.2 `sync_index_history(symbol="000300", days=365)`：akshare 拉 + upsert 到 `index_quotes_daily`
- [ ] 2.3 `get_index_returns(symbol, days)`：返回最近 N 天日收益序列（pct_chg / 100 或自算）
- [ ] 2.4 启动时 ensure_index：unique compound (symbol, date)

## 3. StockIndicatorService

- [ ] 3.1 新建 `app/services/stock_indicator_service.py`
- [ ] 3.2 `sync_indicators_for_codes(codes)`：循环调 akshare（< 100 只可接受）+ upsert 到 `stock_indicators`
- [ ] 3.3 `get_latest_indicators(codes)`：返回 `{code: {pe, pb}, ...}`
- [ ] 3.4 ensure_index unique compound (code, date)

## 4. PortfolioRiskService

- [ ] 4.1 新建 `app/services/portfolio_risk_service.py`
- [ ] 4.2 `calc_beta(user_id, days=60)`：
   - 拿 60 天账户日收益（来自 PaperPerformanceService）
   - 拿 60 天沪深 300 日收益
   - 对齐日期 + numpy.cov / var
   - 返回 `(beta, tag)`：`>1.3 高弹性 / 1.0-1.3 中高弹性 / 0.7-1.0 中性 / <0.7 防御`
- [ ] 4.3 `calc_var(user_id, confidence=0.95, days=252)`：
   - 拿 252 天账户日收益
   - 5% 分位数 × 当前账户市值
   - 返回 `(var_amount, var_pct)` 都是负数
- [ ] 4.4 `calc_weighted_pe(user_id)`：
   - 拿 paper 持仓 codes + 各自 mkt_value
   - 拿 indicators 的 pe
   - Σ(pe × mkt_value) / Σmkt_value
   - 任一 pe 缺失则跳过该 code（不影响其他）
- [ ] 4.5 `calc_weighted_pb(user_id)`：同上
- [ ] 4.6 `get_portfolio_metrics(user_id)`：聚合 4 项 + Beta tag
- [ ] 4.7 单测覆盖：
   - calc_beta：手算公式验证
   - calc_var：mock 收益分布 → 5% 分位数
   - calc_weighted_pe：mock 持仓 + indicators
   - Beta tag 4 个区间映射
   - 边界：snapshot < 2 / indicators 缺失 / HS300 空 → None

## 5. Scheduler 注册

- [ ] 5.1 `_register_portfolio_fundamentals_jobs()` in scheduler_service
- [ ] 5.2 cron: `day_of_week='mon-fri', hour=17, minute=30`（17:00 行情入库 + 30 min 缓冲）
   - 触发：sync_index_history + sync_indicators_for_codes（取自选股 ∪ 持仓 codes 并集）
- [ ] 5.3 启动时检查 `index_quotes_daily` 当年数据缺则触发同步（async）

## 6. API endpoint

- [ ] 6.1 `GET /api/paper/portfolio_metrics` 返回 `{beta: {value, tag}, var: {amount, pct}, weighted_pe, weighted_pb}`
- [ ] 6.2 鉴权 `Depends(get_current_user)`

## 7. 前端集成

- [ ] 7.1 `frontend/src/api/portfolioMetrics.ts`：interface + getMetrics()
- [ ] 7.2 `frontend/src/views/Dashboard/index.vue`：
   - 替换 4 处 Tier 4 mock 为真实数据
   - Beta tag chip 颜色映射
   - 加载失败 / null → 显示 `—`
   - 删 `// TODO: Tier 4` 注释
- [ ] 7.3 onMounted 加 `loadPortfolioMetrics()`，盘后 / 启动时刷新一次（后端数据每日盘后才更新，无需 polling）

## 8. 收口验证

- [ ] 8.1 `just ci` 全绿
- [ ] 8.2 backend 启动：日志 sync 完成 + 2 个 mongo collection 有数据
- [ ] 8.3 GET /api/paper/portfolio_metrics 返回非 null（前提：snapshot 已有 ≥ 60 天数据）
- [ ] 8.4 前端 Tier 4 字段显示真实 Beta / VaR / 加权 PE / 加权 PB
- [ ] 8.5 changelog [Unreleased] 加 entry
- [ ] 8.6 archive change → `openspec/changes/archive/2026-05-08-portfolio-fundamentals/`
- [ ] 8.7 应用 spec → `openspec/specs/portfolio-fundamentals/spec.md`
