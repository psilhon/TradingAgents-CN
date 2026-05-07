import asyncio
import sys
from types import ModuleType

from app.models.config import DataSourceConfig, DataSourceType
from app.services.config_service import ConfigService


class _FakeDataFrame:
    def __len__(self):
        return 1


class _FakeTusharePro:
    def __init__(self):
        self.trade_cal_called = False
        self.stock_basic_called = False

    def trade_cal(self, **kwargs):
        self.trade_cal_called = True
        raise AssertionError("trade_cal should not be used for connection tests")

    def stock_basic(self, **kwargs):
        self.stock_basic_called = True
        return _FakeDataFrame()


def test_tushare_connection_test_uses_stock_basic(monkeypatch):
    fake_pro = _FakeTusharePro()
    fake_tushare = ModuleType("tushare")
    fake_tushare.set_token = lambda token: None
    fake_tushare.pro_api = lambda: fake_pro
    monkeypatch.setitem(sys.modules, "tushare", fake_tushare)

    service = ConfigService()
    ds_config = DataSourceConfig(
        name="Tushare",
        type=DataSourceType.TUSHARE,
        api_key="test-token",
    )

    result = asyncio.run(service.test_data_source_config(ds_config))

    assert result["success"] is True
    assert fake_pro.stock_basic_called is True
    assert fake_pro.trade_cal_called is False
    assert result["details"]["test_result"] == "获取股票基础信息成功"
