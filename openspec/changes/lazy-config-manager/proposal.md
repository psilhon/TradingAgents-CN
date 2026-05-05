## Why

`docs/code-review-2026-05-05.md` Tier 2 第 4 条：`tradingagents/config/config_manager.py:744-745` module import 时**立即实例化** `ConfigManager(...)` + `TokenTracker(...)`，副作用包括：

- `Path.mkdir(exist_ok=True)` 创建 `config/` 目录
- 读 `.env` 文件 + `load_dotenv()`
- 连接 MongoDB（同步阻塞 ~50-100ms）
- 写 4 个 JSON 配置文件（如 `models.json` / `pricing.json` / `settings.json` 不存在时）
- 触发 `DeprecationWarning`

任何 `import tradingagents.config` 路径都触发——CLI 启动 / pytest collect / IDE 索引 / 简单 utility import 都会**意外**连 mongodb + 写文件。已实测：仅 import `tradingagents.utils.api_key_utils` 即触发 mongodb 连接（共享导入链 → `tradingagents/__init__.py` → `tradingagents/config/__init__.py` → `config_manager.py`）。

## What Changes

- **MODIFIED** `tradingagents/config/config_manager.py:744-745`：
  - 删除 module-level `config_manager = ConfigManager(...)` + `token_tracker = TokenTracker(...)`
  - 加 `__getattr__(name)` (PEP 562) 实现 lazy singleton
- **MODIFIED** `tradingagents/config/__init__.py`：相应改 lazy re-export

行为契约：第一次访问 `config_manager` / `token_tracker` 时初始化（行为与之前相同），后续访问直接复用 singleton。

无 BREAKING change（API 表面不变，仅初始化时机延后）。

## Capabilities

### Modified Capabilities

- `secret-handling`：在已有 spec 加 requirement "module import 不得触发 secret / DB 连接副作用"

## Impact

**改动文件**：2 个 Python 文件
**风险**：低——lazy 后首次使用时机延后，但 ConfigManager 之前能工作的场景仍能工作
**收益**：CLI / pytest collect / 工具脚本 import tradingagents.* 不再连 mongodb / 写 JSON / load .env
