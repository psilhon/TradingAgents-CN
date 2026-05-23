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

# 导入集成缓存
try:
    from .integrated import IntegratedCacheManager

    INTEGRATED_CACHE_AVAILABLE = True
except ImportError:
    IntegratedCacheManager = None
    INTEGRATED_CACHE_AVAILABLE = False

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


def get_cache() -> StockDataCache | IntegratedCacheManager:
    """
    获取缓存实例（统一入口）

    根据 CacheConfig.from_environment 决策缓存策略（4.3 起经 CacheConfig 单一来源）：
    - "file": 使用文件缓存
    - "integrated" (默认): 使用集成缓存（自动选择 MongoDB/Redis/File）
    - "adaptive": 使用自适应缓存（同 integrated）

    环境变量 TA_CACHE_STRATEGY 仍是配置入口（CacheConfig.from_environment
    内部解析），用法与 4.3 前一致。

    返回：
        StockDataCache 或 IntegratedCacheManager 实例
    """
    global _cache_instance

    if _cache_instance is None:
        # 4.3：经 CacheConfig 单一来源派生策略 + backend 配置
        try:
            from tradingagents.config.database_manager import get_database_manager

            from ._config import CacheConfig

            cache_config = CacheConfig.from_environment(get_database_manager())
            strategy = cache_config.cache_strategy
        except Exception as e:
            logger.warning(f"⚠️ CacheConfig 初始化失败，降级到 file 策略: {e}")
            cache_config = None
            strategy = "file"

        if strategy in ("integrated", "adaptive"):
            if INTEGRATED_CACHE_AVAILABLE:
                try:
                    _cache_instance = IntegratedCacheManager(config=cache_config)
                    logger.info("✅ 使用集成缓存系统（支持 MongoDB/Redis/File 自动选择）")
                except Exception as e:
                    logger.warning(f"⚠️ 集成缓存初始化失败，降级到文件缓存: {e}")
                    _cache_instance = StockDataCache()
            else:
                logger.warning("⚠️ 集成缓存不可用，使用文件缓存")
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
    "AdaptiveCacheSystem",
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
