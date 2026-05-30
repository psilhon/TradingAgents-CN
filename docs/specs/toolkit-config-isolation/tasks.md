# toolkit-config-isolation Tasks

单 change，TDD red/green。单次 commit + 用户 1-click push。

## Task 1 — ContextVar helper + 隔离测试（red → green）

- [ ] **red**：`tests/test_toolkit_config_isolation.py`（`pytestmark = unit`）
  - 隔离核心：两线程各 `set_toolkit_config({"research_depth": "A"/"B"})` 后 `get_toolkit_config()` 互不串味
  - 默认兜底：未 set 时返回含 `DEFAULT_CONFIG` 键的 dict
  - 不污染默认：`set_toolkit_config({...})` 后 `DEFAULT_CONFIG` 原值不变
  - 先跑 → 因 helper 未建而 fail（ImportError）
- [ ] **green**：新建 `tradingagents/agents/utils/toolkit_config.py`
  - `_current_config: ContextVar[dict | None] = ContextVar("toolkit_config", default=None)`
  - `set_toolkit_config(config)`：`_current_config.set({**DEFAULT_CONFIG, **config})`
  - `get_toolkit_config()`：ContextVar 有值返回之；否则 `dict(DEFAULT_CONFIG)`
  - 全类型注解（pyright STRICT）
- [ ] 跑 `pytest tests/test_toolkit_config_isolation.py` 全绿

## Task 2 — 接入 Toolkit（green）

- [ ] **改** `tradingagents/agents/utils/agent_utils.py`：
  - `__init__`：`if config: set_toolkit_config(config)`
  - `config` property：`return get_toolkit_config()`
  - `update_config` classmethod：docstring 标 deprecated + 内部转调 `set_toolkit_config`（保留 `cls._config.update` 行为给兜底场景或直接删 body 改调 helper —— 实现时定，以不破坏调用方为准）
  - line 692：`get_toolkit_config().get("research_depth", "标准")`
  - 保留 `_config` 类属性（默认兜底来源）
- [ ] **补测试**：property 一致性（`Toolkit(cfg).config` 行为）+ line 692 路径（`set_toolkit_config({"research_depth": 4})` → 读到 4）
- [ ] **import-smoke**：`python -c "import tradingagents.agents.utils.agent_utils; print('OK')"`

## Task 3 — 验证闭环 + 收尾

- [ ] `pytest -m unit` 全套绿（确认未破坏既有用例）
- [ ] `uvx ruff check` + `ruff format --check` + `uvx pyright`（改动文件 0 error）
- [ ] **CHANGELOG**：`docs/CHANGELOG.md` `[Unreleased]` → Fixed 加条目（Toolkit config 跨请求串味修复 + ContextVar 隔离）
- [ ] **commit**：`fix(agents): Toolkit config 实例隔离 — ContextVar 注入消除跨请求串味`
- [ ] **push**：用户 1-click `git push origin main`

## 验证目标（可验证化）

- 「隔离生效」= 两线程并发 set 不同 config，各自 `get_toolkit_config()` 返回各自值（测试 1，旧代码必挂、新代码必过）
- 「不破坏现有」= `pytest -m unit` 全绿 + pyright/ruff 0 error
- 「向后兼容」= `fundamentals_analyst.py:84` 的 `toolkit.config['online_tools']` 仍可读（property 返回含该键 dict）

## 不在范围

详见 proposal.md 「Out of Scope」段。
