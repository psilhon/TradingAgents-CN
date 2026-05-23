# 2.1 — 交易所后缀统一 tasks

## 实施步骤

- [ ] **commit 1（本次）**：立项 + spec
  - `docs/specs/dataflows-schema-consistency/spec.md`（4 Requirement + 6 Scenario）
  - `docs/specs/dataflows-schema-consistency-hardening/{proposal,tasks}.md`
  - `docs/specs/dataflows-schema-consistency-hardening/2.1-exchange-suffix-unify/{proposal,tasks}.md`
  - commit："docs(spec): 立项 dataflows-schema-consistency epic + stage 2.1"

- [ ] **commit 2**：red + green + migration + CHANGELOG
  - `tests/test_exchange_suffix_unify.py` red
  - 6 writer 文件改 `.SS → .SH`
  - 9 处 reader `.replace(".SS", "")` 移除
  - `scripts/migrations/2.1_unify_exchange_suffix.js` migration script (dry-run mode)
  - `just ci` 全绿
  - `docs/CHANGELOG.md` `[Unreleased]` Fixed 段追加条目
  - commit："fix(dataflows): 2.1 — 交易所后缀统一 .SS → .SH"

- [ ] **Push + migration 跑**：用户 1-click
  - `git push origin main`
  - 先 dry-run: `mongosh "..." --eval "load('scripts/migrations/2.1_unify_exchange_suffix.js')"`
  - 确认数量后 commit: `mongosh "..." --eval "DRY_RUN=false; load('scripts/migrations/2.1_unify_exchange_suffix.js')"`
  - mongo 验证：`db.market_quotes.countDocuments({full_symbol: /\.SS$/})` MUST == 0

## 验证

- [ ] `just ci` 464+ passed
- [ ] grep `\.SS` in app/services + app/worker + tradingagents/dataflows/providers 命中 0
- [ ] mongo `db.market_quotes.countDocuments({$or: [{full_symbol: /\.SS$/}, {ts_code: /\.SS$/}]})` = 0
- [ ] 同 doc 后缀冲突 0 个：`db.market_quotes.aggregate([{$match: {$expr: {$ne: ['$full_symbol', '$ts_code']}}}, {$count: 'n'}])` = 0 (full_symbol + ts_code 都存在时)

## 不在 2.1 范围

详见 proposal.md「Out of Scope」段。
