"""Contract test for portfolio_risk_service._inner_join_returns.

capability data-quality-gate Req 3 Scenario "后端 service 缺上游数据 MUST 返 None"
+ Scenario 后端不得用 "合成 / 占位 0" 填补缺失。

change 2026-05-20-paper-null-quote-handling — v1.3.1 hotfix (W2).

v1.3.0 漏修 W2：`portfolio_risk_service._get_aligned_index_returns:80` 用
`aligned.append(0.0)` 兜底缺失 HS300 日期，自称"保守"实际让 var(HS300) deflate
+ cov skew，得到的 Beta 不是真 β 是带假数据的伪指标。

新契约：用 inner-join 对齐——只用账户日期 ∩ 指数日期的交集；少于 30 天返 None。
"""

from __future__ import annotations

import pytest

from app.services.portfolio_risk_service import _inner_join_returns


@pytest.mark.unit
def test_inner_join_full_overlap():
    """账户日期 == 指数日期 → 全保留，行为与 v1.3.0 一致（regression guard）."""
    account_dates = ["2026-05-15", "2026-05-16", "2026-05-17"]
    account_returns = [0.01, 0.02, -0.005]
    idx_map = {
        "2026-05-15": 0.005,
        "2026-05-16": 0.015,
        "2026-05-17": -0.003,
    }
    a, h = _inner_join_returns(account_dates, account_returns, idx_map)
    assert a == [0.01, 0.02, -0.005]
    assert h == [0.005, 0.015, -0.003]


@pytest.mark.unit
def test_inner_join_disjoint_dates_returns_empty():
    """账户日期 ∩ 指数日期 = ∅ → 返空 list（calc_beta 处会判 < 30 返 None）."""
    account_dates = ["2026-05-15", "2026-05-16"]
    account_returns = [0.01, 0.02]
    idx_map = {"2026-04-01": 0.005, "2026-04-02": 0.015}  # 完全不重合
    a, h = _inner_join_returns(account_dates, account_returns, idx_map)
    assert a == []
    assert h == []


@pytest.mark.unit
def test_inner_join_partial_overlap():
    """部分重合 → 只保留交集日期，**且 account_returns 同步过滤**.

    这是 W2 修复核心：旧代码只过滤 index_returns（用 0.0 兜底），导致
    account 和 index 错位对齐；新代码同步保留交集索引。
    """
    account_dates = ["2026-05-15", "2026-05-16", "2026-05-17", "2026-05-18"]
    account_returns = [0.01, 0.02, -0.005, 0.008]
    # 指数缺 2026-05-16（假日 / 数据缺）
    idx_map = {
        "2026-05-15": 0.005,
        "2026-05-17": -0.003,
        "2026-05-18": 0.002,
    }
    a, h = _inner_join_returns(account_dates, account_returns, idx_map)
    # 交集：2026-05-15, 2026-05-17, 2026-05-18（2026-05-16 不在）
    assert a == [0.01, -0.005, 0.008]
    assert h == [0.005, -0.003, 0.002]


@pytest.mark.unit
def test_inner_join_index_has_extra_dates():
    """指数日期多于账户日期 → 只取账户日期所在的子集（账户在主导）."""
    account_dates = ["2026-05-15", "2026-05-16"]
    account_returns = [0.01, 0.02]
    idx_map = {
        "2026-05-14": 0.0,  # 不在账户
        "2026-05-15": 0.005,
        "2026-05-16": 0.015,
        "2026-05-17": 0.0,  # 不在账户
    }
    a, h = _inner_join_returns(account_dates, account_returns, idx_map)
    assert a == [0.01, 0.02]
    assert h == [0.005, 0.015]


@pytest.mark.unit
def test_inner_join_no_zero_padding():
    """缺失日期 MUST NOT 被 0.0 兜底（v1.3.0 旧行为，本 fix 切断）."""
    account_dates = ["2026-05-15", "2026-05-16", "2026-05-17"]
    account_returns = [0.01, 0.02, -0.005]
    # 完全没有 2026-05-16 数据
    idx_map = {"2026-05-15": 0.005, "2026-05-17": -0.003}
    a, h = _inner_join_returns(account_dates, account_returns, idx_map)
    # 2026-05-16 不应作为 0.0 出现在结果中
    assert 0.0 not in h or h.count(0.0) == 0  # 检查没有合成 0
    # 结果长度 = 交集 = 2，不是 account_dates 的 3
    assert len(a) == len(h) == 2
    assert a == [0.01, -0.005]
    assert h == [0.005, -0.003]


@pytest.mark.unit
def test_inner_join_empty_inputs():
    """空输入 → 空输出，不抛异常."""
    a, h = _inner_join_returns([], [], {})
    assert a == []
    assert h == []
