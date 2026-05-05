# 代码 Review 报告 — 2026-05-05

> v1.1.0 后首次系统性 audit。范围：`tradingagents/` + `cli/` + `main.py` + `tests/` + fork-local 配置 / CI / Docker。**排除** `app/` 和 `frontend/`（专有授权）。
>
> 审计方式：5 个并行 audit agent 各自分领域（agents+graph / dataflows / llm+tools+utils / cli+tests / fork configs），每个返回结构化 findings。本文是聚合 + 跨域综合。
>
> 本文档作为 backlog 源头——下一步从中挑高优先项目转 OpenSpec changes 进决策追溯链。

---

## TL;DR — 5 个最严重的发现

1. **🔴 假数据污染 LLM 决策链**（dataflows）：数据源失败时返回 `random.uniform(10, 50)` 假股价 + hardcoded `f"{search_term}相关财经新闻标题"` 假新闻给 agent，模型无法区分降级 vs 真实信号。直接影响交易决策。
2. **🔴 测试体系事实上是空的**（cli+tests）：226 个 test 文件中标 `unit` marker 的 = **0 个**，CI `pytest -m unit` 永远 collect 0 测试。三个 STRICT lint hook 中 pytest 那个等于装饰品。
3. **🔴 License 边界跨越**（llm_adapters）：Apache 2.0 的 `tradingagents/llm_adapters/` 反向 import 专有授权的 `app.utils.api_key_utils.is_valid_api_key` 共 5 处，违反 license 分层。
4. **🔴 端口 loopback 单点风险**（fork configs）：`docker-compose.yml` base 文件全部端口默认 `0.0.0.0`，loopback 铁律仅靠**未 tracked** 的 `docker-compose.override.yml` 兜底——任何新机器 clone 后未 override 立即暴露公网。
5. **🔴 `upstream-sync-check.yml` 与项目铁律正面冲突**（fork configs）：cron 定时 fetch + 自动 `git push origin main` + 自动 `gh issue create`——HARD-GATE 明令禁止的"自动外部写入"。整个 workflow 应删（fork 已声明独立分叉）。

## 跨域共性主题

- **Leaky abstraction × N**：4 份 LLM provider 注册表、3 套 MongoDB 连接抽象、4 层缓存、5+ 处 token 优先级 inline、7 份 `_get_company_name` 拷贝、4 套 provider symbol 归一化。"统一" 仅在抽象方法签名层。
- **Module-level 副作用**：`config_manager.py` import 即 mkdir+连 MongoDB+读 .env+写 4 个 JSON；`cli/main.py` import 即改全局 logging；`akshare.py` 进程级 monkey-patch `requests.get`；`logging_init.py` 改全局 `sys.path`。
- **错误吞噬 + 假数据兜底**：业务层无法区分"无数据"vs"上游失败"，加上 `_generate_fallback_data` 假数据，LLM 把降级误读为真实信号。
- **AKShare "拉全市场过滤一行" 反模式**：v1.1.0 修了 favorites_service 的同模式，但 dataflows 中**至少还有 3 处**（A股 / HK 同模式）。
- **Doc 漂移**：CLAUDE.md 多处与现状不符（版本号 / compose 文件清单 / pre-commit 模式）。

---

## 各域完整发现

### 1. `tradingagents/agents` + `tradingagents/graph`

#### Critical

- `tradingagents/graph/trading_graph.py:843` — `process_signal` 用 `final_state["final_trade_decision"]`，若 graph 因任一节点异常未填充该字段会 KeyError；Risk Manager 失败有兜底，但 Trader 等节点异常时无兜底，整条链直接崩。
- `tradingagents/agents/managers/risk_manager.py:120` — `except Exception` 内引用 `start_time`，若首次 `try` 在 `start_time = time.time()` 之前抛异常（如 `prompt` 构造时），`start_time` 未定义会再次抛 `UnboundLocalError`。
- `tradingagents/agents/utils/memory.py:19` — `_collections: dict[str, any]` 用 `any`（内置函数）当类型注解，应为 `Any`；`# noqa: RUF012` 屏蔽了 lint 但语义错误。

#### High

- `tradingagents/graph/conditional_logic.py:14` — `should_continue_market`/`_social`/`_news`/`_fundamentals` 4 个方法 90% 代码重复（仅 state key、tool name、max_tool_calls 不同），应抽 `_should_continue_analyst(analyst_type, max_calls)` 模板。
- `tradingagents/agents/analysts/market_analyst.py:496`, `fundamentals_analyst.py:499`+ — `market_tool_call_count` 在 conditional_logic 里读但 analyst 节点每次返回 `+1`，工具节点 `tools_market` 不更新计数器；`fundamentals` 用 `ToolMessage` 反向更新（line 117-120）逻辑两套并存。
- `tradingagents/agents/researchers/{bull,bear}_researcher.py` + `analysts/{market,fundamentals,social_media,news,china_market}_analyst.py` — `_get_company_name` 7 份近乎相同的拷贝（含同一个美股硬编码字典 `{AAPL: 苹果公司, ...}`），任何修订都得改 7 处；应抽到 `agents/utils/`。
- `tradingagents/graph/trading_graph.py:30-546` — `__init__` 单方法 ~350 行 + 11 个 provider 分支 + 重复的 `quick_config = self.config.get("quick_model_config", {})` 解析（line 229/450/515）；明显该走 strategy/registry。
- `tradingagents/graph/signal_processing.py:228` — `_smart_price_estimation` 返回类型 `-> float` 但实际 `return None` (line 291)；调用方 line 175 检测 `if target_price` 但 `0.0` 也会被当 falsy 误判。
- `tradingagents/agents/utils/memory.py:111-297` — provider→embedding 选型 8 个 `elif` 分支重复（`dashscope_key = os.getenv(...)` + try/import/setattr）；`fallback_available` 仅 google 分支设置，其它分支访问会 AttributeError（line 426 用 `hasattr` 才不崩，依赖巧合）。
- `tradingagents/agents/managers/research_manager.py:101` — `judge_decision` 写入 history 但同一 dict 又写 `current_response: response.content`，下一轮 debate 拿 `current_response.startswith("Bull")` 判断说话人；如果 manager 输出以 "Bull" 开头会污染 speaker tracking。
- `tradingagents/graph/trading_graph.py:705-799` — `propagate` 的三条 stream 分支（debug/progress/no-progress）70% 代码重复。
- `tradingagents/agents/analysts/fundamentals_analyst.py:280-289` — 检测 qwen 后**重新创建** LLM 实例（含 HTTP client/token 校验），每次节点执行都重建；其他 6 个 analyst 不做这事，行为不一致。
- `tradingagents/graph/trading_graph.py:1119-1155` — `_log_state` 同步写本地 JSON，propagate 阻塞磁盘 IO；多并发分析时阻塞 event loop。

#### Medium / Low

- 多处 `market_info["is_china"]` / `["is_hk"]` 取值后丢弃（无效语句）。
- `trader.py:44` `logger.warning("⚠️ memory可用，获取历史记忆")` 把正常路径打成 warning。
- `int(len/1.8)` token 估算 magic number 散落 4+ 处。
- `conditional_logic.py:48,154` `max_tool_calls = 3` vs `1` 硬编码。
- 三个 risk_mgmt debator 不传 `instrument_context`，可能幻觉错股票代码。
- `memory.py:643-686` `__main__` block 调用 `FinancialSituationMemory()` 缺必填参数，是死代码。
- `aggresive_debator.py` 文件名拼错 `aggresive` 应 `aggressive`。

#### Cross-cutting

1. **共有抽象缺位**：7 份 `_get_company_name`、4 份 `should_continue_*`、3 份 stream 循环、6 份 prompt-token 估算 —— 抽 `agents/utils/company_resolver.py` + `graph/_should_continue_template.py`。
2. **状态字段半结构化**：`AgentState` 用 plain str 拼 `"\nBull Analyst: ..."`，下游靠 `startswith("Bull")` 解析；任何 prompt 改动都可能悄悄破坏路由——建议 history 用 list-of-dict。
3. **Provider 路由分散**：`trading_graph.py:__init__`、`memory.py:__init__`、`graph/setup.py:88-105` 都各自做 `"dashscope" in llm_provider` 字符串匹配。

---

### 2. `tradingagents/dataflows`

#### Critical

- `tradingagents/dataflows/optimized_china_data.py:2129` — 数据源失败时返回 `random.uniform(10, 50)` 随机价格作为"模拟数据"输出给 LLM。**模型会拿到伪造价格做决策**。应 raise 而不是 fallback。
- `tradingagents/dataflows/news/chinese_finance.py:143` — `_search_finance_news` 永远返回硬编码假新闻 `f"{search_term}相关财经新闻标题"`，结果流向 `news_sentiment` → `overall_sentiment` → 决策。
- `tradingagents/dataflows/providers/china/akshare.py:762,800` — `_get_realtime_quotes_data(code)` 单股查询调 `stock_zh_a_spot()` / `stock_zh_a_spot_em()` 拉全市场 5849 行后 `.iloc` 过滤一行；与已知 favorites_service 60s bug 同模式（仍在兜底链中）。
- `tradingagents/dataflows/providers/hk/improved_hk.py:275,759,766` — `get_company_name`/`get_hk_stock_info_akshare` 调 `ak.stock_hk_spot()` 拉全 HK 市场只为查 1 只股票名/行情。
- `tradingagents/dataflows/cache/adaptive.py:97,136,209` — Redis/MongoDB 反序列化用 `pickle.load/loads`。任何能写缓存键的旁路（共享 Redis、容器逃逸、MongoDB 弱口令）即 RCE。
- `tradingagents/dataflows/providers/china/akshare.py:60-152` — 进程级 monkey-patch `requests.get`（`requests._akshare_headers_patched` 标记），影响全进程所有 HTTP 调用，包括非 AKShare 路径。`last_request_time` dict 在闭包里非线程安全。
- `tradingagents/dataflows/cache/db_cache.py:58-64` — 默认 `MONGODB_PORT=27018` / `REDIS_PORT=6380` 与项目约定 `54302/54303`（容器内 `27017/6379`）冲突；默认密码 `tradingagents123` 嵌入 URL，未配 env 时直接生效。

#### High

- `tradingagents/dataflows/news/realtime_news.py:162,204,260` — 三处 `requests.get` 无 `timeout`，会无限挂起。
- `tradingagents/dataflows/providers/hk/improved_hk.py:736` — `threading.Lock.acquire(timeout=60)` 在 async path 上使用阻塞锁，**冻结 event loop 长达 60s**；锁内还包了完整 HTTP 调用。
- `tradingagents/dataflows/providers/china/baostock.py:55-62,77-108,128-143` — 每个方法都 `bs.login() + bs.logout()`，baostock 是进程级单例 session；并发调用会互相 logout。
- `tradingagents/dataflows/cache/mongodb_cache_adapter.py:57,181,230,273,307,336` — 全部 `str(symbol).zfill(6)`；对 US 票 `AAPL` 变 `00AAPL`，跨市场查询全错。
- `tradingagents/dataflows/news/google_news.py:73` — `query` 不 URL-encode，含空格/中文/特殊字符直接拼 URL。
- `tradingagents/dataflows/news/google_news.py:113-128` — Timeout 后跳页继续，并非"重试"。
- `tradingagents/dataflows/news/reddit.py:93,102` — 公司名当 regex pattern（`Johnson & Johnson` 中 `.` 与 `&` 不被转义）；`datetime.utcfromtimestamp` Python 3.12 deprecated。
- `tradingagents/dataflows/providers/china/akshare.py:545-692` — `get_batch_stock_quotes` 每次调用重新拉 5849 行，A 股路径无 in-memory 缓存（HK 路径有 600s cache）。
- `tradingagents/dataflows/providers/us/yfinance.py:41-49` — `init_ticker` decorator 每次方法调用 `yf.Ticker(symbol)` 重建；无 LRU。
- `tradingagents/dataflows/cache/file_cache.py:349` — `Path(metadata["file_path"])` 直接用元数据 JSON 里的路径打开，**路径遍历风险**。
- `tradingagents/dataflows/providers/china/tushare.py:71,87,105,112` — token 长度记入 INFO 日志；`ts.set_token` 全局副作用，并发数据库 token 与 .env token 互踩。

#### Medium / Low

- `db_cache.py:77-78` 用 `logger.error()` 输出连接成功状态。
- `improved_hk.py:317-322` `time.time() - cache_ttl + 3600` 黑魔法。
- `mongodb_cache_adapter.py:358-363` 全局 singleton 无锁 + 并发首次创建可能 2 实例。
- `data_source_manager.py:485,2438,2454+` — Token 优先级 "数据库 or env" 5+ 处 inline。
- `BaseStockDataProvider` 用 `symbol` 但 AKShareProvider 子类用 `code` —— LSP 边界。
- `realtime_metrics.py:60-61` — 直接 `from app.core.config import settings`，耦合专有授权层。
- `optimized_china_data.py:2110` — `except Exception: continue` 吞所有异常。
- `realtime_news.py:312` — US ticker suffix 检测对纯 ticker 失败 → 走中文东财路径。

#### Cross-cutting

1. **接口契约虚名**：`BaseStockDataProvider` 名义统一，实际每个 provider 自造 symbol 标准化 + 各自缓存 + 各自 fallback 链。
2. **缓存层四套并存**：`StockDataCache`（file）+ `AdaptiveCacheSystem`（pickle redis/mongo）+ `MongoDBCacheAdapter`（共享）+ provider 内部缓存；TTL/key 规则各异。
3. **错误吞噬 + 假数据**：业务层无法区分"无数据"vs"上游失败"，加上 `_generate_fallback_data` 假数据，LLM 把降级误读为真实信号。**应全部移除假数据 fallback**，让上游 raise，由编排层决定是否兜底。

---

### 3. `tradingagents/{llm_adapters, llm_clients, api, tools, utils, config, constants, models}`

#### Critical

- `tradingagents/llm_adapters/{dashscope_openai_adapter,deepseek_adapter,google_openai_adapter,openai_compatible_base}.py` — Apache 2.0 包反向 import 专有授权代码 `app.utils.api_key_utils.is_valid_api_key`（5 处）。**License 边界跨越**。修复：把 `is_valid_api_key` 移到 `tradingagents/utils/`。
- `tradingagents/llm_adapters/dashscope_openai_adapter.py:62`, `google_openai_adapter.py:79`, `openai_compatible_base.py:101` — 日志输出 API key **前 10 个字符** + 长度。OpenAI key `sk-` + 48 字符前 10 位泄露 7 个有效熵字符。改成只 log "存在/缺失"。
- `tradingagents/config/config_manager.py:733-734` — module import 时**立即实例化** `ConfigManager(...)`，会调 `Path.mkdir(exist_ok=True)`、读 `.env`、连 MongoDB、写 4 个 JSON。任何 import 即触发副作用。改成 lazy singleton。
- `tradingagents/api/stock_api.py:18-23` — runtime `sys.path.append(dataflows_path)` 后无包前缀 import；同文件第 13 行 import 的 `logger` 被 line 23 重新 import 同名遮蔽。
- `tradingagents/llm_adapters/openai_compatible_base.py:21-22` — `logger = get_logger("agents")` 立刻被 `logger = setup_llm_logging()` 覆盖。同模式见 `deepseek_adapter.py:20-21`。第一行无效。

#### High

- `tradingagents/llm_adapters/__init__.py` 仅暴露 2 个类，`openai_compatible_base.py` 还有 `ChatDeepSeekOpenAI` / `ChatZhipuOpenAI` / `ChatQianfanOpenAI` / `ChatCustomOpenAI` + `create_openai_compatible_llm` 工厂——**两条独立工厂链**：`llm_adapters.create_openai_compatible_llm` vs `llm_clients.create_llm_client`，调用方需要知道选哪一个。这就是 `llm_adapters/` 与 `llm_clients/` 职责重叠核心证据。
- `tradingagents/llm_clients/factory.py:33` 把 `qwen` 路由到 `OpenAIClient`，`llm_adapters/dashscope_openai_adapter.py` 也提供 `ChatDashScopeOpenAI`——**同一 provider 两套实现**，用哪个看导入路径决定。
- `tradingagents/llm_clients/factory.py:8` `_PROVIDER_ALIASES` 中 `siliconflow → openai`——但 siliconflow 的 base_url 不是 `api.openai.com`。alias 后调用方未传 base_url，最终发到 `api.openai.com`。**功能性 bug**。
- `tradingagents/llm_clients/openai_client.py:64` ollama 分支硬编码 `api_key = "ollama"`，对所有非 ollama 但 `api_key_env=None` 的 provider 同样会赋值（脆弱）。
- `tradingagents/config/config_manager.py:146` OpenAI key 长度硬等于 51——OpenAI 早已发布 `sk-proj-` 前缀的项目级 key（更长，含连字符）。该 validator 把所有新格式 key 判为无效，到 `load_models:288` 直接 disable 模型——**用户配了正确的 sk-proj- key 也无法启用**。
- `tradingagents/llm_adapters/openai_compatible_base.py:481` `OPENAI_COMPATIBLE_PROVIDERS["custom_openai"]["models"]` 列出 `claude-3-haiku/sonnet/opus`、`gemini-pro`——但 OpenAI-compat 端点不一定能调用 Anthropic/Google 模型，**误导**。
- `tradingagents/llm_adapters/google_openai_adapter.py:200-205` exception fallback 返回带"Google AI 调用失败：…"内容的 `LLMResult`，**吞掉真实异常**——下游 agent 把这段中文当作真实 LLM 输出处理；token tracker 不会记录失败。
- `tradingagents/llm_adapters/google_openai_adapter.py:225-260` `_optimize_message_content` / `_enhance_news_content`：在 LLM adapter 层根据中文关键词猜测内容是新闻并强行注入"发布时间"、"新闻标题"、"文章来源: Google AI 智能分析"等假信息。**leaky abstraction + 数据污染**。
- `tradingagents/models/stock_data_models.py:12,80` 用 pydantic v1 API（`@validator`、`Config` class、`regex=`），pydantic v3 会移除。
- `tradingagents/utils/logging_init.py:13-14` module-level `sys.path.insert(0, ...)`——任何 import 这个模块的代码都会污染 sys.path。

#### Medium / Low

- `openai_compatible_base.py:128-134` `try/except` 区分新旧 LangChain 参数名，但 `try` 永不抛——except 永不执行（死代码）。
- `openai_compatible_base.py:294-324` `_truncate_messages` 静默从尾部截断 messages（system prompt 可能被丢弃），无 caller 可控开关。
- `dashscope_openai_adapter.py:120` / `deepseek_adapter.py:151` session_id 用 `hash()` 进程间不稳定。
- 4 个 adapter token 提取逻辑各不相同（4 套规则）。
- `config_manager.py:78` 构造参数名义可配置实际不可配置。
- `database_config.py` vs `database_manager.py` vs `mongodb_storage.py` — **3 个 MongoDB 连接来源**，3 套 env 名约定。
- `providers_config.py:8` / `news_filter.py:10` / `unified_news_tool.py:12` 自建 logger 绕过 `logging_manager`。
- `anthropic_client.py:32` / `google_client.py:23-25` 不读环境变量只读 kwargs；`OpenAIClient` 读 env——**3 个 client 行为不一致**。
- `stock_utils.py:48` / `unified_news_tool.py:79-81` / `stock_data_models.py` — 港股识别逻辑 3 处复制。
- `config_manager.py:546` `datetime.fromisoformat(record.timestamp)` 与 naive `datetime.now()` 比较会 TypeError。
- `model_catalog.py:32` `claude-3-7-sonnet-latest` 不存在；`gemini-2.5-flash-lite-preview-06-17` preview 版写死有过期风险。
- `enhanced_news_retriever.py` 空文件 dead module。

#### Cross-cutting

- **LLM 抽象未真正解耦**：`llm_adapters/` 与 `llm_clients/` 同时存在，**4 份 provider 注册表**（`MODEL_OPTIONS` / `provider_keys` / `_PROVIDER_CONFIG` / `OPENAI_COMPATIBLE_PROVIDERS`），添加新供应商需同步至少 4 处。
- **Config 散落**：`config/` 8 个文件有 3 套 MongoDB 抽象、2 套布尔解析、deprecated `ConfigManager` 模块导入即触发 mkdir / .env load / MongoDB 连接副作用。
- **`google_openai_adapter._enhance_news_content` 把业务语义灌进 adapter 层**是最严重的 leak。

---

### 4. `cli/` + `main.py` + `tests/`

#### Critical

- `tests/conftest.py:14-25` 把所有未显式标 marker 的 test auto-mark 成 `requires_env`，结果 `tests/` 下 **226 个 `test_*.py` 中只有 2 个标了 `integration`、4 个 `requires_env`、零个 `unit`**。CI/pre-commit 跑 `pytest -m unit` 永远 collect 0 → exit 5 → **测试体系实际完全不在 CI 流水线里**。
- 70+ 文件直接 `import baostock`/`tushare.pro_api()`/`requests.get("http://localhost:8000")` 进行真实联调，但既未 `requires_network` 也未 `integration`。`tests/test_amplitude_api.py:5-9` 写死 `BASE_URL`/`USERNAME=admin/PASSWORD=admin123`，无 fixture/skip 逻辑，离线必崩。

#### High

- `cli/main.py:1546,1551,1556,1561,1566` API key **前 12 位**直接渲染到 Rich 表格（`DEFAULT_API_KEY_DISPLAY_LENGTH=12`）。改成 `***` 或末 4 位。
- `tests/test_import.py`、`tests/test_pydantic_fix.py` 等 17+ 文件**不含任何 `def test_*`**，纯 `try/except + print` 脚本，pytest collect 不到——一次性调试残留，应转 `scripts/` 或删。
- `cli/main.py:1828-1857` `main()` catch `SystemExit` 但**没有 `KeyboardInterrupt` / SIGTERM 处理**。1860 LOC + 多智能体长流程，Ctrl+C 在 LangGraph stream 中可能留下半完成 state + 未关闭的 LLM streaming connection。
- `tests/services/test_*.py`、`tests/middleware/test_trace_id.py`、`tests/dataflows/test_realtime_metrics.py`、`tests/unit/tools/analysis/test_indicators_uil.py` 都是**纯 mock / 纯函数**测试，却被 conftest 默认打成 `requires_env` —— CI 跑不到这批最有价值的回归测试。

#### Medium / Low

- `main.py:1-26` 顶层 demo 硬编码 `llm_provider=google` + Gemini endpoint + `NVDA / 2024-05-10`，与 `cli/main.py` typer app 完全分裂；`pyproject.toml` 没有 `[project.scripts]` entry point。
- `cli/main.py:1758-1783` `test` 子命令直接 `subprocess.run([sys.executable, "tests/integration/..."])`——硬编码相对路径 + 单测试文件。
- 多个 test 文件 `sys.path.append(...)` 重复 hack（conftest 已做）。
- `cli/main.py` 1860 LOC 单文件，`run_analysis()` ~700 LOC 把 UI / state / LangGraph 编排 / 信号转换全混。
- 30+ 个 `test_*_fix.py` / `test_*_quick.py` / `test_*_simple.py` / `test_*_debug.py` 命名暴露生命周期（修 bug 时新增、修完不清理），多数已是孤儿。
- `cli/main.py:62-84` `setup_cli_logging()` 在 module import 时副作用执行，单测 import `cli.main` 改全局 logging 配置。
- `tests/__init__.py` 让 tests 成为 package，与 pytest rootdir auto-discovery 冲突。
- 多个 `tests/testgoogle.py` / `tests/check_*.py` / `tests/verify_*.py` 不符合 `test_*.py` 命名，pytest 默认 collect 不到。

#### 测试 marker 重分类（按现有规则可立即执行）

可立即标 `unit` 的 mock-only 文件：
- `tests/middleware/test_trace_id.py` (FastAPI TestClient + 内置 logger)
- `tests/services/test_quotes_backfill.py` / `test_quotes_ingestion_and_enrichment.py` / `test_scheduler_quotes_job.py` / `test_screening_roe_field.py`（纯 monkeypatch + FakeManager/FakeCursor）
- `tests/dataflows/test_realtime_metrics.py`（纯函数）
- `tests/unit/tools/analysis/test_indicators_uil.py`（numpy/pandas 纯计算）
- `tests/test_provider_keys.py` / `test_normalize_provider_keys_script.py`（纯 mapping）
- `tests/test_tushare_unified/test_tushare_sync_service.py`（AsyncMock 全 mock）

#### Cross-cutting

- **CLI**：单 typer app + 1860 LOC 巨型 `cli/main.py`，框架选择正确但缺乏拆分；启动时无意义副作用；API key 半截打印 + 无 SIGINT graceful shutdown 是两个真实风险点。
- **测试**：测试金字塔**完全倒置且事实上 dead** —— 226 文件中真正可在 CI 跑的 unit test 是**零**。建议立刻给纯 mock 文件批量补 `pytestmark = pytest.mark.unit`。

---

### 5. Fork configs / CI / Docker

#### Critical

- `.github/workflows/upstream-sync-check.yml:1-256` 整个 workflow 直接违反"独立分叉，不再 sync upstream"约定（`openspec/specs/repository-scope/spec.md`）。它每周一定时 fetch upstream、自动 `git push origin main`（line 223）、自动 `gh issue create`（line 168-174）。HARD-GATE 明令禁止"自动外部写入"。**整文件应删**。
- `.github/workflows/upstream-sync-check.yml:218-219` `python scripts/sync_upstream.py --auto` 引用脚本不存在，auto-sync 一旦触发直接报错；即使能跑也违反铁律。
- `Dockerfile.backend:89` `--host 0.0.0.0` 监听公网。即便容器端口由 override 限制为 `127.0.0.1:54301:8000`，prod-like compose 用 hub 镜像若缺 override 就直接暴露。
- `docker-compose.yml:15,72,101,130,156,179` base compose 所有端口映射 `"8000:8000"` 等全部绑 `0.0.0.0`，且**端口非 54300-54309 段**。仅靠 `docker-compose.override.yml`（**未 tracked**）兜底——任何 clone 后未 override 的环境立即暴露公网。
- `docker-compose.yml:34-35,104,133,158,183-185` 硬编码密码 `tradingagents123` 进 tracked YAML（mongo/redis/mongo-express/redis-commander 全部）。`mongo-express` 的 `ME_CONFIG_BASICAUTH_PASSWORD` 与 mongo root 同密码。

#### High

- `Dockerfile.backend:6` `python:3.10-slim-bookworm`，与本地 3.12 偏离（已知坑）。
- `docker-compose.hub.nginx.yml` 和 `docker-compose.hub.nginx.arm.yml` **不存在**（CLAUDE.md 命令速查段宣称 3 个 compose 变体，实际只有 1 + override）。**文档与现实漂移**。
- `docker-compose.yml:43` `CORS_ORIGINS` hardcode 上游默认 `localhost:3000/8080/5173`，与 fork 端口段位 54300 完全不符；override 修正了，但 base 仍 tracked。
- `Dockerfile.backend:67-69` `pip install` 用清华镜像 + `prefer-binary`，CI 不可重现，且无 lock 验证；与本地 `uv sync --frozen` 路径完全不同源。
- `frontend/vite.config.ts:53-55` `fs.allow: [resolve(__dirname, '..')]` 允许 vite dev 读项目根之外（含 `.env`），dev only 但仍是越权读盘风险。

#### Medium / Low

- `.github/workflows/ci.yml:33-34` CI 走 `uv pip install -e ".[dev]"`，但 justfile `setup` 段没装 dev extras——本地与 CI 装包不同源。
- `.pre-commit-config.yaml` 与 CLAUDE.md 描述冲突：CLAUDE.md 写"WARN-ONLY 模式"但实际 ruff/format/pyright 都是 STRICT。**文档过时**。
- `.github/dependabot.yml:7-10` `pip` ecosystem 拉 PR 但项目用 uv.lock，dependabot 不懂 uv lock，PR 必假阳性 / 假绿。
- `pyproject.toml:7` `version = "1.1.0"`，CLAUDE.md "项目身份"段说 `1.0.0-preview`——**文档过时**。
- `docker-compose.yml:1` `version: '3.8'` docker compose v2 已 deprecated。
- `Dockerfile.backend:80` `COPY .env.docker ./.env` 把 dev 配置打进镜像。
- `.gitignore:212-216` 文件中段有损坏行（带空格分隔字符 `c o n f i g / b a c k u p /`），ignore 规则失效。
- `docker-compose.yml:97` `mongo:4.4` EOL（2024-02），有 CVE。

#### Sanity check 结果

| 项 | 状态 | 证据 |
|---|---|---|
| 端口段位 loopback | ⚠️ 部分 | override 全 `127.0.0.1:543xx`（合规），base 全 `0.0.0.0` 且非段位（不合规）；override 未 tracked = 单点风险 |
| ruff exclude | ✅ | `pyproject.toml:112` `["app", "frontend", "scripts", ".venv"]` |
| pyright exclude | ✅ | `pyproject.toml:125` 同上 + `**/node_modules` |
| 自动外部写 trigger | ❌ | `upstream-sync-check.yml` cron + auto push + auto issue create |
| Dockerfile python 版本 | ⚠️ | `python:3.10-slim-bookworm`，与本地 3.12 偏离 |

#### Cross-cutting

最严重是 `upstream-sync-check.yml` 与项目铁律正面冲突 + HARD-GATE 禁止动作；其次 `docker-compose.yml` base 端口绑定与端口段位约定完全不符，loopback 只靠 untracked override 兜底。CLAUDE.md 多处与现状漂移：版本号、compose 文件清单、pre-commit 模式描述。

---

## 反向 import baseline（v1.1.0 后）

OpenSpec spec `license-boundary` 要求 `tradingagents/ → app/` 反向 import 数量单调不增。**v1.1.0 后 baseline = 22**（修完 `move-api-key-utils-to-tradingagents` 之后），具体清单见下：

```
tradingagents/config/runtime_settings.py:55 (注释行 # type: ignore)
tradingagents/tools/unified_news_tool.py:259 → app.services.news_data_service
tradingagents/utils/stock_validator.py:{342,512,786,790,841} → app.core.config / app.worker.*
tradingagents/dataflows/realtime_metrics.py:{58,375} → app.core.config
tradingagents/dataflows/interface.py:{65,120,1501,1739} → app.core.database / app.core.config
tradingagents/dataflows/data_source_manager.py:{113,433,529,2340,2471,2502} → app.core.database
tradingagents/dataflows/providers/us/alpha_vantage_common.py:51 → app.core.database
tradingagents/dataflows/providers/us/optimized.py:532 → app.core.config
tradingagents/dataflows/providers/china/tushare.py:53 → app.core.database
```

后续 OpenSpec change `eliminate-app-business-layer-imports`（梯队 3）将系统性消除这些。任何新 PR 都不得增加该数字。

---

## 推荐 OpenSpec changes（按 ROI 排序）

下表按"影响范围 × 实施成本"排序——前面的优先做。每条对应未来一个独立 OpenSpec change（`/opsx:propose <id>`）。

### 第一梯队（立即做，1-2 个工作半天）

| ID 建议 | 范围 | 描述 | 立即收益 |
|---|---|---|---|
| `delete-upstream-sync-workflow` | 1 文件 | 删 `.github/workflows/upstream-sync-check.yml`（铁律违反 + HARD-GATE 违规） | 消除潜在自动 push 风险 |
| `docker-compose-loopback-baseline` | base compose | 把 `docker-compose.yml` 端口前缀全改 `127.0.0.1:543xx:` + 校正端口段位 | 移除 untracked override 单点风险 |
| `tests-mark-unit-batch-1` | tests/ 局部 | 给 ~10 个纯 mock 测试文件批量补 `pytestmark = pytest.mark.unit`（已列清单） | CI pytest hook 真正生效 |
| `claude-md-doc-drift` | CLAUDE.md | 修 3 处漂移：版本号 1.1.0 / compose 文件清单 / pre-commit STRICT 模式 | 消除新会话 prime context 误导 |

### 第二梯队（中等工作量，每条 1-2 工作日）

| ID 建议 | 范围 | 描述 |
|---|---|---|
| `remove-fake-data-fallback` | dataflows | 删 `optimized_china_data.py:2129` random price + `chinese_finance.py:143` 假新闻 + 全局 `_generate_fallback_data` 假数据，改为 raise |
| `move-api-key-utils-to-tradingagents` | llm_adapters + app | 把 `app.utils.api_key_utils.is_valid_api_key` 移到 `tradingagents/utils/`，删除 5 处反向 import（修 license 边界） |
| `redact-api-key-logs` | llm_adapters + cli | 统一 `_log_api_key()` helper，改成只 log "存在/缺失" + 末 4 位（消除前 10 字符泄露） |
| `lazy-config-manager` | config_manager | 改成 lazy singleton，消除 module import 时 mkdir + 连 mongodb + 写 JSON 副作用 |
| `fix-openai-key-validator` | config_manager | 修 `key.length == 51` 硬等的 bug，支持 `sk-proj-` 前缀的项目级 key |
| `tests-cleanup-debug-scripts` | tests/ | 移除 30+ `test_*_fix.py` / `debug_*.py` / `quick_*.py` 历史 ad-hoc 脚本（不符合 `test_*.py` 命名的也清掉） |

### 第三梯队（架构级重构，每条 1 周量级）

| ID 建议 | 范围 | 描述 |
|---|---|---|
| `consolidate-llm-adapter-layers` | llm_adapters + llm_clients | 合并两个目录 / 工厂链；统一 4 份 provider 注册表为单一 source of truth |
| `extract-company-resolver` | agents/ | 抽 7 份 `_get_company_name` 拷贝 + 美股硬编码字典到 `agents/utils/company_resolver.py` |
| `provider-registry-single-source` | tradingagents/ | 统一 `MODEL_OPTIONS` + `provider_keys` + `_PROVIDER_CONFIG` + `OPENAI_COMPATIBLE_PROVIDERS` 4 份注册表 |
| `eliminate-akshare-fullmarket-pull` | dataflows/providers/china + hk | 找出剩余 3+ 处"拉全市场过滤一行"反模式，逐一改成单股 API |
| `cache-layer-consolidation` | dataflows/cache | 统一 4 套缓存层（FileCache / AdaptiveCacheSystem / MongoDBCacheAdapter / provider 内部）；同时把 `pickle.load` 改成 JSON 或 msgpack |
| `agent-state-structured-history` | agents/ + graph/ | history 从 plain str + `startswith("Bull")` 解析改成 list-of-dict |

### 第四梯队（小修小补，攒 1 个 change 一起做）

| ID 建议 | 范围 | 描述 |
|---|---|---|
| `misc-bugfix-batch` | 多目录 | risk_manager `start_time` UnboundLocal / `process_signal` KeyError 兜底 / `_smart_price_estimation` 类型谎报 / `siliconflow → openai` 路由 bug / `mongodb_cache_adapter.zfill(6)` 跨市场 bug / google_news URL-encode / reddit regex escape |
| `dockerfile-python-3.12` | Dockerfile.backend | 升 base image `python:3.12-slim-bookworm` 与本地一致 |
| `gitignore-fix-corrupted-lines` | .gitignore | 修 line 212-216 的损坏行 |

---

## 不建议改的（low ROI 或越界）

- 多处中文 emoji 重度日志：保留特色；如要做按 OpenSpec 单独提
- `aggresive_debator.py` 拼写：改名涉及 import 链，收益小
- pydantic v1 → v2 迁移（`stock_data_models.py`）：大改动，等到 pydantic v3 真删 v1 API 时再做
- 公司名硬编码字典消除：需要外部数据源，超出 fork 范围

---

## 下一步

请 review 本文 + 从 4 梯队中挑要立即做的 changes。我建议至少把"第一梯队"4 个全做（消除铁律违规 + 文档漂移 + 测试空转）——加起来不超过半天工作量。

回复格式：`第一梯队全做 + 第二梯队挑 [...]` 或具体 ID 清单。
