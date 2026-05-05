## 1. OpenSpec scaffolding — commit 1

- [x] 1.1 创建 change 目录 + proposal/tasks/spec
- [x] 1.2 `openspec validate` 通过
- [x] 1.3 commit（仅 OpenSpec 文件）

## 2. A 股 worker fallback 死代码删除 — commit 2

- [x] 2.1 `akshare.py:_get_realtime_quotes_data` 删 `stock_zh_a_spot()` / `stock_zh_a_spot_em()` 分支（净删 70 行）
- [x] 2.2 grep 验证：`stock_zh_a_spot` 仅剩 `get_batch_stock_quotes`（worker 合法路径）
- [x] 2.3 ruff + pyright 0 errors
- [x] 2.4 pytest -m unit 仍 12 pass
- [x] 2.5 commit

## 3. HK profile/hist API 集成 + 字段覆盖度实测 — commit 3

- [x] 3.1 REPL 实测 `ak.stock_hk_security_profile_em("00700")` → 14 列含证券简称/板块/上市日期/沪深港通
- [x] 3.2 REPL 实测 `ak.stock_hk_hist("00700", period="daily")` → 11 列含开盘/收盘/最高/最低/成交量/成交额/涨跌幅/换手率
- [x] 3.3 决策：profile + hist 字段覆盖足够，主路径切换可行
- [x] 3.4 实施 `improved_hk.py:get_hk_stock_info_akshare` 切换（共减 47 行）
- [x] 3.5 实施 `improved_hk.py:get_company_name` 切换（profile 取证券简称）
- [x] 3.6 ruff + pyright 0 errors
- [x] 3.7 pytest -m unit 仍 12 pass
- [x] 3.8 smoke 0700.HK：60s+ → **0.51s**（实测）
- [x] 3.9 commit

## 4. 删 HK 全局 cache + threading.Lock — commit 4

- [x] 4.1 `improved_hk.py` 删 `_akshare_hk_spot_cache` 全局 dict
- [x] 4.2 删 `_akshare_hk_spot_lock = threading.Lock()` + `import threading`
- [x] 4.3 grep 验证 `improved_hk.py` 无 `threading\.Lock` / `_akshare_hk_spot` 残留（仅 docstring 注释提到）
- [x] 4.4 ruff + pyright 0 errors
- [x] 4.5 并发 smoke：5 路 ThreadPoolExecutor 总耗 **0.76s**（之前串行上限 300s）
- [x] 4.6 commit

## 5. 收口 — commit 5

- [x] 5.1 docs/CHANGELOG.md `### Fixed` 条目
- [x] 5.2 archive change → `openspec/specs/dataflow-performance/spec.md`
- [x] 5.3 commit
