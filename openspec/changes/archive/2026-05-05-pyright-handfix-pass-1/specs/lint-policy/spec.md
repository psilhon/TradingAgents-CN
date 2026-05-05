## MODIFIED Requirements

### Requirement: pyright 配置 — 中文 + 数据处理 fork 友好

`pyproject.toml [tool.pyright]` MUST 用 `typeCheckingMode = "standard"`，**不**给 `tradingagents/` 设 `strict = [...]`——本 fork 大量使用 pandas DataFrame / 第三方数据源库返回值（无 type stub），strict 模式下 `reportUnknown*Type` 报警噪音 ~8,000+，无法治理也无价值。

降级 standard 后还需 silence 以下 7 类 fork 项目固有噪音（在 `[tool.pyright]` 设为 `"none"`）：

```toml
reportAttributeAccessIssue = "none"     # pandas DataFrame .column_name 动态属性
reportFunctionMemberAccess = "none"     # 类似 attribute access
reportReturnType = "none"               # 返回值类型推断（第三方库返回 unknown）
reportMissingModuleSource = "none"      # 装了包但缺 stub（如 dashscope）
reportUnsupportedDunderAll = "none"     # __all__ 类型推断
reportOperatorIssue = "none"            # 操作符与 unknown 类型
reportAssignmentType = "none"           # 赋值时类型推断
```

降级后 pyright 仍可检查"真问题"：
- `reportMissingImports`（缺 import / 模块找不到 — fork 删模块后的孤儿）
- `reportOptionalMemberAccess`（Optional 没 None check — 真 bug）
- `reportPossiblyUnbound`（变量可能未定义 — 真 bug）
- `reportArgumentType`（类型不匹配传参）
- `reportCallIssue`（调用签名错误）

#### Scenario: pyproject 不再含 strict tradingagents

- **WHEN** `grep -E "^strict\s*=" pyproject.toml`
- **THEN** 命中数为 0（没有 strict 段）

#### Scenario: pyright 错误数大幅减少 + 7 类 silence

- **WHEN** 跑 `uvx pyright`
- **THEN** 错误数 ≤ 900（从 1,224 砍到约 830）
- **AND** `reportAttributeAccessIssue` / `reportFunctionMemberAccess` / `reportReturnType` / `reportMissingModuleSource` / `reportUnsupportedDunderAll` / `reportOperatorIssue` / `reportAssignmentType` 报警基本消失
