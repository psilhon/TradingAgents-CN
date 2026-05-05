## Why

`pytest-baseline` 后剩 16 个 collection errors（644 tests collected，其中 16 文件 import-time fail）。各文件 import 失败原因：
- 引用已重组/重命名的模块（`tradingagents.dataflows.akshare_utils`、`tradingagents.dataflows.optimized_china_data` 等已迁到 `providers/china/`）
- import-time 连 mongo（`from pymongo import MongoClient` + 立即连接，端口 27017 不存在）
- 缺第三方包 stub

这些都是 dead test（无法 collection 即无法 run），按 `stable-v1-cleanup` + `pytest-baseline` 一致策略：删。需要时 git history 恢复。

## What Changes

- **REMOVED** 16 个 dead test 文件：
  - tests/system/test_llm_provider_sanitization.py
  - tests/test_akshare_debug.py / test_akshare_priority.py
  - tests/test_amount_fix.py
  - tests/test_dashscope_token_tracking.py
  - tests/test_data_config_cli.py
  - tests/test_financial_data_validation.py
  - tests/test_finnhub_news_fix.py
  - tests/test_news_timeout_fix.py
  - tests/test_query.py / test_user_check.py（import-time 连 mongo）
  - tests/test_sse_and_worker_config.py / test_system_config_summary_sse_queue.py
  - tests/test_tushare_unified/test_tushare_provider.py
  - tests/unit/dataflows/test_unified_dataframe.py
  - tests/unit/test_stocks_kline_news_api.py

预期效果：644 tests collected, **0 collection errors**

## Capabilities

无变更（`lint-policy` spec 已含 pytest collection 干净 scenario）。

## Impact

- 16 dead test 文件删除，git history 仍可恢复
- pytest collection 干净（0 errors）
- 后续可立 `pytest-marker-strict` 设计 marker 体系 + 转严格
