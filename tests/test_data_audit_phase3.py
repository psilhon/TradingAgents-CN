"""data-audit-phase3 单元测试.

覆盖两个纯函数：
- sanitize_numeric_fields —— stock_basic_info 写库前数值 sanity 闸门（Item 1）。
- merge_duplicate_basic_info_docs —— 主键 (code,source)→code 去重选主逻辑（Item 2）。

均为无外部依赖的纯逻辑，标 unit marker（pre-commit / just test 会跑）。
"""

from __future__ import annotations

import pytest

from app.core.database import merge_duplicate_basic_info_docs
from app.services.basics_sync.processing import sanitize_numeric_fields

# --------------------------------------------------------------------------
# Item 1: sanitize_numeric_fields —— 数值 sanity 闸门
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_sanity_rejects_negative_ps() -> None:
    """负 ps 数学上不可能（price-to-sales），应被删除并告警。"""
    doc = {"code": "000001", "ps": -17.4, "pe": 12.0}
    issues = sanitize_numeric_fields(doc)
    assert "ps" not in doc  # 脏值被拒绝入库
    assert doc["pe"] == 12.0  # 正常字段保留
    assert len(issues) == 1
    assert "ps" in issues[0]


@pytest.mark.unit
def test_sanity_rejects_negative_market_cap() -> None:
    """负 total_mv / circ_mv 数学上不可能，应被删除。"""
    doc = {"code": "000002", "total_mv": -100.0, "circ_mv": -50.0}
    issues = sanitize_numeric_fields(doc)
    assert "total_mv" not in doc
    assert "circ_mv" not in doc
    assert len(issues) == 2


@pytest.mark.unit
def test_sanity_rejects_negative_ps_ttm() -> None:
    """ps_ttm 与 ps 同语义，负值同样拒绝。"""
    doc = {"code": "000003", "ps_ttm": -3.2}
    issues = sanitize_numeric_fields(doc)
    assert "ps_ttm" not in doc
    assert len(issues) == 1


@pytest.mark.unit
def test_sanity_keeps_negative_pe() -> None:
    """负 pe 合法（亏损公司），不拒绝、不告警。"""
    doc = {"code": "000004", "pe": -158.1, "pb": -2.0}
    issues = sanitize_numeric_fields(doc)
    assert doc["pe"] == -158.1  # 负 pe 保留
    assert doc["pb"] == -2.0  # 负 pb（负净资产）也合法，保留
    assert issues == []


@pytest.mark.unit
def test_sanity_flags_extreme_pe_but_keeps_it() -> None:
    """量级失真的 pe（|pe|>1000）标记告警但保留数值（极端 PE 理论上可能）。"""
    doc = {"code": "000005", "pe": -16622.0}
    issues = sanitize_numeric_fields(doc)
    assert doc["pe"] == -16622.0  # 标记不删除
    assert len(issues) == 1
    assert "pe" in issues[0]


@pytest.mark.unit
def test_sanity_clean_doc_passes() -> None:
    """全部数值正常的文档：无告警、字段不变。"""
    doc = {"code": "600519", "pe": 28.5, "pb": 9.1, "ps": 12.3, "total_mv": 16692.0}
    issues = sanitize_numeric_fields(doc)
    assert issues == []
    assert doc == {"code": "600519", "pe": 28.5, "pb": 9.1, "ps": 12.3, "total_mv": 16692.0}


@pytest.mark.unit
def test_sanity_none_values_ignored() -> None:
    """字段值为 None（数据源未供给）不算异常，不告警、不动。"""
    doc = {"code": "000006", "ps": None, "total_mv": None, "pe": None}
    issues = sanitize_numeric_fields(doc)
    assert issues == []
    assert doc == {"code": "000006", "ps": None, "total_mv": None, "pe": None}


@pytest.mark.unit
def test_sanity_multiple_issues_accumulate() -> None:
    """多个异常字段：逐个告警。"""
    doc = {"code": "000007", "ps": -1.0, "circ_mv": -2.0, "pe": 99999.0}
    issues = sanitize_numeric_fields(doc)
    assert len(issues) == 3
    assert "ps" not in doc and "circ_mv" not in doc  # 数学不可能值删除
    assert doc["pe"] == 99999.0  # 量级失真 pe 保留


# --------------------------------------------------------------------------
# Item 2: merge_duplicate_basic_info_docs —— 去重选主
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_merge_tushare_wins_over_akshare() -> None:
    """同 code 多源文档：tushare 优先级最高，选为主文档。"""
    docs = [
        {"_id": 1, "code": "000001", "source": "akshare", "name": "平安银行"},
        {"_id": 2, "code": "000001", "source": "tushare", "name": "平安银行"},
    ]
    primary, _patch, dead_ids = merge_duplicate_basic_info_docs(docs)
    assert primary["_id"] == 2  # tushare 文档
    assert dead_ids == [1]


@pytest.mark.unit
def test_merge_akshare_wins_over_baostock() -> None:
    """无 tushare 时 akshare 优先于 baostock。"""
    docs = [
        {"_id": 10, "code": "000002", "source": "baostock"},
        {"_id": 11, "code": "000002", "source": "akshare"},
    ]
    primary, _patch, dead_ids = merge_duplicate_basic_info_docs(docs)
    assert primary["_id"] == 11
    assert dead_ids == [10]


@pytest.mark.unit
def test_merge_patch_fills_missing_fields() -> None:
    """次文档用于补全主文档缺失（None / 不存在）的字段。"""
    docs = [
        {"_id": 1, "code": "000001", "source": "tushare", "name": "平安银行", "total_mv": None},
        {"_id": 2, "code": "000001", "source": "akshare", "industry": "银行", "total_mv": 3000.0},
    ]
    primary, patch, dead_ids = merge_duplicate_basic_info_docs(docs)
    assert primary["_id"] == 1  # tushare 选主
    assert patch["industry"] == "银行"  # 主文档无 industry → 补
    assert patch["total_mv"] == 3000.0  # 主文档 total_mv 为 None → 补
    assert dead_ids == [2]


@pytest.mark.unit
def test_merge_patch_does_not_overwrite_present_fields() -> None:
    """主文档已有的有效字段不被次文档覆盖。"""
    docs = [
        {"_id": 1, "code": "000001", "source": "tushare", "name": "平安银行"},
        {"_id": 2, "code": "000001", "source": "akshare", "name": "PINGAN"},
    ]
    _primary, patch, _dead_ids = merge_duplicate_basic_info_docs(docs)
    assert "name" not in patch  # 主文档已有 name，不覆盖


@pytest.mark.unit
def test_merge_uses_data_source_when_source_absent() -> None:
    """文档已迁移到 data_source 字段时，选主仍按数据源优先级。"""
    docs = [
        {"_id": 1, "code": "000001", "data_source": "akshare"},
        {"_id": 2, "code": "000001", "data_source": "tushare"},
    ]
    primary, _patch, dead_ids = merge_duplicate_basic_info_docs(docs)
    assert primary["_id"] == 2
    assert dead_ids == [1]


@pytest.mark.unit
def test_merge_single_doc_no_dead_no_patch() -> None:
    """只有一份文档（无重复）：无补丁、无待删。"""
    docs = [{"_id": 1, "code": "000001", "source": "tushare", "name": "平安银行"}]
    primary, patch, dead_ids = merge_duplicate_basic_info_docs(docs)
    assert primary["_id"] == 1
    assert patch == {}
    assert dead_ids == []


@pytest.mark.unit
def test_merge_unknown_source_lowest_priority() -> None:
    """未知数据源优先级为 0，低于已知源。"""
    docs = [
        {"_id": 1, "code": "000001", "source": "mystery"},
        {"_id": 2, "code": "000001", "source": "baostock"},
    ]
    primary, _patch, dead_ids = merge_duplicate_basic_info_docs(docs)
    assert primary["_id"] == 2  # baostock 优先于未知源
    assert dead_ids == [1]
