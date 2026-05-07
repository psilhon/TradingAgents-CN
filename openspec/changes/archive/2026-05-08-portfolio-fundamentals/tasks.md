# portfolio-fundamentals — Tasks (archived 2026-05-08)

## 1. 调研现状

- [x] 1.1 akshare `index_zh_a_hist(symbol, period="daily", start_date, end_date)` 列名兼容（日期/收盘/涨跌幅）
- [x] 1.2 akshare `stock_a_indicator_lg(symbol)` 返回 dataframe 时间序列，取 iloc[-1] 最新一行
- [x] 1.3 numpy 2.3.0 已就绪

## 2. IndexDataService

- [x] 2.1 新建 `app/services/index_data_service.py`
- [x] 2.2 sync_index_history(symbol="000300", days=365)：列名兼容 + upsert + 状态字典
- [x] 2.3 get_index_returns: 自算 r_t = C_t/C_{t-1} - 1（不依赖 pct_chg 列）
- [x] 2.4 get_index_dates: 与 returns 对齐
- [x] 2.5 ensure_index：unique compound (symbol, date)

## 3. StockIndicatorService

- [x] 3.1 新建 `app/services/stock_indicator_service.py`
- [x] 3.2 _collect_target_codes: 自选股 ∪ paper 持仓 (CN) 并集
- [x] 3.3 sync_indicators_for_codes: 循环单股调 akshare，upsert
- [x] 3.4 get_latest_indicators: {code: {pe, pb}}
- [x] 3.5 ensure_index unique compound (code, date)

## 4. PortfolioRiskService

- [x] 4.1 新建 `app/services/portfolio_risk_service.py`
- [x] 4.2 calc_beta(days=60)：cov/var + tag 4 区间映射；< 30 天 / 大盘缺数据 / std=0 返回 None
- [x] 4.3 calc_var(confidence=0.95, days=252)：numpy.percentile(returns, 5) × equity
- [x] 4.4 calc_weighted_pe / calc_weighted_pb: Σ(指标 × MV) / ΣMV
- [x] 4.5 get_portfolio_metrics: 聚合 4 项
- [x] 4.6 单测 14 cases 全过：tag 映射 / Beta 完美相关 / Beta 1.5x / VaR 5% 分位 / 加权 PE 公式 / 边界 (空持仓 / indicators 缺失 / 数据不足)

## 5. Scheduler 注册

- [x] 5.1 _register_portfolio_fundamentals_jobs in scheduler_service
- [x] 5.2 cron mon-fri 17:30: sync index 7 天增量 + sync indicators 自选股∪持仓
- [x] 5.3 启动时检查 index_quotes_daily < 60 条则触发 365 天全量同步（async）

## 6. API endpoint

- [x] 6.1 GET /api/paper/portfolio_metrics 返回 `{beta, var, weighted_pe, weighted_pb}`

## 7. 前端集成

- [x] 7.1 frontend/src/api/portfolioMetrics.ts: PortfolioMetrics interface + getMetrics()
- [x] 7.2 Dashboard 4 处 Tier 4 mock 替换为真实数据
- [x] 7.3 Beta tag chip 4 配色：tag-high (红 高弹性) / tag-mid-high (金 中高) / tag-neutral (蓝) / tag-defensive (绿 防御)
- [x] 7.4 onMounted 加 loadPortfolioMetrics()

## 8. 收口验证

- [x] 8.1 just ci 全绿（62 unit tests passed，新增 14 个 portfolio_risk）
- [ ] 8.2 backend 启动验证（实施中未单独 dev-restart，commit 后用户启动验证）
- [ ] 8.3 GET /api/paper/portfolio_metrics 验证（Beta/VaR 依赖 ≥30 天 snapshot，加权 PE/PB 依赖个股 indicators 已 sync 才有数据 — 第一天均显示「—」预期）
- [ ] 8.4 前端 Tier 4 字段显示真实
- [x] 8.5 changelog [Unreleased] 加 entry
- [x] 8.6 archive change → archive/2026-05-08-portfolio-fundamentals/
- [x] 8.7 应用 spec → openspec/specs/portfolio-fundamentals/spec.md
