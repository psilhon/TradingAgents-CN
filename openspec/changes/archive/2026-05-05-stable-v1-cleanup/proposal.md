## Why

本 fork 经 Phase 0 立项 + 2 个 OpenSpec change 实施后，达到"个人使用稳定版本"状态。但仓库仍保留大量**与本 fork 用例无关的上游遗留**：~95 个 Windows 平台脚本、已废弃的 streamlit `web/` UI、学习中心残留 docs、未用的 docker-compose 变体、上游 release notes / blog 等。

更重要的是 **fork 决策变化**：本 fork 不再定期 `git pull upstream/main`，转为**独立分叉**——这意味着删除上游 tracked 文件的"未来 sync 冲突"代价从"高"降为"零"，激进清理收益远大于代价。

清理后实际节省的不是磁盘（97% 是 `.venv` + `node_modules` 运行时缓存），而是：
- 🧹 **认知负担**（不再面对 80+ Windows 脚本 / 废弃 UI / 无关 docs）
- 🔍 **代码搜索准确度**（grep 不再 hit 无关结果）
- 📦 **依赖瘦身**（移除 streamlit + chainlit 依赖让 venv 减少包数）

## What Changes

按 7 类 + 顺序：

- **B (Windows 平台)** — REMOVED：`scripts/*.{ps1,bat,cmd}` (~80 文件) + `scripts/portable/` + `scripts/windows-installer/` + 6 个 Windows-only docs
- **C (streamlit 旧 web/)** — REMOVED：`web/` 整目录 + `pyproject.toml` 移除 `streamlit` / `chainlit` 依赖 + `[tool.ruff/pyright]` exclude 去 web 项 + 重跑 `uv pip install -e .` 让 venv 同步去包
- **D (学习中心残留)** — REMOVED：`docs/learning/` + `docs/paper/` (1.8M) + `docs/blog/2025-11-15-learning-center-and-compliance-updates.md`
- **E (未用 docker-compose 变体)** — REMOVED：`docker-compose.hub.nginx.yml` + `docker-compose.hub.nginx.arm.yml` + `nginx/`
- **F (install/ db config 快照)** — REMOVED：`install/` 整目录（2 个 json 共 1MB，上游 db export 快照）
- **G (examples + 旧版本测试)** — REMOVED：`examples/` (30 .py) + `tests/0.1.14/`
- **H (上游 release notes + blog)** — REMOVED：`docs/releases/` (25 文件 264K) + `docs/blog/` (23 文件 488K)

附带变更：

- **CLAUDE.md** 更新 `Fork 上游同步` 段：从"定期合上游"改为"独立分叉，不再 sync upstream"，删除 `git remote add upstream` 命令建议
- **docs/USAGE.md** 同步：删 fork 上游同步章节
- **docs/CHANGELOG.md** 加 `### Removed` 段汇总 + 在 Phase 1 章节标注 fork 决策变化

无 BREAKING change 对**用户**——所有保留功能（FastAPI 后端 + Vue 前端 + LangGraph 多智能体 + 数据源 + 模拟交易等）行为不变。

## Capabilities

### New Capabilities

- `repository-scope`：定义本 fork 仓库的保留范围（包含什么 / 不包含什么），是后续所有"该不该加这个文件"决策的依据

### Modified Capabilities

无 OpenSpec capability 层面变更——之前两个 change 沉淀的 `theme-management` / `frontend-navigation` 不受影响。

## Impact

**删除文件总数**：~150+ files / 估计 5MB（git tracked 部分）

**改动 tracked 文件**：CLAUDE.md / docs/USAGE.md / docs/CHANGELOG.md / pyproject.toml / pyproject [tool.ruff/pyright] exclude（去 web）

**运行时影响**：

- `uv pip install -e .` 重跑后 venv 减少 streamlit + chainlit + 它们的传递依赖（约 30+ 包减少，~50MB venv 缩减）
- `web/` 删除后，访问 streamlit UI 完全不可能（本来就因 chainlit/starlette 冲突不可启动，无回归）
- docker compose 仅剩 `docker-compose.yml`（本地 build 模式），不再支持 `docker-compose --profile management up` 之外的部署变体

**fork 同步影响**：N/A（已决定不再 sync upstream，本 change 即决策落地）

**风险评估**：

- ⚠️ `docs/paper/` 1.8M 删除——若你后续启用"模拟交易"功能发现这是**模拟交易设计文档**而非学习中心 paper，需 git history 找回（commit 不可逆但 git 历史可恢复）
- ⚠️ `examples/` 30 demo 删除——若需参考代码实现，从 git history 找
- ⚠️ `docs/blog` / `docs/releases` 删除——上游架构演进 reference 丢失，但你不再 sync upstream，参考价值降低

所有删除都通过 git，**不可逆但历史可恢复**（`git log --all -- <path>` + `git show <commit>:<path>`）。
