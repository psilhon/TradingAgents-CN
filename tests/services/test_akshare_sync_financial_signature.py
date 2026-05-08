"""akshare_sync_service.sync_financial_data 鸭子接口签名对齐测试.

Root cause: tradingagents/utils/stock_validator.py:829 调
    `service.sync_financial_data(symbols=[...], limit=20)`
其中 service 可能是 tushare 或 akshare（按数据源优先级动态选择）。
- tushare_sync_service.sync_financial_data(self, symbols=None, limit=20, job_id=None) ✓
- akshare_sync_service.sync_financial_data(self, symbols=None)               ❌ 缺 limit
→ akshare 路径必抛 TypeError: got unexpected keyword argument 'limit'
（实测 logs/error.log 反复出现）

修复：让 akshare signature 对齐 tushare（接受 limit + job_id kwargs，
即便 akshare provider 一次返回全部期数不强制裁剪——保持鸭子接口一致）。
"""

from __future__ import annotations

import inspect

import pytest


@pytest.mark.unit
def test_akshare_sync_financial_data_signature_matches_tushare() -> None:
    """akshare 与 tushare 的 sync_financial_data 签名 MUST 兼容（限定接受 kwargs 集合）."""
    from app.worker.akshare_sync_service import AKShareSyncService
    from app.worker.tushare_sync_service import TushareSyncService

    ak_sig = inspect.signature(AKShareSyncService.sync_financial_data)
    ts_sig = inspect.signature(TushareSyncService.sync_financial_data)

    # tushare 的所有 kwargs（除 self）应该都能在 akshare 上接受
    for name in ts_sig.parameters:
        if name == "self":
            continue
        assert name in ak_sig.parameters, (
            f"akshare.sync_financial_data 缺 kwarg `{name}`，鸭子接口与 tushare 不齐 → stock_validator 调用必 TypeError"
        )


@pytest.mark.unit
def test_akshare_sync_financial_data_accepts_limit_kwarg() -> None:
    """直接验证 akshare signature 接受 limit + job_id（stock_validator 调用形态）."""
    from app.worker.akshare_sync_service import AKShareSyncService

    sig = inspect.signature(AKShareSyncService.sync_financial_data)
    params = sig.parameters

    assert "limit" in params, "缺 limit kwarg（stock_validator.py:831 传该参数）"
    assert "job_id" in params, "缺 job_id kwarg（与 tushare 对齐）"

    # 应该都是有 default 的 kwarg（不强制 caller 传）
    assert params["limit"].default != inspect.Parameter.empty, "limit 应有 default"
    assert params["job_id"].default != inspect.Parameter.empty, "job_id 应有 default"
