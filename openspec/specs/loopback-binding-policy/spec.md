# loopback-binding-policy Specification

## Purpose
TBD - created by archiving change docker-compose-loopback-baseline. Update Purpose after archive.
## Requirements
### Requirement: 所有对外服务必须绑定 loopback 127.0.0.1

本 fork 是个人使用项目，**不**对外（公网 / 同局域网）暴露任何服务。所有对外服务 MUST 只接受 loopback 连接，**禁止**绑 `0.0.0.0` 或其它 host 网卡 IP。

落地约束（按文件类型）：
- `docker-compose.yml` / `docker-compose.*.yml` 端口映射 MUST 形如 `"127.0.0.1:543xx:xxx"`，**禁止**裸 `"543xx:xxx"`（默认绑 0.0.0.0）
- uvicorn / vite dev / 其它 host-side 命令 MUST 用 `--host 127.0.0.1` 启动
- `.env` 中 `API_HOST` / `HOST` 等配置 MUST = `127.0.0.1`（host 端）；容器内部 `API_HOST` 可保留 `0.0.0.0`（容器网络 namespace 隔离，由 host 端口映射前缀控制）

#### Scenario: docker-compose.yml grep 端口绑定

- **WHEN** 在 `docker-compose.yml` / `docker-compose.*.yml`（不含 override）`grep -E '^\s*-\s*"\d'`
- **THEN** 命中行 MUST 全部以 `"127.0.0.1:` 开头
- **AND** 不出现裸 `"PORT:PORT"` 形式

#### Scenario: 新机器首次 clone 后 docker compose up

- **WHEN** 用户在新机器 `git clone` 仓库（不含 untracked override）
- **AND** `docker compose up -d`
- **THEN** 所有端口仅监听 host 的 `127.0.0.1`
- **AND** 同局域网其它机器无法访问任何服务

### Requirement: 端口段位 54300-54309

本 fork 对外服务端口 MUST 在 `54300-54309` 段位内分配，**禁止**使用上游默认的 `3000` / `8000` / `27017` / `6379` 等。

固定分配：

| 端口 | 服务 | 容器内端口 |
|------|------|------|
| 54300 | frontend | 80 |
| 54301 | backend (FastAPI uvicorn) | 8000 |
| 54302 | mongodb | 27017 |
| 54303 | redis | 6379 |
| 54304 | redis-commander | 8081 |
| 54305 | mongo-express | 8081 |
| 54306–54309 | 预留 | — |

#### Scenario: docker-compose.yml 端口检查

- **WHEN** 在 `docker-compose.yml` 找所有 `"127.0.0.1:NNNNN:" 段
- **THEN** 5 位 host 端口 MUST 全部落在 `[54300, 54309]` 区间
- **AND** 同一服务名映射唯一（无重复分配）

