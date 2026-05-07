"""
PaperPerformanceService — 基于 paper_account_snapshots 时间序列计算专业绩效
指标：TWRR / Sharpe / 当前&最大回撤 / 月度收益。

OpenSpec change: paper-account-snapshots
Spec: openspec/specs/paper-account-snapshots/spec.md (after archive)

数学公式严格符合金融行业标准：
- daily_return: r_t = (E_t / E_{t-1}) - 1
- TWRR: ∏(1 + r_t) - 1
- Sharpe (annualized): (mean(r) × 252 - rf) / (std(r) × √252)
- max_drawdown: max over t of [(peak_t - trough_t) / peak_t]
- monthly_return: 按月分组，(E_last / E_first) - 1
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from typing import Any

import numpy as np

from app.services.paper_snapshot_service import get_paper_snapshot_service

logger = logging.getLogger(__name__)

# 默认参数
DEFAULT_RF = 0.02  # 无风险利率：2% 年化（A 股常用基准）
TRADING_DAYS_PER_YEAR = 252


def _calc_daily_returns(equities: list[float]) -> list[float]:
    """从 equity 序列算日收益率 [r_1, r_2, ..., r_{N-1}]."""
    if len(equities) < 2:
        return []
    returns: list[float] = []
    for i in range(1, len(equities)):
        prev = equities[i - 1]
        curr = equities[i]
        if prev <= 0:
            continue
        returns.append((curr / prev) - 1.0)
    return returns


def calc_twrr(equities: list[float]) -> float | None:
    """时间加权收益率 = ∏(1 + r_t) - 1.

    返回小数（0.186 = 18.6%）。snapshot < 2 返回 None.
    """
    returns = _calc_daily_returns(equities)
    if not returns:
        return None
    cumulative = 1.0
    for r in returns:
        cumulative *= 1 + r
    return cumulative - 1.0


def calc_sharpe(equities: list[float], rf: float = DEFAULT_RF) -> float | None:
    """年化 Sharpe 比率 = (annual_return - rf) / annual_vol.

    标准公式：
    - annual_return = mean(daily_returns) × 252
    - annual_vol = std(daily_returns) × √252

    边界：std=0 (无波动) 返回 None 避免除零。
    """
    returns = _calc_daily_returns(equities)
    if len(returns) < 2:
        return None
    arr = np.array(returns)
    std = float(np.std(arr, ddof=1))  # 样本标准差
    if std == 0 or math.isnan(std):
        return None
    mean = float(np.mean(arr))
    annual_return = mean * TRADING_DAYS_PER_YEAR
    annual_vol = std * math.sqrt(TRADING_DAYS_PER_YEAR)
    sharpe = (annual_return - rf) / annual_vol
    if math.isnan(sharpe) or math.isinf(sharpe):
        return None
    return round(sharpe, 4)


def calc_drawdowns(equities: list[float]) -> dict[str, float | None]:
    """扫一次得到当前回撤 + 最大回撤."""
    if len(equities) < 2:
        return {"current_drawdown": None, "max_drawdown": None}

    peak = equities[0]
    max_dd = 0.0
    for e in equities:
        if e > peak:
            peak = e
        if peak > 0:
            dd = (e - peak) / peak  # 负数
            if dd < max_dd:
                max_dd = dd

    # 当前回撤：最后一点距历史峰值
    final_peak = max(equities)
    current_dd = 0.0
    if final_peak > 0:
        current_dd = (equities[-1] - final_peak) / final_peak

    return {
        "current_drawdown": round(current_dd, 6),
        "max_drawdown": round(max_dd, 6),
    }


def calc_monthly_returns(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按月聚合：每月 return = (E_last / E_first) - 1.

    snapshots 按 date 升序。返回 [{month: "2026-04", return_pct: 4.8}, ...]
    最近 N 月（不限制，前端自决定截断）。
    """
    if len(snapshots) < 2:
        return []

    # 按月分组
    by_month: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for s in snapshots:
        d = s.get("date", "")
        eq = s.get("equity")
        if not d or eq is None or len(d) < 7:
            continue
        month = d[:7]  # "2026-04"
        by_month[month].append((d, float(eq)))

    result: list[dict[str, Any]] = []
    for month in sorted(by_month.keys()):
        items = sorted(by_month[month], key=lambda x: x[0])
        if len(items) < 1:
            continue
        first_eq = items[0][1]
        last_eq = items[-1][1]
        if first_eq <= 0:
            continue
        ret_pct = ((last_eq / first_eq) - 1.0) * 100
        result.append({"month": month, "return_pct": round(ret_pct, 2)})
    return result


def _sample_sparkline_points(equities: list[float], target: int = 11) -> list[float]:
    """从 N 个 equity 等距采样 target 个点（含首尾）."""
    n = len(equities)
    if n == 0:
        return []
    if n <= target:
        return list(equities)
    indices = np.linspace(0, n - 1, target, dtype=int)
    return [float(equities[int(i)]) for i in indices]


async def get_overview(user_id: str, days: int = 90) -> dict[str, Any]:
    """聚合所有指标 + sparkline 11 点供前端使用."""
    svc = get_paper_snapshot_service()
    snapshots = await svc.get_snapshots(user_id, days=days)

    if len(snapshots) < 2:
        return {
            "twrr": None,
            "sharpe": None,
            "current_drawdown": None,
            "max_drawdown": None,
            "monthly_returns": [],
            "sparkline_points": [],
        }

    equities = [float(s.get("equity", 0.0)) for s in snapshots]

    drawdowns = calc_drawdowns(equities)
    return {
        "twrr": calc_twrr(equities),
        "sharpe": calc_sharpe(equities),
        "current_drawdown": drawdowns["current_drawdown"],
        "max_drawdown": drawdowns["max_drawdown"],
        "monthly_returns": calc_monthly_returns(snapshots),
        "sparkline_points": _sample_sparkline_points(equities, target=11),
    }


__all__: list[Any] = [
    "calc_twrr",
    "calc_sharpe",
    "calc_drawdowns",
    "calc_monthly_returns",
    "get_overview",
]
