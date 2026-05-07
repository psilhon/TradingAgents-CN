"""
Tests for PortfolioRiskService 核心数学正确性。

覆盖：
- _beta_tag 4 区间映射
- calc_beta 公式（mock account + index returns）
- calc_var 历史模拟法（5% 分位数）
- calc_weighted_pe / calc_weighted_pb 加权平均
- 边界：snapshot < 30 / 持仓为空 / indicators 缺失 / index 数据空
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from app.services.portfolio_risk_service import (
    _beta_tag,
    calc_beta,
    calc_var,
    calc_weighted_pb,
    calc_weighted_pe,
)


@pytest.mark.unit
def test_beta_tag_high():
    assert _beta_tag(1.5) == "高弹性"
    assert _beta_tag(1.31) == "高弹性"


@pytest.mark.unit
def test_beta_tag_mid_high():
    assert _beta_tag(1.12) == "中高弹性"
    assert _beta_tag(1.01) == "中高弹性"
    assert _beta_tag(1.3) == "中高弹性"  # 边界


@pytest.mark.unit
def test_beta_tag_neutral():
    assert _beta_tag(0.85) == "中性"
    assert _beta_tag(1.0) == "中性"  # 边界（>0.7 但 ≤1.0）


@pytest.mark.unit
def test_beta_tag_defensive():
    assert _beta_tag(0.5) == "防御"
    assert _beta_tag(0.7) == "防御"  # 边界
    assert _beta_tag(0) == "防御"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calc_beta_too_few_snapshots():
    """< 30 天账户日收益 → None."""
    with patch(
        "app.services.portfolio_risk_service._get_account_returns",
        new=AsyncMock(return_value=([], [])),
    ):
        result = await calc_beta("u1")
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calc_beta_index_data_missing():
    """账户数据足但大盘数据空 → None."""
    fake_account = (
        ["2026-04-01", "2026-04-02"] * 20,
        [0.01] * 40,
    )
    with (
        patch(
            "app.services.portfolio_risk_service._get_account_returns",
            new=AsyncMock(return_value=fake_account),
        ),
        patch(
            "app.services.portfolio_risk_service._get_aligned_index_returns",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await calc_beta("u1")
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calc_beta_perfect_correlation():
    """账户完全跟大盘走（同向同幅度）→ β = 1.0 中性."""
    n = 60
    np.random.seed(42)
    market_returns = list(np.random.randn(n) * 0.02)
    account_returns = list(market_returns)  # identical
    dates = [f"2026-04-{i + 1:02d}" for i in range(n)]

    with (
        patch(
            "app.services.portfolio_risk_service._get_account_returns",
            new=AsyncMock(return_value=(dates, account_returns)),
        ),
        patch(
            "app.services.portfolio_risk_service._get_aligned_index_returns",
            new=AsyncMock(return_value=market_returns),
        ),
    ):
        result = await calc_beta("u1")

    assert result is not None
    assert result["value"] == pytest.approx(1.0, abs=1e-6)
    assert result["tag"] == "中性"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calc_beta_high_elasticity():
    """账户放大 1.5x 大盘 → β ≈ 1.5 高弹性."""
    n = 60
    np.random.seed(42)
    market_returns = list(np.random.randn(n) * 0.02)
    account_returns = [r * 1.5 for r in market_returns]
    dates = [f"2026-04-{i + 1:02d}" for i in range(n)]

    with (
        patch(
            "app.services.portfolio_risk_service._get_account_returns",
            new=AsyncMock(return_value=(dates, account_returns)),
        ),
        patch(
            "app.services.portfolio_risk_service._get_aligned_index_returns",
            new=AsyncMock(return_value=market_returns),
        ),
    ):
        result = await calc_beta("u1")

    assert result is not None
    assert result["value"] == pytest.approx(1.5, abs=1e-6)
    assert result["tag"] == "高弹性"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calc_var_too_few_data():
    with patch(
        "app.services.portfolio_risk_service._get_account_returns",
        new=AsyncMock(return_value=([], [])),
    ):
        result = await calc_var("u1")
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calc_var_historical_simulation():
    """历史模拟法：5% 分位数验证.

    构造 100 个 returns 服从 normal(0, 0.02)，5% 分位数应接近 -1.65σ ≈ -3.3%.
    然后 var_amount = equity × pct.
    """
    np.random.seed(42)
    returns = list(np.random.randn(100) * 0.02)
    expected_pct = float(np.percentile(np.array(returns), 5))

    fake_snapshots = [{"equity": 200000.0, "date": "2026-05-08"}]

    with (
        patch(
            "app.services.portfolio_risk_service._get_account_returns",
            new=AsyncMock(return_value=([], returns)),
        ),
        patch(
            "app.services.paper_snapshot_service.PaperSnapshotService.get_snapshots",
            new=AsyncMock(return_value=fake_snapshots),
        ),
    ):
        result = await calc_var("u1", confidence=0.95)

    assert result is not None
    assert result["pct"] == pytest.approx(expected_pct, abs=1e-4)
    assert result["amount"] == pytest.approx(200000.0 * expected_pct, abs=1.0)
    assert result["amount"] < 0  # 损失为负


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calc_weighted_pe_basic():
    """加权 PE：002428 (PE 22, MV 40k) + 000776 (PE 14, MV 60k).

    weighted = (22×40 + 14×60) / 100 = 17.2
    """
    fake_positions = [
        {"code": "002428", "mkt_value": 40000.0},
        {"code": "000776", "mkt_value": 60000.0},
    ]
    fake_indicators = {
        "002428": {"pe": 22.0, "pb": 3.0},
        "000776": {"pe": 14.0, "pb": 1.5},
    }

    with (
        patch(
            "app.services.portfolio_risk_service._get_paper_positions_with_mv",
            new=AsyncMock(return_value=fake_positions),
        ),
        patch(
            "app.services.stock_indicator_service.StockIndicatorService.get_latest_indicators",
            new=AsyncMock(return_value=fake_indicators),
        ),
    ):
        result = await calc_weighted_pe("u1")

    assert result == pytest.approx(17.2, abs=1e-2)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calc_weighted_pe_no_positions():
    """空持仓 → None."""
    with patch(
        "app.services.portfolio_risk_service._get_paper_positions_with_mv",
        new=AsyncMock(return_value=[]),
    ):
        result = await calc_weighted_pe("u1")
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calc_weighted_pe_all_indicators_missing():
    """所有持仓 indicators 缺失 → None."""
    fake_positions = [{"code": "X", "mkt_value": 1000.0}]
    with (
        patch(
            "app.services.portfolio_risk_service._get_paper_positions_with_mv",
            new=AsyncMock(return_value=fake_positions),
        ),
        patch(
            "app.services.stock_indicator_service.StockIndicatorService.get_latest_indicators",
            new=AsyncMock(return_value={}),
        ),
    ):
        result = await calc_weighted_pe("u1")
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calc_weighted_pb_basic():
    """加权 PB：相同持仓配 PB."""
    fake_positions = [
        {"code": "002428", "mkt_value": 40000.0},
        {"code": "000776", "mkt_value": 60000.0},
    ]
    fake_indicators = {
        "002428": {"pe": 22.0, "pb": 3.0},
        "000776": {"pe": 14.0, "pb": 1.5},
    }

    with (
        patch(
            "app.services.portfolio_risk_service._get_paper_positions_with_mv",
            new=AsyncMock(return_value=fake_positions),
        ),
        patch(
            "app.services.stock_indicator_service.StockIndicatorService.get_latest_indicators",
            new=AsyncMock(return_value=fake_indicators),
        ),
    ):
        result = await calc_weighted_pb("u1")

    # (3.0×40 + 1.5×60) / 100 = 2.1
    assert result == pytest.approx(2.1, abs=1e-2)
