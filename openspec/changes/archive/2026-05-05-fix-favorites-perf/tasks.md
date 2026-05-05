## 1. 删 favorites_service 同步 fallback — commit 1

- [x] 1.1 编辑 `app/services/favorites_service.py`：删除 line 117-127 的 "missing → quotes_service.get_quotes(missing)" fallback 逻辑（保留 mongo `market_quotes` 主路径）
- [x] 1.2 删除文件顶部的 `from app.services.quotes_service import get_quotes_service` import（如已无其它引用）
- [x] 1.3 ruff + pyright 仍 0 errors
- [x] 1.4 重启 backend
- [x] 1.5 验证：浏览器登录 → 进自选股 → 添加股票 → 列表加载 < 2s（之前 60s）
- [x] 1.6 验证：log 中 GET /api/favorites/ 耗时 < 2s
- [x] 1.7 commit

## 2. 收口

- [x] 2.1 docs/CHANGELOG.md
- [x] 2.2 commit + push + archive（push 由 v1.1.0 release 一起执行）
