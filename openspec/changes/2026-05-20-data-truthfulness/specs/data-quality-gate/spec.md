## MODIFIED Requirements

### Requirement: 前端 MUST 对缺失数据兜底并显式告警，MUST NOT 呈现误导性结果

前端展示层对可能缺失的数据字段 MUST 做 null / undefined / NaN 兜底，缺数据 MUST 显示「—」而非抛错导致整列空白或渲染相邻字段。当某项数据缺失会让结果失真时，前端 MUST 显式告警「数据不可用」，MUST NOT 把它呈现为看似正常的误导性结果（如 0 条筛选结果、按全空字段的任意排序）。

**禁止行为清单（铁律层级）**：

1. **MUST NOT 用合成 / 噪声 / hash / Math.random / Math.sin 等生成器构造看似真实的图表数据**。所有 sparkline / 趋势曲线 / 历史柱图 MUST 来自真实数据 endpoint。无对应数据源时 MUST 删除该图表元素，**MUST NOT 用 mock 装饰**——「视觉装饰」永远低于「数据真实性」。
2. **MUST NOT 用 `\|\| 0` / `\|\| ''` 等假值兜底把 null 假装为 0**。区分 null（无数据）与 0（真实零值）：用 `?? null` 保留 null 语义，模板层用 `v-if`/`v-show` 判定显示「—」。"0 元股票"和"无数据股票"对用户决策意义完全不同。
3. **跨时间维度的聚合 endpoint MUST 按 `updated_at` 过滤当日数据**，MUST NOT 把昨日 / 历史数据混入当日聚合。
4. **任何 quote / 价格 / 盘口类后端 endpoint MUST 返回 `is_stale: bool` + `as_of_date: str` 字段**；前端 MUST 在 `is_stale=true` 时主显示区降级（灰化 / 警告条幅 / 「快照日期 X」chip），MUST NOT 把昨日涨停板当今日大字色块显示。

理由：data-audit 实证——`formatMarketCap` 遇 `undefined` 直接 `.toFixed` 抛错让市值列空白，用户误把相邻的 pe 列当市值；按全 null 的 `total_mv` 排序的每日推荐推出的根本不是市值前 5，而是任意 5 只。2026-05-20 会话又撞到 5 项同源造假（mockTrend sparkline / `|| 0` / 跨日累加 / 002281 昨日涨停板大字红色当今日）——证明缺数据兜底规则要细化到具体禁止行为，不能只说"显示 —"。

#### Scenario: 市值字段缺失

- **WHEN** stock 数据 `total_mv` 为 `null` / `undefined` / `NaN`
- **THEN** UI 显示「—」而非抛错 / 空白 / 渲染为 0
- **AND** 按市值排序的列表 MUST 把缺数据股排到末位或跳过，MUST NOT 把 null 当 0 参与排序

#### Scenario: 合成 sparkline / 趋势曲线 MUST 被禁止

- **WHEN** 前端组件渲染 sparkline / 历史走势 / mini K 线
- **THEN** 数据 MUST 来自真实历史 endpoint（如 `paper_account_snapshots` / `stock_daily_quotes`）
- **AND** 不允许使用 `Math.random` / `Math.sin(seed * ...)` / hash-based / 固定 seed 等任何合成生成器
- **AND** 无对应真实数据时 MUST 不渲染该 sparkline（删除元素或 v-if 守卫），MUST NOT 用 mock 占位
- **AND** CI hook `scripts/check-data-truthfulness.sh` MUST grep `mockTrend|Math\.random|Math\.sin.*\*` 阻塞 commit；违规可加 `// data-truthfulness:allow reason: <理由>` 注释豁免

#### Scenario: null 不得用 || 0 假装为 0

- **WHEN** 后端 API 返回某字段为 `null`（如 `current_price`、`change_percent`）
- **THEN** 前端 MUST 用 `?? null` 保留 null，MUST NOT 用 `|| 0` 假装为零值
- **AND** 模板层 MUST 用 `v-if="value != null"` 守卫，缺数据时显示「—」
- **AND** UI MUST 在视觉上区分「真实零值」（如停牌股票成交量 = 0）和「无数据」（显示 —）

#### Scenario: 全市场聚合 MUST 按当日时间戳过滤

- **WHEN** 后端 endpoint 计算全市场涨停 / 跌停 / 成交额合计等跨日维度聚合
- **THEN** 实现 MUST 在 mongo `$match` 或内存过滤层限定 `updated_at >= 当前 CN tz 日历日 00:00:00`
- **AND** MUST NOT 把昨日 / 历史 quote 一起累加（这会触发 28595 亿成交额 / 137 涨停 这类用户立即识别的造假事故）

#### Scenario: quote endpoint MUST 透出 is_stale

- **WHEN** 后端实现 quote / 盘口 / 价格类 endpoint（如 `/api/stocks/{code}/quote`）
- **THEN** 返回 data 字典 MUST 含 `is_stale: bool` + `as_of_date: str` 字段
- **AND** `is_stale` 计算规则：`updated_at` 的 CN tz 日历日 != 今日 → `true`；缺 `updated_at` 但有 close 值 → 保守判 `true`（不能假装为今日）
- **AND** 前端展示组件 MUST 在 `is_stale=true` 时把主价格 / 涨跌幅区降级显示（opacity ≤ 0.6 / 取消红绿大字色 / 加显眼警告条幅「非今日实时数据」）
- **AND** contract test `tests/test_stocks_quote_truthfulness.py` MUST 验证 endpoint 返回字段含 `is_stale` 和 `as_of_date`

#### Scenario: 数据时效信号 MUST 被消费层尊重

- **WHEN** 后端 endpoint 返回 `is_stale=true` 或 `staleness_seconds > SLA_threshold`
- **THEN** 前端 MUST 视觉化降级（灰化 / 警告条幅 / 时效 chip）
- **AND** MUST NOT 把 stale 数据当 fresh 数据无差别展示
- **AND** 用户能在不悬停 tooltip 的情况下，**一眼识别**当前展示数据非今日实时
