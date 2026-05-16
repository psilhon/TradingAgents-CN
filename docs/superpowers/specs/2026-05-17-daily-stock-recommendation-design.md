# 每日推荐 5 只股票 + 自动分析 — 设计

> 状态：已与用户确认（2026-05-17 brainstorming）。下一步：writing-plans 出实现计划。

## 概述

新增一个每日自动任务：交易日盘后按预设的固定筛选条件选出 5 只股票，逐只跑标准档多智能体分析，结果汇总成「每日推荐」记录，在新建的独立页面展示。

技术上是组合现有积木 + 加一个定时任务，不碰 `tradingagents/` 核心：
- 选股复用 `enhanced_screening_service`（支持 `conditions` + `order_by` + `limit`）
- 分析复用 `simple_analysis_service`（标准档多智能体分析）
- 调度复用 `scheduler_service`（APScheduler，`CronTrigger`）
- 交易日判定复用 `trading_calendar` capability

## 确定的需求参数

| 参数 | 取值 | 来源 |
|---|---|---|
| 选股标准 | 配置驱动——固定 screening 条件 + 排序 + `limit=5` | 用户确认 |
| 触发时间 | 交易日盘后 16:30（非交易日跳过） | 用户确认 |
| 分析深度 | 标准档（每只 6-10 分钟，5 只串行约 30-50 分钟） | 用户确认 |
| 报告呈现 | 新建独立「每日推荐」页面 | 用户确认 |
| 条件管理 | 配置文件，不做配置 UI；调条件用现有「股票筛选」页调试后填入 | 用户确认（方案 A） |

## 组件

全部在 `app/` + `config/` + `frontend/`，不动 `tradingagents/`。

| # | 组件 | 类型 | 职责 |
|---|---|---|---|
| 1 | `config/daily_recommendation.json` | 新文件 | 选股配置：screening 条件 / 排序 / 数量 / 分析深度 / 开关。tracked、可 git diff |
| 2 | `app/services/daily_recommendation_service.py` | 新文件 | 核心编排：读配置 → 选股 → 逐只分析 → 汇总写库 |
| 3 | mongo `daily_recommendations` | 新 collection | 每日一条推荐记录，`date` 唯一索引 |
| 4 | `scheduler_service._register_daily_recommendation_jobs()` | 改 `scheduler_service.py` | 注册 `CronTrigger(hour=16, minute=30)`，job body 先做交易日 guard |
| 5 | `app/routers/daily_recommendation.py` | 新文件 | 列表 / 详情 / 手动触发 3 个端点 |
| 6 | `frontend/src/views/DailyRecommendation/index.vue` | 新文件 | 「每日推荐」页：日期列表 + 当日 5 只卡片 + 手动触发按钮 |
| 7 | `SidebarMenu.vue` + `router/index.ts` | 改 2 文件 | 侧边栏入口 + 路由 `/daily-recommendations` |

## 配置文件结构

`config/daily_recommendation.json`（初始值保守，用户后续自行调整）：

```json
{
  "enabled": true,
  "screening": {
    "conditions": [],
    "order_by": "market_cap",
    "order_direction": "desc",
    "limit": 5
  },
  "analysis": {
    "research_depth": "标准",
    "market_type": "A股"
  }
}
```

- `screening.conditions`：沿用 screening API 的 `ScreeningCondition` schema（实现阶段精确对齐字段格式）。初始为空数组表示「不额外过滤、纯按 `order_by` 取榜单前 5」；用户用现有「股票筛选」页调试出满意条件后填入。
- `order_by` / `order_direction` / `limit`：传给 `enhanced_screening_service.screen_stocks(...)`。
- `enabled=false` 时 scheduler job 跳过。

## mongo `daily_recommendations` schema

```
{
  date: "2026-05-17",            // 唯一索引
  created_at, updated_at,
  status: "running" | "completed" | "partial" | "failed",
  config_snapshot: { ... },      // 当次实际使用的配置（追溯用）
  stocks: [
    {
      symbol, name,
      task_id,                   // 关联 analysis_tasks
      status: "running" | "completed" | "failed",
      recommendation, summary, risk_level, confidence_score
    }
  ]
}
```

## 数据流

```
16:30 cron → trading_calendar.is_trading_day(today)? ──否──→ 跳过
                 │是
                 ▼
   daily_recommendation_service.run_daily_recommendation()
   → 读 config/daily_recommendation.json（enabled? 否则跳过）
   → enhanced_screening_service.screen_stocks(conditions, order_by, limit=5)
   → 写 daily_recommendations 一条（status=running）
   → for 每只: simple_analysis_service 跑标准档分析（串行）
              每只完成后回填该 stock 的 recommendation/summary/risk_level
   → 全部结束 → status=completed / partial（部分失败）/ failed
前端 /daily-recommendations → API → 展示；个股详细分析复用现有「分析报告」页
```

## API（`app/routers/daily_recommendation.py`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/daily-recommendations` | 列表，按 date 倒序，分页（`limit` / `offset`），返回 date + status + 股票数 |
| GET | `/api/daily-recommendations/{date}` | 某日详情，返回 stocks 数组 |
| POST | `/api/daily-recommendations/run` | 手动触发一次（验收 / 不想等 cron 用）；后台异步执行，立即返回 |

均需 `Depends(get_current_user)` 认证，与现有 router 一致。

## 错误处理

- 某只分析失败 → 该 stock 标 `failed`，其余继续；全部跑完 status 为 `partial`
- screening 返回 < 5 只 → 有几只跑几只
- screening 返回 0 只 → 记一条空 stocks 的记录 + `logger.warning` 告警
- 非交易日 → job body 直接 return，不写记录
- `enabled=false` → 同上跳过

## 测试

`tests/` 下新增 `daily_recommendation_service` 的 unit 测试（标 `unit` marker）：
- mock `enhanced_screening_service` + `simple_analysis_service`
- 覆盖：配置读取、选股结果汇总、部分失败时 status=partial、screening 返回 0/不足 5 只、`enabled=false` 跳过

## 范围边界

- 纯 `app/` + `config/` + `frontend/`，不动 `tradingagents/` Apache 2.0 核心
- `app/` / `frontend/` 是上游专有授权代码——用户为 fork 维护者、本机使用，明确指示新增本功能
- 新增 5 个文件 + 改 2 个文件（`scheduler_service.py` 加注册方法、侧边栏+路由）
- 不做：配置 UI（用现有「股票筛选」页）、推荐表现/命中率追踪（YAGNI）
