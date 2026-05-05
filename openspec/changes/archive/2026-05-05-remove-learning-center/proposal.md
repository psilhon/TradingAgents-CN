## Why

上游 `frontend/src/views/Learning/` 提供"学习中心"模块（多智能体框架教学 / 提示词工程 / 模型选择等静态文档站点）。本 fork 定位是**个人二次开发用的实战平台**，不需要保留这个学习内容站点——它占菜单一格、增加路由复杂度、Dashboard 首页可能也有 quick link，对当前用户毫无价值。

## What Changes

- **REMOVED**：删除前端学习中心模块（router / views / menu / quick links）
- **保留**：上游 `tradingagents/` 主代码不动；后端 API 无 learning 相关端点（grep 0 命中），无需改后端 / 数据库

无 BREAKING change（学习中心是独立子模块，移除不影响其它功能）。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无。本次为 **fork-local cleanup**——上游"学习中心"功能从未规范化为 OpenSpec capability，本项目也不打算 retroactive 立 spec。删除范围仅限 frontend 静态资源 + 路由配置，不涉及 spec 层面行为变更。

## Impact

**前端 ~5 个文件**（具体 line/file 见 `tasks.md`）：

| 文件 | 改动 |
|---|---|
| `frontend/src/router/index.ts` | 删除 line 118-149 的 `/learning` 路由 + 3 个 child route |
| `frontend/src/views/Learning/{index,Category,Article}.vue` | 整个目录删除 |
| `frontend/src/components/Layout/SidebarMenu.vue` | 删除"学习中心"菜单项 |
| `frontend/src/views/Dashboard/index.vue` | 删除首页 quick link（如有）|

**无影响**：

- 后端 `app/`：grep `learning` 0 命中
- 数据库：无 learning 相关 collection
- 上游同步：删除上游文件后，未来 `git pull upstream/main` 若上游也改了 `Learning/`，可能 conflict——但学习中心是低频维护模块（看 `git log frontend/src/views/Learning/` 历史），冲突概率低
