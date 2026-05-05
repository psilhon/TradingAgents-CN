## 1. OpenSpec scaffolding — commit 1

- [ ] 1.1 创建 change 目录 + proposal/tasks/spec
- [ ] 1.2 `openspec validate` 通过
- [ ] 1.3 commit（仅 OpenSpec 文件，无代码改动）

## 2. A 股 worker fallback 死代码删除 — commit 2

- [ ] 2.1 `akshare.py:_get_realtime_quotes_data` 删 `stock_zh_a_spot()` / `stock_zh_a_spot_em()` 分支
- [ ] 2.2 grep 验证 `tradingagents/dataflows/providers/china/akshare.py` 不再有 `stock_zh_a_spot` 调用（除 `get_batch_stock_quotes` 合法路径）
- [ ] 2.3 ruff + pyright 0 errors
- [ ] 2.4 pytest -m unit 仍 12 pass
- [ ] 2.5 backend 重启 + smoke /api/health
- [ ] 2.6 commit

## 3. HK profile/hist API 集成 + 字段覆盖度实测 — commit 3

- [ ] 3.1 Python REPL 实测 `ak.stock_hk_security_profile_em("00700")` 字段（确认 `current_price` / `change_percent` 是否在）
- [ ] 3.2 Python REPL 实测 `ak.stock_hk_hist("00700", period="daily")` 取最近一行字段
- [ ] 3.3 决策：profile + hist 字段覆盖足够 → 主路径切到这两个；不够 → 降级方案保留 `stock_hk_spot()` 但加 `asyncio.to_thread()` 包装
- [ ] 3.4 实施 `improved_hk.py:759,766` `get_hk_stock_info_akshare` 切换
- [ ] 3.5 实施 `improved_hk.py:275` `get_company_name` 切换（mapping first → single-stock fallback）
- [ ] 3.6 ruff + pyright 0 errors
- [ ] 3.7 pytest -m unit 仍 12 pass
- [ ] 3.8 backend 重启 + smoke：腾讯 0700.HK 调用一次 `get_hk_stock_data` 验证耗时 < 5s（之前 60s）
- [ ] 3.9 commit

## 4. 删 HK 全局 cache + threading.Lock — commit 4

- [ ] 4.1 `improved_hk.py` 删 `_akshare_hk_spot_cache` 全局 dict（~5 行）
- [ ] 4.2 删 `_akshare_hk_spot_lock = threading.Lock()` + 所有 `acquire/release` 调用
- [ ] 4.3 grep 验证无 `_akshare_hk_spot` 残留
- [ ] 4.4 grep 验证 `improved_hk.py` 无 `threading.Lock` 残留（如其它地方还需要 lock 单独评估）
- [ ] 4.5 ruff + pyright 0 errors
- [ ] 4.6 backend 重启 + 并发 smoke：浏览器多 tab 同时查 0700.HK 验证不阻塞
- [ ] 4.7 commit

## 5. 收口 — commit 5

- [ ] 5.1 docs/CHANGELOG.md `### Fixed` 条目（标性能 + license/agent path 改进）
- [ ] 5.2 archive change → `openspec/specs/dataflow-performance/spec.md`
- [ ] 5.3 commit
