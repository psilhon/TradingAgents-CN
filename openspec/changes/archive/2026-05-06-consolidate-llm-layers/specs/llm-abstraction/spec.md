## ADDED Requirements

### Requirement: 单一 LLM 工厂入口

`tradingagents/` 下任何生产代码（agents / graph / dataflows / tools）调用 LLM MUST 通过 `tradingagents.llm_clients.create_llm_client(provider, model, ...)` → `.get_llm()`，**禁止**：

- 直接实例化 `ChatOpenAI` / `ChatAnthropic` / `ChatGoogleGenerativeAI` / `ChatOpenAI` 子类
- 直接 import `tradingagents/llm_adapters/`（已删除）
- 自建 `langchain_*.Chat*` 实例

测试代码 (`tests/`) 与脚本 (`scripts/`) 不在此约束内（允许 mock / 直接实例化用于行为验证）。

#### Scenario: 生产路径 grep 检查

- **WHEN** 在 `tradingagents/{agents,graph,dataflows,tools}/` grep `from langchain_(openai|anthropic|google_genai) import Chat\|^Chat[A-Z]\w+\(`
- **THEN** 命中数 MUST = 0（除测试 mock 用途）

#### Scenario: 添加新 provider

- **WHEN** 开发者要加新 LLM provider
- **THEN** 仅需在 `tradingagents/llm_clients/provider_specs.py` 加 1 个 `ProviderSpec(...)` 实例
- **AND** 4 张 view（`MODEL_OPTIONS` / `env_key_map` / `_PROVIDER_CONFIG` / `_PROVIDER_ALIASES`）自动 derive

### Requirement: 单一 provider 注册表

provider 元信息（canonical key、aliases、env 变量名、默认 base_url、是否 OpenAI 兼容、客户端工厂、模型列表）MUST 在 `tradingagents/llm_clients/provider_specs.py` 的 `ProviderSpec` dataclass 中**单一定义**。

旧的 4 张平行注册表 (`MODEL_OPTIONS` / `_PROVIDER_CONFIG` / `env_key_map` / `OPENAI_COMPATIBLE_PROVIDERS`) MUST 退化为 ProviderSpec 的派生 view（保持向后兼容 import path）或删除。

#### Scenario: ProviderSpec 是单一来源

- **WHEN** 任意模块需要查 provider 元信息
- **THEN** 最终 source 都追溯到 `provider_specs.PROVIDER_SPECS`（dict 或 tuple）
- **AND** 没有"独立维护"的平行 dict / list 含 provider 元数据

### Requirement: LLM adapter 不得伪造业务元数据

LLM 客户端层 (`tradingagents/llm_clients/`) MUST NOT 在 LLM 响应内容上做"业务语义猜测 + 伪造元数据"操作。具体禁止：

- 检测内容是否含"新闻"特征关键词，自动注入"发布时间 / 新闻标题 / 文章来源"等 LLM 未生成的元字段
- 检测内容长度 / 主题，自动添加"来源: 某 AI 智能分析"等数据污染
- 任何让下游 agent 误以为内容含真实来源的"装饰"操作

LLM 客户端只负责：调 model、token 统计、错误处理、内容 normalize（如 typed content blocks → plain text）。**业务理解归 agent 节点**，不归 LLM 客户端。

#### Scenario: google adapter 不再有 _enhance_news_content

- **WHEN** 在 `tradingagents/llm_clients/_google_impl.py` grep `_enhance_news_content\|_is_news_content\|_optimize_message_content\|新闻标题\|文章来源`
- **THEN** 命中数 MUST = 0

#### Scenario: LLM 客户端响应不含伪造字段

- **WHEN** LLM 调用返回 `AIMessage(content="...")`
- **THEN** content 字段值 MUST 与底层 LangChain LLM 类返回的原始内容一致
- **AND** 不出现 client 层未声明的"装饰"或"补全"
