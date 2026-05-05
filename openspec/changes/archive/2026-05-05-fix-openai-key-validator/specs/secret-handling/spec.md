## ADDED Requirements

### Requirement: API key validator 必须接受供应商当前所有合法格式

任何 LLM / 数据源 provider 的 API key 校验器 MUST 接受该供应商**当前**发布的所有合法 key 格式，**禁止**硬编码单一长度 / 单一字符集。

具体到 OpenAI：

- 必须接受 `sk-` 开头的所有 key 形式
- 必须接受可能的子前缀（如 `sk-proj-`、`sk-svcacct-`）
- 字符集 MUST 包含 `[A-Za-z0-9_-]`（含连字符、下划线，sk-proj- 中常见）
- 长度限制 MUST 用范围（如 ≥ 32），**禁止**硬等于某个数字

历史经典 key 是 51 字符 `sk-[A-Za-z0-9]{48}`，但 2024+ 起 OpenAI 推 `sk-proj-` 项目级 key 长度可达 80+ 字符。供应商扩展 key 格式不需要 fork 改 validator——validator 设计上要面向未来。

#### Scenario: validate_openai_api_key_format 接受 sk-proj-

- **WHEN** `ConfigManager.validate_openai_api_key_format("sk-proj-AbC_dE-fG123...")` 被调用（满足前缀 sk- + 长度 > 32 + 字符集 `[A-Za-z0-9_-]`）
- **THEN** 返回 `True`

#### Scenario: validate_openai_api_key_format 拒绝明显错误

- **WHEN** `validate_openai_api_key_format("not-an-openai-key")` 被调用（前缀不是 sk-）
- **THEN** 返回 `False`
- **AND** `validate_openai_api_key_format("sk-short")`（长度 < 32）返回 `False`
- **AND** `validate_openai_api_key_format(None)` / `""` 返回 `False`
- **AND** `validate_openai_api_key_format("sk-with space")`（含空格）返回 `False`
