# Tasks — cache-backend-protocol-and-filebackend (sub-stage 4.1)

> epic：`cache-layer-consolidation` stage 4（archived `2026-05-22-cache-backend-unification`）
> 体量：~1 天 / 风险：低
> 公开 API 行为零变更；TDD red-green。

## 1. spec delta — commit 1（先于代码）

- [ ] 1.1 在 `docs/specs/dataflow-caching/spec.md` 追加 Requirement「Backend Protocol 接口」：定义 `save(key, envelope) -> bool` / `load(key) -> dict | None` 最小契约（MUST not 内嵌路由 / fallback）
- [ ] 1.2 追加 Requirement「FileBackend 单一职责」：MUST 仅负责文件 IO（路径生成 + envelope 字节读写），MUST NOT 涉及 TTL 判定 / 缓存策略 / 后端路由——这些由 `AdaptiveCacheSystem`（4.4 后由 `Cache`）负责
- [ ] 1.3 加 Scenario：`FileBackend.save` + `load` round-trip MUST 保持 envelope dict 等价（含 `data` / `metadata` / `timestamp` / `backend` 字段）
- [ ] 1.4 加 Scenario：`backends/` 目录下任何 backend 实现 MUST NOT import `pandas` / `pickle` / 业务逻辑模块——backend 是字节进字节出的薄层
- [ ] 1.5 commit `docs(spec): cache-backend-unification 4.1 — Backend Protocol + FileBackend 契约`

## 2. red — commit 2（先测试）

- [ ] 2.1 新建 `tests/dataflows/cache/test_file_backend.py`
- [ ] 2.2 测试：`FileBackend(cache_dir=tmp).save(key, envelope)` + `.load(key)` round-trip dict 相等（pytest tmp_path fixture）
- [ ] 2.3 测试：load 不存在的 key 返回 `None`（无 raise）
- [ ] 2.4 测试：save 写入文件路径 == `{cache_dir}/{key}.json.gz`（断言扩展名 + 父目录）
- [ ] 2.5 测试：envelope 含 `pandas.DataFrame` 通过 `_serialize.py` 经 round-trip 后 shape / columns / 数值保持（复用 stage 2 测试约定）
- [ ] 2.6 测试：envelope 含 `datetime` 字段经 round-trip 后类型 / 值保持
- [ ] 2.7 跑 `just test`（pytest -m unit）：新测试 MUST 全部 FAIL（红——`FileBackend` 尚未实现）
- [ ] 2.8 commit `test(cache): FileBackend round-trip + 单元契约（red）`

## 3. green — commit 3（实现 + 包装层接入）

- [ ] 3.1 新建 `tradingagents/dataflows/cache/backends/__init__.py`（空 + `from .file import FileBackend` re-export）
- [ ] 3.2 新建 `tradingagents/dataflows/cache/backends/_protocol.py`：`Backend` Protocol（typing.Protocol，`save` + `load` 两方法），不 import 任何 backend 实现
- [ ] 3.3 新建 `tradingagents/dataflows/cache/backends/file.py`：`FileBackend` 类，`__init__(cache_dir: Path)` + `save(key, envelope) -> bool` + `load(key) -> dict | None`。逻辑从 `adaptive.py` 的 `_save_to_file` / `_load_from_file` 整体迁移，**仅保留 IO + 错误日志**，不保留 envelope 构建逻辑
- [ ] 3.4 修改 `adaptive.py` `AdaptiveCacheSystem.__init__`：加 `from .backends import FileBackend` + `self.file_backend = FileBackend(cache_dir=self.cache_dir)`
- [ ] 3.5 修改 `adaptive.py` `_save_to_file`：保留 envelope 构建逻辑（含 `timestamp` / `backend` 字段），调用 `self.file_backend.save(cache_key, cache_data)` 完成 IO
- [ ] 3.6 修改 `adaptive.py` `_load_from_file`：改为单行 `return self.file_backend.load(cache_key)`
- [ ] 3.7 跑 `just test`（pytest -m unit）：新测试 + 老测试 MUST 全绿
- [ ] 3.8 跑 `just lint` + `just typecheck`：MUST 全绿
- [ ] 3.9 跑 `just audit-binds` / `just audit-ports`：MUST 全绿（无新增 hardcode）
- [ ] 3.10 commit `feat(cache): Backend Protocol + FileBackend 单一职责（green）`

## 4. 行为兼容验证（push 前）

- [ ] 4.1 起 backend（`just up`）+ 跑 CLI 演示（`.venv/bin/python main.py`）的 cache hit / miss 路径——envelope 文件名 + 内容与切换前等价
- [ ] 4.2 检查 `data/cache/` 现有 `.json.gz` 文件能被切换后版本正常 load（向后兼容）
- [ ] 4.3 `just ci` 完整流水线绿灯
- [ ] 4.4 `just down`

## 5. 收尾

- [ ] 5.1 更新 `docs/CHANGELOG.md` `[Unreleased]` 段加条目
- [ ] 5.2 push `feat/cache-backend-protocol-and-filebackend`
- [ ] 5.3 PR 关联本 sub-stage 提案 + epic archive 链接

## 6. 后续 sub-stage 触发

- [ ] 6.1 本 sub-stage merge 后 → 开 4.2 `cache-redis-mongo-backends`（同 `docs/specs/cache-backend-unification/` 体系）

## 验证清单（每个 commit 前）

- 公开 API 签名 / 行为零改动
- `get_cache()` 返回实例的 `save_stock_data` / `load_stock_data` 行为等价
- `.json.gz` 文件格式不变
- `_serialize.py` 不动
- `tradingagents/dataflows/cache/` grep `pickle` 仍为 0
