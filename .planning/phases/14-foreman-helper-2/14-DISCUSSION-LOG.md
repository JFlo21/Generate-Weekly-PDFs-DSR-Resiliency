# Phase 14: Foreman Helper #2 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-05
**Phase:** 14-foreman-helper-2
**Areas discussed:** capability gate & required fields · same-row multi-role semantics · output
identity (per-slot vs merged) · attribution/ownership & DB contract · mapping-cache
revalidation · rollout flag & rollback · downstream consumers

**Mode note:** Per Juan's 2026-09-05 request, the owner was not interviewed for implementation
detail ("the same way we implemented Helping Foreman" is the default reference). The three
owner decisions (Intake 8 exclusion, optional-column skip, extend-not-rebuild) were supplied in
the request. Every other selection below was made by the planning session from repository
evidence and is marked `[repo]`; genuinely unresolved business decisions are marked `[OPEN]`
and were NOT auto-selected.

---

## Capability gate & required fields

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror `sheet_has_vac_crew_columns` | Capability = name + completed + dept columns mapped; skip Helper #2 path otherwise | ✓ [repo] |
| Mirror Helper #1's 4-column log check | Log-only; detection silently runs on partial schemas | |
| Require all six Helper #2 columns | Makes optional metadata mandatory; rejects valid sheets | |

**Choice:** VAC-crew-style gate. **Notes:** Helper #1 never gates on `Active?`/`Email`; owner
decision D-14-02 forbids making optional fields required.

---

## Same-row multi-role semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Hold the conflicting row with visibility | Row out of every file this run; distinct log reason; run-summary/Sentry count | recommended, **[OPEN — Juan]** |
| Helper #1 wins | Priority rule | |
| Both helper files | Double credit; violates exactly-once | |
| Primary keeps the row | Drops helper credit | |
| Abort the run (prototype `HelperAssignmentConflictError`) | One bad row blocks all output | |

**Choice:** none — recorded as O-14-A. Only the conflict-handling task is blocked.

---

## Output identity: per-slot variant vs merge into the Helper #1 file

| Option | Description | Selected |
|--------|-------------|----------|
| Per-slot variant / filename token | Mirrors Helper #1 mechanics; Helper #1 files byte-identical (HLP-02) | ✓ [repo] |
| Merge Helper #2 rows into the person's existing `_Helper_` file | One file per person; changes Helper #1 file content and hashes | |

**Choice:** per-slot. **Notes:** consequence — the same person in slot 1 on some rows and slot 2
on others in one WR/week gets two files; flagged for Juan's confirmation at the checkpoint
(non-blocking).

---

## Attribution / ownership & DB contract

| Option | Description | Selected |
|--------|-------------|----------|
| New frozen role column pair + RPC return columns (additive, DROP-first RPC rebuild) | Helper #2 never overwrites `frozen_helper`; Phase 12 rules apply | ✓ [repo], migration gated by `checkpoint:decision` |
| Reuse `frozen_helper` for both slots | Overwrites/impersonates Helper #1 | |
| No freeze for Helper #2 at all | Diverges from Helper #1; loses ownership stability | fallback only when the column is absent |

**Choice:** additive role columns with a tolerant fallback so generation and migration can be
sequenced independently.

---

## Mapping-cache revalidation

| Option | Description | Selected |
|--------|-------------|----------|
| Mapping-schema marker → one bounded full revalidation | Pre-Helper-#2 registry mappings fall through once | ✓ [repo] |
| Permanent full rediscovery | Reintroduces the Phase 11.1 wall-clock regression | |
| Do nothing | Version-unchanged sheets never gain Helper #2 capability | |

---

## Rollout flag & rollback

| Option | Description | Selected |
|--------|-------------|----------|
| One additive env flag, default off; runbook preconditions | Real deployment boundary; Actions edit is a separate approval | ✓ [repo] |
| Prototype triple gate (`HELPER2_ENABLED` + `SOURCE_PROVEN` + `JOB_PRODUCER_PROVEN`, import fails closed) | Operational preconditions encoded as import-time gates | |
| No flag; ship live | No boundary for pilot/rollback | |

---

## Downstream consumers

| Option | Description | Selected |
|--------|-------------|----------|
| Extend every variant-parsing interface together (excel, change_detection, cleanup, publish script, portal labels) | No orphaned parser; Sentry unknown-variant guard stays quiet | ✓ [repo] |
| Generator only | Publish script logs unknown variant; portal shows raw token | |

---

## Claude's Discretion

- Internal metadata names, variant tokens, flag name, snapshot column names, log strings, test
  placement; whether the attribution-freeze slice trails the generation slice.

## Deferred Ideas

- Helper #1 `"NA"` quirk; Intake 8 discovery status (currently discovered); RA `Assigned Helper 2?`
  automation and `Helper #2 Job [#]` producer; Backup 2 columns; `row_state` hash inclusion when
  incremental is enabled; Phase 13 `wr_week_ownership` representation of the Helper #2 role.
