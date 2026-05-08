"""
QuotesService: 提供A股批量实时快照获取（AKShare东方财富 spot 接口），带内存TTL缓存。
- 不使用通达信（TDX）作为兜底数据源。
- 仅用于筛选返回前对 items 进行行情富集。
"""

from __future__ import annotations

import asyncio
import math
import time
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _safe_float(v) -> Optional[float]:
    try:
        if v is None:
            return None
        # 处理字符串中的逗号/百分号/空白
        if isinstance(v, str):
            s = v.strip().replace(",", "")
            if s.endswith("%"):
                s = s[:-1]
            if s == "-" or s == "":
                return None
            return float(s)
        # 处理 pandas/numpy 数值
        return float(v)
    except Exception:
        return None


class QuotesService:
    def __init__(
        self,
        ttl_seconds: int = 30,
        fetch_timeout_seconds: float = 8.0,
    ) -> None:
        self._ttl = ttl_seconds
        # 盘内 akshare spot 拉取超时上限。akshare 偶尔慢到 60-110s，
        # 超时后降级到 stale cache / mongo 历史快照，避免 UI 阻塞。
        self._fetch_timeout = fetch_timeout_seconds
        self._cache_ts: float = 0.0
        self._cache: Dict[str, Dict[str, Optional[float]]] = {}
        self._lock = asyncio.Lock()

    async def _ensure_cache(self) -> Dict[str, Dict[str, Optional[float]]]:
        """确保 cache 有效（在 TTL 内），过期则刷新。返回完整 cache（全市场）.

        OpenSpec capability `trading-calendar` 铁律：盘外（周末 / 节假日 /
        非交易时段）不刷新 akshare。但盘外仍需提供数据让 UI 显示「最近一次盘中
        快照」——首次启动 cache 空时从 mongo `market_quotes` 加载已持久化数据
        到内存。盘内则正常拉 akshare 刷新。
        """
        now = time.time()
        async with self._lock:
            if self._cache and (now - self._cache_ts) < self._ttl:
                return self._cache

            # 盘外 guard：不调 akshare；cache 空则从 mongo 加载历史快照
            try:
                from app.services.trading_calendar_service import (
                    get_trading_calendar_service,
                )

                if not await get_trading_calendar_service().is_intraday_now():
                    if not self._cache:
                        self._cache = await self._load_cache_from_mongo()
                        self._cache_ts = time.time()  # 假装新鲜，避免重复 mongo 加载
                    return self._cache
            except Exception as e:
                # trading_calendar 异常时保守降级：仍刷新（避免彻底无数据）
                logger.debug(f"trading_calendar guard 失败，fallback 刷新 cache: {e}")

            # 盘内 fetch：加超时降级，避免 akshare 慢调用阻塞 UI / lock 串行
            try:
                data = await asyncio.wait_for(
                    asyncio.to_thread(self._fetch_spot_akshare),
                    timeout=self._fetch_timeout,
                )
                if data:
                    self._cache = data
                    self._cache_ts = time.time()
                    return self._cache
                logger.warning("AKShare spot 返回空，沿用现有 cache 或降级 mongo 快照")
            except asyncio.TimeoutError:
                logger.warning(f"AKShare spot fetch 超时（>{self._fetch_timeout}s），沿用现有 cache 或降级 mongo 快照")
            except Exception as e:
                logger.warning(f"AKShare spot fetch 异常: {e}，沿用现有 cache 或降级 mongo 快照")

            # 降级链：有旧 cache 就直接返回（不刷 ts，下个 ttl 周期再重试 fetch）；
            # 无旧 cache 才读 mongo 历史快照。
            if self._cache:
                return self._cache
            self._cache = await self._load_cache_from_mongo()
            self._cache_ts = time.time()
            return self._cache

    async def _load_cache_from_mongo(self) -> Dict[str, Dict[str, Optional[float]]]:
        """盘外 fallback：从 mongo `market_quotes` 加载已持久化的最近一次盘中
        快照到内存 cache 格式。

        mongo `market_quotes` 由项目其他 realtime sync job（实时行情入库 / 实时
        行情同步 Tushare/AKShare 等）持续写入，含 close + pct_chg + amount 等
        字段。盘外用这份 stale data 比 UI 全显「—」好。
        """
        try:
            from app.core.database import get_mongo_db

            db = get_mongo_db()
            result: Dict[str, Dict[str, Optional[float]]] = {}
            cursor = db["market_quotes"].find(
                {},
                {"code": 1, "close": 1, "pct_chg": 1, "amount": 1, "_id": 0},
            )
            async for doc in cursor:
                code = str(doc.get("code", "")).strip()
                if not code:
                    continue
                # 标准化 6 位代码（与 _fetch_spot_akshare 一致）
                code = code.zfill(6) if code.isdigit() else code
                result[code] = {
                    "close": doc.get("close"),
                    "pct_chg": doc.get("pct_chg"),
                    "amount": doc.get("amount"),
                }
            logger.info(f"QuotesService 盘外 fallback：从 mongo 加载 {len(result)} 条到 cache")
            return result
        except Exception as e:
            logger.warning(f"QuotesService._load_cache_from_mongo 失败: {e}")
            return {}

    async def get_market_overview(self) -> Dict[str, Optional[float]]:
        """全市场统计：涨停 / 跌停 / 上涨 / 下跌家数 + 成交额合计。

        简化阈值：pct_chg >= 9.5% 算涨停，<= -9.5% 算跌停（不区分主板/创业板/科创板的
        ±10% / ±20% 涨跌幅限制，足够 Dashboard 概览用）。

        amount 单位假设 akshare 返回为元，统一 / 1e8 转亿。如返回为万元，前端再调整。
        """
        cache = await self._ensure_cache()
        if not cache:
            return {
                "limit_up": None,
                "limit_down": None,
                "advance": None,
                "decline": None,
                "amount_total": None,
                "total": 0,
            }

        limit_up = limit_down = advance = decline = 0
        amount_total: float = 0.0
        for q in cache.values():
            pct = q.get("pct_chg")
            amt = q.get("amount")
            # NaN 守卫：pandas 数值列空值是 NaN（float），非 None；JSON 序列化时
            # NaN → null 让前端 fallback 到「—」。统一过滤 NaN
            if pct is not None and not math.isnan(pct):
                if pct >= 9.5:
                    limit_up += 1
                elif pct <= -9.5:
                    limit_down += 1
                if pct > 0:
                    advance += 1
                elif pct < 0:
                    decline += 1
            if amt is not None and not math.isnan(amt):
                amount_total += amt

        return {
            "limit_up": limit_up,
            "limit_down": limit_down,
            "advance": advance,
            "decline": decline,
            # 转成亿（原始单位元）
            "amount_total": round(amount_total / 1e8, 0),
            "total": len(cache),
        }

    async def get_quotes(self, codes: List[str]) -> Dict[str, Dict[str, Optional[float]]]:
        """获取一批股票的近实时快照（最新价、涨跌幅、成交额）。
        - 优先使用缓存；缓存超时或为空则刷新一次全市场快照。
        - 返回仅包含请求的 codes。
        """
        codes = [c.strip() for c in codes if c]
        now = time.time()
        async with self._lock:
            if self._cache and (now - self._cache_ts) < self._ttl:
                return {c: q for c, q in self._cache.items() if c in codes and q}
            # 刷新缓存（阻塞IO放到线程）
            data = await asyncio.to_thread(self._fetch_spot_akshare)
            self._cache = data
            self._cache_ts = time.time()
            return {c: q for c, q in self._cache.items() if c in codes and q}

    def _fetch_spot_akshare(self) -> Dict[str, Dict[str, Optional[float]]]:
        """通过 AKShare 东方财富全市场快照接口拉取行情，并标准化为字典。
        预期列（常见）：代码、名称、最新价、涨跌幅、成交额。
        不同版本可能有差异，做多列名兼容。
        """
        try:
            import akshare as ak  # 已在项目中使用，不额外安装

            df = ak.stock_zh_a_spot_em()
            if df is None or getattr(df, "empty", True):
                logger.warning("AKShare spot 返回空数据")
                return {}
            # 兼容常见列名
            code_col = next((c for c in ["代码", "代码code", "symbol", "股票代码"] if c in df.columns), None)
            price_col = next((c for c in ["最新价", "现价", "最新价(元)", "price", "最新"] if c in df.columns), None)
            pct_col = next((c for c in ["涨跌幅", "涨跌幅(%)", "涨幅", "pct_chg"] if c in df.columns), None)
            amount_col = next((c for c in ["成交额", "成交额(元)", "amount", "成交额(万元)"] if c in df.columns), None)

            if not code_col or not price_col:
                logger.error(f"AKShare spot 缺少必要列: code={code_col}, price={price_col}")
                return {}

            result: Dict[str, Dict[str, Optional[float]]] = {}
            for _, row in df.iterrows():  # type: ignore
                code_raw = row.get(code_col)
                if not code_raw:
                    continue
                # 标准化股票代码：移除前导0，然后补齐到6位
                code_str = str(code_raw).strip()
                # 如果是纯数字，移除前导0后补齐到6位
                if code_str.isdigit():
                    code_clean = code_str.lstrip("0") or "0"  # 移除前导0，如果全是0则保留一个0
                    code = code_clean.zfill(6)  # 补齐到6位
                else:
                    code = code_str.zfill(6)
                close = _safe_float(row.get(price_col))
                pct = _safe_float(row.get(pct_col)) if pct_col else None
                amt = _safe_float(row.get(amount_col)) if amount_col else None
                # 若成交额单位为万元，统一转换为元（部分接口是万元，这里不强转，保持原样由前端展示单位）
                result[code] = {"close": close, "pct_chg": pct, "amount": amt}
            logger.info(f"AKShare spot 拉取完成: {len(result)} 条")
            return result
        except Exception as e:
            logger.error(f"获取AKShare实时快照失败: {e}")
            return {}


_quotes_service: Optional[QuotesService] = None


def get_quotes_service() -> QuotesService:
    global _quotes_service
    if _quotes_service is None:
        _quotes_service = QuotesService(ttl_seconds=30)
    return _quotes_service
