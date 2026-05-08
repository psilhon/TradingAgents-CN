"""QuoteSnapshotReader: hot-path 从 mongo `market_quotes` 批量读持仓 / 自选股快照.

按 OpenSpec change `2026-05-08-realtime-trading-data-flow` Requirement 1：
hot-path（router / WebSocket 推送等用户请求路径）MUST NOT 同步触发 akshare /
tushare 等外部行情源；持仓 / 自选股查询走 mongo `market_quotes`，缺漏 code
返回 None 占位，不 fallback 触发 fetch。

设计：
- 仅读 mongo，无任何上游 fetch
- 每条 record 带 `last_price_as_of`（来自 doc.updated_at）
- 顶层 `as_of_ts` = min(records.last_price_as_of)，忽略 None；全缺漏返回 None
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from app.core.database import get_mongo_db

logger = logging.getLogger(__name__)


def _to_iso(ts: Any) -> Optional[str]:
    """mongo updated_at 字段 → ISO8601 字符串.

    支持 datetime（含 tz / naive）+ 已 ISO 字符串 + None.
    naive datetime 假定 UTC（与 mongo 默认一致）.
    """
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts.isoformat()
    if isinstance(ts, str):
        return ts
    return None


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class QuoteSnapshotReader:
    """从 mongo `market_quotes` 读快照；不 fallback 上游 fetch."""

    COLLECTION = "market_quotes"

    async def read_quotes(self, codes: list[str]) -> dict[str, Any]:
        """批量读 codes 的 quote 快照.

        Returns:
            {
                "quotes": {
                    "<code>": {"close", "pct_chg", "amount", "last_price_as_of"} | (all None when missing)
                },
                "as_of_ts": str | None,  # min last_price_as_of, ignoring None; None if all missing
            }
        """
        normalized: list[str] = []
        seen: set[str] = set()
        for c in codes:
            if not isinstance(c, str):
                continue
            s = c.strip()
            if not s or s in seen:
                continue
            seen.add(s)
            normalized.append(s)

        if not normalized:
            return {"quotes": {}, "as_of_ts": None}

        db = get_mongo_db()
        coll = db[self.COLLECTION]
        cursor = coll.find(
            {"code": {"$in": normalized}},
            {"_id": 0, "code": 1, "close": 1, "pct_chg": 1, "amount": 1, "updated_at": 1},
        )

        found: dict[str, dict[str, Any]] = {}
        async for doc in cursor:
            code = str(doc.get("code", "")).strip()
            if not code:
                continue
            found[code] = {
                "close": _safe_float(doc.get("close")),
                "pct_chg": _safe_float(doc.get("pct_chg")),
                "amount": _safe_float(doc.get("amount")),
                "last_price_as_of": _to_iso(doc.get("updated_at")),
            }

        quotes: dict[str, dict[str, Any]] = {}
        for c in normalized:
            quotes[c] = found.get(
                c,
                {"close": None, "pct_chg": None, "amount": None, "last_price_as_of": None},
            )

        valid_ts = [q["last_price_as_of"] for q in quotes.values() if q["last_price_as_of"]]
        as_of_ts = min(valid_ts) if valid_ts else None

        return {"quotes": quotes, "as_of_ts": as_of_ts}


_reader: Optional[QuoteSnapshotReader] = None


def get_quote_snapshot_reader() -> QuoteSnapshotReader:
    global _reader
    if _reader is None:
        _reader = QuoteSnapshotReader()
    return _reader
