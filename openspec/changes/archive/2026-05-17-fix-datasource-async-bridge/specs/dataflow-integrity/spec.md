## ADDED Requirements

### Requirement: 数据源访问层 MUST 在任意 event loop 上下文安全

`tradingagents/dataflows/data_source_manager.py` 的数据源访问方法（`_get_tushare_data` / `_get_akshare_data` / `_get_baostock_data` 等同步方法，内部桥接 async provider）MUST 在以下三种调用上下文都能正确执行，不得因当前线程的 event loop 状态而失败：

1. **纯同步上下文**（无 event loop）——如 CLI `python main.py`
2. **线程池工作线程**（无 running loop）——如 FastAPI `run_in_executor` 跑的 `propagate`
3. **运行中的 event loop 线程**——如 FastAPI async 路径直接 `await` 的调用链（股票代码验证 `prepare_stock_data_async`）

具体约束：同步方法在内部调用 async provider 时，MUST NOT 假设"当前线程没有 running event loop"，MUST NOT 直接对一个可能正在运行的 loop 调 `run_until_complete()`。

#### Scenario: 在运行中的 event loop 里调用数据源方法

- **WHEN** 调用方位于一个正在运行的 event loop 线程（如 FastAPI async handler / async 验证函数）
- **THEN** `data_source_manager.py` 的数据源方法 MUST 正常返回数据
- **AND** MUST NOT 抛 `RuntimeError: this event loop is already running`

#### Scenario: 同步 / 线程池上下文回归

- **WHEN** 调用方在纯同步上下文（CLI）或无 running loop 的线程池工作线程
- **THEN** 数据源方法行为与修复前一致（正常取数，不回归）
