# Toolkit Config Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `Toolkit` 的跨请求 config 串味 —— 用 `contextvars.ContextVar` 持有请求级 config，替换类级共享可变 dict。

**Architecture:** 新建 module-level ContextVar helper（`toolkit_config.py`），`Toolkit.config` 改为「优先读 ContextVar → 回退 `DEFAULT_CONFIG` 默认」，`Toolkit.__init__` 在构造时把 config set 进 ContextVar。分析在 worker 线程内执行，每线程独立 ContextVar context → 天然隔离。类属性 `_config` 与 `update_config` 保留作兼容兜底。

**Tech Stack:** Python 3.12 / `contextvars`（stdlib）/ pytest（`-m unit`）/ ruff + pyright STRICT。

**License 边界:** 全部改动在 `tradingagents/`（Apache 2.0）+ `tests/`，不碰 `app/` / `frontend/`。

**关键事实（实现时务必知道）:**
- `DEFAULT_CONFIG`（`tradingagents/default_config.py`）**没有** `research_depth` 键 —— 所以 `agent_utils.py:692` 用 `.get("research_depth", "标准")` 带 fallback。helper 的 merge `{**DEFAULT_CONFIG, **config}` 自然兼容；「默认兜底」测试要断言一个 **DEFAULT_CONFIG 里真有的键**（用 `online_tools`），不要断言 `research_depth`。
- `DEFAULT_CONFIG` 有键：`online_tools`（bool）、`llm_provider`（"openai"）、`max_debate_rounds`（1）等。
- ContextVar **不**跨 `loop.run_in_executor` 边界自动传播 → set 点必须在 worker 线程内。`Toolkit.__init__` 在 worker 线程被调（`trading_graph.py:555` ← `_get_trading_graph` ← `_execute_analysis_sync`），满足。
- pre-commit STRICT：ruff check + ruff format + pyright 全过才能 commit；`pytest -m unit` 在 pre-push 阻塞。
- 运行 pytest 用 `.venv/bin/python -m pytest ...`。conftest 已把项目根加进 sys.path。

---

## File Structure

| 文件 | 责任 | 动作 |
|---|---|---|
| `tradingagents/agents/utils/toolkit_config.py` | ContextVar 持有 + set/get 请求级 config | 新建（~35 行） |
| `tradingagents/agents/utils/agent_utils.py` | `Toolkit` 接入 helper（init/property/line 692/update_config） | 改 4 处 |
| `tests/test_toolkit_config_isolation.py` | 隔离 + 兜底 + 不污染 + property + 692 路径 守护 | 新建（unit） |
| `docs/CHANGELOG.md` | `[Unreleased]` Fixed 条目 | 改 1 处 |

---

## Task 1: ContextVar helper + 隔离/兜底/不污染测试（red → green）

**Files:**
- Create: `tradingagents/agents/utils/toolkit_config.py`
- Test: `tests/test_toolkit_config_isolation.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_toolkit_config_isolation.py`：

```python
"""Toolkit config 实例隔离（ContextVar 注入）守护测试。

回归背景：Toolkit 原先用类级共享可变 dict 持有 config，update_config
in-place mutate 它，导致并发分析跨请求串味（cross-request config bleed）。
改用 contextvars.ContextVar 后，每个执行上下文（worker 线程）持有独立 config。
纯逻辑 unit test，不触外部依赖。
"""

from __future__ import annotations

import threading

import pytest

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.agents.utils.toolkit_config import (
    get_toolkit_config,
    set_toolkit_config,
)

pytestmark = pytest.mark.unit


def test_isolation_across_threads() -> None:
    """核心回归：两个线程各 set 不同 config，互不串味。

    旧的类级共享 dict 在此处必挂（B 线程会覆写 A 线程的值）。
    """
    results: dict[str, object] = {}
    barrier = threading.Barrier(2)

    def worker(name: str, depth: str) -> None:
        set_toolkit_config({"research_depth": depth})
        # 两线程都 set 完之后再各自读，最大化暴露串味
        barrier.wait(timeout=5)
        results[name] = get_toolkit_config().get("research_depth")

    t_a = threading.Thread(target=worker, args=("A", "快速"))
    t_b = threading.Thread(target=worker, args=("B", "全面"))
    t_a.start()
    t_b.start()
    t_a.join(timeout=5)
    t_b.join(timeout=5)

    assert results["A"] == "快速", f"线程 A 串味：读到 {results['A']}"
    assert results["B"] == "全面", f"线程 B 串味：读到 {results['B']}"


def test_default_fallback_when_unset() -> None:
    """未 set 时返回含 DEFAULT_CONFIG 键的 dict（用 online_tools，
    因为 DEFAULT_CONFIG 没有 research_depth 键）。"""

    def worker(out: dict[str, object]) -> None:
        # 全新线程 context，必定未 set
        cfg = get_toolkit_config()
        out["has_key"] = "online_tools" in cfg
        out["value"] = cfg.get("online_tools")

    out: dict[str, object] = {}
    t = threading.Thread(target=worker, args=(out,))
    t.start()
    t.join(timeout=5)

    assert out["has_key"] is True
    assert out["value"] == DEFAULT_CONFIG["online_tools"]


def test_set_does_not_mutate_default_config() -> None:
    """set_toolkit_config 写新 dict，绝不污染共享 DEFAULT_CONFIG。"""
    original = DEFAULT_CONFIG.get("online_tools")
    set_toolkit_config({"online_tools": not original, "research_depth": "深度"})
    assert DEFAULT_CONFIG.get("online_tools") == original, "DEFAULT_CONFIG 被污染"
    assert "research_depth" not in DEFAULT_CONFIG, "新键泄漏进 DEFAULT_CONFIG"


def test_set_merges_over_defaults() -> None:
    """set 后的 config 既含传入键，也含 DEFAULT_CONFIG 的其它键。"""
    set_toolkit_config({"research_depth": "标准"})
    cfg = get_toolkit_config()
    assert cfg["research_depth"] == "标准"
    assert "online_tools" in cfg  # 来自 DEFAULT_CONFIG 合并
```

- [ ] **Step 2: 跑测试确认 fail**

Run: `.venv/bin/python -m pytest tests/test_toolkit_config_isolation.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tradingagents.agents.utils.toolkit_config'`（collection error）。

- [ ] **Step 3: 写 helper 实现**

创建 `tradingagents/agents/utils/toolkit_config.py`：

```python
"""Request-scoped Toolkit configuration via ContextVar.

Toolkit's tool methods are ``@staticmethod @tool`` (no ``self``), so they
historically read a class-level shared mutable dict (``Toolkit._config``).
``update_config`` mutated it in place, so two concurrent analyses in one
process clobbered each other's config (cross-request config bleed).

This module holds the *current execution context's* config in a
``ContextVar``. Analyses run in worker threads (each with its own ContextVar
context), so per-request config stays isolated. The setter always stores a
fresh dict merged over ``DEFAULT_CONFIG`` — it never mutates a shared dict.

Constraint: ContextVar does not propagate across ``loop.run_in_executor``
boundaries automatically, so ``set_toolkit_config`` must be called *inside*
the worker thread that runs the graph (it is — via ``Toolkit.__init__``).
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from tradingagents.default_config import DEFAULT_CONFIG

_current_config: ContextVar[dict[str, Any] | None] = ContextVar(
    "toolkit_config", default=None
)


def set_toolkit_config(config: dict[str, Any]) -> None:
    """Store a request-scoped config (merged over DEFAULT_CONFIG) for the
    current context. Always writes a NEW dict — never mutates a shared one."""
    _current_config.set({**DEFAULT_CONFIG, **config})


def get_toolkit_config() -> dict[str, Any]:
    """Return the current context's config, or a copy of DEFAULT_CONFIG when
    nothing has been set (CLI / tests / any non-worker path)."""
    current = _current_config.get()
    if current is None:
        return dict(DEFAULT_CONFIG)
    return current
```

- [ ] **Step 4: 跑测试确认 pass**

Run: `.venv/bin/python -m pytest tests/test_toolkit_config_isolation.py -q`
Expected: PASS（4 passed）。

- [ ] **Step 5: lint + typecheck helper + 测试**

Run:
```bash
uvx ruff check tradingagents/agents/utils/toolkit_config.py tests/test_toolkit_config_isolation.py
uvx ruff format --check tradingagents/agents/utils/toolkit_config.py tests/test_toolkit_config_isolation.py
uvx pyright tradingagents/agents/utils/toolkit_config.py
```
Expected: ruff "All checks passed!" / format "already formatted" / pyright "0 errors"。
若 format 报未格式化：跑 `uvx ruff format <file>` 再继续。

- [ ] **Step 6: 不 commit**（等 Task 2 接入后一起 commit；本 change 单 commit）

---

## Task 2: 接入 Toolkit（green）

**Files:**
- Modify: `tradingagents/agents/utils/agent_utils.py`（import 段 + 第 33-48 行 Toolkit 头部 + 第 692 行）
- Test: `tests/test_toolkit_config_isolation.py`（追加 2 个用例）

- [ ] **Step 1: 加 import**

在 `tradingagents/agents/utils/agent_utils.py` 第 8 行 `from tradingagents.default_config import DEFAULT_CONFIG` 之后加一行：

```python
from tradingagents.agents.utils.toolkit_config import get_toolkit_config, set_toolkit_config
```

（`DEFAULT_CONFIG` import 保留 —— 第 34 行类属性仍用它。）

- [ ] **Step 2: 改 Toolkit 类头部（第 33-48 行）**

将现有：

```python
class Toolkit:
    _config = DEFAULT_CONFIG.copy()

    @classmethod
    def update_config(cls, config):
        """Update the class-level configuration."""
        cls._config.update(config)

    @property
    def config(self):
        """Access the configuration."""
        return self._config

    def __init__(self, config=None):
        if config:
            self.update_config(config)
```

替换为：

```python
class Toolkit:
    # 类属性保留作 ContextVar 未 set 时的默认兜底来源（不再承载请求级状态）。
    _config = DEFAULT_CONFIG.copy()

    @classmethod
    def update_config(cls, config):
        """Set request-scoped config via ContextVar.

        Deprecated（命名保留兼容）：此前 in-place mutate 类级共享 dict，导致
        并发分析跨请求串味。现转调 set_toolkit_config，写请求级 ContextVar。
        """
        set_toolkit_config(config)

    @property
    def config(self):
        """Access the current request-scoped configuration."""
        return get_toolkit_config()

    def __init__(self, config=None):
        if config:
            set_toolkit_config(config)
```

- [ ] **Step 3: 改第 692 行**

将：

```python
        research_depth = Toolkit._config.get("research_depth", "标准")
```

替换为：

```python
        research_depth = get_toolkit_config().get("research_depth", "标准")
```

- [ ] **Step 4: 追加 property + 692 路径测试**

在 `tests/test_toolkit_config_isolation.py` 末尾追加：

```python
def test_toolkit_property_reflects_set_config() -> None:
    """Toolkit().config property 与 get_toolkit_config 行为一致。"""
    from tradingagents.agents.utils.agent_utils import Toolkit

    tk = Toolkit(config={"research_depth": "深度"})
    assert tk.config.get("research_depth") == "深度"
    assert tk.config.get("research_depth") == get_toolkit_config().get("research_depth")


def test_toolkit_init_sets_context_for_line692_read() -> None:
    """构造 Toolkit 后，line 692 风格的读取拿到本次 config 的 research_depth。"""
    from tradingagents.agents.utils.agent_utils import Toolkit

    Toolkit(config={"research_depth": 4})
    # 模拟 agent_utils.py:692 的读取路径
    assert get_toolkit_config().get("research_depth", "标准") == 4
```

- [ ] **Step 5: 跑新测试 + import-smoke**

Run:
```bash
.venv/bin/python -m pytest tests/test_toolkit_config_isolation.py -q
.venv/bin/python -c "import tradingagents.agents.utils.agent_utils; print('IMPORT_OK')"
```
Expected: pytest 6 passed；import 打印 `IMPORT_OK`（其间 MongoDB "connection refused" 日志属正常 fallback，可忽略）。

- [ ] **Step 6: 不 commit**（Task 3 验证后统一 commit）

---

## Task 3: 全量验证 + CHANGELOG + commit

**Files:**
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: 跑全套 unit 测试（确认未破坏既有）**

Run: `.venv/bin/python -m pytest -m unit -q`
Expected: 全绿（含新增 6 个用例）。若有既有用例因本改动失败 → 停下排查，不要继续。

- [ ] **Step 2: lint + format + typecheck 改动文件**

Run:
```bash
uvx ruff check tradingagents/agents/utils/toolkit_config.py tradingagents/agents/utils/agent_utils.py tests/test_toolkit_config_isolation.py
uvx ruff format --check tradingagents/agents/utils/toolkit_config.py tradingagents/agents/utils/agent_utils.py tests/test_toolkit_config_isolation.py
uvx pyright tradingagents/agents/utils/toolkit_config.py tradingagents/agents/utils/agent_utils.py tests/test_toolkit_config_isolation.py
```
Expected: ruff "All checks passed!" / format "already formatted" / pyright "0 errors, 0 warnings"。

- [ ] **Step 3: 改 CHANGELOG**

在 `docs/CHANGELOG.md` 的 `[Unreleased]` 段（若无 `### Fixed` 子段则新建）加一条：

```markdown
### Fixed

- **agents**: 修复 `Toolkit` config 跨请求串味（cross-request config bleed）—— 类级共享可变 dict 改为 `contextvars.ContextVar` 注入，并发分析的 config（如 `research_depth`）按执行上下文隔离。`_config` / `update_config` 保留兼容（见 `docs/specs/toolkit-config-isolation/`）。
```

（若 `[Unreleased]` 下已有 `### Fixed`，把上面那条 bullet 追加进去，不要重复建子标题。）

- [ ] **Step 4: 确认改动文件清单（精确 add，禁止 `git add -A`）**

Run: `git status --short`
Expected 仅这些：
```
 M docs/CHANGELOG.md
 M tradingagents/agents/utils/agent_utils.py
?? docs/specs/toolkit-config-isolation/
?? tests/test_toolkit_config_isolation.py
?? tradingagents/agents/utils/toolkit_config.py
```

- [ ] **Step 5: Commit（精确文件列表）**

```bash
git add tradingagents/agents/utils/toolkit_config.py \
        tradingagents/agents/utils/agent_utils.py \
        tests/test_toolkit_config_isolation.py \
        docs/CHANGELOG.md \
        docs/specs/toolkit-config-isolation/
git commit -m "fix(agents): Toolkit config 实例隔离 — ContextVar 注入消除跨请求串味"
```

pre-commit hook（ruff/format/pyright）会自动跑；全过才成功。若 hook 修改了文件（如 format），重新 `git add` 那些文件再 commit，**禁止 `--no-verify`**。

- [ ] **Step 6: Push（HARD-GATE，用户 1-click）**

**不要自动执行。** 向用户报告 commit 完成，请用户 1-click：`git push origin <当前分支>`。

---

## Self-Review（plan 对照 spec）

- **Spec 覆盖**：
  - helper（ContextVar set/get）→ Task 1 ✅
  - Toolkit `__init__` / `config` property / line 692 / `update_config` deprecated → Task 2 ✅
  - 5 个测试场景（隔离/兜底/不污染/property/692）→ Task 1（前 3）+ Task 2（后 2）✅
  - CHANGELOG `[Unreleased]` Fixed → Task 3 ✅
  - 不变量「写新 dict 不 mutate 共享」→ `test_set_does_not_mutate_default_config` 守护 ✅
- **Placeholder 扫描**：无 TBD/TODO；每个改代码的 step 都有完整代码块。
- **类型/命名一致性**：`set_toolkit_config` / `get_toolkit_config` 跨 Task 1/2/3 命名一致；helper 签名与 import 语句、调用点一致。
- **关键纠偏已纳入**：DEFAULT_CONFIG 无 `research_depth` 键 → 兜底测试改断 `online_tools`（已落实在 Task 1 测试代码）。
- **License 边界**：仅 `tradingagents/` + `tests/` + `docs/`，未触 `app/` / `frontend/` ✅。
