# docs/archive/dev-history — fork 开发过程产物（冻结）

**冻结版本**：fork v1.3.x
**冻结日期**：2026-05-21
**维护状态**：不再更新

本目录归档的是 fork 自身在开发过程中产生的一次性文档：dated bugfix notes、fix summary、tech review、设计探索、已完成的实施计划、已完成的 migration 记录、阶段性 progress summary。这些文档当时帮助解决具体问题或对齐认知，但现在功能事实已沉淀到 `openspec/specs/`，相关内容不再代表当前实践。

## 当前事实在哪

- **功能事实**：[`openspec/specs/`](../../../openspec/specs/) — 22 个 stable capability spec
- **架构横切**：[`docs/ai-context/architecture.md`](../../ai-context/architecture.md)
- **已知问题**：[`docs/ai-context/known-issues.md`](../../ai-context/known-issues.md)

## 子目录与文件索引

| 名称 | 内容性质 | 文件数 |
|---|---|---|
| 顶层 flat 文件 | fork 早期 fix summary（2026-05-05 由根目录整理引入） | 4 |
| `bugfix/` | 2025-10-26 / 2025-10-27 一次性 bugfix 记录 | 10 |
| `fixes/` | dated fix notes（async/asyncio/cache/datafrme/混合命名约定）| 38 |
| `tech_reviews/` | 2025-10 ~ 2025-11 设计评审会议纪要 + 实施指南 | 8 |
| `changes/` | 历史 change 提案（含 DEPRECATION_NOTICE 标记的废弃流程） | 6 |
| `improvements/` | 性能 / 架构改进 summary | 6 |
| `analysis/` | 早期数据分析 / 估值对比 / 时间统计准确性分析 | 9 |
| `implementation/` | 已完成的实施计划（如 foreign_stock_support / realtime-pe-pb） | 2 |
| `migration/` | data directory 重组完成记录 | 2 |
| `summary/` | 阶段性进展 summary | 3 |
| `integration/` | 早期数据流集成计划 + summary | 3 |
| `upstream-fix-reports/` | 上游一次性 fix report（duplicate_logger / logger_position / logging_import / print_to_log_conversion / pip_freeze / syntax_error），2026-05-05 一并归位 | 6 |

## 顶层 flat 文件

挪入本目录前位于 `docs/archive/` 根（2026-05-05 commit `refactor: 整理项目根目录结构` 引入）：

- `AUTHENTICATION_FIX_SUMMARY.md` — 早期认证问题修复总结
- `BACKEND_STARTUP.md` — 早期后端启动指南（当前请用 `docs/QUICK_START.md` + `scripts/dev.sh`）
- `FIXES_SUMMARY.md` — 早期 fix 汇总
- `SOLUTION_SUMMARY.md` — 股票详情页问题解决方案总结

## 引用注意

引用本目录任何文件作为依据时，必须明确"内容冻结于 v1.3.x"，并交叉验证当前 `openspec/specs/` 是否给出更新的事实。
