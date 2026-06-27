#!/usr/bin/env bash
# SessionStart hook — inject grounding context so every session starts knowing
# "where we are + what's next" from BOTH the repo status file and the second brain.
#
# Design guarantees:
#   * Fails open: always exits 0; if anything is missing, injects a fallback note.
#   * Safe JSON: file contents are JSON-encoded via Python (NOT shell-interpolated),
#     so markdown quotes/newlines/backslashes can never corrupt the hook output.
#   * Bounded: each section truncated; total capped under the 10,000-char limit.
#   * Read-only: reads files only; never writes the vault or the repo.
set +e

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -z "$ROOT" ] && ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"

PROJECT_STATE="$ROOT/.claude/project-state.md"
# Real (spaced) vault path — quoted; the space-truncation bug only affects the
# additionalDirectories settings key, not a shell `open()` here.
WIKI_STATE="C:/Users/juflores/OneDrive - Centuri Group, Inc/Documents/my-wiki/wiki/current-state.md"

python - "$PROJECT_STATE" "$WIKI_STATE" <<'PY' 2>/dev/null
import json, sys

def read(path, limit=4200):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()[:limit]
    except Exception:
        return "(not available: %s)" % path

project_state = read(sys.argv[1])
wiki_state = read(sys.argv[2])

ctx = (
    "ClaudeOS session grounding (auto-injected). Use this to pick the next step;"
    " do not re-derive what is already here.\n\n"
    "=== REPO STATUS (.claude/project-state.md) ===\n" + project_state + "\n\n"
    "=== SECOND-BRAIN CURRENT STATE (my-wiki/wiki/current-state.md) ===\n" + wiki_state
)
ctx = ctx[:9500]

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": ctx,
    }
}))
PY
exit 0
