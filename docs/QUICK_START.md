# 快速开始（fork v1.3.0）

> **fork 视角快速开始**——本文件覆盖上游 Docker 路径版本。
> fork 使用 **Apple Silicon macOS + 原生 Homebrew 服务（mongo + redis）** 部署，零 Docker。
> 上游原版 QUICK_START 仅保留在 git 历史中（参考 commit `5b8cd3c` 之前）。

## 5 分钟跑通最短路径

### 0. 前置要求

- **macOS Apple Silicon（arm64）**——fork 仅支持此平台（[`repository-scope` spec](../openspec/specs/repository-scope/spec.md)）
- **Homebrew** 已装：`brew --version` 能跑
- **Python 3.12 (homebrew)**：`brew install python@3.12`
- **uv**：`brew install uv`
- **Node 20+**（前端）：`brew install node`
- **mongosh**：`brew install mongosh`（首次部署脚本会装）
- **just**（命令运行器）：`brew install just`

### 1. clone

```bash
git clone git@github.com:psilhon/TradingAgents-CN.git
cd TradingAgents-CN
```

### 2. 首次部署（一次性）

```bash
./scripts/setup-native.sh
```

脚本会：
- `brew install mongodb-community@7.0 redis mongosh`（如未装）
- 创建 mongo 数据目录 `data/mongodb/` 和 redis 数据目录 `data/redis/`
- 用 [`config/mongod.conf`](../config/mongod.conf) 起 mongo 一次，创建管理员账号 `admin / tradingagents123`
- 起完关掉，准备好给后续 `just up` 用

### 3. 装 Python 依赖

```bash
uv venv --python /opt/homebrew/opt/python@3.12/bin/python3.12 \
        --python-preference only-system
uv sync --frozen --python .venv/bin/python --python-preference only-system
uv pip install -e . --python .venv/bin/python
```

> **不要直接 `uv sync` 不加 `--frozen`**——uv.lock 与 pyproject 有已知偏差（fork 已在 v1.x 大量加新依赖，旧 lock 会触发 universal resolution 失败）。详见项目根 [`CLAUDE.md`](../CLAUDE.md) "项目特殊约定" 段。

### 4. 装前端依赖

```bash
cd frontend && npm install && cd ..
```

### 5. 配 `.env`

```bash
cp .env.example .env
```

打开 `.env` 至少填 1 个 LLM key（DashScope / DeepSeek / SiliconFlow / Google AI / OpenAI 任选其一）。各厂家配置见 [`configuration/`](configuration/)。

> **Claude 助手不会读 / 写 / 复制 secret 值**（HARD-GATE）。`.env` 由你手填。

### 6. 启动全栈

```bash
just up
```

等待约 5-15 秒，看到：

```
✅ mongodb  127.0.0.1:54302
✅ redis    127.0.0.1:54303
✅ backend  127.0.0.1:54301
✅ frontend 127.0.0.1:54300
```

### 7. 访问

- **前端**：http://127.0.0.1:54300
- **后端 API**：http://127.0.0.1:54301/docs（FastAPI 自动文档）

注册账号后即可使用 Dashboard / 自选股 / 模拟账户 / 每日推荐等功能。

### 8. 停服

```bash
just down
```

全栈停（含原生 mongo + redis，无残留进程）。

## CLI 多智能体演示（无需前端）

```bash
.venv/bin/python main.py
```

> 需要 `.env` 至少 1 个 LLM key + 1 个数据源 key（Tushare / FinnHub 等）。

## 常见后续操作

- **故障排查 / 端口冲突 / 日志位置** → [`operations.md`](operations.md)
- **完整使用流程 / 各功能详解** → [`USAGE.md`](USAGE.md)
- **二开 / 加功能** → [`ai-context/`](ai-context/) + [`openspec/specs/`](../openspec/specs/)
- **重建 .venv（依赖装漂时）** → [`USAGE.md`](USAGE.md) § "重建 venv"

## CI 同源命令

本地 + pre-commit + GitHub Actions 都跑同一组：

```bash
just ci          # 完整流水线 (lint + typecheck + test)
just lint        # 仅 ruff check + format check
just typecheck   # 仅 pyright
just test        # 仅 pytest -m unit
just fix         # 自动修复 ruff lint / format
just setup       # 装 pre-commit hook（首次 setup）
```

## 文档入口

- [`README.md`](README.md) — 文档中心，按角色（用户 / 二开 / 运维 / AI prime）分流
- [`USAGE.md`](USAGE.md) — fork 使用手册（详细版）
- [`operations.md`](operations.md) — 运维手册
- [项目根 `CLAUDE.md`](../CLAUDE.md) — fork 项目级 AI 助手规则与永恒约定
