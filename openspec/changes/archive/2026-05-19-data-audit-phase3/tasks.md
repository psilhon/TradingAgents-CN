# data-audit-phase3 — Tasks

> 阶段划分按项目三阶段流程。Phase 1 调研先于实施；MongoDB 迁移顺序锁死（见 task 3）。
> Item 3 字段名统一面最广，排在 Item 1/2 之后做，避免 diff 互相干扰。

## 1. 调研现状（实施前确认）

- [x] 1.1 精确清点 `source` / `data_source` 出现的全部 MongoDB 集合 + `app/` 文件，定统一方向 → **统一为 `data_source`**（仅 `stock_basic_info` 偏离用 `source`）
- [x] 1.2 确认 `stock_basic_info` 当前索引：`code_source_unique` 两处创建点（`app/core/database.py:309` 匿名 `(code,source)` unique + `app/services/basics_sync_service.py:72` 具名 `code_source_unique`）
- [x] 1.3 复核 `database_screening_service` 等靠 `query["source"]=source` 过滤规避重复的代码点 → 详核留 task 3.6
- [x] 1.4 实跑 `/tmp/data_audit.js` 取库当前基线 → `stock_basic_info` 11360 docs（tushare 5517 + akshare 5519 + baostock 324，重复已复发）；负 `ps` 1 条、负 `pe` 1365 条（合法）
- [x] 1.5 定 `data_consistency_checker` 去留 → **删**：318 行全量文件无人 import（死代码）+ 48 行 no-op stub（`manager.py` 调用永远返回「一致」，空转）
- [x] 1.6 定 sanity 阈值 → 拒负 `ps`/`total_mv`/`circ_mv`（数学不可能）；标记 `|pe|` 越界（>1000）告警；**不拒负 `pe`/`pb`**（亏损 / 负净资产为合法）

## 2. Item 1 — 写库前数值 sanity 闸门

- [x] 2.1 实现 sanity 校验函数 `sanitize_numeric_fields`（`basics_sync/processing.py`）：负 `ps`/`ps_ttm`/`total_mv`/`circ_mv` 拒写、`|pe|`>1000 标记
- [x] 2.2 接入 `multi_source_basics_sync_service` 的 `UpdateOne` 前
- [x] 2.3 接入 `basics_sync_service` 写入路径（`SyncStats` 加 `warnings` 字段）
- [x] 2.4 被拒 / 被标记的 doc → 失败信息汇总进 `sync_status.warnings`，状态转 `success_with_errors`
- [x] 2.5 清理 `data_consistency_checker` 死代码：删 2 文件 + `manager.get_daily_basic_with_consistency_check` + `__init__` 空转块 + `tests/test_data_consistency.py`
- [x] 2.6 确认无悬空 import / 引用（`py_compile` + `just typecheck` 0 error）
- [x] 2.7 迁移补 Step 4：一次性 `$unset` 存量历史负值脏字段（闸门只拦新写入、`$set` 不 unset 被剥离字段，故需清存量；7.6 验证时发现 1 条残留负 `ps` 后补）

## 3. Item 2 — 主键 (code, source) → code（顺序锁死）

- [x] 3.1 写 MongoDB 去重迁移 `migrate_stock_basic_info`（`database.py`）+ 纯函数 `merge_duplicate_basic_info_docs`（选主 tushare>akshare>baostock，次文档补全缺失字段）
- [x] 3.2 去重后删两处 `code_source_unique` 复合唯一索引（迁移按 key spec 命中 `code_1_source_1` / `code_source_unique`）
- [x] 3.3 建 `code` 单字段唯一索引 `code_unique`（`create_database_indexes` + `basics_sync_service._ensure_indexes`）
- [x] 3.4 upsert key 改 `{"code": code}`——全部写入点：`basics_sync_service` / `multi_source_basics_sync_service` / `akshare_sync_service` / `baostock_sync_service` / `stock_sync` router 内联 3 处 / `stock_data_service`
- [x] 3.5 迁移逻辑幂等（三步均可安全重复执行；实跑验证幂等）
- [x] 3.6 复核下游 `query["source"]` 过滤补丁 → A 股专属 reader 改名 `source`→`data_source`（过滤逻辑保留，post-单一主键已冗余但低风险，移除可后续）；市场通用 `unified_stock_service` 保留不动（改名会破坏 HK/US，CN 读优雅降级到 fallback）

## 4. Item 3 — source/data_source 字段名统一

- [x] 4.1 选定统一字段名 → `data_source`（调研 1.1 结论）
- [x] 4.2 一次性数据迁移：`migrate_stock_basic_info` Step 3 `$rename source→data_source`（幂等）
- [x] 4.3 全 `app/` `stock_basic_info` 写入/读取路径代码改写为 `data_source`（sync service / worker / `stocks`·`reports`·`stock_sync` router / `stock_data_service`·`favorites_service`·`database_screening_service`）
- [x] 4.4 `stock_screening_view` `$lookup` join 的 `let`/`$eq` 对齐为同名 `data_source`；视图改为 drop-and-recreate 以应用新 pipeline
- [x] 4.5 确认无悬空引用，`py_compile` + `just typecheck` 通过

## 5. Item 4 — 审计脚本固化

- [x] 5.1 `/tmp/data_audit.js` → `scripts/data_audit.js`
- [x] 5.2 去 `[DEBUG-da7f]` 临时标记，补正式头注释（用途 / 运行命令）；加重复 code 检查
- [x] 5.3 `docs/data-audit-2026-05-17.md` 审计脚本段更新路径

## 6. 测试

- [x] 6.1 sanity 闸门单元测试：拒负 `ps` / `total_mv` / `ps_ttm`、不拒负 `pe`、标记越界 `pe`、None 忽略、多异常累加（8 个 unit test）
- [x] 6.2 去重选主单元测试 `merge_duplicate_basic_info_docs`：源优先级选主 / 补全缺失字段 / 不覆盖已有 / 单文档（7 个 unit test）
- [x] 6.3 `just test`（`-m unit`）全绿（新增 15 个，全套 177 passed / 2 skipped）

## 7. 文档与收口验证

- [x] 7.1 `docs/CHANGELOG.md` `[Unreleased]` 加条目
- [x] 7.2 `docs/data-audit-2026-05-17.md` Phase 3 标记完成
- [x] 7.3 `architecture.md` 经查未描述 `stock_basic_info` schema、`known-issues.md` 无相关条目——无可更新项，跳过
- [x] 7.4 `just ci` 全绿（lint + typecheck + test）
- [x] 7.5 实跑迁移（`init_database`）+ `scripts/data_audit.js` 验证 → `stock_basic_info` 11360→5843 docs（0 重复 code）、`source` 0 残留 / `data_source` 全覆盖、唯一索引 `code_unique`
- [x] 7.6 后端启动 + basics 同步手动触发验证 → 后端启动 `schema 迁移完成` + `Application startup complete` 无 import 错误；`multi_source` 同步 5519 股 `success_with_errors`（sanity 闸门标记 109 个量级失真 pe、0 重复 code、新文档带 `data_source`）；migration Step 4 清理 1 条残留负 `ps`，负值全清零
- [x] 7.7 archive change → `openspec/changes/archive/2026-05-19-data-audit-phase3/`
- [x] 7.8 应用 spec → `openspec/specs/data-quality-gate/`（+3 Requirement）+ `openspec/specs/audit-tooling/`（+1 Requirement）
