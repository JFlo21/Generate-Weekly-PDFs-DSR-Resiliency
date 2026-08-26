# Phase 11: Incremental Read + Affected-Group Regeneration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-26
**Phase:** 11-incremental-read-affected-group-regeneration
**Mode:** advisor (calibration `full_maturity`, advisor model sonnet); started 2026-08-26
05:38Z, paused via `/gsd-pause-work` after all four `gsd-advisor-researcher` tables returned
(persisted as `11-ADVISOR-*.md`), resumed 2026-08-26 ~07:10 CDT from
`11-DISCUSS-CHECKPOINT.json` without re-dispatching research.
**Areas discussed:** Read watermark & safety window; Affected-group regen & row source;
Parity proof harness (INC-04); Rollout, kill switch & retirement order

---

## Read watermark & safety window

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed 15-min overlap, capture-time watermark | Persist `last_read_at` captured before the read; subtract `SAFETY_WINDOW` only in the query; ship the seven FULL-read escalation triggers in the same change | ✓ |
| Self-scaling one-interval overlap | Window grows with elapsed time since last successful run, capped; self-heals missed runs but harder to test | |
| Version-gated + full-sheet read on change | `if_version_after` only; changed sheets read in full. No deletion gap, no row savings | |
| Exact watermark, zero overlap | `rows_modified_since = last_read_at` exactly. Simplest; unbounded boundary row-loss risk | |

**User's choice:** Fixed 15-min overlap, capture-time watermark (advisor recommendation)
**Notes:** Advisor flagged that the design-spec draft persists `now − SAFETY_WINDOW`, which
double-subtracts run-over-run; the capture-time rule supersedes the spec on that point.
`rowsModifiedSince` never surfaces deletions (verified SDK 4.3.0) → deletions stay with the
weekly deep run. No follow-up needed.

---

## Affected-group regen & row source

| Option | Description | Selected |
|--------|-------------|----------|
| C. Hybrid — membership from `row_state`, scoped full re-fetch | Affected (wr, week) set picks which sheets/groups to touch; full read of only those sheets; unmodified grouping/excel path. Zero schema change | ✓ |
| B. `row_state`-exclusive, raw fields only | Extend schema with raw columns; re-run attribution/pricing at read time. Migration + parity work this phase | |
| A. `row_state`-exclusive, raw + derived | Store resolved foreman/price/variant too. Zero Smartsheet calls, but risks silently changing billing output | |
| D. Status-quo-plus | Keep full grouping; affected set becomes a parity assertion only. No efficiency win | |

**User's choice:** C. Hybrid (advisor recommendation)
**Follow-up asked:** Is Option B in Phase 11 scope or deferred?
**Follow-up answer:** Defer B out of Phase 11 — later slice once C is clean for 5
consecutive runs (recorded as a deferred idea). INC-02's "rows from `row_state`" clause is
therefore an explicit, approved partial for this phase.

---

## Parity proof harness (INC-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Shadow-incremental, in-process | Both paths from one snapshot inside each run; compare group list + content hashes; verdict persisted in `run_ledger.notes`; sub-budgeted | ✓ |
| Dual-output + `compare_control_run.py` | Generate both `.xlsx` sets and diff byte-level; doubles openpyxl cost — better paired with the weekly deep run | |
| Shadow-incremental + dual-output on weekly deep run | In-process hash parity every frequent run plus a byte-level dual-output check on the Monday deep run | |
| Replay harness | Capture a run, replay incremental offline. Deterministic but not scheduled-run evidence; new subsystem | |

**User's choice:** Shadow-incremental, in-process (advisor recommendation)
**Follow-up asked:** During the shadow window, issue the real `if_version_after` /
`rows_modified_since` reads too, or derive the candidate set purely from the full snapshot's
upsert result?
**Follow-up answer:** Issue real delta reads in shadow — proves the watermark + escalation
logic end-to-end before the flag flips; adds a read-side assertion (every hash-changed row
must appear in the delta read). Extra `get_sheet` calls are sub-budgeted and fail-open.
Alternating runs ruled out (Phase 10 lesson); dual-output kept in reserve for the deep run.

---

## Rollout, kill switch & retirement order

| Option | Description | Selected |
|--------|-------------|----------|
| A + D: separate write-flip PR first; frequent-only cron; retirement PR after parity | `RUN_MEMORY_WRITE_ENABLED` flips in its own operator-gated PR (WR-01/WR-04/IN-01). Incremental flag scoped to `production_frequent`; fallbacks logged in `run_ledger.mode`; INC-05 as a later PR | ✓ |
| A + C: separate write-flip PR; manual-dispatch opt-in first, then promote | Same write-flip isolation, first incremental runs via `workflow_dispatch` + `advanced_options` until N clean runs | |
| B + D: bundle write-flip into Phase 11 PR; frequent-only cron | One larger protected-area PR; fewer review cycles; mixed blast radius | |
| B + C: bundle write-flip; manual-dispatch opt-in first | Single PR, incremental starts manual-only | |

**User's choice:** A + D (advisor recommendation; the two advisor "recommended" rows compose)
**Follow-up asked:** Where does the write-flip PR live relative to Phase 11?
**Follow-up answer:** Phase 11 plan 01 = WR-01 / WR-04 / IN-01 fixes; the workflow flip PR
is cut from that work as a separate small owner-approved PR; later plans assume it landed
(planner inserts a human-verify checkpoint before the first plan needing populated memory).

---

## Closing

**"Ready to create context?"** → Create context.

## Claude's Discretion

- Exact config constant names/defaults (`SAFETY_WINDOW_MINUTES=15`,
  `RUN_MEMORY_SHADOW_MAX_MINUTES`, per-call timeout) following the existing sub-budget pattern
- Affected-set → sheet mapping and per-consumer scoping of `all_rows` users in incremental mode
- Streak query, `parity_details` shape, Sentry event shape for a parity `fail`
- Fixture + live-verification design for success criterion 3 (deep-run deletion / formula-only repair)
- Module layout for the shadow comparison

## Deferred Ideas

- Option B `row_state`-exclusive raw-field sourcing (schema extension) — later slice after C is clean
- Dual-output byte-level parity on the weekly deep run — optional hardening
- Replay harness — CI supplement, not scheduled-run evidence
- Self-scaling overlap window — only if cadence changes
- Manual-dispatch-only first incremental run — not chosen; available ad hoc
- 44-open-PR backlog triage — separate pass

## Reviewed Todos

- Folded: `2026-08-25-run-memory-review-followups.md` (WR-01 / WR-04 / IN-01 → plan 01)
- Not folded: `2026-08-25-fix-snapshot-store-int-arg-type.md` (unrelated mypy finding)
