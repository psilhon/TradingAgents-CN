"""Safe envelope serializer for cache payloads (replaces pickle).

Encodes envelope dicts to gzip(JSON) bytes. Handles `datetime` and
`pandas.DataFrame` via tagged objects; everything else must be JSON-native
or `json.dumps` raises TypeError (surfaced as a cache miss by the caller's
outer except).

This module is intentionally light-imports (gzip / json / datetime / pandas)
so unit tests can `spec_from_file_location` it without triggering MongoDB
side effects from the `tradingagents.dataflows` package init.
"""

import gzip
import json
from datetime import datetime
from io import StringIO
from typing import Any

import pandas as pd

_DT_TAG = "__dt__"
_DF_TAG = "__df_split__"


def _encode_value(v: Any) -> Any:
    if isinstance(v, datetime):
        return {_DT_TAG: v.isoformat()}
    if isinstance(v, pd.DataFrame):
        return {_DF_TAG: v.to_json(orient="split")}
    if isinstance(v, dict):
        return {k: _encode_value(vv) for k, vv in v.items()}
    if isinstance(v, list):
        return [_encode_value(vv) for vv in v]
    return v


def _decode_value(v: Any) -> Any:
    if isinstance(v, dict):
        if len(v) == 1 and _DF_TAG in v:
            return pd.read_json(StringIO(v[_DF_TAG]), orient="split")
        if len(v) == 1 and _DT_TAG in v:
            return datetime.fromisoformat(v[_DT_TAG])
        return {k: _decode_value(vv) for k, vv in v.items()}
    if isinstance(v, list):
        return [_decode_value(vv) for vv in v]
    return v


def encode_envelope(envelope: dict) -> bytes:
    """Encode envelope dict to gzip(JSON) bytes. Safe replacement for pickle.dumps."""
    return gzip.compress(json.dumps(_encode_value(envelope)).encode("utf-8"))


def decode_envelope(blob: bytes) -> dict:
    """Decode gzip(JSON) bytes back to envelope.

    Raises on legacy pickle bytes (gzip.decompress / json.loads fails)
    so callers can treat the failure as a cache miss.
    """
    obj = json.loads(gzip.decompress(blob).decode("utf-8"))
    return _decode_value(obj)
