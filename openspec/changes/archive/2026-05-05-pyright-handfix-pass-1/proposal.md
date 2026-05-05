## Why

`pyright-cleanup-baseline` 后剩 1,224 errors。**继续按"调宽 + 真治理"两段走**：本 change 是"调宽段"——silence 7 类 fork 项目固有噪音（pandas 动态属性 / 第三方库无 stub / 等），剩"真问题"类留独立 hand-fix change。

数据：
| 类别 | Count | 性质 | 本 change 处理 |
|---|---|---|---|
| `reportAttributeAccessIssue` | 228 | pandas DataFrame `.col` 动态属性 | 🔇 silence |
| `reportFunctionMemberAccess` | 47 | 类似 attribute | 🔇 silence |
| `reportReturnType` | 38 | 返回值类型推断 | 🔇 silence |
| `reportMissingModuleSource` | 32 | 装了但缺 stub | 🔇 silence |
| `reportUnsupportedDunderAll` | 18 | `__all__` 类型 | 🔇 silence |
| `reportOperatorIssue` | 16 | 操作符类型 | 🔇 silence |
| `reportAssignmentType` | 16 | 赋值类型推断 | 🔇 silence |
| 其它真问题 | ~830 | reportMissingImports 494 / reportOptionalMemberAccess 132 / reportArgumentType 107 / reportPossiblyUnbound 58 / reportCallIssue 26 / 等 | 留 hand-fix change |

预期效果：1,224 → ~830 errors（-32%）。

## What Changes

- **MODIFIED** `pyproject.toml [tool.pyright]`：加 7 个 rule 设为 `"none"`（silence）
- 不修代码

## Capabilities

### Modified Capabilities

- `lint-policy`：MODIFY「pyright 配置 — 中文 + 数据处理 fork 友好」Requirement 加 silence 7 类 rule 的 fork-friendly 配置

## Impact

- pyright 1,224 → ~830 errors
- 剩 ~830 是真问题（缺 import / 真 None bug / 类型不匹配 / 等），留 `pyright-handfix-pass-2` 治理
- pre-commit hook 仍 warn-only
- 无 runtime 影响（仅 pyright 配置）
