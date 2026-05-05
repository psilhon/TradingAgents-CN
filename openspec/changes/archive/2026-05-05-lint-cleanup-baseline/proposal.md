## Why

接手上游时 ruff 报 21,321 issues，CI 一直 red。Q&A 拍板治理策略：
- Q1 = C 混合（先调宽中文友好规则 + 真治理剩下）
- Q2 = b 按 rule code 分批
- Q3 = ii 治理过程 warn-only，最后转严格

数据揭示：top 10 rule code 占 95%，其中 **RUF001/002/003 + E501 共 7,827 issues（37%）是中文项目固有噪音**，调宽即可砍掉；剩 ~13,500 中 ~10,000 ruff --fix 自动可修，~3,500 需手动改。

本 change 是治理的**第一个里程碑**——只做"调宽 + 高频自动修"，把 errors 降到可手控范围（< 5,000）。后续手动修的 rule 留给独立 change。

## What Changes

- **MODIFIED** `pyproject.toml` `[tool.ruff.lint]`：
  - 加 `ignore = ["RUF001", "RUF002", "RUF003"]`（中文全角字符放行——本 fork 是中文项目，全角字符是常态而非问题）
  - `line-length` 从 100 调到 140（中文 docstring 友好）
- **MODIFIED 大量代码**（按 Q2=b 每 rule 一个 commit）：依次 ruff --fix 高频低风险 rule
  - W293 blank-line-with-whitespace (9,114) → 1 commit
  - F541 f-string-missing-placeholders (1,705) → 1 commit
  - I001 unsorted-imports (594) → 1 commit
  - F401 unused-import (411) → 1 commit
  - UP006 non-pep585-annotation (342) → 1 commit
  - UP045 non-pep604-annotation-optional (272) → 1 commit
  - W291 trailing-whitespace (124) → 1 commit
  - UP035 deprecated-import (120) → 1 commit
  - 剩 fixable 小项打包 → 1 commit
- **每 commit 后**跑 `vue-tsc` + 重启 backend / 验证 `/api/health` + 浏览器烟测，回归立刻 revert

无 BREAKING change（纯 lint 治理 + 配置调宽）。

## Capabilities

### New Capabilities

- `lint-policy`：定义本 fork 的 ruff 配置策略（哪些 rule 放行、line-length、未来如何治理）

### Modified Capabilities

无。

## Impact

**改动文件**：
- `pyproject.toml`（[tool.ruff.lint] 段加 ignore + line-length 调）
- 整个 `tradingagents/` + `tests/` 目录（W293 涉及 9k+ 行空白修整 / F541 删 f 前缀 / I001 重排 import / F401 删 import / UP00X 类型注解升级）

**估计 commit 数**：~10（1 配置 + 8-9 自动修 + 1 收口）

**风险**：

- ⚠️ 每个 ruff --fix 后必须验证 backend 仍能启动 + import smoke test。F401 删 import 风险最高（动态使用的 import 会被误删）
- ⚠️ I001 重排 import 可能改变模块加载顺序触发循环 import（罕见但要测）
- ⚠️ UP006/UP045 类型注解升级要 Python ≥ 3.10，本 fork 用 3.12 ✓

**收益**：
- ruff issues 21,321 → < 5,000（粗估，实测后调整）
- CI 可逐步转严格（pre-commit + CI 都阻塞），但本 change 不转
- 开发体感：grep 不再 hit 大量 RUF001 中文字符 hit

**不在本 change 范围**：
- 手动修 E402 / B007 / B905 / E712 / E722 / 等需推理改动的 rule（约 3,500 issues）
- pre-commit / CI 转严格模式（warn-only 保留到下一 change）
- F821 undefined-name (14)、F811 redefined-while-unused (12) 等 真 bug 类（这些是真问题，留给单独 hotfix change）
