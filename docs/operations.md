# 运维手册（fork v1.3.0）

fork 一站式运维参考：端口段位 / 原生服务管理 / 备份恢复 / 日志位置 / 常用排查命令。

> **不是 SSOT**——具体功能行为以 [`openspec/specs/`](../openspec/specs/) 为准（特别是 [`native-local-deployment`](../openspec/specs/native-local-deployment/spec.md)、[`loopback-binding-policy`](../openspec/specs/loopback-binding-policy/spec.md)、[`secret-handling`](../openspec/specs/secret-handling/spec.md)）。本文件是面向运维者的操作指引。

## 端口段位（项目级永恒约定）

**对外服务端口段位：54300–54309**（10 个，顺序分配；段外端口禁止占用）。

| 端口 | 服务 | 配置位置 |
|---|---|---|
| 54300 | frontend (vite dev) | 命令行 `--port 54300`（不动 `frontend/vite.config.ts`，专有授权代码） |
| 54301 | backend (FastAPI / uvicorn) | 命令行 `--port 54301` 或 `.env` 的 `API_PORT` |
| 54302 | mongodb (native) | [`config/mongod.conf`](../config/mongod.conf)：`net.port` |
| 54303 | redis (native) | [`config/redis.conf`](../config/redis.conf)：`port` |
| 54304–54309 | 预留 | — |

**所有服务强制绑定 `127.0.0.1` (loopback only)**：项目为个人使用，不对外暴露。落地：

- uvicorn / vite dev 必须 `--host 127.0.0.1`
- `config/mongod.conf`：`bindIp: 127.0.0.1`
- `config/redis.conf`：`bind 127.0.0.1`
- `.env` 的 `API_HOST` / `HOST` 必须 `127.0.0.1`

验证违规：`just audit-binds`（capability spec：[`loopback-binding-policy`](../openspec/specs/loopback-binding-policy/spec.md)）。

## 原生服务管理

### 一站式启停（推荐）

`scripts/dev.sh` 统一管理原生 mongo + redis + backend + frontend：

```bash
just up                     # = scripts/dev.sh start  起全栈
just down                   # = scripts/dev.sh stop   停全栈（含原生服务，无残留）
just status                 # 端口 / 进程 / 服务状态
just logs                   # tail backend log
just logs-frontend          # tail frontend log
just dev-restart            # 重启全栈
scripts/dev.sh --help       # 完整参数
```

### 首次部署（一次性）

```bash
./scripts/setup-native.sh   # 装 mongo + redis + mongosh，创建 mongo 用户
```

### 手动启停（细粒度调试）

```bash
./scripts/local-services.sh start        # 仅起原生 mongo + redis
./scripts/local-services.sh stop
./scripts/local-services.sh status

# 手动 backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 54301 --reload

# 手动 frontend
cd frontend && npm run dev -- --port 54300
```

### 原生服务文件清单

| 文件 | 用途 |
|---|---|
| [`config/mongod.conf`](../config/mongod.conf) | MongoDB 7.0 配置（bind 127.0.0.1:54302, 项目本地 dbpath, auth=on）|
| [`config/redis.conf`](../config/redis.conf) | Redis 配置（bind 127.0.0.1:54303, AOF, maxmemory 64MB）|
| [`scripts/local-services.sh`](../scripts/local-services.sh) | 原生服务编排（替代 docker compose）|
| [`scripts/setup-native.sh`](../scripts/setup-native.sh) | 首次部署一次性安装器 |
| `data/mongodb/`、`data/redis/` | 数据目录（gitignored）|

### 默认凭据（本地 dev 公开）

- mongo：`admin / tradingagents123` @ `127.0.0.1:54302`
- redis：无密码 @ `127.0.0.1:54303`

> **这是公开的本地 dev 默认密码**，不是用户 secret——可以在文档 / 命令 / 日志中直接出现。生产部署请通过 `.env` 覆盖。

## 备份与恢复

### MongoDB 备份

详见 [`guides/DATABASE_BACKUP_RESTORE.md`](guides/DATABASE_BACKUP_RESTORE.md)。常用命令：

```bash
# 备份全库到 backup/<timestamp>/
mongodump --host 127.0.0.1 --port 54302 \
          --username admin --password tradingagents123 \
          --authenticationDatabase admin \
          --out backup/$(date +%Y%m%d_%H%M%S)/

# 恢复
mongorestore --host 127.0.0.1 --port 54302 \
             --username admin --password tradingagents123 \
             --authenticationDatabase admin \
             backup/<timestamp>/
```

`backup/` 已 gitignored。

### Redis AOF 备份

Redis 配置中 `appendonly yes`，AOF 文件位于 `data/redis/appendonly.aof`。需要导出时直接复制即可：

```bash
cp data/redis/appendonly.aof backup/redis-$(date +%Y%m%d_%H%M%S).aof
```

## 日志位置

| 服务 | 日志路径 | 查看 |
|---|---|---|
| backend | `.dev/backend.log`（由 dev.sh 输出）| `just logs` |
| frontend | `.dev/frontend.log` | `just logs-frontend` |
| mongodb | `data/mongodb/mongod.log` | `tail -f data/mongodb/mongod.log` |
| redis | `data/redis/redis.log` | `tail -f data/redis/redis.log` |
| dev.sh 状态 | `.dev/*.pid` / `.dev/*.status` | `just status` |

> `.dev/` 已 gitignored；`logger` 模块输出层级见 [`config/error_log_separation.md`](config/error_log_separation.md)。

## 本地垃圾清理 + 日志归档

`scripts/clean-local-cruft.sh`（`just clean` 调用）一站式清理：

```bash
just clean         # 实际清理
just clean-dry     # dry-run 看动作，不真删
```

清理范围（**不动当前在写日志 / git tracked / data/ / .venv/**）：

| 类别 | 动作 |
|---|---|
| mongod 日志 | 调 `db.adminCommand({logRotate:1})` 触发轮转（mongod.conf 配 `rename` 模式自动 mv 当前 log → `.log.<ts>`）；删 `logs/mongod.log.*` > 7 天 |
| Python 轮转日志 | 删 `logs/*.log.[0-9]+` > 3 天（RotatingFileHandler 产物） |
| Python cache | `__pycache__` / `.ruff_cache` / `.pytest_cache` / `tradingagents.egg-info` 全删 |
| `.env.bak*` 备份 | 累积 ≥ 3 个时 `tar.gz` 归档到 `backup/`，再删原文件 |
| 孤儿 pid | `.dev/*.pid` 对应进程已死的清掉 |

**首次启用注意**：mongod.conf 从 `reopen` 改为 `rename` 模式，需要 `just down && just up` 重启 mongod 才生效。脚本会探测并提示。重启前调 `just clean` 仅清 cache，不归档 mongod.log。

## MongoDB 索引优化

慢查询排查 / 索引调优详见 [`maintenance/mongodb_index_optimization.md`](maintenance/mongodb_index_optimization.md)。

定期检查（建议每月）：

```bash
mongosh --host 127.0.0.1 --port 54302 \
        --username admin --password tradingagents123 \
        --authenticationDatabase admin \
        --eval "db.getSiblingDB('tradingagents').currentOp({secs_running: {\$gt: 1}})"
```

## 常用排查命令

```bash
# 端口占用
lsof -i :54300-54309

# 进程状态
ps aux | grep -E "uvicorn|vite|mongod|redis-server" | grep -v grep

# 全栈状态一键
just status

# 测试连接
curl http://127.0.0.1:54301/health   # backend healthz
curl http://127.0.0.1:54300           # frontend index
mongosh --host 127.0.0.1 --port 54302 --eval "db.runCommand({ping: 1})"
redis-cli -h 127.0.0.1 -p 54303 ping
```

## 数据正确性审计

2026-05-17 完成的数据正确性系统性修复 + 后续防复发计划见 [`data-audit-2026-05-17.md`](data-audit-2026-05-17.md)。

待办（Phase 3 防复发）：

- `data_consistency_checker` 接入写入闸门
- `stock_basic_info` upsert key 重构
- 字段名统一
- 审计脚本固化

## Secret / API key 处理

- `.env` 已 gitignored；配置流程见 [`USAGE.md`](USAGE.md) § 1 step 6
- AI 助手 / Claude **不读 / 不写 / 不复制** secret 值（HARD-GATE，参见项目 `CLAUDE.md`）
- 详细规范：[`openspec/specs/secret-handling/spec.md`](../openspec/specs/secret-handling/spec.md)、[`security/api_keys_security.md`](security/api_keys_security.md)

## 故障排查

通用故障：[`troubleshooting/`](troubleshooting/)

- [`stock_name_issue.md`](troubleshooting/stock_name_issue.md) — 股票名称展示问题
- [`google_client_options_error.md`](troubleshooting/google_client_options_error.md) — Google AI client 错误
- [`finnhub-news-data-setup.md`](troubleshooting/finnhub-news-data-setup.md) — finnhub 配置
- [`llm-config-test-fix.md`](troubleshooting/llm-config-test-fix.md) — LLM 配置测试
- [`pdf_word_export_issues.md`](troubleshooting/pdf_word_export_issues.md) — 导出问题
- [`web-startup-issues.md`](troubleshooting/web-startup-issues.md) — web 启动问题

## 上游 cherry-pick（罕用）

fork 已声明**独立分叉**，不再批量 sync upstream。需 cherry-pick 上游某个 commit 时临时加 remote、用完即删：

```bash
git remote add upstream https://github.com/hsliuping/TradingAgents-CN.git
git fetch upstream
git cherry-pick <commit-sha>
# 完成后清理
git remote remove upstream
```

不要在仓库内长期保留 `upstream` remote，也不要配置任何自动 sync workflow（capability spec：[`repository-scope`](../openspec/specs/repository-scope/spec.md)）。
