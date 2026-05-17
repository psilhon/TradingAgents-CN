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
    """
    analysis_cfg = cfg.get("analysis", {})
    request = SingleAnalysisRequest(
        symbol=symbol,
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
