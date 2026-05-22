## Why

`docs/code-review-2026-05-05.md` 第三梯队架构重构项 `cache-layer-consolidation`。

`tradingagents/dataflows/cache/` 共 **2750 行 / 6 文件 / 4 套缓存实现 + 2 条旁路**：

| 实现 | 文件 | 状态 |
|---|---|---|
| `StockDataCache` | `file_cache.py`（688 行） | live — 文件兜底，被 `IntegratedCacheManager` 包装 |
| `AdaptiveCacheSystem` | `adaptive.py`（423 行） | live — 多后端，被 `IntegratedCacheManager` 包装 |
| `IntegratedCacheManager` | `integrated.py`（383 行） | live — `get_cache()` 入口 |
| `DatabaseCacheManager` | `db_cache.py`（546 行） | **死代码** |
| `MongoDBCacheAdapter`（旁路） | `mongodb_cache_adapter.py`（445 行） | live — 14+ 调用方 |
| 函数旁路 | `app_adapter.py`（120 行） | live |

**全量收敛（4 实现 → 1 抽象 + 换 pickle + 统一 config）≈ 1-2 周、跨多数据流文件、高风险**——故分阶段。本 change 是**阶段 1**，只做两件安全的事：删死代码 + 抽公共 helper。

**死代码确证**（grep 全仓 `*.py`，排除 `.venv` / `__pycache__`）：

- `db_cache.py` 的 `get_db_cache()` 工厂——**零调用方**
- `DatabaseCacheManager` 类——仅被 `cache/__init__.py` 重导出（try-import + `__all__`），**无任何外部消费者**
- 即整个 `db_cache.py`（Redis+MongoDB 双写实现，546 行）完全 orphaned

**冗余**：MD5 cache-key 生成 / TTL 解析 / 序列化策略，在 `file_cache.py`、`adaptive.py`、（待删的）`db_cache.py` 各有一份独立实现。

## What Changes

### 阶段定位

`cache-layer-consolidation` 的 **stage 1 / N**。本 change 只做安全改动；pickle 替换、config 统一、4 实现合并均为后续独立 change（见「不在范围」）。

### Part A — 删除 `db_cache.py` 死代码

- 删除 `tradingagents/dataflows/cache/db_cache.py` 整文件（546 行）
- `cache/__init__.py`：删除 `from .db_cache import DatabaseCacheManager` 的 try-import 块（含 `except` 分支的 `DatabaseCacheManager = None`）+ `__all__` 里的 `"DatabaseCacheManager"`
- **零行为风险**——纯删 orphaned 代码

### Part B — 抽公共 helper

- 新建 `tradingagents/dataflows/cache/_common.py`：集中 cache-key 生成（MD5）+ TTL 解析
- 存活的实现（`file_cache.py` / `adaptive.py`）改用 helper，删各自的 inline 实现
- **行为保持要求**：helper 对代表性输入 MUST 产出与原实现**逐字节一致**的 cache-key——否则既有磁盘 / MongoDB 缓存条目全部 miss（冷启动，非正确性 bug，但 proposal 显式声明）

### Part B 的前置契约（tasks 内核对）

`file_cache.py` 与 `adaptive.py` 的 key scheme 是否兼容需在实施时先确认：

- **兼容** → 抽出统一 `make_cache_key()`，两实现共用
- **不兼容** → Part B 缩为仅抽 TTL 解析 helper（或该子项拆出为后续 change）；不强行合并不兼容的 key scheme

### 不在范围（后续独立 change）

- `pickle` → JSON/gzip 安全替换（`adaptive.py` 7 处 `pickle.dump/load`）
- `TA_CACHE_STRATEGY` / `TA_USE_APP_CACHE` / `USE_MONGODB_STORAGE` 三开关的 config 统一
- 4 套实现合并为单一后端抽象
- `app_adapter.py` / `mongodb_cache_adapter.py` 两条旁路（均 live，14+ 调用方，独立 concern）

## Capabilities

### New Capabilities

- `dataflow-caching`：dataflows 缓存层的模块清单与共用约束。锁定——无孤儿缓存实现；cache-key 生成与 TTL 解析经单一 helper，不得在各实现内重复。后续阶段的 change 扩充本 capability。

## Impact

**改动文件**：删 1（`db_cache.py`）+ 改 `cache/__init__.py` + 改 `file_cache.py` + 改 `adaptive.py` + 新建 `_common.py` + 1 新建 test + 1 spec + 1 CHANGELOG 段

**许可边界**：全部在 `tradingagents/dataflows/cache/`（Apache 2.0）——不触及 `app/` `frontend/`。

**风险**：
- Part A：零行为风险（纯删 orphaned 死代码）。实施前 tasks 内再次 grep 复核 + 查 `importlib` / 字符串动态导入。
- Part B：中等——key 生成抽取必须逐字节保持，需 byte-identical 测试护栏；若两实现 key scheme 不兼容则按前置契约缩范围。

**收益**：
- 缓存层 2750 → ~2200 行（删 db_cache）
- key 生成 / TTL 从「每实现一份」收敛为单一 helper
- 新 capability 起头，为后续 consolidation 阶段建立 spec 锚点
