"""
Daily recommendation service.

Loads the feature configuration and orchestrates the post-market screening +
multi-agent analysis cron job: screen a handful of stocks, run a standard-depth
analysis on each, and persist a single ``daily_recommendations`` document.
"""

import copy
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.database import get_mongo_db
from app.models.analysis import AnalysisParameters, SingleAnalysisRequest
from app.models.screening import ScreeningCondition
from app.services.enhanced_screening_service import get_enhanced_screening_service
from app.services.simple_analysis_service import get_simple_analysis_service

logger = logging.getLogger(__name__)

# Collection holding one document per daily-recommendation run.
_COLLECTION = "daily_recommendations"

# System identifier for cron-initiated analysis tasks. The analysis service
# maps the literal "admin" to a fixed ObjectId (see SimpleAnalysisService.
# _convert_user_id), so this job has no real user behind it.
_SYSTEM_USER_ID = "admin"

# Resolved once at import time; tests can monkeypatch this module attribute.
_CONFIG_PATH: Path = (
    Path(__file__).parent.parent.parent / "config" / "daily_recommendation.json"
)

_SAFE_DEFAULT: dict[str, Any] = {
    "enabled": False,
    "screening": {
        "conditions": [],
        "order_by": "market_cap",
        "order_direction": "desc",
        "limit": 5,
    },
    "analysis": {
        "research_depth": "标准",
        "market_type": "A股",
    },
}

# save_config 校验用的允许值集合
_VALID_DIRECTIONS = {"asc", "desc"}
_VALID_RESEARCH_DEPTHS = {"快速", "标准", "深度"}
_VALID_MARKET_TYPES = {"A股"}


def load_config() -> dict[str, Any]:
    """Load the daily-recommendation config from *config/daily_recommendation.json*.

    Returns the parsed dict on success.  Falls back to a safe default
    (``enabled=False``) if the file is absent or contains invalid JSON, and
    logs a warning in both cases.
    """
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        logger.warning(
            "daily_recommendation.json not found at %s; using safe default",
            _CONFIG_PATH,
        )
    except json.JSONDecodeError as exc:
        logger.warning(
            "Failed to parse daily_recommendation.json (%s); using safe default",
            exc,
        )
    return copy.deepcopy(_SAFE_DEFAULT)


def _validate_config(cfg: Any) -> None:
    """校验配置结构，非法则抛 ValueError（消息面向用户）。

    形参类型用 Any（非 dict）—— 配置可能来自 PUT 请求的任意 JSON body，
    非对象（如数组）应被首行 isinstance 守卫拦成 400，而非 500。
    """
    from app.models.screening import BASIC_FIELDS_INFO, OperatorType

    if not isinstance(cfg, dict):
        raise ValueError("配置必须是一个对象")
    if not isinstance(cfg.get("enabled"), bool):
        raise ValueError("enabled 必须是布尔值")

    screening = cfg.get("screening")
    if not isinstance(screening, dict):
        raise ValueError("screening 必须是一个对象")

    limit = screening.get("limit")
    # bool 是 int 的子类，需显式排除
    if not isinstance(limit, int) or isinstance(limit, bool) or not (1 <= limit <= 20):
        raise ValueError("screening.limit 必须是 1-20 的整数")

    if screening.get("order_direction") not in _VALID_DIRECTIONS:
        raise ValueError("screening.order_direction 必须是 asc 或 desc")

    order_by = screening.get("order_by")
    valid_order_fields = set(BASIC_FIELDS_INFO) | {"market_cap"}
    if not isinstance(order_by, str) or order_by not in valid_order_fields:
        raise ValueError(f"screening.order_by 必须是已知字段名，收到: {order_by!r}")

    conditions = screening.get("conditions")
    if not isinstance(conditions, list):
        raise ValueError("screening.conditions 必须是数组")
    for i, cond in enumerate(conditions, 1):
        if not isinstance(cond, dict):
            raise ValueError(f"条件 {i}: 必须是对象")
        if "value" not in cond:
            raise ValueError(f"条件 {i}: 缺少 value")
        field = cond.get("field")
        if field not in BASIC_FIELDS_INFO:
            raise ValueError(f"条件 {i}: 不支持的字段 {field!r}")
        try:
            op = OperatorType(cond.get("operator"))
        except ValueError:
            raise ValueError(f"条件 {i}: 非法操作符 {cond.get('operator')!r}") from None
        if op not in BASIC_FIELDS_INFO[field].supported_operators:
            raise ValueError(f"条件 {i}: 字段 {field!r} 不支持操作符 {op.value!r}")

    analysis = cfg.get("analysis")
    if not isinstance(analysis, dict):
        raise ValueError("analysis 必须是一个对象")
    if analysis.get("research_depth") not in _VALID_RESEARCH_DEPTHS:
        raise ValueError("analysis.research_depth 必须是 快速/标准/深度 之一")
    if analysis.get("market_type") not in _VALID_MARKET_TYPES:
        raise ValueError("analysis.market_type 目前仅支持 A股")


def save_config(cfg: dict[str, Any]) -> None:
    """校验 *cfg* 并写入 config/daily_recommendation.json。

    校验不通过抛 ValueError（router 转 400）。写文件用 ensure_ascii=False
    保持中文可读，与现有文件格式一致。
    """
    _validate_config(cfg)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    logger.info("每日推荐配置已保存: %s", _CONFIG_PATH)


async def _select_stocks(cfg: dict[str, Any]) -> list[dict[str, str]]:
    """Run the configured screening and return up to ``limit`` stocks.

    Each returned dict has ``symbol`` and ``name`` keys. The config stores
    ``order_by`` / ``order_direction`` as plain strings and ``conditions`` as
    plain dicts; here they are translated into the shapes the screening
    service expects (a ``List[Dict[str, str]]`` for ordering and
    ``ScreeningCondition`` objects for the filter).
    """
    screening = cfg.get("screening", {})
    limit = int(screening.get("limit", 5))

    conditions = [
        ScreeningCondition(**cond) for cond in screening.get("conditions", [])
    ]

    order_by: list[dict[str, str]] | None = None
    order_field = screening.get("order_by")
    if order_field:
        order_by = [
            {
                "field": str(order_field),
                "direction": str(screening.get("order_direction", "desc")),
            }
        ]

    service = get_enhanced_screening_service()
    result = await service.screen_stocks(
        conditions=conditions,
        limit=limit,
        order_by=order_by,
    )

    items = result.get("items", []) or []
    stocks: list[dict[str, str]] = []
    for item in items[:limit]:
        code = str(item.get("code") or item.get("symbol") or "").strip()
        if not code:
            continue
        stocks.append({"symbol": code, "name": str(item.get("name") or code)})
    return stocks


async def _analyze_one(symbol: str, cfg: dict[str, Any]) -> dict[str, Any]:
    """Run a single standard-depth analysis to completion and return its result.

    Returns a dict with ``task_id`` / ``recommendation`` / ``summary`` /
    ``risk_level``. ``execute_analysis_background`` is a coroutine; awaiting it
    directly runs the analysis synchronously to completion, after which the
    result is read back via ``get_task_status``.

    ``execute_analysis_background`` does *not* re-raise when an analysis fails —
    it marks the task ``failed`` and returns normally. Failure is therefore
    detected by inspecting the task status here and raising, which lets the
    orchestrator's per-stock ``except`` branch mark the stock ``failed``.
    """
    analysis_cfg = cfg.get("analysis", {})
    request = SingleAnalysisRequest(
        symbol=symbol,
        # stock_code is nominally deprecated, but simple_analysis_service feeds
        # the analysis graph `request.stock_code` directly — it must be set too,
        # otherwise the graph analyses a None ticker.
        stock_code=symbol,
        parameters=AnalysisParameters(
            market_type=analysis_cfg.get("market_type", "A股"),
            research_depth=analysis_cfg.get("research_depth", "标准"),
        ),
    )

    service = get_simple_analysis_service()
    created = await service.create_analysis_task(_SYSTEM_USER_ID, request)
    task_id = created["task_id"]

    await service.execute_analysis_background(task_id, _SYSTEM_USER_ID, request)

    status = await service.get_task_status(task_id) or {}

    # get_task_status returns TaskState.to_dict(), whose "status" key holds the
    # plain TaskStatus value string ("failed" for a failed task). A failed
    # analysis surfaces here, not as a raised exception.
    task_status = str(status.get("status") or "").lower()
    if task_status == "failed":
        raise RuntimeError(
            str(status.get("error_message") or f"analysis failed for {symbol}")
        )

    result_data = status.get("result_data") or {}
    return {
        "task_id": task_id,
        "recommendation": result_data.get("recommendation"),
        "summary": result_data.get("summary"),
        "risk_level": result_data.get("risk_level"),
    }


async def _persist_initial(cfg: dict[str, Any], stocks: list[dict[str, str]]) -> Any:
    """Ensure the unique index, then insert the initial ``running`` document.

    Returns the inserted document ``_id`` so the run can be finalised later.
    """
    db = get_mongo_db()
    coll = db[_COLLECTION]
    await coll.create_index("date", unique=True)

    doc = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "status": "running",
        "config_snapshot": cfg,
        "stocks": [
            {
                "symbol": s["symbol"],
                "name": s["name"],
                "task_id": None,
                "recommendation": None,
                "summary": None,
                "risk_level": None,
                "status": "pending",
            }
            for s in stocks
        ],
        "created_at": datetime.now(),
    }
    insert_result = await coll.insert_one(doc)
    return insert_result.inserted_id


async def _persist_final(
    doc_id: Any, stocks: list[dict[str, Any]], status: str
) -> None:
    """Update the run document with the analysed stocks and the final status."""
    db = get_mongo_db()
    coll = db[_COLLECTION]
    await coll.update_one(
        {"_id": doc_id},
        {
            "$set": {
                "status": status,
                "stocks": stocks,
                "completed_at": datetime.now(),
            }
        },
    )


async def run_daily_recommendation() -> None:
    """Orchestrate the daily screening + analysis run.

    Flow: load config -> (if enabled) screen up to ``limit`` stocks -> persist a
    ``running`` document -> analyse each stock serially -> persist the final
    document with status ``completed`` / ``partial`` / ``failed``.
    """
    cfg = load_config()
    if not cfg.get("enabled"):
        logger.info("Daily recommendation is disabled; skipping run")
        return

    stocks = await _select_stocks(cfg)
    logger.info("Daily recommendation: screened %d stock(s)", len(stocks))

    doc_id = await _persist_initial(cfg, stocks)

    analysed: list[dict[str, Any]] = []
    failed_count = 0
    for stock in stocks:
        symbol = stock["symbol"]
        entry: dict[str, Any] = {
            "symbol": symbol,
            "name": stock["name"],
            "task_id": None,
            "recommendation": None,
            "summary": None,
            "risk_level": None,
            "status": "pending",
        }
        try:
            outcome = await _analyze_one(symbol, cfg)
            entry.update(
                task_id=outcome["task_id"],
                recommendation=outcome["recommendation"],
                summary=outcome["summary"],
                risk_level=outcome["risk_level"],
                status="completed",
            )
        except Exception as exc:  # noqa: BLE001 - one bad stock must not abort the run
            logger.error("Daily recommendation: analysis failed for %s: %s", symbol, exc)
            entry["status"] = "failed"
            failed_count += 1
        analysed.append(entry)

    if not analysed:
        overall_status = "completed"
    elif failed_count == len(analysed):
        overall_status = "failed"
    elif failed_count > 0:
        overall_status = "partial"
    else:
        overall_status = "completed"

    await _persist_final(doc_id, analysed, overall_status)
    logger.info(
        "Daily recommendation finished: status=%s (%d ok, %d failed)",
        overall_status,
        len(analysed) - failed_count,
        failed_count,
    )
