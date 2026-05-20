"""
Tests for PaperSnapshotService.take_snapshot.

Regression: `_get_last_price` returns a `(price, as_of)` tuple since the
2026-05-08 realtime-trading-data-flow change. `take_snapshot` must unpack it.
Treating the tuple as a scalar raises TypeError for any account holding a CN
stock, which silently aborts the daily snapshot — leaving every snapshot-derived
metric (TWRR / Sharpe / drawdown / Beta / VaR) permanently empty.
"""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.services.paper_snapshot_service import PaperSnapshotService


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length):
        return list(self._docs)


class _FakeCollection:
    def __init__(self, *, find_one_result=None, find_docs=None):
        self._find_one_result = find_one_result
        self._find_docs = find_docs or []
        self.updates: list[dict] = []

    async def find_one(self, *args, **kwargs):
        return self._find_one_result

    def find(self, *args, **kwargs):
        return _FakeCursor(self._find_docs)

    async def update_one(self, flt, update, upsert=False):
        self.updates.append({"filter": flt, "update": update, "upsert": upsert})


class _FakeDB:
    def __init__(self, collections):
        self._collections = collections

    def __getitem__(self, name):
        return self._collections[name]


def _build_service(*, account, positions):
    snapshots = _FakeCollection()
    db = _FakeDB(
        {
            "paper_accounts": _FakeCollection(find_one_result=account),
            "paper_positions": _FakeCollection(find_docs=positions),
            "paper_account_snapshots": snapshots,
        }
    )
    return PaperSnapshotService(db=db), snapshots


@pytest.mark.unit
def test_take_snapshot_with_cn_holding_writes_snapshot():
    """An account holding a CN stock must still produce a snapshot.

    Regression guard: `_get_last_price` returns `(price, as_of)`; `take_snapshot`
    must unpack it. Treating the tuple as a number raises TypeError and aborts
    the snapshot for every account that holds a stock.
    """
    account = {"user_id": "u1", "cash": {"CNY": 1000.0}, "realized_pnl": {"CNY": 0.0}}
    positions = [
        {
            "user_id": "u1",
            "code": "002428",
            "market": "CN",
            "quantity": 100,
            "avg_cost": 25.0,
        },
    ]
    svc, snapshots = _build_service(account=account, positions=positions)

    # `_get_last_price` 签名升级为 (price, as_of, pct_chg) 3-tuple（commit 31c5a108）
    with patch(
        "app.routers.paper._get_last_price",
        new=AsyncMock(return_value=(30.0, "2026-05-17T15:00:00", None)),
    ):
        result = asyncio.run(svc.take_snapshot("u1", date(2026, 5, 17)))

    assert result["ok"] is True
    assert result["positions_value"] == pytest.approx(3000.0)  # 30.0 * 100
    assert result["equity"] == pytest.approx(4000.0)  # 1000 cash + 3000 positions
    assert result["unrealized_pnl"] == pytest.approx(500.0)  # (30 - 25) * 100
    assert len(snapshots.updates) == 1
    assert snapshots.updates[0]["update"]["$set"]["equity"] == pytest.approx(4000.0)
    assert snapshots.updates[0]["upsert"] is True


@pytest.mark.unit
def test_take_snapshot_marks_partial_on_unavailable_price():
    """When `_get_last_price` yields (None, None, None) for a holding, the snapshot
    is marked partial=true with the position code in missing_quote_codes; aggregate
    fields are None (not 0/cash) to avoid polluting historical TWRR/Sharpe.

    change 2026-05-20-paper-null-quote-handling — v1.3.1 fix C4:
    旧契约 "skip the holding, equity=cash only" 是 null-as-0 合成；新契约 partial
    coverage 时 positions_value/equity/unrealized_pnl 整体 None + partial 标志。
    """
    account = {"user_id": "u1", "cash": {"CNY": 1000.0}, "realized_pnl": {"CNY": 0.0}}
    positions = [
        {
            "user_id": "u1",
            "code": "002428",
            "market": "CN",
            "quantity": 100,
            "avg_cost": 25.0,
        },
    ]
    svc, snapshots = _build_service(account=account, positions=positions)

    with patch(
        "app.routers.paper._get_last_price",
        new=AsyncMock(return_value=(None, None, None)),
    ):
        result = asyncio.run(svc.take_snapshot("u1", date(2026, 5, 17)))

    assert result["ok"] is True
    # 新契约：partial coverage → 聚合字段 None，partial=true + missing_codes 列出
    assert result["positions_value"] is None
    assert result["equity"] is None
    assert result["unrealized_pnl"] is None
    assert result["partial"] is True
    assert result["missing_quote_codes"] == ["002428"]
    assert len(snapshots.updates) == 1
    # mongo 写入 doc 包含新字段
    written = snapshots.updates[0]["update"]["$set"]
    assert written["partial"] is True
    assert written["missing_quote_codes"] == ["002428"]
    assert written["equity"] is None
    assert written["positions_value"] is None
