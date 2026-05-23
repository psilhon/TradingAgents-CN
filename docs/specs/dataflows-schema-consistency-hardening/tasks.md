# dataflows-schema-consistency-hardening Epic Tasks

每 sub-stage 内 TDD red/green + migration script + push 由用户 1-click。

## Sub-stage 2.1 — 交易所后缀统一（`.SS → .SH`）

- [ ] **立项**：`docs/specs/dataflows-schema-consistency/spec.md` + `docs/specs/dataflows-schema-consistency-hardening/{proposal,tasks}.md` + `2.1-exchange-suffix-unify/{proposal,tasks}.md`
- [ ] **red**：`tests/test_exchange_suffix_unify.py` source-level grep 守护 + 行为测试
- [ ] **green**：6 writer 文件改 `.SS → .SH`
- [ ] **reader 简化**：9 处 `.replace(".SS", "")` 移除
- [ ] **migration**：`scripts/migrations/2.1_unify_exchange_suffix.js`
- [ ] **CHANGELOG** + commit
- [ ] **Push + migration 跑**：由用户 1-click

## Sub-stage 2.2 — trade_date 格式统一

- [ ] 立项 2.2 proposal + tasks
- [ ] red + green + migration + CHANGELOG + commit
- [ ] Push + migration 跑

## Sub-stage 2.3 — stock_basic_info 加 full_symbol

- [ ] 立项 2.3 proposal + tasks
- [ ] red + green + migration + CHANGELOG + commit
- [ ] Push + migration 跑

## 验证（all sub-stages done）

- [ ] `just ci` 464+ passed
- [ ] mongo 内 `.SS` 计数 = 0 (market_quotes / stock_basic_info / stock_daily_quotes)
- [ ] mongo 内 trade_date yyyymmdd 计数 = 0
- [ ] stock_basic_info full_symbol exists count = total count

## 不在 epic 范围

详见 proposal.md「Out of Scope」段。
