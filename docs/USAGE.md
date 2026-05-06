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

# 8) 启 docker db + 创建初始 admin 用户
docker compose up -d mongodb redis
sleep 30   # 等 mongo healthy

# 上游 scripts/create_default_admin.py hardcode 27017，临时 patch 到 54302
sed -i.orig 's/localhost:27017/localhost:54302/g' scripts/create_default_admin.py
.venv/bin/python scripts/create_default_admin.py     # 创建 admin/admin123
mv scripts/create_default_admin.py.orig scripts/create_default_admin.py   # 还原
```

## 2. 日常开发命令

```bash
# CI（本地 + GitHub Actions 同源）
just ci         # lint + typecheck + test
just lint       # 仅 ruff
just typecheck  # 仅 pyright
just test       # 仅 pytest
just fix        # 自动修复 ruff lint/format

# 🚀 全栈启停（推荐）—— scripts/dev.sh 管理 docker + backend + frontend
just up               # 起全栈（docker mongo+redis + backend uvicorn + frontend vite）
just down             # 停全栈（含 docker，0 残留进程/端口/PID 文件）
just status           # 端口 + 进程 + docker 状态一览
just logs             # tail backend log（Ctrl-C 退出）
just logs-frontend    # tail frontend log
just dev-restart      # 重启全栈

# 手动启停（细粒度调试，多数场景用上面的 just）
docker compose up -d mongodb redis     # 仅起 db
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 54301 --reload
cd frontend && npm run dev -- --port 54300   # vite dev 强制走端口段位 54300（与 docker frontend 互斥）

# CLI demo
.venv/bin/python main.py
```

**dev.sh 行为细节**：

- 状态文件存 `.dev/{backend,frontend}.{pid,log}`（已 gitignored）
- start 幂等：检测端口占用 / 已运行进程 → skip，不强抢
- stop 用 `pkill -P` 杀 vite/uvicorn 子进程（避免 npm wrapper 死后留 vite 孤儿）+ 1.5s 优雅退出窗口
- backend boot 慢（~5-15s 连 mongo + 装 scheduler），`status` 立即查可能显示端口未监听属正常
- 与 docker frontend 容器互斥（同 :54300）—— 本脚本只跑 vite dev 模式

## 3. 二次开发流程（OpenSpec + Phase 1/2/3）

按全局 `~/.claude/CLAUDE.md` 的三阶段流程：

| 阶段 | 动作 |
|---|---|
| **Phase 0**（已完成）| 立项基础设施（CLAUDE.md / docs / openspec / CI） |
| **Phase 1 立项** | 用 `/opsx:propose "需求"` 起草 OpenSpec change，过 9 项 cross-check |
| **Phase 2 执行** | subagent 自驱实现，主代理监控 A/B 类阻塞 |
| **Phase 3 收口** | `superpowers:finishing-a-development-branch` 出报告，本地 commit + tag，你 1 click push |

主开发战场：`tradingagents/`（Apache 2.0）。`app/` 和 `frontend/` 是上游专有授权，仅本机学习目的可改。

## 4. Fork 状态：独立分叉

本 fork 不再定期 sync 上游 `hsliuping/TradingAgents-CN`。需要上游某项功能 / 修复时手动 cherry-pick：

```bash
# 添加 upstream remote 仅作 cherry-pick 临时用
git remote add upstream https://github.com/hsliuping/TradingAgents-CN.git
git fetch upstream
git log upstream/main -- <path>                   # 看上游某文件历史
git cherry-pick <commit-hash>                     # 单独引入特定 commit
git remote remove upstream                        # 用完即删，避免误 merge
```

**不要** `git merge upstream/main` 或 `git pull upstream main`——这会引入大量本 fork 已删的内容（Windows 脚本 / 学习中心 / streamlit 等），违反 `repository-scope` spec。

注：上游遗留的 `.github/workflows/upstream-sync-check.yml` 仍跑（提示上游新 commit 数），仅供参考，不应触发同步行动。

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
