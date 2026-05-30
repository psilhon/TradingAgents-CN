import numpy as np
import pandas as pd
import pytest

from tradingagents.tools.analysis.indicators import (
    IndicatorSpec,
    compute_many,
    rsi,
)

pytestmark = pytest.mark.unit


def make_df(n=60, seed=42):
    rng = np.random.default_rng(seed)
    close = pd.Series(np.cumsum(rng.normal(0, 1, n)) + 100)
    high = close + rng.uniform(0, 2, n)
    low = close - rng.uniform(0, 2, n)
    vol = pd.Series(rng.integers(1000, 5000, n))
    amount = vol * close
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "vol": vol, "amount": amount})


def test_compute_many_basic_columns():
    df = make_df(80)
    specs = [
        IndicatorSpec("ma", {"n": 5}),
        IndicatorSpec("ma", {"n": 20}),
        IndicatorSpec("macd"),
        IndicatorSpec("rsi", {"n": 14}),
        IndicatorSpec("boll", {"n": 20, "k": 2}),
        IndicatorSpec("atr", {"n": 14}),
        IndicatorSpec("kdj", {"n": 9, "m1": 3, "m2": 3}),
    ]
    out = compute_many(df, specs)

    # 列存在
    for col in [
        "ma5",
        "ma20",
        "dif",
        "dea",
        "macd_hist",
        "rsi14",
        "boll_mid",
        "boll_upper",
        "boll_lower",
        "atr14",
        "kdj_k",
        "kdj_d",
        "kdj_j",
    ]:
        assert col in out.columns

    # 最后一行应有数值（对应窗口已满足）
    last = out.iloc[-1]
    for col in [
        "ma5",
        "ma20",
        "dif",
        "dea",
        "macd_hist",
        "rsi14",
        "boll_mid",
        "boll_upper",
        "boll_lower",
        "atr14",
        "kdj_k",
        "kdj_d",
        "kdj_j",
    ]:
        assert not pd.isna(last[col]), f"{col} should not be NaN"


def test_no_inplace_modification():
    df = make_df(40)
    out = compute_many(df, [IndicatorSpec("ma", {"n": 5})])
    assert "ma5" in out.columns and "ma5" not in df.columns


@pytest.mark.parametrize("method", ["ema", "sma", "china"])
def test_rsi_all_gains_is_100_not_nan(method):
    """全程上涨（无下跌）时 RSI 应为 100（最大超买），而非 NaN。

    回归：avg_loss==0 时 rs = avg_gain / 0 -> 此前用 .replace(0, NaN) 把
    分母变 NaN -> RSI=NaN，丢失"满超买"语义。标准 RSI 约定零损失 = 100。
    """
    close = pd.Series([float(i) for i in range(1, 21)])  # 单调递增
    out = rsi(close, n=14, method=method)
    last = out.iloc[-1]
    assert not pd.isna(last), f"method={method}: 全涨窗口 RSI 不应为 NaN"
    assert last == pytest.approx(100.0), f"method={method}: 全涨窗口 RSI 应为 100，实得 {last}"


def test_rsi_stays_in_range_with_mixed_moves():
    """有涨有跌时 RSI 落在 (0, 100) 开区间内（不退化、不越界）。"""
    close = pd.Series([100, 101, 100, 102, 101, 103, 102, 104, 103, 105, 104, 106, 105, 107, 106, 108])
    out = rsi(close, n=14, method="ema")
    last = out.iloc[-1]
    assert not pd.isna(last)
    assert 0.0 < last < 100.0
