# Tasks — cache-pickle-replacement

> `cache-layer-consolidation` stage 2。replace pickle with JSON+gzip in `adaptive.py`。

## 1. 立项 — commit 1

- [x] 1.1 写 `proposal.md`
- [x] 1.2 写 `tasks.md`
- [x] 1.3 写 `specs/dataflow-caching/spec.md`（ADDED Requirements，扩 capability）
- [x] 1.4 commit（`c943f543`）

## 2. Serializer helper + TDD — commit 2

- [x] 2.1 **RED**：写 `tests/test_cache_serialize.py`（5 用例，spec_from_file_location 隔离加载保持纯 unit）
- [x] 2.2 **GREEN**：新建 `tradingagents/dataflows/cache/_serialize.py`
- [x] 2.3 `pytest tests/test_cache_serialize.py` PASS（5 passed, 0.27s）
- [x] 2.4 commit（`8951ac78`）

## 3. 替换 adaptive.py 的 7 处 pickle — commit 3

- [x] 3.1 文件后端：`_save_to_file` / `_load_from_file` 用 `encode_envelope` / `decode_envelope`；扩展 `.pkl` → `.json.gz`
- [x] 3.2 Redis 后端：`_save_to_redis` / `_load_from_redis` 同上（timestamp 不再先转 isoformat，envelope 内 datetime 由 helper 标签化）
- [x] 3.3 MongoDB 后端：save 非 DF 分支 → `data_type="json"` + `json.dumps(default=str)`；load 加 `json` 分支 + legacy `pickle` 删 doc 不 unpickle
- [x] 3.4 `clear_expired_cache`：新格式 `*.json.gz` 过期检查 + 老 `*.pkl` `unlink()` legacy sweep（不反序列化）
- [x] 3.5 删 `import pickle`
- [x] 3.6 grep 验证：`tradingagents/dataflows/cache/` 内真实 `pickle` 调用 = 0（仅注释 / 日志字符串提及）
- [x] 3.7 `just lint` + `just typecheck` 0 errors
- [x] 3.8 `pytest -m unit` 无回归（284 passed = 279 + 5 新增）
- [ ] 3.9 commit

## 4. CHANGELOG + 验证 + Archive — commit 4

- [ ] 4.1 `docs/CHANGELOG.md` `[Unreleased]` 加 `### Security` 段
- [ ] 4.2 `just ci` 通过
- [ ] 4.3 Archive：change 目录 → `openspec/changes/archive/`
- [ ] 4.4 Spec sync：把新 Requirement append 到 `openspec/specs/dataflow-caching/spec.md`
- [ ] 4.5 commit archive + spec sync
- [ ] 4.6 finishing report
