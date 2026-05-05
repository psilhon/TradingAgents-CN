## MODIFIED Requirements

### Requirement: 真 bug 类 lint issue 优先修

`F821` (undefined-name) 和 `F811` (redefined-while-unused) 是潜在 runtime 错误（NameError / 错 import 模块），治理优先级 MUST 高于代码风格 / 复杂度类（如 E402 / B007 / E722）。

代码风格 / 类型注解 / 复杂度类（E5xx / B0xx / RUFxxx / UPxxx 等）SHALL 在真 bug 修完后**按 rule code 分批治理**——每个 rule 一个 commit、每 commit 后验证（核心模块 import + backend health）、目标 ruff stat 降到 0（或留 < 50 个明确合理 noqa 标注）。

ruff stat 中 F821 + F811 数量 SHALL 维持 **0**（任何新引入的真 bug 必须立即修，不积累）。

#### Scenario: ruff F821 + F811 数量

- **WHEN** `uvx ruff check . --select F821,F811`
- **THEN** Found 0 errors
- **AND** exit code 0

#### Scenario: 风格类治理后总 issue 数

- **WHEN** 完成所有 lint-handfix-pass 后跑 `uvx ruff check .`
- **THEN** Found ≤ 50 errors（剩余必须是无法/不应修的合理 noqa case）
- **AND** 没有 F821 / F811 / E722 / B007 / B905 等明显可治理的 rule 残留

### Requirement: F811 重复 import 修复策略

修 F811 (redefined-while-unused) 时，MUST 删除 ruff 标记的 `previous definition`（即被覆盖的 unused 那条），保留实际生效的最新 definition——除非通过代码 review 确认 previous definition 是正确的（这种情况下应反向修：保留 previous，删 redefined 的）。

#### Scenario: 默认删 unused previous

- **WHEN** ruff 报 `F811 Redefinition of unused 'get_logger' from line 11`
- **AND** line 11 是 `from A import get_logger`，line 14 是 `from B import get_logger`
- **THEN** 默认删除 line 11
- **AND** 保留 line 14（实际生效的 import）

## ADDED Requirements

### Requirement: unsafe-fixes 应用前必须 smoke test

应用 `ruff --fix --unsafe-fixes` 改动后，MUST 验证：

1. `.venv/bin/python -c "import tradingagents.graph.trading_graph"` 不报错
2. backend 重启 + curl `/api/health` HTTP 200
3. （如改动涉及 frontend 相关）vite dev 仍跑 + 浏览器 5 个常用页面无 console error

任一失败 MUST 立即 `git revert` 该 commit，并降级为"按 rule code 单独处理"+ 每个 rule 评估 unsafe-fix 安全性。

#### Scenario: unsafe-fix 后 backend 启动失败

- **WHEN** 跑 `uvx ruff check --fix --unsafe-fixes --select F841 .`
- **AND** 修改若干 .py 文件删 unused variable
- **AND** backend 重启时报 `ImportError`（因副作用 import 被误删）
- **THEN** 立即 `git revert` 该 commit
- **AND** 改回手动逐个评估 F841 case
