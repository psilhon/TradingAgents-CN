# 4.8 — Design refinements（E1-E4）

## Why

4.7 hotfix + hardening 之后做的两轮 code review（`/code-review` xhigh effort + `/pr-review-toolkit:review-pr` 5 个 specialist 并行）将剩余非关键性发现归为 P4「可延后」。这 4 项不是 user-facing bug，但都是 **正确性 / 可运维性 / 代码体量**的渐进改进：

- **E1（atomic write）**：`FileBackend.save` 当前 `open + write` 不原子，进程被 SIGKILL / 磁盘满 / OOM 时会留下 truncated `.json.gz`——下次 `load()` gzip decode 抛异常，被 catch 后视为 cache miss + 重写，正确性不破，但代价是脏文件残留 + 静默"miss"。
- **E2（cache_dir env override）**：`get_cache()` 内 hardcode `Path("data/cache")` 相对 CWD。若 uvicorn 被 systemd / docker 起在非项目根（CWD=`/`），缓存会落到 `/data/cache`——FastAPI worker 都同一目录所以仍能命中自身，但与开发模式（CWD=项目根）写出的缓存隔离。env `TA_CACHE_DIR` 让运维一键修正。
- **E3（typed dispatch dedup）**：`Cache.save_stock_data` / `save_fundamentals_data` / `load_*` / `find_cached_*` 共 6 个公开方法，结构几乎一致——envelope 构造 + cache_key 派生 + TTL 推断 + 路由调用——只在 data_type 字符串和 id 字段集上不同。stage 5 之后扩 news_data / report_data 时按现状是每多一种类型 +4 个方法 +30 行 boilerplate。抽 `_save_typed` / `_load_typed` / `_find_typed` 私有 helper 后公开 API 仍保持，新增类型只需 `data_type + id_fields` 两个参数。
- **E4（close() 生命周期）**：`Cache` 无显式 close()，FastAPI shutdown hook / pytest teardown 无法主动释放 redis / mongo client 连接。Python GC 兜底，但 ResourceWarning + 测试套件残留连接是已知噪音。`Backend` Protocol 加可选 `close()`，各后端实现各自的关闭语义。

每项独立可验证。立项一次落入同一 4.8 sub-stage，4 个 commit 实施（每项一个），不切 4 个 sub-stage 因为改动局部，互不依赖。

## What Changes

### `tradingagents/dataflows/cache/backends/file.py`

- `FileBackend.save` 改为「写临时文件 + os.replace 原子换名」模式：
  - 写入 `{cache_dir}/.{key}.json.gz.tmp.{pid}` 后调 `os.replace(tmp, final)` —— POSIX 保证 same-filesystem rename 原子
  - 异常路径用 try/finally 清理残留临时文件，不让 partial tmp 累积
  - 现有 `cache_dir.mkdir(parents=True, exist_ok=True)` 不变（构造时确保目录）

### `tradingagents/dataflows/cache/__init__.py`

- `get_cache()` 读 env `TA_CACHE_DIR`，缺省 `"data/cache"`：
  ```python
  cache_dir = Path(os.getenv("TA_CACHE_DIR", "data/cache")).expanduser()
  ```
- `~` expand 让 `TA_CACHE_DIR=~/.cache/tradingagents` 这种常见运维写法可用。

### `tradingagents/dataflows/cache/_cache.py`

- 内部抽 3 个私有 helper：
  - `_save_typed(symbol, data, data_type: str, id_fields: dict[str, str]) -> str`
  - `_load_typed(cache_key: str) -> Any | None`
  - `_find_typed(symbol, data_type: str, id_fields: dict[str, str], max_age_hours: int | None) -> str | None`
- 4 个公开方法（`save_stock_data` / `load_stock_data` / `find_cached_stock_data` / `save_fundamentals_data` / `load_fundamentals_data` / `find_cached_fundamentals_data`）改成 thin 调用 helper。公开 API 签名 / cache_key 派生 / 行为 MUST 字节级保持。
- 新增 `Cache.close() -> None`：
  - 委派 file/redis/mongo backend 的 `close()`（如方法存在；duck-typed via `getattr(b, "close", None)`）
  - 各 backend 异常 catch 不让一个 backend 拖垮关闭流程
- 同步加 `def __enter__` / `def __exit__` 让 `with Cache(...) as c:` 成立（Phase 1 可选；testing 友好）

### `tradingagents/dataflows/cache/backends/_protocol.py`

- 在 `Backend` Protocol 内加 `close() -> None` —— 但**作为可选方法**：runtime_checkable Protocol 不强制方法实现存在，调用方用 `getattr(b, "close", None)` 检测后调。这样三个后端都加上自己的 close()，但不破坏其它符合旧 Protocol 的 mock 测试。

### `tradingagents/dataflows/cache/backends/{file,redis,mongo}.py`

- `FileBackend.close()`：no-op（文件后端无连接资源）
- `RedisBackend.close()`：`self._client.close()`（redis-py `Redis` 实例的 close，4.x 起释放连接池）
- `MongoBackend.close()`：`self._client.close()`（pymongo `MongoClient` 关闭连接池）

### `docs/specs/dataflow-caching/spec.md`

加 1 新 Requirement +  4 修订 Requirement：

- **新增 Requirement "FileBackend 原子写入"**：禁止 partial-write 残留，覆盖 SIGKILL / OOM / 磁盘满场景。
- **修订 Requirement "FileBackend 单一职责"**：`save` 现在用临时文件 + os.replace（标 4.8 起）。
- **修订 Requirement "统一 Cache 类（公开 API 单一实现）"**：加 `close()` 公开方法 +  context manager 协议。
- **修订 Requirement "Backend Protocol 接口"**：加可选 `close()`（runtime-checkable Protocol 不强制实现；调用方 duck-type 检测）。
- **新增 Requirement "缓存目录可由 env 覆盖"**：`TA_CACHE_DIR` 控制 `get_cache()` 路径推断；`~` expand 支持。

## Impact

### Code 变化
- `file.py`：+10 行（原子写入 helper + finally 清理）
- `_cache.py`：净 -30 行左右（dedup 后 6 个公开方法各从 ~20 行压到 ~5 行；helper 共 ~40 行）+ 10 行 close()
- `__init__.py`：+2 行（os.getenv + expanduser）
- backends/{file,redis,mongo}.py：各 +5 行 close()
- 总变化：-5 ~ +30 行净

### Spec
- `docs/specs/dataflow-caching/spec.md`：+ 1 个新 Requirement / + 4 个 Scenario

### 测试
- E1：`tests/test_file_backend.py` 加 atomic write 测试（模拟写入 raise，验证 cache_dir 不留 `.tmp` 残留 + 不留 truncated final）
- E2：`tests/test_get_cache.py` 加 env override 测试（monkeypatch `TA_CACHE_DIR` 后 `Cache.file_backend.cache_dir` 匹配）
- E3：`tests/test_cache_class.py` 已有的 6 个公开方法字节级测试覆盖此项（不破任何即可）；加 1 个测试确认私有 helper 存在并被调用（防 helper 被绕开）
- E4：`tests/test_cache_class.py` 加 Cache.close() 测试 + 各 backend close mock 验证；context manager 协议测试

### 用户 / callsite
- **零破坏**：所有变化都是内部实现或可选 env / 可选生命周期。`Cache` 公开 API 签名 + cache_key 派生 + 路由 + TTL 行为字节级保持。
- 运维新增能力：`TA_CACHE_DIR` env + `Cache.close()` API。

### 风险
- E1（atomic write）：`os.replace` 在 Windows 上对已存在 dest 行为不同，但项目是 POSIX-only（macOS / Linux），不需处理。
- E3（dedup）：稍微提高函数嵌套深度，但 cache_key 派生 + envelope 形状字节级保持是 spec 强约束 + 测试守护，不会偏离。
- E4（close）：误调 close() 后再用 Cache 实例当前会让 backend 操作返 False / None（已经是 Cache 整体的错误约定）；不需要重置 state。

## Out of Scope (4.8 不做)

- B1（envelope dict → TypedDict / Pydantic Model）—— 类型化是 stage 5 重设计的范畴
- N2（news_data 公开方法）—— 仍待真正消费方接入再做
- 其它 v2 stage 改造（schema 重设计 / async API / metrics 接入）
