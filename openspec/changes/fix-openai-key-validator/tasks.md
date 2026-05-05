## 1. 放宽 OpenAI key validator — commit 1

- [x] 1.1 改 `validate_openai_api_key_format`：删 `len == 51`、改 pattern 为 `^sk-[A-Za-z0-9_-]{29,}$`、加最小长度 32
- [x] 1.2 加 docstring 说明历史经典 vs sk-proj-/sk-svcacct- 兼容性
- [x] 1.3 8 个 test case 全部通过（classic / sk-proj- / sk-svcacct- 接受；short / wrong prefix / empty / None / 含空格 拒绝）
- [x] 1.4 ruff + pyright 0 errors
- [x] 1.5 pytest -m unit 仍 12 pass
- [x] 1.6 commit

## 2. 收口

- [x] 2.1 docs/CHANGELOG.md `### Fixed` 条目
- [x] 2.2 archive
