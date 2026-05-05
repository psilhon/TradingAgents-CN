## ADDED Requirements

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
