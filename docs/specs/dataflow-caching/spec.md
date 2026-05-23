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

- `save(key: str, envelope: dict) -> bool` — 将 envelope dict 写入后端，成功返回 `True`，失败返回 `False`（不 raise）
- `load(key: str) -> dict | None` — 从后端读取 envelope dict；不存在 / 读取失败返回 `None`（不 raise）

Protocol MUST NOT 包含：

- TTL 判定逻辑（由调用方 `AdaptiveCacheSystem` / 未来的 `Cache` 类负责）
- 后端路由 / fallback 选择（由 cache 顶层负责）
- envelope 构建（`timestamp` / `backend` 标签等元数据由调用方填充）

后端实现 MUST 保持「字节进字节出」的薄层职责——把 envelope dict 经 `_serialize.py` 的 `encode_envelope` / `decode_envelope` 与底层存储介质双向转换，不解释 envelope 内部结构。

#### Scenario: Protocol 接口最小性

- **WHEN** 检查 `Backend` Protocol 定义
- **THEN** MUST 仅含 `save` / `load` 方法签名（4.1 阶段），不含 TTL / 路由 / envelope 构建相关方法
- **AND** 任何 backend 实现 MUST 通过 `isinstance(impl, Backend)` 结构性检查（Protocol 鸭子类型）

### Requirement: FileBackend 单一职责

`tradingagents/dataflows/cache/backends/file.py` 的 `FileBackend` 类 MUST 仅负责文件 IO，符合 `Backend` Protocol。具体：

- `__init__(cache_dir: Path)` — 接收缓存目录，MUST `mkdir(parents=True, exist_ok=True)` 确保存在
- `save(key, envelope) -> bool` — 写入 `{cache_dir}/{key}.json.gz`，经 `encode_envelope` 编码；失败返回 `False`
- `load(key) -> dict | None` — 读取 `{cache_dir}/{key}.json.gz`，经 `decode_envelope` 解码；文件不存在或解码失败返回 `None`

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

- **WHEN** 在 `tradingagents/dataflows/cache/backends/` 全目录 grep `import pandas` / `import pickle`
- **THEN** 命中数 MUST = 0
- **AND** 在该目录 grep `from tradingagents.dataflows` 命中 MUST 仅指向 `tradingagents.dataflows.cache._serialize`（serialize helper 是允许的依赖）
