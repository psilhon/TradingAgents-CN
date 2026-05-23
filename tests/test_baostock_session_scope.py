"""dataflows-reliability stage 1.3 — baostock session lifecycle scope.

Verify that `tradingagents/dataflows/providers/china/baostock.py` consolidates
the previously-scattered `bs.login()` / `bs.logout()` calls (12 sites each)
into a single `_BaoStockSession.scope()` context manager that uses
threading.Lock + refcount to share one session across concurrent / nested
callers.

Without this consolidation, baostock's process-level session semantics cause
one thread's `bs.logout()` to invalidate another thread's active query.
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

_BAOSTOCK_PY = Path(__file__).resolve().parents[1] / "tradingagents" / "dataflows" / "providers" / "china" / "baostock.py"


@pytest.fixture(autouse=True)
def reset_session_state():
    """Reset _BaoStockSession class-level state between tests (avoid pollution)."""
    try:
        from tradingagents.dataflows.providers.china.baostock import _BaoStockSession

        _BaoStockSession._refcount = 0
        _BaoStockSession._logged_in = False
        yield
        _BaoStockSession._refcount = 0
        _BaoStockSession._logged_in = False
    except ImportError:
        # Pre-implementation: class doesn't exist yet — let source-level
        # tests fail meaningfully; behavior tests will be skipped.
        yield


# --- Source-level guards ---


def test_session_class_exists() -> None:
    """`_BaoStockSession` class MUST be defined in baostock.py."""
    src = _BAOSTOCK_PY.read_text()
    assert "class _BaoStockSession" in src, "baostock.py MUST define `_BaoStockSession` class for session lifecycle management"


def test_session_uses_threading_lock() -> None:
    """`_BaoStockSession` MUST use threading.Lock for refcount protection."""
    src = _BAOSTOCK_PY.read_text()
    assert "import threading" in src, "baostock.py MUST `import threading`"
    assert "threading.Lock()" in src, "baostock.py MUST contain `threading.Lock()` for session state"


def test_no_scattered_login() -> None:
    """Outside `_BaoStockSession.scope`, no `self.bs.login()` calls remain.

    Allow 1 occurrence inside `_BaoStockSession.scope` (the only legit
    login call site after 1.3).
    """
    src = _BAOSTOCK_PY.read_text()
    lines = src.splitlines()
    login_lines = [(i + 1, line) for i, line in enumerate(lines) if "bs.login()" in line and not line.lstrip().startswith("#")]
    # Exactly 1: inside _BaoStockSession.scope
    assert len(login_lines) == 1, (
        f"expected exactly 1 `bs.login()` call site (inside _BaoStockSession.scope); "
        f"found {len(login_lines)}:\n" + "\n".join(f"  line {i}: {line.strip()}" for i, line in login_lines)
    )


def test_no_scattered_logout() -> None:
    """Outside `_BaoStockSession.scope`, no `self.bs.logout()` calls remain."""
    src = _BAOSTOCK_PY.read_text()
    lines = src.splitlines()
    logout_lines = [(i + 1, line) for i, line in enumerate(lines) if "bs.logout()" in line and not line.lstrip().startswith("#")]
    assert len(logout_lines) == 1, (
        f"expected exactly 1 `bs.logout()` call site (inside _BaoStockSession.scope); "
        f"found {len(logout_lines)}:\n" + "\n".join(f"  line {i}: {line.strip()}" for i, line in logout_lines)
    )


def test_scope_used_by_query_methods() -> None:
    """Query methods MUST use `with _BaoStockSession.scope(...)` for session
    lifecycle. We expect ≥ 7 callsites (12 original query methods minus
    test_connection helper).
    """
    src = _BAOSTOCK_PY.read_text()
    scope_uses = src.count("_BaoStockSession.scope(")
    # Allow some flexibility: the contextmanager `scope` itself is 1
    # reference (the `@contextmanager` decorated method), plus the
    # callsites. So we expect ≥ 8 mentions overall.
    assert scope_uses >= 7, f"expected ≥ 7 `_BaoStockSession.scope(` mentions (method def + ≥ 6 callsites); found {scope_uses}"


# --- Behavior tests (depend on _BaoStockSession existing) ---


def _make_bs_mock(login_ok: bool = True):
    """Build a MagicMock that simulates the baostock module-level API.

    `bs.login()` returns an object with `error_code` and `error_msg`,
    matching baostock's actual return shape.
    """
    bs = MagicMock()
    bs.login.return_value = MagicMock(error_code="0" if login_ok else "1", error_msg="boom")
    return bs


def test_scope_single_block_login_logout_once() -> None:
    """Single `with scope(...)` block calls login + logout once each."""
    from tradingagents.dataflows.providers.china.baostock import _BaoStockSession

    bs = _make_bs_mock()
    with _BaoStockSession.scope(bs):
        pass
    assert bs.login.call_count == 1
    assert bs.logout.call_count == 1


def test_scope_nested_shares_session() -> None:
    """Nested `with scope(...)` blocks share one session (refcount semantics)."""
    from tradingagents.dataflows.providers.china.baostock import _BaoStockSession

    bs = _make_bs_mock()
    with _BaoStockSession.scope(bs):
        with _BaoStockSession.scope(bs):
            with _BaoStockSession.scope(bs):
                pass
    assert bs.login.call_count == 1, f"nested scope MUST share session, login expected 1 call, got {bs.login.call_count}"
    assert bs.logout.call_count == 1, f"nested scope MUST share session, logout expected 1 call (outer only), got {bs.logout.call_count}"


def test_scope_concurrent_threads_share_session() -> None:
    """N concurrent threads each entering scope MUST share one login/logout.

    Use an inside-with barrier so all threads are guaranteed to overlap
    inside the scope before any releases — this forces refcount to climb
    to n_threads, after which all release, triggering exactly 1 logout.
    A `time.sleep` would be flaky; a barrier is deterministic.
    """
    import time as _time

    from tradingagents.dataflows.providers.china.baostock import _BaoStockSession

    bs = _make_bs_mock()
    n_threads = 5
    start_barrier = threading.Barrier(n_threads)
    inside_barrier = threading.Barrier(n_threads)

    def worker():
        start_barrier.wait()  # release all to scope() acquire together
        with _BaoStockSession.scope(bs):
            inside_barrier.wait()  # block here until all n_threads are inside the scope
            # tiny work — at this point refcount has climbed to n_threads
            _time.sleep(0.005)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # refcount semantics: any number of overlapping threads collapse to a
    # single login when the first acquires + last to release triggers logout.
    # Strict assertion: login MUST NOT exceed 1 (no race-induced double login).
    assert bs.login.call_count == 1, f"concurrent threads MUST share session, login expected 1, got {bs.login.call_count}"
    # logout: similar — exactly 1 when last refcount→0
    assert bs.logout.call_count == 1, f"concurrent threads expected 1 logout (last release), got {bs.logout.call_count}"


def test_scope_login_failure_raises_and_refcount_unchanged() -> None:
    """Login failure (error_code != '0') MUST raise; refcount stays 0."""
    from tradingagents.dataflows.providers.china.baostock import _BaoStockSession

    bs = _make_bs_mock(login_ok=False)
    with pytest.raises(Exception, match="登录失败"):
        with _BaoStockSession.scope(bs):
            pass
    # After failure, refcount MUST remain 0 (no spurious increment)
    assert _BaoStockSession._refcount == 0, f"failed login MUST NOT increment refcount; got {_BaoStockSession._refcount}"
    # logout MUST NOT be called when login failed
    assert bs.logout.call_count == 0


def test_scope_logout_failure_does_not_raise() -> None:
    """`bs.logout()` raising MUST NOT propagate out of scope context manager."""
    from tradingagents.dataflows.providers.china.baostock import _BaoStockSession

    bs = _make_bs_mock()
    bs.logout.side_effect = RuntimeError("network glitch on logout")

    # Should NOT raise — logout error swallowed (logged as warning)
    with _BaoStockSession.scope(bs):
        pass

    # Verify logout WAS attempted
    assert bs.logout.call_count == 1
    # State recovered: logged_in flipped to False even on logout error
    assert _BaoStockSession._logged_in is False
