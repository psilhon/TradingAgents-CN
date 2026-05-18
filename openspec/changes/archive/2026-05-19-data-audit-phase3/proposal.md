# data-audit-phase3

> data-audit 2026-05-17 的 Phase 3「防复发」：给 `stock_basic_info` 写入路径加数值 sanity 闸门、把复合主键 `(code, source)` 收敛为单一 `code`、统一 `source`/`data_source` 字段名、把一次性审计脚本 `/tmp/data_audit.js` 固化为 `scripts/data_audit.js`。

## Why

2026-05-17 数据正确性审计（`docs/data-audit-2026-05-17.md`）定位到一类系统性反模式——「数据源失败 → adapter 吞异常返回空 → 不完整数据照写进库 → 下游不校验照用」。方案 A 当日只止了血（P0 全部处置、`data-quality-gate` spec 回填），审计文档明确把 **Phase 3 防复发** 列为未做，`CLAUDE.md`「下一优先项」也指向它。当前残留 5 个根因仍会让同类问题复发：

1. **basics 写库前缺数值 sanity 校验**：`multi_source_basics_sync_service` 把 doc 直接 `UpdateOne` 进 `stock_basic_info`，不校验数值合理性。审计实证库里出现数学上不可能的负 `ps`、量级失真的 `pe=-16622`。`data-quality-gate` spec 只锁了 `financial_data_service` 的关键字段闸门，basics 写入路径仍裸奔。
2. **`data_consistency_checker` 名存实亡**：仓库有两份——`app/services/data_consistency_checker.py`（318 行全量实现，**无人 import**，纯死代码）+ `app/services/data_sources/data_consistency_checker.py`（48 行 no-op stub，被 `manager.py` import 但 `check_daily_basic_consistency()` 永远返回「一致」）。`manager.py:250-256` 的 cross-source 校验调用因此是空转。
3. **`stock_basic_info` 复合主键 `(code, source)` 制造 ×N 重复**：upsert key 是 `(code, source)`（`multi_source_basics_sync_service.py:299`），唯一索引 `code_source_unique` 在 `app/core/database.py:309` + `app/services/basics_sync_service.py:72` **两处**创建。每个数据源各写一份，审计时 `5841 真实代码 × ~3 源 ≈ 16557 docs`。方案 A 当日删过一次重，但只要再多源同步一次就复发。
4. **`source` / `data_source` 字段名分裂**：同一语义两个字段名并存（审计时 `source` 16557 docs vs `data_source` 5203 docs），`stock_screening_view` 的财务 join 因 `data_source==source` 命名不一致而几乎 join 不上。
5. **审计脚本是 `/tmp` 一次性产物**：`/tmp/data_audit.js` 不在版本库，重启即丢，无法定期复核数据健康。

## What Changes

### Item 1 — `stock_basic_info` 写库前数值 sanity 闸门

- 在 basics 同步写入路径（`multi_source_basics_sync_service` + `basics_sync_service`）的 `UpdateOne` 前，对关键数值字段做 sanity 校验：
  - 拒绝数学上不可能的值：负 `ps` / 负 `total_mv` / 负 `circ_mv`。
  - 标记量级失真的值：`|pe|` 超出合理界（阈值 Phase 1 调研定）。
  - 关键字段全 None 的 doc 拒写（与 `data-quality-gate` 的 `financial_data_service` 闸门同语义）。
- 被拒 / 被标记的 doc：失败信息落入 `sync_status.warnings`，同步状态转 `success_with_errors`（复用 `data-quality-gate` 已落地的 warnings 通道）。
- 清理 `data_consistency_checker` 死代码：Phase 1 调研定 `manager.py` cross-source 调用去留——post-方案A basics 单源（tushare 优先），cross-source 比对在 live path 已不触发；倾向删 318 行全量死代码 + no-op stub + `manager.py` 空转调用，由 sanity 闸门取代。

### Item 2 — `stock_basic_info` 主键 `(code, source)` → `code`

- upsert key：`UpdateOne({"code": code, "source": data_source}, ...)` → `UpdateOne({"code": code}, ...)`。
- 唯一索引：两处（`app/core/database.py` + `app/services/basics_sync_service.py`）的 `code_source_unique` 复合唯一索引 → `code` 单字段唯一索引。
- 数据迁移（顺序锁死）：先合并 / 去重残留同 code 多 source 文档（保留优先源 tushare，保 baostock 独有代码）→ 删旧复合索引 → 建 `code` 唯一索引。
- 下游清理：`database_screening_service` 等靠 `query["source"]=source` 过滤来规避重复的脆弱补丁，主键收敛后复核可否移除。

### Item 3 — `source` / `data_source` 字段名统一

- 统一字段名为 **`data_source`**（Phase 1 调研定论）。理由：`stock_financial_data` / `market_quotes` / `stock_daily_quotes` 三个数据集合已用 `data_source`，仅 `stock_basic_info` 偏离用 `source`，改 `stock_basic_info` 一侧改动面最小；且 `source` 在 `news_data` 集合已被占用为「媒体出处」语义，继续拿 `source` 当数据源标识会撞名。
- 把 `stock_basic_info` 的写入 / 读取路径（`basics_sync_service` / `multi_source_basics_sync_service` / 各 worker sync service / `stock_data_service` / `unified_stock_service` / `favorites_service` / `database_screening_service` / 相关 router）中代表数据源标识的 `source` 字段全部改为 `data_source`。
- 一次性数据迁移：把 `stock_basic_info` 现有文档的 `source` 字段 rename 为 `data_source`。
- `stock_screening_view` 的 `$lookup` join（`app/core/database.py` 的 `let`/`$eq`）对齐为同名 `data_source`。
- **排除 B 类同形词**：`news_data.source`（新闻媒体出处）、配置来源、通知来源、分析触发来源、API 响应体里的 `source`/`pe_source` 等非「数据提供商标识」语义一律不动。

### Item 4 — 审计脚本固化

- `/tmp/data_audit.js` → `scripts/data_audit.js`（tracked），去 `[DEBUG-da7f]` 临时标记、补正式头注释。
- `docs/USAGE.md` 补运行说明（mongosh 连接串 + 何时跑）。

### 文档

- `docs/CHANGELOG.md` `[Unreleased]` 加条目。
- `docs/data-audit-2026-05-17.md` Phase 3 标记完成。
- `docs/ai-context/architecture.md` / `known-issues.md` 随 schema 变化更新。

## Out of Scope

- **`market_quotes` 行情陈旧**（审计 P1 #5/#6，eastmoney `clist` 接口连通性问题）——属数据源连通性，另开 change。
- **日期格式 / 交易所后缀不统一**（审计 P1 #7/#8）——schema 一致性的另一面，本 change 不含，可后续单列。
- **`stock_daily_quotes.pre_close` 全 null**（审计 P1 #10）——单独的数据源字段问题。
- **多源数据 reconcile 机制**：post-方案A 已收敛为 tushare 单源，本 change 不重建 cross-source 比对，只删其死代码。
- **前端改动**：本 change 是数据层 / 后端 / 工具，不碰 `frontend/`。

## Impact

**改动范围**：

- `app/services/multi_source_basics_sync_service.py` — 写库 sanity 闸门 + upsert key。
- `app/services/basics_sync_service.py` — 闸门 + 唯一索引。
- `app/core/database.py` — `stock_basic_info` 唯一索引 + `stock_screening_view` join 条件。
- `app/services/data_consistency_checker.py` + `app/services/data_sources/data_consistency_checker.py` + `manager.py` — 死代码清理。
- `source` / `data_source` 字段名统一 — 跨约 30 个 `app/` 文件（Phase 1 精确清点）。
- MongoDB 一次性迁移：`stock_basic_info` 去重 + 索引重建 + 字段 rename。
- 新增 `scripts/data_audit.js`。
- `tests/` — 新增 sanity 闸门 + upsert 主键单元测试。
- 文档若干。

**风险**：高

- 大面积触及 `app/` 专有授权代码（已获本对话明确授权——用户选「全包」）。
- MongoDB 索引迁移顺序坑：必须先去重再建 `code` 唯一索引，否则建索引报 duplicate key。
- 字段名统一漏改一处 → 下游 join / filter 静默失配。
- `pre-commit` STRICT，改完须过 ruff / format / pyright，0 error 才能 commit。

**收益**：

- 同类「错误数据静默入库」根因闭环——换任何数据源出问题都被闸门拦。
- `stock_basic_info` 去重复，下游计数 / 筛选 / 排序不再 ×N 偏差。
- 跨集合 join 不再因字段名分裂失配。
- 数据健康可定期复核（固化审计脚本）。

## 依赖与时序

**前置**：`data-quality-gate` capability 已落地（commit `cd226369` / `4651fff1`）——本 change 的 sanity 闸门复用其 `sync_status.warnings` + `success_with_errors` 机制。

**时序约束（实施期）**：

1. **MongoDB `stock_basic_info` 主键迁移三步锁死**：去重 / 合并残留同 code 多 source 文档 → 删 `code_source_unique` 复合唯一索引（两处）→ 建 `code` 单字段唯一索引。顺序错则建索引报 duplicate key。
2. **字段名统一**：代码改写 + 一次性数据迁移须在同一 change 内完成，不能只改代码留旧字段名文档。
3. **Phase 1 调研先于实施**：精确清点 `source`/`data_source` 出现的全部集合与文件、定 `|pe|` sanity 阈值、定 `data_consistency_checker` 去留。
4. Item 1 / 2 / 4 相对独立可并行；Item 3 字段名统一面最广，建议最后做（避免与 Item 1/2 的 diff 互相干扰）。

**后续**：审计 P1 剩余项（行情陈旧 / 日期格式 / 交易所后缀 / `pre_close`）按需另开 change。
