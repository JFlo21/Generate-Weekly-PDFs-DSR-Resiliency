#!/usr/bin/env bash
# Phase-09 6-gate validation harness — run after every wave PR (D-03).
#
# Cheapest-first ordering: AST equality -> facade completeness -> pytest
# -> mypy delta -> py_compile -> golden run_summary structural diff. Every
# gate is BLOCKING; any non-zero exit aborts the run (set -e). On a red
# gate the wave PR is reverted, not patched (D-03 revert-not-patch).
#
# UTF-8 stdout (PYTHONUTF8) is forced so the engine's import-time emoji
# startup banners do not crash on a Windows cp1252 console; this is a
# harmless no-op on Linux/CI where UTF-8 is already the default.
#
# Usage:
#   bash scripts/run_6_gates.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

echo "=== Gate 1: AST import equality ==="
python scripts/check_api_equality.py

echo "=== Gate 2: Facade completeness ==="
python scripts/check_facade_completeness.py

echo "=== Gate 3: pytest ==="
python -m pytest tests/ -q

echo "=== Gate 4: mypy delta ==="
bash scripts/check_mypy_delta.sh

echo "=== Gate 5: py_compile ==="
python -m py_compile generate_weekly_pdfs.py
echo "PASS: py_compile clean"

echo "=== Gate 6: golden run_summary ==="
TEST_MODE=true SKIP_UPLOAD=true python generate_weekly_pdfs.py >/dev/null
python scripts/check_run_summary_structure.py

echo "=== ALL 6 GATES PASSED ==="
