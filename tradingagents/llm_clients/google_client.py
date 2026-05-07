import os
from typing import Any

from .base_client import BaseLLMClient
from .validators import validate_model


class GoogleClient(BaseLLMClient):
    """Client for Google Gemini models."""

    def get_llm(self) -> Any:
        self.warn_if_unknown_model()
        from tradingagents.llm_clients._google_impl import ChatGoogleOpenAI

        llm_kwargs = {"model": self.model}

        if self.base_url:
            llm_kwargs["base_url"] = self.base_url

        for key in ("temperature", "max_tokens", "timeout", "max_retries", "callbacks", "http_client", "http_async_client", "transport"):
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        # API key 优先级：kwargs > GOOGLE_API_KEY env（与 OpenAIClient / AnthropicClient 行为对齐——
        # OpenSpec spec llm-abstraction 要求 3 个 client 行为一致）
        google_api_key = self.kwargs.get("api_key") or self.kwargs.get("google_api_key") or os.environ.get("GOOGLE_API_KEY")
        if google_api_key:
            llm_kwargs["google_api_key"] = google_api_key

        return ChatGoogleOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        return validate_model("google", self.model)
