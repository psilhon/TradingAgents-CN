"""file_cache 路径遍历加固测试。

`StockDataCache._generate_cache_key` 把 `symbol` 逐字拼进缓存文件名（见
`_get_cache_path`）。symbol 来自外部 / LLM 工具参数，形如 "../../etc/passwd"
的输入若不净化可越出缓存 base_dir（路径遍历）。修复对 symbol 做字符白名单。

注意：白名单保留 `.`（symbol 如 "600519.SH" 需要），故 ".." 字符串会留存——
但只要剥掉路径分隔符（正斜杠 / 反斜杠），".." 就只是普通文件名的一部分，无法跨目录。
真正的安全不变量是「解析后的缓存路径仍在 base_dir 内」，由下方测试钉死。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_CACHE_DIR = Path(__file__).resolve().parents[1] / "tradingagents" / "dataflows" / "cache"
_FILE_CACHE_SRC = _CACHE_DIR / "file_cache.py"


def _load_file_cache():
    spec = importlib.util.spec_from_file_location("file_cache_under_test_pathsafe", _FILE_CACHE_SRC)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["file_cache_under_test_pathsafe"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- 源码守护 ----


def test_generate_cache_key_sanitizes_symbol_source_guard() -> None:
    """修复必须在 symbol 进入文件名前做字符白名单，且不再回传裸 symbol。"""
    src = _FILE_CACHE_SRC.read_text()
    assert "re.sub(" in src, "symbol 字符白名单 (re.sub) 缺失"
    assert 'return f"{symbol}_{data_type}_{cache_key}"' not in src, "裸 symbol 仍嵌入 cache key — 路径遍历回归"


# ---------------------------------------------------------------- 行为 ----


@pytest.mark.parametrize(
    "evil",
    [
        "../../etc/passwd",
        "..\\..\\windows",
        "600519/../../x",
        "a/b/c",
    ],
)
def test_generate_cache_key_has_no_path_separators(tmp_path: Path, evil: str) -> None:
    mod = _load_file_cache()
    cache = mod.StockDataCache(cache_dir=str(tmp_path))
    key = cache._generate_cache_key("stock_data", evil)
    assert "/" not in key and "\\" not in key, f"cache key 含路径分隔符: {key!r}"


def test_cache_path_stays_within_base_dir(tmp_path: Path) -> None:
    """终极不变量：恶意 symbol 派生的缓存路径解析后仍在 base_dir 内。"""
    mod = _load_file_cache()
    cache = mod.StockDataCache(cache_dir=str(tmp_path))
    key = cache._generate_cache_key("stock_data", "../../../../../../tmp/evil")
    path = cache._get_cache_path("stock_data", key, "json", symbol="000001")
    resolved = path.resolve()
    assert resolved.is_relative_to(tmp_path.resolve()), f"缓存路径逃逸 base_dir: {resolved}"


def test_normal_symbol_preserved_in_cache_key(tmp_path: Path) -> None:
    """合法 symbol（字母/数字/点）原样保留，缓存键稳定不漂移。"""
    mod = _load_file_cache()
    cache = mod.StockDataCache(cache_dir=str(tmp_path))
    key = cache._generate_cache_key("stock_data", "600519.SH")
    assert key.startswith("600519.SH_stock_data_")
