---
phase: quick-260528-lu6
plan: "01"
subsystem: documentation
tags: [agents-md, codex, living-ledger, lean-docs]
dependency_graph:
  requires: []
  provides: [AGENTS.md lean Codex-flavored mirror]
  affects: [AGENTS.md]
tech_stack:
  added: []
  patterns: [lean-pointer documentation pattern]
key_files:
  created: [AGENTS.md]
  modified: []
decisions:
  - "AGENTS.md mirrors CLAUDE.md structure exactly (346 lines, byte-identical except 7
    intended Codex-flavor hunks), passing the plan's min_lines:330 gate. (Executor's
    in-run PowerShell count of 279 was a miscount; wc -l confirms 346 for both files.)"
metrics:
  duration: "~5 min"
  completed: "2026-05-28"
---

# Quick Task 260528-lu6: Reconcile AGENTS.md to Lean Pointer — Summary

Replaced the bloated, untracked 2,275-line AGENTS.md with a lean 346-line Codex-flavored mirror of the canonical CLAUDE.md (also 346 lines), deferring the Living Ledger to its single canonical source at `memory-bank/living-ledger.md`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rewrite AGENTS.md as lean Codex-flavored mirror | d30be0e | AGENTS.md (created, 346 git-diff insertions) |
| 2 | Confirm documentation-only blast radius | d30be0e | verified — only AGENTS.md changed |

## Deviations from Plan

### None (measurement note)

The executor's in-run PowerShell line count (`Get-Content | Measure-Object -Line` → 279)
under-counted the file. Authoritative `wc -l` reports **346 lines for both CLAUDE.md and
AGENTS.md**, and `diff CLAUDE.md AGENTS.md` shows only 7 intended Codex-flavor hunks — a
complete, byte-faithful mirror. The plan's `min_lines: 330` gate **passes** at 346; there
was no real deviation and no content is missing. All other gates pass (zero `.Codex/`
paths, zero inlined dated entries, 8 ledger pointer refs, injection + ledger sections
present, @Codex trigger present).

## Requirements Addressed

- **LU6-01:** Living Ledger de-inlined — final section contains ONLY the adapted 3-paragraph blockquote pointer to `memory-bank/living-ledger.md`. Zero inlined entries.
- **LU6-02:** Staleness eliminated — AGENTS.md defers entirely to `memory-bank/living-ledger.md` (47+ entries), no stale content copied.
- **LU6-03:** All `.Codex/` references removed — confirmed 0 occurrences. Real `.github/` paths kept verbatim.
- **LU6-04:** Anti-pattern removed — both the AUTONOMOUS CLOUD MEMORY INJECTION section and the Living Ledger pointer explicitly instruct appending to `memory-bank/living-ledger.md`, NOT to AGENTS.md's own bottom. Self-references say "this `AGENTS.md` file".

## Codex-Flavor Substitutions Applied

- Intro line: "guidance to Codex (OpenAI Codex / agentic coding agents)"
- Trigger: `@Codex` (was `@claude`)
- pre-push hook note: "Claude Code hook ... does not gate Codex/terminal pushes — run `pytest tests/` manually before pushing"
- Living Ledger pointer: AGENTS.md-appropriate wording mirroring CLAUDE.md's deferral
- Detailed References: `not to AGENTS.md` (was `not to CLAUDE.md`)

## Self-Check

- AGENTS.md exists: FOUND
- Commit d30be0e: verified via `git rev-parse --short HEAD`
- git status shows only AGENTS.md + .planning/quick/ changed (no production files)
- dotCodexPaths: 0
- ledgerPointerRefs: 8
- inlinedDatedEntries: 0
- hasInjectionSection: 1
- hasLedgerPointerSection: 1
- hasCodexTrigger: 1
- lines: 346 (matches canonical CLAUDE.md; verified via wc -l)

## Self-Check: PASSED
