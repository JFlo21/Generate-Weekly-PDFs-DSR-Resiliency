---
slug: legacy-attachment-cleanup
status: resolved
trigger: |
  Legacy wrong-claimer / hash-named subcontractor attachment backlog is
  not being cleaned up. After the 2026-05-27 Supabase schema fix restored
  correct frozen-claimer resolution, the workflow now regenerates the
  CORRECT per-week claimer file (e.g. _ReducedSub_User_Mark_Diaz) but the
  OLD wrong-claimer file from the broken period (e.g.
  _ReducedSub_User_Wade_Watson_<ts>_<hash>, hash-named) is NEVER deleted,
  so duplicates accumulate on TARGET_SHEET_ID=5723337641643908 and
  SUBCONTRACTOR_PPP_SHEET_ID=8162920222379908. Operator confirmed: old
  hash-named files from 2 days ago persist; only newly-(re)generated
  groups get clean names + supersede their own prior copy.
created: 2026-05-27
updated: 2026-05-27
goal: find_and_fix
---

# Debug Session: legacy-attachment-cleanup

## Symptoms

- **Expected:** After the attribution fix, each subcontractor WR+week+variant
  should have exactly ONE current file, named after the correct frozen
  claimer, and the old wrong-claimer / hash-named duplicate from the broken
  period should be removed.
- **Actual:** The correct new file (clean-named when E was briefly `'1'`) is
  ADDED, but the old wrong-claimer hash-named file persists alongside it →
  duplicates on both TARGET and PPP sheets.
- **Operator observations this session:**
  - Old hash-named files from ~2 days ago still on the preplanned pricing
    sheet + the subcontractor preplanned pricing sheet.
  - Reverting the E flag `1 -> 0` deleted nothing (correctly — the flag is
    not a delete trigger, and no run executed after the revert).
  - Some current-week groups (e.g. Jose Mendez, week ending 5/31) DID get a
    clean-named file; older unchanged groups kept their hash-named files.

## Evidence (this session — root cause investigation complete)

Run **26534649865** (scheduled, 2026-05-27 19:45 UTC, completed SUCCESS in
**23m32s** — confirming the bulk-RPC perf fix; was 1h26m / 3h-cancel before):

- `SUPABASE_HASH_STORE_AUTHORITATIVE=True` during this run (E was briefly
  flipped to `'1'` by commit 7077471; since reverted to `'0'` by 2b890af).
- **Bulk RPC works now:** 5 `lookup_attribution_bulk` POSTs, **0** per-row
  `lookup_attribution` POSTs, no `rpc_missing` warning. (Pre-fix run
  26487514913 had 138,478 per-row POSTs.)
- **Attribution fix verified end-to-end:** WR_90727774 historical weeks
  regenerated as `WR_90727774_WeekEnding_030126_ReducedSub_User_Mark_Diaz.xlsx`
  (CORRECT — was `_User_Wade_Watson` pre-fix). Supabase snapshot confirms
  frozen_primary = Mark Diaz for those weeks; Wade Watson only for 05-17/05-24.
- **Deletions this run:** 6 total `✅ Deleted:` lines, **all `_User_` primary,
  0 `ReducedSub`/`AEPBillable`**. All 6 were same-claimer hash→clean swaps via
  `🗑️ Removing 1 prior primary attachment` (e.g. Jose Mendez, John Flores).
- **End-of-run cleanup removed nothing:** `🧹 Variant pruning done:
  removed_variants=0, removed_off_contract=0` (TARGET + PPP) and
  `🧹 Cleanup complete: removed 0 stale file(s)`.
- **Garbage regenerated:** 118 `_User__NO_MATCH` + 29 `_User_Unknown_Foreman`
  clean-named files generated for old weeks whose SOURCE foreman is
  `#NO MATCH` / blank (snapshot had 935 #NO MATCH/blank `frozen_primary` rows).

Supabase (project `poeyztlmsawfoqlanucc`, schema `billing_audit`):
- Schema fix applied + verified earlier this session (migration
  `fix_lookup_attribution_multirole_and_add_bulk`): `lookup_attribution` now
  returns `(primary_foreman, helper, helper_dept, vac_crew, source_run_id)`;
  `lookup_attribution_bulk` created. Both GRANTed to `service_role`.
  `attribution_snapshot`: 142,806 rows, weeks 2025-06-29..2026-05-31, 99.3%
  real `frozen_primary`.

Code (`generate_weekly_pdfs.py`):
- `cleanup_untracked_sheet_attachments` def at **L2999**; identity-dedup loop
  at **L3266-3288** — groups attachments by parsed identity
  `(wr, week, variant, identifier=claimer)` via `build_group_identity`, sorts
  by timestamp token, **keeps newest per identity, removes older copies of the
  SAME identity only**.
- Off-contract delete paths exist for: bare-primary (`primary_wr_scope`,
  `not _identifier`, L3235-3243), sub legacy-primary (empty-identifier
  `_ReducedSub`/`_AEPBillable`), sub off-contract variant whitelist
  (`{'reduced_sub','reduced_sub_helper'}` on PPP), vac legacy. **None target a
  non-empty WRONG-but-valid claimer (e.g. `_User_Wade_Watson`).**
- `KEEP_HISTORICAL_WEEKS` = `'false'` (workflow L267); gate at L3268 is
  `if ident not in valid_wr_weeks and KEEP_HISTORICAL_WEEKS: continue` — does
  NOT preserve (false), but the dedup still only acts within-identity.
- `run_claimer_remediation` deletes only `_GARBAGE_PATTERNS`
  (`_NO_MATCH` + `_Unknown_Foreman`); isolated path uses
  `_ALWAYS_GARBAGE_PATTERNS = ('_NO_MATCH',)`. Does NOT match valid names
  like "Wade Watson".

## Eliminated

- **"Reverting E `1->0` should have deleted files."** ELIMINATED — the E flag
  only switches the filename scheme + change-detection source for FUTURE runs;
  it is not a deletion trigger, and no run executed after the revert.
- **"Cleanup is broken / not running."** ELIMINATED — cleanup ran (logged
  `removed_variants=0, removed_off_contract=0`, `removed 0 stale`) and the
  per-identity delete-old correctly removed 6 same-claimer prior copies. It is
  working AS DESIGNED; the design just has no path for cross-claimer legacy
  removal.
- **"Attribution still broken (wrong foreman)."** ELIMINATED — the RPC fix is
  verified; WR_90727774 now resolves Mark Diaz correctly. Remaining wrong-name
  files are STALE artifacts from the pre-fix period, not new mis-resolutions.

## Root Cause

`cleanup_untracked_sheet_attachments` dedups **only within a single identity
tuple `(wr, week, variant, claimer)`** — it keeps the newest copy per identity
and never cross-deletes between different claimers. This is the deliberate
Foundation A **"claimer-file coexistence / no-cross-delete" invariant**
([2026-05-20 13:45] Living Ledger rule 2): a legitimate mid-week foreman switch
must yield TWO coexisting files, neither clobbering the other.

When the 2026-05-27 attribution fix corrected historical claimers
(Wade Watson → Mark Diaz), the run ADDED the correct `_User_Mark_Diaz` file but
the old `_User_Wade_Watson_<ts>_<hash>` file is a DIFFERENT identity with one
member → kept. No existing mechanism removes it:
- per-identity delete-old → different identity, skips it;
- `run_claimer_remediation` → only `_NO_MATCH`/`_Unknown_Foreman`, not a real
  (but wrong) name;
- a forced full regen → regenerates the correct file but still won't
  cross-delete the wrong-claimer one.

So legacy hash-named wrong-claimer files persist indefinitely as duplicates.

## Fix Approach (to design + build in this session)

A **one-time, kill-switch-gated legacy-attachment cleanup migration** that, for
each `(wr, week, variant)` the current run produced a CLEAN-named current file
for, deletes the LEGACY HASH-NAMED attachments for that same
`(wr, week, variant)` **regardless of claimer**. The hash/timestamp token is the
reliable legacy signal (clean-named = current/correct scheme; hash-named =
pre-migration / possibly-wrong-claimer).

Design constraints / invariants to preserve:
1. **Do NOT violate no-cross-delete for legitimate multi-foreman weeks.** Two
   CLEAN-named claimer files for the same (wr, week, variant) must BOTH survive.
   Only HASH-NAMED (legacy) files are eligible for cross-claimer deletion, and
   only when a clean current file exists for that (wr, week, variant).
2. **Kill-switch gated, default-evaluated carefully**, workflow-pinned per the
   IN-04 / 2026-04-24 14:30 rules. Likely also gated on
   `SUPABASE_HASH_STORE_AUTHORITATIVE` (clean names are the supersession
   signal — meaningless when E is dormant and files are hash-named).
3. **Dual-target:** apply to BOTH TARGET_SHEET_ID and SUBCONTRACTOR_PPP_SHEET_ID
   (respect the PPP variant whitelist — only reduced_sub* on PPP).
4. **PII discipline** (sanitized log markers registered in `_PII_LOG_MARKERS`).
5. **End-to-end regression test REQUIRED** (project rule [2026-05-20 00:26] #4 /
   [2026-05-19 22:00]) — static mirror tests do not count.
6. **Decide the ~147 unattributable rows** (source foreman `#NO MATCH` / blank):
   they will perpetually regenerate as garbage. Options: (a) skip generation for
   no-valid-claimer rows, (b) leave to the existing remediation sweep, (c) flag
   for operator source-data fix. This decision is part of the fix design.

Sequencing note: this migration is the cleanup step in the E re-activation
runbook (deploy RPC ✓ → remediate/cleanup → validate → flip E='1' + forced
regen). E currently `'0'`.

## Current Focus

- hypothesis: ROOT CAUSE CONFIRMED (no-cross-delete invariant + absence of a
  legacy-hash cross-claimer cleanup path).
- next_action: Design + build the one-time gated legacy-attachment cleanup
  migration per the Fix Approach above; add end-to-end regression test; decide
  the ~147 unattributable-row handling. Honor TDD (project mandates regression
  coverage for row-flow / attachment-lifecycle fixes).
- reasoning_checkpoint: This is invariant-sensitive production billing code —
  the fix MUST NOT let two legitimate CLEAN-named claimers cross-delete; only
  legacy HASH-named files are deletion-eligible.

## Resolution

- root_cause: ``cleanup_untracked_sheet_attachments`` deduplicates only WITHIN a
  single identity tuple ``(wr, week, variant, claimer)`` (the Foundation A
  no-cross-delete invariant), so when the 2026-05-27 attribution fix corrected a
  historical claimer (Wade Watson -> Mark Diaz) the old wrong-claimer LEGACY
  HASH-NAMED file — a different identity — was never cross-deleted and persisted
  as a duplicate on both target sheets.
- fix: Added a default-OFF, kill-switch-gated one-time cleanup
  (``LEGACY_HASH_CLAIMER_CLEANUP_ENABLED`` + a ``legacy_hash_cleanup`` param on
  ``cleanup_untracked_sheet_attachments``) that, for each ``(wr, week, variant)``
  with a CLEAN-named current file on the row, deletes the surviving LEGACY
  HASH-NAMED attachment for that same ``(wr, week, variant)`` regardless of
  claimer. New ``_is_legacy_hash_named`` discriminator (6-digit HHMMSS token
  after WeekEnding). Two CLEAN-named claimers both survive (no-cross-delete
  invariant intact). Wired at both TARGET and PPP call sites (PPP respects its
  reduced_sub* whitelist). PII marker registered; flag workflow-documented +
  advanced_options-activatable; Living Ledger entry added.
- decisions: (Q1) ~147 unattributable rows LEFT to ``run_claimer_remediation``
  (scope = wrong-claimer hash files only). (Q2) Dedicated kill switch,
  independent of ``SUPABASE_HASH_STORE_AUTHORITATIVE``, default OFF — prep step
  before E re-activation.
- tdd: end-to-end regression suite ``tests/test_legacy_hash_claimer_cleanup.py``
  (14 methods, RED->GREEN) drives the real cleanup function.
- validation: ``pytest tests/`` -> 1000 passed / 29 skipped / 69 subtests
  (was 986; +14, zero regressions). ``python -m py_compile
  generate_weekly_pdfs.py`` clean.
- cycles: 1 (investigation, prior session) + 1 (fix, this session).
