"""财务数据写库校验闸门单元测试。

针对 FinancialDataService._has_meaningful_financials —— 确保数据源接口
失败时产生的 all-null 财务文档会在写库前被拦截，不会污染
stock_financial_data 集合。
"""

import pytest

from app.services.financial_data_service import FinancialDataService

pytestmark = pytest.mark.unit


class TestFinancialValidationGate:
    def setup_method(self):
        # __init__ 只设置 collection_name / db=None，无任何 I/O
        self.svc = FinancialDataService()

    def test_real_financials_pass(self):
        """含真实财务数值的文档应通过校验。"""
        doc = {
            "symbol": "600519",
            "report_period": "20260331",
            "revenue": 53909252220.51,
            "net_income": 28153831489.89,
            "total_assets": 319918844905.58,
            "roe": 10.5687,
        }
        assert self.svc._has_meaningful_financials(doc) is True

    def test_all_null_doc_rejected(self):
        """关键字段全为 None 的文档应被拒（接口失败时的典型产物）。"""
        doc = {
            "symbol": "600519",
            "report_period": "20260630",
            "data_source": "tushare",
            "revenue": None,
            "net_income": None,
            "net_profit": None,
            "total_assets": None,
            "total_equity": None,
            "total_liab": None,
            "roe": None,
        }
        assert self.svc._has_meaningful_financials(doc) is False

    def test_doc_without_financial_keys_rejected(self):
        """只有元数据、没有任何财务字段的文档应被拒。"""
        doc = {
            "symbol": "600519",
            "report_period": "20260331",
            "data_source": "tushare",
        }
        assert self.svc._has_meaningful_financials(doc) is False

    def test_single_meaningful_field_passes(self):
        """只要有一个关键财务字段非空即放行。"""
        assert self.svc._has_meaningful_financials({"roe": 10.5}) is True
        assert self.svc._has_meaningful_financials({"net_profit": 1.0}) is True
        assert self.svc._has_meaningful_financials({"total_liab": 5489879000000.0}) is True

    def test_zero_is_meaningful(self):
        """0 是合法财务数值（如净利润为 0），不应被当成"空"。"""
        assert self.svc._has_meaningful_financials({"net_income": 0}) is True
        assert self.svc._has_meaningful_financials({"revenue": 0.0}) is True
