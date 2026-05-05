## 1. 加 just task — commit 1

- [ ] 1.1 编辑 `justfile` 加 `audit-ports` task（lsof + nc + 标记违规 + exit code）
- [ ] 1.2 编辑 `justfile` 加 `audit-binds` task（grep fork-local tracked 文件中 `0.0.0.0` 违规 + 上游 hardcode 端口）
- [ ] 1.3 本地验证：`just audit-ports` 当前全栈应全 ✓
- [ ] 1.4 本地验证：`just audit-binds` 应 0 违规
- [ ] 1.5 commit `feat(just): add audit-ports + audit-binds tasks for binding hygiene`

## 2. CLAUDE.md 加 Fork patch 清单段 — commit 2

- [ ] 2.1 编辑 `CLAUDE.md` 在「项目特殊约定」段后加「Fork patch 清单」段
- [ ] 2.2 列出已 patched 文件 + 字段：
  - `frontend/vite.config.ts`：host / port / proxy.target / strictPort / hmr.host
  - `pyproject.toml`：[tool.ruff/pyright/pytest] 段
  - `.pre-commit-config.yaml`：warn-only mode + uvx 工具调用
  - `.github/workflows/ci.yml`：uv sync --frozen + uv pip install -e .
  - `docker-compose.yml`：通过 `docker-compose.override.yml` !override（不直接改）
- [ ] 2.3 列出"完全不动"原则适用文件：`app/` / `tradingagents/` 业务逻辑 / `docs/architecture/` 等
- [ ] 2.4 commit `docs: add Fork patch list section to CLAUDE.md`

## 3. coding-standards.md 加配置层次表 — commit 3

- [ ] 3.1 编辑 `docs/ai-context/coding-standards.md` 加「配置层次表」段（6 层 + 优先级 + 影响 + audit task）
- [ ] 3.2 6 层：
  1. CLI args（最高，临时覆盖）
  2. 环境变量（`UV_PYTHON` / `HOMEBREW_NO_AUTO_UPDATE` 等）
  3. `.env`（运行时配置，gitignored）
  4. `frontend/vite.config.ts` / `pyproject.toml` / `.pre-commit-config.yaml`（fork-local patch）
  5. `docker-compose.override.yml`（本地端口覆盖，git 不可见）
  6. 上游 tracked 代码（`docker-compose.yml` / `app/services/config_service.py` 等 hardcode）
- [ ] 3.3 每层标注：示例 / 影响范围 / 改完跑哪个 audit task
- [ ] 3.4 commit `docs: add config-hierarchy table to coding-standards`

## 4. 收口

- [ ] 4.1 更新 `docs/CHANGELOG.md` `[Unreleased]` 加 `### Added` 段
- [ ] 4.2 commit `docs: changelog for binding-audit-tooling`
- [ ] 4.3 push 全部 commit（用户 1-click HARD-GATE 守门）
- [ ] 4.4 `openspec archive binding-audit-tooling --yes`
