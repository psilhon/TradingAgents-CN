## Why

ruff 已治理至 0 errors（4 个 lint changes 累计 53 commit），现在可以**只转 ruff 严格阻塞**——任何新引入的 ruff issue 立即 block commit / push / CI。

**不能全转**（lint + typecheck + test 一起）因：
- pyright: **9,955 errors** + 32 warnings（unknown type 居多，治理工程量极大）
- pytest: `.venv` 里没装（pyproject.toml 漏 dev dep；`uv run pytest` 失败）

转严格前后对比：

| 触发 | 治理前（warn-only）| 治理后（ruff 严格）|
|---|---|---|
| `git commit` 含 ruff issue | echo `[warn-only]` 通过 | exit 1 阻塞 |
| `git push` （pre-push）| 同上（pytest hook 仍 warn-only） | ruff 已通；pytest/pyright 仍 warn-only |
| GitHub Actions CI | `just ci` 跑完 ruff lint exit 1 → 整体 fail | 同左，但 ruff 不再有 fail|

## What Changes

- **MODIFIED** `.pre-commit-config.yaml`：
  - `ruff-check` hook：去掉 bash wrapper，恢复直接 `uv run ruff check`（fail 阻塞）
  - `ruff-format` hook：同上
  - `pyright` hook：**保留** warn-only（9955 errors 没治理）
  - `pytest` hook：**保留** warn-only（pytest 没装 + 大量 test 需 .env / 网络）
- **MODIFIED** `.pre-commit-config.yaml` 顶部注释：从"WARN-ONLY MODE"改为"分阶段严格"——ruff 严格 / pyright + pytest warn-only

无 BREAKING change（用户层面无变化；仅 commit 时 ruff 报错会阻塞——但目前 ruff 0 errors，不会触发）。

## Capabilities

### Modified Capabilities

- `lint-policy`：MODIFY「lint 治理过程保持 warn-only」Requirement 加"ruff 完成 0 errors 后转严格"+"分模块严格（ruff vs pyright vs pytest）独立"

## Impact

**改动文件**：`.pre-commit-config.yaml`（2 个 hook entry + 顶部注释）

**风险**：
- ⚠️ 用户首次 `just setup` 装 pre-commit hook 后（之前没装），所有 commit 都跑 ruff。引入新 ruff 错误立即 block——此时正确反应是修代码而非 `--no-verify` 跳 hook（HARD-GATE 禁）
- ⚠️ 严格模式后 commit 速度略降（ruff 跑 .py 文件 < 1s，无大影响）

**收益**：
- ruff 不再退化（任何回归立即 block）
- 后续 OpenSpec changes 添加新代码时强制符合 fork lint policy
- 为 pyright-cleanup / pytest-baseline 后续 changes 铺路（每个完成可独立转严格）
