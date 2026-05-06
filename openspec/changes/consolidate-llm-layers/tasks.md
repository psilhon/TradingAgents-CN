## 1. OpenSpec scaffolding — commit 1

- [ ] 1.1 创建 change 目录 + proposal/tasks/spec
- [ ] 1.2 `openspec validate` 通过
- [ ] 1.3 commit

## 2. 移 ChatGoogleOpenAI + 删 _enhance_news_content — commit 2

- [ ] 2.1 创建 `tradingagents/llm_clients/_google_impl.py`，复制 `google_openai_adapter.py` 内容
- [ ] 2.2 删 `_enhance_news_content` / `_is_news_content` / `_optimize_message_content` 三件套（~50 行）
- [ ] 2.3 改 `tradingagents/llm_clients/google_client.py:12` import 路径 `_google_impl`
- [ ] 2.4 改 `tradingagents/agents/utils/google_tool_handler.py:25` 字符串比较新名（如保留 ChatGoogleOpenAI）
- [ ] 2.5 ruff + pyright 0 errors
- [ ] 2.6 pytest -m unit 仍 12 pass
- [ ] 2.7 smoke：调 google llm 一次确认正常返回
- [ ] 2.8 commit

## 3. ProviderSpec dataclass 单一来源 — commit 3

- [ ] 3.1 创建 `tradingagents/llm_clients/provider_specs.py`：`ProviderSpec` dataclass + 11 个 provider 实例 + 派生 view 函数
- [ ] 3.2 改 `model_catalog.py` `MODEL_OPTIONS` 派生自 `provider_specs`
- [ ] 3.3 改 `provider_keys.py` `env_key_map` / `default_urls` / `_ALIASES` 派生
- [ ] 3.4 改 `openai_client.py` `_PROVIDER_CONFIG` 派生
- [ ] 3.5 改 `factory.py` `_PROVIDER_ALIASES` / `_OPENAI_COMPATIBLE` 派生
- [ ] 3.6 ruff + pyright 0 errors
- [ ] 3.7 pytest -m unit 仍 12 pass（含 test_provider_keys / test_normalize_provider_keys_script）
- [ ] 3.8 smoke：trading_graph.py 11 个 provider 分支选 1 个跑端到端
- [ ] 3.9 commit

## 4. 修 4 个 bug — commit 4

- [ ] 4.1 `factory.py`：siliconflow 加 canonical 条目（不 alias 到 openai）
- [ ] 4.2 `anthropic_client.py:get_llm`：读 `ANTHROPIC_API_KEY` env（与 OpenAIClient 对齐）
- [ ] 4.3 `google_client.py:get_llm`：读 `GOOGLE_API_KEY` env
- [ ] 4.4 `trading_graph.py:118`：anthropic 分支改走 `create_llm_client`
- [ ] 4.5 `trading_graph.py:148`：custom fallback 分支改走 `create_llm_client`
- [ ] 4.6 ruff + pyright 0 errors + pytest 12 pass
- [ ] 4.7 commit

## 5. Token tracker callback handler — commit 5

- [ ] 5.1 创建 `tradingagents/llm_clients/token_callback.py`：`LangChainTokenCallback(BaseCallbackHandler)` 实现 `on_llm_end`
- [ ] 5.2 `BaseLLMClient.get_llm()` attach callback（透传 callbacks kwargs）
- [ ] 5.3 删除 `OpenAICompatibleBase._track_token_usage`、`ChatDashScopeOpenAI._generate` 中的 token 写入、`ChatDeepSeek._generate` 同（这些类下个 commit 整体删除）
- [ ] 5.4 验证 mongodb `token_usage` collection 写入字段对等（vs 老路径）
- [ ] 5.5 ruff + pyright 0 errors + pytest 12 pass
- [ ] 5.6 commit

## 6. 删 Chain A llm_adapters/ — commit 6

- [ ] 6.1 grep 确认 `tradingagents/llm_adapters/{dashscope_openai_adapter,deepseek_adapter,openai_compatible_base,google_openai_adapter}.py` 在生产路径无引用（_google_impl 已替代）
- [ ] 6.2 `git rm` 4 个文件
- [ ] 6.3 改 `llm_adapters/__init__.py`：清 export 或整个删除目录
- [ ] 6.4 改 `tests/` 顶层活跃 test 的 import（_legacy/ 不在 CI 跑可后处理）
- [ ] 6.5 改 `scripts/` 中的 import（如有）
- [ ] 6.6 ruff + pyright 0 errors
- [ ] 6.7 pytest -m unit 仍 12 pass
- [ ] 6.8 backend 重启 + smoke /api/health
- [ ] 6.9 commit

## 7. 收口 — commit 7

- [ ] 7.1 docs/CHANGELOG.md `### Changed` 条目
- [ ] 7.2 archive change → `openspec/specs/llm-abstraction/spec.md`
- [ ] 7.3 commit
