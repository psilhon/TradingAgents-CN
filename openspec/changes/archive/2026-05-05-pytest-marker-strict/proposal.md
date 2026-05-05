## Why

ruff + pyright 都已 0 errors + 转 STRICT。pytest 是最后一个 warn-only hook。644 tests collected 但**绝大多数需 `.env` (LLM key / Tushare token) / 网络 / docker mongo / redis**——盲目转严格会让任何环境都 fail。

按之前 spec 设计的 marker 体系：`unit` (纯 Python) / `integration` (docker) / `requires_env` (env keys) / `requires_network` (公网)。pre-commit hook 只跑 `pytest -m unit`——0 fail 是任何环境基线。

## What Changes

- **MODIFIED** `pyproject.toml [tool.pytest.ini_options]`：加 `markers` 列表注册 4 个 marker
- **MODIFIED** `tests/conftest.py`：加 `pytest_collection_modifyitems` hook，给**未显式标记**的 test 自动加 `requires_env`（保守默认）
- **MODIFIED** `.pre-commit-config.yaml` pytest hook：去 warn-only wrapper，entry 改 `uv run --no-sync pytest -m unit -p no:cacheprovider`
- **添加 `@pytest.mark.unit`** 到几个公认的 unit test 文件作为 baseline（让 hook 至少跑几个 0-fail unit test）

## Capabilities

### Modified Capabilities

- `lint-policy`：MODIFY「lint 治理过程保持 warn-only」加"pytest 通过 marker 隔离 + 转严格只跑 unit"细节落地

## Impact

- pre-commit pytest hook 转 STRICT（跑 unit marker test）
- 默认所有未标记 test 不在 pre-commit 跑（被 auto-mark `requires_env`）
- 后续给真正的 unit test 加 `@pytest.mark.unit` 逐步扩展 hook 严格 cov
- 不影响 `pytest` 直接跑全套（用户手动跑 `.venv/bin/pytest` 仍跑全部 644）
