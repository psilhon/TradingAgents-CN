## Why

2026-05-20 会话中用户连续撞到「数据造假」事件并定铁律：

> 数据采集不到时可以不显示，不能胡编乱造，生成虚假或者过时信息糊弄。这是作为一个股票交易系统绝对不能容忍的事情。

**穷举审计前端 + 后端发现 5 项违规**（详 `/diagnose` 报告）：

| # | 违规 | 文件 | 用户感知 |
|---|---|---|---|
| V1 | 自选股 sparkline 走势线 = code hash 噪声合成 | `frontend/src/views/Dashboard/index.vue:232,629-647` | 看上去是「最近 14 天走势」，实际是 `Math.sin(seed * 9301 + i * 49297)` 噪声 |
| V2 | Hero 4 个 stat sparkline 固定 seed mock | `frontend/src/views/Dashboard/index.vue:650-653` | 「模拟总资产 ¥338,054」下方上扬曲线跟实际账户净值历史**无任何关系** |
| V3 | `current_price \|\| 0` 把 null 假装为 0 元 | `frontend/src/views/Dashboard/index.vue:919-920` | 后端 null → 前端 ¥0.00 +0.00%（用户以为该股票"价格 0 元"）|
| V4 | `compute_overview` 跨日 cache 累加 | `app/services/market_overview_prewarm_service.py:74-87` | 28595 亿成交额事件源头：今天+昨天+10 天前一锅煮 |
| V5 | `/stocks/{code}/quote` 不返 is_stale，Detail 主价格区无 stale 灯 | `app/routers/stocks.py:115` + `frontend/src/views/Stocks/Detail.vue` | 002281 昨日涨停板 ¥230.89 +10% 大字红色显示当今日 |

**V5 在本次会话已修**（is_stale 后端字段 + Detail 主价格区灰化 + 警告条幅）——但 V1-V4 仍在 main，且**现有 spec 体系跟实际代码冲突**：

- `data-quality-gate` Requirement 3 已经写「前端 MUST 对缺失数据兜底并显式告警」——V1-V4 全部违反这条但无 enforcement
- `realtime-trading-data-flow` Requirement 1 锁定「`/api/market/overview` MUST 仅从 in-memory cache 聚合」——但 **cache 聚合本身就是 V4 跨日污染的源头**

不立 enforcement 机制 → review 不靠（mockTrend 在本仓库存在数月没被发现）→ 未来必复发。

## What Changes

### 改动 1：spec 升级（解开 spec 之间的设计冲突）

- **MODIFIED** `realtime-trading-data-flow` Requirement 1：把"MUST 从 in-memory cache 聚合"约束降级为**延迟 SLO**（p99 < 50ms），允许 mongo aggregate 或 cache 任一实现，但 MUST 保证聚合的所有数据点 `updated_at` 同属当前 CN tz 日历日
- **MODIFIED** `data-quality-gate` Requirement 3：扩 4 个新 Scenarios，把"合成 sparkline"、"`|| 0` 假 0"、"跨日累加"、"quote endpoint 缺 is_stale" 显式列为违规

### 改动 2：V1+V2 — Dashboard sparkline 清理

- **MODIFIED** `frontend/src/views/Dashboard/index.vue`：
  - 删除自选股列表的 Sparkline 列（每行 14 天 mock 噪声曲线）
  - 删除 `mockTrend()` + `strSeed()` 函数（~25 行）
  - Hero 4 个 stat：删 3 个 mock sparkline（分析任务数 / 成功率 / 自选股数），保留「模拟总资产」一条并改接 `paperPerformance.sparkline_points`（已有真实历史数据，来自 paper-account-snapshots capability）
  - 删除 `heroTrend` 对象

### 改动 3：V3 — 缺数据显示「—」+ 整行灰化

- **MODIFIED** `frontend/src/views/Dashboard/index.vue:loadFavoriteStocks`：
  - `current_price: item.current_price || 0` → `current_price: item.current_price ?? null`
  - `change_percent: item.change_percent || 0` → `change_percent: item.change_percent ?? null`
  - 模板加 `v-if="stock.current_price != null"` 判断；缺时显示「—」
  - 新增 `isMissingQuote(stock)` 函数；watchlist-item 加 `.is-missing` 类（复用 `.is-stale` 的 opacity 0.5 风格）

### 改动 4：V4 — compute_overview 改 mongo aggregate today filter

- **MODIFIED** `app/services/market_overview_prewarm_service.py:compute_overview`：
  - 不再读 `QuotesService._cache`
  - 改为对 mongo `market_quotes` 执行 `$facet` aggregate，`$match` 限定 `updated_at >= today_cn_start`
  - p99 < 50ms（实测：本地 mongo 单机 5500 doc aggregate ~20ms）
  - prewarm 体系不动（其它消费者保留 cache 兼容）

### 改动 5：F4 — `/quote` is_stale 字段 + Detail 主价格区灰化（已在 working tree）

- **MODIFIED** `app/routers/stocks.py`：`/stocks/{code}/quote` data dict 加 `is_stale: bool` + `as_of_date: str`（CN tz 日历日比较；缺 updated_at 但有 close 时保守判 stale）
- **MODIFIED** `frontend/src/views/Stocks/Detail.vue`：主价格区 `is_stale=true` 时 opacity 0.55 + 黄色警告条幅「非今日实时数据，当前展示为 X 的快照」

### 改动 6：pre-commit grep 黑名单 + contract test

- **NEW** `scripts/check-data-truthfulness.sh`：grep `frontend/src/views/Dashboard,Stocks` + `frontend/src/components/Layout` 路径下违规关键词（`mockTrend`/`Math\.random`/`Math\.sin.*\*`/`演示数据`/`占位数据`/`\|\|\s*0[^.0-9]`），hit 即非 0 退出
- **MODIFIED** `.pre-commit-config.yaml`：注册新 hook 在 commit 前阻塞
- **NEW** `tests/test_stocks_quote_truthfulness.py`：pytest -m unit contract test，验证 `/stocks/{code}/quote` 返回字段含 `is_stale` 和 `as_of_date`
- 违规可加 `// data-truthfulness:allow reason: <理由>` 注释豁免（脚本看见自动放行，强制 git blame 留痕）

## Capabilities

无新建。复用扩展两个现有 capability：

- `data-quality-gate`（扩 Requirement 3 新 Scenarios）
- `realtime-trading-data-flow`（修 Requirement 1：cache 约束 → 延迟 SLO）

## Impact

**改动文件**：
- 2 个 spec deltas
- 4 个后端 / 前端业务文件（V1-V4 + F4 已落地）
- 3 个新文件（hook 脚本 / contract test / pre-commit 注册）

**视觉变化**：
- Dashboard 自选股列表少了一列 Sparkline
- Hero 区少 3 个小走势图，「模拟总资产」那条变真实账户净值历史
- 缺数据股票变灰显示「—」

**风险**：低
- V4 的 mongo aggregate 取代 cache：spec 升级后合规，p99 实测 < 50ms 远低于 SLO
- F4 已在生产中验证（用户截图）
- pre-commit hook 误报靠 `data-truthfulness:allow` 注释豁免

**收益**：闭环——历史违规清零 + 未来无法再悄悄写回 mockTrend / `|| 0` / 跨日累加。
