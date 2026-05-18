# backfill-data-quality-gate-spec

> 回填 capability spec：2026-05-17 数据正确性系统审计（`docs/data-audit-2026-05-17.md`）发现系统性数据质量崩塌，方案 A 修复落地于 commit `cd226369` + `4651fff1`，但这次 P0 级修复未走 OpenSpec、无 capability spec 锁定铁律。本 change 补齐 `data-quality-gate` spec。代码已落地，本 change 不改任何代码。

## Why

2026-05-17 用户反馈「股票筛选市值字段完全不可用」，`/diagnose` 全链路排查（`docs/data-audit-2026-05-17.md`）确认这不是单个 bug，是**系统性数据质量崩塌**：总市值 99.9% 缺失、pe/pb 不可信、财报全 null、每日推荐已被污染。

共性根因是同一个反模式——「数据源失败 → adapter 吞异常返回空 → 上游当成正常空数据 → 错误/不完整数据照写进库 → 前端不校验照显示 / 照排序 / 照喂给 LLM」，整条链路**没有任何一道数据质量闸门**。

方案 A 修复当日落地：commit `cd226369`（写库校验闸门 + 失败告警）+ `4651fff1`（前端兜底 + 误导性结果告警）。但对一个**数据正确性零容忍**的交易分析系统，这次 P0 级修复直接热修上线，没有 capability spec 把「数据质量闸门」沉淀成铁律——换任何数据源出问题都可能重演同一个反模式。

本 change 是**回填式 spec 补全**：把 `cd226369` + `4651fff1` 已落地的两道闸门（写库层 + 前端展示层）锁进 capability spec，恢复决策追溯链。

## What Changes

新建 capability `data-quality-gate`，锁定铁律：

- 数据同步写库前 MUST 校验关键字段，拒绝关键字段全为 `None` 的文档入库
- 数据源接口失败 MUST 显式告警并落入 `sync_status.warnings`，同步状态 MUST NOT 用 `success` 掩盖估值 / 财报数据缺口
- 前端展示层 MUST 对缺失数据兜底（显示「—」而非崩溃），数据缺失时 MUST 显式告警而非呈现误导性结果（0 结果 / 任意排序）

## Out of Scope

本 change 只回填**方案 A 已落地**的两道闸门。data-audit Phase 3「防复发」尚未做，明确不在本 spec 范围，作 release 后独立 change：

- `data_consistency_checker` 接入写入路径做 cross-source 偏差闸门
- `stock_basic_info` upsert key `(code, source)` → `code` 架构调整
- `source` / `data_source` 字段名、日期格式、交易所后缀统一
- `/tmp/data_audit.js` 固化为 `scripts/data_audit.js` 定期数据健康检查

## Impact

- 新建 `openspec/specs/data-quality-gate/spec.md`
- **0 代码改动**——两道闸门已实现于 `cd226369` + `4651fff1`，本 change 纯文档回填
- 风险：无
