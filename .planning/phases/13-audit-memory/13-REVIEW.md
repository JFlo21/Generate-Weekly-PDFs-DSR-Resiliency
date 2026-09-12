---
phase: 13-audit-memory
reviewed: 2026-09-12T03:19:17Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - .claude/project-state.md
  - .github/prompts/configuration-environment.md
  - audit_billing_changes.py
  - billing_audit/snapshot_store.py
  - docs/CHANGELOG_CONTEXT.md
  - docs/superpowers/specs/2026-08-24-supabase-run-memory-design.md
  - memory-bank/living-ledger.md
  - pipeline/config.py
  - pipeline/orchestrate.py
  - pipeline_memory/__init__.py
  - pipeline_memory/audit_findings.py
  - pipeline_memory/client.py
  - pipeline_memory/schema.sql
  - tests/golden/mypy_baseline.txt
  - tests/golden/mypy_baseline_count.txt
  - tests/test_audit_findings.py
  - tests/test_audit_findings_sql_contract.py
  - tests/test_snapshot_store.py
  - website/docs/reference/environment.md
  - website/docs/runbook/operations.md
findings:
  critical: 0
  warning: 3
  info: 1
  total: 4
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-09-12T03:19:17Z
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Reviewed the phase-13 diff (`git diff 80a79b9^..HEAD`) against `80a79b9^` for every listed
file, scoped strictly to what this phase actually changed (not the whole file history) per
the review instructions. The new surface is: `pipeline_memory/audit_findings.py` (new module,
672 lines), ~495 new lines in `pipeline_memory/schema.sql` (`audit_finding` /
`audit_finding_event` tables, `upsert_audit_findings` + `acknowledge_finding` RPCs,
`open_findings` / `finding_history_by_wr` views), a ~98-line wiring addition in
`pipeline/orchestrate.py` (`_run_audit_memory_phase` + its `main()` call site), a new
`AUDIT_MEMORY_ENABLED` flag in `pipeline/config.py` mirrored by `_audit_write_enabled()` in
`pipeline_memory/client.py`, an unrelated mypy narrowing fix in
`billing_audit/snapshot_store.py`, two new comprehensive test files
(`tests/test_audit_findings.py`, `tests/test_audit_findings_sql_contract.py`), a regression
lock in `tests/test_snapshot_store.py`, and documentation updates that were cross-checked
against the code (no contradictions found).

Overall the implementation is careful and well-tested: the fail-open contract, the
Python-authoritative-hash / SQL-never-recomputes-key contract, the RLS/REVOKE model for the
five pre-existing tables, the D-CD-01 pooled-week rule, and the D-10 per-check reaudited-pairs
scoping are all correctly implemented and match their extensive docstrings and the SQL
contract test (`tests/test_audit_findings_sql_contract.py`). I traced the `upsert_audit_findings`
plpgsql transition table (open→fixed→reopened, acknowledged→resurfaced, the CTE-snapshot
semantics that prevent the `to_fix` branch from ever double-processing a finding_key present
in `incoming`) and found it logically sound. I did not find a correctness bug, security
vulnerability, or data-loss risk in the diff. I did find three defense-in-depth /
observability / maintainability gaps worth fixing before this ships, detailed below.

## Warnings

### WR-01: `upsert_audit_findings` RPC is missing the explicit `GRANT EXECUTE ... TO service_role` its sibling RPC has

**File:** `pipeline_memory/schema.sql:812-950` (function body), compare `pipeline_memory/schema.sql:557-558`
**Issue:** `upsert_rows_bulk` (the pre-existing analog RPC) is immediately followed by:
```sql
GRANT EXECUTE ON FUNCTION pipeline_memory.upsert_rows_bulk(BIGINT, TEXT, JSONB)
    TO service_role;
```
`upsert_audit_findings` — the RPC `pipeline_memory/audit_findings.py::upsert_audit_findings()`
actually calls in production via the Supabase Python client (service_role key, over
PostgREST) — has no equivalent `GRANT`/`REVOKE` statement anywhere in the file. It currently
still works only because PostgreSQL auto-grants `EXECUTE` on every newly created function to
`PUBLIC` by default, and nothing in this file revokes that grant for this specific function
(the schema-wide `REVOKE ALL ON SCHEMA pipeline_memory FROM anon, authenticated` blocks those
two roles regardless, so there is no live anon/authenticated exposure today). But this is an
implicit, fragile dependency: the file's own header comment for `acknowledge_finding`
explicitly documents that "Postgres auto-grants EXECUTE on a new function to PUBLIC by
default... which would otherwise leave this... callable by anon/authenticated via PostgREST"
and reacts by adding a `REVOKE ALL ... FROM PUBLIC`. If a future edit "hardens"
`upsert_audit_findings` the same way (adds `REVOKE ALL ... FROM PUBLIC` to match
`acknowledge_finding`'s pattern) without also re-adding an explicit `GRANT ... TO
service_role`, the production write path breaks silently — this write is fail-open, so the
failure mode is `upsert_written`/`upsert_errored` counters going wrong and audit-memory
writes silently going to zero, not a crash a reviewer would catch quickly.
**Fix:**
```sql
GRANT EXECUTE ON FUNCTION pipeline_memory.upsert_audit_findings(TEXT, JSONB, JSONB)
    TO service_role;
```
Add this immediately after the function's closing `$$;` (schema.sql:950), mirroring
`upsert_rows_bulk`'s treatment exactly, so the grant is self-documenting and doesn't depend
on the PUBLIC default surviving future edits.

### WR-02: Skip-reason/outcome counters computed in `audit_findings.py` are never surfaced anywhere in production

**File:** `pipeline_memory/audit_findings.py:93-135`, `pipeline/orchestrate.py:2996-3037`
**Issue:** `pipeline_memory/audit_findings.py` maintains seven module-level counters
(`findings_skipped_no_match`, `findings_skipped_multi_week`,
`findings_skipped_unimplemented_check`, `findings_week_ambiguous`,
`findings_skipped_unresolved_row`, `findings_skipped_no_recipe`, `upsert_written`,
`upsert_errored`) via `_bump_counter`, exposed through `counters()`, whose own docstring says
it exists "for the run-summary log line" (`pipeline_memory/audit_findings.py:125`). Nothing in
`pipeline/orchestrate.py`'s `_run_audit_memory_phase` or its `main()` call site
(`pipeline/orchestrate.py:2996-3037`) ever calls `_mem_audit_findings.counters()` — the
Sentry breadcrumb only carries `findings_emitted` (a local count from `build_finding_payloads`)
plus the RPC's own opened/seen/fixed/resurfaced/reopened summary. This is an established,
otherwise-followed pattern in this exact codebase: `pipeline_memory/writer.py::get_counters()`
is merged into `_run_summary` at `pipeline/orchestrate.py:5523`. Every one of the seven
skip-reason counters this phase carefully engineered (e.g. to make the D-CD-01 multi-week
ambiguity rate and the D-02 recipe-coverage gap observable in shadow, per the module's own
docstrings) is invisible in production logs, Sentry, and `run_summary.json` — if
`findings_skipped_unresolved_row` or `findings_skipped_no_match` silently climbs due to an
unrelated data-shape drift in `audit_billing_changes.py`, there is currently no
operator-visible signal.
**Fix:** Add `_mem_audit_findings.counters()` to the breadcrumb payload in
`pipeline/orchestrate.py`'s audit-memory block, e.g.:
```python
sentry_add_breadcrumb(
    "audit_memory", "Audit-memory upsert completed",
    data={
        "findings_emitted": _audit_mem_result["findings_emitted"],
        **_audit_mem_summary,
        **_mem_audit_findings.counters(),
    },
)
```
(and/or fold into `_run_summary` alongside `_billing_audit_writer.get_counters()` if the
21-key `run_summary.json` contract has room, per the module's own reset-per-run assumption).

### WR-03: `IDENTITY_RECIPES` is documented as authoritative but its values are never read by any code path

**File:** `pipeline_memory/audit_findings.py:22-32, 59-68, 477`
**Issue:** The module docstring states the canonical hash input's identity segment is
"that check's identity values in the fixed `IDENTITY_RECIPES` order" (lines 26-27), and
`IDENTITY_RECIPES` is presented as the per-check "ordered list of logical identity fields
hashed after `check_id`" (lines 59-61). In reality, `IDENTITY_RECIPES`'s tuple *values* are
never read anywhere in the module — the only usages are `finding_type not in IDENTITY_RECIPES`
(a *membership* check, line 477) and `set(IDENTITY_RECIPES) == MEMORY_BACKED_CHECKS` (a *keys*
comparison, in `tests/test_audit_findings.py:429`). The actual identity-value order used to
build `finding_key` is hardcoded independently, three separate times, inside
`_build_rate_sanity_payload` (line 239: `(wr, week_ending, cu, work_type)`),
`_build_price_variance_payload` (line 313: `(wr, week_ending)`), and
`_build_data_consistency_payload` (line 399: `(wr, week_ending, ",".join(issue_codes))` — note
even the field name drifts here, "issues" in the dict vs. `issue_codes` in code). Nothing ties
these three hardcoded tuples back to `IDENTITY_RECIPES`'s declared tuple values, so a future
edit to `IDENTITY_RECIPES` (e.g. during a `FINDING_KEY_RECIPE_VERSION` bump, exactly the
scenario this module's docstrings repeatedly call out as the sensitive operation) could
silently diverge from the real hashing logic with zero test failure, while a maintainer
reading only the docstring would reasonably believe editing the dict changes behavior.
**Fix:** Either (a) make `IDENTITY_RECIPES` load-bearing — have each `_build_*_payload`
function pull its identity tuple by iterating `IDENTITY_RECIPES[check_id]` and reading the
named fields off a local values dict, so a dict edit actually changes behavior and the
existing recipe-coverage test provides real protection; or (b) if keeping the three hardcoded
tuples for clarity, add a table-driven test that asserts each `_build_*_payload` function's
identity tuple order matches `IDENTITY_RECIPES[check_id]` exactly, so the two can never drift
silently.

## Info

### IN-01: `findings_skipped_multi_week` counter name breaks the module's own naming convention

**File:** `pipeline_memory/audit_findings.py:99, 236-240`
**Issue:** Every other `findings_skipped_*` counter (`findings_skipped_no_match`,
`findings_skipped_unresolved_row`, `findings_skipped_no_recipe`,
`findings_skipped_unimplemented_check`) corresponds to a finding that is genuinely dropped
(the builder function returns `None`, no payload is emitted). `findings_skipped_multi_week`
is the one exception: `_build_rate_sanity_payload` bumps it (line 237) but then *continues* to
build and return a real payload with `week_ending=None` (lines 239-260) — the finding is not
skipped at all. This is inconsistent with the sibling counter for the identical situation on
`price_variance_anomaly`, `findings_week_ambiguous` (line 105), which is named accurately
("ambiguous", not "skipped") for the same non-dropping behavior. If/when WR-02 above is fixed
and these counters start appearing in operator-facing logs, `findings_skipped_multi_week`
will read as "N findings were dropped" when in fact zero were dropped.
**Fix:** Rename to `findings_multi_week_ambiguous` (or similar) to match the
`findings_week_ambiguous` naming pattern, updating the one call site (line 237) and the two
test assertions in `tests/test_audit_findings.py` (lines 227, 316/329 area) that reference
counter names by substring match (`"no_match" in k or "unmatched" in k` style) or by exact key.

---

_Reviewed: 2026-09-12T03:19:17Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
