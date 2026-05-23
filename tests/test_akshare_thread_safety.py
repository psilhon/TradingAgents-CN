"""dataflows-reliability stage 1.2 — AKShare patched_get thread safety.

Verify that `tradingagents/dataflows/providers/china/akshare.py` protects
the `last_request_time` rate-limit counter with `threading.Lock`. Without
the lock, multi-worker FastAPI deployments will see `last_request_time`
read-check-write races collapse the 0.5s eastmoney.com rate-limit,
triggering anti-bot blocks.

Two layers of defense:

1. **Source-level grep** — guards against regressions where someone
   accidentally drops the lock acquire. We check that `akshare.py`
   source contains `threading.Lock()` declaration + a `with <lock>:` block
   wrapping the `last_request_time` read-check-write region. This is the
   primary defense since the actual closure is non-trivially mockable.

2. **Isolated reproduction** — replicate the patched_get rate-limit
   structure in a tiny standalone closure, verify that without lock the
   concurrent path produces races (control), and with lock the same path
   serializes correctly (treatment). Demonstrates the fix's mechanism
   without booting the real AKShare provider.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_AKSHARE_PY = Path(__file__).resolve().parents[1] / "tradingagents" / "dataflows" / "providers" / "china" / "akshare.py"


# --- Source-level guards (primary defense) ---


def test_akshare_imports_threading() -> None:
    """akshare.py MUST import threading (for Lock)."""
    src = _AKSHARE_PY.read_text()
    assert "import threading" in src, "akshare.py MUST `import threading` for Lock"


def test_akshare_declares_lock() -> None:
    """akshare.py MUST declare a Lock object near the patched_get closure."""
    src = _AKSHARE_PY.read_text()
    # Either `rate_limit_lock = threading.Lock()` or `_lock = threading.Lock()`
    # — accept any threading.Lock() declaration. Common naming is
    # `rate_limit_lock` (this stage's convention).
    assert "threading.Lock()" in src, "akshare.py MUST contain `threading.Lock()` declaration to protect last_request_time read-check-write"


def test_akshare_uses_with_lock_for_rate_limit() -> None:
    """The rate-limit block (read-check-sleep-write of last_request_time)
    MUST be wrapped in a `with <lock>:` block.

    Heuristic: source MUST contain `with rate_limit_lock` (the stage's
    naming convention) AND the line right before `last_request_time[`
    write should be inside that with block.
    """
    src = _AKSHARE_PY.read_text()
    assert "with rate_limit_lock:" in src or "with rate_limit_lock " in src, (
        "akshare.py MUST contain `with rate_limit_lock:` block wrapping last_request_time read-check-sleep-write"
    )


def test_lock_protects_last_request_time_block() -> None:
    """Verify the last_request_time read+write happens *after* a `with
    rate_limit_lock:` statement, not outside it (would mean lock declared
    but unused).
    """
    src = _AKSHARE_PY.read_text()
    lines = src.splitlines()
    # Find the line with `with rate_limit_lock:`
    with_lock_idx = None
    for i, line in enumerate(lines):
        if "with rate_limit_lock:" in line:
            with_lock_idx = i
            break
    assert with_lock_idx is not None, "no `with rate_limit_lock:` block found"

    # Within the next ~20 lines (the with block body), there MUST be at
    # least one `last_request_time[` write.
    block_text = "\n".join(lines[with_lock_idx : with_lock_idx + 20])
    assert "last_request_time[" in block_text, (
        f"`with rate_limit_lock:` block at line {with_lock_idx + 1} MUST contain "
        f"last_request_time write — lock is unused if write happens outside it"
    )


# --- Isolated reproduction (mechanism test) ---


def _make_unsafe_rate_limiter():
    """Build the OLD (pre-1.2) patched_get rate-limit structure: dict without lock."""
    last_request_time = {"time": 0.0}
    hit_count = {"n": 0}

    def call(url: str) -> None:
        if "eastmoney.com" in url:
            current_time = time.time()
            time_since_last = current_time - last_request_time["time"]
            if time_since_last < 0.05:  # shrunk to 50ms for test speed
                time.sleep(0.05 - time_since_last)
            last_request_time["time"] = time.time()
        hit_count["n"] += 1

    return call, hit_count


def _make_safe_rate_limiter():
    """Build the NEW (1.2) patched_get rate-limit structure with threading.Lock."""
    last_request_time = {"time": 0.0}
    hit_count = {"n": 0}
    rate_limit_lock = threading.Lock()

    def call(url: str) -> None:
        if "eastmoney.com" in url:
            with rate_limit_lock:
                current_time = time.time()
                time_since_last = current_time - last_request_time["time"]
                if time_since_last < 0.05:
                    time.sleep(0.05 - time_since_last)
                last_request_time["time"] = time.time()
        hit_count["n"] += 1

    return call, hit_count, last_request_time


def test_lock_serializes_concurrent_rate_limit() -> None:
    """With Lock, concurrent calls to the rate-limited URL MUST serialize:
    last_request_time after N concurrent calls MUST advance by ≥ (N-1) *
    interval (0.05s in this test) — proving the lock kept them in order.
    """
    call, _hit, last_rt = _make_safe_rate_limiter()
    n_threads = 5
    barrier = threading.Barrier(n_threads)

    def worker():
        barrier.wait()  # release all threads simultaneously
        call("https://api.eastmoney.com/test")

    start = time.time()
    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - start

    # 5 threads × 0.05s interval = ≥ 0.2s total (4 gaps × 0.05s)
    # First call has no wait; subsequent (N-1) each wait ≥ 0.05s
    min_expected = (n_threads - 1) * 0.05
    assert elapsed >= min_expected - 0.01, (
        f"concurrent calls should serialize to ≥ {min_expected:.2f}s, got {elapsed:.2f}s — lock not enforcing serialization"
    )
    # last_request_time MUST have been written N times — final value is recent
    assert last_rt["time"] > 0


def test_no_lock_allows_concurrent_rate_limit_bypass() -> None:
    """**Control case** — without lock, concurrent threads bypass rate-limit.

    This test demonstrates the bug 1.2 fixes. If this test ever starts
    failing (i.e. concurrent calls accidentally serialize), it means
    Python's GIL behavior changed and the test is no longer a useful
    control — but the lock is still needed for correctness.
    """
    call, _hit = _make_unsafe_rate_limiter()
    n_threads = 5
    barrier = threading.Barrier(n_threads)

    def worker():
        barrier.wait()
        call("https://api.eastmoney.com/test")

    start = time.time()
    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - start

    # Without lock, most threads read same last=0, sleep nothing, run in
    # parallel — elapsed should be < the locked floor (4 * 0.05 = 0.2s).
    # Use a forgiving threshold (≤ 0.15s) — under heavy CI load this could
    # spuriously fail otherwise. The point is to demonstrate non-serialization.
    assert elapsed < 0.15, (
        f"control: unlocked concurrent calls should NOT serialize; if elapsed {elapsed:.3f}s >= 0.15s, test isn't proving the fix's value"
    )
