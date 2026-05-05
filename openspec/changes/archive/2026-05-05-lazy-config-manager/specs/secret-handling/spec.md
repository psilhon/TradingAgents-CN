## ADDED Requirements

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
