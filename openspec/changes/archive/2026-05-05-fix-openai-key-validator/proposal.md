## Why

`docs/code-review-2026-05-05.md` Tier 2 第 5 条：`tradingagents/config/config_manager.py:157` OpenAI key 长度硬等于 **51**。

OpenAI 早已发布 `sk-proj-` 前缀的项目级 key + `sk-svcacct-` 服务账号 key，长度远超 51 字符且含连字符 / 下划线。该 validator 把所有新格式 key 判为无效（line 161 pattern `^sk-[A-Za-z0-9]{48}$` 也不允许 `-` / `_`），到 `load_models:288` 直接 disable 模型——**用户配了正确的 sk-proj- key 也无法启用**。

## What Changes

- **MODIFIED** `tradingagents/config/config_manager.py:134-163` `validate_openai_api_key_format`：
  - 删除硬编码 `len == 51` 检查
  - 改 pattern 为 `^sk-[A-Za-z0-9_-]{32,}$`（接受 sk-、sk-proj-、sk-svcacct- 等所有现行格式）
  - 注释说明历史经典 key 是 51 字符 sk-[48] 格式，新 project key 更长且含 `-_`

无 BREAKING change（更宽松，原本 valid 的 key 仍 valid）。

## Capabilities

### Modified Capabilities

- `secret-handling`：在已有 spec 加 requirement "API key 校验器接受供应商当前所有合法格式"

## Impact

**改动文件**：1 个 Python 文件
**风险**：低——validator 放宽不会引入安全风险（只是接受更多合法 key）
**收益**：用户配 `sk-proj-` 或 `sk-svcacct-` key 不再被错误拒绝
