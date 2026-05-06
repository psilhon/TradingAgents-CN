import os
from typing import Any

from langchain_anthropic import ChatAnthropic

from .base_client import BaseLLMClient, normalize_content
from .validators import validate_model


class NormalizedChatAnthropic(ChatAnthropic):
    """Anthropic wrapper that normalizes structured content to text."""

    def invoke(self, input, config=None, **kwargs):
        return normalize_content(super().invoke(input, config, **kwargs))


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic Claude models."""

    def get_llm(self) -> Any:
        self.warn_if_unknown_model()
        llm_kwargs = {"model": self.model}

        if self.base_url:
            llm_kwargs["base_url"] = self.base_url

        for key in ("timeout", "max_retries", "callbacks", "http_client", "http_async_client"):
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        # API key 优先级：kwargs > ANTHROPIC_API_KEY env（与 OpenAIClient 行为对齐——
        # OpenSpec spec llm-abstraction 要求 3 个 client 行为一致）
        api_key = self.kwargs.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            llm_kwargs["api_key"] = api_key

        return NormalizedChatAnthropic(**llm_kwargs)

    def validate_model(self) -> bool:
        return validate_model("anthropic", self.model)
