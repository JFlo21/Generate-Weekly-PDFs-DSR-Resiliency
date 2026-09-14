---
phase: 11-incremental-read-affected-group-regeneration
reviewed: 2026-09-14T15:53:33Z
depth: standard
files_reviewed: 29
files_reviewed_list:
  - CLAUDE.md
  - pipeline/orchestrate.py
  - pipeline/fetch.py
  - pipeline/parity.py
  - pipeline/change_detection.py
  - pipeline/cleanup.py
  - pipeline/discovery.py
  - pipeline/config.py
  - pipeline/attribution.py
  - pipeline/observability.py
  - pipeline_memory/reader.py
  - pipeline_memory/writer.py
  - generate_weekly_pdfs.py
  - billing_audit/schema.sql
  - .github/workflows/weekly-excel-generation.yml
  - .github/prompts/configuration-environment.md
  - docs/run-memory-write-flip-checklist.md
  - tests/golden/facade_allowlist.json
  - tests/golden/baseline_names.json
  - tests/golden/mypy_baseline.txt
  - tests/golden/mypy_baseline_count.txt
  - tests/fixtures/incremental/abbreviated_sheet_response.json
  - tests/fixtures/incremental/deleted_row.json
  - tests/fixtures/incremental/formula_only_change.json
  - tests/test_incremental_read.py
  - tests/test_deep_run_reconciliation.py
  - tests/test_parity_shadow.py
  - tests/test_pipeline_memory_shadow.py
  - tests/test_security_audit_followup.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-09-14T15:53:33Z
**Depth:** standard
**Files Reviewed:** 29
**Status:** issues_found

## Summary

Reviewed Phase 11 (Incremental Read + Affected-Group Regeneration, INC-01..INC-05) at
HEAD, covering the delta-read primitives (`if_version_after` probe + `rows_modified_since`
fetch), the 7-trigger `resolve_run_mode` escalation ladder, the PHASE 2a/2b incremental
split, `pipeline_memory` reader/writer contracts, shadow-incremental parity proof,
weekly deep-run deletion reconciliation, and the INC-05 local-cache/pre-fetch retirement,
per the task's explicit scope (the stale `diff_base` was intentionally ignored in favor
of reviewing the listed files as they exist at HEAD).

This is an unusually defensive, heavily self-documented codebase: nearly every
non-obvious branch carries an inline citation to the incident, PR, or design decision
that produced it, and the fail-open/"too wide, never too narrow" (T-11-18) invariant is
enforced consistently at every escalation point I traced (delta-probe exceptions,
unconfirmed memory writes, identity-lost rows, empty sheet mappings, zero-row deep-run
sheets). `pipeline_memory/reader.py` and `writer.py` (2,061 combined lines) show no
confirmed defects — every Supabase read/write failure path degrades to "cannot confirm,
escalate," matching the documented contract. `pipeline/cleanup.py`'s `keep_historical`
call-boundary override, `pipeline/discovery.py`'s registry-version skip gate (including
the Phase 14 `mapping_schema` marker check), and `pipeline/observability.py`'s PII
scrubbing (log body, breadcrumb `data` keys, stack-frame vars) were all traced and are
internally consistent with their own documentation and with the workflow YAML (the
Sentry Crons monitor schedule literal was cross-checked byte-for-byte against the
weekday `schedule.cron` value and matches).

Three findings resulted, all traceable to the Phase 11 Plan 08 (INC-05) retirement of
the local JSON caches: one genuine correctness gap in the delta-probe's
abbreviated-response heuristic (a whole-sheet-emptied edge case is silently
misclassified as "unchanged," narrowing this run's affected-group scope — self-healing
only via the next weekly full/deep run, which does not depend on the version
watermark), and two code-quality items where the INC-05 cleanup left dead imports/dead
functions behind. No Critical/BLOCKER-level issues were found: no injection vectors, no
hardcoded secrets, no unsafe deserialization, no auth bypasses, no data-loss paths, and
no thread-safety defects (the two module-level mutable globals in `pipeline/fetch.py`,
`_LAST_SHEET_VERSIONS` and `_LAST_FULL_READ_FAILED_SHEET_IDS`, are lock-protected at
every mutation site, including the new `ThreadPoolExecutor`-driven delta-probe path).

## Warnings

### WR-01: Whole-sheet-emptied delta probe is indistinguishable from "unchanged," silently narrowing this run's affected-group scope

**File:** `pipeline/fetch.py:154-165`, `pipeline/fetch.py:244-261`, `pipeline/orchestrate.py:1788-1790`

**Issue:** `_is_abbreviated_response` classifies a probe response as "abbreviated / sheet
unchanged" using pure falsy-truthiness on `.rows`:

```python
def _is_abbreviated_response(sheet: Any) -> bool:
    return not getattr(sheet, 'rows', None)
```

Per the documented Smartsheet `if_version_after` contract (and the real captured fixture
`tests/fixtures/incremental/abbreviated_sheet_response.json`, whose `raw_response` is
`{"version": 8}` with no `rows` key at all), a version that has *not* advanced yields a
response with `rows` absent/`None`. But a version that *has* advanced yields the full,
current sheet — which legitimately has `rows == []` when every row on that source sheet
has been deleted (the probe call carries no `rows_modified_since` filter, so it returns
the sheet's complete current row set, not a delta). `not []` is `True`, so this second,
genuinely-changed case is indistinguishable from the first at this call site.

The consequence in `fetch_sheet_delta` (`pipeline/fetch.py:244-261`): when
`_is_abbreviated_response(probe)` is `True` and `probe.version` is present (which it
always is on a full response), the function returns
`{"escalate": False, "sheet": None, "version": version, "calls": 1}` — the exact same
shape as a genuine no-op — and unconditionally advances the persisted
`_LAST_SHEET_VERSIONS[source['id']]` watermark to the new version. The consuming loop in
`pipeline/orchestrate.py::_run_phase2_incremental` treats this identically to "nothing
changed":

```python
sheet = probe_result.get("sheet")
if sheet is None:
    continue  # unchanged -- zero rows, nothing to add
```

(`pipeline/orchestrate.py:1788-1790` — the comment itself conflates "unchanged" with
"zero rows," which is precisely the bug.) A source sheet that goes from N rows to zero
in one probe cycle therefore contributes nothing to `delta_rows`, so
`_run_memory_write_phase` never diffs its rows against `row_state`, and the WR/week
pairs it would have affected never enter this run's `affected` set — the opposite of the
codebase's own repeatedly-stated T-11-18 invariant ("regeneration scope can only ever be
too WIDE, never too narrow"). No escalation, warning log, or Sentry signal is raised for
this specific case, unlike every other ambiguous/failure condition in this module (probe
exceptions, missing version, memory-write non-confirmation all escalate loudly).

This is bounded, not unbounded data loss: the weekly `weekly_comprehensive` deep run
(`_reconcile_deep_run_deletions`) performs a true full read via `get_all_source_rows`
unconditionally — it does not consult `last_sheet_version`/the probe outcome at all — so
a whole-sheet deletion missed by every `production_frequent` run in between is still
caught and reconciled at the next Monday deep run. The practical impact is therefore a
detection-latency gap (up to ~1 week) for the specific, comparatively rare event of an
entire source sheet being emptied, rather than permanent data loss.

**Fix:** Disambiguate using a field that only exists on the full (non-abbreviated)
response shape — e.g. require both `rows` and a full-response-only attribute (such as
`columns` or `total_row_count`, which the abbreviated `{"version": 8}` shape never
carries) to be absent before classifying as "abbreviated/unchanged":

```python
def _is_abbreviated_response(sheet: Any) -> bool:
    """True only when the response is the genuinely abbreviated
    {"version": N}-only shape (no rows AND no sheet-level metadata).
    A full response with zero rows (e.g. every row deleted) must NOT
    be classified as abbreviated.
    """
    has_rows = bool(getattr(sheet, 'rows', None))
    if has_rows:
        return False
    # A full response always carries sheet-level metadata the
    # abbreviated {"version": N}-only shape never does.
    return getattr(sheet, 'columns', None) is None
```

At minimum, add a WARNING log (and widen `dropped_row_ids`/escalate to full mode) when a
probe reports a version increase but zero rows, so this edge case is visible and
correct, rather than silently absorbed into the "unchanged" path.

## Info

### IN-01: Eleven dead imports from `pipeline.attribution` in `pipeline/orchestrate.py`

**File:** `pipeline/orchestrate.py:257-276`

**Issue:** The `from pipeline.attribution import (...)` block imports 19 names; 11 are
never referenced again anywhere in `orchestrate.py` (confirmed via repo-wide grep for
both call-syntax and bare-name usage, and for any monkeypatch/attribute-access against
`pipeline.orchestrate.<name>` — zero matches):

```python
from pipeline.attribution import (  # noqa: E402
    BILLING_AUDIT_ROW_CACHE_MAX_ENTRIES,      # unused
    PHASE_1_1_HASH_PRUNE_VERSION,             # unused
    SUBPROJECT_B_HASH_PRUNE_VERSION,          # unused
    SUBPROJECT_D_HASH_PRUNE_VERSION,          # unused
    VAC_CREW_HASH_PRUNE_VERSION,              # unused
    _SUBCONTRACTOR_SCOPE_VARIANTS,
    _build_primary_wr_scope,
    _build_subcontractor_wr_scope,
    _build_vac_crew_wr_scope,
    _run_phase_1_1_hash_prune,                # unused
    _run_subproject_b_hash_prune,             # unused
    _run_subproject_d_hash_prune,             # unused
    _run_vac_crew_hash_prune,                 # unused
    build_helper2_fill_keys,
    helper2_fill_admits,
    load_billing_audit_row_cache,             # unused
    run_claimer_remediation,
    save_billing_audit_row_cache,             # unused
    warm_billing_audit_row_cache,
)
```

This is leftover from the Phase 11 Plan 08 (INC-05) retirement of the local
`hash_history`/`billing_audit_row_cache` JSON caches — `orchestrate.py`'s own inline
comment (~line 3350-3360) and `pipeline/attribution.py`'s module docstring both state
explicitly that `pipeline.orchestrate.main()` no longer calls the four hash-prune
runners or the load/save cache helpers. The separate, still-required re-export of these
same names in `generate_weekly_pdfs.py` (confirmed present in
`tests/golden/baseline_names.json` / `facade_allowlist.json`) is unaffected by this
finding — that facade-level import serves the golden-file completeness contract and
should stay.

**Fix:** Remove the 11 unused names from this specific import statement:

```python
from pipeline.attribution import (  # noqa: E402
    _SUBCONTRACTOR_SCOPE_VARIANTS,
    _build_primary_wr_scope,
    _build_subcontractor_wr_scope,
    _build_vac_crew_wr_scope,
    build_helper2_fill_keys,
    helper2_fill_admits,
    run_claimer_remediation,
    warm_billing_audit_row_cache,
)
```

### IN-02: ~375 lines of one-time hash-history prune logic in `pipeline/attribution.py` have no production caller

**File:** `pipeline/attribution.py:231-605`

**Issue:** `_run_phase_1_1_hash_prune` (231-375), `_run_subproject_b_hash_prune`
(378-441), `_run_vac_crew_hash_prune` (444-523), and `_run_subproject_d_hash_prune`
(526-605) all mutate a `hash_history: dict` parameter that models the local JSON cache
retired by Phase 11 Plan 08 (INC-05). The module's own docstring says so directly:
"`pipeline.orchestrate.main()` no longer calls it" (line 78) and "are no longer called
by `pipeline.orchestrate`" (line 108). These four functions (plus their four
`*_HASH_PRUNE_VERSION` sentinel constants) are reachable today only from their own
unit tests, not from any production entry point — this is confirmed dead code in the
live call graph, distinct from IN-01 (which is a dead *import*, not a dead
*function body*).

This is flagged as Info rather than a request to delete: `CLAUDE.md`'s production-safety
rules direct against removing production code "unless it is definitively broken or
causing bugs," and these functions are still exercised by fixture-level tests that
presumably the team wants to keep green as historical/regression coverage. The
finding is for maintainability visibility — a future maintainer skimming
`pipeline/attribution.py` has no signal (short of reading the docstrings closely) that
this ~40% of the file's line count is unreachable in production, which risks
bit-rotting logic around a data structure (`hash_history`) that no longer exists
anywhere in the runtime path.

**Fix:** Either (a) explicitly mark the four functions and their version constants as
archival/retired in a section banner comment (e.g. `# RETIRED — Phase 11 Plan 08 /
INC-05: kept for one-time-migration regression coverage only, no production caller`),
or (b) relocate them out of the actively-maintained `pipeline/attribution.py` module
into a dedicated `tests/`-adjacent or `scripts/archive/`-style location if the team
agrees the migrations are permanently done and the fixture tests can be retired with
them. No behavior change either way — this is a discoverability/documentation fix,
not a functional one.

---

_Reviewed: 2026-09-14T15:53:33Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
