# Phase 2: Attribution Bulk-Prefetch + Historical Claimer Remediation - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the four per-row `lookup_attribution` RPC pre-pass sites in
`generate_weekly_pdfs.py` with a single bulk in-memory load of
`billing_audit.attribution_snapshot`, so the `ATTRIBUTION_RESOLUTION_WEEKS=8`
scope no longer gates group-KEY formation. Every generated group (recent AND
historical) is then partitioned/named by its real frozen claimer — zero
`_NO_MATCH` / `_Unknown_Foreman` filenames for any row that has a frozen
claimer — with no time-budget regression. Then remediate the most recent
~26-week window of already-corrupted attachments and safely re-activate
Sub-project E (`SUPABASE_HASH_STORE_AUTHORITATIVE=1`).

Read-side only. The freeze/write side (`freeze_row`, snapshot population) is
correct and ~99% populated — it is NOT touched.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**6 requirements are locked.** See `02-SPEC.md` for full requirements,
boundaries, and acceptance criteria.

Downstream agents MUST read `02-SPEC.md` before planning or implementing.
Requirements are not duplicated here.

**In scope (from SPEC.md):**
- Bulk in-memory `attribution_snapshot` loader, replacing the 4 per-row
  `lookup_attribution` RPC pre-pass sites in `generate_weekly_pdfs.py`.
- Removing the `ATTRIBUTION_RESOLUTION_WEEKS` week-scope from group-KEY
  formation so every generated group resolves its real claimer (exact env-var
  disposition decided here — see D-04).
- Recent-window (~6 months / ≈26 weeks) remediation: regenerate correct files +
  delete garbage attachments.
- Re-activation of Sub-project E (`SUPABASE_HASH_STORE_AUTHORITATIVE=1`) after
  the fix is validated by a clean run.
- Regression tests, Living Ledger entry, and `environment.md` / workflow doc
  updates.

**Out of scope (from SPEC.md):**
- Deep-history (>~6 months) remediation of already-corrupted attachments — the
  code fix makes them self-heal on next natural edit.
- Any change to the FREEZE/write side (`freeze_row`, snapshot population) — it
  is already correct (~99% populated); only the read side changes.
- Railway → Render migration / Artifact Explorer redesign — separate v1.1.
- Re-architecting change-detection beyond what Sub-project E already shipped.
- Fixing the upstream Smartsheet `#NO MATCH` foreman-formula data quality — the
  frozen snapshot is the source of truth.
- Relaxing the missing-`Helper Dept #` hard gate that blocks helper-variant
  emission (126 rows in run 26200546881) — a separate Smartsheet-data / gate
  decision; flagged so it isn't lost.

</spec_lock>

<decisions>
## Implementation Decisions

### Bulk-loader design (Requirement 1)
- **D-01:** **New bulk RPC.** Add `lookup_attribution_bulk(p_wr_weeks jsonb)`
  to `billing_audit/schema.sql` AND a matching reader in
  `billing_audit/writer.py`. It accepts the run's `(wr, week_ending)` set and
  returns all matching `attribution_snapshot` rows in one round-trip, applying
  the SAME server-side `#NO MATCH` / blank → NULL per-role normalization the
  existing `lookup_attribution` RPC already does (do NOT replicate that CASE
  logic in Python — keep one source of truth). Rejected: direct table SELECT
  (would require exposing the table for SELECT + a second copy of the
  normalization logic). DDL co-ships with the Python code in the same PR per
  the `[2026-04-25 12:00]` schema-co-ship rule. **Operator coordination
  required at merge time:** the data team must deploy the new RPC to the live
  Supabase project and reload the PostgREST schema cache before the fix is live
  (mirrors the existing `lookup_attribution` RPC deployment).
- **D-02:** **Load the exact run `(wr, week_ending)` set.** The bulk query is
  bounded to exactly the `(wr, week_ending)` pairs this run discovered/grouped
  — not a recency superset. This structurally cannot miss a generated group
  (it loads precisely what gets generated) and keeps the request count
  O(distinct bulk queries), not O(completed rows). Rejected: a
  `week_ending >= cutoff` superset, because it reintroduces a recency window —
  a generated group older than the cutoff would miss its claimer (the exact
  bug class being fixed). Honor the SPEC constraint that the fetch stays
  bounded (`attribution_snapshot` is ~142k rows; chunk the `(wr, week)` set if
  one RPC payload would be too large — planner decision).
- **D-03:** **Map-aware resolver, keep the Foundation A contract.** Add a
  `prefetch_attribution(pairs)` builder that returns an in-memory map keyed by
  `(wr, week_ending, smartsheet_row_id)` → frozen-roles row. `resolve_claimer`
  reads a preloaded map (optional `prefetched_map` parameter or a thin sibling
  resolver — minimum-diff, planner picks) instead of issuing a per-row RPC. The
  use / `no_history` / `disabled` / `fetch_failure`(HOLD) decision table and
  `ROLE_BY_VARIANT` mapping are preserved EXACTLY (`billing_audit/writer.py`
  §`resolve_claimer` L869, `ROLE_BY_VARIANT` L858). The 4 pre-pass sites build
  the map once and resolve O(1) from it.
- **D-04:** **Bulk-load total-failure semantics = preserve existing per-variant
  policy.** If the entire bulk RPC fails (transient outage / retries exhausted),
  the affected keys are treated as `fetch_failure` and `resolve_claimer` applies
  each variant's EXISTING policy unchanged — Sub-project D (production primary,
  every WR) falls back to use-current (`_primary_claimer_map` miss → current
  foreman, never HOLD); Sub-projects B (subcontractor primary) and C (vac_crew)
  HOLD. Do NOT invent new "HOLD the whole run" semantics — that would suppress
  an entire run's billing output on a Supabase blip, the failure mode the
  Sub-project D no-HOLD decision already rejected. Satisfies SPEC Requirement 6(d)
  / the Constraints fail-safe clause (degrade to documented fallback, never crash
  or silent wrong value).

### Week-scope env-var disposition (Requirement 1 / Boundaries)
- **D-05:** **Drop `ATTRIBUTION_RESOLUTION_WEEKS` entirely.** The exact-set bulk
  load (D-02) makes recency-gating obsolete, and removing it eliminates the
  precise footgun that caused this incident. Remove: the env-var read
  (`generate_weekly_pdfs.py` L638-647), all four `_attribution_week_in_scope`
  gates (the sub-primary ~L5492, vac_crew ~L5565, primary ~L5657, and the
  Phase 1.1 sub-helper direct-lookup gate ~L6203), the
  `_attribution_resolution_cutoff` (L5335) and `_attribution_week_in_scope`
  (L5354) helpers, the startup-banner line (L839-840), the workflow `env:` pin
  in `.github/workflows/weekly-excel-generation.yml`, the
  `environment.md` entry, and `tests/test_attribution_resolution_scope.py`
  (delete or repurpose — planner picks; a regression test that a historical
  group resolves its real claimer is the replacement per Requirement 6(b)).
  Rejected: keeping it as a decoupled default-OFF payload knob — a vestigial
  recency var on this exact code path is a re-incident risk not worth the knob.

### Remediation mechanism (Requirement 4)
- **D-06:** **Dedicated env-gated one-shot remediation mode.** A default-OFF
  flag (e.g. `REMEDIATE_CLAIMERS=1`; final name = planner) drives a remediation
  pass that is ISOLATED from the normal cron generation path, with its own
  logging, counters, and a dry-run. Rationale: this is a destructive operation
  against production Smartsheet attachments — it must be observable and
  reversible, not folded silently into the generic cleanup. Rejected: reusing
  `REGEN_WEEKS` + the generic `cleanup_untracked_sheet_attachments` to delete
  orphans (broader blast radius, relies on `KEEP_HISTORICAL_WEEKS` reaching the
  window, less targeted).
- **D-07:** **Name-pattern garbage sweep.** Within the remediation window,
  delete ONLY attachments whose filename matches `*_NO_MATCH*` /
  `*_Unknown_Foreman*` (across TARGET_SHEET_ID and SUBCONTRACTOR_PPP_SHEET_ID as
  applicable). This is the narrowest possible blast radius — it structurally
  cannot delete a real-claimer file. The garbage files have a DIFFERENT identity
  than the correct-claimer files (claimer `_NO_MATCH` vs the real name), so
  same-identity replacement (`delete_old_excel_attachments`) will never remove
  them; an explicit pattern sweep is required. Must still respect the
  live-identity exemption (`[2026-05-19 23:45]` rule) so a correct file is never
  collateral-deleted.
- **D-08:** **Dry-run-first + env-configurable window.** The remediation window
  is env-configurable (default ~26 weeks / ~6 months). First invocation is
  report-only: it logs what WOULD be regenerated and which garbage attachments
  WOULD be deleted (with counts), the operator reviews, then re-runs to execute.
  The flag stays default-OFF so remediation NEVER fires on the scheduled cron.

### Sub-project E re-activation sequencing (Requirements 4 + 5)
- **D-09:** **Order: fix → validate → flip `AUTHORITATIVE=1` → remediate.** Land
  the fix with `SUPABASE_HASH_STORE_AUTHORITATIVE=0`; validate a clean run; flip
  to `1` (its `no_row → regenerate` wave now produces CORRECT clean-named files
  because the fix resolves real claimers — E's "regen is safe" invariant
  restored); THEN run remediation to sweep the old garbage attachments and cover
  any gaps. Remediating AFTER E activation means the regenerated files are
  clean-named (matching E's steady state) — no token→clean double-churn.
- **D-10:** **Validation gate = an acceptance-criteria run.** Before flipping
  `AUTHORITATIVE=1`, a real / production-equivalent run must demonstrate: zero
  `*_NO_MATCH*` / `*_Unknown_Foreman*` filenames for rows that have a frozen
  claimer; attribution HTTP request count O(distinct bulk queries) (not the
  ~137k baseline) verified via run-log; runtime within `TIME_BUDGET_MINUTES=165`;
  and `pytest tests/` green (incl. the new RED-before / GREEN-after regression
  test). Evidence-based per the verification-before-completion discipline — not
  a spot-check.
- **D-11:** **The `AUTHORITATIVE=1` flip is a gated operator follow-up.** This
  phase ships the fix + remediation mode + a documented re-activation
  runbook/checklist. The one-line
  `SUPABASE_HASH_STORE_AUTHORITATIVE: '1'` workflow change is a SEPARATE,
  explicit operator action taken AFTER a green validation run (D-10) — it is NOT
  auto-committed in the main fix PR. This preserves the human gate between
  validation and going-live, directly avoiding a repeat of the premature-flip
  incident (`67539ec` → corruption → revert `46cd05d`/PR #234).

### Carried-forward project conventions (apply throughout, locked by prior phases)
- **D-12:** Any NEW behavior-changing env flag added here (remediation flag,
  etc.) ships default-ON for fixes-as-default or default-OFF for the destructive
  remediation, and is PINNED in the workflow `env:` block per the IN-04 rule and
  surfaced in the startup banner.
- **D-13:** The `billing_audit` bulk reader stays fail-safe: reuse `with_retry`
  + the per-op circuit breaker + `_classify_postgrest_error`, with a DISTINCT op
  id (e.g. `lookup_attribution_bulk`) so a bulk-read outage cannot cascade into
  disabling `freeze_attribution` / `pipeline_run_*` / `lookup_attribution` /
  `lookup_group_hash` (op-isolation invariant, `[2026-04-25 14:00]`).
- **D-14:** Preserve ALL CR-01 four-site identity lockstep + mirror-matcher
  invariants. This phase does NOT change variant grouping, filename grammar, or
  the identity tuple — it only changes WHERE the claimer value comes from
  (bulk map vs per-row RPC). The resolved claimer must flow into the exact same
  identity surfaces unchanged.

### Claude's Discretion
- Exact bulk-RPC payload chunking strategy if the run's `(wr, week)` set exceeds
  a safe single-payload size (D-02) — planner picks based on set size.
- Resolver wiring shape — `prefetched_map` param on `resolve_claimer` vs a thin
  sibling resolver (D-03) — minimum-diff, planner picks.
- Disposition of `tests/test_attribution_resolution_scope.py` — delete vs
  repurpose into a historical-group-resolves-real-claimer regression (D-05).
- Where in the run flow the prefetch map is built (once, before the 4 pre-pass
  blocks / before `group_source_rows`) — minimum-diff, planner picks.
- Final names for the remediation flag + window env var (D-06/D-08).
- Living Ledger entry timestamp — executor sets at commit time.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked requirements (read first)
- `.planning/phases/02-attribution-bulk-prefetch-historical-claimer-remediation/02-SPEC.md`
  — 6 locked requirements, boundaries, acceptance criteria. MUST read before planning.

### Superpowers lineage — the read-side contract this phase extends
- `docs/superpowers/specs/2026-05-20-claim-attribution-foundation-design.md` §5
  — Foundation A: the `resolve_claimer` use/HOLD decision table this phase preserves (D-03).
- `docs/superpowers/plans/2026-05-20-claim-attribution-foundation.md`
  — Foundation A implementation plan.
- `docs/superpowers/specs/2026-05-25-subproject-e-supabase-hash-store-design.md`
  — Sub-project E (Scope §, Risks §): the "regen wave is wasteful-but-safe" assumption this phase restores; the AUTHORITATIVE flag + clean-filename design.
- `docs/superpowers/2026-05-21-subproject-b-helper-exclusion-UAT.md`
  — carried UAT B-1..B-4 (two same-week claimers coexist; helper-completed rows excluded from `_User_` files); Phase 2's acceptance run must satisfy these.
- `docs/superpowers/RESUME-2026-05-21-current.md`
  — session resume context (currently untracked — commit alongside this phase).

### Root-cause / debug artifacts
- `.planning/debug/sub-helper-shadow-missing.md` — 2-cycle session that spawned Phase 1.1.
- `.planning/debug/helper-generation-workflow-analysis-2026-05-20.md`
  — zero-rate / missing-`Helper Dept #` drops; flags the still-open helper-dept gate (out of scope here).
  (Both `.planning/debug/*.md` are currently untracked — commit alongside this phase.)

### Code integration map — `billing_audit/`
- `billing_audit/writer.py` — `_lookup_attribution_all` (L754), `resolve_claimer` (L869),
  `ResolveOutcome` (L840), `ROLE_BY_VARIANT` (L858), `lookup_attribution` (L914). The bulk
  reader + map-aware resolver land here.
- `billing_audit/client.py` — `with_retry`, per-op circuit breaker,
  `_classify_postgrest_error`, run-global kill switch (`get_client()` returns None). The
  bulk reader reuses these with a distinct op id (D-13).
- `billing_audit/schema.sql` — canonical DDL; the new `lookup_attribution_bulk` RPC is
  added here and co-ships in the same PR (D-01).

### Code integration map — `generate_weekly_pdfs.py`
- 4 per-row pre-pass sites to replace with the bulk map: `_sub_primary_claimer_map` (~L5471),
  `_vac_crew_claimer_map` (~L5547), `_primary_claimer_map` (~L5622), and the Phase 1.1
  sub-helper direct `lookup_attribution` (~L6203). Consumption sites: vac ~L5796,
  primary ~L5875, sub-primary ~L6052.
- `ATTRIBUTION_RESOLUTION_WEEKS` env read (L638-647), `_attribution_resolution_cutoff`
  (L5335), `_attribution_week_in_scope` (L5354), startup banner (L839-840) — all removed (D-05).

### Project rules / intel (read before planning)
- `CLAUDE.md` — Living Ledger; especially `[2026-05-26 01:45]` (this incident's prior
  hotfix), `[2026-04-25 12:00]` (schema-co-ship rule, D-01), `[2026-04-25 14:00]`
  (op-isolation + per-row→bulk parallelization lesson, D-13), `[2026-05-19 23:45]`
  (live-identity exemption, D-07), and the CR-01 four-site lockstep entries (D-14).
- `.planning/intel/decisions.md` — every locked ADR-equivalent rule.
- `.planning/intel/constraints.md` — time budget, billing_audit schema, change-detection key.
- `.github/instructions/python.instructions.md` — PEP 8, type hints, docstrings.
- `.github/instructions/performance-optimization.instructions.md` — `PARALLEL_WORKERS ≤ 8`, time-budget proportions.
- `.github/instructions/github-actions-ci-cd-best-practices.instructions.md` — workflow `env:` pinning (IN-04).
- `.claude/rules/smartsheet-python-optimization.md` — Smartsheet API contract; `openpyxl` engine policy.
- `.claude/rules/documentation-maintenance.md` — runbook changelog policy.

### Files updated by this phase
- `.github/workflows/weekly-excel-generation.yml` — remove `ATTRIBUTION_RESOLUTION_WEEKS`
  pin, add remediation-flag pin (default-OFF), the `AUTHORITATIVE=1` flip is operator-applied later (D-11).
- `website/docs/reference/environment.md` — remove `ATTRIBUTION_RESOLUTION_WEEKS`, document the remediation flag + window var.
- `tests/test_attribution_resolution_scope.py` (remove/repurpose), `tests/test_billing_audit_shadow.py`
  (bulk reader tests), `tests/test_primary_claim_attribution.py`,
  `tests/test_subcontractor_primary_claim_attribution.py`, `tests/test_vac_crew_claim_attribution.py`
  (map-aware resolution + historical-group regression).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `resolve_claimer` / `ResolveOutcome` / `ROLE_BY_VARIANT` (`billing_audit/writer.py`):
  the entire use/HOLD decision table is reused verbatim; only its data source changes
  from a per-row RPC to a preloaded map (D-03).
- `with_retry` + per-op circuit breaker + `_classify_postgrest_error`
  (`billing_audit/client.py`): the bulk reader reuses this fail-safe machinery with a
  distinct op id (D-13) — no new retry/breaker logic.
- The existing `lookup_attribution` RPC's `#NO MATCH`/blank → NULL CASE normalization
  in `billing_audit/schema.sql`: the bulk RPC reuses the SAME normalization so there's
  one source of truth (D-01).
- The run's `(wr, week_ending)` set is already assembled during discovery/grouping —
  feed it to `prefetch_attribution` once before the pre-pass blocks (D-02).

### Established Patterns
- Default-ON kill switch for behavior changes / default-OFF for destructive ops, pinned
  in the workflow `env:` block + surfaced in the startup banner (IN-04 / D-12).
- Bounded-parallel I/O with `ThreadPoolExecutor(max_workers=min(PARALLEL_WORKERS, n))`
  — relevant only if the bulk query is chunked; the goal is to ELIMINATE per-row network
  cost, not parallelize it (`[2026-04-25 14:00]`).
- CR-01 four-site identity lockstep + mirror-matcher invariants (D-14): unchanged here.
- Name-pattern + live-identity-exempt attachment deletion (`cleanup_untracked_sheet_attachments`
  precedent, `[2026-05-19 23:45]`) informs the remediation sweep (D-07).

### Integration Points
- New `lookup_attribution_bulk` RPC in Supabase `billing_audit` schema (operator deploy + PostgREST cache reload, D-01).
- The 4 pre-pass blocks in `generate_weekly_pdfs.py` collapse to a single prefetch +
  O(1) map reads; consumption sites (L5796/5875/6052) read the same `ResolveOutcome`.
- The remediation mode is a new top-level branch in `generate_weekly_pdfs.py` (or a sibling
  entry point — planner picks) gated by the default-OFF flag, touching TARGET + PPP attachments.
- E re-activation is a workflow `env:` one-liner applied by the operator post-validation (D-11).

</code_context>

<specifics>
## Specific Ideas

- Evidence anchors from the incident (for the regression test + acceptance run):
  first AUTHORITATIVE=1 run `26439205107` produced 1,116 clean files of which
  **372 were garbage** (131 `_User__NO_MATCH`, 241 `_User_Unknown_Foreman`),
  concentrated in old weeks; recent weeks resolved real names (15/19).
  `attribution_snapshot.frozen_primary` is ~99% populated with real names back to
  mid-2025 — the data exists; the pipeline never read it for out-of-scope weeks.
- The ~137k `POST /rpc/lookup_attribution` calls (+8,044 `RemoteProtocolError`
  retries) in the canceled run are the baseline the bulk load must collapse to
  O(distinct bulk queries).
- Garbage files are CLEAN-named (no `_<timestamp>_<hash>` tokens) because they were
  uploaded during AUTHORITATIVE=1 — the name-pattern sweep (D-07) keys on the
  `_NO_MATCH` / `_Unknown_Foreman` substring, not on token shape, so it works
  whether or not E is currently active.

</specifics>

<deferred>
## Deferred Ideas

- **Missing-`Helper Dept #` hard gate relaxation** — rows with helper criteria but a
  missing/unmapped `Helper Dept #` are hard-blocked from helper-variant emission
  (126 rows in run 26200546881, per
  `.planning/debug/helper-generation-workflow-analysis-2026-05-20.md`). A separate
  Smartsheet-data / gate decision; explicitly OUT OF SCOPE here but preserved so it
  isn't lost.
- **Deep-history (>~6 months) remediation** — left as-is; the code fix makes those
  attachments self-heal on next natural edit. Out of scope per SPEC.
- **Railway → Render migration + Artifact Explorer redesign** — separate v1.1 milestone.

</deferred>

---

*Phase: 02-attribution-bulk-prefetch-historical-claimer-remediation*
*Context gathered: 2026-05-26*
