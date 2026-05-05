## Why

`CLAUDE.md` 经过 4 次 OpenSpec change 累积已 179 行，**超过项目级模板的 50-150 行建议上限**。模板要求"短而精，只写项目特有事实"，超长会让新会话 AI 助手 prime context 时信息过载、关键约定被淹没。

诊断：当前 CLAUDE.md 最末段「已知坑」（10 行）属"长尾信息"——

- 信息密度低（每条独立、不互相引用）
- 长期增长趋势（每次踩坑加一条）
- 阅读频率低（不是每次会话都需要）

适合外置到 `docs/ai-context/known-issues.md`，CLAUDE.md 留 1 行指引。

## What Changes

- **NEW**：`docs/ai-context/known-issues.md`（容纳从 CLAUDE.md 移出的"已知坑"段 + 后续新踩坑）
- **MODIFIED**：`CLAUDE.md` 删除「已知坑」段（line 170-179）+ 在「AI 上下文入口」段补一行指引"已知坑：见 `docs/ai-context/known-issues.md`"
- **MODIFIED**：`docs/ai-context/coding-standards.md`（如有引用 known issues 的链接，更新指向新位置）

无 BREAKING change（仅文档重组，规则信息无变化）。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `repository-scope`：MODIFY「文档范围」Requirement，加 "CLAUDE.md 行数 ≤ 150 + 长尾内容外置到 docs/ai-context/" 约束

## Impact

**改动文件**：3
- `CLAUDE.md` (-10 行 + 1 行指引 = ~170 行回 150 内)
- `docs/ai-context/known-issues.md` (新建)
- `openspec/specs/repository-scope/spec.md` (MODIFY 既有 spec)

**风险**：无 runtime 影响；纯文档重组。

**收益**：CLAUDE.md 回到模板范围；已知坑后续可无负担增长（externalized）。
