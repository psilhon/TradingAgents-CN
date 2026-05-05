## 1. 调宽 ruff 配置 — commit 1

- [ ] 1.1 编辑 `pyproject.toml` `[tool.ruff.lint]` 加 `ignore = ["RUF001", "RUF002", "RUF003"]` + `[tool.ruff]` `line-length = 140`
- [ ] 1.2 跑 `uvx ruff check . --statistics` 看新基线（预期降到 ~13,500）
- [ ] 1.3 commit `chore(lint): widen ruff config — ignore RUF001-003 + line-length 140`

## 2. W293 blank-line-with-whitespace（9,114 → 0）— commit 2

- [ ] 2.1 跑 `uvx ruff check --fix --select W293 .`
- [ ] 2.2 验证：`vue-tsc --noEmit` 通过
- [ ] 2.3 验证：`.venv/bin/python -c "import tradingagents"` 不报错
- [ ] 2.4 重启 backend + curl /api/health 200
- [ ] 2.5 commit `fix(lint): auto-fix W293 blank-line-with-whitespace (9114 → 0)`

## 3. F541 f-string-missing-placeholders（1,705 → 0）— commit 3

- [ ] 3.1 跑 `uvx ruff check --fix --select F541 .`
- [ ] 3.2 验证 + 重启 backend + curl
- [ ] 3.3 commit `fix(lint): auto-fix F541 f-string-missing-placeholders (1705 → 0)`

## 4. I001 unsorted-imports（594 → 0）— commit 4

- [ ] 4.1 跑 `uvx ruff check --fix --select I001 .`
- [ ] 4.2 验证（特别注意循环 import：先 `python -c "import tradingagents.graph.trading_graph"` 测核心模块）
- [ ] 4.3 重启 backend + curl
- [ ] 4.4 commit `fix(lint): auto-fix I001 unsorted-imports (594 → 0)`

## 5. F401 unused-import（411 → 0）— commit 5

- [ ] 5.1 跑 `uvx ruff check --fix --select F401 .`
- [ ] 5.2 **特别仔细验证**：F401 删 import 风险最高
  - `import tradingagents.graph.trading_graph` 不报错
  - backend 启动 + 浏览器登录 + 切几个菜单
  - 任何 ImportError 立即 git revert
- [ ] 5.3 commit `fix(lint): auto-fix F401 unused-import (411 → 0)`

## 6. UP006 non-pep585-annotation（342 → 0）— commit 6

- [ ] 6.1 跑 `uvx ruff check --fix --select UP006 .`
- [ ] 6.2 验证（Python ≥ 3.10 type hint 升级，本 fork 3.12 ✓）
- [ ] 6.3 重启 backend
- [ ] 6.4 commit `fix(lint): auto-fix UP006 non-pep585-annotation (342 → 0)`

## 7. UP045 non-pep604-annotation-optional（272 → 0）— commit 7

- [ ] 7.1 跑 `uvx ruff check --fix --select UP045 .`
- [ ] 7.2 验证 + 重启
- [ ] 7.3 commit `fix(lint): auto-fix UP045 non-pep604-annotation-optional (272 → 0)`

## 8. W291 trailing-whitespace（124 → 0）— commit 8

- [ ] 8.1 跑 `uvx ruff check --fix --select W291 .`
- [ ] 8.2 验证 + 重启
- [ ] 8.3 commit `fix(lint): auto-fix W291 trailing-whitespace (124 → 0)`

## 9. UP035 deprecated-import（120 → 0）— commit 9

- [ ] 9.1 跑 `uvx ruff check --fix --select UP035 .`
- [ ] 9.2 验证 + 重启
- [ ] 9.3 commit `fix(lint): auto-fix UP035 deprecated-import (120 → 0)`

## 10. 剩余 fixable 一把梭 — commit 10

- [ ] 10.1 跑 `uvx ruff check --fix .` 修剩下所有 fixable（W292 73 + RUF010 116 + UP015 64 + RUF019 34 + UP009 40 + RUF022 17 + UP007 18 + 等小项）
- [ ] 10.2 验证 + 重启 backend + 浏览器手测（端到端：登录 / 切菜单 / 主题切换）
- [ ] 10.3 commit `fix(lint): auto-fix remaining fixable issues`

## 11. 报告 + 收口

- [ ] 11.1 跑 `uvx ruff check . --statistics` 看最终残留 errors（应只剩需手动改的 rule：E402 71 + RUF013 125 + B007 50 + E722 31 + B905 14 + E712 13 + 等共 ~3500）
- [ ] 11.2 更新 `docs/CHANGELOG.md` `[Unreleased]` 加 `### Fixed` 段汇总
- [ ] 11.3 浏览器手测全栈无回归（登录 / 切 5 个菜单 / 主题 / 配置中心）
- [ ] 11.4 commit `docs: changelog for lint-cleanup-baseline`
- [ ] 11.5 push 全部 commit（用户 1-click HARD-GATE）
- [ ] 11.6 `openspec archive lint-cleanup-baseline --yes`
