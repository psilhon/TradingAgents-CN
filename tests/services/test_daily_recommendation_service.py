"""
Tests for daily_recommendation_service:
- load_config()
- run_daily_recommendation() orchestration
"""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.daily_recommendation_service as svc

# ---------------------------------------------------------------------------
# Real-config smoke test (plan-mandated: proves the shipped JSON is loadable)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_config_reads_real_config_file():
    """load_config() can read config/daily_recommendation.json and returns a
    dict with the three required top-level keys."""
    config = svc.load_config()
    assert isinstance(config, dict)
    assert "enabled" in config
    assert "screening" in config
    assert "analysis" in config


# ---------------------------------------------------------------------------
# Value-parsing tests — isolated against a fixture JSON, not the shipped file
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_config_parses_values_correctly(tmp_path):
    """load_config() correctly parses all expected fields from a known JSON
    fixture, exercised in isolation from the shipped config file."""
    fixture = {
        "enabled": True,
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
    fixture_path = tmp_path / "daily_recommendation.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    with patch.object(svc, "_CONFIG_PATH", fixture_path):
        config = svc.load_config()

    assert config["enabled"] is True

    screening = config["screening"]
    assert "conditions" in screening
    assert screening["order_by"] == "market_cap"
    assert screening["order_direction"] == "desc"
    assert screening["limit"] == 5

    analysis = config["analysis"]
    assert analysis["research_depth"] == "标准"
    assert analysis["market_type"] == "A股"


# ---------------------------------------------------------------------------
# Error-path / safe-default tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_config_missing_file_returns_safe_default(tmp_path, caplog):
    """When the config file does not exist, load_config() returns a safe
    default dict with enabled=False and logs a warning."""
    missing_path = tmp_path / "nonexistent.json"
    with caplog.at_level(logging.WARNING), patch.object(svc, "_CONFIG_PATH", missing_path):
        config = svc.load_config()
    assert isinstance(config, dict)
    assert config["enabled"] is False
    assert "screening" in config
    assert "analysis" in config
    assert caplog.records, "expected a warning log record but none was emitted"
    assert any(r.levelno == logging.WARNING for r in caplog.records)


@pytest.mark.unit
def test_load_config_malformed_file_returns_safe_default(tmp_path, caplog):
    """When the config file contains invalid JSON, load_config() returns the
    safe default instead of raising, and logs a warning."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ not valid json }")
    with caplog.at_level(logging.WARNING), patch.object(svc, "_CONFIG_PATH", bad_file):
        config = svc.load_config()
    assert config["enabled"] is False
    assert "screening" in config
    assert "analysis" in config
    assert caplog.records, "expected a warning log record but none was emitted"
    assert any(r.levelno == logging.WARNING for r in caplog.records)


# ---------------------------------------------------------------------------
# run_daily_recommendation() orchestration tests
#
# These exercise the screening -> per-stock analysis -> persistence flow with
# the two collaborating services and the mongo handle fully mocked, so no
# network or DB is touched. The assertions verify orchestration *behaviour*:
# status transitions, the number of analyses triggered, and the persisted
# document shape.
# ---------------------------------------------------------------------------


def _enabled_cfg(limit: int = 5) -> dict:
    """A minimal enabled config matching config/daily_recommendation.json."""
    return {
        "enabled": True,
        "screening": {
            "conditions": [],
            "order_by": "market_cap",
            "order_direction": "desc",
            "limit": limit,
        },
        "analysis": {
            "research_depth": "标准",
            "market_type": "A股",
        },
    }


class _FakeCollection:
    """A minimal async mongo collection capturing inserted / updated docs."""

    def __init__(self):
        self.created_indexes: list = []
        self.inserted: list[dict] = []
        self.updates: list[tuple] = []
        self._inserted_id = "fake_object_id"

    async def create_index(self, keys, **kwargs):
        self.created_indexes.append((keys, kwargs))

    async def insert_one(self, doc):
        self.inserted.append(doc)
        return MagicMock(inserted_id=self._inserted_id)

    async def update_one(self, flt, update, **kwargs):
        self.updates.append((flt, update))
        return MagicMock(matched_count=1, modified_count=1)


class _FakeDB:
    """A fake mongo db exposing the daily_recommendations collection."""

    def __init__(self):
        self.collection = _FakeCollection()

    def __getitem__(self, name):
        assert name == "daily_recommendations"
        return self.collection


def _make_analysis_service(results_by_symbol: dict, fail_symbols=None):
    """Build a fake simple-analysis service mirroring the real contract.

    *results_by_symbol* maps a symbol to the result dict returned by
    get_task_status; *fail_symbols* is a set of symbols whose analysis fails.

    The real ``execute_analysis_background`` swallows analysis errors (it marks
    the task ``failed`` in state and returns normally — it does NOT re-raise),
    so the fake ``_execute`` here never raises either. Failure is instead
    surfaced through ``get_task_status``: for a failed symbol ``_status``
    returns a FAILED-shaped dict (``status="failed"`` + ``error_message``),
    matching ``TaskState.to_dict()``.
    """
    fail_symbols = fail_symbols or set()
    service = MagicMock()
    counter = {"n": 0}

    async def _create(user_id, request):
        counter["n"] += 1
        return {"task_id": f"task-{counter['n']}", "status": "pending"}

    async def _execute(task_id, user_id, request):
        # Real execute_analysis_background never re-raises on analysis failure;
        # it marks the task failed and returns. The fake mirrors that.
        return None

    async def _status(task_id):
        # task ids are task-1, task-2, ... in screening order
        idx = int(task_id.split("-")[1]) - 1
        symbols = list(results_by_symbol.keys())
        symbol = symbols[idx]
        if symbol in fail_symbols:
            return {
                "status": "failed",
                "error_message": f"analysis blew up for {symbol}",
                "result_data": None,
            }
        return {"status": "completed", "result_data": results_by_symbol[symbol]}

    service.create_analysis_task = AsyncMock(side_effect=_create)
    service.execute_analysis_background = AsyncMock(side_effect=_execute)
    service.get_task_status = AsyncMock(side_effect=_status)
    return service


@pytest.mark.unit
def test_run_daily_recommendation_disabled_returns_without_writing(caplog):
    """When enabled=False, run_daily_recommendation() returns early and never
    touches the screening service or mongo."""
    fake_db = _FakeDB()
    with (
        patch.object(svc, "load_config", return_value={"enabled": False}),
        patch.object(svc, "get_mongo_db", return_value=fake_db) as mock_db,
        patch.object(svc, "get_enhanced_screening_service") as mock_screen,
        patch.object(svc, "get_simple_analysis_service") as mock_analysis,
        caplog.at_level(logging.INFO),
    ):
        result = asyncio.run(svc.run_daily_recommendation())

    assert result is None
    mock_db.assert_not_called()
    mock_screen.assert_not_called()
    mock_analysis.assert_not_called()
    assert fake_db.collection.inserted == []


@pytest.mark.unit
def test_run_daily_recommendation_happy_path():
    """Screening returns 3 stocks -> 3 analyses run -> one completed doc
    persisted with each stock filled in and overall status=completed."""
    fake_db = _FakeDB()
    items = [
        {"code": "600000", "name": "浦发银行"},
        {"code": "000001", "name": "平安银行"},
        {"code": "600519", "name": "贵州茅台"},
    ]
    screen = MagicMock()
    screen.screen_stocks = AsyncMock(return_value={"total": 3, "items": items})

    results = {
        "600000": {"recommendation": "买入", "summary": "稳健", "risk_level": "低"},
        "000001": {"recommendation": "持有", "summary": "中性", "risk_level": "中等"},
        "600519": {"recommendation": "买入", "summary": "强势", "risk_level": "中等"},
    }
    analysis = _make_analysis_service(results)

    with (
        patch.object(svc, "load_config", return_value=_enabled_cfg()),
        patch.object(svc, "get_mongo_db", return_value=fake_db),
        patch.object(svc, "get_enhanced_screening_service", return_value=screen),
        patch.object(svc, "get_simple_analysis_service", return_value=analysis),
    ):
        asyncio.run(svc.run_daily_recommendation())

    # one doc inserted
    assert len(fake_db.collection.inserted) == 1
    doc = fake_db.collection.inserted[0]
    assert doc["config_snapshot"] == _enabled_cfg()
    assert "date" in doc
    # unique index on date ensured before write
    assert fake_db.collection.created_indexes, "expected a unique index on date"

    # 3 analyses triggered (one create + one execute per stock)
    assert analysis.create_analysis_task.await_count == 3
    assert analysis.execute_analysis_background.await_count == 3

    # final doc updated to completed with filled stocks
    assert fake_db.collection.updates, "expected a final status update"
    _flt, final_update = fake_db.collection.updates[-1]
    final_doc = final_update["$set"]
    assert final_doc["status"] == "completed"
    stocks = final_doc["stocks"]
    assert len(stocks) == 3
    by_symbol = {s["symbol"]: s for s in stocks}
    assert by_symbol["600000"]["name"] == "浦发银行"
    assert by_symbol["600000"]["recommendation"] == "买入"
    assert by_symbol["600000"]["summary"] == "稳健"
    assert by_symbol["600000"]["risk_level"] == "低"
    assert by_symbol["600000"]["task_id"] == "task-1"
    assert all(s["status"] == "completed" for s in stocks)


@pytest.mark.unit
def test_run_daily_recommendation_caps_at_limit():
    """Screening with limit=5: even if more items come back, only the first 5
    stocks are analysed."""
    fake_db = _FakeDB()
    items = [{"code": f"60000{i}", "name": f"股票{i}"} for i in range(8)]
    screen = MagicMock()
    screen.screen_stocks = AsyncMock(return_value={"total": 8, "items": items})

    results = {f"60000{i}": {"recommendation": "持有", "summary": "x", "risk_level": "中等"} for i in range(5)}
    analysis = _make_analysis_service(results)

    with (
        patch.object(svc, "load_config", return_value=_enabled_cfg(limit=5)),
        patch.object(svc, "get_mongo_db", return_value=fake_db),
        patch.object(svc, "get_enhanced_screening_service", return_value=screen),
        patch.object(svc, "get_simple_analysis_service", return_value=analysis),
    ):
        asyncio.run(svc.run_daily_recommendation())

    assert analysis.create_analysis_task.await_count == 5
    _flt, final_update = fake_db.collection.updates[-1]
    assert len(final_update["$set"]["stocks"]) == 5


@pytest.mark.unit
def test_run_daily_recommendation_empty_screening():
    """Screening returns 0 stocks -> a doc with empty stocks is written and the
    overall status is completed (not an error)."""
    fake_db = _FakeDB()
    screen = MagicMock()
    screen.screen_stocks = AsyncMock(return_value={"total": 0, "items": []})
    analysis = _make_analysis_service({})

    with (
        patch.object(svc, "load_config", return_value=_enabled_cfg()),
        patch.object(svc, "get_mongo_db", return_value=fake_db),
        patch.object(svc, "get_enhanced_screening_service", return_value=screen),
        patch.object(svc, "get_simple_analysis_service", return_value=analysis),
    ):
        asyncio.run(svc.run_daily_recommendation())

    assert len(fake_db.collection.inserted) == 1
    analysis.create_analysis_task.assert_not_awaited()
    _flt, final_update = fake_db.collection.updates[-1]
    final_doc = final_update["$set"]
    assert final_doc["stocks"] == []
    assert final_doc["status"] == "completed"


@pytest.mark.unit
def test_run_daily_recommendation_partial_failure():
    """When one stock's analysis raises, that stock is marked failed, the
    others stay completed, and the overall status is partial."""
    fake_db = _FakeDB()
    items = [
        {"code": "600000", "name": "浦发银行"},
        {"code": "000001", "name": "平安银行"},
        {"code": "600519", "name": "贵州茅台"},
    ]
    screen = MagicMock()
    screen.screen_stocks = AsyncMock(return_value={"total": 3, "items": items})

    results = {
        "600000": {"recommendation": "买入", "summary": "稳健", "risk_level": "低"},
        "000001": {"recommendation": "持有", "summary": "中性", "risk_level": "中等"},
        "600519": {"recommendation": "买入", "summary": "强势", "risk_level": "中等"},
    }
    analysis = _make_analysis_service(results, fail_symbols={"000001"})

    with (
        patch.object(svc, "load_config", return_value=_enabled_cfg()),
        patch.object(svc, "get_mongo_db", return_value=fake_db),
        patch.object(svc, "get_enhanced_screening_service", return_value=screen),
        patch.object(svc, "get_simple_analysis_service", return_value=analysis),
    ):
        asyncio.run(svc.run_daily_recommendation())

    # all 3 still attempted despite the middle one failing
    assert analysis.create_analysis_task.await_count == 3
    _flt, final_update = fake_db.collection.updates[-1]
    final_doc = final_update["$set"]
    assert final_doc["status"] == "partial"
    by_symbol = {s["symbol"]: s for s in final_doc["stocks"]}
    assert by_symbol["000001"]["status"] == "failed"
    assert by_symbol["600000"]["status"] == "completed"
    assert by_symbol["600519"]["status"] == "completed"


@pytest.mark.unit
def test_run_daily_recommendation_all_failed():
    """When every stock's analysis raises, the overall status is failed."""
    fake_db = _FakeDB()
    items = [
        {"code": "600000", "name": "浦发银行"},
        {"code": "000001", "name": "平安银行"},
    ]
    screen = MagicMock()
    screen.screen_stocks = AsyncMock(return_value={"total": 2, "items": items})
    analysis = _make_analysis_service({"600000": {}, "000001": {}}, fail_symbols={"600000", "000001"})

    with (
        patch.object(svc, "load_config", return_value=_enabled_cfg()),
        patch.object(svc, "get_mongo_db", return_value=fake_db),
        patch.object(svc, "get_enhanced_screening_service", return_value=screen),
        patch.object(svc, "get_simple_analysis_service", return_value=analysis),
    ):
        asyncio.run(svc.run_daily_recommendation())

    _flt, final_update = fake_db.collection.updates[-1]
    final_doc = final_update["$set"]
    assert final_doc["status"] == "failed"
    assert all(s["status"] == "failed" for s in final_doc["stocks"])


@pytest.mark.unit
def test_run_daily_recommendation_translates_order_by():
    """The plain-string config order_by/order_direction is translated into the
    List[Dict[str,str]] shape the screening service expects."""
    fake_db = _FakeDB()
    screen = MagicMock()
    screen.screen_stocks = AsyncMock(return_value={"total": 0, "items": []})
    analysis = _make_analysis_service({})

    with (
        patch.object(svc, "load_config", return_value=_enabled_cfg()),
        patch.object(svc, "get_mongo_db", return_value=fake_db),
        patch.object(svc, "get_enhanced_screening_service", return_value=screen),
        patch.object(svc, "get_simple_analysis_service", return_value=analysis),
    ):
        asyncio.run(svc.run_daily_recommendation())

    _args, kwargs = screen.screen_stocks.await_args
    assert kwargs["order_by"] == [{"field": "market_cap", "direction": "desc"}]
    assert kwargs["limit"] == 5
