# Phase 14: Foreman Helper #2 - Research

**Researched:** 2026-09-05
**Domain:** Python billing pipeline (Smartsheet → Excel → Smartsheet), Supabase attribution/memory, portal variant surfacing
**Confidence:** MEDIUM-HIGH — every code claim below was read this session with `Read`/`Grep` against the current repository (not the prototype, not memory). Gaps where evidence could not be obtained read-only are explicitly marked "pending — resolve in execution task."

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Confirmed owner decisions (2026-09-05; supersede the 2026-08 handoff)

- **D-14-01 [owner]: Intake ProMax 8 (`2244739192541060`) is intentionally excluded.** No Helper #2
  columns, formula repair, reconnection, report inclusion, row migration, readiness prerequisite, or
  schema-reconciliation task. Its missing columns are accepted, not a defect or release blocker.
  Exclusion never authorizes deleting historical records, workbooks, attachments, or attribution
  evidence. *Live observation 2026-09-05 ~07:40Z (read-only Smartsheet MCP):* the sheet is a
  direct child of the Intake folder `8815193070299012` that `discover_folder_sheets` scans
  (`pipeline/config.py:311` default `ORIGINAL_CONTRACT_FOLDER_IDS`), it maps
  `Weekly Reference Logged Date` (the only strict-mode acceptance gate,
  `pipeline/discovery.py:668-680`), it has the full Helper #1 column set, and it has none of the
  six Helper #2 columns. **Therefore today's discovery accepts it as a source sheet; Phase 14 does
  not change that either way** — its primary / Helper #1 / VAC behavior stays whatever it is
  today, and the Helper #2 path reports "capability unavailable" for it. Verification lives in a
  fixture test (a sheet with Helper #1 columns and no Helper #2 columns), never a live-sheet
  remediation. — **Reversibility:** reversible.
- **D-14-02 [owner]: Missing optional Helper #2 columns must not break generation.** On an otherwise
  eligible source they mean the capability is unavailable there: skip only the Helper #2 path,
  keep primary / Helper #1 / VAC behavior, never reject the sheet, never make the new fields
  universally required, never force historical sources onto the new schema. The four conditions
  stay distinguishable in logs and run summary: intentionally excluded source · eligible source
  without capability · eligible source with no qualifying completion · failed/incomplete read (a
  read failure is NOT "no helper"; existing fail-closed `_failed_validation_sids` /
  `sentry_capture_sheet_drop` handling in `pipeline/discovery.py:681-696` is preserved).
- **D-14-03 [owner]: Extend the existing Helping Foreman behavior.** Same stages, same modules, same
  business rules as Helper #1 for completion eligibility, dept/job handling, attribution,
  grouping, pricing, filenames, and output routing. No generic role engine, no speculative
  Helper #3 abstraction. This request authorizes a second helper capability; it does **not**
  establish a rule that the same physical unit is billed to the customer twice.

### Eligibility contract (mirrors Helper #1 — from code)

- **D-14-04 [repo]: Required fields for a Helper #2 output = the Helper #1 row rule, slot-shifted.**
  Helper #1 today (`pipeline/fetch.py:855-859`): `Foreman Helping?` non-blank AND
  `Helping Foreman Completed Unit?` checked AND `Units Completed?` checked → helper row;
  grouping then requires `__helper_dept` (`pipeline/grouping.py:620-625`, `change_detection.py:431`);
  `Helper Job #` is optional. Helper #2 therefore requires `Foreman Helping? #2` (real name),
  `Helping Foreman #2 Completed Unit?` checked, `Units Completed?` checked, and `Helper #2 Dept #`
  present; `Helper #2 Job [#]` optional. `Foreman Helper #2 Active?` and `Foreman Helper #2 Email`
  are **optional metadata, never gating** — Helper #1 ignores `Foreman Helper Active?` /
  `Foreman Helper Email` today, and the vault handoff records that the `"NA"` no-match fallback
  makes `… Active?` read `True`. **Sheet capability gate** = the three key columns mapped (name,
  completed, dept), mirroring `sheet_has_vac_crew_columns` (`pipeline/fetch.py:566`) rather than
  Helper #1's log-only 4-column check (`fetch.py:554-563`). — **Reversibility:** reversible.
- **D-14-05 [repo]: Fabricated-claim guard on the Helper #2 path only.** Blank, `NA`, `#NO MATCH`,
  and the other Smartsheet formula-error tokens (the prototype's `FORMULA_ERROR_VALUES` set is the
  reference list) are non-claims: no `__is_helper2_row`-style flag, no group, no workbook, no
  attachment, no `freeze_row` role value (which already nulls named sentinels via
  `_null_if_named_sentinel`, `billing_audit/writer.py:625-631`). **Helper #1's inherited `"NA"`
  quirk is NOT changed in this phase** — that is a production behavior change outside scope;
  recorded under Deferred. — **Reversibility:** reversible.

### Same-row multi-role semantics (behavior contract)

- **D-14-06 [repo]: Helper #2 is a per-slot output identity, mirroring Helper #1's mechanics.** A
  valid Helper #2 row is excluded from primary emission exactly like a valid Helper #1 row
  (`grouping.py:370-379`, `693-699`, `806-820` — "the helper, not the primary foreman, earns the
  credit; emitting both would double-count") and lands only in the Helper #2 file for that
  (WR, week, Helper #2 claimant, dept, job). Case table:
  | Case | Contract |
  |---|---|
  | No helper | unchanged primary behavior |
  | Helper #1 only | byte-identical to today (HLP-02) |
  | Helper #2 only | mirrors Helper #1: row leaves primary, appears once in the Helper #2 file |
  | Both helpers, different rows/units | independent files; each row appears exactly once, in its own helper's file |
  | Same person in slot 1 on some rows and slot 2 on others (same WR/week) | two files (one per slot) — accepted consequence of per-slot identity; **Juan to confirm** at the plan checkpoint (not blocking) |
  | Both helpers valid on the SAME row | **O-14-A (OPEN)** below |
  | Same person in both slots on the same row | collapses into O-14-A; if resolved as "one claim", the person is credited once |
  | VAC/subcontractor overlap | VAC rows keep precedence exactly as today (`__is_vac_crew` short-circuits helper handling, `grouping.py:370-371`, `815`); subcontractor Helper #2 rows mirror the Helper #1 asymmetry — shadow files only, never the legacy helper key (`grouping.py:704-730`, ledger `[2026-05-19]`) |
  | Independent completion flags | each slot's completed checkbox gates only its own slot |
  | Missing dept/job | dept missing → no Helper #2 claim (row stays where Helper #1 logic puts it); job missing → proceeds, logged like Helper #1 (`change_detection.py:433-434`) |
  | Assignment changes / late completion / week boundaries | identical to Helper #1: attribution freezes per role on first real value (Phase 12 rules), late completion regenerates the affected group via the normal hash path, week boundary follows `Weekly Reference Logged Date` semantics unchanged |
  — **Reversibility:** costly — filename token and variant vocabulary become part of the
  published artifact contract (`public.artifacts.variant`, portal filters, cleanup parser).
- **O-14-A [OPEN — Juan]: A source row where BOTH helper completion boxes are checked with valid
  names and depts.** Distinguish the three money flows: internal production credit (which helper's
  file shows the line item), subcontractor payment (`_ReducedSub_Helper*` / `_AEPBillable_Helper*`
  shadow files pay the subcontractor helper), and customer billing (the row must appear in
  exactly one customer-facing file). Options: (1) **hold** the row out of every file this run,
  log a distinct reason, count it in the run summary / Sentry, and surface it for correction
  (mirrors Subproject B's HOLD semantics; the prototype's `HelperAssignmentConflictError` aborted
  before workbook generation, which is too blunt — one bad row must not block the run);
  (2) Helper #1 wins (invents a priority rule); (3) both files (double credit — violates
  exactly-once); (4) primary keeps it (drops helper credit). **Recommendation: (1) hold with
  visibility** until Juan states the business rule. Only the conflict-handling task is blocked;
  everything else proceeds. No rule is invented silently.

### Attribution, ownership, and data contracts

- **D-14-07 [repo]: Helper #2 gets its own frozen role; it never overwrites `frozen_helper`.**
  Phase 12 rules apply unchanged (sentinel never a claimer; per-role first-write-wins
  `freeze_row`; ladder `observed_in_week → backfill_* → operator → sentinel`, D-12-A).
  `ROLE_BY_VARIANT` (`billing_audit/writer.py:1047-1055`) gains the Helper #2 variants → a new
  role column pair on `billing_audit.attribution_snapshot` (additive, nullable; names by the
  planner, e.g. `frozen_helper2` / `frozen_helper2_dept`) plus the `lookup_attribution*` RPCs'
  return columns — which cannot be extended with `CREATE OR REPLACE` (`schema.sql:336-339`
  documents the DROP-first requirement). This is a **Supabase schema/RPC change = protected
  area**: the implementation plan must (a) make generation work with a "no Helper #2 snapshot
  column yet" fallback (use current value, log, no crash) so old code ignores new columns and new
  code tolerates their absence, (b) sequence the migration as its own plan behind a
  `checkpoint:decision` for Juan, (c) keep `billing_audit.backfill_attribution` and the
  12-06 provenance columns untouched. A later Helper #2 completion on a row already frozen with
  primary or Helper #1 attribution is recorded in the Helper #2 role only — no overwrite, no
  inherited ownership from another week. — **Reversibility:** costly — published RPC return
  contract and scheduled-code compatibility.
- **D-14-08 [repo → planner decides with evidence]: `pipeline_memory.row_state` Helper #2 fields.**
  `row_state` carries `helper_observed / helper_completed / helper_dept / helper_job`
  (`pipeline_memory/schema.sql:113-116`, writer `pipeline_memory/writer.py:798-803`) and its
  `content_hash` is a fixed field tuple (schema comment above line 100: changing the tuple
  produces a `row_event` for every row once — 10-RESEARCH Pitfall 3). Adding `helper2_*` columns
  is additive; whether to include them in the row hash decides whether a Helper #2-only change is
  visible to the incremental affected-group path (`RUN_MEMORY_INCREMENTAL_ENABLED` is OFF in
  production today). The planner records the choice and its one-time churn cost explicitly; no
  silent omission.
- **D-14-09 [repo]: Legacy identities are byte-identical when Helper #2 is absent.** Helper #2 fields
  enter the change-detection tuple (`change_detection.py:183-192`, `_extended_row_fields(x,
  variant)`) and the group-identity string (`orchestrate.py:499-506`) **only under Helper #2
  variants** — never appended as empty fields to primary / Helper #1 / VAC keys, hashes, or
  filenames (HLP-06). — **Reversibility:** reversible.

### Discovery and mapping-cache reuse

- **D-14-10 [repo]: Six exact titles join the `synonyms` map; cached mappings get ONE bounded
  revalidation.** Titles (verified live on Main ProMax `3239244454645636`, 82 columns):
  `Foreman Helping? #2`, `Foreman Helper #2 Active?`, `Helping Foreman #2 Completed Unit?`,
  `Helper #2 Dept #`, `Helper #2 Job [#]` (bracket form, like `Helper Job [#]` →
  canonical `Helper Job #`), `Foreman Helper #2 Email`. `_build_discovery_skip_index`
  (`discovery.py:190-230`, D-11.1-01) admits a `sheet_registry` row whose stored
  `column_mapping` was written before the code knew these synonyms, so a version-unchanged sheet
  would never gain Helper #2 capability. Extend the admission test with a mapping-schema marker
  (an additive key inside the stored `column_mapping` JSON or a synonym-generation value) so
  pre-Helper-#2 mappings fall through to full validation exactly once — "any doubt → full
  validation" stays the rule; no permanent rediscovery, no local JSON cache (D-11.1-03).
  — **Reversibility:** reversible.

### Filenames, cleanup, downstream consumers

- **D-14-11 [repo]: New variant token(s) must be first-class everywhere a variant is parsed.**
  Owning interfaces to extend together, never one without the others: `pipeline/excel.py`
  variant switch + `variant_suffix` (`excel.py:271-360`, header block `540-570`);
  `change_detection.build_group_identity` / `extract_data_hash_from_filename` and the
  documented filename shapes (`change_detection.py:582-615`, precedence note `737-741`);
  `pipeline/cleanup.py` legacy/unpartitioned and placeholder-sweep rules (`cleanup.py:238-290`,
  `389-470`, `552-556`) — a `_Helper2_<name>`-style file is a first-class identity, never
  "legacy unpartitioned", and only placeholder-named Helper #2 files not produced this run are
  swept; `scripts/publish_artifacts_to_supabase.py` `_CANONICAL_VARIANTS` + `normalize_variant`
  7-way chain (`:83-140`; unknown tokens fire a Sentry guard today); `portal-v2/src/lib/
  variantLabels.ts` + `VariantFilterBar`. `public.artifacts.variant` has no CHECK constraint
  (publish script comment) → no artifacts-table migration. Token spelling (the prototype's
  `helper2` / `_Helper2_` / `aep_billable_helper2` / `reduced_sub_helper2` are candidates) is the
  planner's call after inspecting these interfaces; the parser precedence must keep
  `_AEPBillable_Helper2_` / `_ReducedSub_Helper2_` above their component forms and must not
  collide with a Helper #1 named `2…` (`_Helper_2Pac` ≠ `_Helper2_`). — **Reversibility:**
  costly — same reason as D-14-06.

### Rollout, pilot, rollback

- **D-14-12 [repo]: One additive feature flag, default off; no import-time triple gate.** A real
  deployment boundary exists (new billing artifacts on `TARGET_SHEET_ID`; attribution migration
  ordering), so Helper #2 generation ships behind a single env flag consistent with
  `pipeline/config.py` conventions (the prototype's `HELPER2_ENABLED` is the candidate name);
  the prototype's `HELPER2_SOURCE_PROVEN` / `HELPER2_JOB_PRODUCER_PROVEN` import-fails-closed gate
  is dropped — the Resource Analyst assignment automation and the `Helper #2 Job [#]` producer
  are operational preconditions recorded in the runbook and pilot checklist, not code gates.
  Flag default and workflow wiring (`.github/workflows/weekly-excel-generation.yml`) are
  separate approval items — GitHub Actions is inspect-only in this phase. Pilot: fixtures →
  `TEST_MODE` → `SKIP_UPLOAD=true` + `WR_FILTER` on WRs that carry a real Helper #2 assignment
  (data precondition: RA `Foreman Helper #2` was blank on 539/539 rows on 2026-08-23 — if still
  blank, the pilot is fixture-only and says so) → one controlled upload → compare. Rollback:
  flag off; Helper #2 attachments and attribution rows are **retained** (cleanup must not treat
  them as placeholders); claimed units are never moved back to the primary foreman.
  — **Reversibility:** reversible (flag) / costly (any migration — see D-14-07).

### Claude's Discretion

- Internal row-metadata names (`__helper2_foreman` etc.), variant tokens, flag name, snapshot
  column names, log-reason strings, and test module placement — chosen by the planner/executor
  to match the surrounding code after inspecting the owning interfaces listed above.
- Whether the attribution-freeze slice ships in the same PR as generation or trails it (both
  behind the same flag) — planner decides from the dependency analysis; the fallback in D-14-07
  makes either order safe.

### Carried forward from earlier phases

- Phase 1.1 (ledger `[2026-05-19]`, `[2026-05-21]`): subcontractor helper rows emit only shadow
  files; valid helper rows leave the primary file. Helper #2 mirrors both.
- Phase 11 D-06 / Phase 11.1 D-11.1-01, D-11.1-03: nothing outside the affected scope in
  incremental mode; sheet identity lives only in `pipeline_memory.sheet_registry`; no local
  JSON caches return.
- Phase 12 D-12-A, D-12-C, D-12-D: no `wr_week_ownership` table (deferred to Phase 13); the
  945 `#NO MATCH` rows are out of OWN-03 scope; sentinel never a claimer.

### Deferred Ideas (OUT OF SCOPE)

- **Helper #1 `"NA"` fabricated-name quirk** — `fetch.py:855-859` accepts any non-blank string as a
  helper name; fixing Helper #1 is a production behavior change outside this feature. Separate
  follow-up with its own fixtures.
- **Intake 8 discovery status** — it is discovered today (see D-14-01). Whether Juan wants it out of
  `ORIGINAL_CONTRACT_FOLDER_IDS` discovery entirely is a separate operational decision; Phase 14
  neither removes nor repairs it.
- **Resource Analyst `Assigned Helper 2?` automation and the `Helper #2 Job [#]` producer** —
  Smartsheet-side prerequisites owned by Juan; recorded in the pilot checklist, not code.
- **Backup 2 Helper #2 columns** — optional Smartsheet work (`backup2_helper2_plan.md` in the
  vault); not a generator task.
- **`row_state` Helper #2 hash inclusion when `RUN_MEMORY_INCREMENTAL_ENABLED` turns on** — if
  D-14-08 lands on "columns yes, hash no", revisit before enabling incremental.
- **Phase 13 `wr_week_ownership`** — Helper #2 role must be representable there; note for Phase 13.

**Open item requiring Juan's decision before the conflict-handling task can be planned in detail:**
O-14-A (both helper slots valid on the same row). Everything else in this research is actionable
without further owner input.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HLP-01 | Eligible Helper #2 completion produces its own weekly Excel output; group key, hash, header, filename, and attachment routing all name the same claimant | Impact Map (Architecture Patterns), Affected Consumers table — `grouping.py`, `change_detection.py`, `excel.py`, `orchestrate.py:derive_group_identity` |
| HLP-02 | Helper #1 stays fully independent — unchanged outputs/keys/hashes/filenames with or without Helper #2 | `change_detection.py` variant-gated meta_parts (415-437), `derive_group_identity` variant dispatch (orchestrate.py:498-508) — both branch on explicit variant-tuple membership, never a shared/ambiguous key |
| HLP-03 | Missing optional Helper #2 columns skip only that path with a distinct log reason; sheet never rejected | `sheet_has_vac_crew_columns`-style capability gate pattern (fetch.py:566-570); Active Sources section |
| HLP-04 | Intake ProMax 8 stays excluded via existing config/fixtures; no remediation | Active Sources section — `ORIGINAL_CONTRACT_FOLDER_IDS` verified at `pipeline/config.py:311` |
| HLP-05 | Blank/NA/#NO MATCH/unchecked/no-capability inputs create no Helper #2 claim/group/workbook/attachment/attribution row | Common Pitfalls (fabricated-claim guard), `_null_if_named_sentinel` (billing_audit/writer.py:118-124) |
| HLP-06 | Later Helper #2 completion on an already-frozen row is recorded in its own role only; idempotent; legacy hashes/filenames unchanged when Helper #2 absent | Ownership/Timing/Repeated-Runs section — `freeze_row` all-sentinel gate (writer.py:632-636), `ROLE_BY_VARIANT` (1047-1055) |
| HLP-07 | Ships behind one additive flag, default off, scoped pilot, rollback preserves evidence | D-14-12 (verbatim above), Findings Disposition |
</phase_requirements>

## Summary

Phase 14 extends an existing, well-factored "helper variant" mechanism rather than building
anything new. Helper #1 today is not a single function — it is a **dispatch pattern repeated at
roughly a dozen call sites**, each of which branches on `row['__variant']` or the raw string
`'helper'` / the tuple `('helper', 'aep_billable_helper', 'reduced_sub_helper')`. Every one of
those sites is a place Helper #2 must add a parallel branch, and the codebase's own incident
history (Living Ledger `[2026-05-19 22:00]`, `[2026-05-21 12:35]`) shows the *exact* failure mode
to avoid: a guard applied to the primary-key branch but forgotten on the sibling helper-key branch,
or an exact-match `if variant == 'helper':` that silently falls through to the primary `else` for
a new variant string. Both real production incidents were "we added a new variant tuple member
and missed one of the ~12 call sites that dispatch on it." Phase 14 is structurally the same
change Subprojects B/C/D already made twice; the research below is largely a checklist of the
sites those subprojects touched, re-derived for a `helper2`-shaped extension.

Three findings in this research were **not** named in the phase's audit-scope prompt and are new,
load-bearing discoveries this session:

1. **`pipeline/cleanup.py:518-520`** — `_HELPER_VARIANTS_FOR_ORPHAN_GATE = frozenset({'helper',
   'aep_billable_helper', 'reduced_sub_helper'})` detects when a primary attachment was superseded
   by a helper claim, for Sentry-tagged cleanup. Without a Helper #2 entry, a primary attachment
   superseded ONLY by a Helper #2 claim will never be recognized as a migration orphan and may be
   left stale (not a data-loss bug, but a cleanup gap).
2. **`pipeline/upload.py:343`** — `if variant in ('reduced_sub', 'reduced_sub_helper'):` is the
   hardcoded gate that dual-routes a group's upload task to `SUBCONTRACTOR_PPP_SHEET_ID`. Without
   a `reduced_sub_helper2` entry here, a subcontractor Helper #2 shadow file will upload to
   `TARGET_SHEET_ID` only and the subcontractor will never see it on the PPP sheet — a functional
   miss, not a crash, so it would not surface in a smoke test that only checks "did a file get
   produced."
3. **`pipeline/change_detection.py:482-545`** (`_compute_aggregated_content_hash`) special-cases
   the `helper` variant with per-foreman sub-bucketing specifically because reading
   `sorted_rows[0]` for group identity is unsafe across multiple helpers sharing one aggregation
   bucket. A `helper2` variant used by the same billing_audit aggregation path needs the identical
   special-case, or it inherits the exact bug this code was written to prevent.

**Primary recommendation:** Treat this as a "clone the helper branch at every site" refactor, not
a new capability. Use the existing `('helper', 'aep_billable_helper', 'reduced_sub_helper')`
variant-tuple membership tests as the literal checklist of files/lines to touch, add the
corresponding `helper2`-family tuple everywhere, and add one new regression test per touched
module asserting the Helper #1-only and Helper #2-only paths are both byte-identical to today
when the other is absent (HLP-02/HLP-06). The single highest-leverage file is
`pipeline/orchestrate.py`'s `derive_group_identity` (line 460) — it already collapsed three
duplicated identity call sites into one function specifically so a future variant addition (this
one) only needs one dispatch branch, not three.

## Architectural Responsibility Map

This is a single-process batch pipeline (no browser/SSR tiers), so the map below is adapted to
the project's actual layers.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Column discovery / synonym mapping | Ingestion (`pipeline/discovery.py`) | Persistence (`pipeline_memory.sheet_registry` cache) | Discovery decides whether a sheet CAN produce Helper #2 rows this run; the registry cache can suppress that decision on an unchanged sheet (D-14-10) |
| Row eligibility / field extraction | Ingestion (`pipeline/fetch.py`) | — | Pure per-row boolean gate + metadata population, mirrors Helper #1 exactly |
| Grouping / primary exclusion / claimant partitioning | Business logic (`pipeline/grouping.py`) | Persistence (`billing_audit.attribution_snapshot` reads via `resolve_claimer`) | Decides which file a row's credit lands in; reads frozen attribution for subcontractor claim continuity |
| Change detection / hashing / group identity | Business logic (`pipeline/change_detection.py`, `pipeline/orchestrate.py`) | Persistence (`pipeline_memory.group_state`, `billing_audit.group_content_hash`) | Hash/identity determine regeneration and are the byte-identity contract (HLP-02/HLP-06) |
| Workbook rendering | Output (`pipeline/excel.py`) | — | Per-variant header/dept/job display selection |
| Attribution freeze/read | Persistence (`billing_audit/writer.py` + Supabase RPCs) | — | Protected area — schema/RPC change, DROP-first requirement |
| Run memory (row_state) | Persistence (`pipeline_memory/writer.py` + Supabase) | — | Additive columns; hash-inclusion decision is independent of column addition (D-14-08) |
| Cleanup / attachment lifecycle | Output lifecycle (`pipeline/cleanup.py`) | — | Legacy-migration and orphan-detection gates are variant-tuple-keyed; miss = stale files, not data loss |
| Upload routing | Output (`pipeline/upload.py`) | — | Hardcoded variant-tuple gate decides secondary PPP-sheet routing (new finding #2 above) |
| Artifact publish / portal surfacing | Presentation (`scripts/publish_artifacts_to_supabase.py`, `portal-v2/`) | — | Additive-only; unknown-variant guard logs a warning but does not fail; portal has a generic label fallback |

## Standard Stack

No new external dependency is required. Phase 14 extends existing modules using packages already
declared in `requirements.txt` (Smartsheet SDK, Supabase client, `openpyxl`, `sentry-sdk`).
`[VERIFIED: pipeline/config.py, billing_audit/writer.py, pipeline_memory/writer.py imports read this session — all stdlib + already-vendored packages, no new import introduced by the research]`.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Extending the existing per-variant dispatch pattern | A generic N-helper-slot data model (list of helper assignments per row) | Rejected by owner (D-14-03: "No generic role engine, no speculative Helper #3 abstraction") — would touch every call site anyway with more risk, for a slot count that is not requested |
| Reusing the prototype's `pipeline/types.py` dataclass shape (`HelperAssignment`, `normalize_helper_value`) | Inline field reads matching the existing helper-1 style (`row_data.get('Foreman Helping? #2')`, `str(...).strip()`) | The dataclass shape is cleaner but touches a currently-empty stub module and adds an abstraction layer none of the other variants use; the planner should pick whichever matches the surrounding code more closely (Claude's Discretion per CONTEXT.md) |

**Installation:** None required.

## Package Legitimacy Audit

**Not applicable — this phase installs no new external packages.** All modules touched already
import only stdlib and already-declared dependencies. No `npm view` / `pip index versions` /
`cargo search` check was needed or performed.
## Architecture Patterns

### System Architecture Diagram

```
Smartsheet (13+ sheets)
      │
      ▼
┌─────────────────────────┐   sheet_registry watermark match?
│ discovery.py             │──────► YES: reuse cached column_mapping
│ discover_source_sheets   │         verbatim (D-11.1-01 skip index,        ⚠ D-14-10:
│ (synonyms:555-579,       │         discovery.py:438,452-461) — SKIPS      pre-Helper-#2
│  gate:668-681)           │         the synonyms pass entirely on a hit    cached mapping
└──────────┬───────────────┘                                                never re-derived
           │ NO / doubt → full column-title validation (synonyms match)
           ▼
┌─────────────────────────┐
│ fetch.py                 │  per row: is_helper_row = name & completed-ckbx & units-ckbx
│ get_all_source_rows      │  (fetch.py:851-885) → __is_helper_row, __helper_foreman,
│                           │  __helper_dept, __helper_job written onto row dict
└──────────┬───────────────┘
           ▼
┌─────────────────────────┐  valid_helper_row (dept required) excludes row from
│ grouping.py               │  primary emission (370-379, 693-699) and emits
│ group_source_rows         │  ('helper', key, foreman) — non-sub rows only (721-724);
│ (~1145 lines)              │  subcontractor rows instead emit 'reduced_sub_helper' /
│                           │  'aep_billable_helper' shadow keys (1146-1180), reading
│                           │  frozen claim history via resolve_claimer when enabled
└──────────┬───────────────┘
           ▼
┌─────────────────────────┐  meta_parts += HELPER=/HELPER_DEPT=/HELPER_JOB= ONLY when
│ change_detection.py       │  variant in ('helper','aep_billable_helper',
│ calculate_data_hash /     │  'reduced_sub_helper') (415-437) — byte-identity guarantee
│ derive_group_identity     │  (orchestrate.py:460-528) dispatches the SAME tuple for the
│ (via orchestrate.py)      │  history-key / filename identifier (one function, 3 call sites)
└──────────┬───────────────┘
           ▼
┌─────────────────────────┐  variant_suffix = "_Helper_<name>" / "_AEPBillable_Helper_<name>" /
│ excel.py generate_excel   │  "_ReducedSub_Helper_<name>" (255-360); REPORT DETAILS header
│                           │  reads __helper_dept/__helper_job, not primary Dept#/Job# (540-570)
└──────────┬───────────────┘
           ▼
┌─────────────────────────┐  build_group_identity re-parses the filename by EARLIEST
│ cleanup.py + upload.py    │  reserved-token position (736-812); orphan-supersede gate
│                           │  (cleanup.py:518-520) and PPP dual-route gate
│                           │  (upload.py:343) are variant-tuple literals — MUST list helper2
└──────────┬───────────────┘
           ▼
   TARGET_SHEET_ID (+ SUBCONTRACTOR_PPP_SHEET_ID for reduced_sub* variants)
           │
           ▼
┌─────────────────────────┐  billing_audit.freeze_row writes p_helper (never p_helper2
│ Supabase (async/optional) │  today); pipeline_memory row_state writes helper_* (never
│ billing_audit +           │  helper2_* today); scripts/publish_artifacts_to_supabase.py
│ pipeline_memory           │  normalize_variant maps filename → DB variant column
└─────────────────────────┘
```

### Helper #1 Impact Map (audit item 1) — what Helper #2 must mirror vs. keep independent

Every row below was read this session (`Read`/`Grep`) against current `HEAD`, not the prototype.

| Stage | File:Function (Helper #1 evidence) | What Helper #2 mirrors | What stays independent |
|---|---|---|---|
| Discovery — synonyms | `pipeline/discovery.py:555-579` `synonyms` dict maps `'Foreman Helping?':'Foreman Helping?'`, `'Helper Dept #':'Helper Dept #'`, `'Helper Job [#]':'Helper Job #'`, etc. `[VERIFIED: pipeline/discovery.py:555-579]` | Add 6 new synonym entries for the exact titles in D-14-10 (`Foreman Helping? #2` → itself, `Helper #2 Job [#]` → canonical `Helper #2 Job #`, mirroring the existing bracket-form handling) | Existing Helper #1 synonym keys are untouched — additive dict entries only |
| Discovery — cached-mapping skip | `pipeline/discovery.py:190-297` `_build_discovery_skip_index`; used at `:438,452-461` — a version-matched `sheet_registry` row returns its STORED `column_mapping` verbatim, bypassing the synonyms pass entirely. `[VERIFIED: pipeline/discovery.py:220-297,443-461]` | D-14-10: admission test needs a mapping-schema marker so a pre-Helper-#2 cached mapping (written before this synonym set existed) falls through to full validation once | The 5 existing admission conditions (registry row exists, live version matches, mapping non-empty + has `Weekly Reference Logged Date`, name non-empty) are unchanged |
| Discovery — acceptance gate | `pipeline/discovery.py:668-681` — the ONLY strict-mode gate is `'Weekly Reference Logged Date' in mapping`; a sheet with zero Helper #2 columns still passes. `[VERIFIED: pipeline/discovery.py:668-681]` | Nothing — Helper #2 columns are never part of the acceptance gate (D-14-02, D-14-04) | Gate logic is 100% untouched; this is exactly why Intake 8 (no Helper #2 cols) is still accepted today (D-14-01) |
| Discovery — failed-read handling | `pipeline/discovery.py:682-697` — any exception during validation is Sentry-captured (PII-stripped) and the sid is appended to `_failed_validation_sids`, which aborts the run rather than silently continuing short. `[VERIFIED: pipeline/discovery.py:682-697]` | Helper #2's capability check must never route through this path — "no Helper #2 columns" is a legitimate mapping outcome, not an exception | Existing fail-closed behavior for genuine read failures is unchanged (D-14-02's 4th distinguishable condition) |
| Fetch — capability logging | `pipeline/fetch.py:553-570` — Helper #1 does a **log-only** 4-column presence check (`554-563`, only warns if incomplete, never gates); `sheet_has_vac_crew_columns` (`566,570`) is a **hard boolean gate**: `'VAC Crew Helping?' in column_mapping and 'Vac Crew Completed Unit?' in column_mapping`. `[VERIFIED: pipeline/fetch.py:553-570]` — quoted verbatim: `sheet_has_vac_crew_columns = 'VAC Crew Helping?' in column_mapping and 'Vac Crew Completed Unit?' in column_mapping` | D-14-04 explicitly picks the VAC-crew pattern (hard gate on 3 key columns: name/completed/dept mapped) over Helper #1's log-only pattern — this is a deliberate deviation, not a mirror | Helper #1's own log-only check is untouched |
| Fetch — row detection | `pipeline/fetch.py:851-885` — `is_helper_row = bool(helper_name and helping_foreman_completed_checked and units_completed_checked)`, then populates `__is_helper_row`, `__helper_foreman`, `__helper_dept`, `__helper_job` (no truthiness check on dept/job here — that happens in grouping). `[VERIFIED: pipeline/fetch.py:859,869-876]` — quoted: `is_helper_row = bool(helper_name and helping_foreman_completed_checked and units_completed_checked)` | Slot-shifted clone: `is_helper2_row` reading `Foreman Helping? #2` / `Helping Foreman #2 Completed Unit?`, writing `__is_helper2_row`, `__helper2_foreman`, `__helper2_dept`, `__helper2_job` | `Foreman Helper Active?` / `Foreman Helper Email` are read nowhere in this block — confirms D-14-04's claim that Helper #1 ignores them; Helper #2's Active?/Email columns must be equally non-gating |
| Fetch — dual-checkbox recompute | `pipeline/fetch.py:974-981` — inside the `price_missing_or_zero` exclusion diagnostic branch, `_fh_helping`/`_fh_completed` are recomputed independently from the earlier `helper_name`/`helping_foreman_completed_checked` values, purely for a log-tag decision (`'helper'` vs `'VAC crew'`). `[VERIFIED: pipeline/fetch.py:974-981]` | A Helper #2 clone of this diagnostic recompute, OR fold both slots into the existing `_is_specialized` check — planner's call, non-functional (logging only) | This branch only fires when a row was excluded for missing/zero price; does not affect eligibility |
| Grouping — primary exclusion (billing_audit pre-pass) | `pipeline/grouping.py:360-389` — a pre-pass that resolves primary claimers skips rows where `__is_helper_row and __helper_foreman and __helper_dept` are all truthy, because "valid helper rows are excluded from the primary emission path, so resolving their primary claimer is pure overhead." `[VERIFIED: pipeline/grouping.py:372-379]` | Helper #2 valid rows must be excluded from this pre-pass the same way | VAC-crew rows are already excluded first (`:370-371`) — ordering matters if a row could be both |
| Grouping — main-loop exclusion + helper key emission | `pipeline/grouping.py:614-742` — `valid_helper_row = helper_mode_enabled and is_helper_row and helper_foreman and helper_dept` (dept required, job optional per `625`); when true, the primary branch is skipped (`693-697`) and `keys_to_add.append(('helper', helper_key, helper_foreman))` fires ONLY when `not is_subcontractor_row` (`721-724`) — subcontractor rows get a debug-only log instead (`725-734`), because their credit lives exclusively in the shadow variants below. `[VERIFIED: pipeline/grouping.py:619-626,693-697,721-734]` | Full clone: `valid_helper2_row`, its own primary-exclusion branch, its own `('helper2', ...)` key emission gated by `not is_subcontractor_row` | `RES_GROUPING_MODE` kill-switch semantics (`'primary'` sends helper rows to main) apply identically — reuse the same env var, do not add a second switch |
| Grouping — subcontractor shadow partition | `pipeline/grouping.py:790-838` (primary-variant leg) and `:940-1090+` (helper-variant leg, claim-history attribution via `resolve_claimer`) — a subcontractor helper-completed row is EXCLUDED from the sub-primary `_USER_` key (`_sub_is_valid_helper_row`, `814-820`) and instead partitioned by the FROZEN helper foreman when `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED`, falling back to the current Smartsheet value on any lookup failure (D-12 default, never a HOLD). `[VERIFIED: pipeline/grouping.py:814-820,975,1012-1057]` | Same pattern for Helper #2, calling `resolve_claimer('helper2', ...)` once `ROLE_BY_VARIANT` knows that variant | The per-WR dedupe warning set (`_bug_c_warning_seen`) and remediation-text branching (fetch_failure vs unavailable vs no_history) are reusable verbatim — just key on the Helper #2 tuple too |
| Grouping — shadow variant tokens | `pipeline/grouping.py:1159` (`'reduced_sub_helper'`), `:1177` (`'aep_billable_helper'`); filename-shape comments at `:1261-1262,1327-1328` document `MMDDYY_WR_REDUCEDSUB_HELPER_<name>` / `MMDDYY_WR_AEPBILLABLE_HELPER_<name>`. `[VERIFIED: pipeline/grouping.py:1159,1177,1261-1262]` | New tokens `reduced_sub_helper2` / `aep_billable_helper2` (or planner's chosen spelling) at the equivalent `keys_to_add.append(...)` sites | Existing token spellings are untouched |
| Change detection — base hash fields | `pipeline/change_detection.py:48-90` `_extended_row_fields` — the 16 base fields (WR, snapshot date, CU, quantity, price, pole, work type, dept, scope, completed, customer, job, work order, CU description, UOM, area) contain **no helper fields at all**. `[VERIFIED: pipeline/change_detection.py:60-78]` | No change needed — Helper #2 identity does not belong in the base per-row tuple, exactly like Helper #1 | This function is variant-agnostic by design; do not add helper2 fields here |
| Change detection — variant-gated meta | `pipeline/change_detection.py:415-437` — `if variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'): meta_parts.append(f"HELPER={helper_foreman}") ...` reading `sorted_rows[0]`. `[VERIFIED: pipeline/change_detection.py:417,435-437]` — quoted: `if variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):` | Add a second `if variant in ('helper2', 'aep_billable_helper2', 'reduced_sub_helper2'): meta_parts.append(f"HELPER2=...")` block — THIS is the mechanism that makes HLP-06 (byte-identical when Helper #2 absent) hold: primary/Helper#1/VAC hashes never see a `HELPER2=` token because their `variant` never matches this new tuple | The existing `if variant in ('helper', ...)` block's tuple must NOT be widened to include `helper2` — that would collapse Helper #1 and Helper #2 into the same hash-meta shape and violate HLP-02 |
| Change detection — aggregated hash | `pipeline/change_detection.py:482-545` `_compute_aggregated_content_hash` — special-cases ONLY `v == 'helper'` with per-`(foreman,dept,job)` sub-bucketing (`520-538`) because reading `sorted_rows[0]` breaks for a bucket containing multiple helpers; every OTHER variant (including today's `aep_billable_helper`/`reduced_sub_helper`!) falls to the generic `else: calculate_data_hash(variant_rows)` branch. `[VERIFIED: pipeline/change_detection.py:518-540]` | **New pitfall, not previously documented**: a `helper2` bucket needs the SAME sub-bucketing special-case, or multi-Helper#2 aggregation silently inherits the sort-order-dependent bug this code exists to prevent (see Common Pitfalls) | `aep_billable_helper`/`reduced_sub_helper` already fall to the generic branch today — confirm with the planner whether that is an existing latent gap (pending — resolve in execution task; out of Phase 14's stated scope unless it blocks Helper #2's identical shadow-variant shape) |
| Change detection — filename parse / precedence | `pipeline/change_detection.py:582-814` `build_group_identity` — dispatches on the tail's EARLIEST reserved-token position among `{AEPBillable, ReducedSub, VacCrew, Helper, User}` (`751-759`), not fixed order, specifically because a real name can itself contain a reserved word. `[VERIFIED: pipeline/change_detection.py:751-812]` — quoted: `_reserved_positions = {_tok: tail.index(_tok) for _tok in ('AEPBillable', 'ReducedSub', 'VacCrew', 'Helper', 'User') if _tok in tail}` | Add `'Helper2'` to the reserved-token set and its own elif branch (mirroring `elif _first_marker == 'Helper':`); verified this session that `"_Helper2_"` and `"_Helper_"` are mutually exclusive substrings (no collision with `_Helper_2Pac`-style names, CONTEXT.md's own example) | The AEPBillable/ReducedSub two-level nested dispatch (`post_aep`/`post_rs` checking for `'Helper'`) needs a parallel `'Helper2'` check inside those same branches — this is the exact site that emits `aep_billable_helper2`/`reduced_sub_helper2` on parse |
| Excel — filename suffix | `pipeline/excel.py:255-370` — `elif variant == 'aep_billable_helper':` / `elif variant == 'reduced_sub_helper':` / `elif variant == 'helper':` are three SEPARATE `elif` branches (not a shared tuple check), each building `variant_suffix` and each raising `ValueError` defensively if `__helper_foreman` is empty (the two shadow branches only — the legacy `helper` branch has a documented, deliberately out-of-scope silent-fallthrough gap, tests/test_subcontractor_pricing.py). `[VERIFIED: pipeline/excel.py:282-344]` | Three new sibling `elif` branches for `aep_billable_helper2`/`reduced_sub_helper2`/`helper2`, each reading `__helper2_foreman` | Do not fold Helper #2 into the existing branches — they are exact-match `elif`, so a missed branch means Helper #2 rows fall through to the bottom of the chain (primary or vac_crew handling) — same failure class as ledger `[2026-05-21 12:35]` |
| Excel — REPORT DETAILS header | `pipeline/excel.py:542-580` — `if variant == 'helper':` reads `__helper_foreman`/`__helper_dept`/`__helper_job`; `elif variant in ('reduced_sub_helper', 'aep_billable_helper'):` reads `__helper_dept`/`__helper_job` but displays `current_foreman` (the ATTRIBUTED claimer, not `__helper_foreman`) — a deliberate distinction the code comments call out as a previously-shipped defect fix (ledger `[2026-05-21 12:35]`, read this session). `[VERIFIED: pipeline/excel.py:545-566]` | Mirror both branches for `helper2`/`{aep_billable,reduced_sub}_helper2`, preserving the same `current_foreman`-vs-`__helper_foreman` distinction for the shadow pair | This is the EXACT bug class from the ledger entry — an exact-match variant gate that a new tuple member falls through — Phase 14 must not repeat it for Helper #2 |
| Orchestrate — single group-identity chokepoint | `pipeline/orchestrate.py:460-528` `derive_group_identity(first_row, ...)` — ONE function feeding THREE call sites (main-loop identifier/file_identifier/history_key; `valid_wr_weeks` attachment-cleanup tuple; `current_keys` hash-history prune), specifically extracted (per its own docstring) because "before this extraction each site carried its own copy of the branch chain" and a drift between copies caused "a fresh history key treated as stale, live attachments pruned, permanent regeneration churn." `[VERIFIED: pipeline/orchestrate.py:460-508]` | Add ONE new `if variant in ('helper2', 'aep_billable_helper2', 'reduced_sub_helper2'):` branch here (mirroring the existing `if variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):` at `:499`) — because of this refactor, Helper #2 needs exactly ONE new branch, not three | This is the single highest-leverage, lowest-risk file in the whole change — `tests/test_group_identity_and_header_foreman.py` already pins this function's contract per-branch |
| Cleanup — legacy/placeholder rules | `pipeline/cleanup.py:198-293` (params), `:385-470` (matching logic) — every one-time-migration gate (`sub_offcontract_variants`, `sub_legacy_primary_variants`, `vac_legacy_wr_scope`, `primary_wr_scope`) matches against KNOWN existing variant strings only; none reference a variant that doesn't exist yet. `[VERIFIED: pipeline/cleanup.py:249-256,406-474]` | No changes needed for the ONE-TIME migration gates — a Helper #2 filename is a brand-new identity, never a "legacy" one, so these gates correctly ignore it by construction | — |
| Cleanup — orphan-supersede gate (NEW FINDING) | `pipeline/cleanup.py:497-546` — `_HELPER_VARIANTS_FOR_ORPHAN_GATE = frozenset({'helper', 'aep_billable_helper', 'reduced_sub_helper'})` (`518-520`) detects "a primary attachment superseded by a live helper for the same WR/week" for Sentry-tagged cleanup logging. `[VERIFIED: pipeline/cleanup.py:518-520]` — quoted verbatim above | **MUST add** `'helper2'`/`'aep_billable_helper2'`/`'reduced_sub_helper2'` to this frozenset, or a primary attachment superseded only by a Helper #2 claim is never flagged as a migration orphan (stale-file risk, not data loss) | Not named in the audit-scope's line-anchor list — discovered by reading the full file this session |
| Cleanup — sentinel-superseded gate | `pipeline/cleanup.py:89-196` (`_is_sentinel_identifier`/`_is_real_name_identifier`) + `:548-611` (gate logic) — uses `billing_audit.writer.is_sentinel_claimer`, a variant-agnostic name check, plus a fixed `_SANITIZED_ERROR_IDENTIFIERS` allowlist (`98-113`, e.g. `'no match'`, `'invalid'`) | No structural change needed — this gate is variant-generic; it will work for Helper #2 automatically, PROVIDED Helper #2's own "unknown" placeholder spelling (if the display fallback introduces one, e.g. `'Unknown Helper 2'`) is added to `_SENTINEL_CLAIMERS` in `billing_audit/writer.py` (see next row) | `_is_sentinel_identifier`/`_is_real_name_identifier` themselves need zero edits |
| Upload — PPP dual-route gate (NEW FINDING) | `pipeline/upload.py:253-366`, specifically `:343` — `if variant in ('reduced_sub', 'reduced_sub_helper'):` is the ONLY place that decides a group's task also routes to `SUBCONTRACTOR_PPP_SHEET_ID`. `[VERIFIED: pipeline/upload.py:343]` — quoted verbatim above | **MUST add** `'reduced_sub_helper2'` to this tuple, or a subcontractor Helper #2 shadow file uploads to `TARGET_SHEET_ID` only and the subcontractor is never shown it on the PPP sheet | Not named in the audit-scope's line-anchor list (which cited `upload.py:42`, a docstring) — discovered by reading the full module this session; this is the single easiest site to miss because it produces no error, just a silent routing gap |
| billing_audit — sentinel claimer names | `billing_audit/writer.py:79-115` `_SENTINEL_CLAIMERS` frozenset (`"unknown foreman"`, `"unknown"`, `"unknown helper"`, `"unknown vac crew"`, `"no match"`, …) + `is_sentinel_claimer()`. `[VERIFIED: billing_audit/writer.py:96-101,105-115]` | If Helper #2's Excel display fallback introduces a new placeholder string (e.g. `'Unknown Helper 2'`, mirroring `excel.py`'s `'Unknown Helper'` fallback at `:547`), add its normalized form to `_SENTINEL_CLAIMERS` | The check is casefold+`_`→space normalized already, so `Unknown_Helper_2` and `unknown helper 2` are treated identically once added |
| billing_audit — freeze_row all-sentinel short-circuit (CRITICAL PITFALL) | `billing_audit/writer.py:625-636` — `p_primary`, `p_helper`, `p_vac_crew` are computed, then `if all(is_sentinel_claimer(v) for v in (p_primary, p_helper, p_vac_crew)): return False` (deferred, RPC never called). `[VERIFIED: billing_audit/writer.py:630-636]` — quoted verbatim above | **MUST add** a `p_helper2` computation AND add it to this `all(...)` tuple — otherwise a row where Helper #2 is the ONLY real claimer (primary/helper/vac_crew all sentinel) is misclassified as fully-sentinel and `freeze_attribution` is never invoked, silently dropping the Helper #2 freeze | This is the single most dangerous silent-drop risk found this session — it fails with NO error, NO log distinguishable from a genuinely-sentinel row, and NO test would catch it unless the test specifically constructs "Helper #2 is the only real name on this row" |
| billing_audit — ROLE_BY_VARIANT / resolve_claimer | `billing_audit/writer.py:1047-1055` (dict), `:1058-1134` (`resolve_claimer`, reads `row.get(role)` from the RPC-returned row). `[VERIFIED: billing_audit/writer.py:1047-1055,1129-1130]` — full current dict quoted: `{"primary": "primary_foreman", "reduced_sub": "primary_foreman", "aep_billable": "primary_foreman", "helper": "helper", "reduced_sub_helper": "helper", "aep_billable_helper": "helper", "vac_crew": "vac_crew"}` | Add `"helper2": "helper2", "reduced_sub_helper2": "helper2", "aep_billable_helper2": "helper2"` — but the `"helper2"` role key only resolves to a real value once the RPC actually returns a `helper2` column (see schema.sql row below) | `freeze_row`'s docstring (`543-549`) explicitly enumerates "the 7 variant strings" as the current valid set for its `variant` kwarg — that enumeration is now stale documentation once Helper #2 ships (update it) |
| Supabase — `freeze_attribution` RPC params | `billing_audit/schema.sql:180-201` documents params `p_primary, p_helper, p_helper_dept, p_vac_crew, p_pole, p_cu, p_work_type, p_release, p_run_id, p_wr, p_week_ending, p_smartsheet_row_id` — **no `p_helper2`/`p_helper2_dept` today**. `[VERIFIED: billing_audit/schema.sql:181-192]` | Add `p_helper2 TEXT`, `p_helper2_dept TEXT` params + corresponding `attribution_snapshot` columns (`frozen_helper2`, `frozen_helper2_dept`) — this is the protected-area schema/RPC change D-14-07 calls out; needs `checkpoint:decision` | `p_vac_crew` has no `_dept` sibling at all today (asymmetry already exists in the current schema — not a Helper #2 concern, just noted for planner awareness) |
| Supabase — `lookup_attribution` / `lookup_attribution_bulk` RPC return shape (DROP-FIRST NUANCE) | `billing_audit/schema.sql:332-343` documents that `lookup_attribution`'s return-column change REQUIRES `DROP FUNCTION IF EXISTS` first because "Postgres CREATE OR REPLACE FUNCTION cannot change a function's return columns" (a real 2026-05-27 incident where a bare CREATE OR REPLACE silently never deployed). The comment at `:382-386` for `lookup_attribution_bulk` says only "apply this CREATE OR REPLACE" — but `lookup_attribution_bulk` (`:387-414`) has the IDENTICAL `RETURNS TABLE (...)` shape problem. `[VERIFIED: billing_audit/schema.sql:336-343,382-399]` | **Both** RPCs need a DROP-first sequence when adding a `helper2`/`helper2_dept` return column — the schema.sql comment for the bulk RPC is itself stale/incomplete on this point and should be corrected in the same migration | This is a new finding this session: the documented DROP-first warning only names `lookup_attribution`, but the identical Postgres restriction applies to `lookup_attribution_bulk`'s return table too |
| pipeline_memory — row_state helper columns | `pipeline_memory/schema.sql:100-126` DDL has `helper_observed, helper_completed, helper_dept, helper_job` — no `helper2_*` columns. `pipeline_memory/writer.py:786-807` builds the payload from `row_data.get("Foreman Helping?")` etc.; `HASH_FIELDS` (`:615-632`) is a **fixed 16-item tuple** consumed by `compute_content_hash` (`:635-645`) in that exact enumeration order. `[VERIFIED: pipeline_memory/schema.sql:100-126; pipeline_memory/writer.py:615-632,786-807]` — full current tuple quoted: `("wr","week_ending","snapshot_date","cu","pole","work_type","quantity","units_total_price","units_completed","foreman_observed","helper_observed","helper_completed","helper_dept","helper_job","vac_crew_observed","vac_completed")` | Add `helper2_observed, helper2_completed, helper2_dept, helper2_job` columns (additive) to schema + writer payload; D-14-08 defers to the planner WHETHER to also add them to `HASH_FIELDS` — doing so changes every row's `content_hash` once (one-time `row_event` for every row, matching 10-RESEARCH Pitfall 3, since `RUN_MEMORY_INCREMENTAL_ENABLED` is OFF in production this is currently a shadow-mode-only cost, not a production behavior change) | `content_hash` is scoped to business-content columns only (schema.sql comment `:93-97`) — this is a real, evidenced constraint, not a guess |
| scripts — normalize_variant / _CANONICAL_VARIANTS | `scripts/publish_artifacts_to_supabase.py:83-141` — `_CANONICAL_VARIANTS` is a 7-entry frozenset; `normalize_variant` is a 7-way substring-precedence chain (`_AEPBillable_Helper_` / `_ReducedSub_Helper_` checked BEFORE their bare `_AEPBillable`/`_ReducedSub` forms, which are checked before `_Helper_`). `[VERIFIED: scripts/publish_artifacts_to_supabase.py:85-93,114-141]` — full current chain quoted: `if "_AEPBillable_Helper_" in filename: return "aep_billable_helper"` / `if "_ReducedSub_Helper_" in filename: return "reduced_sub_helper"` / `if "_AEPBillable" in filename: ...` / `if "_ReducedSub" in filename: ...` / `if "_VacCrew" in filename: ...` / `if "_Helper_" in filename: return "helper"` / `return "primary"` | Add `_CANONICAL_VARIANTS` entries for the 3 new tokens; insert `if "_AEPBillable_Helper2_" in filename: return "aep_billable_helper2"` and `if "_ReducedSub_Helper2_" in filename: return "reduced_sub_helper2"` BEFORE the bare `_AEPBillable`/`_ReducedSub` checks, and `if "_Helper2_" in filename: return "helper2"` (verified this session: `"_Helper2_"` and `"_Helper_"` never both match the same real filename — see precedence note below) | An unrecognized variant token today only logs a WARNING (`:269-271`) and does not fail the publish step — so a missed Helper #2 branch here is a portal-metadata-quality gap, not a pipeline outage |
| portal-v2 — variant labels | `portal-v2/src/lib/variantLabels.ts` (full file read, 22 lines) — `VARIANT_LABELS` is a small exact-match map (`''→'Primary'`, `helper→'Helper'`, `vac_crew→'VAC Crew'`, `_AEPBillable→'AEP Billable (Sub)'`, `_ReducedSub→'Reduced Sub'`); `getVariantLabel()` falls back to `startsWith('_AEPBillable_Helper')` / `startsWith('_ReducedSub_Helper')` prefix checks, then a generic `variant.replace(/^_/,'').replace(/_/g,' ')`. `[VERIFIED: portal-v2/src/lib/variantLabels.ts:1-22]` | **Purely additive, not required for correctness** — a bare `helper2` token falls through to the generic fallback and displays as literal `"helper2"` (functional, just unpolished); `aep_billable_helper2`/`reduced_sub_helper2` tokens actually DO already match the existing `startsWith('_AEPBillable_Helper')`/`startsWith('_ReducedSub_Helper')` checks IF the DB stores the underscore-prefixed capitalized form — see note below | **Unresolved ambiguity, not blocking**: `VARIANT_LABELS`' keys mix snake_case (`helper`, `vac_crew` — matching `normalize_variant`'s output) with underscore-prefixed capitalized forms (`_AEPBillable`, `_ReducedSub` — NOT matching `normalize_variant`'s snake_case output). This inconsistency predates Phase 14 and is not caused by it; pending — resolve in execution task (confirm what `public.artifacts.variant` actually stores in production before deciding if portal label work is needed at all) |

### Recommended Project Structure

No new files or directories are required by default — every touched module already exists.
`pipeline/types.py` (currently a 24-line empty stub, confirmed read this session) is an optional
landing spot if the planner chooses the prototype's dataclass shape (see Don't Hand-Roll below).

### Pattern 1: Variant-tuple membership dispatch (the pattern to replicate)

**What:** Every stage that must treat "helper-family" variants uniformly checks membership in an
explicit tuple/frozenset (`('helper', 'aep_billable_helper', 'reduced_sub_helper')` or the
frozenset equivalent), never a single exact-match string and never a substring/prefix test on
`__variant`.
**When to use:** Any new code path that needs to know "is this row/group a helper-of-any-kind."
**Example (existing, current code):**
```python
# Source: pipeline/change_detection.py:417 (read this session)
if variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):
    meta_parts.append(f"HELPER={helper_foreman}")
```
The Helper #2 equivalent is a sibling `if` block with its own tuple — never widening the existing
tuple (that would collapse HLP-02's independence guarantee).

### Pattern 2: Single dispatch function feeding multiple call sites

**What:** `pipeline/orchestrate.py:derive_group_identity` (line 460) was extracted specifically to
stop 3 call sites from drifting out of sync with each other.
**When to use:** Whenever the same variant-dispatch logic would otherwise need to be duplicated.
**Example:**
```python
# Source: pipeline/orchestrate.py:498-508 (read this session)
variant = first_row.get('__variant', 'primary')
if variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):
    helper_foreman = first_row.get('__helper_foreman', '')
    helper_dept = first_row.get('__helper_dept', '')
    helper_job = first_row.get('__helper_job', '')
    identifier = f"{helper_foreman}|{helper_dept}|{helper_job}"
    file_identifier = (
        _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]
        if helper_foreman else ''
    )
    return identifier, file_identifier
```

### Anti-Patterns to Avoid

- **Exact-match `if variant == 'helper':` for a family of variants:** `pipeline/excel.py`'s
  REPORT DETAILS selector did exactly this and silently mis-displayed subcontractor helper-shadow
  rows until the `[2026-05-21 12:35]` fix (Living Ledger, read this session). Any new Helper #2
  branch must use the grouped-tuple form from day one.
- **Applying a guard to one branch of a per-row loop but not its sibling branch:** the
  `[2026-05-19 22:00]` incident (Living Ledger, read this session) was exactly this — the
  `is_subcontractor_row` guard was applied to the primary-key emission but forgotten on the
  legacy-helper-key emission in the same function, producing a duplicate-billing artifact in a
  live run. Every `keys_to_add.append(...)` site for Helper #2 needs the identical guard the
  Helper #1 sibling site has.
- **Widening an existing variant tuple instead of adding a parallel one:** would silently merge
  Helper #1 and Helper #2 hash/identity/display behavior and violate HLP-02.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Formula-error / non-claim value detection | A new ad-hoc blank/NA/#NO-MATCH check for Helper #2 | The pattern already used for CU exclusion (`'NO MATCH' in cu_text`, `fetch.py:842`) generalized, OR the prototype's `FORMULA_ERROR_VALUES` frozenset (`pipeline/types.py` hunk in the reference patch, lines 825-837) — an 11-token set covering `#BLOCKED`, `#CIRCULAR REFERENCE`, `#INVALID ...`, `#NO MATCH`, `#REF`, `#UNPARSEABLE` | Helper #1 today has NO such guard (that's the deferred "NA" quirk) — Helper #2 is a new path and D-14-05 requires it from day one; reinventing the token list risks missing a Smartsheet error spelling the prototype already enumerated |
| Sentinel/placeholder name detection | A second `is_sentinel_claimer`-like function scoped to Helper #2 | The existing `billing_audit.writer.is_sentinel_claimer` (`writer.py:105-115`) — already variant-agnostic, already used by `pipeline/cleanup.py`'s `_is_sentinel_identifier` | One source of truth for the "named placeholder" family, per the existing code comment (`writer.py:96`) — a second implementation would drift the moment either one is updated |
| Variant filename parsing | A new regex/parser for Helper #2 filenames | Extend `build_group_identity`'s existing earliest-reserved-token dispatch (`change_detection.py:751-812`) and `normalize_variant`'s existing precedence chain (`publish_artifacts_to_supabase.py:114-141`) | Both already solve the hard part (a real name containing a reserved word, hybrid AEPBillable/ReducedSub+Helper tokens) — a parallel parser would need to re-derive the same edge cases and would inevitably diverge from the canonical one two subprojects have already hardened |
| Multi-helper-slot data model | A generic `list[HelperAssignment]` per row for N helper slots | Two parallel scalar slots (Helper #1 fields, Helper #2 fields), matching D-14-03's explicit rejection of "a generic role engine" | Owner decision — no Helper #3 is requested; a generic model adds complexity without present value and every consumer (grouping, hashing, Excel headers) would need list-handling instead of two `if` branches |

## Affected Consumers — Disposition Summary (audit item 3)

Per-interface disposition: **CHANGE** (functional miss if not extended), **ADDITIVE** (safe to
extend, not required for core correctness), **REGRESSION-TEST-ONLY** (already variant-generic,
needs a new test but no code change), or **PROTECTED** (Supabase schema/RPC — needs
`checkpoint:decision`).

| Interface | Owning function:lines | Disposition | Constraint the new token(s) must satisfy |
|---|---|---|---|
| `pipeline/discovery.py` synonyms | `:555-579` | CHANGE | 6 new exact-title keys, additive to dict |
| `pipeline/discovery.py` skip-index admission | `_build_discovery_skip_index:190-297` | CHANGE | Add a mapping-schema marker check (D-14-10); must not weaken the existing 5 conditions |
| `pipeline/fetch.py` capability gate | new code, pattern at `:566,570` | CHANGE | Hard 3-column gate (name/completed/dept mapped), not Helper #1's log-only 4-column pattern (D-14-04 deviation) |
| `pipeline/fetch.py` row detection | new code, pattern at `:851-885` | CHANGE | Same boolean formula, slot-shifted field names |
| `pipeline/grouping.py` pre-pass exclusion | `:372-379` | CHANGE | Must exclude valid Helper #2 rows from primary-claimer pre-pass too |
| `pipeline/grouping.py` main-loop exclusion + key emission | `:619-742` | CHANGE | New `valid_helper2_row` + `('helper2', ...)` key, `not is_subcontractor_row` guard (mirror `[2026-05-19 22:00]` fix) |
| `pipeline/grouping.py` subcontractor shadow partition | `:790-1090+` | CHANGE | New `resolve_claimer('helper2', ...)` call once `ROLE_BY_VARIANT` supports it |
| `pipeline/change_detection.py` base hash fields | `_extended_row_fields:48-90` | NO CHANGE | Confirmed variant-agnostic; helper fields never belong here |
| `pipeline/change_detection.py` variant-gated meta | `calculate_data_hash:415-437` | CHANGE | New sibling `if variant in ('helper2', ...)` block — never widen the existing tuple |
| `pipeline/change_detection.py` aggregated hash | `_compute_aggregated_content_hash:482-545` | CHANGE (new finding) | New sub-bucketing special-case for `helper2`, mirroring the existing `helper` case exactly |
| `pipeline/change_detection.py` filename parse | `build_group_identity:582-814` | CHANGE | New `'Helper2'` reserved token + elif branch + nested AEPBillable/ReducedSub checks |
| `pipeline/excel.py` filename suffix | `:255-370` | CHANGE | 3 new sibling `elif` branches (not folded into existing ones) |
| `pipeline/excel.py` header display | `:542-580` | CHANGE | Mirror both the plain-helper and shadow-helper display branches, preserving `current_foreman`-vs-`__helper_foreman` distinction |
| `pipeline/orchestrate.py` group identity | `derive_group_identity:460-528` | CHANGE (single site) | One new tuple-gated branch feeds all 3 call sites automatically |
| `pipeline/cleanup.py` one-time legacy-migration gates | `:198-293,385-470` | NO CHANGE | Correctly variant-string-scoped; a new identity is never "legacy" |
| `pipeline/cleanup.py` orphan-supersede gate | `_HELPER_VARIANTS_FOR_ORPHAN_GATE:518-520` | CHANGE (new finding) | Add 3 new tokens to the frozenset |
| `pipeline/cleanup.py` sentinel-superseded gate | `:89-196,548-611` | REGRESSION-TEST-ONLY | Variant-agnostic already; needs a Helper #2-specific test, not a code change (unless a new placeholder string is introduced — see billing_audit row) |
| `pipeline/upload.py` PPP dual-route gate | `:343` | CHANGE (new finding) | Add `'reduced_sub_helper2'` to the tuple |
| `billing_audit/writer.py` `_SENTINEL_CLAIMERS` | `:96-101` | ADDITIVE | Only needed if Excel introduces a new "Unknown Helper 2"-style placeholder |
| `billing_audit/writer.py` `freeze_row` all-sentinel check | `:625-636` | CHANGE — CRITICAL | `p_helper2` MUST join the `all(is_sentinel_claimer(...))` tuple, or a Helper #2-only real claim is silently never frozen |
| `billing_audit/writer.py` `ROLE_BY_VARIANT` / `resolve_claimer` | `:1047-1055,1058-1134` | CHANGE | 3 new dict entries → `"helper2"` role; only resolves once schema row exists |
| `billing_audit/schema.sql` `freeze_attribution` RPC | `:180-201` | PROTECTED | New `p_helper2`/`p_helper2_dept` params + `attribution_snapshot` columns; `checkpoint:decision` |
| `billing_audit/schema.sql` `lookup_attribution` | `:332-373` | PROTECTED | DROP-first required (documented) |
| `billing_audit/schema.sql` `lookup_attribution_bulk` | `:375-414` | PROTECTED (new finding) | DROP-first ALSO required despite the comment saying "CREATE OR REPLACE" — same Postgres return-type restriction applies |
| `pipeline_memory/schema.sql` `row_state` | `:100-126` | CHANGE | Additive `helper2_*` columns |
| `pipeline_memory/writer.py` payload + `HASH_FIELDS` | `:615-632,786-807` | CHANGE (columns) / PLANNER DECISION (hash inclusion) | D-14-08: columns are additive; hash-tuple inclusion is a one-time-churn tradeoff the planner must state explicitly |
| `scripts/publish_artifacts_to_supabase.py` `_CANONICAL_VARIANTS`/`normalize_variant` | `:85-93,114-141` | CHANGE | 3 new frozenset entries + 3 new precedence-ordered branches |
| `portal-v2/src/lib/variantLabels.ts` | `:1-22` | ADDITIVE | Generic fallback already renders something non-crashing; friendly labels are UX polish |
| `portal-v2/.../VariantFilterBar.tsx` | grep-verified only, not fully read | ADDITIVE | Consumes `getVariantLabel()`; no direct variant-string logic of its own found |
| `.github/workflows/weekly-excel-generation.yml` `RES_GROUPING_MODE` | `:290` | NO CHANGE (inspect-only) | Confirmed `${{ github.event.inputs.res_grouping_mode \|\| 'both' }}` — Helper #2 reuses the same kill switch, no new workflow input needed unless the planner wants a separate rollout toggle (D-14-12 already specifies a separate `HELPER2_ENABLED`-style env flag instead) |

## Active Sources and Field Contracts (audit item 2)

`pipeline/config.py:309-311` (read this session) defines the folder universe:
```python
SUBCONTRACTOR_FOLDER_IDS = _parse_sheet_ids(os.getenv('SUBCONTRACTOR_FOLDER_IDS', '4232010517505924,2588197684307844'))
ORIGINAL_CONTRACT_FOLDER_IDS = _parse_sheet_ids(os.getenv('ORIGINAL_CONTRACT_FOLDER_IDS', '7644752003786628,8815193070299012'))
```
`[VERIFIED: pipeline/config.py:309,311]` — this confirms, from the code itself (not merely
repeating CONTEXT.md's claim), that Intake folder `8815193070299012` is one of the two default
`ORIGINAL_CONTRACT_FOLDER_IDS` folders `discover_folder_sheets` scans. Discovery then runs every
sheet found in these folders through `_validate_single_sheet` (`discovery.py:443-697`), whose ONLY
strict-mode acceptance gate is `'Weekly Reference Logged Date' in mapping` (`:668-681`) — Helper #2
column presence plays no role in whether a sheet is accepted as a source at all, confirmed by
reading the gate directly.

The following facts are **supplied by 14-CONTEXT.md as a live, read-only Smartsheet MCP
observation dated 2026-09-05** and are recorded here as-is, per the audit-scope instruction not to
re-verify them (no network/Smartsheet access is available in this research session):

- Intake Promax 8 (`2244739192541060`) is a direct child of Intake folder `8815193070299012`,
  maps `Weekly Reference Logged Date`, has the full Helper #1 column set, and has none of the six
  Helper #2 columns.
- Main ProMax (`3239244454645636`, 82 columns) has all six Helper #2 titles exactly as listed in
  D-14-10.
- Backup 2 (`2230129632694148`) is in `base_sheet_ids`, has a manual Helper #1 name, and has no
  Helper #2 columns.
- Live ProMax report `6761112897802116` is a report, not a generator source — column visibility
  there proves nothing about the generator (this is a general Smartsheet-architecture fact:
  reports do not appear in `discover_source_sheets`'s sheet-ID universe at all, confirmed by
  reading `pipeline/discovery.py` end-to-end this session — the discovery functions only ever
  operate on `client.Sheets.get_sheet` / folder-listing calls, never a report ID).

**Pending — resolve in execution task:** the exact live column IDs for the six Helper #2 titles on
Main ProMax, and whether any OTHER sheet in the 11-sheet Intake folder or the ProMax Database
folder already has partial Helper #2 columns, requires a live Smartsheet read this research session
could not perform (no token, no network access authorized). The planner/executor should re-run
the same read-only discovery-mapping probe before writing fixtures, and treat the CONTEXT.md
observation as a snapshot that may have drifted by execution time.

## Ownership, Timing, and Repeated Runs (audit item 4)

Three "already processed" mechanisms were investigated for whether they could suppress a later
Helper #2 completion:

1. **`billing_audit.writer.freeze_row` first-write-wins.** `[VERIFIED: billing_audit/writer.py:520-655]`
   Confirmed: `freeze_row` computes `p_primary`/`p_helper`/`p_vac_crew` independently and only
   defers the RPC (returns `False`, no write) when **all three** are sentinel (`:632-636`). Once
   Helper #2 adds `p_helper2`, this tuple must grow to four elements — see the CRITICAL pitfall
   in the Impact Map above. Provided that fix is made, the freeze RPC's per-role columns are
   independent (D-14-07 requirement: Helper #2 gets its own role, first-write-wins per role, never
   overwriting `frozen_helper`) — this is a natural consequence of the RPC writing named columns,
   not row-level exclusivity, confirmed by the params-doc at `schema.sql:180-192` (`p_helper` and
   `p_vac_crew` are independent columns already; the RPC's UPSERT semantics were not directly
   observable in this read-only pass — **pending — resolve in execution task**: confirm the
   `freeze_attribution` function body's UPSERT/`ON CONFLICT` clause, which lives in Supabase, not
   in the repo, per `schema.sql:213-219`'s own statement that "the table DDL itself is NOT defined
   here").
2. **`pipeline_memory.group_state` content-hash skip.** Not read in full this session (out of the
   audit's named anchor list beyond `row_state`) — **pending, resolve in execution task**: confirm
   whether `group_state`'s hash-skip path could suppress a Helper #2-only regeneration when
   `RUN_MEMORY_INCREMENTAL_ENABLED` is on. Given `change_detection.py:415-437`'s variant-gated
   `HELPER2=` meta token (once added) changes the group's content hash the moment a Helper #2
   completion appears, and hash-based skip logic (`_resolve_unchanged_for_skip`, read this
   session at `change_detection.py:817-848`) compares against the STORED hash for that
   `(wr, week, variant, identifier)` tuple — a brand-new `helper2` variant has no stored hash on
   its first run (`no_row` → `False` → regenerate, confirmed at `:829-832`), so the FIRST Helper #2
   completion cannot be suppressed by this mechanism structurally. A SUBSEQUENT Helper #2-only
   change on an EXISTING Helper #2 group depends on the hash actually changing, which depends on
   D-14-08's row_state-hash-inclusion decision only if the pipeline ever sources content from
   `row_state` instead of a live Smartsheet re-fetch — today's grouping/hashing reads live fetched
   rows (`INC-02`'s Option C hybrid, confirmed in REQUIREMENTS.md), so this is not a live concern
   for Phase 14 unless `RUN_MEMORY_INCREMENTAL_ENABLED` changes in the future (already flagged as
   a Deferred item).
3. **`sheet_registry` skip index.** `[VERIFIED: pipeline/discovery.py:190-297,443-461]` — already
   covered in depth above (D-14-10). This is a REAL suppression risk: a cached mapping from before
   Helper #2's synonyms existed would never be re-validated on an unchanged sheet, so Helper #2
   would silently never activate on that sheet until ITS version changes for an unrelated reason.
   This is the one mechanism in this list confirmed to have no self-correcting behavior today
   without the D-14-10 mapping-schema-marker fix.
4. **`_live_row_attachments` pre-seed.** Named in the audit scope but not read this session
   (`pipeline/orchestrate.py:1200-1244` per the earlier grep listing of `def` lines) — **pending,
   resolve in execution task**: confirm this pre-seed is keyed by `(wr, week, variant, identifier)`
   the same way `group_state` is, which would make it structurally safe for a brand-new `helper2`
   variant for the same first-run reason as #2 above, but this was not directly verified.

**D-14-09 claimant-source confirmation (CONTEXT.md's "must hold" requirement):** Confirmed this
session, by direct reading, which single value feeds each downstream consumer for a helper-family
row today:
- **Grouping key:** `helper_foreman` (the raw current `Foreman Helping?` value, or the frozen
  claim-history value for subcontractor rows) — `grouping.py:704,1151-1153`.
- **Hash meta:** `sorted_rows[0].get('__helper_foreman')` — `change_detection.py:427`.
- **Header display:** `__helper_foreman` for the plain `helper` variant, but `current_foreman`
  (the group's partition-key claimer) for the two shadow variants — `excel.py:547,564`. This
  asymmetry is real and intentional (ledger `[2026-05-21 12:35]`), not a bug — Helper #2 must
  replicate it exactly, not "fix" it into consistency.
- **Filename identifier:** `__helper_foreman`, sanitized — `orchestrate.py:500-507`,
  `excel.py:308,324,343`.
- **Attachment routing:** the parsed filename identifier (round-tripped through
  `build_group_identity`), consumed by `cleanup.py`/`upload.py`'s `valid_wr_weeks` tuples — not
  `__helper_foreman` directly at that stage, since cleanup/upload operate on already-generated
  filenames, not live row dicts.

## Findings Disposition (audit item 5)

| Finding | Disposition |
|---|---|
| Every "CHANGE" row in the Affected Consumers table above | Required Helper #2 implementation task |
| Base hash fields (`_extended_row_fields`), one-time legacy-migration cleanup gates, sentinel-superseded cleanup gate, `RES_GROUPING_MODE` kill switch | Existing behavior to preserve and verify (regression test, no code change) |
| Intake ProMax 8 exclusion-from-Helper-2-capability (has cols for #1, none for #2) | Accepted exception (D-14-01) — fixture test only, never a live-sheet remediation |
| Backup 2 (`2230129632694148`) — Helper #1 present, no Helper #2 columns | Accepted exception (capability-unavailable case, not a task) — CONTEXT.md Specifics section, not independently re-verified this session (no network access) |
| Missing optional Helper #2 capability on any otherwise-eligible sheet | Accepted exception, must be logged with a distinct reason (D-14-02/HLP-03) |
| Helper #1 `"NA"` fabricated-name quirk (`fetch.py:855-859` accepts any non-blank string) | Unrelated follow-up — explicitly Deferred; Phase 14 does NOT inherit this defect into the new Helper #2 path (D-14-05 requires the opposite: a formula-error guard from day one) |
| `aep_billable_helper`/`reduced_sub_helper` NOT special-cased in `_compute_aggregated_content_hash` today (falls to generic branch) | Unrelated follow-up — a demonstrated dependency was NOT found requiring Phase 14 to fix this for the EXISTING variants; flag for the planner as a nearby latent gap worth a one-line mention, not a blocking task, since Helper #2 introducing ITS OWN correctly-special-cased `helper2` bucket does not require touching the existing `helper`-only special case |
| `docs/ai/architecture.md`'s "three row variants" domain-model summary (94-101) not mentioning the four subcontractor shadow variants | Unrelated pre-existing doc-drift, out of Phase 14 scope — no dependency found requiring Phase 14 to fix it |
| O-14-A (both helper slots valid on same row) | Owner decision required before the conflict-handling task can be planned in detail; recommendation is "hold with visibility" per CONTEXT.md |

## Prototype Reference (audit item 6)

`.planning/phases/14-foreman-helper-2/reference/helper2-prototype-2026-07/` was read this session
(README, patch file-list via `diff --git` headers, the `pipeline/types.py` hunk in full, and the
first 70 lines of the runbook). `[VERIFIED: reference/helper2-prototype-2026-07/README.md:1-11;
helper2_prototype_vs_d11f20f.patch (diff headers); helper2_rollout_runbook.md:1-70]`

**Base state confirmed still current:** the patch's `pipeline/types.py` hunk diffs against a
24-line empty stub with the exact docstring "Phase-09 Wave 0 ships this as a STUB..." — reading
the CURRENT `pipeline/types.py` this session shows it is **still that identical 24-line stub**
(`[VERIFIED: pipeline/types.py:1-24]`), so this one hunk, at least, applies cleanly against
present-day `HEAD` if the planner chooses to reuse its shape.

**16 files the prototype touched** (from the patch's `diff --git` headers): `billing_audit/writer.py`,
`generate_weekly_pdfs.py`, `pipeline/attribution.py`, `pipeline/change_detection.py`,
`pipeline/cleanup.py`, `pipeline/config.py`, `pipeline/discovery.py`, `pipeline/excel.py`,
`pipeline/fetch.py`, `pipeline/grouping.py`, `pipeline/observability.py`, `pipeline/orchestrate.py`,
`pipeline/pricing.py`, `pipeline/types.py` (new content), `pipeline/upload.py`,
`scripts/publish_artifacts_to_supabase.py`. This file list is a strong external cross-check on the
Impact Map above — it independently touches the same core modules this session's code reading
identified, PLUS three modules not in the audit-scope's anchor list and not read this session:
`pipeline/attribution.py`, `pipeline/pricing.py`, `pipeline/observability.py`.
**Pending — resolve in execution task:** what those three hunks do (likely: `attribution.py` WR-scope
builders extended for a Helper #2 role; `pricing.py` — probably untouched pricing math, possibly
just a comment; `observability.py` — likely a new PII log-marker string for Helper #2 fields).
`generate_weekly_pdfs.py` being touched directly is most likely because the prototype's base
(2026-07-22, `d11f20f`) predates or straddles the Phase 9 facade-thinning work — **do not** target
the facade in the actual implementation; per `.claude/rules/python-module-architecture.md` and the
current `docs/ai/implementation-truth.md:38` facade description, all new behavior belongs in the
owning `pipeline/*`/`billing_audit/*`/`pipeline_memory/*` module.

**Reusable ideas, evaluated:**

| Prototype asset | Verdict |
|---|---|
| `FORMULA_ERROR_VALUES` frozenset (11 Smartsheet error tokens) | Reuse — directly implements D-14-05's fabricated-claim guard; no equivalent exists in current code for helper name fields (only for `CU`) |
| `HELPER_VARIANTS` / `HELPER2_VARIANTS` frozensets | Reuse the PATTERN (a named frozenset beats scattered tuple literals across a dozen call sites) — but note the CURRENT codebase's actual pattern is inline tuple literals at each site (`('helper', 'aep_billable_helper', 'reduced_sub_helper')`), not a shared imported constant; introducing a shared constant is a reasonable improvement but is a discretionary refactor the planner should decide on explicitly, not silently mix with the inline-literal style still used everywhere else |
| `normalize_helper_value()` | Reuse — thin wrapper combining strip + `FORMULA_ERROR_VALUES` check; matches D-14-05 exactly |
| `extract_contact_emails()` | Likely NOT needed — D-14-04 explicitly marks `Foreman Helper #2 Email` as non-gating optional metadata; only build this if the planner decides to actually surface the email somewhere (not currently required by any HLP-0x requirement) |
| `HelperAssignment` dataclass (`role: Literal[1,2]`, `is_valid` property) | Optional — a clean shape IF the planner wants a typed value object; current codebase style favors plain dict fields (`__helper_foreman` etc.) matching every other variant, so introducing a dataclass here is a stylistic choice, not a requirement |
| `HelperAssignmentConflictError` + import-time raise on conflict | **Rejected** (D-14-12, O-14-A) — CONTEXT.md is explicit that aborting the run on one bad row is "too blunt"; the recommended O-14-A resolution is HOLD-with-visibility, not an exception |
| `HELPER2_SOURCE_PROVEN` / `HELPER2_JOB_PRODUCER_PROVEN` import-fails-closed gate | **Rejected** (D-14-12) — operational preconditions belong in the runbook/pilot checklist, not as code that fails the whole module import |
| Runbook's "Required Columns" ordered list (6 columns, types/contact-options/hidden/locked copied from Helper #1) | Reuse as pilot-checklist content — this is Smartsheet-side column provisioning, already largely done per the CONTEXT.md D-14-10 live-verification (all 6 titles already exist on Main ProMax) |
| Runbook's dry-run-by-default safety gates (`--execute`, `PRODUCTION_SMARTSHEET_WRITE_APPROVED`, `--tests-passed`, `--approved-plan-sha256`) | Reuse the PATTERN for any Smartsheet-write tooling the plan introduces, if any — Phase 14 as scoped is generation-only (Smartsheet reads + Excel writes + attachment upload), so this may not apply unless the plan adds a column-provisioning script |

**Prototype test files** (`test_helper2_formula_generation.py.txt`, 482 lines;
`test_weekly_excel_helper_split.py.txt`, 303 lines — both renamed `.txt` so pytest never collects
them, confirmed by the reference README) were located but **not read in full this session**
(bounded scope) — **pending, resolve in execution task**: skim these two files during planning for
reusable test-case shapes (input fixtures, expected filename assertions), but treat every assertion
as needing re-validation against current code, since the prototype's base predates Phases 10-12
(run memory, INC-05 retirement, ownership ladder) per the reference README's own statement.

## Common Pitfalls

### Pitfall 1: Exact-match variant gate silently swallows a new variant (HIGH severity, real precedent)
**What goes wrong:** A stage that dispatches with `if variant == 'helper':` / `elif variant ==
'vac_crew':` / `else:` (primary) silently routes an unrecognized new variant into the `else`
(primary) branch instead of raising or logging.
**Why it happens:** Exact-match dispatch was written before the variant vocabulary grew; nobody
touches it again until a new variant is added and the bottom `else` masks the miss.
**How to avoid:** Every new Helper #2 branch must be added as an explicit sibling branch (`elif
variant == 'helper2':` or `elif variant in (...)`), verified against a test that specifically
constructs a Helper #2-variant row and asserts it does NOT take the primary/vac_crew path.
**Warning signs:** A Helper #2 Excel file shows the PRIMARY `Dept #`/`Job #` instead of
`Helper #2 Dept #`/`Helper #2 Job #` — this is the literal symptom of the real
`[2026-05-21 12:35]` incident (`pipeline/excel.py`'s REPORT DETAILS selector), read this session
from the Living Ledger.

### Pitfall 2: A guard applied to one branch of a per-row loop but not its sibling (HIGH severity, real precedent)
**What goes wrong:** `is_subcontractor_row` (or an equivalent per-row boolean) is threaded through
the primary-key emission branch correctly but the parallel helper-key emission branch in the same
function is missed, because the two branches are physically separated in the function body.
**Why it happens:** The two `keys_to_add.append(...)` call sites for a given row do not share a
single code path; adding a guard to one does not propagate to the other.
**How to avoid:** When adding the Helper #2 `keys_to_add.append(('helper2', ...))` site in
`grouping.py`, copy the EXACT guard structure (`if not is_subcontractor_row: ... else: <debug log>`)
from the adjacent Helper #1 site (`grouping.py:721-734`), not a re-derived version.
**Warning signs:** A subcontractor Helper #2 row appears in BOTH `TARGET_SHEET_ID`'s legacy
`_Helper2_<name>` file AND the correct `_ReducedSub_Helper2_<name>`/`_AEPBillable_Helper2_<name>`
shadow file — this is the literal symptom of the real `[2026-05-19 22:00]` incident (a live,
UAT-confirmed duplicate-billing artifact), read this session from the Living Ledger.

### Pitfall 3: A "family" frozenset/tuple defined at one call site is not updated at every OTHER call site that needs the same family (HIGH severity, new finding this session)
**What goes wrong:** The codebase has at least four INDEPENDENT places that enumerate
"the helper-family variant strings" as inline literals: `change_detection.py:417`,
`cleanup.py:518-520`, `upload.py:343`, and (implicitly) `orchestrate.py:499`. There is no single
shared constant — each site owns its own literal tuple/frozenset. Extending Helper #1's tuple to
include Helper #2 requires touching ALL of them; missing even one produces a silent, non-crashing
functional gap (this session found two such gaps not named in the audit-scope's anchor list:
`cleanup.py:518-520` and `upload.py:343`).
**Why it happens:** No compile-time or test-time check enforces that these four literals stay in
sync; they were each written independently as each subproject (B/C/D) shipped.
**How to avoid:** Grep for every occurrence of `'aep_billable_helper'` and `'reduced_sub_helper'`
literals repo-wide as the definitive checklist before considering the Helper #2 implementation
complete, rather than relying on the audit-scope's named anchor list alone (which itself missed
two real sites, corrected in this research).
**Warning signs:** A Helper #2 subcontractor shadow file uploads to `TARGET_SHEET_ID` but never
appears on the PPP sheet (upload.py:343 gap); a primary attachment superseded only by a Helper #2
claim is never cleaned up as a migration orphan (cleanup.py:518-520 gap).

### Pitfall 4: `freeze_row`'s all-sentinel short-circuit silently drops a Helper #2-only freeze (CRITICAL severity, new finding this session)
**What goes wrong:** `billing_audit/writer.py:632-636`'s `if all(is_sentinel_claimer(v) for v in
(p_primary, p_helper, p_vac_crew)): return False` will treat a row where Helper #2 is the ONLY
real claimer as fully-sentinel (since `p_helper2` is not in that tuple) and never call the
`freeze_attribution` RPC at all — no error, no distinguishing log line, and no attribution
snapshot for that row's Helper #2 role, ever, until some OTHER role also gets a real name (which
may never happen for a helper-only row).
**Why it happens:** The all-sentinel tuple was written before Helper #2 existed and is not
automatically widened by adding a new `p_helper2` parameter elsewhere in the function.
**How to avoid:** When adding `p_helper2 = _null_if_named_sentinel(row.get("__helper2_foreman"))`,
the SAME edit must add `p_helper2` to the `all(...)` generator's tuple.
**Warning signs:** Only discoverable by a test that constructs a row with a real Helper #2 name
and sentinel/blank primary+helper+vac_crew, then asserts `freeze_attribution` WAS called — a test
that only checks "the Excel file is correct" would never catch this, because Excel generation
does not depend on the freeze RPC succeeding.

### Pitfall 5: `_compute_aggregated_content_hash`'s per-variant special-casing must be replicated for `helper2` (MEDIUM severity, new finding this session)
**What goes wrong:** `change_detection.py:482-545` reads `sorted_rows[0]` for a variant's identity
UNLESS that variant is specially sub-bucketed (today, only `helper` is). A `helper2` bucket
aggregating rows from multiple Helper #2 foremen without the same sub-bucketing would silently
depend on row sort order and would only capture the first Helper #2's identity.
**Why it happens:** This aggregation path serves `billing_audit` integration, a separate
consumer from the main per-group hash path (`calculate_data_hash`), and the two were not written
by the same change.
**How to avoid:** Copy the exact `if v == 'helper': <sub-bucket by (foreman,dept,job)>` shape
(`:520-538`) for `v == 'helper2'`.
**Warning signs:** A `pipeline_run.content_hash` for a WR/week with 2+ distinct Helper #2 foremen
does not change when a non-first Helper #2's identity changes — very hard to notice without a
dedicated multi-helper2 test fixture.

### Pitfall 6: DROP-first is required for BOTH lookup RPCs, not just the documented one (MEDIUM severity, new finding this session)
**What goes wrong:** `billing_audit/schema.sql:382-386`'s operator instructions for
`lookup_attribution_bulk` say "apply this CREATE OR REPLACE" — but adding a `helper2`/
`helper2_dept` column to its `RETURNS TABLE (...)` shape hits the identical Postgres restriction
documented at `:336-341` for the single-row `lookup_attribution` ("cannot change return type of
existing function"). Following the bulk RPC's own comment literally would silently fail to deploy
the exact same way the `[incident 2026-05-27]` (documented in the same file) did for the
single-row RPC.
**Why it happens:** The bulk RPC's comment was written before this exact deploy failure mode was
discovered and documented on the single-row RPC below it in the same file; the comment above it
was never back-patched.
**How to avoid:** Apply `DROP FUNCTION IF EXISTS billing_audit.lookup_attribution_bulk(jsonb);`
before recreating it with the new return columns, exactly as the single-row RPC's migration does.
**Warning signs:** The migration "succeeds" (no error) but Helper #2 attribution reads always
return `NULL`/absent for the new column — the classic silent-non-deploy symptom the `:336-341`
comment already describes for the sibling function.

## Code Examples

### Adding a new helper-family variant branch (the pattern every touched module follows)
```python
# Pattern observed at 4+ independent sites this session:
# change_detection.py:417, cleanup.py:518-520 (as a frozenset), upload.py:343,
# orchestrate.py:499, excel.py:282/310/338 (as separate elif branches)
if variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):
    ...  # Helper #1-family behavior — DO NOT WIDEN THIS TUPLE
if variant in ('helper2', 'aep_billable_helper2', 'reduced_sub_helper2'):
    ...  # Helper #2-family behavior — NEW sibling block
```

### The eligibility formula to slot-shift (verified current Helper #1 code)
```python
# Source: pipeline/fetch.py:854-859 (read this session)
foreman_helping_val = row_data.get('Foreman Helping?')
helper_name = str(foreman_helping_val).strip() if foreman_helping_val else ''
helping_foreman_completed = row_data.get('Helping Foreman Completed Unit?')
helping_foreman_completed_checked = is_checked(helping_foreman_completed)
is_helper_row = bool(helper_name and helping_foreman_completed_checked and units_completed_checked)
```
The Helper #2 clone reads `'Foreman Helping? #2'` / `'Helping Foreman #2 Completed Unit?'` and
(per D-14-05, a deliberate deviation) should route `helper_name` through a formula-error guard
(`normalize_helper_value`-style) before the truthiness check — Helper #1's version does not do
this today (the deferred "NA" quirk).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Local JSON discovery cache / `hash_history.json` / `discovery_cache.json` | `pipeline_memory.sheet_registry` + `group_state` (Supabase) as the sole cross-run identity store | Phase 11 Plan 08 (INC-05) | Any Helper #2 caching concern must be reasoned about in terms of `sheet_registry`/`group_state`, never a local file — no local JSON cache pattern should be reintroduced |
| Placeholder sentinel names stored as real claimers | Sentinel-never-a-claimer (Phase 12/OWN-02): `is_sentinel_claimer` + `_null_if_named_sentinel` | 2026-09-01 (owner decision, ledger `[2026-09-01 19:45]`) | Helper #2's frozen role must be nulled the same way on a sentinel value, from day one — not retrofitted later |

**Deprecated/outdated:** The prototype's `HELPER2_SOURCE_PROVEN`/`HELPER2_JOB_PRODUCER_PROVEN`
import-time fail-closed gate and its `HelperAssignmentConflictError` abort-on-conflict are both
explicitly rejected by the current owner decision (D-14-12, O-14-A) — do not resurrect either
pattern even though they appear in the reference prototype.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pipeline_memory.group_state`'s hash-skip mechanics (not `row_state`) behave the same "no_row → regenerate" way `_resolve_unchanged_for_skip` documents for the Supabase-authoritative path | Ownership/Timing/Repeated Runs, item 2 | If `group_state`'s own skip logic differs from the documented `_resolve_unchanged_for_skip` contract, a first Helper #2 completion could theoretically be skipped — low risk since `_resolve_unchanged_for_skip` IS the function that reads `group_state`, but its full body beyond lines 817-848 was not read |
| A2 | `_live_row_attachments` pre-seed (`orchestrate.py:1200-1244`) is keyed the same way `group_state` is (by full identity tuple, not a coarser key) | Ownership/Timing/Repeated Runs, item 4 | If it is keyed more coarsely, a brand-new Helper #2 variant might not get its attachment pre-seeded correctly on first run — function body not read this session |
| A3 | `pipeline/attribution.py`, `pipeline/pricing.py`, `pipeline/observability.py` (touched by the prototype patch, outside the audit-scope's named anchors) need only minor/no changes for Helper #2 | Prototype Reference | If pricing or attribution logic has a helper-count-dependent branch not surfaced by this research, the planner could underscope a task; these three files were identified only via the prototype's file list, not read this session |
| A4 | The `freeze_attribution` Postgres function's UPSERT semantics key on `(wr, week_ending, smartsheet_row_id)` only (row-level), so per-role columns are independent and Helper #2 cannot collide with Helper #1's row in that RPC | Ownership/Timing/Repeated Runs, item 1 | The function body lives in Supabase, not the repo (`schema.sql:213-219` says so explicitly) — if the actual UPSERT logic is more complex (e.g., conditionally overwrites unrelated columns), D-14-07's "never overwrites `frozen_helper`" guarantee would need the RPC body itself patched, not just new params added |
| A5 | Portal-v2's `public.artifacts.variant` column stores the exact snake_case `normalize_variant()` output (not the underscore-capitalized filename token) for every row currently in production | Affected Consumers table, portal-v2 row | `VARIANT_LABELS`' own keys mix both conventions, which this research could not resolve without a live DB read; if the underscore-capitalized form is actually stored, the portal fallback behavior for Helper #2 tokens differs from what's stated |

## Open Questions

> Disposition markers added during plan revision (2026-09-05). Every question below carries either a
> `(RESOLVED → plan/task)` marker naming where it is closed, or an `(OPEN by owner instruction)`
> marker naming the checkpoint that gates it. O-14-A stays open deliberately — it is a business
> decision about money and no agent may close it.

1. **O-14-A: Same-row, both-helper-slots-valid conflict resolution.**
   **(OPEN by owner instruction → gated in 14-08 Task 1, `checkpoint:decision` with
   `gate="blocking-human"`.)** This is not an unanswered research question; it is a business rule
   reserved to Juan. The checkpoint enumerates the four options with their consequences and cannot be
   auto-resolved in any mode. 14-08 Task 2 is BLOCKED on the recorded answer.
   - What we know: CONTEXT.md frames four options and recommends "hold with visibility"
     (mirroring Subproject B's HOLD semantics); the prototype's abort-on-conflict approach is
     explicitly rejected.
   - What's unclear: The exact business rule for internal credit vs. subcontractor payment vs.
     customer billing when a row is legitimately double-checked.
   - Recommendation: Block only the conflict-handling task on Juan's decision; implement
     everything else in this research first, with the HOLD path stubbed to the recommended
     behavior pending confirmation.

2. **Same person in Helper #1 slot on some rows and Helper #2 slot on other rows, same WR/week.**
   **(RESOLVED → non-blocking by design; per-slot identity proceeds per D-14-06. The confirmation is
   asked as a documentation follow-up inside 14-08 Task 1, and the operator-facing note is written in
   14-10 Task 1.)** No code path waits on this; the only open part was whether operators need a
   runbook callout, and 14-10 Task 1 writes one either way.
   - What we know: CONTEXT.md's case table accepts "two files, one per slot" as a consequence of
     per-slot identity, and flags it "Juan to confirm... not blocking."
   - What's unclear: Whether this needs an explicit runbook callout for operators reviewing
     billing output.
   - Recommendation: Proceed with per-slot identity (matches D-14-06); add a one-line runbook note
     during the pilot-documentation task.

3. **`group_state`/`_live_row_attachments` exact keying (A1/A2 above).**
   **(RESOLVED → 14-02 Task 1, which reads the four call paths and writes a
   CONFIRMED SAFE / REQUIRES GUARD / STILL UNKNOWN verdict per mechanism into
   `14-PENDING-RESOLUTIONS.md` under `## A1` and `## A2`, in Wave 1 before any dependent plan makes a
   design choice.)** The companion module-scope gap (A3: `attribution.py`, `pricing.py`,
   `observability.py`) is resolved in 14-02 Task 2 under `## A3`.
   - What we know: The documented contract at `_resolve_unchanged_for_skip` (lines 817-848,
     verified) behaves safely for a brand-new variant's first run.
   - What's unclear: Full body of `group_state`'s read path and `_live_row_attachments` beyond
     what was read this session.
   - Recommendation: A quick read of `pipeline_memory/reader.py` (`get_group_state_attachments_by_wr`)
     and `orchestrate.py:1200-1244` at the start of planning, before writing the change-detection
     task, would close this gap cheaply.

## Environment Availability

Not applicable in the traditional sense — Phase 14 introduces no new external tool/runtime
dependency. The existing dependencies (Smartsheet SDK, Supabase client, pytest) are already
pinned in `requirements.txt` and already exercised by the current test suite; this research
session was explicitly barred from network/Smartsheet/Supabase access and from running
`generate_weekly_pdfs.py`, so no live probe of Smartsheet/Supabase reachability was performed or
attempted. **Pending — resolve in execution task:** confirm `SMARTSHEET_API_TOKEN` and Supabase
env vars are present in the execution environment before any `TEST_MODE`/`SKIP_UPLOAD` dry run.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (config in `pyproject.toml`; no separate `pytest.ini`/`setup.cfg`; no root or `tests/` `conftest.py` found this session) |
| Config file | `pyproject.toml` |
| Quick run command | `python -m py_compile generate_weekly_pdfs.py` (syntax gate), then a targeted `pytest tests/test_<module>.py -v` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HLP-01 | Eligible Helper #2 completion produces correct group key/hash/header/filename/attachment identity | unit | `pytest tests/test_group_identity_and_header_foreman.py -x` | ✅ (437 lines, verified exists) |
| HLP-01 | Change-detection hash includes Helper #2 fields only under Helper #2 variants | unit | `pytest tests/test_change_detection_tiebreak.py -x` | ✅ (472 lines, verified exists) |
| HLP-01 | Subcontractor Helper #2 shadow-file dual-routing (TARGET + PPP) | unit/integration | `pytest tests/test_subcontractor_helper_shadow_rescue.py -x` | ✅ (1523 lines, verified exists) |
| HLP-02 | Helper #1 outputs byte-identical with Helper #2 present or absent | regression | New parametrized case in `tests/test_group_identity_and_header_foreman.py` and `tests/test_change_detection_tiebreak.py` | ❌ Wave 0 — new test cases, not new files |
| HLP-03 | Sheet without Helper #2 columns skips only that path with a distinct log reason | unit | New test in a Helper #2-specific module (e.g. `tests/test_foreman_helper_2.py`, planner's naming choice) | ❌ Wave 0 — new file |
| HLP-04 | Intake 8 fixture (Helper #1 columns present, Helper #2 columns absent) never breaks discovery | unit | Same new Helper #2 test module, fixture-based (never live-sheet) | ❌ Wave 0 |
| HLP-05 | Blank/NA/#NO MATCH/unchecked/no-capability never creates a Helper #2 claim | unit | Same new Helper #2 test module | ❌ Wave 0 |
| HLP-05 | `freeze_row` all-sentinel check includes `p_helper2` (Pitfall 4) | unit | `pytest tests/test_billing_audit_shadow.py -x` (extend with a Helper#2-only-real-claimer case) | ✅ (5539 lines, verified exists) |
| HLP-06 | Later Helper #2 completion on an already-frozen row lands in its own role only; idempotent | unit | `pytest tests/test_billing_audit_shadow.py -x` | ✅ |
| HLP-06 | `pipeline_memory.row_state` Helper #2 columns additive; hash-inclusion decision explicit | unit | `pytest tests/test_pipeline_memory_shadow.py -x` | ✅ (2311 lines, verified exists) |
| HLP-06 | `scripts/publish_artifacts_to_supabase.py` normalizes new variant tokens correctly, precedence-safe | unit | `pytest tests/test_publish_artifacts_to_supabase.py -x` | ✅ (634 lines, verified exists) |
| HLP-06 | VAC-crew precedence over helper handling unaffected by Helper #2 | regression | `pytest tests/test_vac_crew.py tests/test_vac_crew_claim_attribution.py tests/test_vac_crew_exclusion_leak.py -x` | ✅ (3 files, verified exist) |
| HLP-07 | Feature flag default-off; fixture-only pilot when RA source is blank | manual + fixture | `TEST_MODE=true python generate_weekly_pdfs.py` (no token needed) — **manual-only** for the live-upload comparison step, justified because it requires a real Smartsheet write approval outside this phase's planning-only authorization | ✅ command exists per `CLAUDE.md` |

### Sampling Rate
- **Per task commit:** `python -m py_compile generate_weekly_pdfs.py` then the single most-relevant
  targeted test file from the map above (`pytest tests/test_<module>.py -x`).
- **Per wave merge:** `pytest tests/ -v` (full suite — this repo's CLAUDE.md-mandated gate before
  any push).
- **Phase gate:** Full suite green, plus `bash scripts/run_6_gates.sh` if any module is moved
  (not expected for this phase — all changes are additive edits to existing modules).

### Wave 0 Gaps
- [ ] A new Helper #2-specific test module (naming is planner's discretion per CONTEXT.md,
      e.g. `tests/test_foreman_helper_2.py`) covering HLP-03/HLP-04/HLP-05's fixture-only cases
      (Intake-8-shaped fixture: Helper #1 columns present, Helper #2 columns absent).
- [ ] New parametrized "Helper #2 absent → byte-identical" regression cases added to the EXISTING
      `tests/test_group_identity_and_header_foreman.py` and `tests/test_change_detection_tiebreak.py`
      (HLP-02/HLP-06) — comparing group keys, hashes, filenames, and meaningful cells, never binary
      file equality, per ROADMAP success criterion 2.
- [ ] A new test case in `tests/test_billing_audit_shadow.py` constructing a row where Helper #2
      is the ONLY real claimer (primary/helper/vac_crew all sentinel/blank) and asserting
      `freeze_attribution` IS still invoked — this is the regression test for Pitfall 4 (the
      CRITICAL all-sentinel short-circuit finding) and does not exist today since Helper #2 does
      not exist today.
- [ ] A new test case in `tests/test_publish_artifacts_to_supabase.py` for the 3 new variant
      tokens' precedence (confirming `_Helper2_` and `_Helper_` never cross-match, and
      `_AEPBillable_Helper2_`/`_ReducedSub_Helper2_` outrank their bare forms).
- [ ] A new test case in `tests/test_subcontractor_helper_shadow_rescue.py` (or a Helper-2-specific
      sibling) asserting a `reduced_sub_helper2` group's upload task includes BOTH
      `TARGET_SHEET_ID` and `SUBCONTRACTOR_PPP_SHEET_ID` — this is the regression test for the
      `upload.py:343` new finding.
- [ ] A new test case asserting `_HELPER_VARIANTS_FOR_ORPHAN_GATE` (or its Helper #2 successor)
      correctly flags a primary attachment superseded only by a Helper #2 claim — regression test
      for the `cleanup.py:518-520` new finding.

*Framework install: none — pytest and the full fixture/test harness already exist and are
exercised by the 59-plus existing modules in `tests/`.*

## Security Domain

`.planning/config.json` does not set `security_enforcement: false`, so this section is included
per the default-enabled rule.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | This phase touches no auth surface — Smartsheet token and Supabase service-role usage are unchanged, existing patterns |
| V3 Session Management | No | Not applicable — batch pipeline, no sessions |
| V4 Access Control | No | No new RBAC surface; portal-v2's existing RLS/role gating is untouched (variant label display is read-only, additive) |
| V5 Input Validation | Yes | Helper #2 field extraction must apply the SAME defensive `str(...).strip()` + formula-error-token guard (D-14-05) already used for other Smartsheet-sourced fields — never trust a Smartsheet cell value as pre-sanitized |
| V6 Cryptography | No | No new secrets, keys, or crypto operations introduced |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| PII leakage into Sentry/logs from a new helper-name field | Information Disclosure | Reuse the existing `_redact_exception_message` (`pipeline/observability.py`, confirmed imported by `pipeline/upload.py:30`) and the existing `_PII_LOG_MARKERS` pattern for any new log line naming a Helper #2 person; do not log raw helper names outside markers already vetted for PII scrubbing |
| Injection via a Helper #2 column value used unsanitized in a filename/identifier | Tampering | Reuse `_RE_SANITIZE_HELPER_NAME` (`pipeline/config.py:28`, confirmed `re.compile(r'[^\w\-]')`) for every new filename/identifier construction site — never build a Helper #2 identifier string without passing it through this sanitizer first |
| Supabase RPC schema drift causing silent data loss (the DROP-first Pitfall 6) | Tampering / Repudiation | Follow the documented DROP-first sequencing for BOTH `lookup_attribution` and `lookup_attribution_bulk`; verify via `NOTIFY pgrst, 'reload schema';` and a post-migration read-back before considering the migration complete |

## Sources

### Primary (HIGH confidence — read this session with `Read`/`Grep` against current `HEAD`)
- `pipeline/discovery.py`, `pipeline/fetch.py`, `pipeline/grouping.py`, `pipeline/change_detection.py`,
  `pipeline/excel.py`, `pipeline/orchestrate.py`, `pipeline/cleanup.py`, `pipeline/upload.py`,
  `pipeline/config.py`, `pipeline/types.py` — read directly, line ranges cited inline throughout.
- `billing_audit/writer.py`, `billing_audit/schema.sql` — read directly, line ranges cited inline.
- `pipeline_memory/writer.py`, `pipeline_memory/schema.sql` — read directly, line ranges cited inline.
- `scripts/publish_artifacts_to_supabase.py` — read directly, line ranges cited inline.
- `portal-v2/src/lib/variantLabels.ts` (full file), `portal-v2/src/components/artifacts/VariantFilterBar.tsx` (grep only) — read this session.
- `docs/ai/architecture.md:38-115`, `docs/ai/implementation-truth.md:38-92` — read this session.
- `memory-bank/living-ledger.md` entries `[2026-05-19 22:00]` and `[2026-05-21 12:35]` — read this session (exact headers differ slightly from CONTEXT.md's abbreviated `[2026-05-19]`/`[2026-05-21]` citation — full timestamps confirmed).
- `.github/workflows/weekly-excel-generation.yml:290` — read this session.
- `.planning/phases/14-foreman-helper-2/reference/helper2-prototype-2026-07/` (README, patch diff-headers, `pipeline/types.py` hunk in full, runbook lines 1-70) — read this session.
- `.planning/phases/14-foreman-helper-2/14-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` (Phase 12 and Phase 14 sections) — read this session.
- `tests/` — existence of all 6 named modules plus the 3 `test_vac_crew*.py` modules confirmed via directory listing this session (contents not read in full).

### Secondary (MEDIUM confidence)
- 14-CONTEXT.md's own live Smartsheet MCP observations (2026-09-05, read-only) — cited verbatim, not independently re-verified this session per the audit-scope's explicit instruction (no network/token access authorized).

### Tertiary (LOW confidence / not directly read this session)
- `pipeline/attribution.py`, `pipeline/pricing.py`, `pipeline/observability.py` — identified only via the prototype patch's file list; contents not read this session (Assumption A3).
- `pipeline_memory/reader.py` (`get_group_state_attachments_by_wr`), `pipeline/orchestrate.py:1200-1244` (`_live_row_attachments`) — named in the audit scope but not read in full this session (Assumptions A1/A2).
- The `freeze_attribution` Postgres function BODY (lives in Supabase, not the repo, per `schema.sql:213-219`'s own statement) — never available to a repo-only read (Assumption A4).

## Metadata

**Confidence breakdown:**
- Standard stack: N/A — no new dependencies.
- Architecture / impact map: HIGH — every claim in the impact map and disposition tables cites a specific file:line range read this session, with verbatim quotes for the load-bearing ones.
- Pitfalls: HIGH for Pitfalls 1-2 (real, documented production incidents) and MEDIUM-HIGH for Pitfalls 3-6 (new findings this session, derived from direct code reading, not yet confirmed by a failing test).
- Ownership/timing mechanics: MEDIUM — the `freeze_row`/`sheet_registry` mechanics are HIGH confidence (read directly); `group_state`/`_live_row_attachments` full keying behavior is LOW-MEDIUM (not fully read, flagged as Assumptions A1/A2).

**Research date:** 2026-09-05
**Valid until:** Treat as valid until the first Helper #2 implementation PR merges — this is a
fast-moving, actively-developed area of the codebase (Phases 10-13 all touched adjacent modules
within the prior two weeks), so re-verify line numbers against `HEAD` at plan time if more than a
few days elapse.

