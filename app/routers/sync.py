"""
Sync router for stock basics synchronization
- POST /api/sync/stock_basics/run -> trigger full sync
- GET  /api/sync/stock_basics/status -> get last status
Requires MongoDB initialized by app lifespan.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.services.basics_sync_service import get_basics_sync_service
from app.routers.auth_db import get_current_user

router = APIRouter(prefix="/api/sync", tags=["sync"])


def _require_admin(user: dict) -> None:
    if not user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="权限不足")


@router.post("/stock_basics/run")
async def run_stock_basics_sync(
    force: bool = False,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        service = get_basics_sync_service()
        result = await service.run_full_sync(force=force)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock_basics/status")
async def get_stock_basics_status():
    service = get_basics_sync_service()
    status = await service.get_status()
    return {"success": True, "data": status}
