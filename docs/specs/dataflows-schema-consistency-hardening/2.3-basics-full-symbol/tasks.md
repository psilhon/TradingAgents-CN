# 2.3 — stock_basic_info full_symbol invariant 守护 tasks

## 调研结论

stage 2.3 实质已完成（writer + 数据皆 canonical）。本 stage 仅加 spec invariant 测试 + audit script 防回归。

## 实施步骤

- [ ] **commit 1**：立项 + 实施（合并因为实质零代码改）
  - `docs/specs/dataflows-schema-consistency-hardening/2.3-basics-full-symbol/{proposal,tasks}.md`
  - `tests/test_stock_basic_info_full_symbol.py` 守护 writer + helper 行为
  - `scripts/migrations/2.3_audit_full_symbol.js` audit-only script（无 --write flag）
  - `docs/CHANGELOG.md` `[Unreleased]` 追加
  - commit："test(dataflows): 2.3 — stock_basic_info full_symbol invariant 守护"

- [ ] **Push**：由用户 1-click

## 验证

- [ ] `just ci` 486+ passed
- [ ] audit script `mongosh ... --file scripts/migrations/2.3_audit_full_symbol.js` 报 0 异常 doc

## 不在 2.3 范围

详见 proposal.md「Out of Scope」段。
