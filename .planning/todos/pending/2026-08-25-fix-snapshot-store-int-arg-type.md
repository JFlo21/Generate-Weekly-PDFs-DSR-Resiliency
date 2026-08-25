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
