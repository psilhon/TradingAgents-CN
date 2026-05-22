## Why

`docs/code-review-2026-05-05.md` 第三梯队架构重构项 `agent-state-structured-history`。

**投资辩论的 speaker tracking 靠字符串前缀嗅探**：

`tradingagents/graph/conditional_logic.py:210` 的 `should_continue_debate`：

```python
current_speaker = state["investment_debate_state"]["current_response"]
...
next_speaker = "Bear Researcher" if current_speaker.startswith("Bull") else "Bull Researcher"
```

`current_response` 字段被**复用**——它本是「上一轮论点文本」（bull/bear researcher 写入 `f"Bull Analyst: {response.content}"` / `f"Bear Analyst: {response.content}"`，对手 researcher 在 prompt 里读它作「最后的看涨/看跌论点」）。routing 靠嗅探这段文本是否以 `"Bull"` 开头来反推发言者。

**脆弱点**：

1. routing 正确性依赖 `"Bull Analyst: "` / `"Bear Analyst: "` 前缀逐字节稳定——前缀字符串一旦改动（如本地化、加 emoji），routing 静默错乱。
2. `research_manager.py:106` 写 `current_response = response.content`（裁决全文，**无前缀**）。manager 在辩论结束后运行，当前不影响 routing，但 `current_response` 的语义在三个写入方之间不一致，是隐患。
3. LLM 输出本身若以 "Bull" 开头（researcher 拷贝里 news 版无前缀场景已有先例），嗅探即误判。

**风险讨论侧** `conditional_logic.py:239,241` 用 `latest_speaker.startswith("Risky")` / `.startswith("Safe")`。这里 `latest_speaker` **已经是结构化离散字段**（3 个 debator 分别写 `"Risky"` / `"Safe"` / `"Neutral"`）——`.startswith` 是不必要的宽松匹配，应收紧为相等比较。

## What Changes

### 设计：给 InvestDebateState 加显式 speaker 字段

不再让 routing 嗅探 `current_response` 文本，而是读一个专门的结构化字段：

- `InvestDebateState` TypedDict 新增 `current_speaker: str`，取值 `"Bull"` / `"Bear"` / `"Manager"`
- `bull_researcher` 写 `current_speaker = "Bull"`，`bear_researcher` 写 `"Bear"`，`research_manager` 写 `"Manager"`
- `should_continue_debate` 改读 `current_speaker`：`"Bear Researcher" if current_speaker == "Bull" else "Bull Researcher"`
- `current_response` **保留**——它仍是「上一轮论点文本」，被对手 researcher 在 prompt 里消费；本 change 只是停止把它复用为 routing 信号，不删除它

### 风险讨论侧收紧

`should_continue_risk_analysis` 的 `latest_speaker.startswith("Risky")` / `.startswith("Safe")` → `== "Risky"` / `== "Safe"`。`latest_speaker` 已是结构化字段，无 schema 变更。

### 改动清单

- **MODIFIED** `tradingagents/agents/utils/agent_states.py`：`InvestDebateState` 加 `current_speaker` 字段
- **MODIFIED** `tradingagents/agents/researchers/bull_researcher.py`：state 写入加 `current_speaker: "Bull"`
- **MODIFIED** `tradingagents/agents/researchers/bear_researcher.py`：state 写入加 `current_speaker: "Bear"`
- **MODIFIED** `tradingagents/agents/managers/research_manager.py`：state 写入加 `current_speaker: "Manager"`
- **MODIFIED** `tradingagents/graph/conditional_logic.py`：`should_continue_debate` 读 `current_speaker`；`should_continue_risk_analysis` 收紧比较
- **MODIFIED** 初始 `InvestDebateState` 构造点（`trading_graph` propagate 区）：加 `current_speaker: ""` 键，保持直接 subscript 不 KeyError
- **NEW** `tests/test_conditional_logic_routing.py`：`should_continue_debate` / `should_continue_risk_analysis` 路由单元测试（纯 state 逻辑，无 LLM）
- **MODIFIED** `docs/CHANGELOG.md`：`[Unreleased]` 加一段

### 行为契约（不变 / 变）

- **不变**：辩论从 Bull 开始（初始 `current_speaker = ""`，`"" == "Bull"` 为 False → "Bull Researcher"，与原 `"".startswith("Bull")` 一致）；轮转 Bull↔Bear；达 `max_count` → "Research Manager"；风险轮转 Risky→Safe→Neutral→Risky，达上限 → "Risk Judge"
- **变**：routing 不再依赖 `current_response` 文本前缀——`current_response` 即使被改写也不影响 speaker 路由

### 不在本 change 范围（YAGNI）

- 把 `history` / `bull_history` / `bear_history` 的字符串拼接重构为结构化 turn list——这些字符串直接喂 prompt，重构等于改写 5+ 文件的 prompt 构造，不是本 backlog 项的内容
- `current_response` 字段移除——它仍是对手 researcher 消费的「上一轮论点」文本
- `RiskDebateState` schema 变更——`latest_speaker` 已结构化，只收紧比较

## Capabilities

### New Capabilities

- `agent-debate-routing`：多智能体辩论（投资辩论 + 风险讨论）的 speaker 路由与终止规则。锁定：speaker tracking MUST 用 agent state 里的显式结构化字段，禁止嗅探 response 文本前缀。

## Impact

**改动文件**：6 个 source 修改 + 1 新建 test + 1 spec + 1 CHANGELOG 段

**许可边界**：全部在 `tradingagents/`（Apache 2.0）——不触及 `app/` `frontend/` 专有授权代码。

**风险**：低
- routing 行为契约不变（初始 / 轮转 / 终止全部对齐原行为），仅信号来源从「文本嗅探」换成「结构化字段」
- `InvestDebateState` 加字段——所有读写 `investment_debate_state` 的点须同批改（含初始构造点），否则直接 subscript 触发 `KeyError`；tasks 里逐点核对
- `should_continue_debate` / `should_continue_risk_analysis` 是纯 state 逻辑，可无 LLM 直接单元测试覆盖

**收益**：
- speaker 路由不再依赖 `"Bull Analyst: "` 前缀逐字节稳定，消除一类静默误路由隐患
- `current_response` 语义单一化（仅「论点文本」，不再兼任 routing 信号）
- 新 capability 锁定契约
