# dataflow-caching Specification

## ADDED Requirements

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

### Requirement: cache-key 与 TTL 经单一 helper

cache-key 生成与 TTL 解析逻辑 MUST 集中在单一 helper 模块（`cache/_common.py`），存活的缓存实现引用该 helper，不得各自维护 inline 拷贝。

- TTL 解析：MUST 由 helper 单一提供
- cache-key 生成：若各实现 key scheme 兼容，MUST 由 helper 单一提供；若不兼容，各实现保留各自 key scheme 但该差异 MUST 在 helper 模块或实现内显式记录（注释说明为何不能共用）

helper 的抽取 MUST 行为保持——对代表性输入产出与抽取前逐字节一致的结果。

#### Scenario: 无重复的 key/TTL 实现

- **WHEN** 在 `cache/` 下 grep MD5 cache-key 生成 / TTL 硬编码
- **THEN** key 生成（兼容前提下）与 TTL 解析的实现 MUST 仅出现在 `cache/_common.py`
- **AND** `file_cache.py` / `adaptive.py` MUST 调用 helper 而非各自 inline

#### Scenario: helper 抽取行为保持

- **WHEN** helper 抽取完成
- **THEN** 对代表性输入，helper 产出的 cache-key MUST 与抽取前各实现产出的逐字节一致（由单元测试护栏锁定）
