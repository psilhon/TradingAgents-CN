# Tasks — agent-state-structured-history

## 1. 立项 — commit 1

- [x] 1.1 写 `proposal.md`
- [x] 1.2 写 `tasks.md`
- [x] 1.3 写 `specs/agent-debate-routing/spec.md`（新 capability，ADDED Requirements）
- [ ] 1.4 commit（仅 OpenSpec 文件）

## 2. 结构化 speaker 字段 + 路由测试 — commit 2

- [ ] 2.1 **RED**：写 `tests/test_conditional_logic_routing.py`（`@pytest.mark.unit`，纯 state dict，无 LLM / 无 mock）
  - `should_continue_debate`：`current_speaker="Bull"` → `"Bear Researcher"`
  - `should_continue_debate`：`current_speaker="Bear"` → `"Bull Researcher"`
  - `should_continue_debate`：`current_speaker=""`（初始）→ `"Bull Researcher"`
  - `should_continue_debate`：`count >= 2*max_rounds` → `"Research Manager"`
  - `should_continue_risk_analysis`：`latest_speaker="Risky"` → `"Safe Analyst"`
  - `should_continue_risk_analysis`：`latest_speaker="Safe"` → `"Neutral Analyst"`
  - `should_continue_risk_analysis`：`latest_speaker="Neutral"` → `"Risky Analyst"`
  - `should_continue_risk_analysis`：`count >= 3*max_rounds` → `"Risk Judge"`
  - 测试断言基于 `current_speaker`（新字段），RED 阶段会因 `conditional_logic` 仍读 `current_response` 而失败
- [ ] 2.2 `agent_states.py`：`InvestDebateState` 加 `current_speaker: Annotated[str, "..."]` 字段
- [ ] 2.3 `bull_researcher.py`：`new_investment_debate_state` 加 `"current_speaker": "Bull"`
- [ ] 2.4 `bear_researcher.py`：`new_investment_debate_state` 加 `"current_speaker": "Bear"`
- [ ] 2.5 `research_manager.py`：`new_investment_debate_state` 加 `"current_speaker": "Manager"`
- [ ] 2.6 grep 定位初始 `InvestDebateState` 构造点（预期 `tradingagents/graph/` propagate / propagation 区）→ 加 `"current_speaker": ""`
- [ ] 2.7 **GREEN**：`conditional_logic.should_continue_debate` 改读 `current_speaker`，routing `current_speaker == "Bull"`
- [ ] 2.8 `conditional_logic.should_continue_risk_analysis`：`.startswith("Risky")` → `== "Risky"`，`.startswith("Safe")` → `== "Safe"`
- [ ] 2.9 跑 `pytest tests/test_conditional_logic_routing.py` PASS
- [ ] 2.10 grep 验证：`tradingagents/` 内 `current_response` 不再被任何 routing / 控制流读取（仅作 prompt 文本）
- [ ] 2.11 `just lint` + `just typecheck` 0 errors
- [ ] 2.12 `pytest -m unit` 无回归
- [ ] 2.13 commit

## 3. CHANGELOG + 验证 + Archive — commit 3

- [ ] 3.1 `docs/CHANGELOG.md` `[Unreleased]` 加 `### Changed` 段
- [ ] 3.2 `just ci` 通过（lint + typecheck + test）
- [ ] 3.3 Archive：change 目录 → `openspec/changes/archive/2026-05-22-agent-state-structured-history`
- [ ] 3.4 Spec sync：稳定 spec 写入 `openspec/specs/agent-debate-routing/spec.md`（新 capability）
- [ ] 3.5 commit archive + spec sync
- [ ] 3.6 finishing report；push / tag 决策交用户
