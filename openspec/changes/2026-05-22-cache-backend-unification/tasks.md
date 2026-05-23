# Tasks — cache-backend-unification (epic 立项)

> `cache-layer-consolidation` stage 4，多 sub-stage epic 的**立项 / 总图 change**。
> 本 change **不含代码改动 / 不含 spec delta**——仅 proposal 作为蓝本。
> sub-stage 4.1–4.6 各自开独立 OpenSpec change，独立 TDD + push + CI。

## 1. 立项 — commit 1（唯一 commit）

- [x] 1.1 调查 cache 层 4 实现拓扑 + 40+ 调用方分布（已在 proposal「Why」段记录）
- [x] 1.2 设计目标架构（`Cache` 单一类 + `Backend` Protocol + `CacheConfig` dataclass，proposal「目标架构」段）
- [x] 1.3 拆 sub-stage 4.1–4.6（proposal「Sub-stage 拆分」表，每条独立体量 + 风险）
- [x] 1.4 写 `proposal.md`
- [x] 1.5 写 `tasks.md`（本文件）
- [ ] 1.6 commit

## 2. Epic 归档时机

- [ ] 2.1 **当 sub-stage 4.1 立项**（独立 OpenSpec change 开出）→ 本 epic change 归档到 `openspec/changes/archive/`。在此之前作为 active change 锚点。

## 3. Sub-stage 索引（不在本 change 实施）

| # | Sub-stage 名（建议 change 名） | 体量 | 风险 |
|---|---|---|---|
| 4.1 | `cache-backend-protocol-and-filebackend` | 1 天 | 低 |
| 4.2 | `cache-redis-mongo-backends` | 1 天 | 低 |
| 4.3 | `cache-config-dataclass` | 1-2 天 | 中 |
| 4.4 | `cache-unified-class` | 2-3 天 | 中 |
| 4.5 | `cache-callsite-migration` | 2 天 | 中-高 |
| 4.6 | `cache-remove-deprecated-layers` | 0.5 天 | 低 |

预计总体量 ~7-9 天 wall-clock，逐条 sub-stage 串行 / 独立验证。

## 4. 与已完成 stage 的关系

- **stage 1**（`cache-layer-cleanup-stage1`，已 archived）：删 orphaned `db_cache.py` + 调查 helper 抽取（Part B deferred）。
- **stage 2**（`cache-pickle-replacement`，已 archived）：`adaptive.py` 7 处 pickle → `_serialize.py` 安全序列化。
- **stage 3**（原计划「config 三开关统一」）：调查发现框架被错读（`USE_MONGODB_STORAGE` 非 cache 配置），未开成独立 change；cache config 统一**折叠**到本 epic 的 sub-stage **4.3**。
