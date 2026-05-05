# repository-scope Specification

## Purpose
TBD - created by archiving change stable-v1-cleanup. Update Purpose after archive.
## Requirements
### Requirement: Fork 独立分叉模式

本仓库 SHALL 是 `hsliuping/TradingAgents-CN` 的**独立分叉**，**不再定期** `git pull upstream/main`。任何上游新功能 / 修复都通过手动 cherry-pick 单独决策引入，不批量 merge。

CLAUDE.md / docs/USAGE.md MUST 反映此状态——不在文档中建议配置 `upstream` remote 或定期同步流程。

#### Scenario: AI 助手或新开发者读 CLAUDE.md

- **WHEN** AI 助手或新开发者打开 `CLAUDE.md` 寻找"如何与上游同步"
- **THEN** 文档明确说明本 fork 是独立分叉，不应建议 `git remote add upstream` 或 `git merge upstream/main`
- **AND** 不出现"定期同步上游"相关流程

### Requirement: 平台支持范围 — 仅 macOS

本 fork SHALL 仅支持在 macOS（Apple Silicon arm64）平台运行。**MUST NOT** 包含 Windows 平台特定的脚本 / 文档 / 配置。

仓库代码 MUST NOT 含：
- `*.ps1` / `*.bat` / `*.cmd` 脚本（Windows shell）
- `scripts/portable/` 或 `scripts/windows-installer/` 目录
- 任何标题或文件名含 Windows / windows-installer / portable 的 docs

#### Scenario: 仓库根 grep Windows 痕迹

- **WHEN** 在仓库根（排除 `.venv` / `.git` / `node_modules` / `frontend/node_modules`）执行 `find . \( -name "*.ps1" -o -name "*.bat" -o -name "*.cmd" \)`
- **THEN** 命中数为 0

#### Scenario: docs 中 Windows 文档

- **WHEN** 在 `docs/` 目录 `find -iname "*windows*"`
- **THEN** 命中数为 0

### Requirement: 仅保留实际使用的运行时配置

本 fork SHALL 只保留**实际启动用的** runtime 配置文件。废弃 / 未启用 / 上游为多场景准备的配置 MUST 删除。

具体保留：

- `docker-compose.yml`（本地 build 模式 — 唯一用的 docker compose 文件）
- `docker-compose.override.yml`（本地端口覆盖，git 不可见）

具体删除：

- `docker-compose.hub.nginx.yml` / `docker-compose.hub.nginx.arm.yml`（上游 docker hub 镜像 + nginx 反代部署，本 fork 不用）
- `nginx/` 目录（仅给 hub.nginx 变体用）
- `install/` 目录（上游 db config export 快照）

#### Scenario: docker compose 变体清单

- **WHEN** 在仓库根 `ls docker-compose*.yml`
- **THEN** 仅返回 `docker-compose.yml`（`docker-compose.override.yml` 不在 git 里）

### Requirement: Python 依赖范围 — 实际使用

`pyproject.toml` 的 `dependencies` SHALL 只含**实际被代码 import 的**包。已删除功能（streamlit `web/` UI）的依赖 MUST 一并移除。

具体移除：

- `streamlit>=1.28.0`（旧 `web/` UI 已删，且因 chainlit 冲突本来就不可启动）
- `chainlit>=2.5.5`（代码 0 引用，且锁死旧 starlette 引发其他冲突）

#### Scenario: pyproject.toml 不再含 streamlit / chainlit

- **WHEN** `grep -E "^\\s+\"(streamlit|chainlit)" pyproject.toml`
- **THEN** 命中数为 0
- **AND** `[tool.ruff].exclude` / `[tool.pyright].exclude` 不再含 `web` 项

### Requirement: 文档范围 — fork 自维护，不含上游历史叙述

`docs/` 目录 SHALL 只含本 fork 维护的文档。上游历史 release notes / blog / 学习中心残留 MUST 删除。

具体保留：

- `docs/CHANGELOG.md`（fork 自己的 changelog）
- `docs/USAGE.md`（fork 维护者使用手册）
- `docs/ai-context/` 目录（AI prime context）
- `docs/architecture/` / `docs/api/` / `docs/configuration/` 等技术参考文档（功能性，非历史叙述）

具体删除：

- `docs/releases/`（上游 release notes，fork 不发 release）
- `docs/blog/`（上游 blog post，叙述性历史）
- `docs/learning/`（学习中心 docs）
- `docs/paper/`（学习中心 paper 资源 / 或模拟交易设计 paper — 用户决策"全删"）
- `docs/blog/2025-11-15-learning-center-and-compliance-updates.md`（学习中心专题，已被 docs/blog 整目录删覆盖）
- 各种 Windows-only 故障排查 docs（合并入"Requirement: 平台支持范围"）

#### Scenario: docs 子目录范围

- **WHEN** `ls docs/` 不含 `releases` / `blog` / `learning` / `paper` 子目录
- **AND** `find docs -name "*windows*" -iname "*portable*"` 命中 0
- **THEN** 范围合规

### Requirement: 示例 / 旧版本测试 不保留

本 fork SHALL 不保留上游的 `examples/` 演示代码与 `tests/<旧版本号>/` 历史测试快照。需要参考实现时通过 `git log --all -- <path>` 找回。

具体删除：

- `examples/`（30 个 .py demo）
- `tests/0.1.14/`（旧版本快照）

#### Scenario: examples 与旧测试目录

- **WHEN** `ls examples 2>/dev/null` 与 `ls tests/0.1.14 2>/dev/null`
- **THEN** 都返回 "No such file or directory"

