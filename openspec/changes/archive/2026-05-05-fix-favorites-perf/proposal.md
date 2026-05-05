## Why

实测 `GET /api/favorites/` 耗时 **19-63 秒**（每次都拉 AKShare `stock_zh_a_spot_em` 全 A 股 5849 条 spot），frontend 因 timeout 重试导致 10+ 并发请求雪崩。

根因 chain：
1. `favorites_service.get_user_favorites` line 117-127：mongo `market_quotes` collection miss 时**同步**调 `quotes_service.get_quotes(missing_codes)`
2. `quotes_service._fetch_spot_akshare`：AKShare 接口设计是"拉全市场"——传 1 个 code 也拉 5849 条
3. 全市场拉取耗 60s + asyncio.Lock 串行
4. frontend 没有节流，60s 内反复发 GET 触发雪崩

新加的自选股在 `market_quotes` 还没被 worker sync 之前就触发慢路径。

## What Changes

**最小修复路径**——不引入新依赖、不改 quotes_service 实现：

- **MODIFIED** `app/services/favorites_service.py:117-127`：删除"missing 时同步调 `quotes_service.get_quotes(missing)`" fallback。改为：mongo `market_quotes` miss 的 code，`current_price` / `change_percent` 留 `None`，前端显示 `-`
- 用户体验：添加自选股 < 1s 返回；价格字段在 worker（`quotes_ingest_service` 已有）30s 后自动 sync 落库 → 下次 GET hit cache 即有价格
- 与"自选股列表"语义一致——不强求即时实时价（实时价应在"个股详情页"按需调）

不在本 change 修：
- `quotes_service` 改用 AKShare 单股 API（更大改动，独立 change `quotes-service-single-stock-api`）
- frontend 节流（独立 change `frontend-api-throttle`）

无 BREAKING change（前端已经处理 `current_price=None`，仅显示更早出现）。

## Capabilities

### New Capabilities

- `favorites-performance`：定义 favorites 列表 GET 的性能契约（依赖 mongo `market_quotes` 而非外部 API 同步调用）

## Impact

**改动文件**：`app/services/favorites_service.py`（删 ~10 行 fallback 代码）
**性能**：60s → < 1s（mongo query only）
**风险**：低——前端已显示 `-` 处理 None
**收益**：自选股列表用户体验从"卡死 60s"→"瞬间响应"
