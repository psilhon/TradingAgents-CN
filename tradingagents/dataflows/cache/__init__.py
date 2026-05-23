"""
缓存管理模块

支持多种缓存策略：
- 文件缓存（默认）- 简单稳定，不依赖外部服务
- 数据库缓存（可选）- MongoDB + Redis，性能更好
- 自适应缓存（推荐）- 自动选择最佳后端

使用方法：
    from tradingagents.dataflows.cache import get_cache
    cache = get_cache()  # 自动选择最佳缓存策略

配置缓存策略：
    export TA_CACHE_STRATEGY=integrated  # 启用集成缓存（MongoDB/Redis）
    export TA_CACHE_STRATEGY=file        # 使用文件缓存（默认）
"""

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

# 导入自适应缓存
try:
    from .adaptive import AdaptiveCacheSystem

    ADAPTIVE_CACHE_AVAILABLE = True
except ImportError:
    AdaptiveCacheSystem = None
    ADAPTIVE_CACHE_AVAILABLE = False

# 导入集成缓存（4.4 后 deprecated，构造时 raise DeprecationWarning）
try:
    from .integrated import IntegratedCacheManager

    INTEGRATED_CACHE_AVAILABLE = True
except ImportError:
    IntegratedCacheManager = None
    INTEGRATED_CACHE_AVAILABLE = False

# 4.4 新公开 API：统一 Cache 类
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

# 全局缓存实例
_cache_instance = None


def get_cache() -> "StockDataCache | Cache":
    """
    获取缓存实例（统一入口）

    根据 CacheConfig.from_environment 决策缓存策略：
    - "file": 使用 StockDataCache（文件缓存）
    - "integrated" (默认) / "adaptive": 4.4 起返回新 `Cache` 类，吸收路由 +
      fallback + envelope 构建。老 IntegratedCacheManager / AdaptiveCacheSystem
      仍可用但 deprecated（构造时 raise DeprecationWarning），4.6 才删

    环境变量 TA_CACHE_STRATEGY 仍是配置入口（CacheConfig.from_environment 解析）。

    返回：
        StockDataCache 或 Cache 实例
    """
    global _cache_instance

    if _cache_instance is None:
        # 派生 CacheConfig（单一来源）
        try:
            from pathlib import Path

            from tradingagents.config.database_manager import get_database_manager

            from ._config import CacheConfig

            db_manager = get_database_manager()
            cache_config = CacheConfig.from_environment(db_manager)
            strategy = cache_config.cache_strategy
        except Exception as e:
            logger.warning(f"⚠️ CacheConfig 初始化失败，降级到 file 策略: {e}")
            cache_config = None
            strategy = "file"

        if strategy in ("integrated", "adaptive") and UNIFIED_CACHE_AVAILABLE and cache_config is not None:
            # 4.4：新 Cache 类，注入 3 个 backend
            try:
                from .backends import FileBackend, MongoBackend, RedisBackend

                cache_dir = Path("data/cache")
                file_backend = FileBackend(cache_dir=cache_dir)
                redis_backend = RedisBackend(redis_client=db_manager.get_redis_client())
                mongo_backend = MongoBackend(mongodb_client=db_manager.get_mongodb_client())
                _cache_instance = Cache(
                    file_backend=file_backend,
                    config=cache_config,
                    redis_backend=redis_backend,
                    mongo_backend=mongo_backend,
                )
                logger.info("✅ 使用统一 Cache（4.4，支持 MongoDB/Redis/File 自动路由 + fallback）")
            except Exception as e:
                logger.warning(f"⚠️ 统一 Cache 初始化失败，降级到文件缓存: {e}")
                _cache_instance = StockDataCache()
        else:
            _cache_instance = StockDataCache()
            logger.info("✅ 使用文件缓存系统")

    return _cache_instance


__all__ = [
    "ADAPTIVE_CACHE_AVAILABLE",
    "APP_CACHE_AVAILABLE",
    # 可用性标志
    "FILE_CACHE_AVAILABLE",
    "INTEGRATED_CACHE_AVAILABLE",
    "MONGODB_CACHE_ADAPTER_AVAILABLE",
    "UNIFIED_CACHE_AVAILABLE",
    "AdaptiveCacheSystem",
    # 4.4 新公开 API（推荐）
    "Cache",
    # deprecated（保留兼容，4.6 删）
    "IntegratedCacheManager",
    # MongoDB 缓存适配器
    "MongoDBCacheAdapter",
    # 缓存类（供高级用户直接使用）
    "StockDataCache",
    # 应用缓存适配器
    "get_basics_from_cache",
    # 统一入口（推荐使用）
    "get_cache",
    "get_market_quote_dataframe",
]
