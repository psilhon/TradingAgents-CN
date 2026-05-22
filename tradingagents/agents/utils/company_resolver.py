"""公司名解析 — agent 层由股票代码解析人类可读公司名的单一入口。

OpenSpec capability: agent-company-resolution。

此前 tradingagents/agents/ 下有 7 份近乎相同的 _get_company_name 拷贝
（analysts / researchers），逻辑已分歧。本模块为唯一定义，禁止再在 agent
文件内自建本地副本。

dataflows 依赖刻意做函数内惰性 import：tradingagents.dataflows 包 import
即连 MongoDB，模块级 import 会让任何 import 本模块的 agent 付出该代价。
"""

from tradingagents.utils.logging_init import get_logger

logger = get_logger("default")


def get_company_name(ticker: str, market_info: dict, agent_label: str = "分析师") -> str:
    """根据股票代码与市场信息解析公司中文名称。

    Args:
        ticker: 股票代码
        market_info: 市场信息字典，含 is_china / is_hk / is_us 布尔标志
        agent_label: 调用方标识，仅用于日志前缀（如 "市场分析师"）

    Returns:
        公司名称；任何失败路径都降级为带代码的占位名称，绝不抛异常。
    """
    try:
        if market_info["is_china"]:
            # A 股：统一接口 → 解析「股票名称:」字段；miss 时二级降级到 data_source_manager
            from tradingagents.dataflows.interface import get_china_stock_info_unified

            stock_info = get_china_stock_info_unified(ticker)
            logger.debug(f"📊 [{agent_label}] 获取股票信息返回: {stock_info[:200] if stock_info else 'None'}...")

            if stock_info and "股票名称:" in stock_info:
                company_name = stock_info.split("股票名称:")[1].split("\n")[0].strip()
                logger.info(f"✅ [{agent_label}] 成功获取中国股票名称: {ticker} -> {company_name}")
                return company_name

            logger.warning(f"⚠️ [{agent_label}] 无法从统一接口解析股票名称: {ticker}，尝试降级方案")
            try:
                from tradingagents.dataflows.data_source_manager import (
                    get_china_stock_info_unified as get_info_dict,
                )

                info_dict = get_info_dict(ticker)
                if info_dict and info_dict.get("name"):
                    company_name = info_dict["name"]
                    logger.info(f"✅ [{agent_label}] 降级方案成功获取股票名称: {ticker} -> {company_name}")
                    return company_name
            except Exception as e:
                logger.error(f"❌ [{agent_label}] 降级方案也失败: {e}")

            logger.error(f"❌ [{agent_label}] 所有方案都无法获取股票名称: {ticker}")
            return f"股票代码{ticker}"

        elif market_info["is_hk"]:
            # 港股：改进的港股工具
            try:
                from tradingagents.dataflows.providers.hk.improved_hk import get_hk_company_name_improved

                company_name = get_hk_company_name_improved(ticker)
                logger.debug(f"📊 [{agent_label}] 使用改进港股工具获取名称: {ticker} -> {company_name}")
                return company_name
            except Exception as e:
                logger.debug(f"📊 [{agent_label}] 改进港股工具获取名称失败: {e}")
                clean_ticker = ticker.replace(".HK", "").replace(".hk", "")
                return f"港股{clean_ticker}"

        elif market_info["is_us"]:
            # 美股：静态映射表，miss 返回代码占位
            us_stock_names = {
                "AAPL": "苹果公司",
                "TSLA": "特斯拉",
                "NVDA": "英伟达",
                "MSFT": "微软",
                "GOOGL": "谷歌",
                "AMZN": "亚马逊",
                "META": "Meta",
                "NFLX": "奈飞",
            }
            company_name = us_stock_names.get(ticker.upper(), f"美股{ticker}")
            logger.debug(f"📊 [{agent_label}] 美股名称映射: {ticker} -> {company_name}")
            return company_name

    except Exception as e:
        logger.error(f"❌ [{agent_label}] 获取公司名称失败: {e}")

    return f"股票代码{ticker}"
