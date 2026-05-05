## Why

`lint-handfix-pass-1` 修完 19 个真 bug 后剩 850 issues，全是代码风格 / 复杂度 / 类型注解类。按 Q1=A 真治理目标 0 errors，本 change 处理这 850 中可治理的（含 583 unsafe-fixable + ~267 手动），目标降到 ~50（或更低）。

## What Changes

按风险递增、Q2=b 每 rule 一个 commit：

- **Task 1（🟢 低风险 unsafe-fix）**：B007 (50) + RUF059 (17) + E712 (13) + RUF005 (7) — 全 `_` 占位 + `is True/False` 比较
- **Task 2（🟢 RUF013 implicit-optional × 125）** — type hint 加 `Optional[X]`
- **Task 3（🟢 手动 E722 bare-except × 31）** — 加 `except Exception:` 显式
- **Task 4（🟢 手动 B-rules: B905 14 + B904 5 + B006 2 + B009 1）** — bug-prevention 类
- **Task 5（🟡 W293 hidden × 279）** — `--unsafe-fixes` 修隐藏空白；验证后 commit
- **Task 6（🟡 F841 unused-variable × 66）** — `--unsafe-fixes` 删变量；careful 验证副作用 import
- **Task 7（🟡 手动 E402 × 63）** — 重组 import 或加 `# noqa: E402`（业务有理由的）
- **Task 8（🟡 手动 E501 > 140 × 114）** — 分割中文长行 / 加 `# noqa: E501`
- **Task 9（🔴 F401 剩余 × 35）** — 每个加 `# noqa: F401` 或删，看上下文
- **Task 10（一把梭剩余）** — UP035 / RUF022 / RUF012 / F403 / F405 / RUF015 / F601 / F823 / I001 / RUF034 等小项
- **Task 11（收口）** — CHANGELOG / push / archive

每 task 后验证：核心模块 import + backend `/api/health` 200 + frontend vite 仍跑。

## Capabilities

### Modified Capabilities

- `lint-policy`：MODIFY「真 bug 类 lint issue 优先修」Requirement 加 "代码风格类按 rule code 分批治理目标 0"

## Impact

**改动文件**：~50-100（涉及 tradingagents/ + tests/ 多目录）
**estimated commit 数**：11（10 fix + 1 收口）+ 1 archive
**风险**：每 task 后立即验证，引入回归立刻 git revert
**收益**：850 → 估 ~0-50 errors，可考虑后续 `lint-strict-mode-enable` 转严格模式
