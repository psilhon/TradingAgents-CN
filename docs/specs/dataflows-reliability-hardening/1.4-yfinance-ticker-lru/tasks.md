# 1.4 — yfinance.Ticker LRU 缓存 tasks

- [ ] **commit 1**：立项
  - `docs/specs/dataflows-reliability-hardening/1.4-yfinance-ticker-lru/{proposal,tasks}.md`
  - commit："docs(spec): 立项 stage 1.4 — yfinance Ticker LRU"

- [ ] **commit 2**：red + green + CHANGELOG
  - `tests/test_yfinance_ticker_cache.py` red：spy `yf.Ticker`，断同 symbol 多次调用 ctor 仅触发 1 次 + case-insensitive 合并
  - `tradingagents/dataflows/providers/us/yfinance.py`：加 `functools.lru_cache(maxsize=128)` 包 `_get_ticker(symbol)` helper；3 处调用点（line 46 / 163 / 272）改调 helper
  - `just ci` 全绿
  - `docs/CHANGELOG.md` `[Unreleased]` Changed 段追加条目
  - commit："perf(dataflows): 1.4 — yfinance.Ticker LRU 缓存 (maxsize=128)"

- [ ] **Push**：由用户 1-click `git push origin main`

## 验证

- [ ] `just ci` 441+ passed（baseline 441 from 1.1）
- [ ] grep `yf.Ticker(` in providers/us/yfinance.py 命中 1（只在 `_get_ticker` helper 内）
