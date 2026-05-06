"""
Google AI (Gemini) LLM 客户端实现 — `llm_clients/` 内部模块。

由 `tradingagents/llm_adapters/google_openai_adapter.py` 搬入（OpenSpec change
`consolidate-llm-layers`）。继承 `ChatGoogleGenerativeAI`（不是 ChatOpenAI）—
原 ChatOpenAI 兼容路径不适用。

**已删除** `_enhance_news_content` / `_is_news_content` / `_optimize_message_content`
三件套（leaky abstraction + 数据污染——LLM 层不应根据中文关键词猜内容是新闻并
伪造 "发布时间 / 新闻标题 / 文章来源: Google AI 智能分析" 等元字段）。
OpenSpec spec: `llm-abstraction` "LLM adapter 不得伪造业务元数据"。
"""

import os
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import LLMResult
from langchain_google_genai import ChatGoogleGenerativeAI

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")


class ChatGoogleOpenAI(ChatGoogleGenerativeAI):
    """Google AI 客户端封装。

    继承 `ChatGoogleGenerativeAI`，提供：
    - kwargs 优先 + GOOGLE_API_KEY env 兜底的 API key 解析
    - 自定义 `base_url`（中转地址 / 官方域名自动识别）的 `client_options.api_endpoint` 透传
    - token 使用追踪（`config_manager.token_tracker`）
    - 失败时返回带友好提示的 LLMResult（避免 caller 崩）
    """

    def __init__(self, base_url: str | None = None, **kwargs):
        logger.info("🔍 [Google初始化] 开始初始化 ChatGoogleOpenAI")
        logger.info(f"🔍 [Google初始化] kwargs 中是否包含 google_api_key: {'google_api_key' in kwargs}")
        logger.info(f"🔍 [Google初始化] 传入的 base_url: {base_url}")

        kwargs.setdefault("temperature", 0.1)
        kwargs.setdefault("max_tokens", 2000)

        google_api_key = kwargs.get("google_api_key")
        if not google_api_key:
            from tradingagents.utils.api_key_utils import is_valid_api_key, redact_api_key

            env_api_key = os.getenv("GOOGLE_API_KEY")
            logger.info(f"🔍 [Google初始化] 从环境变量读取 GOOGLE_API_KEY: {'有值' if env_api_key else '空'}")

            if env_api_key and is_valid_api_key(env_api_key):
                logger.info(f"✅ [Google初始化] 环境变量中的 API Key 有效 {redact_api_key(env_api_key)}")
                google_api_key = env_api_key
            elif env_api_key:
                logger.warning("⚠️ [Google初始化] 环境变量中的 API Key 无效（可能是占位符），将被忽略")
                google_api_key = None
            else:
                logger.warning("⚠️ [Google初始化] GOOGLE_API_KEY 环境变量为空")
                google_api_key = None
        else:
            logger.info("✅ [Google初始化] 使用 kwargs 中传入的 API Key（来自数据库配置）")

        if not google_api_key:
            raise ValueError(
                "Google API key not found. Please configure API key in web interface "
                "(Settings -> LLM Providers) or set GOOGLE_API_KEY environment variable."
            )

        kwargs["google_api_key"] = google_api_key

        if base_url:
            base_url = base_url.rstrip("/")
            is_google_official = "generativelanguage.googleapis.com" in base_url

            if is_google_official:
                # 官方域名：提取域名部分，SDK 自动添加 /v1beta
                if base_url.endswith("/v1beta"):
                    api_endpoint = base_url[:-7]
                elif base_url.endswith("/v1"):
                    api_endpoint = base_url[:-3]
                else:
                    api_endpoint = base_url
            else:
                # 中转地址：直接使用完整 URL
                api_endpoint = base_url

            kwargs["client_options"] = {"api_endpoint": api_endpoint}
            logger.info(f"✅ [Google初始化] 设置 client_options.api_endpoint: {api_endpoint}")

        super().__init__(**kwargs)

        logger.info("✅ Google AI 客户端初始化成功")
        logger.info(f"   模型: {kwargs.get('model', 'gemini-pro')}")

    @property
    def model_name(self) -> str:
        # 移除 "models/" 前缀，返回纯模型名
        model = self.model
        if model and model.startswith("models/"):
            return model[7:]
        return model or "unknown"

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, **kwargs) -> LLMResult:
        try:
            result = super()._generate(messages, stop, **kwargs)
            self._track_token_usage(result, kwargs)
            return result

        except Exception as e:
            logger.error(f"❌ Google AI 生成失败: {e}")
            logger.exception(e)

            error_str = str(e)
            if "API_KEY_INVALID" in error_str or "API key not valid" in error_str:
                error_content = (
                    "Google AI API Key 无效或未配置。\n\n请检查：\n"
                    "1. GOOGLE_API_KEY 环境变量是否正确配置\n"
                    "2. API Key 是否有效（访问 https://ai.google.dev/ 获取）\n"
                    "3. 是否启用了 Gemini API\n\n建议：使用其他 AI 模型（如阿里百炼、DeepSeek）"
                )
            elif "Connection" in error_str or "Network" in error_str:
                error_content = f"Google AI 网络连接失败: {error_str}\n\n请检查网络 / 防火墙 / 代理设置"
            else:
                error_content = f"Google AI 调用失败: {error_str}\n\n请检查配置或使用其他 AI 模型"

            from langchain_core.outputs import ChatGeneration

            error_message = AIMessage(content=error_content)
            error_generation = ChatGeneration(message=error_message)
            return LLMResult(generations=[[error_generation]])

    def _track_token_usage(self, result: LLMResult, kwargs: dict[str, Any]) -> None:
        try:
            if hasattr(result, "llm_output") and result.llm_output:
                token_usage = result.llm_output.get("token_usage", {})

                input_tokens = token_usage.get("prompt_tokens", 0)
                output_tokens = token_usage.get("completion_tokens", 0)

                if input_tokens > 0 or output_tokens > 0:
                    from tradingagents.config.config_manager import token_tracker

                    session_id = kwargs.get("session_id", f"google_openai_{hash(str(kwargs)) % 10000}")
                    analysis_type = kwargs.get("analysis_type", "stock_analysis")

                    token_tracker.track_usage(
                        provider="google",
                        model_name=self.model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        session_id=session_id,
                        analysis_type=analysis_type,
                    )

                    logger.debug(f"📊 [Google] Token: 输入={input_tokens}, 输出={output_tokens}")

        except Exception as track_error:
            logger.error(f"⚠️ Google Token 追踪失败: {track_error}")
