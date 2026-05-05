## 1. lazy singleton 重构 — commit 1

- [x] 1.1 `config_manager.py:744-745` 删 module-level 实例化 + 加 `_*_instance` 缓存 + PEP 562 `__getattr__` resolver
- [x] 1.2 `tradingagents/config/__init__.py` 改 lazy re-export
- [x] 1.3 smoke test: `from tradingagents.utils.api_key_utils import ...` **无** mongodb 连接日志（已通过）
- [x] 1.4 smoke test: `from tradingagents.config.config_manager import config_manager` 首次访问触发初始化 + `type=ConfigManager`（已通过）
- [x] 1.5 ruff + pyright 0 errors
- [x] 1.6 pytest -m unit 仍 12 pass
- [x] 1.7 commit

## 2. 收口

- [x] 2.1 docs/CHANGELOG.md `### Fixed` 条目
- [x] 2.2 archive
