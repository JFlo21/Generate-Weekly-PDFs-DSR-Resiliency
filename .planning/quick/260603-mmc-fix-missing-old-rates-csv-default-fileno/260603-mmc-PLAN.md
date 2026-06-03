---
phase: quick-260603-mmc
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - generate_weekly_pdfs.py
  - tests/test_subcontractor_pricing.py
  - memory-bank/living-ledger.md
autonomous: true
requirements:
  - QUICK-OLD-RATES-CSV-FIX
  - QUICK-SENTRY-MODERNIZE
user_setup: []

must_haves:
  truths:
    - "A run whose resolved OLD_RATES_CSV path does not exist emits NO ERROR-level log and NO Sentry event for that condition - it is a benign INFO + breadcrumb skip."
    - "load_contract_rates and build_cu_to_group_mapping still return {} when the file is absent (empty-dict contract preserved)."
    - "A file that EXISTS but is malformed still raises a Sentry ERROR, now grouped under a stable fingerprint ['rate-csv-load-failure', <fn>]."
    - "The Sentry cron monitor_config describes the REAL production schedule (weekday every-2h, America/Chicago, max_runtime aligned to the live workflow timeout), not the stale 'every Monday 17:30 America/Phoenix' values."
    - "Sentry issues can be filtered by run mode: res_grouping_mode, wr_filter_active (BOOL), force_generation - with NO raw WR list, names, or dollar amounts in any tag/context."
    - "pytest tests/ passes in full; python -m py_compile generate_weekly_pdfs.py succeeds."
  artifacts:
    - path: "generate_weekly_pdfs.py"
      provides: "os.path.isfile() existence guard in both rate loaders; fingerprinted except; corrected monitor_config; run-mode tags"
      contains: "os.path.isfile"
    - path: "tests/test_subcontractor_pricing.py"
      provides: "New assertNoLogs(level=ERROR) tests for the benign missing-file skip branch in both loaders"
      contains: "assertNoLogs"
    - path: "memory-bank/living-ledger.md"
      provides: "Dated [YYYY-MM-DD HH:MM] entry recording optional-rate-CSV skip + Sentry monitor_config correction + new run-mode tags"
      contains: "rate CSV"
  key_links:
    - from: "load_contract_rates (generate_weekly_pdfs.py)"
      to: "benign INFO + sentry_add_breadcrumb skip branch"
      via: "if not os.path.isfile(filepath): return {} BEFORE the open()/except path"
      pattern: "os\\.path\\.isfile"
    - from: "build_cu_to_group_mapping (generate_weekly_pdfs.py)"
      to: "benign INFO + sentry_add_breadcrumb skip branch"
      via: "if not os.path.isfile(old_csv_path): return {} BEFORE the open()/except path"
      pattern: "os\\.path\\.isfile"
    - from: "_sentry_cron_checkin_start monitor_config"
      to: "real production cron schedule"
      via: "schedule value '0 13,15,17,19,21,23,1 * * 1-5', timezone America/Chicago"
      pattern: "America/Chicago"
---

<objective>
Fix the recurring Sentry ERROR caused by the missing OLD_RATES_CSV default,
and correct/extend the existing Sentry 2.x instrumentation in the Python
billing pipeline.

The OLD_RATES_CSV default file ('CU List - Corpus North & South.csv') was
never committed. The production workflow pins OLD_RATES_CSV='', but
_sanitize_csv_path treats empty as "use default", so every run resolves to the
missing file. Both rate loaders catch the resulting FileNotFoundError into a
logging.error(...) + empty dict - and because LoggingIntegration(event_level=
logging.ERROR) is configured, each of those errors fires a Sentry event on
EVERY run. Research confirmed the billing blast radius is ZERO (RATE_CUTOFF_DATE
is pinned empty; the only unconditional consumer revert_subcontractor_price is
never called). The real defect is operational noise: a benign missing-optional-
file condition is reported to Sentry as a recurring ERROR.

Fix: make a missing rate CSV a clean, explicit, NON-fatal skip (INFO + benign
breadcrumb, return {}) BEFORE the except path - so it stops producing Sentry
events - while keeping the except for genuinely malformed files (now
fingerprinted). Then correct the Sentry cron monitor_config (currently STALE:
wrong schedule, wrong timezone, wrong max_runtime) and add PII-safe run-mode
tags.

Purpose: Kill recurring false-positive Sentry ERRORs; make the cron monitor and
issue triage actually reflect the production run shape.
Output: Surgical edits to generate_weekly_pdfs.py, new TDD tests, a dated
Living Ledger entry.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/quick/260603-mmc-fix-missing-old-rates-csv-default-fileno/260603-mmc-RESEARCH.md
@CLAUDE.md
@.claude/rules/smartsheet-python-optimization.md
@.claude/rules/documentation-maintenance.md

<scope_note>
The research's "adopt-now set" was #1/#2/#3/#4. Codebase verification (2026-06-03)
refined this:
- #1 (fingerprint) - folded into Task 1's except upgrade.
- #2 (final run-summary set_context) - ALREADY PRESENT at
  generate_weekly_pdfs.py:10126-10135 as set_context("session_summary", {...counts only...}),
  plus a _run_summary JSON dict (:10070-10091) and a tag block (:10116-10124).
  DO NOT re-add it. Task 2 verifies it exists; no new run-summary context.
- #3 (cron monitor_config) - ALREADY PRESENT but STALE at :7890-7897:
  "30 17 * * 1", America/Phoenix, max_runtime 120. This is a genuine bug -
  Task 2 CORRECTS it to the real production schedule.
- #4 (run-mode tags) - net-new; Task 2 adds them.
- #5 (attachments), #6 (span set_data), #7 (structured logger / floor bump) -
  OUT of scope. Do NOT bump the sentry-sdk>=2.35.0 floor.
</scope_note>

<interfaces>
<!-- Verified signatures the executor will use directly - no codebase exploration needed. -->

generate_weekly_pdfs.py - existing helpers (all no-op when SENTRY_DSN unset, safe in tests):

def sentry_add_breadcrumb(category, message, level="info", data=None)   # :972

def sentry_capture_with_context(exception, context_name=None, context_data=None,
                                tags=None, fingerprint=None)   # :982 - sets scope.fingerprint, set_context, set_tag, capture_exception

def _redact_exception_message(exc, *, max_len=240) -> str   # :937

Module-level run-mode vars (accessible from main()/helpers):
RES_GROUPING_MODE = os.getenv('RES_GROUPING_MODE', 'both').lower()                       # :140
WR_FILTER = [w.strip() for w in os.getenv('WR_FILTER','').split(',') if w.strip()]       # :190  (a LIST - never put raw into a tag)
FORCE_GENERATION = os.getenv('FORCE_GENERATION','0').lower() in ('1','true','yes')       # :346

Target loaders (current bodies):
def load_contract_rates(filepath):            # :1432 - rates = {}; try: open(filepath)...; except Exception: logging.error(...); return rates
def build_cu_to_group_mapping(old_csv_path):  # :1493 - mapping = {}; try: open(old_csv_path)...; except Exception: logging.error(...); return mapping

Cron monitor (STALE config to correct):
_sentry_cron_checkin_start(monitor_slug)      # :7878 - capture_checkin(..., monitor_config={...STALE...}) at :7887-7898

Existing run-mode tag block (where #4 tags go, alongside it):
sentry_sdk.set_tag("component"/"process"/"test_mode"/"github_actions", ...)   # :1391-1394

REAL production cron (from .github/workflows/weekly-excel-generation.yml, VERIFIED 2026-06-03):
  weekday: '0 13,15,17,19,21,23,1 * * 1-5'   (primary - use this for schedule.value)
  TZ: America/Chicago        timeout-minutes: 180        TIME_BUDGET_MINUTES: 165

Existing missing-file tests (already pass; must keep passing):
tests/test_subcontractor_pricing.py:43  TestLoadContractRates.test_missing_file_returns_empty
tests/test_subcontractor_pricing.py:759 TestBuildCuToGroupMapping.test_missing_file_returns_empty
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: TDD - make missing rate CSV a benign skip (not a Sentry ERROR)</name>
  <files>tests/test_subcontractor_pricing.py, generate_weekly_pdfs.py</files>
  <behavior>
    RED first - add two tests, one per loader, asserting the missing-file path
    is benign (no ERROR log) while still returning the empty contract:

    - In class TestLoadContractRates (tests/test_subcontractor_pricing.py near :43):
        def test_missing_file_is_benign_not_error(self):
            with self.assertNoLogs(level="ERROR"):
                rates = generate_weekly_pdfs.load_contract_rates("/nonexistent/path.csv")
            self.assertEqual(rates, {})
    - In class TestBuildCuToGroupMapping (near :759):
        def test_missing_file_is_benign_not_error(self):
            with self.assertNoLogs(level="ERROR"):
                mapping = generate_weekly_pdfs.build_cu_to_group_mapping("/nonexistent/old.csv")
            self.assertEqual(mapping, {})

    These MUST fail before the implementation (current code logs an ERROR via
    the except branch). The existing :43 and :759 test_missing_file_returns_empty
    tests MUST keep passing (empty-dict contract preserved).
    assertNoLogs requires Python 3.10+ (project floor is 3.10; CI is 3.12).
  </behavior>
  <action>
    STEP 1 (RED): Add the two tests above. Run them; confirm both FAIL because
    the current loaders take the except Exception -> logging.error path on a
    missing file.

    STEP 2 (GREEN): Add an existence guard at the TOP of each loader body,
    BEFORE the try:/open(), so a missing path returns the empty contract WITHOUT
    entering the except. This implements RESEARCH section 2 / improvement #1.

    In load_contract_rates (generate_weekly_pdfs.py:1432), immediately after
    rates = {} / the REQUIRED_HEADERS line and BEFORE try::
        if not os.path.isfile(filepath):
            # Optional/retired rate CSV absent (e.g. pinned-empty OLD_RATES_CSV
            # resolving to its uncommitted default 'CU List - Corpus North & South.csv').
            # Benign - skip cleanly. INFO (not error) so LoggingIntegration
            # (event_level=ERROR) does NOT fire a Sentry event every run.
            logging.info(f"Rate CSV not present, skipping load: {filepath}")
            sentry_add_breadcrumb(
                "rate_loading", "rate CSV absent - skipped",
                level="info", data={"path_present": False},
            )
            return rates

    In build_cu_to_group_mapping (generate_weekly_pdfs.py:1493), immediately
    after mapping = {} and BEFORE try:, the symmetric guard using old_csv_path
    and returning mapping. Use the same INFO string prefix
    "Rate CSV not present, skipping load:" so the verifier and tests match.

    STEP 3 (fingerprint the genuine failure - improvement #1): In BOTH loaders'
    existing except Exception as e: blocks, KEEP the logging.error(...) line
    (a present-but-malformed file is still a real error worth a Sentry event),
    and ADD a fingerprinted capture AFTER it so genuine failures group stably:
        sentry_capture_with_context(
            e,
            context_name="rate_loading",
            context_data={
                "file_present": True,
                "error": _redact_exception_message(e),   # NEVER raw str(e)
            },
            tags={"phase": "rate_load"},
            fingerprint=["rate-csv-load-failure", "load_contract_rates"],  # fn name per loader
        )
    Use "build_cu_to_group_mapping" as the fingerprint fn-name in the second
    loader. Pass ONLY _redact_exception_message(e) into context_data - never
    str(e) (PII guardrail: context_data BYPASSES before_send_log).

    DO NOT touch _sanitize_csv_path, the :408 OLD_RATES_CSV default string, the
    workflow's pinned-empty rate vars, or the empty-dict return contract. The
    guard belongs in the LOADERS only (per RESEARCH section 5 "What NOT to touch").
    import os is already present at module top - do not re-import.

    STEP 4 (GREEN confirm): Re-run the two new tests; both PASS. Re-run the full
    TestLoadContractRates and TestBuildCuToGroupMapping classes; all pass.
  </action>
  <verify>
    <automated>cd "C:/Users/juflores/dev/Generate-Weekly-PDFs-DSR-Resiliency" && python -m pytest "tests/test_subcontractor_pricing.py" -v -k "missing_file or benign" && python -m py_compile generate_weekly_pdfs.py</automated>
  </verify>
  <done>Both new assertNoLogs(level="ERROR") tests pass; existing :43/:759 tests still pass; both loaders return {} on a missing file via the new INFO/breadcrumb branch (no ERROR log, no Sentry event); malformed-but-present files still hit the fingerprinted except. py_compile clean.</done>
</task>

<task type="auto">
  <name>Task 2: Correct stale cron monitor_config + add PII-safe run-mode tags</name>
  <files>generate_weekly_pdfs.py</files>
  <action>
    PART A - Correct the STALE Sentry cron monitor_config (improvement #3).
    In _sentry_cron_checkin_start (generate_weekly_pdfs.py:7890-7897) the
    monitor_config currently describes a non-existent schedule
    ("30 17 * * 1", America/Phoenix, max_runtime 120). Replace those values
    with the REAL production schedule (verified from
    .github/workflows/weekly-excel-generation.yml on 2026-06-03):
        monitor_config={
            "schedule": {"type": "crontab", "value": "0 13,15,17,19,21,23,1 * * 1-5"},
            "timezone": "America/Chicago",
            "checkin_margin": 5,
            "max_runtime": 180,          # align with workflow timeout-minutes: 180
            "failure_issue_threshold": 1,
            "recovery_threshold": 1,
        }
    Keep the surrounding if not SENTRY_DSN: return None guard, the
    capture_checkin(monitor_slug=..., status=MonitorStatus.IN_PROGRESS, ...) call
    shape, and the except/log-and-return-None behavior verbatim. This is a
    metadata-only correction - schedule data, NO PII.

    Use the weekday schedule (most frequent / matches CLAUDE.md) as the single
    representative crontab. Do NOT attempt to encode all three crons; Sentry
    monitor_config takes one schedule.

    PART B - Add PII-safe run-mode tags (improvement #4). Alongside the existing
    run-mode tag block at generate_weekly_pdfs.py:1391-1394 (right after the
    github_actions set_tag), add:
        sentry_sdk.set_tag("res_grouping_mode", RES_GROUPING_MODE)
        sentry_sdk.set_tag("wr_filter_active", str(bool(WR_FILTER)))   # BOOL, never the WR list
        sentry_sdk.set_tag("force_generation", str(FORCE_GENERATION))
    CRITICAL PII guardrail: wr_filter_active MUST be str(bool(WR_FILTER)) (a
    "True"/"False" string), NEVER the WR_FILTER list itself - WR numbers are
    row-PII and set_tag BYPASSES before_send_log. RES_GROUPING_MODE is a fixed
    enum {primary,helper,both} (safe); FORCE_GENERATION is a bool (safe).

    PART C - Verify-only (improvement #2, do NOT re-implement): Confirm the final
    run-summary already exists as set_context("session_summary", {...}) at
    generate_weekly_pdfs.py:10126-10135 (counts/booleans only). Do not add a
    second run-summary context or capture_message. If (and only if) it is somehow
    absent, STOP and report - do not invent a new one.

    DO NOT bump sentry-sdk in requirements.txt (stays >=2.35.0). DO NOT add
    set_measurement, add_attachment, span set_data, or the structured logger.
    DO NOT change SENTRY_ENABLE_LOGS. Additive/surgical only.
  </action>
  <verify>
    <automated>cd "C:/Users/juflores/dev/Generate-Weekly-PDFs-DSR-Resiliency" && python -m py_compile generate_weekly_pdfs.py && python ".planning/quick/260603-mmc-fix-missing-old-rates-csv-default-fileno/verify_sentry_mods.py"</automated>
  </verify>
  <done>monitor_config now uses the real weekday crontab + America/Chicago + max_runtime 180; America/Phoenix and "30 17 * * 1" are gone; res_grouping_mode / wr_filter_active(BOOL) / force_generation tags present near :1391; existing session_summary set_context untouched (count == 1); no set_measurement and no sentry-sdk floor bump; verify_sentry_mods.py exits 0.</done>
</task>

<task type="auto">
  <name>Task 3: Append dated Living Ledger entry (self-documenting memory)</name>
  <files>memory-bank/living-ledger.md</files>
  <action>
    Per CLAUDE.md "Autonomous Cloud Memory Injection" and
    .claude/rules/documentation-maintenance.md, this change introduces new
    operational behavior (rate CSVs are now treated as optional / benign-when-
    absent; Sentry cron monitor_config corrected; new PII-safe run-mode tags).
    APPEND a single dated entry to the BOTTOM of memory-bank/living-ledger.md
    (NOT CLAUDE.md, which must stay lean). Read the last few existing ledger
    entries first to match their bullet/heading style. Use the real wall-clock
    timestamp at execution time in [YYYY-MM-DD HH:MM] form.

    The entry MUST synthesize what / why / how, covering:
      - Rate CSVs are now OPTIONAL, not error-on-absent: load_contract_rates and
        build_cu_to_group_mapping gained an os.path.isfile() guard that logs INFO
        + a benign Sentry breadcrumb and returns the empty dict when the resolved
        path is absent, BEFORE the except.
      - Root cause: the uncommitted OLD_RATES_CSV default
        ('CU List - Corpus North & South.csv') resolved on every run (workflow
        pins OLD_RATES_CSV: '', but _sanitize_csv_path treats empty as "use
        default"), and the except -> logging.error path fired a Sentry event each
        run via LoggingIntegration(event_level=ERROR). Billing blast radius
        confirmed ZERO (RATE_CUTOFF_DATE pinned empty; revert_subcontractor_price
        never called).
      - The except is preserved for genuinely malformed-but-present files, now
        fingerprinted ['rate-csv-load-failure', <fn>] with
        _redact_exception_message().
      - Corrected the STALE Sentry cron monitor_config
        (was "30 17 * * 1" / America/Phoenix / max_runtime 120 -> now
        "0 13,15,17,19,21,23,1 * * 1-5" / America/Chicago / max_runtime 180).
      - Added PII-safe run-mode tags: res_grouping_mode, wr_filter_active (a BOOL,
        never the WR list), force_generation.
      - Guardrails preserved: did NOT change the :408 default string, the
        workflow's pinned-empty rate vars (one-line revert path intact), the
        empty-dict contract, _sanitize_csv_path, the sentry-sdk>=2.35.0 floor, or
        SENTRY_ENABLE_LOGS (stays OFF).

    The entry text must literally contain the phrase "rate CSV" and either
    "os.path.isfile" or "optional" so the verifier matches. Do NOT inline this
    into CLAUDE.md. A separate CLAUDE.md env/Sentry note or runbook changelog is
    NOT required for this quick task (the change is internal log-routing, not a
    new operator command or env var) - keep CLAUDE.md lean per its own directive.
  </action>
  <verify>
    <automated>cd "C:/Users/juflores/dev/Generate-Weekly-PDFs-DSR-Resiliency" && python ".planning/quick/260603-mmc-fix-missing-old-rates-csv-default-fileno/verify_sentry_mods.py" --with-ledger</automated>
  </verify>
  <done>memory-bank/living-ledger.md has a new bottom entry with a [YYYY-MM-DD HH:MM] timestamp that documents the optional-rate-CSV skip, the root cause, the fingerprinted except, the cron monitor_config correction, and the new run-mode tags; CLAUDE.md is unchanged. verify_sentry_mods.py --with-ledger exits 0.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| filesystem -> loaders | OLD_RATES_CSV / NEW_RATES_CSV paths come from env via _sanitize_csv_path; loaders open whatever path resolves |
| pipeline -> Sentry | tags, contexts, breadcrumbs, and cron monitor_config leave the trust boundary and reach Sentry servers; set_tag/set_context BYPASS before_send_log |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-mmc-01 | Information Disclosure | New run-mode Sentry tags (wr_filter_active) | mitigate | wr_filter_active is emitted as str(bool(WR_FILTER)) - a True/False BOOL, never the WR list. res_grouping_mode is a fixed enum; force_generation is a bool. verify_sentry_mods.py asserts the exact str(bool(WR_FILTER)) form is present. |
| T-mmc-02 | Information Disclosure | Fingerprinted rate-load except context_data | mitigate | Exception text routed through _redact_exception_message(e) (:937) before entering context_data; raw str(e) is never placed in a context. |
| T-mmc-03 | Information Disclosure | Benign-skip INFO log / breadcrumb | accept | The logged value is a static config filename, not row data; INFO level keeps it out of the Sentry event stream (LoggingIntegration event_level=ERROR). breadcrumb data is path_present:False only. |
| T-mmc-04 | Tampering | OLD_RATES_CSV path resolution | accept | Out of scope and unchanged: _sanitize_csv_path is the existing CodeQL-tracked sanitizer and is deliberately NOT modified; the guard only adds an isfile() check in the loaders. |
| T-mmc-05 | Denial of Service | Sentry event volume from recurring ERROR | mitigate | The primary fix: converting the per-run rate-CSV ERROR into a benign INFO/breadcrumb removes a recurring false-positive Sentry event on every cron run. |
</threat_model>

<verification>
Phase-level checks (run from repo root, the CLAUDE.md authoritative commands):

1. Full suite green (pre-push gate): pytest tests/ -v
2. Targeted rate-loader tests: pytest tests/test_subcontractor_pricing.py -v
3. Syntax: python -m py_compile generate_weekly_pdfs.py
4. Static Sentry + benign-skip + ledger assertions:
   python ".planning/quick/260603-mmc-fix-missing-old-rates-csv-default-fileno/verify_sentry_mods.py" --with-ledger

PII spot-check (manual): confirm no new code puts WR_FILTER (the list),
foreman/dept/job names, customer names, or dollar amounts into set_tag /
set_context / add_breadcrumb / add_attachment. Only counts, booleans, fixed
enums, static filenames, and _redact_exception_message output may cross the
Sentry boundary.
</verification>

<success_criteria>
- A missing rate CSV produces an INFO log + benign breadcrumb and returns the
  empty dict - NO logging.error, NO Sentry event - for BOTH load_contract_rates
  and build_cu_to_group_mapping.
- Existing tests/test_subcontractor_pricing.py:43 and :759 still pass; two new
  assertNoLogs(level="ERROR") tests pass.
- A present-but-malformed rate CSV still raises a Sentry ERROR, fingerprinted
  ['rate-csv-load-failure', <fn>], with only _redact_exception_message(e) in
  context_data.
- Sentry cron monitor_config reflects the real production schedule
  ("0 13,15,17,19,21,23,1 * * 1-5", America/Chicago, max_runtime 180); the stale
  America/Phoenix / "30 17 * * 1" / 120 values are gone.
- res_grouping_mode, wr_filter_active (BOOL), force_generation tags are present;
  no raw WR list anywhere.
- The pre-existing session_summary set_context is untouched (improvement #2 was
  already implemented; not duplicated).
- requirements.txt sentry-sdk floor unchanged (>=2.35.0); SENTRY_ENABLE_LOGS
  default unchanged (OFF); _sanitize_csv_path, :408 default string, and workflow
  rate-var pins untouched (one-line revert path preserved).
- A dated [YYYY-MM-DD HH:MM] Living Ledger entry documents the change; CLAUDE.md
  is not modified.
- pytest tests/ -v and python -m py_compile generate_weekly_pdfs.py both pass.
</success_criteria>

<output>
After completion, create .planning/quick/260603-mmc-fix-missing-old-rates-csv-default-fileno/260603-mmc-SUMMARY.md
</output>
