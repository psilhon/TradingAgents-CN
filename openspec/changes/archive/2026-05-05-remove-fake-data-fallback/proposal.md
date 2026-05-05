## Why

`docs/code-review-2026-05-05.md` 第 1 个 critical 发现：数据源失败时 dataflows 返回**伪造数据**给 LLM agent，模型会拿到假股价 / 假新闻做交易决策——直接污染决策链。

具体违规位点：

1. `tradingagents/dataflows/optimized_china_data.py:2118-2137` `_generate_fallback_data`（A股）：失败时返回含 `random.uniform(10, 50)` 假股价 + `random.uniform(-5, 5)` 假涨跌幅的 markdown 文本
2. `tradingagents/dataflows/optimized_china_data.py:2139-2152` `_generate_fallback_fundamentals`：失败时返回基本面数据"模拟"占位
3. `tradingagents/dataflows/news/chinese_finance.py:143-157` `_search_finance_news`：永远返回硬编码假新闻 `f"{search_term}相关财经新闻标题"`
4. `tradingagents/dataflows/providers/us/optimized.py:490-508` `_generate_fallback_data`（**美股**）：同模式 `random.uniform(100, 300)` 假美股价格——audit 漏抓，本 change 一并修

业务层无法区分"无数据"vs"上游失败 + 假数据兜底"，LLM 把降级误读为真实信号。

## What Changes

- **MODIFIED** `tradingagents/dataflows/optimized_china_data.py`：
  - 删 `_generate_fallback_data` + `_generate_fallback_fundamentals` 两个方法
  - 替换为 `_render_data_unavailable` + `_render_fundamentals_unavailable`：返回明确的"数据不可用"标识 markdown（无任何数字字段）
  - 删 `import random`（unused）
- **MODIFIED** `tradingagents/dataflows/providers/us/optimized.py`：同模式删 `_generate_fallback_data` + `import random`，替换为 `_render_data_unavailable`
- **MODIFIED** `tradingagents/dataflows/news/chinese_finance.py:143`：
  - `_search_finance_news` 返回 `[]`（空列表）+ 加 `# TODO` 注释说明这是 stub，需接真实新闻源
  - `analyze_news_sentiment` 在收到空列表时已能正常处理（line 132 的 `if sentiment_scores else 0`）
- **NEW** capability `dataflow-integrity`：定义"数据源 fallback 不得返回伪造业务数据"铁律

## Capabilities

### New Capabilities

- `dataflow-integrity`：禁止假数据兜底污染 LLM 决策链

## Impact

**改动文件**：2 个 Python 文件 + 1 个新 spec
**风险**：低——降级路径输出更明确，agent 可正常处理"无数据"语义
**收益**：消除 LLM 决策被假股价 / 假新闻污染的风险（critical 级安全缺陷）
