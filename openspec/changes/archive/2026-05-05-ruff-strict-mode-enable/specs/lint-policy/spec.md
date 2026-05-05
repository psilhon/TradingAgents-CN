## MODIFIED Requirements

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
