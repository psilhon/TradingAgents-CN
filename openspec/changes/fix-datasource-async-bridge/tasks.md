# fix-datasource-async-bridge — Tasks

> 对应 [proposal.md](./proposal.md) / [spec.md](./specs/dataflow-integrity/spec.md)
>
> 实施阶段：**Phase 2 执行**。遵循 `superpowers:systematic-debugging`——先写失败测试复现 bug，再改代码。

## 1. 失败测试先行（systematic-debugging Phase 4）

- [x] 1.1 新建 `tests/dataflows/test_data_source_manager_async_bridge.py`，测试标 `@pytest.mark.unit`
- [x] 1.2 写测试：在 `async def test_...`（pytest-asyncio，即「有 running event loop」的环境）里，mock 三个 provider 的 `get_historical_data` / `get_stock_basic_info` 返回假 DataFrame / dict，调 `DataSourceManager._get_tushare_data` / `_get_akshare_data` / `_get_baostock_data`，断言正常返回、不抛 `RuntimeError: this event loop is already running`
- [x] 1.3 跑测试确认**当前红**（复现 bug）：3 个 async 测试 `RuntimeError: This event loop is already running`，1 个 sync 测试 PASSED

## 2. 修复：统一异步桥接 helper

- [x] 2.1 在 `data_source_manager.py` 模块级新增 `_run_provider_coro(coro)`：检测当前线程 running loop——无则 `asyncio.run(coro)`，有则在独立线程跑 `asyncio.run` 并阻塞取结果
- [x] 2.2 `_get_tushare_data`：3 处 `run_until_complete`（含缓存命中分支）→ `_run_provider_coro`，移除 2 个 `get_event_loop` 样板块
- [x] 2.3 `_get_akshare_data`：同 2.2
- [x] 2.4 `_get_baostock_data`：同 2.2

## 3. 验证

- [x] 3.1 跑 1.1 的测试，确认**转绿**（4 passed）
- [x] 3.2 跑同步上下文回归（`test_tushare_data_in_sync_context` 通过，CLI / 线程池路径不破）
- [x] 3.3 `just lint` + `just typecheck`：ruff All checks passed / pyright 0 errors 0 warnings
- [x] 3.4 端到端验证：在真实 async 上下文（`asyncio.run`）调 `prepare_stock_data_async("603009")`，结果 `is_valid=True` / `stock_name=北特科技` / `has_historical=True`，不再抛 event loop 错误

## 4. 收口

- [x] 4.1 `docs/CHANGELOG.md` `[Unreleased]` `### Fixed` 加一条
- [ ] 4.2 本地 commit（commit message 中英混合，`fix:` 前缀）
- [ ] 4.3 归档 change 到 `openspec/changes/archive/`（Phase 3 收口，用户确认后）
