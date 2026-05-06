from .base_client import BaseLLMClient
from .provider_keys import normalize_provider_key
from .provider_specs import derive_factory_aliases, derive_openai_compatible_set

# 派生自 provider_specs.PROVIDER_SPECS（OpenSpec spec llm-abstraction：单一来源）
_PROVIDER_ALIASES = derive_factory_aliases()
_OPENAI_COMPATIBLE = derive_openai_compatible_set() | {"openai"}  # openai canonical 不在 _PROVIDER_CONFIG 但仍走 OpenAIClient


def create_llm_client(
    provider: str,
    model: str,
    base_url: str | None = None,
    **kwargs,
) -> BaseLLMClient:
    provider_lower = normalize_provider_key(provider)
    provider_lower = _PROVIDER_ALIASES.get(provider_lower, provider_lower)

    if provider_lower in _OPENAI_COMPATIBLE:
        from .openai_client import OpenAIClient

        return OpenAIClient(model, base_url, provider=provider_lower, **kwargs)

    if provider_lower == "google":
        from .google_client import GoogleClient

        return GoogleClient(model, base_url, **kwargs)

    if provider_lower == "anthropic":
        from .anthropic_client import AnthropicClient

        return AnthropicClient(model, base_url, **kwargs)

    raise ValueError(f"Unsupported LLM provider: {provider}")
