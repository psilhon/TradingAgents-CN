## ADDED Requirements

### Requirement: Snapshot 写入闸门 + partial 标志

`paper_snapshot_service.take_snapshot` MUST 在写入 mongo 前检测 partial quote coverage——遍历账户所有 positions，收集 `_get_last_price(code, currency)` 返 None 的 code 列表（`missing_quote_codes`）。

文档 schema 扩 2 字段：

- `partial`: `bool` — 当 `missing_quote_codes` 非空时为 `true`
- `missing_quote_codes`: `list[str]` — 缺 quote 的 position code 列表（空 list 时也存在该字段，避免 read path 用 `doc.get(...)` 的 default 触发歧义）

partial=true 时：

- `positions_value` MUST 写 `None`（不能用 0 / 部分累加值合成）
- `equity` MUST 写 `None`（公式分量缺失，equity 不可信）
- `cash` / `realized_pnl` / `unrealized_pnl` 仍按 partial 的可计算结果写入（cash 不依赖 quote；realized 是历史成交；unrealized 跳过 missing 的 position 后剩余可计算）

partial=false 时（所有 position 都有 quote 或无 position）：

- 行为与 v1.3.0 一致（equity 公式严格满足 `equity == cash + positions_value`）

backward compat：读 path（PerformanceService / API endpoint / 历史回填 script）MUST 用 `doc.get("partial", False)` 处理无 `partial` 字段的旧文档（v1.3.0 release 之前到本 hotfix 之间产生的所有 snapshot），按 fully-covered 处理；MUST NOT 抛 KeyError。

理由：v1.3.0 release 后审计发现 `app/routers/paper.py:316` 用 `last or 0.0` 把缺 quote 的 position market_value 合成为 0，equity = cash + 失真 positions_value 持久化进 mongo——后续 PaperPerformanceService 计算 TWRR/Sharpe/回撤直接基于这条假记录，让 90 天历史曲线被污染。本 Req 把"partial 检测 + 写入闸门"固化进 service 层，从源头切断污染。

#### Scenario: full coverage 时 partial=false

- **WHEN** 账户内所有 position 的 `_get_last_price(code, "CN")` 返回非 None
- **THEN** 写入文档 `partial=false`, `missing_quote_codes=[]`
- **AND** `positions_value`, `equity` 数值正确（与 v1.3.0 行为一致）

#### Scenario: 部分 position 缺 quote 时 partial=true

- **WHEN** 账户内有 N 个 position，其中 M (1 ≤ M ≤ N) 个 `_get_last_price` 返 None
- **THEN** 写入文档 `partial=true`, `missing_quote_codes=[code_i, ...]`（M 个）
- **AND** `positions_value=None`, `equity=None`
- **AND** `cash`, `realized_pnl` 正常写入

#### Scenario: 所有 position 缺 quote 时也 partial=true

- **WHEN** 账户内所有 position 都缺 quote（罕见，如开盘前 / 节假日同步异常）
- **THEN** `partial=true`, `missing_quote_codes` 列出全部 code
- **AND** `positions_value=None`, `equity=None`

#### Scenario: 空仓账户 partial=false

- **WHEN** 账户无任何 position（纯现金账户 / 新账户）
- **THEN** `partial=false`, `missing_quote_codes=[]`, `positions_value=0.0`（真零值，非合成）
- **AND** `equity = cash`

#### Scenario: 旧文档 backward compat

- **WHEN** read path（PerformanceService.calc_X / API endpoint / 回填 script）读取无 `partial` 字段的旧 snapshot 文档
- **THEN** 必须用 `doc.get("partial", False)` 处理，按 fully-covered 解读
- **AND** MUST NOT 抛 KeyError 或拒绝该文档
- **AND** 历史 90 天曲线对这些旧文档照常计算（视为 v1.3.0 行为）

## MODIFIED Requirements

### Requirement: paper_account_snapshots collection schema

mongo collection `paper_account_snapshots` MUST 持久化每个 user 每个交易日的账户快照。

schema 锁定 **9 字段**（v1.3.1 扩 partial 闸门两字段 + 微调 nullable 语义）：

- `user_id`: 用户标识符（与 paper_accounts 一致）
- `date`: 字符串 YYYY-MM-DD（交易日，按 Asia/Shanghai 时区）
- `equity`: 总资产 `float | None`（partial=true 时为 None；否则 = cash[CNY] + Σ positions[CN].mkt_value）
- `cash`: 当日可用现金（CNY）`float`
- `positions_value`: 持仓市值 `float | None`（partial=true 时为 None）
- `realized_pnl`: 累计已实现盈亏（CNY）`float`
- `unrealized_pnl`: 浮动盈亏（CNY）`float | None`（partial=true 时为 None；否则按可计算 position 聚合）
- `partial`: `bool`（v1.3.1 新增；读旧文档时 `doc.get("partial", False)`）
- `missing_quote_codes`: `list[str]`（v1.3.1 新增；partial=false 时为空 list）

索引：
- unique compound `(user_id, date)`
- 普通 `user_id`

#### Scenario: 数据完整性

- **WHEN** paper user 已使用 N 个交易日
- **THEN** `paper_account_snapshots` 该 user 应有 ≤ N 条文档
- **AND** 每条 date 唯一（同 user 同一日期不重复）

#### Scenario: equity 公式

- **WHEN** snapshot 写入且 `partial=false`
- **THEN** `equity == cash + positions_value`（容许 0.01 浮点误差）
- **AND** `positions_value == Σ position.quantity × _get_last_price(code, "CN")`
- **AND** 所有 position 的 quote MUST 非 None（否则应 partial=true 路径）

#### Scenario: partial=true 时 equity 公式不适用

- **WHEN** snapshot 写入且 `partial=true`（部分或全部 position 缺 quote）
- **THEN** `equity=None`, `positions_value=None`
- **AND** MUST NOT 用 cash + 部分累加 positions_value 合成 equity（这正是 v1.3.0 漏修的根因）

### Requirement: PaperPerformanceService 数学正确性

`PaperPerformanceService` MUST 提供以下方法，数学公式严格符合金融行业标准：

- `calc_twrr(snapshots) -> float | None`：时间加权收益率
- `calc_sharpe(snapshots, rf=0.02) -> float | None`：年化 Sharpe 比率
- `calc_drawdowns(snapshots) -> {current, max}`：当前 + 历史最大回撤
- `calc_monthly_returns(snapshots) -> list[{month, return_pct}]`：按月聚合收益

边界：

- snapshot 数 < 2 时所有方法返回 None / 空列表（无法计算）
- **v1.3.1 扩**：每个方法入口 MUST 先过滤掉 `partial=true` 的 snapshot（这些日期数据不可信，参与计算会污染金融指标）；过滤后 < 2 时返 None / 空列表
- backward compat：无 `partial` 字段的旧 snapshot 按 fully-covered 处理（不过滤）

#### Scenario: TWRR 公式

- **WHEN** snapshot equity 序列 = [100, 110, 121]（partial 全 false）
- **THEN** daily_returns = [0.10, 0.10]
- **AND** TWRR = (1.10 × 1.10) − 1 = 0.21（21%）

#### Scenario: Sharpe 公式

- **WHEN** mean(daily_returns) = 0.001 / std = 0.02 / rf=0.02 / N=252
- **THEN** annualized_return = 0.001 × 252 = 0.252
- **AND** annualized_vol = 0.02 × √252 ≈ 0.317
- **AND** Sharpe = (0.252 − 0.02) / 0.317 ≈ 0.732

#### Scenario: Sharpe 零波动率

- **WHEN** std(daily_returns) = 0（账户净值无波动）
- **THEN** calc_sharpe 返回 None
- **AND** 不抛 ZeroDivisionError

#### Scenario: 当前回撤

- **WHEN** equity 历史峰值 = 240, 当前 = 231
- **THEN** current_drawdown = (231 − 240) / 240 = −0.0375（−3.75%）

#### Scenario: 最大回撤

- **WHEN** equity 序列 = [100, 120, 90, 110, 80, 100]（partial 全 false）
- **THEN** peaks=[100, 120, 120, 120, 120, 120], drawdowns=[0, 0, −25%, −8.33%, −33.33%, −16.67%]
- **AND** max_drawdown = −0.3333（最深谷距前峰）

#### Scenario: 单调递增无回撤

- **WHEN** equity 序列单调递增 [100, 110, 121, 133]（partial 全 false）
- **THEN** current_drawdown = 0
- **AND** max_drawdown = 0

#### Scenario: partial=true 日期被跳过

- **WHEN** snapshot 序列 = [{eq=100, partial=false}, {eq=None, partial=true}, {eq=121, partial=false}]
- **THEN** 过滤后 valid 序列 = [{eq=100}, {eq=121}]
- **AND** TWRR 计算用 valid 序列：daily_returns = [(121-100)/100] = [0.21]
- **AND** 不会因中间含 None equity 抛 TypeError

#### Scenario: 过滤后 snapshot 数不足

- **WHEN** snapshot 序列共 5 条但 4 条 `partial=true`
- **THEN** 过滤后只剩 1 条，< 2，calc_X 全部返 None / 空列表
- **AND** 不抛异常

#### Scenario: 旧文档无 partial 字段

- **WHEN** snapshot 序列全部来自 v1.3.1 之前（无 `partial` 字段）
- **THEN** 按 fully-covered 处理（`doc.get("partial", False) == False`），全部参与计算
- **AND** 行为与 v1.3.0 一致（regression guard）
