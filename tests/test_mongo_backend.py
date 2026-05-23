"""MongoBackend 单元测试 — sub-stage 4.2 cache-redis-mongo-backends.

mock mongo client + collection，验证 envelope ↔ doc schema 转换 + 过期 doc
删除 + legacy pickle 降级（MUST NOT 调 pickle.loads）。
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

pytestmark = pytest.mark.unit

_CACHE_DIR = Path(__file__).resolve().parents[1] / "tradingagents" / "dataflows" / "cache"
_SRZ_PATH = _CACHE_DIR / "_serialize.py"
_MONGO_BACKEND_PATH = _CACHE_DIR / "backends" / "mongo.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_load_module("tradingagents.dataflows.cache._serialize", _SRZ_PATH)
_mongo_backend_mod = _load_module("_mongo_backend_under_test", _MONGO_BACKEND_PATH)
MongoBackend = _mongo_backend_mod.MongoBackend


def _mock_client_collection() -> tuple[MagicMock, MagicMock]:
    """返回 (mock_client, mock_collection) — client[<db>][<collection>] 与 client.<db>.<collection> 都指到同一 mock_collection."""
    client = MagicMock()
    collection = MagicMock()
    # 同时 wire attribute + __getitem__ chain（pymongo 两种 API 都返回同一 Collection 对象）
    client.tradingagents.cache = collection
    client.__getitem__.return_value.__getitem__.return_value = collection
    return client, collection


# --- save schema 转换 ---


def test_save_dataframe_envelope_sets_data_type_dataframe() -> None:
    client, collection = _mock_client_collection()
    backend = MongoBackend(mongodb_client=client)
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    envelope = {"data": df, "metadata": {"rows": 2}, "timestamp": datetime(2026, 5, 23), "backend": "mongodb"}
    assert backend.save("k_df", envelope, ttl_seconds=3600) is True
    assert collection.replace_one.called
    args, kwargs = collection.replace_one.call_args
    filter_arg, doc_arg = args[0], args[1]
    assert filter_arg == {"_id": "k_df"}
    assert doc_arg["_id"] == "k_df"
    assert doc_arg["data_type"] == "dataframe"
    assert doc_arg["backend"] == "mongodb"
    assert kwargs.get("upsert") is True


def test_save_plain_dict_envelope_sets_data_type_json() -> None:
    client, collection = _mock_client_collection()
    backend = MongoBackend(mongodb_client=client)
    envelope = {"data": {"k": "v", "n": 42}, "metadata": {}, "timestamp": datetime(2026, 5, 23), "backend": "mongodb"}
    assert backend.save("k_json", envelope, ttl_seconds=600) is True
    doc_arg = collection.replace_one.call_args[0][1]
    assert doc_arg["data_type"] == "json"


def test_save_with_ttl_sets_expires_at() -> None:
    client, collection = _mock_client_collection()
    backend = MongoBackend(mongodb_client=client)
    envelope = {"data": "x", "metadata": {}, "timestamp": datetime(2026, 5, 23), "backend": "mongodb"}
    before = datetime.now()
    backend.save("k_ttl", envelope, ttl_seconds=3600)
    after = datetime.now()
    doc_arg = collection.replace_one.call_args[0][1]
    expires = doc_arg["expires_at"]
    assert isinstance(expires, datetime)
    assert before + timedelta(seconds=3600 - 2) <= expires <= after + timedelta(seconds=3600 + 2)


def test_save_without_ttl_omits_expires_at() -> None:
    client, collection = _mock_client_collection()
    backend = MongoBackend(mongodb_client=client)
    envelope = {"data": "x", "metadata": {}, "timestamp": datetime(2026, 5, 23), "backend": "mongodb"}
    backend.save("k_no_ttl", envelope)
    doc_arg = collection.replace_one.call_args[0][1]
    assert doc_arg.get("expires_at") is None or "expires_at" not in doc_arg


# --- load schema 重建 ---


def test_load_json_doc_rebuilds_envelope() -> None:
    client, collection = _mock_client_collection()
    backend = MongoBackend(mongodb_client=client)
    collection.find_one.return_value = {
        "_id": "k",
        "data": '{"k": "v", "n": 42}',
        "data_type": "json",
        "metadata": {"src": "test"},
        "timestamp": datetime(2026, 5, 23),
        "expires_at": datetime(2099, 1, 1),  # 远未过期
        "backend": "mongodb",
    }
    out = backend.load("k")
    assert out is not None
    assert out["data"] == {"k": "v", "n": 42}
    assert out["metadata"] == {"src": "test"}
    assert out["timestamp"] == datetime(2026, 5, 23)
    assert out["backend"] == "mongodb"


def test_load_dataframe_doc_rebuilds_envelope() -> None:
    client, collection = _mock_client_collection()
    backend = MongoBackend(mongodb_client=client)
    df = pd.DataFrame({"a": [1, 2, 3], "b": [1.1, 2.2, 3.3]})
    collection.find_one.return_value = {
        "_id": "k",
        "data": df.to_json(orient="split"),
        "data_type": "dataframe",
        "metadata": {},
        "timestamp": datetime(2026, 5, 23),
        "expires_at": datetime(2099, 1, 1),
        "backend": "mongodb",
    }
    out = backend.load("k")
    assert out is not None
    pd.testing.assert_frame_equal(out["data"], df)


def test_load_missing_doc_returns_none() -> None:
    client, collection = _mock_client_collection()
    backend = MongoBackend(mongodb_client=client)
    collection.find_one.return_value = None
    assert backend.load("missing") is None


# --- 过期 doc 处理 ---


def test_load_expired_doc_deletes_and_returns_none() -> None:
    client, collection = _mock_client_collection()
    backend = MongoBackend(mongodb_client=client)
    collection.find_one.return_value = {
        "_id": "k_exp",
        "data": "{}",
        "data_type": "json",
        "metadata": {},
        "timestamp": datetime(2026, 5, 22),
        "expires_at": datetime(2026, 5, 22, 10, 0, 0),  # 已过期
        "backend": "mongodb",
    }
    result = backend.load("k_exp")
    assert result is None
    assert collection.delete_one.called
    delete_filter = collection.delete_one.call_args[0][0]
    assert delete_filter == {"_id": "k_exp"}


# --- legacy pickle 降级（CRITICAL：MUST NOT 调 pickle.loads） ---


def test_load_legacy_pickle_doc_deletes_and_returns_none_without_unpickle() -> None:
    client, collection = _mock_client_collection()
    backend = MongoBackend(mongodb_client=client)
    collection.find_one.return_value = {
        "_id": "k_pickle",
        "data": b"\x80\x04\x95\x06\x00\x00\x00\x00\x00\x00\x00fake_pickle_bytes",  # 任意 pickle bytes，MUST NOT 被 unpickle
        "data_type": "pickle",
        "metadata": {},
        "timestamp": datetime(2026, 5, 1),
        "expires_at": datetime(2099, 1, 1),  # 未过期，纯靠 data_type 触发降级
        "backend": "mongodb",
    }
    with patch("pickle.loads") as mock_loads, patch("pickle.load") as mock_load:
        result = backend.load("k_pickle")
    assert result is None
    assert not mock_loads.called, "MUST NOT call pickle.loads on legacy doc"
    assert not mock_load.called, "MUST NOT call pickle.load on legacy doc"
    assert collection.delete_one.called
    assert collection.delete_one.call_args[0][0] == {"_id": "k_pickle"}


# --- 无客户端降级 ---


def test_none_client_save_returns_false() -> None:
    backend = MongoBackend(mongodb_client=None)
    envelope = {"data": 1, "metadata": {}, "timestamp": datetime(2026, 5, 23), "backend": "mongodb"}
    assert backend.save("k", envelope, ttl_seconds=600) is False


def test_none_client_load_returns_none() -> None:
    backend = MongoBackend(mongodb_client=None)
    assert backend.load("k") is None


def test_none_client_does_not_raise() -> None:
    backend = MongoBackend(mongodb_client=None)
    backend.save("k", {"data": 1, "metadata": {}, "timestamp": datetime(2026, 5, 23), "backend": "mongodb"})
    backend.load("k")


# --- 源码洁净度（spec scenario） ---


def test_mongo_module_does_not_import_pickle() -> None:
    source = _MONGO_BACKEND_PATH.read_text()
    assert "import pickle" not in source, "MongoBackend MUST NOT import pickle (legacy 降级用字符串比较)"


def test_mongo_module_imports_pandas() -> None:
    """MongoBackend 允许 import pandas（doc schema 转换要求）."""
    source = _MONGO_BACKEND_PATH.read_text()
    assert "import pandas" in source or "from pandas" in source, "MongoBackend 必须 import pandas（DataFrame schema 转换）"


# --- Protocol 接口（含 4.2 ttl_seconds） ---


def test_mongo_backend_has_save_load_methods() -> None:
    backend = MongoBackend(mongodb_client=None)
    assert callable(getattr(backend, "save", None))
    assert callable(getattr(backend, "load", None))


def test_save_signature_accepts_ttl_seconds_kwarg() -> None:
    client, _ = _mock_client_collection()
    backend = MongoBackend(mongodb_client=client)
    envelope = {"data": 1, "metadata": {}, "timestamp": datetime(2026, 5, 23), "backend": "mongodb"}
    backend.save("k", envelope, ttl_seconds=42)
    backend.save("k", envelope)  # 可选
