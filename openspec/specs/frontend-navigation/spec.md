# frontend-navigation Specification

## Purpose
TBD - created by archiving change remove-learning-center. Update Purpose after archive.
## Requirements
### Requirement: 前端主导航模块清单

前端 SHALL 提供以下顶级导航模块（与 `SidebarMenu.vue` + `router/index.ts` 配置一致），且 MUST NOT 提供"学习中心"模块（fork 已删除上游静态学习内容站点）：

- 仪表板（Dashboard）
- 股票分析
- 股票筛选
- 自选股管理
- 个股详情
- 模拟交易
- 配置中心
- 使用统计
- 批量分析
- 定时任务

#### Scenario: 用户登录后查看主菜单

- **WHEN** 用户使用 admin 账号成功登录进入主界面
- **THEN** 主菜单（左侧 SidebarMenu）显示上述 10 个模块项
- **AND** 主菜单不显示"学习中心"项
- **AND** 不显示任何 `/learning/*` 路由入口

#### Scenario: 用户直接访问已删除的 learning URL

- **WHEN** 用户在地址栏输入 `http://localhost:54300/learning` 或子路径（如 `/learning/category` / `/learning/article/:id`）
- **THEN** 浏览器跳转到默认 fallback（router 的 `/:pathMatch(.*)*` 404 页或重定向到首页）
- **AND** 页面不渲染原 `Learning/*.vue` 组件
- **AND** 浏览器 console 无 module not found 错误

#### Scenario: Dashboard 首页 quick link 不含学习中心

- **WHEN** 用户进入 Dashboard 首页（`/`）
- **THEN** 首页 quick link / 推荐入口区域不显示指向 `/learning/*` 的链接
- **AND** 所有显示的 quick link 都指向上述 10 个模块之一

### Requirement: 前端代码无学习中心残留

前端代码库 MUST NOT 包含任何指向已删除"学习中心"模块的 import / 引用 / 字符串字面量（例外：CHANGELOG / git history / 历史 docs 中的叙述性文本可保留）。

#### Scenario: grep 检查无残留

- **WHEN** 在 `frontend/src/` 目录执行 `grep -rln "Learning\|学习中心" .`
- **THEN** 命中数为 0
- **AND** TypeScript 类型检查（`npm run type-check`）通过无错误

