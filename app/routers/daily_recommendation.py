"""
每日推荐API路由

暴露已持久化的每日推荐结果（列表 / 详情）并支持手动触发当日推荐任务。
推荐结果由收盘后定时任务写入 ``daily_recommendations`` 集合。
"""

import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.core.database import get_mongo_db
from app.routers.auth_db import get_current_user
from app.services.daily_recommendation_service import (
    load_config,
    run_daily_recommendation,
    save_config,
)

router = APIRouter()
logger = logging.getLogger("webapi")

# Collection holding one document per daily-recommendation run.
_COLLECTION = "daily_recommendations"


@router.get("", response_model=Dict[str, Any])
async def list_daily_recommendations(
    user: dict = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """获取每日推荐列表（按日期倒序，支持分页）。

    每条记录只返回摘要字段：``date`` / ``status`` / ``stock_count``。
    """
    try:
        db = get_mongo_db()
        coll = db[_COLLECTION]

        cursor = (
            coll.find({}, {"date": 1, "status": 1, "stocks": 1, "_id": 0})
            .sort("date", -1)
            .skip(offset)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)

        records = [
            {
                "date": doc.get("date"),
                "status": doc.get("status"),
                "stock_count": len(doc.get("stocks") or []),
            }
            for doc in docs
        ]

        return {
            "success": True,
            "data": records,
            "message": "每日推荐列表获取成功",
        }
    except Exception as e:
        logger.error(f"❌ 获取每日推荐列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config", response_model=Dict[str, Any])
async def get_recommendation_config(user: dict = Depends(get_current_user)):
    """读取每日推荐配置（config/daily_recommendation.json）。

    文件缺失 / JSON 损坏时 load_config 返回安全默认（enabled=False），不报错。
    """
    try:
        cfg = load_config()
        return {"success": True, "data": cfg, "message": "配置获取成功"}
    except Exception as e:
        logger.error(f"❌ 获取每日推荐配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config", response_model=Dict[str, Any])
async def update_recommendation_config(
    config: Dict[str, Any],
    user: dict = Depends(get_current_user),
):
    """校验并保存每日推荐配置；校验失败返回 400 + 具体错误。"""
    try:
        save_config(config)
        return {"success": True, "data": config, "message": "配置已保存"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 保存每日推荐配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{date}", response_model=Dict[str, Any])
async def get_daily_recommendation(
    date: str,
    user: dict = Depends(get_current_user),
):
    """获取指定日期的每日推荐完整文档（含 ``stocks`` 数组）。"""
    try:
        db = get_mongo_db()
        coll = db[_COLLECTION]

        doc = await coll.find_one({"date": date}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="该日期的每日推荐不存在")

        return {
            "success": True,
            "data": doc,
            "message": "每日推荐详情获取成功",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取每日推荐详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run", response_model=Dict[str, Any])
async def trigger_daily_recommendation(
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """手动触发当日每日推荐任务（后台异步执行，立即返回）。

    若当日推荐已存在则不再触发——``run_daily_recommendation`` 通过
    ``insert_one`` 写入，集合对 ``date`` 有唯一索引，重复触发会在后台
    任务里静默抛 ``DuplicateKeyError``。这里在请求阶段先查重，命中则
    直接返回提示。
    """
    try:
        today = datetime.now().strftime("%Y-%m-%d")

        db = get_mongo_db()
        coll = db[_COLLECTION]
        existing = await coll.find_one({"date": today}, {"_id": 1})
        if existing:
            logger.info(f"⚠️ 今日推荐已存在，跳过触发: {today}")
            return {
                "success": False,
                "data": None,
                "message": "今日推荐已生成，请勿重复触发",
            }

        async def run_recommendation_task():
            """包装函数：在后台运行每日推荐任务。"""
            try:
                logger.info("🚀 [BackgroundTask] 开始执行每日推荐任务")
                await run_daily_recommendation()
                logger.info("✅ [BackgroundTask] 每日推荐任务完成")
            except Exception as e:
                logger.error(
                    f"❌ [BackgroundTask] 每日推荐任务失败: {e}", exc_info=True
                )

        background_tasks.add_task(run_recommendation_task)
        logger.info(f"✅ 每日推荐任务已在后台启动: {today}")

        return {
            "success": True,
            "data": {"date": today},
            "message": "每日推荐任务已在后台启动",
        }
    except Exception as e:
        logger.error(f"❌ 触发每日推荐任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
