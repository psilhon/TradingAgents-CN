# daily-rec-multi-config — Tasks

> 阶段划分按项目三阶段流程。后端先于前端；MongoDB 迁移顺序锁死（见 task 4）。

## 1. 调研现状（实施前确认）

- [x] 1.1 复核 `app/services/daily_recommendation_service.py` 当前函数边界
- [x] 1.2 复核 `app/routers/daily_recommendation.py` 路由
- [x] 1.3 复核 `app/services/scheduler_service.py` 中每日推荐 job 及注册调用点
- [x] 1.4 确认 `daily_recommendations` 集合现有索引（`_persist_initial` 内 `date` 唯一索引）

## 2. 配置存储层改造（service）

- [x] 2.1 `_CONFIG_PATH` 改为 `_CONFIG_DIR = config/daily_recommendations/`（+ `_LEGACY_CONFIG_PATH`）
- [x] 2.2 移除 `_SAFE_DEFAULT`（多配置下无单一「默认配置」概念）
- [x] 2.3 新增 `_new_config_id()`：`secrets.token_hex(4)` 生成 8 位十六进制串
- [x] 2.4 `_validate_config()`：增 `name` 非空校验；移除 `enabled` 校验
- [x] 2.5 新增 `list_configs()`：扫描目录返回所有配置（按 name 排序）
- [x] 2.6 改造 `load_config(config_id)`：按 id 读单文件（id 非法 ValueError / 缺失 FileNotFoundError）
- [x] 2.7 新增 `create_config(cfg)`：生成 id、写文件、返回标准配置 dict
- [x] 2.8 新增 `update_config(config_id, cfg)`：校验后覆盖写
- [x] 2.9 新增 `delete_config(config_id)`：仅删文件（不动结果文档）
- [x] 2.10 新增 `migrate_legacy_config()`：旧单文件 → 目录，名「默认配置」，删旧文件，丢 `enabled`
- [x] 2.11 `app/main.py` lifespan 内、`init_db()` 后调用 `migrate_legacy_config()`

## 3. 配置 CRUD API

- [x] 3.1 删除单数 `GET/PUT /api/daily-recommendations/config`
- [x] 3.2 `GET /configs`：列出所有配置
- [x] 3.3 `POST /configs`：新建，返回标准配置
- [x] 3.4 `GET /configs/{id}`：取单个
- [x] 3.5 `PUT /configs/{id}`：更新（校验失败 400，不存在 404）
- [x] 3.6 `DELETE /configs/{id}`：删除
- [x] 3.7 新增 `GET /result-configs`：历史结果出现过的配置（去重，含已删除）

## 4. 结果存储 / MongoDB 索引迁移（顺序锁死）

- [x] 4.1 `_ensure_result_indexes`：回填缺 `config_id` 的旧文档为 `legacy` / `迁移前历史`
- [x] 4.2 回填后删除旧的 `date_1` 单字段唯一索引
- [x] 4.3 建立 `(date, config_id)` 复合唯一索引
- [x] 4.4 `_persist_initial` 写入 `config_id` + `config_name`
- [x] 4.5 迁移逻辑幂等（三步均可安全重复执行）

## 5. 执行流改造

- [x] 5.1 `run_daily_recommendation(config_id)` 加参数
- [x] 5.2 去掉 `if not cfg.get("enabled"): skip` 守卫
- [x] 5.3 `POST /run` body 加 `config_id`；config_id 不存在返回 400/404
- [x] 5.4 `/run` 查重键由 `(today)` 改为 `(today, config_id)`
- [x] 5.5 `GET /` 加 `config_id` 过滤；`GET /{date}` 加必填 `config_id` 查询参数

## 6. 定时任务下线

- [x] 6.1 删除 `scheduler_service.py` 中 `_register_daily_recommendation_jobs()` 函数
- [x] 6.2 删除其注册调用点
- [x] 6.3 删除 `_run_daily_recommendation()` 包装函数
- [x] 6.4 确认无悬空 import / 引用（`py_compile` 通过）

## 7. 前端 — API client 与配置管理

- [x] 7.1 `dailyRecommendation.ts`：`DailyRecommendationConfig` 加 `id`/`name`、去 `enabled`
- [x] 7.2 `dailyRecommendation.ts`：新增配置 CRUD + `resultConfigs` 方法
- [x] 7.3 `dailyRecommendation.ts`：`run` 带 `config_id`；list/detail 带 `config_id` 参数
- [x] 7.4 `ConfigDrawer.vue`：表单加 `name` 字段
- [x] 7.5 `ConfigDrawer.vue` 改造为配置管理抽屉（左列表新建/选中/删除 + 右编辑表单，单抽屉双栏，避免嵌套 drawer）

## 8. 前端 — 结果页配置选择器与执行入口

- [x] 8.1 `index.vue`：顶部加配置选择器，选项 = 现存配置 + 仅历史中存在的已删除配置（只读标注「已删除」）
- [x] 8.2 选中配置后左侧日期列表只显示该配置历史
- [x] 8.3 「立即生成」执行当前选中配置，触发前 `ElMessageBox` 确认显示配置名
- [x] 8.4 「配置」按钮打开配置管理抽屉
- [x] 8.5 无配置时选择器显示引导提示、「立即生成」禁用

## 9. 测试

- [x] 9.1 `test_daily_recommendation_config.py`：配置 CRUD（create 生成 id / list / update / delete / 路径穿越防护）
- [x] 9.2 校验用例：`name` 非空必填；stray `enabled`/`id` 被丢弃
- [x] 9.3 迁移用例：legacy 单文件 → 目录、名「默认配置」、删旧文件、幂等
- [x] 9.4 `test_daily_recommendation_service.py`：`run_daily_recommendation(config_id)` 编排 + `(date,config_id)` 复合索引 + 结果文档带 config_id/config_name
- [x] 9.5 `just test`（`-m unit`）全绿（29 个每日推荐 unit test，全套 161 passed）

## 10. 文档与收口验证

- [x] 10.1 `docs/ai-context/project-structure.md` 加 `config/daily_recommendations/` 目录
- [x] 10.2 `docs/ai-context/architecture.md`：经查每日推荐功能本就未在该文档出现，无既有执行流描述可更新；新增整节属本 change 范围外，跳过
- [x] 10.3 `docs/USAGE.md`：同上，每日推荐本就不在 USAGE，跳过新增
- [x] 10.4 `docs/CHANGELOG.md` `[Unreleased]` 加 `### Changed` 条目
- [x] 10.5 `just ci` 全绿（lint + typecheck + test，161 passed）
- [ ] 10.6 后端启动验证 + `POST /run` 手动触发验证（用户执行）
- [ ] 10.7 前端验证：配置选择器 / 配置管理 / 立即生成（用户执行）
- [ ] 10.8 archive change → `openspec/changes/archive/<date>-daily-rec-multi-config/`
- [ ] 10.9 应用 spec → `openspec/specs/daily-recommendation/spec.md`
