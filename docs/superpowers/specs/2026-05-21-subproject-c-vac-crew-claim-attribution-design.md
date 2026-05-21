# Sub-project C — VAC Crew Claim Attribution (Design)

- **Status:** approved (design), pending implementation plan
- **Date:** 2026-05-21
- **Depends on:** Foundation A (`billing_audit.writer.resolve_claimer` +
  HOLD contract, [2026-05-20 13:45]); Sub-project B (the per-frozen-claimer
  partition pattern, [2026-05-21 09:21])
- **Sequencing:** A → B → **C** → D → E. C is the third consumer of
  Foundation A. E (Supabase hash-store migration + stripping
  `_<hash>`/`_<timestamp>` filename tokens) remains **last**; C therefore
  **retains** the existing hash-in-filename + `hash_history.json`
  change-detection mechanism unchanged.

## 1. Goal

Re-partition the `vac_crew` Excel files so each file holds only **one
frozen vac-crew claimer's** completed line items, named
`_VacCrew_<name>`, mirroring how B partitions subcontractor primary
files. Attribution is **frozen first-write-wins per row** via
`billing_audit.attribution_snapshot.frozen_vac_crew` (already captured by
`freeze_row`; C only *consumes* it).

**Why:** today a WR+week produces ONE `{week}_{wr}_VACCREW` group holding
every crew member → a single `_VacCrew` file. If two crew members work the
same WR+week, their line items are commingled in one file and a member who
switches mid-week can be re-credited. Partitioning by the frozen claimer
fixes both.

## 2. Operator-approved decisions

1. **Scope = ALL vac_crew rows, every sheet** (subcontractor *and*
   original-contract). vac_crew is a cross-sheet concept and `freeze_row`
   captures `frozen_vac_crew` for all of them. (Unlike B, which was
   subcontractor-only.)
2. **Filename token = `_VacCrew_<name>`** (mirrors the helper-shadow
   `_Helper_<name>` convention; the legacy unpartitioned `_VacCrew` — no
   name — must still parse for migration cleanup).
3. **Partition model = fallback-to-current.** Rows with a frozen claimer
   group under that claimer; rows with no frozen claimer yet
   (`no_history`) fall back to the current `__vac_crew_name`. (Every row
   reaching the vac_crew block is `Vac Crew Completed Unit?` +
   `Units Completed?` checked.)
4. **Kill switches (new, default-on, workflow-pinned):**
   `VAC_CREW_CLAIM_ATTRIBUTION_ENABLED` (gates partitioning) and
   `VAC_CREW_LEGACY_CLEANUP_ENABLED` (gates destructive legacy cleanup).
   A vac_crew-scoped flag is correct because the subcontractor flag's name
   would mislead for original-contract vac crew. (A universal
   `CLAIM_ATTRIBUTION_ENABLED` flag was considered and deferred to an
   E-era consolidation to avoid re-scoping B's already-shipped flag.)
5. **Outage = HOLD.** On `resolve_claimer` `fetch_failure` the row is
   deferred (`record_attribution_hold`), no vac_crew file is emitted that
   run, and `summarize_attribution_holds()` fires once at end-of-run.
   Correctness over availability — a possibly mis-attributed billing file
   is worse than a late one. Mirrors B.

## 3. Architecture & data flow

```
completed vac_crew rows
   ↓  PRE-PASS (Approach A — bounded ThreadPoolExecutor,
   ↓  max_workers = min(PARALLEL_WORKERS, n); single-row groups skip the executor)
   resolve_claimer(variant="vac_crew", current=__vac_crew_name, *,
                   wr, week_ending=week.date(), row_id=__row_id,
                   enabled=VAC_CREW_CLAIM_ATTRIBUTION_ENABLED)
   → {__row_id: ResolveOutcome}      # NO Supabase I/O inside the grouping loop
   ↓  group_source_rows vac_crew block
   'use'        → claimer = frozen_vac_crew (or current on empty) → {week}_{wr}_VACCREW_{sanitized claimer}
   'no_history' → claimer = current __vac_crew_name              → same shape
   'hold'       → DEFER row + record_attribution_hold(wr, week.date(), 'vac_crew'); emit nothing
   map-miss / disabled → use current __vac_crew_name (NEVER hold)
```

The pre-pass placement and the "no per-row attribution I/O in the hot
loop" rule come from Foundation A / B ([2026-05-21 09:21] rule 2). A row
absent from the map (attribution disabled, pre-pass skipped, missing
`__row_id`, unexpected per-row error) resolves to use-current at
emission — **never** HOLD; only `resolve_claimer`'s own `fetch_failure`
HOLDs (so a plumbing fault can never silently suppress a billing file).

## 4. Touch points — CR-01 four-site lockstep + display + hash

The claimer identifier MUST be built identically at all four sites; drift
breaks attachment-identity matching or hash-history persistence
([2026-05-15] CR-01, extended by B).

| Site | Today (vac_crew) | Sub-project C |
|---|---|---|
| Group key / `__current_foreman` (emission) | `{week}_{wr}_VACCREW`; foreman unused | `{week}_{wr}_VACCREW_{sanitized claimer}`; `__current_foreman = claimer` |
| `valid_wr_weeks` cleanup tuple builder | identifier `''` | sanitized claimer |
| `current_keys` hash-prune set | `{wr}|{week}|vac_crew|''` | `{wr}|{week}|vac_crew|{sanitized claimer}` |
| `build_group_identity` parser | `VacCrew` → `vac_crew`, identifier `''` | extract claimer via span-join; **reorder the `VacCrew` branch ahead of the `Helper` scan** so a crew name containing the `Helper` token cannot misparse (B round-7 Codex lesson); legacy `_VacCrew` (no name) still yields identifier `''` |

`generate_excel`:
- filename `variant_suffix = '_VacCrew'` → `_VacCrew_{sanitized claimer}`
  (sourced from `__current_foreman`, set by the pre-pass).
- display **foreman = the attributed claimer (`__current_foreman`)**;
  `display_dept` / `display_job` stay from `__vac_crew_dept` /
  `__vac_crew_job`. (Do NOT regress to a row's current name — the
  [2026-05-21 12:35] dept-#/Job-# display-source lesson.)

Hash: the vac_crew **history-key** gains the claimer
(`{wr}|{week}|vac_crew|{sanitized claimer}`); the per-row **content** hash
keeps `__vac_crew_name` as-is (it is the change-detection content, not the
identity key).

Identifier sanitization reuses `_RE_SANITIZE_IDENTIFIER` (the same
sanitizer B uses), `[:50]`.

## 5. Configuration

| Var | Default | Effect |
|---|---|---|
| `VAC_CREW_CLAIM_ATTRIBUTION_ENABLED` | `'1'` | On ⇒ pre-pass + per-claimer partitioning. Off ⇒ today's single `_VacCrew` group (exact legacy behavior). |
| `VAC_CREW_LEGACY_CLEANUP_ENABLED` | `'1'` | On ⇒ destructive legacy-`_VacCrew` TARGET cleanup runs. Off ⇒ reverts to pre-C cleanup behavior. |

Both pinned in `.github/workflows/weekly-excel-generation.yml`, documented
in `website/docs/reference/environment.md`, and their resolved state
printed in the startup banner.

## 6. Migration (one-time, idempotent)

- **TARGET-only cleanup** (vac_crew never routes to PPP — confirmed in the
  upload-routing function): `cleanup_untracked_sheet_attachments` gains a
  vac_crew off-contract gate that deletes empty-identifier `_VacCrew`
  attachments for in-scope vac WRs, **with the `valid_wr_weeks`
  live-identity exemption** so a current per-claimer file is never deleted
  ([2026-05-19 23:45] data-loss lesson). In-scope WRs come from a shared
  `_build_vac_crew_wr_scope(groups)` (WRs with any `_VACCREW` group key) —
  one implementation used by both the cleanup call site and the prune (no
  drift, mirroring B's `_build_subcontractor_wr_scope`).
- **One-time hash prune** `_run_vac_crew_hash_prune` with a NEW
  `VAC_CREW_HASH_PRUNE_VERSION` constant + `_vac_crew_prune_version`
  sentinel (DISTINCT from B's `_subproject_b_prune_version` and Phase
  1.1's `_phase_prune_version`), dropping legacy `{wr}|{week}|vac_crew|''`
  orphans for in-scope vac WRs. It **returns the mutated-bool** and wires
  into the existing `_hash_history_migration_dirty` save path so it
  persists even on no-update runs ([2026-05-21 13:20] Codex P2 fix). New
  PII marker `"Vac crew hash-history prune"` registered in
  `_PII_LOG_MARKERS`. The prune is benign (drops a hash key → at most one
  regeneration, never data loss), so it carries no live-identity exemption.

## 7. Error handling & preemptive B-lessons

Apply the fixes already learned in B from the start (do not re-introduce
the bugs):
- **Empty-claimer → `'Unknown'` sentinel** before any `_VacCrew_<name>`
  key/filename is built (B Codex P1). `__vac_crew_name` is required for
  vac_crew detection so it is normally non-empty, but the fallback chain
  (`frozen or current or 'Unknown'`) guards the edge.
- **`.date()` normalization** on the `record_attribution_hold` call
  (Copilot #1).
- **Defensive raise** on the vac_crew suffix helper if it ever receives an
  unexpected variant (Copilot #2 convention for new variant-identity
  helpers).

`billing_audit/` is **NOT modified** — Foundation A already provides
`resolve_claimer`, `ROLE_BY_VARIANT["vac_crew"] = "vac_crew"`,
`record_attribution_hold`, and `summarize_attribution_holds`.

## 8. Out of scope

- Hash/timestamp filename-token stripping and the Supabase
  change-detection cutover — that is **Sub-project E**.
- Primary-workflow primary partitioning — **Sub-project D**.
- Any change to legacy `primary` / `helper` / subcontractor
  (`reduced_sub` / `aep_billable` / `*_helper`) variants, the upload
  routing, or the hash content algorithm.

## 9. Testing (TDD, true end-to-end)

New `tests/test_vac_crew_claim_attribution.py`, driving real production
code paths (per the [2026-05-20 00:26] rule 4 — static mirror classes do
NOT count):
- `group_source_rows` partitioning: frozen / no_history / hold / disabled
  / map-miss outcomes.
- `build_group_identity`: `_VacCrew_<name>` round-trip, a claimer name
  containing the `Helper` token parsing as `vac_crew`, legacy `_VacCrew`
  (no name) → identifier `''`.
- Two claimers on the same WR+week produce two coexisting files (no
  cross-delete).
- TARGET cleanup: in-scope empty-identifier `_VacCrew` deleted; a live
  per-claimer identity exempt; non-vac WRs preserved.
- Prune: return-value contract (mutated → True, idempotent → False) +
  idempotency + PII marker registered.
- HOLD records exactly one hold with a date-only week key.
- Non-vac variants unaffected (byte-identical grouping for
  primary/helper/subcontractor).
- Production-code-site invariants: source-level grep guards that the
  four identity sites carry the vac_crew claimer.

Full `pytest tests/` must remain green at every plan-completion checkpoint.
