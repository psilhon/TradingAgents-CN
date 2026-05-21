# data-quality-gate Specification

## Purpose

锁定数据进入系统的质量闸门——数据同步写库前的关键字段校验、数据源失败的显式告警（不被 `success` 状态掩盖）、前端对缺失数据的兜底与告警——防止错误 / 不完整的数据污染筛选、每日推荐与多智能体分析决策。capability 实现于 commit `cd226369` + `4651fff1`（2026-05-17 数据审计方案 A），spec 由 change `backfill-data-quality-gate-spec` 回填。

## Requirements

### Requirement: 数据同步写库前 MUST 校验关键字段

数据同步服务在把文档写入 MongoDB 前 MUST 校验关键字段，关键字段全为 `None` / 缺失的文档 MUST 被拒绝入库，MUST NOT 因「dict 非空」就判真写入。

理由：数据源接口（如 tushare 财报接口）失败时常被逐层 `except` 吞掉，standardizer 仍用空 dict 拼出一个「全 null 但非空」的文档，旧写库逻辑 `if data:` 判真照写——库里堆积 all-null 垃圾，基本面分析拿到空数据。一个交易分析系统对数据错误零容忍。

#### Scenario: 财务文档关键字段全 None

- **WHEN** `financial_data_service` 准备写入一条财务文档，但 `revenue` / `net_income` / `total_assets` / `total_equity` 等关键字段全为 `None`
- **THEN** 该文档被写库校验闸门拒绝，不写入 `stock_financial_data`
- **AND** 记录告警，而非静默跳过

#### Scenario: 关键字段有效则正常写入

- **WHEN** 财务文档关键字段含有效数值
- **THEN** 文档正常写入 MongoDB

### Requirement: 数据源失败 MUST 显式告警，同步状态 MUST NOT 掩盖数据缺口

数据同步过程中数据源接口失败（权限不足 / 接口报错 / 返回空）时，MUST 显式告警并把失败原因落入 `sync_status.warnings`。当估值 / 财报等关键数据获取失败时，同步状态 MUST NOT 标为 `success`——MUST 用 `success_with_errors` 等可区分状态，使下游与运维能识别「同步跑完了但数据有缺口」。

理由：旧逻辑把「凭证失败 / 接口失败」伪装成「数据为空、同步成功」，掩盖了估值数据缺口，直到用户在前端发现市值列空白才暴露。

#### Scenario: daily_basic 估值接口失败

- **WHEN** `multi_source_basics_sync_service` 同步时 `daily_basic` 估值数据获取失败
- **THEN** 大声告警并把失败信息追加到 `sync_status.warnings`
- **AND** 同步状态转为 `success_with_errors`，不标 `success`

#### Scenario: 全部数据源正常

- **WHEN** 同步过程中所有数据源接口均成功
- **THEN** 同步状态为 `success`，`sync_status.warnings` 为空

### Requirement: 前端 MUST 对缺失数据兜底并显式告警，MUST NOT 呈现误导性结果

前端展示层对可能缺失的数据字段 MUST 做 null / undefined / NaN 兜底，缺数据 MUST 显示「—」而非抛错导致整列空白或渲染相邻字段。当某项数据缺失会让结果失真时，前端 MUST 显式告警「数据不可用」，MUST NOT 把它呈现为看似正常的误导性结果（如 0 条筛选结果、按全空字段的任意排序）。

**禁止行为清单（铁律层级）**：

1. **MUST NOT 用合成 / 噪声 / hash / Math.random / Math.sin 等生成器构造看似真实的图表数据**。所有 sparkline / 趋势曲线 / 历史柱图 MUST 来自真实数据 endpoint。无对应数据源时 MUST 删除该图表元素，**MUST NOT 用 mock 装饰**——「视觉装饰」永远低于「数据真实性」。
2. **MUST NOT 用 `\|\| 0` / `\|\| ''` 等假值兜底把 null 假装为 0**。区分 null（无数据）与 0（真实零值）：用 `?? null` 保留 null 语义，模板层用 `v-if`/`v-show` 判定显示「—」。"0 元股票"和"无数据股票"对用户决策意义完全不同。
3. **跨时间维度的聚合 endpoint MUST 按 `updated_at` 过滤当日数据**，MUST NOT 把昨日 / 历史数据混入当日聚合。
4. **任何 quote / 价格 / 盘口类后端 endpoint MUST 返回 `is_stale: bool` + `as_of_date: str` 字段**；前端 MUST 在 `is_stale=true` 时主显示区降级（灰化 / 警告条幅 / 「快照日期 X」chip），MUST NOT 把昨日涨停板当今日大字色块显示。
5. **后端 service / router 缺上游数据 MUST 返回 None / null，MUST NOT 用 `value or 0` / `last or 0.0` / `default=0` 等等价模式合成假零值**。"算式分量缺失自动当 0"（如 `Number(null) * X = 0` / `(None or 0.0) * qty = 0`）会让上层得到一个看似正常但完全虚假的结果，比纯空白更具误导性。
6. **每个直接面向 dashboard / portfolio / paper / market 的 endpoint MUST 有 contract test，断言全 null 上游 → endpoint 返 null/None，绝不出现合成 0**。test MUST 标 `@pytest.mark.unit`，pre-push hook 阻塞 commit 直到 test PASS。grep 层防线（`scripts/check-data-truthfulness.sh`）只覆盖词法模式，contract test 覆盖语义层（不可被 grep 抓取的模式如 `formatMoney(null)='0.00'` / `last or 0.0`）。

理由：data-audit 实证——`formatMarketCap` 遇 `undefined` 直接 `.toFixed` 抛错让市值列空白，用户误把相邻的 pe 列当市值；按全 null 的 `total_mv` 排序的每日推荐推出的根本不是市值前 5，而是任意 5 只。2026-05-20 会话又撞到 5 项同源造假（mockTrend sparkline / `|| 0` / 跨日累加 / 002281 昨日涨停板大字红色当今日）——证明缺数据兜底规则要细化到具体禁止行为，不能只说"显示 —"。2026-05-20 baseline 审计在 v1.3.0 release **之后** 又发现 5 critical 语义层漏修（`formatMoney(null)='0.00'` / `?.HKD || 0` / 浮盈 `null × null` 假红色亏损 / 后端 `last or 0.0` 污染 mongo snapshot / pnl_stream ws push 同根因），全部 grep 层抓不到——证明语义层必须用 contract test 强约束（change 2026-05-20-paper-null-quote-handling）。

#### Scenario: 市值字段缺失

- **WHEN** stock 数据 `total_mv` 为 `null` / `undefined` / `NaN`
- **THEN** UI 显示「—」而非抛错 / 空白 / 渲染为 0
- **AND** 按市值排序的列表 MUST 把缺数据股排到末位或跳过，MUST NOT 把 null 当 0 参与排序

#### Scenario: 市值范围筛选数据不可用

- **WHEN** 用户用「市值范围」筛选但 `total_mv` 数据不可用，返回 0 条结果
- **THEN** 前端明确提示「市值数据不可用」
- **AND** 不显示误导性的「无股票匹配」

#### Scenario: 每日推荐按缺失字段排序

- **WHEN** 每日推荐配置按市值排序，但 `total_mv` 数据缺失
- **THEN** 推荐详情页顶部显示数据缺失告警
- **AND** 用户能知道当前排序结果不可信

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

### Requirement: stock_basic_info 写库前 MUST 做数值 sanity 校验

basics 同步服务（`multi_source_basics_sync_service` / `basics_sync_service`）把文档写入 `stock_basic_info` 前 MUST 对关键数值字段做 sanity 校验。数学上不可能的值 MUST 被拒写，量级失真的值 MUST 被标记告警。

具体：

- `ps` / `total_mv` / `circ_mv` 为负 → 数学上不可能（营收、市值恒 ≥ 0），MUST 拒绝该值入库。
- `pe` 绝对值超出合理界（阈值由实施期调研确定）→ MUST 标记并告警。
- 关键字段全为 `None` 的文档 → MUST 拒写（与 `data-quality-gate` 已锁的 `financial_data_service` 闸门同语义）。

被拒 / 被标记的情况 MUST 把失败原因落入 `sync_status.warnings`，同步状态 MUST 转 `success_with_errors`，MUST NOT 标 `success`。

理由：data-audit 2026-05-17 实证库里出现负 `ps`（price-to-sales 不可能为负）、`pe=-16622` 量级失真值。`data-quality-gate` 原只锁了 `financial_data_service` 的关键字段闸门，basics 写入路径无任何数值闸门——错误数值照写不误。

#### Scenario: 负 ps 写入 stock_basic_info

- **WHEN** basics 同步准备写入一条文档，`ps`（或 `total_mv` / `circ_mv`）为负值
- **THEN** 该负值被 sanity 闸门拒绝入库
- **AND** 失败信息追加到 `sync_status.warnings`，同步状态转 `success_with_errors`

#### Scenario: pe 量级失真

- **WHEN** 文档 `pe` 绝对值超出合理界
- **THEN** 闸门标记该值并把告警追加到 `sync_status.warnings`

#### Scenario: 数值正常则正常写入

- **WHEN** 文档所有关键数值字段均通过 sanity 校验
- **THEN** 文档正常写入 `stock_basic_info`
- **AND** `sync_status.warnings` 不因该文档增项

#### Scenario: 清理存量历史脏值

- **WHEN** sanity 闸门启用前已入库的 `stock_basic_info` 文档存在负 `ps` / `ps_ttm` / `total_mv` / `circ_mv`
- **THEN** `stock_basic_info` 迁移 MUST 一次性 `$unset` 这些历史脏字段
- **AND** 使整个集合（不只新写入）满足「无数学上不可能的负值」不变量

### Requirement: stock_basic_info MUST 用单一主键 code

`stock_basic_info` 集合的 upsert key 与唯一索引 MUST 是单一 `code`，MUST NOT 是复合 `(code, source)`。每只股票在该集合 MUST 只有一条文档。

- basics 同步的 upsert MUST 用 `{"code": code}` 作为查询键。
- 集合 MUST 有 `code` 单字段唯一索引，MUST NOT 有 `(code, source)` 复合唯一索引。
- 改造前的复合主键残留的同 code 多 source 重复文档 MUST 经一次性迁移合并 / 去重（保留优先源、保留独有代码）。

理由：复合主键 `(code, source)` 让每个数据源各写一份，data-audit 实证 `5841 真实代码 × ~3 源 ≈ 16557 docs`，下游所有读该表的计数 / 筛选 / 排序产生 ×N 偏差。

#### Scenario: 多源同步不产生重复文档

- **WHEN** basics 同步先后用不同数据源同步同一只股票
- **THEN** `stock_basic_info` 中该 `code` 只有一条文档（后写覆盖，不新增行）

#### Scenario: 唯一索引形态

- **WHEN** 检查 `stock_basic_info` 的索引
- **THEN** 存在 `code` 单字段唯一索引
- **AND** 不存在 `(code, source)` 复合唯一索引

#### Scenario: 迁移顺序

- **WHEN** 执行 `stock_basic_info` 主键迁移
- **THEN** 先合并 / 去重残留的同 code 多 source 文档
- **AND** 再删除旧的 `code_source_unique` 复合唯一索引
- **AND** 最后建立 `code` 单字段唯一索引

### Requirement: 数据源标识 MUST 用统一字段名

MongoDB 各集合中标识「数据来源」的字段 MUST 用统一字段名，MUST NOT 同语义两个字段名（`source` / `data_source`）并存。

- 所有写入路径 MUST 用统一字段名。
- 既有文档中的旧字段名 MUST 经一次性数据迁移 rename 到统一名。
- 跨集合 join（如 `stock_screening_view` 的财务 join）MUST 用统一字段名匹配。

理由：data-audit 实证 `source`（16557 docs）与 `data_source`（5203 docs）同语义并存，`stock_screening_view` 财务 join 因 `data_source==source` 命名不一致而几乎 join 不上。

#### Scenario: 字段名一致性

- **WHEN** 检查任一含数据源标识的集合的文档
- **THEN** 数据源字段名为统一字段名
- **AND** 不出现另一个同语义字段名

#### Scenario: screening_view join 命中

- **WHEN** `stock_screening_view` 做基础信息与财务数据的 join
- **THEN** join 条件两侧字段名一致，join 正常命中
