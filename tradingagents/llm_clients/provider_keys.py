"""Provider key 标准化 + 环境变量 + 默认 URL utility。

OpenSpec spec ``llm-abstraction``：所有 dict 派生自 ``provider_specs.PROVIDER_SPECS``。
添加新 provider 改 ProviderSpec 即可，本文件无需改动。
"""

from __future__ import annotations

from .provider_specs import (
    derive_aliases_map,
    derive_canonical_aliases_map,
    derive_chinese_alias_map,
    derive_default_url_map,
    derive_env_key_map,
)

# 派生 view（向后兼容历史 import name）
_ALIASES = derive_aliases_map()
_CANONICAL_ALIASES = derive_canonical_aliases_map()
_CHINESE_ALIAS_MAP = derive_chinese_alias_map()
_ENV_KEY_MAP = derive_env_key_map()
_DEFAULT_URL_MAP = derive_default_url_map()


def normalize_provider_key(provider: str) -> str:
    if provider is None:
        return ""

    raw = str(provider).strip()
    if not raw:
        return ""

    # 中文子串匹配（如 "阿里百炼大模型" → "qwen"）
    for cn_fragment, canonical in _CHINESE_ALIAS_MAP.items():
        if cn_fragment in raw:
            return canonical

    lowered = raw.lower()
    return _ALIASES.get(lowered, lowered)


def env_key_for_provider(provider: str) -> str:
    key = normalize_provider_key(provider)
    return _ENV_KEY_MAP.get(key, "")


def default_backend_url(provider: str) -> str:
    key = normalize_provider_key(provider)
    return _DEFAULT_URL_MAP.get(key, "https://dashscope.aliyuncs.com/compatible-mode/v1")


def canonical_aliases(provider: str) -> list[str]:
    key = normalize_provider_key(provider)
    return list(_CANONICAL_ALIASES.get(key, []))
