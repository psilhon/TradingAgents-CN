# Tasks — cache-config-dataclass (sub-stage 4.3)

> epic：`cache-layer-consolidation` stage 4（archived `2026-05-22-cache-backend-unification`）
> 前置：4.2 已完成（commit `89ae6dfa`）—— 3 个 backend 全部抽出
> 体量：~1-2 天 / 风险：中（`get_cache()` 入口决策 + AdaptiveCacheSystem ctor 路径变化）
> 公开 API 行为零变更；TDD red-green。

## 1. spec delta — commit 1（先于代码）

- [ ] 1.1 在 `docs/specs/dataflow-caching/spec.md` 追加 Requirement「CacheConfig 单一来源」：定义 `CacheConfig` dataclass 必含字段（`cache_strategy` / `primary_backend` / `fallback_enabled` / `ttl_settings`）+ `frozen=True` 不可变约束 + `from_environment(db_manager)` 工厂方法语义
- [ ] 1.2 加 Scenario：`CacheConfig` MUST 是 `@dataclass(frozen=True)`——构造后赋值字段 MUST raise `FrozenInstanceError`
- [ ] 1.3 加 Scenario：`from_environment` 后端推断三路径：redis_available → primary_backend="redis" / 仅 mongodb_available → "mongodb" / 都没 → "file"
- [ ] 1.4 加 Scenario：`from_environment` 读 `TA_CACHE_STRATEGY` env：默认 "integrated" / "file" → cache_strategy="file" / 非法值 fallback 默认 "integrated"（不 raise）
- [ ] 1.5 加 Scenario：`ttl_settings` MUST 含 6 个 market×data_type key（us_/china_ × stock_data/news/fundamentals），默认值与现状一致
- [ ] 1.6 加 Scenario：`AdaptiveCacheSystem(config=CacheConfig(...))` 可直接注入 config 不经过 db_manager.get_config()（unit test 友好）
- [ ] 1.7 明示「不在范围」：`TA_USE_APP_CACHE` 是 dataflow 数据源优先级开关，不属 `CacheConfig`（consumer：mongodb_cache_adapter / data_source_manager，与 cache backend 选择正交）
- [ ] 1.8 commit `docs(spec): cache-backend-unification 4.3 — CacheConfig 单一来源契约`

## 2. red — commit 2（先测试）

- [ ] 2.1 新建 `tests/test_cache_config.py`（仿 `tests/test_file_backend.py` spec_from_file_location 模式避免 dataflows 包副作用）
- [ ] 2.2 测试：`CacheConfig(cache_strategy="integrated", primary_backend="redis", fallback_enabled=True, ttl_settings={"us_stock_data": 7200, ...})` 构造成功
- [ ] 2.3 测试：`config.primary_backend = "file"` MUST raise `FrozenInstanceError`（frozen=True 验证）
- [ ] 2.4 测试：`from_environment(mock_db_manager)` redis 可用 → primary_backend="redis"
- [ ] 2.5 测试：`from_environment(mock_db_manager)` 仅 mongo 可用 → primary_backend="mongodb"
- [ ] 2.6 测试：`from_environment(mock_db_manager)` 都不可用 → primary_backend="file"
- [ ] 2.7 测试：`TA_CACHE_STRATEGY=file` env → cache_strategy="file"（monkeypatch）
- [ ] 2.8 测试：`TA_CACHE_STRATEGY` 未设置 → cache_strategy="integrated"
- [ ] 2.9 测试：`TA_CACHE_STRATEGY=invalid_value` → cache_strategy="integrated"（fallback 默认，不 raise）
- [ ] 2.10 测试：`ttl_settings` 默认含 6 个 standard key + 值匹配（us_stock_data=7200 / china_stock_data=3600 等）
- [ ] 2.11 测试：`config.ttl_settings["us_stock_data"]` = 7200（与 db_manager.get_config()["cache"]["ttl_settings"] 等价）
- [ ] 2.12 跑 `just test`：MUST 全 FAIL（红——`_config.py` 尚未实现）
- [ ] 2.13 commit `test(cache): CacheConfig 构造 + 不可变 + from_environment 三路径（red）`

## 3. green — commit 3（实现 + 包装层接入）

### 3.1 CacheConfig 实现

- [ ] 3.1.1 新建 `tradingagents/dataflows/cache/_config.py`
- [ ] 3.1.2 `@dataclass(frozen=True)` `CacheConfig` 含 4 字段
- [ ] 3.1.3 `_DEFAULT_TTL_SETTINGS` 模块级常量（6 个 key 与 db_manager 现状一致）
- [ ] 3.1.4 `from_environment(db_manager)` classmethod：
  - 读 `TA_CACHE_STRATEGY` env，验证 ∈ {"integrated", "adaptive", "file"}，否则默认 "integrated"
  - 从 `db_manager` 检测：redis_available → "redis" / mongodb_available → "mongodb" / else "file"
  - `fallback_enabled = True`（与现状硬编码一致）
  - `ttl_settings` 用 `_DEFAULT_TTL_SETTINGS`（注：未来若 db_manager 也 expose ttl override，可在此 merge）

### 3.2 AdaptiveCacheSystem 接入

- [ ] 3.2.1 `__init__(cache_dir=None, config: CacheConfig | None = None)` 加可选 config
- [ ] 3.2.2 `config is None` 时 `self.config = CacheConfig.from_environment(self.db_manager)`；否则 `self.config = config`
- [ ] 3.2.3 `self.primary_backend = self.config.primary_backend`（保留属性兼容 IntegratedCacheManager 现状）/ `self.fallback_enabled = self.config.fallback_enabled`
- [ ] 3.2.4 `_get_ttl_seconds` 改读 `self.config.ttl_settings.get(ttl_key, 7200)`
- [ ] 3.2.5 删 `self.cache_config = self.config["cache"]` 中转 + 直接 dict 读取路径

### 3.3 IntegratedCacheManager 接入

- [ ] 3.3.1 `__init__(cache_dir=None, config: CacheConfig | None = None)` 加可选 config
- [ ] 3.3.2 透传到 `AdaptiveCacheSystem(cache_dir, config=config)`
- [ ] 3.3.3 `_log_cache_status` / `get_cache_stats` 内 `self.adaptive_cache.primary_backend` 等保持（3.2.3 已保留属性兼容）

### 3.4 get_cache() 接入

- [ ] 3.4.1 删除 `cache/__init__.py` 模块级 `DEFAULT_CACHE_STRATEGY = os.getenv(...)`
- [ ] 3.4.2 `get_cache()` 调 `CacheConfig.from_environment(get_database_manager())` 拿 config
- [ ] 3.4.3 根据 `config.cache_strategy` 决定 instantiate `IntegratedCacheManager(config=config)` 或 `StockDataCache()`（StockDataCache 不接受 config 因为它是 file-only 路径）

### 3.5 验证

- [ ] 3.5.1 跑 `just test`：新 + 老测试 MUST 全绿
- [ ] 3.5.2 跑 `just lint` + `just typecheck`：MUST 全绿
- [ ] 3.5.3 跑 `just audit-binds` / `just audit-ports`：MUST 全绿
- [ ] 3.5.4 grep `os.getenv("TA_CACHE_STRATEGY")` 在 cache/ 目录 MUST 仅命中 `_config.py`（移到单一入口）
- [ ] 3.5.5 commit `feat(cache): CacheConfig dataclass + AdaptiveCacheSystem/IntegratedCacheManager/get_cache 接入（green）`

## 4. 行为兼容验证（push 前）

- [ ] 4.1 `TA_CACHE_STRATEGY=integrated` `just up` → CLI smoke：`from tradingagents.dataflows.cache import get_cache; get_cache()` 返回 `IntegratedCacheManager`
- [ ] 4.2 `TA_CACHE_STRATEGY=file` 重启 → 同测返回 `StockDataCache`
- [ ] 4.3 `just ci` 完整流水线绿灯
- [ ] 4.4 `just down`

## 5. 收尾

- [ ] 5.1 更新 `docs/CHANGELOG.md` `[Unreleased]` 段加条目
- [ ] 5.2 commit `docs(changelog): cache backend 4.3 — CacheConfig 单一来源`
- [ ] 5.3 push main（1 click HARD-GATE）

## 6. 后续 sub-stage 触发

- [ ] 6.1 本 sub-stage merge 后 → 开 4.4 `cache-unified-class`（新 Cache 类 + 公开 API 实现，体量 2-3 天 / 中风险）

## 验证清单（每个 commit 前）

- 公开 API 签名 / 行为零改动
- `get_cache()` 返回类型与现状一致（`StockDataCache` / `IntegratedCacheManager`）
- `AdaptiveCacheSystem(cache_dir=...)` 现有调用方零改动（config 是可选参数）
- `TA_CACHE_STRATEGY` env 含义不变（取值集 + 默认值）
- TTL 默认值字节级一致（6 个 key 数值未漂移）
- `tradingagents/dataflows/cache/` grep `pickle` 仍为 0
- `os.getenv("TA_CACHE_STRATEGY")` 在 cache/ 目录唯一命中 _config.py
