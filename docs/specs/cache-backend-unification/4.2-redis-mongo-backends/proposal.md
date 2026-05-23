## Why

`cache-layer-consolidation` epic（archived `2026-05-22-cache-backend-unification`）的 sub-stage 4.2，紧接 4.1（`Backend` Protocol + `FileBackend` 已落，commit `e7f17d69`）。

`AdaptiveCacheSystem` 现存仍有 2 个后端的 save/load 私有方法 + 内联序列化逻辑混在 `adaptive.py`：

- `_save_to_redis` / `_load_from_redis`（adaptive.py L89-L125）— 用 `_serialize.py` envelope round-trip，但 TTL 必须传 `setex`
- `_save_to_mongodb` / `_load_from_mongodb`（adaptive.py L127-L201）— 不走 envelope round-trip，而是 doc schema 转换：DataFrame → `to_json()` / 其它 → `json.dumps(default=str)`，含 `data_type` 字段区分；load 时检查 `expires_at` 过期 + 重建 envelope；含 **legacy pickle 降级路径**（`data_type == "pickle"` → 删 doc + cache miss）

按 4.1 spec delta 已明示：「`list_keys` / `delete` will be added when 4.2 ... actually need them」——4.2 是首次需要扩 Protocol 接口的 sub-stage。

## What Changes

### Protocol 接口扩展（向前兼容）

`Backend.save` 签名加可选 `ttl_seconds` 参数：

```python
def save(self, key: str, envelope: dict, ttl_seconds: int | None = None) -> bool: ...
```

- `FileBackend.save` 接受 `ttl_seconds` 但 **ignore**（文件后端无 native TTL，依赖 `AdaptiveCacheSystem._is_cache_valid` 做过期判定，行为与 4.1 完全一致）
- `RedisBackend.save` 用 `ttl_seconds` 走 `setex(key, ttl, payload)`；`ttl_seconds=None` 时走普通 `set`（无过期）
- `MongoBackend.save` 用 `ttl_seconds` 设 `expires_at = now + timedelta(seconds=ttl_seconds)`；`ttl_seconds=None` 时不设 expires_at

`Backend.load(key) -> dict | None` 接口不变（4.1 已定型）。

### 新增

- `tradingagents/dataflows/cache/backends/redis.py` — `RedisBackend` 类
  - `__init__(redis_client)` 注入 redis 客户端（从 `db_manager.get_redis_client()` 来；`None` 时所有方法直接 return False/None）
  - `save(key, envelope, ttl_seconds)` — `encode_envelope` 走 `setex` / `set`
  - `load(key)` — `get` + `decode_envelope`；未命中或解码失败 return None

- `tradingagents/dataflows/cache/backends/mongo.py` — `MongoBackend` 类
  - `__init__(mongodb_client, db_name="tradingagents", collection_name="cache")` 注入 mongo 客户端
  - `save(key, envelope, ttl_seconds)` — envelope → doc schema 转换：拆出 `data` / `metadata` / `timestamp` / `backend` → 构 doc + DataFrame `to_json()` / 普通 `json.dumps(default=str)` + `data_type` 字段 + `expires_at`；`replace_one(upsert=True)`
  - `load(key)` — `find_one` → 检查 `expires_at` 过期则删 doc + return None → 按 `data_type` 反序列化重建 envelope → return；**legacy pickle 降级**：`data_type == "pickle"` 时删 doc + log + return None（**MUST NOT** 调 `pickle.loads`）

### 修改

- `_protocol.py`：扩 `save` 签名加 `ttl_seconds` 参数 + docstring 说明
- `file.py`：`save` 签名加 `ttl_seconds`（ignore），向后兼容
- `adaptive.py`：
  - `__init__` 初始化 `self.redis_backend = RedisBackend(...)` + `self.mongo_backend = MongoBackend(...)`
  - `_save_to_redis` / `_load_from_redis` / `_save_to_mongodb` / `_load_from_mongodb` 改薄包装委托 backend
  - envelope 构建保留在上层（同 4.1 file 路径）
  - mongo schema 转换 **迁入 MongoBackend**（不在 adaptive 层）——这是 backend 内部存储介质细节，不该泄漏到 cache 层

### 新增测试

- `tests/test_redis_backend.py`：mock redis client，覆盖
  - save + load round-trip
  - `ttl_seconds=None` 用 `set`；非 None 用 `setex`
  - `redis_client=None` 时 save → False / load → None（不 raise）
  - load 不存在 key 返 None
  - DataFrame / datetime envelope round-trip（依赖 `_serialize.py`）

- `tests/test_mongo_backend.py`：mock mongo client + collection，覆盖
  - save 构 doc 正确（`_id` / `data_type` / `expires_at` 字段）
  - DataFrame envelope → `data_type="dataframe"`，普通 dict envelope → `data_type="json"`
  - load 重建 envelope（含 `data` / `metadata` / `timestamp` / `backend="mongodb"`）
  - 过期 doc（`expires_at < now`）load 返 None + 删 doc
  - **legacy pickle 降级**：`data_type="pickle"` doc 经 load 返 None + 删 doc + MUST NOT 调 `pickle.loads`
  - `mongodb_client=None` 时 save → False / load → None

### 公开 API 行为不变

- `get_cache()` 入口、`save_stock_data` / `load_stock_data` / `find_cached_stock_data` 等公开方法签名与行为完全不变
- 40+ 调用方零改动
- Redis / MongoDB 存储格式不变（envelope bytes / doc schema 字节级一致）
- 老 MongoDB pickle doc 仍能触发降级（删 doc + cache miss）

## Capabilities

### Modified Capabilities

- `dataflow-caching`（位于 `docs/specs/dataflow-caching/spec.md`）：扩 Requirement「Backend Protocol 接口」加 `ttl_seconds` 可选参数 + ADDED Requirement「RedisBackend 单一职责」+ 「MongoBackend 单一职责（含 legacy pickle 降级）」。新 Scenario：redis round-trip / mongo doc schema / legacy pickle 降级路径。
- **修订 4.1 Scenario**「backends/ 目录依赖洁净度」：`import pandas` 命中数 MUST ≤ 1 且唯一允许位置为 `backends/mongo.py`（DataFrame `to_json()` / `pd.read_json` 是 mongo doc schema 转换的存储介质要求；redis / file 后端仍是纯 envelope bytes round-trip，不允许 import pandas）。`import pickle` 命中仍 MUST = 0。

> **设计权衡记录**：mongo backend 之所以必须 import pandas，是因为 MongoDB 的 doc-typed schema 要求 `data` 字段是 string（而非 raw bytes）——历史 schema 经 stage 2 `cache-pickle-replacement` 沉淀为 `data_type` + `df.to_json()` / `json.dumps()` 模式，已 stable。重新设计 mongo 为「envelope bytes 存 Binary 字段」可让 mongo 像 redis / file 一样纯 round-trip，但会破坏现存 doc 向后兼容（需要双格式 reader），超出 4.2 范围（1 天体量）。该重设计可在 4.4 (`Cache` 类抽象重设计) 或 4.6 (deprecated 层清理) 时一并评估。

## Impact

**改动文件**（6 新 + 3 改）：

- 新：`backends/redis.py` / `backends/mongo.py` / `tests/test_redis_backend.py` / `tests/test_mongo_backend.py`
- 改：`backends/_protocol.py`（save 加 ttl_seconds）/ `backends/file.py`（save 加 ttl_seconds ignore）/ `backends/__init__.py`（re-export RedisBackend + MongoBackend）
- 改：`adaptive.py`（4 个 `_save/load_to/from_*` 方法薄包装化）+ `docs/specs/dataflow-caching/spec.md`（追加 Requirement + Scenario）

**许可边界**：全部在 `tradingagents/dataflows/cache/`（Apache 2.0）+ `tests/`（Apache 2.0）+ `docs/specs/`。**不动** `app/` / `frontend/`。

**风险**：低-中

- 主要风险点：Mongo backend 的 doc schema 转换迁出 adaptive.py——schema 已 stable（stage 2 cache-pickle-replacement 沉淀），单元测试守住等价
- legacy pickle 降级路径回归保护（spec 2 个 Scenario + test_mongo_backend.py 显式断言不调 `pickle.loads`）
- Protocol 扩 `ttl_seconds` 参数对 file backend 是 ignore，向后兼容
- mock 测试不依赖真 Redis / MongoDB，CI 不需要起服务

**收益**：

- 3 个 backend 拓扑完整，4.3 起可以引入 `CacheConfig` 统一 schema 而不必同时改后端
- backend 的存储介质细节（redis `setex` / mongo `expires_at` / pickle 降级）封装在自己模块内，`adaptive.py` 不再含介质相关代码
- 单元测试可独立验证每个 backend（mock client），不依赖 `AdaptiveCacheSystem` 完整初始化

**回滚**：

单 sub-stage 串行 4 个 commit（spec → red → green → CHANGELOG），回滚 = `git revert` 4 个 commit。adaptive.py 包装层 fallback 到原内联实现即可。
