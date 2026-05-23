## Why

`cache-layer-consolidation` epic 6 个 sub-stage 完成后，两轮 code review（`/code-review` + `/pr-review-toolkit:review-pr`）合计发现 ~25 个独立 finding。其中 8 个属于「ship 即影响用户」的关键路径 bug，7 个属可观测性 / 防御性硬化，3 个测试覆盖缺口，3 个文档/风格遗漏。本 sub-stage 一次性修补。

**触发**：现状代码已 push 到 origin/main (`f59c1541`)，默认 `TA_CACHE_STRATEGY=integrated` 配置下：

- A 股 fundamentals 报告 100% silent fail（kwarg 不匹配 + TypeError 被外层 try/except 吞）
- `cache.load_stock_data(key)` 返指 indefinitely 老数据（TTL 不被任何 read path enforce）
- `/api/cache/stats` 返回总是 `total_size=0` + 3 个 per-type count=0（router 读的字段不在新 dict）
- `/api/cache/clear` 弹"成功"但 Redis/Mongo cache 未触及
- MongoDB 缓存条目 8 小时 timezone 漂移（naive `datetime.now()` vs pymongo naive UTC）
- A 股 / 美股「过期缓存兜底」safety net silent dead（`metadata_dir` AttributeError）
- A 股 fundamentals cache_key 与历史不字节级一致（`data_type="fundamentals"` vs `"fundamentals_data"`），既有 cache 全 miss
- A 股 entry 经 `is_cache_valid(key)` 不传 symbol → 默认走 `us_stock_data=7200s` 而非 `china_*=3600s`

## What Changes

### P0 — 用户路径关键修复（8 个 finding）

1. **F1 修 callsite kwarg**：`tradingagents/dataflows/optimized_china_data.py:252` `fundamentals_data=` → `data=`
2. **F7 fundamentals data_type 回退**：`Cache.save_fundamentals_data` + `find_cached_fundamentals_data` + `_get_ttl_seconds("X", "fundamentals")` 内部 data_type 改回 `"fundamentals_data"`（与 IntegratedCacheManager 字节级一致），TTL key 仍是 `china_fundamentals` / `us_fundamentals`
3. **F2 load 路径加 TTL**：`Cache.load_stock_data` / `load_fundamentals_data` 检查 envelope.timestamp + ttl_settings 派生 TTL；`find_cached_*(max_age_hours=None)` 走同样 TTL（不再 None 跳过）
4. **F6 is_cache_valid 读 envelope metadata**：从 envelope.metadata.data_type + metadata.symbol 派生 TTL bucket，caller args 仅作 fallback
5. **F3 get_cache_stats 补字段**：加 `total_size`（alias of total_size_bytes）+ 解 envelope per-type count（`stock_data_count` / `news_count` / `fundamentals_count`）
6. **F8 clear_old_cache 扩 Redis/Mongo**：`Backend` Protocol 加可选 `clear(max_age_days)` 方法，`RedisBackend.clear(0)` 调 `flushdb()`，`MongoBackend.clear(0)` 调 `delete_many({})`，`FileBackend.clear(N)` 即现有 file glob 逻辑。`Cache.clear_old_cache` 调 3 个 backend 的 clear
7. **F4 mongo timezone-aware**：`MongoBackend` save/load 用 `datetime.now(timezone.utc)`；read 时 normalize 比对；unknown `data_type` 不止 warn，还要 `delete_one` 消除 zombie
8. **F5 metadata_dir AttributeError 兼容**：`Cache` 加 `metadata_dir` property → 指向 `cache_dir / ".compat_empty_metadata"`（不实际创建）；`*_meta.json` glob 永远空 → `_try_get_old_cache` silent 退化为 return None（消除 AttributeError，但 stale-cache fallback 仍 dead；恢复 fallback 留待 P4）

### P1 — 可观测性 + 防御性硬化（7 个 finding）

9. **O1 logger.exception**：所有 backend + Cache + __init__ 内 `logger.error(f"... {e}")` → `logger.exception(...)`（保留 traceback）
10. **O2 fallback transition log**：`_save_routed` / `_load_routed` 加 `logger.info("primary={x} failed; using file fallback")`
11. **O3 per-iter stat**：`Cache.get_cache_stats` try 移到 loop 内
12. **O4 Cache.__init__ 校验**：`primary_backend="redis"` 且 `redis_backend=None` raise ValueError；mongo 同
13. **O5 CacheConfig 运行时校验**：`__post_init__` validate `cache_strategy` / `primary_backend` Literal；显式 `eq=True, unsafe_hash=False`，自定义 `__hash__` 基于 sorted ttl_settings tuple
14. **O6 单例线程安全**：`__init__.py` 加 `threading.Lock` 包 `_cache_instance`
15. **O7 reset_cache + 失败不缓存**：新加 `reset_cache()` API；首次创建若走 fallback（Cache 初始化失败 → StockDataCache）不 cache，下次 get_cache 重试

### P2 — 测试覆盖（3 个 finding）

16. **T1 integration suite**：`tests/integration/test_cache_real_backends.py` mark `requires_env`（需要 `just up`），跑 3 backend round-trip + mongo timezone + redis bytes 路径
17. **T2 _try_get_old_cache callsite test**：mock `get_cache()` 返新 Cache 实例，断言 `_try_get_old_cache` 不再 raise AttributeError
18. **T3 router schema test**：FastAPI TestClient `app/routers/cache.py`（mock `get_cache()`），断言响应 dict 含 router 期望 4 个字段

### P3 — 文档清理（3 个 finding）

19. **D1 删除 stale 类引用**：5 个文件移除 `AdaptiveCacheSystem` / `IntegratedCacheManager` 提及（替换为 `Cache`）
20. **D2 删除 sub-stage 版本考古**：inline 「4.4 时写的 ...」「4.5 起 ...」「sub-stage 4.X」锚点全删，保留行为描述
21. **D3 统一英文注释**：`_cache.py` 中文 inline 注释（L57 / L118 / L183 / L218 / L246）改英文

## Capabilities

### Modified Capabilities

- `dataflow-caching`（位于 `docs/specs/dataflow-caching/spec.md`）：
  - **修订**「统一 Cache 类」Requirement 公开方法签名段：明示 `load_*` 和 `find_cached_*` 强制 TTL 检查；`is_cache_valid` 从 envelope.metadata 读 data_type/symbol；`get_cache_stats` 返回 dict 必含 `total_size` / `stock_data_count` / `news_count` / `fundamentals_count`
  - **扩展**「Backend Protocol 接口」加可选 `clear(max_age_days: int) -> None` 方法（File: 文件 glob 删；Redis: flushdb 当 days=0；Mongo: delete_many 当 days=0）
  - **修订**「MongoBackend 单一职责」加 timezone-aware UTC 要求 + 未知 data_type delete_one
  - **修订**「CacheConfig 单一来源」加 `__post_init__` Literal 校验 + 显式 hash 规则
  - ADDED Scenario「Cache 公开 API None-safe 字节级兼容」加 fundamentals data_type 回退守护
  - ADDED Scenario「Cache load_stock_data 强制 TTL」/「is_cache_valid 读 envelope metadata」/「clear_old_cache 跨 backend 清理」

## Impact

**改动文件**（5 改 + 4 新）：

- 改：`tradingagents/dataflows/cache/_cache.py`（公开 API 行为修复 + 新方法）
- 改：`tradingagents/dataflows/cache/_config.py`（__post_init__）
- 改：`tradingagents/dataflows/cache/__init__.py`（lock + reset_cache + 失败不缓存）
- 改：`tradingagents/dataflows/cache/backends/_protocol.py`（加 clear 方法）
- 改：`tradingagents/dataflows/cache/backends/{file,redis,mongo}.py`（clear 实现 + timezone-aware + logger.exception）
- 改：`tradingagents/dataflows/optimized_china_data.py:252`（kwarg fix，1 行）
- 改：`docs/specs/dataflow-caching/spec.md`
- 改：`docs/CHANGELOG.md`
- 新：`tests/test_cache_p0_hotfix.py` / `tests/test_cache_p1_hardening.py` / `tests/integration/test_cache_real_backends.py`

**许可边界**：全部 `tradingagents/dataflows/cache/`（Apache 2.0，cache epic 范围内）+ `tradingagents/dataflows/optimized_china_data.py`（Apache 2.0 主代码，cache epic hotfix 性质，1 行 kwarg 修复有明确范围）。**不动** `app/` / `frontend/`。

**风险**：中-低

- P0 修复都是「补回 IntegratedCacheManager 时代的行为」，回退到字节级兼容
- P0 F8 扩 Backend Protocol（加 clear 方法）—— 这是公开 Protocol 变更，但 Protocol 自身在 4.6 后仅有 cache/_cache.py 一个消费方，影响范围限于本 epic
- P1 全是防御性加硬，无行为变化
- P3 纯文档

**收益**：

- 4 个 critical 用户面故障消除（A 股 fundamentals / load TTL / clear / stats UI）
- 历史 cache_key 字节级回退兼容（升级到 4.6 不丢已有 cache）
- 真实 traceback + fallback log，未来类似问题快速定位
- 单例锁消除冷启动 race
- 文档去除 stale 引用，git blame 仍可追溯 sub-stage 4.X 历史

**回滚**：

5 commits 串行（spec → P0 → P1 → P2 → P3+changelog+push），任一回退 = `git revert`。
