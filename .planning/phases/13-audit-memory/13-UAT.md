---
status: testing
phase: 13-audit-memory
source: [13-VERIFICATION.md]
started: 2026-09-12T03:27:19Z
updated: 2026-09-12T03:27:19Z
---

## Current Test

number: 1
name: Success criterion 2 — audit wall clock proportional to affected groups + open findings
expected: |
  With AUDIT_MEMORY_ENABLED=1 on a frequent (2-hourly) run, the audit-memory phase's
  logged counters (examined=/distinct=, findings_sent=/reaudited_pairs_sent=/opened=.../reopened=)
  and its wall clock scale with the affected-group set plus open findings, not with the
  full row population. Observe across at least two consecutive live runs (measured, not
  asserted — 13-CONTEXT.md D-09 shadow-first).
awaiting: user response

## Tests

### 1. Success criterion 2 — audit wall clock proportional to affected groups + open findings
expected: With AUDIT_MEMORY_ENABLED=1 on frequent runs, audit-memory wall clock and the run-log counters (examined=/distinct=, findings_sent=/reaudited_pairs_sent=/opened=.../reopened=) scale with affected groups + open findings. Code is architecturally consistent (to_fix/upsert CTEs scoped to p_reaudited_pairs and incoming findings only; build_finding_payloads iterates only this run's emitted findings); the property itself is production-observed once the flag is flipped on.
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
