# secret-handling Specification

## Purpose
TBD - created by archiving change redact-api-key-logs. Update Purpose after archive.
## Requirements
### Requirement: API key 在 log / 显示中必须脱敏

任何 API key / token / secret 输出到 log / Rich 表格 / 错误信息 / 文件 等场景 MUST 脱敏。允许的输出形式：

- `(missing)` 或 `空` 或 `未配置`：表示 key 缺失
- `(len=N, ends ...XXXX)`：仅展示长度 + 末 4 字符（用于辨识但无法暴破缩范围）
- `存在` / `已配置`：仅 boolean

**禁止**的输出形式：
- 任何形式的"前缀截取"（`key[:N]` 含 N ≥ 1）
- key 全文
- key 校验后的派生字段（如 hash 前缀）

#### Scenario: tradingagents/ + cli/ 不出现 key 前缀截取

- **WHEN** 在 `tradingagents/` 和 `cli/` 目录 grep `(api_)?key\[:[0-9]+\]` 或 `truncate_api_key`（用于显示场景，不含 utility 自身定义）
- **THEN** 命中数 MUST = 0

#### Scenario: 标准脱敏 helper 必须可用

- **WHEN** 任意模块需要在 log / 显示中输出 API key
- **THEN** import path MUST 是 `tradingagents.utils.api_key_utils.redact_api_key`
- **AND** 该函数返回的字符串 MUST NOT 含 key 前缀

#### Scenario: 末 4 字符规则

- **WHEN** `redact_api_key("sk-abc...XYZ1234")` 被调用（key 长度 > 8）
- **THEN** 返回 `f"(len={N}, ends ...1234)"` 形式
- **AND** key 长度 ≤ 8 时返回 `f"(len={N}, ***)"`（不暴露任何字符）
- **AND** key 为 None / 空字符串时返回 `(missing)`

### Requirement: module import 不得触发 secret / DB 副作用

`tradingagents/` 任何模块的 module-level 代码（import 即执行）MUST NOT 触发以下副作用：

- 连接 MongoDB / Redis / 外部 HTTP 服务
- 读 `.env` / 调 `load_dotenv()`（除非该模块就是 .env 加载入口）
- 写文件 / `Path.mkdir`
- 调用 LLM / 数据源 API
- 修改全局 `sys.path` / monkey-patch 全局函数

副作用 MUST 移到首次调用 / 显式 init 函数 / 实例方法触发——常见模式是 `__getattr__` (PEP 562) 实现 lazy singleton。

#### Scenario: 纯 import 不触发 mongodb 连接

- **WHEN** 用户执行 `python -c "from tradingagents.utils.api_key_utils import is_valid_api_key"`
- **THEN** 进程 stdout / stderr MUST NOT 出现 `MongoDB连接成功` / `MongoDBStorage` / 等 db 连接日志
- **AND** `Path.mkdir` 不被调用（除非该 utility 自身需要）

#### Scenario: 首次访问 lazy singleton 触发初始化

- **WHEN** 用户执行 `from tradingagents.config.config_manager import config_manager` 后立即访问 `config_manager.config_dir`
- **THEN** 此时（首次访问）触发 ConfigManager 初始化（mongodb / .env / mkdir）
- **AND** 返回的 `config_manager` 是 ConfigManager 实例
- **AND** 后续访问复用 singleton（不重新初始化）

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

