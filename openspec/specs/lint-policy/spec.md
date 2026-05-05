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

`.pre-commit-config.yaml` MUST 在 lint 治理期间（ruff issue 数 > 0）保持 warn-only 模式（不阻塞 commit）。

ruff issues 治理至 **0 errors** 后 SHALL 转严格阻塞模式：
- `ruff-check` / `ruff-format` hook 必须直接调用（不经 bash exit-zero wrapper）
- 任何新引入的 ruff issue 立即 block commit（exit 1）

pyright / pytest 等其它 hook **独立**决定何时转严格——按 capability 分阶段（先 ruff，再 pyright，最后 pytest），各自达 0 errors 后单独转。

`.github/workflows/ci.yml` 的 `just ci` MAY 仍因 pyright / pytest fail，但 ruff lint 部分 MUST 通过——CI 红的根因从"ruff 21k issues"变为"pyright 类型问题 / pytest 缺失"，更聚焦真问题。

#### Scenario: ruff 0 errors 后 commit 含 ruff 错误被阻塞

- **WHEN** ruff 已 0 errors
- **AND** 用户改某 .py 引入新 F401 unused-import
- **AND** 跑 `git commit -m "..."`
- **THEN** pre-commit ruff-check hook fail
- **AND** commit 不被创建（exit 1）
- **AND** 用户必须修 import 或 `# noqa: F401`（不允许 `--no-verify` 跳）

#### Scenario: pyright / pytest 仍 warn-only

- **WHEN** ruff 转严格后用户跑 commit
- **AND** pyright 报 9000+ errors / pytest 缺失
- **THEN** pre-commit pyright + pytest hook 输出 `[warn-only]` 但 exit 0
- **AND** commit 成功

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

