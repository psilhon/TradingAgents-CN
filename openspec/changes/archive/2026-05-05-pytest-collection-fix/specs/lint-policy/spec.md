## ADDED Requirements

### Requirement: pytest collection 0 errors

`pytest --collect-only` SHALL 报告 0 collection errors。任何引用已重组/删除模块的 dead test MUST 删除（git history 恢复），任何 import-time 副作用（如连 mongo / 网络请求）必须移到 fixture 或 lazy 调用。

#### Scenario: pytest collection 完全干净

- **WHEN** `.venv/bin/python -m pytest --collect-only`
- **THEN** 输出 `N tests collected` 不含 `errors`
- **AND** 不报 INTERNALERROR
- **AND** exit code 0
