"""Drive a coroutine to completion from synchronous code, safely.

Synchronous helpers in the data layer (e.g. optimized_china_data) need to call
async provider methods. Using ``asyncio.get_event_loop().run_until_complete(...)``
breaks when the synchronous caller is itself running inside an active event loop
(an async FastAPI route or a LangGraph async node): ``run_until_complete`` raises
``RuntimeError("This event loop is already running")``. Callers that swallow
exceptions then silently degrade (e.g. "no financial data").

``run_coro_blocking`` works in both cases:
- No loop running on the current thread -> ``asyncio.run`` (fresh loop).
- A loop is already running -> offload the coroutine to a dedicated worker
  thread that owns its own loop, and block until it finishes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

_T = TypeVar("_T")


def run_coro_blocking(coro: Coroutine[Any, Any, _T]) -> _T:
    """Run ``coro`` to completion and return its result, even when an event
    loop is already running on the current thread.

    Exceptions raised inside the coroutine propagate to the caller unchanged.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop on this thread: safe to create and drive one.
        return asyncio.run(coro)

    # A loop is already running here; run the coroutine in a separate thread
    # with its own loop and wait for the result. The outer (sync) caller was
    # already going to block, so blocking on .result() is acceptable.
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()
