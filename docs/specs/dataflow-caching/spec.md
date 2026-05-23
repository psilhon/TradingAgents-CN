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
- `clear(max_age_days: int) -> None` — 清理过期数据（4.7 起加入）：`max_age_days=0` 表示清空全部；非 0 表示删除超过 `max_age_days` 天的条目。各后端语义：File 删 mtime 早于 cutoff 的 `*.json.gz`；Redis `max_age_days=0` 调 `flushdb()`，非 0 时 no-op（Redis 自有 native TTL）；Mongo `max_age_days=0` 调 `delete_many({})`，非 0 时 `delete_many({"timestamp": {"$lt": cutoff}})`
- `close() -> None` — 释放后端持有的连接资源（4.8 起加入，**可选方法**）。File 后端 no-op；Redis 后端调 `redis_client.close()`；Mongo 后端调 `mongo_client.close()`。MUST NOT raise——调用方（`Cache.close()`）以 duck-type 方式 `getattr(b, "close", None)` 检测后调用，因此符合旧 Protocol 不实现 `close` 的 mock backend 仍可用

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
- `save(key, envelope) -> bool` — 写入 `{cache_dir}/{key}.json.gz`，经 `encode_envelope` 编码；失败返回 `False`。**4.8 起 MUST 原子写入**：先写临时文件 `{cache_dir}/.{key}.json.gz.tmp.{pid}`，写完后调 `os.replace(tmp, final)` 原子换名；写入中途异常时 MUST 清理残留临时文件（finally 块 unlink）。临时文件名以 `.` 开头让 `glob("*.json.gz")` 自然跳过；带 `pid` 让多进程并行写不同 key 不互冲。POSIX 保证 same-filesystem `os.replace` 原子（项目仅支持 macOS/Linux）
- `load(key) -> dict | None` — 读取 `{cache_dir}/{key}.json.gz`，经 `decode_envelope` 解码；文件不存在或解码失败返回 `None`
- `close() -> None` — no-op（4.8 起加入，无连接资源需要释放）

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
- `close() -> None` — 4.8 起加入。`redis_client=None` 时 no-op；否则调 `redis_client.close()` 释放连接池。异常 catch 不 raise（破坏关闭流程不可接受——其它 backend 仍需关闭）

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
  - 所有 `datetime` 值（`timestamp` / `expires_at`）MUST 使用 `datetime.now(timezone.utc)`（4.7 起 timezone-aware UTC，与 BSON 存储语义一致；避免 naive local 与 pymongo 默认 naive UTC 反序列化的时区漂移）
  - `replace_one({"_id": key}, doc, upsert=True)`
- `load(key) -> dict | None` — `find_one({"_id": key})`：
  - doc 不存在 → 返 `None`
  - `expires_at` 已过期 → 删 doc + 返 `None`（4.7 起：read 时若 `expires_at` 为 naive 则视作 UTC 处理；比对用 `datetime.now(timezone.utc)`）
  - `data_type="dataframe"` → `pd.read_json(StringIO(data))` 重建 DataFrame
  - `data_type="json"` → `json.loads(data)` 重建
  - `data_type="pickle"`（legacy） → 删 doc + log + 返 `None`，**MUST NOT** 调任何 `pickle.load*` / `pickle.loads`
  - 未识别 `data_type`（其它值） → 4.7 起 MUST `delete_one` + warn + 返 `None`（消除 zombie 累积；4.6 前仅 warn 不删）
  - 重建为 envelope `{data, metadata, timestamp, backend="mongodb"}` 返回
- `close() -> None` — 4.8 起加入。`mongodb_client=None` 时 no-op；否则调 `mongo_client.close()` 释放连接池。异常 catch 不 raise

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
  - `primary_backend: Literal["redis", "mongodb", "file"]` — `Cache` 首选 backend，由 db_manager 检测可用性派生
  - `fallback_enabled: bool` — 主 backend 失败时是否降级到 file
  - `ttl_settings: Mapping[str, int]` — `{market}_{data_type_stem}` → TTL seconds，MUST 含 6 个标准 key（`us_stock_data` / `us_news` / `us_fundamentals` / `china_stock_data` / `china_news` / `china_fundamentals`）。注意 key 用 stem（无 `_data` 后缀）即使消费方传入 `"fundamentals_data"` / `"news_data"`（`Cache._get_ttl_seconds` 自动 strip suffix；见 Cache Requirement）
- `from_environment(db_manager) -> CacheConfig` classmethod：从 env + db_manager 检测结果构造 CacheConfig 的产线工厂
- `__post_init__` 4.7 起 MUST 运行时校验 Literal 字段（`cache_strategy` ∈ {integrated, adaptive, file}，`primary_backend` ∈ {redis, mongodb, file}），非法值 MUST raise `ValueError`（不再依赖类型检查工具——`CacheConfig(primary_backend="postgres")` 直接构造也要 raise）
- 显式 `eq=True, unsafe_hash=False` + 自定义 `__hash__` 基于 `(cache_strategy, primary_backend, fallback_enabled, tuple(sorted(ttl_settings.items())))`（4.7 起；`Mapping` 默认不 hashable，dataclass 自动派生的 `__hash__` 会 raise TypeError）

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

### Requirement: 统一 Cache 类（公开 API 单一实现）

`tradingagents/dataflows/cache/_cache.py` 的 `Cache` 类 MUST 是 cache 层公开 API 的单一实现。具体：

- `__init__(file_backend: FileBackend, config: CacheConfig, redis_backend: RedisBackend | None = None, mongo_backend: MongoBackend | None = None)` — 显式注入 backends 实例 + CacheConfig
- 公开方法 MUST 覆盖 10 个真实消费方法签名（与 4.4 前 `IntegratedCacheManager` 字节级对齐）。所有 `start_date` / `end_date` / `data_source` 参数 MUST 接受 `None`，内部 normalize 到默认值（`start_date or ""` / `end_date or ""` / `data_source or "default"`），与 4.4 前 IntegratedCacheManager 行为字节级一致：
  - `save_stock_data(symbol, data, start_date: str | None = None, end_date: str | None = None, data_source: str | None = None) -> str`
  - `load_stock_data(cache_key) -> Any | None`
  - `find_cached_stock_data(symbol, start_date: str | None = None, end_date: str | None = None, data_source: str | None = None, max_age_hours: int | None = None) -> str | None`
  - `save_fundamentals_data(symbol, data, data_source: str | None = None) -> str`
  - `load_fundamentals_data(cache_key) -> Any | None`
  - `find_cached_fundamentals_data(symbol, data_source: str | None = None, max_age_hours: int | None = None) -> str | None`
  - `is_cache_valid(cache_key, symbol=None, data_type=None) -> bool`
  - `get_cache_stats() -> dict`
  - `clear_old_cache(max_age_days=7) -> None`
  - `get_cache_backend_info() -> dict`
  - `close() -> None` — 4.8 起加入。委派 file/redis/mongo backend 的 `close()`（duck-typed via `getattr(b, "close", None)`），各 backend 异常 catch 单条 logger.exception，不 raise——一个 backend 关闭失败 MUST NOT 拖垮其它 backend 关闭。Cache 实例 close 后再用 backend 操作返 False/None（既有错误约定）；不重置 state
  - `__enter__() -> Cache` / `__exit__(...) -> None` — 4.8 起加入，让 `with Cache(...) as c:` 出 with 块自动调 `close()`

`Cache` 负责（cache 层职责）：

- envelope 构建（`{data, metadata, timestamp, backend}` dict）
- 路由：按 `config.primary_backend` 选 primary backend 调 save/load
- fallback：primary 失败时 if `config.fallback_enabled` 降到 `file_backend`
- TTL 推断：`config.ttl_settings.get(f"{market}_{data_type_stem}", 7200)`。**4.7 修订**：`data_type_stem` 为 caller 传入 `data_type` 去掉可能的 `_data` 后缀（与历史 IntegratedCacheManager 一致：`"fundamentals_data" → "us_fundamentals"`；`"news_data" → "us_news"`；`"stock_data"` 不变）
- cache_key 生成：md5 hash(symbol + dates + data_source + data_type)。**4.7 修订**：fundamentals / news 路径 MUST 使用 `"fundamentals_data"` / `"news_data"` 作 data_type（与历史 IntegratedCacheManager → AdaptiveCacheSystem.save_data 字节级一致）
- **load 路径 TTL 强制**（4.7 起）：`load_stock_data` / `load_fundamentals_data` MUST 在返回 envelope.data 前用 `_get_ttl_seconds(metadata.symbol, metadata.data_type)` 派生 TTL，检查 envelope.timestamp 是否 fresh；过期 → 返 None
- **find_cached_\* TTL 强制**（4.7 起）：`find_cached_stock_data` / `find_cached_fundamentals_data` 在 `max_age_hours=None` 时使用上述 default TTL；非 None 时使用 `max_age_hours * 3600`
- **is_cache_valid 读 envelope metadata**（4.7 起）：MUST 优先从 envelope.metadata.symbol / metadata.data_type 派生 TTL bucket，caller 传的 symbol/data_type 仅作 fallback
- **Cache.__init__ 一致性校验**（4.7 起）：`config.primary_backend == "redis"` 且 `redis_backend is None` MUST raise `ValueError`；mongo 同
- **metadata_dir 兼容属性**（4.7 起）：Cache MUST 暴露 `metadata_dir` property 指向 `file_backend.cache_dir / ".compat_empty_metadata"`（不实际创建），让历史 callsite `cache.metadata_dir.glob("*_meta.json")`（StockDataCache 时代留下的兜底路径）不再 raise AttributeError，行为退化为 silent return None（恢复 stale-cache fallback 留待未来 sub-stage）
- `get_cache_stats` 返回 dict（4.7 修订）MUST 含字段：`primary_backend` / `fallback_enabled` / `total_files` / `total_size` (bytes，**字段名字节级匹配** `app/routers/cache.py:38` 消费) / `total_size_bytes` (alias) / `total_size_mb` / `cache_dir` / `backend_info` / `stock_data_count` / `news_count` / `fundamentals_count`（per-type count 由 file_backend 解 envelope.metadata.data_type 累加；redis/mongo primary 时返 0）

`Cache` MUST NOT：

- 依赖 `IntegratedCacheManager` / `AdaptiveCacheSystem` / `StockDataCache`（行为合并而非包装）
- 直接调 `db_manager.get_config()` / 读 env（config 由构造方传入）

#### Scenario: get_cache() 返新 Cache 实例

- **WHEN** `cache_strategy ∈ {"integrated", "adaptive"}`
- **THEN** `get_cache()` MUST 返 `Cache` 实例（**不再**返 `IntegratedCacheManager`）
- **WHEN** `cache_strategy == "file"`
- **THEN** `get_cache()` MUST 返 `StockDataCache` 实例（与 4.4 前一致）

#### Scenario: Cache 路由 — primary 直走

- **WHEN** `Cache(file_backend=fb, redis_backend=rb, config=CacheConfig(primary_backend="redis", ...))` save_stock_data 调用，rb.save 返 True
- **THEN** MUST 调 `rb.save(...)`
- **AND** MUST NOT 调 `fb.save(...)`

#### Scenario: Cache fallback — primary 失败降到 file

- **WHEN** `Cache(file_backend=fb, redis_backend=rb, config=CacheConfig(primary_backend="redis", fallback_enabled=True, ...))` save_stock_data 调用，rb.save 返 False
- **THEN** MUST 调 `fb.save(...)` 作为降级路径
- **AND** save_stock_data 返非空 cache_key

#### Scenario: Cache fallback 关闭

- **WHEN** primary=redis + rb.save 返 False + `fallback_enabled=False`
- **THEN** save_stock_data 返 `""`（empty string，与 4.4 前 AdaptiveCacheSystem.save_data 失败语义一致）
- **AND** MUST NOT 调 fb.save

#### Scenario: Cache is_cache_valid TTL 判定

- **WHEN** backend.load 返 envelope with `timestamp = now - 1h`，TTL 配置 = 2h
- **THEN** `is_cache_valid(key)` MUST 返 True
- **WHEN** envelope `timestamp = now - 25h`，TTL = 24h
- **THEN** MUST 返 False

#### Scenario: Cache 公开 API None-safe 字节级兼容

- **WHEN** 调用 `Cache.save_stock_data("AAPL", data, None, None, None)`（显式传 None）
- **THEN** 返回的 cache_key MUST 与 `Cache.save_stock_data("AAPL", data, "", "", "default")` 字节级相同
- **AND** MUST NOT raise（callsite 真实形式：data_source_manager._save_to_cache 以 `start_date: str | None = None` 传入）
- **WHEN** 调用 `Cache.save_fundamentals_data("AAPL", data)` 不传 data_source
- **THEN** 返回的 cache_key MUST 与 `Cache.save_fundamentals_data("AAPL", data, "default")` 字节级相同（**不是** "unknown" 或其它）
- **WHEN** 调用 `Cache.find_cached_stock_data("AAPL")` 仅传 symbol（其它 optional 全 None）
- **THEN** MUST NOT raise + 走与 `(symbol, "", "", "default", None)` 等价路径

> **历史注记**：4.4 加入「Requirement: IntegratedCacheManager / AdaptiveCacheSystem 标记 deprecated」+ 2 个相关 Scenario；4.6 随删除两个 deprecated 类一并删除该 Requirement。两个类在 4.6 后从 cache 层彻底拆除。`StockDataCache` 在 4.4 未 deprecate，4.6 保留（`TA_CACHE_STRATEGY=file` 路径 + 2 个外部 import 依赖）。

### Requirement: get_cache 工厂线程安全 + 失败实例不缓存

`tradingagents/dataflows/cache/__init__.py` 的 `get_cache()` 工厂（4.7 起）MUST：

- 单例访问受 `threading.Lock` 保护（FastAPI 异步 handler + Uvicorn worker 多线程下避免冷启动 race 双重 instantiate backends）
- 首次构造若走 fallback 路径（`Cache` init 失败 → `StockDataCache`）MUST NOT 缓存该 fallback 实例，下次 `get_cache()` 重试主路径
- 主路径成功构造的 `Cache` 实例 MUST 缓存（避免重复创建 db client）
- 暴露 `reset_cache()` 模块级函数，清除单例（测试 + 运维 reload 用）

#### Scenario: get_cache 线程安全

- **WHEN** N 个线程同时调首次 `get_cache()`
- **THEN** 全部线程 MUST 返回同一 `Cache` 实例（`id()` 相等）
- **AND** `FileBackend.__init__` / `RedisBackend.__init__` / `MongoBackend.__init__` 各 MUST 仅被调用一次

#### Scenario: fallback 实例不持久化

- **WHEN** `Cache` 初始化抛异常（e.g. `db_manager` 不可用），`get_cache()` 返 `StockDataCache` fallback 实例
- **AND** 后续条件改善（`db_manager` 恢复）
- **AND** 再次 `get_cache()`
- **THEN** MUST 重新尝试 `Cache` 主路径（不返回先前 fallback 缓存）

#### Scenario: reset_cache 清除单例

- **WHEN** `get_cache()` 已返回缓存实例
- **AND** 调 `reset_cache()`
- **AND** 再次 `get_cache()`
- **THEN** MUST 构造新实例（不返回先前缓存）

### Requirement: Cache 公开 API 4.7 修订汇总

下列 Scenarios 守护 4.7 引入 / 修订的 Cache 行为。

#### Scenario: Cache.load_stock_data 强制 TTL

- **WHEN** 调 `cache.save_stock_data("AAPL", data, ...)` 得 cache_key
- **AND** 模拟时间快进超过 `us_stock_data=7200s` TTL
- **AND** 调 `cache.load_stock_data(cache_key)`
- **THEN** MUST 返 `None`（4.7 前会返 stale data）

#### Scenario: Cache.find_cached_*(max_age_hours=None) 走 default TTL

- **WHEN** save 一个 12 小时前的 stock_data envelope（us 股，TTL=2h）
- **AND** 调 `find_cached_stock_data("AAPL", ..., data_source="...", max_age_hours=None)`
- **THEN** MUST 返 `None`（envelope 已超 default TTL；4.7 前 max_age_hours=None 跳过 TTL 检查）

#### Scenario: Cache.is_cache_valid 优先读 envelope.metadata

- **WHEN** save 一个 A 股 fundamentals envelope（`metadata.symbol="000001"` / `metadata.data_type="fundamentals_data"`），90 分钟前
- **AND** 调 `cache.is_cache_valid(cache_key)` 不传 symbol / data_type
- **THEN** MUST 从 envelope.metadata 读出 symbol/data_type → 计算 `china_fundamentals=43200s` TTL → 返 True
- **AND** **不应** 回退到 default `us_stock_data` bucket（4.7 前 bug 路径）

#### Scenario: Cache.save_fundamentals_data 字节级回退到 fundamentals_data data_type

- **WHEN** `cache.save_fundamentals_data("AAPL", report, "finnhub")`
- **THEN** cache_key MUST == `md5("AAPL___finnhub_fundamentals_data")` (与 4.6 前 IntegratedCacheManager → adaptive_cache.save_data(data_type="fundamentals_data") 字节级一致)
- **AND** `_get_ttl_seconds("AAPL", "fundamentals_data")` MUST 派生 `us_fundamentals=86400s`（strip `_data` suffix 查找）

#### Scenario: Backend.clear 跨后端清理

- **WHEN** `cache.clear_old_cache(0)` 调用，primary=redis with fallback file
- **THEN** MUST 调 `file_backend.clear(0)` + `redis_backend.clear(0)` + `mongo_backend.clear(0)`（若 mongo_backend 非 None）
- **AND** `redis_backend.clear(0)` MUST 调 underlying `redis_client.flushdb()`
- **AND** `mongo_backend.clear(0)` MUST 调 underlying `collection.delete_many({})`
- **AND** `file_backend.clear(0)` MUST 删除全部 `*.json.gz`

#### Scenario: Cache.get_cache_stats 字段完整

- **WHEN** save 3 个 stock_data + 1 个 news_data + 2 个 fundamentals_data envelope
- **AND** 调 `cache.get_cache_stats()`
- **THEN** 返 dict MUST 含 `total_size` (字节，与 4.6 前 IntegratedCacheManager 字段名一致 — `app/routers/cache.py:39` 消费) / `stock_data_count=3` / `news_count=1` / `fundamentals_count=2`
- **AND** MUST 同时含 4.6 字段 `total_size_bytes` / `total_size_mb` / `total_files=6` / `primary_backend` / `fallback_enabled` / `cache_dir` / `backend_info`

#### Scenario: Cache.__init__ 一致性校验

- **WHEN** 构造 `Cache(file_backend=fb, config=CacheConfig(primary_backend="redis", ...), redis_backend=None)`
- **THEN** MUST raise `ValueError`（明示 redis_backend 不可缺）
- **WHEN** 构造 `Cache(file_backend=fb, config=CacheConfig(primary_backend="mongodb", ...), mongo_backend=None)`
- **THEN** 同样 raise

#### Scenario: Cache.metadata_dir 兼容属性

- **WHEN** 访问 `cache.metadata_dir`
- **THEN** MUST 返回 `Path` 对象（指向 `file_backend.cache_dir / ".compat_empty_metadata"`，不实际创建该目录）
- **AND** `cache.metadata_dir.glob("*_meta.json")` MUST 返回空迭代器（不 raise）
- **AND** 历史 callsite `_try_get_old_cache` 经此 path silent 退化为 return None（不再 AttributeError）

#### Scenario: CacheConfig __post_init__ Literal 校验

- **WHEN** 构造 `CacheConfig(cache_strategy="bogus", primary_backend="redis", fallback_enabled=True, ttl_settings={})`
- **THEN** MUST raise `ValueError`
- **WHEN** `CacheConfig(cache_strategy="integrated", primary_backend="postgres", ...)` 
- **THEN** 同样 raise
- **AND** 错误 message MUST 命名非法字段 + 列出允许值

#### Scenario: CacheConfig 可 hash

- **WHEN** 构造 `CacheConfig(...)` 实例
- **AND** 调 `hash(config)`
- **THEN** MUST 返 int（不 raise TypeError）
- **AND** 两个字段相等的 CacheConfig 实例 MUST hash 相等

### Requirement: FileBackend 原子写入

`FileBackend.save` 4.8 起 MUST 原子写入——磁盘满 / 进程 SIGKILL / OOM 等中断 MUST NOT 在 `cache_dir` 留下 truncated 的 `*.json.gz` 终态文件。具体：

- 写入 MUST 落到 `{cache_dir}/.{key}.json.gz.tmp.{pid}` 临时文件（前导 `.` 让 `glob("*.json.gz")` 自然跳过；带 `pid` 后缀让多进程并行写不同 key 不互冲）
- 临时文件写完 + close 后调 `os.replace(tmp, final)` 完成原子换名（POSIX same-filesystem rename 原子性）
- 写入中途异常 MUST 经 try/finally 路径清理临时文件 → unlink（best-effort，吞 FileNotFoundError）
- 最终路径 `{cache_dir}/{key}.json.gz` 在任何时刻 MUST 要么不存在要么为完整 gzip(JSON) envelope；不允许 partial-write 终态

#### Scenario: FileBackend 写入异常不留临时残留

- **WHEN** mock `encode_envelope` 抛异常，调 `FileBackend.save(key, envelope)`
- **THEN** MUST 返 `False`
- **AND** `cache_dir` 内 MUST NOT 留任何 `.{key}.json.gz.tmp.*` 临时文件（finally 已清理）
- **AND** `{cache_dir}/{key}.json.gz` MUST NOT 存在（从未 replace 上去）

#### Scenario: FileBackend 写入成功后无临时残留

- **WHEN** 正常 `FileBackend.save(key, envelope)` 返 `True`
- **THEN** `cache_dir` 内 MUST 只有 `{key}.json.gz`（替换完成后 tmp 名已不存在）
- **AND** glob `.*.tmp.*` MUST 返空

### Requirement: 缓存目录可由 env 覆盖

4.8 起 `get_cache()` MUST 通过 env `TA_CACHE_DIR` 决定 `FileBackend` 的 `cache_dir` 参数；env 未设 fallback 到 `"data/cache"` 相对路径（保持 4.7 行为）。env 值 MUST 经 `Path(...).expanduser()` 处理，允许 `~/.cache/tradingagents` 这类用户家目录路径。

#### Scenario: TA_CACHE_DIR 控制 FileBackend.cache_dir

- **WHEN** monkeypatch env `TA_CACHE_DIR=/tmp/test_cache`
- **AND** 调 `get_cache()`
- **THEN** 返回的 `Cache.file_backend.cache_dir == Path("/tmp/test_cache")`

#### Scenario: TA_CACHE_DIR expanduser

- **WHEN** monkeypatch env `TA_CACHE_DIR=~/.cache/ta`
- **AND** 调 `get_cache()`
- **THEN** `Cache.file_backend.cache_dir` MUST 已 expand `~`（不含字面 `~` 字符）

#### Scenario: TA_CACHE_DIR 未设默认 data/cache

- **WHEN** delete env `TA_CACHE_DIR`
- **AND** 调 `get_cache()`
- **THEN** `Cache.file_backend.cache_dir == Path("data/cache")`

### Requirement: Cache.close + Backend.close 生命周期

4.8 起 `Cache` MUST 暴露 `close() -> None` 方法 + context manager 协议（`__enter__` / `__exit__`），让 FastAPI shutdown hook / pytest teardown 主动释放 redis / mongo 客户端连接池。具体：

- `Cache.close()` MUST 遍历 `file_backend` / `redis_backend` / `mongo_backend`，对每个非 None backend duck-type 检测 `getattr(b, "close", None)` 后调用（兼容旧 mock backend 不实现 close 的情况）
- 单个 backend close 抛异常 MUST 经 `logger.exception` 记录但**不 raise**，确保剩余 backend 仍被关闭
- `Cache.__exit__(...)` MUST 调 `self.close()` 并返 None（不抑制异常）
- 各 backend close 语义见 Backend Protocol（File no-op；Redis / Mongo 调 client.close()）

#### Scenario: Cache.close 委派三个 backend

- **WHEN** 构造 Cache(file_backend=fb, redis_backend=rb, mongo_backend=mb, config=...)
- **AND** 调 `cache.close()`
- **THEN** MUST 调 `fb.close()` + `rb.close()` + `mb.close()` 各一次（顺序不限）

#### Scenario: Cache.close 单 backend 失败不影响其它

- **WHEN** mock `rb.close` raise RuntimeError
- **AND** 调 `cache.close()`
- **THEN** MUST NOT raise（异常吞）
- **AND** MUST 仍调 `fb.close()` + `mb.close()`（关闭流程不被一个 backend 故障打断）
- **AND** logger MUST 记录 exception（含 traceback）

#### Scenario: Cache 支持 with 语法

- **WHEN** `with Cache(file_backend=fb, ...) as c: pass`
- **THEN** 出 with 块时 MUST 调 `c.close()`
- **AND** `fb.close()` MUST 被调

#### Scenario: RedisBackend.close 调 client.close

- **WHEN** mock_client = MagicMock(), `RedisBackend(mock_client).close()`
- **THEN** mock_client.close MUST 被调一次
- **WHEN** `RedisBackend(None).close()`（client=None）
- **THEN** MUST NOT raise

#### Scenario: MongoBackend.close 调 client.close

- **WHEN** mock_client = MagicMock(), `MongoBackend(mock_client).close()`
- **THEN** mock_client.close MUST 被调一次
- **WHEN** `MongoBackend(None).close()`（client=None）
- **THEN** MUST NOT raise

### Requirement: Cache typed dispatch helper（内部 dedup）

4.8 起 `Cache._save_typed` / `Cache._load_typed` / `Cache._find_typed` 私有 helper MUST 承载 stock_data / fundamentals_data 路径的共同逻辑（envelope 构建 + cache_key 派生 + TTL 推断 + 路由调用）。公开 API（`save_stock_data` / `save_fundamentals_data` / `load_*` / `find_cached_*`）MUST 改为对 helper 的 thin 调用，但**公开 API 签名 + cache_key 派生 + envelope 形状 + TTL bucket 派生 MUST 字节级保持** 4.7 行为（守护 4.7 修订汇总下的所有 Scenario 仍绿）。

#### Scenario: 公开 save 方法路由经 _save_typed

- **WHEN** spy `Cache._save_typed`
- **AND** 调 `cache.save_stock_data("AAPL", df, "2024-01-01", "2024-12-31", "yfinance")`
- **AND** 调 `cache.save_fundamentals_data("AAPL", report, "finnhub")`
- **THEN** `_save_typed` MUST 各被调一次（共 2 次）
- **AND** 第一次 call_args MUST 含 `data_type="stock_data"` + id_fields 含 start_date/end_date/data_source
- **AND** 第二次 call_args MUST 含 `data_type="fundamentals_data"` + id_fields 含 data_source（无 start_date/end_date）
