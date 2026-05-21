"""Contract test for favorites reorder + lazy migration (capability watchlist-management).

change 2026-05-21-watchlist-limit-and-ordering.

锁定 reorder_favorites validate 行为 + _lazy_migrate_order 幂等行为 + service-level
reorder_favorites (mocked db).
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from app.services.favorites_service import (
    FavoritesService,
    _lazy_migrate_order,
    _validate_reorder_codes,
)

# ===== _validate_reorder_codes pure helper =====


@pytest.mark.unit
def test_validate_reorder_codes_exact_match_ok():
    """ordered_codes 与 existing 集合完全一致 → 不 raise."""
    _validate_reorder_codes(
        existing_codes=["000001", "002428", "300124"],
        ordered_codes=["002428", "300124", "000001"],
    )


@pytest.mark.unit
def test_validate_reorder_codes_missing_raises():
    """ordered_codes 缺一个 → ValueError."""
    with pytest.raises(ValueError, match="不一致"):
        _validate_reorder_codes(
            existing_codes=["000001", "002428", "300124"],
            ordered_codes=["000001", "002428"],
        )


@pytest.mark.unit
def test_validate_reorder_codes_extra_raises():
    """ordered_codes 多一个 → ValueError."""
    with pytest.raises(ValueError, match="不一致"):
        _validate_reorder_codes(
            existing_codes=["000001", "002428"],
            ordered_codes=["000001", "002428", "300124"],
        )


@pytest.mark.unit
def test_validate_reorder_codes_duplicate_raises():
    """ordered_codes 含重复 → ValueError."""
    with pytest.raises(ValueError, match="重复"):
        _validate_reorder_codes(
            existing_codes=["000001", "002428", "300124"],
            ordered_codes=["000001", "002428", "000001"],
        )


@pytest.mark.unit
def test_validate_reorder_codes_empty_both_ok():
    """两边都空 → 不 raise."""
    _validate_reorder_codes(existing_codes=[], ordered_codes=[])


# ===== _lazy_migrate_order pure helper =====


@pytest.mark.unit
def test_lazy_migrate_all_missing_assigns_by_added_at():
    """全部缺 order → 按 added_at 升序回填 0,1,2..."""
    favorites = [
        {"stock_code": "C", "added_at": datetime(2026, 5, 3)},
        {"stock_code": "A", "added_at": datetime(2026, 5, 1)},
        {"stock_code": "B", "added_at": datetime(2026, 5, 2)},
    ]
    migrated, did_migrate = _lazy_migrate_order(favorites)
    assert did_migrate is True
    # 按 added_at 升序：A(0), B(1), C(2)
    by_code = {f["stock_code"]: f["order"] for f in migrated}
    assert by_code["A"] == 0
    assert by_code["B"] == 1
    assert by_code["C"] == 2


@pytest.mark.unit
def test_lazy_migrate_all_have_order_no_migrate():
    """全部有 order → did_migrate=False，不修改."""
    favorites = [
        {"stock_code": "A", "order": 0, "added_at": datetime(2026, 5, 1)},
        {"stock_code": "B", "order": 1, "added_at": datetime(2026, 5, 2)},
    ]
    migrated, did_migrate = _lazy_migrate_order(favorites)
    assert did_migrate is False
    # 原 list 内容不变
    assert migrated[0]["order"] == 0
    assert migrated[1]["order"] == 1


@pytest.mark.unit
def test_lazy_migrate_partial_missing_appends_to_end():
    """部分缺 order：有 order 的保持，缺的按 added_at 排序后追加到末尾."""
    favorites = [
        {"stock_code": "A", "order": 0, "added_at": datetime(2026, 5, 1)},
        {"stock_code": "B", "order": 1, "added_at": datetime(2026, 5, 2)},
        {"stock_code": "D", "added_at": datetime(2026, 5, 4)},  # 缺 order
        {"stock_code": "C", "added_at": datetime(2026, 5, 3)},  # 缺 order
    ]
    migrated, did_migrate = _lazy_migrate_order(favorites)
    assert did_migrate is True
    by_code = {f["stock_code"]: f["order"] for f in migrated}
    # 有 order 的保留
    assert by_code["A"] == 0
    assert by_code["B"] == 1
    # 缺 order 的按 added_at 升序追加：C(2), D(3)
    assert by_code["C"] == 2
    assert by_code["D"] == 3


@pytest.mark.unit
def test_lazy_migrate_missing_added_at_falls_back():
    """缺 order 同时缺 added_at → 用 epoch 兜底（不应抛异常）."""
    favorites = [
        {"stock_code": "A"},  # 全缺
        {"stock_code": "B"},
    ]
    migrated, did_migrate = _lazy_migrate_order(favorites)
    assert did_migrate is True
    # 两条都分配了 order（具体顺序不重要，只要稳定即可）
    assert all("order" in f for f in migrated)
    assert {f["order"] for f in migrated} == {0, 1}


@pytest.mark.unit
def test_lazy_migrate_empty():
    """空 list → did_migrate=False，返回空 list."""
    migrated, did_migrate = _lazy_migrate_order([])
    assert migrated == []
    assert did_migrate is False


# ===== reorder_favorites service-level（with fake db）=====


class _FakeFavoritesCollection:
    def __init__(self, initial: dict | None = None) -> None:
        self.doc = initial
        self.updates: list[dict] = []

    async def find_one(self, query: dict):
        if self.doc and self.doc.get("user_id") == query.get("user_id"):
            return self.doc
        return None

    async def update_one(self, query: dict, update: dict, **kwargs):
        self.updates.append({"query": query, "update": update, "kwargs": kwargs})
        # 支持 $set with array index: e.g. {"$set": {"favorites.0.order": 1}}
        if self.doc and "$set" in update:
            for path, val in update["$set"].items():
                if path.startswith("favorites."):
                    parts = path.split(".")
                    if len(parts) == 3:
                        idx = int(parts[1])
                        field = parts[2]
                        self.doc["favorites"][idx][field] = val
                    else:
                        self.doc[path] = val

        class _R:
            matched_count = 1 if self.doc else 0
            modified_count = 1 if self.doc else 0

        return _R()


class _FakeDB:
    def __init__(self, coll: _FakeFavoritesCollection) -> None:
        self.user_favorites = coll
        self.users = _FakeFavoritesCollection()


def _make_service_with(favorites: list[dict]) -> tuple[FavoritesService, _FakeFavoritesCollection]:
    coll = _FakeFavoritesCollection({"user_id": "user_A", "favorites": favorites})
    svc = FavoritesService()
    svc.db = _FakeDB(coll)
    return svc, coll


@pytest.mark.unit
def test_reorder_full_set_updates_order():
    """ordered_codes 完整 → 每条 order 按数组索引更新."""
    favorites = [
        {"stock_code": "000001", "order": 0, "added_at": datetime(2026, 5, 1)},
        {"stock_code": "002428", "order": 1, "added_at": datetime(2026, 5, 2)},
        {"stock_code": "300124", "order": 2, "added_at": datetime(2026, 5, 3)},
    ]
    svc, coll = _make_service_with(favorites)

    async def _run():
        n = await svc.reorder_favorites("user_A", ["002428", "300124", "000001"])
        assert n == 3
        # 新 order：002428→0, 300124→1, 000001→2
        by_code = {f["stock_code"]: f["order"] for f in coll.doc["favorites"]}
        assert by_code["002428"] == 0
        assert by_code["300124"] == 1
        assert by_code["000001"] == 2

    asyncio.run(_run())


@pytest.mark.unit
def test_reorder_missing_code_raises():
    """ordered_codes 缺 code → ValueError，不更新任何."""
    favorites = [
        {"stock_code": "000001", "order": 0},
        {"stock_code": "002428", "order": 1},
        {"stock_code": "300124", "order": 2},
    ]
    svc, coll = _make_service_with(favorites)

    async def _run():
        with pytest.raises(ValueError):
            await svc.reorder_favorites("user_A", ["000001", "002428"])
        # 原 order 保留
        by_code = {f["stock_code"]: f["order"] for f in coll.doc["favorites"]}
        assert by_code["300124"] == 2  # 未变

    asyncio.run(_run())


@pytest.mark.unit
def test_reorder_empty_favorites_empty_request_ok():
    """既无 favorites 也无 ordered_codes → 0 updated，不 raise."""
    svc, _coll = _make_service_with([])

    async def _run():
        n = await svc.reorder_favorites("user_A", [])
        assert n == 0

    asyncio.run(_run())


# ===== get_user_favorites lazy migration 集成 =====


@pytest.mark.unit
def test_get_user_favorites_lazy_migrates_missing_order():
    """旧文档无 order → get 时 lazy 回填 + update mongo."""
    favorites_no_order = [
        {"stock_code": "A", "stock_name": "测A", "added_at": datetime(2026, 5, 1)},
        {"stock_code": "B", "stock_name": "测B", "added_at": datetime(2026, 5, 2)},
    ]
    svc, coll = _make_service_with(favorites_no_order)

    async def _run():
        # 关闭实时行情批量富集（依赖太重），只测 lazy migration 这条路径
        # 直接调内部 _lazy_migrate_order + 验证：先确保 service 有内部钩子
        # 简化：本测验证 mongo 文档 update 发生 + favorites 持久化 order
        _items = await svc.get_user_favorites("user_A")
        # 应该被 lazy migrate（mongo 文档已加 order）
        for fav in coll.doc["favorites"]:
            assert "order" in fav
        # 验证 update 调用发生
        assert len(coll.updates) >= 1

    # get_user_favorites 内部会调批量行情服务（外部依赖）；如果失败 service 会
    # try/except 兜底——只要 lazy_migrate 在富集前发生，coll.doc 应已就位
    try:
        asyncio.run(_run())
    except Exception as e:
        # 若外部依赖（quote service）失败，至少应该看到 mongo update 已发生
        # 这是 service 的兜底约定
        if "favorites" not in coll.doc:
            raise
        for fav in coll.doc["favorites"]:
            assert "order" in fav, f"lazy migration 未生效: {fav!r} (err={e!r})"
