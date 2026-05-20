#!/usr/bin/env bash
# .claude/hooks/format-python.sh
#
# PostToolUse hook for Edit / Write / MultiEdit.
# Auto-runs `uvx ruff format <file>` on edited .py files to reduce pre-commit blocks.
#
# Project is in STRICT pre-commit mode (ruff-format-check is blocking). Formatting
# at edit time means the user can `git commit` without ruff complaints.
#
# Hook protocol:
#   stdin: JSON { tool_name, tool_input: { file_path, ... }, ... }
#   exit 0 always (this is a convenience hook, never blocks)

set -euo pipefail

INPUT="$(cat || true)"

if [[ -z "$INPUT" ]]; then
  exit 0
fi

# Extract file_path
FILE_PATH="$(printf '%s' "$INPUT" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    ti = d.get("tool_input", {}) or {}
    print(ti.get("file_path") or "")
except Exception:
    pass
' 2>/dev/null || echo "")"

# Only act on .py files
if [[ "$FILE_PATH" != *.py ]]; then
  exit 0
fi

# Skip if file doesn't exist (e.g. it was deleted)
if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# Skip files under .venv / node_modules / .git / scripts/_legacy
case "$FILE_PATH" in
  *.venv/*|*node_modules/*|*.git/*|*scripts/_legacy/*)
    exit 0
    ;;
esac

# Run ruff format silently. uvx pulls from pypi if not cached — should be cached
# after first run. Don't fail the hook even if ruff errors out.
uvx ruff format "$FILE_PATH" >/dev/null 2>&1 || true

exit 0
