## ADDED Requirements

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

理由：data-audit 实证——`formatMarketCap` 遇 `undefined` 直接 `.toFixed` 抛错让市值列空白，用户误把相邻的 pe 列当市值；按全 null 的 `total_mv` 排序的每日推荐推出的根本不是市值前 5，而是任意 5 只。

#### Scenario: 市值字段缺失

- **WHEN** 前端 `formatMarketCap` 收到 `null` / `undefined` / `NaN`
- **THEN** 返回「—」，不抛错
- **AND** 不会因异常导致整列空白或错位渲染相邻字段

#### Scenario: 市值范围筛选数据不可用

- **WHEN** 用户用「市值范围」筛选但 `total_mv` 数据不可用，返回 0 条结果
- **THEN** 前端明确提示「市值数据不可用」
- **AND** 不显示误导性的「无股票匹配」

#### Scenario: 每日推荐按缺失字段排序

- **WHEN** 每日推荐配置按市值排序，但 `total_mv` 数据缺失
- **THEN** 推荐详情页顶部显示数据缺失告警
- **AND** 用户能知道当前排序结果不可信
