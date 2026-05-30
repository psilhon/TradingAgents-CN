# toolkit-config-isolation

## Why

`tradingagents/agents/utils/agent_utils.py` 的 `Toolkit` 用**类级共享可变 dict** 持有 config：

```python
class Toolkit:
    _config = DEFAULT_CONFIG.copy()        # 类属性（全进程唯一）

    @classmethod
    def update_config(cls, config):
        cls._config.update(config)         # in-place mutate 共享 dict

    @property
    def config(self):
        return self._config                # 无实例级隔离

    def __init__(self, config=None):
        if config:
            self.update_config(config)     # 走 classmethod → 改全局
```

构造 `Toolkit(config_a)` 后再构造 `Toolkit(config_b)`，或一个 FastAPI 进程里**两个并发分析**各自构造 graph/toolkit，会互相覆写同一个 `_config` —— cross-request config bleed（A 用户的分析读到 B 用户的 `research_depth` 等设置）。`trading_graph.py:555` 每次分析新建 `Toolkit(config=self.config)`，该 bug 在并发场景下可达（last-writer-wins + 竞态）。

全项目 code review（2026-05-30 workflow）将此列为 **HIGH / CONFIRMED correctness**。

### 实际消费面（决定改动规模，已逐一核实源码）

- 26 个 `@staticmethod @tool` 方法中，**仅 `agent_utils.py:692`** 读 `Toolkit._config`（取 `research_depth`）。
- 外部**仅 `fundamentals_analyst.py:84`** 读 `toolkit.config['online_tools']`（且仅 debug 日志）。
- `online_tools` **不** gate 工具绑定（`trading_graph.py` 的 ToolNode 把 online+offline 全绑，由 LLM 自选；见该方法注释）。

> 因此根因是「**共享可变状态被 mutate**」，不是「26 个工具的架构耦合」。修复应针对 bleed 本身，而非重构全部工具签名（那是 over-engineering / 违反 YAGNI）。

## What Changes

### 新建 helper `tradingagents/agents/utils/toolkit_config.py`（~30 行）

用 `contextvars.ContextVar` 持有「当前执行上下文的 config」：

- `_current_config: ContextVar[dict | None]`（module-level，default=None）
- `set_toolkit_config(config: dict) -> None` —— 合并 `DEFAULT_CONFIG` + 传入 config 成**新 dict**，set 进 ContextVar（绝不 in-place mutate 任何共享 dict）
- `get_toolkit_config() -> dict` —— ContextVar 有值则返回；否则返回 `DEFAULT_CONFIG` 的只读副本作为默认兜底

### 改 `tradingagents/agents/utils/agent_utils.py`（2 处）

- `Toolkit.__init__(config)`：传 config 时调 `set_toolkit_config(config)`（不再走 `cls._config.update`）
- `Toolkit.config` property：`return get_toolkit_config()`
- `Toolkit._config` 类属性：**保留**，作为 `get_toolkit_config` 在 ContextVar 未 set 时的默认来源（CLI / 测试 / 任何不经 Toolkit 构造的路径）
- `Toolkit.update_config` classmethod：**保留但标 deprecated**（docstring 说明 + 内部转调 `set_toolkit_config`），避免破坏潜在调用方
- line 692：`Toolkit._config.get("research_depth", "标准")` → `get_toolkit_config().get("research_depth", "标准")`

### 不变量（根治 bleed 的核心）

`set_toolkit_config` 永远写**新 dict** 进 ContextVar，绝不 mutate 共享的 `DEFAULT_CONFIG` 或类属性 `_config`。并发分析在各自的 worker 线程里有独立 ContextVar context → 天然隔离。

## Impact

### 线程模型（为什么 ContextVar 成立）

分析在 worker 线程内执行：`simple_analysis_service._execute_analysis_sync`（经 `loop.run_in_executor`）→ `_get_trading_graph` → `TradingAgentsGraph(...)` → `Toolkit(config)`（set ContextVar）→ `propagate` → `graph.stream` → `@staticmethod tool`（read ContextVar）。set 与 read 同在一个 worker 线程，ContextVar 命中；3 个并发分析 = 3 个独立线程 context → 隔离。

**设计约束**：ContextVar 不跨 `run_in_executor` 边界自动传播，所以 set 点必须在 worker 线程内（`Toolkit.__init__` 满足）；**不要**在 async 路由层 set。CLI 直跑（`main.py`，单线程）：构造 `Toolkit(config)` 即 set，同线程 tool 读到，照常工作。

### Code 变化

| 文件 | 变化 |
|---|---|
| `tradingagents/agents/utils/toolkit_config.py` | 新建（~30 行） |
| `tradingagents/agents/utils/agent_utils.py` | `__init__` / `config` property / line 692 改写 + `update_config` 标 deprecated（~10 行净变化） |
| `tests/test_toolkit_config_isolation.py` | 新建（unit） |
| `docs/CHANGELOG.md` | `[Unreleased]` Fixed 条目 |

### 测试（纯 unit，无外部依赖）

1. **隔离核心（回归）**：两个线程各构造 `Toolkit({"research_depth": "A"/"B"})` 后 `get_toolkit_config()`，断言互不串味。旧代码此处必挂。
2. **默认兜底**：未构造 Toolkit 时 `get_toolkit_config()` 含 `DEFAULT_CONFIG` 键。
3. **不污染默认**：`set_toolkit_config({"research_depth": "X"})` 后 `DEFAULT_CONFIG["research_depth"]` 不变（证明写的是新 dict）。
4. **property 一致性**：`Toolkit(cfg).config` 与 `get_toolkit_config()` 行为一致。
5. **line 692 路径**：`set_toolkit_config({"research_depth": 4})` 后该读取点拿到 4。

### License 边界

全部改动在 `tradingagents/`（Apache 2.0）+ `tests/`，**不碰** `app/` / `frontend/`（专有授权）。`fundamentals_analyst.py:84` 的 `toolkit.config['online_tools']` 读取行为不变（property 仍返回含该键的 dict），无需改动。

### 风险

- 低。改动面 3 文件、消费面 1 处，行为对所有现有调用方保持兼容（property 接口不变、`_config` / `update_config` 保留）。
- 唯一需测试覆盖的语义点：ContextVar 跨线程隔离 —— 由测试 1 显式守护。

### Push 策略

单次 commit + 用户 1-click `git push origin main`（按项目 dataflows epic 惯例）。

## Out of Scope

- **不**把 26 个工具改实例方法（消费面仅 1 处，不值；违反 YAGNI）。
- **不**删 `_config` / `update_config`（保兼容；删公共 API 需更大测试面）。
- **不**动 `online_tools` 的工具绑定逻辑（本就不是 bug）。
- **不**给 ContextVar 配 set/reset token 生命周期（单线程单分析串行执行，A 方案足够）。
- 其它 code review 发现（RSI NaN / signal_processing regex 等）属各自独立 change。
