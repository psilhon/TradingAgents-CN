# dataflows-reliability-hardening Epic Tasks

按 sub-stage 推进，每 sub-stage 内 TDD red/green。每 stage 独立 commit + 独立 push。

## Sub-stage 1.1 — realtime_news timeout hotfix

- [ ] **立项**：`docs/specs/dataflows-reliability-hardening/1.1-realtime-news-timeout/proposal.md` + tasks.md
- [ ] **spec delta**：dataflows-reliability/spec.md 加 Requirement「HTTP 请求必须设 timeout」+ 2 个 Scenario（已 done as part of capability spec 立项）
- [ ] **red**：`tests/test_realtime_news_timeout.py` —— mock `requests.get`，断 3 处 call_args.kwargs 含 `timeout=(10, 30)` 元组
- [ ] **green**：`tradingagents/dataflows/news/realtime_news.py:162/204/260` 加 `timeout=(10, 30)` 参数
- [ ] **跑** `pytest tests/test_realtime_news_timeout.py` 全绿
- [ ] **CHANGELOG**：`[Unreleased]` Fixed 段加条目
- [ ] **commit**：`fix(dataflows): 1.1 — realtime_news 3 处 requests.get 加 timeout`

## Sub-stage 1.2 — AKShare requests.get 范围收缩

- [ ] **调研** akshare 内部是否走全局 `requests.get`：源码读 `akshare/stock_feature/stock_zh_a.py` 等核心模块
- [ ] **立项**：1.2 proposal + tasks
- [ ] **red**：`tests/test_akshare_session.py` —— 断 `requests.get` 未被改写 + module level `_akshare_session` 暴露 + headers 正确
- [ ] **green**：构造 module-level `requests.Session` + 注入 headers/hooks + 调用现场用 session
- [ ] **CHANGELOG** + commit

## Sub-stage 1.3 — baostock session lifecycle 收敛

- [ ] **立项**：1.3 proposal + tasks
- [ ] **red**：`tests/test_baostock_session.py` —— mock `bs.login/logout`，断 7-10 处方法只触发 1 次 login（context manager 嵌套复用）+ 多线程并发不互踩
- [ ] **green**：抽 `_baostock_session_scope` context manager + refcount + threading.Lock
- [ ] **CHANGELOG** + commit

## Sub-stage 1.4 — yfinance Ticker LRU

- [ ] **立项**：1.4 proposal + tasks
- [ ] **red**：`tests/test_yfinance_ticker_cache.py` —— spy `yf.Ticker`，断重复同 symbol 调用 ctor 仅 1 次
- [ ] **green**：`@functools.lru_cache(maxsize=128)` 包 `_get_ticker(symbol)` helper
- [ ] **CHANGELOG** + commit

## Push 节点

每 sub-stage 完成 commit 后由用户 1-click `git push origin main`。

## 不在 epic 范围

详见 proposal.md 「Out of Scope」段。
