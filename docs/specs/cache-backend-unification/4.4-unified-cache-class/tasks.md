# Tasks — cache-unified-class (sub-stage 4.4)

> epic：`cache-layer-consolidation` stage 4（archived `2026-05-22-cache-backend-unification`）
> 前置：4.3 已完成（commit `3ce41fdd`）—— CacheConfig 单一来源已落
> 体量：~2-3 天 / 风险：中
> 公开 API 行为零变更；TDD red-green。

## 1. spec delta — commit 1（先于代码）

- [ ] 1.1 在 `docs/specs/dataflow-caching/spec.md` 追加 Requirement「统一 Cache 类（公开 API 单一实现）」：定义 `Cache` 类构造签名 + 10 个公开方法 + 路由 / fallback 规则 + envelope 构建职责
- [ ] 1.2 追加 Requirement「IntegratedCacheManager / AdaptiveCacheSystem 标记 deprecated」：构造时 MUST raise `DeprecationWarning`（`stacklevel=2`，message 指向 `Cache`）；类保留可用、行为不变；4.6 才删
- [ ] 1.3 加 Scenario：`get_cache()` 当 `cache_strategy in {"integrated", "adaptive"}` 返 `Cache` 实例；`cache_strategy="file"` 返 `StockDataCache`
- [ ] 1.4 加 Scenario：`Cache(file_backend, config(primary="file"))` save_stock_data → 写 file_backend → load_stock_data 取回等价
- [ ] 1.5 加 Scenario：路由 — `Cache(...)` with primary=redis + redis_backend.save 成功 → MUST 调 redis_backend.save，MUST NOT 调 file_backend.save
- [ ] 1.6 加 Scenario：fallback — primary=redis + redis_backend.save 返 False + `fallback_enabled=True` → MUST 调 file_backend.save
- [ ] 1.7 加 Scenario：fallback 关闭 — primary=redis + 失败 + `fallback_enabled=False` → save_stock_data 返 ""（empty string，与 4.4 前 AdaptiveCacheSystem 行为一致）
- [ ] 1.8 加 Scenario：DeprecationWarning — `IntegratedCacheManager()` MUST raise DeprecationWarning；`AdaptiveCacheSystem()` 同；警告后行为 MUST 不变
- [ ] 1.9 加 Scenario：`is_cache_valid` TTL 判定 — primary backend load 返 envelope timestamp + TTL 内 → True；超 TTL → False
- [ ] 1.10 commit `docs(spec): cache-backend-unification 4.4 — Cache 类 + deprecated 标记契约`

## 2. red — commit 2（先测试）

### 2.1 tests/test_cache_class.py（构造 + 公开 API + 路由）

- [ ] 2.1.1 仿 test_file_backend.py spec_from_file_location 模式加载 `_cache.py`
- [ ] 2.1.2 测试：构造 — `Cache(file_backend, config)` 必传；`redis_backend` / `mongo_backend` 可选 None
- [ ] 2.1.3 测试：save_stock_data → load_stock_data round-trip（primary=file，mock file_backend）
- [ ] 2.1.4 测试：cache_key 决定性 — 同 symbol/dates/data_source 两次 save 同 cache_key
- [ ] 2.1.5 测试：路由 primary=redis — Cache(file=fb, redis=rb, config(primary='redis')) → save 调 rb.save，未调 fb.save
- [ ] 2.1.6 测试：路由 primary=mongodb — save 调 mongo_backend.save
- [ ] 2.1.7 测试：fallback enabled — primary=redis + rb.save 返 False → 调 fb.save
- [ ] 2.1.8 测试：fallback disabled — primary=redis + rb.save False + fallback_enabled=False → save_stock_data 返 ""，fb.save 未调
- [ ] 2.1.9 测试：load_stock_data primary 路径 — primary=redis + rb.load 返 envelope → 返 envelope.data，未调 fb.load
- [ ] 2.1.10 测试：load_stock_data fallback — primary=redis + rb.load 返 None + fallback_enabled=True → 调 fb.load
- [ ] 2.1.11 测试：find_cached_stock_data 与 save_stock_data 配合 — save 后 find 同 args 找到 cache_key
- [ ] 2.1.12 测试：save_fundamentals_data / load_fundamentals_data round-trip
- [ ] 2.1.13 测试：find_cached_fundamentals_data 同
- [ ] 2.1.14 测试：is_cache_valid — mock backend 返 timestamp = now - 1h，TTL=2h → True；timestamp = now - 25h，TTL=24h → False
- [ ] 2.1.15 测试：get_cache_stats 返 dict 含 `cache_dir` / `primary_backend` / `fallback_enabled` / `total_files` 等（保留 app/routers/cache.py 消费的字段）
- [ ] 2.1.16 测试：get_cache_backend_info 返 dict 含 `primary_backend` / `fallback_enabled` / `mongodb_available` / `redis_available`
- [ ] 2.1.17 测试：clear_old_cache(max_age_days=0) 删所有过期文件

### 2.2 tests/test_cache_deprecation.py（deprecated 警告）

- [ ] 2.2.1 测试：`IntegratedCacheManager()` MUST raise DeprecationWarning（pytest.warns(DeprecationWarning)）
- [ ] 2.2.2 测试：`AdaptiveCacheSystem()` 同
- [ ] 2.2.3 测试：DeprecationWarning message 含 "Cache" 关键字指向迁移目标
- [ ] 2.2.4 测试：警告后 IntegratedCacheManager / AdaptiveCacheSystem 仍可正常 instantiate + 调 save_stock_data（行为不变）

### 2.3 跑测试 + commit

- [ ] 2.3.1 跑 `just test`：新测试 MUST 全部 FAIL（红——`Cache` 尚未实现 + DeprecationWarning 未加）
- [ ] 2.3.2 commit `test(cache): 新 Cache 类 + deprecated 老类警告（red）`

## 3. green — commit 3（实现）

### 3.1 _cache.py 实现

- [ ] 3.1.1 新建 `tradingagents/dataflows/cache/_cache.py`
- [ ] 3.1.2 `Cache` 类构造 + 4 个属性（backends + config）
- [ ] 3.1.3 `_get_cache_key` 内部方法（md5 hash 与 AdaptiveCacheSystem 现状一致）
- [ ] 3.1.4 `_get_ttl_seconds` 内部方法（从 config.ttl_settings 派生，与 AdaptiveCacheSystem 现状一致）
- [ ] 3.1.5 `_save_via_backend(backend_name, key, envelope, ttl)` 内部分派（dict 映射 backend）
- [ ] 3.1.6 `_load_via_backend(backend_name, key)` 内部分派
- [ ] 3.1.7 `save_stock_data` 实现：构 cache_key + envelope + 路由 primary + if 失败 fallback
- [ ] 3.1.8 `load_stock_data` 实现：路由 primary load + if None fallback
- [ ] 3.1.9 `find_cached_stock_data` 实现：构 cache_key + 调 load_stock_data 判存在（与 AdaptiveCacheSystem 现状一致）
- [ ] 3.1.10 `save_fundamentals_data` / `load_fundamentals_data` / `find_cached_fundamentals_data` 同 stock_data 模式，metadata.data_type="fundamentals"
- [ ] 3.1.11 `is_cache_valid` 实现：load envelope 取 timestamp + 与 TTL 比对
- [ ] 3.1.12 `get_cache_stats` 实现：遍历 cache_dir 统计 + backend_info
- [ ] 3.1.13 `get_cache_backend_info` 实现：返 config + db_manager available flags
- [ ] 3.1.14 `clear_old_cache(max_age_days)` 实现：遍历 cache_dir/*.json.gz，按 mtime 删过期

### 3.2 老类标记 deprecated

- [ ] 3.2.1 `integrated.py` `IntegratedCacheManager.__init__` 顶加 `warnings.warn("IntegratedCacheManager is deprecated; use Cache from tradingagents.dataflows.cache instead", DeprecationWarning, stacklevel=2)`
- [ ] 3.2.2 `adaptive.py` `AdaptiveCacheSystem.__init__` 同样模式

### 3.3 get_cache() 切换

- [ ] 3.3.1 修改 `cache/__init__.py` import `Cache` from `_cache`
- [ ] 3.3.2 `get_cache()` 当 `cache_strategy in {"integrated", "adaptive"}` 时构造并返 `Cache(file_backend, config, redis_backend, mongo_backend)`
- [ ] 3.3.3 `cache_strategy="file"` 仍走 `StockDataCache()`（不变）
- [ ] 3.3.4 `cache/__init__.py` `__all__` 加 `Cache` re-export

### 3.4 验证

- [ ] 3.4.1 跑 `just test`：新 + 老测试 MUST 全绿（含旧 cache_serialize / file_backend / redis_backend / mongo_backend / cache_config tests）
- [ ] 3.4.2 跑 `just lint` + `just typecheck`：MUST 全绿
- [ ] 3.4.3 跑 `just audit-binds` + `just audit-ports`：MUST 全绿
- [ ] 3.4.4 grep `pickle` in cache/：仍 0 命中
- [ ] 3.4.5 commit `feat(cache): 新 Cache 类 + IntegratedCacheManager/AdaptiveCacheSystem 标记 deprecated（green）`

## 4. 行为兼容验证（push 前）

- [ ] 4.1 `TA_CACHE_STRATEGY=integrated` `just up` → Python REPL：`from tradingagents.dataflows.cache import get_cache; c = get_cache()`
  - `isinstance(c, Cache)` MUST True（新行为）
  - `c.save_stock_data("000001", {"k": "v"}, "2026-01-01", "2026-01-02", "test")` 返非空 cache_key
  - `c.load_stock_data(cache_key)` 返回原数据
- [ ] 4.2 验证 app/routers/cache.py 路由能正常调 `cache.get_cache_stats()` / `clear_old_cache(7)` / `get_cache_backend_info()`
- [ ] 4.3 `just ci` 完整流水线绿灯
- [ ] 4.4 `just down`

## 5. 收尾

- [ ] 5.1 更新 `docs/CHANGELOG.md` `[Unreleased]` 段加条目
- [ ] 5.2 commit `docs(changelog): cache backend 4.4 — 统一 Cache 类 + deprecated 老类`
- [ ] 5.3 push main（1 click HARD-GATE）

## 6. 后续 sub-stage 触发

- [ ] 6.1 本 sub-stage merge 后 → 开 4.5 `cache-callsite-migration`（40+ 调用方迁移到新 `Cache`，体量 2 天 / 中-高风险）

## 验证清单（每个 commit 前）

- 公开 API 方法签名 / 返值类型 / 行为零改动
- `get_cache()` 返回类型从 `IntegratedCacheManager` 变 `Cache`，但**所有调用方走鸭子类型方法调用**（无 `isinstance` 检查；grep 已确认）
- 40+ 调用方零改动
- `cache_strategy="file"` 仍走 `StockDataCache`（不变）
- `tradingagents/dataflows/cache/` grep `pickle` 仍为 0
- `IntegratedCacheManager` / `AdaptiveCacheSystem` 仍可 instantiate，仅触发 DeprecationWarning
- `cache.get_cache_stats() / get_cache_backend_info() / clear_old_cache(N)` 返回字段集与 4.4 前一致（守护 app/routers/cache.py 消费）

## 与 4.3 的差异点

- 4.3 引入 config 抽象不改类层级；4.4 引入新公开类型 `Cache` + deprecated 老类
- 4.3 不引入 DeprecationWarning；4.4 在两处构造时触发
- 4.3 17 个新 unit test；4.4 预计 21 个 cache_class + 4 个 deprecation = ~25 个
- 4.3 测试纯 dataclass 无 mock；4.4 mock 3 个 backend 注入
