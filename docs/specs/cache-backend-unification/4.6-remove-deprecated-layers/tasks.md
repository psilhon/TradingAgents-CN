# Tasks — cache-remove-deprecated-layers (sub-stage 4.6，epic 收尾)

> epic：`cache-layer-consolidation` stage 4（archived `2026-05-22-cache-backend-unification`）
> 前置：4.5 已完成（commit `e13631f2`）—— Cache 公开 API None-safe 签名兼容
> 体量：~0.5 天 / 风险：低
> 公开 API 行为零变更；非 TDD（纯删除，无新行为）。

## 1. spec delta — commit 1（先于代码）

- [ ] 1.1 在 `docs/specs/dataflow-caching/spec.md` **删除**「Requirement: IntegratedCacheManager / AdaptiveCacheSystem 标记 deprecated」整段（含 2 个 Scenario：DeprecationWarning 触发 / deprecated 类行为不变）
- [ ] 1.2 commit `docs(spec): cache-backend-unification 4.6 — 删除 deprecated 标记 Requirement`

## 2. 删除 deprecated 类 — commit 2

- [ ] 2.1 删除 `tradingagents/dataflows/cache/adaptive.py` 整文件
- [ ] 2.2 删除 `tradingagents/dataflows/cache/integrated.py` 整文件
- [ ] 2.3 删除 `tests/test_cache_deprecation.py` 整文件
- [ ] 2.4 修改 `tradingagents/dataflows/cache/__init__.py`：
  - 删除 `from .integrated import IntegratedCacheManager` try-import 块（含 `INTEGRATED_CACHE_AVAILABLE` flag 赋值）
  - 删除 `from .adaptive import AdaptiveCacheSystem` try-import 块（含 `ADAPTIVE_CACHE_AVAILABLE` flag 赋值）
  - 删除 `__all__` 中 4 个相关条目：`"AdaptiveCacheSystem"` / `"IntegratedCacheManager"` / `"ADAPTIVE_CACHE_AVAILABLE"` / `"INTEGRATED_CACHE_AVAILABLE"`
  - `get_cache()` 内 `INTEGRATED_CACHE_AVAILABLE` 条件检查改用 `UNIFIED_CACHE_AVAILABLE`
- [ ] 2.5 跑 `just test`：MUST 全绿（含 cache_class + cache_callsite_compatibility + cache_config + file_backend + redis_backend + mongo_backend + cache_serialize）
- [ ] 2.6 跑 `just lint` + `just typecheck`：MUST 全绿
- [ ] 2.7 跑 `just audit-binds` + `just audit-ports`：MUST 全绿
- [ ] 2.8 grep `IntegratedCacheManager` / `AdaptiveCacheSystem` in `tradingagents/` + `app/` MUST 0 命中（确认彻底清理）
- [ ] 2.9 grep `pickle` in cache/ 仍为 0
- [ ] 2.10 commit `chore(cache): 删除 deprecated IntegratedCacheManager + AdaptiveCacheSystem`

## 3. 行为兼容验证（push 前）

- [ ] 3.1 `just ci` 完整流水线绿灯（4.5 后 371 → 4.6 删 4 个 deprecation test ≈ 367）
- [ ] 3.2 `TA_CACHE_STRATEGY=file` + REPL：`from tradingagents.dataflows.cache import get_cache; isinstance(get_cache(), StockDataCache)` MUST True（file 策略路径不变）
- [ ] 3.3 `TA_CACHE_STRATEGY=integrated` + REPL：`isinstance(get_cache(), Cache)` MUST True（新 Cache 路径不变）

## 4. 收尾

- [ ] 4.1 更新 `docs/CHANGELOG.md` `[Unreleased]` 段加条目（4.6 删除 deprecated 类，epic 收尾）
- [ ] 4.2 commit `docs(changelog): cache backend 4.6 — 删除 deprecated 类，epic 收尾`
- [ ] 4.3 push main（1 click HARD-GATE）

## 5. epic 整体回顾（4.6 完成后）

- [ ] 5.1 `cache-layer-consolidation` 全 6 个 sub-stage 完成：4.1 FileBackend → 4.2 Redis/Mongo → 4.3 CacheConfig → 4.4 Cache 类 → 4.5 None-safe 兼容 → 4.6 删除 deprecated
- [ ] 5.2 cache 层最终拓扑：
  - `Cache` 类（284 行，单一公开 API）
  - 3 个 backends（FileBackend + RedisBackend + MongoBackend，~150 行/each）
  - `CacheConfig` dataclass（97 行）
  - `StockDataCache`（file 策略备用，未迁移；保留外部依赖兼容）
- [ ] 5.3 epic 总改动量：~1200+ 行新增 + ~743 行死代码删除（adaptive + integrated）
- [ ] 5.4 cache 测试覆盖：cache_serialize 5 + file_backend 10 + redis 12 + mongo 16 + cache_config 17 + cache_class 21 + callsite_compatibility 8 = **89 个 unit test**

## 验证清单（每个 commit 前）

- 公开 API 行为零变更（`get_cache().save_stock_data` 等仍工作）
- `TA_CACHE_STRATEGY=file` 仍走 `StockDataCache`
- `TA_CACHE_STRATEGY=integrated` 仍走 `Cache`
- 40+ 调用方零接触
- grep `IntegratedCacheManager` / `AdaptiveCacheSystem` in tradingagents/ + app/ MUST 0
- grep `pickle` 调用 MUST 0
- `StockDataCache` 仍可 import（2 个外部依赖保留）
