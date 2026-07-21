# Phase 08: smartsheet-python-sdk 4.x Compatibility Migration - Context

**Gathered:** 2026-07-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Compat-only migration of the production billing engine off the temporary
`smartsheet-python-sdk>=3.1.0,<4.0.0` emergency pin (hotfix 260608-gwm /
PR #273) onto SDK **4.3.0**, with **zero behavior change** to the
Smartsheet → Excel → Smartsheet pipeline. Explicitly NOT a redesign,
optimization, or retry-logic change. Target change surface is deliberately
tiny: `requirements.txt`, removal of one dead facade block, ledger/docs
notes. **No GitHub Actions workflow edits** (locked decision D-03).

</domain>

<decisions>
## Implementation Decisions

### Target version & pin shape (discussed 2026-07-21)
- **D-01:** Pin **exact**: `smartsheet-python-sdk==4.3.0`. Not a range.
  Rationale: the June 2026 crash happened because an unreviewed release
  auto-entered production; exact pin makes that structurally impossible.
  This EXTENDS the Living Ledger 260608-gwm rule (upper-bound
  transport-critical deps) to its strongest form: exact-pin + deliberate
  reviewed bumps.
- **D-02:** 4.3.0 chosen over 4.0.2 because the 4.0.1→4.3.0 changelog was
  reviewed live on 2026-07-21 and every change is additive; only 4.3.0
  grazes in-use models (new `proof` field on `Row`, new template case in
  `PaginatedChildrenResult.append_data`) — additive, low risk. Zero
  changes to `smartsheet.exceptions`, `ApiError`/`error.result` internals,
  or any in-use call signature across 4.0.1–4.3.0.

### CI install posture (discussed 2026-07-21)
- **D-03:** **No workflow-file changes.** The 08-RESEARCH.md `--no-binary`
  prescription is OBSOLETE: the 4.0.0 wheel packaging bug was fixed in
  4.0.1 (upstream issue #144; wheel sizes verified 2026-07-21: 4.0.0 =
  7,842 B broken; 4.0.1–4.3.0 = 259–271 KB healthy). PyPI artifacts are
  immutable, so the exact-pinned 4.3.0 wheel cannot regress. An
  import-smoke CI step was considered and REJECTED as redundant with the
  exact pin (revisit only when a future bump PR shows packaging anomalies).

### Code change scope
- **D-04:** Remove the dead 3.x re-export workaround block in
  `generate_weekly_pdfs.py` (the `import smartsheet.smartsheet as
  _ss_smartsheet_module` block, currently ~lines 30–45; research verdict
  "remove", still valid post-Phase-09). Line 18
  `import smartsheet.exceptions as ss_exc` STAYS. Zero changes to
  `pipeline/retry.py` classification logic or any `except ss_exc.*` path.
  `tests/test_billing_audit_shadow.py:65` imports `smartsheet.smartsheet`
  directly — module still exists in 4.x, no test change expected (SDK-04
  research finding stands).

### Behavior-neutrality proof (discussed 2026-07-21)
- **D-05:** Pre-merge proof = **full `scripts/run_6_gates.sh` on 4.3.0**
  (AST equality, facade completeness, pytest, mypy delta, py_compile,
  golden run_summary) **PLUS a live read-only probe** against real
  Smartsheet on 4.3.0 (real `Sheets.get_sheet`, attachment list, and an
  error-shape sanity check). The live probe exists because
  `tests/test_smartsheet_retry.py` builds `ApiError.error.result` with
  `mock.Mock()` — mocked tests cannot catch real SDK error-shape drift,
  and TEST_MODE synthetic runs never touch the transport at all.

### Rollout & rollback (discussed 2026-07-21)
- **D-06:** Rollout sequence: (1) SKIP_UPLOAD real-data dry-run on the
  branch (reads prod, writes nothing); (2) merge in a weekday daytime
  window immediately after a green scheduled run (do NOT merge in the
  Sunday-night window before the Monday 05:00 UTC weekly deep run);
  (3) fire ONE manual workflow_dispatch canary and watch it green before
  walking away. Canary is a normal idempotent production run.
- **D-07:** Rollback protocol: revert PR (restores the `<4.0.0` pin; pip
  cache auto-busts on the requirements.txt hash), then optionally one
  confirm dispatch. No other rollback machinery needed.

### Research refresh obligations for the planner
- **D-08:** Treat `08-RESEARCH.md` (2026-06-08, self-expired 2026-07-08)
  as authoritative on the 4.0.0 root cause and in-use surface audit, but
  STALE on: (a) `--no-binary` — obsolete per D-03; (b) target version —
  now 4.3.0 per D-01/D-02; (c) all `generate_weekly_pdfs.py` line
  references — pre-Phase-09 monolith numbering; the retry `except` blocks
  it references were consolidated into `pipeline/retry.py` (v1.3.1) and
  extended by PR #284 (`_RETRYABLE_HTTP_STATUS` + `_http_status_code()`
  ApiError introspection); (d) SDK-05 requirement text — pin target is
  `==4.3.0` with NO workflow comment about `--no-binary`.

### Claude's Discretion
- Exact `requirements.txt` comment wording (must record review date +
  exact-pin rationale pointer to the ledger).
- Live-probe implementation shape: throwaway script vs committed
  `scripts/` utility — planner decides; keep it read-only either way.
- Living Ledger entry wording; whether CLAUDE.md's local-dev install note
  needs the (now plain) `pip install` guidance refreshed.
- Whether SDK-06's "identical output" evidence is satisfied by Gate 6 +
  the SKIP_UPLOAD dry-run in D-06 step 1 (recommended) or needs a formal
  A/B compare — planner's call within the D-05/D-06 envelope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase definition & research
- `.planning/ROADMAP.md` § Phase 08 — goal, SDK-01..06 requirements, success criteria
- `.planning/phases/08-smartsheet-python-sdk-4-0-0-compatibility-migration/08-RESEARCH.md` — 4.0.0 surface audit (read WITH the D-08 staleness corrections)

### Code that must survive unchanged
- `pipeline/retry.py` — the transient-retry exception contract (typed `ss_exc.*` set, `_RETRYABLE_API_CODES`, `_RETRYABLE_HTTP_STATUS`, `_api_result_code()`, `_http_status_code()`); depends on `ApiError.error.result` internals
- `tests/test_smartsheet_retry.py` — 17 tests incl. PR #284's 5xx cases; documents the mocked `error.result` shape
- `generate_weekly_pdfs.py` lines 17–18 (SDK imports, keep) and ~30–45 (re-export block, REMOVE per D-04)

### Proof harness
- `scripts/run_6_gates.sh` — the six-gate behavior-neutrality oracle (Gates: AST equality, facade completeness, pytest, mypy delta, py_compile, golden run_summary)

### Files to change
- `requirements.txt` lines 7–8 — pin + comment (only dependency change)
- `memory-bank/living-ledger.md` — 260608-gwm entry to extend; append the new dated migration entry here

### Explicitly out of scope (do not edit)
- `.github/workflows/weekly-excel-generation.yml`, `.github/workflows/system-health-check.yml` — D-03: no install-step changes

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/run_6_gates.sh`: calibrated Phase 09 harness; re-runnable as-is (forces PYTHONUTF8=1 for Windows)
- `pipeline/retry.py::smartsheet_call_with_retry`: centralized retry — the ONLY place ApiError internals are introspected; a live probe exercising it covers the whole pipeline's error-handling dependency
- TEST_MODE (synthetic, no token) and SKIP_UPLOAD (real reads, no writes) run modes for staged validation

### Established Patterns
- Additive/surgical changes only; `pytest tests/ -v` gates push (Claude Code pre-push hook)
- Conventional Commits; PR body needs Objective / Changes Made / Production Safety Check
- Living Ledger append (dated `[YYYY-MM-DD HH:MM]`) in the same PR as the code change

### Integration Points
- SDK import sites post-Phase-09: `generate_weekly_pdfs.py:17-18,34`, `pipeline/retry.py:67`, `pipeline/orchestrate.py:40`; `pipeline/fetch.py` / `pipeline/discovery.py` consume the SDK only via `smartsheet_call_with_retry`
- `tests/test_billing_audit_shadow.py:65` imports `smartsheet.smartsheet` (exists in 4.x — no change)

</code_context>

<specifics>
## Specific Ideas

Verified facts from the 2026-07-21 live re-research (planner need not refetch):
- Release timeline: 4.0.0 (06-08, broken wheel) → 4.0.1 (06-09, packaging fix #144) → 4.0.2 (06-10) → 4.1.0 (06-26) → 4.2.0 (07-09) → 4.3.0 (07-20)
- Wheel sizes (PyPI JSON): 4.0.0 = 7,842 B; 4.0.1 = 259,410 B; 4.0.2 = 259,431 B; 4.1.0 = 266,410 B; 4.2.0 = 268,439 B; 4.3.0 = 270,661 B; none yanked
- 4.0.1→4.3.0 changelog: entirely additive to surfaces this codebase does not use, EXCEPT 4.3.0's additive `Row.proof` field and `PaginatedChildrenResult.append_data` template case (both in-use models, additive only)

</specifics>

<deferred>
## Deferred Ideas

- CI post-install import-smoke verification line — rejected for this phase
  (redundant with exact pin); reconsider as part of any FUTURE SDK bump PR
  checklist if packaging anomalies reappear.

</deferred>

---

*Phase: 08-smartsheet-python-sdk-4-0-0-compatibility-migration*
*Context gathered: 2026-07-21*
