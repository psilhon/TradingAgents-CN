"""Contract test for favorites 10-supe limit (capability watchlist-management).

change 2026-05-21-watchlist-limit-and-ordering.

锁定 FAVORITES_LIMIT = 10 + FavoritesLimitExceededError 行为 + count/order helper
契约。

Service-level test 用 monkeypatch 把 _get_db 换成 fake mongo（in-memory dict），
避免起真 mongo；router-level test 在 test_favorites_router_reorder.py。
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from app.services.favorites_service import (
    FAVORITES_LIMIT,
    FavoritesLimitExceededError,
    FavoritesService,
    _compute_next_order,
)

# ===== _compute_next_order pure helper =====


@pytest.mark.unit
def test_compute_next_order_empty():
    """空列表 → 0（第一条 order）."""
    assert _compute_next_order([]) == 0


@pytest.mark.unit
def test_compute_next_order_sequential():
    """顺序 [0,1,2] → 3."""
    assert _compute_next_order([{"order": 0}, {"order": 1}, {"order": 2}]) == 3


@pytest.mark.unit
def test_compute_next_order_with_gaps():
    """带 gap [0,1,3] → 4（max+1，不复用 gap）."""
    assert _compute_next_order([{"order": 0}, {"order": 1}, {"order": 3}]) == 4


@pytest.mark.unit
def test_compute_next_order_missing_field():
    """部分条目缺 order 字段 → 视为 -1，max(0, ...) + 1.

    保守：旧文档若混入会被 lazy migration 处理，但 compute_next_order
    防御性兼容（缺 order 当 -1 不参与 max）.
    """
    # 全缺 order → 视为 max=-1 + 1 = 0（防御）
    assert _compute_next_order([{}, {}]) == 0
    # 部分有 order
    assert _compute_next_order([{"order": 0}, {}, {"order": 2}]) == 3


# ===== FAVORITES_LIMIT 常量 + Exception =====


@pytest.mark.unit
def test_favorites_limit_constant_is_10():
    """常量锁定 10 — 修改需通过 spec 流程."""
    assert FAVORITES_LIMIT == 10


@pytest.mark.unit
def test_favorites_limit_exceeded_error_is_exception():
    """自定义异常 — router 据此转 409."""
    assert issubclass(FavoritesLimitExceededError, Exception)
    # 可携带 message
    err = FavoritesLimitExceededError("已达自选股上限 10 支")
    assert str(err) == "已达自选股上限 10 支"


# ===== add_favorite limit 行为（service-level with fake db）=====


class _FakeFavoritesCollection:
    """模拟 user_favorites collection 的最小子集."""

    def __init__(self, initial: dict | None = None) -> None:
        self.doc = initial  # {"user_id": ..., "favorites": [...]}
        self.updates: list[dict] = []

    async def find_one(self, query: dict) -> dict | None:
        if self.doc and self.doc.get("user_id") == query.get("user_id"):
            return self.doc
        return None

    async def update_one(self, query: dict, update: dict, upsert: bool = False):
        self.updates.append({"query": query, "update": update, "upsert": upsert})
        # 简化：若 $push 则追加到 self.doc.favorites
        if self.doc is None and upsert:
            self.doc = {"user_id": query.get("user_id"), "favorites": []}
        if self.doc is not None and "$push" in update:
            push_target = update["$push"]
            for field, val in push_target.items():
                self.doc.setdefault(field, []).append(val)

        class _R:
            matched_count = 1 if self.doc else 0
            modified_count = 1 if self.doc else 0
            upserted_id = None

        return _R()


class _FakeDB:
    def __init__(self, fav_coll: _FakeFavoritesCollection) -> None:
        self.user_favorites = fav_coll
        self.users = _FakeFavoritesCollection()  # 不会被命中（_is_valid_object_id=False）


def _make_service_with_existing(n: int) -> tuple[FavoritesService, _FakeFavoritesCollection]:
    """构造一个 user 已有 N 条自选的 service."""
    favorites = [
        {
            "stock_code": f"{i:06d}",
            "stock_name": f"测试股{i}",
            "added_at": datetime(2026, 5, 1, 0, 0, i),
            "order": i,
        }
        for i in range(n)
    ]
    coll = _FakeFavoritesCollection({"user_id": "user_A", "favorites": favorites})
    svc = FavoritesService()
    svc.db = _FakeDB(coll)
    return svc, coll


@pytest.mark.unit
def test_add_below_limit_ok():
    """< 10 支时 add 正常."""
    svc, coll = _make_service_with_existing(5)

    async def _run():
        ok = await svc.add_favorite("user_A", "999001", "测试新股")
        assert ok is True
        # 写入 favorites 增 1
        assert len(coll.doc["favorites"]) == 6

    asyncio.run(_run())


@pytest.mark.unit
def test_add_at_limit_raises():
    """已有 10 支 → add 第 11 支 raise FavoritesLimitExceededError."""
    svc, coll = _make_service_with_existing(10)
    initial_len = len(coll.doc["favorites"])

    async def _run():
        with pytest.raises(FavoritesLimitExceededError):
            await svc.add_favorite("user_A", "999001", "测试新股")
        # 不写 mongo
        assert len(coll.doc["favorites"]) == initial_len

    asyncio.run(_run())


@pytest.mark.unit
def test_grandfather_existing_over_limit_still_blocks_new_add():
    """已有 12 支（grandfather）→ add 第 13 支仍 raise；已有不强删."""
    svc, coll = _make_service_with_existing(12)
    initial_len = len(coll.doc["favorites"])

    async def _run():
        with pytest.raises(FavoritesLimitExceededError):
            await svc.add_favorite("user_A", "999001", "测试新股")
        # 已有 12 条保留不强删
        assert len(coll.doc["favorites"]) == initial_len

    asyncio.run(_run())


# ===== _format_favorite 透出 order 字段 =====


@pytest.mark.unit
def test_format_favorite_exposes_order_field():
    """_format_favorite 返回 dict 含 order 字段."""
    svc = FavoritesService()
    raw = {
        "stock_code": "000001",
        "stock_name": "平安银行",
        "order": 3,
        "added_at": datetime(2026, 5, 1),
    }
    formatted = svc._format_favorite(raw)
    assert "order" in formatted
    assert formatted["order"] == 3


@pytest.mark.unit
def test_format_favorite_missing_order_returns_none():
    """旧文档缺 order → format 返 order=None（lazy migration 兜底）."""
    svc = FavoritesService()
    raw = {"stock_code": "000001", "stock_name": "平安银行"}
    formatted = svc._format_favorite(raw)
    assert formatted["order"] is None
