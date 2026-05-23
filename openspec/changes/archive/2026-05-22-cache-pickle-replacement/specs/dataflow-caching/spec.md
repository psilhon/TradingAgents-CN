## ADDED Requirements

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
