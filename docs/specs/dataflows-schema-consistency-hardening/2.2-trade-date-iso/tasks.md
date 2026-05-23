# 2.2 — trade_date 格式统一 tasks

## 实施步骤

- [ ] **commit 1（本次）**：立项
  - `docs/specs/dataflows-schema-consistency-hardening/2.2-trade-date-iso/{proposal,tasks}.md`
  - capability spec Scenario「trade_date canonical ISO 8601 格式」已就位
  - commit："docs(spec): 立项 stage 2.2 — trade_date ISO 8601 统一"

- [ ] **commit 2**：red + green + migration + CHANGELOG
  - `tests/test_trade_date_iso.py` red：source-level grep 守护 + 行为测试 `_to_iso_date`
  - `quotes_ingestion_service.py` green：加 `_to_iso_date` helper + `_bulk_upsert` 调用
  - `scripts/migrations/2.2_trade_date_iso.js` migration script (dry-run default)
  - `just ci` 全绿
  - CHANGELOG 追加
  - commit："fix(dataflows): 2.2 — trade_date ISO 8601 统一 (writer + migration)"

- [ ] **Push + migration 跑**：由用户 1-click

## 验证

- [ ] `just ci` 478+ passed
- [ ] mongo `db.market_quotes.countDocuments({trade_date: /^\d{8}$/})` = 0
- [ ] grep `strftime` writer 端无 `"%Y%m%d"` 直接入 mongo

## 不在 2.2 范围

详见 proposal.md「Out of Scope」段。
