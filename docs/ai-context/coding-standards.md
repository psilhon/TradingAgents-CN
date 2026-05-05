# coding-standards.md

> AI prime context — 项目特有规范。**不重复**全局 `~/.claude/CLAUDE.md`。

## Python lint / format / typecheck

| 工具 | 配置 | 备注 |
|---|---|---|
| `ruff` 0.15.x | `pyproject.toml [tool.ruff]` | `target-version = "py310"`（匹配 `requires-python>=3.10`），line-length 100 |
| `pyright` 1.1.x | `pyproject.toml [tool.pyright]` | `include = ["tradingagents", "tests"]`；strict 仅 `tradingagents` |
| `pytest` 8.x | `pyproject.toml [tool.pytest.ini_options]` | 已 ignore `tests/0.1.14/`（旧版本快照） |

## 排除目录（lint / typecheck 都不扫）

```
app/         # 专有授权代码，不二改
frontend/    # JS/TS 栈，归 npm run lint
web/         # 已废弃 streamlit
scripts/     # 上游一次性脚本
examples/    # 示例
.venv/       # 虚拟环境
.chainlit/   # chainlit import 副作用产物
```

## pre-commit hook：⚠️ WARN-ONLY 模式

**接手时所有 hook 用 bash wrapper 强制 exit 0**——上游代码无 ruff 治理，存量 warning 数量未知，强制阻塞会让所有 commit 卡住。

要切回阻塞模式：`.pre-commit-config.yaml` 顶部注释有完整说明（每个 entry 把 `bash -c '... || echo "[warn] ..."' --` 改回原始命令）。建议时机：完成首轮 ruff cleanup 后。

## CI 流水线 (`just ci`)

本地 hook + `.github/workflows/ci.yml` 调同一组命令：

```
just ci  =  just lint && just typecheck && just test
         =  ruff check . + ruff format --check . + pyright + pytest
```

CI 用 `uv sync --frozen` + `uv pip install -e .`（**不用 `--locked`**，因为 uv.lock 过时）。

## Python 版本约定

| 场景 | 版本 | 来源 |
|---|---|---|
| 本地 venv | 3.12.13 | homebrew `python@3.12`（arm64）|
| 上游 Docker | 3.10 | `Dockerfile.backend` 用 `python:3.10-slim` |
| 真实最低 | 3.10 | `pyproject.toml requires-python` |
| `.python-version` | 3.10 | 上游锁，**不修改**（用 `UV_PYTHON` / `--python` 覆盖）|

## Commit message 风格

跟上游：`feat: / fix: / chore: / refactor: / docs:` 前缀 + 中英文 body。范例 `git log --oneline | head` 学。

## 二次开发原则

1. **改 `tradingagents/`** 是常规
2. **改 `app/` 或 `frontend/`** 需明确声明动机；商业部署要取得作者授权
3. **改 tracked 上游文件**（pyproject.toml / .gitignore / docker-compose.yml）会增加上游 sync 冲突；**优先用 `docker-compose.override.yml` / `pyproject.toml` 末尾追加 / `.git/info/exclude` 等本地化机制**
4. **不动 `.python-version`**（上游锁），用环境变量覆盖
5. **不动 `uv.lock`**（已知过时），用 `--frozen` + `uv pip install -e .`

## Binding / Port 配置层次表

> 沉淀自 OpenSpec change `binding-audit-tooling`：Phase 0 撞墙 4 次教训——binding/port 信息散在 6 层，每次只看一层导致"修一处冒一处"。

**覆盖优先级（高 → 低）**：

| # | 层 | 示例 | 影响范围 | 改完必跑 |
|---|---|---|---|---|
| 1 | **CLI args** | `uvicorn --host 127.0.0.1 --port 54301`<br>`vite --port 54300` | 临时单次启动覆盖；最高优先级；不入版本 | `just audit-ports`（看实际 listen） |
| 2 | **环境变量** | `UV_PYTHON=...`<br>`UV_PYTHON_PREFERENCE=only-system`<br>`HOMEBREW_NO_AUTO_UPDATE=1` | shell 级覆盖；CI / 文档命令；不入版本 | — |
| 3 | **`.env`** | `API_PORT=54301`<br>`MONGODB_PORT=54302`<br>`API_HOST=127.0.0.1` | 本机运行时配置；gitignored；后端 pydantic-settings 读 | 重启 backend 验证 + `just audit-ports` |
| 4 | **fork-local patched 配置** | `frontend/vite.config.ts`（host/port/proxy）<br>`pyproject.toml [tool.*]`<br>`.pre-commit-config.yaml` | 全 fork 一致；commit 入版本；与上游同步可能冲突 | `just audit-binds` + type-check + 重启相关服务 |
| 5 | **`docker-compose.override.yml`** | `127.0.0.1:54302:27017` | 本机 docker 端口映射；`.git/info/exclude` 本地独有；compose 自动 merge | `docker compose up` 后 `just audit-ports` |
| 6 | **上游 tracked 代码 hardcode**（最低） | `app/services/config_service.py:491` `port=27017` fallback<br>`scripts/create_default_admin.py` `localhost:27017`<br>`docker-compose.yml` 默认 ports | 上游默认值；fork 通过上面 5 层之一覆盖；不直接改（除非在 OpenSpec change 范围）| 改 fork-local 配置后必跑 `just audit-binds` 确认覆盖生效 |

**关键原则**：

- **改高层覆盖低层** — 用 layer 1-3 (CLI / env / .env) 优先，layer 4 (fork patch) 必要时才改，layer 5/6 (override / 上游 hardcode) 最后手段
- **任何 binding 改动必跑 `just audit-ports`** — 看实际 listen 状态而不是只看 log
- **任何 fork-local 配置改动必跑 `just audit-binds`** — 防 hardcode 残留违规
- **新加 hardcode 端口数字到 fork-local 配置 → 检讨是否该走 .env 覆盖** — hardcode 是技术债

**对照 CLAUDE.md「Fork patch 清单」**：列出 layer 4 / 5 已 patched 字段全集，新加改动前先看清单。

## 测试约定

- `tests/` 含 pytest 测试 + 一些 debug 脚本（`debug_*.py` / `fast_tdx_test.py`）
- `tests/conftest.py` 把项目根加进 `sys.path`，所以测试可直接 `import tradingagents`
- `tests/0.1.14/` 是历史版本快照，pytest 已 ignore
- 部分测试需要 `.env` 里的 LLM / Tushare key
