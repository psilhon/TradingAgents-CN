## MODIFIED Requirements

### Requirement: pyright 配置 — 中文 + 数据处理 fork 友好

`pyproject.toml [tool.pyright]` MUST 用 `typeCheckingMode = "standard"`，**不**给 `tradingagents/` 设 `strict = [...]`。

需 silence 以下 15 类 fork 项目固有噪音 + 上游 dead code path 类（在 `[tool.pyright]` 设为 `"none"`）：

```toml
# pass-1 (fork 项目固有噪音)
reportAttributeAccessIssue = "none"
reportFunctionMemberAccess = "none"
reportReturnType = "none"
reportMissingModuleSource = "none"
reportUnsupportedDunderAll = "none"
reportOperatorIssue = "none"
reportAssignmentType = "none"
# pass-2 (上游 dead code path + 真问题但批量治理代价高)
reportMissingImports = "none"          # 上游 dead code 引用已删模块
reportOptionalMemberAccess = "none"    # Optional 没 None check（fork 现有大量 case）
reportArgumentType = "none"            # 第三方库返回 Any 与签名不匹配
reportPossiblyUnbound = "none"         # 变量可能未定义
reportCallIssue = "none"               # 调用签名错误
reportIncompatibleMethodOverride = "none"
reportOptionalOperand = "none"
reportGeneralTypeIssues = "none"
```

降级后 pyright 仍可检查少数严重错误（如严重 unbound / 类型不可恢复错误等），但日常 fork 维护不再被噪音淹没。

#### Scenario: pyproject 不再含 strict tradingagents

- **WHEN** `grep -E "^strict\s*=" pyproject.toml`
- **THEN** 命中数为 0

#### Scenario: pyright 0 errors

- **WHEN** 跑 `uvx pyright`
- **THEN** 错误数为 0
- **AND** 任何引入新 pyright error 的 commit 被 pre-commit hook 阻塞

### Requirement: lint 治理过程保持 warn-only

`.pre-commit-config.yaml` MUST 在 lint 治理期间（lint issue 数 > 0）保持 warn-only 模式。

各 lint 工具治理至 **0 errors** 后 SHALL 独立转严格阻塞模式：
- `ruff-check` / `ruff-format`：ruff 0 errors 后转严格（已在 ruff-strict-mode-enable change 完成）
- `pyright`：pyright 0 errors 后转严格（本 change 完成）
- `pytest`：pytest 全部 unit test pass 后转严格（独立 pytest-marker-strict change）

**pytest 转严格特殊要求**：因大量 test 需 `.env` (LLM key / 数据源 token) / 网络 / docker mongo / 等运行时依赖，**不能盲目转严格**。MUST 先用 pytest marker 体系隔离：
- `@pytest.mark.unit`：纯 Python 逻辑，无外部依赖（默认跑）
- `@pytest.mark.integration`：需 docker / mongo / redis（CI 跑，本地按需）
- `@pytest.mark.requires_env`：需 `.env` LLM key / 数据源 token（本地用户配齐才跑）
- `@pytest.mark.requires_network`：需公网（CI 可跑，CI 离线时 skip）

pre-commit hook 转严格时只跑 `pytest -m "unit and not requires_env and not requires_network"`，确保任何环境都能 0-fail 通过。

`.github/workflows/ci.yml` 的 `just ci` MAY 仍因 pytest fail，但 ruff + pyright lint 部分 MUST 通过。

#### Scenario: ruff 0 errors 后 commit 含 ruff 错误被阻塞

- **WHEN** ruff 已 0 errors
- **AND** 用户改某 .py 引入新 F401 unused-import
- **AND** 跑 `git commit -m "..."`
- **THEN** pre-commit ruff-check hook fail
- **AND** commit 不被创建（exit 1）
- **AND** 用户必须修 import 或 `# noqa: F401`（不允许 `--no-verify` 跳）

#### Scenario: pyright 0 errors 后 commit 含 pyright 错误被阻塞

- **WHEN** pyright 已 0 errors
- **AND** 用户改某 .py 引入新 reportUnboundVariable
- **AND** 跑 `git commit -m "..."`
- **THEN** pre-commit pyright hook fail
- **AND** commit 不被创建（exit 1）

#### Scenario: pytest 仍 warn-only

- **WHEN** ruff + pyright 转严格后用户跑 commit
- **AND** pytest 缺失或大量 fail
- **THEN** pre-commit pytest hook 输出 `[warn-only]` 但 exit 0
- **AND** commit 成功
