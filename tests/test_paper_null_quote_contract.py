"""Contract test for paper router null-quote handling.

capability data-quality-gate Requirement 3 (Scenario: 后端 service 缺上游数据 MUST
返 None) + paper-account-snapshots (Scenario: partial quote coverage 处理).

change 2026-05-20-paper-null-quote-handling — v1.3.1 hotfix.

v1.3.0 release 漏修：`app/routers/paper.py:316,556` 用 `last or 0.0` 把缺 quote
的 position market_value 合成为 0，污染 mongo `paper_account_snapshots` 写入链路。

本 contract test 验证：
1. `_compute_mkt_value(last, qty)`：last=None → 返 None；last 有值 → 返 round(last*qty, 2)
2. `_compute_unrealized_pnl(last, avg_cost, qty)`：last=None → 返 None；否则返计算值
3. `_aggregate_positions_by_currency(positions_data)`：partial coverage 时
   该 currency 的 positions_value=None + missing_codes 反映缺失
4. `_compute_equity_by_currency(cash, positions_value)`：positions_value=None →
   equity=None

纯单元测试，不起 FastAPI / mongo，pre-push hook 可跑。
"""

from __future__ import annotations

import pytest

from app.routers.paper import (
    _aggregate_positions_by_currency,
    _compute_equity_by_currency,
    _compute_mkt_value,
    _compute_unrealized_pnl,
)

# ===== _compute_mkt_value =====


@pytest.mark.unit
def test_compute_mkt_value_with_quote():
    """有 last_price 时返 round(last * qty, 2)."""
    assert _compute_mkt_value(10.5, 100) == 1050.0
    assert _compute_mkt_value(12.345, 200) == 2469.0


@pytest.mark.unit
def test_compute_mkt_value_null_quote_returns_none():
    """last=None 时返 None（不允许合成为 0）.

    这是 v1.3.0 漏修的核心：`round((last or 0.0) * qty, 2)` 让 last=None 变成
    market_value=0，污染 mongo 写入链路。修复后 None 短路返 None。
    """
    assert _compute_mkt_value(None, 100) is None


@pytest.mark.unit
def test_compute_mkt_value_zero_qty():
    """qty=0（边界，理论上不应有零持仓 position）→ 仍合理返 0（真零值）."""
    assert _compute_mkt_value(10.5, 0) == 0.0


# ===== _compute_unrealized_pnl =====


@pytest.mark.unit
def test_compute_unrealized_pnl_with_quote():
    """有 last_price 时返 round((last - avg_cost) * qty, 2)."""
    # last=12, avg_cost=10, qty=100 → (12-10)*100 = 200
    assert _compute_unrealized_pnl(12.0, 10.0, 100) == 200.0
    # 浮亏：last=8, avg_cost=10, qty=100 → -200
    assert _compute_unrealized_pnl(8.0, 10.0, 100) == -200.0


@pytest.mark.unit
def test_compute_unrealized_pnl_null_quote_returns_none():
    """last=None 时返 None（不允许 0 - avg_cost = -avg_cost 这种假亏损）.

    这是 C3 PaperTrading 浮盈表达式假红色亏损的同根因——前端用 Number(null||0)
    后做减法会得到 -avg_cost*qty，本 helper 在后端保证不输出这种污染值。
    """
    assert _compute_unrealized_pnl(None, 10.0, 100) is None


# ===== _aggregate_positions_by_currency =====


@pytest.mark.unit
def test_aggregate_full_coverage_single_currency():
    """所有 position 都有 quote → positions_value 正确累加，无 missing."""
    positions = [
        ("000001", "CNY", 10.0, 100),  # mkt=1000
        ("000002", "CNY", 20.0, 200),  # mkt=4000
    ]
    result = _aggregate_positions_by_currency(positions)
    assert result["CNY"]["value"] == 5000.0
    assert result["CNY"]["missing_codes"] == []
    assert result["CNY"]["has_quote"] == 2
    assert result["CNY"]["missing"] == 0


@pytest.mark.unit
def test_aggregate_partial_coverage_single_currency():
    """部分 position 缺 quote → 该 currency value=None，missing_codes 列出."""
    positions = [
        ("000001", "CNY", 10.0, 100),  # mkt=1000
        ("000002", "CNY", None, 200),  # missing
        ("000003", "CNY", 30.0, 300),  # mkt=9000
    ]
    result = _aggregate_positions_by_currency(positions)
    # partial 时整 currency value=None（不能合成）
    assert result["CNY"]["value"] is None
    assert result["CNY"]["missing_codes"] == ["000002"]
    assert result["CNY"]["has_quote"] == 2
    assert result["CNY"]["missing"] == 1


@pytest.mark.unit
def test_aggregate_all_missing_single_currency():
    """所有 position 都缺 quote → value=None，missing_codes 全列出."""
    positions = [
        ("000001", "CNY", None, 100),
        ("000002", "CNY", None, 200),
    ]
    result = _aggregate_positions_by_currency(positions)
    assert result["CNY"]["value"] is None
    assert set(result["CNY"]["missing_codes"]) == {"000001", "000002"}
    assert result["CNY"]["has_quote"] == 0
    assert result["CNY"]["missing"] == 2


@pytest.mark.unit
def test_aggregate_empty_positions():
    """无 position → 三个 currency 都是 0 / 空 missing_codes（真零值）."""
    result = _aggregate_positions_by_currency([])
    for currency in ("CNY", "HKD", "USD"):
        assert result[currency]["value"] == 0.0
        assert result[currency]["missing_codes"] == []
        assert result[currency]["has_quote"] == 0
        assert result[currency]["missing"] == 0


@pytest.mark.unit
def test_aggregate_multi_currency_independent():
    """不同 currency 独立判定 — CNY full + HKD partial → CNY 正常，HKD=None."""
    positions = [
        ("000001", "CNY", 10.0, 100),  # CNY full
        ("00700", "HKD", None, 50),  # HKD missing → HKD bucket partial
        ("00941", "HKD", 50.0, 100),  # HKD has quote
    ]
    result = _aggregate_positions_by_currency(positions)
    assert result["CNY"]["value"] == 1000.0
    assert result["CNY"]["missing_codes"] == []
    assert result["HKD"]["value"] is None
    assert result["HKD"]["missing_codes"] == ["00700"]
    assert result["HKD"]["has_quote"] == 1
    assert result["HKD"]["missing"] == 1


# ===== _compute_equity_by_currency =====


@pytest.mark.unit
def test_compute_equity_full_coverage():
    """positions_value 非 None → equity = cash + positions_value."""
    assert _compute_equity_by_currency(1000.0, 5000.0) == 6000.0


@pytest.mark.unit
def test_compute_equity_partial_coverage_returns_none():
    """positions_value=None → equity=None（公式分量缺失 equity 不可信）.

    这是 v1.3.0 漏修的根因——`equity = cash + 失真 positions_value` 持久化
    进 mongo snapshot，后续 TWRR/Sharpe/回撤全失真。
    """
    assert _compute_equity_by_currency(1000.0, None) is None


@pytest.mark.unit
def test_compute_equity_zero_positions():
    """positions_value=0（无持仓真零值）→ equity = cash."""
    assert _compute_equity_by_currency(1000.0, 0.0) == 1000.0
