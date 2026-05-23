## Why

`cache-layer-consolidation` epic（archived `2026-05-22-cache-backend-unification`）的最终 sub-stage 4.6，紧接 4.5（Cache 公开 API None-safe 签名已落，commit `e13631f2`）。

4.4 给 `IntegratedCacheManager` / `AdaptiveCacheSystem` 加了 `DeprecationWarning` + 保留可用，承诺 4.6 删除。4.5 经历完整的 None-safe 兼容性回归守护后，新 `Cache` 类已字节级兼容历史 callsite 行为，到达拆除老类的时机。

调研外部依赖（commit `e13631f2`）：

```bash
# 0 业务代码引用（grep 命中全在 tests/ 注释 + deprecation test 自身）
$ rg "IntegratedCacheManager|AdaptiveCacheSystem" tradingagents/ app/ --type py | grep -v "tradingagents/dataflows/cache/"
# (no business code matches)

# 0 isinstance 检查（无类型断言会被破坏）
$ rg "isinstance.*(IntegratedCacheManager|AdaptiveCacheSystem)" --type py
# (empty)
```

到达 4.6 删除前置条件：
- ✅ 新 `Cache` 类公开 API 与历史 IntegratedCacheManager 字节级对齐（4.5 守护）
- ✅ 外部业务代码 0 引用 deprecated 类
- ✅ 0 isinstance 类型断言
- ✅ DeprecationWarning 已在 4.4 起触发（观察期完成）

## What Changes

### 删除

- `tradingagents/dataflows/cache/adaptive.py`（整文件，~360 行）
- `tradingagents/dataflows/cache/integrated.py`（整文件，~383 行）
- `tests/test_cache_deprecation.py`（依赖被删类，4.6 起无意义）

### 修改

- `tradingagents/dataflows/cache/__init__.py`：
  - 删除 `from .integrated import IntegratedCacheManager` try-import 块（含 `INTEGRATED_CACHE_AVAILABLE` flag）
  - 删除 `from .adaptive import AdaptiveCacheSystem` try-import 块（含 `ADAPTIVE_CACHE_AVAILABLE` flag）
  - 删除 `__all__` 中的 `"AdaptiveCacheSystem"` / `"IntegratedCacheManager"` / `"ADAPTIVE_CACHE_AVAILABLE"` / `"INTEGRATED_CACHE_AVAILABLE"` 条目
  - `get_cache()` 已走 `Cache` 路径，逻辑不动；但删除 `INTEGRATED_CACHE_AVAILABLE` flag 的条件检查（改用 `UNIFIED_CACHE_AVAILABLE`）

- `docs/specs/dataflow-caching/spec.md`：
  - **删除** 4.4 加的「IntegratedCacheManager / AdaptiveCacheSystem 标记 deprecated」Requirement 整段（含 2 个 Scenario）—— 这些类已删除，Requirement 也失效
  - 加历史注记说明该 Requirement 在 4.6 失效原因（git blame 可追溯到 4.4 archive）

### 保留（不在 4.6 范围）

- `StockDataCache`（`file_cache.py`）：
  - `TA_CACHE_STRATEGY=file` 策略仍走 `StockDataCache`，未迁移到新 `Cache`（迁移属未来工作）
  - 外部仍有 2 个引用：`tradingagents/dataflows/_compat_imports.py` 兼容性 import + `tradingagents/dataflows/providers/us/optimized.py:16-19` fallback `get_cache()` 函数
  - epic proposal 当初写「移除 3 个 deprecated 类」是概述措辞，4.4 实际只 deprecate 了 2 个；4.6 严格按 4.4 deprecation 范围执行

- `cache.save_stock_data` 等公开 API（在新 `Cache` 上）：行为完全不变

- 4.5 加的 `tests/test_cache_callsite_compatibility.py`：守护新 `Cache` 公开 API 行为，4.6 后仍有价值（防止后续修改漂移）

## Capabilities

### Modified Capabilities

- `dataflow-caching`（位于 `docs/specs/dataflow-caching/spec.md`）：**删除** 「IntegratedCacheManager / AdaptiveCacheSystem 标记 deprecated」 Requirement + 2 个相关 Scenario；其余 Cache 类 Requirement 不变。

## Impact

**改动文件**（2 删 + 2 改）：

- 删：`tradingagents/dataflows/cache/adaptive.py`
- 删：`tradingagents/dataflows/cache/integrated.py`
- 删：`tests/test_cache_deprecation.py`
- 改：`tradingagents/dataflows/cache/__init__.py`（删 try-import + __all__ 清理）
- 改：`docs/specs/dataflow-caching/spec.md`（删 deprecation Requirement + Scenarios）

**许可边界**：全部在 `tradingagents/dataflows/cache/`（Apache 2.0）+ `tests/`（Apache 2.0）+ `docs/specs/`。**不动** `app/` / `frontend/`。

**风险**：低

- 0 外部业务代码引用，grep 验证
- 0 isinstance 类型断言
- 4.4-4.5 的 DeprecationWarning 观察期已完成
- `StockDataCache` 保留，`TA_CACHE_STRATEGY=file` 路径不变

**收益**：

- cache 层最终拓扑：1 `Cache` 类 + 3 backends + `CacheConfig` + `StockDataCache`（file 策略备用）
- adaptive.py + integrated.py 总计 ~743 行死代码删除
- DeprecationWarning 触发噪音消除
- epic 收尾，cache-layer-consolidation 完成

**回滚**：

单 sub-stage 4 commit，回滚 = `git revert`。

## 与 4.5 的差异点

- 4.5 修补 4.4 Cache 类签名漏洞；4.6 拆除 4.4 标记 deprecated 的两个老类
- 4.5 加 8 个新 test（callsite_compatibility）；4.6 净删 ~4 个 test（test_cache_deprecation.py 整文件）
- 4.5 改 _cache.py 签名；4.6 删 adaptive.py + integrated.py 整文件
- 4.5 引入 Scenario；4.6 删除 4.4 的 Requirement 段

## 与 epic proposal 范围的偏差

epic proposal 4.6 概述写「移除 3 个 deprecated 类」（暗指 Adaptive / Integrated / StockDataCache）。但 4.4 实际仅 deprecate 了 Adaptive + Integrated 两个；`StockDataCache` 在 4.4 时未加 DeprecationWarning，且 `TA_CACHE_STRATEGY=file` 策略路径 + 2 个 import 外部依赖仍 active。

4.6 严格按 4.4 deprecation 范围执行（删 Adaptive + Integrated），保留 StockDataCache。如未来需要彻底消除 StockDataCache，可开**单独的 sub-stage**（如 4.7 或独立 change）评估 file 策略路径迁移到新 Cache + 处理 2 个外部 import。
