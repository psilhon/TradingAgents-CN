# Tasks — cache-redis-mongo-backends (sub-stage 4.2)

> epic：`cache-layer-consolidation` stage 4（archived `2026-05-22-cache-backend-unification`）
> 前置：4.1 已完成（commit `e7f17d69`）—— `Backend` Protocol + `FileBackend` 已落
> 体量：~1 天 / 风险：低-中（mongo schema 转换迁出 adaptive 是主要风险点）
> 公开 API 行为零变更；TDD red-green。

## 1. spec delta — commit 1（先于代码）

- [ ] 1.1 在 `docs/specs/dataflow-caching/spec.md` 修改 Requirement「Backend Protocol 接口」：`save` 签名加可选 `ttl_seconds: int | None = None` 参数 + 说明各 backend 的处置语义（file ignore / redis setex / mongo expires_at）
- [ ] 1.2 追加 Requirement「RedisBackend 单一职责」：MUST 仅负责 Redis IO，符合 Backend Protocol；`ttl_seconds=None` 用 `set`，非 None 用 `setex`；`redis_client=None` 时 save → False / load → None 不 raise
- [ ] 1.3 追加 Requirement「MongoBackend 单一职责」：MUST 仅负责 Mongo IO；内部做 envelope ↔ doc schema 转换（`data_type` 字段区分 dataframe / json）；MUST 处理 legacy pickle doc（`data_type == "pickle"` → 删 doc + cache miss + MUST NOT 调 `pickle.loads*`）
- [ ] 1.4 加 Scenario：Redis save with TTL → MUST 调 setex；不带 TTL → MUST 调 set
- [ ] 1.5 加 Scenario：Mongo save 含 DataFrame → doc data_type="dataframe"；普通 dict → doc data_type="json"
- [ ] 1.6 加 Scenario：Mongo load 过期 doc（expires_at < now）→ 返 None + 删 doc
- [ ] 1.7 加 Scenario：Mongo load legacy pickle doc → MUST 返 None + 删 doc + MUST NOT 调 `pickle.loads*`
- [ ] 1.8 **修订** 4.1 Scenario「backends/ 目录依赖洁净度」：`import pandas` 命中 MUST ≤ 1，且唯一允许位置为 `backends/mongo.py`（DataFrame `to_json()` / `pd.read_json` 是 mongo doc schema 转换的存储介质要求，与 redis / file 后端的 envelope bytes round-trip 模式不同）；`import pickle` 命中仍 MUST = 0
- [ ] 1.9 加 Scenario：backends/ 目录全目录 grep `pickle` 命中数 MUST = 0（含 mongo.py 的 legacy 降级路径，因其用字符串比较 `data_type == "pickle"` 而非 import / 调用 pickle）
- [ ] 1.10 commit `docs(spec): cache-backend-unification 4.2 — RedisBackend + MongoBackend 契约`

## 2. red — commit 2（先测试）

### 2.1 RedisBackend 测试

- [ ] 2.1.1 新建 `tests/test_redis_backend.py`（仿 `tests/test_file_backend.py` 的 `spec_from_file_location` 模式避免 dataflows 包副作用）
- [ ] 2.1.2 测试：`RedisBackend(redis_client=mock).save(key, envelope, ttl_seconds=3600)` → mock 收到 `setex(key, 3600, payload)` 调用
- [ ] 2.1.3 测试：`save(key, envelope)` 默认 ttl_seconds=None → mock 收到 `set(key, payload)`（不是 setex）
- [ ] 2.1.4 测试：`RedisBackend(redis_client=None).save(...)` → False，`.load(...)` → None（不 raise）
- [ ] 2.1.5 测试：`load` 不存在 key（mock get 返 None）→ None
- [ ] 2.1.6 测试：DataFrame envelope round-trip（mock get 返回 encode_envelope 的 bytes）→ shape / columns 保持
- [ ] 2.1.7 测试：datetime envelope round-trip → 时间值保持

### 2.2 MongoBackend 测试

- [ ] 2.2.1 新建 `tests/test_mongo_backend.py`
- [ ] 2.2.2 测试：`MongoBackend(mongodb_client=mock).save(key, envelope_with_dataframe, ttl_seconds=3600)` → mock collection 收到 `replace_one` with `data_type="dataframe"` + `expires_at = now + 3600s`（容差 ±2s）
- [ ] 2.2.3 测试：save 普通 dict envelope → `data_type="json"`
- [ ] 2.2.4 测试：`load(key)` 经 mock find_one 返 valid doc → 重建 envelope dict（`data` / `metadata` / `timestamp` / `backend="mongodb"`）
- [ ] 2.2.5 测试：load 过期 doc（expires_at < now）→ None + mock collection 收到 `delete_one`
- [ ] 2.2.6 测试：load legacy pickle doc（data_type="pickle"）→ None + mock collection 收到 `delete_one` + MUST NOT 调任何 `pickle.*` 方法（用 `unittest.mock.patch('pickle.loads')` 守护）
- [ ] 2.2.7 测试：`MongoBackend(mongodb_client=None).save(...)` → False，`.load(...)` → None
- [ ] 2.2.8 测试：DataFrame envelope round-trip（mock find_one 返 `data_type="dataframe"` + `to_json()` 字符串）→ shape / columns 保持

### 2.3 跑测试 + commit

- [ ] 2.3.1 跑 `just test`（pytest -m unit）：新测试 MUST 全部 FAIL（红——RedisBackend / MongoBackend 尚未实现）
- [ ] 2.3.2 commit `test(cache): Redis/Mongo Backend round-trip + legacy pickle 降级（red）`

## 3. green — commit 3（实现 + 包装层接入）

### 3.1 Protocol 扩展

- [ ] 3.1.1 修改 `_protocol.py`：`save` 签名加 `ttl_seconds: int | None = None` + docstring 说明各 backend 处置语义
- [ ] 3.1.2 修改 `file.py`：`FileBackend.save` 签名加 `ttl_seconds` 参数（ignore，仅文档说明）

### 3.2 RedisBackend 实现

- [ ] 3.2.1 新建 `backends/redis.py`
- [ ] 3.2.2 `RedisBackend.__init__(redis_client)` 注入客户端，无 mkdir 等副作用
- [ ] 3.2.3 `save(key, envelope, ttl_seconds=None)` — `redis_client=None` 立即 return False；否则 `encode_envelope` + `setex` / `set`；异常 catch 返 False
- [ ] 3.2.4 `load(key)` — `redis_client=None` 立即 return None；否则 `get` + `decode_envelope`；未命中 / 解码失败返 None

### 3.3 MongoBackend 实现

- [ ] 3.3.1 新建 `backends/mongo.py`
- [ ] 3.3.2 `MongoBackend.__init__(mongodb_client, db_name="tradingagents", collection_name="cache")` 注入客户端
- [ ] 3.3.3 `save(key, envelope, ttl_seconds=None)` — envelope schema 拆解 + DataFrame `to_json()` / 普通 `json.dumps(default=str)` + 构 doc + `replace_one(upsert=True)`
- [ ] 3.3.4 `load(key)` — `find_one` → 过期检查 + `delete_one` 短路 → legacy pickle 降级（`data_type == "pickle"` 删 doc + None） → 按 data_type 反序列化重建 envelope
- [ ] 3.3.5 legacy 降级路径 MUST NOT import pickle / 调 pickle.loads（用 `data_type == "pickle"` 字符串比较即可）

### 3.4 包装层接入

- [ ] 3.4.1 修改 `backends/__init__.py` re-export `RedisBackend` + `MongoBackend`
- [ ] 3.4.2 修改 `adaptive.py`：`__init__` 加 `self.redis_backend = RedisBackend(self.db_manager.get_redis_client())` + `self.mongo_backend = MongoBackend(self.db_manager.get_mongodb_client())`
- [ ] 3.4.3 `_save_to_redis` 改薄包装：build envelope（含 timestamp / backend="redis"）+ `self.redis_backend.save(key, envelope, ttl_seconds)`
- [ ] 3.4.4 `_load_from_redis` 改：`return self.redis_backend.load(key)`
- [ ] 3.4.5 `_save_to_mongodb` 改薄包装：build envelope + `self.mongo_backend.save(key, envelope, ttl_seconds)`
- [ ] 3.4.6 `_load_from_mongodb` 改：`return self.mongo_backend.load(key)`
- [ ] 3.4.7 删除 adaptive.py 中现在已不用的 import：`json` / `pd` / `StringIO` / `timedelta`（若不再被其它路径用）—— 谨慎检查每个 import 的剩余引用再删

### 3.5 验证

- [ ] 3.5.1 跑 `just test`：新 + 老测试 MUST 全绿
- [ ] 3.5.2 跑 `just lint` + `just typecheck`：MUST 全绿
- [ ] 3.5.3 跑 `just audit-binds` / `just audit-ports`：MUST 全绿
- [ ] 3.5.4 grep `pickle` in `tradingagents/dataflows/cache/`：命中数 MUST = 0（dataflow-caching capability 红线）
- [ ] 3.5.5 commit `feat(cache): Redis/Mongo Backend 单一职责 + adaptive 包装层接入（green）`

## 4. 行为兼容验证（push 前）

- [ ] 4.1 起 backend（`just up`）+ Python REPL：`from tradingagents.dataflows.cache import get_cache; c = get_cache(); c.save_stock_data("000001", {"k":"v"}, "2026-01-01", "2026-01-02", "test")` → 验证 Redis / Mongo doc 实际写入（用 `redis-cli` / `mongosh` 查）
- [ ] 4.2 验证存量 MongoDB cache doc（如有）能被新 MongoBackend 正常 load——schema 字节级兼容
- [ ] 4.3 验证 legacy pickle doc（如有；可手工 insert 一个 `data_type="pickle"` 测试 doc）经 load 返 None + 被自动删除
- [ ] 4.4 `just ci` 完整流水线绿灯
- [ ] 4.5 `just down`

## 5. 收尾

- [ ] 5.1 更新 `docs/CHANGELOG.md` `[Unreleased]` 段加条目
- [ ] 5.2 commit `docs(changelog): cache backend 4.2 — Redis/Mongo Backend 抽出`
- [ ] 5.3 push main（1 click HARD-GATE）

## 6. 后续 sub-stage 触发

- [ ] 6.1 本 sub-stage merge 后 → 开 4.3 `cache-config-dataclass`（CacheConfig 统一 dataclass，体量 1-2 天 / 中风险）

## 验证清单（每个 commit 前）

- 公开 API 签名 / 行为零改动
- `get_cache()` 返回实例的所有 `save_*_data` / `load_*_data` 行为等价
- Redis bytes / MongoDB doc 字节级 / 字段级兼容
- 老 MongoDB pickle doc 经 load 触发降级（删 doc + None），**永远不**走 unpickle
- `tradingagents/dataflows/cache/` grep `pickle` 仍为 0
- backends/ 目录依赖洁净：不 import pandas（除 mongo.py 必须，因 DataFrame 序列化逻辑迁入 backend）/ 不 import pickle / 仅允许 _serialize 作为 dataflow 内部依赖

## 与 4.1 的差异点

- 4.1 Protocol 只有 `save(key, envelope) -> bool`；4.2 扩 `ttl_seconds` 可选参数
- 4.1 FileBackend 是纯 envelope round-trip；4.2 MongoBackend 是 envelope ↔ doc schema 转换（更复杂）
- 4.1 无 legacy 兼容；4.2 MongoBackend 含 legacy pickle 降级路径
- 4.1 backend 不 import pandas；4.2 mongo.py MUST import pandas（DataFrame `to_json()` / `pd.read_json` 在 backend 内）—— spec 显式允许 mongo.py 例外
