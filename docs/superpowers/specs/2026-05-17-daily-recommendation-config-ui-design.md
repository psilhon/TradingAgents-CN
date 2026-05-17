# 每日推荐配置可视化编辑 — 设计

> 状态：已与用户确认（2026-05-17 brainstorming）。下一步：writing-plans 出实现计划。
> 背景：原「每日推荐」设计稿（`2026-05-17-daily-stock-recommendation-design.md`）明确以 YAGNI 排除了配置 UI（"调条件用现有股票筛选页"）。用户现要求新增——属合理的需求演进。

## 概述

给「每日推荐」功能加一个配置编辑界面：在 DailyRecommendation 页弹出结构化表单，可视化展示并编辑 `config/daily_recommendation.json`，带选股结果预览，保存即写回文件。下次 cron（16:30）或手动「立即生成」时 `load_config()` 重新读取生效。

纯 `app/` + `frontend/` 层，不碰 `tradingagents/`，不改调度时间（仍硬编码 16:30）。

## 确定的需求参数

| 参数 | 取值 | 来源 |
|---|---|---|
| 编辑形态 | 结构化表单（非原始 JSON 编辑器） | 用户确认 |
| 选股结果预览 | 要——表单内「预览」按钮，复用现有筛选 API | 用户确认 |
| 界面位置 | DailyRecommendation 页操作栏加「配置」按钮 → 右侧 `el-drawer` | 设计确定 |
| 字段元数据来源 | 复用现有 `/api/screening/fields` + `/api/screening/industries` | 设计确定 |

## 组件

| # | 组件 | 类型 | 职责 |
|---|---|---|---|
| 1 | `daily_recommendation_service.save_config()` | 改 `daily_recommendation_service.py` | 校验配置 + 写回 `config/daily_recommendation.json`；非法抛 `ValueError` |
| 2 | `GET /api/daily-recommendations/config` | 改 `daily_recommendation.py` | 读配置返回（文件缺失返回安全默认） |
| 3 | `PUT /api/daily-recommendations/config` | 改 `daily_recommendation.py` | 校验 + 保存；非法返回 400 + 明确错误 |
| 4 | `getConfig()` / `saveConfig()` | 改 `frontend/src/api/dailyRecommendation.ts` | 前端 API 封装 |
| 5 | `ConfigDrawer.vue` | 新文件 `frontend/src/views/DailyRecommendation/ConfigDrawer.vue` | 结构化配置表单 + 预览 |
| 6 | `DailyRecommendation/index.vue` | 改 | 操作栏加「配置」按钮 → 打开 drawer |

## 表单结构

`ConfigDrawer.vue` 用 `el-drawer`（右侧），标题「每日推荐配置」，分 4 段：

| 段 | 配置项 | 控件 |
|---|---|---|
| 任务开关 | `enabled` | `el-switch` |
| 选股条件 | `screening.conditions[]` | 可增删的条件行：`字段下拉` + `操作符下拉`（按字段类型过滤可选操作符）+ `值输入`（随操作符变形） |
| 排序与数量 | `screening.order_by` / `order_direction` / `limit` | 字段下拉 + 升/降序下拉 + 数字框（1–20） |
| 分析设置 | `analysis.research_depth` / `market_type` | 下拉（research_depth 对齐 `AnalysisParameters` 支持档位）/ 下拉（A股，目前固定） |

**条件行的值输入随操作符变形**：
- 单值操作符（`>` `<` `>=` `<=` `==` `!=`）→ 单个数字框
- `between` → 两个数字框（下限、上限）
- `in` / `not_in` → 多选；`industry` 字段时选项来自 `/api/screening/industries`
- `contains` → 文本框

**字段元数据**：drawer 打开时拉 `GET /api/screening/fields`，得到字段名 / 类型 / 各字段支持的操作符，驱动字段下拉与操作符过滤。不在前端重复维护字段表。

## 预览

表单底部「预览」按钮 → 用表单当前的 `conditions` + `order_by` + `limit` 调现有 `POST /api/screening/enhanced`（秒级，仅筛选不跑分析）→ 在 drawer 内展示会选出的前 N 只（股票代码 / 名称 / 排序字段值）。保存前即可验证条件是否合理。预览失败只提示、不阻塞编辑。

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/daily-recommendations/config` | 返回当前配置 dict；文件缺失返回安全默认 |
| PUT | `/api/daily-recommendations/config` | body 为完整配置 dict；校验通过则写文件返回 200，否则 400 + 错误信息 |

均需 `Depends(get_current_user)`，与现有 router 一致。预览不加新端点，复用 `/api/screening/enhanced`。

## 校验规则（`save_config`）

写文件前逐项校验，任一不过即抛 `ValueError`（router 转 400）：

- `enabled`：必须 bool
- `screening.limit`：int，1–20
- `screening.order_by`：字符串，须为已知筛选字段名或 `market_cap`
- `screening.order_direction`：`asc` / `desc`
- `screening.conditions`：list；每项含 `field` / `operator` / `value`；`field` 在 `BASIC_FIELDS_INFO` 内；`operator` 为合法 `OperatorType` 且为该字段类型所支持——复用 `enhanced_screening_service.validate_conditions`
- `analysis.research_depth`：在分析服务支持的档位内
- `analysis.market_type`：`A股`

写文件用 `json.dump(..., ensure_ascii=False, indent=2)`，保持与现有文件格式一致。

## 数据流

```
DailyRecommendation 页「配置」按钮
  → 打开 ConfigDrawer
  → GET /api/daily-recommendations/config + GET /api/screening/fields → 填充表单
  → 用户编辑
  → 「预览」→ POST /api/screening/enhanced（当前条件）→ drawer 内显示选股结果
  → 「保存」→ PUT /api/daily-recommendations/config → save_config 校验 + 写文件
  → 下次 cron 16:30 / 手动「立即生成」时 load_config() 重新读取生效
```

## 错误处理

- GET config：文件缺失 / JSON 损坏 → 返回安全默认（`load_config()` 已有此行为），不报错
- PUT config 校验失败 → 400 + 具体错误（哪个字段/条件不合法），前端 toast 提示
- 预览调用失败 → 前端提示「预览失败」，不阻塞继续编辑 / 保存
- 保存成功 → toast + 关闭 drawer

## 测试

`tests/services/` 下新增 `save_config` 校验逻辑单元测试（标 `unit` marker）：
- 合法配置 → 写入成功
- 非法 `limit`（0 / 超 20 / 非整数）→ 抛 `ValueError`
- 非法 `order_direction` → 抛 `ValueError`
- 条件含未知 `field` / 非法 `operator` → 抛 `ValueError`
- 非法 `enabled` 类型 → 抛 `ValueError`
- 用 tmp 路径 monkeypatch `_CONFIG_PATH`，避免污染真实配置文件

## 范围边界

- 纯 `app/` + `frontend/`，不动 `tradingagents/`
- 不做：条件间 AND/OR 嵌套逻辑（`conditions` 数组即 AND，维持现状）；配置历史/版本；调度时间 UI（仍硬编码 16:30）
- `analysis.market_type` 暂只 A股
- 新增 1 个前端文件，改 4 个文件（router / service / 前端 API / 前端页），加 1 个测试文件
