---
phase: 08-smartsheet-python-sdk-4-0-0-compatibility-migration
reviewed: 2026-07-22T16:05:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - generate_weekly_pdfs.py
  - memory-bank/living-ledger.md
  - requirements.txt
  - tests/golden/baseline_names.json
  - tests/test_entrypoint_no_double_import.py
findings:
  critical: 0
  warning: 1
  info: 3
  total: 4
status: issues_found
---

# Phase 08: Code Review Report

**Reviewed:** 2026-07-22T16:05:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the Phase 08 SDK 4.3.0 migration diff (`c48955f..HEAD`): the 27-line
3.x re-export shim deletion in `generate_weekly_pdfs.py`, the exact pin
`smartsheet-python-sdk==4.3.0` in `requirements.txt`, the `_exc_name` removal
from `tests/golden/baseline_names.json`, the env-sanitation change in
`tests/test_entrypoint_no_double_import.py`, and the appended Living Ledger
entries.

**Core migration is sound — verified empirically this session:**

- Installed SDK is 4.3.0; `smartsheet.exceptions` exists on 4.3.0 and exposes
  all 8 exception classes `pipeline/retry.py` depends on (`RateLimitExceededError`,
  `UnexpectedErrorShouldRetryError`, `InternalServerError`,
  `ServerTimeoutExceededError`, `SystemMaintenanceError`,
  `UnexpectedRequestError`, `HttpError`, `ApiError`) — the deleted shim is
  genuinely dead on 4.x, and the retained `import smartsheet.exceptions as
  ss_exc` does not crash.
- No active code uses APIs removed in 4.0 (`Folders.get_folder(`,
  `list_folders`, `.Templates`) — only `archive/` backup references remain.
- `scripts/check_api_equality.py` (Gate 1): `PASS: all 177 baseline names
  present`; `baseline_names.json` has exactly 177 entries, no duplicates,
  `_exc_name` absent. The removal was mandatory, not optional — Gate 1 fails
  on `missing = baseline - combined`, so a stale `_exc_name` entry would have
  broken the gate (the shim's `_exc_name = None` assignment was the only AST
  top-level source of that name).
- `python -m py_compile generate_weekly_pdfs.py` clean.
- `tests/test_smartsheet_retry.py`: 17 passed on 4.3.0.
- Empty-string env var propagation to a subprocess verified working on
  Windows (`'ZZ_EMPTY_TEST' in os.environ` → present, `''`), and
  `pipeline/orchestrate.py:438-442` uses a falsy check (`if not API_TOKEN`)
  with an explicit `return` after the synthetic branch — the test's
  empty-string strategy is logically correct. `load_dotenv()` is called with
  defaults (`override=False`) at `generate_weekly_pdfs.py:24`, so the comment's
  "load_dotenv never overrides an existing var" claim holds.
- Living Ledger cross-references verified: commits `b2e76bf` (touches exactly
  `generate_weekly_pdfs.py` −27 / `baseline_names.json` −1) and `76e2471`
  (touches exactly `requirements.txt`) exist and match their claims; the
  178→177 and "facade completeness 108 names" figures match the actual files
  (`facade_allowlist.json` = 108 entries); `scripts/run_6_gates.sh` and the
  referenced `deferred-items.md` exist. The D-05 probe entry honestly records
  the pre-existing `SKIP_UPLOAD` delete-before-skip defect instead of burying
  it. Note: the diff range contains **two** appended ledger entries
  ([2026-07-22 02:31] and [2026-07-22 10:20]); the third entry the phase
  references ([2026-07-21 18:20]) predates the diff base.

**One real defect found:** the changed entrypoint test fails on vanilla
Windows — reproduced this session — because the parent decodes the child's
forced-UTF-8 output with cp1252. See WR-01.

## Warnings

### WR-01: Entrypoint test crashes with masked `TypeError` on vanilla Windows — hermeticity fix is incomplete

**File:** `tests/test_entrypoint_no_double_import.py:35-40`
**Issue:** The phase's stated goal for this file was hermeticity (commit
`4aa19ff` "make entrypoint banner test hermetic against developer .env"), and
the token side is fixed — but the test is still environment-sensitive on the
exact platform its own comment calls out ("emoji banners on Windows cp1252").
The test forces the **child** to UTF-8 (`PYTHONUTF8=1`,
`PYTHONIOENCODING=utf-8`) but the **parent's** `subprocess.run(...,
capture_output=True, text=True)` decodes the pipes with the parent's locale
codec (cp1252 on vanilla Windows). The child's emoji banner bytes (e.g.
`0x8f`) are undecodable in cp1252, both `_readerthread`s die with
`UnicodeDecodeError`, `result.stdout`/`result.stderr` come back `None`, and
line 40 raises:

```
TypeError: unsupported operand type(s) for +: 'NoneType' and 'NoneType'
```

— which masks the real cause AND the test's own diagnostic tail-of-output
message. Reproduced this session: `python -m pytest
tests/test_entrypoint_no_double_import.py` → **FAILED** (plain Windows shell);
`PYTHONUTF8=1 python -m pytest ...` → passed in 1.19s. Consequences: (a) the
ledger's "1164 passed, 0 failed" verification evidence only reproduces in
UTF-8 parent environments (Linux CI, or shells with `PYTHONUTF8` set) — a
vanilla Windows developer gets a confusing failure; (b) the
`.github/hooks/pre-push-tests.json` Claude Code hook will deny `git push` in
such sessions on a test that has nothing wrong with the code under test.
**Fix:** Pin the parent-side decode explicitly:

```python
result = subprocess.run(
    [sys.executable, 'generate_weekly_pdfs.py'],
    cwd=repo_root, env=env,
    capture_output=True, text=True,
    encoding='utf-8', errors='replace',
    timeout=180,
)
```

(`errors='replace'` additionally guarantees the reader threads can never die
mid-stream, so the assertion's diagnostic message always prints.)

## Info

### IN-01: `import smartsheet` / `import smartsheet.exceptions as ss_exc` are now unused in the facade

**File:** `generate_weekly_pdfs.py:17-18`
**Issue:** The deleted shim was the only in-file consumer of `ss_exc` (and of
`smartsheet.smartsheet`). After the deletion, neither `smartsheet` nor
`ss_exc` is referenced anywhere else in the facade (line 87's
`logging.getLogger('smartsheet.smartsheet')` is a string literal), no test or
pipeline module accesses `generate_weekly_pdfs.smartsheet` /
`generate_weekly_pdfs.ss_exc`, and neither name appears in
`tests/golden/facade_allowlist.json` (Gate 2) or `baseline_names.json`
(Gate 1 ignores imports). Retention was a deliberate, documented D-04 plan
decision ("line-18 ss_exc import stays"), so this is informational — but the
imports now read as load-bearing when they are not, and any F401-style linter
(e.g. the aspirational `ruff check .`) will flag them.
**Fix:** In a future cleanup, either remove both imports or annotate the
retention: `import smartsheet.exceptions as ss_exc  # noqa: F401 — kept per
D-04; retry contract lives in pipeline/retry.py`.

### IN-02: Exact-pin rationale contradicted by unbounded `sentry-sdk>=2.54.0` one line above

**File:** `requirements.txt:2` (vs. the new comment at lines 5-9)
**Issue:** The new pin comment states the rule as "an unreviewed SDK release
can never auto-enter production" — but `sentry-sdk>=2.54.0` directly above
has no upper bound at all. `sentry_sdk.init` wraps engine startup, so a
future breaking sentry-sdk major would auto-install on the next CI run and
could crash the production pipeline at import — the exact failure mode the
260608-gwm hotfix (smartsheet 4.0.0) was recovering from. Out of this
phase's change scope, but the phase's own comment now documents a policy the
adjacent line violates.
**Fix:** Follow-up: apply at least an upper bound (`sentry-sdk>=2.54.0,<3`)
under the same 260608-gwm "upper-bound transport-critical deps" ledger rule.

### IN-03: `.github/instructions/copilot-setup.instructions.md` still documents the old `>=3.1.0` pin

**File:** `.github/instructions/copilot-setup.instructions.md:219`
**Issue:** The line `requirements.txt - Dependencies (sentry-sdk>=2.35.0,
smartsheet-python-sdk>=3.1.0, etc.)` now contradicts the shipped
`smartsheet-python-sdk==4.3.0` (and the sentry-sdk floor is also stale —
actual is `>=2.54.0`). CLAUDE.md requires keeping the `.github` Copilot docs
in sync with reality; an agent reading this doc would conclude 3.x is still
acceptable.
**Fix:** Update the line to `smartsheet-python-sdk==4.3.0` and
`sentry-sdk>=2.54.0` (or drop the version specifics and point at
`requirements.txt` as the single source of truth).

---

_Reviewed: 2026-07-22T16:05:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
