---
name: port-loopback-audit
description: Audit ports (54300-54309 only) and host binds (127.0.0.1 only) across vite.config.ts, mongod.conf, redis.conf, scripts/, justfile, .env. Use after adding any new service / port reference / proxy / bind config, or when verifying the loopback-binding-policy spec is upheld. Outputs violations with line numbers and fix suggestions.
disable-model-invocation: true
---

# port-loopback-audit

项目硬约束（来自 `CLAUDE.md` § "端口分配" + `openspec/specs/loopback-binding-policy/spec.md`）：

1. **对外服务端口段位**：`54300–54309`（10 个，顺序分配，下表外的端口禁止）
2. **所有 host 必须 `127.0.0.1`**（loopback only，禁止 `0.0.0.0`）

| 端口 | 服务 |
|------|------|
| 54300 | frontend (vite dev) |
| 54301 | backend (FastAPI / uvicorn) |
| 54302 | mongodb (native) |
| 54303 | redis (native) |
| 54304–54309 | 预留 |

## 何时调用

- 加新服务 / 新 port reference
- 改 vite proxy / dev server / uvicorn 命令行
- 改 `config/mongod.conf` / `config/redis.conf`
- 改 `.env.example`（不读 `.env`，HARD-GATE）
- 改 `scripts/dev.sh` / `scripts/local-services.sh` / `justfile`
- 升级 Vue / Vite / Element Plus 后回归
- OpenSpec change 涉及网络 / 服务 / 部署

## 审计步骤

```bash
# 1. 端口段位检查（grep 不在 54300–54309 段位的硬编码端口）
grep -nE ':(5(43[0-9])|[1-9][0-9]{0,3}|0\.0\.0\.0:[0-9]+)' \
  frontend/vite.config.ts \
  config/mongod.conf \
  config/redis.conf \
  scripts/*.sh \
  justfile \
  .env.example \
  2>/dev/null \
  | grep -vE ':5430[0-9]' \
  | grep -vE '#' \
  || echo "  ✅ 无段外端口"

# 2. 0.0.0.0 / wildcard bind 检查
grep -nE '(0\.0\.0\.0|--host\s+0\.0\.0\.0|bind\s+0\.0\.0\.0|bindIp:\s*0\.0\.0\.0|HOST=0\.0\.0\.0)' \
  frontend/vite.config.ts \
  config/mongod.conf \
  config/redis.conf \
  scripts/*.sh \
  justfile \
  .env.example \
  app/main.py \
  2>/dev/null \
  || echo "  ✅ 无 0.0.0.0 绑定"

# 3. 跑项目已有的 audit-binds（如有）
just audit-binds 2>/dev/null || echo "  ℹ️ just audit-binds 未定义"
```

## 输出格式

```
port-loopback-audit:
  端口段位 (54300–54309):
    ✅ frontend/vite.config.ts:42  → port 54300
    ✅ scripts/dev.sh:18  → uvicorn 127.0.0.1:54301
    ⚠️ docs/USAGE.md:88  → 提到 8000 (文档残留, 非运行配置, 不阻塞)
    
  Loopback 绑定:
    ✅ config/mongod.conf:5  → bindIp: 127.0.0.1
    ✅ config/redis.conf:11  → bind 127.0.0.1
    
  违规:
    ❌ <file>:<line>  → <现状>  → <修复建议>
    
建议：<proceed | abort | fix-and-rerun>
```

## 常见违规模式

| 模式 | 修复 |
|------|------|
| `vite.config.ts` 出现 hardcode 8000 / 3000 / 5173 | 改 `server.port: 54300` 或命令行 `--port 54300` 覆盖 |
| `--host 0.0.0.0` 出现在 uvicorn / vite 命令 | 改 `--host 127.0.0.1` |
| `bindIp: 0.0.0.0` in `mongod.conf` | 改 `bindIp: 127.0.0.1` |
| `bind 0.0.0.0` in `redis.conf` | 改 `bind 127.0.0.1` |
| `API_HOST=0.0.0.0` in `.env.example` | 改 `API_HOST=127.0.0.1` |
| 端口超出段位（如 54310, 8080） | 重新分配到 54304–54309 预留段 |

## 不视为违规

- `docs/` 文档中提到 8000 / 3000（上游残留示例）— 不阻塞，但建议加 "本 fork 使用 54301" 备注
- `tests/` 中 mock 端口 — 不审计
- `.venv/` / `node_modules/` — 跳过
- 注释行 — 跳过
