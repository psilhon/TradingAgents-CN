## ADDED Requirements

### Requirement: pyright 配置 — 中文 + 数据处理 fork 友好

`pyproject.toml [tool.pyright]` MUST 用 `typeCheckingMode = "standard"`，**不**给 `tradingagents/` 设 `strict = [...]`——本 fork 大量使用 pandas DataFrame / 第三方数据源库返回值（无 type stub），strict 模式下 `reportUnknown*Type` 报警噪音 ~8,000+，无法治理也无价值。

降级 standard 后 pyright 仍可检查真问题：
- `reportMissingImports`（缺 import / 模块找不到）
- `reportAttributeAccessIssue`（错属性访问）
- `reportCallIssue`（调用签名错误）
- `reportOptionalMemberAccess`（Optional 没 None check）
- `reportPossiblyUnbound`（变量可能未定义）
- `reportArgumentType` / `reportReturnType`（类型不匹配）

#### Scenario: pyproject 不再含 strict tradingagents

- **WHEN** `grep -E "^strict\s*=" pyproject.toml`
- **THEN** 命中数为 0（没有 strict 段）

#### Scenario: pyright 错误数大幅减少

- **WHEN** 跑 `uvx pyright`
- **THEN** 错误数 ≤ 1,500（从 9,955 砍到约 1,224）
- **AND** `reportUnknown*Type` 报警基本消失（不再因 untyped 第三方库返回值报警）
