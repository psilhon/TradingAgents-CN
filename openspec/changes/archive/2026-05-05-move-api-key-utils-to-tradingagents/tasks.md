## 1. 移动文件 + 修 import — commit 1

- [x] 1.1 `git mv app/utils/api_key_utils.py tradingagents/utils/api_key_utils.py`
- [x] 1.2 5 处 `tradingagents/llm_adapters/*.py` import 改 `tradingagents.utils.api_key_utils`（sed）
- [x] 1.3 `app/routers/{config,system_config}.py` import 改 `tradingagents.utils.api_key_utils`
- [x] 1.4 grep 验证 `tradingagents/` 不再 import `app.utils.api_key_utils`（0 hit）
- [x] 1.5 `ruff check --fix` + `ruff format` 修补移动后 style（25 fixes，最终 All checks passed）
- [x] 1.6 pyright 0 errors
- [x] 1.7 smoke import test 通过
- [x] 1.8 记录反向 import baseline = 22（v1.1.0 后状态）到 `docs/code-review-2026-05-05.md`
- [x] 1.9 commit

## 2. 收口

- [x] 2.1 docs/CHANGELOG.md `### Fixed` 条目
- [x] 2.2 archive
