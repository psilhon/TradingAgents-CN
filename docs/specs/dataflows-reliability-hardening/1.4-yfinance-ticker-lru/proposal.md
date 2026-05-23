# 1.4 — yfinance.Ticker LRU 缓存

## Why

`tradingagents/dataflows/providers/us/yfinance.py` 当前 3 处构造 `yf.Ticker(symbol)` 实例，全部每次方法调用重建：

- **line 46** — `init_ticker` decorator wrapping `YFinanceUtils` 全部方法（line 52 `@decorate_all_methods(init_ticker)`），每个 `YFinanceUtils.get_stock_data(symbol)` / `get_stock_info(symbol)` / 等公开方法触发 1 次 `yf.Ticker(symbol)` 构造
- **line 163** — `get_YFin_data_online`（模块级函数）每次直接 `yf.Ticker(symbol.upper())`
- **line 272** — 技术指标函数每次 `yf.Ticker(symbol.upper())`

`yf.Ticker` 构造调用 yfinance 内部 session setup（HTTP client 配置 / Yahoo cookie / proxy detection）—— 同 symbol 重复构造时所有这些开销重复。一个典型 agent 请求会对同 ticker 调多个方法（fetch price + info + dividends + financials），按当前模式每个方法都新建 Ticker，session setup 重做一遍。

`docs/code-review-2026-05-05.md` 第二域 dataflows High finding：
> tradingagents/dataflows/providers/us/yfinance.py:41-52 — init_ticker decorator 每次重建无 LRU

## What Changes

### `tradingagents/dataflows/providers/us/yfinance.py`

引入 module-level `_get_ticker(symbol)` helper 用 `functools.lru_cache(maxsize=128)` 缓存：

```python
@functools.lru_cache(maxsize=128)
def _get_ticker(symbol: str) -> yf.Ticker:
    """Cached yf.Ticker factory — case-insensitive on symbol.

    yf.Ticker ctor isn't free: yfinance 内部 session setup（HTTP client / 
    cookie / proxy detection）每次重做。同一 agent 请求会对同 ticker 调
    多个方法（price + info + dividends + financials），缓存让所有调用
    共享同一 Ticker 实例。

    maxsize=128 够用：单进程同时活跃 < 128 个 stock；超过后 LRU 自动 evict。
    """
    return yf.Ticker(symbol.upper())
```

改造 3 个调用点：

- `init_ticker` decorator: `ticker = yf.Ticker(symbol)` → `ticker = _get_ticker(symbol)`
- line 163: `ticker = yf.Ticker(symbol.upper())` → `ticker = _get_ticker(symbol)`
- line 272: `ticker = yf.Ticker(symbol.upper())` → `ticker = _get_ticker(symbol)`

helper 内统一 `.upper()` normalize，避免 `"aapl"` / `"AAPL"` / `"AaPl"` 占 3 个 cache 槽（yfinance 接受任意 case 但语义同一）。

### spec delta（已落 capability spec）

`docs/specs/dataflows-reliability/spec.md` Requirement「第三方 client 实例须缓存」已含 Scenario「yfinance.Ticker 复用」。本 sub-stage 落实该 Scenario。

## Impact

### Code 变化

`providers/us/yfinance.py`：净 +15（helper 函数 +12，3 处调用点改写 +3）

### 行为变化

- 同 symbol 多次方法调用 → ticker ctor 触发 1 次（首次），子序列命中 cache 返同对象
- 不同 symbol 各占独立 cache 槽，maxsize=128 自动 LRU evict
- case-insensitive：`get_stock_data("aapl")` 与 `get_stock_data("AAPL")` 命中同一 cache 槽
- 公开 API 行为 / 返回结果：零变化（仅性能优化）

### 测试

`tests/test_yfinance_ticker_cache.py` 新建：

- spy `yf.Ticker`，调 `YFinanceUtils.get_stock_data` + `get_stock_info` 各一次同 symbol，断 ctor 调 1 次
- 调不同 symbol，断每个 symbol 各调一次
- 调 case-mixed (`aapl` vs `AAPL`)，断命中同一 cache 槽（ctor 仅 1 次）
- `_get_ticker.cache_clear()` 在 fixture 内调用避免测试间污染

### 用户 / callsite

零破坏：所有调用方收到的 ticker 实例语义一致（yfinance Ticker 内部数据 lazy load + 内置 cache，复用安全）。

### 风险

低。

- yfinance Ticker 实例线程安全性：yfinance 文档未明示线程安全，但内部用 `requests.Session` 默认线程安全；同进程同 symbol 复用 Ticker 是 yfinance 推荐用法（`yf.Tickers()` 批量接口就是这么用的）。
- cache 数据 stale：yfinance 内部数据有自己的 TTL；ticker 实例复用不破坏数据时效——每次调 `ticker.history()` / `ticker.info` 仍触发新的 API 请求。Ticker 仅缓存 client 句柄。

## Out of Scope

- yfinance batch API (`yf.Tickers()`) 的引入（属性能优化，本 stage 仅 reliability）
- 跨进程 ticker 共享（无 use case；LRU 进程级足够）
- ticker 实例 TTL 失效机制（yfinance Ticker 行为 stale 的实际证据不足）
