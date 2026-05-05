## Why

用户切换深色主题后，**任何路由切换 / API 调用 / 页面刷新**都会让主题被强制切回浅色。根因已定位：`frontend/src/stores/auth.ts` 的 `syncUserPreferencesToAppStore()` 函数（在 login / fetchUser / updateUser 三处被调）会用后端 `user.preferences.ui_theme`（admin 默认 `light`）强制覆盖 `appStore.theme`，导致用户手动 toggle 的状态被覆盖。

附属 bug：`stores/app.ts:116 toggleTheme()` 改 `this.theme` 但**不写 localStorage**（与 `setTheme()` 不一致），即使去掉后端覆盖，刷新页面也无法持久化。

这是"主题切换"功能的**核心 UX 问题**——用户首次进入产品就会撞到，必须修。

## What Changes

- **MODIFIED**（行为变更）：用户的主题选择**完全本地持久化**（localStorage），不再被后端 user preferences 覆盖
  - `auth.ts:381-383` 删除 `ui_theme` 同步逻辑
  - `app.ts toggleTheme()` 加 `localStorage.setItem('app-theme', ...)` 修复 useStorage 单向绑定 bug
- **不做**：多设备主题同步（即"toggle 也写后端 prefs"的方向延后扩展，记入"延后项"）

无 BREAKING change（用户体验是改善，不影响 API 契约）。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无 OpenSpec capability 层面变更。本次为 **fork-local bug fix**——上游"主题管理"功能从未规范化为 OpenSpec capability，本项目此次不做 retroactive 立 spec（与 `remove-learning-center` 同一原则）。修改局限于 2 个 frontend 文件 4 行代码。

## Impact

**前端 2 个文件**：

| 文件 | 改动 |
|---|---|
| `frontend/src/stores/auth.ts` | 删除 line 381-383 的 `if (prefs.ui_theme) { appStore.setTheme(...) }` 块 |
| `frontend/src/stores/app.ts` | `toggleTheme()` 内调用 `applyTheme()` 后加 `localStorage.setItem('app-theme', this.theme)` |

**无影响**：

- 后端：不动 `app/services/user_service.py` 的 `preferences.ui_theme` 字段（数据保留，仅前端不再 sync）
- 数据库：无 schema 变更
- 用户已有数据：之前 saved 的 `ui_theme` 仍在 mongo，未来若改回多设备同步可复用
