## ADDED Requirements

### Requirement: Watchlist 数量上限 10 支

每个 user 的自选股数量 MUST 上限 **10** 支。

- 后端 `favorites_service.add_favorite` 入口 MUST 校验当前数量；`count >= 10` 时 MUST raise `FavoritesLimitExceededError`（自定义异常）。
- 后端 `POST /api/favorites/` MUST 把 `FavoritesLimitExceededError` 转 HTTP `409 Conflict`，detail 文案「已达自选股上限 10 支，请先移除」。
- 前端「添加自选」入口 MUST 在 `favoriteStocks.length >= 10` 时 disable + tooltip 提示；若用户绕过前端（API 直调）触发 409 → MUST 用 `el-message-box` / `el-notification` 明确告知上限。
- **Grandfather**：现有用户已 > 10 支的 MUST 保留不强删；但 add 仍按 count >= 10 拒绝。

理由：watchlist UX 设计——超过 10 支用户无法"快速扫一眼最关心的股"，反而成为弱版的全市场筛选器；产品定位需要硬约束。

#### Scenario: count < 10 时正常 add

- **WHEN** user 当前 N 支自选股，N < 10
- **AND** 调 `add_favorite(user_id, "002428")`
- **THEN** 返回成功，文档加 1 条；新条目 `order = N`

#### Scenario: count == 10 时拒绝 add

- **WHEN** user 当前已有 10 支自选股
- **AND** 调 `add_favorite(user_id, "002428")`
- **THEN** raise `FavoritesLimitExceededError`
- **AND** 不写 mongo

#### Scenario: count > 10 时同样拒绝（grandfather）

- **WHEN** user 当前已有 12 支自选股（早期数据）
- **AND** 调 `add_favorite(user_id, "002428")`
- **THEN** raise `FavoritesLimitExceededError`
- **AND** 已有 12 支文档不被强删（read 仍返回全部 12 条）

#### Scenario: router 转 409

- **WHEN** POST `/api/favorites/` 触发 `FavoritesLimitExceededError`
- **THEN** response status code = 409
- **AND** body `{"detail": "已达自选股上限 10 支，请先移除"}`

### Requirement: Watchlist 自定义顺序持久化

mongo `user_favorites.favorites[]`（或 `users.favorite_stocks[]` for ObjectId user）每条 MUST 含 `order: int` 字段；read 时按 `order` 升序排。

- `add_favorite` MUST 给新条目分配 `order = current_count`（追加末尾）
- `remove_favorite` MUST NOT 重新编号剩余条目（gap 无碍，保持稳定）
- 新增 `reorder_favorites(user_id, ordered_codes: list[str])` 方法：
  - ordered_codes MUST 与现有 codes 集合**完全一致**（数量相等 + 无缺失 + 无多余 + 无重复）
  - 不一致 MUST raise `ValueError`
  - 一致时按 ordered_codes 顺序更新每条 `order` 字段（mongo arrayFilters per element）
- 新增 `PUT /api/favorites/reorder` endpoint：body `{"order": ["000001", "002428", ...]}`，ValueError → HTTP 400
- `_format_favorite` MUST 透出 `order` 字段供前端使用

理由：用户拖拽排序的状态必须跨设备同步；本地 state 不足以满足"我看自选股第一只总是关注的那只"的产品体感。

#### Scenario: add 新条目分配 order

- **WHEN** user 当前已有 3 条（order: 0, 1, 2）
- **AND** 调 `add_favorite(user_id, "002428")`
- **THEN** 新条目 `order = 3`（追加末尾）

#### Scenario: remove 不重新编号

- **WHEN** user 当前 5 条（order: 0,1,2,3,4），删除 order=2 的条目
- **THEN** 剩余条目 order 保持 0,1,3,4（gap 在 2）
- **AND** read 按 order 升序返回 4 条

#### Scenario: reorder 完整数组正确更新

- **WHEN** user 当前 3 条 codes = ["000001", "002428", "300124"]
- **AND** 调 `reorder_favorites(user_id, ["002428", "300124", "000001"])`
- **THEN** 002428 → order=0, 300124 → order=1, 000001 → order=2
- **AND** read 按新顺序返回

#### Scenario: reorder codes 不一致 raise ValueError

- **WHEN** user 当前 3 条 codes = ["000001", "002428", "300124"]
- **AND** 调 `reorder_favorites(user_id, ["000001", "002428"])`（缺 300124）
- **THEN** raise `ValueError("ordered_codes 与现有 codes 集合不一致")`
- **AND** 不更新任何条目 order

#### Scenario: reorder 含重复 code raise ValueError

- **WHEN** 调 `reorder_favorites(user_id, ["000001", "002428", "000001"])`
- **THEN** raise `ValueError("ordered_codes 含重复 code")`

#### Scenario: router PUT reorder ok

- **WHEN** PUT `/api/favorites/reorder` body `{"order": [...完整 codes...]}`
- **THEN** status 200，response `{"success": true, "data": {"updated": N}}`

#### Scenario: router PUT reorder 不一致返 400

- **WHEN** PUT `/api/favorites/reorder` body 缺/多/重复 code
- **THEN** status 400，detail 描述不一致原因

### Requirement: 旧文档 backward compat lazy migration

`get_user_favorites` MUST 兼容无 `order` 字段的旧 mongo 文档（v1.3.1 之前所有 favorites 数据）：

- 读取时检测：若任一条目缺 `order` 字段（视为旧文档）
- MUST 按 `added_at` 排序（升序，最早添加在前）
- MUST 给每条按排序后的 index 分配 `order = index`
- MUST update 回 mongo 持久化（避免每次 read 重复 migrate）
- MUST 兼容两条 storage path（`users.favorite_stocks` ObjectId user / `user_favorites.favorites` string user）
- migration 幂等：再次 read 时所有条目都有 order，无需再 migrate

理由：避免一刀切的批量迁移脚本；用户访问 watchlist 时按需 migrate，渐进推进；幂等保证安全。

#### Scenario: 全部旧文档 lazy migrate

- **WHEN** mongo `user_favorites.favorites` 有 5 条全部缺 `order` 字段，`added_at` 升序为 [t1, t2, t3, t4, t5]
- **AND** 调 `get_user_favorites(user_id)`
- **THEN** 返回 5 条，对应 order = [0, 1, 2, 3, 4]
- **AND** mongo 文档已持久化 order 字段
- **AND** 下次 read 不再触发 migration（all conditions met）

#### Scenario: 部分缺 order 文档 lazy migrate

- **WHEN** mongo `user_favorites.favorites` 有 5 条，其中 3 条有 order=[0,1,2]，2 条缺 order
- **AND** 调 `get_user_favorites(user_id)`
- **THEN** 缺 order 的 2 条按 added_at 排序后分配 order = [3, 4]（追加在末尾）
- **AND** mongo 持久化

#### Scenario: 全部有 order 不触发 migration

- **WHEN** mongo 所有条目都有 order 字段
- **AND** 调 `get_user_favorites(user_id)`
- **THEN** 直接按 order 升序返回，不 update mongo

### Requirement: 前端 Dashboard watchlist UX

`frontend/src/views/Dashboard/index.vue` watchlist panel MUST：

- `.watchlist-list` 容器 `max-height: 360px` + `overflow-y: auto` + 自定义细 scrollbar 样式（与项目 `.scroll-body` 一致）——超 6 行可滚动而非撑高 panel
- 列表头新增小排序 select：
  - 「自定义」（默认）—— 按后端 order 升序，allow drag
  - 「涨跌幅↓」—— client-side 按 `change_percent` 降序
  - 「涨跌幅↑」—— 升序
  - 「代码↑」—— 按 `stock_code` 字典序
  - select 状态本地 ref，**不持久化**（刷新回默认）
- 仅「自定义」模式启用拖拽（用 sortablejs，参考 `SortableDataSourceList.vue` 实现）
- 拖完成立即 `PUT /api/favorites/reorder`；失败 revert UI 顺序 + `el-message.error("排序保存失败，已回退")`
- 整行 `cursor: grab`（仅 draggable 模式）；左侧 hover 显 ⋮⋮ icon（仅 draggable 模式）
- 「管理 →」按钮在 `favoriteStocks.length >= 10` 时 disable + el-tooltip 提示"已达 10 支上限"

#### Scenario: 默认自定义模式按 order 排

- **WHEN** 用户首次进 Dashboard，select 默认「自定义」
- **THEN** watchlist 按 favoriteStocks (即 backend `order` 升序) 渲染
- **AND** 每行 cursor: grab，sortable enable

#### Scenario: 切换涨跌幅↓不影响后端

- **WHEN** 用户切换 select 到「涨跌幅↓」
- **THEN** watchlist 按 change_percent 降序 client-side 排序
- **AND** 拖拽 disable（cursor: default + ⋮⋮ icon 不显）
- **AND** 不调 PUT reorder（仅本地 view）

#### Scenario: 拖拽成功

- **WHEN** select=自定义，用户拖动条目改变顺序
- **THEN** UI 立即反映新顺序
- **AND** 同步 PUT `/api/favorites/reorder` body `{"order": newCodes}`
- **AND** 后端返 200，UI 状态保持

#### Scenario: 拖拽失败 revert

- **WHEN** 拖拽后 PUT 失败（网络错误 / 服务端 500）
- **THEN** UI 顺序 revert 到拖前的快照
- **AND** 显示 `el-message.error("排序保存失败，已回退")`

#### Scenario: 滚动条按需出现

- **WHEN** favoriteStocks.length <= 6（约 360px 内放得下）
- **THEN** 容器无滚动条
- **WHEN** favoriteStocks.length > 6
- **THEN** 容器内出现垂直 scrollbar（细样式与项目其他 `.scroll-body` 一致）

#### Scenario: 已达上限 manage 按钮 disable

- **WHEN** favoriteStocks.length >= 10
- **THEN** 「管理 →」按钮 `disabled=true`
- **AND** hover 显 el-tooltip「已达 10 支上限，请先移除」
