# TradingAgents-CN — Claude Code 项目级配置

> 本项目是 fork 自 [hsliuping/TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN) 的下游副本（`psilhon/TradingAgents-CN`）。本文件只写**本项目特有**的事实——通用规则见 `~/.claude/CLAUDE.md`。

## 项目身份

- **定位**：面向中文用户的多智能体股票分析学习平台（FastAPI 后端 + Vue 3 前端 + LangGraph 多智能体 + 多数据源）
- **当前版本**：`v1.2.1`（fork patch release；`pyproject.toml` 已对齐；上游 `v1.0.1`）
- **当前阶段**：**v1.2.1 已发布**，`[Unreleased]` 累积大量 Dashboard 模拟账户专业化 + 项目铁律 capabilities，待下次 release 合到 v1.3.0。OpenSpec 累计 **33 条 changes archived**（v1.2.1 后新加 5 条 capability：`paper-realtime-quotes` / `trading-calendar` / `paper-account-snapshots` / `portfolio-fundamentals` + market overview/dashboard 重构系列）。Dashboard 模拟账户 panel 9 处 mock（5 Tier 3 + 4 Tier 4）已全部接入真实数据源（TWRR/Sharpe/回撤/月度收益 + Beta/VaR/加权 PE-PB），新账户首日显示「—」属预期。剩余 follow-up：第三梯队 4 条（cache 层 / app 反向 import / agent state / company resolver）+ 第四梯队 3 条 + Tier 4 扩展（多基准 / 蒙卡 VaR / 板块敞口 / 港股美股 calendar+snapshot）+ 4 处零散 TODO，按需排期，见 `docs/code-review-2026-05-05.md`。
- **技术栈**：Python 3.12（homebrew arm64）+ uv + FastAPI + Uvicorn + Vue 3 + Vite + **原生 MongoDB 7.0 + Redis 8**（Homebrew，不用 Docker）
- **License 双轨**：根目录 Apache 2.0；`app/`（FastAPI 后端）和 `frontend/`（Vue 前端）为**专有授权**，商业用途必须联系作者 hsliup@163.com

## 命令速查

```
# 🚀 全栈启停（推荐）—— scripts/dev.sh 管理 原生 mongo+redis + backend + frontend
just up                     # = scripts/dev.sh start  起全栈
just down                   # = scripts/dev.sh stop   停全栈（含原生服务，无残留）
just status                 # 端口/进程/服务状态
just logs                   # tail backend log（or just logs-frontend）
just dev-restart            # 重启全栈
scripts/dev.sh --help       # 完整参数

# 首次部署（一次性）—— 装 mongo+redis+mongosh，创建 mongo 用户
./scripts/setup-native.sh

# 手动启停（细粒度调试用——大多数场景用上面的 just）
./scripts/local-services.sh start         # 仅起原生 mongo + redis
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 54301 --reload
cd frontend && npm install && npm run dev -- --port 54300

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

**原生服务文件清单**：

| 文件 | 用途 | tracked |
|------|------|------|
| `config/mongod.conf` | MongoDB 7.0 配置（bind 127.0.0.1:54302, 项目本地 dbpath, auth=on）| ✅ |
| `config/redis.conf` | Redis 配置（bind 127.0.0.1:54303, AOF, maxmemory 64MB）| ✅ |
| `scripts/local-services.sh` | 原生服务编排（替代 docker compose）| ✅ |
| `scripts/setup-native.sh` | 首次部署一次性安装器 | ✅ |
| `data/mongodb/`、`data/redis/` | 数据目录（gitignored）| ❌ |

**Fork 状态：独立分叉（不再 sync upstream）**

本 fork 是 `hsliuping/TradingAgents-CN` 的独立分叉，**不再定期** `git pull upstream/main`。需要上游某项功能 / 修复时手动 cherry-pick 单独决策引入，不批量 merge。

不要在本仓库配置 `upstream` remote 或建议任何"定期同步"流程——这是项目级永恒约定（详见 `openspec/specs/repository-scope/spec.md`）。

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

- **Python 版本偏离**：本地用 homebrew **3.12**，与 `.python-version=3.10`（上游锁）不一致。`pyproject.toml` 写 `>=3.10` 形式上接受。**不修改 `.python-version`**（避免上游同步冲突），用环境变量 `UV_PYTHON` 或显式 `--python` 覆盖。
- **uv.lock 已过时，禁止 `uv sync` 直接重解析**：lock 锁的是旧版 `tradingagents 0.1.0`（25 个直接依赖），现 pyproject 是 v1.1.0（68 个直接依赖含 motor/fastapi/uvicorn 等，已删 streamlit/chainlit）。直接 `uv sync` 会触发 universal resolution，因 `qianfan>=0.4.20` 在 Python 3.13 不可用而失败。**正确流程**：`uv sync --frozen` + `uv pip install -e ".[dev]"`（见命令速查）。
- **`requirements.txt` 已废弃**：作者明确标注（首行注释），用 `pyproject.toml` 走 uv。
- **`app/` 和 `frontend/` 是专有授权代码**：可读、可本地改、可个人学习，但商业部署必须取得作者授权。任何"清理 / 重构 / 顺手改"的范围**默认排除这两个目录**，除非用户明确指示。
- **数据库连接默认值**（原生服务 + business code 均一致）：`admin / tradingagents123`，host=127.0.0.1，port=54302/54303。**这是公开的本地 dev 默认密码**，不是用户 secret，可在响应里直接引用。
- **commit message 风格**：跟上游保持中英混合（`feat:` / `fix:` / `chore:` 前缀 + 中英文 body），看 `git log --oneline` 学。
- **Python 包用 flat layout**（`tradingagents/` 而非 `src/tradingagents/`）—— `pyproject.toml [tool.setuptools.packages.find]` 已配 `include = ["tradingagents*"]`。`project-audit` 报 `src/` 缺失为**已知误报**，不要建 `src/`。
- **`pre-commit` hook 处于 STRICT 模式**：3 个 hook（ruff-check / ruff-format / pyright）pre-commit 阻塞，pytest -m unit 在 pre-push 阻塞。所有 hook 0 errors 才能 commit/push。详见 `openspec/specs/lint-policy/spec.md`。

## Fork patch 清单（哪些上游 tracked 文件可改 / 必须改 / 不动）

为对齐 fork 端口段位 / loopback / 工具链定制，下列上游文件**已被 patch 入版本**——不要回滚到上游原始内容：

| 文件 | 已 patched 字段 / 段 | 理由 |
|------|------|------|
| `frontend/vite.config.ts` | `server.host` / `server.port` / `server.strictPort` / `server.hmr.host` / `server.proxy['/api'].target` | 上游 hardcode `0.0.0.0:3000` + proxy `:8000`，违反端口段位 + loopback 规定 |
| `pyproject.toml` | `[tool.ruff]` / `[tool.pyright]` / `[tool.pytest.ini_options]` 段（追加在末尾） + dependencies 移除 streamlit/chainlit + version `1.1.0` | init-ci Recipe B 工具配置 + stable-v1-cleanup 删依赖 + v1.1.0 release |
| `.pre-commit-config.yaml` | STRICT 模式（ruff/format/pyright pre-commit 阻塞 + pytest -m unit pre-push 阻塞）+ uvx 工具调用 | lint 治理沉淀完成后转 STRICT |
| `.github/workflows/ci.yml` | `uv sync --frozen` + `uv pip install -e .`（不用 `--locked`） | uv.lock 与 pyproject 不同步已知坑 |
| `.gitignore` | 末尾追加 `.chainlit/` + `.claude/settings.local.json` | fork-local 自动产物 + 本地权限记录 |
| `docs/CHANGELOG.md` / `docs/USAGE.md` / `docs/ai-context/*.md` | 全部新建 + 维护 | Phase 0 prime context HARD-GATE |

**完全不动**（原则 — 改动属于"专有授权范围"或"业务逻辑"）：

- `app/` 后端业务代码（专有授权，仅本机学习目的可读）
- `frontend/src/` 业务代码（同上；vite.config.ts 是构建配置例外）
- `tradingagents/` Apache 2.0 主代码（除非在 OpenSpec change 范围内）
- `docs/architecture/` / `docs/api/` / `docs/configuration/` 等技术参考文档
- `tests/` 业务测试（除非新加 fork 自己的测试）

**改 fork-local 配置后必跑**：`just audit-binds` 验证未引入 hardcode 违规。

## 端口分配（项目级永恒约定）

**对外服务端口段位：54300–54309**（10 个，顺序分配，下表外的端口禁止占用）。

| 端口 | 服务 |
|------|------|
| 54300 | frontend (vite dev) |
| 54301 | backend (FastAPI / uvicorn) |
| 54302 | mongodb (native) |
| 54303 | redis (native) |
| 54304–54309 | 预留 |

**落地方式**：`config/mongod.conf` 和 `config/redis.conf` 显式绑定 `127.0.0.1:54302/54303`；uvicorn/vite 命令行强制 `--host 127.0.0.1 --port 5430X`。

**前端 vite dev 端口**：`npm run dev -- --port 54300`，**不修改 `frontend/vite.config.ts`**（专有授权代码），通过命令行 `--port` 参数强制覆盖默认 5173。

**🔒 所有对外服务强制绑定 `127.0.0.1`（loopback only）**：本项目为个人使用，不对外暴露。所有 host 配置 / 服务监听地址必须只接受 loopback 连接，禁止绑 `0.0.0.0`（含同局域网访问）。落地：
- uvicorn / vite dev 命令必须 `--host 127.0.0.1`
- `config/mongod.conf`：`bindIp: 127.0.0.1`
- `config/redis.conf`：`bind 127.0.0.1`
- `.env` 的 `API_HOST` / `HOST` 必须 `127.0.0.1`

## AI 上下文入口

新会话 prime 优先级：

1. `docs/ai-context/project-structure.md` — 顶层目录 + 入口文件清单
2. `docs/ai-context/coding-standards.md` — 项目特有 lint/typecheck/排除约定 + 二开原则
3. `docs/ai-context/architecture.md` — 三层架构 + 多智能体编排 + 数据源链 + LLM 抽象
4. `docs/USAGE.md` — fork 维护者 / 二开者使用手册（区别于上游 README）
5. `docs/CHANGELOG.md` — fork 自身改动历史（不含上游 commits）
6. `docs/ai-context/known-issues.md` — 已知坑（fork 撞过的 + 上游遗留），按需查
7. 上游详细文档：`README.md` / `docs/QUICK_START.md` / `docs/STRUCTURE.md` / `docs/architecture/`

## OpenSpec 状态

活跃 change `openspec/changes/<id>/` / 稳定 spec `openspec/specs/<capability>/` / 探索 `openspec/explorations/<topic>/`。二开流程：`/opsx:propose <name>` → cross-check → Phase 2 实施 → Phase 3 finishing。

## Secrets / 凭据

`.env` 已 gitignored。配置见 `docs/USAGE.md` § 1 step 6。**HARD-GATE**：Claude 不读/写/复制 secret 值，由你手动填。
