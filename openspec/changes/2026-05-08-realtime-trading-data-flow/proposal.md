# realtime-trading-data-flow

> 把交易学习平台的"实时行情 / 持仓 PnL"链路从 **pull-driven HTTP 轮询** 升级为 **push-driven mongo hot-snapshot + WebSocket** 架构，让 UI 永远 < 50ms 响应、不被 akshare 慢调用阻塞，并把数据时效（`as_of_ts` / `staleness_seconds`）显式透传到前端。

## Why

当前实时数据链路对交易场景**SLO 全面不达标**：

| 数据类 | 交易系统应有 SLO | 当前实际表现 | 差距 |
|---|---|---|---|
| 持仓 last price | < 1s | 30s sync + UI polling | **量级差** |
| 实时盈亏 PnL | < 1s | 跟着 last price + 前端聚合 | **量级差** |
| 自选股最新价 | < 1s | 同上 | **量级差** |
| 大盘涨跌停 / 成交额 | < 5s | cold start 110s / warm 30s | **量级差** |
| 数据时效透出 | 必须 | **完全不透出** | 致命 |

实测取证（2026-05-08 webapi.log）：

```
09:40:11 trace 2d230a6b /api/market/overview 110.034s（cold + akshare 慢）
09:40:11 trace 87e3042a /api/market/overview   0.008s（同时进，等 lock）
09:43:59 trace 9d21bd31 /api/market/overview  37.232s（30s TTL 过期再 fetch）
00:22:55 trace 691c17f9 /api/market/overview  68.261s
00:22:55 trace 8aa21818 /api/market/overview  68.251s（lock 串行）
```

四类根因：

1. **Pull 模式触底**：`/api/market/overview` / `/api/paper/account` / `/api/paper/performance` 等 hot path 直接（或间接）触发上游 fetch；前端 30s polling，体验天花板就是数十秒级。
2. **Hot path 与慢源耦合**：[`app/services/quotes_service.py:69`](app/services/quotes_service.py:69) 里 `await asyncio.to_thread(self._fetch_spot_akshare)` 调 `ak.stock_zh_a_spot_em()`——akshare p99 几十秒，**不应该**出现在用户请求路径。
3. **WebSocket 已有但用法残缺**：`/ws/notifications` / `/ws/task_progress` 仅做事件通道，**没有 quote / PnL 流**；Dashboard 仍 30s polling。
4. **freshness 不透出**：UI 不知道看到的是什么时候的价。交易决策若依据 stale price 是 dangerous——这是金融工程视角的**不可妥协项**。

> ⚠️ 上一个 change（hotfix）在 [`quotes_service.py`](app/services/quotes_service.py) 加了 8s timeout + stale fallback——**那是 web 思维的兜底，不是交易系统的方案**。本 change 把架构问题正式立项，timeout 保留作 belt-and-suspenders，但不再依赖它"扛"用户请求。

## What Changes

### 后端：hot-path 与慢源解耦（核心）

- **NEW** `app/services/quote_snapshot_reader.py`：
  - `read_market_overview() -> dict`：直接从 mongo `market_quotes` 聚合（涨停 / 跌停 / 上涨 / 下跌 / 成交额 / total），**永不调 akshare**
  - `read_quotes(codes: list[str]) -> dict`：从 mongo `market_quotes` 批量查；缺漏的 code 标 `None`（不触发上游 fetch）
  - 每个返回都带 `as_of_ts`（mongo 中**最新一条** `updated_at` 的 max）+ `staleness_seconds`（now - as_of_ts）

- **MODIFIED** `app/routers/market.py`：
  - `GET /api/market/overview` 改走 `quote_snapshot_reader.read_market_overview()`，剥离 `QuotesService.get_market_overview()` 调用
  - 响应 schema 加 `as_of_ts: ISO8601` + `staleness_seconds: float` 必返字段
  - SLO：p99 < 50ms（去掉 akshare 路径后纯 mongo 聚合）

- **MODIFIED** `app/routers/paper.py`：
  - `_get_last_price(code, market)` A 股分支只读 mongo `market_quotes`（已是当前实现），加返回 `(price, as_of_ts)` tuple
  - `GET /api/paper/account` / `/api/paper/performance` / `GET /api/paper/positions` 响应里 positions 数组每条带 `last_price_as_of`
  - 顶层响应加 `as_of_ts`（取所有 positions 的 min `last_price_as_of`，反映"最 stale 的那条"）

- **MODIFIED** `app/services/quotes_service.py`：
  - `get_quotes(codes)` 加超时降级（与上一 change 在 `_ensure_cache` 加的同模式）—— 这条是**收尾**，不是核心
  - 增加单测保证 `_fetch_spot_akshare` 永不在 hot-path 同步调用（仅 worker / scheduler 路径）

### 后端：PnL 服务端聚合 + 增量推送

- **NEW** `app/services/pnl_stream_service.py`：
  - `compute_pnl(user_id) -> dict`：拉 user 的 `paper_positions` + 当前 `market_quotes`，算实时 PnL；返回 `{positions: [...], total_unrealized, total_realized, total_equity, as_of_ts}`
  - **lifecycle 任务**：盘中（trading-calendar `is_intraday_now()`）每 N 秒（默认 3s）扫描所有有 active position 的 user，重算 PnL，与上次结果 diff 后通过 redis pub/sub 发布到 `channel:pnl:{user_id}`
  - 盘外不跑（依赖 `trading-calendar` capability）
  - 单 user 单次重算 < 50ms（mongo 索引已有）

- **NEW** `GET /ws/quotes` WebSocket endpoint（在 `app/routers/websocket_notifications.py` 同模块或新建 `websocket_quotes.py`）：
  - 客户端连接后通过消息 `{type: "subscribe", codes: ["000001", "600036"]}` 订阅
  - 后端订阅 redis `channel:quote:{code}`（由 realtime sync 写 mongo 后 publish），收到推送给该 ws
  - `{type: "subscribe_pnl"}` 订阅自己的 PnL 流（不能订别人的；user_id 从 token 取）
  - 心跳 30s 一次（已有 manager 模式）

- **MODIFIED** `app/services/realtime_quote_sync_service.py`：
  - 30s sync 完成 mongo upsert 后，对每个变化的 code 发 redis publish `channel:quote:{code}`（payload 含 close / pct_chg / amount / updated_at）
  - 不动既定 30s 颗粒（保留 `paper-realtime-quotes` capability spec 不变）

### 后端：freshness SLO 监控

- **NEW** `app/services/quote_freshness_monitor.py`：
  - 周期检查 `market_quotes.updated_at` 的 max；若盘中超过 SLO 阈值（默认 90s = 3 个 30s sync 周期）则 logger.warning + 写一条 `system_logs` 事件
  - 暴露 `GET /api/market/freshness` endpoint：返回 `{as_of_ts, staleness_seconds, sync_running: bool, last_successful_sync_at}` 给 UI 角标用

### 文档

- **MODIFIED** `docs/ai-context/architecture.md`：新增"实时数据流 SLO 模型"段，画 push 模式 ASCII 图 + 列 SLO 表
- **MODIFIED** `docs/CHANGELOG.md`：`[Unreleased]` 新增条目

## Out of Scope

- **sync 颗粒升级** 30s → 1-3s：保持 `paper-realtime-quotes` capability 既定颗粒；本 change 是"hot path 改读 mongo + 推送"，不动写库频率（拍板：D2）
- **Tushare 主源切换**：依赖 `data_source_config` token 流程，独立 follow-up（拍板：D4）
- **港股 / 美股实时**：本 change 仅 A 股；HK/US 已有 `ForeignStockService` 单独路径
- **前端改造**：本 change 仅出后端契约（`as_of_ts` / `/ws/quotes`），前端订阅切换为独立 follow-up；过渡期前端可继续 polling 但能立刻拿到 `as_of_ts` 显示新鲜度（拍板：D3）
- **市场深度 / 五档行情 / Tick 级数据**：超出 paper trading 学习平台范围
- **多 user 高并发场景**：个人 fork 单用户场景，不优化 multi-tenant

## Impact

**改动范围**：
- 新建 `app/services/quote_snapshot_reader.py`（~80 行）
- 新建 `app/services/pnl_stream_service.py`（~150 行）
- 新建 `app/services/quote_freshness_monitor.py`（~60 行）
- 新建 `app/routers/websocket_quotes.py` 或扩展 `websocket_notifications.py`（~120 行）
- 修改 `app/routers/market.py`（~20 行）
- 修改 `app/routers/paper.py`（~40 行，加 `as_of_ts` 字段）
- 修改 `app/services/realtime_quote_sync_service.py`（~30 行，加 redis publish）
- 修改 `app/services/scheduler_service.py`（注册 PnL stream task，~15 行）
- 新建 `tests/services/test_quote_snapshot_reader.py`（~60 行）
- 新建 `tests/services/test_pnl_stream_service.py`（~80 行）
- 新建 `tests/integration/test_ws_quotes.py`（~100 行）
- 新建 `openspec/specs/realtime-trading-data-flow/spec.md`
- 更新 `docs/ai-context/architecture.md` + `docs/CHANGELOG.md`

**风险**：中

- **Redis pub/sub 引入**：当前 redis 只做 cache，新增 pub/sub 通道。redis 单节点（docker compose 已起），无 HA 风险，但宕机时 ws 推送停摆 → degrade 到前端 30s polling fallback
- **WebSocket connection 数量**：单用户场景 < 5 连接，无压力；但 PnL stream 每 3s 触发广播，CPU 需 profile（预计单 user / 全量 < 100 持仓时 < 5% CPU）
- **既定 30s sync 不动**：用户感知"实时"由 push + 前端立刻渲染保障；30s sync 颗粒在实测中能让 UI 刷新感（push 介于 0-30s）
- **前置依赖**：当前 4 个 router 有 security 加固改动未 commit（`config.py` / `multi_source_sync.py` / `sync.py` / `websocket_notifications.py`）。**本 change 必须在它们 commit + CI 绿之后开**（拍板：D6）。否则 base 不稳定，本 change 的 ws 改动会 conflict

**收益**：

- UI hot path p99 < 50ms（与现状 cold 110s 差三个数量级）
- 数据时效完全透出（用户/agent 看到的每个 price 都带 `as_of_ts`）
- PnL 服务端聚合，避免前端用 stale price 算错
- 为后续 tushare 主源 + 1-3s 颗粒升级提供完整的 push-driven 基础架构（不需要再改 hot path）
- 满足金融工程视角的**最低**SLO 模型；为未来真实交易接入（券商 API）打地基

**不可逆性**：低
- 所有改动可 git revert
- mongo / redis 无 schema 破坏（只新增字段 / channel）
- WebSocket 新 endpoint，旧 endpoint 不动
- 过渡期前端 polling 继续工作（响应字段加了 `as_of_ts` 但旧字段都保留）
