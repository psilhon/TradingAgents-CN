"""dataflows-reliability stage 1.4 — yfinance.Ticker LRU cache.

Verify that `yfinance.py` exposes a module-level `_get_ticker(symbol)` helper
wrapped in `functools.lru_cache(maxsize=128)`, and that the 3 historical
construction sites (`init_ticker` decorator + 2 standalone module functions)
all route through it.

Without caching, every method call on `YFinanceUtils.get_*` reconstructs a
`yf.Ticker(symbol)` instance — yfinance internal session setup (HTTP
client / cookie / proxy detection) runs each time. A typical agent request
touches `history` + `info` + `dividends` + `financials` on the same ticker;
caching lets all of these share one Ticker.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def yf_module(monkeypatch):
    """Import yfinance.py with `yf.Ticker` spied; clear LRU between tests
    so a previously-cached symbol doesn't bleed into the next test.
    """
    from tradingagents.dataflows.providers.us import yfinance as yf_mod

    # Spy yf.Ticker as MagicMock factory so we can count construction calls
    # and inspect the args each construction received.
    ticker_factory = MagicMock(side_effect=lambda symbol: MagicMock(name=f"Ticker({symbol})"))
    monkeypatch.setattr(yf_mod.yf, "Ticker", ticker_factory)

    # Clear the LRU cache before each test (otherwise prior test's cached
    # ticker instances persist and ctor count stays at 0 in this test).
    if hasattr(yf_mod, "_get_ticker"):
        yf_mod._get_ticker.cache_clear()

    yield yf_mod, ticker_factory

    # Tear-down: clear cache again so the next test gets a clean slate
    if hasattr(yf_mod, "_get_ticker"):
        yf_mod._get_ticker.cache_clear()


# --- 1.4: _get_ticker helper exists + LRU caches by symbol ---


def test_get_ticker_helper_exists(yf_module) -> None:
    """`yfinance.py` MUST expose module-level `_get_ticker(symbol)` helper."""
    yf_mod, _ = yf_module
    assert hasattr(yf_mod, "_get_ticker"), "module MUST expose _get_ticker(symbol) helper"
    assert callable(yf_mod._get_ticker), "_get_ticker MUST be callable"


def test_get_ticker_uses_lru_cache(yf_module) -> None:
    """`_get_ticker` MUST be decorated with functools.lru_cache (maxsize=128)."""
    yf_mod, _ = yf_module
    # functools.lru_cache wraps the function with a `cache_info()` introspection
    # method — direct callable still works but has __wrapped__ + cache_info
    assert hasattr(yf_mod._get_ticker, "cache_info"), "_get_ticker MUST be wrapped in functools.lru_cache (missing cache_info attr)"
    assert hasattr(yf_mod._get_ticker, "cache_clear")
    info = yf_mod._get_ticker.cache_info()
    assert info.maxsize == 128, f"expected maxsize=128, got {info.maxsize}"


def test_get_ticker_same_symbol_caches(yf_module) -> None:
    """Repeated `_get_ticker(symbol)` for the same symbol MUST hit cache (ctor called once)."""
    yf_mod, ticker_factory = yf_module
    a = yf_mod._get_ticker("AAPL")
    b = yf_mod._get_ticker("AAPL")
    c = yf_mod._get_ticker("AAPL")
    assert a is b is c, "same-symbol calls MUST return the same cached Ticker instance"
    assert ticker_factory.call_count == 1, (
        f"yf.Ticker should be constructed once for repeated same-symbol calls, got {ticker_factory.call_count}"
    )


def test_get_ticker_different_symbols_independent(yf_module) -> None:
    """Different symbols MUST each construct their own ticker."""
    yf_mod, ticker_factory = yf_module
    yf_mod._get_ticker("AAPL")
    yf_mod._get_ticker("TSLA")
    yf_mod._get_ticker("NVDA")
    assert ticker_factory.call_count == 3, "each distinct symbol MUST trigger ctor once"


def test_get_ticker_case_insensitive(yf_module) -> None:
    """`_get_ticker('aapl')` and `_get_ticker('AAPL')` MUST hit the same cache slot."""
    yf_mod, ticker_factory = yf_module
    lower = yf_mod._get_ticker("aapl")
    upper = yf_mod._get_ticker("AAPL")
    mixed = yf_mod._get_ticker("AaPl")
    assert lower is upper is mixed, "case-mixed same symbol MUST share one cached Ticker"
    assert ticker_factory.call_count == 1, f"case-insensitive normalize MUST yield 1 ctor call, got {ticker_factory.call_count}"
    # Verify ctor was called with normalized (upper) form
    ticker_factory.assert_called_with("AAPL")


# --- 1.4: init_ticker decorator routes through _get_ticker ---


def test_init_ticker_decorator_uses_get_ticker(yf_module) -> None:
    """`init_ticker` decorator MUST construct ticker via `_get_ticker` helper.

    Source-level grep: the decorator body should reference `_get_ticker`
    (not raw `yf.Ticker(symbol)`). Catches regressions where someone reverts
    to the direct ctor pattern.
    """
    yf_mod, _ = yf_module
    from pathlib import Path

    src = Path(yf_mod.__file__).read_text()
    # Find the init_ticker function body — should call _get_ticker, NOT yf.Ticker directly
    # Find lines between `def init_ticker(` and the next `def ` or `class `
    lines = src.splitlines()
    in_func = False
    func_body = []
    for line in lines:
        if line.startswith("def init_ticker"):
            in_func = True
            continue
        if in_func:
            if line.startswith("def ") or line.startswith("class ") or line.startswith("@"):
                break
            func_body.append(line)
    body_text = "\n".join(func_body)
    assert "_get_ticker" in body_text, "init_ticker decorator body MUST call _get_ticker(symbol), not yf.Ticker(symbol) directly"
    # Should NOT have raw yf.Ticker() construction in the decorator body
    assert "yf.Ticker(" not in body_text, f"init_ticker MUST route through _get_ticker, not call yf.Ticker directly. Body:\n{body_text}"


def test_no_direct_yf_ticker_construction_outside_helper() -> None:
    """Source-level grep: only `_get_ticker` may call `yf.Ticker(`; other call
    sites MUST be migrated to the helper.

    Allowed: 1 line inside `def _get_ticker(...)` body. Everywhere else MUST
    be `_get_ticker(symbol)`.
    """
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "tradingagents" / "dataflows" / "providers" / "us" / "yfinance.py"
    text = src.read_text()
    lines = text.splitlines()

    yf_ticker_lines = [(i, line) for i, line in enumerate(lines, start=1) if "yf.Ticker(" in line and not line.lstrip().startswith("#")]
    # We expect exactly 1 occurrence — inside the _get_ticker helper.
    assert len(yf_ticker_lines) == 1, (
        f"expected exactly 1 `yf.Ticker(` call site (inside _get_ticker helper); found {len(yf_ticker_lines)}:\n"
        + "\n".join(f"  line {i}: {line.strip()}" for i, line in yf_ticker_lines)
    )
    # That one occurrence must be inside _get_ticker
    only_line_num, _ = yf_ticker_lines[0]
    # Scan backwards for nearest def — must be _get_ticker
    enclosing_def = None
    for i in range(only_line_num - 1, -1, -1):
        line = lines[i]
        if line.startswith("def "):
            enclosing_def = line
            break
    assert enclosing_def is not None and "_get_ticker" in enclosing_def, (
        f"`yf.Ticker(` at line {only_line_num} is not inside _get_ticker helper; enclosing def: {enclosing_def!r}"
    )
