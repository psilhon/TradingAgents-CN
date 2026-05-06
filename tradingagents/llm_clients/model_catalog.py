"""CLI prompts 用的 model catalog。

OpenSpec spec ``llm-abstraction``：MODEL_OPTIONS 现在派生自
``provider_specs.PROVIDER_SPECS``。添加新 provider 改 ProviderSpec 即可。
"""

from __future__ import annotations

from .provider_specs import derive_model_options

ModelOption = tuple[str, str]
ProviderModeOptions = dict[str, dict[str, list[ModelOption]]]


# 从 provider_specs 派生（单一来源）
MODEL_OPTIONS: ProviderModeOptions = derive_model_options()


def get_model_options(provider: str, mode: str) -> list[ModelOption]:
    return MODEL_OPTIONS[provider.lower()][mode]


def get_known_models() -> dict[str, list[str]]:
    return {
        provider: sorted({value for options in mode_options.values() for _, value in options if value != "custom"})
        for provider, mode_options in MODEL_OPTIONS.items()
    }
