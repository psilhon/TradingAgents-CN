# 4.8 — Design refinements tasks

按 TDD red/green pattern + 每 refinement 一个 commit 实施。

## E1 — FileBackend 原子写入

- [ ] **spec delta**：`docs/specs/dataflow-caching/spec.md` 加 Requirement "FileBackend 原子写入" + 修订 "FileBackend 单一职责" 注明 4.8 起 save 用 temp + os.replace
- [ ] **red**：`tests/test_file_backend.py` 加 3 个测试
  - `test_save_atomic_no_tmp_leakage`：mock `os.replace` raise，验证 `cache_dir` 内只有 cleanup 后无 `.tmp` 残留
  - `test_save_atomic_no_partial_final`：mock `f.write` 写到一半 raise，验证 final `.json.gz` 不存在（不被部分写入污染）
  - `test_save_atomic_replace_called`：mock `os.replace` 验证被调用一次，源路径含 `.tmp.{pid}` 后缀
- [ ] **green**：`tradingagents/dataflows/cache/backends/file.py` 改 `save` 实现：
  - 写入 `{cache_dir}/.{key}.json.gz.tmp.{pid}` （前导 `.` 让临时文件被 glob 忽略；pid 让多进程并行写不同 key 不互冲）
  - 写完成功 → `os.replace(tmp, final)`
  - 写中途异常 → try/finally 内 unlink 临时文件
  - 现有 `cache_dir.mkdir(parents=True, exist_ok=True)` 保留
- [ ] 跑 `tests/test_file_backend.py` 全绿
- [ ] commit："feat(cache): E1 — FileBackend 原子写入（temp + os.replace）"

## E2 — TA_CACHE_DIR env 覆盖

- [ ] **spec delta**：加 Requirement "缓存目录可由 env 覆盖"，含 default + expanduser 行为
- [ ] **red**：`tests/test_get_cache.py` 加 2 个测试（新文件或已有 test_init）
  - `test_get_cache_uses_env_cache_dir`：monkeypatch `TA_CACHE_DIR=/tmp/xxx`，重置 cache 实例，调 `get_cache()`，断 `cache.file_backend.cache_dir == Path("/tmp/xxx")`
  - `test_get_cache_env_cache_dir_expanduser`：monkeypatch `TA_CACHE_DIR=~/.cache/x`，断路径已 expand `~`
- [ ] **green**：`tradingagents/dataflows/cache/__init__.py` 的 `get_cache()` 读 env：
  ```python
  import os
  cache_dir = Path(os.getenv("TA_CACHE_DIR", "data/cache")).expanduser()
  ```
- [ ] 跑 `tests/test_get_cache.py` 全绿
- [ ] commit："feat(cache): E2 — TA_CACHE_DIR env 覆盖缓存目录"

## E3 — Typed dispatch dedup（_save_typed / _load_typed / _find_typed）

- [ ] **spec delta**：修订 Cache 类 Requirement 注 4.8 内部抽 helper，公开 API 行为 + cache_key 派生字节级保持
- [ ] **red**：`tests/test_cache_class.py` 加 1 个测试 + 字节级 cache_key 测试已存在
  - `test_save_methods_call_save_typed`：spy `Cache._save_typed`，调 `save_stock_data` + `save_fundamentals_data` 各一次，断 `_save_typed.call_count == 2`，断 call_args 含 data_type 和 id_fields
  - 已有的 byte-compat 测试（4.7 已加）保持不破
- [ ] **green**：`tradingagents/dataflows/cache/_cache.py` 加 3 个私有 helper，6 个公开方法改 thin
  - `_save_typed(symbol, data, data_type, id_fields: dict[str, str]) -> str`
  - `_load_typed(cache_key) -> Any | None`：与 load_stock_data 现行实现等价（_load_routed + _envelope_is_fresh）
  - `_find_typed(symbol, data_type, id_fields, max_age_hours=None) -> str | None`
  - 公开方法各 1 行调用 helper（normalize None → defaults 仍保留在公开方法）
- [ ] 跑 `pytest tests/test_cache_class.py tests/test_cache_p0_hotfix.py tests/test_cache_callsite_compatibility.py` 全绿
- [ ] commit："refactor(cache): E3 — typed dispatch dedup（_save_typed / _load_typed / _find_typed）"

## E4 — Cache.close() + Backend.close()

- [ ] **spec delta**：加 close 到 Backend Protocol + Cache 公开 API；context manager 协议
- [ ] **red**：`tests/test_cache_class.py` + `tests/test_redis_backend.py` + `tests/test_mongo_backend.py` 加 close 测试
  - `test_cache_close_dispatches`：Cache.close() 调三个 backend 的 close
  - `test_cache_close_swallows_backend_error`：mock redis_backend.close raise，断 Cache.close 不 raise（也调 mongo + file close）
  - `test_cache_context_manager`：`with Cache(...) as c: ...` 出 with 块后 backend close 被调
  - `test_redis_backend_close_calls_client_close`
  - `test_mongo_backend_close_calls_client_close`
  - `test_file_backend_close_no_op`
- [ ] **green**：
  - `_protocol.py`：加 `def close(self) -> None: ...` 文档化为可选（调用方 duck-type 检测）
  - `file.py`：`close()` no-op
  - `redis.py`：`close()` → `if self._client: self._client.close()`，异常吞
  - `mongo.py`：`close()` → 同
  - `_cache.py`：加 `close()` 委派 3 个 backend，单条 logger.exception 不 raise；加 `__enter__` / `__exit__`
- [ ] 跑 `just ci`
- [ ] **CHANGELOG**：`docs/CHANGELOG.md` 加 4.8 entry
- [ ] commit："feat(cache): E4 — Cache.close() 生命周期 + Backend close + context manager"
- [ ] **collapse-friendly final**：若 just ci 还有红的，回 P3 思路（修红 → 增量 commit）

## 验证

- [ ] `just ci` 413+ 测试通过
- [ ] `grep -r "os.replace" tradingagents/dataflows/cache/` 命中只有 file.py
- [ ] `grep -rn "TA_CACHE_DIR" tradingagents/` 命中只有 __init__.py
- [ ] `grep -rn "def close" tradingagents/dataflows/cache/` 命中 4 个（file/redis/mongo backend + Cache）

## 不在 4.8 范围

- TypedDict / Pydantic envelope（stage 5）
- news_data 公开方法（待实际消费方）
- async cache API
- prometheus metrics

## Push

push 到 origin/main 由用户 1 click 触发（强 HARD-GATE）。本 sub-stage 仅本地 commit。
