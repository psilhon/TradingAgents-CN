# fix-datasource-async-bridge

> 修复 `tradingagents/dataflows/data_source_manager.py` 的同步/异步桥接 bug——3 个数据源方法在「调用方位于运行中的 event loop」时全线失败，导致 Web 端股票分析在「股票代码验证」阶段即崩溃。

## Why

用户实测：Web 端分析北特科技（`603009`）失败，弹窗「股票代码无效 无法获取历史数据」。任务状态 `failed (0%)`——多 agent 分析（`propagate`）一次都没跑。

实测取证（2026-05-16 `logs/tradingagents.log`）：

```
❌ [备用数据源-DataSourceCode.TUSHARE]  获取失败: 603009, 错误: this event loop is already running.
❌ [备用数据源-DataSourceCode.BAOSTOCK] 获取失败: 603009, 错误: this event loop is already running.
❌ [所有数据源失败] 无法获取daily数据: 603009

Traceback (most recent call last):
  File ".../tradingagents/dataflows/data_source_manager.py", line 1312, in _get_tushare_data
    data = loop.run_until_complete(provider.get_historical_data(symbol, start_date, end_date))
  File "uvloop/loop.pyx", line 1512, in uvloop.loop.Loop.run_until_complete
RuntimeError: this event loop is already running.
```

### 根因

`data_source_manager.py` 的三个数据源方法 `_get_tushare_data`(1251)、`_get_akshare_data`(1346)、`_get_baostock_data`(1396) 共 7 处 `run_until_complete` 同步/异步桥接（`_get_tushare_data` 3 处——含缓存命中分支、`_get_akshare_data` 2 处、`_get_baostock_data` 2 处）：

```python
loop = asyncio.get_event_loop()      # 在 running 的 uvloop 里 → 拿到正在跑的 loop
...
loop.run_until_complete(provider.get_historical_data(...))   # 在 running loop 上调 → RuntimeError
```

代码注释（"在线程池中没有事件循环"）暴露了错误假设：**它假设自己永远在没有 running event loop 的同步环境运行**。该假设：

- ✅ 对 CLI 路径成立（`python main.py` 是纯同步进程）
- ✅ 对 `propagate` 的线程池路径成立（FastAPI `run_in_executor` 的工作线程无 running loop）
- ❌ 对「async 函数直接 await」的调用链不成立——FastAPI 的 `prepare_stock_data_async`（股票代码验证）在主 event loop 线程里 await，链路同步调到 DataSourceManager，此时 loop 正 running → `run_until_complete` 非法。

### 影响范围

- Web 端**所有**股票分析在「股票代码验证」阶段失败（三个数据源全挂在同一个 bug 上）。
- CLI 路径不受影响（无 running loop，`run_until_complete` 合法）。
- `propagate`（多 agent 分析阶段）本身不炸（跑在线程池工作线程）——所以修好验证阶段的根因，完整分析即可一路跑通。

## What Changes

### MODIFIED `tradingagents/dataflows/data_source_manager.py`

- **NEW** 模块级 helper `_run_provider_coro(coro)`：同步执行一个 async coroutine，在任意 event loop 上下文都安全：
  - 当前线程**无** running loop → `asyncio.run(coro)`
  - 当前线程**有** running loop → 把 coroutine 丢到一个独立线程执行 `asyncio.run`（独立线程无 running loop，合法），阻塞等结果
- **MODIFIED** `_get_tushare_data` / `_get_akshare_data` / `_get_baostock_data`：7 处 `loop.run_until_complete(...)` 全部替换为 `_run_provider_coro(...)`，移除各方法里手写的 `get_event_loop` / `new_event_loop` / `set_event_loop` 样板（共 4 个样板块）。

### NEW 测试 `tests/dataflows/test_data_source_manager_async_bridge.py`

标 `unit` marker（纯逻辑、mock provider、无 `.env` key、无网络）。在 `async def` 测试函数（= 有 running event loop 的环境）里调三个数据源方法，断言不再抛 `this event loop is already running`；并加同步上下文回归。

### 文档

`docs/CHANGELOG.md` `[Unreleased]` 记一笔。

## 不做什么（明确排除）

- **不改 `app/` 专有授权代码**（`prepare_stock_data_async` 等调用方）。根因在 DataSourceManager，从 source 修；调用方无需改动。
- **不补 Tushare token**。这是独立的次要问题（Tushare `pro_bar` 无 token 抛 `IOError`），验证逻辑会降级到免 token 的 akshare / baostock，不阻塞本 change。
