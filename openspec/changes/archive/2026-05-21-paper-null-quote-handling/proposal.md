## Why

v1.3.0 (2026-05-18) release 收口了 Dashboard 模拟账户 mock 数据问题，并固化了 grep 层防复发（`scripts/check-data-truthfulness.sh` + pre-commit hook，覆盖 `mockTrend` / `Math.random` / `Math.sin.*\*` / `演示数据` / `占位数据`）。

2026-05-20 在 v1.3.0 发布**之后**用 `data-truthfulness-auditor` subagent 做了 baseline 扫描——**grep 层 0 命中**，但语义层撞到 **5 critical + 3 warning** 漏修（grep hook 抓不到的 null-as-0 模式）：

| # | 违规 | 文件 | 用户感知 |
|---|---|---|---|
| C1 | `formatMoney(null)` 返回 `'0.00'`（`!value` 把 null 和真 0 混淆）| `frontend/src/views/Dashboard/index.vue:899-902` | 缺 quote 时 `¥{{ formatMoney(p.last_price) }}` 渲染 `¥0.00`，与真 0 视觉不可区分 |
| C2 | HK/USD 账户 `?.HKD \|\| 0` 强转 | `frontend/src/views/PaperTrading/index.vue:65-86` | 未启用美股账户时显示 `HK$0.00 / $0.00`，"未启用"被渲染成"余额为零" |
| C3 | 浮盈算式 null × null 渲染**假红色亏损** | `frontend/src/views/PaperTrading/index.vue:142-143` | `(Number(null \|\| 0) - avg_cost) × qty = -avg_cost × qty`，红色显示一个完全虚假的亏损（错向信号） |
| C4 | `market_value = round((last or 0.0) * qty, 2)` | `app/routers/paper.py:316, 556` | **写入 mongo snapshot 污染源头**：缺 quote 的持仓被计成市值 0，equity = cash + 失真 positions_value 持久化进 `paper_account_snapshots`，TWRR / Sharpe / 回撤等所有 90 天衍生指标被污染 |
| C5 | ws push payload `unrealized_pnl = 0.0` for null quote | `app/services/pnl_stream_service.py:104-117` | 实时推流路径上重演 C4 根因，前端 store 消费 `total_unrealized` 时渲染假 ¥0.00 |
| W1 | Dashboard 多个 computed 在 loading / 空账户返 0 | `frontend/src/views/Dashboard/index.vue:684-714` | 新账户首日 KPI 显示 `¥0.00 / 0%`，与 v1.3.0 release notes 承诺的"新账户首日显示「—」属预期"自相矛盾 |
| W2 | `portfolio_risk_service` 缺失日期 `aligned.append(0.0)` 污染 Beta 计算 | `app/services/portfolio_risk_service.py:80` | Beta = cov(R_acct, R_HS300) / var(R_HS300) 用合成 0 注入会 deflate var + skew cov——给用户看的"组合 Beta 0.83 中性"可能根本不是真 β |
| W3 | K 线 OHLC `float(row.get("open", 0))` 缺字段补 0 | `app/routers/stocks.py:545-549, 616-621` | 历史 K 线某根 candle 缺 open/high/low/close（停牌日 / 部分写入文档）时渲染 OHLC 全 0 的假阴线 |

**根因**：v1.3.0 的 grep 黑名单只覆盖**词法模式**，无法识别：
- `formatMoney` / `Number()` 等函数内部的 `!value` / `|| 0` 兜底
- 后端 `last or 0.0` 语义等价模式
- 算式分量缺失自动当 0（`null × X = 0`）
- mongo aggregate 缺失日补 0

要**真正闭环防复发**，必须升 spec 到「语义层 null-as-0 禁令」+ 强制 **contract test 覆盖**（针对每个 dashboard endpoint，喂全 null 上游断言返 null，不能合成 0）。

## What Changes

### 改动 1：spec 升级（接 grep 后的语义层）

- **MODIFIED** `data-quality-gate` Requirement 3：扩 2 个新 Scenario
  - "Scenario: 后端 service 缺上游数据 MUST 返 None"——禁 `last or 0.0` / `value or 0` 类后端等价模式
  - "Scenario: Contract test MUST 覆盖空态契约"——每个 dashboard endpoint 必须有 `@pytest.mark.unit` test 喂全 null 上游断言 endpoint 返 null/None
- **MODIFIED** `paper-account-snapshots` Requirement "equity 公式"：从"`equity == cash + positions_value`"升级为"partial quote coverage 时 `positions_value = None` + `partial: true` 标志，equity 也为 None；PerformanceService 计算 TWRR/Sharpe/回撤时 MUST 跳过 `partial=true` 的日期"
- **ADDED** `paper-account-snapshots` Requirement "Snapshot 写入闸门 + partial 标志"——独立 Req 锁定文档 schema 增量

### 改动 2：C4 + C5 + W2 后端 null 严格化（数据链上游 fix）

- **MODIFIED** `app/routers/paper.py`：
  - `get_account` (line 316)：`mkt_value = None if last is None else round(last * qty, 2)`；聚合 `positions_value_by_currency[currency]` 时跳过 None；返 `quote_coverage: {has_quote: int, missing: int, missing_codes: [str]}` 字段；`equity_by_currency` 在 positions_value 不完整时返 None
  - `list_positions` (line 556)：同上
- **MODIFIED** `app/services/pnl_stream_service.py`：line 104-117 `mkt_value = None / unrealized = None` 替代 `0.0`；聚合 `positions_value` / `total_unrealized` 时跳过 None；顶层 payload 缺 quote 时返 None；新增 `quote_coverage` 字段
- **MODIFIED** `app/services/paper_snapshot_service.py`：检测 partial quote coverage；snapshot 文档加 `partial: bool` + `missing_quote_codes: list[str]`；`positions_value` 在 partial=true 时写 None；backward compat：读旧文档无 `partial` 字段默认 False
- **MODIFIED** `app/services/paper_performance_service.py`：`calc_twrr` / `calc_sharpe` / `calc_drawdowns` / `calc_monthly_returns` 全部跳过 `partial=true` 的日期（不参与 daily_returns 序列）；snapshot 数过滤后 < 2 时返回 None / 空列表
- **MODIFIED** `app/services/portfolio_risk_service.py`：`aligned.append(0.0)` 改 inner-join 对齐，账户日期 ∩ 指数日期交集 < 30 天时返 None
- **MODIFIED** `app/routers/stocks.py`：K 线 OHLC 加 `_safe_float()` 工具，缺字段返 None；`volume` / `amount` 同步严格化

### 改动 3：C1 + C2 + C3 + W1 前端 nullable 守卫

- **MODIFIED** `frontend/src/views/Dashboard/index.vue`：
  - `formatMoney` 改签名 `(value: number | null | undefined): string`，`null/undefined/NaN` → `'—'`，仅真 0 → `'0.00'`
  - 模板所有 `¥{{ formatMoney(...) }}` 改为 formatter 内置 ¥（避免 null 时显示 `¥—`）
  - 4 个 computed（`successRate` / `totalEquity` / `positionRatio` / `realizedPnl` / `pnlRate`）改签名返 `number | null`；模板 `v-if` 守卫显示「—」
- **MODIFIED** `frontend/src/views/PaperTrading/index.vue`：
  - lines 65-86：HK/USD tab 整 `v-if="account.cash?.HKD != null"` 守卫；缺账户 tab 不渲染并提示"未启用美股账户"
  - lines 142-143：浮盈表达式包 `v-if="row.last_price != null"`；null 时显示 `<span class="muted">—</span>`，避免假红色亏损
  - `fmtAmount` 同步检查 null
- **MODIFIED** `frontend/src/api/paper.ts` 类型定义：account / position dataclass 加 `quote_coverage?` + `partial?`；nullable 字段类型从 `number` 改 `number | null`

### 改动 4：Contract test 覆盖（pre-push 阻塞）

- **NEW** `tests/test_paper_null_quote_contract.py`（`@pytest.mark.unit`）：
  - 给定全 null `_get_last_price`，`/api/paper/account` 返 `positions_value=None` + `equity=None` + `partial=true`
  - 给定部分 null，返 `quote_coverage.missing_codes=[...]` + 字段计算正确
  - `list_positions` 缺 quote 时 `market_value` 返 None（非 0）
- **NEW** `tests/test_pnl_stream_null_quote_contract.py`：ws push payload 喂全 null `last_price` 断言 `unrealized_pnl=None` + `total_unrealized=None`
- **NEW** `tests/test_paper_snapshot_partial_contract.py`：写入闸门——`take_snapshot` 在 partial coverage 时写 `partial=true`；`PaperPerformanceService` 喂含 partial=true snapshot 序列断言这些日期不参与 TWRR/Sharpe 计算
- **NEW** `tests/test_portfolio_risk_beta_inner_join.py`：账户 / 指数日期不重合时 Beta 返 None；交集 < 30 天返 None
- **NEW** `tests/test_stocks_kline_ohlc_nullable.py`：mongo 文档缺 open/high/low/close 字段时 endpoint 返 null（非 0）
- **NEW** `tests/test_dashboard_formatmoney_unit.py`（前端 vitest 跑不通；用 ts unit test 框架放 `frontend/src/utils/__tests__/`）：`formatMoney(null)='—'`, `formatMoney(0)='0.00'`, `formatMoney(0.5)='0.50'`

### 改动 5：CHANGELOG hotfix 段

- **MODIFIED** `docs/CHANGELOG.md`：`[Unreleased]` 段加 v1.3.1 hotfix 子段，列 5 critical + 3 warning 修复 + spec delta + contract test 增量

## Capabilities

无新建。复用扩展两个现有 capability：

- `paper-account-snapshots`（MODIFIED equity 公式 Requirement + ADDED Snapshot 写入闸门 Requirement）
- `data-quality-gate`（MODIFIED Requirement 3，扩 2 个新 Scenario）

## Impact

**改动文件**：
- 2 个 spec deltas
- 5 个后端业务文件（paper.py / pnl_stream_service / paper_snapshot_service / paper_performance_service / portfolio_risk_service / stocks.py）
- 2 个前端业务文件（Dashboard / PaperTrading）+ 1 个 API 类型定义
- 6 个新 contract test 文件
- 1 个 CHANGELOG 段

**视觉变化**（用户可见）：
- 缺 quote 的持仓显示「—」而非 `¥0.00`
- PaperTrading HK/USD tab 未启用账户不渲染（提示文案替代）
- PaperTrading 浮盈列缺 quote 显示「—」而非假红色亏损
- Dashboard 新账户首日 KPI 显示「—」（与 release notes 承诺一致）
- K 线某根 candle 数据不全时跳过该 bar（不渲染假阴线）

**API breaking changes**：
- `/api/paper/account` response：`positions_value` / `equity` 字段类型从 `float` 改 `float | null`；新增 `quote_coverage` 字段
- `/api/paper/positions` response：`market_value` / `unrealized_pnl` 从 `float` 改 `float | null`
- WS `pnl_stream` payload：同上 + 顶层新增 `quote_coverage`
- 旧前端代码（如有外部消费者）需同步兼容；本 fork 仅自用，已在改动 3 同步处理

**风险**：中
- mongo `paper_account_snapshots` 文档 schema 增 2 字段——backward compat 通过 `doc.get("partial", False)` 处理
- 历史 90 天 snapshot 文档无 `partial` 字段 → 默认按 fully-covered 处理；如要回填需单独 admin script（本 change 不包含，留 follow-up）
- pre-push test 时长增加 ~3-5s（6 个新 unit test）

**收益**：
- v1.3.0 释放后**真正闭环**——5 critical 是 release 漏修，本 change 等于 hotfix v1.3.1
- 后端写入闸门确保未来缺 quote 不再污染历史 snapshot → TWRR / Sharpe / 回撤等指标可信
- contract test 把"语义层 null-as-0 禁令"固化进 CI，下次有人写 `last or 0.0` 时 pre-push 阻塞
