"""
PortfolioRiskService — paper 账户组合层风险/估值指标：
- Beta vs 沪深 300（cov / var）
- VaR (1D, 95%) 历史模拟法
- 加权 PE / PB（市值加权）

OpenSpec change: portfolio-fundamentals
Spec: openspec/specs/portfolio-fundamentals/spec.md (after archive)

依赖：
- paper-account-snapshots: 账户日收益序列（PaperPerformanceService）
- IndexDataService: 沪深 300 日收益序列
- StockIndicatorService: 持仓 PE / PB
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

from app.core.database import get_mongo_db

logger = logging.getLogger(__name__)


# Beta 弹性 tag 映射
def _beta_tag(beta: float) -> str:
    if beta > 1.3:
        return "高弹性"
    if beta > 1.0:
        return "中高弹性"
    if beta > 0.7:
        return "中性"
    return "防御"


async def _get_account_returns(user_id: str, days: int = 60) -> tuple[list[str], list[float]]:
    """从 paper_account_snapshots 算账户日收益 + 对应 date 列表."""
    from app.services.paper_snapshot_service import get_paper_snapshot_service

    snapshots = await get_paper_snapshot_service().get_snapshots(user_id, days=days + 1)
    if len(snapshots) < 2:
        return [], []

    dates: list[str] = []
    returns: list[float] = []
    for i in range(1, len(snapshots)):
        prev_eq = float(snapshots[i - 1].get("equity", 0.0))
        curr_eq = float(snapshots[i].get("equity", 0.0))
        if prev_eq <= 0:
            continue
        dates.append(snapshots[i].get("date", ""))
        returns.append((curr_eq / prev_eq) - 1.0)
    return dates, returns


async def _get_aligned_index_returns(
    account_dates: list[str], symbol: str = "000300"
) -> list[float]:
    """从 IndexDataService 拿日收益，按 account_dates 对齐返回."""
    from app.services.index_data_service import get_index_data_service

    svc = get_index_data_service()
    # 多拿一些防止盘外日期不齐
    all_returns = await svc.get_index_returns(symbol, days=len(account_dates) + 30)
    all_dates = await svc.get_index_dates(symbol, days=len(account_dates) + 30)
    if not all_returns or len(all_returns) != len(all_dates):
        return []

    # 构建 date → return map
    idx_map = dict(zip(all_dates, all_returns))
    aligned: list[float] = []
    for d in account_dates:
        if d in idx_map:
            aligned.append(idx_map[d])
        else:
            aligned.append(0.0)  # 缺失日期记 0（保守）
    return aligned


async def calc_beta(user_id: str, days: int = 60) -> dict[str, Any] | None:
    """β = cov(R_account, R_HS300) / var(R_HS300).

    需 ≥ 60 天对齐的账户 + 大盘日收益序列。
    """
    account_dates, account_returns = await _get_account_returns(user_id, days)
    if len(account_returns) < 30:  # 至少 30 天才有意义
        return None

    index_returns = await _get_aligned_index_returns(account_dates)
    if not index_returns or len(index_returns) != len(account_returns):
        return None

    a = np.array(account_returns)
    h = np.array(index_returns)
    if np.var(h) == 0 or math.isnan(np.var(h)):
        return None

    cov = float(np.cov(a, h, ddof=1)[0][1])
    var = float(np.var(h, ddof=1))
    if var == 0 or math.isnan(var):
        return None

    beta = cov / var
    if math.isnan(beta) or math.isinf(beta):
        return None

    return {"value": round(beta, 4), "tag": _beta_tag(beta)}


async def calc_var(
    user_id: str, confidence: float = 0.95, days: int = 252
) -> dict[str, Any] | None:
    """历史模拟法 VaR：(account_returns 5% 分位数) × 当前 equity.

    返回 `{amount, pct}`（都是负数）。
    """
    _, account_returns = await _get_account_returns(user_id, days)
    if len(account_returns) < 30:
        return None

    arr = np.array(account_returns)
    pct = float(np.percentile(arr, (1 - confidence) * 100))
    if math.isnan(pct):
        return None

    # 拿当前 equity（最后一条 snapshot）
    from app.services.paper_snapshot_service import get_paper_snapshot_service

    snapshots = await get_paper_snapshot_service().get_snapshots(user_id, days=1)
    if not snapshots:
        return None
    equity = float(snapshots[-1].get("equity", 0.0))
    if equity <= 0:
        return None

    amount = round(equity * pct, 2)  # 负数
    return {"amount": amount, "pct": round(pct, 6)}


async def _get_paper_positions_with_mv(user_id: str) -> list[dict[str, Any]]:
    """获取 paper 持仓 + 当前市值（CN only）."""
    from app.routers.paper import _get_last_price

    db = get_mongo_db()
    positions = await db["paper_positions"].find(
        {"user_id": user_id, "market": "CN"}
    ).to_list(None)

    result: list[dict[str, Any]] = []
    for p in positions:
        code = p.get("code")
        qty = int(p.get("quantity", 0))
        if qty <= 0 or not code:
            continue
        last = await _get_last_price(code, "CN")
        if last is None or last <= 0:
            continue
        mv = qty * float(last)
        result.append({"code": code, "mkt_value": mv})
    return result


async def calc_weighted_pe(user_id: str) -> float | None:
    """加权 PE = Σ(pe_i × mv_i) / Σmv_i."""
    positions = await _get_paper_positions_with_mv(user_id)
    if not positions:
        return None

    from app.services.stock_indicator_service import get_stock_indicator_service

    codes = [p["code"] for p in positions]
    indicators = await get_stock_indicator_service().get_latest_indicators(codes)

    weighted_sum = 0.0
    total_mv = 0.0
    for p in positions:
        ind = indicators.get(p["code"])
        if not ind or ind.get("pe") is None:
            continue
        weighted_sum += float(ind["pe"]) * p["mkt_value"]
        total_mv += p["mkt_value"]
    if total_mv == 0:
        return None
    return round(weighted_sum / total_mv, 2)


async def calc_weighted_pb(user_id: str) -> float | None:
    """加权 PB = Σ(pb_i × mv_i) / Σmv_i."""
    positions = await _get_paper_positions_with_mv(user_id)
    if not positions:
        return None

    from app.services.stock_indicator_service import get_stock_indicator_service

    codes = [p["code"] for p in positions]
    indicators = await get_stock_indicator_service().get_latest_indicators(codes)

    weighted_sum = 0.0
    total_mv = 0.0
    for p in positions:
        ind = indicators.get(p["code"])
        if not ind or ind.get("pb") is None:
            continue
        weighted_sum += float(ind["pb"]) * p["mkt_value"]
        total_mv += p["mkt_value"]
    if total_mv == 0:
        return None
    return round(weighted_sum / total_mv, 2)


async def get_portfolio_metrics(user_id: str) -> dict[str, Any]:
    """聚合 Beta / VaR / 加权 PE/PB 给 endpoint."""
    return {
        "beta": await calc_beta(user_id),
        "var": await calc_var(user_id),
        "weighted_pe": await calc_weighted_pe(user_id),
        "weighted_pb": await calc_weighted_pb(user_id),
    }


__all__: list[Any] = [
    "calc_beta",
    "calc_var",
    "calc_weighted_pe",
    "calc_weighted_pb",
    "get_portfolio_metrics",
]
