"""
每日推荐 API 路由。

暴露已持久化的每日推荐结果（列表 / 详情）、每日推荐的多个命名配置
（CRUD），并支持手动按配置触发推荐任务。结果文档由手动触发的任务写入
``daily_recommendations`` 集合，按 ``(date, config_id)`` 唯一。
"""

import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.database import get_mongo_db
from app.routers.auth_db import get_current_user
from app.services.daily_recommendation_service import (
    create_config,
    delete_config,
    list_configs,
    load_config,
    run_daily_recommendation,
    update_config,
)

router = APIRouter()
logger = logging.getLogger("webapi")

# Collection holding one document per (date, config) daily-recommendation run.
_COLLECTION = "daily_recommendations"


class RunRequest(BaseModel):
    """``POST /run`` 请求体：指定要执行的配置。"""

    config_id: str


@router.get("", response_model=Dict[str, Any])
async def list_daily_recommendations(
    user: dict = Depends(get_current_user),
    config_id: str | None = Query(None, description="按配置过滤；缺省返回全部"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """获取每日推荐列表（按日期倒序，支持分页）。

    每条记录返回摘要字段：``date`` / ``status`` / ``stock_count`` /
    ``config_id`` / ``config_name``。传 ``config_id`` 时只返回该配置的历史。
    """
    try:
        db = get_mongo_db()
        coll = db[_COLLECTION]

        query: dict[str, Any] = {}
        if config_id:
            query["config_id"] = config_id

        cursor = (
            coll.find(
                query,
                {
                    "date": 1,
                    "status": 1,
                    "stocks": 1,
                    "config_id": 1,
                    "config_name": 1,
                    "_id": 0,
                },
            )
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
                "config_id": doc.get("config_id"),
                "config_name": doc.get("config_name"),
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


@router.get("/configs", response_model=Dict[str, Any])
async def list_recommendation_configs(user: dict = Depends(get_current_user)):
    """列出所有每日推荐配置（config/daily_recommendations/ 下每个文件一个）。"""
    try:
        return {
            "success": True,
            "data": list_configs(),
            "message": "配置列表获取成功",
        }
    except Exception as e:
        logger.error(f"❌ 获取每日推荐配置列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/configs", response_model=Dict[str, Any])
async def create_recommendation_config(
    config: Dict[str, Any],
    user: dict = Depends(get_current_user),
):
    """新建一个每日推荐配置；校验失败返回 400 + 具体错误。"""
    try:
        stored = create_config(config)
        return {"success": True, "data": stored, "message": "配置已创建"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 创建每日推荐配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/configs/{config_id}", response_model=Dict[str, Any])
async def get_recommendation_config(
    config_id: str,
    user: dict = Depends(get_current_user),
):
    """读取单个每日推荐配置。"""
    try:
        return {"success": True, "data": load_config(config_id), "message": "配置获取成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="配置不存在")
    except Exception as e:
        logger.error(f"❌ 获取每日推荐配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/configs/{config_id}", response_model=Dict[str, Any])
async def update_recommendation_config(
    config_id: str,
    config: Dict[str, Any],
    user: dict = Depends(get_current_user),
):
    """校验并更新指定配置；校验失败 400，配置不存在 404。"""
    try:
        stored = update_config(config_id, config)
        return {"success": True, "data": stored, "message": "配置已保存"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="配置不存在")
    except Exception as e:
        logger.error(f"❌ 保存每日推荐配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/configs/{config_id}", response_model=Dict[str, Any])
async def delete_recommendation_config(
    config_id: str,
    user: dict = Depends(get_current_user),
):
    """删除指定配置文件。历史推荐结果不受影响。"""
    try:
        delete_config(config_id)
        return {"success": True, "data": None, "message": "配置已删除"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="配置不存在")
    except Exception as e:
        logger.error(f"❌ 删除每日推荐配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/result-configs", response_model=Dict[str, Any])
async def list_result_configs(user: dict = Depends(get_current_user)):
    """列出历史结果中出现过的配置（config_id + config_name，去重）。

    前端用它补齐配置选择器 —— 已删除但仍有历史结果的配置据此可见。
    """
    try:
        db = get_mongo_db()
        coll = db[_COLLECTION]
        pipeline = [
            {
                "$group": {
                    "_id": "$config_id",
                    "config_name": {"$first": "$config_name"},
                }
            }
        ]
        rows = await coll.aggregate(pipeline).to_list(length=None)
        data = [
            {"config_id": r["_id"], "config_name": r.get("config_name")}
            for r in rows
            if r.get("_id")
        ]
        return {"success": True, "data": data, "message": "结果配置列表获取成功"}
    except Exception as e:
        logger.error(f"❌ 获取结果配置列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run", response_model=Dict[str, Any])
async def trigger_daily_recommendation(
    req: RunRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """手动触发指定配置的当日推荐任务（后台异步执行，立即返回）。

    查重维度为 ``(今日, config_id)`` —— 集合对 ``(date, config_id)`` 有复合
    唯一索引，重复触发会在后台任务里抛 ``DuplicateKeyError``。这里在请求阶段
    先查重，命中则直接返回提示。
    """
    config_id = req.config_id
    try:
        # 配置必须存在才允许触发
        try:
            load_config(config_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="配置不存在")

        today = datetime.now().strftime("%Y-%m-%d")

        db = get_mongo_db()
        coll = db[_COLLECTION]
        existing = await coll.find_one(
            {"date": today, "config_id": config_id}, {"_id": 1}
        )
        if existing:
            logger.info(f"⚠️ 该配置今日推荐已存在，跳过触发: {today} / {config_id}")
            return {
                "success": False,
                "data": None,
                "message": "该配置今日推荐已生成，请勿重复触发",
            }

        async def run_recommendation_task():
            """包装函数：在后台运行每日推荐任务。"""
            try:
                logger.info(f"🚀 [BackgroundTask] 开始执行每日推荐任务: {config_id}")
                await run_daily_recommendation(config_id)
                logger.info("✅ [BackgroundTask] 每日推荐任务完成")
            except Exception as e:
                logger.error(
                    f"❌ [BackgroundTask] 每日推荐任务失败: {e}", exc_info=True
                )

        background_tasks.add_task(run_recommendation_task)
        logger.info(f"✅ 每日推荐任务已在后台启动: {today} / {config_id}")

        return {
            "success": True,
            "data": {"date": today, "config_id": config_id},
            "message": "每日推荐任务已在后台启动",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 触发每日推荐任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{date}", response_model=Dict[str, Any])
async def get_daily_recommendation(
    date: str,
    config_id: str = Query(..., description="配置 id"),
    user: dict = Depends(get_current_user),
):
    """获取指定日期 + 配置的每日推荐完整文档（含 ``stocks`` 数组）。"""
    try:
        db = get_mongo_db()
        coll = db[_COLLECTION]

        doc = await coll.find_one(
            {"date": date, "config_id": config_id}, {"_id": 0}
        )
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
