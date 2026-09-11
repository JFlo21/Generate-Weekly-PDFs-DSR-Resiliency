---
created: 2026-08-25T00:05:00-05:00
title: Fix class-A mypy finding — billing_audit/snapshot_store.py int(row.get()) arg-type
area: billing_audit
severity: minor
files:
  - billing_audit/snapshot_store.py:370
---

## Problem

The only genuine type defect (class A) accepted into the mypy Gate-4 re-baseline
(56 -> 65, commit after `a1499d6`, gap G-09-MOD-06): `int(row.get(...))` receives
`Any | None`. It is runtime-guarded by the `except (TypeError, ValueError): continue`
directly below, so there is no correctness impact today — but the baseline now
permanently hides it. Blame `a6e19db` (2026-08-12, quick task 260812-jqx, #330).
Attribution: `.planning/debug/mypy-delta-56-to-65-2026-08-24.md` row #3.

## Solution

One-line fix in protected billing code (narrow the value before `int()`, or
`str(...)` with an explicit `None` guard) with a unit test, in its own plan/quick
task. After the fix, lower `tests/golden/mypy_baseline*.txt` back by exactly the
removed lines in a dedicated re-baseline commit whose ledger entry names them
(re-baseline hygiene rule, ledger `[2026-08-25 00:02]`).

## Resolution

**2026-09-11 (Phase 13 plan 13-02, Tasks 1-2):** Fixed. `sheet_id`/`row_id` are
now read into locals in `fetch_snapshot_provenance` and the loop `continue`s
when either is `None` BEFORE the `int()` cast; the pre-existing
`except (TypeError, ValueError): continue` is unchanged, so runtime behavior
is byte-for-byte preserved (4 new regression tests in
`tests/test_snapshot_store.py::TestFetchSnapshotProvenanceKeyGuard`, plus the
full suite: 2342 passed / 1 skipped, no regression). `tests/golden/mypy_baseline.txt`
dropped exactly the one `snapshot_store.py:370` `[arg-type]` line (71 -> 70
lines); `tests/golden/mypy_baseline_count.txt` moved `71` -> `70`; ledger entry
recorded per the re-baseline hygiene rule. `bash scripts/run_6_gates.sh` green
at the lowered baseline.
