"""市场概况 API — 全市场聚合统计（涨停/跌停/上涨/下跌/成交额）。

数据源：`app/services/market_overview_prewarm_service.py` 的
in-memory hot snapshot（底层 `QuotesService._cache`，由盘中 prewarm task
每 30s 异步刷新）。hot-path **永不**在请求路径同步触发 akshare 拉取
（OpenSpec change 2026-05-08-realtime-trading-data-flow Requirement 1）.

cache 空（首启 + prewarm 还未跑过任何一轮）时返回 nullable 字段 +
`as_of_ts=null`，前端基于此显示"等待数据"，不阻塞。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends

from app.core.database import get_mongo_db
from app.routers.auth_db import get_current_user
from app.services.market_overview_prewarm_service import get_prewarm_service
from app.services.quote_freshness_monitor import get_freshness_monitor
from app.services.quotes_service import INDICES_CONFIG
from app.services.realtime_quote_sync_service import get_realtime_quote_sync_service
from app.services.trading_calendar_service import get_trading_calendar_service

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/freshness")
async def get_market_freshness(_user: dict = Depends(get_current_user)) -> dict:
    """市场行情数据时效摘要 — 给 UI 角标渲染（绿/黄/红）.

    OpenSpec change 2026-05-08-realtime-trading-data-flow Requirement
    "GET /api/market/freshness MUST 暴露数据时效给 UI 角标".

    返回字段：
    - as_of_ts: str | None ISO8601，mongo `market_quotes.updated_at` max
    - staleness_seconds: float | None now - as_of_ts
    - is_intraday: bool 当前是否盘中
    - last_successful_sync_at: str | None
    - sync_running: bool prewarm task 是否在跑
    - sla_threshold_seconds: float SLA 阈值（默认 90s）
    - breach: bool 盘中且 staleness > SLA
    """
    info = await get_freshness_monitor().get_freshness()
    return {"success": True, "data": info}


@router.get("/overview")
async def get_market_overview(_user: dict = Depends(get_current_user)) -> dict:
    """A 股市场概况：涨停/跌停/上涨/下跌家数 + 成交额合计（亿元）+ 是否盘中 + 数据时效.

    返回字段：
    - limit_up: int | None 涨停家数（pct_chg >= 9.5%）；cache 空时为 None
    - limit_down: int | None 跌停家数（pct_chg <= -9.5%）
    - advance: int | None 上涨家数（pct_chg > 0）
    - decline: int | None 下跌家数（pct_chg < 0）
    - amount_total: float | None 成交额合计（亿元）
    - total: int 全市场样本数（cache 空时 0）
    - as_of_ts: str | None ISO8601，hot snapshot 最新时刻；cache 空时 None
    - staleness_seconds: float | None now - as_of_ts；cache 空时 None
    - is_intraday: bool 当前是否 A 股交易日盘中（前端 polling guard 用）
    """
    overview = await get_prewarm_service().compute_overview()
    is_intraday = False
    try:
        is_intraday = await get_trading_calendar_service().is_intraday_now()
    except Exception:
        pass
    overview["is_intraday"] = is_intraday
    return {"success": True, "data": overview}


@router.get("/indices/snapshot")
async def get_indices_snapshot(_user: dict = Depends(get_current_user)) -> dict:
    """指数行情快照：A 股 3 + 港股 1（上证 / 深证 / 创业板 / 恒指）。

    数据由 scheduler 每 5 秒调 `sync_indices()` 刷新到 mongo `market_indices`。
    sina hq.sinajs.cn 端点盘外也返回上次收盘价 + 时间戳，前端用 `as_of` 判断
    今日 vs 隔夜（CN tz 日历日比较），非今日时灰化。

    返回数组（按 INDICES_CONFIG 顺序，前端 ticker 直接渲染）：
    ```
    [{code, label, kind, value, change, pct_chg, as_of}, ...]
    ```
    缺数据的项 value/change/pct_chg/as_of 为 None，前端显示「—」。
    """
    db = get_mongo_db()
    docs = await db["market_indices"].find({}, {"_id": 0}).to_list(None)
    by_code = {d.get("code"): d for d in docs}

    result = []
    for code, cfg in INDICES_CONFIG.items():
        doc = by_code.get(code) or {}
        upd = doc.get("updated_at")
        as_of = upd.isoformat() if isinstance(upd, datetime) else None
        result.append({
            "code": code,
            "label": cfg["label"],
            "kind": cfg["kind"],
            "value": doc.get("value"),
            "change": doc.get("change"),
            "pct_chg": doc.get("pct_chg"),
            "as_of": as_of,
        })
    return {"success": True, "data": result}


@router.post("/refresh-quotes")
async def refresh_quotes(_user: dict = Depends(get_current_user)) -> dict:
    """手动刷新行情：按需查询自选股 ∪ paper 持仓 (CN) 的实时行情.

    使用 sina hq.sinajs.cn 批量端点（毫秒级），仅同步目标 codes（通常 ≤100 只），
    不拉全市场快照。写入 mongo `market_quotes` 并 redis publish——前端 WebSocket
    会自动收到更新。盘外也可手动触发。
    """
    # force_publish=True：手动刷新场景下绕过变化检测，强制 publish 到 redis，
    # 让前端 WS 即使行情值未变也能收到事件、更新 last_price_as_of。
    sync_service = get_realtime_quote_sync_service()
    stats = await sync_service.sync_favorites_and_paper_positions(force_publish=True)

    return {
        "success": True,
        "message": "行情刷新完成",
        "data": stats,
    }
