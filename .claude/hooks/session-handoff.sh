#!/usr/bin/env bash
# SessionEnd hook — write an always-fresh, deterministic handoff so the next
# session resumes with current context (no re-research required).
#
# Design guarantees:
#   * Best-effort: always exits 0; never fails or blocks a session.
#   * Non-destructive: writes ONLY .remember/remember.md (the designated
#     handoff slot) and points at .planning/STATE.md. Never rewrites STATE.md's
#     curated narrative.
#   * Polite: skips writing if a handoff was authored in the last 3 minutes
#     (e.g. you just ran /remember) so it never clobbers a richer handoff.
set +e

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -z "$ROOT" ] && ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
cd "$ROOT" 2>/dev/null || exit 0

HANDOFF="$ROOT/.remember/remember.md"
mkdir -p "$ROOT/.remember" 2>/dev/null

# Don't clobber a handoff written in the last 180s (e.g. by /remember).
if [ -f "$HANDOFF" ]; then
  now=$(date +%s 2>/dev/null || echo 0)
  mtime=$(stat -c %Y "$HANDOFF" 2>/dev/null || stat -f %m "$HANDOFF" 2>/dev/null || echo 0)
  if [ "$now" -gt 0 ] && [ "$mtime" -gt 0 ] && [ $((now - mtime)) -lt 180 ]; then
    exit 0
  fi
fi

TS="$(date +'%Y-%m-%d %H:%M %Z' 2>/dev/null || echo 'unknown time')"
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
LASTCOMMIT="$(git log -1 --pretty='%h %s' 2>/dev/null || echo 'none')"
DIRTY="$(git status --porcelain 2>/dev/null | grep -c . 2>/dev/null || echo 0)"

# Pull current position from GSD STATE.md (best-effort, plain grep).
FOCUS="$(grep -m1 '^\*\*Current focus:\*\*' .planning/STATE.md 2>/dev/null | sed 's/^\*\*Current focus:\*\* *//')"
NEXTSTEP="$(grep -m1 '^Next:' .planning/STATE.md 2>/dev/null | sed 's/^Next: *//')"

{
  echo "# Session Handoff (auto)"
  echo
  echo "_Written automatically at session end — ${TS}._"
  echo
  echo "**Resume here:** read \`.planning/STATE.md\` — it is the authoritative"
  echo "project front door (position, locked decisions, next step) and is"
  echo "auto-surfaced at SessionStart by the GSD session-state hook."
  echo
  echo "## Snapshot"
  echo "- **Branch:** \`${BRANCH}\`"
  echo "- **Last commit:** ${LASTCOMMIT}"
  echo "- **Uncommitted files:** ${DIRTY}"
  [ -n "$FOCUS" ] && echo "- **Current focus:** ${FOCUS}"
  [ -n "$NEXTSTEP" ] && echo "- **Next:** ${NEXTSTEP}"
  echo
  echo "## Where context lives"
  echo "- \`.planning/STATE.md\` — start here (position, decisions, next step)"
  echo "- \`.planning/phases/*/*-CONTEXT.md\` — locked decisions per phase"
  echo "- \`.planning/phases/*/*-DISCUSSION-LOG.md\` — alternatives considered"
  echo "- \`.remember/\` + context-mode KB — searchable session history"
} > "$HANDOFF" 2>/dev/null

exit 0
