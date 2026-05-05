# lint-policy Specification

## Purpose
TBD - created by archiving change lint-cleanup-baseline. Update Purpose after archive.
## Requirements
### Requirement: ruff 配置 — 中文项目友好放行

`pyproject.toml` `[tool.ruff.lint]` MUST 含以下 `ignore` 清单（中文全角字符在中文 codebase 是常态，非代码质量问题）：

```toml
ignore = ["RUF001", "RUF002", "RUF003"]
```

`pyproject.toml` `[tool.ruff]` `line-length` MUST 设为 `140`（不是 100）—— 中文 docstring 1 行字符密度高于英文，标准 100 行长导致大量误报。

#### Scenario: ruff 不报中文全角字符

- **WHEN** `tradingagents/agents/` 某个 Python 文件含中文字符（变量名 / 字符串 / docstring / 注释）
- **AND** 跑 `uvx ruff check <file>`
- **THEN** 输出不含 RUF001 / RUF002 / RUF003 报错
- **AND** 中文字符（如`：` `，`）原样保留不需 `# noqa` 注释

#### Scenario: 中文 docstring 100-140 字符不报 E501

- **WHEN** 某 Python 函数 docstring 单行 120 中文字符
- **AND** 跑 ruff check
- **THEN** 不报 E501 line-too-long
- **AND** 仅当行长 > 140 时报 E501

### Requirement: lint 治理 — 按 rule code 分批 + 每 commit 验证

ruff 治理 MUST 按单一 rule code 分批 commit（一个 rule 一个 commit），不允许混合。每个 commit 后 MUST 验证：

1. `vue-tsc --noEmit` 通过（不引入 TypeScript 类型错误—— 仅适用前端）
2. `.venv/bin/python -c "import tradingagents"` 不报错（核心包仍可 import）
3. backend 启动：`.venv/bin/uvicorn app.main:app --port 54301` + curl `/api/health` HTTP 200

任一验证失败 MUST 立即 `git revert` 该 commit + 在 OpenSpec 后续 change 单独处理。

#### Scenario: F401 ruff --fix 后 backend 仍能启动

- **WHEN** 跑 `uvx ruff check --fix --select F401 tradingagents/`
- **AND** ruff 修改若干 .py 文件删 unused import
- **AND** 跑 backend 启动 + curl /api/health
- **THEN** HTTP 200 返回正常
- **AND** backend log 无 ImportError / ModuleNotFoundError

#### Scenario: 引入回归则 revert

- **WHEN** 某 ruff --fix commit 后 backend 启动失败（如 F401 删了实际有动态用法的 import）
- **THEN** 该 commit MUST `git revert` 而非追加 fix
- **AND** 在 follow-up change 加 `# noqa: F401` 标记保留 import 的合法理由

### Requirement: lint 治理过程保持 warn-only

`.pre-commit-config.yaml` MUST 在 lint 治理期间（lint issue 数 > 0）保持 warn-only 模式。

各 lint 工具治理至 **0 errors** 后 SHALL 独立转严格阻塞模式：
- `ruff-check` / `ruff-format`：ruff 0 errors 后转严格（已在 ruff-strict-mode-enable change 完成）
- `pyright`：pyright 0 errors 后转严格（已在 pyright-handfix-pass-2 change 完成）
- `pytest`：通过 marker 体系隔离后转严格（本 change 完成）

**pytest 转严格落地方案**：

`pyproject.toml [tool.pytest.ini_options]` MUST 注册 4 个 marker：
- `unit`：纯 Python 逻辑，无外部依赖
- `integration`：需 docker / mongo / redis
- `requires_env`：需 `.env` LLM key / 数据源 token
- `requires_network`：需公网

`tests/conftest.py` MUST 含 `pytest_collection_modifyitems` hook：未显式标记任何上述 4 个 marker 的 test 自动加 `requires_env`（保守默认——不知道 test 需要什么时假设需要 env）。

pre-commit `pytest` hook entry MUST 是 `uv run --no-sync pytest -m unit ...`——只跑显式标记 `unit` 的 test。任何环境都能 0-fail 通过（`unit` 标记的 test 不依赖外部）。

#### Scenario: pytest 转严格后 commit 无 unit test fail

- **WHEN** 用户跑 `git commit`
- **AND** pre-commit pytest hook 触发 `pytest -m unit`
- **AND** 现有 `unit` 标记的 test 全部 pass
- **THEN** commit 成功

#### Scenario: 未标记 marker 的 test 默认不在 hook 跑

- **WHEN** test 文件没显式 `@pytest.mark.unit/integration/requires_env/requires_network`
- **AND** conftest 的 `pytest_collection_modifyitems` 跑
- **THEN** 该 test 自动加 `requires_env`
- **AND** 不在 `pytest -m unit` 中被选中

#### Scenario: 用户手动跑全套仍可

- **WHEN** 用户跑 `.venv/bin/pytest`（无 `-m` filter）
- **THEN** 全部 644 tests 都被选中（含 unit + integration + requires_env + requires_network）
- **AND** 行为与转严格前一致

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

### Requirement: pytest collection 0 errors

`pytest --collect-only` SHALL 报告 0 collection errors。任何引用已重组/删除模块的 dead test MUST 删除（git history 恢复），任何 import-time 副作用（如连 mongo / 网络请求）必须移到 fixture 或 lazy 调用。

#### Scenario: pytest collection 完全干净

- **WHEN** `.venv/bin/python -m pytest --collect-only`
- **THEN** 输出 `N tests collected` 不含 `errors`
- **AND** 不报 INTERNALERROR
- **AND** exit code 0

### Requirement: 纯 mock / 纯函数 test 必须显式标 unit

任何**纯 Python 逻辑**测试文件（满足下列全部 4 条判据）SHALL 在文件顶部显式标 `pytestmark = pytest.mark.unit`：

- 不发起任何外部网络请求（HTTP / DNS / TCP）
- 不连接外部数据源（mongo / redis / mysql / 任何 docker service）
- 不读 LLM API key / Tushare token / 数据源 token 等需 `.env` 才有的 secret
- 不依赖 `app/`（FastAPI 后端）或 `frontend/` 实际启动

判据满足后，仅依赖 `unittest.mock.patch` / `monkeypatch` / `AsyncMock` / 内置数据结构 / numpy / pandas 纯计算的 test 必须标 `unit`。

判据不满足的（连网络 / 连数据库 / 读真实 secret）保持 conftest auto-mark 为 `requires_env` 不变。

#### Scenario: pre-commit pytest hook collect 数量

- **WHEN** 执行 `uv run --no-sync pytest -m unit --collect-only`
- **THEN** collect 数 MUST > 0（fork 启动时即立即标记 ≥ 10 个文件作为 baseline）
- **AND** pytest exit 0（全部 pass）

#### Scenario: 新加的纯 mock test 必须标 unit

- **WHEN** 开发者加新 test 文件
- **AND** 该文件满足 4 条 unit 判据
- **THEN** 该文件 MUST 在顶部加 `pytestmark = pytest.mark.unit`
- **AND** 不依赖 conftest auto-mark

