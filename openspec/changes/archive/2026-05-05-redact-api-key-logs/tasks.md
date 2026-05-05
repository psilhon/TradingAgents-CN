## 1. 加 redact_api_key helper + 替换调用 — commit 1

- [x] 1.1 `tradingagents/utils/api_key_utils.py` 加 `redact_api_key(key)` 函数（返回 `(missing)` / `(len=N, ***)` / `(len=N, ends ...XXXX)`）
- [x] 1.2 替换 `tradingagents/config/config_manager.py:118,647`
- [x] 1.3 替换 4 处 llm_adapters 的 `前10位:` log（dashscope / openai_compatible_base × 2 / google_openai_adapter / deepseek_adapter）
- [x] 1.4 替换 `cli/main.py:1546-1566` 5 处 Rich 表格
- [x] 1.5 删 `cli/main.py:49` 已不用的 `DEFAULT_API_KEY_DISPLAY_LENGTH` 常量
- [x] 1.6 grep 验证无 `key[:N]` 前缀截取（仅保留 `truncate_api_key` 函数本身）
- [x] 1.7 ruff + pyright 0 errors
- [x] 1.8 pytest -m unit 仍 12 pass
- [x] 1.9 commit

## 2. 收口

- [x] 2.1 docs/CHANGELOG.md `### Fixed` 条目
- [x] 2.2 archive
