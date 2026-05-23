"""RedisBackend 单元测试 — sub-stage 4.2 cache-redis-mongo-backends.

mock redis client，验证 Backend Protocol 行为 + TTL 路径分支。
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

pytestmark = pytest.mark.unit

_CACHE_DIR = Path(__file__).resolve().parents[1] / "tradingagents" / "dataflows" / "cache"
_SRZ_PATH = _CACHE_DIR / "_serialize.py"
_REDIS_BACKEND_PATH = _CACHE_DIR / "backends" / "redis.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# 先加载 _serialize.py（light-imports）注入 sys.modules，让 redis.py 的
# `from tradingagents.dataflows.cache._serialize import ...` 命中预加载版本，
# 跳过 cache/__init__ 副作用。
_load_module("tradingagents.dataflows.cache._serialize", _SRZ_PATH)
_redis_backend_mod = _load_module("_redis_backend_under_test", _REDIS_BACKEND_PATH)
RedisBackend = _redis_backend_mod.RedisBackend


# --- TTL 路径分支 ---


def test_save_with_ttl_calls_setex() -> None:
    client = MagicMock()
    backend = RedisBackend(redis_client=client)
    envelope = {"data": "v", "metadata": {}, "timestamp": datetime(2026, 5, 23), "backend": "redis"}
    assert backend.save("key1", envelope, ttl_seconds=3600) is True
    assert client.setex.called
    assert not client.set.called
    args, _ = client.setex.call_args
    assert args[0] == "key1"
    assert args[1] == 3600
    # 第三个参数是 encoded bytes
    assert isinstance(args[2], bytes)


def test_save_without_ttl_calls_set() -> None:
    client = MagicMock()
    backend = RedisBackend(redis_client=client)
    envelope = {"data": "v", "metadata": {}, "timestamp": datetime(2026, 5, 23), "backend": "redis"}
    assert backend.save("key2", envelope) is True  # ttl_seconds 默认 None
    assert client.set.called
    assert not client.setex.called


# --- 无客户端降级 ---


def test_save_with_none_client_returns_false() -> None:
    backend = RedisBackend(redis_client=None)
    envelope = {"data": "v", "metadata": {}, "timestamp": datetime(2026, 5, 23), "backend": "redis"}
    assert backend.save("k", envelope, ttl_seconds=60) is False


def test_load_with_none_client_returns_none() -> None:
    backend = RedisBackend(redis_client=None)
    assert backend.load("anything") is None


def test_none_client_does_not_raise() -> None:
    backend = RedisBackend(redis_client=None)
    backend.save("k", {"data": 1}, 100)  # 不应 raise
    backend.load("k")  # 不应 raise


# --- load 未命中 ---


def test_load_missing_key_returns_none() -> None:
    client = MagicMock()
    client.get.return_value = None
    backend = RedisBackend(redis_client=client)
    assert backend.load("missing") is None


def test_load_decode_failure_returns_none() -> None:
    client = MagicMock()
    client.get.return_value = b"\x00\x01\x02not_valid_envelope"
    backend = RedisBackend(redis_client=client)
    assert backend.load("corrupt") is None  # 解码失败 → cache miss


# --- envelope round-trip ---


def test_dataframe_envelope_roundtrip() -> None:
    client = MagicMock()
    df = pd.DataFrame({"a": [1, 2, 3], "b": [1.1, 2.2, 3.3]})
    envelope = {"data": df, "metadata": {"rows": 3}, "timestamp": datetime(2026, 5, 23, 9, 30), "backend": "redis"}
    backend = RedisBackend(redis_client=client)
    backend.save("df_key", envelope, ttl_seconds=600)
    encoded_bytes = client.setex.call_args[0][2]
    # 模拟 redis get 返回写入时的 bytes
    client.get.return_value = encoded_bytes
    out = backend.load("df_key")
    assert out is not None
    pd.testing.assert_frame_equal(out["data"], df)
    assert out["timestamp"] == envelope["timestamp"]


def test_datetime_envelope_roundtrip() -> None:
    client = MagicMock()
    envelope = {
        "data": {"last_update": datetime(2026, 5, 23, 14, 0, 0)},
        "metadata": {},
        "timestamp": datetime(2026, 5, 23, 14, 0, 0),
        "backend": "redis",
    }
    backend = RedisBackend(redis_client=client)
    backend.save("dt_key", envelope, ttl_seconds=300)
    encoded_bytes = client.setex.call_args[0][2]
    client.get.return_value = encoded_bytes
    out = backend.load("dt_key")
    assert out is not None
    assert out["data"]["last_update"] == datetime(2026, 5, 23, 14, 0, 0)


# --- 源码洁净度（spec scenario） ---


def test_redis_module_does_not_import_pandas_or_pickle() -> None:
    source = _REDIS_BACKEND_PATH.read_text()
    assert "import pandas" not in source, "RedisBackend MUST NOT import pandas (薄层职责)"
    assert "import pickle" not in source, "RedisBackend MUST NOT import pickle (4.1 安全契约)"


# --- Protocol 接口最小性（含 4.2 ttl_seconds） ---


def test_redis_backend_has_save_load_methods() -> None:
    client = MagicMock()
    backend = RedisBackend(redis_client=client)
    assert callable(getattr(backend, "save", None))
    assert callable(getattr(backend, "load", None))


def test_save_signature_accepts_ttl_seconds_kwarg() -> None:
    """Backend Protocol 4.2 扩展：save 接受 ttl_seconds 关键字参数."""
    client = MagicMock()
    backend = RedisBackend(redis_client=client)
    envelope = {"data": 1, "metadata": {}, "timestamp": datetime(2026, 5, 23), "backend": "redis"}
    # 不应 raise TypeError
    backend.save("k", envelope, ttl_seconds=42)
    backend.save("k", envelope)  # ttl_seconds 是可选


# --- 4.8 E4: close() 生命周期 ---


def test_close_calls_client_close() -> None:
    """`close()` MUST 调 redis_client.close() 释放连接池."""
    client = MagicMock()
    backend = RedisBackend(redis_client=client)
    backend.close()
    assert client.close.called, "close() MUST 调 client.close()"
    assert client.close.call_count == 1


def test_close_with_none_client_no_raise() -> None:
    """`close()` 在 client=None 时 MUST no-op，不 raise."""
    backend = RedisBackend(redis_client=None)
    # 不应抛任何异常
    backend.close()


def test_close_swallows_client_close_failure() -> None:
    """单个 backend close 失败 MUST NOT raise（让 Cache.close 关闭流程能继续）."""
    client = MagicMock()
    client.close.side_effect = RuntimeError("network down")
    backend = RedisBackend(redis_client=client)
    # 不应 raise
    backend.close()
    assert client.close.called
