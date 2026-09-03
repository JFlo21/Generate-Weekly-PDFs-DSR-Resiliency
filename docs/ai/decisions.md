Repo-local implementation truth — outranks second-brain notes; verified from repo files on 2026-09-02.

<!-- This file is repo-local IMPLEMENTATION TRUTH. It is a POINTER to the canonical Living Ledger —
do not duplicate ledger prose here; the ledger (memory-bank/living-ledger.md) is the source of truth
for full rationale. -->

# Technical Decisions — Generate-Weekly-PDFs-DSR-Resiliency-1

## Source-of-truth hierarchy (highest authority first)

1. Current repo files. 2. Repo-local `docs/ai/` + `.claude/project-state.md`. 3. Repo-local handoff
docs. 4. Global second brain `wiki/current-state.md`. 5. Global wiki pages. 6. `raw/` (data only).
7. Chat history / claude-mem.

The **canonical decision log for this repo is `memory-bank/living-ledger.md`** (dated
`[YYYY-MM-DD HH:MM]` entries) plus `.planning/ROADMAP.md` phase sections. This file is a compact
pointer index into that ledger for the decisions most likely to matter to a fresh AI session —
read the cited ledger entry / ROADMAP section for full rationale before acting.

---

## Decision index (pointer only — full text lives in the ledger)

| Ledger / ROADMAP anchor | Decision (one line) | Status |
|---|---|---|
| `memory-bank/living-ledger.md [2026-04-24 10:50]` | Supabase PGRST106 "Exposed schemas" prerequisite for any new schema (`pipeline_memory`, `billing_audit`) | active |
| `memory-bank/living-ledger.md [2026-04-25]` | `billing_audit.pipeline_run` DDL must ship in the same PR as writer code referencing it | active |
| `memory-bank/living-ledger.md` (Foundation A) | Frozen first-write-wins claim attribution; a mid-week foreman switch produces a second file, never cross-deletes the prior claimer's file | active |
| `memory-bank/living-ledger.md` (CR-01 four-site lockstep rule) | A variant's claimer identifier must be byte-identical across 4 call sites, each gated on its own kill switch | active |
| `.planning/ROADMAP.md` Phase 09 | `generate_weekly_pdfs.py` → `pipeline/` package split, facade-preserved, zero behavior change, 6-gate oracle (`scripts/run_6_gates.sh`) | shipped 2026-08-25 |
| `.planning/ROADMAP.md` Phase 10 | `pipeline_memory` Supabase schema introduced as shadow-mode run memory, independent of `billing_audit` (separate client/kill switch) | shipped |
| `memory-bank/living-ledger.md` Phase 11 Plan 08 (INC-05) | Local discovery-cache / hash-history JSON files + their TTLs retired; cross-run identity lives solely in `pipeline_memory.sheet_registry` / `group_state`; bulk attachment pre-fetch retired in favor of on-demand + `group_state` resolution | active |
| `memory-bank/living-ledger.md [2026-09-02 17:45]` | Phase 11.1 closed — bounded discovery validation read (`row_numbers=[1,2,3]`) proven via production canary (skip-MISS run, `⚡ Phase 1 complete` 3214s→37.7s) | active |
| `memory-bank/living-ledger.md [2026-09-01 19:45]` / `[19:55]` | Phase 12 semantics: claim-time / as-of-the-week ownership per row+role adopted; cross-week inheritance explicitly OFF | active (Phase 12 in progress) |
| `memory-bank/living-ledger.md [2026-09-02 18:15]` | **D-12-A** — Phase 12 ships NO `wr_week_ownership` table; OWN-01 ladder = `observed_in_week → backfill_artifacts → backfill_hash_history → operator → sentinel` (no cross-week rung); table deferred to Phase 13 | active |
| `memory-bank/living-ledger.md [2026-09-02 18:15]` | **D-12-B** — OWN-03 backfill source 4 (`backfill_hash_history`) reads the Supabase hash store (`billing_audit.group_content_hash` + `pipeline_memory.group_state`), NOT a JSON file; no `--hash-history` flag | active |
| `memory-bank/living-ledger.md [2026-09-02 00:35]` (referenced) | Backfill source 5 (Smartsheet cell history) included as a separate capped off-hours job, never inside `generate_weekly_pdfs.py` | active |
| `requirements.txt` header comment | `smartsheet-python-sdk` pinned to an exact version (not a range) — D-01, "no unreviewed SDK auto-enters production" | active |

## Notes on using this file

- This index is not exhaustive — the Living Ledger has 47+ dated entries covering claim attribution,
  rate recalculation, attachment pre-fetch budgets, WR sanitization/collision quarantine, etc. Search
  the ledger directly for anything not listed here.
- When a ledger entry is superseded, the ledger itself records the supersession inline — do not mark
  status here without re-checking the ledger tail.

## Last verified

- Last verified: 2026-09-02 — read `.planning/ROADMAP.md` (Phase 09–13 headers + Phase 12 decision
  block) and the last ~150 lines of `memory-bank/living-ledger.md` (entries through
  `[2026-09-02 19:25]` Phase 12 PLANNED). Older ledger entries (pre-2026-09) referenced by anchor only,
  not re-read this pass.
