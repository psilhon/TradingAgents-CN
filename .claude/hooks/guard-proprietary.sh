#!/usr/bin/env bash
# .claude/hooks/guard-proprietary.sh
#
# PreToolUse hook for Edit / Write / MultiEdit.
# Blocks edits under app/ and frontend/src/ unless CLAUDE_ALLOW_PROPRIETARY=1.
#
# Reason: app/ and frontend/src/ are under proprietary license (see app/LICENSE,
# frontend/LICENSE). Commercial use requires explicit author authorization.
# Reading them is fine; modifying them is out of scope by default.
#
# Bypass mechanism: user can set CLAUDE_ALLOW_PROPRIETARY=1 for a session,
# or explicitly re-prompt with the intent to modify these paths.
#
# Hook protocol:
#   stdin: JSON { tool_name, tool_input: { file_path, ... }, ... }
#   exit 0: allow
#   exit 2: block + send stderr back to model

set -euo pipefail

# Bypass if user explicitly authorized via env var
if [[ "${CLAUDE_ALLOW_PROPRIETARY:-0}" == "1" ]]; then
  exit 0
fi

# Bypass if an OpenSpec change is currently being implemented
# (marker file written when Phase 2 starts, removed on archive)
REPO_ROOT_EARLY="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
if [[ -f "$REPO_ROOT_EARLY/openspec/changes/.implementing" ]]; then
  exit 0
fi

# Read hook JSON from stdin (may be empty if invoked weirdly)
INPUT="$(cat || true)"

if [[ -z "$INPUT" ]]; then
  # No input — let it pass; this hook only enforces when we can read file_path
  exit 0
fi

# Parse file_path (handle Edit / Write / MultiEdit)
FILE_PATH="$(printf '%s' "$INPUT" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    ti = d.get("tool_input", {}) or {}
    fp = ti.get("file_path") or ti.get("notebook_path") or ""
    print(fp)
except Exception:
    pass
' 2>/dev/null || echo "")"

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# Normalize to relative path from repo root
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
case "$FILE_PATH" in
  "$REPO_ROOT"/*)
    REL="${FILE_PATH#$REPO_ROOT/}"
    ;;
  /*)
    # Absolute path outside repo — not our concern
    exit 0
    ;;
  *)
    REL="$FILE_PATH"
    ;;
esac

# Check protected paths
case "$REL" in
  app/*|frontend/src/*)
    cat >&2 <<EOF
[guard-proprietary] BLOCKED: $REL

This file is under proprietary license (app/LICENSE or frontend/LICENSE).
The fork-level CLAUDE.md treats app/ and frontend/src/ as out-of-scope by default.

To proceed, choose one:
  1. Re-prompt explicitly: "edit $REL because <reason>" — Claude will re-attempt.
  2. Set CLAUDE_ALLOW_PROPRIETARY=1 in env for this session.
  3. Active OpenSpec change: write the change id to openspec/changes/.implementing
     (gitignored marker file, auto-bypasses the guard). Remove on archive.

This guard exists because CLAUDE.md says: "任何'清理 / 重构 / 顺手改'的范围默认排除这两个目录".
EOF
    exit 2
    ;;
esac

exit 0
