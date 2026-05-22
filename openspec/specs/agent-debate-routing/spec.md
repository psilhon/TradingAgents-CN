# agent-debate-routing Specification

## Purpose

锁定多智能体辩论的「下一发言者」路由与终止契约：投资辩论（bull/bear researcher）与风险讨论（risky/safe/neutral analyst）如何决定下一个发言节点、何时结束。核心约束——speaker tracking MUST 基于 agent state 的显式结构化字段，禁止嗅探 response 文本前缀。此前投资辩论靠 `current_response.startswith("Bull")` 反推发言者，本 capability 收敛后路由不再依赖论点文本的前缀约定。

## Requirements

### Requirement: 结构化 speaker 路由

多智能体辩论（投资辩论的 bull/bear、风险讨论的 risky/safe/neutral）的「下一发言者」路由 MUST 基于 agent state 里的**显式结构化字段**判定，禁止嗅探 response 文本前缀。

- 投资辩论：`InvestDebateState` MUST 含 `current_speaker` 字段，取值集合 `{"Bull", "Bear", "Manager", ""}`；`conditional_logic.should_continue_debate` MUST 读 `current_speaker`，不得读 `current_response` 文本来推断发言者
- 风险讨论：`RiskDebateState.latest_speaker` 已是结构化离散字段（`{"Risky", "Safe", "Neutral"}`）；`should_continue_risk_analysis` MUST 用相等比较，不得用 `startswith` 前缀匹配
- `current_response` 字段保留其原语义（上一轮论点文本，供对手 researcher 在 prompt 中消费），MUST NOT 再被任何控制流 / routing 逻辑读取

#### Scenario: 投资辩论 routing grep 检查

- **WHEN** 在 `tradingagents/graph/conditional_logic.py` 检查 `should_continue_debate`
- **THEN** 路由判定 MUST 基于 `current_speaker` 字段
- **AND** MUST NOT 出现 `current_response.startswith(...)` 一类文本嗅探

#### Scenario: speaker 字段由发言节点写入

- **WHEN** `bull_researcher` / `bear_researcher` / `research_manager` 节点返回新的 `investment_debate_state`
- **THEN** 该 dict MUST 含 `current_speaker`，分别为 `"Bull"` / `"Bear"` / `"Manager"`

### Requirement: 投资辩论轮转与终止契约

`should_continue_debate` MUST 按下列规则路由：

- `count >= 2 * max_debate_rounds` → 返回 `"Research Manager"`（辩论结束）
- 否则 `current_speaker == "Bull"` → 返回 `"Bear Researcher"`
- 否则（含 `"Bear"` / `"Manager"` / 初始 `""`）→ 返回 `"Bull Researcher"`

辩论 MUST 从 Bull 开始：初始 `InvestDebateState` 的 `current_speaker` 为 `""`，首次路由落到 `"Bull Researcher"`。

#### Scenario: Bull 发言后轮到 Bear

- **WHEN** `current_speaker == "Bull"` 且 `count < 2 * max_debate_rounds`
- **THEN** `should_continue_debate` 返回 `"Bear Researcher"`

#### Scenario: Bear 发言后轮到 Bull

- **WHEN** `current_speaker == "Bear"` 且 `count < 2 * max_debate_rounds`
- **THEN** `should_continue_debate` 返回 `"Bull Researcher"`

#### Scenario: 初始状态从 Bull 开始

- **WHEN** `current_speaker == ""`（初始 state）
- **THEN** `should_continue_debate` 返回 `"Bull Researcher"`

#### Scenario: 达上限结束辩论

- **WHEN** `count >= 2 * max_debate_rounds`
- **THEN** `should_continue_debate` 返回 `"Research Manager"`

### Requirement: 风险讨论轮转与终止契约

`should_continue_risk_analysis` MUST 按下列规则路由：

- `count >= 3 * max_risk_discuss_rounds` → 返回 `"Risk Judge"`
- 否则 `latest_speaker == "Risky"` → 返回 `"Safe Analyst"`
- 否则 `latest_speaker == "Safe"` → 返回 `"Neutral Analyst"`
- 否则（含 `"Neutral"` / 初始）→ 返回 `"Risky Analyst"`

#### Scenario: 风险讨论三方轮转

- **WHEN** `latest_speaker` 依次为 `"Risky"` / `"Safe"` / `"Neutral"` 且未达上限
- **THEN** `should_continue_risk_analysis` 依次返回 `"Safe Analyst"` / `"Neutral Analyst"` / `"Risky Analyst"`

#### Scenario: 达上限结束讨论

- **WHEN** `count >= 3 * max_risk_discuss_rounds`
- **THEN** `should_continue_risk_analysis` 返回 `"Risk Judge"`
