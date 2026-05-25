# Sub-project D — Primary-Workflow Primary Claim Attribution (Design)

**Date:** 2026-05-25
**Status:** Approved (brainstorming complete; awaiting implementation plan)
**Author:** Claude Code session (brainstorming skill)
**Branch:** `feat/subproject-d-primary-claim-attribution`

## Context

This is the fourth consumer in the "universal per-line-item claim
attribution" effort. Every Excel file is partitioned by the FROZEN
foreman/helper/vac-crew member who actually claimed each line item,
sourced from `billing_audit.attribution_snapshot` via Foundation A's
`resolve_claimer`. Sequencing A → B → C → D → E:

- **Foundation A** (read layer + HOLD contract): SHIPPED.
- **Phase 1.1** (subcontractor helper-shadow): SHIPPED.
- **Sub-project B** (subcontractor PRIMARY → `_ReducedSub_User_<name>` /
  `_AEPBillable_User_<name>`): MERGED (#215) + helper-exclusion hotfix (#216).
- **Sub-project C** (vac_crew → `_VacCrew_<name>`, all sheets): MERGED (#219).
- **Sub-project D** (primary-workflow NON-subcontractor primary
  partitioning): **THIS DOCUMENT.** Highest blast radius — touches the
  core primary grouping and the largest attachment migration.
- **Sub-project E** (Supabase hash-store migration + strip
  `_<hash>`/`_<timestamp>` tokens from filenames): NOT STARTED, last.

D is the core primary path: every non-subcontractor WR currently produces
exactly one bare primary Excel file on `TARGET_SHEET_ID`. With D enabled,
each becomes one-or-more `_User_<claimer>` files (one per frozen claimer),
and the legacy bare file must be migrated away.

## Goal

Partition the production primary Excel files by the FROZEN primary foreman
who claimed each line item. A WR+week whose rows were claimed by two
different foremen produces two files, one per claimer, each containing only
that claimer's completed line items. When attribution is unavailable
(no frozen row yet, kill switch off, or Supabase outage), fall back to the
current foreman and still generate — the core primary path never withholds
billing output.

## Key codebase findings (verified against the C-merged base, commit 8f546ae)

These are the facts the design relies on. All line numbers are
approximate and will drift; they are anchors, not contracts.

1. **Foundation A is D-ready.** `billing_audit/writer.py`
   `ROLE_BY_VARIANT['primary'] = 'primary_foreman'`. Passing variant
   `'primary'` to `resolve_claimer` resolves the `primary_foreman` column.
   No `billing_audit/` change is needed (honors invariant #8).
2. **Emission foreman propagates to `__current_foreman`.** In
   `group_source_rows` (~line 5746-5750) the `keys_to_add` loop sets
   `r_copy['__current_foreman'] = current_foreman or effective_user`.
   Whatever foreman D puts in the emission tuple's 3rd element becomes the
   group's `__current_foreman`.
3. **The parser already supports D's filename.** `build_group_identity`
   parses `..._User_<name>_<hash>` → `('primary', wr, week, name)` — the
   decommissioned activity-log "Primary+User" variant. D's *core* work
   needed no parser change. **(Updated post-implementation:** the final
   review surfaced a latent bug — when a claimer NAME contains a reserved
   token (e.g. "Pat Helper"), the old fixed-order variant scan misparsed
   `_User_Pat_Helper` as `helper`. So D ultimately *did* harden the parser:
   `build_group_identity` now dispatches on the EARLIEST reserved-token
   position. See the post-merge fix commit + the Living Ledger entry. The
   "ZERO parser changes" framing held only for the originally-produced
   filenames, not for reserved-token-in-name edge cases.)**
4. **The legacy `User` column is never populated in production.** Only
   `__effective_user` is set (~line 4620). `first_row.get('User')` (the
   legacy primary identifier source at ~line 8054) returns `None` in
   practice, so today's primary files are BARE
   (`WR_{wr}_WeekEnding_{MMDDYY}_{ts}_{hash}.xlsx`) with history key
   `{wr}|{week}|primary|` (empty identifier). The migration is therefore a
   clean bare → `_User_<claimer>` transition, with no real-world
   `User`-tag collision.
5. **`generate_excel` primary DISPLAY is D-ready, but the FILENAME suffix
   is NOT.** The primary display branch (~line 6408) sets
   `display_foreman = current_foreman` (= `__current_foreman`, the
   partition-key claimer when on / `effective_user` when off) — no change
   needed. HOWEVER, the filename-suffix branch (~line 6221-6223) sets
   `variant_suffix = ''` UNCONDITIONALLY for the primary variant — it
   ignores the identifier entirely. Without a fix, every per-claimer
   primary group would generate to the SAME bare filename
   `WR_..._WeekEnding_..._{ts}_{hash}.xlsx` (collision/overwrite) and the
   `_User_<claimer>` identity would never round-trip. **D MUST modify this
   branch** to emit `_User_{sanitized_claimer}` when
   `PRIMARY_CLAIM_ATTRIBUTION_ENABLED and __current_foreman`, mirroring the
   `vac_crew` branch at ~line 6205-6220. (The decommissioned activity-log
   path that the parser still reads no longer has a live filename builder.)
6. **WR matchers asymmetry.** `_key_matches_excluded_wr` (EXCLUDE_WRS,
   ~line 5886) already has `or suffix.startswith(f"{wr}_USER_")`.
   `_key_matches_wr` (WR_FILTER, ~line 5833) does NOT. D must add the
   `_USER_` clause to `_key_matches_wr`. Both keep `suffix == wr` for the
   OFF/legacy bare key.

## Architecture

### Scope

**In scope.** Only the production primary emission:
`RES_GROUPING_MODE in ('helper', 'both')`, `not is_subcontractor_row`,
`not valid_helper_row` — the branch at ~line 5303-5305 that today emits
`('primary', f"{week_end_for_key}_{wr_key}", None)`.

**Out of scope.**
- `RES_GROUPING_MODE == 'primary'` legacy mode (non-production; it lumps
  helper + subcontractor rows into one primary file per WR, where
  partitioning by `primary_foreman` would be semantically wrong). Stays
  bare/legacy.
- Subcontractor primary rows — Sub-project B already owns them via
  `_ReducedSub_User_` / `_AEPBillable_User_`; the bare primary for sub
  rows is already suppressed.
- Helper rows — excluded from primary by the existing `valid_helper_row`
  cascade.
- VAC crew — Sub-project C owns `_VacCrew_<name>`.

### Filename / key / identity shapes

| State | Group key | Filename | Identity tuple |
|-------|-----------|----------|----------------|
| D ON  | `{week}_{wr}_USER_{sanitized_claimer}` | `WR_{wr}_WeekEnding_{MMDDYY}_{ts}_User_{claimer}_{hash}.xlsx` | `(wr, week, 'primary', claimer)` |
| D OFF | `{week}_{wr}` | `WR_{wr}_WeekEnding_{MMDDYY}_{ts}_{hash}.xlsx` | `(wr, week, 'primary', None)` |

`build_group_identity` already parses both shapes (finding #3).

### Partition model — fallback-to-current, never HOLD

D reuses Foundation A's `resolve_claimer('primary', …)` in a parallel
pre-pass (Approach 1). Consumption at emission:

- `action == 'use'` → frozen claimer (`outcome.name`), or `no_history`
  collapses to the current `effective_user` inside `resolve_claimer`.
- `action == 'hold'` (Supabase `fetch_failure`) → **use current
  `effective_user` and still generate.** D does NOT defer, does NOT call
  `record_attribution_hold`, and emits no end-of-run hold summary.
- map-miss / disabled / any pre-pass fault → use current `effective_user`.

Empty resolved claimer → `'Unknown Foreman'` sentinel (mirrors B's
Codex-P1 fix) so the `_USER_` suffix builder never receives an empty
identifier.

**Rationale for no-HOLD (operator-chosen).** D covers EVERY
non-subcontractor WR. Under HOLD, a full Supabase outage would suppress
ALL primary billing files for that run. The core primary path prioritizes
availability: it always emits, attributing to the current foreman when the
frozen claimer can't be read. This deliberately differs from B (sub
primary HOLDs) — B's blast radius is limited to subcontractor WRs.

### Configuration — two new default-on, workflow-pinned kill switches

- **`PRIMARY_CLAIM_ATTRIBUTION_ENABLED`** (default `'1'`; truthy
  `1`/`true`/`yes`/`on`). Gates the partitioning AND all four identity
  surfaces (pre-pass, emission, main-loop site a, sites b/c). OFF ⇒
  byte-identical legacy bare primary at every surface.
- **`LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED`** (default `'1'`). Gates
  the destructive migration (forced bare-primary attachment cleanup +
  one-time hash prune). OFF ⇒ TARGET cleanup byte-identical to today.

Both are pinned in `.github/workflows/weekly-excel-generation.yml` and
documented in `website/docs/reference/environment.md` (invariant #9).

## Components / change surface

All emission/identity changes are gated on
`PRIMARY_CLAIM_ATTRIBUTION_ENABLED`; OFF reproduces exact legacy behavior.

### 1. Pre-pass (`group_source_rows`)

Add `_primary_claimer_map: dict` keyed by `__row_id`, beside B's
`_sub_primary_claimer_map` and C's `_vac_crew_claimer_map` (~line 5077).

- Guard: `BILLING_AUDIT_AVAILABLE and PRIMARY_CLAIM_ATTRIBUTION_ENABLED`.
- Eligible rows: completed (`is_checked(Units Completed?)`), has
  `Work Request #` + parseable `Weekly Reference Logged Date`,
  `not r.get('__is_vac_crew')`, AND `not is_subcontractor`
  (`__source_sheet_id is not None and __source_sheet_id in
  _FOLDER_DISCOVERED_SUB_IDS` ⇒ excluded). `__row_id` must be `int`.
- Bounded `ThreadPoolExecutor(max_workers=min(PARALLEL_WORKERS, n))`;
  single-row groups skip the executor (invariant #7).
- Per row: `resolve_claimer('primary', effective_user, wr=…,
  week_ending=<date>, row_id=…, enabled=PRIMARY_CLAIM_ATTRIBUTION_ENABLED)`.
- Outer try/except → on failure, `_primary_claimer_map = {}` (all rows
  fall back to current at emission).

### 2. Emission (production primary branch, ~line 5303-5305)

Replace the single `('primary', f"{week}_{wr}", None)` append with a
kill-switch branch:

- **ON:** read `_primary_claimer_map.get(r.get('__row_id'))`.
  - `outcome.action == 'use'` → `claimer = outcome.name or effective_user
    or 'Unknown Foreman'`.
  - else (`hold` / miss / disabled / `None`) → `claimer = effective_user
    or 'Unknown Foreman'`.
  - `claimer_sanitized = _RE_SANITIZE_IDENTIFIER.sub('_', claimer)[:50]`.
  - Emit `('primary', f"{week_end_for_key}_{wr_key}_USER_{claimer_sanitized}",
    claimer)`. Log `🧑 PRIMARY GROUP CREATED` once per new key.
- **OFF:** emit legacy `('primary', f"{week_end_for_key}_{wr_key}", None)`.

### 3. Site (a) — main-loop identity (~line 8051-8057, primary `else`)

- **ON:** `_pf = first_row.get('__current_foreman', '')`;
  `identifier = file_identifier = _RE_SANITIZE_IDENTIFIER.sub('_', _pf)[:50]
  if _pf else ''`.
- **OFF:** legacy `first_row.get('User')` path unchanged.
- `history_key = f"{wr_num}|{week_raw}|{variant}|{identifier}"` (unchanged
  shape — identifier now carries the claimer when ON).

### 4. Sites (b) `valid_wr_weeks` (~line 8786) and (c) `current_keys` (~8994-9013)

Both already branch per-variant for vac_crew / reduced_sub / aep_billable.
Add the same ON-gated primary derivation: `_pf =
group_rows[0].get('__current_foreman', '')`; `file_id` /`_ident` =
sanitized `_pf` when `PRIMARY_CLAIM_ATTRIBUTION_ENABLED and _pf` else `''`.
This keeps the 4-tuple (site b) and pipe-key (site c) byte-identical to
site (a) and to the `_User_<name>` filename — the four-site lockstep
(invariant #1).

### 5. WR matchers (`group_source_rows`, ~line 5833 / 5886)

- `_key_matches_wr` (WR_FILTER): add `or suffix.startswith(f"{wr}_USER_")`.
- `_key_matches_excluded_wr` (EXCLUDE_WRS): already has it — no change.
- Both retain `suffix == wr` so the OFF/legacy bare key still matches.
  (Invariant #3 — mirror-matcher rule.)

### 6. `generate_excel`

- **Filename suffix (~line 6221-6223) — REQUIRED change.** Replace the
  unconditional `variant_suffix = ''` for the primary variant with:
  when `PRIMARY_CLAIM_ATTRIBUTION_ENABLED and first_row.get('__current_foreman')`,
  set `variant_suffix = f"_User_{_RE_SANITIZE_IDENTIFIER.sub('_', _pf)[:50]}"`;
  else `variant_suffix = ''`. Mirrors the `vac_crew` branch exactly. OFF ⇒
  bare suffix (legacy), so byte-identical. This is what produces the
  `_User_<claimer>` filename that `build_group_identity` round-trips and
  that distinguishes per-claimer files on disk / on the sheet.
- **Display foreman — no change.** The primary display branch already uses
  `current_foreman` (the claimer when on, `effective_user` when off).

## Migration (gated on `LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED`)

### 7a. Forced bare-primary attachment cleanup on TARGET_SHEET_ID

- New shared helper `_build_primary_wr_scope(groups) -> set[str]`: the set
  of WR numbers that have a partitioned `{week}_{wr}_USER_{claimer}`
  primary group in this run (i.e., WRs whose bare predecessor should be
  cleaned).
- Add `primary_wr_scope: set[str] | None = None` param to
  `cleanup_untracked_sheet_attachments` (alongside `sub_wr_scope` /
  `sub_legacy_primary_variants`).
- At the TARGET call site only: for an attachment whose parsed identity is
  `(wr, week, 'primary', None | '')` (bare) AND `wr in primary_wr_scope`:
  delete it unconditionally (regardless of `KEEP_HISTORICAL_WEEKS`)
  **UNLESS** that identity is in `valid_wr_weeks` (live-identity
  exemption). The exemption protects a bare-primary file the current run
  legitimately produced (e.g., an overlapping WR still emitting bare
  primary because attribution was disabled for those specific rows).
- Gated on `PRIMARY_CLAIM_ATTRIBUTION_ENABLED and
  LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED`. OFF ⇒ no behavior change.
- The PPP sheet (`SUBCONTRACTOR_PPP_SHEET_ID`) is NOT in scope — D is
  non-subcontractor only; pass `primary_wr_scope=None` for PPP.

### 7b. One-time hash-history prune

- New `_run_subproject_d_hash_prune(hash_history, groups) -> bool`.
- New `SUBPROJECT_D_HASH_PRUNE_VERSION = 1` constant + `_subproject_d_prune_version`
  sentinel persisted in `hash_history.json` (distinct from the
  Phase-1.1 / B / C sentinels).
- Drops legacy empty-identifier primary history keys `{wr}|{week}|primary|`
  for WRs in `_build_primary_wr_scope(groups)`.
- **Gated on `PRIMARY_CLAIM_ATTRIBUTION_ENABLED`** (invariant #5 — OFF must
  not delete now-active legacy keys; when OFF the bare key is the live key).
- Returns a "mutated" bool (True when it ran the body / advanced the
  sentinel; False on the idempotent early-return) that is OR'd into
  `_hash_history_migration_dirty`, so the sentinel persists even on a
  no-update run (B's Codex-P2 fix).
- Benign drop-path: a dropped hash costs at most one regeneration, never
  data loss — so no live-identity exemption is needed. Scoped to in-scope
  WRs to avoid touching legacy `primary`-mode keys for unrelated WRs.

### Why both 7a and 7b

They are independent surfaces. Without 7a, every migrated WR keeps a
duplicate-looking bare file on TARGET forever. Without 7b, the stale
history key lingers harmlessly but accumulates.

## Error handling & edge cases

- **Pre-pass failure** (any exception) → empty `_primary_claimer_map` →
  all rows use-current at emission. A plumbing fault can never suppress a
  primary file.
- **Empty claimer** → `'Unknown Foreman'` sentinel before the `_USER_`
  suffix is built.
- **Thread safety** — reuse B/C's bounded executor + memoized,
  thread-safe `billing_audit` client; per-op counters already lock-guarded.
- **No HOLD path** — `action == 'hold'` consumed as use-current;
  `record_attribution_hold` never called for `'primary'`.
- **Two claimers, same WR+week** → two coexisting `_User_<a>` / `_User_<b>`
  files. The claimer is in the identity tuple, so they are distinct
  identities; the per-identity cleanup keeps both and never cross-deletes
  (Foundation A invariant #2).
- **D OFF** → byte-identical legacy at every surface: bare `{week}_{wr}`
  key, `''` identifier, bare filename, `{wr}|{week}|primary|` history key,
  no migration cleanup, no prune.
- **Mixed attribution state on one WR** (some rows partitioned, an
  overlapping bare file still live) → `valid_wr_weeks` exemption protects
  the live bare file from 7a.
- **WR_FILTER / EXCLUDE_WRS** now both match `{wr}_USER_<name>`.

## Testing strategy

TDD red→green throughout. New file
`tests/test_primary_claim_attribution.py`, plus targeted extensions to
existing suites.

- **End-to-end `group_source_rows`** (synthetic rows + mocked
  `resolve_claimer`): partition-by-claimer; two-claimer coexistence; OFF
  byte-identical bare key; fall-back-on-`hold` still emits under current
  foreman with NO hold recorded.
- **`build_group_identity`** `_User_<name>` primary round-trip regression
  (claimer names with underscores; a claimer literally named with a
  `Helper`/`VacCrew` substring still parses as `primary`).
- **WR matchers** — both `_key_matches_wr` and `_key_matches_excluded_wr`
  match `{wr}_USER_<name>` and still match the bare `{wr}`.
- **Four-site source-grep invariants** (the `TestProductionCodeSiteInvariants`
  pattern): assert each of the four identity sites + both matchers carry
  the primary `__current_foreman` / `_USER_` derivation, gated on the kill
  switch.
- **Migration:**
  - 7a forced bare-primary cleanup E2E: in-scope bare deleted; live
    per-claimer `_User_` file NOT deleted; overlapping live bare exempt via
    `valid_wr_weeks`; OFF ⇒ no deletion.
  - 7b prune idempotency + version sentinel + kill-switch gating
    (OFF ⇒ no prune) + migration-dirty save on a no-update run + scope
    discipline (unrelated WRs untouched).
- **Pre-pass concurrency** — N concurrent resolves preserve counter
  accuracy / no silent drops / no exceptions.
- **Living-Ledger-entry-present** test.
- **Verification gate:** `pytest tests/` green (baseline 814 passed /
  26 skipped / 60 subtests), `python -m py_compile generate_weekly_pdfs.py`,
  and a `TEST_MODE=true` smoke run.

## Invariants honored (from the handoff)

1. **CR-01 four-site lockstep** — claimer identifier byte-identical at
   main-loop `identifier`/`file_identifier`/`history_key`,
   `valid_wr_weeks`, `current_keys`, and the `build_group_identity` parser
   (parser already conformant — finding #3).
2. **Kill-switch gates all identity surfaces** — OFF reproduces exact
   legacy.
3. **Mirror-matcher rule** — extend `_key_matches_wr` for `_USER_`
   (`_key_matches_excluded_wr` already done).
4. **Mutual exclusion** — D's emission is already scoped to
   `not is_subcontractor_row and not valid_helper_row`; vac/helper/sub do
   not double-emit primary.
5. **One-time prune** — distinct version sentinel; gated on the kill
   switch (OFF doesn't delete now-active legacy keys); returns a "mutated"
   bool wired into `_hash_history_migration_dirty`.
6. **HOLD policy** — D deliberately does NOT hold (operator decision for
   the core path); fall-back-to-current + generate.
7. **Per-row attribution I/O in a bounded pre-pass**, never the hot loop.
8. **`billing_audit/` not modified** — `resolve_claimer('primary', …)` is
   already supported.
9. **New kill switches workflow-pinned + documented.**

## Out of scope / explicitly deferred

- Sub-project E (Supabase hash-store migration + stripping
  `_<hash>`/`_<timestamp>` filename tokens). Until E ships, the hash stays
  in filenames.
- `RES_GROUPING_MODE == 'primary'` legacy-mode partitioning.
- Any `billing_audit/` schema or reader change.
