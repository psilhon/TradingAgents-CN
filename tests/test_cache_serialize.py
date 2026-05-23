"""cache._serialize 单元测试 — OpenSpec change cache-pickle-replacement.

`import tradingagents.dataflows.cache` 会触发 `dataflows` 包 import →
`config_manager` 连 MongoDB。本 helper 是纯函数模块，用
`spec_from_file_location` 单独加载保持纯 unit（无外部依赖）。
"""

import importlib.util
import pickle
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

pytestmark = pytest.mark.unit

_SRZ_PATH = Path(__file__).resolve().parents[1] / "tradingagents" / "dataflows" / "cache" / "_serialize.py"
_spec = importlib.util.spec_from_file_location("_cache_serialize_under_test", _SRZ_PATH)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
encode_envelope = _mod.encode_envelope
decode_envelope = _mod.decode_envelope


def test_dict_roundtrip():
    env = {
        "data": {"k": "v", "n": 42, "f": 3.14},
        "metadata": {"src": "test", "symbol": "AAPL"},
        "timestamp": datetime(2026, 5, 22, 12, 0, 0),
        "backend": "file",
    }
    out = decode_envelope(encode_envelope(env))
    assert out["data"] == {"k": "v", "n": 42, "f": 3.14}
    assert out["metadata"] == {"src": "test", "symbol": "AAPL"}
    assert out["timestamp"] == datetime(2026, 5, 22, 12, 0, 0)
    assert out["backend"] == "file"


def test_dataframe_roundtrip():
    df = pd.DataFrame({"a": [1, 2, 3], "b": [1.1, 2.2, 3.3]})
    env = {"data": df, "metadata": {}, "timestamp": datetime(2026, 5, 22), "backend": "redis"}
    out = decode_envelope(encode_envelope(env))
    pd.testing.assert_frame_equal(out["data"], df)
    assert out["timestamp"] == datetime(2026, 5, 22)
    assert out["backend"] == "redis"


def test_nested_datetime_in_data():
    env = {
        "data": [1, "two", {"nested_dt": datetime(2026, 1, 1, 9, 30)}],
        "metadata": {},
        "timestamp": datetime(2026, 5, 22),
        "backend": "file",
    }
    out = decode_envelope(encode_envelope(env))
    assert out["data"][0] == 1
    assert out["data"][1] == "two"
    assert out["data"][2]["nested_dt"] == datetime(2026, 1, 1, 9, 30)


def test_legacy_pickle_bytes_rejected_without_unpickle():
    """老 pickle bytes 输入 decode → 失败（不调 pickle.loads）。"""
    pickle_bytes = pickle.dumps({"hostile": "payload"})
    with pytest.raises(Exception):
        decode_envelope(pickle_bytes)


def test_none_data():
    env = {"data": None, "metadata": {}, "timestamp": datetime(2026, 5, 22), "backend": "file"}
    out = decode_envelope(encode_envelope(env))
    assert out["data"] is None
