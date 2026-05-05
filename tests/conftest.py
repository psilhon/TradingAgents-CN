import os
import sys

import pytest

# 将项目根目录加入 sys.path，确保 `import tradingagents` 可用
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# OpenSpec change `pytest-marker-strict`:
# 给未显式标记 marker 的 test 自动加 `requires_env`（保守默认）。
# pre-commit hook 跑 `pytest -m unit` 只选 unit 标记，未标记的不跑——
# 防止盲目转严格让任何环境都 fail。
_KNOWN_MARKERS = {"unit", "integration", "requires_env", "requires_network"}


def pytest_collection_modifyitems(config, items):
    """给未显式标 marker 的 test 自动加 requires_env"""
    auto_mark = pytest.mark.requires_env
    for item in items:
        if not any(m.name in _KNOWN_MARKERS for m in item.iter_markers()):
            item.add_marker(auto_mark)
