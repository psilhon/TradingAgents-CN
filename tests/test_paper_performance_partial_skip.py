"""Contract test for PaperPerformanceService 跳过 partial=true 日期.

capability paper-account-snapshots Scenario "partial=true 日期被跳过" +
"过滤后 snapshot 数不足" + "旧文档无 partial 字段".

change 2026-05-20-paper-null-quote-handling — v1.3.1 hotfix.

paper-account-snapshots 文档新增 partial: bool 字段后，PerformanceService
计算 TWRR/Sharpe/回撤/月度收益时 MUST 过滤掉 partial=true 的日期（这些日期
equity=None 不可信，参与计算会污染金融指标）。

backward compat：旧文档无 partial 字段 → 按 fully-covered 处理（doc.get(
"partial", False)），保持 v1.3.0 行为。
"""

from __future__ import annotations

import pytest

from app.services.paper_performance_service import (
    _filter_valid_snapshots,
    calc_drawdowns,
    calc_monthly_returns,
    calc_sharpe,
    calc_twrr,
)

# ===== _filter_valid_snapshots =====


@pytest.mark.unit
def test_filter_drops_partial_snapshots():
    """partial=true 的 snapshot 被过滤掉."""
    snapshots = [
        {"date": "2026-05-15", "equity": 100.0, "partial": False},
        {"date": "2026-05-16", "equity": None, "partial": True},
        {"date": "2026-05-17", "equity": 110.0, "partial": False},
    ]
    result = _filter_valid_snapshots(snapshots)
    assert len(result) == 2
    assert [s["date"] for s in result] == ["2026-05-15", "2026-05-17"]


@pytest.mark.unit
def test_filter_drops_none_equity_even_if_partial_false():
    """equity=None 即使 partial=false（防御）也被过滤."""
    snapshots = [
        {"date": "2026-05-15", "equity": 100.0, "partial": False},
        {"date": "2026-05-16", "equity": None, "partial": False},  # 异常但防御
    ]
    result = _filter_valid_snapshots(snapshots)
    assert len(result) == 1
    assert result[0]["date"] == "2026-05-15"


@pytest.mark.unit
def test_filter_backward_compat_old_doc_no_partial_field():
    """旧文档无 partial 字段 → doc.get('partial', False) → 按 fully-covered 处理."""
    snapshots = [
        {"date": "2026-05-10", "equity": 100.0},  # v1.3.0 文档无 partial 字段
        {"date": "2026-05-11", "equity": 105.0},
        {"date": "2026-05-12", "equity": 110.0},
    ]
    result = _filter_valid_snapshots(snapshots)
    # 全部保留（regression guard v1.3.0 行为）
    assert len(result) == 3


@pytest.mark.unit
def test_filter_empty_input():
    """空输入 → 空输出，不抛异常."""
    assert _filter_valid_snapshots([]) == []


# ===== calc_X 行为 in presence of partial =====


@pytest.mark.unit
def test_calc_twrr_with_filtered_equity_serie():
    """calc_twrr 接 list[float] 参数（已过滤过）→ 正常计算.

    [100, 110, 121] → daily_returns [0.10, 0.10] → TWRR = 1.10*1.10 - 1 = 0.21
    """
    assert calc_twrr([100.0, 110.0, 121.0]) == pytest.approx(0.21, abs=1e-9)


@pytest.mark.unit
def test_calc_sharpe_too_few_after_filter():
    """过滤后 < 2 → calc_sharpe 返回 None（既有边界 regression guard）."""
    assert calc_sharpe([100.0]) is None
    assert calc_sharpe([]) is None


@pytest.mark.unit
def test_calc_drawdowns_too_few_after_filter():
    """过滤后 < 2 → calc_drawdowns 返 {None, None}."""
    result = calc_drawdowns([100.0])
    assert result["current_drawdown"] is None
    assert result["max_drawdown"] is None


@pytest.mark.unit
def test_calc_monthly_returns_skips_partial_rows():
    """calc_monthly_returns 看 snapshots 文档列表，必须跳过 partial=true 的行.

    若不跳过，含 None equity 会让 float() 抛 TypeError 或污染月度聚合。
    """
    snapshots = [
        {"date": "2026-04-30", "equity": 100.0, "partial": False},
        {"date": "2026-05-01", "equity": None, "partial": True},  # 不应参与
        {"date": "2026-05-31", "equity": 110.0, "partial": False},
    ]
    result = calc_monthly_returns(snapshots)
    # 应有 2026-04 + 2026-05 两个月，partial 行不参与
    months = {r["month"] for r in result}
    assert months == {"2026-04", "2026-05"}
    # 不抛 TypeError（核心 regression guard）


@pytest.mark.unit
def test_calc_monthly_returns_all_partial_returns_empty():
    """所有 snapshot 都 partial=true → monthly_returns 空（< 2 not enough valid 日期）."""
    snapshots = [
        {"date": "2026-05-15", "equity": None, "partial": True},
        {"date": "2026-05-16", "equity": None, "partial": True},
    ]
    result = calc_monthly_returns(snapshots)
    assert result == []
