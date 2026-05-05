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

### Added

- **Binding / port 审计工具与文档**（OpenSpec change `binding-audit-tooling`）：把 Phase 0 撞墙 4 次的"反应式排查"系统化为工具 + 文档：
  - `just audit-ports`：扫所有段位 5430x 端口的 LISTEN 状态，标记非 127.0.0.1 binding 为违规（exit 1）。段位外端口（如其它项目占的 :54310）不报警
  - `just audit-binds`：扫 fork-local 配置文件的 binding hygiene（vite.config.ts / docker-compose.override.yml / pyproject.toml）—— 检查 0.0.0.0 hardcode + docker 端口前缀 + vite host/port/proxy 配置
  - `CLAUDE.md`「Fork patch 清单」段：列 6 类上游 tracked 必 patch 文件 + 完全不动原则文件 + 通过 override 不直接改的文件
  - `docs/ai-context/coding-standards.md`「Binding / Port 配置层次表」段：6 层（CLI / env / .env / fork-local config / override / 上游 hardcode）+ 优先级 + 改完必跑 audit task
  - 建立 base spec `audit-tooling`

### Removed

- **学习中心模块**（OpenSpec change `remove-learning-center`）：删除前端"学习中心"模块——本 fork 是个人二次开发实战平台，不需要保留上游静态学习内容站点。删除范围：(1) `router/index.ts` 的 `/learning` 路由 + 3 个 child route + `/paper/:name.md` 兼容重定向；(2) `views/Learning/` 整个目录（3 个 .vue 文件）；(3) `SidebarMenu.vue` 的"学习中心"菜单项 + 未用 `Reading` icon import；(4) `Dashboard/index.vue` 的 AI 学习中心推荐卡片（template + `goToLearning` 函数 + 相关 SCSS + 未用 `Reading` icon import）。无后端 / 数据库改动。访问 `/learning/*` 现走 404 fallback。建立 base spec `frontend-navigation`。

- **稳定版 v1 大清理**（OpenSpec change `stable-v1-cleanup`）：fork 决策转为**独立分叉**（不再 sync upstream），激进清理 7 类与本 fork 用例无关的上游遗留：
  - **Windows 平台支持**（91 文件 / 15527 行）：~80 个 .ps1/.bat/.cmd 脚本 + `scripts/portable/` + `scripts/windows-installer/` + 6 个 Windows-only docs
  - **streamlit 旧 web/**（25 文件 + pyproject deps）：删 `web/` 整目录 + pyproject 移除 `streamlit` / `chainlit` deps + uv pip uninstall + 改 ruff/pyright exclude
  - **学习中心残留 docs**（12 文件 / 3821 行）：`docs/learning/` + `docs/paper/` (1.8M) + 含 learning 的 blog post（被 task 8 覆盖删）
  - **未用 docker-compose 变体**（3 文件 / 505 行）：`docker-compose.hub.nginx.yml` + `.arm.yml` + `nginx/` 整目录
  - **install/ db config 快照**（2 文件 / 33176 行）：1MB 上游 db export
  - **examples + 旧版本测试**（47 文件 / 8588 行）：`examples/` 30 demo + `tests/0.1.14/` 旧快照 + 清 pyproject pytest config
  - **上游 release / blog**（47 文件 / 21395 行）：`docs/releases/` + `docs/blog/`
  - **CLAUDE.md / docs/USAGE.md "Fork 上游同步"段重写**：从"定期合"改为"独立分叉，cherry-pick"
  - 总计 ~228 文件 / ~83000 行删除。Backend 重启验证无回归（/api/health 200）。建立 base spec `repository-scope`。

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
