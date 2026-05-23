## Why

`cache-layer-consolidation` epic（archived `2026-05-22-cache-backend-unification`）的 sub-stage 4.4，紧接 4.3（`CacheConfig` 已落，commit `3ce41fdd`）。

到 4.3 为止，3 个 backend 都已抽出 + config 已统一，但 cache 顶层仍是**两层包装**：

```
get_cache()
└── IntegratedCacheManager           [383 行，包装层]
    ├── self.legacy_cache = StockDataCache(...)
    └── self.adaptive_cache = AdaptiveCacheSystem(...)   [4.3 后 ~360 行]
                              ├── self.file_backend
                              ├── self.redis_backend
                              ├── self.mongo_backend
                              ├── self.config (CacheConfig)
                              └── primary_backend 路由 + fallback → file
```

**问题**：

1. **两层包装语义稀薄**：`IntegratedCacheManager` 实际上只做「if use_adaptive then adaptive else legacy」一个布尔分支——一旦决定走 adaptive，所有方法都透传给 `adaptive_cache.save_data(...) / load_data(...)`。包装层只额外提供「save_news_data / load_news_data 走 legacy」这一个差异化路径，但调研发现外部消费方为 0（grep `cache.save_news_data` / `cache.load_news_data` 在 `tradingagents/` + `app/` 命中为 0；命中均为 `NewsService.save_news_data`，不同对象）。
2. **公开 API 与内部 API 不一致**：消费方调 `save_stock_data(symbol, data, start_date, end_date, data_source) -> str`；`AdaptiveCacheSystem` 内部用 `save_data(symbol, data, ..., data_type)`；翻译层散落在 `IntegratedCacheManager.save_stock_data`。
3. **测试不易**：`IntegratedCacheManager` 必经 `StockDataCache(legacy_cache)` + `AdaptiveCacheSystem` 完整初始化，单元测试要双重 mock。

## What Changes

### 新增 `Cache` 类（公开 API 唯一实现）

`tradingagents/dataflows/cache/_cache.py` 新建：

```python
class Cache:
    def __init__(
        self,
        file_backend: FileBackend,
        config: CacheConfig,
        redis_backend: RedisBackend | None = None,
        mongo_backend: MongoBackend | None = None,
    ) -> None:
        ...
    # 公开 API（10 个，与 IntegratedCacheManager 的真实消费方法对齐）
    def save_stock_data(self, symbol, data, start_date='', end_date='', data_source='default') -> str: ...
    def load_stock_data(self, cache_key) -> Any | None: ...
    def find_cached_stock_data(self, symbol, start_date=None, end_date=None, data_source=None, max_age_hours=None) -> str | None: ...
    def save_fundamentals_data(self, symbol, data, data_source='unknown') -> str: ...
    def load_fundamentals_data(self, cache_key) -> Any | None: ...
    def find_cached_fundamentals_data(self, symbol, data_source=None, max_age_hours=None) -> str | None: ...
    def is_cache_valid(self, cache_key, symbol=None, data_type=None) -> bool: ...
    def get_cache_stats(self) -> dict: ...
    def clear_old_cache(self, max_age_days=7) -> None: ...
    def get_cache_backend_info(self) -> dict: ...
```

`Cache` 自身负责：
- envelope 构建（timestamp / backend tag / metadata）
- 路由：按 `config.primary_backend` 选 primary backend；失败时 if `config.fallback_enabled` 降到 file_backend
- TTL 推断：`config.ttl_settings.get(f"{market}_{data_type}")`
- cache_key 生成（md5 hash of symbol + dates + data_source + data_type，与 AdaptiveCacheSystem 现状一致）
- stock_data / fundamentals_data 区分（仅靠 metadata.data_type 字段；与现状一致）

`Cache` 不再依赖：
- `AdaptiveCacheSystem`（行为合并进来）
- `IntegratedCacheManager`（包装层取消）
- `StockDataCache`（legacy_cache 路径不再走，file 走 `file_backend`）

### 修改 `get_cache()`

```python
def get_cache() -> StockDataCache | Cache:
    cache_config = CacheConfig.from_environment(get_database_manager())
    if cache_config.cache_strategy == "file":
        return StockDataCache()  # file-only 路径仍走 legacy（与 4.3 前一致）
    # integrated / adaptive 走新 Cache 类
    db_manager = get_database_manager()
    file_backend = FileBackend(cache_dir=Path("data/cache"))
    redis_backend = RedisBackend(redis_client=db_manager.get_redis_client())
    mongo_backend = MongoBackend(mongodb_client=db_manager.get_mongodb_client())
    return Cache(file_backend, cache_config, redis_backend, mongo_backend)
```

### 标记 deprecated（保留可用）

- `IntegratedCacheManager.__init__` 加 `warnings.warn(DeprecationWarning, "use Cache from tradingagents.dataflows.cache instead", stacklevel=2)`
- `AdaptiveCacheSystem.__init__` 同上
- 类本身保留——4.6 才删（观察期）
- `cache/__init__.py` `__all__` 加 `Cache` re-export

### 新增测试

- `tests/test_cache_class.py`：
  - 构造（用 mock backends 注入 + 真 `CacheConfig`）
  - `save_stock_data` round-trip：primary=file → 写 file_backend → load 取回 envelope
  - 路由：primary=redis + redis_backend.save 成功 → 写 redis 不写 file
  - fallback：primary=redis + redis_backend.save 失败 + fallback_enabled=True → 写 file_backend
  - fallback 关闭：primary=redis + 失败 + fallback_enabled=False → save 整体失败 return ""
  - `load_stock_data` 路由：primary=redis → 先查 redis；miss 时 if fallback → 查 file
  - `find_cached_stock_data` 生成 cache_key 与 `save_stock_data` 一致（同 symbol/dates/source 应能找到）
  - `save_fundamentals_data` / `load_fundamentals_data` / `find_cached_fundamentals_data` 同样路径
  - `is_cache_valid` TTL 判定（mock backend 返 timestamp 现在 - 1 小时 vs 现在 - 24 小时 + TTL=2h）
  - `get_cache_stats` 返 dict 含 backend_info / cache_dir
  - `get_cache_backend_info` 返 primary_backend / fallback_enabled
  - `clear_old_cache` 删过期 .json.gz 文件不删 fresh 文件
- `tests/test_cache_deprecation.py`：
  - `IntegratedCacheManager()` 触发 DeprecationWarning（pytest.warns）
  - `AdaptiveCacheSystem()` 触发 DeprecationWarning
  - 警告后行为不变（仍可调 save/load）

### 公开 API 行为不变

- `get_cache()` 返回的对象上 10 个真实消费方法签名 100% 与 4.4 前 `IntegratedCacheManager` 同名方法对齐
- 40+ 调用方零改动（编译 + 测试守护）
- `TA_CACHE_STRATEGY=file` 路径仍走 `StockDataCache`，未改动

## Capabilities

### Modified Capabilities

- `dataflow-caching`（位于 `docs/specs/dataflow-caching/spec.md`）：ADDED Requirement「统一 Cache 类（公开 API 单一实现）」+ 「IntegratedCacheManager / AdaptiveCacheSystem 标记 deprecated」。新 Scenario：路由 / fallback / `get_cache()` 返新 Cache 实例 / deprecated warning 触发。

## Impact

**改动文件**（2 新 + 3 改）：

- 新：`cache/_cache.py`（新 `Cache` 类，预计 ~250 行）
- 新：`tests/test_cache_class.py` + `tests/test_cache_deprecation.py`
- 改：`cache/__init__.py`（`get_cache()` 改返 `Cache`，加 `Cache` re-export）
- 改：`cache/integrated.py`（`__init__` 加 DeprecationWarning + 类保留）
- 改：`cache/adaptive.py`（`__init__` 加 DeprecationWarning + 类保留）
- 改：`docs/specs/dataflow-caching/spec.md`（追加 Requirement + Scenarios）

**许可边界**：全部在 `tradingagents/dataflows/cache/`（Apache 2.0）+ `tests/`（Apache 2.0）+ `docs/specs/`。**不动** `app/` / `frontend/`。

**风险**：中

- 主要风险点：`get_cache()` 返回的对象类型从 `IntegratedCacheManager` 变 `Cache`——签名兼容但 `isinstance(x, IntegratedCacheManager)` 检查会失败。grep 显示 40+ 调用方**无一**做 `isinstance` 检查（全部走鸭子类型方法调用），安全
- `clear_old_cache` 文件遍历逻辑迁出 StockDataCache → `Cache._clear_old_files`，可能漏掉 StockDataCache 内的某些细节（如分类目录扫描）—— round-trip + 集成 smoke test 守护
- `get_cache_backend_info` / `get_cache_stats` 返回结构字段集需保留 `app/routers/cache.py` 消费的字段（`primary_backend` / `fallback_enabled` / `total_size` / `total_files` 等）

**收益**：

- cache 层从「2 包装 + 路由」收敛为「1 Cache 类 + N Backend」
- 公开 API 与实现统一，新增方法或 backend 不再编辑多层
- `Cache` 可独立单元测试（注入 mock backends，无需 db_manager）
- 为 4.5（调用方迁移）+ 4.6（删 deprecated 层）扫清前置

**回滚**：

单 sub-stage 4 commit，回滚 = `git revert`。`get_cache()` fallback 到旧 `IntegratedCacheManager` 路径即可。

## 不在 4.4 范围

- `save_news_data` / `load_news_data`：调研后确认外部消费为 0（grep 命中均为 `NewsService.save_news_data`，不同对象）；新 `Cache` 类不实现，避免承担死代码
- 调用方迁移：40+ 调用方继续调相同方法名（鸭子类型兼容），不主动改 `data_source_manager` / `app/` 等消费方——4.5 stage 才做
- `StockDataCache` 删除：`TA_CACHE_STRATEGY=file` 仍走 StockDataCache；4.6 才考虑统一 file 路径

## 与 4.3 的差异点

- 4.3 引入 config 抽象（不改类层级）；4.4 引入新公开 API 类型 + deprecated 老类
- 4.3 改动在 cache/ 根 + __init__（薄）；4.4 新建 _cache.py 250 行实现 + 改 3 个文件
- 4.3 不引入 DeprecationWarning；4.4 在 2 个老类构造时触发
- 4.3 17 个新 unit test；4.4 预计 20+ test 跨 _cache 类与 deprecation
