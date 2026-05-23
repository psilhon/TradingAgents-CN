"""MongoBackend — MongoDB `Backend` implementation.

Unlike `FileBackend` / `RedisBackend` (which round-trip opaque envelope bytes
via `_serialize.py`), MongoDB stores documents with typed fields, so this
backend interprets the envelope's `data` field to drive a doc schema:

- `pandas.DataFrame` data → `df.to_json(orient='split')` + `data_type="dataframe"`
- Other data → `json.dumps(default=str)` + `data_type="json"`

The doc shape is sealed by stage 2 (`cache-pickle-replacement`). A
re-design to store envelope bytes as Binary fields would unify all three
backends to pure round-trip, but would break compatibility with existing
docs — deferred to 4.4 / 4.6.

**Legacy pickle 降级**: docs with `data_type="pickle"` from before stage 2
MUST be deleted on load + return cache miss. We never call `pickle.loads` —
the load path uses string equality on the `data_type` field to detect legacy
docs. This is enforced by the spec Requirement "MongoBackend 单一职责
（含 legacy pickle 降级）" and by `test_mongo_backend.py` patching
`pickle.loads` / `pickle.load` to verify they are never invoked.

Implements `Backend` Protocol (`_protocol.py`).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any

import pandas as pd


def _utcnow() -> datetime:
    """Return current time as timezone-aware UTC datetime.

    Wrapped so tests can monkeypatch a single seam, and so MongoBackend
    never accidentally drops back to naive `datetime.now()`.
    """
    return datetime.now(timezone.utc)


def _to_utc_aware(dt: datetime | None) -> datetime | None:
    """Normalize a datetime to timezone-aware UTC.

    PyMongo's default tz_aware=False returns naive UTC datetimes; this
    helper attaches UTC so comparison against `_utcnow()` is consistent
    on hosts in non-UTC timezones.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class MongoBackend:
    """MongoDB backend — typed doc schema + legacy pickle drop-on-load."""

    def __init__(
        self,
        mongodb_client: Any | None,
        db_name: str = "tradingagents",
        collection_name: str = "cache",
    ) -> None:
        self._logger = logging.getLogger(__name__)
        self._client = mongodb_client
        self._db_name = db_name
        self._collection_name = collection_name

    def _collection(self):
        if self._client is None:
            return None
        return self._client[self._db_name][self._collection_name]

    def save(self, key: str, envelope: dict, ttl_seconds: int | None = None) -> bool:
        """Persist `envelope` as a typed doc under `_id=key`."""
        if self._client is None:
            return False
        try:
            data = envelope.get("data")
            if isinstance(data, pd.DataFrame):
                serialized = data.to_json(orient="split")
                data_type = "dataframe"
            else:
                serialized = json.dumps(data, default=str)
                data_type = "json"

            doc: dict[str, Any] = {
                "_id": key,
                "data": serialized,
                "data_type": data_type,
                "metadata": envelope.get("metadata", {}),
                "timestamp": _to_utc_aware(envelope.get("timestamp")) or _utcnow(),
                "backend": "mongodb",
            }
            if ttl_seconds is not None:
                doc["expires_at"] = _utcnow() + timedelta(seconds=ttl_seconds)

            collection = self._collection()
            if collection is None:
                return False
            collection.replace_one({"_id": key}, doc, upsert=True)
            self._logger.debug(f"mongo backend save: {key} (ttl={ttl_seconds})")
            return True
        except Exception:
            self._logger.exception(f"mongo backend save failed for {key}")
            return False

    def load(self, key: str) -> dict | None:
        """Load envelope for `key`, with expiry + legacy pickle drop-on-load."""
        if self._client is None:
            return None
        try:
            collection = self._collection()
            if collection is None:
                return None

            doc = collection.find_one({"_id": key})
            if not doc:
                return None

            # Expiry check — normalize stored datetime to UTC-aware before comparing
            # against current UTC wall clock (PyMongo defaults to naive UTC; without
            # this normalization, hosts in non-UTC timezones drift by their offset).
            expires_at = _to_utc_aware(doc.get("expires_at"))
            if expires_at is not None and expires_at < _utcnow():
                collection.delete_one({"_id": key})
                return None

            data_type = doc.get("data_type")
            if data_type == "dataframe":
                data = pd.read_json(StringIO(doc["data"]), orient="split")
            elif data_type == "json":
                data = json.loads(doc["data"])
            elif data_type == "pickle":
                # Legacy from before stage 2 (cache-pickle-replacement).
                # MUST NOT call pickle.loads — drop the doc + cache miss.
                collection.delete_one({"_id": key})
                self._logger.info(f"dropped legacy pickle mongo cache entry: {key}")
                return None
            else:
                # Unknown data_type — could be a future-schema doc or a corrupted
                # entry from an aborted write. Drop it so it doesn't accumulate as
                # a zombie that misses+warns on every read (4.7 修订: 4.6 仅 warn).
                collection.delete_one({"_id": key})
                self._logger.warning(f"dropped unknown data_type {data_type!r} mongo cache entry: {key}")
                return None

            envelope = {
                "data": data,
                "metadata": doc.get("metadata", {}),
                "timestamp": _to_utc_aware(doc.get("timestamp")),
                "backend": "mongodb",
            }
            self._logger.debug(f"mongo backend load: {key}")
            return envelope
        except Exception:
            self._logger.exception(f"mongo backend load failed for {key}")
            return None

    def clear(self, max_age_days: int) -> None:
        """Delete cache docs older than `max_age_days` (0 = all docs)."""
        if self._client is None:
            return
        try:
            collection = self._collection()
            if collection is None:
                return
            if max_age_days == 0:
                result = collection.delete_many({})
                self._logger.info(f"mongo backend cleared {result.deleted_count} docs (max_age_days=0)")
                return
            cutoff = _utcnow() - timedelta(days=max_age_days)
            result = collection.delete_many({"timestamp": {"$lt": cutoff}})
            self._logger.info(f"mongo backend cleared {result.deleted_count} docs older than {max_age_days}d")
        except Exception:
            self._logger.exception("mongo backend clear failed")
