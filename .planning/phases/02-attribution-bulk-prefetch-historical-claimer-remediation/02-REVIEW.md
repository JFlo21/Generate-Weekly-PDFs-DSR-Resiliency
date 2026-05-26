---
phase: 02-attribution-bulk-prefetch-historical-claimer-remediation
reviewed: 2026-05-26T20:10:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - billing_audit/schema.sql
  - billing_audit/writer.py
  - generate_weekly_pdfs.py
  - tests/test_billing_audit_shadow.py
  - tests/test_claimer_remediation.py
  - tests/test_primary_claim_attribution.py
  - tests/test_subcontractor_helper_shadow_rescue.py
  - tests/test_subcontractor_primary_claim_attribution.py
  - tests/test_vac_crew_claim_attribution.py
  - .github/workflows/weekly-excel-generation.yml
  - website/docs/reference/environment.md
  - website/docs/runbook/operations.md
findings:
  blocker: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-05-26T20:10:00Z
**Depth:** standard
**Files Reviewed:** 12 (CLAUDE.md read for context only, not counted)
**Status:** issues_found

## Summary

Phase 2 replaces four per-row `lookup_attribution` RPC pre-passes (the
~137k-calls/run pattern that caused the timeout incident) with a single
bulk `prefetch_attribution` call + an O(1) map-aware `resolve_claimer`,
removes the `ATTRIBUTION_RESOLUTION_WEEKS` recency-scope gate that
suppressed historical frozen claimers, and adds a default-OFF,
dry-run-first, window-limited garbage-attachment remediation sweep
(`run_claimer_remediation`).

Overall the change is well-structured and the fail-safe philosophy is
mostly preserved: the new Supabase reader never raises, the remediation
mode is default-OFF with dry-run-first and a live-identity exemption, and
the CR-01 identity-tuple lockstep and mirror-matcher invariants are
untouched (no new variant key shapes were introduced). The
`ATTRIBUTION_RESOLUTION_WEEKS` removal is clean — all remaining references
are in comments/docstrings/planning artifacts, no dangling code reference.

The most serious finding is a **deployment-ordering hazard**: the
bulk-prefetch wiring is unconditionally active in `group_source_rows`
(no dedicated kill switch), and the new `lookup_attribution_bulk` RPC is a
hard runtime dependency. If this ships before the data team deploys that
RPC, every subcontractor (B) and vac-crew (C) row HOLDs on every run —
silently suppressing those billing files — because the D-04 contract
deliberately removed the per-row fallback. Several WARNING-level issues
cluster around the operator activation path for remediation being
documented as `workflow_dispatch` while the workflow hard-codes the flag
off with no input binding, plus a WR-sanitization key inconsistency
between the prefetch map key and the resolver lookup key.

## Blocker Issues

### CR-01: Bulk-prefetch is a hard runtime dependency with no per-row fallback — a missing/failed `lookup_attribution_bulk` RPC HOLDs all subcontractor + vac-crew billing files

**File:** `generate_weekly_pdfs.py:5598-5644`, `billing_audit/writer.py:838-931`
**Issue:**
The bulk-prefetch wiring in `group_source_rows` is gated only on
`BILLING_AUDIT_AVAILABLE` and the per-variant feature flags (all default-ON
in production). There is no separate kill switch for the bulk path and the
prior per-row pre-passes were fully deleted. By the explicit D-04 contract,
on `prefetch_attribution` returning `fetch_failure` the caller does NOT fall
back to the per-row `resolve_claimer` RPC path — B and C construct
`ResolveOutcome('hold', ...)` directly.

A missing `lookup_attribution_bulk` function (the new RPC that the data team
must deploy separately — see `billing_audit/schema.sql:279-322` and the
runbook Step 1) returns PostgREST `PGRST202` (function not found). That code
matches `_PGRST_PERMANENT_PREFIXES` (`PGRST2`) in
`billing_audit/client.py:86-90`, so `with_retry` bails after one attempt and
returns `None` (`client.py:683-684`), making `prefetch_attribution` return
`({}, "fetch_failure")` (`writer.py:902-903`). Result: B HOLDs every
completed subcontractor row, C HOLDs every completed vac-crew row → **no
`_ReducedSub*` / `_AEPBillable*` / `_VacCrew*` Excel files generated at all**
until the RPC is deployed. Note this is op-isolated (PGRST202 is not a
global-kill code), so it does NOT trip `_global_disable_reason` and does NOT
disable the `freeze_row` writes — but the read-side billing-file suppression
is still a production-breaking outcome.

Unlike the pre-Phase-2 state (where the already-deployed single
`lookup_attribution` RPC worked), Phase 2 introduces a brand-new RPC
dependency whose absence is indistinguishable, at the resolver, from a
genuine Supabase outage. The only documented recovery
(`BILLING_AUDIT_AVAILABLE=false`, per operations.md roll-back table) also
disables the `freeze_row` writes, corrupting the durable snapshot.

**Fix:**
Enforce the deployment ordering in code so a missing RPC degrades gracefully
instead of suppressing billing. Two acceptable approaches:

1. Add a dedicated default-ON kill switch for the bulk prefetch that, when a
   `fetch_failure` is observed at prefetch time, falls back to the
   already-deployed per-row `lookup_attribution` path for B/C/sub-helper
   (preserving generation), e.g.:

```python
# In group_source_rows, after _attr_map, _attr_status = _prefetch_attribution(...)
if _attr_status == 'fetch_failure' and ATTRIBUTION_BULK_PREFETCH_FALLBACK_TO_PER_ROW:
    # Pass prefetched_map=None to B/C/D consumers so resolve_claimer issues
    # the per-row lookup_attribution RPC (deployed) instead of HOLDing.
    _attr_map = None
```

2. Or make the bulk path conditional on the bulk RPC being verified present
   (a one-shot probe at startup), pinning the wiring behind a workflow flag
   that the operator flips only after the runbook Step 1 RPC deploy is
   confirmed — and keep the per-row pre-passes as the default until then.

At minimum, the merge MUST be gated on confirmation that
`lookup_attribution_bulk` is live in the target Supabase project; the current
code provides no automatic protection if that ordering is violated.

## Warnings

### WR-01: WR-sanitization key mismatch — prefetch map key is sanitized but `resolve_claimer` lookup key is not, violating the documented "all consumers consume the sanitized value" rule

**File:** `billing_audit/writer.py:886, 906-915`, `generate_weekly_pdfs.py:5623, 5673, 5773, 5786`, `billing_audit/writer.py:997-1002`
**Issue:**
The bulk path uses three WR representations that only coincide for numeric
WR#s:
- `prefetch_attribution` payload WR = `_WR_SANITIZE.sub("_", str(wr).split(".")[0])[:50]` (sanitized) — `writer.py:886`.
- `result_map` key WR = `str(row["wr"])` = the snapshot's stored `s.wr`, which `freeze_row` wrote sanitized (`writer.py:281, 536`) — so the map key is the **sanitized** WR.
- `resolve_claimer` lookup key WR = the caller's raw `wr` = `str(_wr_raw).split('.')[0]` (NOT run through `_WR_SANITIZE`) — `generate_weekly_pdfs.py:5673` etc., consumed at `writer.py:998`.

The prior per-row path sanitized the WR before the RPC
(`_lookup_attribution_all` at `writer.py:799-801`), so it matched the
snapshot. The new bulk path's map key is sanitized while the resolver lookup
key is not, so for any sanitization-sensitive WR# the `_key in prefetched_map`
test misses → `no_history` → use-current (silently dropping a valid frozen
claimer). CLAUDE.md rule [2026-04-23 18:25] explicitly requires every
downstream consumer of the identifier to consume the sanitized value.
Realistic numeric WR#s make `_WR_SANITIZE` a no-op, so production data is
unaffected today, but this is an untested latent split-brain (no test
exercises a divergent WR).

**Fix:**
Sanitize the lookup-key WR inside `resolve_claimer`'s prefetched-map branch
(or sanitize at the four call sites that build the pairs/keys) so the map key
and the lookup key are produced by the same `_WR_SANITIZE` expression:

```python
# writer.py resolve_claimer, prefetched_map branch:
_wr_key = _WR_SANITIZE.sub("_", str(wr).split(".")[0])[:50]
_key = (_wr_key, week_ending, row_id) if (week_ending and row_id) else None
```

Add a regression test with a WR# containing a sanitization-sensitive
character that asserts the frozen claimer still resolves.

### WR-02: Documented `workflow_dispatch` activation path for remediation does not exist — the workflow hard-codes `REMEDIATE_CLAIMERS: '0'` with no input binding

**File:** `.github/workflows/weekly-excel-generation.yml:443-451`, `website/docs/runbook/operations.md` (Step 4), `website/docs/reference/environment.md` (`REMEDIATE_CLAIMERS` operator workflow)
**Issue:**
The env block pins `REMEDIATE_CLAIMERS: '0'`, `REMEDIATION_DRY_RUN: '1'`,
`REMEDIATION_WINDOW_WEEKS: '26'` as **literals** (not
`${{ github.event.inputs.X || '0' }}`), and there is no `workflow_dispatch`
input for these keys, nor does the `advanced_options` parser
(`weekly-excel-generation.yml:210-214`) handle them. A literal value in a
step `env:` block takes precedence over anything pushed to `$GITHUB_ENV`.
Yet `environment.md` and `operations.md` Step 4 both instruct operators to
set `REMEDIATE_CLAIMERS: '1'` "via `workflow_dispatch`." Following the
documented procedure has no effect — the only way to actually activate
remediation through this workflow is to edit the YAML (or invoke locally).
For a destructive (attachment-deleting) operation, an unreachable documented
activation path is an operational hazard: an operator may believe they are
running a dry-run when nothing ran.

**Fix:**
Either (a) wire real `workflow_dispatch` inputs and bind the env values
(`REMEDIATE_CLAIMERS: ${{ github.event.inputs.remediate_claimers || '0' }}`,
similarly for dry-run and window), or (b) handle the three keys in the
`advanced_options` parser, or (c) correct both docs to state the only
activation path is editing the workflow YAML / local-shell invocation.
Approach (a) keeps the workflow pin as the default while making the
documented path real.

### WR-03: Misleading comment in the Subproject D bulk-read block describes a non-existent `action='disabled'` emission-site handling

**File:** `generate_weekly_pdfs.py:5745-5756`
**Issue:**
The comment states: "D never HOLDs: on fetch_failure, use-current at emission
(`resolve_claimer` returns `action='disabled'` from `prefetched_map` when map
is empty + fetch_failure status is handled at the emission site via the
else/no_history fallback path)." This is factually wrong. With
`prefetched_map={}` (empty on fetch_failure) and `enabled=True`,
`resolve_claimer` (`writer.py:997-1011`) takes the `_key in prefetched_map`
miss → `row, status = None, "no_row"` → returns
`ResolveOutcome("use", current_value, "current", "no_history")`. The action
is `'use'` with reason `'no_history'`, NOT `'disabled'`, and the
emission-site path it references does not special-case `disabled`. The
behavior happens to be correct (D uses-current), but the comment will mislead
the next maintainer reasoning about the outage path and could drive an
incorrect "fix" at the emission site.

**Fix:**
Correct the comment to describe the actual flow: "on fetch_failure the bulk
map is empty, so the prefetched-map miss yields a `('use', current,
'no_history')` outcome and D emits with the current foreman — D never HOLDs
by design."

### WR-04: Isolated remediation path (`valid_wr_weeks=None`) can delete a currently-valid `_Unknown_Foreman` billing file with no live-identity exemption

**File:** `generate_weekly_pdfs.py:4098-4128, 7806-7815`, `4203-4217`
**Issue:**
`run_claimer_remediation` is invoked from `main()` with
`valid_wr_weeks=None` (the isolated path). With `None`, the live-identity
exemption at lines 4210-4217 is skipped entirely, so deletion is gated only
on the name-pattern + window filter. The `_Unknown_Foreman` token is emitted
by the legitimate fallback chain whenever `effective_user` resolves to the
`'Unknown Foreman'` sentinel (e.g. a real row whose `Foreman Assigned?` is
blank — see `generate_weekly_pdfs.py:5187, 5973, 5977`). Such a file is a
CURRENT, correct billing artifact, not garbage. In EXECUTE mode the sweep
would delete it; because remediation runs in isolation and returns
immediately (no regeneration in the same session), the file stays deleted
until the next scheduled cron run — a data-absent window on a real WR. This
is the documented "WARNING 6 accepted tradeoff," but it is a genuine
data-loss surface that the dry-run-first + 26-week window only partially
mitigate.

**Fix:**
Prefer running remediation only AFTER Sub-project E activation (as the
runbook Step 4 sequencing intends) so legitimate `Unknown_Foreman` files are
re-generated under clean names, and/or tighten the garbage definition to
require the `_NO_MATCH` token (a pure Smartsheet error token that is never a
legitimate sentinel) while treating `_Unknown_Foreman` more conservatively
(e.g. only delete when a frozen claimer demonstrably exists for that
WR+week+row in the bulk-loaded attribution map). At minimum, document the
data-absent-window risk prominently in the operator workflow.

### WR-05: Subcontractor-helper outage path silently downgrades `fetch_failure` to `no_history` (loses the operator WARNING) under a non-global-kill bulk failure

**File:** `generate_weekly_pdfs.py:6294-6341`
**Issue:**
The rewired sub-helper block calls `resolve_claimer(..., prefetched_map=_attr_map)`.
On a bulk `fetch_failure` the map is empty, so the prefetched-map miss returns
`('use', helper_foreman, 'current', 'no_history')` — the block then sets
`_attribution_reason = None` (the `'use'` branch) or treats it as
`no_history`. The pre-Phase-2 code distinguished a true `fetch_failure` from
`no_history` by inspecting `_global_disable_reason`, which surfaced an
operator-actionable per-WR WARNING. Under a NON-global-kill bulk failure
(exactly the PGRST202 missing-RPC case in CR-01), the sub-helper rows now
silently use the current helper with NO fetch_failure signal, so an operator
tailing logs sees no indication that attribution was unavailable for the
sub-helper variant. This weakens the observability that earlier ledger
entries (Phase 1.1 Bug C) intentionally added.

**Fix:**
Thread the prefetch `_attr_status` into the sub-helper block so that when the
bulk load failed (`_attr_status == 'fetch_failure'`), the block sets
`_attribution_reason = 'fetch_failure'` and emits the per-WR WARNING — mirror
the `fetch_failure` distinction the block had before, driven by the
prefetch status rather than re-reading `_global_disable_reason`.

## Info

### IN-01: Dead imports in the bulk-prefetch block

**File:** `generate_weekly_pdfs.py:5628-5629`
**Issue:** `resolve_claimer as _resolve_claimer_bulk` and
`ResolveOutcome as _ResolveOutcome` are imported but never referenced — B/C/D
each re-import their own aliases (`_resolve_claimer_b/_c/_d`,
`_ResolveOutcome_b/_c`). Confirmed unused via grep.
**Fix:** Remove the two unused aliases from the import at 5626-5630; keep only
`prefetch_attribution as _prefetch_attribution`.

### IN-02: `out_of_window` counter conflates clean and garbage files

**File:** `generate_weekly_pdfs.py:4190-4200, 4242-4249`
**Issue:** The window filter `continue`s and increments `_total_out_of_window`
for ANY out-of-window file (garbage or clean), before the garbage-pattern
check. So the summary's `out_of_window=` count is "all files skipped due to
window," not "garbage skipped due to window," which is mildly misleading when
an operator reasons about blast radius from the summary line.
**Fix:** Either move the garbage check before the window filter, or rename the
metric / add a comment clarifying it counts all out-of-window attachments.

### IN-03: Runbook dry-run summary log line does not match actual output

**File:** `website/docs/runbook/operations.md` (Step 4), `generate_weekly_pdfs.py:4242-4249`
**Issue:** The runbook quotes the dry-run summary as
`"would delete N garbage attachments across TARGET/PPP, 0 executed"`, but the
actual code logs `"✅ run_claimer_remediation [DRY-RUN] complete: scanned=...
garbage=... deleted=... exempted=... out_of_window=..."`. An operator
grepping for the documented phrase will not find it.
**Fix:** Update the runbook to quote the actual summary-line format (or align
the log message to the documented phrasing).

### IN-04: Redundant local `import datetime as _dt` shadows the module-level `datetime` import inside `run_claimer_remediation`

**File:** `generate_weekly_pdfs.py:4130`
**Issue:** The module already imports `datetime`; the function adds a local
`import datetime as _dt` and uses `_dt.date.today()` / `_dt.timedelta` /
`_dt.datetime.strptime`. Functionally correct but inconsistent with the rest
of the module's `datetime.*` usage and adds cognitive overhead.
**Fix:** Drop the local alias and use the module-level `datetime` directly for
consistency.

---

_Reviewed: 2026-05-26T20:10:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
