## ADDED Requirements

### Requirement: 多配置目录存储

每日推荐配置 MUST 以「目录多文件」形式持久化：每个配置一个文件 `config/daily_recommendations/<id>.json`。

- `<id>`：配置创建时由后端生成的 8 位随机串（十六进制），作为文件名主干，不展示给用户。
- 单个配置 JSON schema：
  - `id`：字符串，与文件名主干一致。
  - `name`：字符串，非空，用户可见的配置显示名。
  - `screening`：`{conditions: [...], order_by, order_direction, limit}`，结构与改造前一致。
  - `analysis`：`{research_depth, market_type}`，结构与改造前一致。
- **不再有 `enabled` 字段** —— 所有配置永远可被选择执行。

#### Scenario: 创建配置生成独立文件

- **WHEN** 用户通过配置管理新建一个配置
- **THEN** 后端生成 8 位随机 `id`
- **AND** 写入 `config/daily_recommendations/<id>.json`
- **AND** 文件内 `id` 字段与文件名主干一致

#### Scenario: 配置校验

- **WHEN** 保存（新建或更新）一个配置
- **THEN** `name` MUST 为非空字符串，否则返回 400
- **AND** `screening.limit` MUST 为 1–20 整数
- **AND** `order_direction` MUST 为 `asc` / `desc`
- **AND** `research_depth` MUST 为 `快速` / `标准` / `深度`
- **AND** `market_type` MUST 为 `A股`
- **AND** 不校验 `enabled`（该字段已移除）

### Requirement: legacy 单配置迁移

服务初始化时 MUST 自动迁移改造前的单配置文件。

- **WHEN** `config/daily_recommendations/` 目录不存在或为空，且旧文件 `config/daily_recommendation.json` 存在
- **THEN** 创建目录，将旧配置迁入为一个新配置文件
- **AND** 迁入的配置 `name` 设为「默认配置」，分配新的 8 位随机 `id`
- **AND** 丢弃旧配置的 `enabled` 字段
- **AND** 删除旧的 `config/daily_recommendation.json` 文件
- **AND** 迁移在任何 `load_config` 调用前完成

#### Scenario: 全新部署无 legacy 文件

- **WHEN** 既无配置目录也无旧单文件
- **THEN** 迁移逻辑不报错，配置列表为空
- **AND** 前端引导用户新建第一个配置

### Requirement: 配置 CRUD API

后端 MUST 提供按 `id` 操作的配置管理端点，替换改造前的单数 `GET/PUT /api/daily-recommendations/config`。

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/daily-recommendations/configs` | 列出所有配置（id / name / screening 摘要） |
| POST | `/api/daily-recommendations/configs` | 新建配置，返回生成的 id |
| GET | `/api/daily-recommendations/configs/{id}` | 取单个配置 |
| PUT | `/api/daily-recommendations/configs/{id}` | 更新配置 |
| DELETE | `/api/daily-recommendations/configs/{id}` | 删除配置 |

#### Scenario: 列出配置

- **WHEN** 请求 `GET /api/daily-recommendations/configs`
- **THEN** 返回当前 `config/daily_recommendations/` 下所有配置
- **AND** 每项含 `id` 与 `name`

#### Scenario: 删除配置保留历史结果

- **WHEN** 删除一个配置
- **THEN** 仅删除 `config/daily_recommendations/<id>.json` 文件
- **AND** MongoDB `daily_recommendations` 中该配置已产出的历史结果文档不受影响
- **AND** 历史结果文档中的 `config_id` / `config_name` 保留

### Requirement: 手动执行选择配置

每日推荐 MUST 仅由手动触发执行，且每次执行 MUST 指定一个配置。

- `POST /api/daily-recommendations/run` body MUST 含 `config_id`。
- `run_daily_recommendation(config_id)` 加载该配置后执行筛选 + 多智能体分析，编排流程与改造前一致。
- 不再有「配置启用与否」守卫 —— 给定 `config_id` 即执行。

#### Scenario: 触发指定配置

- **WHEN** `POST /run` body 为 `{"config_id": "a1b2c3d4"}`
- **THEN** 后台加载该配置并执行筛选 + 分析
- **AND** 结果文档写入 `config_id` 与 `config_name`

#### Scenario: 同配置当天重复触发被拒

- **WHEN** 当天该 `config_id` 已有结果文档
- **THEN** `POST /run` 返回提示，不再触发
- **AND** 不同 `config_id` 当天仍可各自触发

#### Scenario: config_id 不存在

- **WHEN** `POST /run` 的 `config_id` 无对应配置文件
- **THEN** 返回 400 / 404，不启动后台任务

### Requirement: 结果按 (日期, 配置) 存储

MongoDB `daily_recommendations` 集合 MUST 支持同一天多个配置各一份结果。

- 唯一索引由单字段 `date` 改为复合 `(date, config_id)`。
- 结果文档新增 `config_id` + `config_name` 字段（`config_snapshot` 沿用）。
- 改造前的旧结果文档 MUST 回填 `config_id="legacy"` / `config_name="迁移前历史"`。

#### Scenario: 索引迁移顺序

- **WHEN** 执行 MongoDB 迁移
- **THEN** 先回填所有缺 `config_id` 的旧文档为 `"legacy"`
- **AND** 再删除旧的 `date` 单字段唯一索引
- **AND** 最后建立 `(date, config_id)` 复合唯一索引

#### Scenario: 同日多配置结果

- **WHEN** 同一天分别用配置 A、配置 B 触发
- **THEN** `daily_recommendations` 当天存在两份文档，分别带 `config_id` A、B
- **AND** 复合唯一索引不冲突

### Requirement: 无自动调度

每日推荐 MUST NOT 包含任何自动定时执行。

- `scheduler_service.py` 中 `_register_daily_recommendation_jobs()` 注册、其调用点、`_run_daily_recommendation()` 包装 MUST 全部移除。
- 16:30 cron job 不再注册。

#### Scenario: 调度器启动不含每日推荐 job

- **WHEN** 后端启动、APScheduler 初始化
- **THEN** 已注册 job 中不含 `daily_recommendation`
- **AND** 每日推荐仅能由 `POST /run` 手动触发

### Requirement: 前端配置选择与管理

每日推荐页 MUST 提供配置选择与配置管理入口。

- 顶部配置选择器：列出现存配置（可执行 / 可编辑）以及仅存在于历史结果中的已删除配置（只读，标注「已删除」）。
- 选中某配置后，左侧日期列表只显示该配置的历史结果。
- 「立即生成」对当前选中配置执行，触发前弹确认并显示配置名。
- 「配置」入口打开配置管理：列出全部配置，支持新建 / 编辑 / 删除；编辑表单含 `name` 字段。

#### Scenario: 查看已删除配置的历史

- **WHEN** 某配置已被删除但仍有历史结果
- **THEN** 该配置仍出现在顶部选择器中，标注「已删除」
- **AND** 选中后可查看其历史结果
- **AND** 该配置不可执行、不可编辑

#### Scenario: 执行前确认

- **WHEN** 用户点击「立即生成」
- **THEN** 弹出确认框显示当前选中配置的 `name`
- **AND** 确认后才调用 `POST /run`
