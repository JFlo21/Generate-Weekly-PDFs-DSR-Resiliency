---
phase: 12-ownership-last-known-foreman-as-of-the-week
reviewed: 2026-09-03T00:00:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - .github/workflows/cell-history-backfill.yml
  - .gitignore
  - billing_audit/own03_backfill_attribution.sql
  - billing_audit/schema.sql
  - billing_audit/writer.py
  - pipeline/cleanup.py
  - pipeline/orchestrate.py
  - scripts/backfill_cell_history_attribution.py
  - scripts/backfill_claim_time_attribution.py
  - tests/test_backfill_cell_history_attribution.py
  - tests/test_backfill_claim_time_attribution.py
  - tests/test_lazy_smartsheet_imports.py
  - tests/test_own03_backfill_sql_contract.py
  - tests/test_own04_documentation.py
  - tests/test_sentinel_superseded_cleanup.py
  - website/docs/reference/environment.md
  - website/docs/runbook/ownership-attribution.md
  - website/docs/runbook/scripts.md
  - website/docs/runbook/workflows.md
  - website/sidebars.ts
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-09-03T00:00:00Z
**Depth:** standard
**Files Reviewed:** 20
**Status:** issues_found

## Summary

This diff is the OWN-03 "cell history" backfill slice (Phase 12 plan 04) plus a
CR-01 hardening fix to the production sentinel-superseded cleanup gate
(`pipeline/cleanup.py`) and a defensive-import fix in `pipeline/orchestrate.py`.
Most of the changed surface is new, off-hours, dispatch-only tooling
(`scripts/backfill_cell_history_attribution.py`, its GitHub Actions workflow, an
owner-applied SQL migration, and matching docs/tests) that never runs inside
`generate_weekly_pdfs.py`.

Per the review brief, `pipeline/cleanup.py` and `pipeline/orchestrate.py` were
specifically checked for fail-safe direction (decline to delete). Both hold up:

- `pipeline/cleanup.py`'s CR-01 fix (`_is_sentinel_identifier` /
  `_is_real_name_identifier`) correctly narrows the old bare
  `startswith('_')` heuristic to an explicit allowlist, and the new
  `_is_real_name_identifier` deliberately treats *every* unrecognized
  leading-underscore token as neutral on *both* sides of the
  sentinel-superseded delete gate (never a deletion victim, never the
  real-name trigger). Traced through the allowlist, the SQL twin
  (`billing_audit/own03_backfill_attribution.sql` STEP 3), and
  `billing_audit.writer.is_sentinel_claimer` — the vocabularies are
  correctly scoped to two different concepts (filename error-token
  sanitization vs. attribution-snapshot placeholder names) and do not
  cross-contaminate.
- `pipeline/orchestrate.py`'s `_is_row_attachment` fallback (when the deep
  `smartsheet.models.enums.attachment_parent_type` import fails) degrades to
  "not a row attachment" rather than risking a mis-bucket, matching the
  documented fail-safe contract, and logs a one-time warning so the
  degradation is never silent.

The new OWN-03 source-5 script (`scripts/backfill_cell_history_attribution.py`)
is well-guarded on its *write* path (shared `--apply`/`--i-approved-this`/backup-probe/RPC
machinery from `backfill_claim_time_attribution.py`, itself gated server-side by
`billing_audit.own03_backfill_attribution.sql`'s sentinel-only `WHERE` clause).
The issues found below are all on the *read/reporting* side: a backlog-count
path that can silently under-report, an operator-facing CLI flag that silently
ignores filters, and a fully vestigial CLI flag. None of them risk a wrongful
write or deletion; they risk masked/skipped remediation work or operator
confusion.

## Warnings

### WR-01: `--check-backlog` can silently report a false "empty queue" when the sources-1-4 report file is corrupted

**File:** `scripts/backfill_cell_history_attribution.py:280-296, 342-350`
**Issue:** `_check_backlog_via_bounded_supabase_scan` (the fallback used when
`generated_docs/own03_backfill_report.json` is *absent*) explicitly documents
and tests "never a false zero backlog" — it returns `-1` on any Supabase
failure, and the caller treats a negative result as fatal (exit 7) specifically
"so a broken backend can never make a weekly job silently report an empty
queue forever" (see the `MED-07` test, `test_client_none_and_report_absent_exits_7`).

That guarantee is **not** applied to the sibling code path used when the
report file *exists but cannot be parsed*. `_load_candidate_report` catches
`(OSError, json.JSONDecodeError)`, logs a `WARNING`, and returns `([], {})`.
`_check_backlog` then computes `sum(...)` over an empty list and returns `0`
— the same "queue is empty" signal a genuinely empty backlog produces. In the
GitHub Actions workflow, `backlog_rows=0` skips the entire "Run cell-history
backfill" step (`cell-history-backfill.yml:107`). A truncated/corrupted
report file (interrupted prior run, disk issue, concurrent write) therefore
causes real backlog work to be silently skipped with a green build — exactly
the failure mode the fallback path was written to prevent, just on the other
branch of the same `if`.

**Fix:** Treat an existing-but-unparseable report file the same way as an
unavailable Supabase client — a fatal, non-zero-hiding condition, e.g.:
```python
def _check_backlog(report_path: str) -> int:
    p = Path(report_path)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logging.error(f"❌ {report_path} exists but could not be parsed: {exc}")
            return -1
        rows = data.get("rows") if isinstance(data, dict) else None
        rows = rows if isinstance(rows, list) else []
        return sum(
            1 for r in rows
            if isinstance(r, dict) and r.get("status") in ("unresolved", "conflict")
        )
    return _check_backlog_via_bounded_supabase_scan()
```
and have `main()` treat `n < 0` from this branch the same as the existing
`n < 0` handling already in place (it already exists for the fallback path —
just needs to also fire here).

### WR-02: `--check-backlog` silently ignores `--wr` / `--weeks` / `--roles`

**File:** `scripts/backfill_cell_history_attribution.py:826-827, 232-243`
**Issue:** `main()` calls `_check_backlog(args.report)` with no scoping
arguments at all, even though `--wr`, `--weeks`, and `--roles` are all valid,
documented CLI flags that argparse happily accepts alongside `--check-backlog`
(nothing rejects the combination). An operator who runs
`--check-backlog --wr 19073866` expecting a scoped count silently gets the
*total* backlog count across every WR/week/role instead — no warning, no
error. `_select_candidates` (which *does* apply these filters) is only used
by the real resolution path, never by `_check_backlog`.
**Fix:** Either thread the filters through to `_check_backlog` /
`_check_backlog_via_bounded_supabase_scan` (best-effort scoping for the
Supabase fallback, exact scoping when the report file is present via
`_select_candidates`), or explicitly reject the combination with a clear
error (`--check-backlog` is mutually exclusive with `--wr`/`--weeks`/`--roles`)
so the CLI never silently discards flags the user passed.

### WR-03: `--dry-run` is a vestigial flag that can never change behavior

**File:** `scripts/backfill_cell_history_attribution.py:260-262`
**Issue:** `--dry-run` is declared as `action="store_true", default=True` and
`args.dry_run` is never read anywhere else in the module (confirmed via
full-file search — the only occurrence of `dry_run` in the file is this
`add_argument` call). The script is *always* effectively in dry-run mode
unless `--apply` is separately passed; there is no way to pass `--dry-run
false` or otherwise toggle it off via this flag, since `store_true` flags
have no negation. The flag is therefore pure noise that misleads a reader (or
an operator writing a new CI step) into thinking it controls something.
**Fix:** Remove the flag (the real on/off switch is `--apply`), or if it must
stay for CLI-symmetry with `backfill_claim_time_attribution.py`, add an
assertion/comment making explicit that it is a no-op, and drop the
`cell-history-backfill.yml:130` `args=(--dry-run)` line that currently passes
a flag with no effect.

## Info

### IN-01: Backlog fallback scan bypasses the RPC read-surface convention and duplicates raw column names

**File:** `scripts/backfill_cell_history_attribution.py:353-425`
**Issue:** `_check_backlog_via_bounded_supabase_scan` performs a raw
`client.schema("billing_audit").table("attribution_snapshot").select("frozen_primary,frozen_helper,frozen_vac_crew")`
table-select. The sibling script's own docstring
(`scripts/backfill_claim_time_attribution.py`, `_discover_sentinel_targets`)
states the established convention explicitly: "never a raw Supabase
table-select on the attribution_snapshot table" — reads should go through
`billing_audit.writer.lookup_attribution` / `prefetch_attribution`. This new
scan is a reasoned, narrowly-scoped, read-only, fail-closed (`return -1` on
error) exception, and the raw column names it hard-codes
(`frozen_primary`/`frozen_helper`/`frozen_vac_crew`) do match the actual table
DDL confirmed in `billing_audit/own03_backfill_attribution.sql:45-49`. But it
is a *second* place in the Python codebase that now hard-codes those
data-team-owned, "opaque to the pipeline" column names (previously only the
owner-applied SQL file did), which is a fresh drift risk if the data team
renames them again — a rename would silently break this fallback (fail-closed
to exit 7, not silently wrong, but still an outage for this one code path
that a table-name-only convention violation makes easier to introduce again
elsewhere).
**Fix:** No urgent action needed given the fail-closed behavior; consider a
follow-up note in `billing_audit/schema.sql`'s opaque-table comment
cross-referencing this second consumer, so a future column rename search
finds it.

### IN-02: Cell-history name-conflict detection does not collapse internal whitespace before comparing distinct names

**File:** `scripts/backfill_cell_history_attribution.py:765-780`
**Issue:** `_resolve_one_candidate` dedupes candidate names via
`distinct_names.setdefault(stripped.casefold(), stripped)` where
`stripped = str(name_value).strip()` — only leading/trailing whitespace is
removed before the case-insensitive key is built. `billing_audit.writer.is_sentinel_claimer`
(used elsewhere in this same function to filter out sentinel names) instead
does `" ".join(text.replace("_", " ").split()).casefold()`, explicitly
collapsing internal whitespace runs. If Smartsheet cell history records the
same person's name with inconsistent internal spacing across two
transitions (e.g. `"Avery  Example"` vs. `"Avery Example"`), this function
treats them as two distinct claimers and reports a spurious `conflict`
instead of resolving to a single `proposed` name. This is fail-safe (under-resolves
rather than mis-resolves — a conflict just means more manual review), so it's
a minor robustness/quality gap rather than a correctness risk.
**Fix:** Normalize with the same whitespace-collapse used elsewhere before
building the `distinct_names` key, e.g. `" ".join(stripped.split()).casefold()`.

---

_Reviewed: 2026-09-03T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
