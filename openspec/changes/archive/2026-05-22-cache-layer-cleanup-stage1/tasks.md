# Tasks — cache-layer-cleanup-stage1

> `cache-layer-consolidation` stage 1：删 `db_cache.py` 死代码 + 抽公共 helper。
> 立项在本会话完成；Phase 2 实施换新会话（`/opsx:apply`）。

## 1. 立项 — commit 1

- [x] 1.1 写 `proposal.md`
- [x] 1.2 写 `tasks.md`
- [x] 1.3 写 `specs/dataflow-caching/spec.md`（新 capability，ADDED Requirements）
- [x] 1.4 commit（仅 OpenSpec 文件）

## 2. Part A — 删除 db_cache.py 死代码 — commit 2

- [x] 2.1 **前置复核**：grep 全仓确认 `DatabaseCacheManager` / `get_db_cache` 零外部消费者；`DB_CACHE_AVAILABLE` 标志亦仅 `__init__.py` 内部、无消费者；无 `importlib` 动态导入
- [x] 2.2 删除 `tradingagents/dataflows/cache/db_cache.py` 整文件（`git rm`）
- [x] 2.3 `cache/__init__.py`：删 db_cache try-import 块 + `__all__` 的 `"DatabaseCacheManager"` + `"DB_CACHE_AVAILABLE"`（连带 orphaned 标志）
- [x] 2.4 `just lint` + `just typecheck` 0 errors
- [x] 2.5 `pytest -m unit` 无回归（279 passed）
- [ ] 2.6 commit

## 3. Part B — 抽公共 helper — 调查后 DEFERRED

- [x] 3.1 详读 `file_cache._generate_cache_key` / `adaptive._get_cache_key` + 两处 TTL 逻辑
- [x] 3.2 **决策点：DEFER**（按 proposal「前置契约」的「拆出」分支）
  - **key 生成不兼容**：`file_cache` 产 `{symbol}_{data_type}_{md5[:12]}`（带前缀 + 截断 12 位、接受任意 `**kwargs`）；`adaptive` 产完整 32 位 md5、无前缀、固定参数。两套 scheme 输入形状 / 参数串格式 / 输出形态全不同——合并必改 key → 既有缓存条目全失效。
  - **TTL 不兼容**：`file_cache` 用硬编码 `ttl_hours` dict（6 项）；`adaptive` 用 config 驱动的 `ttl_settings` 秒数。单位（时 vs 秒）+ 来源（硬编码 vs config）皆异，统一须先做后端抽象重设计。
  - 唯一真正共用原子是 ~4 行「6 位数字 → china」市场判定；为它新建 `_common.py` 模块属过度结构（YAGNI），且两实现（regex vs `len+isdigit`）在 Unicode/换行边界并非字节一致。
  - **结论**：Part B 整体 DEFER 到后续「全量收敛」stage（key/TTL 统一须与后端抽象重设计一并做）。stage 1 只交付 Part A。
- [x] 3.3–3.8 N/A（Part B deferred；无 `_common.py` / 无新测试 / 无独立 commit）

## 4. CHANGELOG + 验证 + Archive — commit 3

- [x] 4.1 `docs/CHANGELOG.md` `[Unreleased]` 加 `### Removed` 段
- [x] 4.2 更新 `proposal.md`（Part B 实施结论）+ change spec（删未交付的 helper Requirement）
- [x] 4.3 `just ci` 通过（lint + typecheck + 279 unit tests）
- [x] 4.4 Archive：change 目录 → `openspec/changes/archive/2026-05-22-cache-layer-cleanup-stage1`
- [x] 4.5 Spec sync：稳定 spec 写入 `openspec/specs/dataflow-caching/spec.md`（新 capability）
- [x] 4.6 commit archive + spec sync
- [ ] 4.6 finishing report；push / tag 决策交用户
