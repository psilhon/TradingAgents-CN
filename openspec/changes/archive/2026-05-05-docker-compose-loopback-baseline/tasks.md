## 1. docker-compose.yml 端口段位 + loopback — commit 1

- [x] 1.1 改 6 个 service 的 ports 字段加 `127.0.0.1:` 前缀 + 落入 54300-54309 段位
- [x] 1.2 改 `CORS_ORIGINS` 为 `http://localhost:54300`（与 override 一致）
- [x] 1.3 改 `VITE_API_BASE_URL` 为 `http://localhost:54301`
- [x] 1.4 删 `version: '3.8'` 行（docker compose v2 deprecated）
- [x] 1.5 image tag `:v1.0.0-preview` → `:v1.1.0`（与 pyproject 同步）
- [x] 1.6 `docker compose config` 验证 yaml 合法
- [x] 1.7 commit

## 2. 收口

- [x] 2.1 docs/CHANGELOG.md `### Changed` 条目
- [x] 2.2 archive
