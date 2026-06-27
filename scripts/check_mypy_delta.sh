#!/usr/bin/env bash
# Gate 4 — mypy error-line count must NOT increase vs the frozen baseline.
#
# Compares the line count of
#   mypy generate_weekly_pdfs.py audit_billing_changes.py billing_audit pipeline
# (config read from pyproject.toml [tool.mypy]) against the count frozen in
# tests/golden/mypy_baseline_count.txt. Fails only on an INCREASE — a
# neutral or reduced count passes (warn-only posture, matches CI
# python-lint.yml).
#
# Skips gracefully (exit 0) when mypy is not installed, per RESEARCH
# §"Environment Availability" fallback ("Skip gate 4 until installed"), so
# the full harness stays green in environments without the dev tooling.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASELINE_TXT="$REPO_ROOT/tests/golden/mypy_baseline.txt"
BASELINE_COUNT_FILE="$REPO_ROOT/tests/golden/mypy_baseline_count.txt"
MYPY_TARGETS=(generate_weekly_pdfs.py audit_billing_changes.py billing_audit pipeline)

# Resolve a mypy runner: prefer the module form, fall back to the binary.
if python -m mypy --version >/dev/null 2>&1; then
  MYPY=(python -m mypy)
elif command -v mypy >/dev/null 2>&1; then
  MYPY=(mypy)
else
  echo "SKIP: mypy not installed — Gate 4 skipped (RESEARCH fallback)"
  exit 0
fi

if [ ! -f "$BASELINE_COUNT_FILE" ]; then
  echo "SKIP: no mypy baseline frozen yet ($BASELINE_COUNT_FILE)"
  exit 0
fi

cd "$REPO_ROOT"
CURRENT_OUT="$(mktemp)"
trap 'rm -f "$CURRENT_OUT"' EXIT

# mypy exits non-zero when it reports type errors; that is expected here,
# so guard against set -e aborting on a normal "errors found" exit.
"${MYPY[@]}" "${MYPY_TARGETS[@]}" >"$CURRENT_OUT" 2>&1 || true

new_count="$(wc -l < "$CURRENT_OUT" | tr -d ' ')"
baseline_count="$(tr -d ' \n' < "$BASELINE_COUNT_FILE")"

if [ "$new_count" -gt "$baseline_count" ]; then
  echo "FAIL: mypy error lines increased ($baseline_count -> $new_count)"
  diff "$BASELINE_TXT" "$CURRENT_OUT" || true
  exit 1
fi

echo "PASS: mypy delta neutral or improved ($baseline_count -> $new_count)"
exit 0
