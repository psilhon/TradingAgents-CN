# 1.2 — AKShare patched_get 线程安全 + spec 适度放宽

## Why

**调研结论否决了原 1.2「local Session 替代全局 monkey-patch」方案**：

```
akshare 全包 1305 处直接 `requests.get` / `requests.post`     ← stock 主流模块
仅少数 6 处用 requests.Session()                              ← 仅期货/外汇/其它非 stock
```

akshare 上游 stock 业务代码全是裸 `requests.get(...)`，下游给一个 `requests.Session()` 实例**无法注入到 akshare 调用链**——没有公开 hook 可用。原 1.2 的 spec 要求「第三方库进程级副作用须收敛」字面上不可达。

**实际剩余可改进点 — 线程安全**：

`tradingagents/dataflows/providers/china/akshare.py:61-76` 闭包内：

```python
last_request_time = {"time": 0}  # dict 闭包变量

def patched_get(url, **kwargs):
    if "eastmoney.com" in url:
        current_time = time.time()
        time_since_last_request = current_time - last_request_time["time"]
        if time_since_last_request < 0.5:
            time.sleep(0.5 - time_since_last_request)
        last_request_time["time"] = time.time()
```

`last_request_time` 是普通 dict，**read-check-write 非原子**。两个线程并发调 patched_get：

- T1 读 last=0, since=1.0, 不 sleep, 写 last=now
- T2 同时读 last=0, since=1.0, 不 sleep, 写 last=now

→ 两个线程同时 hit eastmoney.com，rate-limit (0.5s 间隔) 失效。FastAPI 异步 handler 多 worker 场景下 5+ requests 并发就会全部绕过限流，触发反爬封禁。

## What Changes

### `tradingagents/dataflows/providers/china/akshare.py`

闭包内加 `threading.Lock` 保护 read-check-write 块：

```python
import threading  # 顶部 import

# 闭包内（与 last_request_time 同级）
last_request_time = {"time": 0.0}
rate_limit_lock = threading.Lock()

def patched_get(url, **kwargs):
    if "eastmoney.com" in url:
        # Lock 保护原子 read-check-sleep-write — 多线程并发下 rate-limit 仍有效
        with rate_limit_lock:
            current_time = time.time()
            time_since_last_request = current_time - last_request_time["time"]
            if time_since_last_request < 0.5:
                time.sleep(0.5 - time_since_last_request)
            last_request_time["time"] = time.time()
    # ... rest unchanged
```

注意 `time.sleep()` MUST 在 lock 内——否则一个线程 sleep 时其它线程拿不到锁就 hit；要的就是「其它线程等到我 sleep 完」的串行限流语义。

### spec 修订（`docs/specs/dataflows-reliability/spec.md`）

**Requirement「第三方库进程级副作用须收敛」加注**：

> **依赖库不支持 Session 注入时的折中**：若上游依赖库（如 akshare）业务代码绕过 Session 直接调用模块级 `requests.get` / `requests.post`，下游可保留 module-level monkey-patch，但 MUST 满足：
> - patch 行为线程安全（共享状态用 `threading.Lock` 保护）
> - patch 在模块加载时一次性挂载（不在请求路径反复 patch / unpatch）
> - patch 状态可通过明确的 flag（如 `requests._akshare_headers_patched`）查询，禁止重复挂载

**Scenario 修订** — 原「AKShare provider 不污染全局 requests」改为：

```
#### Scenario: AKShare patch 共享状态线程安全

- WHEN 多线程并发调用 patched_get(url=".../eastmoney.com/...")
- THEN rate-limit 共享状态（last_request_time）MUST 经 threading.Lock 保护
- AND 相邻两次同 URL 调用 MUST 至少间隔 0.5s（限流生效，不被并发绕过）
```

## Impact

### Code 变化

`providers/china/akshare.py`：+3 行（`import threading` + `rate_limit_lock = threading.Lock()` + `with rate_limit_lock:` 缩进调整）

### 行为变化

- 单线程：零行为变化（lock acquire/release 微开销可忽略，远小于 HTTP 调用）
- 多线程并发到 eastmoney.com：限流串行化生效，相邻调用 ≥ 0.5s 间隔
- 公开 API：零变化

### 测试

`tests/test_akshare_thread_safety.py` 新建：

- **source-level grep**：断 `akshare.py` 含 `threading.Lock()` + `with rate_limit_lock:`（防回归）
- **行为测试**：起 N 个 thread 并发调 patched_get（mock original_get 为快速 mock + record time），断每两次相邻 mock 调用间隔 ≥ 0.5s

### 用户 / callsite

零破坏：内部线程安全修复，对外不可见。

### 风险

低。`threading.Lock` 是 stdlib，acquire/release 开销 < 1μs，不会成为瓶颈。lock contention 只在多线程并发到 eastmoney.com 时出现，正是要串行的场景。

## Out of Scope

- 替代 akshare 上游（不可行，1305 处需上游改）
- context manager 范围限定（方案 A，作业量 10x 不值得）
- 其它 dataflows 模块的类似 monkey-patch 检查（若发现新的，单独立 stage）
