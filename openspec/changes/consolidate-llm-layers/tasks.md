## 1. OpenSpec scaffolding — commit 1

- [x] 1.1 创建 change 目录 + proposal/tasks/spec
- [x] 1.2 `openspec validate` 通过
- [x] 1.3 commit

## 2. 移 ChatGoogleOpenAI + 删 _enhance_news_content — commit 2

- [x] 2.1 创建 `tradingagents/llm_clients/_google_impl.py`
- [x] 2.2 删 `_enhance_news_content` / `_is_news_content` / `_optimize_message_content` 三件套
- [x] 2.3 改 `google_client.py:12` import 路径 `_google_impl`
- [x] 2.4 `google_tool_handler.py:25` 字符串比较 "ChatGoogleOpenAI" 保留（新类同名）
- [x] 2.5 ruff + pyright 0 errors
- [x] 2.6 pytest -m unit 仍 12 pass
- [x] 2.7 commit

## 3. ProviderSpec dataclass 单一来源 — commit 3

- [x] 3.1 创建 `tradingagents/llm_clients/provider_specs.py`：12 个 ProviderSpec 实例 + 7 个派生函数
- [x] 3.2 `model_catalog.MODEL_OPTIONS` ← `derive_model_options()`
- [x] 3.3 `provider_keys.{_ALIASES, env_key, default_url, canonical_aliases}` ← derive_*
- [x] 3.4 `openai_client._PROVIDER_CONFIG` ← `derive_openai_provider_config()`
- [x] 3.5 `factory.{_PROVIDER_ALIASES, _OPENAI_COMPATIBLE}` ← derive_*
- [x] 3.6 ruff + pyright 0 errors
- [x] 3.7 14 路 provider routing 全正确
- [x] 3.8 commit

## 4. 修 4 个 bug — commit 4

- [x] 4.1 `factory._PROVIDER_ALIASES` 删 siliconflow→openai alias，独立路由
- [x] 4.2 `anthropic_client.get_llm` 读 ANTHROPIC_API_KEY env
- [x] 4.3 `google_client.get_llm` 读 GOOGLE_API_KEY env
- [x] 4.4 `trading_graph.py:118` anthropic 分支改走 create_llm_client
- [x] 4.5 `trading_graph.py:148` custom fallback 分支改走 create_llm_client
- [x] 4.6 verify：siliconflow 现用正确 base_url + AnthropicClient 自动拾取 env
- [x] 4.7 commit

## 5. Token tracker callback — SKIPPED

实施途中发现：production 实际只用 1 处 `_track_token_usage`（Google）。其它 3 处都在 Chain A 死代码中，commit 6 删 Chain A 后 "3 处重复" 自动消失。加 callback 反而是给 OpenAIClient 加新功能（之前 deepseek/qwen 等没 token tracking）—— 应作 follow-up 独立 change。

经用户确认（"yes"）跳过此 commit。

## 6. 删 Chain A llm_adapters/ — commit 6

- [x] 6.1 grep 验证生产路径无引用（仅 `_google_impl` 替代后的 ChatGoogleOpenAI）
- [x] 6.2 `git rm` 4 个适配器文件（dashscope_openai_adapter / deepseek_adapter / openai_compatible_base / google_openai_adapter）共 1498 行
- [x] 6.3 `llm_adapters/__init__.py` 改 shim：仅 re-export ChatGoogleOpenAI 从 `_google_impl`
- [x] 6.4 25 个 tests/ 文件（import 已删类）git mv 到 tests/_legacy/
- [x] 6.5 9 个 scripts/ 文件 git mv 到 scripts/_legacy/
- [x] 6.6 pyproject.toml ruff/pyright exclude 加 tests/_legacy + scripts/_legacy
- [x] 6.7 ruff + pyright 0 errors
- [x] 6.8 pytest -m unit 12 pass
- [x] 6.9 commit

## 7. 收口 — commit 7

- [x] 7.1 docs/CHANGELOG.md `### Changed` 条目
- [x] 7.2 archive change → `openspec/specs/llm-abstraction/spec.md`
- [x] 7.3 commit
