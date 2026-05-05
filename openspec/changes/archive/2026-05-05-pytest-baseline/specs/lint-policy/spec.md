## MODIFIED Requirements

### Requirement: lint 治理过程保持 warn-only

`.pre-commit-config.yaml` MUST 在 lint 治理期间（ruff issue 数 > 0）保持 warn-only 模式（不阻塞 commit）。

ruff issues 治理至 **0 errors** 后 SHALL 转严格阻塞模式：
- `ruff-check` / `ruff-format` hook 必须直接调用（不经 bash exit-zero wrapper）
- 任何新引入的 ruff issue 立即 block commit（exit 1）

pyright / pytest 等其它 hook **独立**决定何时转严格——按 capability 分阶段（先 ruff，再 pyright，最后 pytest），各自达 0 errors 后单独转。

**pytest 转严格特殊要求**：因大量 test 需 `.env` (LLM key / 数据源 token) / 网络 / docker mongo / 等运行时依赖，**不能盲目转严格**。MUST 先用 pytest marker 体系隔离：
- `@pytest.mark.unit`：纯 Python 逻辑，无外部依赖（默认跑）
- `@pytest.mark.integration`：需 docker / mongo / redis（CI 跑，本地按需）
- `@pytest.mark.requires_env`：需 `.env` LLM key / 数据源 token（本地用户配齐才跑）
- `@pytest.mark.requires_network`：需公网（CI 可跑，CI 离线时 skip）

pre-commit hook 转严格时只跑 `pytest -m "unit and not requires_env and not requires_network"`，确保任何环境都能 0-fail 通过。

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

#### Scenario: pytest collection 不再 INTERNALERROR

- **WHEN** `.venv/bin/python -m pytest --collect-only`
- **THEN** 不报 INTERNALERROR（pytest 可完成 collection 流程）
- **AND** 不含 `from web.*` 等已删模块导致的 sys.exit(1) 退出
- **AND** 残余 collection errors 是各 test 文件 import-time 失败（pymongo 超时 / 缺 module 等），可被 follow-up change `pytest-collection-fix` 单独治理

#### Scenario: pytest 装到 pyproject dev extras

- **WHEN** 新机器 clone 后跑 `uv sync --extra dev`
- **THEN** pytest + pytest-asyncio 自动安装到 `.venv`
- **AND** `.venv/bin/python -m pytest --version` 正常返回
