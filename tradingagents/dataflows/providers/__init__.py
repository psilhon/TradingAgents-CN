"""
统一数据源提供器包
按市场分类组织数据提供器
"""
from .base_provider import BaseStockDataProvider

# 导入中国市场提供器（新路径）
try:
    from .china import AKSHARE_AVAILABLE, BAOSTOCK_AVAILABLE, TUSHARE_AVAILABLE, AKShareProvider, TushareProvider
    from .china import BaostockProvider as BaoStockProvider
except ImportError:
    # 向后兼容：尝试从旧路径导入
    try:
        from .tushare_provider import TushareProvider
    except ImportError:
        TushareProvider = None

    try:
        from .akshare_provider import AKShareProvider
    except ImportError:
        AKShareProvider = None

    try:
        from .baostock_provider import BaoStockProvider
    except ImportError:
        BaoStockProvider = None

    AKSHARE_AVAILABLE = AKShareProvider is not None
    TUSHARE_AVAILABLE = TushareProvider is not None
    BAOSTOCK_AVAILABLE = BaoStockProvider is not None

# 导入港股提供器
try:
    from .hk import HK_PROVIDER_AVAILABLE, ImprovedHKStockProvider, get_improved_hk_provider
except ImportError:
    ImprovedHKStockProvider = None
    get_improved_hk_provider = None
    HK_PROVIDER_AVAILABLE = False

# 导入美股提供器
try:
    from .us import FINNHUB_AVAILABLE, OPTIMIZED_US_AVAILABLE, YFINANCE_AVAILABLE, OptimizedUSDataProvider, YFinanceUtils, get_data_in_range
except ImportError:
    # 向后兼容：尝试从旧路径导入
    try:
        from ..yfin_utils import YFinanceUtils
    except ImportError:
        YFinanceUtils = None

    try:
        from ..optimized_us_data import OptimizedUSDataProvider
    except ImportError:
        OptimizedUSDataProvider = None

    try:
        from ..finnhub_utils import get_data_in_range
    except ImportError:
        get_data_in_range = None

    YFINANCE_AVAILABLE = YFinanceUtils is not None
    OPTIMIZED_US_AVAILABLE = OptimizedUSDataProvider is not None
    FINNHUB_AVAILABLE = get_data_in_range is not None

# 其他提供器（预留）
try:
    from .yahoo_provider import YahooProvider
except ImportError:
    YahooProvider = None

try:
    from .finnhub_provider import FinnhubProvider
except ImportError:
    FinnhubProvider = None

# TDXProvider 已移除
# try:
#     from .tdx_provider import TDXProvider
# except ImportError:
#     TDXProvider = None

__all__ = [
    'AKSHARE_AVAILABLE',
    'BAOSTOCK_AVAILABLE',
    'FINNHUB_AVAILABLE',
    'HK_PROVIDER_AVAILABLE',
    'OPTIMIZED_US_AVAILABLE',
    'TUSHARE_AVAILABLE',
    'YFINANCE_AVAILABLE',
    'AKShareProvider',
    'BaoStockProvider',
    # 基类
    'BaseStockDataProvider',
    'FinnhubProvider',
    # 港股
    'ImprovedHKStockProvider',
    'OptimizedUSDataProvider',
    # 中国市场
    'TushareProvider',
    # 美股
    'YFinanceUtils',
    # 其他（预留）
    'YahooProvider',
    'get_data_in_range',
    'get_improved_hk_provider',
    # 'TDXProvider'  # 已移除
]
