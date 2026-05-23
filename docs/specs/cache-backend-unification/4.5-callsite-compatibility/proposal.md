## Why

`cache-layer-consolidation` epic（archived `2026-05-22-cache-backend-unification`）的 sub-stage 4.5，紧接 4.4（`Cache` 类已落，commit `12302aa3`）。

4.4 完成时 `get_cache()` 已返回新 `Cache` 实例，所有 40+ 调用方已在跑新 Cache。4.5 的实际工作不是改调用方，而是**回头验证新 Cache 是否真能兼容所有 callsite 调用形式**——4.4 写 Cache 时对部分 callsite 边界 case 处理不周，存在以下兼容性漏洞：

### 漏洞 1：`save_stock_data` 不接受 `start_date=None`

callsite 真实形式：

```python
# tradingagents/dataflows/data_source_manager.py:688-703
def _save_to_cache(self, symbol, data, start_date: str | None = None, end_date: str | None = None):
    ...
    self.cache_manager.save_stock_data(symbol, data, start_date, end_date)
```

旧 `IntegratedCacheManager.save_stock_data` 签名 `start_date: str | None = None`，内部用 `start_date or ""` 转换；新 `Cache.save_stock_data` 签名 `start_date: str = ''`——callsite 传 None 时不会 raise（f-string 容忍 None），但 `f"{symbol}_{None}_..."` 会渲染为字面量 `"None"`，导致 **cache_key 与历史值漂移** —— 历史用 IntegratedCacheManager 写入的 cache 在新 Cache 下找不到，cache 全 miss + 重新调上游 API。

### 漏洞 2：`save_fundamentals_data` 默认值漂移

- 旧 `IntegratedCacheManager.save_fundamentals_data(symbol, data, data_source: str = "default")`
- 新 `Cache.save_fundamentals_data(symbol, data, data_source: str = "unknown")`

callsite 不显式传 data_source 时（grep 显示全部 callsite 都显式传，但默认值仍是 API 契约），新 Cache 用 `"unknown"` 作 cache_key 一部分，与历史 cache_key 不一致。

### 漏洞 3：`find_cached_stock_data` 缺 `max_age_hours` 兼容性

实际 callsite 在 `tradingagents/dataflows/optimized_china_data.py:115` 等位置传 `max_age_hours` —— 已被 4.4 新 Cache 支持，但 spec 没显式守护，没有回归测试。

## What Changes

### 修改 `_cache.py` — 公开 API 签名兼容性

- `save_stock_data(symbol, data, start_date: str | None = None, end_date: str | None = None, data_source: str | None = None) -> str`
  - 类型签名改为接受 `None`（与 IntegratedCacheManager 字节级一致）
  - 内部 `start_date or ""` / `end_date or ""` / `data_source or "default"` 防御

- `find_cached_stock_data(symbol, start_date=None, end_date=None, data_source=None, max_age_hours=None) -> str | None`
  - 已经支持 None（4.4 阶段做了 `or ""`），加 unit test 守护

- `save_fundamentals_data(symbol, data, data_source: str | None = None) -> str`
  - 默认值改 `None`，内部 `data_source or "default"`（与 IntegratedCacheManager 默认对齐）

- `find_cached_fundamentals_data(symbol, data_source: str | None = None, max_age_hours: int | None = None) -> str | None`
  - 默认值改 `None`，内部 `data_source or "default"`

- `_get_cache_key` 内部 helper 不变（接收已 normalize 的字符串）

### 新增集成 smoke 测试

`tests/test_cache_callsite_smoke.py`（mark `pytest.mark.requires_env`，CI 不强跑、手动验证）：

- 起 file backend，模拟 `_save_to_cache` 路径：`cache.save_stock_data(symbol, df, None, None)` MUST 不 raise + cache_key 字节级与 `cache.save_stock_data(symbol, df, "", "")` 一致
- 历史 cache_key 兼容性：从 4.4 前 IntegratedCacheManager `or ""` 生成的 cache_key（用同 args + `or ""` 模拟）与新 Cache 生成的 MUST 字节级匹配
- `cache.save_fundamentals_data(symbol, data)`（不传 data_source）MUST 生成与 4.4 前默认 `"default"` 一致的 cache_key

### 新增 unit 测试

`tests/test_cache_callsite_compatibility.py`：

- `save_stock_data(symbol, data)` 不传 start/end/source MUST 不 raise + 返非空 cache_key
- `save_stock_data(symbol, data, None, None, None)` 显式传 None MUST 不 raise + cache_key 与 `("","","default")` 一致（字节级守护）
- `save_fundamentals_data(symbol, data)` 默认 data_source MUST 产生与 `"default"` 一致的 cache_key
- `find_cached_stock_data(symbol)` 不传任何 optional MUST 不 raise（None args）
- `find_cached_fundamentals_data(symbol, data_source=None)` 走默认 `"default"` 路径

### 不在 4.5 范围

- **`clear_expired_cache` 方法补齐**：grep 调用方为 0（仅 IntegratedCacheManager 内部 + cache_internal 测试），不补
- **`is_fundamentals_cache_valid` 方法补齐**：调用方 0
- **`save_news_data` / `load_news_data` 补齐**：4.4 已确认外部消费 0
- **集成 endpoint 真实启动测试**：`app/routers/cache.py` 端点的 HTTP 集成测试已属 `requires_env` mark，CI 不跑；手工跑 `just up` + curl 验证已在 4.4 行为兼容验证清单做过
- **历史 cache 数据迁移**：4.5 后用户首次启动会看到一次 cache miss，重新拉数据写入新格式 — graceful，不需要 ETL 脚本

## Capabilities

### Modified Capabilities

- `dataflow-caching`（位于 `docs/specs/dataflow-caching/spec.md`）：**修订** 4.4 Requirement「统一 Cache 类」公开方法签名段，明示所有 `start_date` / `end_date` / `data_source` 参数 MUST 接受 `None`（内部 normalize 到默认值）；ADDED Scenario「cache_key None-safe 字节级兼容」。

## Impact

**改动文件**（1 新 + 2 改）：

- 改：`tradingagents/dataflows/cache/_cache.py`（公开 API 签名 + None 防御）
- 新：`tests/test_cache_callsite_compatibility.py`（unit 测试）
- 改：`docs/specs/dataflow-caching/spec.md`（修订 + 新 Scenario）

**许可边界**：全部在 `tradingagents/dataflows/cache/`（Apache 2.0）+ `tests/`（Apache 2.0）+ `docs/specs/`。**不动** `app/` / `frontend/`。

**风险**：低（signature 加 None 接受 + 内部 normalize 是纯防御性改动，无路径变化）。

**收益**：

- 公开 API 与历史 `IntegratedCacheManager` 完全字节级兼容，历史 cache 文件（4.4 切换前写入的）经 cache_key 计算后仍能命中
- 防御 callsite 类型漂移 — 任何未来 callsite 传 None 都正确 normalize
- 解除 4.4 残留的潜在 silent bug

**回滚**：

单 sub-stage 4 commit，回滚 = `git revert`。

## 与 4.4 的差异点

- 4.4 引入新公开 API 类型；4.5 修补它的签名兼容性漏洞
- 4.4 unit 测试用 mock backends 不连真 DB；4.5 测试同样模式 + 加字节级 cache_key 守护
- 4.4 24 个新 test；4.5 预计 ~6 个 callsite_compatibility test
