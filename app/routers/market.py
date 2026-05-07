"""市场概况 API — 全市场聚合统计（涨停/跌停/上涨/下跌/成交额）。

数据源：复用 `app/services/quotes_service.py` 的 `QuotesService` 30s TTL 内存缓存
（底层 ak.stock_zh_a_spot_em 全市场快照）。endpoint 直接读 cache 后聚合。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.routers.auth_db import get_current_user
from app.services.quotes_service import get_quotes_service

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/overview")
async def get_market_overview(_user: dict = Depends(get_current_user)) -> dict:
    """A 股市场概况：涨停/跌停/上涨/下跌家数 + 成交额合计（亿元）.

    返回字段：
    - limit_up: int 涨停家数（pct_chg >= 9.5%）
    - limit_down: int 跌停家数（pct_chg <= -9.5%）
    - advance: int 上涨家数（pct_chg > 0）
    - decline: int 下跌家数（pct_chg < 0）
    - amount_total: float 成交额合计（亿元）
    - total: int 全市场样本数
    """
    overview = await get_quotes_service().get_market_overview()
    return {"success": True, "data": overview}
