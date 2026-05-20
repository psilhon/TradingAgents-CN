---
name: fork-patch-guard
description: Use before editing tracked-but-patched fork-local files (frontend/vite.config.ts, pyproject.toml, .pre-commit-config.yaml, .github/workflows/ci.yml, .gitignore) or any file under app/ or frontend/src/. Verifies the edit doesn't regress fork-specific patches or violate proprietary-license scope. Triggers on phrases like "改 vite config", "升级 pyproject", "回滚 pre-commit", "动 app/", "改前端业务代码".
---

# fork-patch-guard

本 fork (`psilhon/TradingAgents-CN`) 对上游 `hsliuping/TradingAgents-CN` 做了若干 patch，每条都有理由。改这些文件前先过本 checklist。

## 适用文件

### A 类 — fork patch（不能回滚成上游原貌）

| 文件 | 已 patched 段位 | 改动前必读 |
|------|----------------|------------|
| `frontend/vite.config.ts` | `server.host` / `server.port` / `server.strictPort` / `server.hmr.host` / `server.proxy['/api'].target` | 端口段位 54300–54309 + loopback 强制 |
| `pyproject.toml` | `[tool.ruff]` / `[tool.pyright]` / `[tool.pytest.ini_options]` 末尾段 + dependencies（移除 streamlit/chainlit）+ version | init-ci Recipe B 工具配置 + stable-v1-cleanup |
| `.pre-commit-config.yaml` | STRICT 模式（ruff/format/pyright pre-commit 阻塞 + pytest -m unit pre-push）+ uvx 工具调用 | `openspec/specs/lint-policy/spec.md` |
| `.github/workflows/ci.yml` | `uv sync --frozen` + `uv pip install -e .`（**不用** `--locked`） | uv.lock 与 pyproject 已知不同步 |
| `.gitignore` | 末尾追加 `.chainlit/` / `.claude/settings.local.json` / `.dev/` / `backup/` | fork-local 产物 + 本地权限 + dev.sh 状态 |

### B 类 — 专有授权范围（仅本机学习目的可读 / 商业用途需作者授权）

- `app/**` 后端业务代码
- `frontend/src/**` 前端业务代码（**例外**：`vite.config.ts` 是构建配置）

默认改动范围**排除** B 类目录，除非用户明确点名。PreToolUse hook 会拦截，需 `CLAUDE_ALLOW_PROPRIETARY=1` 或新一轮 prompt 明确授权。

## Checklist（每次改 A 类文件前过一遍）

- [ ] 改动是否**保留**所有 patch 段位？（对照上表）
- [ ] 若引入新依赖：是否同时改了 `pyproject.toml` 和 `uv.lock`？（注意 `uv.lock` 已过时，按 CLAUDE.md "命令速查" 流程走）
- [ ] 若改 vite proxy / dev server：端口是否仍在 54300–54309？host 是否仍 `127.0.0.1`？→ 跑 `just audit-binds` 验证
- [ ] 若改 pre-commit hook 列表：是否同步更新 `openspec/specs/lint-policy/spec.md`？
- [ ] 若改 ci.yml：本地 `just ci` 还能过吗？

## Checklist（每次改 B 类文件前过一遍）

- [ ] 用户在**本对话**明确说过要改这个文件 / 这个模块 / 这个功能吗？
- [ ] 改动是否真的只在用户点名的范围内？（不顺手清理 / 重排 / 改名）
- [ ] 若是 fork minor / patch release：是否在 OpenSpec change 范围内？
- [ ] 改完后是否会导致 `app/LICENSE` 或 `frontend/LICENSE` 条款适用范围变化？

## 输出格式

调用本 skill 后，逐项输出：

```
fork-patch-guard checklist for <file>:
  ✅ patch 段 X 保留
  ✅ patch 段 Y 保留
  ⚠️ patch 段 Z 改动 — 理由：...
  
建议：<proceed | abort | confirm-with-user>
```

不输出违规清单 = 视为同意，可继续 Edit。
