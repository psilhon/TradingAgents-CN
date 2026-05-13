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


def _to_sina_symbol(code: str) -> Optional[str]:
    """6 位股票代码 → sina hq.sinajs.cn 格式 (sh/sz/bj + 6位)."""
    c = str(code).strip()
    if not c.isdigit() or len(c) > 6:
        return None
    c = c.zfill(6)
    head = c[0]
    if head in ("6", "9"):
        return f"sh{c}"  # 沪市主板 / 科创板
    elif head in ("0", "2", "3"):
        return f"sz{c}"  # 深市主板 / 中小板 / 创业板
    elif head in ("4", "8"):
        return f"bj{c}"  # 北交所
    return None


def _fetch_sina_batch(symbols: list[str]) -> Dict[str, Dict[str, Optional[float]]]:
    """同步调用 sina hq.sinajs.cn 批量端点，解析为标准 dict。

    返回格式 `{sina_symbol: {close, pct_chg, amount}}`.
    新浪字段（A 股）：name, open, prev_close, last_price, high, low, ..., volume(股), amount(元), ...
    """
    import requests

    url = f"https://hq.sinajs.cn/list={','.join(symbols)}"
    # sina 反爬要求 Referer，UA 兼容
    headers = {
        "Referer": "https://finance.sina.com.cn/",
        "User-Agent": "Mozilla/5.0",
    }
    resp = requests.get(url, headers=headers, timeout=6.0)
    resp.encoding = "gbk"  # sina 返回 GBK 编码（中文 name 会乱码但 numeric 字段正常）
    if resp.status_code != 200:
        return {}
    result: Dict[str, Dict[str, Optional[float]]] = {}
    for line in resp.text.splitlines():
        # 格式：var hq_str_sh600519="贵州茅台,1850.00,1860.00,1870.50,..."
        if "=" not in line or '"' not in line:
            continue
        try:
            sym_part, payload = line.split("=", 1)
            sym = sym_part.replace("var hq_str_", "").strip()
            data_str = payload.strip().strip(";").strip('"')
            if not data_str:
                continue  # 停牌或代码错误时返回空字符串
            fields = data_str.split(",")
            if len(fields) < 10:
                continue
            prev_close = _safe_float(fields[2])
            last_price = _safe_float(fields[3])
            amount = _safe_float(fields[9])
            pct_chg = None
            if prev_close and last_price and prev_close > 0:
                pct_chg = round((last_price - prev_close) / prev_close * 100, 3)
            result[sym] = {
                "close": last_price,
                "pct_chg": pct_chg,
                "amount": amount,
            }
        except Exception:
            continue
    return result


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

    def invalidate_cache(self) -> None:
        """强制清除内存 TTL 缓存，使下次 get_quotes / _ensure_cache 重新拉取。"""
        self._cache_ts = 0.0

    async def get_quotes_targeted(
        self, codes: List[str]
    ) -> Dict[str, Dict[str, Optional[float]]]:
        """按需批量查询特定股票行情（不走全市场缓存）。

        直接调用新浪 `hq.sinajs.cn/list=...` 批量端点，毫秒级响应，适合
        手动刷新 / 自选股 / 持仓 等小规模查询（≤80 codes/批）。

        返回格式与 `get_quotes` 一致：`{code: {close, pct_chg, amount}}`.
        失败/无数据时返回空 dict（不抛）。
        """
        codes = [c.strip() for c in codes if c]
        if not codes:
            return {}
        # 转 sina symbol 格式（sh/sz/bj + 6digit）
        sina_symbols: List[str] = []
        code_map: Dict[str, str] = {}  # sina_symbol -> 标准 6 位 code
        for c in codes:
            sym = _to_sina_symbol(c)
            if sym:
                sina_symbols.append(sym)
                code_map[sym] = c.zfill(6) if c.isdigit() else c
        if not sina_symbols:
            return {}

        # 调批量端点（分块 80 个一组）
        result: Dict[str, Dict[str, Optional[float]]] = {}
        chunk_size = 80
        for i in range(0, len(sina_symbols), chunk_size):
            chunk = sina_symbols[i : i + chunk_size]
            try:
                parsed = await asyncio.to_thread(_fetch_sina_batch, chunk)
            except Exception as e:
                logger.warning(f"sina hq batch 失败: {e}")
                continue
            for sym, data in parsed.items():
                code = code_map.get(sym, sym)
                result[code] = data
        logger.info(f"sina hq batch 拉取完成: {len(result)}/{len(sina_symbols)} 条")
        return result

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
        - AKShare 失败时降级到已有 cache 或 mongo 历史快照。
        - 返回仅包含请求的 codes。
        """
        codes = [c.strip() for c in codes if c]
        now = time.time()
        async with self._lock:
            if self._cache and (now - self._cache_ts) < self._ttl:
                return {c: q for c, q in self._cache.items() if c in codes and q}
            # 刷新缓存（阻塞IO放到线程）
            data = await asyncio.to_thread(self._fetch_spot_akshare)
            if data:
                self._cache = data
                self._cache_ts = time.time()
            elif not self._cache:
                # AKShare 失败且无旧缓存：降级到 mongo 历史快照
                self._cache = await self._load_cache_from_mongo()
                self._cache_ts = time.time()
            # else: AKShare 失败但有旧缓存，沿用（不刷 ts，下次仍重试）
            return {c: q for c, q in self._cache.items() if c in codes and q}

    def _fetch_spot_akshare(self) -> Dict[str, Dict[str, Optional[float]]]:
        """全市场实时快照获取（带源降级）。

        源优先级：
        1. 东方财富 `stock_zh_a_spot_em()` — 字段最全，含成交额
        2. 新浪财经 `stock_zh_a_spot()` — 东财被反爬/网络不通时降级

        任一源成功立即返回；全失败返回 {}.
        """
        try:
            import akshare as ak  # 已在项目中使用，不额外安装
        except Exception as e:
            logger.error(f"akshare 导入失败: {e}")
            return {}

        # 1. 优先东方财富
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and not getattr(df, "empty", True):
                result = self._parse_spot_df(df)
                if result:
                    logger.info(f"AKShare spot (eastmoney) 拉取完成: {len(result)} 条")
                    return result
            logger.warning("AKShare spot (eastmoney) 返回空数据，降级到新浪源")
        except Exception as e:
            logger.warning(f"AKShare spot (eastmoney) 失败: {type(e).__name__}，降级到新浪源")

        # 2. 降级到新浪
        try:
            df = ak.stock_zh_a_spot()  # 新浪源
            if df is not None and not getattr(df, "empty", True):
                result = self._parse_spot_df(df)
                if result:
                    logger.info(f"AKShare spot (sina) 拉取完成: {len(result)} 条")
                    return result
            logger.warning("AKShare spot (sina) 返回空数据")
        except Exception as e:
            logger.error(f"AKShare spot (sina) 也失败: {e}")

        return {}

    def _parse_spot_df(self, df) -> Dict[str, Dict[str, Optional[float]]]:
        """解析 AKShare spot DataFrame 为标准 dict 格式。

        兼容东方财富和新浪两种接口的列名差异。
        新浪列：代码 / 名称 / 最新价 / 涨跌额 / 涨跌幅 / 买入 / 卖出 / 昨收
        东财列：代码 / 名称 / 最新价 / 涨跌幅 / 涨跌额 / 成交量 / 成交额 ...
        新浪源无"成交额"列时，amount 字段会是 None（不影响 close/pct_chg 使用）.
        """
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
            # 标准化股票代码：sina 源代码带 sh/sz 前缀，需剥离
            code_str = str(code_raw).strip().lower()
            if code_str.startswith(("sh", "sz", "bj")):
                code_str = code_str[2:]
            if code_str.isdigit():
                code = code_str.lstrip("0").zfill(6) or "000000"
            else:
                code = code_str.zfill(6)
            close = _safe_float(row.get(price_col))
            pct = _safe_float(row.get(pct_col)) if pct_col else None
            amt = _safe_float(row.get(amount_col)) if amount_col else None
            result[code] = {"close": close, "pct_chg": pct, "amount": amt}
        return result


_quotes_service: Optional[QuotesService] = None


def get_quotes_service() -> QuotesService:
    global _quotes_service
    if _quotes_service is None:
        _quotes_service = QuotesService(ttl_seconds=30)
    return _quotes_service
