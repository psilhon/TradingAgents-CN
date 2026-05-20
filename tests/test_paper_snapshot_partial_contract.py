"""Contract test for paper_snapshot_service partial-coverage 闸门.

capability paper-account-snapshots Requirement "Snapshot 写入闸门 + partial 标志"
+ data-quality-gate Req 3.

change 2026-05-20-paper-null-quote-handling — v1.3.1 hotfix.

v1.3.0 漏修：`paper_snapshot_service.take_snapshot:84-85` 用
`if last is None or last <= 0: continue` 把缺 quote 的 position 静默剔除累加，
导致 snapshot 文档的 positions_value 是"部分累加值"——后续 PaperPerformanceService
计算 TWRR/Sharpe 时把这条 partial 记录当 fully-covered 处理，污染金融指标。

新契约：partial coverage 时 positions_value/equity/unrealized_pnl 整体 None，
文档加 partial: bool + missing_quote_codes: list[str] 标志。

本 contract test 验证 `_compute_snapshot_aggregates(positions, last_prices)`
pure helper 的边界行为。
"""

from __future__ import annotations

import pytest

from app.services.paper_snapshot_service import _compute_snapshot_aggregates


@pytest.mark.unit
def test_full_coverage_returns_numeric_aggregates():
    """所有 position 都有 quote → positions_value/unrealized_pnl 数值正确，partial=false."""
    positions = [
        {"code": "000001", "quantity": 100, "avg_cost": 10.0},
        {"code": "000002", "quantity": 200, "avg_cost": 20.0},
    ]
    last_prices = {"000001": 11.0, "000002": 21.0}
    result = _compute_snapshot_aggregates(positions, last_prices)
    # positions_value = 11*100 + 21*200 = 1100 + 4200 = 5300
    assert result["positions_value"] == 5300.0
    # unrealized = (11-10)*100 + (21-20)*200 = 100 + 200 = 300
    assert result["unrealized_pnl"] == 300.0
    assert result["partial"] is False
    assert result["missing_quote_codes"] == []


@pytest.mark.unit
def test_all_missing_quote_returns_none_aggregates():
    """所有 position 缺 quote → positions_value/unrealized_pnl 全 None, partial=true."""
    positions = [
        {"code": "000001", "quantity": 100, "avg_cost": 10.0},
        {"code": "000002", "quantity": 200, "avg_cost": 20.0},
    ]
    last_prices: dict[str, float | None] = {"000001": None, "000002": None}
    result = _compute_snapshot_aggregates(positions, last_prices)
    assert result["positions_value"] is None
    assert result["unrealized_pnl"] is None
    assert result["partial"] is True
    assert set(result["missing_quote_codes"]) == {"000001", "000002"}


@pytest.mark.unit
def test_partial_coverage_returns_none_with_missing_list():
    """部分缺 quote → 整体 None（不允许部分累加），missing_codes 列出缺失."""
    positions = [
        {"code": "000001", "quantity": 100, "avg_cost": 10.0},
        {"code": "000002", "quantity": 200, "avg_cost": 20.0},
        {"code": "000003", "quantity": 300, "avg_cost": 30.0},
    ]
    last_prices = {"000001": 11.0, "000002": None, "000003": 31.0}
    result = _compute_snapshot_aggregates(positions, last_prices)
    assert result["positions_value"] is None
    assert result["unrealized_pnl"] is None
    assert result["partial"] is True
    assert result["missing_quote_codes"] == ["000002"]


@pytest.mark.unit
def test_zero_or_negative_quote_treated_as_missing():
    """last_price=0 或 <0 → 视为缺失（既有逻辑保留：异常 quote 不参与）.

    v1.3.0 旧逻辑 `if last is None or last <= 0: continue`——last<=0 应视为
    数据异常（quote 服务可能返 placeholder 0），保留此判定但归入 missing_codes。
    """
    positions = [
        {"code": "000001", "quantity": 100, "avg_cost": 10.0},
        {"code": "000002", "quantity": 200, "avg_cost": 20.0},
    ]
    last_prices = {"000001": 0.0, "000002": -5.0}  # 异常 quote
    result = _compute_snapshot_aggregates(positions, last_prices)
    assert result["partial"] is True
    assert set(result["missing_quote_codes"]) == {"000001", "000002"}
    assert result["positions_value"] is None
    assert result["unrealized_pnl"] is None


@pytest.mark.unit
def test_empty_positions_returns_zero():
    """无 position（纯现金账户 / 新账户）→ positions_value=0/unrealized_pnl=0（真零值），partial=false."""
    result = _compute_snapshot_aggregates([], {})
    assert result["positions_value"] == 0.0
    assert result["unrealized_pnl"] == 0.0
    assert result["partial"] is False
    assert result["missing_quote_codes"] == []


@pytest.mark.unit
def test_backward_compat_old_doc_missing_partial_field():
    """读旧文档无 partial 字段 → doc.get("partial", False) 不抛 KeyError.

    v1.3.0 release 之前到本 hotfix 之间所有 snapshot 文档无 partial 字段，
    PerformanceService 必须按 fully-covered 处理这些旧文档（regression guard）。
    """
    old_doc = {
        "user_id": "u",
        "date": "2026-05-15",
        "equity": 100.0,
        "cash": 50.0,
        "positions_value": 50.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
    }
    # 关键：直接 doc["partial"] 会 KeyError；必须 .get("partial", False)
    assert old_doc.get("partial", False) is False
    # missing_quote_codes 同理
    assert old_doc.get("missing_quote_codes", []) == []
