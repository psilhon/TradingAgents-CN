# paper-realtime-quotes-job

> APScheduler 定期刷新「自选股 ∪ paper 持仓」的 A 股实时收盘价入 `market_quotes`，让 paper 模拟交易和 Dashboard 持仓显示能拿到行情。

## Why

当前 backend `_get_last_price()` ([app/routers/paper.py:226-270](app/routers/paper.py)) 对 A 股有两个 fallback：

1. `db.market_quotes` 查 close
2. `db.stock_basic_info` 查 current_price

实际数据库状态（生产环境实测）：

| Collection | 应有内容 | 实际 |
|---|---|---|
| `market_quotes` | 实时行情 close | **0 条** |
| `stock_basic_info` | 静态信息 + current_price | 5512 条，但**只有元数据**（code/name/source/sse），无 `current_price` |

→ 所有 A 股 `_get_last_price` 返回 None → paper 持仓 `last_price` / `unrealized_pnl` = null → Dashboard 持仓行显示 `¥0.00 / 0.00%`。

启动日志里现有的 APScheduler jobs 全是**基础信息 + 日 K 线 + 新闻**：
- 股票基础信息同步（BaoStock）→ `stock_basic_info`（无价格字段）
- 日 K 线数据同步（BaoStock）→ `daily_data`（不是 `market_quotes`）
- 新闻数据同步（AKShare - 仅自选股）

**没有任何 job 往 `market_quotes` 写实时收盘价**。这是 paper 模拟交易"无价"的根因。

用户报告：「广发证券（000776）拿不到数据」—— 实际所有 A 股都拿不到。

## What Changes

- **新建 `app/services/realtime_quote_sync_service.py`**：
  - `fetch_quotes_for_codes(codes: list[str]) -> list[dict]`：批量调 akshare 拉行情
  - `sync_favorites_and_paper_positions() -> dict`：取自选股 + paper 持仓代码（去重）→ fetch → upsert 到 `market_quotes`
  - 失败时 log warn，不抛（不阻塞 scheduler）

- **`app/services/scheduler_service.py` 注册两个 job**：
  - **盘中高频**：`IntervalTrigger(seconds=30)` 全天跑；job body 内 guard：仅工作日 9:25–15:00 真正执行 fetch，其它时间直接 return
  - **盘后兜底**：`CronTrigger(day_of_week='mon-fri', hour=17, minute=0)` 每日一次拿当日收盘价
  - 30 秒颗粒 APScheduler `CronTrigger` 不支持（最小分钟），故盘中走 `IntervalTrigger` + job body 时间窗 guard 组合

- **`market_quotes` collection schema 锁定**：
  - 字段：`code` / `symbol` / `close` / `volume` / `updated_at`
  - 索引：`code` 唯一索引（upsert 用）

- **新建 capability `paper-realtime-quotes`**：锁定铁律
  - 范围只刷"自选股 ∪ paper 持仓"，禁止全市场刷
  - 频率：盘中工作日 9:25–15:00 每 30 秒 / 盘后 17:00 一次
  - akshare 调用必须 batch + timeout + 失败降级 + 单次执行不超过 30 秒（防止重叠触发）

## Out of Scope

- **全市场行情刷新**（5500+ 只 A 股，数据量大、akshare rate limit 风险高）
- **港股/美股**（已有 `ForeignStockService` 单独路径，本 change 不涉及）
- **历史 K 线**（已有 `daily_data sync` job）
- **实时推送**（websocket / SSE，超出本 change 范围）
- **节假日日历**（按 `mon-fri` 简化判断；A 股节假日不跑会有少量误触发，可接受作 follow-up）
- **job 监控 / 失败告警**（用现有 logger.warning 即可，告警系统作 follow-up）

## Impact

**改动范围**：
- 新建 `app/services/realtime_quote_sync_service.py`（~120 行）
- 修改 `app/services/scheduler_service.py`（注册 1 个 job，~15 行）
- 新增 `tests/test_realtime_quote_sync_service.py`（~80 行）
- 新建 `openspec/specs/paper-realtime-quotes/spec.md`

**风险**：中
- 30 秒高频对 akshare server 压力（盘中 5.5h × 60s/30s × 2 = 660 次/天）。个人 fork 单用户 codes 数量小（< 100 只），单次 1-3s，可接受；但不适合多用户场景（该约束需在 spec 锁定）
- APScheduler 默认 `max_instances=1` + `coalesce=True` 防止重叠触发（必须显式配置）
- 30 秒颗粒不能用 CronTrigger，必须 IntervalTrigger + job body 时间窗 guard（盘外 return 早，避免空跑）
- 工作日定时 cron 周末不触发（依赖 IntervalTrigger 内 `datetime.weekday()` 判断）
- 不可逆动作：无（只是 mongo upsert，可清空 collection 重做）

**收益**：
- paper 模拟交易持仓显示真实浮动盈亏
- Dashboard 账户卡片真实数据驱动（替代 mock）
- 自选股实时价格也间接受益（`market_quotes` 给所有读取路径用）
- 为后续 `paper-account-snapshots` change 提供数据基础（每日快照需要 equity，equity 依赖 last_price）
