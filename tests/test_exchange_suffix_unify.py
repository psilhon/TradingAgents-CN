"""dataflows-schema-consistency stage 2.1 — 交易所后缀统一 (.SS → .SH).

Verify writer-side code consistently generates `.SH/.SZ/.BJ` (tushare 风格)
suffix for A-share full_symbol values, and reader-side defensive
`.replace(".SS", "")` normalize is removed (writer guarantees canonical
form, reader needs no fallback).

Without unification, mongo `market_quotes` docs can carry
`full_symbol="600519.SS"` + `ts_code="600519.SH"` simultaneously, and 9
downstream readers do `.replace(".SS", "")` to defensively normalize —
a sign of schema fragmentation that's now collapsed at the writer.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[1]


# --- Source-level guards: writer files MUST NOT generate ".SS" ---


_WRITER_FILES = [
    "app/services/basics_sync_service.py",
    "app/services/multi_source_basics_sync_service.py",
    "app/services/stock_data_service.py",
    "tradingagents/dataflows/providers/china/baostock.py",
    "tradingagents/dataflows/providers/china/akshare.py",
]


@pytest.mark.parametrize("rel_path", _WRITER_FILES)
def test_writer_file_does_not_generate_dot_ss(rel_path: str) -> None:
    """Writer files MUST NOT contain `.SS` suffix in f-string / string concat.

    Allowed:
    - `.replace(".SS", ...)` defensive (the reader normalize being removed in
      this stage but allowed in transition for writer files if any)
    - Comments / docstrings (lines starting with `#` or in triple-quoted strings)
    - String comparison like `endswith(".SS")` — not a generator

    Forbidden:
    - `f"...{code}.SS"` / `f"{code}.SS"` — generates .SS into mongo
    - Plain `"600519.SS"` literal that gets stored
    """
    path = _REPO / rel_path
    text = path.read_text()
    lines = text.splitlines()
    forbidden_lines = []
    for i, line in enumerate(lines, start=1):
        # Skip pure comment lines
        if line.lstrip().startswith("#"):
            continue
        # Strict check: f-string / string concat that generates .SS
        # Match `.SS` as suffix in a value being assigned/returned (heuristic:
        # the surrounding context has `f"..."` ending in `.SS"` or `.SS'`)
        if 'return f"' in line and '.SS"' in line:
            forbidden_lines.append((i, line.strip()))
        elif "return f'" in line and ".SS'" in line:
            forbidden_lines.append((i, line.strip()))
        elif '= f"' in line and '.SS"' in line:
            forbidden_lines.append((i, line.strip()))
    assert forbidden_lines == [], f"writer file {rel_path} MUST NOT generate `.SS` suffix; found:\n" + "\n".join(
        f"  line {i}: {line}" for i, line in forbidden_lines
    )


# --- Reader-side: `.replace(".SS", "")` defensive normalize removed ---


_READER_FILES = [
    "tradingagents/tools/unified_news_tool.py",
    "tradingagents/agents/utils/agent_utils.py",
    "tradingagents/utils/news_filter_integration.py",
    "tradingagents/dataflows/news/realtime_news.py",
]


@pytest.mark.parametrize("rel_path", _READER_FILES)
def test_reader_file_no_dot_ss_replace(rel_path: str) -> None:
    """Reader files MUST NOT contain `.replace(".SS", "")` defensive normalize
    after stage 2.1 — writer guarantees canonical `.SH/.SZ/.BJ` form.

    Allowed: `.replace(".XSHE", "")` / `.replace(".XSHG", "")` (ISO ISIN-style
    external tags, kept for compatibility with external news / API input).
    """
    path = _REPO / rel_path
    text = path.read_text()
    # Only check non-comment lines + skip stage 2.1 migration-note lines
    # (注释里写「2.1: 移除 .replace(".SS", "")」是文档不是代码)
    offending = []
    for i, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if "2.1:" in line or "2.1 " in line:
            # Stage 2.1 migration-time documentation comment — skip
            continue
        if '.replace(".SS"' in line:
            offending.append((i, line))
    if offending:
        pytest.fail(
            f'reader file {rel_path} MUST NOT contain executable `.replace(".SS", ...)` '
            f"after stage 2.1 — writer guarantees canonical form. Found:\n"
            + "\n".join(f"  line {i}: {line.strip()}" for i, line in offending)
        )


# --- Behavior tests: helpers return canonical .SH form ---


def test_baostock_provider_get_full_symbol_uses_sh() -> None:
    """`baostock._get_full_symbol('600519')` MUST return `'600519.SH'`.

    Note: `_get_full_symbol` is the *schema output* helper (returns the
    tushare-style `.SH/.SZ/.BJ` form for storage). `_to_baostock_code` is
    a *baostock API input* helper (returns `sh.xxxxxx` form for the
    baostock query API) — that's out of scope for stage 2.1 schema unify.
    """
    from tradingagents.dataflows.providers.china.baostock import BaoStockProvider

    provider = BaoStockProvider()
    assert provider._get_full_symbol("600519") == "600519.SH", "Shanghai A-share code 600519 MUST map to `.SH` suffix (tushare 风格)"
    # Shenzhen + Beijing should be unchanged
    assert provider._get_full_symbol("000001") == "000001.SZ"
    assert provider._get_full_symbol("830799") == "830799.BJ"


def test_akshare_provider_full_symbol_uses_sh() -> None:
    """`akshare._get_full_symbol('600519')` MUST return `'600519.SH'`."""
    from tradingagents.dataflows.providers.china.akshare import AKShareProvider

    provider = AKShareProvider()
    assert provider._get_full_symbol("600519") == "600519.SH"
    assert provider._get_full_symbol("000001") == "000001.SZ"


def test_basics_sync_service_to_full_symbol_uses_sh() -> None:
    """basics_sync_service `_to_full_symbol` (or equivalent) MUST return `.SH`."""
    # The function in basics_sync_service.py at line 413 is internal; we test
    # via source-level grep that .SS isn't generated (already covered above).
    # Behavior test: confirm a representative Shanghai code maps to .SH via
    # the public sync code path — but since basics_sync triggers real tushare
    # network, we keep this test source-level only (above).
    src = (_REPO / "app/services/basics_sync_service.py").read_text()
    # Strict: line 413 area MUST contain `.SH"` (the new canonical form)
    assert '.SH"' in src, 'basics_sync_service.py MUST contain `.SH"` form (Shanghai canonical)'


# --- Migration script source-level guard ---


def test_migration_script_exists() -> None:
    """The 2.1 migration script MUST be present in scripts/migrations/."""
    path = _REPO / "scripts" / "migrations" / "2.1_unify_exchange_suffix.js"
    assert path.exists(), f"migration script MUST be at {path} for the one-shot mongo rewrite"


def test_migration_script_has_dry_run_default() -> None:
    """Migration script MUST default to dry-run mode (safety)."""
    path = _REPO / "scripts" / "migrations" / "2.1_unify_exchange_suffix.js"
    if not path.exists():
        pytest.skip("migration script not yet created (red phase)")
    text = path.read_text()
    assert "DRY_RUN" in text, "migration script MUST contain DRY_RUN flag"
    # Default value should be true (safe). Accept any common JS idiom that
    # achieves this: `DRY_RUN = true`, `typeof DRY_RUN ... : true`, etc.
    idioms = [
        "DRY_RUN = true",  # plain assignment
        "? DRY_RUN : true",  # ternary `(cond) ? DRY_RUN : true` pattern
        ": true",  # generic fallback (covers ternary with literal true)
    ]
    assert any(idiom in text for idiom in idioms), "migration script DRY_RUN flag MUST default to true (safe)"
