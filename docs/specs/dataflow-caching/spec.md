# dataflow-caching Specification

## Purpose

锁定 `tradingagents/dataflows/cache/` 缓存层的模块清单与共用约束。本 capability 由 `cache-layer-consolidation` 的 stage 1（`cache-layer-cleanup-stage1`）起头——确立「无孤儿缓存实现」基线。缓存层的全量收敛（cache-key / TTL 统一、`pickle` 安全替换、4 套实现合并为单一后端抽象）为后续阶段，届时扩充本 capability。

## Requirements

### Requirement: 无孤儿缓存实现

`tradingagents/dataflows/cache/` 下的每个缓存实现模块 MUST 有实际消费者（被 live 数据流代码路径引用），不得保留 orphaned / 仅被 `__init__.py` 重导出而无人消费的缓存实现。

本 capability 起点（stage 1）后，缓存层存活实现为：

- `file_cache.StockDataCache` — 文件后端
- `adaptive.AdaptiveCacheSystem` — 多后端
- `integrated.IntegratedCacheManager` — 包装层，`get_cache()` 入口
- `mongodb_cache_adapter.MongoDBCacheAdapter` — MongoDB 旁路（独立路径）
- `app_adapter` 函数 — app MongoDB 旁路

`db_cache.DatabaseCacheManager`（Redis+MongoDB 双写）已确证 orphaned 并删除。

#### Scenario: 缓存实现可达性检查

- **WHEN** 在全仓 grep 某缓存类 / 工厂函数
- **THEN** 除定义处与 `__init__.py` 重导出外，MUST 至少有一个 live 调用方
- **AND** 无调用方的缓存实现模块 MUST 删除，不得仅靠 `__init__.py` 重导出续命

### Requirement: 缓存序列化禁用 pickle

`tradingagents/dataflows/cache/` 下任何缓存实现 MUST NOT 使用 `pickle.load` / `pickle.loads` / `pickle.dump` / `pickle.dumps` 进行缓存数据的序列化或反序列化。

序列化 MUST 走安全格式（JSON / JSON+gzip 等纯数据格式），不得使用任何可在反序列化时执行任意代码的格式。

非 JSON 原生类型（如 `datetime`、`pandas.DataFrame`）MUST 经显式 tagged 编码或类型转换处理（如 `df.to_json(orient='split')` 配 `pd.read_json` 重建），不得回退到 pickle。

历史遗留的 pickle 缓存条目（旧 `.pkl` 文件 / Redis pickle bytes / MongoDB `data_type="pickle"` doc）MUST 在加载时视为 cache miss 直接降级，**禁止**对其调用任何 `pickle.load*`——后续清理走 `unlink()` / TTL 过期 / `delete_one` 而非反序列化。

#### Scenario: 缓存层 pickle grep 检查

- **WHEN** 在 `tradingagents/dataflows/cache/` 全目录 grep `pickle`
- **THEN** 命中数 MUST = 0（含 `import pickle` / `pickle.load*` / `pickle.dump*`）

#### Scenario: 老 pickle 数据降级路径

- **WHEN** 加载逻辑遇到旧格式（`.pkl` 文件 / 非 JSON Redis bytes / `data_type="pickle"` MongoDB doc）
- **THEN** MUST 返回 cache miss（None）
- **AND** MUST NOT 调用 `pickle.loads` 或 `pickle.load`
- **AND** 可清理（unlink / delete_one），但绝不反序列化

#### Scenario: DataFrame 序列化

- **WHEN** 缓存值为 `pandas.DataFrame`
- **THEN** MUST 经 `df.to_json(orient='split')` + `pd.read_json` 往返
- **AND** shape / columns / 数值 MUST 在 round-trip 后保持

> 注：cache-key 生成 / TTL 解析的 helper 统一原属本 capability stage 1（Part B），调查后确认 `file_cache` 与 `adaptive` 的 key scheme / TTL 配置不兼容，无安全的行为保持抽取目标——该项 deferred 到后续「全量收敛」stage，与后端抽象重设计一并做。

### Requirement: Backend Protocol 接口

`tradingagents/dataflows/cache/backends/_protocol.py` MUST 定义 `Backend` Protocol（`typing.Protocol`），作为可拔插缓存后端的最小契约。Protocol 接口 MUST 覆盖：

- `save(key: str, envelope: dict, ttl_seconds: int | None = None) -> bool` — 将 envelope dict 写入后端；`ttl_seconds` 是 backend native TTL（redis `setex` / mongo `expires_at`），`None` 表示不设过期或后端无 native TTL（file 后端忽略）；成功返回 `True`，失败返回 `False`（不 raise）
- `load(key: str) -> dict | None` — 从后端读取 envelope dict；不存在 / 读取失败返回 `None`（不 raise）

Protocol MUST NOT 包含：

- 后端路由 / fallback 选择（由 cache 顶层负责）
- envelope 构建（`timestamp` / `backend` 标签等元数据由调用方填充）
- 缓存策略判定（哪个 backend 优先 / 何时降级 / TTL 配置来源等——这些是 cache 层职责，backend 只接收 `ttl_seconds` 数值参数）

> 注：4.1 阶段 Protocol 不含 `ttl_seconds`；4.2 扩入该参数因 Redis / Mongo 都需要 native TTL 而 File 后端无该需求（仍 ignore 参数保持 4.1 行为）。`list_keys` / `delete` 仍 deferred 到实际需要的 sub-stage。

后端实现 MUST 保持「字节进字节出」的薄层职责——把 envelope dict 经 `_serialize.py` 的 `encode_envelope` / `decode_envelope` 与底层存储介质双向转换，不解释 envelope 内部结构（**MongoBackend 例外**：见下方 Requirement，因 mongo doc schema 要求 `data` 字段为 typed string 而非 raw bytes）。

#### Scenario: Protocol 接口最小性

- **WHEN** 检查 `Backend` Protocol 定义
- **THEN** MUST 仅含 `save` / `load` 方法签名（4.2 阶段），不含路由 / envelope 构建 / 缓存策略相关方法
- **AND** `save` 签名 MUST 含 `ttl_seconds: int | None = None` 参数；`load` 签名不变
- **AND** 任何 backend 实现 MUST 通过 `isinstance(impl, Backend)` 结构性检查（Protocol 鸭子类型）

### Requirement: FileBackend 单一职责

`tradingagents/dataflows/cache/backends/file.py` 的 `FileBackend` 类 MUST 仅负责文件 IO，符合 `Backend` Protocol。具体：

- `__init__(cache_dir: Path)` — 接收缓存目录，MUST `mkdir(parents=True, exist_ok=True)` 确保存在
- `save(key, envelope) -> bool` — 写入 `{cache_dir}/{key}.json.gz`，经 `encode_envelope` 编码；失败返回 `False`
- `load(key) -> dict | None` — 读取 `{cache_dir}/{key}.json.gz`，经 `decode_envelope` 解码；文件不存在或解码失败返回 `None`

`FileBackend` MUST NOT：

- 调用 `AdaptiveCacheSystem` / `IntegratedCacheManager` / `StockDataCache` 等上层类
- 解释 envelope 内字段（`timestamp` / `backend` / `data` / `metadata` 等仅作为 opaque dict 传递）
- import `pandas` / `pickle` / 业务逻辑模块（`tradingagents.dataflows` 以下任何 dataflow 模块）

#### Scenario: FileBackend save + load round-trip

- **WHEN** 调用 `FileBackend(cache_dir=tmp).save(key, envelope)` 写入任意 dict
- **AND** 同实例调用 `FileBackend(cache_dir=tmp).load(key)`
- **THEN** 返回的 dict MUST 与写入的 envelope 等价（含 `data` / `metadata` / `timestamp` / `backend` 等字段类型与值保持）
- **AND** 文件路径 MUST == `{cache_dir}/{key}.json.gz`（扩展名 `.json.gz` 来自 `_serialize.py` envelope 格式）

#### Scenario: FileBackend.load 不存在的 key

- **WHEN** 调用 `FileBackend(cache_dir=tmp).load("nonexistent_key")`
- **THEN** MUST 返回 `None`
- **AND** MUST NOT raise（异常已在内部 catch + 错误日志）

#### Scenario: backends/ 目录依赖洁净度

- **WHEN** 在 `tradingagents/dataflows/cache/backends/` 全目录 grep `import pandas`
- **THEN** 命中数 MUST ≤ 1，且唯一允许位置为 `backends/mongo.py`（DataFrame `to_json()` / `pd.read_json` 是 mongo doc schema 转换的存储介质要求；redis / file 后端仍是纯 envelope bytes round-trip，不允许 import pandas）
- **WHEN** 在同目录 grep `import pickle`
- **THEN** 命中数 MUST = 0（mongo.py 的 legacy 降级路径用 `data_type == "pickle"` 字符串比较，不 import / 调用 pickle）
- **AND** 在该目录 grep `from tradingagents.dataflows` 命中 MUST 仅指向 `tradingagents.dataflows.cache._serialize`（serialize helper 是允许的依赖）

### Requirement: RedisBackend 单一职责

`tradingagents/dataflows/cache/backends/redis.py` 的 `RedisBackend` 类 MUST 仅负责 Redis IO，符合 `Backend` Protocol。具体：

- `__init__(redis_client)` — 接收 redis 客户端实例（可为 `None`，由 `db_manager.get_redis_client()` 决定）；MUST 无副作用（不 connect / 不 ping）
- `save(key, envelope, ttl_seconds=None) -> bool` — `redis_client=None` 立即 return `False`；否则 `encode_envelope(envelope)` → `setex(key, ttl_seconds, payload)` 若 `ttl_seconds` 非 None，否则 `set(key, payload)`；异常 catch 返 `False`
- `load(key) -> dict | None` — `redis_client=None` 立即 return `None`；否则 `redis_client.get(key)` → `decode_envelope`；未命中 / 解码失败返 `None`

`RedisBackend` MUST NOT：

- import `pandas` / `pickle`
- 解释 envelope 内字段（同 FileBackend，envelope 为 opaque dict）

#### Scenario: RedisBackend save with TTL

- **WHEN** 调用 `RedisBackend(client).save(key, envelope, ttl_seconds=3600)`
- **THEN** MUST 调 `client.setex(key, 3600, encoded_bytes)`
- **AND** MUST NOT 调 `client.set`

#### Scenario: RedisBackend save without TTL

- **WHEN** 调用 `RedisBackend(client).save(key, envelope)`（ttl_seconds 默认 None）
- **THEN** MUST 调 `client.set(key, encoded_bytes)`
- **AND** MUST NOT 调 `client.setex`

#### Scenario: RedisBackend 无客户端降级

- **WHEN** 调用 `RedisBackend(None).save(...)`
- **THEN** MUST 返 `False`
- **AND** MUST NOT raise
- **WHEN** 调用 `RedisBackend(None).load(...)`
- **THEN** MUST 返 `None`
- **AND** MUST NOT raise

### Requirement: MongoBackend 单一职责（含 legacy pickle 降级）

`tradingagents/dataflows/cache/backends/mongo.py` 的 `MongoBackend` 类 MUST 仅负责 MongoDB IO，符合 `Backend` Protocol。具体：

- `__init__(mongodb_client, db_name="tradingagents", collection_name="cache")` — 接收 mongo 客户端实例（可为 `None`）
- `save(key, envelope, ttl_seconds=None) -> bool` — envelope schema 拆解 → 构造 doc：
  - DataFrame `data` 字段 → `df.to_json(orient='split')` + `data_type="dataframe"`
  - 其它 `data` 字段 → `json.dumps(default=str)` + `data_type="json"`
  - 含 `_id=key` / `metadata` / `timestamp` / `expires_at`（仅 `ttl_seconds` 非 None 时设置）/ `backend="mongodb"`
  - `replace_one({"_id": key}, doc, upsert=True)`
- `load(key) -> dict | None` — `find_one({"_id": key})`：
  - doc 不存在 → 返 `None`
  - `expires_at` 已过期 → 删 doc + 返 `None`
  - `data_type="dataframe"` → `pd.read_json(StringIO(data))` 重建 DataFrame
  - `data_type="json"` → `json.loads(data)` 重建
  - `data_type="pickle"`（legacy） → 删 doc + log + 返 `None`，**MUST NOT** 调任何 `pickle.load*` / `pickle.loads`
  - 重建为 envelope `{data, metadata, timestamp, backend="mongodb"}` 返回

`MongoBackend` MUST：

- import `pandas`（DataFrame `to_json` / `pd.read_json` 是 doc schema 转换内部细节）
- 处理 schema 字段（`data_type` / `expires_at`）——这与 FileBackend 的 opaque envelope 模式不同，是 mongo 存储介质特有

`MongoBackend` MUST NOT：

- import `pickle`（legacy 降级用字符串比较即可）
- 调用 `pickle.loads` / `pickle.load`（对 legacy pickle doc 直接删 + cache miss）

#### Scenario: MongoBackend save DataFrame envelope

- **WHEN** 调用 `MongoBackend(client).save(key, envelope_with_dataframe, ttl_seconds=3600)`
- **THEN** mock collection MUST 收到 `replace_one({"_id": key}, doc, upsert=True)`
- **AND** doc MUST 含 `data_type="dataframe"`
- **AND** doc MUST 含 `expires_at ≈ now + 3600s`（±2s 容差）

#### Scenario: MongoBackend save 普通 dict envelope

- **WHEN** 调用 `MongoBackend(client).save(key, envelope_with_dict)`
- **THEN** doc MUST 含 `data_type="json"`

#### Scenario: MongoBackend load 过期 doc

- **WHEN** 调用 `MongoBackend(client).load(key)`，mock find_one 返 doc with `expires_at < now`
- **THEN** MUST 调 `collection.delete_one({"_id": key})`
- **AND** MUST 返 `None`

#### Scenario: MongoBackend load legacy pickle doc

- **WHEN** 调用 `MongoBackend(client).load(key)`，mock find_one 返 doc with `data_type="pickle"`
- **THEN** MUST 调 `collection.delete_one({"_id": key})`
- **AND** MUST 返 `None`
- **AND** MUST NOT 调用 `pickle.loads` / `pickle.load` 或任何 pickle 模块方法

### Requirement: CacheConfig 单一来源

`tradingagents/dataflows/cache/_config.py` MUST 定义 `CacheConfig` dataclass 作为 cache 层 backend 配置的单一来源。具体：

- `@dataclass(frozen=True)` 修饰，构造后字段不可变（赋值 MUST raise `dataclasses.FrozenInstanceError`）
- 字段：
  - `cache_strategy: Literal["integrated", "adaptive", "file"]` — 顶层 instantiation 决策（`get_cache()` 用），folded `TA_CACHE_STRATEGY` env
  - `primary_backend: Literal["redis", "mongodb", "file"]` — `AdaptiveCacheSystem` 首选 backend，由 db_manager 检测可用性派生
  - `fallback_enabled: bool` — 主 backend 失败时是否降级到 file
  - `ttl_settings: Mapping[str, int]` — `{market}_{data_type}` → TTL seconds，MUST 含 6 个标准 key（`us_stock_data` / `us_news` / `us_fundamentals` / `china_stock_data` / `china_news` / `china_fundamentals`）
- `from_environment(db_manager) -> CacheConfig` classmethod：从 env + db_manager 检测结果构造 CacheConfig 的产线工厂

`CacheConfig` MUST NOT 含：

- `TA_USE_APP_CACHE`（dataflow 数据源优先级开关，与 cache backend 配置正交）
- `cache_dir` 路径 / MongoBackend 的 `db_name` / `collection_name`（构造参数而非配置）

#### Scenario: CacheConfig 不可变

- **WHEN** 构造 `config = CacheConfig(cache_strategy="integrated", primary_backend="redis", fallback_enabled=True, ttl_settings={...})`
- **AND** 尝试 `config.primary_backend = "file"`
- **THEN** MUST raise `dataclasses.FrozenInstanceError`

#### Scenario: from_environment 后端推断三路径

- **WHEN** `db_manager.is_redis_available()` 返 True
- **THEN** `from_environment(db_manager).primary_backend == "redis"`
- **WHEN** redis 不可用但 `db_manager.is_mongodb_available()` 返 True
- **THEN** `from_environment(db_manager).primary_backend == "mongodb"`
- **WHEN** 两者都不可用
- **THEN** `from_environment(db_manager).primary_backend == "file"`

#### Scenario: from_environment 读 TA_CACHE_STRATEGY

- **WHEN** env `TA_CACHE_STRATEGY` 未设置
- **THEN** `from_environment(db_manager).cache_strategy == "integrated"`（默认）
- **WHEN** `TA_CACHE_STRATEGY=file`
- **THEN** `cache_strategy == "file"`
- **WHEN** `TA_CACHE_STRATEGY=invalid_value`（非 integrated / adaptive / file）
- **THEN** `cache_strategy == "integrated"`（fallback 默认，MUST NOT raise）

#### Scenario: ttl_settings 默认含 6 个 key

- **WHEN** `from_environment(db_manager).ttl_settings`
- **THEN** MUST 含 6 个 key：`us_stock_data` (7200) / `us_news` (21600) / `us_fundamentals` (86400) / `china_stock_data` (3600) / `china_news` (14400) / `china_fundamentals` (43200)
- **AND** 数值字节级与 4.3 前的 `db_manager.get_config()["cache"]["ttl_settings"]` 一致

#### Scenario: AdaptiveCacheSystem 支持 config 注入

- **WHEN** `AdaptiveCacheSystem(cache_dir=tmp, config=CacheConfig(...))`
- **THEN** 实例 MUST 使用传入的 config，**MUST NOT** 调 `db_manager.get_config()`
- **AND** `instance.primary_backend == config.primary_backend`
- **WHEN** `AdaptiveCacheSystem(cache_dir=tmp)`（config 未传）
- **THEN** 实例 MUST 走 `CacheConfig.from_environment(self.db_manager)` 路径（向后兼容）
