# paper-account-snapshots Specification

## Purpose
TBD - created by archiving change paper-account-snapshots. Update Purpose after archive.
## Requirements

### Requirement: paper_account_snapshots collection schema

mongo collection `paper_account_snapshots` MUST 持久化每个 user 每个交易日的账户快照。

schema 锁定 6 字段：
- `user_id`: 用户标识符（与 paper_accounts 一致）
- `date`: 字符串 YYYY-MM-DD（交易日，按 Asia/Shanghai 时区）
- `equity`: 总资产（cash[CNY] + Σ positions[CN].mkt_value）
- `cash`: 当日可用现金（CNY）
- `positions_value`: 持仓市值（CNY）
- `realized_pnl`: 累计已实现盈亏（CNY）
- `unrealized_pnl`: 浮动盈亏（CNY）

索引：
- unique compound `(user_id, date)`
- 普通 `user_id`

#### Scenario: 数据完整性

- **WHEN** paper user 已使用 N 个交易日
- **THEN** `paper_account_snapshots` 该 user 应有 ≤ N 条文档
- **AND** 每条 date 唯一（同 user 同一日期不重复）

#### Scenario: equity 公式

- **WHEN** snapshot 写入
- **THEN** `equity == cash + positions_value`（容许 0.01 浮点误差）
- **AND** `positions_value == Σ position.quantity × _get_last_price(code, "CN")`

### Requirement: 快照生成时机

snapshot MUST 在以下时机生成：
- **每交易日盘后 16:00**（cron job，给行情入库 1 小时缓冲）
- **backend 启动时**：检查当日是否已有 snapshot，缺则补一条（仅交易日，异步 fire-and-forget）

非交易日（周末 / 节假日）**不**生成（依赖 capability `trading-calendar.is_intraday_now()` 同期判断逻辑）。

#### Scenario: 盘后 cron 生成

- **WHEN** 工作日 16:00 且当日是交易日
- **THEN** scheduler 触发 `take_snapshots_for_all_users()`
- **AND** 每个 paper user 写入一条 `paper_account_snapshots` 文档

#### Scenario: 启动补漏

- **WHEN** backend 启动
- **AND** 当日是交易日
- **AND** 当日 snapshot 缺失
- **THEN** `asyncio.create_task` 异步触发补一条 snapshot
- **AND** 不阻塞 backend 启动流程

#### Scenario: 周末跳过

- **WHEN** 周六 / 周日 / 节假日
- **THEN** cron job 仍触发但 body guard 检查 `is_trading_day(today)` = False 后直接 return
- **AND** 不写 mongo

### Requirement: PaperPerformanceService 数学正确性

`PaperPerformanceService` MUST 提供以下方法，数学公式严格符合金融行业标准：

- `calc_twrr(snapshots) -> float | None`：时间加权收益率
- `calc_sharpe(snapshots, rf=0.02) -> float | None`：年化 Sharpe 比率
- `calc_drawdowns(snapshots) -> {current, max}`：当前 + 历史最大回撤
- `calc_monthly_returns(snapshots) -> list[{month, return_pct}]`：按月聚合收益

边界：snapshot 数 < 2 时所有方法返回 None / 空列表（无法计算）。

#### Scenario: TWRR 公式

- **WHEN** snapshot equity 序列 = [100, 110, 121]
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

- **WHEN** equity 序列 = [100, 120, 90, 110, 80, 100]
- **THEN** peaks=[100, 120, 120, 120, 120, 120], drawdowns=[0, 0, −25%, −8.33%, −33.33%, −16.67%]
- **AND** max_drawdown = −0.3333（最深谷距前峰）

#### Scenario: 单调递增无回撤

- **WHEN** equity 序列单调递增 [100, 110, 121, 133]
- **THEN** current_drawdown = 0
- **AND** max_drawdown = 0

### Requirement: API endpoints

提供 2 个 paper API 供前端 Dashboard 使用：

- `GET /api/paper/snapshots?days=N` (默认 N=90)：返回最近 N 个交易日 snapshot 时间序列
- `GET /api/paper/performance`：返回聚合性能指标 + sparkline 90 天点

返回 schema：

```json
GET /api/paper/performance
{
  "success": true,
  "data": {
    "twrr": 0.186,                    // 时间加权收益率（小数）
    "sharpe": 1.42,                   // Sharpe 比率
    "current_drawdown": -0.032,       // 当前回撤（负数）
    "max_drawdown": -0.085,           // 最大回撤
    "monthly_returns": [              // 按月（最近 7 月）
      {"month": "2026-04", "return_pct": 4.8},
      ...
    ],
    "sparkline_points": [231528, 230000, ...]  // 90 天 equity 等距 ~11 点
  }
}
```

#### Scenario: 性能 endpoint

- **WHEN** GET `/api/paper/performance`
- **THEN** 返回上述 schema
- **AND** 数据缺失（snapshot < 2 条）时所有指标为 null
- **AND** sparkline_points 至少 2 个点（缺则空列表）

#### Scenario: 鉴权

- **WHEN** 未登录用户访问 endpoint
- **THEN** 返回 401 Unauthorized
- **AND** 不暴露任何 user 数据
