# daily-rec-multi-config

> 每日推荐从单一全局配置改为多个命名配置：目录多文件存储；16:30 定时任务下线改全手动；执行时选择配置。

## Why

每日推荐当前只有一个全局配置 `config/daily_recommendation.json`，由 16:30 的 APScheduler cron 自动用它跑一次，结果以 `date` 为唯一键存 MongoDB（每天一份）。

局限：

- 无法保存多套选股策略（如「质量+价值」「成长」「行业主题」）并按需切换。
- 每天只能产出一种推荐 —— 改一次配置就覆盖上一套思路。

目标：支持**多个命名配置**，去掉自动定时任务，每次**手动执行时选一个配置**跑。

## What Changes

### 后端

- **配置存储**：`config/daily_recommendation.json`（单文件）→ `config/daily_recommendations/<id>.json`（目录多文件）。`<id>` = 创建时生成的 8 位随机串，不展示给用户。
- **配置结构**：`{id, name, screening, analysis}` —— **去掉 `enabled` 字段**（所有配置永远可选执行）。
- `app/services/daily_recommendation_service.py`：
  - `_CONFIG_PATH`（单文件）→ `_CONFIG_DIR`（目录）。
  - `_SAFE_DEFAULT` 去掉 `enabled`。
  - 新增 `list_configs()` / `load_config(config_id)` / `create_config(cfg)` / `update_config(config_id, cfg)` / `delete_config(config_id)` / `migrate_legacy_config()`。
  - `_validate_config()` 增 `name` 非空校验，去 `enabled` 校验。
  - `run_daily_recommendation(config_id)` 加参数；去掉 `if not cfg.get("enabled"): skip` 守卫。
  - `_persist_initial` 写入 `config_id` + `config_name`。
- `app/routers/daily_recommendation.py`：
  - 替换单数 `GET/PUT /config` → `/configs` CRUD 五个端点。
  - `POST /run` body 加 `config_id`，查重键由 `(today)` 改为 `(today, config_id)`。
  - `GET /` 与 `GET /{date}` 增 `config_id` 过滤参数。
- **结果集合 `daily_recommendations`**：删 `date` 唯一索引，建 `(date, config_id)` 复合唯一索引；旧文档回填 `config_id="legacy"` / `config_name="迁移前历史"`（**先回填再建索引**）。
- `app/services/scheduler_service.py`：删 `_register_daily_recommendation_jobs()` 注册 + 调用点 + `_run_daily_recommendation()` 包装 —— 16:30 cron 整体下线。

### 前端

- `frontend/src/api/dailyRecommendation.ts`：配置 CRUD 方法；`run(config_id)`；list/detail 带 `config_id`；`DailyRecommendationConfig` interface 加 `id`/`name`、去 `enabled`。
- `frontend/src/views/DailyRecommendation/index.vue`：
  - 顶部加配置选择器 —— 现存配置（可执行/可编辑）+ 仅存在于历史结果中的已删除配置（只读，标注「已删除」）。
  - 选中配置后左侧日期列表只显示该配置历史。
  - 「立即生成」执行当前选中配置（确认弹窗显示配置名）。
  - 「配置」按钮打开配置管理抽屉。
- 配置管理：新增管理抽屉组件 —— 左侧配置列表（新建/选中/删除），右侧复用 `ConfigDrawer.vue` 编辑选中项。
- `ConfigDrawer.vue`：表单加 `name` 字段。

### 测试

- 扩展 `tests/test_daily_recommendation_config.py`：配置 CRUD / 校验（`name` 非空、不再有 `enabled`）/ legacy 单文件→目录迁移 / 带 `config_id` 的 run 查重。
- 前端无测试框架，手动验证。

### 文档

- `docs/CHANGELOG.md` `[Unreleased]` 加条目。
- `docs/USAGE.md` 补多配置使用说明。
- `docs/ai-context/project-structure.md` 加 `config/daily_recommendations/` 目录。
- `docs/ai-context/architecture.md` 更新每日推荐执行流（cron 下线、手动选配置）。

## Out of Scope

- **配置启用/停用（归档）机制**：已明确删 `enabled`，所有配置永远可执行。
- **定时自动执行**：16:30 cron 下线，本 change 不提供任何自动调度。未来如需「定时跑某配置」另开 change。
- **同一配置同一天重复执行 / 覆盖**：维持现状查重语义 —— `(date, config_id)` 已存在则拒绝触发。
- **配置导入 / 导出、配置版本历史**。
- **跨配置结果对比视图**。
- **港股 / 美股**：沿用现有 A 股限定。

## Impact

**改动范围**：

- `app/services/daily_recommendation_service.py` 配置层单→多重构（~+120 行）。
- `app/routers/daily_recommendation.py` 路由重构（~+60 行）。
- `app/services/scheduler_service.py` 删 cron（~-35 行）。
- MongoDB 索引迁移（回填 `config_id` + 改复合唯一索引）。
- `frontend/src/api/dailyRecommendation.ts`（~+40 行）。
- `frontend/src/views/DailyRecommendation/index.vue`（顶部选择器 + 生成/配置入口）。
- `frontend/src/views/DailyRecommendation/ConfigDrawer.vue`（加 `name` 字段）。
- 新增前端配置管理组件（~120 行）。
- `tests/test_daily_recommendation_config.py` 扩展。

**风险**：中

- 触及 `app/` + `frontend/` 专有授权代码（已获本对话明确授权）。
- MongoDB 索引迁移顺序坑：**必须先回填 `config_id` 再建复合唯一索引**，否则旧文档缺字段导致 null 重复、建索引失败。
- 配置目录迁移 `migrate_legacy_config()` 须先于任何 `load_config` 执行。
- `pre-commit` STRICT，改完须过 ruff / format / pyright，0 error 才能 commit。

**收益**：

- 可保存多套选股策略并按需切换。
- 执行入口清晰（手动选配置），去掉「每天只有一种推荐」限制。

## 依赖与时序

**前置**：无 capability 依赖。

**时序约束（实施期）**：

1. MongoDB：回填旧结果文档 `config_id="legacy"` → 删旧 `date` 唯一索引 → 建 `(date, config_id)` 复合唯一索引。三步顺序锁死。
2. `migrate_legacy_config()` 须在服务初始化最早期、任何 `load_config` 调用前执行。
3. 后端 `/configs` 路由先于前端 API 改造就绪。

**后续**：如需恢复定时执行，另开 change（可基于本 change 的 `run_daily_recommendation(config_id)`）。
