---
status: secured
phase: 02-attribution-bulk-prefetch-historical-claimer-remediation
asvs_level: 1
threats_total: 24
threats_closed: 24
threats_open: 0
audit_date: 2026-05-26
---

# Security Policy — Phase 02 Audit

<!-- gsd-security-auditor: Phase 02 — Attribution Bulk-Prefetch + Historical Claimer Remediation -->
<!-- Audit Date: 2026-05-26 | ASVS Level: 1 | Threats Closed: 24/24 | Open: 0/24 -->

## Phase 02 Threat Verification

**Phase:** 02 — Attribution Bulk-Prefetch + Historical Claimer Remediation
**Audit Date:** 2026-05-26
**ASVS Level:** 1
**Threats Closed:** 24/24
**Threats Open:** 0/24

> **T-02-06-02 (Command Injection) was OPEN at audit time and CLOSED during
> this secure-phase run** by implementing the WR-03 fix in
> `.github/workflows/weekly-excel-generation.yml` (commit on this branch). The
> `advanced_options` dispatch input is now bound to an `env:` variable
> (`ADVANCED_OPTIONS`) so the `${{ }}` expansion lands in the environment, not
> the script text, and every shell expansion is quoted with bash-native
> parameter parsing replacing the unquoted `$(echo ... | cut)` pipeline. Parser
> semantics (`key:value,key:value`, `;`→`,` for regen/reset lists) are
> byte-preserved and verified; YAML re-validated. See the audit trail below.

---

### Closed Threats

| Threat ID | Category | Disposition | Evidence |
|-----------|----------|-------------|----------|
| T-02-01 | Tampering / jsonb payload | mitigate | `billing_audit/writer.py:893` — `_WR_SANITIZE.sub("_", str(wr).split(".")[0])[:50]` on every WR before RPC; `schema.sql:317` — `jsonb_to_recordset(p_wr_weeks) AS q(wr TEXT, week_ending DATE)` typed coercion server-side |
| T-02-02 | Elevation / RPC grant | mitigate | `schema.sql:322` — `GRANT EXECUTE ON FUNCTION billing_audit.lookup_attribution_bulk(jsonb) TO service_role;` only |
| T-02-03 | DoS / retry-spam on absent RPC | mitigate | `writer.py:906` — distinct op id `lookup_attribution_bulk`; `writer.py:929-930` — PGRST202 → `rpc_missing`, zero additional retries; D-04 contract documented at `writer.py:856-864` |
| T-02-04 | Info Disclosure / foreman PII in logs | mitigate | `writer.py:950-953` — generic warning only on failure; `generate_weekly_pdfs.py:1046` — `_PII_LOG_MARKERS`; `sentry_before_send_log` at L1226 filters by markers |
| T-02-05 | DoS / oversized jsonb payload | accept (low) | Chunked at 500 (`writer.py:883`); 413 → `fetch_failure` fail-safe |
| T-02-06 | Tampering / WR# into payload | mitigate | `writer.py:893` — `_WR_SANITIZE.sub(...)` at payload construction; `writer.py:1035` — `resolve_claimer` also sanitizes WR before map lookup |
| T-02-07 | Info Disclosure / PII in pre-pass logs | mitigate | `generate_weekly_pdfs.py:5667-5676` — failure log uses generic counts/status only; sub-helper fallback log covered by `_PII_LOG_MARKERS` at L6451-6453 |
| T-02-08 | Tampering / identity-surface drift | mitigate | `generate_weekly_pdfs.py:5634-5688` — single `_attr_map` feeds all four consumer sites (B at L5701, C at L5784, D at L5865, sub-helper at L6368-6403) |
| T-02-09 | DoS / bulk-outage retry storm | mitigate | `generate_weekly_pdfs.py:5729-5731` and `5784-5786` — B/C construct `ResolveOutcome('hold', ...)` directly; per-row RPC never re-invoked; D uses-current without RPC |
| T-02-10 | Repudiation / re-introduce recency window | mitigate | `ATTRIBUTION_RESOLUTION_WEEKS` has zero live code references in `generate_weekly_pdfs.py` (grep: only in comments); absent from workflow YAML; `tests/test_attribution_resolution_scope.py` deleted |
| T-02-11 | Tampering/DoS-of-data / delete live attachment | mitigate | `generate_weekly_pdfs.py:4033` — `_ALWAYS_GARBAGE_PATTERNS = ('_NO_MATCH',)`; L4082 — isolated path uses restricted set; live-identity exemption at L4159-4163; `build_group_identity` reused at L4120 |
| T-02-12 | Elevation / remediation on cron | mitigate | `generate_weekly_pdfs.py:629-630` — `os.getenv('REMEDIATE_CLAIMERS', '0')`; L7901 `if REMEDIATE_CLAIMERS:` gate; no step-env literal pin on cron; Python module default `'0'` |
| T-02-13 | Info Disclosure / foreman PII in remediation logs | mitigate | `generate_weekly_pdfs.py:4195` — summary log emits counts only; individual deletion log at L4181 uses sanitized attachment name |
| T-02-14 | Tampering / ad-hoc filename parse divergence | mitigate | `generate_weekly_pdfs.py:4120` — remediation uses `build_group_identity` for all filename parsing |
| T-02-15 | Repudiation / premature AUTHORITATIVE=1 | mitigate | `.github/workflows/weekly-excel-generation.yml:443` — `SUPABASE_HASH_STORE_AUTHORITATIVE: '0'` with explicit revert-reason comment |
| T-02-16 | Repudiation / premature go-live flip | mitigate | `SUPABASE_HASH_STORE_AUTHORITATIVE: '0'` pinned in workflow; `website/docs/runbook/operations.md` documents human-gated validation gate |
| T-02-17 | Tampering/data loss / execute without dry-run | mitigate | `REMEDIATION_DRY_RUN` defaults `'1'`; workflow comment at L445-454 documents `advanced_options` activation syntax; `run_claimer_remediation` `dry_run` parameter gates all deletes |
| T-02-18 | Info Disclosure / PII in runbook examples | accept (low) | Placeholder values only in runbook |
| T-02-05-01 | DoS-billing-suppression / not-yet-deployed RPC | mitigate | `generate_weekly_pdfs.py:620-621` — `ATTRIBUTION_BULK_PREFETCH_FALLBACK` defaults `'1'`; L5687 — `rpc_missing` → per-row fallback; workflow pin at L462 |
| T-02-05-02 | DoS-retry-storm / fallback on transient | mitigate | `generate_weekly_pdfs.py:5686-5688` — `_attr_use_per_row_fallback` True ONLY on `rpc_missing`; `fetch_failure` does not set this flag; D-04 HOLD preserved at L5729-5731 and L5784-5786 |
| T-02-05-03 | Info-disclosure / WR-sanitization split-brain | mitigate | `writer.py:1035` — `resolve_claimer` sanitizes WR with `_WR_SANITIZE` before map lookup; comment at L1028-1034 documents the split-brain risk |
| T-02-05-04 | Repudiation / sub-helper outage silently downgraded | mitigate | `generate_weekly_pdfs.py:6372-6385` — `_attr_status == 'fetch_failure'` sets `_attribution_reason`; L6440-6466 — per-WR WARNING logged with sanitized identifiers; `_bug_c_warning_seen` prevents spam |
| T-02-05-05 | Tampering (read-side only) | accept | Read-only SELECT RPC; freeze side untouched per threat register |
| T-02-06-01 | Tampering / isolated sweep deletes valid _Unknown_Foreman | mitigate | `generate_weekly_pdfs.py:4033` — `_ALWAYS_GARBAGE_PATTERNS = ('_NO_MATCH',)` only; L4082 — isolated path (`valid_wr_weeks=None` at L7911) uses restricted set |
| T-02-06-03 | Repudiation / out_of_window conflates clean+garbage | mitigate | Garbage check runs before window filter (IN-02 reorder); `out_of_window` incremented only after garbage check passes |
| T-02-06-04 | DoS / window=0 sweeps all history | accept | Default 26 weeks; dry-run-first; `REMEDIATE_CLAIMERS` default OFF |
| T-02-06-05 | Tampering / cron auto-fire | mitigate | Module default `'0'`; no step-env pin; `advanced_options` parser only runs on `workflow_dispatch` with non-empty input |
| T-02-06-02 | Elevation / Command Injection | mitigate (fixed during audit) | `.github/workflows/weekly-excel-generation.yml:201-224` — input bound to `env: ADVANCED_OPTIONS`; `IFS=',' read -ra` + `${option%%:*}`/`${option#*:}` replace the unquoted `$(echo $OPTIONS \| tr)` + `cut` pipeline; all expansions quoted incl. `"$GITHUB_ENV"`. Injection payload `$(cmd)` is now a literal value (verified); YAML re-validated; parser semantics preserved |

---

### Resolved During Audit — T-02-06-02 (was BLOCKER)

#### T-02-06-02: `advanced_options` shell injection feeding destructive remediation mode — FIXED

**Category:** Elevation / Command Injection
**Disposition declared:** mitigate
**Declared mitigation:** "wire real advanced_options parser path; remove masking literal env pins; default OFF + dry-run-first"
**Status: CLOSED — fixed during this secure-phase run**

**What was already implemented (verified at audit time):**
- Literal step-env pins removed (WR-02 closed): confirmed absent from workflow
- Parser branches for `remediate_claimers`, `remediation_dry_run`, `remediation_window_weeks` wired at `.github/workflows/weekly-excel-generation.yml:214-216`
- Default OFF (`REMEDIATE_CLAIMERS='0'`) and dry-run-first confirmed in Python module defaults

**The injection surface that existed at audit time (now removed):**

File: `.github/workflows/weekly-excel-generation.yml:203-218` (pre-fix)

```yaml
run: |
  echo "Parsing advanced options: ${{ github.event.inputs.advanced_options }}"
  OPTIONS="${{ github.event.inputs.advanced_options }}"
  for option in $(echo $OPTIONS | tr ',' '\n'); do
    key=$(echo $option | cut -d':' -f1)
    value=$(echo $option | cut -d':' -f2-)
    case $key in
      remediate_claimers) echo "REMEDIATE_CLAIMERS=$value" >> $GITHUB_ENV ;;
```

Two confirmed injection vectors:
1. Line 204: `${{ github.event.inputs.advanced_options }}` is GitHub Expression syntax expanded at template-render time — a payload of `$(malicious_cmd)` or `` `malicious_cmd` `` executes in the shell before the script body logic runs.
2. Line 207: `$(echo $OPTIONS | tr ',' '\n')` — unquoted word-split loop; shell metacharacters in the input value produce extra words parsed as commands.

**Security significance:** Before Phase 2, `advanced_options` fed only operational controls (`MAX_GROUPS`, `REGEN_WEEKS`, `RESET_WR_LIST`). Phase 2 routes `remediate_claimers:1,remediation_dry_run:0` through this unquoted surface, which enables EXECUTE-mode deletion of Smartsheet attachments. A write-access actor can exploit the injection to both run arbitrary commands on the GitHub Actions runner AND enable the destructive deletion mode in the same input string.

**Bounding factor:** `workflow_dispatch` requires repository write access. The vector is not publicly reachable.

**Fix applied this run (from 02-REVIEW.md WR-03):**
Bound the input to an `env:` variable; reference it as a quoted shell variable throughout; quote all expansions. Implemented form:

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
        remediate_claimers)       echo "REMEDIATE_CLAIMERS=$value"       >> "$GITHUB_ENV" ;;
        remediation_dry_run)      echo "REMEDIATION_DRY_RUN=$value"      >> "$GITHUB_ENV" ;;
        remediation_window_weeks) echo "REMEDIATION_WINDOW_WEEKS=$value" >> "$GITHUB_ENV" ;;
        max_groups)               echo "MAX_GROUPS=$value"               >> "$GITHUB_ENV" ;;
        regen_weeks)              echo "REGEN_WEEKS=$(printf '%s' "$value" | tr ';' ',')" >> "$GITHUB_ENV" ;;
        reset_wr_list)            echo "RESET_WR_LIST=$(printf '%s' "$value" | tr ';' ',')" >> "$GITHUB_ENV" ;;
      esac
    done
```

**Resolution:** The fix was implemented in
`.github/workflows/weekly-excel-generation.yml` during this secure-phase run.
The injection surface pre-existed this phase but the destructive capability was
new to Phase 2; the surface is now removed. Remediation mode
(`REMEDIATE_CLAIMERS=1`) is safe to activate via `workflow_dispatch`
`advanced_options` — the value can no longer break out of the variable.

---

## Advisory Items (Not Blockers)

These items from 02-REVIEW.md are correctness gaps with marginal security relevance. They do not block shipping the read/attribution paths but should be addressed before the next phase.

| Item | File | Description | Security Impact |
|------|------|-------------|-----------------|
| WR-01 (02-REVIEW.md) | `billing_audit/writer.py:920-921` | `rpc_missing` probe calls `_invoke()` directly when `with_retry` returns `None` due to global kill switch or open circuit breaker — one extra live RPC against a disabled integration | Defeats op-isolation kill switch for one call per failed chunk; no data write; bounded |
| WR-02 (02-REVIEW.md) | `billing_audit/writer.py:923-924` | When probe `_invoke()` succeeds (transient recovery), code returns `({}, "fetch_failure")` and discards the data — all B/C rows HOLD for the entire run | Availability impact only; no data deletion or escalation |
| IN-03 (02-REVIEW.md) | `generate_weekly_pdfs.py:6463-6465` | Sub-helper outage WARNING names `PGRST404` but the missing-RPC condition is `PGRST202` — on-call engineer grepping the documented code will miss the relevant log | Operational observability gap; no security escalation |

---

## Accepted Risks Log

| ID | Description | Accepted By | Rationale |
|----|-------------|-------------|-----------|
| T-02-05 | Oversized jsonb payload causing 413 | Threat register | Chunked at 500 pairs; 413 treated as fetch_failure (fail-safe). Practical ceiling ~22 KB/chunk. |
| T-02-18 | PII in runbook examples | Threat register | Runbook uses placeholder values only. |
| T-02-05-05 | Bulk RPC read-side tampering | Threat register | Read-only SELECT; no write path; freeze side untouched. |
| T-02-06-04 | window=0 sweeps all history | Threat register | Mitigated by dry-run-first default and REMEDIATE_CLAIMERS default-OFF. |

---

## Unregistered Flags

None. The 02-06-SUMMARY.md Threat Surface Scan confirmed no new network endpoints, auth paths, file access patterns, or schema changes were introduced by Plans 05/06. The injection surface (WR-03) was registered in the threat model as T-02-06-02.

---

## Security Audit Trail

### 2026-05-26 — Initial audit (gsd-security-auditor)

| Metric | Count |
|--------|-------|
| Threats found | 24 |
| Closed | 23 |
| Open | 1 (T-02-06-02 Command Injection) |

### 2026-05-26 — Remediation during secure-phase run

- Implemented the WR-03 fix for T-02-06-02 in
  `.github/workflows/weekly-excel-generation.yml`: bound the untrusted
  `advanced_options` dispatch input to `env: ADVANCED_OPTIONS`, replaced the
  unquoted `$(echo $OPTIONS | tr ',' '\n')` + `cut` pipeline with
  `IFS=',' read -ra` + `${option%%:*}` / `${option#*:}`, and quoted all
  expansions including `"$GITHUB_ENV"`.
- Verified: YAML re-validates; parser semantics byte-preserved
  (`max_groups`, `regen_weeks`/`reset_wr_list` `;`→`,`, remediation keys);
  an injected `$(cmd)` payload is treated as a literal value, not executed.

| Metric | Count |
|--------|-------|
| Threats found | 24 |
| Closed | 24 |
| Open | 0 |

**threats_open: 0 — phase is THREAT-SECURE.**

Three advisory items (WR-01, WR-02, IN-03 above) remain as non-blocking
follow-ups for a future cleanup pass.

---

_Auditor: gsd-security-auditor (Claude Sonnet) + secure-phase orchestrator remediation_
_Phase: 02-attribution-bulk-prefetch-historical-claimer-remediation_
_Completed: 2026-05-26_
