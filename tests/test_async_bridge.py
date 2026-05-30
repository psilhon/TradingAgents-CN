"""run_coro_blocking 单元测试 —— 同步代码安全驱动协程。

回归背景：optimized_china_data._get_real_financial_metrics 原先用
`asyncio.get_event_loop().run_until_complete(...)` 驱动 provider 的异步方法。
当该同步函数从一个**已在运行的事件循环**里被调用（async FastAPI 路由 /
LangGraph async 节点）时，run_until_complete 抛
RuntimeError("This event loop is already running")，被宽 except 吞掉 ->
真实财务数据静默退化为 None。run_coro_blocking 在「循环已运行」时把协程
offload 到独立线程的新循环，规避该异常。
"""

from __future__ import annotations

import asyncio

import pytest

from tradingagents.utils.async_bridge import run_coro_blocking

pytestmark = pytest.mark.unit


async def _answer(x: int) -> int:
    await asyncio.sleep(0)
    return x * 2


async def _boom() -> None:
    await asyncio.sleep(0)
    raise ValueError("boom")


def test_runs_without_running_loop() -> None:
    """无运行中循环：直接驱动协程到完成。"""
    assert run_coro_blocking(_answer(21)) == 42


def test_runs_inside_running_loop() -> None:
    """关键回归：在已运行的事件循环里调用同步桥接，不抛
    RuntimeError，正确返回结果。旧的 run_until_complete 写法在此处会崩。"""

    async def _outer() -> int:
        # 进入这里时当前线程已有运行中的事件循环
        return run_coro_blocking(_answer(50))

    assert asyncio.run(_outer()) == 100


def test_propagates_exception_without_running_loop() -> None:
    """协程内异常应原样抛出，不被吞。"""
    with pytest.raises(ValueError, match="boom"):
        run_coro_blocking(_boom())


def test_propagates_exception_inside_running_loop() -> None:
    """循环已运行时，offload 线程里的异常也应原样抛回调用方。"""

    async def _outer() -> None:
        run_coro_blocking(_boom())

    with pytest.raises(ValueError, match="boom"):
        asyncio.run(_outer())
