"""
Daily recommendation service.

Manages named daily-recommendation configs — one JSON file per config under
``config/daily_recommendations/`` — and orchestrates a manual screening +
multi-agent analysis run for a chosen config: screen a handful of stocks, run a
standard-depth analysis on each, and persist a ``daily_recommendations``
document keyed by ``(date, config_id)``.
"""

import json
import logging
import re
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.database import get_mongo_db
from app.models.analysis import AnalysisParameters, SingleAnalysisRequest
from app.models.screening import ScreeningCondition
from app.services.enhanced_screening_service import get_enhanced_screening_service
from app.services.simple_analysis_service import get_simple_analysis_service

logger = logging.getLogger(__name__)

# Collection holding one document per (date, config) daily-recommendation run.
_COLLECTION = "daily_recommendations"

# System identifier for system-initiated analysis tasks. The analysis service
# maps the literal "admin" to a fixed ObjectId (see SimpleAnalysisService.
# _convert_user_id), so this job has no real user behind it.
_SYSTEM_USER_ID = "admin"

# Resolved once at import time; tests can monkeypatch these module attributes.
_CONFIG_ROOT: Path = Path(__file__).parent.parent.parent / "config"
_CONFIG_DIR: Path = _CONFIG_ROOT / "daily_recommendations"
# Pre-multi-config single-file config — migrated into _CONFIG_DIR on startup.
_LEGACY_CONFIG_PATH: Path = _CONFIG_ROOT / "daily_recommendation.json"

# _validate_config 校验用的允许值集合
_VALID_DIRECTIONS = {"asc", "desc"}
_VALID_RESEARCH_DEPTHS = {"快速", "标准", "深度"}
_VALID_MARKET_TYPES = {"A股"}

# 配置 id：创建时生成的 8 位十六进制串。也用作文件名主干 —— 严格校验可挡住
# 路径穿越（如 "../foo"）。
_CONFIG_ID_RE = re.compile(r"^[0-9a-f]{8}$")

# 迁移前的历史结果文档没有 config_id，回填这个哨兵值。
_LEGACY_CONFIG_ID = "legacy"
_LEGACY_CONFIG_NAME = "迁移前历史"


# ---------------------------------------------------------------------------
# 配置 CRUD —— 目录多文件存储
# ---------------------------------------------------------------------------


def _new_config_id() -> str:
    """生成 8 位十六进制配置 id。"""
    return secrets.token_hex(4)


def _config_path(config_id: str) -> Path:
    """返回配置文件路径；id 非法（含路径穿越）抛 ValueError。"""
    if not isinstance(config_id, str) or not _CONFIG_ID_RE.match(config_id):
        raise ValueError(f"非法配置 id: {config_id!r}")
    return _CONFIG_DIR / f"{config_id}.json"


def _validate_config(cfg: Any) -> None:
    """校验配置结构，非法则抛 ValueError（消息面向用户）。

    形参类型用 Any —— 配置可能来自 PUT/POST 请求的任意 JSON body，
    非对象（如数组）应被首行 isinstance 守卫拦成 400，而非 500。
    ``id`` 由服务端管理，此处不校验。
    """
    from app.models.screening import BASIC_FIELDS_INFO, OperatorType

    if not isinstance(cfg, dict):
        raise ValueError("配置必须是一个对象")

    name = cfg.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name 必须是非空字符串")

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


def _normalized(config_id: str, cfg: dict[str, Any]) -> dict[str, Any]:
    """构造写盘用的标准配置 dict —— 只保留已知键，丢弃客户端传来的杂字段。"""
    return {
        "id": config_id,
        "name": cfg["name"],
        "screening": cfg["screening"],
        "analysis": cfg["analysis"],
    }


def _write_config(config_id: str, cfg: dict[str, Any]) -> None:
    """把配置写入 config/daily_recommendations/<id>.json。

    ensure_ascii=False 保持中文可读，与项目其他配置文件格式一致。
    """
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path = _config_path(config_id)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def list_configs() -> list[dict[str, Any]]:
    """返回 config/daily_recommendations/ 下所有配置，按 name 排序。

    目录不存在时返回空列表。无法解析的文件跳过并记 warning。
    """
    if not _CONFIG_DIR.is_dir():
        return []
    configs: list[dict[str, Any]] = []
    for path in sorted(_CONFIG_DIR.glob("*.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                configs.append(json.load(fh))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("跳过无法读取的配置文件 %s: %s", path, exc)
    configs.sort(key=lambda c: str(c.get("name", "")))
    return configs


def load_config(config_id: str) -> dict[str, Any]:
    """读取单个配置。

    id 非法抛 ValueError（router 转 400）；文件不存在抛 FileNotFoundError
    （router 转 404）；JSON 损坏抛 json.JSONDecodeError（router 转 500）。
    """
    path = _config_path(config_id)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def create_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """校验 *cfg*、生成 id、写文件，返回写盘后的标准配置 dict。

    校验不通过抛 ValueError（router 转 400）。
    """
    _validate_config(cfg)
    config_id = _new_config_id()
    stored = _normalized(config_id, cfg)
    _write_config(config_id, stored)
    logger.info("已新建每日推荐配置: %s (%s)", stored["name"], config_id)
    return stored


def update_config(config_id: str, cfg: dict[str, Any]) -> dict[str, Any]:
    """校验并覆盖写指定配置，返回写盘后的标准配置 dict。

    id 非法抛 ValueError；配置不存在抛 FileNotFoundError；校验不通过抛
    ValueError。
    """
    _validate_config(cfg)
    path = _config_path(config_id)
    if not path.exists():
        raise FileNotFoundError(f"配置不存在: {config_id}")
    stored = _normalized(config_id, cfg)
    _write_config(config_id, stored)
    logger.info("已更新每日推荐配置: %s (%s)", stored["name"], config_id)
    return stored


def delete_config(config_id: str) -> None:
    """删除指定配置文件。历史结果文档不受影响（保留 config_id/config_name）。

    id 非法抛 ValueError；配置不存在抛 FileNotFoundError。
    """
    path = _config_path(config_id)
    if not path.exists():
        raise FileNotFoundError(f"配置不存在: {config_id}")
    path.unlink()
    logger.info("已删除每日推荐配置: %s", config_id)


def migrate_legacy_config() -> None:
    """把改造前的单配置文件迁入 config/daily_recommendations/ 目录。

    幂等：目录里只要已有任意配置文件就直接返回。在任何 load_config 调用前、
    服务初始化早期执行。
    """
    if _CONFIG_DIR.is_dir() and any(_CONFIG_DIR.glob("*.json")):
        return
    if not _LEGACY_CONFIG_PATH.exists():
        return
    try:
        with open(_LEGACY_CONFIG_PATH, encoding="utf-8") as fh:
            legacy = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("无法读取旧配置 %s，跳过迁移: %s", _LEGACY_CONFIG_PATH, exc)
        return
    config_id = _new_config_id()
    migrated = {
        "id": config_id,
        "name": "默认配置",
        "screening": legacy.get("screening", {}),
        "analysis": legacy.get("analysis", {}),
    }
    _write_config(config_id, migrated)
    _LEGACY_CONFIG_PATH.unlink()
    logger.info("已迁移旧每日推荐配置 -> %s", _config_path(config_id))


# ---------------------------------------------------------------------------
# 执行：筛选 + 多智能体分析
# ---------------------------------------------------------------------------


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


async def _ensure_result_indexes(coll: Any) -> None:
    """迁移 daily_recommendations 集合索引到 (date, config_id) 复合唯一。

    顺序锁死：① 回填旧文档缺失的 config_id → ② 删旧的 date 单字段唯一索引
    → ③ 建复合唯一索引。三步均幂等，可安全重复执行。
    """
    # ① 回填迁移前没有 config_id 的历史文档
    await coll.update_many(
        {"config_id": {"$exists": False}},
        {"$set": {"config_id": _LEGACY_CONFIG_ID, "config_name": _LEGACY_CONFIG_NAME}},
    )
    # ② 删除过时的 date 单字段唯一索引（pymongo 默认名 date_1）
    async for index in coll.list_indexes():
        if index.get("name") == "date_1":
            await coll.drop_index("date_1")
            break
    # ③ 复合唯一索引
    await coll.create_index([("date", 1), ("config_id", 1)], unique=True)


async def _persist_initial(cfg: dict[str, Any], stocks: list[dict[str, str]]) -> Any:
    """Ensure the indexes, then insert the initial ``running`` document.

    Returns the inserted document ``_id`` so the run can be finalised later.
    """
    db = get_mongo_db()
    coll = db[_COLLECTION]
    await _ensure_result_indexes(coll)

    doc = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "config_id": cfg.get("id"),
        "config_name": cfg.get("name"),
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


async def run_daily_recommendation(config_id: str) -> None:
    """Orchestrate a screening + analysis run for the given config.

    Flow: load the config -> screen up to ``limit`` stocks -> persist a
    ``running`` document -> analyse each stock serially -> persist the final
    document with status ``completed`` / ``partial`` / ``failed``.

    Raises ``FileNotFoundError`` if the config was deleted before the run
    started (the router validates existence at trigger time, so this is rare).
    """
    cfg = load_config(config_id)

    stocks = await _select_stocks(cfg)
    logger.info(
        "Daily recommendation [%s]: screened %d stock(s)", config_id, len(stocks)
    )

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
        "Daily recommendation [%s] finished: status=%s (%d ok, %d failed)",
        config_id,
        overall_status,
        len(analysed) - failed_count,
        failed_count,
    )
