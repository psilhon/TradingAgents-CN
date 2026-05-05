## ADDED Requirements

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

治理期间 `.pre-commit-config.yaml` MUST 保持 warn-only 模式（不阻塞 commit），避免治理过程中频繁打断日常开发。

`.github/workflows/ci.yml` 的 `just ci` MAY 仍 fail（CI red 是预期），转严格模式是另一独立 change（如 `lint-strict-mode-enable`）。

#### Scenario: 治理过程中正常 commit 不被阻塞

- **WHEN** 用户在治理期间做某个非 lint 相关的 commit（如新功能 / bug fix）
- **AND** 项目 ruff issues 仍 > 0
- **THEN** pre-commit hook 输出 `[warn-only] ruff check found issues — fix later` 但 commit 成功
- **AND** exit code 0
