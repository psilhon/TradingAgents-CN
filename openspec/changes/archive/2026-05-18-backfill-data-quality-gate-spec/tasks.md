# backfill-data-quality-gate-spec — Tasks (archived 2026-05-18)

## 1. 调研已落地范围

- [x] 1.1 核对 commit `cd226369`：`financial_data_service` 写库前拒绝关键字段全 `None` 的财务文档；`multi_source_basics_sync_service` 的 `daily_basic` 失败时告警 + 落 `sync_status.warnings` + status 转 `success_with_errors`；新增 5 个写库校验单测
- [x] 1.2 核对 commit `4651fff1`：`formatMarketCap` 对 null/undefined/NaN 兜底；筛选 / 每日推荐 在市值数据缺失时显式告警
- [x] 1.3 区分方案 A 已落地范围 vs data-audit Phase 3 待办（后者列入 Out of Scope）

## 2. 撰写 spec

- [x] 2.1 撰写 `data-quality-gate` capability spec：锁定写库校验闸门 / 失败告警不掩盖 / 前端兜底告警三条铁律
- [x] 2.2 确认与既有 `dataflow-integrity` spec 不冲突（`dataflow-integrity` 管 `tradingagents/dataflows` 读取层不返回伪造数据，本 spec 管 `app/services` 写库层与前端展示层，互补）

## 3. 归档

- [x] 3.1 archive change，`data-quality-gate` spec 落入 `openspec/specs/`
