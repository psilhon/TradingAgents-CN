## 1. 移除后端覆盖逻辑

- [x] 1.1 编辑 `frontend/src/stores/auth.ts` 第 381-383 行，删除整个 `if (prefs.ui_theme) { ... }` 块
- [x] 1.2 在 `syncUserPreferencesToAppStore` 函数顶部加注释，说明"主题不再 sync 自后端，由 localStorage 本地持久化"（避免未来开发者再加回来）

## 2. 修复 toggleTheme 持久化

- [x] 2.1 编辑 `frontend/src/stores/app.ts` 的 `toggleTheme()` 方法（line 116-121），在 `this.applyTheme()` 后加一行 `localStorage.setItem('app-theme', this.theme)`
- [x] 2.2 验证 `setTheme()`（line 124-129）已写 localStorage（line 128 已有 ✓，无需改）

## 3. 验证

- [x] 3.1 `cd frontend && npm run type-check` 通过（vue-tsc --noEmit exit 0）
- [x] 3.2 重启 vite dev（HMR 自动生效，未重启）

## 4. 浏览器手测（验收）

- [x] 4.1 登录后初始主题正确
- [x] 4.2 点击 toggle 切到 dark → DOM 加 `.dark` class → 视觉变深色
- [x] 4.3 切换到任意 5 个不同路由 → 主题保持 dark
- [x] 4.4 触发任意 API 调用 → 主题保持 dark
- [x] 4.5 浏览器刷新页面（F5）→ 主题保持 dark
- [x] 4.6 toggle 到 auto → 重复 4.3-4.5 → 主题保持 auto
- [x] 4.7 toggle 到 light → 重复 4.3-4.5 → 主题保持 light
- [x] 4.8 浏览器 DevTools Application > Local Storage：`app-theme` key 值与当前 toggle 状态一致

> 用户反馈："修复成功，现在全局生效了" — 全部验收通过

## 5. 文档与收口

- [x] 5.1 更新 `docs/CHANGELOG.md` `[Unreleased]` 加 `### Fixed` 段
- [x] 5.2 commit + push（用户 1-click HARD-GATE 守门）
- [ ] 5.3 `openspec archive fix-theme-persistence` 归档本 change

## 延后扩展项（不在本 change 范围）

- **多设备主题同步**：toggle 时也 PUT `/api/auth/me` 更新后端 `preferences.ui_theme`，syncUserPreferencesToAppStore 改成"仅首次登录用后端值，之后用 localStorage 优先"。这是 nice-to-have，个人 fork 单设备场景不需要。如需启用，立新 OpenSpec change `theme-multi-device-sync`。
