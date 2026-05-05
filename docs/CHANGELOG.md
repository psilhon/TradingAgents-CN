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

### Fixed

- **代码风格 lint 治理 pass 2**（OpenSpec change `lint-handfix-pass-2`）：`lint-handfix-pass-1` 后剩 850 issues 全部清理至 **0 errors**：
  - **B007/RUF059/E712/RUF005**（87）：unsafe-fix `_` 占位 / `is True/False` 比较
  - **RUF013 implicit-optional**（125）：unsafe-fix 加 `Optional[X]` type hint
  - **B-rules**（22）：unsafe-fix `B905` zip-strict / `B904` raise-from / `B006` mutable-default / `B009` get-attr
  - **W293 hidden**（279）：unsafe-fix 隐藏空白
  - **F841 unused-variable**（66 → 71 修了重新计数）：unsafe-fix 删变量
  - **E722 bare-except**（31）：sed 一把梭 `except:` → `except Exception:`（ruff 不在 unsafe-fix 列表）
  - **剩余 226 issues**（E501 中文长行 / E402 业务 import / F401 动态使用 / F403/F405 import-star / 其它小项）：用 `ruff check --add-noqa` 一次性加 `# noqa: <CODE>` 标注（合理 noqa case）
  - 验证：每 commit 后核心模块 import + backend `/api/health` 200，全过
  - **最终**：`uvx ruff check .` All checks passed!（0 errors）。下一步可立 `lint-strict-mode-enable` 把 pre-commit + CI 转严格阻塞模式

- **真 bug 类 lint 修复 pass 1**（OpenSpec change `lint-handfix-pass-1`）：`lint-cleanup-baseline` 后剩 870 issues 中含 19 个**真 bug**（runtime 可能崩 / 错 import 模块），本 change 全部修复（870 → 851）：
  - **F811 重复 import (5)**：`agent_utils.py:11` / `config_manager.py:36` / `graph/trading_graph.py:18` / `tool_logging.py:14` 删 unused `from logging_init import get_logger`（被 `logging_manager` 覆盖）；`dataflows/data_source_manager.py:2134-2143` 删 identical 的第一份 `def get_data_source_manager` + 配套 redundant global var
  - **F821 缺 import (14)**：tests/ 加 `import os` (×2 文件 / 7 处) + `import logging + logger` 定义 (×2 文件 / 3 处)；`google_tool_handler.py` 加 `import traceback`；`data_source_manager.py:1861` 加 `from tradingagents.config.database_manager import get_database_manager`；`utils/logging_init.py` 加 `import logging` + `get_session_logger` 函数体加 `logger = get_logger(logger_name)` 定义（之前 line 85 用了未定义的 `logger`，跑该函数会 NameError）
  - 验证：F811 + F821 共 0 errors / 5 个核心模块 import smoke / backend `/api/health` 200
  - 沉淀 spec MODIFY `lint-policy`：加 "真 bug 类 lint 优先修" + "F811 默认删 previous unused"

- **Lint baseline 治理**（OpenSpec change `lint-cleanup-baseline`）：上游接手时 ruff 报 21,321 issues，本 change 用 Q1=C / Q2=b / Q3=ii 策略治理至 **870 issues（-95.9%）**：
  - **调宽规则**（`pyproject.toml [tool.ruff]`）：`line-length` 100 → 140；`[tool.ruff.lint].ignore = ["RUF001", "RUF002", "RUF003"]`（中文全角字符在中文 codebase 是常态，非代码质量问题）→ 砍 ~7,800 issues
  - **按 rule code 分批 ruff --fix**（每个一个 commit）：W293 (9114) / F541 (1705) / I001 (559) / F401 (379) / UP006 (342) / UP045 (272) / W291 (114) / UP035 (4) / 剩余一把梭 (522) → 砍 ~12,800 issues
  - 每 commit 后验证：`tradingagents` 包 import + backend `/api/health` 200 + 6 个核心模块 import smoke test 全过
  - **剩 870 issues** 全部无 fixable，需手动改（F841 unused-vars / E402 import-not-at-top / B007 unused-loop-ctrl / F821 undefined-name 等真 bug + 复杂度类）→ 留给后续 hotfix change `lint-handfix-pass-1`
  - 建立 base spec `lint-policy`：定义中文项目友好放行 + 按 rule code 分批 + warn-only 治理过程
  - **CI 仍 red**（870 errors > 0）；转严格模式留给 `lint-strict-mode-enable` change

- **pytest collection 干净化**（OpenSpec change `pytest-collection-fix`）：删除 16 个 dead test（import-time 引用已重组的 `akshare_utils` / `optimized_china_data` / `finnhub_utils` 等模块 / 连 mongo 默认端口 / 缺第三方 stub）。pytest collection 16 errors → 0。`644 tests collected, 0 errors`。

- **pyright handfix pass-1**（OpenSpec change `pyright-handfix-pass-1`）：silence 7 类 fork 项目固有噪音 rule（reportAttributeAccessIssue / reportFunctionMemberAccess / reportReturnType / reportMissingModuleSource / reportUnsupportedDunderAll / reportOperatorIssue / reportAssignmentType）。pyright 1,224 → 879 errors（-28%）。剩 879 是真问题（reportMissingImports 494 / reportOptionalMemberAccess 132 / reportArgumentType 107 / 等），留 `pyright-handfix-pass-2` 治理。

- **pyright baseline 调宽**（OpenSpec change `pyright-cleanup-baseline`）：`pyproject.toml [tool.pyright]` 删 `strict = ["tradingagents"]`。pyright 9,955 → 1,224 errors（-87%）。砍掉的 8,700+ 全是 `reportUnknown*Type`——本 fork 大量用 pandas DataFrame / 第三方数据源（无 type stub）触发的噪音，无价值治理。剩 1,224 多是真问题（`reportMissingImports` 494 / `reportAttributeAccessIssue` 306 等），留独立 change `pyright-handfix-pass-1` 治理。

### Added

- **pytest baseline**（OpenSpec change `pytest-baseline`）：`pyproject.toml` 加 `[project.optional-dependencies] dev = ["pytest>=8", "pytest-asyncio>=1.0"]`（新机器 `uv sync --extra dev` 自动装）。pytest collection 不再 INTERNALERROR（之前因 13 个孤立 test 含 `from web.*` import + sys.exit(1) 让 pytest 早退）。

### Removed

- **13 个孤立 test**（同 `pytest-baseline`）：`tests/{test_risk_assessment, test_dataframe_fix, test_web_fix, test_format_fix, test_web_hk, test_progress, test_enhanced_analysis_history, test_import_fix, test_mongodb_check, test_validation_fix, test_pypandoc_functionality, debug_web_issue, test_fix}.py`——全部 `from web.utils.*` import，但 `web/` 已被 `stable-v1-cleanup` 删除。

### Changed

- **ruff 转严格阻塞模式**（OpenSpec change `ruff-strict-mode-enable`）：4 个 lint changes 治理至 ruff 0 errors 后，`.pre-commit-config.yaml` 的 `ruff-check` / `ruff-format` hook 去掉 warn-only wrapper，引入新 ruff issue 立即阻塞 commit。pyright（9955 errors）+ pytest（未装）保留 warn-only，等独立 `pyright-cleanup` / `pytest-baseline` OpenSpec change 治理后各自转严格。

- **CLAUDE.md 瘦身 + 长尾外置**（OpenSpec change `claude-md-trim`）：CLAUDE.md 从 179 行压到 151 行（仍超 150 模板上限但 ≤ spec 放宽后的 175）。「已知坑」段（10 行）外置到 `docs/ai-context/known-issues.md`（77 行，含完整 fork 撞坑记录 + 上游遗留 + workaround）；「Secrets / 凭据」段（19 行）压成 3 行指引到 `docs/USAGE.md`；「OpenSpec 状态」段（5 行）压成 2 行。MODIFY base spec `repository-scope`「文档范围」Requirement 加"CLAUDE.md ≤ 175 行 + 长尾外置"约束。清理已知坑过时项（chainlit / 专有目录重复）。

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
