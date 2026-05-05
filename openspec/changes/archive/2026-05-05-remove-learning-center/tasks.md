## 1. 删除路由与页面

- [x] 1.1 删除 `frontend/src/router/index.ts` 第 117-156 行的 `/learning` 路由配置（含 3 个 child route：`LearningHome` / `LearningCategory` / `LearningArticle`）+ 同时删除 `/paper/:name.md` 兼容重定向（重定向目标已不存在）
- [x] 1.2 `git rm -r frontend/src/views/Learning/` 整个目录（含 `index.vue` / `Category.vue` / `Article.vue`）

## 2. 清理菜单与入口

- [x] 2.1 编辑 `frontend/src/components/Layout/SidebarMenu.vue`，删除"学习中心"菜单项 + 删除未用的 `Reading` icon import
- [x] 2.2 编辑 `frontend/src/views/Dashboard/index.vue`，删除 AI 学习中心推荐卡片（template + script 的 `goToLearning` 函数 + style 的 `.learning-highlight-card` 段 + @media 内 `.learning-highlight-card` 段 + 未用 `Reading` icon import）
- [x] 2.3 边界判断：`Dashboard/index.vue` line 11 welcome subtitle "现代化的多智能体股票分析学习平台" 中"学习平台"是产品定位形容词（非"学习中心"模块），保留

## 3. 验证残留

- [x] 3.1 `grep -rln "Learning\|学习中心" frontend/src` 返回 0 命中
- [x] 3.2 `cd frontend && npm run type-check` 通过（vue-tsc --noEmit 无错误）
- [x] 3.3 浏览器手测：登录后菜单无"学习中心"项

## 4. 验收

- [x] 4.1 浏览器直接访问 `http://localhost:54300/learning` → 显示 404 页面 "页面不存在" + 推荐其他模块（仪表板 / 单股分析 / 股票筛选 / 队列管理）—— 用户截图验证通过
- [x] 4.2 浏览器 DevTools console 无 error（用户无报错反馈）
- [x] 4.3 其他菜单 + Dashboard 首页所有链接可点击且正确跳转（用户无报错反馈）

## 5. 文档与收口

- [x] 5.1 更新 `docs/CHANGELOG.md` `[Unreleased]` 加 `### Removed` 段
- [ ] 5.2 commit + push（用户 1-click HARD-GATE 守门）
- [ ] 5.3 `openspec archive remove-learning-center` 归档本 change
