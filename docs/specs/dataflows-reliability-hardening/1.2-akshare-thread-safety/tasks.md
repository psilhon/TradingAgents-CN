# 1.2 — AKShare patched_get 线程安全 tasks

## 调研结论

- akshare 上游 1305 处直接 `requests.get`/`requests.post`，**不走 Session**
- 原 1.2「local Session 替代」方案不可行——切换为「保留 monkey-patch + 线程安全」
- 详见 proposal.md「Why」段

## 实施步骤

- [ ] **commit 1**：立项 + spec 修订
  - 创建 `docs/specs/dataflows-reliability-hardening/1.2-akshare-thread-safety/{proposal,tasks}.md`
  - 修订 `docs/specs/dataflows-reliability/spec.md`：
    - Requirement「第三方库进程级副作用须收敛」加注「依赖库不支持 Session 注入时的折中」段
    - Scenario「AKShare provider 不污染全局 requests」改名为「AKShare patch 共享状态线程安全」
  - commit："docs(spec): 立项 stage 1.2 — AKShare patched_get 线程安全 + spec 适度放宽"

- [ ] **commit 2**：red + green + CHANGELOG
  - `tests/test_akshare_thread_safety.py` red：
    - source-level grep 断 `threading.Lock` + `with rate_limit_lock:` 存在
    - 行为测试：起 5+ thread 并发调 patched_get（mock original_get），断相邻调用间隔 ≥ 0.5s
  - `tradingagents/dataflows/providers/china/akshare.py` green：
    - 顶部 `import threading`
    - 闭包内加 `rate_limit_lock = threading.Lock()`
    - read-check-sleep-write 块包到 `with rate_limit_lock:` 内
  - `just ci` 全绿
  - `docs/CHANGELOG.md` `[Unreleased]` Fixed 段追加条目
  - commit："fix(dataflows): 1.2 — AKShare patched_get 共享状态 threading.Lock 保护"

- [ ] **Push**：由用户 1-click `git push origin main`

## 验证

- [ ] `just ci` 448+ passed
- [ ] grep `threading.Lock` 在 akshare.py 命中 1+
- [ ] grep `rate_limit_lock` 在 akshare.py 命中 ≥ 2（声明 + with 块）

## 不在 1.2 范围

- akshare 上游 PR / Session 注入（不可行，详见 proposal）
- 其它 monkey-patch 模式审计（若发现新的单独立 stage）
