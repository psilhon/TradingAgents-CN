## Why

`docs/code-review-2026-05-05.md` 第 4 个 critical 发现：`docker-compose.yml` base 文件全部端口映射默认绑 `0.0.0.0`，loopback 铁律仅靠**未 tracked** 的 `docker-compose.override.yml` 兜底——任何新机器 clone 后未 override 的环境立即暴露公网。

具体违规：
- backend `"8000:8000"` (line 15) — 应 `"127.0.0.1:54301:8000"`
- frontend `"3000:80"` (line 72) — 应 `"127.0.0.1:54300:80"`
- mongodb `"27017:27017"` (line 101) — 应 `"127.0.0.1:54302:27017"`
- redis `"6379:6379"` (line 130) — 应 `"127.0.0.1:54303:6379"`
- redis-commander `"8081:8081"` (line 156) — 应 `"127.0.0.1:54304:8081"`
- mongo-express `"8082:8081"` (line 179) — 应 `"127.0.0.1:54305:8081"`

附带问题：
- `version: '3.8'` (line 1) — docker compose v2 已 deprecated
- `CORS_ORIGINS` (line 43) hardcode 上游默认 `localhost:3000/8080/5173`，与 fork 端口段位 54300 不符
- `VITE_API_BASE_URL` (line 76) hardcode `localhost:8000`，应 `localhost:54301`
- `image: tradingagents-backend:v1.0.0-preview` / `:v1.0.0-preview` (line 12, 69) — fork 已发 v1.1.0

## What Changes

- **MODIFIED** `docker-compose.yml`：所有端口前缀改 `127.0.0.1:`、统一进入 54300-54309 段位、CORS / VITE_API / image tag 同步、删 deprecated `version` 字段
- **NEW** capability `loopback-binding-policy`：锁定本 fork 所有 docker-compose 端口映射 + 服务监听地址必须绑 `127.0.0.1`，禁止 `0.0.0.0`

`docker-compose.override.yml`（未 tracked，仅本地）保持不变——因为已经合规，base 改对后 override 实际可删除（但保留防止其它本地化覆盖需求；用户后续自行决定）。

无 BREAKING change（实际跑容器时 override 已经在做正确的事）。

## Capabilities

### New Capabilities

- `loopback-binding-policy`：定义 fork 范围内的网络绑定铁律——所有对外服务 host 端口绑 `127.0.0.1`，端口段位 54300-54309

## Impact

**改动文件**：`docker-compose.yml` 1 个
**风险**：低——override 已经在做相同的事，没有运行时变化
**收益**：消除 untracked override 的单点风险；新机器 clone 即合规
