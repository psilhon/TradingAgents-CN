# dataflow-performance Specification

## Purpose
TBD - created by archiving change eliminate-akshare-fullmarket-pull. Update Purpose after archive.
## Requirements
### Requirement: agent path 上 dataflows 调用不得拉全市场快照

任何在 LangGraph agent 节点 / FastAPI request 路径上的 dataflows 调用 MUST NOT 触发"全市场快照"API（如 `ak.stock_zh_a_spot` / `ak.stock_zh_a_spot_em` / `ak.stock_hk_spot` / `ak.stock_us_spot` 等"传 1 个 code 但拉数千行"的接口）。

允许场景：
- worker / scheduler / cron 路径下的全市场 ingestion（如 `app/services/quotes_ingestion_service.py` 的 6 分钟入库循环）—— 这些是异步 / 后台执行，不阻塞用户请求

#### Scenario: agent path 单股查询不应触发全市场拉取

- **WHEN** 用户发起对单只股票的分析请求（agent / API）
- **AND** dataflows 在响应路径上被调用
- **THEN** 调用栈中 MUST NOT 出现 `ak.stock_zh_a_spot` / `ak.stock_zh_a_spot_em` / `ak.stock_hk_spot` 字面调用
- **AND** 单股查询 MUST 走单股 API（`stock_bid_ask_em` / `stock_zh_a_hist` / `stock_hk_security_profile_em` / `stock_hk_hist`）

#### Scenario: 全市场拉取调用点必须在 worker 模块

- **WHEN** 在仓库 grep `ak\.\(stock_zh_a_spot\|stock_hk_spot\)`
- **THEN** 命中位点 MUST 全部在 `tradingagents/dataflows/providers/*/akshare.py` 的 `get_batch_stock_quotes` 等 worker-ingestion 接口中
- **AND** 这些接口的调用方 MUST 在 `app/worker/` 或 `app/services/quotes_ingestion_service.py`（async / 后台路径）

### Requirement: HK 单股查询禁用 threading.Lock 阻塞

`improved_hk.py` 中 HK 数据查询 MUST NOT 用 `threading.Lock(timeout=N)` 保护 sync HTTP 调用——sync lock 在 async 调用方（FastAPI handler / agent node）会阻塞 event loop。

如确实需要 lock 序列化（避免并发重复请求），MUST 用 `asyncio.Lock` + `await lock.acquire()`。但**首选**是切换到单股 API 后**完全删除 lock**——单股 API 1KB 而非 1MB，限流压力小 3 个量级，并发重复请求成本可接受。

#### Scenario: improved_hk.py 不含 threading.Lock

- **WHEN** 在 `tradingagents/dataflows/providers/hk/improved_hk.py` grep `threading\.Lock\|threading\.lock`
- **THEN** 命中数 MUST = 0

#### Scenario: HK 单股查询响应时间

- **WHEN** 用户对单只 HK 股票发起 `get_hk_stock_data` / `get_hk_stock_info` 调用
- **AND** 后端无可用 mongo cache（HK 数据 worker 不 sync）
- **THEN** 响应时间 MUST < 5s（之前 60s 因 threading.Lock + 全市场拉取）

