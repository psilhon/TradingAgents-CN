## ADDED Requirements

### Requirement: 任务失败必须保留可诊断错误详情

分析任务失败时，系统 MUST 在任务记录中保存可诊断错误详情，至少包含：

- 用户可读摘要
- 技术错误详情
- 错误分类
- 建议动作

错误详情 MUST 脱敏，不得保存或展示 API Key、token、cookie、私钥等凭据原文。

#### Scenario: LLM HTTP 400 失败可在任务中心查看

- **WHEN** 分析任务因 LLM API 返回 HTTP 400 失败
- **THEN** 任务中心错误弹窗展示 HTTP 400 摘要
- **AND** 技术详情包含供应商返回的脱敏错误文本
- **AND** 不再只显示“分析过程中发生错误”

#### Scenario: 数据源权限失败可区分

- **WHEN** 数据源测试或分析任务因接口权限不足失败
- **THEN** 错误分类为 `data_source_permission`
- **AND** 页面建议用户切换数据源或升级数据源权限

### Requirement: 模拟交易支持粘贴导入初始持仓

模拟交易页面 MUST 支持用户通过粘贴文本批量生成导入持仓行。

支持字段：

- 市场
- 代码
- 名称
- 数量
- 成本价
- 可用数量

输入 MAY 包含表头；分隔符 SHOULD 支持 tab、逗号和连续空格。

#### Scenario: 粘贴带表头的持仓表

- **WHEN** 用户粘贴包含表头的多行持仓
- **AND** 点击解析
- **THEN** 导入表格生成对应持仓行
- **AND** 用户仍可在提交前编辑每一行

#### Scenario: 粘贴无表头的持仓表

- **WHEN** 用户粘贴无表头的行，列顺序为 `市场 代码 名称 数量 成本价 可用数量`
- **THEN** 系统按默认列顺序解析
- **AND** 无效行不进入导入表格

### Requirement: 前端类型检查必须恢复绿色

本 change 完成后，frontend type-check MUST 退出码为 0。

#### Scenario: frontend type-check

- **WHEN** 在 `frontend/` 运行 `npm run type-check -- --pretty false`
- **THEN** 命令成功退出
