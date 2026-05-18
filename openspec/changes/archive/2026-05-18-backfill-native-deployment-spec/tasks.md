# backfill-native-deployment-spec — Tasks (archived 2026-05-18)

## 1. 调研已落地范围

- [x] 1.1 核对 commit `c3f91206`：删 59 个 docker 文件 + 新增 `config/mongod.conf` / `config/redis.conf` / `scripts/local-services.sh` / `scripts/setup-native.sh`
- [x] 1.2 确认仓库无 `Dockerfile*` / `docker-compose*.yml` / `docker/` 残留
- [x] 1.3 确认 `config/mongod.conf` bind `127.0.0.1:54302`、`config/redis.conf` bind `127.0.0.1:54303`，落入端口段位 54300–54309

## 2. 撰写 spec

- [x] 2.1 撰写 `native-local-deployment` capability spec：锁定部署模型 / 容器化文件禁令 / loopback + 端口段位 / 服务编排 / 数据目录铁律
- [x] 2.2 确认与既有 `loopback-binding-policy` spec 不冲突（本 spec 管部署模型，loopback spec 管绑定地址，互补）

## 3. 归档

- [x] 3.1 archive change，`native-local-deployment` spec 落入 `openspec/specs/`
