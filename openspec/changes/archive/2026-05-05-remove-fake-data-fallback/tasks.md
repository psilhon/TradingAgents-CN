## 1. 删除假数据 fallback — commit 1

- [x] 1.1 `optimized_china_data.py` 删 `_generate_fallback_data` + `_generate_fallback_fundamentals` 方法
- [x] 1.2 `optimized_china_data.py` line 167 / 192 / 266 改为 `_render_data_unavailable` / `_render_fundamentals_unavailable`（无 random 字段）
- [x] 1.3 `optimized_china_data.py` 删 `import random`（unused）
- [x] 1.4 `providers/us/optimized.py` 删 `_generate_fallback_data` + 同模式替换 + 删 `import random`（**audit 漏抓，本 change 一并修**）
- [x] 1.5 `chinese_finance.py:143-157` `_search_finance_news` 改为返回 `[]` + TODO 注释
- [x] 1.6 grep 验证 `tradingagents/dataflows/` 不再有业务 `random.uniform/randint/choice`（仅保留 `google_news.py` 的 sleep jitter 合规）
- [x] 1.7 `ruff check` + `pyright` 仍 0 errors
- [x] 1.8 `pytest -m unit` 仍全 pass（12 tests）
- [x] 1.9 commit

## 2. 收口

- [x] 2.1 docs/CHANGELOG.md `### Fixed` 条目（标 critical）
- [x] 2.2 archive
