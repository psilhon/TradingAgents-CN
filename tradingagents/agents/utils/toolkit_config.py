"""Request-scoped Toolkit configuration via ContextVar.

Toolkit's tool methods are ``@staticmethod @tool`` (no ``self``), so they
historically read a class-level shared mutable dict (``Toolkit._config``).
``update_config`` mutated it in place, so two concurrent analyses in one
process clobbered each other's config (cross-request config bleed).

This module holds the *current execution context's* config in a
``ContextVar``. Analyses run in worker threads (each with its own ContextVar
context), so per-request config stays isolated. The setter always stores a
fresh dict merged over ``DEFAULT_CONFIG`` — it never mutates a shared dict.

Constraint: ContextVar does not propagate across ``loop.run_in_executor``
boundaries automatically, so ``set_toolkit_config`` must be called *inside*
the worker thread that runs the graph (it is — via ``Toolkit.__init__``).
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from tradingagents.default_config import DEFAULT_CONFIG

_current_config: ContextVar[dict[str, Any] | None] = ContextVar("toolkit_config", default=None)


def set_toolkit_config(config: dict[str, Any]) -> None:
    """Store a request-scoped config (merged over DEFAULT_CONFIG) for the
    current context. Always writes a NEW dict — never mutates a shared one."""
    _current_config.set({**DEFAULT_CONFIG, **config})


def get_toolkit_config() -> dict[str, Any]:
    """Return the current context's config, or a copy of DEFAULT_CONFIG when
    nothing has been set (CLI / tests / any non-worker path)."""
    current = _current_config.get()
    if current is None:
        return dict(DEFAULT_CONFIG)
    return current
