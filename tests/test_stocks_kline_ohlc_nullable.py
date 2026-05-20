"""Contract test for stocks.py K-line OHLC nullable handling.

capability data-quality-gate Req 3 Scenario "后端 service 缺上游数据 MUST 返 None".

change 2026-05-20-paper-null-quote-handling — v1.3.1 hotfix (W3).

v1.3.0 漏修 W3：`app/routers/stocks.py:545-549,616-621` 用 `float(row.get("open", 0))`
缺字段补 0，停牌日 / 部分写入文档时 OHLC 全 0 → 前端 K 线渲染一根从天上掉到
地面的假阴线影线。

新契约：缺字段返 None；前端 K 线 component 在某根 candle OHLC 任一为 None 时
跳过渲染该 bar。

本 contract test 验证 `_safe_float(v)` pure helper：
- None / missing → None
- 0.0 / 真零 → 0.0（保留真零语义）
- 普通数值 → float(v)
"""

from __future__ import annotations

import pytest

from app.routers.stocks import _safe_float


@pytest.mark.unit
def test_safe_float_none_returns_none():
    """None → None（不强转 0.0）."""
    assert _safe_float(None) is None


@pytest.mark.unit
def test_safe_float_zero_returns_zero():
    """0 / 0.0 → 0.0（真零值，不当 missing）."""
    assert _safe_float(0) == 0.0
    assert _safe_float(0.0) == 0.0


@pytest.mark.unit
def test_safe_float_positive_number():
    """正数 → float."""
    assert _safe_float(10) == 10.0
    assert _safe_float(10.5) == 10.5


@pytest.mark.unit
def test_safe_float_negative_number():
    """负数 → float（停牌日可能有负 close？防御）."""
    assert _safe_float(-1.5) == -1.5


@pytest.mark.unit
def test_safe_float_string_numeric():
    """字符串数字 → float（mongo BSON 偶尔返字符串）."""
    assert _safe_float("12.34") == 12.34


@pytest.mark.unit
def test_safe_float_invalid_string_returns_none():
    """非数字字符串 → None（不应抛 ValueError）."""
    assert _safe_float("abc") is None
    assert _safe_float("") is None


@pytest.mark.unit
def test_safe_float_nan_returns_none():
    """NaN → None（防御 pandas float('nan') 渗透）."""
    assert _safe_float(float("nan")) is None
