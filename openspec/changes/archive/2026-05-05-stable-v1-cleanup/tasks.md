## 1. Fork 决策记录（更新文档）— commit 1 ✅ 63c638b

- [x] 1.1 编辑 `CLAUDE.md`「Fork 上游同步」段：删除该段命令示例，改为"本 fork 是独立分叉，不再定期 sync upstream"声明
- [x] 1.2 编辑 `docs/USAGE.md`「上游同步流程」段同上（cherry-pick 模式）
- [x] 1.3 commit `chore(scope): record independent-fork decision (no upstream sync)`

## 2. 类别 B — 删 Windows 平台支持 — commit 2 ✅ 240997c

- [x] 2.1 git rm 80+ Windows 脚本（.ps1 / .bat / .cmd）
- [x] 2.2 git rm -r scripts/portable scripts/windows-installer
- [x] 2.3 git rm 6 个 Windows-only docs
- [x] 2.4 验证 `find . -name "*.ps1"` 等命中 0
- [x] 2.5 commit `chore(scope): drop Windows platform support (~95 files)`

## 3. 类别 C — 删 streamlit 旧 web/ + 依赖 — commit 3+3.5 ✅ 3850ddb + d3fb660

- [x] 3.1 git rm -r web/
- [x] 3.2 编辑 pyproject.toml：从 dependencies 删除 streamlit + chainlit
- [x] 3.3 编辑 pyproject.toml [tool.ruff/pyright].exclude 删除 web 项
- [x] 3.4 跑 `uv pip install -e .` + `uv pip uninstall streamlit chainlit`（uv pip install 不自动卸载，必须显式 uninstall）
- [x] 3.5 验证 git status 看 VERSION/requirements*.txt 是否被 uv 误删 — 本次未触发已知坑
- [x] 3.6 验证 backend 仍能启动：/api/health 200 ✓ + 监听 127.0.0.1:54301 + 无 startup error
- [x] 3.7 commit `chore(scope): remove streamlit legacy web/ + drop streamlit/chainlit deps` (3850ddb 漏 stage pyproject.toml，fix-up commit d3fb660 补)

## 4. 类别 D — 删学习中心残留 — commit 4 ✅ ad35960

- [x] 4.1 git rm -r docs/learning docs/paper
- [x] 4.2 验证 grep 残留：CHANGELOG/USAGE 自身记录 + blog post 待 task 8 删
- [x] 4.3 commit `chore(scope): remove learning-center docs residue (incl docs/paper/)`

## 5. 类别 E — 删未用 docker-compose 变体 — commit 5 ✅ 8af2cd1

- [x] 5.1 git rm docker-compose.hub.nginx.yml docker-compose.hub.nginx.arm.yml
- [x] 5.2 git rm -r nginx/
- [x] 5.3 验证 ls docker-compose*.yml 仅 docker-compose.yml + override
- [x] 5.4 commit `chore(scope): remove unused docker-compose hub variants + nginx config`

## 6. 类别 F — 删 install/ db config 快照 — commit 6 ✅ 0749749

- [x] 6.1 git rm -r install/
- [x] 6.2 commit `chore(scope): remove install/ db config snapshots (1MB)`

## 7. 类别 G — 删 examples + 旧版本测试 — commit 7 ✅ 0060a88

- [x] 7.1 git rm -r examples tests/0.1.14
- [x] 7.2 编辑 pyproject.toml [tool.pytest.ini_options]：移除 --ignore=tests/0.1.14 + norecursedirs 中的 0.1.14
- [x] 7.3 commit `chore(scope): remove examples/ + tests/0.1.14 historical snapshots`

## 8. 类别 H — 删上游 release notes + blog — commit 8 ✅ 85cfece

- [x] 8.1 git rm -r docs/releases docs/blog
- [x] 8.2 commit `chore(scope): remove upstream release notes + blog posts`

## 9. 收口

- [x] 9.1 更新 `docs/CHANGELOG.md` `[Unreleased]` 加 `### Removed` 段汇总
- [ ] 9.2 浏览器手测：登录 → 切几个菜单 → 主题切换 → 验证一切仍正常
- [ ] 9.3 跑 `du -sh .` 看清理后占用
- [ ] 9.4 跑 `du -sh .venv` 看 venv 是否减少
- [ ] 9.5 commit `docs: changelog summary for stable-v1-cleanup`
- [ ] 9.6 push 全部 commit（用户 1-click HARD-GATE 守门）
- [ ] 9.7 `openspec archive stable-v1-cleanup --yes`
