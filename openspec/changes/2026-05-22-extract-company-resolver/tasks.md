## 0. Phase 1 cross-check（pre-plan-checklist 已过）

- [x] 0.1 既有项目骨架（CLAUDE.md / docs/ai-context/ / CHANGELOG / USAGE / .gitignore / ci.yml / .pre-commit-config.yaml）全部 ✅ 在位
- [x] 0.2 fork-patch 不动清单（pyproject.toml / vite.config.ts / .pre-commit-config.yaml / ci.yml / .gitignore patch 段）本 change 不触及
- [x] 0.3 license boundary：本 change 全部在 `tradingagents/agents/`（Apache 2.0），不碰 `app/` `frontend/`，`guard-proprietary` hook 不触发，无需 `.implementing` marker
- [x] 0.4 端口段位 + loopback 不变（本 change 不改网络配置）
- [x] 0.5 HARD-GATE：本地 commit 允许；push 需对话期再说
- [x] 0.6 工具链顺序：先建 `company_resolver.py` + 测试，再迁移 7 个 call site（call site import 它）

## 1. OpenSpec scaffolding — commit 1

- [x] 1.1 创建 `openspec/changes/2026-05-22-extract-company-resolver/` 目录
- [x] 1.2 写 `proposal.md`
- [x] 1.3 写 `tasks.md`（本文件）
- [x] 1.4 写 `specs/agent-company-resolution/spec.md`（新 capability，ADDED Requirements）
- [x] 1.5 commit（仅 OpenSpec 文件）

## 2. 新建 company_resolver + 单元测试 — commit 2

- [x] 2.1 **RED**：写 `tests/test_company_resolver.py`（`@pytest.mark.unit`，sys.modules 注入 fake dataflows，保持纯 unit 无 mongo）— 10 个用例
- [x] 2.2 **GREEN**：写 `tradingagents/agents/utils/company_resolver.py`
  - `get_company_name(ticker: str, market_info: dict, agent_label: str = "分析师") -> str`
  - canonical 行为：A 股两级降级 + `stock_info and` 空值守卫 / 港股 improved 工具 / 美股 8 项静态字典 / 缺省 `f"股票代码{ticker}"`
  - 日志前缀用 `agent_label` 注入；dataflows 依赖保持函数内惰性 import（避免 import 即连 mongo）
- [x] 2.3 跑 `pytest tests/test_company_resolver.py` PASS（10 passed, 0.06s）
- [x] 2.4 `just lint` + `just typecheck` 0 errors
- [ ] 2.5 commit

## 3. 迁移 7 个 call site — commit 3

> 每个文件：删除本地 `_get_company_name*` 定义，加 import，调用点改 `get_company_name(ticker, market_info, "<label>")`。

- [ ] 3.1 `analysts/market_analyst.py`：删模块级 `_get_company_name`（L17），call site L123 → label `"市场分析师"`
- [ ] 3.2 `analysts/social_media_analyst.py`：删 `_get_company_name_for_social_media`（L14），call site L112 → label `"社交媒体分析师"`
- [ ] 3.3 `analysts/fundamentals_analyst.py`：删 `_get_company_name_for_fundamentals`（L23），call site L167 → label `"基本面分析师"`
- [ ] 3.4 `analysts/china_market_analyst.py`：删 `_get_company_name_for_china_market`（L12），call site L106 → label `"中国市场分析师"`
- [ ] 3.5 `analysts/news_analyst.py`：删嵌套 `_get_company_name`（L44），call site L100 → label `"新闻分析师"`
- [ ] 3.6 `researchers/bull_researcher.py`：删嵌套 `_get_company_name`（L29），call site L77 → label `"多头研究员"`
- [ ] 3.7 `researchers/bear_researcher.py`：删嵌套 `_get_company_name`（L27），call site L75 → label `"空头研究员"`
- [ ] 3.8 检查每个文件删函数后是否留下未用 import（如某文件原 `_get_company_name` 用到的 import 现已无引用）→ 清理
- [ ] 3.9 grep 验证：`tradingagents/agents/` 内 `def _get_company_name` 命中数 = 0
- [ ] 3.10 `just lint` + `just typecheck` 0 errors
- [ ] 3.11 `pytest -m unit` 无回归
- [ ] 3.12 commit

## 4. CHANGELOG + 验证 + Archive — commit 4

- [ ] 4.1 `docs/CHANGELOG.md` `[Unreleased]` 加 `### Changed` 段：「公司名解析逻辑去重」（7 份 `_get_company_name` 拷贝合并为 `company_resolver.get_company_name`，顺带修 news_analyst `stock_info=None` latent TypeError）
- [ ] 4.2 `just ci` 通过（lint + typecheck + test）
- [ ] 4.3 Archive：`mv` change 目录 → `openspec/changes/archive/2026-05-22-extract-company-resolver`
- [ ] 4.4 Spec sync：`mv specs/agent-company-resolution/spec.md` → `openspec/specs/agent-company-resolution/spec.md`（新 capability，无 merge 冲突）
- [ ] 4.5 commit archive + spec sync
- [ ] 4.6 finishing report；push / tag 决策交用户

## 测试覆盖小结

| 区域 | 文件 | marker |
|---|---|---|
| company_resolver 全路径 + news latent bug 回归 | `tests/test_company_resolver.py` | `@pytest.mark.unit` |
| 7 个 call site 无回归 | 既有 `pytest -m unit` | — |
