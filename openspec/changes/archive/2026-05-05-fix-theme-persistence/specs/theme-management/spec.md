## ADDED Requirements

### Requirement: 主题选择本地持久化

用户通过前端 toggle 按钮（`HeaderActions.vue`）或 Settings 页面（`Settings/index.vue`）切换主题（`light` / `dark` / `auto`），主题选择 MUST 立即持久化到浏览器 `localStorage`（key=`app-theme`）。

任何路径的主题切换都 MUST 触发持久化——包括：
- `appStore.toggleTheme()`（toggle 按钮）
- `appStore.setTheme(value)`（Settings 页面下拉选择）

#### Scenario: toggle 切主题后立即持久化

- **WHEN** 用户点击 header 的主题 toggle 按钮
- **THEN** `localStorage.getItem('app-theme')` 返回新选定的主题值（`light` / `dark` / `auto`）
- **AND** `document.documentElement` 的 `dark` class 与新主题一致（dark / auto+系统dark 时存在；light 时不存在）

#### Scenario: Settings 页面切主题后立即持久化

- **WHEN** 用户在 Settings > 外观 页面下拉选择主题并保存
- **THEN** `localStorage.getItem('app-theme')` 返回所选主题值
- **AND** DOM 立即应用新主题（无需刷新）

### Requirement: 主题状态不被后端 user preferences 覆盖

后端 `user.preferences.ui_theme` 字段 MUST NOT 在登录后 / 用户信息刷新后 / 用户更新后被同步到前端 `appStore.theme`。主题状态完全由前端 `localStorage` 主导。

后端字段保留（不删 schema），仅前端不再消费——为未来可选的"多设备主题同步"功能保留 backward compatibility。

#### Scenario: 切到 dark 后路由切换不重置

- **WHEN** 用户切到 dark 主题
- **AND** 用户随后切换到任意其它路由（如从 `/dashboard` 跳到 `/analysis`）
- **THEN** 主题保持 dark
- **AND** `document.documentElement` 仍含 `dark` class
- **AND** localStorage `app-theme` 值仍为 `dark`

#### Scenario: 切到 dark 后任意 API 调用不重置

- **WHEN** 用户切到 dark 主题
- **AND** 前端发起任意触发 user info refresh 的 API 调用（含 login / fetchUserInfo / updateUserInfo）
- **THEN** 主题保持 dark
- **AND** `appStore.theme` 不被 `user.preferences.ui_theme` 覆盖

#### Scenario: 切到 dark 后浏览器刷新不重置

- **WHEN** 用户切到 dark 主题
- **AND** 浏览器执行刷新（F5 / Cmd-R）
- **THEN** 页面重新加载后主题仍为 dark
- **AND** localStorage `app-theme` 值仍为 `dark`

### Requirement: 三种主题循环切换支持

`toggleTheme()` MUST 在 `light` → `dark` → `auto` → `light` 三态间循环切换（与上游 `app.ts:117` 的 themes 数组一致）。

#### Scenario: 完整循环切换

- **WHEN** 当前主题为 light
- **AND** 用户连续点击 toggle 三次
- **THEN** 主题依次切换为 dark / auto / light
- **AND** 每次切换都持久化到 localStorage
