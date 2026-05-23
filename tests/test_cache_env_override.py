"""4.8 E2 — TA_CACHE_DIR env override tests.

Verifies that `get_cache()` reads `TA_CACHE_DIR` from the environment and
threads it to `FileBackend.cache_dir`. `~` MUST be expanded (running ops
typically set `TA_CACHE_DIR=~/.cache/ta`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


class _FakeDBManager:
    """Minimal db_manager stand-in — forces primary=file path so we don't
    need a live Redis / Mongo to construct Cache.
    """

    def is_redis_available(self) -> bool:
        return False

    def is_mongodb_available(self) -> bool:
        return False

    def get_redis_client(self):
        return None

    def get_mongodb_client(self):
        return None


@pytest.fixture
def fake_db_manager(monkeypatch):
    """Replace the real get_database_manager so Cache init can complete in unit tests."""
    monkeypatch.setattr(
        "tradingagents.config.database_manager.get_database_manager",
        lambda: _FakeDBManager(),
    )


def _reset_singleton():
    import tradingagents.dataflows.cache as cache_pkg

    cache_pkg.reset_cache()


# --- 4.8 E2 ---


def test_get_cache_uses_env_cache_dir(monkeypatch, tmp_path, fake_db_manager) -> None:
    """`TA_CACHE_DIR=/tmp/xxx` MUST drive Cache.file_backend.cache_dir."""
    del fake_db_manager  # fixture only needs to apply via param-injection
    import tradingagents.dataflows.cache as cache_pkg

    override = tmp_path / "custom_cache_root"
    monkeypatch.setenv("TA_CACHE_DIR", str(override))
    _reset_singleton()

    cache = cache_pkg.get_cache()
    # If we ended up on the StockDataCache fallback path, the test premise
    # doesn't hold (Cache construction failed silently) — fail loudly so the
    # cause shows up instead of pretending the env was honored.
    assert isinstance(cache, cache_pkg.Cache), f"expected Cache instance with file_backend.cache_dir attr, got {type(cache).__name__}"
    assert cache.file_backend.cache_dir == override


def test_get_cache_default_cache_dir_when_env_unset(monkeypatch, fake_db_manager) -> None:
    """No env → default `Path('data/cache')` (4.7 baseline behavior preserved)."""
    del fake_db_manager
    import tradingagents.dataflows.cache as cache_pkg

    monkeypatch.delenv("TA_CACHE_DIR", raising=False)
    _reset_singleton()

    cache = cache_pkg.get_cache()
    assert isinstance(cache, cache_pkg.Cache)
    assert cache.file_backend.cache_dir == Path("data/cache")


def test_get_cache_env_expanduser(monkeypatch, fake_db_manager) -> None:
    """`TA_CACHE_DIR=~/some/path` MUST be expanded; result MUST NOT contain literal `~`."""
    del fake_db_manager
    import tradingagents.dataflows.cache as cache_pkg

    monkeypatch.setenv("TA_CACHE_DIR", "~/.cache/ta_test_env_e2")
    _reset_singleton()

    cache = cache_pkg.get_cache()
    assert isinstance(cache, cache_pkg.Cache)
    actual = cache.file_backend.cache_dir
    # Literal `~` MUST NOT survive — expanduser should have produced an absolute path.
    assert "~" not in str(actual), f"expected expanded path, got {actual}"
    # Should resolve to `<home>/.cache/ta_test_env_e2`
    assert actual == Path("~/.cache/ta_test_env_e2").expanduser()
