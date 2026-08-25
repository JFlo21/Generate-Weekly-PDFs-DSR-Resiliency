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
# G-09-MOD-06: Gate 6 is a STRUCTURAL oracle over run_summary.json keys and
# value types. It measures the shape of the artifact, not the correctness of
# the data, so real production rows add zero verification signal. TEST_MODE
# alone does not bound the dataset -- it only selects the synthetic in-memory
# rows when SMARTSHEET_API_TOKEN is falsy; with a .env-supplied token this
# same command fetched all 118 production source sheets and 208,511 rows
# during the 2026-08-24 retroactive verification and never reached this gate.
# The command-prefix assignment below is scoped to this single process only
# and does not alter the caller's environment; load_dotenv(override=False)
# will not repopulate it from .env.
SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true python generate_weekly_pdfs.py >/dev/null
python scripts/check_run_summary_structure.py

echo "=== ALL 6 GATES PASSED ==="
