# Phase 2: Attribution Bulk-Prefetch + Historical Claimer Remediation — Specification

**Created:** 2026-05-26
**Ambiguity score:** 0.18 (gate: ≤ 0.20)
**Requirements:** 6 locked

## Goal

Every generated Excel file is partitioned and named by the **real frozen
claimer** from `billing_audit.attribution_snapshot` — zero `_NO_MATCH` /
`_Unknown_Foreman` filenames for any row that has a frozen claimer — with no
time-budget regression, so Sub-project E (`SUPABASE_HASH_STORE_AUTHORITATIVE=1`,
clean filenames + durable hash store) can be safely re-activated.

## Background

Confirmed root cause this session (2026-05-26):

- The timeout hotfix (PR #231) added `ATTRIBUTION_RESOLUTION_WEEKS=8`, gating
  the four per-row `lookup_attribution` pre-pass sites in
  `generate_weekly_pdfs.py` (`_attribution_week_in_scope` at lines ~5492,
  5565, 5657, 6203). It was intended as a *skip* optimization, but the frozen
  claimer is part of the **group key and filename** — so the scope gates
  **key formation**, not just skipping.
- Sub-project E activation (`SUPABASE_HASH_STORE_AUTHORITATIVE=1`, commit
  `67539ec`) with a near-empty `group_content_hash` store returned `no_row`
  for historical groups → **forced regeneration**. Those historical weeks are
  out of the 8-week scope, so their claimer fell back to the current Smartsheet
  foreman — which is blank (`Unknown_Foreman`) or `#NO MATCH` (`_NO_MATCH`) for
  old completed work — and the garbage-named files were uploaded over the real
  historical attachments.
- Evidence: the first AUTHORITATIVE=1 run (`26439205107`) generated 1,116 clean
  files; **372 were `_User__NO_MATCH` (131) / `_User_Unknown_Foreman` (241)**,
  concentrated in old weeks. Recent (in-scope) weeks resolved **real names**
  (15/19). `attribution_snapshot.frozen_primary` is **~99% populated with real
  names across every month back to mid-2025** — the data exists; the pipeline
  just never read it for out-of-scope weeks.
- Consumption site confirmed at `generate_weekly_pdfs.py:5875-5890`: a row
  absent from `_primary_claimer_map` (out-of-scope) → `_d_claimer =
  effective_user or 'Unknown Foreman'` → embedded in `primary_key`.

Immediate mitigation already applied: `SUPABASE_HASH_STORE_AUTHORITATIVE`
reverted to `0` (commit `46cd05d`, pending push). This phase delivers the real
fix so E can be turned back on.

The freeze/write side (`freeze_row`, snapshot population) is correct and
complete — only the **read side** (resolution) is the problem.

## Source Continuity — Superpowers lineage

This phase is the formal GSD continuation of the claim-attribution effort that
was executed through `docs/superpowers/` (specs + plans), not GSD phases. It
picks up exactly where that work left off and closes the emergent interaction it
left open.

**Shipped design history (all merged, tracked in `docs/superpowers/`):**
- **Foundation A** — `resolve_claimer` + HOLD read layer
  (`specs/2026-05-20-claim-attribution-foundation-design.md`,
  `plans/2026-05-20-claim-attribution-foundation.md`).
- **Sub-project B** — subcontractor primary `_ReducedSub_User_` /
  `_AEPBillable_User_` partitioning (PR #215, hotfix #216).
- **Sub-project C** — vac_crew `_VacCrew_<name>` partitioning (PR #219).
- **Sub-project D** — production primary `_User_<claimer>` partitioning
  (PR #223, follow-up #225).
- **Sub-project E** — Supabase durable hash store + clean filenames (PR #229),
  shipped **dormant** by design.

**The open thread Phase 2 closes.** The E design
(`specs/2026-05-25-subproject-e-supabase-hash-store-design.md`) explicitly
classified the first-AUTHORITATIVE cutover as a "one-time regeneration wave —
**wasteful but safe**" (Risks §) and put **"Any attribution / `lookup_attribution`
change" OUT OF SCOPE** (Scope §). That safety held under E's own assumptions, but
the timeout hotfix (PR #231, **one day after** E was specced) added
`ATTRIBUTION_RESOLUTION_WEEKS=8` to **group-KEY formation**. The composition of
the two changes was never analyzed — E's "safe" regen wave, run against the
week-scope, regenerated historical groups with garbage claimer names. **Phase 2
is precisely the attribution change E deferred**, and it restores E's "regen is
safe" invariant. E's secondary mitigation ("dormant shadow-write shrinks the wave
to zero") also under-delivered: shadow writes recorded only recently *changed*
groups (~2,233 rows over ~12h), not the stable-skipped historical set, so the
cutover wave was ~1,119 files (not zero).

**Debug lineage (root-cause artifacts in `.planning/debug/`):**
- `sub-helper-shadow-missing.md` (`status: root_cause_found`) — the 2-cycle
  session that spawned **Phase 1.1** (Bug A pre-acceptance drop, Bug B variant
  duplication); both shipped-fixed.
- `helper-generation-workflow-analysis-2026-05-20.md` (`status:
  root_cause_found`) — zero-rate / missing-`Helper Dept #` helper-row drops; the
  zero-rate path was fixed by Phase 1.1's `_subcontractor_rescue_price`.
  **Still-open adjacent gate:** rows with helper criteria but a missing/unmapped
  `Helper Dept #` are hard-blocked from helper variants (126 rows in run
  26200546881). See Boundaries (out of scope) below.

**Open UAT carried forward:** `docs/superpowers/2026-05-21-subproject-b-helper-exclusion-UAT.md`
— Test 1 (helper-completed rows excluded from subcontractor primary files) passed
in production; Tests 2–4 (primary partitioned by frozen claimer; two claimers on
one WR+week coexist without cross-delete; helper-completed excluded from `_User_`
files) were *blocked* on the then-unmerged B branch. B/C/D are now merged and live,
so these are validatable — Phase 2's acceptance run (correct claimers across all
weeks) must satisfy them. They are folded into this phase's Acceptance Criteria.

**Uncommitted lineage docs to preserve:** four files are currently untracked —
`docs/superpowers/RESUME-2026-05-21-current.md`,
`docs/superpowers/2026-05-21-subproject-b-helper-exclusion-UAT.md`, and both
`.planning/debug/*.md`. Their substance is captured in this SPEC; they should be
committed alongside this phase so the lineage is tracked, not lost.

## Requirements

1. **Bulk attribution prefetch**: Replace the four per-row `lookup_attribution`
   RPC pre-pass sites with a single in-memory load.
   - Current: 4 pre-pass sites call `lookup_attribution` once per completed row,
     gated by `_attribution_week_in_scope`; unbounded = ~137k RPCs/run
     (timeout), bounded = correct only for the last 8 weeks.
   - Target: one bulk load of `attribution_snapshot` for the run's
     `(wr, week_ending)` set into an in-memory map keyed by
     `(wr, week_ending, smartsheet_row_id)`; `resolve_claimer` reads the map
     (O(1)); no per-row RPC; the week-scope no longer gates key formation.
   - Acceptance: a run resolves claimers for generated groups across recent AND
     historical weeks, and the attribution Supabase request count is
     O(distinct bulk queries), not O(completed rows) — verified by run-log HTTP
     count and unit tests on the map builder.

2. **Correct claimer on every generated file**: No garbage names for any row
   that has a frozen claimer.
   - Current: out-of-scope generated groups fall back to current foreman
     (`#NO MATCH`/blank) → `_User__NO_MATCH` / `_User_Unknown_Foreman` files.
   - Target: any generated group whose rows have a frozen role in
     `attribution_snapshot` is partitioned/named by that frozen claimer;
     use-current fallback applies ONLY when no frozen claimer exists (genuine
     `no_history`).
   - Acceptance: a full run produces **0** files named `*_NO_MATCH*` /
     `*_Unknown_Foreman*` for any WR+week+row that has a non-null /
     non-`#NO MATCH` frozen role in `attribution_snapshot`.

3. **No time-budget regression**: Runtime stays within budget.
   - Current: per-row RPC pre-pass; unbounded version blew the run budget
     (~137k calls).
   - Target: the bulk-load approach removes per-row network cost; total runtime
     stays within `TIME_BUDGET_MINUTES=165` / `timeout-minutes=180`.
   - Acceptance: a full production-equivalent run completes within the 165-min
     budget (no premature graceful-stop / "budget exceeded" before generation),
     and attribution HTTP request count is dramatically reduced vs the 137k
     baseline.

4. **Recent-window remediation of corrupted files**: Fix already-uploaded
   garbage for the active billing window.
   - Current: the cutover uploaded `_NO_MATCH` / `_Unknown_Foreman` files over
     real historical attachments.
   - Target: for the most recent **~6 months (≈26 weeks)** of week-endings,
     regenerate affected groups with correct frozen-claimer names AND remove the
     orphaned garbage-named attachments (TARGET + PPP as applicable). Deeper
     history left as-is unless naturally edited.
   - Acceptance: after remediation, for every WR+week in the remediation window,
     the Smartsheet attachment set contains the correct frozen-claimer file(s)
     and contains **no** `_NO_MATCH` / `_Unknown_Foreman` file for rows that
     have a frozen claimer.

5. **Safe Sub-project E re-activation**: Clean filenames + durable hash store
   go live without the regression.
   - Current: `SUPABASE_HASH_STORE_AUTHORITATIVE=0` (mitigation); token
     filenames + JSON change-detection.
   - Target: after the fix is validated by a clean run, restore
     `SUPABASE_HASH_STORE_AUTHORITATIVE=1` so clean filenames + the durable
     `group_content_hash` store go live; the `no_row → regenerate` path now
     resolves the real frozen claimer.
   - Acceptance: with AUTHORITATIVE=1 and the fix in place, a run generates
     clean filenames (no `_<timestamp>_<hash>` tokens) with correct
     frozen-claimer partitions and zero garbage names.

6. **Regression coverage**: TDD tests lock the behavior.
   - Current: existing suite (961 passing) covers per-row resolution + the
     8-week scope; no test asserts historical groups resolve real claimers under
     a bulk load.
   - Target: tests assert (a) the bulk prefetch builds the
     `(wr, week, row_id) → frozen-roles` map correctly, (b) a generated
     historical (out-of-old-8-week-scope) group resolves the real frozen claimer
     rather than use-current, (c) genuine no-frozen-data rows still fall back to
     use-current, (d) a Supabase-failure path degrades to the documented
     fallback (never crash / silent wrong value).
   - Acceptance: `pytest tests/` is green; a regression test reproduces the
     original bug (historical group → `_NO_MATCH`) RED before the fix and GREEN
     after.

## Boundaries

**In scope:**
- Bulk in-memory `attribution_snapshot` loader, replacing the 4 per-row
  `lookup_attribution` RPC pre-pass sites in `generate_weekly_pdfs.py`.
- Removing the `ATTRIBUTION_RESOLUTION_WEEKS` week-scope from group-KEY
  formation so every generated group resolves its real claimer (exact env-var
  disposition — drop vs keep as non-binding safety net — decided in
  discuss/plan).
- Recent-window (~6 months / ≈26 weeks) remediation: regenerate correct files +
  delete garbage attachments.
- Re-activation of Sub-project E (`SUPABASE_HASH_STORE_AUTHORITATIVE=1`) after
  the fix is validated by a clean run.
- Regression tests, Living Ledger entry, and `environment.md` / workflow doc
  updates.

**Out of scope:**
- Deep-history (>~6 months) remediation of already-corrupted attachments —
  cost/churn not justified; the code fix makes them self-heal on next natural
  edit.
- Any change to the FREEZE/write side (`freeze_row`, snapshot population) — it
  is already correct (~99% populated); only the read side changes.
- Railway → Render migration / Artifact Explorer redesign — separate v1.1.
- Re-architecting change-detection beyond what Sub-project E already shipped.
- Fixing the upstream Smartsheet `#NO MATCH` foreman-formula data quality — the
  frozen snapshot is the source of truth; that is a Smartsheet data concern.
- Relaxing the missing-`Helper Dept #` hard gate that blocks helper-variant
  emission (126 rows in run 26200546881, per
  `helper-generation-workflow-analysis-2026-05-20.md`) — a separate
  Smartsheet-data / gate decision; flagged in Source Continuity so it isn't lost.

## Constraints

- Total runtime must stay within `TIME_BUDGET_MINUTES=165` / `timeout-minutes=180`
  (15-min post-job margin preserved); no per-row network regression.
- Fail-safe: a Supabase failure during the bulk load degrades to the documented
  fallback (use-current / regenerate), never a crash or a silent wrong value.
- Bulk fetch must be bounded — load the run's `(wr, week_ending)` set (or a
  bounded recent superset), not unbounded; `attribution_snapshot` is ~142k rows.
- No Smartsheet `@cell`; `PARALLEL_WORKERS ≤ 8`; no row PII in logs / Sentry
  (existing sanitizers preserved).
- Additive / surgical changes to `generate_weekly_pdfs.py`; preserve all CR-01
  four-site identity lockstep + mirror-matcher invariants from the Living
  Ledger.
- The `billing_audit` reader stays fail-safe (per-op circuit breaker, distinct
  op id), consistent with existing `lookup_attribution` / `lookup_group_hash`
  patterns.

## Acceptance Criteria

- [ ] A full run resolves frozen claimers for generated groups across ALL weeks
  (recent + historical), not just the last 8.
- [ ] 0 generated files named `*_NO_MATCH*` / `*_Unknown_Foreman*` for rows that
  have a frozen claimer in `attribution_snapshot`.
- [ ] Attribution resolution issues O(distinct bulk queries) Supabase requests,
  not O(completed rows) — no ~137k-call pattern (verified via run-log HTTP
  count).
- [ ] A full run completes within `TIME_BUDGET_MINUTES=165` (no premature
  graceful-stop).
- [ ] Recent-window (~26 weeks) corrupted attachments remediated: correct
  frozen-claimer files present, garbage files removed, for every WR+week in the
  window.
- [ ] `SUPABASE_HASH_STORE_AUTHORITATIVE=1` restored and a run produces clean
  filenames + correct claimers + zero garbage names.
- [ ] (Carried UAT B-3) Two claimers on the same WR+week produce two coexisting
  files (neither cross-deletes the other), across recent AND remediated-historical
  weeks.
- [ ] (Carried UAT B-1/B-4) Helper-completed rows appear only in `_*_Helper_<name>`
  shadow files, never in `_*_User_<name>` / primary files — preserved by the fix.
- [ ] `pytest tests/` green; a regression test is RED before the fix and GREEN
  after.
- [ ] Living Ledger entry + `environment.md` / workflow docs updated.

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes                                              |
|--------------------|-------|------|--------|----------------------------------------------------|
| Goal Clarity       | 0.88  | 0.75 | ✓      | Real claimer everywhere; E re-activated; no timeout |
| Boundary Clarity   | 0.78  | 0.70 | ✓      | Recent-window remediation; deep history out         |
| Constraint Clarity | 0.78  | 0.65 | ✓      | ≤165min; fail-safe; bounded bulk fetch              |
| Acceptance Criteria| 0.80  | 0.70 | ✓      | 8 pass/fail criteria                                |
| **Ambiguity**      | 0.18  | ≤0.20| ✓      |                                                     |

Status: ✓ = met minimum, ⚠ = below minimum (planner treats as assumption)

## Interview Log

| Round | Perspective     | Question summary                                  | Decision locked                                                       |
|-------|-----------------|---------------------------------------------------|-----------------------------------------------------------------------|
| 1     | Researcher      | Root cause of garbage claimer names?              | 8-week scope gates KEY formation; `attribution_snapshot` ~99% populated → real names exist but unread for old weeks |
| 2     | Boundary Keeper | How much corrupted-file remediation in scope?     | Code fix + recent-window (~6mo / ≈26wk) remediation; deep history out |
| 2     | Boundary Keeper | Is E re-activation a deliverable of this phase?    | Yes — re-activate `AUTHORITATIVE=1` after fix validated               |
| 3     | Failure Analyst | Primary pass/fail bar for "done"?                 | Zero garbage names for rows w/ frozen claimer + ≤165min + pytest green |

---

*Phase: 02-attribution-bulk-prefetch-historical-claimer-remediation*
*Spec created: 2026-05-26*
*Next step: /gsd-discuss-phase 2 — implementation decisions (bulk-loader design, env-var disposition, remediation mechanism, E re-activation sequencing)*
