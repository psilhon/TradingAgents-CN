import os
from collections.abc import Mapping
from typing import Any

from langchain_openai import ChatOpenAI

from .base_client import BaseLLMClient, normalize_content
from .provider_specs import derive_openai_provider_config
from .validators import validate_model


class NormalizedChatOpenAI(ChatOpenAI):
    """ChatOpenAI wrapper that normalizes typed content blocks to text."""

    def invoke(self, input, config=None, **kwargs):
        return normalize_content(super().invoke(input, config, **kwargs))


_PASSTHROUGH_KWARGS = (
    "temperature",
    "max_tokens",
    "timeout",
    "max_retries",
    "callbacks",
    "http_client",
    "http_async_client",
    "extra_body",
)

# 派生自 provider_specs.PROVIDER_SPECS（OpenSpec spec llm-abstraction：单一来源）
_PROVIDER_CONFIG = derive_openai_provider_config()

_DEEPSEEK_EXTRA_BODY_DEFAULTS = {"thinking": {"type": "disabled"}}


def _merge_extra_body_defaults(
    extra_body: Any,
    defaults: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(extra_body) if isinstance(extra_body, Mapping) else {}

    for key, value in defaults.items():
        merged.setdefault(key, value)

    return merged


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI and OpenAI-compatible providers."""

    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        provider: str = "openai",
        **kwargs,
    ):
        super().__init__(model, base_url, **kwargs)
        self.provider = provider.lower()

    def get_llm(self) -> Any:
        self.warn_if_unknown_model()
        llm_kwargs = {"model": self.model}

        if self.provider in _PROVIDER_CONFIG:
            default_base_url, api_key_env = _PROVIDER_CONFIG[self.provider]
            llm_kwargs["base_url"] = self.base_url or default_base_url
            if api_key_env:
                api_key = self.kwargs.get("api_key") or os.environ.get(api_key_env)
                if api_key:
                    llm_kwargs["api_key"] = api_key
            else:
                llm_kwargs["api_key"] = "ollama"
        elif self.base_url:
            llm_kwargs["base_url"] = self.base_url
            api_key = self.kwargs.get("api_key") or os.environ.get("OPENAI_API_KEY")
            if api_key:
                llm_kwargs["api_key"] = api_key

        for key in _PASSTHROUGH_KWARGS:
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        if self.provider == "deepseek":
            llm_kwargs["extra_body"] = _merge_extra_body_defaults(
                llm_kwargs.get("extra_body"),
                _DEEPSEEK_EXTRA_BODY_DEFAULTS,
            )

        return NormalizedChatOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        return validate_model(self.provider, self.model)
