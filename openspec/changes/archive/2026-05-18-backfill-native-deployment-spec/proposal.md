# backfill-native-deployment-spec

> 回填 capability spec：commit `c3f91206` 把本地部署从 Docker 改造为 Homebrew 原生 mongo+redis（资源 -89%），属铁律级行为变更，但改造当时未补 OpenSpec capability spec。本 change 补齐 `native-local-deployment` spec，恢复决策追溯链。代码已落地，本 change 不改任何代码。

## Why

commit `c3f91206`（`feat(deployment): native Homebrew mongo+redis 取代 docker`）做了一次部署模型层面的改造：

- 删除全部 59 个 Docker 相关文件（`docker-compose.yml` / `Dockerfile.{backend,frontend}` / `docker/` / docker 相关 scripts 与 docs）
- 新增 Homebrew 原生服务编排（`config/mongod.conf` / `config/redis.conf` / `scripts/local-services.sh` / `scripts/setup-native.sh`）
- 实测资源占用 -89%（3.2–6.9 GB → 381 MB），启动 6–12× 加速

这是**铁律级的行为变更**——部署方式、服务编排、端口绑定的落地方式全变了。但改造当时未走 OpenSpec，没有 capability spec 锁定这些约束。后续任何 session 想「改回 Docker」或「加 `brew services`」都缺一道 spec 拦截。CLAUDE.md「当前阶段」段已明确点名此漏：「native 部署改造尚未补 OpenSpec capability spec——建议补 `native-local-deployment`」。

本 change 是**回填式 spec 补全**：capability 已实现于 `c3f91206`，本 change 只补 capability spec，恢复决策追溯链。

## What Changes

新建 capability `native-local-deployment`，锁定铁律：

- 本地部署 MUST 用 Homebrew 原生 `mongodb-community@7.0` + `redis`，不用 Docker
- 仓库内 MUST NOT 存在 `docker-compose*.yml` / `Dockerfile*` / `docker/` 等容器化文件
- 原生服务 MUST 绑定 loopback + 落入端口段位（`127.0.0.1:54302` mongo / `127.0.0.1:54303` redis）
- 原生服务 MUST 经 `scripts/local-services.sh` 编排，不用 `brew services`（保持多实例隔离）
- 数据目录 `data/mongodb/` `data/redis/` 与 PID 文件 `.dev/*.pid` MUST gitignored

## Out of Scope

- 数据质量写库闸门——另见 change `backfill-data-quality-gate-spec`
- 桌面 app 打包、生产部署、容器化重新引入——本 fork 个人本地使用，明确不做
- `scripts/local-services.sh` 的实现优化、跨平台（非 Apple Silicon macOS）支持

## Impact

- 新建 `openspec/specs/native-local-deployment/spec.md`
- **0 代码改动**——capability 已实现于 `c3f91206`，本 change 纯文档回填
- 风险：无
