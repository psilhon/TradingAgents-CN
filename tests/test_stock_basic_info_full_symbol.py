"""dataflows-schema-consistency stage 2.3 — stock_basic_info full_symbol invariant.

Stage 2.3 background: audit-2026-05-23 initial probe misread `ts_code` field
(deprecated alias) and reported "stock_basic_info missing full_symbol". On
deeper investigation, all 5846 docs already carry `full_symbol` with
canonical `.SH/.SZ/.BJ` form — both `basics_sync_service.py:265-280` and
`multi_source_basics_sync_service.py:259-281` writers write the field
correctly. This stage adds source-level + behavior guards so a future
refactor can't silently drop the field.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[1]
_BASICS_SYNC = _REPO / "app" / "services" / "basics_sync_service.py"
_MULTI_SOURCE_SYNC = _REPO / "app" / "services" / "multi_source_basics_sync_service.py"
_AUDIT_SCRIPT = _REPO / "scripts" / "migrations" / "2.3_audit_full_symbol.js"


# --- Source-level guards: both basics writers MUST write full_symbol ---


@pytest.mark.parametrize(
    "rel_path",
    [
        "app/services/basics_sync_service.py",
        "app/services/multi_source_basics_sync_service.py",
    ],
)
def test_basics_writer_emits_full_symbol(rel_path: str) -> None:
    """basics sync writers MUST emit `"full_symbol": ...` into the upsert doc.

    Catches refactor regressions that drop the field.
    """
    src = (_REPO / rel_path).read_text()
    # Look for `"full_symbol":` (the dict-key form actually written to mongo)
    assert '"full_symbol":' in src, (
        f'{rel_path} MUST contain `"full_symbol":` field in upsert doc (stage 2.3 invariant — stock_basic_info every doc has full_symbol)'
    )


@pytest.mark.parametrize(
    "rel_path",
    [
        "app/services/basics_sync_service.py",
        "app/services/multi_source_basics_sync_service.py",
    ],
)
def test_basics_writer_has_full_symbol_generator(rel_path: str) -> None:
    """basics sync writers MUST contain a `_generate_full_symbol` helper used
    when the upstream `ts_code` is unavailable.
    """
    src = (_REPO / rel_path).read_text()
    assert "_generate_full_symbol" in src, (
        f"{rel_path} MUST contain `_generate_full_symbol` helper for fallback when upstream ts_code is missing"
    )


# --- Behavior tests: _generate_full_symbol returns canonical suffix ---


def test_basics_sync_generate_full_symbol_returns_canonical() -> None:
    """`BasicsSyncService._generate_full_symbol(code)` MUST return
    canonical `.SH/.SZ/.BJ` form for representative codes.
    """
    from app.services.basics_sync_service import BasicsSyncService

    service = BasicsSyncService.__new__(BasicsSyncService)
    # Shanghai
    assert service._generate_full_symbol("600519") == "600519.SH"
    assert service._generate_full_symbol("688981") == "688981.SH"
    # Shenzhen
    assert service._generate_full_symbol("000001") == "000001.SZ"
    assert service._generate_full_symbol("300750") == "300750.SZ"
    # Beijing (BJ)
    assert service._generate_full_symbol("830799") == "830799.BJ"


def test_multi_source_generate_full_symbol_returns_canonical() -> None:
    """multi_source basics_sync service `_generate_full_symbol` returns canonical."""
    from app.services.multi_source_basics_sync_service import (
        MultiSourceBasicsSyncService,
    )

    service = MultiSourceBasicsSyncService.__new__(MultiSourceBasicsSyncService)
    assert service._generate_full_symbol("600519") == "600519.SH"
    assert service._generate_full_symbol("000001") == "000001.SZ"
    assert service._generate_full_symbol("830799") == "830799.BJ"


# --- Audit script exists ---


def test_audit_script_exists() -> None:
    """2.3 audit script MUST be present."""
    assert _AUDIT_SCRIPT.exists(), f"audit script MUST be at {_AUDIT_SCRIPT}"
