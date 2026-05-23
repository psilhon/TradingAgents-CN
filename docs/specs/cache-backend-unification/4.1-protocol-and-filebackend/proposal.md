## Why

`cache-layer-consolidation` epic（archived `2026-05-22-cache-backend-unification`）的 sub-stage 4.1：进入实施第一步。当前 `tradingagents/dataflows/cache/adaptive.py` 的 `AdaptiveCacheSystem` 把 3 个后端的 save/load 私有方法（`_save_to_file` / `_load_from_file` / `_save_to_redis` / `_load_from_redis` / `_save_to_mongodb` / `_load_from_mongodb`）和路由逻辑混在一个类里——backend 不是可拔插组件，新增 backend / 改后端实现必须改这个类。

本 sub-stage 是**接口抽象 + 文件后端剥离**——通过 `Backend` Protocol 定义可拔插接口，把 `_save_to_file` / `_load_from_file` 拆出到独立 `FileBackend` 类，`AdaptiveCacheSystem` 内部改用 `self.file_backend.save(...)` / `self.file_backend.load(...)`。Redis / Mongo 路径不动（留给 4.2）。

**为什么先 file**：

- File 后端的 save/load 最简单（无 TTL native 支持，无连接管理），抽取风险最低
- File 是 fallback 路径——所有后端失败都降级到文件，行为兼容性最敏感，先在低风险点验证 Protocol 设计
- 4.2 拆 Redis/Mongo 时复用本 sub-stage 定义的 Protocol，避免在 3 个后端拆离过程中反复调整接口

## What Changes

### 新增

- `tradingagents/dataflows/cache/backends/__init__.py` — 子包入口
- `tradingagents/dataflows/cache/backends/_protocol.py` — `Backend` Protocol 定义
- `tradingagents/dataflows/cache/backends/file.py` — `FileBackend` 类（从 `adaptive.py` 拆出 file 路径）

### 修改

- `tradingagents/dataflows/cache/adaptive.py`：
  - `AdaptiveCacheSystem.__init__` 初始化 `self.file_backend = FileBackend(cache_dir=self.cache_dir)`
  - `_save_to_file` / `_load_from_file` 改为薄包装：内部调用 `self.file_backend.save(...)` / `self.file_backend.load(...)`，envelope 构建逻辑（`{"data", "metadata", "timestamp", "backend"}`）保持在 `AdaptiveCacheSystem` 一层（避免本 stage 引入 envelope 契约变更，那是 4.4 的事）
  - 不动 Redis / Mongo 路径

### 新增测试

- `tests/dataflows/cache/test_file_backend.py`：
  - `FileBackend.save` + `FileBackend.load` round-trip（普通 dict / DataFrame envelope / datetime 字段）
  - `FileBackend.load` 不存在的 key → 返回 `None`
  - 文件路径 / 扩展名（`.json.gz`）与原 `_save_to_file` 保持一致
  - `AdaptiveCacheSystem._save_to_file` / `_load_from_file` 经包装层调用 `FileBackend` 后行为等价（同 key 写入读出 envelope 一致）

### 公开 API 行为不变

- `get_cache()` 入口、`save_stock_data` / `load_stock_data` / `find_cached_stock_data` 等公开方法签名与行为完全不变
- 40+ 调用方零改动
- `.json.gz` 缓存文件格式不变（`_serialize.py` 的 envelope 编码不变）

## Capabilities

### Modified Capabilities

- `dataflow-caching`（位于 `docs/specs/dataflow-caching/spec.md`）：ADDED Requirement「Backend Protocol 接口」+ 「FileBackend 单一职责」。spec delta 在 `spec.md` 内追加，**不动**老 `openspec/specs/dataflow-caching/spec.md`（已 superseded 头注）。

## Impact

**改动文件**（4 新 + 2 改）：

- 新：`backends/__init__.py` / `backends/_protocol.py` / `backends/file.py` / `tests/dataflows/cache/test_file_backend.py`
- 改：`adaptive.py`（`_save_to_file` / `_load_from_file` 薄包装化 + `__init__` 加 `self.file_backend`）
- 改：`docs/specs/dataflow-caching/spec.md`（追加 Requirement）

**许可边界**：全部在 `tradingagents/dataflows/cache/`（Apache 2.0）+ `tests/`（Apache 2.0）+ `docs/specs/`。**不动** `app/` / `frontend/`。

**风险**：低

- File 后端无 TTL native / 无连接管理，抽取面小
- 包装层保留 envelope 构建逻辑，序列化契约（`_serialize.py`）零变更
- round-trip 测试 + 公开 API 行为兼容守住调用方零回归

**收益**：

- 为 4.2（Redis/Mongo 拆离）定型 Protocol 接口
- `FileBackend` 单一职责，文件路径 / 序列化集中在一处，未来加新 backend 不再编辑 `adaptive.py`
- 测试可独立验证 backend（不依赖 `AdaptiveCacheSystem` 完整初始化路径）

**回滚**：

单 commit 实现，回滚 = `git revert`。`adaptive.py` 包装层 fallback 到原内联实现即可。
