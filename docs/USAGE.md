# TradingAgents-CN (fork) — 二次开发使用手册

> 上游 `README.md` 是产品介绍（面向最终用户）；本文档是 **fork 维护者 + 二次开发者**的使用手册（面向开发者）。

## 1. 一次性环境搭建（新机器 / 新接手）

```bash
# 1) clone（项目根直接是 git repo，无嵌套）
git clone git@github.com:psilhon/TradingAgents-CN.git
cd TradingAgents-CN

# 2) 配 upstream remote（fork 同步用）
git remote add upstream https://github.com/hsliuping/TradingAgents-CN.git

# 3) 建 venv（homebrew python@3.12，arm64）
brew install python@3.12 || true   # 已装则跳过
uv venv --python /opt/homebrew/opt/python@3.12/bin/python3.12 \
        --python-preference only-system

# 4) 装依赖（注意：必须分两步，uv.lock 已知过时）
uv sync --frozen --python .venv/bin/python --python-preference only-system
uv pip install -e . --python .venv/bin/python
git status   # ⚠️ uv pip install -e . 会误删 VERSION/requirements*.txt
git checkout HEAD -- VERSION requirements.txt requirements-lock.txt 2>/dev/null

# 5) 装 CI 工具链
brew install just
uv tool install pyright ruff
just setup   # 装 pre-commit hook（warn-only 模式，不阻塞）

# 6) 配 .env（必填 JWT_SECRET / CSRF_SECRET / 1 个 LLM key）
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"  # 生成 secret
# 编辑 .env，填 3 处必填项

# 7) 重建本地端口映射（不在 git 里）
# 端口段位 54300-54309，详见 CLAUDE.md
# 内容参考 docker-compose.override.yml 的 git history（如已 commit），或手抄 CLAUDE.md「端口分配」段
```

## 2. 日常开发命令

```bash
# CI（本地 + GitHub Actions 同源）
just ci         # lint + typecheck + test
just lint       # 仅 ruff
just typecheck  # 仅 pyright
just test       # 仅 pytest
just fix        # 自动修复 ruff lint/format

# 服务（端口 54300-54309，见 CLAUDE.md）
docker compose up -d mongodb redis     # 仅起 db，本地跑 backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 54301 --reload
cd frontend && npm run dev -- --port 54300   # vite dev 强制走端口段位 54300（与 docker frontend 互斥）

# CLI demo
.venv/bin/python main.py
```

## 3. 二次开发流程（OpenSpec + Phase 1/2/3）

按全局 `~/.claude/CLAUDE.md` 的三阶段流程：

| 阶段 | 动作 |
|---|---|
| **Phase 0**（已完成）| 立项基础设施（CLAUDE.md / docs / openspec / CI） |
| **Phase 1 立项** | 用 `/opsx:propose "需求"` 起草 OpenSpec change，过 9 项 cross-check |
| **Phase 2 执行** | subagent 自驱实现，主代理监控 A/B 类阻塞 |
| **Phase 3 收口** | `superpowers:finishing-a-development-branch` 出报告，本地 commit + tag，你 1 click push |

主开发战场：`tradingagents/`（Apache 2.0）。`app/` 和 `frontend/` 是上游专有授权，仅本机学习目的可改。

## 4. 上游同步流程

```bash
git fetch upstream
git log --oneline HEAD..upstream/main  # 看新增改动
git merge upstream/main                 # 或 rebase
# 冲突大概率发生在 pyproject.toml / .gitignore；CLAUDE.md / docs/ 等 fork 新文件不冲突
```

`.github/workflows/upstream-sync-check.yml` 已上游自带，会定期检查上游新 commit 数。

## 5. 常见坑（同步自 `CLAUDE.md` 已知坑段）

- 🔴 `uv pip install -e .` 删 tracked 文件 → 装完立即 `git status` 检查
- 🟡 `.chainlit/` import 时自动生成，未 .gitignore（建议本地加到 `.git/info/exclude`）
- ❌ `web/` streamlit 旧 UI 不可启动（chainlit/starlette 冲突）
- ❌ `uv sync` 不带 `--frozen` 会因 qianfan extras 在 3.13 无 wheel 而失败
- ❌ `uv pip install` 不带 `--python .venv/bin/python` 会试图装到系统 homebrew Python，PEP 668 拒绝

更多坑见 `CLAUDE.md` 末尾「已知坑」段。

## 6. 文档地图

| 找... | 看... |
|---|---|
| 项目概览（产品介绍）| `README.md`（上游）|
| AI prime context | `docs/ai-context/{project-structure,coding-standards,architecture}.md` |
| 改动历史（fork 自己的）| `docs/CHANGELOG.md` |
| OpenSpec specs / changes | `openspec/specs/`、`openspec/changes/` |
| 上游详细文档 | `docs/QUICK_START.md`、`docs/STRUCTURE.md`、`docs/architecture/`、`docs/database_setup.md` 等 |
| 端口约定 / 命令速查 / Secrets | `CLAUDE.md` |
