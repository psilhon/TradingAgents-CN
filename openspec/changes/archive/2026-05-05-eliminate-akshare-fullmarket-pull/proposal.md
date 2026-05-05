## Why

`docs/code-review-2026-05-05.md` 第三梯队 #3：v1.1.0 修过 `favorites_service` 的 60s 全市场拉取 bug，但 dataflows 仍有 3+ 处同模式。深度探查（spawned audit agent）后修正：

**真正的 agent path 违规（H1/H2）**：
- `improved_hk.py:759,766` `get_hk_stock_info_akshare` 单股查询调 `ak.stock_hk_spot()` 拉全 HK ~3000 行
- `improved_hk.py:275` `get_company_name` 同模式拉全 HK 只为取名字
- 在 agent 路径 + FastAPI async handler 直接调 → `threading.Lock(timeout=60)` **阻塞 event loop ≤60s**

**worker 路径死代码（C1）**：
- `akshare.py:757-830` `_get_realtime_quotes_data` 单股回退分支调 `stock_zh_a_spot()` / `stock_zh_a_spot_em()` 拉 5849 行 A 股 spot
- 仅被 `app/worker/akshare_sync_service.py` 路径调用，非 agent 路径——但仍是死代码（worker 主路径 `get_batch_stock_quotes` 才是合法的全市场拉取）

**audit 修正了 review 的两个误判**：
- `get_batch_stock_quotes` (`akshare.py:545`) **是合法路径**——worker 6 分钟入 mongo `market_quotes` 的设计就需要全市场拉取，保留不动
- review 称 worker 30s sync，实际是 360s（6 分钟），但不影响结论
- mongo `market_quotes` **只 sync A 股**，HK 完全没入库——HK 路径必须切单股 API（不能用 mongo cache shortcut）

## What Changes

### 改动 1：A 股 worker fallback 死代码清理

- **MODIFIED** `tradingagents/dataflows/providers/china/akshare.py`：
  - 删 `_get_realtime_quotes_data` 中 `stock_zh_a_spot()` / `stock_zh_a_spot_em()` 全市场分支（~70 行）
  - 保留主路径 `ak.stock_bid_ask_em(code)` + 兜底 `ak.stock_zh_a_hist(code)`（都是单股 API，已在用）
  - 不动 `get_batch_stock_quotes`（worker 合法全市场拉取）

### 改动 2：HK 路径重构（核心）

- **MODIFIED** `tradingagents/dataflows/providers/hk/improved_hk.py`：
  - `get_hk_stock_info_akshare` (line 759, 766): `ak.stock_hk_spot()` → `ak.stock_hk_security_profile_em(symbol)` + `ak.stock_hk_hist(symbol, period="daily")` 取最近一行
  - `get_company_name` (line 275): 先查内置 `hk_stock_names` mapping，未命中再 `ak.stock_hk_security_profile_em(symbol)`
  - 删 `_akshare_hk_spot_cache` 全局 dict + `_akshare_hk_spot_lock` threading.Lock（~50 行）
  - 字段覆盖度实测：commit 3 在 Python REPL 跑 `ak.stock_hk_security_profile_em("00700")` 验证 `current_price` / `change_percent` 字段存在；如不全降级方案见 spec

### 改动 3：spec 锁定

- **NEW** capability `dataflow-performance`：
  - "agent path 上 dataflows 调用 MUST NOT 拉全市场快照"
  - "单股查询 MUST 走单股 API"
  - "全市场快照仅允许在 worker ingestion 路径"

## Capabilities

### New Capabilities

- `dataflow-performance`：定义"agent path 不得拉全市场" + "单股查询走单股 API"铁律

## Impact

**改动文件**：2 个 Python 文件（akshare.py + improved_hk.py）+ 1 个新 spec
**风险**：中——HK 路径触及多个上游函数（`get_hk_stock_data_akshare` / `interface.get_hk_stock_data_unified`），需保持签名兼容
**收益**：消除 HK 单股查询 60s event loop 阻塞 + 删除 A 股 worker 死代码（~120 行删除，0 行新增逻辑——只是切换到现有单股 API）
