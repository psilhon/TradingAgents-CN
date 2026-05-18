"""
Tests for daily_recommendation_service:
- list_configs() real-directory smoke test
- run_daily_recommendation(config_id) orchestration
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.daily_recommendation_service as svc

# ---------------------------------------------------------------------------
# Real-directory smoke test (proves the shipped config dir is loadable)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_list_configs_returns_list():
    """list_configs() can read config/daily_recommendations/ and returns a
    list; each config (if any) carries the four required top-level keys."""
    configs = svc.list_configs()
    assert isinstance(configs, list)
    for cfg in configs:
        assert {"id", "name", "screening", "analysis"} <= set(cfg)


# ---------------------------------------------------------------------------
# run_daily_recommendation() orchestration tests
#
# These exercise the screening -> per-stock analysis -> persistence flow with
# the two collaborating services and the mongo handle fully mocked, so no
# network or DB is touched. The assertions verify orchestration *behaviour*:
# status transitions, the number of analyses triggered, and the persisted
# document shape.
# ---------------------------------------------------------------------------


def _cfg(limit: int = 5) -> dict:
    """A minimal config matching config/daily_recommendations/<id>.json."""
    return {
        "id": "abc12345",
        "name": "测试配置",
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
        self.dropped_indexes: list = []
        self.inserted: list[dict] = []
        self.updates: list[tuple] = []
        self.update_many_calls: list[tuple] = []
        self.indexes: list[dict] = []
        self._inserted_id = "fake_object_id"

    async def create_index(self, keys, **kwargs):
        self.created_indexes.append((keys, kwargs))

    async def drop_index(self, name):
        self.dropped_indexes.append(name)

    def list_indexes(self):
        return self._aiter_indexes()

    async def _aiter_indexes(self):
        for idx in self.indexes:
            yield idx

    async def update_many(self, flt, update, **kwargs):
        self.update_many_calls.append((flt, update))
        return MagicMock(matched_count=0, modified_count=0)

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
    service.captured_requests = []
    counter = {"n": 0}

    async def _create(user_id, request):
        counter["n"] += 1
        service.captured_requests.append(request)
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
def test_run_daily_recommendation_happy_path():
    """Screening returns 3 stocks -> 3 analyses run -> one completed doc
    persisted, tagged with config_id/config_name and overall status=completed."""
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
        patch.object(svc, "load_config", return_value=_cfg()),
        patch.object(svc, "get_mongo_db", return_value=fake_db),
        patch.object(svc, "get_enhanced_screening_service", return_value=screen),
        patch.object(svc, "get_simple_analysis_service", return_value=analysis),
    ):
        asyncio.run(svc.run_daily_recommendation("abc12345"))

    # one doc inserted, tagged with the config identity
    assert len(fake_db.collection.inserted) == 1
    doc = fake_db.collection.inserted[0]
    assert doc["config_snapshot"] == _cfg()
    assert doc["config_id"] == "abc12345"
    assert doc["config_name"] == "测试配置"
    assert "date" in doc
    # compound (date, config_id) unique index ensured before write
    assert fake_db.collection.created_indexes, "expected a compound unique index"

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
def test_run_daily_recommendation_request_carries_stock_code():
    """The SingleAnalysisRequest handed to the analysis service must carry the
    code in the `stock_code` field — simple_analysis_service feeds the analysis
    graph `request.stock_code` directly, so a request with only `symbol` set
    leaves the graph analysing a None ticker."""
    fake_db = _FakeDB()
    items = [{"code": "603392", "name": "万泰生物"}]
    screen = MagicMock()
    screen.screen_stocks = AsyncMock(return_value={"total": 1, "items": items})
    analysis = _make_analysis_service({"603392": {"recommendation": "买入", "summary": "x", "risk_level": "低"}})

    with (
        patch.object(svc, "load_config", return_value=_cfg()),
        patch.object(svc, "get_mongo_db", return_value=fake_db),
        patch.object(svc, "get_enhanced_screening_service", return_value=screen),
        patch.object(svc, "get_simple_analysis_service", return_value=analysis),
    ):
        asyncio.run(svc.run_daily_recommendation("abc12345"))

    assert analysis.captured_requests, "expected an analysis request to be captured"
    req = analysis.captured_requests[0]
    assert req.stock_code == "603392"
    assert req.get_symbol() == "603392"


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
        patch.object(svc, "load_config", return_value=_cfg(limit=5)),
        patch.object(svc, "get_mongo_db", return_value=fake_db),
        patch.object(svc, "get_enhanced_screening_service", return_value=screen),
        patch.object(svc, "get_simple_analysis_service", return_value=analysis),
    ):
        asyncio.run(svc.run_daily_recommendation("abc12345"))

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
        patch.object(svc, "load_config", return_value=_cfg()),
        patch.object(svc, "get_mongo_db", return_value=fake_db),
        patch.object(svc, "get_enhanced_screening_service", return_value=screen),
        patch.object(svc, "get_simple_analysis_service", return_value=analysis),
    ):
        asyncio.run(svc.run_daily_recommendation("abc12345"))

    assert len(fake_db.collection.inserted) == 1
    analysis.create_analysis_task.assert_not_awaited()
    _flt, final_update = fake_db.collection.updates[-1]
    final_doc = final_update["$set"]
    assert final_doc["stocks"] == []
    assert final_doc["status"] == "completed"


@pytest.mark.unit
def test_run_daily_recommendation_screening_error_marks_failed():
    """When screening errors (e.g. DB timeout -> source='error'), the run is
    persisted as failed — not silently recorded as a completed/0-stock run."""
    fake_db = _FakeDB()
    screen = MagicMock()
    screen.screen_stocks = AsyncMock(
        return_value={
            "total": 0,
            "items": [],
            "source": "error",
            "error": "db timeout",
        }
    )
    analysis = _make_analysis_service({})

    with (
        patch.object(svc, "load_config", return_value=_cfg()),
        patch.object(svc, "get_mongo_db", return_value=fake_db),
        patch.object(svc, "get_enhanced_screening_service", return_value=screen),
        patch.object(svc, "get_simple_analysis_service", return_value=analysis),
    ):
        asyncio.run(svc.run_daily_recommendation("abc12345"))

    # a doc is persisted and marked failed (not silently "completed")
    assert len(fake_db.collection.inserted) == 1
    _flt, final_update = fake_db.collection.updates[-1]
    assert final_update["$set"]["status"] == "failed"
    # no analysis attempted on a failed screening
    analysis.create_analysis_task.assert_not_awaited()


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
        patch.object(svc, "load_config", return_value=_cfg()),
        patch.object(svc, "get_mongo_db", return_value=fake_db),
        patch.object(svc, "get_enhanced_screening_service", return_value=screen),
        patch.object(svc, "get_simple_analysis_service", return_value=analysis),
    ):
        asyncio.run(svc.run_daily_recommendation("abc12345"))

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
        patch.object(svc, "load_config", return_value=_cfg()),
        patch.object(svc, "get_mongo_db", return_value=fake_db),
        patch.object(svc, "get_enhanced_screening_service", return_value=screen),
        patch.object(svc, "get_simple_analysis_service", return_value=analysis),
    ):
        asyncio.run(svc.run_daily_recommendation("abc12345"))

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
        patch.object(svc, "load_config", return_value=_cfg()),
        patch.object(svc, "get_mongo_db", return_value=fake_db),
        patch.object(svc, "get_enhanced_screening_service", return_value=screen),
        patch.object(svc, "get_simple_analysis_service", return_value=analysis),
    ):
        asyncio.run(svc.run_daily_recommendation("abc12345"))

    _args, kwargs = screen.screen_stocks.await_args
    assert kwargs["order_by"] == [{"field": "market_cap", "direction": "desc"}]
    assert kwargs["limit"] == 5
