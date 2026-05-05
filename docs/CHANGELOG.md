# Changelog

本文件追踪本 **fork**（`psilhon/TradingAgents-CN`）自接手以来的本地化改动。上游 (`hsliuping/TradingAgents-CN`) 的变更通过 `git log upstream/main` 查看，不在本文件复述。

格式遵循 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-CN/1.1.0/)；版本号用 [SemVer 2.0](https://semver.org/lang/zh-CN/) + `-fork.N` 后缀。

---

## [Unreleased] — Phase 0 立项基础设施

### Added — 项目级配置

- 项目级 `CLAUDE.md`（128 行；项目身份 / 命令速查 / 端口分配 / 项目特殊约定 / AI 上下文入口 / Secrets 清单 / 已知坑）
- **端口段位约定 54300–54309**（前端 54300 / 后端 54301 / mongo 54302 / redis 54303 / redis-commander 54304 / mongo-express 54305 / 预留 54306–54309）
- `docker-compose.override.yml`（本地端口映射 + CORS 同步；加入 `.git/info/exclude`，本地独有不污染 fork）

### Added — Phase 0 prime context

- `docs/CHANGELOG.md`（本文件）
- `docs/USAGE.md`（fork 维护者 + 二次开发者使用手册）
- `docs/ai-context/project-structure.md`（顶层目录 + 入口文件清单）
- `docs/ai-context/coding-standards.md`（项目特有规范）
- `docs/ai-context/architecture.md`（架构摘要 + 二开关注点）

### Added — OpenSpec 流程（决策追溯）

- `openspec/{changes,specs}/`
- `.claude/{commands,skills}/`（OpenSpec 自动生成的 4 个 skill + opsx 命令）

### Added — CI / 工具链（init-ci Recipe B）

- `.github/workflows/ci.yml`（lint + typecheck + test + gitleaks security 扫描）
- `.github/dependabot.yml`（依赖升级自动 PR）
- `justfile`（`just ci/lint/typecheck/test/fix/setup` 同源命令）
- `.pre-commit-config.yaml`（**全部 hook 处于 warn-only 模式**——上游存量 warning 不阻塞 commit）
- `pyproject.toml` 追加 `[tool.ruff]` / `[tool.pyright]` / `[tool.pytest.ini_options]`

### Changed — 环境本地化

- Python 版本：本地 venv 用 homebrew `python@3.12.13`（上游 Docker 用 `python:3.10-slim`；不修改上游 `.python-version`）
- `ci.yml` 把 `uv sync --locked --all-extras` 改为 `uv sync --frozen` + `uv pip install -e .`（绕开 lock 不同步问题）

### Fixed

- **主题切换 bug**（OpenSpec change `fix-theme-persistence`）：用户切深色后，路由切换 / API 调用 / 页面刷新会重置回浅色。根因：`stores/auth.ts` 的 `syncUserPreferencesToAppStore()` 在 login / fetchUser / updateUser 三处用后端 `user.preferences.ui_theme`（admin 默认 light）强制覆盖 `appStore.theme`；附加 bug 是 `stores/app.ts toggleTheme()` 未写 localStorage。修复：(1) 删除 auth.ts ui_theme 同步逻辑（后端字段保留 schema 不消费）；(2) toggleTheme 加 `localStorage.setItem('app-theme', ...)`。主题选择现在完全本地持久化。

### Known Issues — 上游遗留（已记录到 `CLAUDE.md` 已知坑段）

- `uv.lock` 锁的仍是旧版 `tradingagents 0.1.0`（25 个直接依赖），与当前 `1.0.0-preview`（70+ 依赖）不同步
- `chainlit` 在 `pyproject.toml` 中但代码 0 引用，且锁死旧 `starlette 0.41`
- `streamlit 1.57` 与 chainlit 锁的旧 starlette 冲突 → `web/` 旧 streamlit UI 不可启动
- `qianfan>=0.4.20` extra 在 Python 3.13 无 wheel
- `uv pip install -e .` 会误删 tracked 文件（`VERSION` / `requirements.txt` / `requirements-lock.txt`），装完必须 `git status` 检查

---

## [1.0.1-fork.0] — 2026-05-05 上游基线

- Fork 自上游 `cdd0316` (`chore: update database export config snapshot`)
- 上游版本：`v1.0.1`（README 徽章；`pyproject.toml` 标 `1.0.0-preview`）
