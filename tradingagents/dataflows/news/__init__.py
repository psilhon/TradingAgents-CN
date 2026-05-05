"""
新闻数据获取模块
统一管理各种新闻数据源
"""

# 导入 Google News
try:
    from .google_news import getNewsData

    GOOGLE_NEWS_AVAILABLE = True
except ImportError:
    getNewsData = None
    GOOGLE_NEWS_AVAILABLE = False

# 导入 Reddit
try:
    from .reddit import fetch_top_from_category

    REDDIT_AVAILABLE = True
except ImportError:
    fetch_top_from_category = None
    REDDIT_AVAILABLE = False

# 导入实时新闻
try:
    from .realtime_news import get_news_with_sentiment, get_realtime_news, search_news_by_keyword

    REALTIME_NEWS_AVAILABLE = True
except ImportError:
    get_realtime_news = None
    get_news_with_sentiment = None
    search_news_by_keyword = None
    REALTIME_NEWS_AVAILABLE = False

# 导入中国财经数据聚合器
try:
    from .chinese_finance import ChineseFinanceDataAggregator

    CHINESE_FINANCE_AVAILABLE = True
except ImportError:
    ChineseFinanceDataAggregator = None
    CHINESE_FINANCE_AVAILABLE = False

__all__ = [
    "CHINESE_FINANCE_AVAILABLE",
    "GOOGLE_NEWS_AVAILABLE",
    "REALTIME_NEWS_AVAILABLE",
    "REDDIT_AVAILABLE",
    # Chinese Finance
    "ChineseFinanceDataAggregator",
    # Reddit
    "fetch_top_from_category",
    # Google News
    "getNewsData",
    "get_news_with_sentiment",
    # Realtime News
    "get_realtime_news",
    "search_news_by_keyword",
]
