## ADDED Requirements

### Requirement: 数据源 fallback 不得返回伪造业务数据

`tradingagents/dataflows/` 任何 provider / aggregator / cache 层在数据源失败时 MUST NOT 返回**伪造的业务数据**给上游（LLM agent）。具体禁止：

- 用 `random.uniform` / `random.randint` / 静态硬编码值生成假股价 / 假成交量 / 假涨跌幅 / 假财务指标
- 返回 hardcoded "示例" 新闻标题 / 来源 / 发布时间 / 文章内容
- 任何让 LLM 无法区分"真实数据"与"降级占位"的输出格式

允许的降级路径：
- 返回**明确标识**为"数据不可用"的文本（含错误信息，但**不含任何业务字段数字**）
- 返回空数据结构（`[]` / `{}`）让上游聚合层做"无数据"语义处理
- raise 异常让上游决定如何处理

#### Scenario: 数据源失败时的输出

- **WHEN** dataflows 任一 provider 在数据源 API 失败 / 超时 / 鉴权失败时
- **THEN** 返回的字符串 MUST NOT 含任何模拟价格 / 涨跌幅 / 成交量 / 财务指标的具体数字
- **AND** 输出 MUST 含明显的"数据不可用 / 失败"标识让 LLM 跳过分析

#### Scenario: 仓库内 random.uniform 业务数据使用

- **WHEN** 在 `tradingagents/dataflows/` grep `random.uniform` / `random.randint` / `random.choice`
- **THEN** 命中行 MUST NOT 出现在数据返回路径上（仅允许出现在 sleep jitter / cache TTL 抖动 / mock fixture 等非业务返回场景）

#### Scenario: 新闻 stub 输出

- **WHEN** 新闻 aggregator 的搜索 stub（未对接真实新闻源）被调用
- **THEN** 返回 `[]`（空列表）让上游 sentiment 计算自然得到 0 / 无数据
- **AND** **不得**返回 hardcoded `f"{term}相关财经新闻"` 等模板字符串
