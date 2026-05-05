## Why

`docs/code-review-2026-05-05.md` 多处发现 API key **前缀**直接打印到 log / Rich 表格，违反全局 CLAUDE.md secret 边界（"输出日志 / 配置 / 错误信息时必须脱敏"）：

- `tradingagents/config/config_manager.py:118,647` — `{api_key[:10]}...`
- `tradingagents/llm_adapters/dashscope_openai_adapter.py:62` — `前10位: {env_api_key[:10]}`
- `tradingagents/llm_adapters/openai_compatible_base.py:101` — `前10位: {env_api_key[:10]}`
- `tradingagents/llm_adapters/google_openai_adapter.py:79` — `前10位: {env_api_key[:10]}`
- `cli/main.py:1546-1566` — 5 处 Rich 表格显示 `{key[:12]}...`

OpenAI key 是 `sk-` + 48 字符，前 10-12 位泄露 7+ 个有效熵字符，显著降低暴破搜索空间。`truncate_api_key()`（已存在）显示前6后6 共 12 字符——也偏多。

## What Changes

- **MODIFIED** `tradingagents/utils/api_key_utils.py`：新增 `redact_api_key(key)` helper，仅返回 `(len=N, ends ...XXXX)` 或 `(missing)`，**不暴露任何前缀**
- **MODIFIED** 5 处 tradingagents/ 日志：`{key[:10]}...` → `redact_api_key(key)`
- **MODIFIED** 5 处 `cli/main.py` Rich 表格：`{key[:12]}...` → `redact_api_key(key)`
- **NEW** capability `secret-handling`：定义 secret 在 log / 显示中的脱敏铁律

## Capabilities

### New Capabilities

- `secret-handling`：禁止 log / 显示 API key 前缀

## Impact

**改动文件**：1 个 utility 增 + 5 个 tradingagents/ + 1 个 cli/
**风险**：低
**收益**：消除 API key 前缀泄露（可被 attacker 用作暴破搜索空间缩小依据）
