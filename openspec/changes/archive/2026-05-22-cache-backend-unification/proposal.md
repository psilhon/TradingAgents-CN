## Why

`docs/code-review-2026-05-05.md` 第三梯队 `cache-layer-consolidation` 的真正核心——前两个 stage（dead code 清理 / pickle 安全替换）已完成；剩余的「4 实现 → 1 抽象」是这一项的主体工作，单条 OpenSpec change 体量过大、风险过高，需要拆为 **multi-stage epic**。本 change 是 epic 的**立项 / 总图 / sub-stage 拆分蓝本**，不实施代码——sub-stage 各自开独立 change。

**现状（4 实现 + 包装层）**：

```
get_cache()                          [cache/__init__.py:84]
├── if TA_CACHE_STRATEGY == "file"
│     → StockDataCache              [file_cache.py，688 行，直接文件操作]
└── else (默认 integrated)
      → IntegratedCacheManager      [integrated.py，383 行，包装层]
          ├── self.legacy_cache = StockDataCache(...)
          └── self.adaptive_cache = AdaptiveCacheSystem(...)   [adaptive.py，stage 2 后 ~410 行]
                ├── _save_to_file / _load_from_file
                ├── _save_to_redis / _load_from_redis
                ├── _save_to_mongodb / _load_from_mongodb
                └── primary_backend 路由 + fallback → file
```

**问题**：

1. **两层包装**：`Integrated` 在 `Adaptive` 之上再包一层，做签名转换（`save_stock_data` ↔ `save_data` 等）。`Adaptive` 内部已经做 backend 路由——`Integrated` 的作用只是「if use_adaptive then adaptive else legacy」一个布尔分支，逻辑稀薄。
2. **后端混在 cache 类里**：`AdaptiveCacheSystem` 一个类里同时有 file/redis/mongodb 三套 save/load 私有方法 + 路由 + fallback——backend 不是可拔插组件，是硬编码分支。
3. **公开 API 与内部 API 不一致**：消费者用 `save_stock_data(symbol, data, start_date, end_date, data_source)` → str；`Adaptive` 内部用 `save_data(symbol, data, ..., data_type)`；翻译层散落在 `Integrated`。新加 backend / 改公开 API 都得改多处。
4. **config 散落**：`TA_CACHE_STRATEGY`（顶层）+ `TA_USE_APP_CACHE`（adapter 内部，与 stage 1 的孤儿 db_cache 同 layer 但独立）—— stage 3 调查发现「三开关统一」其中 1 个 (`USE_MONGODB_STORAGE`) 实际属 ConfigManager 不属 cache，剩 2 个 cache switch 也没有自然的单一 config 对象——真正的 cache config 统一必须随抽象重设计一起做（折叠到本 epic 的 sub-stage）。
5. **40+ 调用方**：`get_cache()` 在 `tradingagents/` / `app/` / `tests/` / `scripts/` 共 40+ 处。任何抽象改动须严格保持公开 API 行为兼容。

## What Changes

### 目标架构

```
Cache(backend: Backend, fallback: Backend | None = None)   [单一类]
  公开 API：save_stock_data / load_stock_data / find_cached_stock_data
            / save_news_data / load_news_data
            / save_fundamentals_data / load_fundamentals_data
            / get_cache_stats / clear_old_cache

Backend (Protocol)                                          [可拔插接口]
  abstract: save(key, envelope) -> bool
            load(key) -> dict | None
            list_keys() -> list[str]
            delete(key) -> None

FileBackend(Backend)        [现 _save_to_file/_load_from_file 拆出]
RedisBackend(Backend)       [现 _save_to_redis/_load_from_redis 拆出]
MongoBackend(Backend)       [现 _save_to_mongodb/_load_from_mongodb 拆出]

CacheConfig (dataclass)                                     [统一 config]
  primary_backend: "redis" | "mongodb" | "file"
  fallback_to_file: bool
  use_app_cache_priority: bool                              [folded TA_USE_APP_CACHE]
  cache_strategy: "file" | "integrated"                     [folded TA_CACHE_STRATEGY]
  ttl_settings: dict
```

`Integrated` 与 `Adaptive` 两个类**消失**——它们的功能合并到 `Cache`。`StockDataCache` 的市场分类目录与「stock/news/fundamentals」三类 API 由 `Cache` 通过 `FileBackend` 实现（market 判定逻辑保留在 `Cache` 层，因为 redis/mongo 后端也需要相同的 routing）。

### Sub-stage 拆分（建议）

每个 sub-stage 独立 OpenSpec change，独立 TDD、独立 commit 链、独立 push + CI。

| # | Sub-stage | 范围 | 体量 | 风险 |
|---|---|---|---|---|
| **4.1** | `Backend` Protocol + `FileBackend` 提取 | 定义接口；把 `_save_to_file`/`_load_from_file` 从 `AdaptiveCacheSystem` 拆出到独立 `FileBackend` 类；adaptive 内部改用 backend 调用。单元测试 round-trip。**`get_cache()` 行为不变。** | 1 天 | 低 |
| **4.2** | `RedisBackend` / `MongoBackend` 提取 | 同 4.1 模式拆 Redis / MongoDB 路径出 `AdaptiveCacheSystem`。安全序列化（stage 2）helper 仍用。 | 1 天 | 低 |
| **4.3** | `CacheConfig` 统一 dataclass | 引入 `cache/_config.py` 的 `CacheConfig` —— 解析 `TA_CACHE_STRATEGY` + `TA_USE_APP_CACHE` + adaptive 的 `cache_config["ttl_settings"]` + `primary_backend` / `fallback_enabled` 等。`AdaptiveCacheSystem` 与 `IntegratedCacheManager` 读 `CacheConfig` 而非散落 env / dict。 | 1-2 天 | 中 |
| **4.4** | 新 `Cache` 类与公开 API | 实现新 `Cache(backend, fallback)` 类，公开 API 取消费者实际使用的 5+ 方法。`AdaptiveCacheSystem` / `IntegratedCacheManager` 标记 deprecated 但保留可用。 | 2-3 天 | 中 |
| **4.5** | `get_cache()` 切换 + 调用方迁移 | `get_cache()` 返回新 `Cache`。40+ 调用方的公开 API 形式不变，但运行的实例是新 `Cache`。覆盖：`tradingagents/dataflows/`、`app/routers/cache.py` 等。集成测试 / 烟雾测试通过。 | 2 天 | 中-高 |
| **4.6** | 删除 deprecated `Adaptive` / `Integrated` / `StockDataCache` | 移除 3 个 deprecated 类、连带 `cache/__init__.py` 的 try-import / `__all__` 清理。仅在 4.5 完成且观察期无回归后执行。 | 0.5 天 | 低（如前置稳） |

预计总体量 **~7-9 天 wall-clock**。每条 sub-stage 应当独立 review、独立 push + CI 绿灯后再开下一条；不允许跨 stage 半成品堆积。

### 不在 epic 范围

- `MongoDBCacheAdapter`（445 行）与 `app_adapter`（120 行）：与 `get_cache()` 体系正交——它们是**优先数据源**（直接读 app 的 `tradingagents` DB 集合），不是 cache backend。14+ 调用方独立调用。保留原样。
- `app/services/foreign_stock_service.py` / `app/routers/cache.py`：属专有授权范围，**不动**业务代码；只通过 `get_cache()` 的公开 API 行为不变保证它们继续工作。

## Capabilities

### Modified Capabilities

- `dataflow-caching`：本 epic **整体落地后**扩入新 Requirement「单一 Cache 抽象 + 可拔插 Backend 协议」、「统一 CacheConfig」。具体 spec delta 在 sub-stage 各自的 change 内 ADDED——本立项 change **不含** spec delta（避免提前承诺尚未实施的契约）。

## Impact

**改动文件**（本立项 change 仅 3 个）：`proposal.md` + `tasks.md` + （无 spec delta）。

**许可边界**：本立项 change 只触动 `openspec/`。各 sub-stage 主要触 `tradingagents/dataflows/cache/`（Apache 2.0），仅最后调用方迁移阶段会 read（不写）`app/` 的 `get_cache()` 调用点验证行为兼容。

**风险**（epic-level）：
- 40+ 调用方覆盖面广；公开 API 行为兼容必须用代表性集成测试 / 烟雾测试守住
- `IntegratedCacheManager` 的 `use_adaptive` 布尔分支隐含运行时降级——新 `Cache` 的 fallback 逻辑必须等价覆盖
- `MongoDBCacheAdapter` 不动是有意为之；epic 不试图把它纳入 `Backend` 抽象（它是数据源不是 cache）——文档显式说明

**收益**：
- cache 层从 2 包装层 + 4 实现 + 散落后端方法 → 1 Cache + N Backend，新增 backend 只加一个 class
- `CacheConfig` 单一 schema 终结 stage 3 调查发现的「config 散落」问题
- 后续若要做 cache-key / TTL 统一（stage 1 Part B deferred 项），在新抽象下成为自然的 `Cache` 类内一个 method，不再是不可调和的两套 scheme

## 立项动作

本 change archive 时机：sub-stage 4.1 立项时——届时本 epic 文档已发挥蓝本作用，归档保留为决策追溯。在此之前保留为 active change，作为 sub-stage 4.x 的引用锚点。
