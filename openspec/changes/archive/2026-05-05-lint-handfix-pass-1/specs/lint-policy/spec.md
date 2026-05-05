## ADDED Requirements

### Requirement: 真 bug 类 lint issue 优先修

`F821` (undefined-name) 和 `F811` (redefined-while-unused) 是潜在 runtime 错误（NameError / 错 import 模块），治理优先级 MUST 高于代码风格 / 复杂度类（如 E402 / B007 / E722）。

ruff stat 中 F821 + F811 数量 SHALL 维持 **0**（任何新引入的真 bug 必须立即修，不积累）。

#### Scenario: ruff F821 + F811 数量

- **WHEN** `uvx ruff check . --select F821,F811`
- **THEN** Found 0 errors
- **AND** exit code 0

### Requirement: F811 重复 import 修复策略

修 F811 (redefined-while-unused) 时，MUST 删除 ruff 标记的 `previous definition`（即被覆盖的 unused 那条），保留实际生效的最新 definition——除非通过代码 review 确认 previous definition 是正确的（这种情况下应反向修：保留 previous，删 redefined 的）。

#### Scenario: 默认删 unused previous

- **WHEN** ruff 报 `F811 Redefinition of unused 'get_logger' from line 11`
- **AND** line 11 是 `from A import get_logger`，line 14 是 `from B import get_logger`
- **THEN** 默认删除 line 11
- **AND** 保留 line 14（实际生效的 import）
