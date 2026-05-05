## Why

`docs/code-review-2026-05-05.md` 第 3 个 critical 发现：Apache 2.0 的 `tradingagents/llm_adapters/` 反向 import 专有授权的 `app.utils.api_key_utils.is_valid_api_key` 共 **5 处**。这违反 fork license 分层（`tradingagents/` 是 Apache 2.0 主代码，`app/` 是专有授权）。

具体违规位点：
- `tradingagents/llm_adapters/google_openai_adapter.py:59`
- `tradingagents/llm_adapters/openai_compatible_base.py:80`
- `tradingagents/llm_adapters/openai_compatible_base.py:245`
- `tradingagents/llm_adapters/dashscope_openai_adapter.py:42`
- `tradingagents/llm_adapters/deepseek_adapter.py:66`

`app/utils/api_key_utils.py` 是纯 Python 通用工具（API key 校验 / 缩略 / env 读取），无业务语义、无 app 专属逻辑——应放在 Apache 2.0 层，由 app/ 反向 import。

## What Changes

- **MOVED** `app/utils/api_key_utils.py` → `tradingagents/utils/api_key_utils.py`（git mv 保留历史）
- **MODIFIED** 5 处 `tradingagents/llm_adapters/*.py` import 改 `from tradingagents.utils.api_key_utils import is_valid_api_key`
- **MODIFIED** ~8 处 `app/routers/*.py` import 改 `from tradingagents.utils.api_key_utils import ...`
- **NEW** capability `license-boundary`：定义"Apache 2.0 包不得反向 import 专有授权代码"铁律 + grep 验证 scenario

## Capabilities

### New Capabilities

- `license-boundary`：fork 双轨 license（Apache 2.0 + 专有授权）的 import 方向铁律

## Impact

**改动文件**：1 个文件移动 + 5 个 tradingagents/ + 8 个 app/
**风险**：低——纯 import 路径变更，逻辑未改
**收益**：消除 license 边界跨越（critical 安全/合规缺陷）
