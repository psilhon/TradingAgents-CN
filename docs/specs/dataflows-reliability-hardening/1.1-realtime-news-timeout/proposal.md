# 1.1 — realtime_news timeout hotfix

## Why

`tradingagents/dataflows/news/realtime_news.py` 内 `RealtimeNewsAggregator` 三个 fetch 方法：

- `_get_finnhub_news` (line 162) → FinnHub `/company-news` 
- `_get_alpha_vantage_news` (line 204) → Alpha Vantage `NEWS_SENTIMENT`
- `_get_newsapi_news` (line 260) → NewsAPI.org `/everything`

都用 `requests.get(url, params=params, headers=self.headers)` **不带 timeout**——这是 user-facing 路径（实时新闻聚合，由 agent 节点直接调用），任一 API 故障 / 网络分区 / DNS 失败时 `requests.get` 默认无限阻塞，拖死整条 agent 链。

`docs/code-review-2026-05-05.md` 第二域 dataflows High finding：
> tradingagents/dataflows/news/realtime_news.py:162,204,260 — 三处 requests.get 无 timeout，会无限挂起

`news/google_news.py:46` 已经按 `timeout=(10, 30)` 惯例修过，本 stage 把同惯例同步到 realtime_news 三处。

## What Changes

### `tradingagents/dataflows/news/realtime_news.py`

三处 `requests.get(...)` 调用各加 `timeout=(10, 30)` 元组参数：

```python
# line 162 (FinnHub)
response = requests.get(url, params=params, headers=self.headers, timeout=(10, 30))
# line 204 (Alpha Vantage)
response = requests.get(url, params=params, headers=self.headers, timeout=(10, 30))
# line 260 (NewsAPI)
response = requests.get(url, params=params, headers=self.headers, timeout=(10, 30))
```

### spec delta（已落 capability spec）

`docs/specs/dataflows-reliability/spec.md` Requirement「HTTP 请求必须设 timeout」已含 Scenario「realtime_news 三处 API 调用必须带 timeout」。本 sub-stage 落实该 Scenario。

## Impact

### Code 变化

`news/realtime_news.py`：净 +3（3 行 `timeout=(10, 30)` 参数追加）

### 行为变化

- 故障路径：FinnHub / Alpha Vantage / NewsAPI 网络挂 / DNS 失败 → 10s connect + 30s read 后抛 `requests.Timeout` → 已有 `except Exception` 路径接住 → log error + 返 `[]` 空列表（与现有 fallback 语义一致）
- 正常路径：API < 30s 响应 → 零行为变化（timeout 仅触发故障路径）

### 测试

`tests/test_realtime_news_timeout.py` 新建：

- mock `requests.get` 验证 `_get_finnhub_news` / `_get_alpha_vantage_news` / `_get_newsapi_news` 的 call_args.kwargs 含 `timeout=(10, 30)`
- 不依赖真实 API 调用（unit 范围）

### 用户 / callsite

零破坏：公开 API 行为不变；仅缩短最坏情况延迟（无限 → 40s）。

### 风险

低。`timeout=(10, 30)` 是 google_news 同惯例，已在生产路径验证。
