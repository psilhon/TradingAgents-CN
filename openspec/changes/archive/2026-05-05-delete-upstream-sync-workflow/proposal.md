## Why

`docs/code-review-2026-05-05.md` 第 5 个 critical 发现：`.github/workflows/upstream-sync-check.yml` 与项目"独立分叉，不再 sync upstream"约定（`openspec/specs/repository-scope/spec.md` 已锁定）正面冲突，且包含 HARD-GATE 明令禁止的"自动外部写入"动作：

- line 55-67：cron `'0 9 * * 1'` 每周一定时触发
- line 168-174：自动 `gh issue create` 创建 issue
- line 218-219：调用 `python scripts/sync_upstream.py --auto`（脚本不存在）
- line 223：自动 `git push origin main`

任何一次触发都违反 `~/.claude/CLAUDE.md` "本地优先" + "不可逆动作禁令"两条 HARD-GATE。

## What Changes

- **REMOVED** `.github/workflows/upstream-sync-check.yml`（整文件删除）
- **MODIFIED** `openspec/specs/repository-scope/spec.md`：在 `Fork 独立分叉模式` requirement 下新增 scenario，禁止任何自动化的 upstream sync workflow

无 BREAKING change（workflow 从未成功运行——所引脚本 `scripts/sync_upstream.py` 不存在）。

## Capabilities

### Modified Capabilities

- `repository-scope`：明确禁止自动化 upstream sync workflow

## Impact

**改动文件**：1 个 workflow 删除 + spec 增量更新
**风险**：极低
**收益**：消除 HARD-GATE 违规风险源 + 消除文档/CI 与铁律之间的认知冲突
