## ADDED Requirements

### Requirement: 通用 utility 必须放在 tradingagents/utils/

无业务语义、无 app/ 专属逻辑的纯 Python 通用工具函数（API key 校验 / 字符串处理 / 时间格式化等）MUST 放在 `tradingagents/utils/` 下。`app/` 若需要使用同一 utility 应 import `tradingagents.utils.*`，**不得**反过来——`tradingagents/` 不得 import `app.utils.*`。

#### Scenario: tradingagents/ 不得 import app.utils

- **WHEN** 在 `tradingagents/` 目录 grep `from app\.utils\.|^import app\.utils\.`（排除 `__pycache__`）
- **THEN** 命中数 MUST = 0

#### Scenario: API key utility 位置

- **WHEN** 任意模块需要使用 `is_valid_api_key` / `truncate_api_key` / `get_env_api_key_for_*` / `should_skip_api_key_update`
- **THEN** import path MUST 是 `tradingagents.utils.api_key_utils`
- **AND** `app/utils/api_key_utils.py` 不存在

### Requirement: tradingagents/ 不得反向 import app/ 业务层（follow-up）

`tradingagents/` 主代码 MUST NOT runtime import `app.core.*` / `app.services.*` / `app.worker.*` 等业务层模块。这是 license 边界 + 模块化原则的双重要求。

**当前状态**：v1.1.0 后 audit 发现仍有 20+ 处反向 import（`app.core.config` / `app.core.database` / `app.services.news_data_service` / `app.worker.tushare_sync_service` 等），分散在 `tradingagents/dataflows/` / `utils/stock_validator.py` / `tools/unified_news_tool.py`。这些是历史耦合，需要专门的 OpenSpec change `eliminate-app-business-layer-imports`（梯队 3 范畴）系统性消除。

#### Scenario: 反向 import 数量必须单调下降

- **WHEN** v1.1.0 起对 `tradingagents/` 目录 `grep "from app\." --include="*.py" --exclude-dir=__pycache__` 计数
- **THEN** 每个新 PR 后该数量 MUST 不超过上一次 commit
- **AND** 仓库 baseline 数（v1.1.0 后）记录在 `docs/code-review-2026-05-05.md`，新计数不得超过 baseline
