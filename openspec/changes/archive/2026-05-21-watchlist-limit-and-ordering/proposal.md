## Why

Dashboard 自选股 panel 当前无数量上限 + 无显式排序——用户加多了一屏铺不下硬挤、看不出来排序逻辑（实际按 mongo array push 自然顺序），缺乏 watchlist 该有的"快速扫一眼最关心的股"体验。

需求：
1. **上限 10 支**——超出上限阻止新增（前端按钮 disable + 后端 409 拒绝）
2. **超 6 行滚动**——容器限高 + 自定义 scrollbar
3. **排序模式**——「自定义」（拖拽顺序，默认）/ 涨跌幅↓ / 涨跌幅↑ / 代码↑
4. **自定义顺序持久化**——拖拽顺序写后端 mongo

## What Changes

### 改动 1：数据模型 — mongo `user_favorites.favorites[].order: int`

- mongo doc 每条 favorite 加 `order: int` 字段（升序排）
- backward compat：旧文档无 `order` → service `get_user_favorites` 读取时按 `added_at` 排序后 lazy 回填 `order`，下次 read 已就位
- 新增（`add_favorite`）：`order = max(existing.order) + 1`，追加末尾
- 删除（`remove_favorite`）：**不**重新编号（gap 无碍，靠 array 顺序排）
- 同时兼容**两条 storage path**（既有 fork 设计）：
  - `users.favorite_stocks[]`（ObjectId user）
  - `user_favorites.favorites[]`（string user，主流路径）

### 改动 2：后端 — favorites_service.py + favorites.py

**MODIFIED `app/services/favorites_service.py`**：
- 抽 `_count_favorites(user_id) -> int` helper（覆盖两条 storage path）
- `add_favorite` 入口加 limit 校验：`count >= 10` 时 raise `FavoritesLimitExceededError`（自定义异常，router 转 409）
- `get_user_favorites` 增 lazy migration：缺 `order` 字段的文档按 `added_at` 排序后回填 `order` 并 update mongo
- 新增 `reorder_favorites(user_id, ordered_codes: list[str]) -> int` 方法：按 ordered_codes 顺序更新每条 `order` 字段（mongo `$set` per element via arrayFilters）；ordered_codes 必须与现有 codes 集合一致（缺/多/重复 → ValueError）
- `_format_favorite` 加 `order` 字段透出

**MODIFIED `app/routers/favorites.py`**：
- `POST /` 捕获 `FavoritesLimitExceededError` → `HTTPException(409, "已达自选股上限 10 支，请先移除")`
- 新增 `PUT /reorder`：body `{"order": ["000001","002428",...]}`，调 `reorder_favorites`，code 集合不一致返 400

### 改动 3：前端 — Dashboard watchlist 列表

**MODIFIED `frontend/src/views/Dashboard/index.vue`**：
- watchlist-list 容器加 `max-height: 360px` + `overflow-y: auto` + 自定义 scrollbar 样式
- 列表头新增小 select：「自定义」/「涨跌幅↓」/「涨跌幅↑」/「代码↑」，默认「自定义」
- 引入 sortablejs（参考 `frontend/src/views/Settings/components/SortableDataSourceList.vue` pattern）：仅「自定义」模式启用，拖完成立即 PUT `/api/favorites/reorder`
- 整行 cursor:grab（仅自定义模式），左侧 hover 时显示 ⋮⋮ icon
- 非「自定义」模式按对应字段 client-side 排序（不动后端），select 切换瞬时切换显示顺序
- 失败 revert：reorder PUT 失败时 favoriteStocks ref 回退到 PUT 前的快照 + `el-message.error` 提示

**MODIFIED `frontend/src/api/favorites.ts`**：新增 `reorder(orderedCodes: string[])` 方法

**MODIFIED `frontend/src/views/Favorites/index.vue`**（如有 add 入口）：已达 10 支时 add 按钮 disable + tooltip 提示

### 改动 4：新 capability `watchlist-management`

- 锁定 watchlist 数据模型 + limit 行为 + 排序行为 + lazy migration
- 不与既有已 archive 的 `favorites-performance` 冲突（那个讲 perf；本次讲 UX/数据模型）

### 改动 5：Contract test

- **NEW** `tests/test_favorites_limit_contract.py`：
  - test_add_below_limit_ok（< 10 时 add 返 True）
  - test_add_at_limit_raises（第 11 支 raise FavoritesLimitExceededError）
  - test_grandfather_existing_over_limit（已有 12 支不强删，但禁止新增）
  - test_router_returns_409_on_limit
- **NEW** `tests/test_favorites_reorder_contract.py`：
  - test_reorder_full_set_updates_order（数组完全匹配 → 每条 order 按数组索引）
  - test_reorder_missing_code_raises（数组缺 code → ValueError）
  - test_reorder_extra_code_raises（数组多 code → ValueError）
  - test_reorder_duplicate_code_raises（数组含重复 → ValueError）
  - test_get_lazy_migration_backfills_order（旧文档无 order → 按 added_at 回填）
  - test_format_favorite_exposes_order_field

## Capabilities

- **新建** `watchlist-management`（独立锁定 watchlist 数据模型 + UX 行为）

## Impact

**改动文件**：
- 2 个后端业务文件（favorites_service + favorites router）
- 2 个前端业务文件（Dashboard + Favorites）+ 1 个 api 类型文件
- 2 个新 contract test 文件
- 1 个新 spec 文件
- 1 个 CHANGELOG 段

**视觉变化**：
- watchlist 容器超 6 行可滚动（之前可能撑高 panel / 溢出）
- 顶部新增小排序 select
- 自定义模式下整行可拖
- 已达 10 支时「管理 →」按钮 + 添加流程 disable

**API breaking change**：
- 无新 schema breaking——`favorite_stocks` / `favorites` 数组每条加 `order` 字段，老前端读旧字段不影响
- 新增 `PUT /api/favorites/reorder` endpoint

**风险**：低
- limit 10 是新约束——若现有用户已 > 10 支，grandfather 保留，禁止新增直到删除到 ≤ 10
- lazy migration：第一次访问触发 update_one；幂等可重入
- 排序模式切换 client-side 排序，不污染后端

**收益**：
- 自选股 UX 升级到产品级（限量 + 滚动 + 排序）
- 自定义顺序持久化跨设备同步
- 新 capability 锁定行为，未来扩展（如多 watchlist 分组）有明确边界
