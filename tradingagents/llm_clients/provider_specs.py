"""LLM provider 单一来源（OpenSpec spec: llm-abstraction）。

所有 provider 元信息（canonical key、aliases、env 变量名、默认 base_url、
是否 OpenAI 兼容、客户端类型、模型列表）在本模块的 ``PROVIDER_SPECS`` 中
**单一定义**。

历史的 4 张平行注册表（``model_catalog.MODEL_OPTIONS`` / ``provider_keys.env_key_map``
/ ``openai_client._PROVIDER_CONFIG`` / ``factory._PROVIDER_ALIASES``）现在
全部由本文件 derive，保持向后兼容 import path。

添加新 provider 的步骤简化为：在 ``PROVIDER_SPECS`` 列表中加 1 个
``ProviderSpec(...)`` 实例，4 张 view 自动同步。
"""

from __future__ import annotations

from dataclasses import dataclass, field

ModelOption = tuple[str, str]


@dataclass(frozen=True)
class ProviderSpec:
    """单个 LLM provider 的全部元信息。"""

    canonical_key: str
    """规范化键（如 "qwen", "glm", "openai"）—— factory / config 路由用此键。"""

    aliases: tuple[str, ...] = ()
    """英文别名（如 qwen 的 ("dashscope", "alibaba")）。"""

    chinese_aliases: tuple[str, ...] = ()
    """中文别名（如 qwen 的 ("阿里百炼", "百炼")）—— ``normalize_provider_key`` 子串匹配用。"""

    env_key: str = ""
    """API key 环境变量名（如 "DASHSCOPE_API_KEY"）。空字符串表示该 provider 不需要 env key（如 ollama）。"""

    default_base_url: str | None = None
    """默认 endpoint URL。``None`` 表示无默认（如 custom_openai 必须 caller 传）。"""

    openai_compatible: bool = False
    """是否走 ``OpenAIClient``（OpenAI 兼容协议 = 走 chat.completions endpoint）。"""

    client_kind: str = "openai"
    """客户端类型：``"openai"`` / ``"google"`` / ``"anthropic"`` —— ``factory.create_llm_client`` 路由用。"""

    models_quick: tuple[ModelOption, ...] = field(default_factory=tuple)
    """quick 模式（fast 模型）的候选列表，CLI 选择用。"""

    models_deep: tuple[ModelOption, ...] = field(default_factory=tuple)
    """deep 模式（reasoning 模型）的候选列表。"""


# 单一来源——所有 provider 元信息从此 list 派生
PROVIDER_SPECS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        canonical_key="openai",
        env_key="OPENAI_API_KEY",
        default_base_url="https://api.openai.com/v1",
        openai_compatible=False,  # ⚠️ openai 自身不在 _PROVIDER_CONFIG 中（caller-supplied base_url 兜底逻辑）
        client_kind="openai",
        models_quick=(
            ("GPT-4o Mini - Fast and cost-effective", "gpt-4o-mini"),
            ("GPT-4.1 Mini - Compact, capable", "gpt-4.1-mini"),
            ("GPT-4.1 Nano - Lightweight", "gpt-4.1-nano"),
            ("Custom model ID", "custom"),
        ),
        models_deep=(
            ("o4-mini - Reasoning focused", "o4-mini"),
            ("o3-mini - Advanced reasoning", "o3-mini"),
            ("GPT-4o - Balanced general model", "gpt-4o"),
            ("Custom model ID", "custom"),
        ),
    ),
    ProviderSpec(
        canonical_key="anthropic",
        env_key="ANTHROPIC_API_KEY",
        default_base_url="https://api.anthropic.com",
        openai_compatible=False,
        client_kind="anthropic",
        models_quick=(
            ("Claude Haiku 3.5 - Fast responses", "claude-3-5-haiku-latest"),
            ("Claude Sonnet 3.5 - Balanced", "claude-3-5-sonnet-latest"),
            ("Claude Sonnet 3.7 - Strong reasoning", "claude-3-7-sonnet-latest"),
            ("Custom model ID", "custom"),
        ),
        models_deep=(
            ("Claude Sonnet 3.7 - Strong reasoning", "claude-3-7-sonnet-latest"),
            ("Claude Sonnet 4 - High performance", "claude-sonnet-4-0"),
            ("Claude Opus 4 - Max capability", "claude-opus-4-0"),
            ("Custom model ID", "custom"),
        ),
    ),
    ProviderSpec(
        canonical_key="google",
        env_key="GOOGLE_API_KEY",
        default_base_url="https://generativelanguage.googleapis.com/v1beta",
        openai_compatible=False,
        client_kind="google",
        models_quick=(
            ("Gemini 2.5 Flash - Fast", "gemini-2.5-flash"),
            ("Gemini 2.5 Flash Lite - Low cost", "gemini-2.5-flash-lite"),
            ("Gemini 2.0 Flash - Stable", "gemini-2.0-flash"),
            ("Custom model ID", "custom"),
        ),
        models_deep=(
            ("Gemini 2.5 Pro - Strong reasoning", "gemini-2.5-pro"),
            ("Gemini 2.5 Pro-002 - Updated", "gemini-2.5-pro-002"),
            ("Gemini 1.5 Pro - Compatibility fallback", "gemini-1.5-pro"),
            ("Custom model ID", "custom"),
        ),
    ),
    ProviderSpec(
        canonical_key="deepseek",
        env_key="DEEPSEEK_API_KEY",
        default_base_url="https://api.deepseek.com",
        openai_compatible=True,
        client_kind="openai",
        models_quick=(
            ("DeepSeek Chat", "deepseek-chat"),
            ("Custom model ID", "custom"),
        ),
        models_deep=(
            ("DeepSeek Chat", "deepseek-chat"),
            ("DeepSeek Reasoner", "deepseek-reasoner"),
            ("Custom model ID", "custom"),
        ),
    ),
    ProviderSpec(
        canonical_key="qwen",
        aliases=("dashscope", "alibaba"),
        chinese_aliases=("阿里百炼", "百炼"),
        env_key="DASHSCOPE_API_KEY",
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        openai_compatible=True,
        client_kind="openai",
        models_quick=(
            ("Qwen Turbo - Fast", "qwen-turbo"),
            ("Qwen Plus - Balanced", "qwen-plus"),
            ("Custom model ID", "custom"),
        ),
        models_deep=(
            ("Qwen Max - High capability", "qwen-max"),
            ("Qwen Max LongContext - Long context", "qwen-max-longcontext"),
            ("Qwen Plus - Balanced", "qwen-plus"),
            ("Custom model ID", "custom"),
        ),
    ),
    ProviderSpec(
        canonical_key="glm",
        aliases=("zhipu",),
        chinese_aliases=("智谱", "智谱ai"),
        env_key="ZHIPU_API_KEY",
        default_base_url="https://open.bigmodel.cn/api/paas/v4/",
        openai_compatible=True,
        client_kind="openai",
        models_quick=(
            ("GLM-4-Flash", "glm-4-flash"),
            ("GLM-4-Air", "glm-4-air"),
            ("Custom model ID", "custom"),
        ),
        models_deep=(
            ("GLM-4-Plus", "glm-4-plus"),
            ("GLM-4-Long", "glm-4-long"),
            ("Custom model ID", "custom"),
        ),
    ),
    ProviderSpec(
        canonical_key="qianfan",
        env_key="QIANFAN_API_KEY",
        default_base_url="https://qianfan.baidubce.com/v2",
        openai_compatible=True,
        client_kind="openai",
        # 千帆历史无 MODEL_OPTIONS 入口，CLI 不展示但 factory 可路由
    ),
    ProviderSpec(
        canonical_key="openrouter",
        env_key="OPENROUTER_API_KEY",
        default_base_url="https://openrouter.ai/api/v1",
        openai_compatible=True,
        client_kind="openai",
        models_quick=(("Custom model ID", "custom"),),
        models_deep=(("Custom model ID", "custom"),),
    ),
    ProviderSpec(
        canonical_key="aihubmix",
        env_key="AIHUBMIX_API_KEY",
        default_base_url="https://aihubmix.com/v1",
        openai_compatible=True,
        client_kind="openai",
        models_quick=(
            ("GPT-4o Mini", "gpt-4o-mini"),
            ("Custom model ID", "custom"),
        ),
        models_deep=(
            ("GPT-4o", "gpt-4o"),
            ("Custom model ID", "custom"),
        ),
    ),
    ProviderSpec(
        canonical_key="ollama",
        env_key="",  # ollama 本地无需 API key
        default_base_url="http://localhost:11434/v1",
        openai_compatible=True,
        client_kind="openai",
        models_quick=(
            ("llama3.1", "llama3.1"),
            ("qwen3", "qwen3"),
            ("Custom model ID", "custom"),
        ),
        models_deep=(
            ("qwen3", "qwen3"),
            ("llama3.1", "llama3.1"),
            ("Custom model ID", "custom"),
        ),
    ),
    ProviderSpec(
        canonical_key="custom_openai",
        env_key="CUSTOM_OPENAI_API_KEY",
        default_base_url=None,  # 必须 caller 传
        openai_compatible=True,
        client_kind="openai",
        models_quick=(
            ("GPT-4o Mini", "gpt-4o-mini"),
            ("GPT-4o", "gpt-4o"),
            ("Custom model ID", "custom"),
        ),
        models_deep=(
            ("GPT-4o", "gpt-4o"),
            ("o1", "o1"),
            ("Custom model ID", "custom"),
        ),
    ),
    ProviderSpec(
        canonical_key="siliconflow",
        env_key="SILICONFLOW_API_KEY",
        default_base_url="https://api.siliconflow.cn/v1",
        openai_compatible=True,
        client_kind="openai",
        # ⚠️ commit 4 修 alias bug：本 commit 仍由 factory alias 到 openai，
        # commit 4 删除该 alias 让 factory 走 openai_compatible 分支并用上 default_base_url
    ),
)


# === 派生 view（保持历史 import path 向后兼容）===

# 索引：canonical_key → ProviderSpec
_BY_CANONICAL: dict[str, ProviderSpec] = {s.canonical_key: s for s in PROVIDER_SPECS}


def get_spec(canonical_key: str) -> ProviderSpec | None:
    """按 canonical key 取 spec（None 如果不存在）。"""
    return _BY_CANONICAL.get(canonical_key)


def all_canonical_keys() -> tuple[str, ...]:
    """返回所有 canonical key tuple。"""
    return tuple(s.canonical_key for s in PROVIDER_SPECS)


def derive_aliases_map() -> dict[str, str]:
    """派生 ``provider_keys._ALIASES``（alias → canonical）。

    包含：每个 spec 的 canonical key 自映射 + 所有英文 alias → canonical。
    中文 alias 由 ``normalize_provider_key`` 的子串匹配单独处理（不在此 dict 中）。
    """
    out: dict[str, str] = {}
    for spec in PROVIDER_SPECS:
        out[spec.canonical_key] = spec.canonical_key
        for alias in spec.aliases:
            out[alias] = spec.canonical_key
    return out


def derive_chinese_alias_map() -> dict[str, str]:
    """派生 ``normalize_provider_key`` 中文子串匹配 dict（中文片段 → canonical）。

    例如 ``{"阿里百炼": "qwen", "百炼": "qwen", "智谱": "glm"}``。
    """
    out: dict[str, str] = {}
    for spec in PROVIDER_SPECS:
        for cn in spec.chinese_aliases:
            out[cn] = spec.canonical_key
    return out


def derive_canonical_aliases_map() -> dict[str, list[str]]:
    """派生 ``provider_keys._CANONICAL_ALIASES``（canonical → [所有显示用 alias]）。"""
    out: dict[str, list[str]] = {}
    for spec in PROVIDER_SPECS:
        all_aliases = list(spec.aliases) + list(spec.chinese_aliases)
        if all_aliases:
            out[spec.canonical_key] = all_aliases
    return out


def derive_env_key_map() -> dict[str, str]:
    """派生 ``provider_keys.env_key_for_provider`` 的内部 map。"""
    return {s.canonical_key: s.env_key for s in PROVIDER_SPECS if s.env_key}


def derive_default_url_map() -> dict[str, str]:
    """派生 ``provider_keys.default_backend_url`` 的内部 map。"""
    return {s.canonical_key: s.default_base_url for s in PROVIDER_SPECS if s.default_base_url}


def derive_openai_compatible_set() -> set[str]:
    """派生 ``factory._OPENAI_COMPATIBLE``。"""
    return {s.canonical_key for s in PROVIDER_SPECS if s.openai_compatible}


def derive_openai_provider_config() -> dict[str, tuple[str | None, str | None]]:
    """派生 ``openai_client._PROVIDER_CONFIG`` —— openai-compatible providers 的 (base_url, env_key) 元组。

    注意：``openai`` canonical 自身**不**在结果中（与历史一致——OpenAIClient 对 "openai"
    走 caller-supplied base_url + OPENAI_API_KEY env 兜底分支）。
    """
    out: dict[str, tuple[str | None, str | None]] = {}
    for spec in PROVIDER_SPECS:
        if spec.openai_compatible and spec.canonical_key != "openai":
            env = spec.env_key if spec.env_key else None
            out[spec.canonical_key] = (spec.default_base_url, env)
    return out


def derive_factory_aliases() -> dict[str, str]:
    """派生 ``factory._PROVIDER_ALIASES`` —— factory 层 alias → canonical 映射。

    历史 ``"siliconflow": "openai"`` 是 bug——caller 不传 base_url 时打到
    api.openai.com（虽然 trading_graph 总传 backend_url 静默掩盖）。
    现已修：siliconflow 作为独立 canonical 路由（用 SILICONFLOW_API_KEY +
    siliconflow 默认 base_url），见 provider_specs PROVIDER_SPECS。
    """
    out: dict[str, str] = {}
    for spec in PROVIDER_SPECS:
        for alias in spec.aliases:
            out[alias] = spec.canonical_key
    return out


def derive_model_options() -> dict[str, dict[str, list[ModelOption]]]:
    """派生 ``model_catalog.MODEL_OPTIONS``。

    仅含有 quick / deep 模型列表的 spec 入选（千帆等无 CLI model 选项的 spec 排除）。
    """
    out: dict[str, dict[str, list[ModelOption]]] = {}
    for spec in PROVIDER_SPECS:
        if spec.models_quick or spec.models_deep:
            out[spec.canonical_key] = {
                "quick": list(spec.models_quick),
                "deep": list(spec.models_deep),
            }
    return out
