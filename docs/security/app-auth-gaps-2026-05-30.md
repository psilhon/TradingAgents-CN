# Security Report — `app/` 鉴权与凭据处理缺口

**日期**：2026-05-30
**范围**：`app/`（FastAPI 后端）+ `frontend/src/`（Vue 前端）—— 专有授权代码
**来源**：全项目 code review（多 agent workflow，recall-biased + 对抗式验证）
**核实方式**：以下每一条都已**逐条对照当前源码**人工复核（含排除"router/app 级 dependencies 兜底"等假阳性），附 `file:line` 与对照锚点。
**状态**：仅报告，未改动任何 `app/` / `frontend/` 代码（专有授权边界）。

> 给维护者的话：本 fork（`psilhon/TradingAgents-CN`）为个人本地学习用途、强制 loopback-only 部署，下列多数问题在"单人 + 仅 127.0.0.1"场景下风险被环境缓解。但若上游或任何人计划**多用户 / 公网 / 局域网**部署，HIGH 项均为可被匿名利用的真实缺口，建议优先处理。

---

## 一、HIGH — 端点无鉴权（匿名可达）

项目里已有正确范式可直接套用：
- **Admin 守卫**：`app/routers/sync.py` 的 `_require_admin(current_user)` + `current_user: dict = Depends(get_current_user)`
- **登录守卫**：`app/routers/akshare_init.py` 的 `start-full` / `start-basic` / `stop` 均挂 `Depends(get_current_user)`

下列 router **完全没有**端点级 `Depends`，且经核实其 `APIRouter(...)` 构造、`main.py` 的 `include_router(...)`、以及全局中间件链（仅 TrustedHost / CORS / OperationLog / RequestID）**都没有**兜底鉴权 → 真实匿名可达。

| # | 端点 | 文件:行 | 影响 |
|---|---|---|---|
| H1 | `POST /api/internal-messages/save`（及 query/search/latest/research-reports/analyst-notes/statistics 全部） | `app/routers/internal_messages.py:77` | 匿名**写入**任意"内部消息 / 研报 / 分析师笔记"，污染喂给 LLM 的数据 |
| H2 | `POST /api/baostock-init/start-full`、`start-basic`、`stop` | `app/routers/baostock_init.py:83,135,221` | 匿名拉起 30–60 min 全量数据初始化（重 CPU/网络/DB）或中止任务。**对比**：同目录 `akshare_init.py` 同名端点有 `Depends(get_current_user)` —— 明显是漏挂 |
| H3 | `GET /api/system-config/config/validate` | `app/routers/system_config.py:63` | 无 auth（**对比** 同文件 `/config/summary:53` 有 `Depends(get_current_user)`）。会先 `bridge_config_to_env()` 重载 Mongo 配置再验证，向匿名返回各 LLM provider / 数据源的配置/key 就绪态 |
| H4 | `POST /api/multi-period-sync/start`、`start-daily/weekly/monthly`、`start-all-history`、`start-incremental` | `app/routers/multi_period_sync.py:36,72,103,134,165,202` | 匿名触发全历史（1990 至今）多周期同步。**对比** `sync.py` 同类操作有 `_require_admin` |
| H5 | `POST /api/social-media/save`（及 query/search/latest/statistics/sentiment-analysis 全部） | `app/routers/social_media.py:68` | 匿名**写入**任意社媒情绪文档（同 H1，污染分析输入） |
| H6 | `POST /api/financial-data/sync/start`、`sync/single`（及所有 query 端点） | `app/routers/financial_data.py:147,183` | 匿名触发财务数据同步任务 |

**建议修法**（统一）：写/重型同步端点加 `current_user: dict = Depends(get_current_user)`；管理类（init / 全量 sync / 破坏性）再叠 `_require_admin(current_user)`。守卫务必置于 `try` **之前**（否则路由内 `except Exception` 会把 `HTTPException(401/403)` 吞成 500，鉴权失效——这正是 v1.4.0 修 `database.py` 时踩到的点）。

---

## 二、HIGH — 前端存储型 XSS

| # | 位置 | 文件:行 | 影响 |
|---|---|---|---|
| H7 | `v-html="renderMarkdown(result.recommendation / result.summary)"` | `frontend/src/components/Global/TaskResultDialog.vue:6,8` | `renderMarkdown = marked.parse(s)`，**无** DOMPurify/sanitize。`recommendation`/`summary` 来自分析任务链（LLM 输出 + 数据源文本）；嵌入 `<img src=x onerror=...>` 等会执行任意 JS |
| H8 | `v-html="renderMarkdown(sec.content)"`（多报告段） | `frontend/src/components/Global/TaskReportDialog.vue:20` | 同根因（`marked.parse` 未净化）。任一报告段含恶意 HTML 即在渲染时执行 |

**建议修法**：渲染前过 DOMPurify，例如 `v-html="DOMPurify.sanitize(marked.parse(s))"`，或全局封装一个 `renderMarkdown` 统一净化（两处共用）。

---

## 三、MEDIUM

| # | 问题 | 文件:行 | 说明 / 建议 |
|---|---|---|---|
| M1 | JWT 缺 `exp` 被当作有效 | `app/services/auth_service.py:41` | `exp=int(payload.get("exp", time.time()))` —— 缺 `exp` 时默认"当前时间"，随后 `exp < now` 为 False → 无过期声明的 token 通过。应：缺 `exp` 直接拒绝 |
| M2 | JWT 签名密钥前 10 字符入日志 | `app/services/auth_service.py:34` | 每次验证 `logger.debug(f"🔑 JWT密钥: {settings.JWT_SECRET[:10]}...")`。削弱密钥强度，应删除 |
| M3 | Authorization header 前 50 字符入日志 | `app/routers/auth_db.py:84` | `logger.debug(f"...{authorization[:50]}...")` 含 token 开头。应只记"有/无"，不记内容 |
| M4 | 明文密码入 INFO 日志 + 默认弱口令 | `app/services/user_service.py:303,345` | `create_admin_user(password="admin123")` 默认弱口令；创建成功 `logger.info(f"   密码: {password}")` 明文落盘。应移除明文日志；默认口令仅限本地、生产强制改密。**注**：密码哈希本身已是 bcrypt（v1.4.0 已修），此处仅"日志泄漏 + 默认值"问题 |
| M5 | `search_keyword` 未转义直入 MongoDB `$regex` | `app/routers/reports.py:168`（同 `stock_data.py:249` / `stocks.py`） | ReDoS / 误匹配。应 `re.escape(search_keyword)` |
| M6 | 信任未认证的代理头作为客户端 IP | `app/middleware/operation_log_middleware.py:124` | 无条件取 `X-Forwarded-For` / `X-Real-IP` 第一段 → 任何客户端可伪造审计日志源 IP。应仅在可信反代后启用，或固定信任跳数 |
| M7 | user_id 转换失败时静默造随机 ObjectId | `app/services/analysis_service.py:86` | `except: new_object_id = ObjectId()` —— 非法 user_id 不报错反而生成新身份，可能产生孤儿数据 / 绕过归属。应抛错而非伪造 |
| M8 | 结果轮询用裸 `fetch` 带 JWT 且失败无限重试 | `frontend/src/views/Analysis/SingleAnalysis.vue:1059` | 5s 轮询里 `fetch(..., Authorization: Bearer ${token})`，结果 API 失败时无退避/停止。应加错误处理 + 退避上限 |

---

## 四、LOW

| # | 问题 | 文件:行 | 说明 |
|---|---|---|---|
| L1 | 限流 fail-open | `app/middleware/rate_limit.py:47` | Redis 异常被 `except Exception` 吞掉后**放行**请求，限流形同虚设（Redis 抖动期）。可接受与否取决于威胁模型，但应显式决策 |
| L2 | 未认证限流键塌缩为 `"unknown"` | `app/middleware/rate_limit.py:40` | `request.client` 为 None 时所有此类客户端共享一个限流桶 |
| L3 | HOST/ALLOWED 默认值违反 loopback | `app/core/config.py:28` | `HOST="0.0.0.0"` / `ALLOWED_ORIGINS/HOSTS=["*"]`。**本 fork 已知**：`dev.sh` 用 `--host 127.0.0.1` 覆盖、v1.4.0 已记 `.env.example` 待修，实际影响 LOW；但默认值本身仍建议收紧 |
| L4 | 登录后开放重定向 | `frontend/src/views/Auth/Login.vue:131` | `router.push(getAndClearRedirectPath())` 未校验是否站内路径（open-redirect）。应白名单校验为内部路径 |

---

## 附：核实说明（诚实记录）

- 每条 HIGH 鉴权缺口均已排除"`APIRouter(dependencies=)` / `include_router(dependencies=)` / 全局鉴权中间件"三种兜底可能 → 确为真实匿名可达，非假阳性。
- M4 的"无盐 SHA-256"原始评审描述**已过期**：当前 `user_service` 密码哈希已是 bcrypt（v1.4.0 commit `d2394d30`），此处据实降级为仅"明文日志 + 默认弱口令"。
- 本报告由 fork 维护者侧的 code review 产出，所有定位针对本 fork 当前代码;若上游对应文件已分叉演进，行号需重新对齐。
