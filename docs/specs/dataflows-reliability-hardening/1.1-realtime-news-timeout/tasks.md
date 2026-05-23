# 1.1 — realtime_news timeout hotfix tasks

- [ ] **commit 1（本次）**：立项 + spec delta
  - 创建 `docs/specs/dataflows-reliability/spec.md`（capability spec，含 4 Requirement + 7 Scenario）
  - 创建 `docs/specs/dataflows-reliability-hardening/{proposal,tasks}.md`（epic 蓝本）
  - 创建本目录 `1.1-realtime-news-timeout/{proposal,tasks}.md`
  - commit："docs(spec): 立项 dataflows-reliability-hardening epic + stage 1.1"

- [ ] **commit 2**：red + green + CHANGELOG
  - `tests/test_realtime_news_timeout.py` red：mock requests.get，断 3 处 call_args 含 `timeout=(10, 30)`
  - `tradingagents/dataflows/news/realtime_news.py`：3 处加 `timeout=(10, 30)`（green）
  - `just ci` 全绿
  - `docs/CHANGELOG.md` `[Unreleased]` Fixed 段追加条目
  - commit："fix(dataflows): 1.1 — realtime_news 3 处 requests.get 加 timeout"

- [ ] **Push**：由用户 1-click `git push origin main`
