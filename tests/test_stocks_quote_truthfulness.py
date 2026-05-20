"""data-truthfulness contract test for /api/stocks/{code}/quote.

capability data-quality-gate Requirement 3 + change 2026-05-20-data-truthfulness：
任何 quote / 价格 / 盘口类后端 endpoint MUST 返回 `is_stale: bool` + `as_of_date: str`
字段；前端 MUST 在 is_stale=true 时降级显示，不允许把昨日涨停板当今日大字色块。

本 contract 覆盖 is_stale 计算的核心 4 个分支（CN tz 日历日比较）：
1. updated_at 是今日 → is_stale=False
2. updated_at 是昨日 → is_stale=True
3. 缺 updated_at 但有 close 值 → 保守判 is_stale=True（不许假装为今日）
4. 缺 close 也缺 updated_at → is_stale=None（数据完全缺失，前端独立判定）

纯单元测试，从 /quote 内部 is_stale 计算逻辑抽出来验证；不起 FastAPI app /
HTTP layer / mongo 连接，pre-commit + pre-push 都能跑。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.core.config import settings


def _compute_is_stale(updated_at_raw, close):
    """复刻 app/routers/stocks.py:get_stock_quote 的 is_stale 计算逻辑。

    保持与 endpoint 内联实现一致 —— 此处 inline 而非 import，因为 router 的
    is_stale 逻辑嵌在 handler 内部 closure（refactor 抽出来后这个 helper 可
    替换为 `from app.routers.stocks import _compute_is_stale`）。
    """
    is_stale = None
    as_of_date = None
    if isinstance(updated_at_raw, datetime):
        tz = ZoneInfo(settings.TIMEZONE)
        upd = updated_at_raw if updated_at_raw.tzinfo else updated_at_raw.replace(tzinfo=ZoneInfo("UTC"))
        upd_cn = upd.astimezone(tz)
        as_of_date = upd_cn.strftime("%Y-%m-%d")
        today_cn = datetime.now(tz).strftime("%Y-%m-%d")
        is_stale = as_of_date != today_cn
    elif close is not None:
        # 保守判 stale：有价格但缺时间戳，不能假装为今日
        is_stale = True
    return is_stale, as_of_date


@pytest.mark.unit
def test_quote_today_updated_is_fresh() -> None:
    """updated_at 是今日（CN tz）时 is_stale=False。"""
    tz = ZoneInfo(settings.TIMEZONE)
    today_noon_cn = datetime.now(tz).replace(hour=12, minute=0, second=0, microsecond=0)
    is_stale, as_of_date = _compute_is_stale(today_noon_cn.astimezone(timezone.utc), close=10.0)
    assert is_stale is False
    assert as_of_date == today_noon_cn.strftime("%Y-%m-%d")


@pytest.mark.unit
def test_quote_yesterday_updated_is_stale() -> None:
    """updated_at 是昨日（CN tz）时 is_stale=True —— 002281 昨日涨停板问题。"""
    tz = ZoneInfo(settings.TIMEZONE)
    yesterday_cn = (datetime.now(tz) - timedelta(days=1)).replace(hour=15, minute=42)
    is_stale, as_of_date = _compute_is_stale(yesterday_cn.astimezone(timezone.utc), close=230.89)
    assert is_stale is True
    assert as_of_date == yesterday_cn.strftime("%Y-%m-%d")


@pytest.mark.unit
def test_quote_missing_updated_at_with_close_conservative_stale() -> None:
    """缺 updated_at 但有 close 时 MUST 保守判 is_stale=True，不许假装今日。"""
    is_stale, as_of_date = _compute_is_stale(None, close=100.0)
    assert is_stale is True
    assert as_of_date is None


@pytest.mark.unit
def test_quote_missing_both_returns_none() -> None:
    """完全缺数据时 is_stale=None（前端按"无数据"独立处理）。"""
    is_stale, as_of_date = _compute_is_stale(None, close=None)
    assert is_stale is None
    assert as_of_date is None


@pytest.mark.unit
def test_quote_naive_utc_datetime_handled() -> None:
    """mongo 返回的 datetime 可能是 naive UTC（tzinfo=None）—— 仍需正确归到 CN tz."""
    # 模拟 mongo 返回的 naive UTC datetime
    tz = ZoneInfo(settings.TIMEZONE)
    today_cn_str = datetime.now(tz).strftime("%Y-%m-%d")
    # 当前 CN 时刻对应的 naive UTC
    now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    is_stale, as_of_date = _compute_is_stale(now_utc_naive, close=100.0)
    assert is_stale is False
    assert as_of_date == today_cn_str
