"""Router-level contract test for favorites limit (409) + /reorder endpoint.

capability watchlist-management（change 2026-05-21-watchlist-limit-and-ordering）.

锁定 HTTP 边界：
- POST /favorites/ 触发 FavoritesLimitExceededError → status 409
- PUT /favorites/reorder body 校验 + 400 on 不一致
- PUT /favorites/reorder ok 路径 → 200

测试用 unittest.mock 直接 monkeypatch favorites_service 方法，不起完整 FastAPI app
（auth + middleware 依赖太多）；改为直接调 router handler 函数.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.routers.favorites import (
    AddFavoriteRequest,
    ReorderFavoritesRequest,
    add_favorite,
    reorder_favorites,
)
from app.services.favorites_service import FavoritesLimitExceededError

FAKE_USER = {"id": "user_A", "username": "tester"}


@pytest.mark.unit
def test_router_post_returns_409_on_limit():
    """service raise FavoritesLimitExceededError → router 转 409 Conflict."""

    async def _run():
        with (
            patch(
                "app.routers.favorites.favorites_service.is_favorite",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.routers.favorites.favorites_service.add_favorite",
                new=AsyncMock(side_effect=FavoritesLimitExceededError("已达自选股上限 10 支")),
            ),
        ):
            req = AddFavoriteRequest(stock_code="002428", stock_name="云南锗业")
            with pytest.raises(HTTPException) as exc_info:
                await add_favorite(req, current_user=FAKE_USER)
            assert exc_info.value.status_code == 409
            assert "上限" in exc_info.value.detail

    asyncio.run(_run())


@pytest.mark.unit
def test_router_post_already_exists_returns_400():
    """已存在 → 400（既有行为 regression guard）."""

    async def _run():
        with patch(
            "app.routers.favorites.favorites_service.is_favorite",
            new=AsyncMock(return_value=True),
        ):
            req = AddFavoriteRequest(stock_code="002428", stock_name="云南锗业")
            with pytest.raises(HTTPException) as exc_info:
                await add_favorite(req, current_user=FAKE_USER)
            assert exc_info.value.status_code == 400

    asyncio.run(_run())


@pytest.mark.unit
def test_router_post_ok_path():
    """service add_favorite True → 200 success（regression guard）."""

    async def _run():
        with (
            patch(
                "app.routers.favorites.favorites_service.is_favorite",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.routers.favorites.favorites_service.add_favorite",
                new=AsyncMock(return_value=True),
            ),
        ):
            req = AddFavoriteRequest(stock_code="002428", stock_name="云南锗业")
            result = await add_favorite(req, current_user=FAKE_USER)
            # ok() wraps in {"success": True, "data": ..., ...}
            assert result["success"] is True
            assert result["data"]["stock_code"] == "002428"

    asyncio.run(_run())


@pytest.mark.unit
def test_router_reorder_ok():
    """service reorder_favorites 返 N → 200 + {updated: N}."""

    async def _run():
        with patch(
            "app.routers.favorites.favorites_service.reorder_favorites",
            new=AsyncMock(return_value=3),
        ):
            req = ReorderFavoritesRequest(order=["002428", "300124", "000001"])
            result = await reorder_favorites(req, current_user=FAKE_USER)
            assert result["success"] is True
            assert result["data"]["updated"] == 3

    asyncio.run(_run())


@pytest.mark.unit
def test_router_reorder_missing_code_returns_400():
    """service raise ValueError（codes 集合不一致）→ router 转 400."""

    async def _run():
        with patch(
            "app.routers.favorites.favorites_service.reorder_favorites",
            new=AsyncMock(side_effect=ValueError("ordered_codes 与现有 codes 集合不一致 (existing=[...], ordered=[...])")),
        ):
            req = ReorderFavoritesRequest(order=["002428"])
            with pytest.raises(HTTPException) as exc_info:
                await reorder_favorites(req, current_user=FAKE_USER)
            assert exc_info.value.status_code == 400
            assert "不一致" in exc_info.value.detail

    asyncio.run(_run())


@pytest.mark.unit
def test_router_reorder_duplicate_returns_400():
    """service raise ValueError (含重复) → 400."""

    async def _run():
        with patch(
            "app.routers.favorites.favorites_service.reorder_favorites",
            new=AsyncMock(side_effect=ValueError("ordered_codes 含重复 code")),
        ):
            req = ReorderFavoritesRequest(order=["000001", "000001"])
            with pytest.raises(HTTPException) as exc_info:
                await reorder_favorites(req, current_user=FAKE_USER)
            assert exc_info.value.status_code == 400

    asyncio.run(_run())


@pytest.mark.unit
def test_router_reorder_service_500_passes_through():
    """service 抛非 ValueError 异常 → router 转 500."""

    async def _run():
        with patch(
            "app.routers.favorites.favorites_service.reorder_favorites",
            new=AsyncMock(side_effect=RuntimeError("mongo connection lost")),
        ):
            req = ReorderFavoritesRequest(order=["000001"])
            with pytest.raises(HTTPException) as exc_info:
                await reorder_favorites(req, current_user=FAKE_USER)
            assert exc_info.value.status_code == 500

    asyncio.run(_run())
