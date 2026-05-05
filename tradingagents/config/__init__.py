"""
配置管理模块

⚠️ ConfigManager 已废弃（见 config_manager.py 模块顶部注释）。
保留 lazy re-export 供历史代码继续 work——module import 不触发 ConfigManager 初始化。
"""

from .config_manager import ModelConfig, PricingConfig, UsageRecord  # 类定义无副作用，可立即 export

__all__ = ["ModelConfig", "PricingConfig", "UsageRecord", "config_manager", "token_tracker"]


def __getattr__(name: str):  # PEP 562 lazy re-export
    if name in ("config_manager", "token_tracker"):
        from . import config_manager as _cm_module

        return getattr(_cm_module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
