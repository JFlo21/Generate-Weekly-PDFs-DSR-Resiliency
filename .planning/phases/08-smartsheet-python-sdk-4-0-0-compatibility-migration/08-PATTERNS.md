# Phase 08: smartsheet-python-sdk 4.3.0 Compatibility Migration - Pattern Map

**Mapped:** 2026-07-21
**Files analyzed:** 3 confirmed modify targets + 1 discretionary (CLAUDE.md) + 0 new files
**Analogs found:** 4 / 4

> **Scope note:** Per 08-CONTEXT.md (D-01–D-08), this is a compat-only pin
> bump. There are NO new files, NO new components/services/controllers, and
> NO GitHub Actions workflow edits (D-03 — `--no-binary` is obsolete, upstream
> fixed the wheel in 4.0.1). The "closest analog" for every touched file is
> unusually strong: this repo already ran the *mirror-image* change (adding
> the `<4.0.0` pin) as quick-task `260608-gwm`, whose PLAN/SUMMARY are read
> directly below as the primary analog. The live read-only probe (D-05) is
> **not a new file** — 08-VALIDATION.md already specifies it as a manual
> `SKIP_UPLOAD=true` dry-run step, not a committed script.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|-----------------|---------------|
| `requirements.txt` (lines 4-8) | config (dependency manifest) | batch (one-time resolution at install) | `.planning/quick/260608-gwm-.../260608-gwm-PLAN.md` Task 1 (the pin's own predecessor edit, same file, same lines) | exact — same file, same lines, mirror-image change |
| `generate_weekly_pdfs.py` (lines 20-46, dead re-export block) | script / SDK import site | request-response (client init at module load) | Same file, lines 1-60 (current live state) + `260608-gwm-PLAN.md` `<interfaces>` block (documents the block being removed, as it looked when added) | exact — literal removal target, already read in full |
| `memory-bank/living-ledger.md` (append) | docs / append-only ledger | event-driven (dated entry per change) | `260608-gwm-SUMMARY.md` Task 2 (Living Ledger append action) + existing 2026-07-21 18:20 / 19:10 entries already in the ledger | exact — same file, same append convention, same phase's own prior entries |
| `CLAUDE.md` (discretionary — local-dev install note) | docs / config | N/A | CLAUDE.md "Build, Test, and Run Commands → Python core engine" section | role-match — only touch if a stale `--no-binary` or version note exists (grep confirms it does NOT — see Metadata) |

**No files are created in this phase.** `pipeline/retry.py` and
`tests/test_smartsheet_retry.py` are read-only reference contracts (must
survive byte-for-byte unchanged per D-04/canonical_refs) — included below
under Shared Patterns for context, not as edit targets.

---

## Pattern Assignments

### `requirements.txt` (config, batch)

**Analog:** the file's own prior edit in `260608-gwm-PLAN.md` Task 1 (2026-06-08, added the `<4.0.0` ceiling this phase now replaces).

**Current state** (read 2026-07-21, lines 4-8):
```
# Core Dependencies
# 3.1.0+ required for Folders.get_folder_children (replacement for deprecated get_folder)
# Upper bound excludes the breaking 4.0.0 (2026-06-08) major release, which removed
# smartsheet.exceptions + Folders.get_folder/list_folders + Templates and changed pagination.
smartsheet-python-sdk>=3.1.0,<4.0.0
```

**Prior-edit pattern to mirror** (from `260608-gwm-PLAN.md` Task 1 — this is
literally how the last SDK-pin edit to this exact file was specified and
verified):
```
Change line N of requirements.txt from:
    smartsheet-python-sdk>=3.1.0
to:
    smartsheet-python-sdk>=3.1.0,<4.0.0

Keep the existing explanatory comment coherent and extend it so a future
operator understands BOTH bounds.
```

**Apply for Phase 08** (per D-01/D-02, exact pin — comment wording is
Claude's Discretion per D-08 but must record review date + ledger pointer):
```
smartsheet-python-sdk==4.3.0
```
Comment must state: (1) this is an EXACT pin, not a range — extends the
260608-gwm "upper-bound transport-critical deps" rule to its strongest form
per D-01; (2) 4.0.1-4.3.0 changelog reviewed 2026-07-21, additive only; (3)
pointer to `memory-bank/living-ledger.md` for full rationale (do not restate
the whole ledger entry inline — this file's own convention, established by
260608-gwm, is a short 2-4 line comment + the ledger holds the narrative).

**Verify pattern to mirror** (from `260608-gwm-PLAN.md` Task 1 `<verify>`,
adapted to exact-pin matching instead of range matching):
```python
python -c "import re,sys; t=open('requirements.txt').read(); m=re.search(r'^smartsheet-python-sdk(.*)$', t, re.M); spec=m.group(1) if m else ''; ok=(spec.strip()=='==4.3.0'); print('SPEC:', spec.strip()); sys.exit(0 if ok else 1)"
```

---

### `generate_weekly_pdfs.py` lines 20-46 (script, SDK import site — removal only)

**Analog:** the block's own addition, documented verbatim in
`260608-gwm-PLAN.md`'s `<interfaces>` section — this phase performs the
exact inverse operation.

**Current live content** (Read directly, lines 17-47 — this IS the removal
target, already fully captured, do not re-read):
```python
17  import smartsheet
18  import smartsheet.exceptions as ss_exc
19
20  # Upstream SDK workaround: smartsheet-python-sdk 3.8.0 raises an
21  # AttributeError from smartsheet.smartsheet.Smartsheet._request_with_retry
22  # whenever the API returns a retryable error (429, 5xx). At
23  # smartsheet/smartsheet.py:303 it does
24  # ``getattr(sys.modules[__name__], native.result.name)`` to look up the
25  # exception class to raise, but that module's top-level imports only
26  # expose ApiError / HttpError / UnexpectedRequestError. The retryable
27  # exception classes (RateLimitExceededError, UnexpectedErrorShouldRetry-
28  # Error, InternalServerError, ServerTimeoutExceededError, SystemMainte-
29  # nanceError) live in smartsheet.exceptions and were never re-exported
30  # into smartsheet.smartsheet, so the getattr fails and our retry
31  # wrapper never gets the real exception. Re-export the missing names
32  # here so the SDK's internal lookup succeeds. The ``if not hasattr``
33  # guard makes this a no-op if the upstream SDK ever re-exports them.
34  import smartsheet.smartsheet as _ss_smartsheet_module
35  _exc_name = None
36  for _exc_name in (
37      'RateLimitExceededError',
38      'UnexpectedErrorShouldRetryError',
39      'InternalServerError',
40      'ServerTimeoutExceededError',
41      'SystemMaintenanceError',
42  ):
43      if not hasattr(_ss_smartsheet_module, _exc_name) and hasattr(ss_exc, _exc_name):
44          setattr(_ss_smartsheet_module, _exc_name, getattr(ss_exc, _exc_name))
45  del _ss_smartsheet_module
46  del _exc_name
47  from dotenv import load_dotenv
```

**Removal action (D-04):** Delete lines 20-46 in full (the comment block +
the `import smartsheet.smartsheet as _ss_smartsheet_module` line + the
re-export loop + both `del` statements). Lines 17-18 (`import smartsheet`,
`import smartsheet.exceptions as ss_exc`) and line 47 onward stay byte-for-
byte unchanged. Confirmed by 08-RESEARCH.md SDK-02: SDK 4.x's `request()`
uses `importlib.import_module(__package__ + ".exceptions")`, making this
workaround a permanent no-op — safe to delete, not just leave inert.

**Do NOT touch (explicitly out of scope, D-04):**
- The six `except ss_exc.*` retry blocks elsewhere in the file — zero
  changes, they resolve `ss_exc.*` directly and never depended on the
  removed re-export.
- `pipeline/retry.py` — the centralized retry contract (see Shared Patterns
  below) — not part of this migration's edit surface at all.

**Verify pattern:**
```bash
python -m py_compile generate_weekly_pdfs.py
pytest tests/ -v -k test_billing_audit_shadow
```

---

### `memory-bank/living-ledger.md` (docs, append-only)

**Analog:** `260608-gwm-PLAN.md` Task 2 action text (the append convention
for this exact ledger, same subsystem) + the two entries this same phase
already added on 2026-07-21 (context-gathering + planning-start), which are
the most recent and most relevant style reference.

**Existing entries from this same phase (read directly, tail of file —
extract the header/timestamp convention, do not restate the full history):**
```
## [2026-07-21 18:20] Phase 08 SDK 4.x migration — decisions locked; exact-pin rule for transport-critical deps

Phase 08 (lift the `<4.0.0` smartsheet-python-sdk pin) unblocked and context
gathered (`/gsd-discuss-phase 08`, branch `feat/phase-08-sdk-430-migration`,
commit `631f757`). Durable rules and facts:

- **Exact-pin rule (extends 260608-gwm):** transport-critical deps get an
  EXACT pin (`smartsheet-python-sdk==4.3.0`), not just an upper bound. ...

## [2026-07-21 19:10] Phase 08 planning started — validation strategy committed
...
```

**Append convention to mirror (header shape, verified across both prior
entries in this ledger):**
```
## [YYYY-MM-DD HH:MM] <short imperative title — what happened>

<1-2 sentence context: which phase/branch/commit>. <Durable rules and facts,
as bullet points, each bolded with a short rule name:>

- **<Rule name>:** <what changed, why, and the generalizable rule other
  future changes should follow>.
```

**Apply for Phase 08 (post-implementation entry — append AFTER the code
change lands, per the same pattern the 260608-gwm predecessor used of
appending post-hoc with commit hashes):** record (1) the exact pin
`==4.3.0` landed, replacing the `<4.0.0` range; (2) the dead re-export block
removed from `generate_weekly_pdfs.py`; (3) commit hash(es); (4) verification
evidence (6-gate harness result + live probe result per D-05); (5) explicit
statement that `--no-binary` is retired (already recorded in the 18:20
entry — do not duplicate, cross-reference it instead).

**Verify pattern (mirrors 260608-gwm-PLAN.md Task 2 `<verify>`):**
```python
python -c "import sys; t=open('memory-bank/living-ledger.md',encoding='utf-8').read(); ok=('smartsheet-python-sdk==4.3.0' in t); print('LEDGER_OK:', ok); sys.exit(0 if ok else 1)"
```

---

### `CLAUDE.md` (discretionary, docs) — likely NO-OP

**Analog:** "Build, Test, and Run Commands → Python core engine" section
(already present, shows the current install command).

**Finding:** `grep -rn "smartsheet-python-sdk" CLAUDE.md` returns zero
matches — CLAUDE.md has never referenced a specific SDK version or
`--no-binary`, so there is nothing stale to refresh here. Per D-08's
discretion note, only touch this file if the planner independently decides
a version pointer adds operator value; the existing pattern for such a
pointer would be a one-line addition inside the existing `pip install -r
requirements.txt` fenced block, not a new section — do not add a new
top-level heading for a one-line fact.

---

## Shared Patterns

### The retry exception contract — READ-ONLY reference, must survive unchanged

**Source:** `pipeline/retry.py` (lines 67, 81-117, 130-155, 158-248)
**Applies to:** Nothing in this phase modifies this file. Included here
only so the planner/implementer can confirm the D-05 live probe and D-04
removal cannot regress it.

```python
# pipeline/retry.py:67
import smartsheet.exceptions as ss_exc

# pipeline/retry.py:81-87 — typed exceptions given exponential backoff
_TRANSIENT_EXC: tuple[type[BaseException], ...] = (
    ss_exc.UnexpectedErrorShouldRetryError,  # API 4004
    ss_exc.ServerTimeoutExceededError,       # API 4002
    ss_exc.SystemMaintenanceError,           # API 4001
    ss_exc.UnexpectedRequestError,           # SDK wrapper: requests.RequestException
    ss_exc.HttpError,                        # SDK wrapper: SSLError; base of 500
)

# pipeline/retry.py:130-155 — ApiError introspection helpers (the exact
# surface D-05's live probe exists to validate against a REAL response,
# since tests/test_smartsheet_retry.py mocks exc.error.result with
# mock.Mock() and cannot catch real SDK error-shape drift)
def _api_error_code(exc: BaseException) -> int | None:
    try:
        return exc.error.result.code  # type: ignore[attr-defined]
    except AttributeError:
        return None

def _http_status_code(exc: BaseException) -> int | None:
    try:
        return exc.error.result.status_code  # type: ignore[attr-defined]
    except AttributeError:
        return None
```

Per D-02, the 4.0.1-4.3.0 changelog review confirmed zero changes to
`smartsheet.exceptions`, `ApiError.error.result` internals, or any of the
above call signatures — this contract is expected to need no code change,
only the D-05 live-probe confirmation (a `SKIP_UPLOAD=true` dry-run per
08-VALIDATION.md, not a new script).

### Mocked-shape blind spot — why a live probe exists (reference only)

**Source:** `tests/test_smartsheet_retry.py` (lines 46-66, 152)
**Applies to:** Explains D-05's rationale; no test file changes required
(SDK-04 finding: net test changes = zero).

```python
# tests/test_smartsheet_retry.py:46-49 — mirrors the real SDK shape but
# is a Mock(), not the live SDK — cannot catch real error-shape drift
err = mock.Mock()
err.error.result.code = 4000
...
# lines 61-66 — same for the 5xx/status_code path
err.error.result.status_code = 503
```

### Living Ledger dated-entry convention

**Source:** `memory-bank/living-ledger.md` (tail, 2026-07-09 and 2026-07-21 entries)
**Applies to:** The one ledger append this phase makes.

```
## [YYYY-MM-DD HH:MM] <imperative title>

<narrative context paragraph>

- **<Bolded rule name>:** <durable rule, generalizable beyond this one change>.
```

---

## No Analog Found

None. Every file in this phase's edit surface (`requirements.txt`,
`generate_weekly_pdfs.py`, `memory-bank/living-ledger.md`) has a direct,
same-file, same-lineage predecessor edit (`260608-gwm`) already in the
repo's history, plus the current live content was read directly for exact
line numbers. `CLAUDE.md` has no analog because it needs no change (see
above).

## Metadata

**Analog search scope:** `generate_weekly_pdfs.py` (lines 1-60),
`requirements.txt` (full, 29 lines), `pipeline/retry.py` (full, 249 lines),
`tests/test_smartsheet_retry.py` (targeted grep, lines 46-66/152),
`memory-bank/living-ledger.md` (tail ~60 lines + grep for `260608-gwm`),
`.planning/quick/260608-gwm-.../260608-gwm-PLAN.md` and `-SUMMARY.md` (full),
`scripts/check_facade_completeness.py` (full, as a style reference for the
gate-script family invoked by `scripts/run_6_gates.sh` — confirmed no new
script is needed per 08-VALIDATION.md's manual-only probe row), CLAUDE.md
(grep only, zero matches for `smartsheet-python-sdk`).
**Files scanned:** 9 read/grepped directly; 08-VALIDATION.md confirmed the
live probe is a manual dry-run, not a new committed file.
**Pattern extraction date:** 2026-07-21
