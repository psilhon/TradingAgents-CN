## 1. OpenSpec scaffolding — commit 1

- [ ] 1.1 创建 `openspec/changes/2026-05-20-data-truthfulness/` 目录
- [ ] 1.2 写 `proposal.md` / `tasks.md`
- [ ] 1.3 写 `specs/realtime-trading-data-flow/spec.md`（MODIFIED Requirement 1）
- [ ] 1.4 写 `specs/data-quality-gate/spec.md`（MODIFIED Requirement 3 + 4 个新 Scenarios）
- [ ] 1.5 `openspec validate 2026-05-20-data-truthfulness --strict` 通过
- [ ] 1.6 commit（仅 OpenSpec 文件）

## 2. F4 — is_stale 后端 + Detail 前端 stale 灰化 — commit 2

- [x] 2.1 `app/routers/stocks.py`：`/stocks/{code}/quote` data dict 加 `is_stale` + `as_of_date` 字段
- [x] 2.2 `frontend/src/views/Stocks/Detail.vue`：主价格区 `is-stale` 类、警告条幅、quote ref 字段、icon import
- [x] 2.3 pyright + ruff + vue-tsc 0 errors
- [ ] 2.4 commit

## 3. V1+V2 — Dashboard sparkline 清理 — commit 3

- [ ] 3.1 `Dashboard/index.vue`：删除自选股 watchlist 内 `<Sparkline>` 元素 + 周边 watchlist-spark CSS
- [ ] 3.2 删除 `mockTrend()` / `strSeed()` 函数（line 628-647 ~25 行）
- [ ] 3.3 Hero 区：删 `heroTrend` 对象 + 3 个 mock Sparkline（分析任务数 / 成功率 / 自选股数）
- [ ] 3.4 Hero「模拟总资产」改接 `paperPerformance.sparkline_points`，v-if 守卫，缺数据时不渲染
- [ ] 3.5 grep `mockTrend|strSeed` 残留 = 0
- [ ] 3.6 vue-tsc 0 errors
- [ ] 3.7 commit

## 4. V3 — 缺数据兜底 — commit 4

- [ ] 4.1 `loadFavoriteStocks`：`item.current_price || 0` → `item.current_price ?? null`；`change_percent` 同理
- [ ] 4.2 模板 watchlist-price / watchlist-chg 加 `v-if="stock.current_price != null"` 守卫；缺数据显示「—」
- [ ] 4.3 加 `isMissingQuote(stock)` 函数 + `.is-missing` CSS 类（opacity 0.5）
- [ ] 4.4 watchlist-item `:class` 绑定加 `is-missing`
- [ ] 4.5 vue-tsc 0 errors
- [ ] 4.6 commit

## 5. V4 — compute_overview 改 mongo aggregate today filter — commit 5

- [ ] 5.1 `market_overview_prewarm_service.compute_overview`：替换为 mongo `market_quotes` aggregate pipeline
- [ ] 5.2 pipeline：`$match` 限定 `updated_at >= today_cn_00:00 UTC`，`$facet` 同时算 limit_up / limit_down / advance / decline / amount_total / total
- [ ] 5.3 keep return shape 兼容（前端不需要改）
- [ ] 5.4 实测 p99 延迟 < 50ms
- [ ] 5.5 pyright 0 errors
- [ ] 5.6 commit

## 6. CI hook — commit 6

- [ ] 6.1 `scripts/check-data-truthfulness.sh`：grep 黑名单脚本（mockTrend / Math.random / 演示数据 / 占位数据 / `|| 0`-after-price）
- [ ] 6.2 支持 `// data-truthfulness:allow reason: ...` 注释豁免（同行或前一行有此注释跳过）
- [ ] 6.3 限路径 `frontend/src/views/Dashboard,Stocks,DailyRecommendation,PaperTrading` + `frontend/src/components/Layout`
- [ ] 6.4 `.pre-commit-config.yaml` 注册新 hook 在 commit 前阻塞
- [ ] 6.5 本地测试：故意往 Dashboard 加 `Math.random()`，确认 hook 阻塞
- [ ] 6.6 commit

## 7. Contract test — commit 7

- [ ] 7.1 `tests/test_stocks_quote_truthfulness.py`：pytest -m unit
- [ ] 7.2 测试用例：mock `/stocks/{code}/quote` 调用，断言返回 dict 含 `is_stale` 和 `as_of_date` key
- [ ] 7.3 测试用例：当 mongo `market_quotes.updated_at` 是昨天时 `is_stale=true`
- [ ] 7.4 测试用例：当 `updated_at` 是今天时 `is_stale=false`
- [ ] 7.5 测试用例：缺 quote 但有 basic_info 时 close=None / is_stale=None
- [ ] 7.6 `pytest -m unit` 全通过
- [ ] 7.7 commit

## 8. 收口 — commit 8

- [ ] 8.1 `docs/CHANGELOG.md` `### Fixed` 条目记录 V1-V5 + 5 个 spec/CI 拼图
- [ ] 8.2 跑 `just ci` 全绿（lint + typecheck + test）
- [ ] 8.3 commit
- [ ] 8.4 archive change → `openspec/changes/archive/2026-05-20-data-truthfulness/`（在 push 后由作者执行）
