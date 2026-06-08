# Phase 08: smartsheet-python-sdk 4.0.0 Compatibility Migration — Research

**Researched:** 2026-06-08
**Domain:** Python SDK upgrade — exception module layout, wheel packaging, import compatibility
**Confidence:** HIGH (all findings verified by direct 4.0.0 sdist/wheel inspection)

---

## Summary

`smartsheet-python-sdk` 4.0.0 was published 2026-06-08 as a breaking major release. The
emergency hotfix (260608-gwm / PR #273) correctly diagnosed an import crash but slightly
misidentified the root cause: **4.0.0 did NOT remove `smartsheet.exceptions`** — the module
and all exception classes are still present in the 4.0.0 source distribution. The actual
crash was caused by a **packaging bug in the 4.0.0 wheel**: the `.whl` file (7.8 KB) ships
only `version.py`, whereas the correctly-built `.whl` for 3.9.0 was 266 KB containing the
full `smartsheet/` package. When `pip install` upgrades from 3.x to 4.0.0 using the wheel,
it replaces the entire `smartsheet/` package directory with only `version.py`, making all
imports fail.

The sdist (`.tar.gz`, 284 KB) is correctly built and installs all source files. Migrating to
4.0.0 therefore requires: (1) changing the `pip install` step in both GitHub Actions
workflows to `--no-binary smartsheet-python-sdk` so pip falls back to the sdist, and (2)
lifting the `<4.0.0` pin in `requirements.txt`. No Python source code changes are strictly
required to import the SDK, because `smartsheet.exceptions` and all exception classes remain
intact when installed from the sdist.

The `smartsheet.smartsheet` re-export workaround (lines 30–54 of `generate_weekly_pdfs.py`)
that patches in `RateLimitExceededError` etc. was needed in 3.x because `request()` did
`getattr(sys.modules[__name__], ...)` for exception lookup. **In 4.0.0, `request()` was
fixed to use `importlib.import_module(__package__ + ".exceptions")`** — the workaround is
now a no-op and can be cleanly removed when the pin is lifted to 4.0.0.

**Primary recommendation:** Install 4.0.0 from sdist (`--no-binary smartsheet-python-sdk`),
lift the `<4.0.0` pin, and remove the re-export workaround block from
`generate_weekly_pdfs.py`.

---

## Project Constraints (from CLAUDE.md)

- **Additive logic only** — no behavior change to the Smartsheet → Excel → Smartsheet
  billing pipeline. This migration is compat-only.
- **Never break production** — `generate_weekly_pdfs.py` is production-critical; changes
  must be surgical and reversible.
- **Preserve the pipeline** — do not touch grouping, hashing, filename, or attachment logic.
- **PARALLEL_WORKERS ≤ 8**, never use `@cell`, openpyxl stays.
- **PEP 8, type hints, 4-space indent, ≤79 char lines** for any Python edits.
- **Conventional Commits** for commit messages; PR description must include Objective,
  Changes Made, and Production Safety Check sections.
- **`.github/hooks/pre-push-tests.json`** gates `git push` on `pytest tests/ -v` passing.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SDK-01 | Exception classes resolve under 4.0.0 — `import smartsheet.exceptions` and retry `except` blocks work without `ModuleNotFoundError` / `AttributeError` | Confirmed: `smartsheet.exceptions` module and all four classes exist in 4.0.0 sdist; crash was from broken wheel, not code removal |
| SDK-02 | `smartsheet.smartsheet` re-export workaround reconciled — kept, updated, or removed | Research verdict: **remove** — 4.0.0 `request()` uses `importlib.import_module` instead of `getattr(sys.modules[__name__], ...)`, making the workaround a no-op |
| SDK-03 | All in-use SDK call sites verified compatible: `Sheets.get_sheet`, `Attachments.*`, `Folders.get_folder_children` | All three APIs: signatures unchanged in 4.0.0, parameter names identical |
| SDK-04 | Full `pytest tests/` passes against 4.0.0; test mocks/fixtures updated if needed | No mock changes needed — `smartsheet.exceptions` and `smartsheet.smartsheet` modules still exist; `smartsheet.models.sheet`, `.folder` unchanged |
| SDK-05 | `requirements.txt` pin lifted to allow 4.0.0; Living Ledger / CLAUDE.md notes updated | Change: `>=3.1.0,<4.0.0` → `>=4.0.0`; add comment about `--no-binary` requirement |
| SDK-06 | `TEST_MODE=true` / `SKIP_UPLOAD=true` run confirms identical output vs 3.x baseline | No SDK call-site changes means behavior is guaranteed identical |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| SDK exception import resolution | Python billing engine | — | Exception classes are imported at module load time in `generate_weekly_pdfs.py` |
| Retry logic (`except ss_exc.*` blocks) | Python billing engine | — | Per-call retry wrappers own rate-limit / 5xx handling |
| Dependency installation | GitHub Actions CI | Local dev env | `requirements.txt` + workflow `pip install` step govern which SDK version is resolved |
| Wheel vs sdist selection | pip install layer | GitHub Actions config | Workflow `pip install` step controls `--no-binary`; no Python code involvement |

---

## Standard Stack

### In-Use SDK Surface (4.0.0 verified)

| API | Call Form (unchanged) | 4.0.0 Status |
|-----|----------------------|--------------|
| `client.Sheets.get_sheet(sheet_id, include=..., row_numbers=...)` | Positional `sheet_id`, keyword params | UNCHANGED — same signature, same return type `Sheet` |
| `client.Attachments.list_row_attachments(sheet_id, row_id)` | Positional args | UNCHANGED — same signature, returns `IndexResult[Attachment]` |
| `client.Attachments.delete_attachment(sheet_id, attachment_id)` | Positional args | UNCHANGED |
| `client.Attachments.attach_file_to_row(sheet_id, row_id, _file)` | Positional args | UNCHANGED |
| `client.Folders.get_folder_children(folder_id, last_key=..., ...)` | `last_key` param | UNCHANGED — still `last_key=`, same `PaginatedChildrenResult` return |
| `client.errors_as_exceptions(True)` | Called after construction | UNCHANGED — method still exists, same behavior |
| `import smartsheet.exceptions as ss_exc` | Module import | UNCHANGED in sdist — module and all classes present |

### Removed in 4.0.0 (NOT used by this codebase — no action)

| Removed | Status in This Codebase |
|---------|------------------------|
| `Folders.get_folder` | Not used — codebase uses `get_folder_children` with `last_key` |
| `Folders.list_folders` | Not used |
| `Templates` class | Not used |
| `list_workspaces` / `list_sights` / `list_webhooks` offset pagination | Not used |
| `share_sheet` / `share_report` etc. on Sheets/Reports/Sights/Workspaces | Not used |

---

## Architecture Patterns

### The Root Cause Explained

```
pip install smartsheet-python-sdk==4.0.0  (default: uses .whl)
    ↓
WHL contains: smartsheet/version.py only (7.8 KB vs expected 266 KB)
    ↓
pip REPLACES existing smartsheet/ dir with version.py-only contents
    ↓
import smartsheet.exceptions → ModuleNotFoundError (file gone)
```

```
pip install --no-binary smartsheet-python-sdk smartsheet-python-sdk==4.0.0
    ↓
Pip falls back to sdist (284 KB tar.gz — all source files)
    ↓
Installs full smartsheet/ package including exceptions.py
    ↓
import smartsheet.exceptions → SUCCESS
```

### The Exception Lookup Difference (3.x vs 4.0.0)

```python
# 3.x (smartsheet/smartsheet.py ~L303):
the_ex = getattr(sys.modules[__name__], native.result.name)
# __name__ = 'smartsheet.smartsheet'
# smartsheet.smartsheet does NOT have RateLimitExceededError etc.
# → AttributeError unless re-export workaround patches them in

# 4.0.0 (smartsheet/smartsheet.py L301-304):
exceptions_module = importlib.import_module(__package__ + ".exceptions")
the_ex = getattr(exceptions_module, native.result.name)
# Loads smartsheet.exceptions directly → ALWAYS works, no workaround needed
```

### The Re-Export Workaround (lines 30–54) — Removal Plan

```python
# CURRENT (lines 30-54 in generate_weekly_pdfs.py):
import smartsheet.smartsheet as _ss_smartsheet_module
for _exc_name in (
    'RateLimitExceededError',
    'UnexpectedErrorShouldRetryError',
    'InternalServerError',
    'ServerTimeoutExceededError',
    'SystemMaintenanceError',
):
    if not hasattr(_ss_smartsheet_module, _exc_name) and hasattr(ss_exc, _exc_name):
        setattr(_ss_smartsheet_module, _exc_name, getattr(ss_exc, _exc_name))
del _ss_smartsheet_module, _exc_name
```

**After migration (4.0.0-only, pin lifted):**
- Remove the entire block including the comment (lines 30–54).
- The `import smartsheet.exceptions as ss_exc` at line 28 stays — it provides the exception
  classes for the `except ss_exc.*` retry blocks throughout the file.
- The `import smartsheet.smartsheet as _ss_smartsheet_module` is removed.
- All six `except ss_exc.X` blocks (lines 8389, 8397, 8603, 8620–8622, 9835, 9843) remain
  **completely unchanged** — they still use `ss_exc.*` which resolves correctly.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Installing from source dist | Custom download script | `pip install --no-binary smartsheet-python-sdk` flag | pip handles sdist build + install natively |
| Exception retry backoff | Custom retry framework | Existing `ss_exc.*` except blocks (unchanged) | Already production-proven; zero behavior change required |
| Pin verification | Custom pip resolver | `pip install --dry-run -r requirements.txt` | Standard pip dry-run confirms version resolution |

---

## Pitfall Inventory

### Pitfall 1: Wheel vs sdist — the root cause
**What goes wrong:** `pip install smartsheet-python-sdk==4.0.0` (default) downloads the wheel,
which contains only `version.py`. The prior `smartsheet/` installation is removed. All imports
fail with `ModuleNotFoundError`.
**Why it happens:** The 4.0.0 wheel was built with hatchling + hatch-vcs but is missing a
`[tool.hatch.build.targets.wheel] packages = ["smartsheet"]` declaration in `pyproject.toml`.
hatchling's version-only build hook only included `version.py`.
**How to avoid:** Add `--no-binary smartsheet-python-sdk` to the `pip install` invocation in
both workflow files. This forces pip to compile from the sdist, which contains all source files.
**Warning signs:** Post-install `python -c "import smartsheet; print(smartsheet.__file__)"` returns
`None` or points to a directory containing only `version.py`.

### Pitfall 2: Re-export workaround left in place after pin lift
**What goes wrong:** Workaround is harmless in 4.0.0 (the `if not hasattr` guard prevents
double-patching), but the dead import `import smartsheet.smartsheet as _ss_smartsheet_module`
adds noise and perpetuates a now-false comment ("SDK raises AttributeError from
`_request_with_retry`"). Method was renamed `request_with_retry` (without leading `_`) in a
prior 3.x release.
**How to avoid:** Remove the full block (lines 30–54 including comment) in the same PR that
lifts the pin.

### Pitfall 3: pip cache serving stale 3.x wheel
**What goes wrong:** GitHub Actions caches `~/.cache/pip` keyed by `hashFiles('requirements.txt')`.
Changing the pin in `requirements.txt` busts the cache hash automatically. However, if the
`--no-binary` flag is added to the workflow command but the cache still contains a 3.x
installation, a cache hit could restore the old resolved packages.
**How to avoid:** The `requirements.txt` hash-based cache key ensures the cache is busted when
the pin changes. Verify with a workflow run that the new SDK version is actually installed
(log `pip show smartsheet-python-sdk` in the install step).

### Pitfall 4: pytest running against the broken wheel install
**What goes wrong:** Developer runs `pytest tests/ -v` locally with the broken WHL installed.
Tests that do `from smartsheet.models.sheet import Sheet` will fail with `ModuleNotFoundError`.
**How to avoid:** After lifting the pin, developers must reinstall from sdist locally:
```
pip install --no-binary smartsheet-python-sdk 'smartsheet-python-sdk>=4.0.0'
```
Document this in CLAUDE.md build instructions.

### Pitfall 5: InternalServerError in error_lookup
**What goes wrong:** `InternalServerError` exists in `smartsheet.exceptions` but is NOT in
`OperationErrorResult.error_lookup` (which only maps Smartsheet errorCodes 4001–4004).
HTTP 500s without a Smartsheet-format body fall back to `ApiError` (code 0, `should_retry=False`).
The `except ss_exc.InternalServerError` blocks are technically dead code via the SDK's normal
retry path in 4.0.0.
**Why it's not a problem:** `InternalServerError` catching in the custom retry blocks is benign
dead code — the SDK handles its own retry loop, and our custom blocks add an outer safety net.
Removing them would be a behavior change, so leave them. No action required.

---

## Call-Site Compatibility Table

Every SDK call site in `generate_weekly_pdfs.py` verified against 4.0.0 sdist source:

| Call Site | Line(s) | 4.0.0 Compatibility | Action |
|-----------|---------|---------------------|--------|
| `import smartsheet.exceptions as ss_exc` | 28 | COMPATIBLE (module exists in sdist) | None |
| `import smartsheet.smartsheet as _ss_smartsheet_module` | 44 | Module still exists; workaround no-op | Remove entire block (L30–54) |
| `ss_exc.RateLimitExceededError` | 8389, 8603, 9835 | COMPATIBLE — class in exceptions | None |
| `ss_exc.UnexpectedErrorShouldRetryError` | 8397, 8620, 9843 | COMPATIBLE | None |
| `ss_exc.InternalServerError` | 8397, 8621, 9843 | COMPATIBLE (class present; rarely raised via SDK) | None |
| `ss_exc.ServerTimeoutExceededError` | 8397, 8622, 9843 | COMPATIBLE | None |
| `client.Sheets.get_sheet(sheet_id, include=..., row_numbers=...)` | ~8150s | COMPATIBLE — sig unchanged | None |
| `client.Attachments.list_row_attachments(TARGET_SHEET_ID, row.id).data` | 8387 | COMPATIBLE — `.data` still on `IndexResult` | None |
| `client.Attachments.delete_attachment(...)` | various | COMPATIBLE | None |
| `client.Attachments.attach_file_to_row(...)` | various | COMPATIBLE | None |
| `client.Folders.get_folder_children(folder_id, last_key=...)` | various | COMPATIBLE — `last_key=` param unchanged | None |
| `client.errors_as_exceptions(True)` | 8134 | COMPATIBLE — method unchanged | None |
| `from smartsheet.models.sheet import Sheet` | 2449 | COMPATIBLE — model unchanged | None |
| `from smartsheet.models.folder import Folder` | 2450 | COMPATIBLE — model unchanged | None |
| `logging.getLogger('smartsheet.smartsheet')` | 137 | COMPATIBLE — submodule still `smartsheet.smartsheet` | None |

**Test file imports verified:**

| Import | File | 4.0.0 Status | Action |
|--------|------|--------------|--------|
| `import smartsheet.exceptions as ss_exc` | test_billing_audit_shadow.py:64 | COMPATIBLE | None |
| `import smartsheet.smartsheet as _ss_smartsheet_module` | test_billing_audit_shadow.py:65 | COMPATIBLE (module still exists) | None |
| `sys.modules["smartsheet.exceptions"] = mock.MagicMock()` | test_billing_audit_shadow.py:80,85 | COMPATIBLE | None |
| `sys.modules["smartsheet.smartsheet"] = mock.MagicMock()` | test_billing_audit_shadow.py:81,86 | COMPATIBLE | None |
| `from smartsheet.models.sheet import Sheet` | test_subcontractor_pricing.py:512, test_vac_crew.py:41 | COMPATIBLE | None |
| `from smartsheet.models.folder import Folder` | test_subcontractor_pricing.py:513, test_vac_crew.py:42 | COMPATIBLE | None |

**Net test file changes required: ZERO.**

---

## Migration Strategy

### Recommended: 4.0.0-Only Clean Migration

Do NOT use a try/except import shim for 3.x/4.0.0 dual-compatibility. The pin is being
lifted from `>=3.1.0,<4.0.0` to `>=4.0.0`. There is no reason to maintain backward
compatibility with 3.x after the lift.

**Rationale:** The workaround's `if not hasattr` guard already makes it safe on both versions.
But keeping dead code with a now-misleading comment is a maintenance hazard. Remove cleanly.

### Exact Changes — by File

**`generate_weekly_pdfs.py`** (1 change):
- Remove lines 30–54 (the re-export workaround block including its comment).
- Line 28 (`import smartsheet.exceptions as ss_exc`) stays.
- Zero changes to exception `except` blocks or any other SDK call.

**`requirements.txt`** (1 change):
- Line 7: Update comment to reflect the `--no-binary` workaround and the packaging bug.
- Line 8: Change `smartsheet-python-sdk>=3.1.0,<4.0.0` to `smartsheet-python-sdk>=4.0.0`.

**`.github/workflows/weekly-excel-generation.yml`** (1 change):
- Line 188: Change `pip install -r requirements.txt` to
  `pip install --no-binary smartsheet-python-sdk -r requirements.txt`

**`.github/workflows/system-health-check.yml`** (1 change):
- Line 51: Same change — `pip install --no-binary smartsheet-python-sdk -r requirements.txt`

**`memory-bank/living-ledger.md`** (1 addition):
- Append dated entry recording: packaging bug nature, `--no-binary` workaround, re-export
  workaround removal, and the rule that transport-critical deps with broken wheels need
  `--no-binary` flags (extends the "upper-bound transport-critical deps" rule from 260608-gwm).

**Total: 5 surgical changes across 5 files. Zero changes to billing logic.**

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | ✓ | 3.14 local / 3.12 CI | — |
| pip | Package install | ✓ | Current | — |
| smartsheet-python-sdk 4.0.0 (sdist) | Migration target | ✓ | 4.0.0 (PyPI) | `--no-binary` forces sdist use |
| pytest | SDK-04 validation | ✓ | 9.0.3 (requirements.txt) | — |
| TEST_MODE env var | SDK-06 dry-run | ✓ | Built into generate_weekly_pdfs.py | — |

**Note on local dev environment:** Local dev currently runs 3.7.2 (system install). After
lifting the pin, developers must reinstall:
```bash
pip install --no-binary smartsheet-python-sdk "smartsheet-python-sdk>=4.0.0"
```
This should be added to CLAUDE.md build instructions.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | none (uses pytest.ini defaults) |
| Quick run command | `pytest tests/ -v -x` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | Notes |
|--------|----------|-----------|-------------------|-------|
| SDK-01 | `import smartsheet.exceptions as ss_exc` succeeds; all 4 exception classes resolve | smoke import | `python -c "import smartsheet.exceptions as ss_exc; ss_exc.RateLimitExceededError"` | Run after `--no-binary` install |
| SDK-01 | `python -m py_compile generate_weekly_pdfs.py` succeeds | syntax | `python -m py_compile generate_weekly_pdfs.py` | Gated in CLAUDE.md |
| SDK-02 | Re-export workaround block removed; no `AttributeError` on client init | unit | `pytest tests/ -v -k test_billing_audit_shadow` | Existing shadow tests cover import path |
| SDK-03 | All call sites function with 4.0.0 signatures | integration smoke | `TEST_MODE=true python generate_weekly_pdfs.py` | Non-destructive; no upload |
| SDK-04 | Full test suite green against 4.0.0 | full suite | `pytest tests/ -v` | All existing tests pass; no new mocks needed |
| SDK-05 | `requirements.txt` resolves to >=4.0.0 | dry-run | `pip install --dry-run --no-binary smartsheet-python-sdk -r requirements.txt` | Confirm 4.0.0 selected |
| SDK-06 | Pipeline produces identical output vs 3.x baseline | smoke | `TEST_MODE=true python generate_weekly_pdfs.py` | Compare logs; no Excel upload |

### Pre-Merge Gate
```bash
# After --no-binary install of 4.0.0:
pip show smartsheet-python-sdk  # confirm version 4.0.0
python -m py_compile generate_weekly_pdfs.py
pytest tests/ -v
TEST_MODE=true python generate_weekly_pdfs.py
```

### Wave 0 Gaps
None — existing test infrastructure covers all phase requirements. No new test files
or fixtures required.

---

## State of the Art

| Old (3.x) | New (4.0.0) | Relevant to Phase |
|-----------|-------------|-------------------|
| `request()` uses `getattr(sys.modules[__name__], name)` for exc lookup | `request()` uses `importlib.import_module(__package__ + ".exceptions")` | SDK-02: re-export workaround is now dead code |
| `_request_with_retry` (private, leading underscore) | `request_with_retry` (public, no underscore) | Comment in workaround was already stale — corrects itself on removal |
| No `get_folder_metadata` | `get_folder_metadata(folder_id, include=None)` added | Not used; no action |
| `Sharing` methods on Sheets/Reports/Sights/Workspaces | Removed; use `client.Sharing` | Not used by this codebase |

---

## Open Questions

1. **Upstream wheel packaging fix**
   - What we know: 4.0.0 wheel ships only `version.py` due to missing hatchling config. The
     `pyproject.toml` has no `[tool.hatch.build.targets.wheel]` declaration.
   - What's unclear: Whether Smartsheet will publish a 4.0.1 patch release before or after
     we complete this migration.
   - Recommendation: File an issue at github.com/smartsheet/smartsheet-python-sdk before
     merging this migration. If 4.0.1 ships with a fixed wheel before merge, the
     `--no-binary` flag can be dropped. If not, the `--no-binary` workaround is stable
     and unobtrusive — proceed with it.

2. **master branch divergence**
   - What we know: ROADMAP.md notes local `master` has diverged 10/10 from `origin/master`.
   - What's unclear: Whether the worktree is rebased before this migration branch is cut.
   - Recommendation: The plan's Wave 0 task should include a `git fetch && git rebase
     origin/master` step before any code edits.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The 4.0.0 wheel packaging bug (version.py-only) persists at time of execution; no 4.0.1 hotfix has shipped | Migration Strategy | If 4.0.1 ships with a fixed wheel, the `--no-binary` flag is unnecessary (benign but redundant) |
| A2 | No other callers of `smartsheet.smartsheet` module internals exist outside of `generate_weekly_pdfs.py` lines 30–54 | Call-Site Table | If other scripts use `_ss_smartsheet_module`, removing the workaround could break them — but `grep` search confirmed no other callers |

---

## Security Domain

> This phase touches no auth, session, data handling, or user-facing surfaces. Security
> enforcement not applicable.

---

## Sources

### Primary (HIGH confidence — direct code inspection)
- `smartsheet_python_sdk-4.0.0.tar.gz` extracted and read: `smartsheet/smartsheet.py`,
  `smartsheet/exceptions.py`, `smartsheet/folders.py`, `smartsheet/__init__.py`,
  `pyproject.toml` — all key architectural decisions verified from source.
- `smartsheet_python_sdk-4.0.0-py3-none-any.whl` inspected: confirmed 7.8 KB wheel contains
  only `version.py`.
- `smartsheet_python_sdk-3.9.0-py3-none-any.whl` inspected: confirmed 266 KB wheel contains
  full package — establishes that 4.0.0 wheel is anomalously small.
- `generate_weekly_pdfs.py` lines 1–65, 8127–8145, 8383–8403, 8603–8622, 9835–9843 read
  directly. [VERIFIED: local codebase grep]
- `requirements.txt`, `.github/workflows/weekly-excel-generation.yml` (lines 154–188),
  `.github/workflows/system-health-check.yml` (lines 50–51) read directly.
- `tests/test_billing_audit_shadow.py` lines 57–86 read directly.
- `tests/test_subcontractor_pricing.py` lines 509–580 read directly.

### Secondary (MEDIUM confidence)
- PyPI JSON API (`https://pypi.org/pypi/smartsheet-python-sdk/4.0.0/json`) — confirmed file
  sizes and URLs. [VERIFIED: live request 2026-06-08]
- `https://raw.githubusercontent.com/smartsheet/smartsheet-python-sdk/mainline/CHANGELOG.md`
  — confirmed 4.0.0 breaking changes list. [VERIFIED: live request 2026-06-08]

---

## Metadata

**Confidence breakdown:**
- Root cause diagnosis: HIGH — direct wheel/sdist byte inspection, confirmed 7.8 KB vs 266 KB
- Re-export workaround verdict (remove): HIGH — `request()` source in 4.0.0 sdist confirmed
- SDK call-site compatibility: HIGH — 4.0.0 sdist source read for every method used
- Test mock compatibility: HIGH — module paths verified to still exist in 4.0.0
- `--no-binary` workaround: HIGH — standard pip feature, sdist confirmed complete

**Research date:** 2026-06-08
**Valid until:** 2026-07-08 (or when 4.0.1 ships fixing the wheel — recheck before then)
