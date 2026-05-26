---
phase: 02-attribution-bulk-prefetch-historical-claimer-remediation
reviewed: 2026-05-26T21:50:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - billing_audit/writer.py
  - generate_weekly_pdfs.py
  - .github/workflows/weekly-excel-generation.yml
  - tests/test_billing_audit_shadow.py
  - tests/test_claimer_remediation.py
  - tests/test_subcontractor_helper_shadow_rescue.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 2: Code Review Report (Gap-Closure Round)

**Reviewed:** 2026-05-26T21:50:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

This is an adversarial gap-closure review of the diff `abbc336..HEAD` — the work
produced by plans 02-05/02-06 (and the standalone `prefetch_attribution` `(wr,week)`
pairs fix) to close the prior 02-REVIEW.md findings (CR-01 deployment-ordering
BLOCKER, WR-01..05, IN-01..04).

**Verdict on the prior findings:** all are credibly closed.
- **CR-01** (code-before-RPC deploy ordering) → closed via the `rpc_missing`
  status in `prefetch_attribution` + the `ATTRIBUTION_BULK_PREFETCH_FALLBACK`
  degradation gate that routes B/C/D/sub-helper to the deployed per-row
  `lookup_attribution` instead of HOLDing all billing. The D-04 transient-outage
  HOLD contract is preserved (genuine `fetch_failure` still HOLDs B/C).
- **WR-01** (split-brain map key) → closed: `resolve_claimer` now sanitizes the
  prefetched-map lookup WR via `_WR_SANITIZE` to match the RPC-echoed sanitized key.
- **WR-03/WR-05** → closed: D never HOLDs (use-current on empty map); sub-helper
  surfaces the outage WARNING without re-issuing a per-row RPC.
- **WR-04** → closed: isolated remediation path (`valid_wr_weeks=None`) restricts
  deletion to `_ALWAYS_GARBAGE_PATTERNS = ('_NO_MATCH',)`, preserving the legitimate
  `_Unknown_Foreman` sentinel.
- **WR-02** → closed: literal step-env pins removed so `advanced_options` $GITHUB_ENV
  exports are not overridden; Python defaults keep cron runs OFF/safe.
- **IN-02** (out_of_window counter inflation) / **IN-04** (shadowed `datetime`
  import) → closed.

Type/key consistency was traced end-to-end: `excel_serial_to_date` → `datetime`,
`_we_d = .date()` → `date`; the prefetch payload `we.isoformat()` and the result_map
`datetime.date.fromisoformat(...)` key are both `date`; the `resolve_claimer` lookup
passes the same `date`. No key-type mismatch. WR sanitization is symmetric at the
producer (RPC echo) and consumer (`resolve_claimer`) sites. No orphaned references to
the removed `_resolve_claimer_bulk`/`_ResolveOutcome` imports remain.

Full suite verified green locally: `pytest tests/` → **986 passed / 29 skipped /
69 subtests**; `py_compile` clean. The 3 skips in the new tests are the documented
postgrest-absent dev-env guard.

The findings below are residual hardening items, not regressions in the fixes.

## Warnings

### WR-01: `rpc_missing` probe re-invocation bypasses the per-op circuit breaker / global kill switch

**File:** `billing_audit/writer.py:905-931`
**Issue:** When `with_retry(_invoke, op="lookup_attribution_bulk")` returns `None`,
the new CR-01 probe calls the bare `_invoke()` directly to re-classify the failure.
`with_retry` can return `None` *without ever running `fn`* in two cases: (a) the
run-global kill switch is set (`_global_disable_reason is not None`), or (b) the
`lookup_attribution_bulk` circuit breaker is already open (`op in _open_circuits`).
In both cases the breaker/kill switch exists precisely to *stop issuing network
calls*, but the probe re-issues a live RPC anyway. It is bounded (one extra call per
failed chunk, and the function returns on the first failed chunk), so it is not a
storm — but it defeats the kill switch / breaker on the already-disabled path, which
the op-isolation invariant (CLAUDE.md [2026-04-25 14:00]) exists to enforce. On a
PGRST106 global-kill run, this also makes one more doomed round-trip after the
integration was supposed to be fully short-circuited.
**Fix:** Gate the probe on breaker/kill state so a disabled integration is not
re-pinged:
```python
result = with_retry(_invoke, op="lookup_attribution_bulk")
if result is None:
    # If the breaker is already open or the run is globally disabled,
    # with_retry never ran fn — do NOT re-issue a live probe. Treat as
    # transient (fetch_failure) so B/C preserve the HOLD contract.
    if (_client_mod._global_disable_reason is not None
            or "lookup_attribution_bulk" in _client_mod._open_circuits):
        return {}, "fetch_failure"
    # ... existing PGRST202 probe ...
```

### WR-02: `rpc_missing` probe discards a successful recovery result (run-wide attribution loss on a transient blip)

**File:** `billing_audit/writer.py:920-924`
**Issue:** In the probe, if the bare `_invoke()` *succeeds* (the original failure was
transient and recovered on the extra call), the code returns `({}, "fetch_failure")`
and throws away the just-fetched data. Because `prefetch_attribution` returns on the
first failed chunk, a single transient blip on chunk 1 that recovers on the probe
discards the frozen-attribution map for the **entire run** — every B/C row then HOLDs
and every D/sub-helper row uses-current, a strictly worse outcome than consuming the
data already in hand. The comment ("treat the original failure as transient")
documents the classification, but the rationale does not justify discarding a result
that succeeded.
**Fix:** When the probe succeeds, fold its rows into `result_map` and `continue` the
chunk loop instead of returning `fetch_failure`:
```python
try:
    _probe_result = _invoke()
except Exception as _probe_exc:
    ...  # classify PGRST202 vs fetch_failure (unchanged)
else:
    _pdata = getattr(_probe_result, "data", None) or []
    if isinstance(_pdata, dict):
        _pdata = [_pdata] if _pdata else []
    for row in _pdata:
        ...  # same key-build + result_map[key] = row as the success path
    if _pdata:
        overall_status = "success"
    continue
```

### WR-03: `advanced_options` shell parser interpolates untrusted dispatch input (command-injection surface now feeding a destructive mode)

**File:** `.github/workflows/weekly-excel-generation.yml:204-217`
**Issue:** The parser interpolates `${{ github.event.inputs.advanced_options }}`
directly into the shell script body (`echo "Parsing ...: ${{ ... }}"` and
`OPTIONS="${{ github.event.inputs.advanced_options }}"`) and loops with unquoted
`$OPTIONS`/`$option`/`$value`. A `workflow_dispatch` operator can inject shell via the
`advanced_options` string (`$(...)`, backticks, `;`). The vector is pre-existing, but
this phase routes three new operator-controlled keys through it
(`remediate_claimers`, `remediation_dry_run`, `remediation_window_weeks`), and one
combination (`remediate_claimers:1,remediation_dry_run:0`) flips a *destructive
attachment-deletion* mode. `workflow_dispatch` requires write access, which bounds
exposure, but a write-access compromise can now both inject runner commands and
silently enable EXECUTE-mode deletion.
**Fix:** Bind the input to an `env:` var, reference it as a quoted shell variable
(never template it into the script body), and quote all expansions:
```yaml
      - name: Parse advanced options
        if: github.event.inputs.advanced_options != ''
        env:
          ADVANCED_OPTIONS: ${{ github.event.inputs.advanced_options }}
        run: |
          printf 'Parsing advanced options: %s\n' "$ADVANCED_OPTIONS"
          IFS=',' read -ra _opts <<< "$ADVANCED_OPTIONS"
          for option in "${_opts[@]}"; do
            key="${option%%:*}"; value="${option#*:}"
            case "$key" in
              remediate_claimers) echo "REMEDIATE_CLAIMERS=$value" >> "$GITHUB_ENV" ;;
              ...
            esac
          done
```

## Info

### IN-01: garbage detection substring-matches the full filename instead of the parsed identifier

**File:** `generate_weekly_pdfs.py:4033,4139`
**Issue:** Garbage detection is `any(pat in _name for pat in _patterns)` against the
full attachment name, not the `_identifier` that `build_group_identity` already
parsed out. `'_NO_MATCH'` will match anywhere in the name. The ledger documents this
as the accepted "WARNING 6" tradeoff and the practical risk is near-nil (`#NO MATCH`
sanitizes to `_NO_MATCH`; a human name "No Match" sanitizes to `No_Match`, which does
not match). Flagged only because the parsed `_identifier` is in hand and would make
the gate exact and self-documenting.
**Fix (optional):** `_is_garbage = any(pat in (_identifier or '') for pat in _patterns)`.

### IN-02: probe `_APIError = ()` fallback relies on the subtle `isinstance(x, ())` == False idiom

**File:** `billing_audit/writer.py:917-919,926`
**Issue:** When `postgrest` is unavailable the probe sets `_APIError = ()` and later
does `isinstance(_probe_exc, _APIError)`. `isinstance(x, ())` is always `False`, so it
correctly falls through to `fetch_failure`. Functionally correct, but the
empty-tuple-as-never-match idiom is easy for a future maintainer to "fix" into a bug,
and the use site (line 926) has no comment explaining it.
**Fix (optional):** make intent explicit:
`if _APIError and isinstance(_probe_exc, _APIError) and ...`.

### IN-03: sub-helper outage WARNING points operators at `PGRST404` but the actual missing-RPC code is `PGRST202`

**File:** `generate_weekly_pdfs.py:6463-6465`
**Issue:** The operator-facing sub-helper fallback WARNING says "check Supabase Logs
for PGRST106/PGRST301/PGRST404 on the 'lookup_attribution' op." The missing-RPC
condition this phase actually classifies (and the whole CR-01 fix keys on) is
`PGRST202` (function not found), not `PGRST404`. An on-call engineer grepping for
`PGRST404` will not find the log line for the exact deploy-ordering failure this
phase exists to handle.
**Fix:** Name `PGRST202` (and/or drop the non-existent `PGRST404`):
`... check Supabase Logs for PGRST106/PGRST301/PGRST202 ...`.

---

_Reviewed: 2026-05-26T21:50:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
