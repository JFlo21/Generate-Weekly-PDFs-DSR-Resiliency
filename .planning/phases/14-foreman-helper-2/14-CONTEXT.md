# Phase 14: Foreman Helper #2 - Context

**Gathered:** 2026-09-05
**Status:** Ready for planning (planning-only authorization — no implementation, production
change, migration, workflow dispatch, push, merge, or deployment in this pass)

<domain>
## Phase Boundary

A second, independently identifiable helping-foreman slot — the `Foreman Helping? #2` column
family — flows through the existing Excel-generation workflow exactly the way Helper #1 does:
discovery and field extraction → completion eligibility → attribution → grouping → workbook
generation → incremental change detection → attachment publication. Primary foremen, Helper #1,
VAC crews, billing attribution, historical records, and the production Python ingestion are not
disrupted. Helper #2 is an extension of the Helping Foreman mechanism, not a replacement for
Helper #1 and not a pipeline rebuild.

**Owner (Juan) was not interviewed for implementation detail** — per the 2026-09-05 request,
"the same way we implemented Helping Foreman" is the default reference and technical choices
were resolved from the repository. Every decision below is tagged **[owner]** (confirmed by Juan
on 2026-09-05), **[repo]** (decided from code/docs evidence by the planning session), or
**[OPEN]** (a genuine business decision only Juan can make; only dependent work is blocked).

</domain>

<decisions>
## Implementation Decisions

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Owner decisions and requirements
- `.planning/ROADMAP.md` §"Phase 14: Foreman Helper #2" — goal, confirmed owner decisions,
  success criteria, planning-only authorization.
- `.planning/REQUIREMENTS.md` §"Foreman Helper #2 (Phase 14)" — HLP-01 … HLP-07.
- `.planning/ROADMAP.md` §"Phase 12" D-12-A … D-12-D — ownership ladder and sentinel rules
  Helper #2 attribution must follow.

### Production guardrails (must not regress)
- `CLAUDE.md` §"Production safety", §"Guardrails" — change-detection key, helper dual-checkbox
  rule, `safe_merge_cells()`, no `@cell`, `PARALLEL_WORKERS ≤ 8`, Job # synonyms,
  `advanced_options` parser, time budget.
- `.claude/rules/billing-pipeline-guardrails.md` — pointer index.
- `.claude/rules/python-module-architecture.md` — facade stays thin; behavior in the owning
  `pipeline/*` / `billing_audit/*` / `pipeline_memory/*` module.
- `docs/ai/architecture.md` §"Domain model — variants, grouping keys, metadata fields"
  (lines 92-112) — the three row variants, metadata fields, group keys, filename shapes.
- `docs/ai/implementation-truth.md` lines 42, 87-90 — grouping module and helper rules as
  verified.
- `memory-bank/living-ledger.md` entries `[2026-05-19]` (subcontractor helper asymmetry) and
  `[2026-05-21]` (helper-completed rows belong solely to helper files) — grep the headers; never
  load the whole file.

### Data contracts
- `billing_audit/schema.sql` lines 184-212 (`freeze_row` params, reader-dependent columns),
  317-365 and 394-412 (`lookup_attribution*` return columns), 336-339 (DROP-first rule for RPC
  return-column changes).
- `pipeline_memory/schema.sql` lines 96-125 (`row_state` helper columns and the fixed
  content-hash tuple contract).
- `billing_audit/writer.py` `ROLE_BY_VARIANT` (1047-1055), `freeze_row` payload (620-650),
  `_null_if_named_sentinel`.

### Prior Helper #2 work (reference evidence, NOT code to apply)
- `.planning/phases/14-foreman-helper-2/reference/helper2-prototype-2026-07/` — snapshot taken
  2026-09-05 of the uncommitted prototype found in the sibling clone
  `C:/Users/juflores/dev/Generate-Weekly-PDFs-DSR-Resiliency` (branch `master` at `d11f20f`,
  2026-07-22; 448 insertions across 16 files): `helper2_prototype_vs_d11f20f.patch`,
  `test_helper2_formula_generation.py`, `test_weekly_excel_helper_split.py`,
  `helper2_rollout_runbook.md`. Its base predates Phases 10-12 (run memory, INC-05 retirement,
  ownership); reuse ideas (types, tests, runbook sections), not hunks. Its pre-selected variant
  names and its import-time triple gate are candidates/rejected respectively (D-14-11, D-14-12).
- Vault (read-only, external to repo): `wiki/projects/Generate-Weekly-PDFs-DSR-Resiliency.md`
  §"Foreman Helper #2 rollout — Smartsheet side done, generator side dormant (2026-08-18 → 23)"
  — Smartsheet column rollout (644 columns / 109 sheets), RA column IDs `1589780186173316`
  (`Foreman Helper #2`) and `1303443306483588` (`Assigned Helper 2?`), Backup 2 skip, the
  `"NA"` quirk.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `sheet_has_vac_crew_columns` capability pattern (`pipeline/fetch.py:566`) — the per-sheet
  "key columns mapped → detection active, else skipped wholesale" gate Helper #2 should mirror.
- Helper #1 row detection block (`pipeline/fetch.py:851-885`) and `is_checked` — slot-shift for
  Helper #2; the `FILTER_DIAGNOSTICS` logging pattern carries over.
- `keys_to_add.append((variant, key, claimant))` (`pipeline/grouping.py:722`) and
  `_RE_SANITIZE_HELPER_NAME` (`pipeline/config.py:28`) — group-key emission and name sanitizing.
- `_extended_row_fields(x, variant)` + the sort/hash tuple (`pipeline/change_detection.py:183-192`)
  and the helper meta parts (`427-436`) — variant-aware hash inputs.
- `ROLE_BY_VARIANT` / `resolve_claimer` / `_null_if_named_sentinel` (`billing_audit/writer.py`).
- `normalize_variant` precedence chain (`scripts/publish_artifacts_to_supabase.py:114-140`).
- Prototype `pipeline/types.py` hunk — `FORMULA_ERROR_VALUES`, `normalize_helper_value`,
  `HelperAssignment` dataclass — a clean shape for the shared error-value contract.

### Established Patterns
- Variants are detected **per row, never per sheet**; each variant's Excel header reads its own
  fields with no fallthrough to the primary foreman or `Job #` (April-2026 Arrowhead leak).
- Change-detection identity is `(WR, week_ending, variant, foreman, dept, job)`; helper keys are
  six pipe-parts. Never shorten.
- Attachment identity resolves from `pipeline_memory.group_state` with per-row fallback; the
  Supabase hash store is authoritative; no local JSON caches.
- Cleanup is fail-safe: placeholder identities not produced this run are swept; named identities
  are never matched by the legacy-unpartitioned rules.
- Tests: `unittest`-style classes in `tests/` (59 modules), production-code-site invariant
  tests (`tests/test_subcontractor_helper_shadow_rescue.py:1351`), byte-identity regression
  fixtures for "feature absent" paths.

### Integration Points
- `pipeline/discovery.py:555-579` synonyms; `:190-230` skip index; `:668-680` acceptance gate.
- `pipeline/fetch.py:554-566` capability logging/gating; `:851-885` row detection;
  `:977` dual-checkbox recompute.
- `pipeline/grouping.py:370-379` primary-path exclusion; `:606-745` helper key emission;
  `:798-830` subcontractor helper partition; `:943-1090` attribution/claimant resolution.
- `pipeline/change_detection.py:183-192`, `:420-440`, `:497-530`, `:548-615`.
- `pipeline/excel.py:259-360` (suffix), `:540-570` (header), `pipeline/orchestrate.py:478-523`
  (group identity), `pipeline/cleanup.py` (above), `pipeline/upload.py:42`.
- `billing_audit/writer.py` (freeze/resolve), `pipeline_memory/writer.py:790-806` (row_state).
- `scripts/publish_artifacts_to_supabase.py`, `portal-v2/src/lib/variantLabels.ts`,
  `portal-v2/src/components/artifacts/VariantFilterBar.tsx`.
- `.github/workflows/weekly-excel-generation.yml:290` (`RES_GROUPING_MODE`) — inspect-only.

</code_context>

<specifics>
## Specific Ideas

- Exact Smartsheet titles (live-verified 2026-09-05 on `3239244454645636`): `Foreman Helping? #2`,
  `Foreman Helper #2 Active?`, `Helping Foreman #2 Completed Unit?`, `Helper #2 Dept #`,
  `Helper #2 Job [#]`, `Foreman Helper #2 Email`. Helper #1's job column is `Helper Job [#]`
  (mapped to canonical `Helper Job #`); mirror the bracket handling.
- Discovery anchors: Main ProMax `3239244454645636`; live ProMax report `6761112897802116`
  (reports are not generator sources — a column's visibility there proves nothing about the
  generator); Intake folder `8815193070299012` (11 sheets on 2026-09-05, Intake 8 included);
  excluded Intake 8 `2244739192541060`; Backup 2 `2230129632694148` (in `base_sheet_ids`, manual
  Helper #1 name, no Helper #2 columns → capability-unavailable case, not a task).
- Live evidence must stay distinguishable from fixtures in every summary: "fixture pass" ≠
  "dry-run pass" ≠ "controlled upload verified" ≠ "production observed".

</specifics>

<deferred>
## Deferred Ideas

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

</deferred>

---

*Phase: 14-foreman-helper-2*
*Context gathered: 2026-09-05*
