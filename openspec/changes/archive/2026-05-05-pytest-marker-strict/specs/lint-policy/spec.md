## MODIFIED Requirements

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
