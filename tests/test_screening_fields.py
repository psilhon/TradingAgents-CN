"""筛选字段映射集成测试。

验证 database_screening_service.screen_stocks 的查询 / 排序 / 结果格式化链路：
按 total_mv 筛选 → 返回结构正确、关键字段齐全、降序排序生效。

需真实 MongoDB（stock_screening_view，akshare 数据源）。属 integration 标记，
默认 `-m "not integration"` 跳过，用 `pytest -m integration` 显式执行。
"""

import asyncio

import pytest
from dotenv import load_dotenv

pytestmark = pytest.mark.integration

load_dotenv()


def test_screening_fields():
    """按 total_mv 筛选：结果结构、关键字段、降序排序均正确。"""
    from app.core.database import init_db
    from app.services.database_screening_service import get_database_screening_service

    async def _run():
        await init_db()
        service = get_database_screening_service()

        # 显式指定 source，结果不受数据源优先级配置漂移影响
        results, total = await service.screen_stocks(
            conditions=[{"field": "total_mv", "operator": ">=", "value": 100}],
            limit=3,
            order_by=[{"field": "total_mv", "direction": "desc"}],
            source="akshare",
        )

        # 结构不变量
        assert isinstance(total, int)
        assert isinstance(results, list)
        assert len(results) <= 3
        assert len(results) <= total

        # 回归闸门：total_mv>=100 在 akshare 源下必有数据，0 结果即筛选链路回归
        assert total > 0, f"total_mv>=100 筛选返回 total={total}，疑似选股链路回归"
        assert results, "total>0 但 results 为空"

        # 字段完整性：_format_result 统一输出后端字段名
        first = results[0]
        assert isinstance(first, dict)
        for field in ("code", "name", "total_mv"):
            assert field in first, f"结果缺字段 {field}，实际字段：{sorted(first)}"

        # 筛选条件必须在结果中体现
        assert first["total_mv"] >= 100

        # 降序排序生效
        market_values = [r["total_mv"] for r in results]
        assert market_values == sorted(market_values, reverse=True)

    asyncio.run(_run())
