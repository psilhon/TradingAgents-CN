# Tasks — cache-callsite-hotfix-and-hardening (sub-stage 4.7)

> epic：`cache-layer-consolidation` stage 4（archived `2026-05-22-cache-backend-unification`）
> 前置：4.6 已完成（commit `f59c1541`）—— deprecated 类已删除
> 体量：~1-2 天 / 风险：中-低
> 公开 API 行为收敛回 4.6 前 IntegratedCacheManager 字节级兼容；新加 Backend Protocol clear 方法。

## 1. spec delta — commit 1（已落 + 立项 commit）

- [x] 1.1 写 4.7 proposal.md
- [x] 1.2 写 4.7 tasks.md（本文件）
- [ ] 1.3 修订 `docs/specs/dataflow-caching/spec.md` 「Cache」Requirement 公开方法签名段 + 加 Scenarios
- [ ] 1.4 commit `docs(spec): 立项 cache-backend-unification 4.7 — callsite hotfix + hardening`

## 2. P0 — 用户路径关键修复 (commit 2)

包含 8 个 finding（F1-F8）+ 配套 unit 测试。

- [ ] 2.1 `tradingagents/dataflows/optimized_china_data.py:252` 改 `data=fundamentals_data`（F1，1 行）
- [ ] 2.2 `_cache.py save_fundamentals_data / find_cached_fundamentals_data` data_type 回退到 `"fundamentals_data"`（F7）
- [ ] 2.3 `_cache.py load_stock_data / load_fundamentals_data` 加 envelope.timestamp + TTL 检查（F2）
- [ ] 2.4 `_cache.py find_cached_stock_data / find_cached_fundamentals_data` max_age_hours=None 时改走 default TTL（F2）
- [ ] 2.5 `_cache.py is_cache_valid` 优先读 envelope.metadata 的 data_type/symbol，caller args 仅 fallback（F6）
- [ ] 2.6 `_cache.py get_cache_stats` 加 `total_size` alias + 解 envelope per-type count（F3）
- [ ] 2.7 `backends/_protocol.py Backend` 加可选 `clear(max_age_days: int) -> None` 方法
- [ ] 2.8 `backends/{file,redis,mongo}.py` 实现 clear（F8）
- [ ] 2.9 `_cache.py clear_old_cache` 调 3 个 backend 的 clear（F8）
- [ ] 2.10 `backends/mongo.py` 改 `datetime.now(timezone.utc)` + 比对时 normalize（F4）+ unknown data_type delete_one（F4）
- [ ] 2.11 `_cache.py Cache` 加 `metadata_dir` property → `cache_dir / ".compat_empty_metadata"`（F5）
- [ ] 2.12 新建 `tests/test_cache_p0_hotfix.py` 覆盖 F1-F8 红测试
- [ ] 2.13 `just ci` 全绿
- [ ] 2.14 commit `fix(cache): P0 hotfix — 8 个用户路径 bug + 测试`

## 3. P1 — Observability + 防御性硬化 (commit 3)

包含 7 个 finding（O1-O7）+ 测试。

- [ ] 3.1 全文件 `logger.error(f"... {e}")` → `logger.exception(...)`（O1）—— grep + replace
- [ ] 3.2 `_save_routed` / `_load_routed` 加 `logger.info("primary={x} failed; using file fallback")`（O2）
- [ ] 3.3 `get_cache_stats` try 移到 loop 内（O3）
- [ ] 3.4 `Cache.__init__` 校验 primary_backend ↔ backends（O4）
- [ ] 3.5 `CacheConfig.__post_init__` Literal 校验 + 自定义 __hash__（O5）
- [ ] 3.6 `__init__.py` 加 `threading.Lock` 包 `_cache_instance`（O6）
- [ ] 3.7 `__init__.py` 加 `reset_cache()` + 首次失败不缓存（O7）
- [ ] 3.8 新建 `tests/test_cache_p1_hardening.py`
- [ ] 3.9 `just ci` 全绿
- [ ] 3.10 commit `feat(cache): P1 hardening — observability + 校验 + 单例锁`

## 4. P2 — 集成测试 + router schema (commit 4)

- [ ] 4.1 新建 `tests/integration/__init__.py`（如不存在）
- [ ] 4.2 新建 `tests/integration/test_cache_real_backends.py` mark `requires_env`，跑 round-trip
- [ ] 4.3 新建 `tests/test_router_cache_schema.py` mock get_cache，验证 router 响应字段
- [ ] 4.4 `tests/test_cache_p0_hotfix.py` 加 `_try_get_old_cache` callsite 不 raise AttributeError 测试
- [ ] 4.5 `just ci` 全绿（integration 测试需要 `just up`，CI 不强跑因 requires_env mark）
- [ ] 4.6 commit `test(cache): P2 integration + router schema + metadata_dir callsite`

## 5. P3 — 文档清理 + CHANGELOG + push (commit 5)

- [ ] 5.1 5 个文件删除 `AdaptiveCacheSystem` / `IntegratedCacheManager` 提及（替换为 `Cache`）（D1）
- [ ] 5.2 移除 sub-stage 版本考古 inline 注释（D2）
- [ ] 5.3 `_cache.py` 中 inline 中文注释改英文（D3）
- [ ] 5.4 更新 `docs/CHANGELOG.md` Unreleased 段
- [ ] 5.5 commit `docs(cache): P3 — 清理 deprecated 类引用 + 版本考古 + 英文注释 + changelog`
- [ ] 5.6 push main（HARD-GATE 1 click）

## 6. 验证清单（push 前）

- 公开 API 字节级兼容：
  - `Cache.save_fundamentals_data("AAPL", data)` cache_key MUST == `md5("AAPL___default_fundamentals_data")` (与 IntegratedCacheManager.save_fundamentals_data → adaptive 一致)
  - `Cache.save_stock_data("AAPL", data, None, None, None)` cache_key MUST 与 ("", "", "default") 一致（4.5 守护保留）
- TTL 强制：load_stock_data 在 envelope.timestamp 超 TTL 时返 None
- `_try_get_old_cache` 在新 Cache 下 silent return None（不 raise）
- `cache.clear_old_cache(0)` 调 redis flushdb + mongo delete_many（mock 验证）
- `cache.get_cache_stats()` 返 dict 含 6+ 字段，覆盖 router 期望
- `just ci` 全绿 / `just audit-binds` 合规 / grep `pickle` 0 / grep `import pandas in backends/` ≤ 1 (mongo only)
