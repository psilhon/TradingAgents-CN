# CLAUDE.md

> **TradingAgents-CN** — fork 自 [hsliuping/TradingAgents-CN](https://github.com/hsliuping/TradingAgents-CN) 的下游副本（`psilhon/TradingAgents-CN`）。本文件只写**本项目特有**的事实——通用规则见 `~/.claude/CLAUDE.md`。

## 项目身份

- **定位**：面向中文用户的多智能体股票分析学习平台（FastAPI 后端 + Vue 3 前端 + LangGraph 多智能体 + 多数据源）
- **当前版本**：`v1.3.5`（fork patch release；`pyproject.toml` 经 `[tool.setuptools.dynamic]` 派生；上游 `v1.0.1`）
- **当前阶段**：**功能固化阶段**，cache-layer-consolidation epic 4.1-4.8 全部 sub-stage 已落地，本地 cache 层架构收敛完成。最新 v1.3.5（2026-05-23，fork patch release，M2「cache epic 收尾 + 累积发版」），`[Unreleased]` 空骨架待累积。**2026-05-23 起对齐全局 v36 OpenSpec 降级**：`openspec/` 冻结为只读档案（47 changes archived + 26 stable capability spec），新 spec / change 改走 `docs/specs/`。最后一条活跃 OpenSpec change `2026-05-22-cache-backend-unification`（cache-layer-consolidation stage 4 epic 蓝本）随切换归档；后续 sub-stage 4.1–4.8 全部在 `docs/specs/cache-backend-unification/` 体系内推进完成。**backlog 完成状态一律以 `openspec/changes/archive/` 为准**——`docs/code-review-2026-05-05.md` 顶部「✅ 完成状态总览」块（19 条建议已全部清零）+ `docs/data-audit-2026-05-17.md`「未处置」段是静态快照，查 backlog 看那两处，不在本文件复述（避免漂移）。
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

# 测试（conftest.py 已把项目根加进 sys.path；marker 体系见 pyproject.toml [tool.pytest.ini_options]）
.venv/bin/pytest -m unit          # 纯逻辑用例（pre-push hook + just test 跑这套，最快）
.venv/bin/pytest -m integration   # 集成测试（需 mongo / redis）
# 全跑去掉 -m；marker 还有 "not requires_env and not requires_network"（跳 .env key / 公网）；单文件/用例用标准 pytest 语法

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
just audit-ports # 验证端口段位 54300-54309
just audit-binds # 验证 loopback 绑定，改 fork-local 配置后必跑
just clean-dry   # 预览将清理的 dev 产物（.dev/ / data/ / logs/）
just clean       # 实际清理
```

## 项目特殊约定（永恒事实）

每条覆盖所有 session；与全局软规则冲突时本节优先；HARD-GATE 不可覆盖。

- **Python 版本偏离**：本地用 homebrew **3.12**，与 `.python-version=3.10`（上游锁）不一致。`pyproject.toml` 写 `>=3.10` 形式上接受。**不修改 `.python-version`**（避免上游同步冲突），用环境变量 `UV_PYTHON` 或显式 `--python` 覆盖。
- **uv.lock 已过时，禁止 `uv sync` 直接重解析**：lock 锁的是旧版 `tradingagents 0.1.0`（25 个直接依赖），现 pyproject 是 v1.2.1（68 个直接依赖含 motor/fastapi/uvicorn 等，已删 streamlit/chainlit）。直接 `uv sync` 会触发 universal resolution，因 `qianfan>=0.4.20` 在 Python 3.13 不可用而失败。**正确流程**：`uv sync --frozen` + `uv pip install -e ".[dev]"`（见命令速查）。
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
| `pyproject.toml` | `[tool.ruff]` / `[tool.pyright]` / `[tool.pytest.ini_options]` 段（追加在末尾） + dependencies 移除 streamlit/chainlit + version 字段 | init-ci 工具链配置（ruff/pyright/pytest）+ stable-v1-cleanup 删依赖 + v1.x release 版本维护 |
| `.pre-commit-config.yaml` | STRICT 模式（ruff/format/pyright pre-commit 阻塞 + pytest -m unit pre-push 阻塞）+ uvx 工具调用 | lint 治理沉淀完成后转 STRICT |
| `.github/workflows/ci.yml` | `uv sync --frozen` + `uv pip install -e .`（不用 `--locked`） | uv.lock 与 pyproject 不同步已知坑 |
| `.gitignore` | 末尾追加 `.chainlit/` + `.claude/settings.local.json` + `.dev/` + `backup/` | fork-local 自动产物 + 本地权限记录 + dev.sh 状态 + mongodump 临时输出 |
| `docs/CHANGELOG.md` / `docs/USAGE.md` / `docs/ai-context/*.md` | 全部新建 + 维护 | Phase 0 prime context HARD-GATE |
| `docs/README.md` / `docs/QUICK_START.md` | 重写为 fork 视角（覆盖上游 v1.0.1 README + Docker-first QUICK_START）| docs-stabilization-v1 / 角色化入口 |
| `docs/operations.md` | 新建 fork-local 文件 | docs-stabilization-v1 / 运维角色 prime |

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

**功能事实 SSOT**（2026-05-23 起切换）：优先 [`docs/specs/<capability>/spec.md`](docs/specs/) 若存在（新事实）→ 回退 [`openspec/specs/<capability>/spec.md`](openspec/specs/)（2026-05-23 前 26 条 stable capability spec 档案，不删不改）。[`docs/ai-context/`](docs/ai-context/) 描述跨 capability 的横切关系；[`docs/`](docs/) 其它目录默认为参考资料或归档。

新会话 prime 优先级：

1. [`docs/README.md`](docs/README.md) — **fork 视角文档中心 + 四角色入口**（用户 / 二开 / 运维 / AI prime），覆盖上游版本
2. `docs/ai-context/project-structure.md` — 顶层目录 + 入口文件清单
3. `docs/ai-context/coding-standards.md` — 项目特有 lint/typecheck/排除约定 + 二开原则
4. `docs/ai-context/architecture.md` — 三层架构 + 多智能体编排 + 数据源链 + LLM 抽象 + **v1.3.x capability 索引**
5. `docs/USAGE.md` — fork 维护者 / 二开者使用手册（含功能矩阵）
6. `docs/operations.md` — **运维角色 prime**（端口段位 / 原生服务 / 备份 / 日志）
7. `docs/CHANGELOG.md` — fork 自身改动历史（不含上游 commits）
8. `docs/ai-context/known-issues.md` — 已知坑（fork 撞过的 + 上游遗留），按需查
9. `docs/specs/<capability>/spec.md`（如存在）→ 回退 `openspec/specs/<capability>/spec.md` — 按 capability 按需查（功能事实 SSOT，按上述优先级）

> 历史"上游详细文档"入口（`docs/STRUCTURE.md` / `docs/architecture/`）改为按需查；上游原版 README/QUICK_START 已挪到 `docs/archive/legacy-upstream/`。

## spec 工作流（2026-05-23 切换）

> **对齐全局 v36 OpenSpec 降级**：本项目从 cache-backend-unification 归档之后停止在 `openspec/` 写新 change，新工作流落 `docs/specs/`。`openspec/` 整体冻结为只读决策档案——47 changes archived + 26 stable capability spec 全部保留，仍是「2026-05-23 前」事实的 SSOT，不删不改。

**新 change 工作流**：

- 新 capability spec 落 `docs/specs/<capability>/spec.md`
- 既有 26 条 openspec capability 如需修改，**先 copy 到 `docs/specs/` 再改**，老文件加 `> superseded by docs/specs/<...>` 头注
- change proposal 落 `docs/specs/<change-id>/{proposal,tasks}.md`（沿用 OpenSpec 的 proposal/tasks 双文件结构，Phase 2/3 流程不变，只改位置）
- 不再走 `/opsx:propose` / `/opsx:apply` / `/opsx:archive` slash 命令——它们对 `openspec/` 历史档案仍有意义，但新 change 用普通文件 + git commit 即可
- explorations 仍落 `openspec/explorations/`（无降级争议；亦可改 `docs/explorations/`）

## Secrets / 凭据

`.env` 已 gitignored。配置见 `docs/USAGE.md` § 1 step 6。**HARD-GATE**：Claude 不读/写/复制 secret 值，由你手动填。
