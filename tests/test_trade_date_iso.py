"""dataflows-schema-consistency stage 2.2 — trade_date ISO 8601 统一.

Verify that `app/services/quotes_ingestion_service.py` normalizes
`trade_date` to canonical `yyyy-mm-dd` ISO 8601 form before writing to
`market_quotes`, regardless of upstream source returning `yyyymmdd` or
`yyyy-mm-dd`.

Tushare API input (e.g. `api.daily_basic(trade_date="20260521")`) MUST
stay `yyyymmdd` — that's an upstream API constraint; only mongo storage
schema is unified.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[1]
_INGESTION_SERVICE = _REPO / "app" / "services" / "quotes_ingestion_service.py"
_MIGRATION_SCRIPT = _REPO / "scripts" / "migrations" / "2.2_trade_date_iso.js"


# --- Source-level guards ---


def test_quotes_ingestion_service_has_iso_normalizer() -> None:
    """quotes_ingestion_service.py MUST contain `_to_iso_date` helper for
    canonical ISO 8601 normalization before mongo write.
    """
    src = _INGESTION_SERVICE.read_text()
    assert "_to_iso_date" in src, "quotes_ingestion_service.py MUST contain `_to_iso_date` helper (stage 2.2 canonical ISO 8601 normalize)"


def test_bulk_upsert_uses_iso_normalizer() -> None:
    """`_bulk_upsert` MUST call `_to_iso_date(trade_date)` before writing,
    ensuring trade_date is canonical yyyy-mm-dd in mongo regardless of
    upstream caller passing yyyymmdd.
    """
    src = _INGESTION_SERVICE.read_text()
    lines = src.splitlines()
    # Find `async def _bulk_upsert(`
    in_bulk_upsert = False
    body = []
    for _i, line in enumerate(lines):
        if "def _bulk_upsert(" in line:
            in_bulk_upsert = True
            continue
        if in_bulk_upsert:
            if (
                line.startswith("    async def ")
                or line.startswith("    def ")
                or line.startswith("class ")
                or (not line.startswith(" ") and line.strip())
            ):
                # End of method body (next method or class declaration)
                break
            body.append(line)
    body_text = "\n".join(body)
    assert "_to_iso_date" in body_text, (
        "`_bulk_upsert` body MUST call `_to_iso_date` to normalize trade_date before mongo write. Source body:\n" + body_text[:1000]
    )


def test_migration_script_exists() -> None:
    """2.2 migration script MUST be present."""
    assert _MIGRATION_SCRIPT.exists(), f"migration script MUST be at {_MIGRATION_SCRIPT}"


def test_migration_script_dry_run_default() -> None:
    """Migration script MUST default to dry-run."""
    if not _MIGRATION_SCRIPT.exists():
        pytest.skip("migration script not yet created (red phase)")
    text = _MIGRATION_SCRIPT.read_text()
    assert "DRY_RUN" in text
    # Accept common JS dry-run-default idioms
    idioms = ["DRY_RUN = true", "? DRY_RUN : true", ": true"]
    assert any(idiom in text for idiom in idioms), "migration script DRY_RUN flag MUST default to true (safe)"


# --- Behavior tests: _to_iso_date helper accepts both formats ---


def test_iso_date_normalizes_yyyymmdd() -> None:
    """`_to_iso_date('20260521')` MUST return `'2026-05-21'`."""
    from app.services.quotes_ingestion_service import QuotesIngestionService

    service = QuotesIngestionService.__new__(QuotesIngestionService)
    # _to_iso_date may be instance method or static — try both
    fn = getattr(service, "_to_iso_date", None) or getattr(QuotesIngestionService, "_to_iso_date", None)
    assert fn is not None, "`_to_iso_date` helper MUST exist on QuotesIngestionService"
    # If instance method, call via instance; if static, the staticmethod
    # call still works the same way.
    result = fn("20260521") if callable(fn) and not isinstance(fn, staticmethod) else fn.__func__("20260521")
    assert result == "2026-05-21", f"_to_iso_date('20260521') MUST return '2026-05-21', got {result!r}"


def test_iso_date_passes_through_yyyy_mm_dd() -> None:
    """`_to_iso_date('2026-05-21')` MUST return `'2026-05-21'` unchanged
    (idempotent on already-canonical form).
    """
    from app.services.quotes_ingestion_service import QuotesIngestionService

    service = QuotesIngestionService.__new__(QuotesIngestionService)
    fn = getattr(service, "_to_iso_date", None) or getattr(QuotesIngestionService, "_to_iso_date", None)
    result = fn("2026-05-21") if callable(fn) and not isinstance(fn, staticmethod) else fn.__func__("2026-05-21")
    assert result == "2026-05-21", f"_to_iso_date('2026-05-21') MUST be idempotent, got {result!r}"


def test_iso_date_handles_datetime() -> None:
    """`_to_iso_date(datetime(2026, 5, 21))` MUST return `'2026-05-21'`."""
    from app.services.quotes_ingestion_service import QuotesIngestionService

    service = QuotesIngestionService.__new__(QuotesIngestionService)
    fn = getattr(service, "_to_iso_date", None) or getattr(QuotesIngestionService, "_to_iso_date", None)
    result = fn(datetime(2026, 5, 21)) if callable(fn) and not isinstance(fn, staticmethod) else fn.__func__(datetime(2026, 5, 21))
    assert result == "2026-05-21", f"_to_iso_date(datetime) MUST return '2026-05-21', got {result!r}"


def test_iso_date_rejects_garbage_falls_back_to_today() -> None:
    """`_to_iso_date('garbage')` MUST NOT raise — falls back to today's ISO date.

    Robust default avoids one bad upstream value crashing the entire bulk write.
    """
    from app.services.quotes_ingestion_service import QuotesIngestionService

    service = QuotesIngestionService.__new__(QuotesIngestionService)
    fn = getattr(service, "_to_iso_date", None) or getattr(QuotesIngestionService, "_to_iso_date", None)
    # Pass garbage — should not raise
    result = fn("garbage") if callable(fn) and not isinstance(fn, staticmethod) else fn.__func__("garbage")
    # Should be today's date in ISO format (heuristic check: 10 chars, two dashes)
    assert isinstance(result, str)
    assert len(result) == 10 and result.count("-") == 2, f"_to_iso_date('garbage') MUST fall back to today's yyyy-mm-dd, got {result!r}"
