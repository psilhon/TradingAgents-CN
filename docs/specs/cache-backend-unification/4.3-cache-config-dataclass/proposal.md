## Why

`cache-layer-consolidation` epic（archived `2026-05-22-cache-backend-unification`）的 sub-stage 4.3，紧接 4.2（`RedisBackend` + `MongoBackend` 已落，commit `89ae6dfa`）。

`AdaptiveCacheSystem` 当前的 backend 配置散落在多处来源：

```
db_manager.get_config()["cache"]               # database_manager.py L297
├── primary_backend       (redis/mongodb/file，由可用性自动推断)
├── fallback_enabled      (硬编码 True)
└── ttl_settings          (6 个 market×data_type 硬编码 TTL)

os.getenv("TA_CACHE_STRATEGY")                 # cache/__init__.py L76
                                                # = "integrated" / "file" / "adaptive"
                                                # 决定 get_cache() 返 IntegratedCacheManager
                                                # 还是 StockDataCache
```

**问题**：

1. **schema 散落**：cache 配置一半在 dict（`db_manager.get_config()["cache"]`），一半在 env（`TA_CACHE_STRATEGY`）。新加配置项要决定塞哪边。
2. **类型不安全**：dict 路径无类型校验。`cache_config["ttl_settings"].get(ttl_key, 7200)`——若 ttl_settings dict 结构改了消费方不会被强类型抓出。
3. **测试困难**：`AdaptiveCacheSystem.__init__` 必经 `db_manager.get_config()`——单元测试要 mock 整个 db_manager。无法直接传一份 backend config 跑。
4. **4.4 前置阻塞**：4.4 引入新 `Cache` 类时希望直接 `Cache(backend, fallback, config)`，需要 config 是结构化对象而非散落 dict + env。

## What Changes

### 新增 `CacheConfig` dataclass

`tradingagents/dataflows/cache/_config.py` 新建：

```python
@dataclass(frozen=True)
class CacheConfig:
    cache_strategy: Literal["integrated", "adaptive", "file"]  # 顶层 instantiation 决策
    primary_backend: Literal["redis", "mongodb", "file"]       # AdaptiveCacheSystem 内部首选
    fallback_enabled: bool                                      # 主后端失败时是否降级到 file
    ttl_settings: Mapping[str, int]                             # market_data_type → TTL seconds

    @classmethod
    def from_environment(cls, db_manager) -> "CacheConfig":
        """从 env + db_manager 检测结果派生 CacheConfig (产线入口)."""
        ...
```

`frozen=True` 让 CacheConfig 不可变——一旦构造完不再变更（与现状一致：当前 `primary_backend` 在 `AdaptiveCacheSystem.__init__` 后只读不变）。

### 修改

- `tradingagents/dataflows/cache/__init__.py`：
  - `get_cache()` 改用 `CacheConfig.from_environment(get_database_manager())` 拿配置，读 `config.cache_strategy` 决定走 `IntegratedCacheManager` 还是 `StockDataCache`
  - 删除模块级 `DEFAULT_CACHE_STRATEGY = os.getenv(...)`——CacheConfig 是单一来源

- `tradingagents/dataflows/cache/adaptive.py`：
  - `AdaptiveCacheSystem.__init__(cache_dir: str | None = None, config: CacheConfig | None = None)` 加可选 config 参数
  - `config is None` 时 fallback 到 `CacheConfig.from_environment(self.db_manager)`（向后兼容现有调用方）
  - 内部消费 `self.config.primary_backend` / `self.config.fallback_enabled` / `self.config.ttl_settings`，去掉 `self.cache_config` dict 中转
  - `_get_ttl_seconds` 改读 `self.config.ttl_settings`

- `tradingagents/dataflows/cache/integrated.py`：
  - `IntegratedCacheManager` 透传 `config` 参数到 `AdaptiveCacheSystem`（与 cache_dir 同样路径）
  - `_log_cache_status` 仍读 `self.adaptive_cache.config.primary_backend` 等（属性路径变化）

### 新增测试

- `tests/test_cache_config.py`：
  - `CacheConfig` 构造 + 字段类型 + `frozen=True`（赋值 raise FrozenInstanceError）
  - `from_environment` 三路径分支：redis available → `primary_backend="redis"` / 仅 mongodb → `mongodb` / 都没 → `file`
  - `from_environment` 读 `TA_CACHE_STRATEGY` env：默认 `"integrated"` / `TA_CACHE_STRATEGY=file` → `cache_strategy="file"` / 非法值降级到默认
  - `ttl_settings` 含 6 个标准 key + 默认值

### 不在 4.3 范围

- **`TA_USE_APP_CACHE`**：经调研，消费方为 `mongodb_cache_adapter.MongoDBCacheAdapter` + `dataflows.data_source_manager`——**这是 dataflow 数据源优先级开关，不是 cache backend 配置**。它决定上游数据先查 app MongoDB 集合还是直查 API；与 `AdaptiveCacheSystem` / `IntegratedCacheManager` 的 cache backend 选择正交。强行折进 `CacheConfig` 会破坏单一职责。epic proposal 当初的「2 个 cache switch 一并折叠」设想经此次调研否定。
- **`cache_dir` 路径**：仍由 `AdaptiveCacheSystem.__init__(cache_dir=...)` 单独参数控制——它是文件系统位置而非配置选项，与 backend 选择无关。
- **`MongoBackend` 的 `db_name` / `collection_name`**：MongoBackend 自己的构造参数（硬编码 `"tradingagents"` / `"cache"` 默认），不属 backend-selection 配置。

## Capabilities

### Modified Capabilities

- `dataflow-caching`（位于 `docs/specs/dataflow-caching/spec.md`）：ADDED Requirement「CacheConfig 单一来源」。新 Scenario：构造 + 不可变 + `from_environment` 三路径分支 + `TA_CACHE_STRATEGY` 解析。

## Impact

**改动文件**（2 新 + 3 改）：

- 新：`backends/../_config.py`（位于 `cache/_config.py`，与 `_serialize.py` 同层；非 backend 实现，是 cache 层 config 抽象）
- 新：`tests/test_cache_config.py`
- 改：`cache/__init__.py`（`get_cache()` 改用 CacheConfig）
- 改：`adaptive.py`（`AdaptiveCacheSystem` 接受可选 config 参数）
- 改：`integrated.py`（透传 config 到 AdaptiveCacheSystem）
- 改：`docs/specs/dataflow-caching/spec.md`（追加 Requirement + Scenarios）

**许可边界**：全部在 `tradingagents/dataflows/cache/`（Apache 2.0）+ `tests/`（Apache 2.0）+ `docs/specs/`。**不动** `app/` / `frontend/`。

**风险**：中

- 主要风险点：`get_cache()` 入口决策路径改了——`TA_CACHE_STRATEGY` env 解析从模块级 `os.getenv` 移到 `CacheConfig.from_environment`，需要确保 env 读取时机与现状一致（init time 一次性 vs 每次调用）
- `AdaptiveCacheSystem.__init__` 加可选参数，现有调用方零改动（保持 `cache_dir` 为唯一必传）
- `IntegratedCacheManager` 内部读 adaptive_cache 属性路径变化（`adaptive_cache.primary_backend` → `adaptive_cache.config.primary_backend`），消费 callsite 少（仅 `_log_cache_status` + `get_cache_stats`）

**收益**：

- cache 配置单点 schema，类型安全
- `AdaptiveCacheSystem` 可独立测试（构造时传 `CacheConfig(...)` mock，不必 mock 整个 db_manager）
- 为 4.4 `Cache` 类抽象提供 `Cache(backend, fallback, config=CacheConfig)` 自然接口
- TTL 默认值集中在 `CacheConfig`，便于后续策略调整

**回滚**：

单 sub-stage 4 commit（spec → red → green → changelog），回滚 = `git revert` 4 个 commit。`AdaptiveCacheSystem` / `IntegratedCacheManager` fallback 到原 dict 读取路径即可。

## 与 4.2 的差异点

- 4.2 在 backend 层（IO 拆分）；4.3 在 cache 层（config 抽象）
- 4.2 改动文件全在 `backends/`；4.3 改动在 `cache/` 根 + `__init__.py` + `adaptive.py` + `integrated.py`
- 4.2 增 `import pandas` 例外；4.3 不动 backend，不引入新例外
- 4.2 引入 mock client 测 backend；4.3 引入纯 dataclass 测 config（无 mock）
