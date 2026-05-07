"""
Tests for TradingCalendarService — 覆盖：
- sync_year 写 mongo 行为
- is_trading_day mongo 命中 / 未命中
- 内存缓存命中
- 节假日识别（mongo 没该日期 → 非交易日）
- mongo 失败 fallback 到 weekday
- get_today_status 综合返回
"""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest

from app.services.trading_calendar_service import TradingCalendarService


class _FakeCollection:
    def __init__(self, docs: list[dict[str, Any]] | None = None):
        self.docs = docs or []
        self.upsert_calls: list[dict[str, Any]] = []

    async def find_one(self, query):
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                return d
        return None

    async def update_one(self, query, update, upsert=False):
        _ = upsert  # 兼容 motor 签名，本 fake 不区分 upsert flag
        for i, d in enumerate(self.docs):
            if all(d.get(k) == v for k, v in query.items()):
                # 已存在 → modify
                self.docs[i] = {**d, **update.get("$set", {})}
                self.upsert_calls.append({"query": query, "update": update, "upserted": False})

                class _Result:
                    upserted_id = None
                    modified_count = 1

                return _Result()
        # 不存在 → insert
        self.docs.append(update.get("$set", {}))
        self.upsert_calls.append({"query": query, "update": update, "upserted": True})

        class _Result:
            upserted_id = "fake_id"
            modified_count = 0

        return _Result()

    async def count_documents(self, query):
        if not query:
            return len(self.docs)
        return sum(1 for d in self.docs if all(d.get(k) == v for k, v in query.items()))

    async def create_index(self, *args, **kwargs):
        return None


class _FakeDB:
    def __init__(self, collections: dict[str, _FakeCollection]):
        self._collections = collections

    def __getitem__(self, name: str) -> _FakeCollection:
        return self._collections[name]


def _build_db(calendar_docs: list[dict[str, Any]] | None = None) -> _FakeDB:
    return _FakeDB({"trading_calendar": _FakeCollection(calendar_docs or [])})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_trading_day_mongo_hit():
    db = _build_db(
        calendar_docs=[
            {"date": "2026-05-08", "year": 2026},
            {"date": "2026-05-11", "year": 2026},
        ]
    )
    svc = TradingCalendarService(db=db)  # type: ignore[arg-type]

    assert await svc.is_trading_day(date(2026, 5, 8)) is True
    assert await svc.is_trading_day(date(2026, 5, 11)) is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_trading_day_holiday_returns_false():
    """节假日：mongo 该年有数据但具体日期无文档 → False."""
    db = _build_db(
        calendar_docs=[
            {"date": "2026-05-08", "year": 2026},
            # 2026-05-09 / 2026-05-10 周末 + 2026-05-12 假设是节假日：均不存在
        ]
    )
    svc = TradingCalendarService(db=db)  # type: ignore[arg-type]

    assert await svc.is_trading_day(date(2026, 5, 9)) is False  # 周六
    assert await svc.is_trading_day(date(2026, 5, 10)) is False  # 周日
    assert await svc.is_trading_day(date(2026, 5, 12)) is False  # 假节


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_trading_day_falls_back_when_year_data_missing():
    """启动初期：mongo 该年无任何数据 → 不 cache False；下次查再次 query mongo."""
    db = _build_db(calendar_docs=[])
    svc = TradingCalendarService(db=db)  # type: ignore[arg-type]

    # 第一次查（mongo 空）
    result = await svc.is_trading_day(date(2026, 5, 8))
    assert result is False  # mongo 空，find_one 返回 None
    # 应该未缓存（_cache 为空）
    assert "2026-05-08" not in svc._cache


@pytest.mark.unit
@pytest.mark.asyncio
async def test_is_trading_day_caches_after_year_synced():
    """mongo 已 sync 该年数据后，is_trading_day 缓存结果."""
    db = _build_db(
        calendar_docs=[
            {"date": "2026-05-08", "year": 2026},
        ]
    )
    svc = TradingCalendarService(db=db)  # type: ignore[arg-type]

    await svc.is_trading_day(date(2026, 5, 8))
    assert svc._cache.get("2026-05-08") is True

    # 周末（mongo 有该年数据但具体日期无）
    await svc.is_trading_day(date(2026, 5, 9))
    assert svc._cache.get("2026-05-09") is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_year_filters_by_year_and_upserts():
    db = _build_db(calendar_docs=[])
    svc = TradingCalendarService(db=db)  # type: ignore[arg-type]

    # mock akshare 返回（含其他年份混合）
    fake_df = pd.DataFrame(
        {
            "trade_date": [
                "2025-12-30",
                "2025-12-31",
                "2026-01-02",
                "2026-01-05",
                "2027-01-04",
            ]
        }
    )
    with patch.object(TradingCalendarService, "_fetch_calendar", return_value=fake_df):
        result = await svc.sync_year(2026)

    assert result["year"] == 2026
    assert result["total"] == 2  # 仅 2026 的 2 个日期
    assert result["inserted"] == 2

    # mongo 含 2026 两个日期
    assert await db["trading_calendar"].count_documents({"year": 2026}) == 2  # type: ignore[index]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_year_akshare_failure_returns_zero():
    db = _build_db(calendar_docs=[])
    svc = TradingCalendarService(db=db)  # type: ignore[arg-type]

    def _raise():
        raise RuntimeError("akshare 网络挂了")

    with patch.object(TradingCalendarService, "_fetch_calendar", side_effect=_raise):
        result = await svc.sync_year(2026)

    assert result == {"year": 2026, "total": 0, "inserted": 0, "updated": 0}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_today_status_returns_full_dict():
    from datetime import datetime as real_datetime

    db = _build_db(
        calendar_docs=[
            {"date": "2026-05-08", "year": 2026},  # 假设 today
            {"date": "2026-05-11", "year": 2026},  # 下一个交易日（5/9-10 周末）
        ]
    )
    svc = TradingCalendarService(db=db)  # type: ignore[arg-type]

    # mock datetime.now 返回 2026-05-08 08:00（盘外时段，让 is_intraday=False）
    fake_now = real_datetime(2026, 5, 8, 8, 0, tzinfo=svc._tz)

    with patch("app.services.trading_calendar_service.datetime") as mock_datetime:
        mock_datetime.now.return_value = fake_now
        # 让其他 datetime 方法保持原行为
        mock_datetime.side_effect = lambda *args, **kwargs: real_datetime(*args, **kwargs)

        status = await svc.get_today_status()

    assert status["date"] == "2026-05-08"
    assert status["is_trading_day"] is True
    assert status["is_intraday"] is False  # 8:00 不在盘中
    assert status["next_trading_day"] == "2026-05-11"
