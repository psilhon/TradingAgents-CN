## 1. 批量补 unit marker — commit 1

- [x] 1.1 实测 10 个候选文件
- [x] 1.2 5 个 fully-passing 文件加 `pytestmark = pytest.mark.unit`
- [x] 1.3 5 个 stale mock 失败文件**不动**（作 follow-up backlog `tests-fix-stale-mocks`）
- [x] 1.4 跑 `pytest -m unit` 验证：12 passed, 0 failed
- [x] 1.5 ruff + pyright 仍 0 errors
- [x] 1.6 commit

## 2. 收口

- [x] 2.1 docs/CHANGELOG.md `### Changed` 条目
- [x] 2.2 archive
