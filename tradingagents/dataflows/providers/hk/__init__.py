"""
港股数据提供器
"""

# 导入改进的港股工具
try:
    from .improved_hk import ImprovedHKStockProvider, get_hk_stock_info_improved, get_improved_hk_provider
    HK_PROVIDER_AVAILABLE = True
except ImportError:
    ImprovedHKStockProvider = None
    get_improved_hk_provider = None
    get_hk_stock_info_improved = None
    HK_PROVIDER_AVAILABLE = False

# 导入港股数据工具
try:
    from .hk_stock import HKStockProvider
    HK_STOCK_AVAILABLE = True
except ImportError:
    HKStockProvider = None
    HK_STOCK_AVAILABLE = False

__all__ = [
    'HK_PROVIDER_AVAILABLE',
    'HK_STOCK_AVAILABLE',
    'HKStockProvider',
    'ImprovedHKStockProvider',
    'get_hk_stock_info_improved',
    'get_improved_hk_provider',
]

