# 1.3 — baostock session lifecycle 收敛 tasks

## 实施步骤

- [ ] **commit 1**：立项
  - 创建 `docs/specs/dataflows-reliability-hardening/1.3-baostock-session-scope/{proposal,tasks}.md`
  - capability spec Scenario「baostock session 单一入口」已就位，本 stage 不需 spec 修订
  - commit："docs(spec): 立项 stage 1.3 — baostock session lifecycle 收敛 (refcount + lock)"

- [ ] **commit 2**：red + green + CHANGELOG
  - `tests/test_baostock_session_scope.py` red：
    - source-level grep：`_BaoStockSession` 类存在 + `bs.login()` 散落 = 0 + `bs.logout()` 散落 = 0
    - 行为测试（mock bs.login/logout）：嵌套 with 仅 1 次 login/logout + 5 并发 thread 仅 1 次 login/logout + login 失败抛 Exception
  - `tradingagents/dataflows/providers/china/baostock.py` green：
    - 顶部 `import threading` + `from contextlib import contextmanager`
    - 加 `_BaoStockSession` class（class-level lock + refcount + scope contextmanager）
    - 12 处 query 方法改用 `with _BaoStockSession.scope(self.bs):` 替代散落的 `lg = self.bs.login()` / `self.bs.logout()`
  - `just ci` 全绿
  - `docs/CHANGELOG.md` `[Unreleased]` Fixed 段追加条目
  - commit："fix(dataflows): 1.3 — baostock session lifecycle 收敛 (refcount + lock)"

- [ ] **Push**：由用户 1-click `git push origin main`（4 个 stage commit 累积 push）

## 验证

- [ ] `just ci` 454+ passed
- [ ] grep `bs.login()` baostock.py 命中 = 1（仅在 `_BaoStockSession.scope` 内）
- [ ] grep `bs.logout()` baostock.py 命中 = 1（同上）
- [ ] grep `with _BaoStockSession.scope` 命中 ≥ 7（12 处 query 方法）

## 不在 1.3 范围

详见 proposal.md「Out of Scope」段。
