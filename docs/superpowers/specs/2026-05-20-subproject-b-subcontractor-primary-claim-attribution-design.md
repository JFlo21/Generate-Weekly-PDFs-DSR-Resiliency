# Subproject B — Subcontractor Primary Claim Attribution

**Date:** 2026-05-20
**Status:** Approved design (pre-implementation)
**Author:** Brainstormed with the operator; design Parts 1–2 approved.
**Scope:** Sub-project **B** of the "universal per-line-item claim
attribution" effort. Builds directly on Foundation A
(`docs/superpowers/specs/2026-05-20-claim-attribution-foundation-design.md`).
C / D / E each get their own spec.

---

## 1. Motivation

Foundation A shipped the read layer (`_lookup_attribution_all`), the
shared resolution contract (`resolve_claimer` + `ROLE_BY_VARIANT`), and
the dormant HOLD machinery (`record_attribution_hold` /
`summarize_attribution_holds`). Nothing consumes them yet.

B is the **first consumer**. It re-partitions the two **subcontractor
primary** variants — `reduced_sub` (always emitted) and `aep_billable`
(post-cutoff) — so that each generated Excel file holds the line items
of **one frozen primary claimer** and is named after them, rather than
one file per WR+week keyed on whatever foreman is currently assigned on
the Smartsheet.

This realizes, for the subcontractor primary artifacts, the whole-system
vision from Foundation A §1: every file partitioned by the foreman who
**claimed** each line item (logged it `Units Completed?`-checked),
attribution **frozen first-write-wins per row**, surviving reschedules.
The subcontractor helper-shadow variants are already partitioned this way
(Phase 1.1); B brings the subcontractor *primary* variants to parity.

---

## 2. Scope & one-line behavior

B re-partitions `reduced_sub` and `aep_billable` from *one file per
WR+week* (current foreman) to *one file per WR+week per frozen primary
claimer*, consuming `resolve_claimer`.

**B changes only the partition dimension** of those two variant keys.
Explicitly unchanged:

- **Which rows are included** in `reduced_sub` / `aep_billable` — the
  row-acceptance + helper-exclusion logic in `group_source_rows` is
  Phase 1.1's domain and is not touched. Whatever rows land in a
  `_ReducedSub` file today continue to land in a `_ReducedSub_User_<claimer>`
  file under B.
- The legacy `primary` and `vac_crew` variants.
- The Phase 1.1 helper-shadow path (`reduced_sub_helper` /
  `aep_billable_helper`) — it keeps its bespoke `lookup_attribution`
  consumer; B does NOT migrate it onto `resolve_claimer` (Foundation A
  §11 defers that).
- `billing_audit/` — Foundation A already provides everything B reads.

### Operator-confirmed decisions (this brainstorm)

1. **Partition model — fallback to current foreman.** Rows with a frozen
   primary claimer group under that claimer; rows with no frozen claimer
   yet (`no_history`) fall back to the current `effective_user`. Every
   accepted row still lands somewhere. Because the row-acceptance gate
   already requires `Units Completed?` checked
   (`generate_weekly_pdfs.py`, the `if not wr or not log_date_str or not
   units_completed_checked …: continue` guard), `no_history` only occurs
   for a row completed *this* run but not yet frozen — the freeze for
   that row happens later in the same run's main loop, so the next run
   resolves it to `frozen`. Mirrors the shipped helper-shadow semantics.
2. **Kill switch — reuse `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED`**
   (default `'1'`, already workflow-pinned). Its documented scope is
   broadened to govern helper-shadow AND primary claim attribution on
   subcontractor sheets.
3. **Filename — reserved `User` token.** `_ReducedSub_User_<name>` /
   `_AEPBillable_User_<name>`, reusing the existing `_User_` primary-foreman
   convention. Unambiguous against the `Helper` token; legacy `_ReducedSub`
   (no token) stays parseable so migration recognizes it as an orphan.
4. **Migration — explicit forced cleanup + one-time hash-history prune**
   (kill-switch gated), so legacy unpartitioned files never coexist with
   the new per-claimer files (the Phase 1.1 Bug B2 / SUB-09
   duplicate-billing-artifact trap).
5. **Outage behavior — HOLD.** On a genuine Supabase outage
   (`fetch_failure`) the affected rows are deferred (not emitted) and a
   loud end-of-run WARNING fires. Correctness over availability for the
   primary billing artifact. B is the first consumer of Foundation A's
   HOLD machinery.
6. **Wiring — parallel pre-pass (Approach A).** Resolve attribution for
   all subcontractor rows in a bounded `ThreadPoolExecutor` before the
   grouping loop, so no per-row Supabase round-trip runs inside the hot
   grouping loop (honors the [2026-04-25 14:00] latency lesson).

---

## 3. Cross-cutting invariant (inherited from Foundation A §2)

**Claimer-file coexistence & no-cross-delete.** Each file holds only one
claimer's line items, named after that claimer. Two primary foremen on
the same WR+week produce **two coexisting files** that must never
cross-delete. This holds because the claimer name is part of the
**identity tuple** `(wr, week, variant, identifier=claimer)`: two claimers
on the same WR+week+variant are distinct identities → distinct filenames,
distinct `valid_wr_weeks` entries → attachment cleanup keeps both (it only
prunes older copies *within the same identity*). B MUST carry a
regression test proving two same-week primary claimers coexist.

---

## 4. Attribution resolution (Approach A: parallel pre-pass)

Inside `group_source_rows`, **before** the main grouping loop:

1. First pass over `rows` collects, for each subcontractor row, the tuple
   `(row_id, wr_key, week_ending_date, effective_user)`. Subcontractor
   detection reuses the hoisted `is_subcontractor_row` predicate
   (`__source_sheet_id in _FOLDER_DISCOVERED_SUB_IDS`). Rows that fail the
   acceptance gate (missing WR / week / not completed) are skipped here
   exactly as they are skipped in the main loop.
2. A `ThreadPoolExecutor(max_workers=min(PARALLEL_WORKERS, n))` (cap 8 —
   the codebase-wide parallel-I/O cap) calls
   `resolve_claimer('reduced_sub', effective_user, wr=wr_key,
   week_ending=week_ending_date, row_id=row_id,
   enabled=SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED)` once per row,
   building a `{row_id: ResolveOutcome}` map. `reduced_sub` and
   `aep_billable` both map to `primary_foreman` in `ROLE_BY_VARIANT`, so
   **one resolve per row serves both** variants.
3. The map is local to `group_source_rows`; no caller signature changes.
   No new Supabase I/O runs inside the grouping loop.

**Concurrency safety.** `resolve_claimer` → `_lookup_attribution_all`
shares the existing `with_retry(op="lookup_attribution")` circuit breaker
and the `get_client()` memoized client (Foundation A reused the
already-thread-safe machinery; the freeze_row path has run parallel since
2026-04-25). The pre-pass swallows per-row exceptions defensively
(`logging.exception` with sanitized `row_id` only) so one bad row cannot
poison the map — but `resolve_claimer` is already non-raising by
contract, so this is belt-and-suspenders.

---

## 5. Emission changes in `group_source_rows`

At the subcontractor variant block (today: the `if is_subcontractor_row
and SUBCONTRACTOR_RATE_VARIANTS_ENABLED:` block that appends
`('reduced_sub', f"{week}_{wr}_REDUCEDSUB", effective_user)` and the
cutoff-gated `('aep_billable', …)`), consult the pre-pass map by
`row_id`:

- **`outcome.action == 'use'`** → `claimer = outcome.name`.
  - `reduced_sub` key becomes
    `f"{week}_{wr}_REDUCEDSUB_USER_{claimer_sanitized}"`, appended as
    `('reduced_sub', key, claimer)`.
  - `aep_billable` key (when `Snapshot Date >= _AEP_BILLABLE_CUTOFF`)
    becomes `f"{week}_{wr}_AEPBILLABLE_USER_{claimer_sanitized}"`, appended
    as `('aep_billable', key, claimer)`.
  - `claimer_sanitized = _RE_SANITIZE_IDENTIFIER.sub('_', claimer)[:50]`
    (the existing `_User_` convention sanitizer, idempotent).
- **`outcome.action == 'hold'`** → emit **neither** `reduced_sub` nor
  `aep_billable` for this row; call `record_attribution_hold(wr_key,
  week_ending_date, 'reduced_sub')` once. The helper-shadow keys (if this
  row is also a valid helper row) still emit via the unchanged Phase 1.1
  path.

`no_history` / `disabled` resolve to `action == 'use'` with
`outcome.name == effective_user`, so the fallback-to-current behavior is
automatic and needs no extra branch.

The map lookup defaults safely: a row absent from the map (e.g. attribution
disabled so the pre-pass was skipped, or an unforeseen gap) is treated as
`use` current `effective_user` — never HOLD — so a map miss can never
silently suppress a billing file.

---

## 6. Filenames

In `generate_excel` variant-suffix construction (today: `reduced_sub →
'_ReducedSub'`, `aep_billable → '_AEPBillable'`):

- `reduced_sub` → `f"_ReducedSub_User_{claimer_sanitized}"`
- `aep_billable` → `f"_AEPBillable_User_{claimer_sanitized}"`

where `claimer = first_row.get('__current_foreman')` (set from the
`keys_to_add` tuple's claimer element via the existing `r_copy['__current_foreman']
= current_foreman or effective_user` line), sanitized with
`_RE_SANITIZE_IDENTIFIER`. A defensive `raise ValueError` fires if the
claimer is empty (mirrors the existing `aep_billable_helper` /
`reduced_sub_helper` defensive raises) — production never hits it because
`resolve_claimer`'s `use` outcome always returns a non-empty name
(falling back to `effective_user`, which defaults to `'Unknown Foreman'`).
Helper-shadow suffixes (`_ReducedSub_Helper_<name>` etc.) are unchanged.

---

## 7. Parser & the three identity sites (the CR-01 invariant)

The [2026-05-15] CR-01 rule: the identity tuple is rebuilt at three
main-loop sites plus the filename parser, and they MUST stay in lockstep.

- **`build_group_identity`.** In the `ReducedSub` / `AEPBillable`
  non-`Helper` branches (which today set `identifier = ''`), parse a
  leading `User` token: if the post-variant tail starts with `User`,
  `identifier = '_'.join(post[1:-1])` (span-join so underscored names
  survive); otherwise `identifier = ''`. Variant stays `reduced_sub` /
  `aep_billable`. Legacy `_ReducedSub` (no `User` token) still parses to
  `identifier=''` → recognized as a migration orphan. The existing
  variant-first ordering (subcontractor tokens checked before
  `Helper`/`User`/`VacCrew`) is preserved.
- **Site 1 — main-loop `identifier` / `file_identifier`.** Move
  `reduced_sub` / `aep_billable` out of the bare `else` (which reads the
  `User` row field) into a branch deriving `identifier = file_identifier =
  _RE_SANITIZE_IDENTIFIER.sub('_', first_row.get('__current_foreman'))[:50]`.
  The `history_key = f"{wr}|{week}|{variant}|{identifier}"` then carries the
  claimer.
- **Site 2 — `valid_wr_weeks`.** Add the claimer-derived `file_id` for
  `reduced_sub` / `aep_billable` so attachment cleanup keeps the live
  per-claimer file.
- **Site 3 — `current_keys` (hash-history prune).** Same claimer-derived
  identifier so the per-claimer hash key is recognized as current and not
  stale-pruned.

A source-level grep regression test asserts all three sites + the parser
carry the new branch (mirrors the existing
`test_production_valid_wr_weeks_and_current_keys_carry_shadow_variant_gate`).

---

## 8. Migration of legacy unpartitioned files

When B ships, every legacy `_ReducedSub` / `_AEPBillable` file
(`identifier == ''`, no `_User_` token) is obsolete and must not coexist
with the new per-claimer files (the Phase 1.1 Bug B2 / SUB-09
duplicate-billing trap). Two deterministic, idempotent cleanups, both
gated by `SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED` (default `'1'`):

1. **Forced attachment cleanup.** Extend `cleanup_untracked_sheet_attachments`
   (already accepts `sub_wr_scope` / variant-scope kwargs from SUB-09):
   for in-scope subcontractor WRs, unconditionally delete any attachment
   parsing to `variant ∈ {reduced_sub, aep_billable}` **and** `identifier
   == ''` **and** `ident not in valid_wr_weeks`. The `valid_wr_weeks`
   exemption is the [2026-05-19 23:45] WR-01 live-identity guard
   (belt-and-suspenders — B never emits an empty identifier, so a live
   file is always exempt; a legacy orphan is never in `valid_wr_weeks`).
   Runs on **both** target sheets: `TARGET_SHEET_ID` (reduced_sub +
   aep_billable) and `SUBCONTRACTOR_PPP_SHEET_ID` (reduced_sub). The WR
   scope comes from the shared `_build_subcontractor_wr_scope(groups)`
   helper so it can never drift from the source-side variant emission.
2. **One-time hash-history prune.** A version-sentinel prune
   (`SUBPROJECT_B_HASH_PRUNE_VERSION`, persisted in `hash_history.json`
   alongside the existing `_phase_prune_version` sentinel) drops legacy
   `…|reduced_sub|` / `…|aep_billable|` empty-identifier entries for sub
   WRs. The normal stale-prune at Site 3 would clear them eventually, but
   the sentinel makes migration deterministic on the first run and
   survives interrupted / no-update runs. Dropping a hash entry costs at
   most one regeneration (the engine's safe default), never data loss.

---

## 9. HOLD wiring (B is Foundation A's first consumer)

- During emission, each held row calls `record_attribution_hold(wr_key,
  week_ending_date, 'reduced_sub')` once.
- At end-of-run in `main()` — alongside the existing hash-history save /
  `run_summary.json` emission, after the main group-processing loop —
  call `summarize_attribution_holds()` **exactly once**. It emits one
  PII-safe aggregate WARNING (counts + sanitized WR list only) and returns
  the message. The implementation may additionally escalate to an explicit
  Sentry capture so a Supabase outage that suppresses billing files is
  loudly visible, not silent.

**Accepted asymmetry.** On a `fetch_failure` outage the Supabase client is
globally unreachable, so every subcontractor row's primary dimension
HOLDs → **zero** `_ReducedSub` / `_AEPBillable` files generate that run
(they catch up next run). The unchanged Phase 1.1 helper-shadow path
instead falls back to the current helper and still generates
`_ReducedSub_Helper_*` / `_AEPBillable_Helper_*` files (with its own
fallback WARNINGs). This split is intentional: the primary billing
artifact gets the stronger correctness guarantee; the already-shipped
helper-shadow path is out of scope for B per Foundation A §11.

---

## 10. Config

- **Attribution gating (no new var):** reuse
  `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED`, passed as the
  `enabled=` argument to `resolve_claimer`. Broaden its documented scope
  (inline comment + `website/docs/reference/environment.md`) to: "governs
  helper-shadow AND primary claim attribution on subcontractor sheets."
- **One new kill switch:** `SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED`
  (default `'1'`, workflow-pinned), gating only the *destructive*
  migration cleanup in §8. Required by the repo rule [2026-05-19 22:00]
  #4 (destructive cleanup paths must have their own default-on switch);
  mirrors `SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED`. This is the only
  new env var B introduces, and it is for the migration cleanup, not
  attribution.
- Startup banner: log the resolved state of the new cleanup switch
  alongside the existing `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED`
  line.

---

## 11. Error handling / fail-safe

- `resolve_claimer` / `_lookup_attribution_all` never raise on a Supabase
  failure (Foundation A §8), so HOLD is driven exclusively by the
  contract's classified `fetch_failure` outcome. The pre-pass does NOT
  wrap the resolve in a `try/except` that downgrades failures to
  `use`-current — that would defeat the HOLD guarantee. It DOES wrap the
  executor body in a defensive `try/except` for *unexpected,
  non-contract* exceptions (e.g. an executor/threading fault); such a
  row is logged (PII-safe, `row_id` only) and omitted from the map,
  which the emission step then treats as a map miss → `use` current.
  Rationale: a contract-classified outage HOLDs (correctness), but an
  unexpected plumbing fault should never silently suppress a billing
  file.
- A map miss for any reason resolves to `use` current `effective_user` —
  never HOLD — so the pre-pass can never silently zero out a run's
  subcontractor primary files through a bug in the map plumbing.
- B introduces no change to the billing pipeline's non-attribution paths
  (discovery, fetch, pricing, Excel layout, upload).

---

## 12. Testing (true end-to-end, per [2026-05-20 00:26] #4)

Static mirror classes are insufficient — they pass even when the
upstream emission is broken. New tests (new file, e.g.
`tests/test_subcontractor_primary_claim_attribution.py`) drive real
production code paths:

- **End-to-end grouping** — drive `group_source_rows` on synthetic
  Smartsheet rows with mocked `resolve_claimer` / `_lookup_attribution_all`;
  assert `_REDUCEDSUB_USER_<claimer>` / `_AEPBILLABLE_USER_<claimer>` group
  keys partition by frozen primary; `no_history` falls back to current
  `effective_user`; `hold` suppresses both primary keys but not the
  helper-shadow keys.
- **Two-claimer coexistence** (Foundation A §2 mandate) — two primary
  foremen on the same WR+week emit two distinct identities; cleanup keeps
  both.
- **Filename round-trip** — `generate_excel` produces
  `_ReducedSub_User_<name>` / `_AEPBillable_User_<name>`;
  `build_group_identity` parses them back to `(wr, week, reduced_sub /
  aep_billable, name)`; legacy `_ReducedSub` → `identifier=''`; the empty
  claimer defensive raise fires.
- **Three-site identity consistency** — source-level grep guards that
  Site 1 / Site 2 / Site 3 + the parser all carry the claimer branch.
- **Migration** — forced cleanup deletes legacy `identifier=''`
  reduced_sub / aep_billable on TARGET + PPP for in-scope sub WRs; exempts
  live identities (`valid_wr_weeks`) and non-sub WRs; kill-switch-off →
  no deletion. Hash prune drops legacy entries idempotently (version
  sentinel; second run is a no-op).
- **HOLD accounting** — `record_attribution_hold` increments on
  fetch_failure rows; `summarize_attribution_holds` fires once at
  end-of-run with a PII-safe message; no holds → no WARNING.
- **Parallel pre-pass concurrency** — concurrent resolve produces a
  correct `{row_id: ResolveOutcome}` map with no lost/duplicated entries
  (mirror `FreezeRowConcurrencyTests`).
- **Byte-identical preservation** — primary / original-contract /
  vac_crew / helper-shadow outputs unchanged (ROADMAP-style success
  criterion; the partition change is scoped strictly to the two
  subcontractor primary variants).

`pytest tests/` must exit 0.

---

## 13. File footprint

- **`generate_weekly_pdfs.py`:** parallel attribution pre-pass + emission
  changes in `group_source_rows`; `generate_excel` filename builder;
  `build_group_identity` parser; the three identity sites;
  `cleanup_untracked_sheet_attachments` migration scope; one-time
  hash-prune helper + `SUBPROJECT_B_HASH_PRUNE_VERSION`; end-of-run
  `summarize_attribution_holds` call; startup-banner line; new
  `SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED` env var.
- **`.github/workflows/weekly-excel-generation.yml`:** pin
  `SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED`.
- **`website/docs/reference/environment.md`:** document the new var +
  broadened scope of `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED`.
- **`tests/test_subcontractor_primary_claim_attribution.py`** (new): the §12 suite.
- **`billing_audit/`:** NOT modified.
- **`CLAUDE.md`:** Living Ledger entry added at execution time per repo rule.

---

## 14. Out of scope (future sub-projects)

- **C** — VAC crew partition by `frozen_vac_crew`.
- **D** — primary-workflow primary foreman partition (highest blast
  radius + largest migration; deliberately last).
- **E** — Supabase-backed change-detection hash store + stripping the
  `_<hash>` / `_<timestamp>` filename tokens.
- Refactoring the live Phase 1.1 helper-shadow consumer onto
  `resolve_claimer` (Foundation A §11 — sub-helper proves itself first).
- Any change to row-inclusion / helper-exclusion logic in
  `group_source_rows`.
