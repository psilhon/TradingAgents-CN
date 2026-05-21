## 0. Phase 1 cross-check（pre-plan-checklist 已过 — 既有项目骨架全在位）

- [x] 0.1 既有项目骨架（CLAUDE.md / docs/ai-context/ / CHANGELOG / USAGE / .gitignore / ci.yml / .pre-commit-config.yaml）全部 ✅
- [x] 0.2 fork-patch 不动清单（pyproject.toml / vite.config.ts / .pre-commit-config.yaml / ci.yml / .gitignore patch 段）
- [x] 0.3 license boundary：用户在本对话明确授权改 `app/services/favorites_service.py` + `app/routers/favorites.py` + `frontend/src/views/Dashboard/index.vue` + `frontend/src/views/Favorites/index.vue` + `frontend/src/api/favorites.ts`
- [x] 0.4 端口段位 + loopback 不变（本 change 不改网络配置）
- [x] 0.5 HARD-GATE：本地 commit 允许；push 到 feat/** 分支需对话期再说
- [x] 0.6 guard-proprietary hook marker `openspec/changes/.implementing` 已写为 `2026-05-21-watchlist-limit-and-ordering`

## 1. OpenSpec scaffolding — commit 1

- [x] 1.1 创建 `openspec/changes/2026-05-21-watchlist-limit-and-ordering/` 目录
- [x] 1.2 写 `proposal.md`
- [x] 1.3 写 `tasks.md`（本文件）
- [x] 1.4 写 `specs/watchlist-management/spec.md`（新 capability，ADDED Requirements）
- [ ] 1.5 commit（仅 OpenSpec 文件）

## 2. 后端 — favorites_service 数据模型 + limit + reorder + lazy migration — commit 2

- [ ] 2.1 **RED**：写 `tests/test_favorites_limit_contract.py`
  - test_count_favorites_helper（< 10 / == 10 / > 10）
  - test_add_below_limit_ok
  - test_add_at_limit_raises_FavoritesLimitExceededError
  - test_grandfather_existing_over_limit（已有 12 支但 add 第 13 支仍 raise）
  - test_format_favorite_exposes_order_field
- [ ] 2.2 **RED**：写 `tests/test_favorites_reorder_contract.py`
  - test_reorder_full_set_updates_order
  - test_reorder_missing_code_raises_ValueError
  - test_reorder_extra_code_raises_ValueError
  - test_reorder_duplicate_code_raises_ValueError
  - test_get_lazy_migration_backfills_order（旧文档无 order → 按 added_at 回填）
- [ ] 2.3 **GREEN**：改 `app/services/favorites_service.py`
  - 新增 `FavoritesLimitExceededError(Exception)` 自定义异常
  - `FAVORITES_LIMIT = 10` 模块常量
  - 抽 `_count_favorites(user_id) -> int`（覆盖 ObjectId / string user 两条 storage path）
  - `add_favorite` 入口：`if count >= FAVORITES_LIMIT: raise FavoritesLimitExceededError(...)`；favorite_stock dict 加 `order = count`（已 count = 现有数量，新条目 index = count）
  - `_format_favorite` 加 `"order": favorite.get("order")`
  - `get_user_favorites` 增 lazy migration：若任一条目缺 `order` → 按 `added_at` 排序后给每条分配 order=index 并 update 回 mongo；返回时按 order 升序
  - 新增 `reorder_favorites(user_id, ordered_codes: list[str]) -> int`：先 count + 读现有 codes 集合 → 与 ordered_codes 比较（缺/多/重复 → ValueError）→ 按 ordered_codes 顺序 update 每条 order（mongo `$set` with arrayFilters per element）
- [ ] 2.4 跑 contract tests PASS
- [ ] 2.5 跑既有 `tests/test_favorites_*` 无回归
- [ ] 2.6 ruff / format / pyright 0 errors
- [ ] 2.7 commit

## 3. 后端 — favorites router 409 + /reorder endpoint — commit 3

- [ ] 3.1 **RED**：扩 `tests/test_favorites_limit_contract.py` + 新 `tests/test_favorites_router_reorder.py`
  - test_router_post_returns_409_on_limit
  - test_router_reorder_endpoint_ok
  - test_router_reorder_missing_code_returns_400
- [ ] 3.2 **GREEN**：改 `app/routers/favorites.py`
  - `POST /` try/except 捕获 `FavoritesLimitExceededError` → `HTTPException(status_code=409, detail="...")`
  - 新增 `PUT /reorder`：Pydantic body model `ReorderRequest(order: list[str])`，调 `favorites_service.reorder_favorites(...)`，ValueError → 400
- [ ] 3.3 PASS + lint + typecheck
- [ ] 3.4 commit

## 4. 前端 — favorites.ts api + reorder 调用 — commit 4

- [ ] 4.1 **GREEN**：改 `frontend/src/api/favorites.ts`
  - 新增 `reorder(orderedCodes: string[]): Promise<ApiResponse>` 方法 → `PUT /api/favorites/reorder`
  - 类型：FavoriteItem 加 `order?: number`
- [ ] 4.2 `cd frontend && npm run type-check` 0 errors
- [ ] 4.3 commit（与 task 5 合并为一个 frontend commit，先不单独 commit）

## 5. 前端 — Dashboard watchlist 滚动 + 排序 + 拖拽 — commit 4

- [ ] 5.1 **GREEN**：改 `frontend/src/views/Dashboard/index.vue`
  - watchlist-list CSS：`max-height: 360px; overflow-y: auto`；自定义 scrollbar 样式（与既有 `.scroll-body` 一致）
  - 列表头加排序 select `<el-select size="small">`：custom / chg_desc / chg_asc / code_asc，model 绑定 `watchlistSortMode` ref，默认 `'custom'`
  - 新增 computed `sortedFavoriteStocks` 按 mode 返回不同排序：custom → 按 favoriteStocks 原顺序（已按 order 升序，后端已保证）；chg_desc/asc → 按 change_percent；code_asc → 按 stock_code
  - watchlist-item v-for 改用 sortedFavoriteStocks
  - 引入 sortablejs (动态 import in onMounted)：仅 sortMode='custom' 时 enable；onChange handler 调用 favoritesApi.reorder(newOrderCodes)；失败 revert favoriteStocks 到 PUT 前快照
  - 整行 `:class="{ 'is-draggable': watchlistSortMode === 'custom' }"`；CSS `.is-draggable { cursor: grab; }`
  - 左侧 hover 显示 ⋮⋮ icon（仅 is-draggable 时）
  - 「管理 →」按钮加 `:disabled="favoriteStocks.length >= 10"` + el-tooltip
- [ ] 5.2 `cd frontend && npm run type-check` 0 errors
- [ ] 5.3 grep scripts/check-data-truthfulness.sh 0 命中（防 regression）
- [ ] 5.4 commit（含 task 4）

## 6. 前端 — Favorites 页 add 入口防呆 — commit 5

- [ ] 6.1 **GREEN**：改 `frontend/src/views/Favorites/index.vue`
  - 检查 add 按钮存在；若 favoriteStocks.length >= 10 disabled + tooltip
  - 若 add 操作 catch 到 409 → el-message-box 提示「已达 10 支上限，请先移除」
- [ ] 6.2 type-check 0 errors
- [ ] 6.3 commit

## 7. CHANGELOG hotfix entry — commit 6

- [ ] 7.1 `docs/CHANGELOG.md` `[Unreleased]` 加 `### Added` 段：「**自选股管理升级**」概述（10 支上限 + 滚动 + 排序模式 + 拖拽持久化 + 新 capability watchlist-management）
- [ ] 7.2 commit

## 8. 验证 + Archive — commit 7

- [ ] 8.1 `just ci` 通过
- [ ] 8.2 `scripts/check-data-truthfulness.sh` 0 命中
- [ ] 8.3 `cd frontend && npm run type-check` 0 errors
- [ ] 8.4 删除 `openspec/changes/.implementing` marker
- [ ] 8.5 Archive：mv change → `openspec/changes/archive/YYYY-MM-DD-watchlist-limit-and-ordering`
- [ ] 8.6 Spec sync：mv `specs/watchlist-management/spec.md` → `openspec/specs/watchlist-management/spec.md`（新 capability，无 merge 冲突）
- [ ] 8.7 commit archive + spec sync
- [ ] 8.8 给 finishing report + 问用户 push / tag 决策

## 不在本 change 范围（明确 YAGNI）

- 排序模式持久化（local state 即可，刷新回默认）
- 多 watchlist 分组 / 文件夹
- 自选股标签 / 笔记重构
- 拖拽到 trash 删除手势
- 移动端拖拽手势优化
- 跨设备实时同步（自定义顺序刷新可见即可）
- mongo 历史数据回填脚本（lazy migration 第一次 GET 触发）
- favorites schema 完整 Pydantic 化（保留 dict-based 兼容现有写入路径）

## 测试覆盖小结

| 区域 | 文件 | marker |
|---|---|---|
| favorites limit | `tests/test_favorites_limit_contract.py` | `@pytest.mark.unit` |
| favorites reorder + lazy migration | `tests/test_favorites_reorder_contract.py` | `@pytest.mark.unit` |
| favorites router 409 + reorder endpoint | `tests/test_favorites_router_reorder.py` | `@pytest.mark.unit` |
| 前端 | type-check + 人工 review | - |
