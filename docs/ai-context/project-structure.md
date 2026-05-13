# project-structure.md

> AI prime context — 项目目录布局 + 入口文件。简洁优先；详尽见上游 `docs/STRUCTURE.md`。

## 顶层目录

| 目录 | 用途 | 二开权重 |
|---|---|---|
| `tradingagents/` | **LangGraph 多智能体核心**（Apache 2.0）| 🔴 主开发区 |
| `app/` | FastAPI 后端 + routers / services / schemas / middleware / worker | 🟡 **专有授权**，仅本机学习改 |
| `frontend/` | Vue 3 + Vite + Element Plus 前端 | 🟡 **专有授权** + JS/TS 栈 |
| `cli/` | 命令行入口（数据初始化、akshare/baostock/tushare init）| 🟢 Apache 2.0 |
| `tests/` | pytest 测试 + debug 脚本 | 🟢 含旧快照 `0.1.14/`（pytest 已 ignore）|
| `web/` | streamlit 旧 UI | ⚫ **已废弃**（chainlit/starlette 冲突，不可启动）|
| `openspec/` | OpenSpec 决策追溯（fork 加）| 🟢 changes / specs |
| `docs/` | 文档 73+ 文件 | 🟢 散乱无统一索引；上游已有 `QUICK_START.md` `STRUCTURE.md` `architecture/` 等 |
| `config/` | 原生服务配置（`mongod.conf` / `redis.conf`）| 🟢 fork 加 |
| `scripts/` | 上游一次性脚本（数据导出、迁移等） + fork 新增 `setup-native.sh` / `local-services.sh` | ⚫ 不在 lint 范围 |
| `data/` | 原生 mongo/redis 数据目录（gitignored）| — |
| `examples/` | 示例代码 | ⚫ 不在 lint 范围 |
| `data/` `reports/` `assets/` `images/` | 运行时 / 静态资源 | — |

## 关键入口文件

| 入口 | 启动命令 | 用途 |
|---|---|---|
| `app/main.py` | `uvicorn app.main:app --port 54301` | FastAPI 后端主入口 |
| `app/__main__.py` | `python -m app` | 等价后端入口 |
| `app/worker.py` / `app/worker/` | apscheduler 定时任务 | 后台 worker |
| `main.py` | `python main.py` | LangGraph 多智能体 CLI demo（Google AI 默认）|
| `cli/main.py` | `python -m cli.main` | 数据初始化 CLI |
| `frontend/src/main.ts` | `npm run dev -- --port 54300` | Vue 前端入口（强制段位 54300）|
| `tradingagents/graph/trading_graph.py` | 被 `main.py` import | **多智能体编排核心** |

## 配置文件

| 文件 | 作用 | tracked? |
|---|---|---|
| `pyproject.toml` | Python 依赖 + ruff/pyright/pytest 配置 | ✓ |
| `uv.lock` | **过时**（锁旧版 0.1.0，25 依赖；当前 1.0.0-preview 70+ 依赖）| ✓ |
| `requirements.txt` | **已弃用**（首行注释；用 pyproject）| ✓ |
| `requirements-lock.txt` | **过时** | ✓ |
| `frontend/package.json` | npm scripts (dev/build/lint/format/type-check) | ✓ |
| `config/mongod.conf` | MongoDB 7.0 配置（bind 127.0.0.1:54302, 项目本地 dbpath）| ✓ fork 加 |
| `config/redis.conf` | Redis 配置（bind 127.0.0.1:54303, AOF）| ✓ fork 加 |
| `scripts/local-services.sh` | 原生服务编排（替代 docker compose）| ✓ fork 加 |
| `scripts/setup-native.sh` | 一次性安装脚本（brew install + mongo user 创建）| ✓ fork 加 |
| `.env` / `.env.example` | 配置（150+ 项；必填 3 处）| `.env` gitignored / `.env.example` tracked |
| `justfile` / `.pre-commit-config.yaml` / `.github/workflows/ci.yml` | 本 fork 加的 CI 配方（init-ci Recipe B）| ✓ 待 commit |

## License 双轨

| 范围 | 许可 |
|---|---|
| 根目录 + `tradingagents/` + `cli/` + `tests/` 等 | Apache 2.0 |
| `app/`（FastAPI 后端）+ `frontend/`（Vue）| **专有，商业用须授权**（hsliup@163.com）|

详见 `LICENSE` / `LICENSING.md` / `COPYRIGHT.md`。
