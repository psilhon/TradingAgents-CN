"""Toolkit config 实例隔离（ContextVar 注入）守护测试。

回归背景：Toolkit 原先用类级共享可变 dict 持有 config，update_config
in-place mutate 它，导致并发分析跨请求串味（cross-request config bleed）。
改用 contextvars.ContextVar 后，每个执行上下文（worker 线程）持有独立 config。
纯逻辑 unit test，不触外部依赖。
"""

from __future__ import annotations

import threading

import pytest

from tradingagents.agents.utils.toolkit_config import (
    get_toolkit_config,
    set_toolkit_config,
)
from tradingagents.default_config import DEFAULT_CONFIG

pytestmark = pytest.mark.unit


def test_isolation_across_threads() -> None:
    """核心回归：两个线程各 set 不同 config，互不串味。"""
    results: dict[str, object] = {}
    barrier = threading.Barrier(2)

    def worker(name: str, depth: str) -> None:
        set_toolkit_config({"research_depth": depth})
        barrier.wait(timeout=5)
        results[name] = get_toolkit_config().get("research_depth")

    t_a = threading.Thread(target=worker, args=("A", "快速"))
    t_b = threading.Thread(target=worker, args=("B", "全面"))
    t_a.start()
    t_b.start()
    t_a.join(timeout=5)
    t_b.join(timeout=5)

    assert results["A"] == "快速", f"线程 A 串味：读到 {results['A']}"
    assert results["B"] == "全面", f"线程 B 串味：读到 {results['B']}"


def test_default_fallback_when_unset() -> None:
    """未 set 时返回含 DEFAULT_CONFIG 键的 dict（用 online_tools，
    因为 DEFAULT_CONFIG 没有 research_depth 键）。"""

    def worker(out: dict[str, object]) -> None:
        cfg = get_toolkit_config()
        out["has_key"] = "online_tools" in cfg
        out["value"] = cfg.get("online_tools")

    out: dict[str, object] = {}
    t = threading.Thread(target=worker, args=(out,))
    t.start()
    t.join(timeout=5)

    assert out["has_key"] is True
    assert out["value"] == DEFAULT_CONFIG["online_tools"]


def test_set_does_not_mutate_default_config() -> None:
    """set_toolkit_config 写新 dict，绝不污染共享 DEFAULT_CONFIG。"""
    original = DEFAULT_CONFIG.get("online_tools")
    set_toolkit_config({"online_tools": not original, "research_depth": "深度"})
    assert DEFAULT_CONFIG.get("online_tools") == original, "DEFAULT_CONFIG 被污染"
    assert "research_depth" not in DEFAULT_CONFIG, "新键泄漏进 DEFAULT_CONFIG"


def test_set_merges_over_defaults() -> None:
    """set 后的 config 既含传入键，也含 DEFAULT_CONFIG 的其它键。"""
    set_toolkit_config({"research_depth": "标准"})
    cfg = get_toolkit_config()
    assert cfg["research_depth"] == "标准"
    assert "online_tools" in cfg


def test_toolkit_property_reflects_set_config() -> None:
    """Toolkit().config property 与 get_toolkit_config 行为一致。"""
    from tradingagents.agents.utils.agent_utils import Toolkit

    tk = Toolkit(config={"research_depth": "深度"})
    assert tk.config.get("research_depth") == "深度"
    assert tk.config.get("research_depth") == get_toolkit_config().get("research_depth")


def test_toolkit_init_sets_context_for_line692_read() -> None:
    """构造 Toolkit 后，line 692 风格的读取拿到本次 config 的 research_depth。"""
    from tradingagents.agents.utils.agent_utils import Toolkit

    Toolkit(config={"research_depth": 4})
    assert get_toolkit_config().get("research_depth", "标准") == 4
