## 1. 删除路由与页面

- [ ] 1.1 删除 `frontend/src/router/index.ts` 第 118-149 行的 `/learning` 路由配置（含 3 个 child route：`LearningHome` / `LearningCategory` / `LearningArticle`）
- [ ] 1.2 `git rm -r frontend/src/views/Learning/` 整个目录（含 `index.vue` / `Category.vue` / `Article.vue`）

## 2. 清理菜单与入口

- [ ] 2.1 编辑 `frontend/src/components/Layout/SidebarMenu.vue`，删除"学习中心"菜单项（grep `学习中心` 找具体行）
- [ ] 2.2 编辑 `frontend/src/views/Dashboard/index.vue`，若含学习中心 quick link 则一并删除（先 grep `Learning|学习` 定位）

## 3. 验证残留

- [ ] 3.1 `grep -rln "Learning\|学习中心" frontend/src` 应为 0 命中（确保无残留 import / route name / link）
- [ ] 3.2 `cd frontend && npm run type-check` 应通过（删除后无 TS 类型错误）
- [ ] 3.3 浏览器手测：登录后菜单无"学习中心"项

## 4. 验收

- [ ] 4.1 浏览器直接访问 `http://localhost:54300/learning` 应跳转到 404 / 首页（路由不再匹配）
- [ ] 4.2 浏览器 console 无 error / warning
- [ ] 4.3 主菜单 + Dashboard 首页所有链接可点击且正确跳转

## 5. 文档与收口

- [ ] 5.1 更新 `docs/CHANGELOG.md` `[Unreleased]` 加 `### Removed` 段：`移除前端"学习中心"模块（路由 / 视图 / 菜单 / 首页 quick link）`
- [ ] 5.2 commit + push（用户 1-click HARD-GATE 守门）—— commit message 用 `feat(frontend): remove 学习中心 module` 前缀
- [ ] 5.3 `openspec archive remove-learning-center` 归档本 change
