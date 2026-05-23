"""FileBackend 单元测试 — sub-stage 4.1 cache-backend-protocol-and-filebackend.

`tradingagents.dataflows.cache.backends.file.FileBackend` 是文件 IO 薄层，
符合 `Backend` Protocol。本测试只验证 backend 自身契约，不依赖
`AdaptiveCacheSystem` 完整初始化路径。

参考 `tests/test_cache_serialize.py` 的 `spec_from_file_location` 模式
避免 `dataflows` 包 import 副作用（config_manager 连 MongoDB）。
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

pytestmark = pytest.mark.unit

_CACHE_DIR = Path(__file__).resolve().parents[1] / "tradingagents" / "dataflows" / "cache"
_SRZ_PATH = _CACHE_DIR / "_serialize.py"
_FILE_BACKEND_PATH = _CACHE_DIR / "backends" / "file.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# 先单独加载 _serialize.py（light-imports，无 DB 副作用），注入到 sys.modules；
# 然后加载 file.py（其内部 `from tradingagents.dataflows.cache._serialize
# import ...` 会命中 sys.modules 里的版本，跳过包级 __init__ 副作用）。
# _load_module 已在内部 `sys.modules[name] = mod`，丢掉返回值即可。
_load_module("tradingagents.dataflows.cache._serialize", _SRZ_PATH)
_file_backend_mod = _load_module("_file_backend_under_test", _FILE_BACKEND_PATH)
FileBackend = _file_backend_mod.FileBackend


# --- Protocol 契约（基础 round-trip） ---


def test_save_then_load_returns_equivalent_envelope(tmp_path: Path) -> None:
    backend = FileBackend(cache_dir=tmp_path)
    envelope = {
        "data": {"k": "v", "n": 42, "f": 3.14},
        "metadata": {"src": "test", "symbol": "AAPL"},
        "timestamp": datetime(2026, 5, 23, 12, 0, 0),
        "backend": "file",
    }
    assert backend.save("key_abc", envelope) is True
    out = backend.load("key_abc")
    assert out is not None
    assert out["data"] == envelope["data"]
    assert out["metadata"] == envelope["metadata"]
    assert out["timestamp"] == envelope["timestamp"]
    assert out["backend"] == envelope["backend"]


def test_load_missing_key_returns_none(tmp_path: Path) -> None:
    backend = FileBackend(cache_dir=tmp_path)
    assert backend.load("does_not_exist") is None


def test_load_missing_key_does_not_raise(tmp_path: Path) -> None:
    """load 不存在 key MUST 返回 None 而非 raise — 异常应在内部 catch."""
    backend = FileBackend(cache_dir=tmp_path)
    # 不应抛任何异常
    result = backend.load("nonexistent")
    assert result is None


# --- 文件路径 + 扩展名契约 ---


def test_save_writes_to_expected_path(tmp_path: Path) -> None:
    backend = FileBackend(cache_dir=tmp_path)
    envelope = {"data": "x", "metadata": {}, "timestamp": datetime(2026, 5, 23), "backend": "file"}
    assert backend.save("abc123", envelope) is True
    expected_path = tmp_path / "abc123.json.gz"
    assert expected_path.exists(), f"expected file at {expected_path}"


def test_init_creates_cache_dir_if_missing(tmp_path: Path) -> None:
    target = tmp_path / "newly_created" / "nested"
    assert not target.exists()
    FileBackend(cache_dir=target)
    assert target.exists() and target.is_dir()


# --- envelope 内嵌特殊类型（依赖 _serialize.py） ---


def test_save_load_with_dataframe_envelope(tmp_path: Path) -> None:
    backend = FileBackend(cache_dir=tmp_path)
    df = pd.DataFrame({"a": [1, 2, 3], "b": [1.1, 2.2, 3.3]})
    envelope = {
        "data": df,
        "metadata": {"rows": 3},
        "timestamp": datetime(2026, 5, 23, 9, 30, 0),
        "backend": "file",
    }
    assert backend.save("df_key", envelope) is True
    out = backend.load("df_key")
    assert out is not None
    pd.testing.assert_frame_equal(out["data"], df)
    assert out["timestamp"] == envelope["timestamp"]


def test_save_load_with_datetime_in_data(tmp_path: Path) -> None:
    backend = FileBackend(cache_dir=tmp_path)
    envelope = {
        "data": {"last_update": datetime(2026, 5, 23, 14, 0, 0)},
        "metadata": {},
        "timestamp": datetime(2026, 5, 23, 14, 0, 0),
        "backend": "file",
    }
    assert backend.save("dt_key", envelope) is True
    out = backend.load("dt_key")
    assert out is not None
    assert out["data"]["last_update"] == datetime(2026, 5, 23, 14, 0, 0)


# --- backends/ 目录依赖洁净度（spec scenario） ---


def test_file_module_does_not_import_pandas_or_pickle() -> None:
    """backends/file.py source MUST NOT contain `import pandas` / `import pickle`."""
    source = _FILE_BACKEND_PATH.read_text()
    assert "import pandas" not in source, "FileBackend MUST NOT import pandas (薄层职责)"
    assert "import pickle" not in source, "FileBackend MUST NOT import pickle (4.1 安全契约)"


def test_file_module_only_dataflow_import_is_serialize() -> None:
    """backends/file.py 内 `from tradingagents.dataflows` 仅允许指向 _serialize."""
    source = _FILE_BACKEND_PATH.read_text()
    lines = [line.strip() for line in source.splitlines() if "tradingagents.dataflows" in line]
    for line in lines:
        # 允许 `from tradingagents.dataflows.cache._serialize import ...`
        assert "_serialize" in line, f"非法 dataflow 依赖: {line}"


# --- Protocol 接口最小性 ---


def test_filebackend_satisfies_backend_protocol() -> None:
    """FileBackend MUST 实现 Backend Protocol 的 save / load 两方法."""
    backend = FileBackend(cache_dir=Path("/tmp"))
    assert callable(getattr(backend, "save", None))
    assert callable(getattr(backend, "load", None))
