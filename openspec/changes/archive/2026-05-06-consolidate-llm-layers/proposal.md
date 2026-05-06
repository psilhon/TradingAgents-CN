## Why

`docs/code-review-2026-05-05.md` 第三梯队 #1+#2 合并：

**问题 1：两条独立 LLM 工厂链并存**
- `tradingagents/llm_adapters/`（继承 `ChatOpenAI` / `ChatGoogleGenerativeAI`，含 token tracker）
- `tradingagents/llm_clients/`（包装 LangChain，含 model 校验 + factory）

深度探查发现：**Chain A 在生产路径仅 1 次实例化**（B 反向 import `ChatGoogleOpenAI`），其余 ~50 次都在 `tests/_legacy/`（已归档）+ `scripts/`。Chain B 才是真正生产路径——`trading_graph.py:30` `create_llm_by_provider` 是唯一 LLM 入口，11 个 provider 分支全走 `create_llm_client`。`OPENAI_COMPATIBLE_PROVIDERS` + `create_openai_compatible_llm` 在生产**零引用**。

**问题 2：4 份 provider 注册表**
- `model_catalog.MODEL_OPTIONS` — provider → 模型列表
- `provider_keys.{env_key_map, default_urls, _ALIASES}` — env / url / alias
- `openai_client._PROVIDER_CONFIG` — endpoint 配置
- `openai_compatible_base.OPENAI_COMPATIBLE_PROVIDERS` — 兼容性元 + 模型列表

字段命名分歧严重；同一 provider 在不同表里键名不一致（dashscope ↔ qwen / zhipu ↔ glm）；模型列表两份不一致。**添加新供应商需同步至少 4 处**。

**伴生 bug**：
- `siliconflow → openai` alias 不传 base_url 时打到 `api.openai.com`（trading_graph 总传 backend_url 静默掩盖）
- `google_openai_adapter._enhance_news_content` 在 LLM 层伪造新闻来源元信息（leaky abstraction + 数据污染）
- `AnthropicClient` / `GoogleClient` 不读 env（`OpenAIClient` 读）—— 3 client 行为不一致
- `trading_graph.py:118,148` anthropic + custom 分支**绕开** `create_llm_client` 直接实例化
- 3-4 处 `_track_token_usage` 重复实现

## What Changes

- **NEW** `tradingagents/llm_clients/provider_specs.py`：`ProviderSpec` dataclass 作为 4 表单一来源
- **NEW** `tradingagents/llm_clients/_google_impl.py`：从 `llm_adapters/google_openai_adapter.py` 搬入，删 `_enhance_news_content` / `_is_news_content` / `_optimize_message_content` 三件套
- **NEW** `tradingagents/llm_clients/token_callback.py`：抽 token tracker 为 `LangChainTokenCallback`
- **MODIFIED** `tradingagents/llm_clients/factory.py`：siliconflow 加 canonical 条目（不 alias）
- **MODIFIED** `tradingagents/llm_clients/{anthropic_client,google_client}.py`：`get_llm` 读 env（与 OpenAIClient 对齐）
- **MODIFIED** `tradingagents/graph/trading_graph.py`：anthropic + custom 分支改走 `create_llm_client`
- **REMOVED** `tradingagents/llm_adapters/{dashscope_openai_adapter,deepseek_adapter,openai_compatible_base,google_openai_adapter}.py`（共 ~1500 行；Google 已搬到 _google_impl.py）
- **MODIFIED** `tradingagents/llm_adapters/__init__.py`：删 export
- **MODIFIED** `tests/` + `scripts/` ~50 处 import 改路径（绝大多数在 `tests/_legacy/`）

- **NEW** capability `llm-abstraction`：定义 LLM 抽象层铁律
  - 单一工厂入口 `create_llm_client`
  - 单一 provider 注册表 `ProviderSpec`
  - LLM adapter 不得伪造业务元数据

## Capabilities

### New Capabilities

- `llm-abstraction`：LLM 抽象层单一入口 + 单一注册表 + 不得伪造业务元数据

## Impact

**改动文件**：~20 个文件（4 删除 + 3 新建 + 5 修改 tradingagents/ + ~50 tests/scripts import）
**风险**：中——token tracker 改 callback 需验证计数对等；google `_optimize_message_content` 删除前需端到端测一次
**收益**：
- 消除 leaky abstraction（`_enhance_news_content` 数据污染）
- 修复 siliconflow base_url bug
- 添加新供应商：4 处 → 1 个 `ProviderSpec`
- ~1500 行死代码删除
