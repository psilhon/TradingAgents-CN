# Tasks — agent-state-structured-history

## 1. 立项 — commit 1

- [x] 1.1 写 `proposal.md`
- [x] 1.2 写 `tasks.md`
- [x] 1.3 写 `specs/agent-debate-routing/spec.md`（新 capability，ADDED Requirements）
- [x] 1.4 commit（仅 OpenSpec 文件）

## 2. 结构化 speaker 字段 + 路由测试 — commit 2

- [x] 2.1 **RED**：写 `tests/test_conditional_logic_routing.py`（`@pytest.mark.unit`，spec_from_file_location 隔离加载 conditional_logic 绕开 graph 包 mongo 副作用）— 8 用例，RED 阶段 2 fail / 6 pass
- [x] 2.2 `agent_states.py`：`InvestDebateState` 加 `current_speaker` 字段
- [x] 2.3 `bull_researcher.py`：`new_investment_debate_state` 加 `"current_speaker": "Bull"`
- [x] 2.4 `bear_researcher.py`：`new_investment_debate_state` 加 `"current_speaker": "Bear"`
- [x] 2.5 `research_manager.py`：`new_investment_debate_state` 加 `"current_speaker": "Manager"`
- [x] 2.6 初始 `InvestDebateState` 构造点（`propagation.py:34`）→ 加 `"current_speaker": ""`
- [x] 2.7 **GREEN**：`conditional_logic.should_continue_debate` 改读 `current_speaker`，routing `current_speaker == "Bull"`
- [x] 2.8 `conditional_logic.should_continue_risk_analysis`：`.startswith` → `==`
- [x] 2.9 跑 `pytest tests/test_conditional_logic_routing.py` PASS（8 passed, 0.14s）
- [x] 2.10 grep 验证：`conditional_logic.py` 已无 `current_response` 引用
- [x] 2.11 `just lint` + `just typecheck` 0 errors
- [x] 2.12 `pytest -m unit` 无回归（279 passed = 271 既有 + 8 新增）
- [ ] 2.13 commit

## 3. CHANGELOG + 验证 + Archive — commit 3

- [x] 3.1 `docs/CHANGELOG.md` `[Unreleased]` `### Changed` 加 ③ 条目
- [x] 3.2 `just ci` 通过（lint + typecheck + 279 unit tests）
- [x] 3.3 Archive：change 目录 → `openspec/changes/archive/2026-05-22-agent-state-structured-history`
- [x] 3.4 Spec sync：稳定 spec 写入 `openspec/specs/agent-debate-routing/spec.md`（新 capability）
- [x] 3.5 commit archive + spec sync
- [ ] 3.6 finishing report；push / tag 决策交用户
