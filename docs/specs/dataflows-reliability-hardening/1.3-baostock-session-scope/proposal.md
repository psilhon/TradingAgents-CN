# 1.3 — baostock session lifecycle 收敛 (refcount + lock)

## Why

`tradingagents/dataflows/providers/china/baostock.py` 当前 **12 处散落 `bs.login()` + 12 处 `bs.logout()`**——`test_connection` / `get_stock_list_sync` / `get_stock_list` / `get_valuation_data` / `_get_stock_info_detail` / `_get_latest_kline_data` / `get_historical_data` + 5+ 其它 query 方法各自独立 login/logout。

baostock 模块级 `bs.login()` / `bs.logout()` **进程级单例**——共享一个 session。并发调用会互相干扰：

```
T1: bs.login() → session active
T2: bs.login() → session active (reuse same session)
T1: bs.query_stock_basic() → start fetching
T2: bs.logout() → session closed (!)
T1: bs.query iteration → fails (session closed)
```

FastAPI multi-worker / asyncio 多 task 场景下，盘中数据并发拉取会随机失败。

`docs/code-review-2026-05-05.md` 第二域 dataflows High finding：
> baostock per-call login/logout — 7-10 处散落 + 并发互踩

`docs/specs/dataflows-reliability/spec.md` Requirement「外部 session 单例须线程安全」+ Scenario「baostock session 单一入口」已就位，本 sub-stage 落实。

## What Changes

### `tradingagents/dataflows/providers/china/baostock.py`

引入 module-level `_BaoStockSession` 单例 + context manager：

```python
import threading
from contextlib import contextmanager


class _BaoStockSession:
    """Process-level baostock session lifecycle manager (refcount + lock).
    
    baostock module-level login() / logout() share one process session.
    Concurrent callers without coordination cause one thread's logout to
    invalidate another's active query. This manager:
    
    - threading.Lock 保护 refcount + login state
    - First scope acquire 触发 bs.login()
    - Subsequent scope acquire 共享同 session（refcount++）
    - Last scope release（refcount→0）触发 bs.logout()
    """
    _lock = threading.Lock()
    _refcount = 0
    _logged_in = False
    
    @classmethod
    @contextmanager
    def scope(cls, bs):
        """Acquire session for the duration of this `with` block.
        
        Raises Exception on login failure (consistent with existing callsites
        which check `lg.error_code != '0'`).
        """
        # Acquire
        with cls._lock:
            if cls._refcount == 0:
                lg = bs.login()
                if lg.error_code != "0":
                    raise Exception(f"BaoStock登录失败: {lg.error_msg}")
                cls._logged_in = True
            cls._refcount += 1
        try:
            yield
        finally:
            # Release
            with cls._lock:
                cls._refcount -= 1
                if cls._refcount == 0 and cls._logged_in:
                    try:
                        bs.logout()
                    except Exception as e:
                        logger.warning(f"baostock logout error (ignored): {e}")
                    cls._logged_in = False
```

12 处 query 方法改造模板（每处 ~3-4 行变更）：

**Before**:
```python
def fetch_stock_list():
    lg = self.bs.login()
    if lg.error_code != "0":
        raise Exception(f"登录失败: {lg.error_msg}")
    try:
        rs = self.bs.query_stock_basic()
        # ... process rs ...
        return df
    finally:
        self.bs.logout()
```

**After**:
```python
def fetch_stock_list():
    with _BaoStockSession.scope(self.bs):
        rs = self.bs.query_stock_basic()
        # ... process rs ...
        return df
```

12 处 `lg = self.bs.login()` → `with _BaoStockSession.scope(self.bs):`；12 处 `self.bs.logout()` 删除（scope context manager 接管 lifecycle）。

### spec delta

`docs/specs/dataflows-reliability/spec.md` Requirement「外部 session 单例须线程安全」+ Scenario「baostock session 单一入口」**已就位**，本 sub-stage 直接落实，无需 spec 修订。

## Impact

### Code 变化

`providers/china/baostock.py`：

- `_BaoStockSession` 单例 class：+35 行
- 12 处 query 方法去散落 login/logout：净 -~30 行（每处 ~2 行 boilerplate 消失）
- 总净变化：约 +5 行（代码量基本持平，复杂度下降）

### 行为变化

- 单线程顺序调多个 query 方法：之前 N 次 login/logout 往返；现在仅 1 次 login（首次）+ 1 次 logout（最后）—— 性能提升
- 并发调用：T1 login → T2 共享 session → T1 finish refcount-1 → T2 logout 触发 → 串行化的 session lifecycle
- 嵌套 with（同一线程内 query 调用 query 方法）：refcount 累加，正确释放
- 错误：login 失败保持 raise Exception；logout 失败仅 warning（既有行为）

### 测试

`tests/test_baostock_session_scope.py` 新建：

- **source-level grep**：断 baostock.py
  - `_BaoStockSession` class 定义存在
  - `with _BaoStockSession.scope(` 命中 ≥ 7 个（query 方法数）
  - `self.bs.login()` 散落命中 = 0（除非在 `_BaoStockSession` 内）
  - `self.bs.logout()` 散落命中 = 0
- **行为测试**（mock bs.login + bs.logout）：
  - 单线程嵌套 with：login 仅调 1 次 + logout 仅调 1 次
  - 多线程 5 并发 with：login/logout 仍仅 1 次（refcount 合并）
  - login 失败：with 块抛 Exception + refcount 不增
  - logout 失败：with 块出口不 raise（仅 warning）

### 用户 / callsite

零破坏：

- 公开 API 不变（query 方法签名 / 返回值 / 异常行为字节级保持）
- baostock 数据查询逻辑零变化
- 单进程多线程 baostock 调用从「随机失败」→「稳定串行」

### 风险

低-中：

- baostock 是否真的支持「先 login 一次，多线程并发 query」语义？文档说 session 是 process-level，重复 login 返回同 session；并发 query 应该是支持的（baostock 自身没有并发警告）。若实测发现 baostock 内部对并发 query 限制，需切换为「query 串行化」方案——但这属于后续 stage，本 sub-stage 仅解决 login/logout 互踩，已是显著改进
- _BaoStockSession 是 class-level state（不是 instance attr）：跨 BaoStockProvider 实例共享 session，符合 baostock 模块级 session 语义；但 `_lock` / `_refcount` 跨进程重置正常（每进程独立）

## Out of Scope

- 切换到 baostock 上游推荐的 client 模式（baostock 无 client API）
- 业务逻辑修复（query 解析错误等，属各方法的 capability）
- baostock 真并发 query 限制的实测验证（属性能测试，本 stage 仅修死锁/互踩）
