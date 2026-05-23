# Tasks — cache-callsite-compatibility (sub-stage 4.5)

> epic：`cache-layer-consolidation` stage 4（archived `2026-05-22-cache-backend-unification`）
> 前置：4.4 已完成（commit `12302aa3`）—— Cache 类已落但有签名兼容性漏洞
> 体量：~0.5-1 天 / 风险：低（纯签名 + None 防御修补）
> TDD red-green。

## 1. spec delta — commit 1（先于代码）

- [ ] 1.1 在 `docs/specs/dataflow-caching/spec.md` 「统一 Cache 类」 Requirement 内**修订**公开方法签名段：明示所有 `start_date` / `end_date` / `data_source` 参数 MUST 接受 `None`，内部 normalize 到默认值（与 4.4 前 IntegratedCacheManager 字节级一致）
- [ ] 1.2 加 Scenario「cache_key None-safe 字节级兼容」：`Cache.save_stock_data(symbol, data, None, None, None)` 生成的 cache_key MUST 与 `Cache.save_stock_data(symbol, data, "", "", "default")` 字节级相同
- [ ] 1.3 加 Scenario「save_fundamentals_data 默认 data_source 兼容」：不传 data_source 时 cache_key MUST 与传 `"default"` 一致
- [ ] 1.4 commit `docs(spec): cache-backend-unification 4.5 — Cache 公开 API None-safe 签名契约`

## 2. red — commit 2（先测试）

- [ ] 2.1 新建 `tests/test_cache_callsite_compatibility.py`（spec_from_file_location 模式）
- [ ] 2.2 测试：`save_stock_data(symbol, data)` 不传 start/end/source MUST 不 raise + 返非空 cache_key
- [ ] 2.3 测试：`save_stock_data(symbol, data, None, None, None)` 显式传 None MUST 不 raise + cache_key 与 `("","","default")` 字节级一致
- [ ] 2.4 测试：`save_fundamentals_data(symbol, data)` 不传 data_source MUST 不 raise + cache_key 与 `data_source="default"` 字节级一致（**不是** `"unknown"`）
- [ ] 2.5 测试：`save_fundamentals_data(symbol, data, None)` 显式 None MUST normalize 到 `"default"`
- [ ] 2.6 测试：`find_cached_stock_data(symbol)` 不传任何 optional MUST 不 raise（None args 内部 normalize）
- [ ] 2.7 测试：`find_cached_fundamentals_data(symbol, data_source=None)` MUST 不 raise + 走 `"default"` 路径
- [ ] 2.8 跑 `just test`：新测试中至少 4 个 MUST FAIL（红——`save_stock_data` 当前不接受 None，`save_fundamentals_data` 默认 `"unknown"` 不是 `"default"`）
- [ ] 2.9 commit `test(cache): Cache 公开 API None-safe 兼容（red）`

## 3. green — commit 3（实现）

- [ ] 3.1 修改 `_cache.py` `save_stock_data` 签名：`start_date: str | None = None, end_date: str | None = None, data_source: str | None = None`；函数体顶部 normalize `start_date = start_date or ""` / `end_date = end_date or ""` / `data_source = data_source or "default"`
- [ ] 3.2 修改 `_cache.py` `save_fundamentals_data` 签名：`data_source: str | None = None`；函数体 normalize `data_source = data_source or "default"`
- [ ] 3.3 修改 `_cache.py` `find_cached_stock_data` 签名已含 None（4.4 写了），但补 normalize：在调 `_get_cache_key` 之前显式赋值（清晰性）
- [ ] 3.4 修改 `_cache.py` `find_cached_fundamentals_data`：`data_source or "default"`（与 save 对齐，4.4 时写的 `or "unknown"` 是签名漂移）
- [ ] 3.5 跑 `just test`：新 + 老测试 MUST 全绿
- [ ] 3.6 跑 `just lint` + `just typecheck` + `just audit-binds`：MUST 全绿
- [ ] 3.7 commit `feat(cache): Cache 公开 API None-safe 签名 + 默认值对齐（green）`

## 4. 行为兼容验证（push 前）

- [ ] 4.1 `just ci` 完整流水线绿灯（4.4 后 363 → 4.5 加 ~6 个 test ≈ 369）
- [ ] 4.2 grep 仍 `cache_key` 字节级守护：对 `Cache.save_stock_data("AAPL", df, None, None, None)` 与 `Cache.save_stock_data("AAPL", df, "", "", "default")` 经 md5 应得同样 hash

## 5. 收尾

- [ ] 5.1 更新 `docs/CHANGELOG.md` `[Unreleased]` 段加条目
- [ ] 5.2 commit `docs(changelog): cache backend 4.5 — Cache 公开 API None-safe 签名`
- [ ] 5.3 push main（1 click HARD-GATE）

## 6. 后续 sub-stage 触发

- [ ] 6.1 本 sub-stage merge 后 → 开 4.6 `cache-remove-deprecated-layers`（删 IntegratedCacheManager / AdaptiveCacheSystem / StockDataCache 包装层，0.5 天 / 低风险）

## 验证清单（每个 commit 前）

- `Cache.save_stock_data("X", data, None, None, None)` 与 `("X", data, "", "", "default")` cache_key MUST 字节级相同
- `Cache.save_fundamentals_data("X", data)` 与 `("X", data, "default")` cache_key MUST 字节级相同
- 公开方法签名 / 类型 hint 含 `| None`，与 4.4 前 IntegratedCacheManager 字节级一致
- 不引入新的 callsite 改动；40+ 调用方零接触
- `tradingagents/dataflows/cache/` grep `pickle` 仍 0
