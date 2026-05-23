# dataflows-reliability Specification

## Purpose

锁定 `tradingagents/dataflows/` 数据源层（providers / news / cache 之外的支持模块）的 reliability 契约。本 capability 由 `dataflows-reliability-hardening` epic 起头——确立「HTTP 请求必须设 timeout / 进程级副作用须收敛 / 外部 session 并发安全」三类基线。

不在范围：业务逻辑正确性（属各 provider 的 capability spec），cache 层契约（属 `dataflow-caching`），数据 schema 一致性（属 data-audit 类 capability）。

## Requirements

### Requirement: HTTP 请求必须设 timeout

`tradingagents/dataflows/` 下所有出站 HTTP 调用（`requests.get` / `requests.post` / `requests.request` / `httpx` 同类）MUST 显式设 `timeout=` 参数，禁止依赖库默认（默认 = 无限阻塞）。

数值约定（与 4.5 前 `news/google_news.py:46` 已确立的惯例一致）：

- `timeout=(connect, read)` 元组形式，连接 10s + 读取 30s
- 或单值 `timeout=30`（连接 + 读取共用）
- **特殊场景**：实时行情类高频调用可降至 `(5, 10)` 避免阻塞循环；批量历史数据可放宽到 `(10, 60)`

无 timeout 出站调用 MUST 视为 reliability bug：调用方在数据源故障 / 网络分区 / DNS 失败时会无限挂起，拖死整条 agent 调用链。

#### Scenario: realtime_news 三处 API 调用必须带 timeout

- **WHEN** `RealtimeNewsAggregator._get_finnhub_news` / `_get_alpha_vantage_news` / `_get_newsapi_news` 调用 `requests.get`
- **THEN** 每处 MUST 含 `timeout=` 参数
- **AND** 数值符合 `(connect, read)` 约定，不允许 `timeout=None` 或缺省

#### Scenario: dataflows 全目录 grep 无 timeout-less requests

- **WHEN** 在 `tradingagents/dataflows/` 全目录 grep `requests\.(get|post|put|delete|request)\(` 命中
- **AND** 每处匹配的同一调用语句（含跨多行）
- **THEN** MUST 包含 `timeout` 关键字（参数名）
- **AND** 例外：测试 / docstring 内的示例代码（标记 `# noqa: TIMEOUT` 或在 `tests/` 目录下）

### Requirement: 第三方库进程级副作用须收敛

`tradingagents/dataflows/` 下的 provider 实现 MUST NOT 对全局模块 / 进程级状态做不可逆 monkey-patch。具体：

- MUST NOT 覆写 `requests.get` / `requests.post` 等模块级函数
- MUST NOT 设置进程级全局 flag（如 `requests._akshare_headers_patched`）让其它模块通过该 flag 判断状态
- MUST NOT 修改其它库（pandas / yfinance / akshare 等）的全局配置项

可接受的 workaround：

- 在 provider 内构造 local `requests.Session` 实例 + 注入 headers / hooks
- 用 `contextlib.contextmanager` 范围限定的 patch（with 块外恢复原状）
- pip 包升级修复（向上游提 issue）

#### Scenario: AKShare provider 不污染全局 requests

- **WHEN** 加载 `tradingagents/dataflows/providers/china/akshare.py`
- **THEN** MUST NOT 设置 `requests.get = patched_get` 或 `requests._akshare_*` 属性
- **AND** AKShare 调用需要的 headers / 限流 MUST 通过本地 Session 或包装函数实现

### Requirement: 外部 session 单例须线程安全

`tradingagents/dataflows/` 下若使用进程级单例的外部库 session（baostock / akshare / yfinance 等）MUST 通过统一 helper 管理 lifecycle，禁止散落 `login()` / `logout()` 调用让并发互相 logout。

具体：

- session lifecycle 收敛到 module-level helper（如 `_get_session()` / `_session_scope()` context manager）
- helper MUST 用 `threading.Lock` 保护 login/logout / refcount 状态
- 调用方 MUST NOT 直接调 `bs.login()` / `bs.logout()`，而是通过 helper

#### Scenario: baostock session 单一入口

- **WHEN** grep `tradingagents/dataflows/providers/china/baostock.py` 内 `bs.login()` / `bs.logout()` 调用
- **THEN** 命中 MUST 仅在单一 session helper / context manager 内
- **AND** 公开方法 MUST 通过 helper 间接使用，不直接 login/logout

### Requirement: 第三方 client 实例须缓存

`tradingagents/dataflows/` 下昂贵构造 + 可复用的第三方 client 实例（如 `yfinance.Ticker`）MUST 缓存复用，禁止每次方法调用重建。

具体：

- 用 `functools.lru_cache` 或显式 dict cache 持有最近 N 个实例
- cache size 默认 ≤ 128（避免无界增长）
- TTL 视 client 行为决定（yfinance.Ticker 内部数据可能过期，需评估）

#### Scenario: yfinance.Ticker 复用

- **WHEN** 重复对同一 symbol 调用 `YFinanceUtils.get_*` 系列方法
- **THEN** `yf.Ticker(symbol)` 构造调用 MUST 最多一次（仅首次实例化）
- **AND** 子序列调用 MUST 命中 cache 返同一 ticker 对象
