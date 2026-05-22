## Why

`docs/code-review-2026-05-05.md` 第三梯队架构重构项 `extract-company-resolver`。

`tradingagents/agents/` 下有 **7 份近乎相同的 `_get_company_name` 拷贝**：

| 文件 | 函数名 | 形态 |
|---|---|---|
| `researchers/bull_researcher.py` | `_get_company_name`（嵌套） | 精简版 |
| `researchers/bear_researcher.py` | `_get_company_name`（嵌套） | 精简版 |
| `analysts/market_analyst.py` | `_get_company_name`（模块级） | 完整版 |
| `analysts/social_media_analyst.py` | `_get_company_name_for_social_media` | 完整版 |
| `analysts/fundamentals_analyst.py` | `_get_company_name_for_fundamentals` | 完整版 |
| `analysts/china_market_analyst.py` | `_get_company_name_for_china_market` | 完整版 |
| `analysts/news_analyst.py` | `_get_company_name`（嵌套） | **异常版** |

**这不是纯机械重复——7 份已经分歧**：

1. **4 个 analyst 模块级拷贝**（market / social_media / fundamentals / china_market）：仅日志前缀 `[XXX分析师]` 不同，逻辑一致。含 A 股两级降级（统一接口 → `data_source_manager`）+ `stock_info and` 空值守卫 + 港股 improved 工具 + 美股 8 项静态字典。
2. **bull / bear researcher 精简版**：缺 A 股 miss 路径的 `data_source_manager` 二级降级；参数名为 `ticker_code` / `market_info_dict`。
3. **news_analyst 异常版**：A 股分支**无二级降级**，且 `if "股票名称:" in stock_info` **缺 `stock_info and` 空值守卫**——`get_china_stock_info_unified` 返回 `None` 时抛 `TypeError`（latent bug）；未知市场返回 `f"股票{ticker}"` 而非 `f"股票代码{ticker}"`。

任何对公司名解析逻辑的修订都得改 7 处，且新代码会继续在某个拷贝旁长出第 8 份。美股硬编码字典 `{AAPL: 苹果公司, ...}` 也复制了多份。

## What Changes

### 设计：canonical 行为调和

7 份合并为 1，取 **analyst 模块级版本为 canonical 行为**（4/7 多数派 + 行为最完整 + 有空值守卫）：

- **A 股**：`get_china_stock_info_unified` 统一接口 → 解析 `股票名称:`（带 `stock_info and` 空值守卫）→ miss 时二级降级 `data_source_manager.get_china_stock_info_unified` → 最终 `f"股票代码{ticker}"`
- **港股**：`improved_hk.get_hk_company_name_improved` → 异常时 `f"港股{clean_ticker}"`
- **美股**：8 项静态字典 → miss 时 `f"美股{ticker}"`
- **未知市场 / 外层异常**：`f"股票代码{ticker}"`
- 日志前缀通过 `agent_label` 参数注入（如 `"市场分析师"`），不再硬编码

**行为变化（均为修正方向，proposal 显式声明）**：
- `news_analyst`：获得 `stock_info and` 空值守卫 → 修掉 `stock_info=None` 时的 `TypeError`；获得 A 股二级降级
- `bull` / `bear` researcher：获得 A 股二级降级
- 美股 / 港股 / A 股成功路径行为不变

### 改动清单

- **NEW** `tradingagents/agents/utils/company_resolver.py`：
  - `get_company_name(ticker: str, market_info: dict, agent_label: str = "分析师") -> str`
  - canonical 行为如上；自带 `logger`
- **NEW** `tests/test_company_resolver.py`：单元测试（`@pytest.mark.unit`），mock `dataflows` 依赖
- **MODIFIED** 7 个 call site：删除各自的 `_get_company_name*` 定义，改 `from tradingagents.agents.utils.company_resolver import get_company_name` + 传 `agent_label`
  - `researchers/{bull,bear}_researcher.py`（嵌套 def → 删）
  - `analysts/{market,social_media,fundamentals,china_market,news}_analyst.py`（模块级 / 嵌套 def → 删）
- **MODIFIED** `docs/CHANGELOG.md`：`[Unreleased]` 加一段

### 不在本 change 范围（YAGNI）

- 改进美股名称解析（8 项静态字典是已有最低实现，保留原样，只集中化——扩展是独立 concern）
- A 股 / 港股数据源链本身的重构（属 `dataflow-integrity` capability）
- 其它 agent 内重复（`should_continue_*` 4 份、stream 循环 3 份——见 code-review 第三梯队其它项）

## Capabilities

### New Capabilities

- `agent-company-resolution`：agent 层公司名解析单一入口 + 解析行为契约（A 股两级降级 / 港股 improved 工具 / 美股静态字典 / 缺省 `股票代码{ticker}`），锁定后未来不得再 fork 成多份。

## Impact

**改动文件**：1 新建 source + 1 新建 test + 7 个 call site 修改 + 1 spec + 1 CHANGELOG 段

**许可边界**：全部在 `tradingagents/agents/`（Apache 2.0）——不触及 `app/` `frontend/` 专有授权代码，`guard-proprietary` hook 不触发，无需 `.implementing` marker。

**风险**：低
- 纯内部重构，无 API / schema 变化
- 唯一行为变化是 3 个 call site 获得更完整的降级路径 + 1 个 latent TypeError 修复——均为修正方向
- 7 个 call site 的调用点签名统一为 `get_company_name(ticker, market_info, agent_label)`，原签名 `(ticker, market_info)` / `(ticker_code, market_info_dict)` 形态各异，迁移时逐一核对

**收益**：
- 7 份拷贝 → 1 份，公司名解析逻辑修订从「改 7 处」降为「改 1 处」
- 修掉 `news_analyst` 的 `stock_info=None` latent TypeError
- 美股硬编码字典单一来源
- 新 capability 锁定契约，杜绝第 8 份拷贝
