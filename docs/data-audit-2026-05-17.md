# 数据正确性系统审计 — 2026-05-17

> 触发：用户反馈「股票筛选市值字段完全不可用、内容错误」。一个交易分析系统对数据错误零容忍，遂做全链路排查。
> 方法：`/diagnose` 流程 —— 建数据审计脚本（`/tmp/data_audit.js`）直连 MongoDB 逐字段验证 → 回溯代码根因。
> 结论：**这不是单个 bug，是系统性的数据质量崩塌。** 当前数据库状态下，筛选、每日推荐、基本面分析的结论均不可信。

## 现象纠偏

用户截图里「市值 -158.10 / -242.51」**不是市值，是 pe 值**：

| 股票 | tushare 源 pe | akshare 源 pe |
|---|---|---|
| 卓胜微 300782 | **-158.10** | -207.40 |
| 光莆股份 300632 | **-242.51** | -308.83 |

真正的市值列（`total_mv`）是**空白**——前端 `formatMarketCap` 遇到 `undefined` 直接抛错，渲染为空，用户把相邻的市盈率列当成了市值列。

---

## P0 — 数据错误，直接误导分析/交易决策

### 1. `stock_basic_info` 三倍重复

- 集合 16557 docs，但只有 **5841 个真实股票代码**。每只股票存 3 份（tushare / akshare / baostock 各一）。
- **根因**：upsert key 是复合键 `(code, source)`（`app/services/multi_source_basics_sync_service.py:284`，唯一索引 `code_source_unique` 同理）。每个数据源各写一份，从不合并成一条。`5841 × ~3 ≈ 16557`。
- **影响**：下游所有读这张表的逻辑都看到 ×3 行。`screening_service._get_universe()` 取的 universe 含重复 code；统计/计数全部偏差。screening 靠 `database_screening_service` 里 `query["source"]=source` 过滤才勉强不爆——这是脆弱补丁，不是设计。

### 2. 总市值 99.9% 缺失 / 流通市值 100% 缺失

- `total_mv` 仅 20/16557 有值（0.1%）；`circ_mv` **0 条**。
- **根因**：最近一次 sync 用 akshare（`sync_status.data_sources_used: ['stock_list:akshare']` 实证）。
  - `akshare_adapter.get_daily_basic` 写死 `max_stocks=10`、不取 `circ_mv`、`pe/pb/turnover_rate` 写死 `None`。
  - `baostock_adapter` 显式 `total_mv=None`，无 `circ_mv` 字段。
  - 只有 `tushare_adapter` 真正请求 `total_mv,circ_mv`，但 tushare `daily_basic` 调用失败被 `except` 吞掉（`tushare_adapter.py:95-97`）→ 静默降级到没有市值的 adapter。
- **影响**：① 市值列空白；② 「市值范围」筛选永远 0 结果；③ 见下连锁后果。

### 3. `pe` / `pb` / `ps` 数据不可信

- 覆盖率仅 62.8%（10406/16557）。
- 同一只股票不同源数值差 20-40%：卓胜微 akshare `pe=-207` vs tushare `pe=-158`。
- 出现**数学上不可能**的负 `ps`：*ST天箭 `ps=-17.4`、*ST仕净 `ps=-32.6`（营收恒 ≥ 0，price-to-sales 不可能为负）。
- 极端量级：康希诺 `pe=-16622`、光大同创 `pe=-7872`。
- **根因**：cross-source 不一致零 reconcile；写库前无 sanity 校验；`data_consistency_checker` 存在但只是个比较/报告工具，不拦写入（且有两份重复文件：`app/services/` 与 `app/services/data_sources/` 各一）。

### 4. `stock_financial_data` 全字段为 null

- 10 docs，`revenue / net_income / total_assets / total_equity` **全部 null**；`report_period` 还是未来季度 `20260630`。
- **根因**：tushare 财报接口（income/balancesheet/cashflow）权限受限，调用失败被逐层 `except` 吞掉 → standardizer 仍用空 dict `{}` 拼出一个「全 null 但非空」的 dict → 写库逻辑 `if financial_data:` 判真 → 写入一行垃圾。
- **影响**：基本面分析无数据。

### 连锁后果 — 新功能「每日推荐」已被污染

- 今日（2026-05-17）daily_recommendations 配置 `order_by: market_cap`。`total_mv` 全 null → 按全 null 字段排序 → **推的根本不是市值前 5，而是任意 5 只**。
- 实证：今日推出万泰生物 / 爱乐达 / 中大力德 / 振江股份 / 海川智能 —— 明显都不是 A 股市值前 5（真·前 5 应是茅台 / 工行级）。
- 更糟：海川智能那条 AI 结论原话写了「**缺乏最新财务数据支撑**」—— 垃圾数据已经流进 LLM 分析输出。

---

## P1 — 数据陈旧 / 不一致

| # | 问题 | 证据 |
|---|---|---|
| 5 | 实时行情采集 job 已失败 3 天 | `quotes_ingestion_status`: `success:false`, `error_message:'未获取到行情数据'`, last_sync `2026-05-14` |
| 6 | `market_quotes` 估值字段几乎全空 | total_mv 0/5850、circ_mv 0/5850、pe 3/5850、pb 3/5850；327 只股票行情卡在 9 天前（trade_date=20260507） |
| 7 | 日期格式不统一 | 同一个 `market_quotes` 集合 trade_date 既有 `20260516` 又有 `2026-05-17`；`stock_daily_quotes` 用 `2025-05-16` |
| 8 | 交易所后缀不统一 | `market_quotes` 上交所用 `.SS`，`stock_daily_quotes` 用 `.SH`；`market_quotes` 绝大多数 doc 没有 `full_symbol` |
| 9 | 字段名分裂 | `source`（16557 docs）vs `data_source`（5203 docs）并存；screening_view 财务 join 用 `data_source==source`，因命名不一致而几乎 join 不上 |
| 10 | `stock_daily_quotes.pre_close` 100% null | 2415/2415 全 null（但 `change` 字段非 null） |

---

## 共性根因（bug class）

所有问题是**同一个反模式**：

```
数据源凭证/权限不足 → adapter 吞异常返回空 → 上游当成「正常的空数据」
→ 不完整/错误的数据照写进库 → 前端不校验照显示 / 照排序 / 照喂给 LLM
```

整条链路**没有任何一道数据质量闸门**。代码层温床：

1. 遍地 `except Exception: return None` —— 把「凭证失败 / 接口失败」伪装成「数据为空」。
2. 遍地 `if "field" in d:` 静默跳过缺字段 —— 不写 null、不告警。
3. 写库前零校验 —— all-null 财报、缺市值的基础信息照写不误。
4. 前端格式化函数对 null/undefined 不设防 —— `formatMarketCap` 直接 `.toFixed` 抛错。
5. 前端市值筛选单位换算错误 —— 注释假设后端单位是「万元」按 ×10000 换算，但 DB 存的是「亿元」（`processing.py` 做过 `/10000`）。

---

## 实测确认 — tushare token 权限不足（2026-05-17 实跑）

用项目自身的 `TushareProvider` 实跑各接口（脚本 `/tmp/tushare_probe.py`），结果决定性：

| 接口 | 结果 | 供给的字段 |
|---|---|---|
| `stock_basic` | ✅ OK（5517 行） | 股票列表（基线：token 有效） |
| `daily_basic` | ❌ **「您没有接口(daily_basic)访问权限」** | total_mv / circ_mv / pe / pb / ps |
| `income` | ❌ **「您没有接口(income)访问权限」** | revenue / net_income |
| `fina_indicator` | ❌ **「您没有接口(fina_indicator)访问权限」** | roe / 利润率 |

**结论**：配置的 tushare token 是低档位账户，只有 `stock_basic`（股票列表）权限，**没有 `daily_basic`（估值）和财报接口权限**。`daily_basic` 需 2000 积分（见 tushare doc_id=108）。

这把 P0#2（市值缺失）、P0#3（pe/pb/ps 不全）、P0#4（财报全 null）的**直接成因**全部坐实——不是代码 bug，是数据源权限不足。代码的「静默降级 + 不校验」只是把这个权限问题伪装成了「数据为空」。两者都要修：数据源权限要解决，代码闸门也要补（否则换任何源出问题都会重演）。

## 修复路线（建议，分阶段）

**Phase 1 — 止血（display 层，不碰数据源）**
- 前端 `formatMarketCap` 等格式化函数加 null 兜底，缺数据显示「—」而非崩溃 / 误导。
- 「市值范围」筛选、「每日推荐」在 `total_mv` 不可用时显式报「市值数据不可用」，不返回误导性的 0 结果 / 任意 5 只。

**Phase 2 — 数据层**
- ✅ 已坐实：tushare token 无 `daily_basic`/财报权限（见上节）。需二选一：
  - **方案 A — 充值 tushare 积分**（≥2000 积分解锁 `daily_basic` + 财报）：最稳，涉及付费/外部账户，须用户决策。
  - **方案 B — 换源到 akshare 全市场快照**：`akshare.stock_zh_a_spot_em()` 免费、一次调用返回全 A 股总市值/流通市值/PE/PB。需重写 akshare adapter 的 `get_daily_basic`（现在是 `max_stocks=10` 的逐股 stub），改用这个批量接口。免费但 akshare 稳定性偏低。
- sync 写库前加校验闸门：all-null / 缺关键字段 → 拒写 + 告警，不静默入库。
- 修 upsert key（要么只用 `code` 单源，要么明确多源设计 + 下游统一去重）。
- 统一 `source`/`data_source` 字段名、日期格式、交易所后缀。

**Phase 3 — 防复发**
- 让 `data_consistency_checker` 真正接入写入路径做闸门，cross-source 偏差超阈值告警。
- 把 `/tmp/data_audit.js` 固化成 `scripts/data_audit.js`，定期跑数据健康检查。

---

## 审计脚本

`/tmp/data_audit.js` —— 直连 MongoDB 检查各集合字段完整率 + 数值合理性（neg/zero/null/NaN）。运行：

```bash
mongosh "mongodb://admin:tradingagents123@127.0.0.1:54302/tradingagentscn?authSource=admin" --quiet --file /tmp/data_audit.js
```

---

## 处置结果（2026-05-17 当日完成，方案 A）

用户充值 tushare 积分后走方案 A，当日完成：

| 问题 | 处置 | 结果 |
|---|---|---|
| P0#2 市值缺失 | tushare `daily_basic` 解锁后跑全市场 basics 同步 | `total_mv`/`circ_mv` 覆盖 5495/5517，哨兵值正确（茅台 16692 亿、市值前 5 = 工行/建行/农行/中移动/中石油） |
| P0#3 pe/pb 不可信 | 统一由 tushare `daily_basic` 单源供给 | pe 覆盖 5464/5517，cross-source 不一致消除 |
| P0#4 财务数据全 null | tushare `income`/`fina_indicator` 解锁后跑全量财务同步 | `stock_financial_data` 5510 docs，营收/净利覆盖 ~5450，0 错误 |
| P0#1 三倍重复 | 删除与 tushare 重复的 akshare/baostock 文档 | `stock_basic_info` 16559→5841 docs，零重复（保留 324 条 baostock 独有代码） |
| 10 条 all-null 财务垃圾 | 定向 `deleteMany` | 已清除 |
| 静默降级反模式 | `multi_source_basics_sync_service` 加失败告警；`financial_data_service` 加写库前校验闸门（拒绝 all-null）+ 单元测试 | 已落地（commit `cd226369`） |
| 前端崩溃/误导 | `formatMarketCap` 兜底 + 筛选/每日推荐告警 | 已落地（commit `4651fff1`） |

**未处置（建议后续）**：
- ③ upsert key `(code,source)` → `code` + 唯一索引调整：属架构小改，重复数据已清、tushare 优先源稳定，暂不影响功能。
- `data_consistency_checker` 接入写入闸门、`market_quotes` 行情陈旧（eastmoney `clist` 接口连通性问题）。
