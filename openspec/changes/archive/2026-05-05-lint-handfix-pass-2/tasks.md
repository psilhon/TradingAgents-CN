## 1. B007 + RUF059 + E712 + RUF005 unsafe-fix（87 → 0）

- [ ] 1.1 `uvx ruff check --fix --unsafe-fixes --select B007,RUF059,E712,RUF005 .`
- [ ] 1.2 验证 + commit `fix(lint): unsafe-fix B007/RUF059/E712/RUF005 (87 → 0)`

## 2. RUF013 implicit-optional unsafe-fix（125 → 0）

- [ ] 2.1 `uvx ruff check --fix --unsafe-fixes --select RUF013 .`
- [ ] 2.2 验证 + commit `fix(lint): unsafe-fix RUF013 implicit-optional (125 → 0)`

## 3. E722 bare-except 手动（31 → 0）

- [ ] 3.1 用 `uvx ruff check --fix --unsafe-fixes --select E722 .` 自动改成 `except Exception:`（unsafe 因可能改业务逻辑）
- [ ] 3.2 验证 + commit `fix(lint): E722 bare-except → except Exception (31 → 0)`

## 4. B-rules: B905 + B904 + B006 + B009（22 → 0）

- [ ] 4.1 `uvx ruff check --fix --unsafe-fixes --select B905,B904,B006,B009 .`
- [ ] 4.2 验证 + commit `fix(lint): unsafe-fix B-rules zip/raise-from/mutable-default (22 → 0)`

## 5. W293 hidden（279 → 0）

- [ ] 5.1 `uvx ruff check --fix --unsafe-fixes --select W293 .`
- [ ] 5.2 ⚠️ careful 验证：grep 改动是否影响字符串 literal（特别 docstring 内格式化空白）
- [ ] 5.3 验证 + commit `fix(lint): unsafe-fix W293 hidden blank-line-with-whitespace (279 → 0)`

## 6. F841 unused-variable（66 → 0）

- [ ] 6.1 `uvx ruff check --fix --unsafe-fixes --select F841 .`
- [ ] 6.2 ⚠️ careful 验证：删变量可能影响副作用（如 `result = some_call()` 调用必要但变量没用）；core import smoke test
- [ ] 6.3 验证 + commit `fix(lint): unsafe-fix F841 unused-variable (66 → 0)`

## 7. E402 module-import-not-at-top 手动（63）

- [ ] 7.1 grep E402 位置，看每个是否合理（如 try-import 模式 / sys.path 操作后 import / TYPE_CHECKING 等）
- [ ] 7.2 大部分加 `# noqa: E402` 注释（保留业务原因），少数能重排的重排
- [ ] 7.3 验证 + commit `fix(lint): E402 add noqa for legitimate cases / reorder where possible`

## 8. E501 line-too-long > 140 手动（114 → 减少）

- [ ] 8.1 grep E501 看长行模式（多是中文 docstring / log 拼接）
- [ ] 8.2 能分割的分割；中文 docstring 长行加 `# noqa: E501`
- [ ] 8.3 验证 + commit `fix(lint): E501 split long lines / noqa for Chinese docstrings`

## 9. F401 剩余 unused-import（35）

- [ ] 9.1 grep F401 位置，看每个是否动态使用（`hasattr` / `getattr` / `__all__` / re-export pattern）
- [ ] 9.2 动态用的加 `# noqa: F401`（含 reason），真不用的删
- [ ] 9.3 验证 + commit `fix(lint): F401 remove or noqa with rationale`

## 10. 一把梭剩余（UP035 + RUF022 + RUF012 + F403 + F405 + RUF015 + F601 + F823 + I001 + RUF034）

- [ ] 10.1 `uvx ruff check --fix --unsafe-fixes .` 一把梭
- [ ] 10.2 剩余手动看
- [ ] 10.3 验证 + commit `fix(lint): auto-fix + manual remaining small rules`

## 11. 收口

- [ ] 11.1 `uvx ruff check . --statistics` 看最终残留（目标 < 50）
- [ ] 11.2 浏览器手测端到端：登录 / 切 5 菜单 / 主题切换 / 配置中心
- [ ] 11.3 更新 docs/CHANGELOG.md `[Unreleased]` 加 `### Fixed` 段
- [ ] 11.4 commit `docs: changelog for lint-handfix-pass-2`
- [ ] 11.5 push（用户 1-click）
- [ ] 11.6 `openspec archive lint-handfix-pass-2 --yes`
