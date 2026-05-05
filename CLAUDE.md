# TradingAgents-CN — Claude Code 项目级配置

> 本项目是 fork 自 [hsliuping/TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN) 的下游副本（`psilhon/TradingAgents-CN`）。本文件只写**本项目特有**的事实——通用规则见 `~/.claude/CLAUDE.md`。

## 项目身份

- **定位**：面向中文用户的多智能体股票分析学习平台（FastAPI 后端 + Vue 3 前端 + LangGraph 多智能体 + 多数据源）
- **上游版本**：`v1.0.1`（`pyproject.toml` 标 `1.0.0-preview`，未对齐）
- **当前阶段**：**Phase 0 完成** — 立项基础设施已就位（venv + CLAUDE.md + `docs/ai-context/` + `docs/{CHANGELOG,USAGE}.md` + OpenSpec + init-ci Recipe B）；下一动作 = Phase 1 立项第一个 OpenSpec change
- **技术栈**：Python 3.12（homebrew arm64）+ uv + FastAPI + Uvicorn + Vue 3 + Vite + MongoDB 4.4 + Redis 7 + Docker Compose
- **License 双轨**：根目录 Apache 2.0；`app/`（FastAPI 后端）和 `frontend/`（Vue 前端）为**专有授权**，商业用途必须联系作者 hsliup@163.com

## 命令速查

```
# 数据库（本地开发只起 mongo+redis，不在 docker 跑 backend）
docker compose up -d mongodb redis
docker compose down

# 后端（本地 venv 跑，连 docker 起的 db；端口 54301 见「端口分配」段）
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 54301 --reload

# 前端（独立终端）
cd frontend && npm install && npm run dev    # vite dev 默认 5173，临时不归端口段

# CLI 多智能体演示（需要 .env 里至少 1 个 LLM key）
.venv/bin/python main.py

# 测试（conftest.py 已把项目根加进 sys.path）
.venv/bin/pytest tests/                       # 全跑（部分用例需 .env 里的 LLM/Tushare key）
.venv/bin/pytest tests/integration/           # 仅集成测试
.venv/bin/pytest tests/test_xxx.py -v         # 单文件

# 重建 venv（依赖装漂了用）
rm -rf .venv
uv venv --python /opt/homebrew/opt/python@3.12/bin/python3.12 --python-preference only-system
uv sync --frozen --python .venv/bin/python --python-preference only-system
uv pip install -e . --python .venv/bin/python
```

**3 个 docker-compose 变体**（按场景选）：

| 文件 | 用途 | 后端镜像 |
|------|------|------|
| `docker-compose.yml` | 本地 dev / 改代码后 build | 本地 build `tradingagents-backend:v1.0.0-preview` |
| `docker-compose.hub.nginx.yml` | prod-like / amd64 Linux | 作者发布的 `hsliup/tradingagents-backend:v1.0.1` + Nginx 反代 |
| `docker-compose.hub.nginx.arm.yml` | 同上 / Apple Silicon | 同上，arm64 镜像 |

可选管理 UI：`docker compose --profile management up -d`（redis-commander :8081 / mongo-express :8082）

**Fork 上游同步**（首次：配 upstream remote；之后：定期合）：

```
git remote add upstream https://github.com/hsliuping/TradingAgents-CN.git    # 仅首次
git fetch upstream
git merge upstream/main                       # 或 rebase；本地 CLAUDE.md / .env 是 untracked / gitignored，不会冲突
```

**CI 同源命令**（本地 + pre-commit + GitHub Actions 都跑同一组）：

```
just ci          # 完整流水线 (lint + typecheck + test)
just lint        # 仅 ruff check + format check
just typecheck   # 仅 pyright
just test        # 仅 pytest
just fix         # 自动修复 ruff lint/format
just setup       # 装 pre-commit hook（首次 setup）
```

## 项目特殊约定（永恒事实）

每条覆盖所有 session；与全局软规则冲突时本节优先；HARD-GATE 不可覆盖。

- **Python 版本偏离**：本地用 homebrew **3.12**，与 `.python-version=3.10`（上游锁）和 `Dockerfile.backend` 的 `python:3.10-slim` 不一致。`pyproject.toml` 写 `>=3.10` 形式上接受。**不修改 `.python-version`**（避免上游同步冲突），用环境变量 `UV_PYTHON` 或显式 `--python` 覆盖。
- **uv.lock 已过时，禁止 `uv sync` 直接重解析**：lock 锁的是旧版 `tradingagents 0.1.0`（25 个直接依赖），现 pyproject 是 1.0.0-preview（70+ 直接依赖含 motor/streamlit/fastapi/uvicorn 等）。直接 `uv sync` 会触发 universal resolution，因 `qianfan>=0.4.20` 在 Python 3.13 不可用而失败。**正确流程**：`uv sync --frozen` + `uv pip install -e .`（见命令速查）。
- **`requirements.txt` 已废弃**：作者明确标注（首行注释），用 `pyproject.toml` 走 uv。
- **Streamlit 旧 UI 不可用**：`web/` 目录下的 25 个 streamlit 文件无法启动——`streamlit 1.57` 与 `chainlit` 锁的旧 `starlette 0.41` 冲突。**主路径走 FastAPI(`app/`) + Vue(`frontend/`)**，不要试图修 `web/`。
- **chainlit 在 pyproject 但代码 0 引用**：疑似上游残留依赖。它锁死 starlette 旧版导致上一条问题。要修必须先卸 chainlit（涉及改 pyproject，超出常规范围，请先确认）。
- **`app/` 和 `frontend/` 是专有授权代码**：可读、可本地改、可个人学习，但商业部署必须取得作者授权。任何"清理 / 重构 / 顺手改"的范围**默认排除这两个目录**，除非用户明确指示。
- **数据库连接默认值**与 `docker-compose.yml` 完全对齐：`admin / tradingagents123`，host=localhost，port=27017/6379。**这是上游公开的本地 dev 默认密码**（写在 docker-compose.yml 里），不是用户 secret，可在响应里直接引用。
- **commit message 风格**：跟上游保持中英混合（`feat:` / `fix:` / `chore:` 前缀 + 中英文 body），看 `git log --oneline` 学。
- **Python 包用 flat layout**（`tradingagents/` 而非 `src/tradingagents/`）—— `pyproject.toml [tool.setuptools.packages.find]` 已配 `include = ["tradingagents*"]`。`project-audit` 报 `src/` 缺失为**已知误报**，不要建 `src/`。
- **`pre-commit` hook 处于 WARN-ONLY 模式**：所有 hook 用 bash wrapper 强制 exit 0，commit / push 永不被阻塞但 warning 会输出。要切回阻塞：见 `.pre-commit-config.yaml` 顶部注释。

## 端口分配（项目级永恒约定）

**对外服务端口段位：54300–54309**（10 个，顺序分配，下表外的端口禁止占用）。

| 端口 | 服务 | 容器内端口 |
|------|------|------|
| 54300 | frontend | 80 |
| 54301 | backend (FastAPI / uvicorn) | 8000 |
| 54302 | mongodb | 27017 |
| 54303 | redis | 6379 |
| 54304 | redis-commander | 8081 |
| 54305 | mongo-express | 8081 |
| 54306–54309 | 预留 | — |

**落地方式**：根目录 `docker-compose.override.yml`（已加入 `.git/info/exclude`，本地独有，不污染 fork）会被 `docker compose` 自动 merge 进 `docker-compose.yml`，覆盖端口映射 + 同步 `CORS_ORIGINS`。换机器需重建该文件——内容见本仓库历史或 CLAUDE.md 端口表。

**例外**：vite dev server 默认 `5173` 是临时本地开发端口，**不**纳入本段约定；前端进 docker 后必须走 54300。

## AI 上下文入口

新会话 prime 优先级：

1. `docs/ai-context/project-structure.md` — 顶层目录 + 入口文件清单
2. `docs/ai-context/coding-standards.md` — 项目特有 lint/typecheck/排除约定 + 二开原则
3. `docs/ai-context/architecture.md` — 三层架构 + 多智能体编排 + 数据源链 + LLM 抽象
4. `docs/USAGE.md` — fork 维护者 / 二开者使用手册（区别于上游 README）
5. `docs/CHANGELOG.md` — fork 自身改动历史（不含上游 commits）
6. 上游详细文档：`README.md` / `docs/QUICK_START.md` / `docs/STRUCTURE.md` / `docs/architecture/`

## OpenSpec 状态

- 进行中的 change：`openspec/changes/<id>/`
- 稳定 spec：`openspec/specs/<capability>/`
- 探索：`openspec/explorations/<topic>/`
- 二开流程：`/opsx:propose "需求"` 起草 change → 主代理 cross-check → Phase 2 subagent 实施 → Phase 3 finishing

## Secrets / 凭据清单

`.env`（已被 `.gitignore` 第 20 行忽略，安全）。**必填**：

| Key | 用途 | 来源 |
|-----|------|------|
| `JWT_SECRET` | 用户认证 token 签名 | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `CSRF_SECRET` | CSRF 防护 | 同上，再生成一次 |
| 任意 1 个 LLM key | 模型调用 | `DEEPSEEK_API_KEY` / `DASHSCOPE_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` 任选 |

**推荐填**（缺了功能受限但能启动）：

| Key | 用途 | 获取 |
|-----|------|------|
| `TUSHARE_TOKEN` | A 股完整数据 | https://tushare.pro 注册免费层 |
| `FINNHUB_API_KEY` | 美股新闻 | https://finnhub.io 免费层 |

数据库连接**不需要改**（默认 localhost + dev 密码已对齐 docker-compose）。

## 已知坑（一次性记录，避免每次 session 重新踩）

- 🔴 **`uv pip install -e .` 会误删 tracked 文件 `VERSION` / `requirements.txt` / `requirements-lock.txt`**——本会话已实测复现。原因不明（无 `setup.py` / `MANIFEST.in`，文件也不在 `.gitignore`），疑似 setuptools editable build 或 uv 0.11 editable 实现的副作用。**装完立即跑 `git status`**；若有删除，立即 `git checkout HEAD -- VERSION requirements.txt requirements-lock.txt` 恢复。
- 🟡 **`.chainlit/` 在 import chainlit 时自动生成**且未在 `.gitignore` 中，会污染 `git status`。可加到 `.gitignore` 或在 git 操作前手动忽略。
- 重装依赖时如果跑 `uv sync`（不带 `--frozen`），会因 `qianfan` extra 在 3.13 无可用 wheel 而失败——必须 `--frozen` 跳过解析
- `uv pip install` 必须带 `--python .venv/bin/python`，否则 uv 会试图装到系统 homebrew Python，PEP 668 拒绝
- Docker Desktop 必须先手动启动（GUI 操作，Claude 不能代替）
- `app/` 和 `frontend/` 改动属于专有授权代码，commit / push 前确认目的合规
