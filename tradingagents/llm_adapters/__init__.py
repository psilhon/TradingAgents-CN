"""LLM adapters 兼容 shim（OpenSpec change ``consolidate-llm-layers``）。

历史的 4 个适配器文件已删除：
- ``dashscope_openai_adapter.py`` / ``ChatDashScopeOpenAI``
- ``deepseek_adapter.py`` / ``ChatDeepSeek``
- ``openai_compatible_base.py`` / ``ChatDeepSeekOpenAI`` / ``ChatDashScopeOpenAIUnified``
  / ``ChatQianfanOpenAI`` / ``ChatZhipuOpenAI`` / ``ChatCustomOpenAI``
- ``google_openai_adapter.py`` / ``ChatGoogleOpenAI``（已搬到 ``llm_clients/_google_impl.py``）

唯一保留：``ChatGoogleOpenAI`` 通过本 shim 重新导出（向后兼容个别仍引用此路径的测试 / 脚本）。

新代码 SHALL 通过 ``tradingagents.llm_clients.create_llm_client(provider, model, ...)``
统一入口创建 LLM——不再 import ``llm_adapters``。
"""

from tradingagents.llm_clients._google_impl import ChatGoogleOpenAI

__all__ = ["ChatGoogleOpenAI"]
