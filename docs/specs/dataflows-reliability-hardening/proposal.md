# dataflows-reliability-hardening Epic

## Why

`docs/code-review-2026-05-05.md` 报的 dataflows 反模式经 v1.3.x 多轮治理后，仍有 4 项 reliability finding 实际未修：

1. `news/realtime_news.py:162,204,260` 三处 `requests.get` 无 timeout——FinnHub / Alpha Vantage / NewsAPI 故障时无限挂起拖死 agent 链
2. `providers/china/akshare.py:59-152` monkey-patch `requests.get` 全进程副作用——影响全进程所有 HTTP 调用，闭包内 `last_request_time` dict 非线程安全
3. `providers/china/baostock.py` 7-10 处散落 `bs.login()` + `bs.logout()`——baostock 进程级 session 单例，并发互相 logout
4. `providers/us/yfinance.py:41-52` `init_ticker` decorator 每次方法调用重建 `yf.Ticker(symbol)`——无 LRU

cache-backend-unification epic 收尾后这些 finding 实质阻塞了 dataflows 层的 reliability 基线。立 epic 一次性收敛——分 4 个 sub-stage 按风险从小到大递进，每个独立可验证。

## What Changes

### 新建 capability spec `docs/specs/dataflows-reliability/spec.md`

锁定 4 个 reliability 契约（已落地）：

- **HTTP 请求必须设 timeout** — 4 个 Scenario 覆盖 realtime_news 3 处 + 全目录 grep 守护
- **第三方库进程级副作用须收敛** — AKShare 不污染全局 requests
- **外部 session 单例须线程安全** — baostock session 单一入口
- **第三方 client 实例须缓存** — yfinance.Ticker 复用

### 4 个 sub-stage

#### 1.1 — realtime_news timeout hotfix

`tradingagents/dataflows/news/realtime_news.py` 3 处 `requests.get(url, params=params, headers=self.headers)` → 加 `timeout=(10, 30)`（与 `news/google_news.py:46` 同惯例）。

工作量：半天。

#### 1.2 — AKShare requests.get monkey-patch 范围收缩

将 `tradingagents/dataflows/providers/china/akshare.py:55-152` 的 `requests.get = patched_get` 全局覆写改为：

- 构造 module-level `_akshare_session: requests.Session` 实例
- 注入 headers / 添加 hooks / 限流逻辑到 session
- AKShare 调用现场用 session 而非裸 `requests.get`
- 删除全局 `requests._akshare_headers_patched` flag

工作量：1-2 天。需要测 AKShare 内部是否实际能用我们的 session（akshare 内部走 `requests.get` 还是有自己的 session？需调研）。

#### 1.3 — baostock session lifecycle 收敛

将 `tradingagents/dataflows/providers/china/baostock.py` 7-10 处散落的 `bs.login()` + `bs.logout()` 改为：

- module-level `_baostock_session_scope` context manager（`with _baostock_session_scope(): df = bs.query_xxx()`)
- 内部用 `threading.Lock` 保护 + refcount（嵌套调用复用 session）
- 所有 query 方法 wrap 在 context manager 内

工作量：1-2 天。

#### 1.4 — yfinance.Ticker LRU

将 `tradingagents/dataflows/providers/us/yfinance.py:41-52` 的 `init_ticker` decorator 改为：

- module-level `@functools.lru_cache(maxsize=128)` 缓存 `_get_ticker(symbol)` helper
- decorator 内调用 `_get_ticker(symbol)` 而非 `yf.Ticker(symbol)` 直构造
- 2 处散落 `yf.Ticker(symbol.upper())`（line 163, 272）也走 helper

工作量：半天。

## Impact

### Code 变化

| Stage | 文件 | 行数变化 |
|---|---|---|
| 1.1 | `news/realtime_news.py` | +3（3 处加 `timeout` 参数） |
| 1.2 | `providers/china/akshare.py` | -50 ~ +30（删 monkey-patch + 加 Session） |
| 1.3 | `providers/china/baostock.py` | -30 ~ +60（抽 context manager） |
| 1.4 | `providers/us/yfinance.py` | -5 ~ +20（加 LRU helper） |

### Spec

`docs/specs/dataflows-reliability/spec.md` 新建（4 Requirement + 7 Scenario）。

### 测试

每 sub-stage 加自己的单元测试：

- 1.1：`tests/test_realtime_news_timeout.py`（mock requests，断 call_args 含 timeout）
- 1.2：`tests/test_akshare_session.py`（断 `requests.get` global 未被改、AKShare session 含 headers）
- 1.3：`tests/test_baostock_session.py`（断 login/logout 仅在 helper 内 + 并发不互踩）
- 1.4：`tests/test_yfinance_ticker_cache.py`（spy `yf.Ticker`，断重复同 symbol 调用 ctor 仅 1 次）

### 用户 / callsite

零破坏：所有变化都是内部 reliability fix，对外公开 API 行为不变。

### 风险

- 1.2 最高：akshare 内部是否真用我们的 Session 需调研；若 akshare hardcode 走全局 `requests.get`，需保留某种 patch 但范围收缩到 contextmanager
- 1.3 中：baostock session 并发模型需测试覆盖
- 1.1 / 1.4 最低：纯内部行为优化

### Push 策略

每 sub-stage 独立 commit + 用户 1-click push（按 cache epic 4.7-4.8 惯例）。

## Out of Scope

- 业务逻辑修复（属各 provider capability spec）
- pandas DataFrame schema 一致性（属 data-audit 类 capability）
- cache 层契约（属 `dataflow-caching`）
- 上游 PR / pip 包升级（外部依赖，不在本 epic 范围）
