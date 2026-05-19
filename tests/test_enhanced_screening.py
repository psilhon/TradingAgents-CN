"""增强股票筛选服务集成测试。

覆盖 enhanced_screening_service 的端到端行为：字段元信息、数据库优化筛选、
条件校验（正向 + 负向）、字段统计、复杂多条件筛选。

注意：EnhancedScreeningService.screen_stocks 内部 try/except 会把异常吞成
`source="error"` —— 断言显式拦截，否则筛选崩溃也会被当成空结果放过。

需真实 MongoDB（stock_screening_view / stock_basic_info）。属 integration 标记，
默认 `-m "not integration"` 跳过，用 `pytest -m integration` 显式执行。
"""

import asyncio
from typing import Any

import pytest
from dotenv import load_dotenv

pytestmark = pytest.mark.integration

load_dotenv()


def _assert_screen_result(result: dict[str, Any], limit: int) -> None:
    """校验 EnhancedScreeningService.screen_stocks 返回值的结构 + 未吞内部异常。"""
    assert isinstance(result, dict)
    # source="error" 表示 screen_stocks 内部捕获了异常（如查询超时）
    assert result.get("source") != "error", f"筛选内部异常被吞：{result.get('error')}"
    assert "error" not in result
    assert isinstance(result["total"], int)
    assert result["total"] >= 0
    assert isinstance(result["items"], list)
    assert len(result["items"]) <= limit
    assert len(result["items"]) <= result["total"]
    for item in result["items"]:
        assert item.get("code"), f"结果项缺 code：{item}"


def test_enhanced_screening():
    """enhanced_screening_service 各路径返回结构正确、路由正确、校验逻辑有效。"""
    from app.core.database import init_db
    from app.models.screening import OperatorType, ScreeningCondition
    from app.services.enhanced_screening_service import get_enhanced_screening_service

    async def _run():
        await init_db()
        service = get_enhanced_screening_service()

        # 1. 支持字段元信息（代码定义的注册表，与库内数据无关）
        fields = await service.get_all_supported_fields()
        assert isinstance(fields, list) and fields, "支持字段列表为空"
        for field_info in fields:
            assert {"name", "display_name", "field_type"} <= field_info.keys()

        # 2. 基础多条件筛选 —— 全部基础字段条件应走数据库优化路径
        conditions = [
            ScreeningCondition(field="total_mv", operator=OperatorType.GTE, value=100),
            ScreeningCondition(field="pe", operator=OperatorType.BETWEEN, value=[5, 30]),
            ScreeningCondition(field="industry", operator=OperatorType.CONTAINS, value="银行"),
        ]
        result = await service.screen_stocks(conditions=conditions, limit=10, use_database_optimization=True)
        _assert_screen_result(result, limit=10)
        assert result["optimization_used"] == "database", (
            f"全部为基础字段条件却未走数据库优化：optimization_used={result['optimization_used']}"
        )

        # 3. 条件校验 —— 正向：合法条件应全部通过
        validation = await service.validate_conditions(conditions)
        assert validation["valid"] is True, f"合法条件被判为非法：{validation['errors']}"
        assert validation["errors"] == []

        # 3b. 条件校验 —— 负向：不支持的字段应被识别（确保校验未整体失效）
        bad_conditions = [ScreeningCondition(field="不存在的字段", operator=OperatorType.GTE, value=1)]
        bad_validation = await service.validate_conditions(bad_conditions)
        assert bad_validation["valid"] is False
        assert bad_validation["errors"], "非法字段未产生校验错误"

        # 4. 字段统计信息
        field_info = await service.get_field_info("total_mv")
        assert field_info is not None
        assert field_info["name"] == "total_mv"
        assert "statistics" in field_info

        # 5. 复杂多条件筛选（BETWEEN / LTE / IN 操作符）
        complex_conditions = [
            ScreeningCondition(field="total_mv", operator=OperatorType.BETWEEN, value=[100, 1000]),
            ScreeningCondition(field="pe", operator=OperatorType.LTE, value=20),
            ScreeningCondition(field="pb", operator=OperatorType.LTE, value=3),
            ScreeningCondition(field="area", operator=OperatorType.IN, value=["北京", "上海", "深圳"]),
        ]
        complex_result = await service.screen_stocks(
            conditions=complex_conditions,
            limit=15,
            order_by=[{"field": "total_mv", "direction": "desc"}],
        )
        _assert_screen_result(complex_result, limit=15)

    asyncio.run(_run())
