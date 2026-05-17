"""
Tests for StockIndicatorService._fetch_latest_indicator.

Regression: akshare 1.18.x removed `stock_a_indicator_lg`. The PE/PB fetch must
use `stock_zh_valuation_baidu`, which returns a per-indicator (date, value)
time series — one call for 市盈率(TTM), one for 市净率.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from app.services.stock_indicator_service import StockIndicatorService


def _baidu_stub(pe_rows=None, pb_rows=None):
    """Build a fake stock_zh_valuation_baidu that returns per-indicator frames."""

    def _fake(symbol, indicator, period):
        if indicator == "市盈率(TTM)":
            return pd.DataFrame(pe_rows if pe_rows is not None else [])
        if indicator == "市净率":
            return pd.DataFrame(pb_rows if pb_rows is not None else [])
        raise AssertionError(f"unexpected indicator: {indicator}")

    return _fake


@pytest.mark.unit
def test_fetch_latest_indicator_parses_latest_pe_pb():
    """_fetch_latest_indicator takes the last row of each indicator series."""
    pe_rows = [
        {"date": date(2026, 5, 15), "value": 30.0},
        {"date": date(2026, 5, 16), "value": 31.5},
    ]
    pb_rows = [
        {"date": date(2026, 5, 15), "value": 3.0},
        {"date": date(2026, 5, 16), "value": 3.2},
    ]
    with patch(
        "akshare.stock_zh_valuation_baidu",
        side_effect=_baidu_stub(pe_rows, pb_rows),
    ):
        result = StockIndicatorService._fetch_latest_indicator("002428")

    assert result == {"date": "2026-05-16", "pe_ttm": 31.5, "pb": 3.2}


@pytest.mark.unit
def test_fetch_latest_indicator_empty_pe_returns_none():
    """An empty PE series means no usable data — return None."""
    with patch(
        "akshare.stock_zh_valuation_baidu",
        side_effect=_baidu_stub(pe_rows=[], pb_rows=[{"date": date(2026, 5, 16), "value": 3.2}]),
    ):
        assert StockIndicatorService._fetch_latest_indicator("002428") is None


@pytest.mark.unit
def test_fetch_latest_indicator_nan_value_becomes_none():
    """A NaN PE value is sanitised to None (loss-making stocks etc.)."""
    pe_rows = [{"date": date(2026, 5, 16), "value": float("nan")}]
    pb_rows = [{"date": date(2026, 5, 16), "value": 3.2}]
    with patch(
        "akshare.stock_zh_valuation_baidu",
        side_effect=_baidu_stub(pe_rows, pb_rows),
    ):
        result = StockIndicatorService._fetch_latest_indicator("002428")

    assert result is not None
    assert result["pe_ttm"] is None
    assert result["pb"] == 3.2
