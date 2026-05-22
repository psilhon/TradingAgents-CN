## ADDED Requirements

### Requirement: 单一公司名解析入口

`tradingagents/agents/` 下任何 agent 节点（analysts / researchers / managers 等）需要由股票代码得到人类可读公司名时，MUST 通过 `tradingagents.agents.utils.company_resolver.get_company_name(ticker, market_info, agent_label)` 获取。

**禁止**在 agent 文件内自定义 `_get_company_name` / `_get_company_name_for_*` 等本地副本。

#### Scenario: 生产路径 grep 检查

- **WHEN** 在 `tradingagents/agents/` grep `def _get_company_name`
- **THEN** 命中数 MUST = 0
- **AND** 公司名解析的唯一定义在 `tradingagents/agents/utils/company_resolver.py`

#### Scenario: 调用签名统一

- **WHEN** agent 节点调用公司名解析
- **THEN** 调用形态 MUST 为 `get_company_name(ticker, market_info, agent_label)`
- **AND** `agent_label` 仅用于日志前缀，不影响解析结果

### Requirement: 公司名解析行为契约

`get_company_name` MUST 按市场分支解析，行为契约如下：

- **A 股**（`market_info["is_china"]`）：先调 `dataflows.interface.get_china_stock_info_unified`，解析 `股票名称:` 字段；解析前 MUST 做空值守卫（输入为 `None` 不得抛异常）；一级 miss 时 MUST 二级降级到 `dataflows.data_source_manager.get_china_stock_info_unified`；两级都 miss 返回 `f"股票代码{ticker}"`
- **港股**（`market_info["is_hk"]`）：调 `dataflows.providers.hk.improved_hk.get_hk_company_name_improved`；异常时返回 `f"港股{clean_ticker}"`（`clean_ticker` 去掉 `.HK` / `.hk` 后缀）
- **美股**（`market_info["is_us"]`）：查静态字典；miss 返回 `f"美股{ticker}"`
- **未知市场或任意未捕获异常**：返回 `f"股票代码{ticker}"`

函数 MUST NOT 抛异常——所有失败路径降级为带代码的占位名称。

#### Scenario: A 股数据源返回 None 不崩

- **WHEN** `get_china_stock_info_unified` 返回 `None`
- **THEN** `get_company_name` MUST NOT 抛 `TypeError`
- **AND** 落入二级降级或返回 `f"股票代码{ticker}"`

#### Scenario: 美股静态字典命中

- **WHEN** 调用 `get_company_name("AAPL", {"is_us": True, ...})`
- **THEN** 返回 `"苹果公司"`

#### Scenario: 美股静态字典未命中

- **WHEN** 调用 `get_company_name("ZZZZ", {"is_us": True, ...})`
- **THEN** 返回 `"美股ZZZZ"`

#### Scenario: 全部失败降级

- **WHEN** 所有数据源调用失败或市场标志全为 False
- **THEN** 返回 `f"股票代码{ticker}"`（绝不抛异常）
