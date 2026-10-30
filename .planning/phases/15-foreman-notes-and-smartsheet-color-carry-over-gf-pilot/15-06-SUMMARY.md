---
phase: 15-foreman-notes-and-smartsheet-color-carry-over-gf-pilot
plan: 06
subsystem: docs
tags: [foreman-notes, docs, runbook, docusaurus, changelog]
requires: [15-05]
provides:
  - "Configuration catalog, architecture module row and ledger entry for the Phase 15 pilot"
  - "website/docs/runbook/foreman-notes-pilot.md operator runbook page"
  - "FOREMAN_NOTES_* reference section in website/docs/reference/environment.md"
  - "Synthesized changelog entry website/blog/2026-10-30-phase-15-foreman-notes-pilot.md (PR: pending for 15-07)"
affects: [15-07]
tech-stack:
  added: []
  patterns:
    - "single-source dry-run recipe copied verbatim into catalog and runbook"
key-files:
  created:
    - website/docs/runbook/foreman-notes-pilot.md
    - website/blog/2026-10-30-phase-15-foreman-notes-pilot.md
  modified:
    - .github/prompts/configuration-environment.md
    - docs/ai/architecture.md
    - memory-bank/living-ledger.md
    - website/docs/reference/environment.md
    - website/sidebars.ts
key-decisions:
  - "Dry-run recipe documented with the revised effective-scope rule: AUDIT_MEMORY_ENABLED counts as a write path (15-05 deviation)"
  - "Allowlist documented only as 'set in env / repository variable'; pilot GFs referred to as GF-1..GF-3, no names or WR numbers anywhere"
requirements-completed: [FN-02, FN-11]
status: complete
commits: 2
plan_head_before: 6fc9fd9c24c233b89b9c2505cf494830a6453ecd
plan_head_after: 7a93875bcb7a4d35bc28dfa66e85983ce4c6bec9
metrics:
  duration: "~25m"
  completed: 2026-10-29
actuals:
  tokens: 12000
  tasks: 2
  commits: 2
---

# Phase 15 Plan 06: Operator documentation Summary

Operators can now configure, rehearse, roll out and roll back the Foreman Notes and colour pilot from the repo docs and the Docusaurus runbook alone; the website typecheck and build are verified green.

## Tasks

| Task | Name | Commit |
|------|------|--------|
| 1 | Tracer: repo docs (catalog, architecture, ledger) | b90f3bb |
| 2 | Website runbook page, environment reference, changelog entry | 7a93875 |

## What was documented

- **Catalog** (`.github/prompts/configuration-environment.md`): `FOREMAN_NOTES_SCOPE`, `_PILOT_GFS` (default empty, "set in env / repository variable"), `_UPLOAD`, and the two GF column ids; the effective-scope rule; the verbatim dry-run recipe; rollout and rollback.
- **Architecture**: a Components row for `pipeline/foreman_notes.py` with its seams, plus a verification note.
- **Ledger**: dated Phase 15 entry at the bottom with Why, Change, Rollback, seven durable rules (effective scope, dry-run no-persist guard, pilot-gated hash inputs, `Foreman Notes` never in `_extended_row_fields` / `GROUP_DERIVATION_KEYS`, colours never hash inputs, marker suffix, no PII to Sentry/logs) and the D-15-13 merge gate.
- **Website**: runbook page (component owner stated: Python billing pipeline), environment reference section linking it, a sentence on the hash-store flag, and the synthesized what/why/how changelog entry with a `PR: pending` line that 15-07 must replace.

## Verification

- Task 1 automated check: `[True, True, True, True, True, True]`, exit 0. Diff vs the Task 1 files shows additions only.
- Allowlist-value grep over the Phase 15 diff (`FOREMAN_NOTES_PILOT_GFS` followed by a non-alias value): prints nothing. `whats-new.md` untouched (diff vs BASE_SHA exits 0).
- `cd website && npm run typecheck && npm run build`: **exit 0** (`tsc` clean; `[SUCCESS] Generated static files in "build"`, no broken-link warnings in the output; `website/build` is gitignored). Verified, not an unverified manual step.
- Full suite: `pytest tests/ -q` -> **2747 passed, 3 skipped, 821 subtests passed** (includes the golden baseline `tests/test_foreman_notes_baseline.py`).
- `bash scripts/run_6_gates.sh` not re-run: docs-only change; Gate 4 (mypy delta) remains a pre-existing failure from a stale `tests/golden/mypy_baseline_count.txt` (70), noted in 15-05. Baseline file not edited. Phase 15 adds zero mypy errors.

## Deviations from Plan

- [Rule 3 - blocking] Added `'runbook/foreman-notes-pilot'` to `website/sidebars.ts` (not in the plan's file list): the sidebar is explicit, so without it the new page would be built but unreachable from navigation.
- [Interpretation] The blog entry uses `authors: [operators]` (the hand-written changelog author key) and absolute site links (`/docs/...`) because relative `.md` links from the blog plugin to docs pages do not resolve across plugins. `sidebar_position: 10` (8 and 9 were taken).

## Requirements

FN-02 (allowlist set in env / repository variable, documented) and FN-11 (effective scope and dry-run recipe documented) were already Complete; this plan documents them. FN-13 (merge gated on Phase 11 closure) is recorded in the ledger, runbook and changelog but left Pending: the gate is satisfied only at merge time (15-07).

## Known Stubs

None. The blog entry's `PR: pending` placeholder is intentional and is owned by 15-07, which must replace it (also in the header line of the same entry).

## Threat Flags

None. Docs contain variable names only: no names, WR numbers, tokens or `.env` content (T-15-25, T-15-28 mitigated); build result recorded honestly (T-15-29).

## Self-Check: PASSED

- All six plan files plus `website/sidebars.ts`: FOUND
- Commits b90f3bb, 7a93875: ancestors of HEAD
