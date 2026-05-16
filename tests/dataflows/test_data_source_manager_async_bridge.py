"""data_source_manager 同步/异步桥接回归测试。

对应 OpenSpec change: fix-datasource-async-bridge

复现并守护 bug：三个数据源方法 _get_{tushare,akshare,baostock}_data 内部用
loop.run_until_complete() 桥接 async provider。当调用方位于一个「正在运行的
event loop」（FastAPI async 路径）时，run_until_complete 抛
RuntimeError: this event loop is already running，导致所有数据源失败。

测试策略：用 @pytest.mark.asyncio 把测试体放进一个 running event loop，
在其中同步调用数据源方法 —— 修复前抛 event loop 错误（红），修复后正常返回（绿）。
"""

from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from tradingagents.dataflows.data_source_manager import ChinaDataSource, DataSourceManager


def _make_manager() -> DataSourceManager:
    """构造一个绕过 __init__ 副作用的裸 DataSourceManager，用于方法级测试。"""
    mgr = DataSourceManager.__new__(DataSourceManager)
    mgr.current_source = ChinaDataSource.TUSHARE
    return mgr


def _fake_provider() -> MagicMock:
    """provider 的 async 方法用 AsyncMock，使其可被 await / run_until_complete。"""
    provider = MagicMock()
    provider.get_historical_data = AsyncMock(return_value=pd.DataFrame({"close": [10.0, 11.0]}))
    provider.get_stock_basic_info = AsyncMock(return_value={"name": "北特科技"})
    return provider


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tushare_data_in_running_loop(monkeypatch):
    """running event loop 里调 _get_tushare_data 不应抛 'this event loop is already running'。"""
    mgr = _make_manager()
    provider = _fake_provider()
    monkeypatch.setattr(mgr, "_get_cached_data", MagicMock(return_value=None))
    monkeypatch.setattr(mgr, "_get_tushare_adapter", lambda: provider)
    monkeypatch.setattr(mgr, "_save_to_cache", MagicMock(return_value=None))
    monkeypatch.setattr(mgr, "_format_stock_data_response", MagicMock(return_value="OK-TUSHARE"))

    result = mgr._get_tushare_data("603009", "20250101", "20250201")
    assert result == "OK-TUSHARE"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_akshare_data_in_running_loop(monkeypatch):
    """running event loop 里调 _get_akshare_data 不应降级为 event loop 错误字符串。"""
    mgr = _make_manager()
    provider = _fake_provider()
    monkeypatch.setattr(
        "tradingagents.dataflows.providers.china.akshare.get_akshare_provider",
        lambda: provider,
    )
    monkeypatch.setattr(mgr, "_format_stock_data_response", MagicMock(return_value="OK-AKSHARE"))

    result = mgr._get_akshare_data("603009", "20250101", "20250201")
    assert "event loop" not in result
    assert result == "OK-AKSHARE"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_baostock_data_in_running_loop(monkeypatch):
    """running event loop 里调 _get_baostock_data 不应抛 'this event loop is already running'。"""
    mgr = _make_manager()
    provider = _fake_provider()
    monkeypatch.setattr(
        "tradingagents.dataflows.providers.china.baostock.get_baostock_provider",
        lambda: provider,
    )
    monkeypatch.setattr(mgr, "_format_stock_data_response", MagicMock(return_value="OK-BAOSTOCK"))

    result = mgr._get_baostock_data("603009", "20250101", "20250201")
    assert result == "OK-BAOSTOCK"


@pytest.mark.unit
def test_tushare_data_in_sync_context(monkeypatch):
    """同步上下文（无 running loop）回归：修复前后都应正常工作。"""
    mgr = _make_manager()
    provider = _fake_provider()
    monkeypatch.setattr(mgr, "_get_cached_data", MagicMock(return_value=None))
    monkeypatch.setattr(mgr, "_get_tushare_adapter", lambda: provider)
    monkeypatch.setattr(mgr, "_save_to_cache", MagicMock(return_value=None))
    monkeypatch.setattr(mgr, "_format_stock_data_response", MagicMock(return_value="OK-SYNC"))

    result = mgr._get_tushare_data("603009", "20250101", "20250201")
    assert result == "OK-SYNC"
