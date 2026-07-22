---
phase: quick-260722-nst
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/test_skip_upload_delete_gating.py
  - pipeline/orchestrate.py
autonomous: true
requirements: [PR286-REVIEW]

must_haves:
  truths:
    - "With SKIP_UPLOAD=true, the isolated REMEDIATE_CLAIMERS sweep never calls delete_attachment against production, even when REMEDIATION_DRY_RUN=0."
    - "run_claimer_remediation receives an effective dry_run of True whenever SKIP_UPLOAD is set."
    - "The REMEDIATE_CLAIMERS log line reports the effective dry_run (post-SKIP_UPLOAD), not the raw REMEDIATION_DRY_RUN flag."
    - "Existing 5 pinned SKIP_UPLOAD-gated cleanup call sites remain unchanged; this adds the 6th mutating call site."
  artifacts:
    - path: "pipeline/orchestrate.py"
      provides: "SKIP_UPLOAD-gated dry_run at the run_claimer_remediation call site"
      contains: "REMEDIATION_DRY_RUN or SKIP_UPLOAD"
    - path: "tests/test_skip_upload_delete_gating.py"
      provides: "Source-pin test for the 6th (claimer-remediation) mutating call site"
      contains: "or SKIP_UPLOAD"
  key_links:
    - from: "pipeline/orchestrate.py REMEDIATE_CLAIMERS branch"
      to: "pipeline.attribution.run_claimer_remediation"
      via: "dry_run=REMEDIATION_DRY_RUN or SKIP_UPLOAD"
      pattern: "dry_run=REMEDIATION_DRY_RUN or SKIP_UPLOAD"
---

<objective>
Extend the SKIP_UPLOAD "zero Smartsheet mutations" invariant (Living Ledger
[2026-07-22 14:37]) to the isolated claimer-remediation call site flagged in PR #286
review.

Confirmed defect: `pipeline/orchestrate.py:457-462` calls
`run_claimer_remediation(client, dry_run=REMEDIATION_DRY_RUN, ...)`. When
`SKIP_UPLOAD=true`, `REMEDIATE_CLAIMERS=1`, and `REMEDIATION_DRY_RUN=0`, the sweep can
call `delete_attachment` against production — violating the invariant. Both
`SKIP_UPLOAD` (config.py:48) and `REMEDIATION_DRY_RUN` (config.py:421-423) are already
bools, so the fix is a boolean OR at the call site plus an honest log line.

Purpose: Close the last unguarded mutating call site so SKIP_UPLOAD is a hard,
uniform read-only switch. This is the 6th mutating call site; the other 5 are already
pinned in tests/test_skip_upload_delete_gating.py.
Output: One-line surgical fix + adjacent log-line correction + a source-pin test.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md

<interfaces>
From pipeline/attribution.py — the function being gated (DO NOT modify it):
```python
def run_claimer_remediation(
    client,
    dry_run: bool,
    window_weeks: int,
    valid_wr_weeks: 'set | None' = None,
) -> None:
    # dry_run=True => report counts only, no attachment deleted.
```

From pipeline/config.py (both already bools — a boolean OR is valid):
```python
SKIP_UPLOAD = os.getenv('SKIP_UPLOAD', 'false').lower() == 'true'          # line 48
REMEDIATION_DRY_RUN = os.getenv('REMEDIATION_DRY_RUN', '1').strip().lower() \
    in ('1', 'true', 'yes', 'on')                                          # line 421-423
```

Current defect site — pipeline/orchestrate.py:451-463 (SKIP_UPLOAD is already imported at line 112):
```python
if REMEDIATE_CLAIMERS:
    logging.info(
        f"🧹 REMEDIATE_CLAIMERS=True — running isolated claimer "
        f"remediation sweep (dry_run={REMEDIATION_DRY_RUN}, "
        f"window_weeks={REMEDIATION_WINDOW_WEEKS})"
    )
    run_claimer_remediation(
        client,
        dry_run=REMEDIATION_DRY_RUN,
        window_weeks=REMEDIATION_WINDOW_WEEKS,
        valid_wr_weeks=None,  # isolated path: no live-identity set
    )
    return
```

Existing pinning convention (tests/test_skip_upload_delete_gating.py) uses
`inspect.getsource(orch)` + substring assertions. `test_orchestrate_gates_untracked_cleanup_and_purge`
asserts `src.count("dry_run=SKIP_UPLOAD") >= 5`. NOTE: the new call uses
`dry_run=REMEDIATION_DRY_RUN or SKIP_UPLOAD`, which does NOT contain the exact
substring `dry_run=SKIP_UPLOAD` — so that `>= 5` count stays valid and must NOT be
bumped. The 6th site gets its own dedicated pin asserting `or SKIP_UPLOAD` inside the
REMEDIATE_CLAIMERS branch.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add failing source-pin test for the 6th (claimer-remediation) mutating call site</name>
  <files>tests/test_skip_upload_delete_gating.py</files>
  <behavior>
    - New test class TestRemediationGatesOnSkipUpload with one test method.
    - Test: `inspect.getsource(pipeline.orchestrate)`, slice the REMEDIATE_CLAIMERS
      branch (index from `if REMEDIATE_CLAIMERS:` to its `return`), and assert the
      run_claimer_remediation call passes `dry_run=REMEDIATION_DRY_RUN or SKIP_UPLOAD`.
    - Assertion substring: "REMEDIATION_DRY_RUN or SKIP_UPLOAD".
    - Must FAIL against current source (which still reads `dry_run=REMEDIATION_DRY_RUN`).
    - Do NOT change the existing `>= 5` count assertion in
      test_orchestrate_gates_untracked_cleanup_and_purge.
  </behavior>
  <action>Append a new class TestRemediationGatesOnSkipUpload to
tests/test_skip_upload_delete_gating.py mirroring the existing source-inspection
pattern (TestUploadWorkerWiresSkipUpload). Locate the branch with
`src.index("if REMEDIATE_CLAIMERS:")`, take a ~600-char window, and assert it contains
`"REMEDIATION_DRY_RUN or SKIP_UPLOAD"`. Add a short docstring noting this pins the 6th
mutating call site (isolated claimer-remediation sweep) to the SKIP_UPLOAD invariant.
Run to confirm RED before implementing Task 2. Follow this file's documented
signature/version-pin convention if the harness references a call-site hash (bump to
v6 only if an explicit hash constant in this file requires it — otherwise no bump).</action>
  <verify>
    <automated>python -m pytest tests/test_skip_upload_delete_gating.py::TestRemediationGatesOnSkipUpload -v 2>&1 | grep -Ev '^#' | grep -q "1 failed" && echo RED_CONFIRMED</automated>
  </verify>
  <done>New test exists and FAILS against unmodified orchestrate.py (RED state confirmed); existing 5-site count assertion untouched.</done>
</task>

<task type="auto">
  <name>Task 2: Gate the remediation call on SKIP_UPLOAD and correct the log line (GREEN)</name>
  <files>pipeline/orchestrate.py</files>
  <action>In the REMEDIATE_CLAIMERS branch (pipeline/orchestrate.py:451-463) make two
surgical edits and nothing else — do NOT modify run_claimer_remediation itself:
1. Change the call argument from `dry_run=REMEDIATION_DRY_RUN` to
   `dry_run=REMEDIATION_DRY_RUN or SKIP_UPLOAD`.
2. Update the adjacent `logging.info(...)` so the reported dry_run reflects the
   effective value. Introduce a local `_effective_dry_run = REMEDIATION_DRY_RUN or
   SKIP_UPLOAD` immediately before the log call, log `dry_run={_effective_dry_run}`,
   and pass `dry_run=_effective_dry_run` to run_claimer_remediation so the logged and
   applied values cannot drift. Keep the existing window_weeks text.
SKIP_UPLOAD is already imported (orchestrate.py:112); no new import needed. Preserve
the isolation semantics (early `return` after the sweep).</action>
  <verify>
    <automated>python -m pytest tests/test_skip_upload_delete_gating.py -v && python -m py_compile generate_weekly_pdfs.py && echo GREEN_OK</automated>
  </verify>
  <done>All tests in test_skip_upload_delete_gating.py pass (including the new 6th-site pin); py_compile clean; SKIP_UPLOAD=true now forces dry_run at the remediation call and the log line reports the effective value.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| pipeline → Smartsheet API | `run_claimer_remediation` can issue `delete_attachment` (irreversible production mutation) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-nst-01 | Tampering | orchestrate.py REMEDIATE_CLAIMERS branch | mitigate | Force `dry_run` True when SKIP_UPLOAD set (`REMEDIATION_DRY_RUN or SKIP_UPLOAD`); pinned by source-inspection test so future edits that drop the gate fail CI |
| T-nst-02 | Repudiation | remediation log line | mitigate | Log the effective dry_run (post-OR) so run history accurately records whether deletes could have fired |
| T-nst-SC | Tampering | npm/pip installs | accept | No new dependencies added; test uses stdlib `inspect`/`unittest.mock` already in the suite |
</threat_model>

<verification>
- `python -m pytest tests/test_skip_upload_delete_gating.py -v` — all pass, 6th call site pinned.
- `python -m py_compile generate_weekly_pdfs.py` — clean.
- Broader safety net: `python -m pytest tests/test_skip_upload_delete_gating.py tests/test_billing_audit_shadow.py -v`.
- Manual reasoning check: with SKIP_UPLOAD=true + REMEDIATION_DRY_RUN=0, effective dry_run is True → zero `delete_attachment` calls; invariant holds.
</verification>

<success_criteria>
- SKIP_UPLOAD=true guarantees the isolated claimer-remediation sweep performs zero Smartsheet mutations regardless of REMEDIATION_DRY_RUN.
- The remediation log line reports the effective dry_run value (no drift between logged and applied).
- Only two files changed; run_claimer_remediation body untouched; existing 5-site pins intact.
- PR #286 review issue resolved.
</success_criteria>

<output>
Create `.planning/quick/260722-nst-gate-claimer-remediation-on-skip-upload-/260722-nst-SUMMARY.md` when done.
</output>
