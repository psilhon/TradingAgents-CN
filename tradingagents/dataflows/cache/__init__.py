"""
缓存管理模块

拓扑：
- `Cache` (推荐): 统一公开 API + 3 个 pluggable backends (File / Redis / Mongo) +
  CacheConfig 单一配置
- `StockDataCache`: file-only 策略备用 (TA_CACHE_STRATEGY=file 路径 + 2 个外部
  import 依赖保留)

使用方法：
    from tradingagents.dataflows.cache import get_cache
    cache = get_cache()  # 自动选择最佳缓存策略

配置缓存策略：
    export TA_CACHE_STRATEGY=integrated  # 启用统一 Cache（MongoDB/Redis/File）
    export TA_CACHE_STRATEGY=file        # 使用 StockDataCache 文件缓存
"""

import os
import threading

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")

# 导入文件缓存
try:
    from .file_cache import StockDataCache

    FILE_CACHE_AVAILABLE = True
except ImportError:
    StockDataCache = None
    FILE_CACHE_AVAILABLE = False

# 公开 API：统一 Cache 类
try:
    from ._cache import Cache

    UNIFIED_CACHE_AVAILABLE = True
except ImportError:
    Cache = None  # type: ignore[assignment,misc]
    UNIFIED_CACHE_AVAILABLE = False

# 导入应用缓存适配器（函数，非类）
try:
    from .app_adapter import get_basics_from_cache, get_market_quote_dataframe

    APP_CACHE_AVAILABLE = True
except ImportError:
    get_basics_from_cache = None
    get_market_quote_dataframe = None
    APP_CACHE_AVAILABLE = False

# 导入 MongoDB 缓存适配器
try:
    from .mongodb_cache_adapter import MongoDBCacheAdapter

    MONGODB_CACHE_ADAPTER_AVAILABLE = True
except ImportError:
    MongoDBCacheAdapter = None
    MONGODB_CACHE_ADAPTER_AVAILABLE = False

# 全局缓存实例 + 构造锁
_cache_instance = None
_cache_instance_lock = threading.Lock()


def get_cache() -> "StockDataCache | Cache":
    """获取缓存实例（统一入口）。

    根据 `CacheConfig.from_environment` 决策缓存策略：
    - "file": 使用 StockDataCache
    - "integrated" (默认) / "adaptive": 返回新 `Cache` 类（路由 + fallback +
      envelope 构建一体）

    线程安全：单例构造受 `_cache_instance_lock` 保护，避免 FastAPI 多线程冷启
    动两次实例化 + 两组 backend 连接。

    失败语义：若主路径（统一 Cache + 三 backend）构造抛异常，本次返回
    `StockDataCache` fallback **但不缓存**——下次 `get_cache()` 重试主路径，
    避免临时 db 故障让进程永远停在 fallback 状态。

    返回：
        StockDataCache 或 Cache 实例
    """
    global _cache_instance

    # Fast path — instance already cached.
    if _cache_instance is not None:
        return _cache_instance

    with _cache_instance_lock:
        # Re-check inside the lock: another thread may have constructed
        # while we were waiting.
        if _cache_instance is not None:
            return _cache_instance

        # Derive CacheConfig (single source of truth).
        try:
            from pathlib import Path

            from tradingagents.config.database_manager import get_database_manager

            from ._config import CacheConfig

            db_manager = get_database_manager()
            cache_config = CacheConfig.from_environment(db_manager)
            strategy = cache_config.cache_strategy
        except Exception:
            logger.exception("⚠️ CacheConfig 初始化失败，降级到 file 策略（本次返回不缓存）")
            cache_config = None
            strategy = "file"

        if strategy in ("integrated", "adaptive") and UNIFIED_CACHE_AVAILABLE and cache_config is not None:
            try:
                from .backends import FileBackend, MongoBackend, RedisBackend

                # 4.8+: TA_CACHE_DIR env override (default "data/cache"; ~ expanded
                # so ops can set TA_CACHE_DIR=~/.cache/tradingagents). Hardcoded
                # relative path otherwise picks up CWD — drifts when uvicorn is
                # launched outside the project root (systemd / docker).
                cache_dir = Path(os.getenv("TA_CACHE_DIR", "data/cache")).expanduser()
                file_backend = FileBackend(cache_dir=cache_dir)
                redis_backend = RedisBackend(redis_client=db_manager.get_redis_client())
                mongo_backend = MongoBackend(mongodb_client=db_manager.get_mongodb_client())
                instance = Cache(
                    file_backend=file_backend,
                    config=cache_config,
                    redis_backend=redis_backend,
                    mongo_backend=mongo_backend,
                )
                _cache_instance = instance  # only cache on full success
                logger.info("✅ 使用统一 Cache（支持 MongoDB/Redis/File 自动路由 + fallback）")
                return instance
            except Exception:
                logger.exception("⚠️ 统一 Cache 初始化失败，降级到文件缓存（本次返回不缓存，下次重试主路径）")
                # 不缓存 fallback 实例 — 下次 get_cache() 会重试统一 Cache 路径。
                # 若 StockDataCache 也不可用（None），直接 raise 让 caller 看见。
                if StockDataCache is None:
                    raise RuntimeError("Neither unified Cache nor StockDataCache fallback is available") from None
                return StockDataCache()

        # strategy == "file" — cache the StockDataCache instance (intentional, stable choice).
        if StockDataCache is None:
            raise RuntimeError("TA_CACHE_STRATEGY=file but StockDataCache is unavailable")
        _cache_instance = StockDataCache()
        logger.info("✅ 使用文件缓存系统")
        return _cache_instance


def reset_cache() -> None:
    """清除 get_cache() 缓存的单例（测试 + 运维 reload 用）。

    线程安全；下次 `get_cache()` 重新构造。
    """
    global _cache_instance
    with _cache_instance_lock:
        _cache_instance = None
        logger.debug("cache singleton reset")


__all__ = [
    "APP_CACHE_AVAILABLE",
    # 可用性标志
    "FILE_CACHE_AVAILABLE",
    "MONGODB_CACHE_ADAPTER_AVAILABLE",
    "UNIFIED_CACHE_AVAILABLE",
    # 公开 API（推荐）
    "Cache",
    # MongoDB 缓存适配器
    "MongoDBCacheAdapter",
    # 缓存类（file 策略备用 + 外部依赖兼容）
    "StockDataCache",
    # 应用缓存适配器
    "get_basics_from_cache",
    # 统一入口（推荐使用）
    "get_cache",
    "get_market_quote_dataframe",
    # 单例 reload（测试 + 运维）
    "reset_cache",
]
