## MODIFIED Requirements

### Requirement: 前端 MUST 对缺失数据兜底并显式告警，MUST NOT 呈现误导性结果

前端展示层对可能缺失的数据字段 MUST 做 null / undefined / NaN 兜底，缺数据 MUST 显示「—」而非抛错导致整列空白或渲染相邻字段。当某项数据缺失会让结果失真时，前端 MUST 显式告警「数据不可用」，MUST NOT 把它呈现为看似正常的误导性结果（如 0 条筛选结果、按全空字段的任意排序）。

**禁止行为清单（铁律层级）**：

1. **MUST NOT 用合成 / 噪声 / hash / Math.random / Math.sin 等生成器构造看似真实的图表数据**。所有 sparkline / 趋势曲线 / 历史柱图 MUST 来自真实数据 endpoint。无对应数据源时 MUST 删除该图表元素，**MUST NOT 用 mock 装饰**——「视觉装饰」永远低于「数据真实性」。
2. **MUST NOT 用 `\|\| 0` / `\|\| ''` 等假值兜底把 null 假装为 0**。区分 null（无数据）与 0（真实零值）：用 `?? null` 保留 null 语义，模板层用 `v-if`/`v-show` 判定显示「—」。"0 元股票"和"无数据股票"对用户决策意义完全不同。
3. **跨时间维度的聚合 endpoint MUST 按 `updated_at` 过滤当日数据**，MUST NOT 把昨日 / 历史数据混入当日聚合。
4. **任何 quote / 价格 / 盘口类后端 endpoint MUST 返回 `is_stale: bool` + `as_of_date: str` 字段**；前端 MUST 在 `is_stale=true` 时主显示区降级（灰化 / 警告条幅 / 「快照日期 X」chip），MUST NOT 把昨日涨停板当今日大字色块显示。
5. **后端 service / router 缺上游数据 MUST 返回 None / null，MUST NOT 用 `value or 0` / `last or 0.0` / `default=0` 等等价模式合成假零值**。"算式分量缺失自动当 0"（如 `Number(null) * X = 0` / `(None or 0.0) * qty = 0`）会让上层得到一个看似正常但完全虚假的结果，比纯空白更具误导性。
6. **每个直接面向 dashboard / portfolio / paper / market 的 endpoint MUST 有 contract test，断言全 null 上游 → endpoint 返 null/None，绝不出现合成 0**。test MUST 标 `@pytest.mark.unit`，pre-push hook 阻塞 commit 直到 test PASS。grep 层防线（`scripts/check-data-truthfulness.sh`）只覆盖词法模式，contract test 覆盖语义层（不可被 grep 抓取的模式如 `formatMoney(null)='0.00'` / `last or 0.0`）。

理由：data-audit 实证——`formatMarketCap` 遇 `undefined` 直接 `.toFixed` 抛错让市值列空白；2026-05-20 baseline 审计在 v1.3.0 release **之后** 发现 5 critical 漏修（`formatMoney(null)='0.00'` / `?.HKD || 0` 显示 `HK$0.00` / 浮盈 `null × null` 渲染**假红色亏损** / 后端 `last or 0.0` 污染 mongo snapshot / pnl_stream ws push 同根因），全部 grep 层抓不到——证明语义层必须用 contract test 强约束。

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

#### Scenario: 后端 service 缺上游数据 MUST 返 None（不得用 `or 0` 等价模式合成）

- **WHEN** 后端 service / router 上游数据源（如 `_get_last_price`、mongo 查询、外部 API 调用）返回 `None`
- **THEN** 计算结果 MUST 保留 None 语义传递到 endpoint response
- **AND** MUST NOT 使用 `last or 0.0` / `value or 0` / `obj.get("field", 0)` / `default=0` 等等价模式把 None 合成为 0
- **AND** 算式中含 None 分量时 MUST 短路返 None（如 `mkt_value = None if last is None else round(last * qty, 2)`），MUST NOT 让 `Number(None) * X = 0` 这类语言级隐式转换产生假零值
- **AND** 聚合操作 MUST 显式跳过 None 而非用 None 当 0 累加（如 `if mkt_value is not None: positions_value += mkt_value` 而非 `positions_value += (mkt_value or 0)`）
- **AND** Pydantic / TypedDict 模型字段类型 MUST 用 `Optional[float] = None` 而非 `float = 0.0`，让 mypy / pyright 在编译期捕获 misuse
- **AND** 当聚合结果存在 partial coverage（部分上游缺失），response MUST 透出 `quote_coverage` / `coverage` / `partial` 类标志字段，让前端知情后做视觉降级

#### Scenario: Contract test MUST 覆盖空态契约

- **WHEN** 实现或修改 dashboard / portfolio / paper / market / stocks 类 endpoint
- **THEN** MUST 同步加 contract test，文件名形如 `tests/test_<endpoint>_<scenario>_contract.py`
- **AND** test MUST 标 `@pytest.mark.unit`（pre-push hook 跑这层）
- **AND** test 覆盖率 MUST 包含：
  1. **全 null 上游**：mock 所有依赖返 None → 断言 endpoint 返字段全 None（不出现合成 0 / 假数据）
  2. **部分 null 上游**：mock 部分依赖返 None → 断言聚合字段跳过 None，coverage 字段反映 missing count，partial 标志正确
  3. **全 valid 上游**（regression guard）：mock 所有依赖返有效值 → 断言数值与既有实现一致，防 fix 破坏既有路径
- **AND** test PASS 是 commit 进 main 的前提（pre-push `uv run --no-sync pytest -m unit` 阻塞）
