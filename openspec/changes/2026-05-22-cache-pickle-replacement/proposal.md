## Why

`docs/code-review-2026-05-05.md` 标记的 `pickle.load` 不安全反序列化。`cache-layer-consolidation` 的 stage 2——延续 stage 1 的「分阶段」策略，本 change 单点处理 pickle 安全债。

`tradingagents/dataflows/cache/adaptive.py` 共 7 处 pickle：

| 位置 | 调用 | 路径 |
|---|---|---|
| L80 | `pickle.dump(cache_data, f)` | 文件保存 |
| L97 | `pickle.load(f)` | 文件加载 |
| L115 | `pickle.dumps(cache_data)` | Redis 保存 |
| L136 | `pickle.loads(serialized_data)` | Redis 加载 |
| L164 | `pickle.dumps(data).hex()` | MongoDB 保存（非 DataFrame 分支） |
| L209 | `pickle.loads(bytes.fromhex(...))` | MongoDB 加载（非 DataFrame 分支） |
| L395 | `pickle.load(f)` | `clear_expired_cache` 扫描时反序列化 |

`pickle.load` 是 RCE 原语——只要攻击者能向 `data/cache/` 写文件、Redis、或 MongoDB `tradingagents.cache` 集合，即可在解 pickle 时执行任意代码。本机 dev 环境也不是免责依据（恶意依赖 / 串目录 / 错误备份恢复都可能注入）。

## What Changes

### 新增统一序列化 helper

新建 `tradingagents/dataflows/cache/_serialize.py`：

- `encode_envelope(envelope: dict) -> bytes`：tagged JSON + gzip。递归处理 `datetime`（ISO 字符串标签）/ `pandas.DataFrame`（`to_json(orient='split')` 标签）/ dict / list；未知类型 `json.dumps` 自然抛 TypeError，由 adaptive.py 外层 except 降级为 cache miss。
- `decode_envelope(blob: bytes) -> dict`：反向；老 pickle bytes 解 gzip+json 必失败 → 抛 → 外层 except → cache miss（**永不调用 `pickle.loads`**）。

### 替换 adaptive.py 的 7 处 pickle

| 后端 | save | load |
|---|---|---|
| file | `encode_envelope(envelope)` → `{key}.json.gz` | `decode_envelope(read)` |
| Redis | `encode_envelope(envelope)` 存 bytes | `decode_envelope(bytes)` |
| MongoDB | DataFrame 分支 `to_json` 保留不动；else 改 `data_type="json"` + `json.dumps(data, default=str)` | DataFrame：`pd.read_json` 不动；`data_type="json"`：`json.loads`；`data_type="pickle"`（legacy）：return None（**不** `pickle.loads`） |

文件扩展名从 `.pkl` 改为 `.json.gz`。

### Legacy 数据处理

- **文件**：`clear_expired_cache` 同时 `glob("*.pkl")` 并 `unlink()`（不 `pickle.load`）。新 cache miss 自然冷启动。
- **Redis**：老 pickle bytes 在 `decode_envelope` 失败 → cache miss。Redis TTL 自动过期回收。
- **MongoDB**：legacy `data_type="pickle"` doc 在加载时 return None 并删除 doc（用 `collection.delete_one`，不 unpickle）。

### 验收

- `grep -rn "pickle" tradingagents/dataflows/cache/` 命中数 = 0（`import pickle` / 任何 `pickle.dump*` / `pickle.load*` 全部消失）
- 序列化单元测试覆盖 dict / DataFrame / 嵌套 datetime / 老 pickle bytes 拒绝路径
- `just ci` 全绿，`pytest -m unit` 无回归

### 不在范围

- key 生成 / TTL 统一、4 实现合并、config 统一——属后续 stage（cache-layer-consolidation 全量收敛阶段）
- `mongodb_cache_adapter.py` / `app_adapter.py` 旁路（无 pickle 使用，与本 change 无关）

## Capabilities

### Modified Capabilities

- `dataflow-caching`：**扩**——加 Requirement「缓存序列化禁用 pickle」。

## Impact

**改动文件**：1 新建 helper + 1 新建 test + 改 `adaptive.py` + 1 spec delta + 1 CHANGELOG 段

**许可边界**：全部在 `tradingagents/dataflows/cache/`（Apache 2.0）。

**风险**：
- 序列化格式变更——既有缓存条目（文件 `.pkl` / Redis pickle bytes / MongoDB `data_type="pickle"` doc）变成 cache miss，冷启动一次重填。无正确性影响（缓存是性能优化），但首次运行有数据源回源开销。
- DataFrame 经 `to_json(orient='split')` 往返：`split` 保留 index / columns / values 完整结构，类型兼容；测试覆盖。
- `json.dumps(default=str)` 用于 MongoDB 非 DataFrame 路径：保险兜底，不应触发常见类型。

**收益**：消除 `cache/` 下所有 `pickle.load*` 调用，关闭 code-review 标记的 RCE 攻击面。
