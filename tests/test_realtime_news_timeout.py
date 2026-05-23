"""dataflows-reliability stage 1.1 — realtime_news timeout hotfix.

Verify that `RealtimeNewsAggregator._get_finnhub_realtime_news` /
`_get_alpha_vantage_news` / `_get_newsapi_news` each pass `timeout=(10, 30)`
to `requests.get`, matching the `news/google_news.py:46` convention.

Without timeout, FinnHub / Alpha Vantage / NewsAPI failures (network
partition / DNS / API hang) would block the agent chain indefinitely.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_response_mock(json_payload):
    """Build a MagicMock that behaves like a successful requests.Response."""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = json_payload
    return resp


@pytest.fixture
def aggregator(monkeypatch):
    """RealtimeNewsAggregator with all three API keys populated (so each
    method enters its try block instead of early-returning on missing key).
    """
    # Import inside fixture so monkeypatch env happens before module reads
    monkeypatch.setenv("FINNHUB_API_KEY", "test-finnhub-key")
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-av-key")
    monkeypatch.setenv("NEWSAPI_KEY", "test-newsapi-key")
    from tradingagents.dataflows.news.realtime_news import RealtimeNewsAggregator

    return RealtimeNewsAggregator()


def _assert_timeout_in_call(mock_get) -> None:
    """Assert requests.get was called with `timeout=(10, 30)`."""
    assert mock_get.called, "requests.get should have been called"
    call = mock_get.call_args
    # timeout could be passed positionally or as kwarg — check kwargs first
    timeout = call.kwargs.get("timeout")
    assert timeout is not None, f"requests.get MUST be called with timeout= keyword arg; got args={call.args}, kwargs={call.kwargs}"
    assert timeout == (10, 30), f"expected timeout=(10, 30), got {timeout!r}"


def test_finnhub_realtime_news_passes_timeout(aggregator) -> None:
    """`_get_finnhub_realtime_news` MUST pass timeout=(10, 30) to requests.get."""
    with patch("tradingagents.dataflows.news.realtime_news.requests.get") as mock_get:
        mock_get.return_value = _make_response_mock([])  # empty news list
        aggregator._get_finnhub_realtime_news("AAPL", hours_back=6)
        _assert_timeout_in_call(mock_get)


def test_alpha_vantage_news_passes_timeout(aggregator) -> None:
    """`_get_alpha_vantage_news` MUST pass timeout=(10, 30) to requests.get."""
    with patch("tradingagents.dataflows.news.realtime_news.requests.get") as mock_get:
        mock_get.return_value = _make_response_mock({"feed": []})
        aggregator._get_alpha_vantage_news("AAPL", hours_back=6)
        _assert_timeout_in_call(mock_get)


def test_newsapi_news_passes_timeout(aggregator) -> None:
    """`_get_newsapi_news` MUST pass timeout=(10, 30) to requests.get."""
    with patch("tradingagents.dataflows.news.realtime_news.requests.get") as mock_get:
        mock_get.return_value = _make_response_mock({"articles": []})
        aggregator._get_newsapi_news("AAPL", hours_back=6)
        _assert_timeout_in_call(mock_get)


def test_all_three_calls_use_same_timeout_constant() -> None:
    """Source-level: grep `realtime_news.py` MUST show 3 `requests.get(` matches
    each with `timeout=(10, 30)` — guards against future regressions where
    a new fetch method is added without timeout.

    This catches the case where someone adds a 4th _get_xxx_news method that
    forgets the timeout kwarg — pure mock-based tests above wouldn't see it.
    """
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "tradingagents" / "dataflows" / "news" / "realtime_news.py"
    text = src.read_text()
    # Count requests.get( occurrences in source (excluding comments)
    lines = [line for line in text.splitlines() if "requests.get(" in line and not line.lstrip().startswith("#")]
    assert len(lines) >= 3, f"expected ≥ 3 `requests.get(` call sites, found {len(lines)}"
    for line in lines:
        # Each line MUST contain timeout= (single-line calls); if a call
        # spans multiple lines this test will fail and signal the need to
        # extend the source-scan to multi-line matching.
        assert "timeout=" in line, f"requests.get() call in realtime_news.py missing timeout= kwarg: {line.strip()}"
