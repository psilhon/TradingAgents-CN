# Tasks — cache-layer-cleanup-stage1

> `cache-layer-consolidation` stage 1：删 `db_cache.py` 死代码 + 抽公共 helper。
> 立项在本会话完成；Phase 2 实施换新会话（`/opsx:apply`）。

## 1. 立项 — commit 1

- [x] 1.1 写 `proposal.md`
- [x] 1.2 写 `tasks.md`
- [x] 1.3 写 `specs/dataflow-caching/spec.md`（新 capability，ADDED Requirements）
- [x] 1.4 commit（仅 OpenSpec 文件）

## 2. Part A — 删除 db_cache.py 死代码 — commit 2

- [ ] 2.1 **前置复核**：重新 grep 全仓 `DatabaseCacheManager` / `get_db_cache` / `db_cache`（含 `app/` `tests/` `cli/` `scripts/`），确认仍零外部消费者；查 `importlib` / `__import__` / 字符串动态导入
- [ ] 2.2 删除 `tradingagents/dataflows/cache/db_cache.py` 整文件
- [ ] 2.3 `cache/__init__.py`：删 `from .db_cache import DatabaseCacheManager` try-import 块（含 `except` 的 `DatabaseCacheManager = None`）+ `__all__` 的 `"DatabaseCacheManager"`
- [ ] 2.4 `just lint` + `just typecheck` 0 errors（确认无残留引用 / 未用 import）
- [ ] 2.5 `pytest -m unit` 无回归
- [ ] 2.6 commit

## 3. Part B — 抽公共 helper — commit 3

- [ ] 3.1 详读 `file_cache.py` 与 `adaptive.py` 的 cache-key 生成 + TTL 解析；判定 key scheme 是否兼容
- [ ] 3.2 **决策点**：
  - key scheme 兼容 → 抽统一 `make_cache_key()` + TTL helper 到 `cache/_common.py`
  - 不兼容 → Part B 缩为仅抽 TTL helper；在本 tasks 记录决策与理由
- [ ] 3.3 **RED**：写 `tests/test_cache_common.py`（`@pytest.mark.unit`）——对代表性输入断言 helper 产出的 cache-key 与原实现逐字节一致（迁移前先抓 golden 值）
- [ ] 3.4 **GREEN**：新建 `cache/_common.py`，`file_cache.py` / `adaptive.py` 改用 helper，删 inline 实现
- [ ] 3.5 `pytest tests/test_cache_common.py` PASS（byte-identical 护栏）
- [ ] 3.6 `just lint` + `just typecheck` 0 errors
- [ ] 3.7 `pytest -m unit` 无回归
- [ ] 3.8 commit

## 4. CHANGELOG + 验证 + Archive — commit 4

- [ ] 4.1 `docs/CHANGELOG.md` `[Unreleased]` 加 `### Changed`（+ 必要时 `### Removed`）段
- [ ] 4.2 `just ci` 通过（lint + typecheck + test）
- [ ] 4.3 Archive：change 目录 → `openspec/changes/archive/2026-05-22-cache-layer-cleanup-stage1`
- [ ] 4.4 Spec sync：稳定 spec 写入 `openspec/specs/dataflow-caching/spec.md`（新 capability）
- [ ] 4.5 commit archive + spec sync
- [ ] 4.6 finishing report；push / tag 决策交用户
