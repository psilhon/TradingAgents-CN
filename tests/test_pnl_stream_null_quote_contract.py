"""Contract test for pnl_stream_service null-quote handling.

capability data-quality-gate Requirement 3 (Scenario: 后端 service 缺上游数据 MUST
返 None) + realtime-trading-data-flow.

change 2026-05-20-paper-null-quote-handling — v1.3.1 hotfix.

v1.3.0 release 漏修 C5：`app/services/pnl_stream_service.py:104-117` 用 `mkt_value
= 0.0 / unrealized = 0.0` 当 last_price=None 时兜底，导致 ws push payload 把缺
quote 的 position market_value/unrealized_pnl 合成为 0，前端 store 消费者渲染
假 ¥0.00。

本 contract test 验证 `_aggregate_pnl_positions(positions, quotes)` 纯 helper：
- 全 null 上游 → payload 字段全 None / partial=true / missing_codes 列出
- 部分 null → 聚合跳过 None，coverage 反映 missing count
- 全 valid → regression guard，行为与 v1.3.0 一致
"""

from __future__ import annotations

import pytest

from app.services.pnl_stream_service import _aggregate_pnl_positions


@pytest.mark.unit
def test_aggregate_full_coverage():
    """所有 position 都有 quote → total/positions_value 正确数值，partial=false."""
    positions = [
        {"code": "000001", "quantity": 100, "avg_cost": 10.0},
        {"code": "000002", "quantity": 200, "avg_cost": 20.0},
    ]
    quotes = {
        "000001": {"close": 11.0, "last_price_as_of": "2026-05-20T10:00:00"},
        "000002": {"close": 21.0, "last_price_as_of": "2026-05-20T10:00:00"},
    }
    result = _aggregate_pnl_positions(positions, quotes)
    # mkt_value = 11*100 + 21*200 = 1100 + 4200 = 5300
    assert result["positions_value"] == 5300.0
    # unrealized = (11-10)*100 + (21-20)*200 = 100 + 200 = 300
    assert result["total_unrealized"] == 300.0
    assert result["quote_coverage"]["partial"] is False
    assert result["quote_coverage"]["missing_codes"] == []
    assert result["quote_coverage"]["has_quote"] == 2
    assert result["quote_coverage"]["missing"] == 0
    # position_records 每条字段正确
    assert len(result["position_records"]) == 2
    assert result["position_records"][0]["market_value"] == 1100.0
    assert result["position_records"][0]["unrealized_pnl"] == 100.0


@pytest.mark.unit
def test_aggregate_all_null_quotes():
    """所有 position last_price=None → total_unrealized/positions_value 全 None.

    这是 C5 修复的核心 — 必须切断 ws push 把 0.0 当真值广播的污染路径。
    """
    positions = [
        {"code": "000001", "quantity": 100, "avg_cost": 10.0},
        {"code": "000002", "quantity": 200, "avg_cost": 20.0},
    ]
    quotes: dict[str, dict] = {}  # 全缺 quote
    result = _aggregate_pnl_positions(positions, quotes)
    # 关键断言：聚合字段必须 None，绝对不能是 0.0
    assert result["positions_value"] is None
    assert result["total_unrealized"] is None
    assert result["quote_coverage"]["partial"] is True
    assert set(result["quote_coverage"]["missing_codes"]) == {"000001", "000002"}
    assert result["quote_coverage"]["has_quote"] == 0
    assert result["quote_coverage"]["missing"] == 2
    # 每条 position_records 的 market_value/unrealized_pnl 也是 None
    for rec in result["position_records"]:
        assert rec["market_value"] is None
        assert rec["unrealized_pnl"] is None
        assert rec["last_price"] is None


@pytest.mark.unit
def test_aggregate_partial_null_quotes():
    """部分缺 quote → 聚合跳过 None（不当 0），missing_codes 反映缺失."""
    positions = [
        {"code": "000001", "quantity": 100, "avg_cost": 10.0},  # has quote
        {"code": "000002", "quantity": 200, "avg_cost": 20.0},  # missing
        {"code": "000003", "quantity": 300, "avg_cost": 30.0},  # has quote
    ]
    quotes = {
        "000001": {"close": 11.0, "last_price_as_of": "2026-05-20T10:00:00"},
        "000003": {"close": 31.0, "last_price_as_of": "2026-05-20T10:00:00"},
    }
    result = _aggregate_pnl_positions(positions, quotes)
    # partial coverage 时 positions_value 和 total_unrealized 整体 None（前端
    # 知情后做视觉降级；不允许部分合成）
    assert result["positions_value"] is None
    assert result["total_unrealized"] is None
    assert result["quote_coverage"]["partial"] is True
    assert result["quote_coverage"]["missing_codes"] == ["000002"]
    assert result["quote_coverage"]["has_quote"] == 2
    assert result["quote_coverage"]["missing"] == 1
    # 但每条 position_records 字段独立 None / 有值
    recs_by_code = {r["code"]: r for r in result["position_records"]}
    assert recs_by_code["000001"]["market_value"] == 1100.0
    assert recs_by_code["000001"]["unrealized_pnl"] == 100.0
    assert recs_by_code["000002"]["market_value"] is None
    assert recs_by_code["000002"]["unrealized_pnl"] is None
    assert recs_by_code["000003"]["market_value"] == 9300.0
    assert recs_by_code["000003"]["unrealized_pnl"] == 300.0


@pytest.mark.unit
def test_aggregate_empty_positions():
    """无 position → positions_value=0/total_unrealized=0（真零值），partial=false."""
    result = _aggregate_pnl_positions([], {})
    assert result["positions_value"] == 0.0
    assert result["total_unrealized"] == 0.0
    assert result["position_records"] == []
    assert result["quote_coverage"]["partial"] is False
    assert result["quote_coverage"]["missing_codes"] == []


@pytest.mark.unit
def test_aggregate_zero_qty_position():
    """qty=0 position → mkt_value=0/unrealized=0（真零值，不算 missing）.

    边界场景，理论上零持仓 position 不应出现，但若出现应当 well-defined。
    """
    positions = [{"code": "000001", "quantity": 0, "avg_cost": 10.0}]
    quotes = {"000001": {"close": 11.0, "last_price_as_of": "2026-05-20T10:00:00"}}
    result = _aggregate_pnl_positions(positions, quotes)
    assert result["positions_value"] == 0.0
    assert result["total_unrealized"] == 0.0
    assert result["quote_coverage"]["partial"] is False
