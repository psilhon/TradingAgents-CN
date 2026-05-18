# native-local-deployment Specification

## Purpose

锁定本 fork 的本地部署模型——用 Homebrew 原生 MongoDB + Redis 替代 Docker，并约束服务编排方式、loopback 绑定与运行时产物的版本库卫生。capability 实现于 commit `c3f91206`，spec 由 change `backfill-native-deployment-spec` 回填。

## Requirements

### Requirement: 本地部署 MUST 用 Homebrew 原生服务，不用 Docker

本项目的本地开发与运行环境 MUST 使用 Homebrew 原生进程提供 MongoDB 与 Redis（`mongodb-community@7.0` + `redis`），MUST NOT 依赖 Docker / 容器运行时。

仓库内 MUST NOT 存在容器化文件：`docker-compose*.yml` / `Dockerfile*` / `.dockerignore` / `docker/` 目录 / `docker-init` 类脚本。任何重新引入 Docker 的改动 MUST 先修订本 spec。

理由：本 fork 为 Apple Silicon macOS 个人本地使用，Docker VM 带来 2–4 GB 纯开销。原生化后实测总内存占用 -89%（3.2–6.9 GB → 381 MB），启动 6–12× 加速，业务代码（`app/` / `frontend/` / `tradingagents/`）零改动。

#### Scenario: 仓库不含容器化文件

- **WHEN** 在仓库根扫描 `Dockerfile*` / `docker-compose*.yml` / `docker/`
- **THEN** 0 命中
- **AND** `just audit-binds` 扫描的是 `config/mongod.conf` / `config/redis.conf`，不是 docker compose 文件

#### Scenario: 首次部署经一次性安装器

- **WHEN** 在新机器首次部署
- **THEN** 经 `./scripts/setup-native.sh` 安装 `mongodb-community@7.0` + `redis` + `mongosh` 并创建 mongo 用户
- **AND** 不执行任何 `docker` / `docker compose` 命令

### Requirement: 原生服务 MUST 经 local-services.sh 编排，不用 brew services

MongoDB 与 Redis 进程 MUST 经 `scripts/local-services.sh`（或封装它的 `scripts/dev.sh` / `just up|down|status`）启停，MUST NOT 用 `brew services` 注册为全局服务。

理由：`brew services` 是机器级单实例；本项目用项目本地 `dbPath`（`./data/mongodb`）+ 项目本地配置 + 自管 PID（`.dev/{mongod,redis}.pid`），与机器上其他项目的 mongo/redis 实例并存零冲突。

#### Scenario: 全栈启停

- **WHEN** 执行 `just up`
- **THEN** `scripts/dev.sh` 调 `scripts/local-services.sh` 以项目本地配置启动原生 mongo + redis
- **AND** `just down` 停全栈无残留进程

#### Scenario: 服务隔离

- **WHEN** 启动本项目原生服务
- **THEN** 用绝对路径调 binary（如 `/opt/homebrew/opt/mongodb-community@7.0/bin/mongod`）+ 项目本地 `config/` 配置
- **AND** 不修改任何 `brew services` 注册项，机器上其他项目的 mongo/redis 不受影响

### Requirement: 原生服务 MUST 绑定 loopback 并落入端口段位

原生 MongoDB MUST 绑定 `127.0.0.1:54302`，原生 Redis MUST 绑定 `127.0.0.1:54303`——loopback only 且落在项目端口段位 54300–54309 内。绑定由 tracked 配置文件 `config/mongod.conf`（`bindIp: 127.0.0.1`）与 `config/redis.conf`（`bind 127.0.0.1`）显式声明。

本 Requirement 是 `loopback-binding-policy` 在原生部署模型下的落地形态——loopback spec 管「绑哪个地址」，本 spec 管「在原生服务上由哪个文件落地」。

#### Scenario: mongo / redis 绑定校验

- **WHEN** 检查 `config/mongod.conf` 与 `config/redis.conf`
- **THEN** mongo `net.bindIp = 127.0.0.1`、`net.port = 54302`
- **AND** redis `bind 127.0.0.1`、`port 54303`
- **AND** 二者都不绑 `0.0.0.0` 或任何非 loopback 地址

### Requirement: 原生服务运行时产物 MUST gitignored

原生服务的数据目录 `data/mongodb/` `data/redis/`、PID 文件 `.dev/`、mongodump 临时输出 `backup/` MUST 被 `.gitignore` 排除，MUST NOT 进入版本库。tracked 的只有配置文件（`config/mongod.conf` / `config/redis.conf`）与编排脚本（`scripts/local-services.sh` / `scripts/setup-native.sh`）。

#### Scenario: 运行后仓库无脏数据

- **WHEN** 原生服务运行并写入数据后执行 `git status`
- **THEN** `data/mongodb/` `data/redis/` `.dev/` `backup/` 均不出现在未跟踪文件列表
- **AND** `config/mongod.conf` `config/redis.conf` `scripts/local-services.sh` `scripts/setup-native.sh` 是 tracked 文件
