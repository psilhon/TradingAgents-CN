## Why

pyright 报 **9,955 errors**，其中 80% (~7,983) 是 `reportUnknown*Type`（`reportUnknownMemberType` 3513 + `reportUnknownVariableType` 2516 + `reportUnknownArgumentType` 1387 + `reportUnknownParameterType` 567）—— 这些都是 `pyproject.toml [tool.pyright].strict = ["tradingagents"]` 严格模式触发的"未注解类型"警告。

本 fork 大量代码用 pandas DataFrame / 第三方库返回值（无 stub），strict 模式下每个 `df.column_name` / `result.attribute` 都报 unknown。**真治理"需给所有 5000+ 行加 type hint"——不现实**。

中文项目 + 数据处理重 fork，正确策略是**降级到 standard mode**（去 strict tradingagents），让 pyright 只查真问题（缺 import / 属性访问错 / 类型不匹配等）。

## What Changes

- **MODIFIED** `pyproject.toml [tool.pyright]`：删除 `strict = ["tradingagents"]` 行（所有目录用 `typeCheckingMode = "standard"`）

预期效果：9,955 → ~1,224 errors（-87%）。剩 1,224 多是真问题（`reportMissingImports` 494 + `reportAttributeAccessIssue` 306 + `reportCallIssue` ?），留独立 change `pyright-handfix-pass-1` 治理。

无 BREAKING change。仅配置调整，不改源码。

## Capabilities

### Modified Capabilities

- `lint-policy`：MODIFY「lint 治理过程保持 warn-only」Requirement 加"pyright 配置降级 strict → standard 是中文 + 数据处理 fork 项目的合理 baseline"

## Impact

- pyright 9,955 → ~1,224 errors
- pre-commit pyright hook 仍 warn-only（pyright 还有 1,224 errors 不阻塞）
- 后续可立 `pyright-handfix-pass-1` 治理 1,224（按 error code 分批，类似 lint-cleanup pass-1/2）+ `pyright-strict-mode-enable` 转严格
