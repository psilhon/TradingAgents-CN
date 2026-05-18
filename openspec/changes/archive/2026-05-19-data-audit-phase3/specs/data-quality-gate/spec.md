## ADDED Requirements

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
