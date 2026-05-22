"""conditional_logic 路由单元测试 — OpenSpec change agent-state-structured-history。

`should_continue_debate` / `should_continue_risk_analysis` 是纯 state 逻辑（无 LLM、
无外部依赖）。但 `import tradingagents.graph` 会触发 `graph/__init__.py` eager 加载
`trading_graph` → `config_manager`（import 即连 MongoDB）。这里用
`spec_from_file_location` 单独加载 `conditional_logic.py`，绕开包 `__init__`，
保持本测试为纯 unit。
"""

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_CL_PATH = Path(__file__).resolve().parents[1] / "tradingagents" / "graph" / "conditional_logic.py"
_spec = importlib.util.spec_from_file_location("_conditional_logic_under_test", _CL_PATH)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
ConditionalLogic = _mod.ConditionalLogic


def _invest_state(count: int, current_speaker: str, current_response: str = "") -> dict:
    return {
        "investment_debate_state": {
            "count": count,
            "current_speaker": current_speaker,
            "current_response": current_response,
        }
    }


def _risk_state(count: int, latest_speaker: str) -> dict:
    return {"risk_debate_state": {"count": count, "latest_speaker": latest_speaker}}


# --- 投资辩论路由（max_debate_rounds=1 → max_count=2）---


def test_debate_bull_then_bear():
    logic = ConditionalLogic(max_debate_rounds=1)
    # current_response 故意留空：旧逻辑嗅探 "".startswith("Bull") 会误判为 -> Bull Researcher
    assert logic.should_continue_debate(_invest_state(0, "Bull")) == "Bear Researcher"


def test_debate_bear_then_bull():
    logic = ConditionalLogic(max_debate_rounds=1)
    # current_response 故意以 "Bull" 开头：旧逻辑嗅探会误判为 Bull 刚发言 -> Bear Researcher
    assert logic.should_continue_debate(_invest_state(0, "Bear", "Bull Analyst: x")) == "Bull Researcher"


def test_debate_initial_starts_with_bull():
    logic = ConditionalLogic(max_debate_rounds=1)
    assert logic.should_continue_debate(_invest_state(0, "")) == "Bull Researcher"


def test_debate_max_count_stops():
    logic = ConditionalLogic(max_debate_rounds=1)
    assert logic.should_continue_debate(_invest_state(2, "Bull")) == "Research Manager"


# --- 风险讨论路由（max_risk_discuss_rounds=1 → max_count=3）---


def test_risk_risky_then_safe():
    logic = ConditionalLogic(max_risk_discuss_rounds=1)
    assert logic.should_continue_risk_analysis(_risk_state(0, "Risky")) == "Safe Analyst"


def test_risk_safe_then_neutral():
    logic = ConditionalLogic(max_risk_discuss_rounds=1)
    assert logic.should_continue_risk_analysis(_risk_state(0, "Safe")) == "Neutral Analyst"


def test_risk_neutral_then_risky():
    logic = ConditionalLogic(max_risk_discuss_rounds=1)
    assert logic.should_continue_risk_analysis(_risk_state(0, "Neutral")) == "Risky Analyst"


def test_risk_max_count_stops():
    logic = ConditionalLogic(max_risk_discuss_rounds=1)
    assert logic.should_continue_risk_analysis(_risk_state(3, "Risky")) == "Risk Judge"
