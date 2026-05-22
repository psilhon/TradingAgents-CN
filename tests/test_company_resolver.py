"""company_resolver 单元测试 — OpenSpec change extract-company-resolver。

company_resolver 内对 dataflows 的依赖是函数内惰性 import；真实
tradingagents.dataflows 包 import 即连 MongoDB。本测试通过 sys.modules
注入 fake dataflows 模块，使惰性 import 解析到 mock，保持纯 unit（无外部依赖）。
"""

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tradingagents.agents.utils.company_resolver import get_company_name

pytestmark = pytest.mark.unit


@pytest.fixture
def df(monkeypatch):
    """注入 fake dataflows 模块树，拦截 company_resolver 的惰性 import。"""
    interface = types.ModuleType("tradingagents.dataflows.interface")
    interface.get_china_stock_info_unified = MagicMock()
    dsm = types.ModuleType("tradingagents.dataflows.data_source_manager")
    dsm.get_china_stock_info_unified = MagicMock()
    hk = types.ModuleType("tradingagents.dataflows.providers.hk.improved_hk")
    hk.get_hk_company_name_improved = MagicMock()

    fakes = {
        "tradingagents.dataflows": types.ModuleType("tradingagents.dataflows"),
        "tradingagents.dataflows.providers": types.ModuleType("tradingagents.dataflows.providers"),
        "tradingagents.dataflows.providers.hk": types.ModuleType("tradingagents.dataflows.providers.hk"),
        "tradingagents.dataflows.interface": interface,
        "tradingagents.dataflows.data_source_manager": dsm,
        "tradingagents.dataflows.providers.hk.improved_hk": hk,
    }
    for name, mod in fakes.items():
        monkeypatch.setitem(sys.modules, name, mod)
    return SimpleNamespace(interface=interface, dsm=dsm, hk=hk)


# --- 美股：纯逻辑分支，无外部调用，无需 fixture ---


def test_us_dict_hit():
    assert get_company_name("AAPL", {"is_china": False, "is_hk": False, "is_us": True}) == "苹果公司"


def test_us_dict_hit_lowercase():
    assert get_company_name("aapl", {"is_china": False, "is_hk": False, "is_us": True}) == "苹果公司"


def test_us_dict_miss():
    assert get_company_name("ZZZZ", {"is_china": False, "is_hk": False, "is_us": True}) == "美股ZZZZ"


def test_unknown_market_returns_default():
    assert get_company_name("XYZ", {"is_china": False, "is_hk": False, "is_us": False}) == "股票代码XYZ"


# --- A 股 ---


def test_china_unified_interface_hit(df):
    df.interface.get_china_stock_info_unified.return_value = "股票名称: 平安银行\n其它字段: x"
    assert get_company_name("000001", {"is_china": True}) == "平安银行"


def test_china_none_does_not_raise(df):
    """回归 news_analyst latent bug：stock_info 为 None 时不得抛 TypeError。"""
    df.interface.get_china_stock_info_unified.return_value = None
    df.dsm.get_china_stock_info_unified.return_value = None
    assert get_company_name("000001", {"is_china": True}) == "股票代码000001"


def test_china_fallback_to_data_source_manager(df):
    """一级接口 miss → 二级 data_source_manager 降级命中。"""
    df.interface.get_china_stock_info_unified.return_value = "没有名称字段"
    df.dsm.get_china_stock_info_unified.return_value = {"name": "万科A"}
    assert get_company_name("000002", {"is_china": True}) == "万科A"


def test_china_all_fail_returns_default(df):
    df.interface.get_china_stock_info_unified.return_value = ""
    df.dsm.get_china_stock_info_unified.return_value = {}
    assert get_company_name("000003", {"is_china": True}) == "股票代码000003"


# --- 港股 ---


def test_hk_improved_tool_hit(df):
    df.hk.get_hk_company_name_improved.return_value = "腾讯控股"
    assert get_company_name("0700.HK", {"is_china": False, "is_hk": True}) == "腾讯控股"


def test_hk_improved_tool_exception(df):
    df.hk.get_hk_company_name_improved.side_effect = RuntimeError("boom")
    assert get_company_name("0700.HK", {"is_china": False, "is_hk": True}) == "港股0700"
