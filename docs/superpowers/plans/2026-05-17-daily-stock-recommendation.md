# 每日推荐 5 只股票 + 自动分析 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增一个每日自动任务——交易日盘后 16:30 按配置的固定 screening 条件选 5 只股票、逐只跑标准档多智能体分析、汇总到新建「每日推荐」页展示。

**Architecture:** 组合现有服务 + 加一个 APScheduler cron job，不碰 `tradingagents/` 核心。选股复用 `enhanced_screening_service`，分析复用 `simple_analysis_service`，交易日判定复用 `trading_calendar`。新增一个编排 service、一个 router、一个前端页、一个 mongo collection、一个配置文件。

**Tech Stack:** FastAPI + APScheduler + motor(mongo) + Vue 3 + Element Plus。

**设计依据:** `docs/superpowers/specs/2026-05-17-daily-stock-recommendation-design.md`

---

## File Structure

| 文件 | 动作 | 职责 |
|---|---|---|
| `config/daily_recommendation.json` | 创建 | 选股配置（条件 / 排序 / 数量 / 深度 / 开关）|
| `app/services/daily_recommendation_service.py` | 创建 | 核心编排：读配置 → 选股 → 逐只分析 → 写库 |
| `app/routers/daily_recommendation.py` | 创建 | 列表 / 详情 / 手动触发 3 端点 |
| `app/main.py`（或 router 注册处）| 修改 | 注册新 router |
| `app/services/scheduler_service.py` | 修改 | 加 `_register_daily_recommendation_jobs()` |
| `frontend/src/views/DailyRecommendation/index.vue` | 创建 | 「每日推荐」页 |
| `frontend/src/api/dailyRecommendation.ts` | 创建 | 前端 API 封装 |
| `frontend/src/router/index.ts` | 修改 | 加 `/daily-recommendations` 路由 |
| `frontend/src/components/Layout/SidebarMenu.vue` | 修改 | 加侧边栏入口 |
| `tests/services/test_daily_recommendation_service.py` | 创建 | service unit 测试 |
| `docs/CHANGELOG.md` | 修改 | `[Unreleased]` 加条目 |

**实施前置（每个 Task 开始前确认）:** 实施者需先读这些文件确认精确接口签名——`app/services/enhanced_screening_service.py`（`screen_stocks` 签名与返回结构、`ScreeningCondition` schema）、`app/services/simple_analysis_service.py`（如何创建并执行一个分析任务）、`app/services/scheduler_service.py`（`_register_*_jobs` 模式 + `trading_calendar` 调用）、`app/core/database.py`（`get_mongo_db`）、`app/routers/analysis.py`（router 风格 + `get_current_user` 依赖）。

---

## Task 1: 配置文件 + 配置加载

**Files:**
- Create: `config/daily_recommendation.json`
- Create: `app/services/daily_recommendation_service.py`（先只放 `load_config`）
- Test: `tests/services/test_daily_recommendation_service.py`

- [ ] **Step 1: 创建配置文件**

`config/daily_recommendation.json`:
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
`conditions` 初始为空 = 纯按 `order_by` 取榜单前 5；用户后续用「股票筛选」页调试出条件后填入。

- [ ] **Step 2: 写失败测试**

`tests/services/test_daily_recommendation_service.py`，标 `@pytest.mark.unit`：测 `load_config()` 能读出 `config/daily_recommendation.json`、返回 dict 含 `enabled` / `screening` / `analysis`；文件缺失时返回带 `enabled=False` 的安全默认。

- [ ] **Step 3: 跑测试确认失败** — `.venv/bin/pytest tests/services/test_daily_recommendation_service.py -v`，预期 FAIL（函数未定义）。

- [ ] **Step 4: 实现 `load_config()`**

`daily_recommendation_service.py` 加模块级 `load_config() -> dict`：用标准库 `json` 读项目根的 `config/daily_recommendation.json`（路径用 `Path(__file__)` 上溯到项目根，与项目其它定位方式一致）；文件不存在 / 解析失败 → 返回 `{"enabled": False, ...}` 安全默认 + `logger.warning`。

- [ ] **Step 5: 跑测试确认通过** — 同 Step 3 命令，预期 PASS。

- [ ] **Step 6: Commit** — `git add config/daily_recommendation.json app/services/daily_recommendation_service.py tests/services/test_daily_recommendation_service.py && git commit -m "feat(daily-rec): 每日推荐配置文件 + load_config"`

---

## Task 2: 选股 + 分析编排

**Files:**
- Modify: `app/services/daily_recommendation_service.py`
- Test: `tests/services/test_daily_recommendation_service.py`

- [ ] **Step 1: 写失败测试** — 在测试文件加用例（`unit` marker，mock 掉 `enhanced_screening_service` 和 `simple_analysis_service` + mongo）：
  - `run_daily_recommendation()` 调 screening 取 ≤5 只 → 对每只触发分析 → 写一条 `daily_recommendations`
  - screening 返回 0 只 → 写空 stocks 记录、status 不报错
  - 某只分析失败 → 该 stock 标 `failed`、整体 status=`partial`
  - `enabled=False` → 直接返回、不写库

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现 `run_daily_recommendation()`**

在 `daily_recommendation_service.py` 实现：
  1. `cfg = load_config()`；`cfg["enabled"]` 为假 → `logger.info` 后 return
  2. 调 `enhanced_screening_service.screen_stocks(conditions=cfg[...], order_by=..., limit=cfg["screening"]["limit"])`（精确参数名见该 service 签名）取股票列表
  3. 写一条 `daily_recommendations` 文档（`status="running"`，`config_snapshot=cfg`，`stocks` 初始填 symbol/name）；`date` 用当天，写前 ensure unique index on `date`
  4. 逐只（串行）复用 `simple_analysis_service` 跑标准档分析；每只完成回填该 stock 的 `task_id` / `recommendation` / `summary` / `risk_level` / `status`
  5. 某只异常 → 该 stock `status="failed"`、继续其余
  6. 全部结束 → 文档 `status` = `completed` / `partial`（有失败）/ `failed`（全失败）
  封装成小函数：`_select_stocks(cfg)` / `_analyze_one(symbol, cfg)` / `_persist(...)`，便于测试与阅读。

- [ ] **Step 4: 跑测试确认通过**

- [ ] **Step 5: Commit** — `git commit -m "feat(daily-rec): run_daily_recommendation 选股+分析编排"`

---

## Task 3: scheduler 定时任务

**Files:**
- Modify: `app/services/scheduler_service.py`

- [ ] **Step 1: 加注册方法** — 仿照已有 `_register_paper_snapshot_jobs()` 等，加 `_register_daily_recommendation_jobs()`：`self.scheduler.add_job(...)` 用 `CronTrigger(hour=16, minute=30)`，`max_instances=1, coalesce=True`。

- [ ] **Step 2: job body 加交易日 guard** — job 函数体内先 `trading_calendar` 判断今天是否交易日（用该 service 现有的 `is_trading_day` / 判定方法），非交易日 `logger.info` 后 return；是交易日 → `await daily_recommendation_service.run_daily_recommendation()`。

- [ ] **Step 3: 在 scheduler 启动流程调用** — 在 `scheduler_service` 注册各 job 的地方（已有 `_register_realtime_quote_sync_jobs()` 等的调用处）加一行 `self._register_daily_recommendation_jobs()`。

- [ ] **Step 4: 验证** — `just typecheck`（pyright 0 error）；重启后端 `just dev-restart`，日志确认 job 注册成功（仿照已有 job 的 `logger.info`）。

- [ ] **Step 5: Commit** — `git commit -m "feat(daily-rec): scheduler 加每日 16:30 推荐任务"`

---

## Task 4: API router

**Files:**
- Create: `app/routers/daily_recommendation.py`
- Modify: router 注册处（参考 `app/routers/analysis.py` 如何被注册进 app）

- [ ] **Step 1: 实现 router** — 仿照 `analysis.py` 风格，3 个端点，均 `Depends(get_current_user)`：
  - `GET /api/daily-recommendations`：查 `daily_recommendations`，按 `date` 倒序 + 分页（`limit`/`offset`），返回 `{success, data: [{date, status, stock_count}], message}`
  - `GET /api/daily-recommendations/{date}`：返回某日完整文档（`stocks` 数组）；找不到 404
  - `POST /api/daily-recommendations/run`：`background_tasks.add_task(run_daily_recommendation)` 后台异步触发，立即返回 `{success, message}`（仿 `analysis.py` 的 `/single` 用 `BackgroundTasks` 的写法）
  响应包装统一 `{success, data, message}`（与项目其它 router 一致）。

- [ ] **Step 2: 注册 router** — 在项目注册其它 router 的地方加 `daily_recommendation.router`，prefix `/api/daily-recommendations` 或在 router 内定义（与现有约定一致）。

- [ ] **Step 3: 验证** — `just typecheck`；重启后端，`curl` 三个端点（`POST /run` 触发一次真实跑——这也是端到端验收：等约 30-50 分钟后查 `GET /{date}` 应有 5 只结果）。

- [ ] **Step 4: Commit** — `git commit -m "feat(daily-rec): 每日推荐 API（列表/详情/手动触发）"`

---

## Task 5: 前端「每日推荐」页

**Files:**
- Create: `frontend/src/api/dailyRecommendation.ts`
- Create: `frontend/src/views/DailyRecommendation/index.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/components/Layout/SidebarMenu.vue`

- [ ] **Step 1: API 封装** — `dailyRecommendation.ts`：3 个方法对应 3 端点，用 `ApiClient` 或 `request`（与同目录其它 api 文件一致；注意取值层级——后端返回 `{success, data, message}`，数据在 `res.data`）。

- [ ] **Step 2: 页面组件** — `DailyRecommendation/index.vue`（`<script setup lang="ts">` + Element Plus）：左侧/顶部日期列表（调列表端点），选中某日 → 展示当日 5 只卡片（股票代码+名称、推荐结论、风险等级、`el-link` 跳 `/stocks/:code` 或分析报告页）；顶部「立即生成」按钮调 `POST /run` + `ElMessage` 提示「已在后台生成，约 30-50 分钟」。

- [ ] **Step 3: 路由** — `router/index.ts` 加 `{ path: '/daily-recommendations', name: 'DailyRecommendation', component: () => import('@/views/DailyRecommendation/index.vue'), meta: {title:'每日推荐', requiresAuth:true} }`（仿现有条目）。

- [ ] **Step 4: 侧边栏入口** — `SidebarMenu.vue` 加 `<el-menu-item index="/daily-recommendations">` + 图标 + 文字「每日推荐」（仿现有 `el-menu-item`）。

- [ ] **Step 5: 验证** — `npm --prefix frontend run type-check`（0 error）；vite HMR 后浏览器打开 `/daily-recommendations` 实测页面渲染 + 「立即生成」。

- [ ] **Step 6: Commit** — `git commit -m "feat(daily-rec): 前端「每日推荐」页 + 路由 + 侧边栏入口"`

---

## Task 6: 文档收尾

**Files:**
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: CHANGELOG** — `[Unreleased]` `### Added` 加一条：每日推荐功能（配置驱动选股 + 交易日 16:30 cron + 标准档分析 + 「每日推荐」页），点明 `config/daily_recommendation.json` 是调条件的入口。

- [ ] **Step 2: Commit** — `git commit -m "docs(changelog): 记录每日推荐功能"`

---

## Self-Review

- **Spec coverage:** 设计稿 7 个组件 → Task 1（config）/ Task 2（service）/ Task 2（mongo collection，在 `_persist` 内 ensure index）/ Task 3（scheduler）/ Task 4（router）/ Task 5（前端页+路由+侧边栏）。全覆盖。
- **错误处理** 在 Task 2 Step 1 测试用例 + Step 3 实现中覆盖（0 只 / 部分失败 / enabled=False）。
- **测试:** Task 1、2 有 TDD 步骤、标 `unit` marker，纳入 pre-push hook。
- **顺序依赖:** config（T1）→ service（T2）→ scheduler（T3）→ router（T4）→ 前端（T5），与工具链依赖一致。
- **复用接口的精确签名** 在「实施前置」中要求实施者先读源文件对齐——这是有意为之：本功能是组合现有服务，逐行抄签名易过时，由实施者读当前代码对齐更可靠。
