"""
tradingagents 自有 mongo 连接 helper —— OpenSpec spec `license-boundary` 要求
`tradingagents/`（Apache 2.0）禁止散布反向 import 专有授权 `app/` 模块。

本 module 是 tradingagents → app 反向 import 的**单一桥接点**：
- 优先使用 `app.core.database.get_mongo_db_sync()`（生产/fork 单体 repo 场景）
- ImportError 时 fallback 到独立 pymongo 连接（lib 单独发行场景）

历史：本 change 之前 `tradingagents/` 散布 10 处 `from app.core.database import
get_mongo_db_sync`，违反 spec license-boundary。OpenSpec change
`eliminate-app-business-layer-imports` 收拢到本桥接点。
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# 进程级 mongo 连接 cache（fallback 路径用）
_fallback_client: Any = None
_fallback_db: Any = None


def get_mongo_db_sync():
    """获取同步 mongo db 实例。

    优先桥接 `app.core.database.get_mongo_db_sync`，失败 fallback 到本 module
    自建 pymongo 连接（与 app.core.config 同一组 env vars）。

    返回类型：`pymongo.database.Database`（兼容 `app.core.database` 的同名 API）
    """
    # 路径 1：桥接（生产 / fork 单体 repo 场景）
    try:
        from app.core.database import get_mongo_db_sync as _bridge_impl

        return _bridge_impl()
    except ImportError:
        pass

    # 路径 2：独立 fallback（lib 单独发行场景）
    return _fallback_get_mongo_db_sync()


def _fallback_get_mongo_db_sync():
    """独立 pymongo 连接（不依赖 app/）—— 简化版 scope 处理仅支持 explicit."""
    global _fallback_client, _fallback_db

    if _fallback_db is not None:
        return _fallback_db

    try:
        from pymongo import MongoClient
    except ImportError:
        logger.warning("pymongo 未安装，tradingagents/utils/database 无法 fallback")
        raise

    host = os.getenv("MONGODB_HOST", "localhost")
    port = int(os.getenv("MONGODB_PORT", "27017"))
    user = os.getenv("MONGODB_USERNAME", "")
    pwd = os.getenv("MONGODB_PASSWORD", "")
    database = os.getenv("MONGODB_DATABASE", "tradingagentscn")
    auth_source = os.getenv("MONGODB_AUTH_SOURCE", "admin")

    if user and pwd:
        uri = f"mongodb://{user}:{pwd}@{host}:{port}/{database}?authSource={auth_source}"
    else:
        uri = f"mongodb://{host}:{port}/{database}"

    _fallback_client = MongoClient(
        uri,
        maxPoolSize=int(os.getenv("MONGO_MAX_CONNECTIONS", "100")),
        minPoolSize=int(os.getenv("MONGO_MIN_CONNECTIONS", "10")),
        maxIdleTimeMS=30000,
        serverSelectionTimeoutMS=5000,
    )
    _fallback_db = _fallback_client[database]
    return _fallback_db


def get_mongo_uri() -> str:
    """构建 mongo URI（替代 `settings.MONGO_URI`）。

    OpenSpec change `eliminate-app-business-layer-imports`：替换 tradingagents
    内 2 处 `from app.core.config import settings; settings.MONGO_URI` 反向 import.
    """
    try:
        from app.core.config import settings

        return settings.MONGO_URI
    except ImportError:
        host = os.getenv("MONGODB_HOST", "localhost")
        port = int(os.getenv("MONGODB_PORT", "27017"))
        user = os.getenv("MONGODB_USERNAME", "")
        pwd = os.getenv("MONGODB_PASSWORD", "")
        database = os.getenv("MONGODB_DATABASE", "tradingagentscn")
        auth_source = os.getenv("MONGODB_AUTH_SOURCE", "admin")
        if user and pwd:
            return f"mongodb://{user}:{pwd}@{host}:{port}/{database}?authSource={auth_source}"
        return f"mongodb://{host}:{port}/{database}"


def get_market_analyst_lookback_days(default: int = 60) -> int:
    """读 MARKET_ANALYST_LOOKBACK_DAYS 配置（替代 `settings.MARKET_ANALYST_LOOKBACK_DAYS`）.

    OpenSpec change `eliminate-app-business-layer-imports`：替换 tradingagents
    内 5 处 `from app.core.config import settings; settings.MARKET_ANALYST_LOOKBACK_DAYS`
    反向 import.
    """
    try:
        return int(os.getenv("MARKET_ANALYST_LOOKBACK_DAYS", str(default)))
    except (ValueError, TypeError):
        return default


__all__ = [
    "get_market_analyst_lookback_days",
    "get_mongo_db_sync",
    "get_mongo_uri",
]
