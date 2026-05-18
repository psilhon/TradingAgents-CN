"""
共享的文档指标处理函数
- add_financial_metrics: 将日度基础指标（市值/估值/交易）追加到文档中
- sanitize_numeric_fields: stock_basic_info 写库前的数值 sanity 闸门
"""
from typing import Dict, List

# 数学上不可能为负的字段：price-to-sales、市值恒 ≥ 0。负值必为脏数据，拒绝入库。
_NON_NEGATIVE_FIELDS = ("ps", "ps_ttm", "total_mv", "circ_mv")
# pe 绝对值合理上界：真实 PE 极少超过几百，|pe| 越界意味净利润趋近 0、数值已失真。
# 负 pe 本身合法（亏损公司），故只看绝对值量级，不拒负号。
_PE_FIELDS = ("pe", "pe_ttm")
_PE_SANE_ABS_MAX = 1000.0


def add_financial_metrics(doc: Dict, daily_metrics: Dict) -> None:
    """
    将财务与交易指标写入 doc（就地修改）。
    - 市值：total_mv/circ_mv（从万元转换为亿元）
    - 估值：pe/pb/pe_ttm/pb_mrq/ps/ps_ttm（过滤 NaN/None）
    - 交易：turnover_rate/volume_ratio（过滤 NaN/None）
    - 股本：total_share/float_share（万股，过滤 NaN/None）
    """
    # 市值（万元 -> 亿元）
    if "total_mv" in daily_metrics and daily_metrics["total_mv"] is not None:
        doc["total_mv"] = daily_metrics["total_mv"] / 10000
    if "circ_mv" in daily_metrics and daily_metrics["circ_mv"] is not None:
        doc["circ_mv"] = daily_metrics["circ_mv"] / 10000

    # 估值指标（🔥 新增 ps 和 ps_ttm）
    for field in ["pe", "pb", "pe_ttm", "pb_mrq", "ps", "ps_ttm"]:
        if field in daily_metrics and daily_metrics[field] is not None:
            try:
                value = float(daily_metrics[field])
                if not (value != value):  # 过滤 NaN
                    doc[field] = value
            except (ValueError, TypeError):
                pass

    # 交易指标
    for field in ["turnover_rate", "volume_ratio"]:
        if field in daily_metrics and daily_metrics[field] is not None:
            try:
                value = float(daily_metrics[field])
                if not (value != value):  # 过滤 NaN
                    doc[field] = value
            except (ValueError, TypeError):
                pass

    # 🔥 股本数据（万股）
    for field in ["total_share", "float_share"]:
        if field in daily_metrics and daily_metrics[field] is not None:
            try:
                value = float(daily_metrics[field])
                if not (value != value):  # 过滤 NaN
                    doc[field] = value
            except (ValueError, TypeError):
                pass


def sanitize_numeric_fields(doc: Dict) -> List[str]:
    """stock_basic_info 写库前的数值 sanity 闸门（就地修改 doc）。

    数据源接口失败被逐层 except 吞掉时，会产出"字段齐全但数值错误"的文档
    （如负 ps、量级失真的 pe），旧逻辑不校验照写进库，污染筛选/排序/分析。
    本闸门在 UpdateOne 前拦截：
    - 数学上不可能的值（负 ps/ps_ttm/total_mv/circ_mv）→ 删除该字段，不让脏值入库。
    - pe 量级失真（|pe| 越界）→ 保留数值但告警标记（极端 PE 理论上可能，不强删）。

    Returns:
        告警信息列表（每条描述一个被拒/被标记的字段），供调用方汇总进
        sync_status.warnings；列表为空表示该文档数值全部通过校验。
    """
    issues: List[str] = []
    code = doc.get("code", "?")

    for field in _NON_NEGATIVE_FIELDS:
        value = doc.get(field)
        if value is not None and value < 0:
            issues.append(f"{code} {field}={value} 为负（数学不可能），已拒绝该字段入库")
            doc.pop(field, None)

    for field in _PE_FIELDS:
        value = doc.get(field)
        if value is not None and abs(value) > _PE_SANE_ABS_MAX:
            issues.append(f"{code} {field}={value} 量级失真（|{field}|>{_PE_SANE_ABS_MAX:.0f}）")

    return issues

