# Phase 12: Ownership — last known foreman as of the week - Pattern Map

**Mapped:** 2026-09-02
**Files analyzed:** 9 (3 new scripts/1 new workflow, 2 modified pipeline files, 2 new test files, 1 modified SQL doc + owner-deployed SQL companion)
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|-----------------|---------------|
| `scripts/backfill_claim_time_attribution.py` (NEW) | utility (CLI script) | batch / read-many-write-one (dry-run report → RPC) | `scripts/backfill_attribution_snapshot.py` (CLI/argparse/exit-code shape only — **not** its "current value wins" semantics) | role-match (shape), semantics explicitly divergent |
| `scripts/backfill_cell_history_attribution.py` (NEW, Source 5) | utility (CLI script, external-API) | batch / rate-limited external read | `pipeline/snapshot_drift.py:82-438` (paced/capped `get_cell_history` pattern) — NOT `audit_billing_changes.py`'s stub | exact (working pattern) |
| `.github/workflows/cell-history-backfill.yml` (NEW) | config (CI workflow) | event-driven (cron + workflow_dispatch) | `.github/workflows/weekly-excel-generation.yml` | role-match |
| `billing_audit/schema.sql` (MODIFIED — add `backfill_attribution` RPC contract comment + `attribution_snapshot_backup_<date>` note) | config (owner-deployed SQL, contract-as-comment) | — | `billing_audit/schema.sql:173-257` (`freeze_attribution` / `lookup_attribution` contract-comment blocks) | exact |
| Owner-deployed SQL file for `backfill_attribution` RPC (spec §4; ships as a PR file, e.g. `generated_docs/own03_backfill_<date>.sql` or a `docs/superpowers/specs/` companion) | migration (RPC body, jsonb_to_recordset) | batch write, first-write-wins-only-if-sentinel | `pipeline_memory/schema.sql:244-330` (`upsert_rows_bulk` — the one **actually-defined, repo-owned** `jsonb_to_recordset` RPC in this codebase) | role-match (structure); `billing_audit/schema.sql`'s comment-only pattern for the "ships as owner-deployed" wrapper |
| `pipeline/cleanup.py` (MODIFIED — CR-01 fix) | middleware (filename/sentinel classifier) | transform (pure predicate) | itself, `_is_sentinel_identifier` at `pipeline/cleanup.py:89-116` + call site `pipeline/cleanup.py:495-508` | exact (in-place fix) |
| `pipeline/orchestrate.py` (MODIFIED — WR-01 fix) | controller (orchestration entry) | request-response (Smartsheet API) | `pipeline/discovery.py:75-83` (guarded, function-local `from smartsheet.models.X import Y`) | role-match (import-pattern analog) |
| `tests/test_backfill_claim_time_attribution.py` (NEW) | test | fixture-driven integration (no live Smartsheet/Supabase) | `tests/test_billing_audit_shadow.py` `BackfillCliDateValidationTests` (2589-2727) + `_make_fake_supabase_client`/`_fake_rpc_response` (135-220) | role-match |
| `tests/test_cleanup.py` (NEW) | test | unit (pure predicate) | `tests/test_sentinel_never_a_claimer.py` `SentinelPredicateTests` (74-100+) | exact (structure) |
| WR-01 structural/grep test (lives inside `tests/test_backfill_claim_time_attribution.py` or a new small file — Claude's discretion) | test | structural/static (source-grep, no execution) | `tests/test_billing_audit_shadow.py:2617-2638` (`_read_source` + `_collapse_ws` regex-on-source pattern) | exact |

**Tracked-source gate:** every analog path above verified via `git ls-files` — all tracked (`weekly-excel-generation.yml`, `billing_audit/schema.sql`, `billing_audit/writer.py`, `pipeline/cleanup.py`, `pipeline/discovery.py`, `pipeline/orchestrate.py`, `pipeline/snapshot_drift.py`, `pipeline_memory/schema.sql`, `scripts/backfill_attribution_snapshot.py`, `tests/test_billing_audit_shadow.py`, `tests/test_sentinel_never_a_claimer.py`, `supabase/portal_schema.sql`, `audit_billing_changes.py`). No gitignored mirror paths were used.

---

## Pattern Assignments

### `scripts/backfill_claim_time_attribution.py` (NEW)

**Analog:** `scripts/backfill_attribution_snapshot.py` (301 lines, full file read) — copy the *shape*, reject the *semantics*.

**Copy this shape:**
- Repo-root `sys.path` bootstrap so the script runs from anywhere (lines 25-28):
```python
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
```
- `argparse.ArgumentTypeError` (not bare `ValueError`) for malformed CLI date/token input, so argparse prints a clean usage message (lines 31-52) — the new script's `--weeks` parsing should mirror this.
- `load_dotenv()` called **before** `get_client()`, with ImportError silently passed and any other exception logged as a WARNING (lines 101-114) — exact text pattern `except ImportError: pass` / `logging.warning(...load_dotenv() failed...)` is grep-tested in `tests/test_billing_audit_shadow.py:2617-2638`.
- Exit-code discipline: distinct non-zero exit codes per failure class (2 = no Supabase client, 5 = flag definitively off, 7 = flag-read connectivity failure, 3/4/6 = other failures) — `get_flag`/`is_flag_resolved` split shown at lines 142-161. The new script should define its own small exit-code table (client missing, backup table missing before `--apply`, dry-run-only violation, RPC row errors) using the same "distinguish definitive-off from read-failure" discipline.
- `release`/`run_id` normalization to `""` (never `None`) before building RPC params, with GitHub Actions rerun-awareness (`GITHUB_RUN_ID` + `GITHUB_RUN_ATTEMPT`) (lines 199-223).
- Local exception counter alongside a writer-reported counter, OR-combined into the final exit gate (lines 226-294) — regression-tested at `tests/test_billing_audit_shadow.py:2640-2661`; mirror this "two independent failure signals, either flips exit code" shape for the new RPC's per-row `updated|skipped_real_name|skipped_no_row` result handling.

**Reject this semantics (do NOT copy):**
- Lines 235-259: this script treats "row currently shows `Units Completed?` checked in the CURRENT Smartsheet pull, for the target week" as the claim. The new script must NEVER read current Smartsheet state as a source — it reads `pipeline_memory.row_event`/`row_state` (source 1), non-sentinel `attribution_snapshot` on the same row (source 2), `public.artifacts` filenames (source 3), and frozen `hash_history.json` (source 4), and (separately, source 5) Smartsheet cell history — never "what does the row show today."
- `freeze_row(row, ...)` (line 259) is the wrong write path entirely — that's the live first-write-wins freeze RPC. The new script must call the new `billing_audit.backfill_attribution(p_rows jsonb)` RPC, which writes ONLY where `frozen_<role>` is currently sentinel/NULL.

**CLI flags to implement (spec §5, Claude's discretion on argparse wiring):**
```
--wr 91234567,…      --weeks 2026-07-05,…   --roles primary,helper,vac_crew
--sources 1,2,3,4     (5 never on by default)
--dry-run (default ON) → generated_docs/own03_backfill_report.json + .csv
--apply --i-approved-this   (requires backup table to exist)
```

---

### `scripts/backfill_cell_history_attribution.py` (NEW — OWN-03 Source 5)

**Analog:** `pipeline/snapshot_drift.py` (710 lines; read 1-60, 82-99, 280-438 this session) — this is the REAL working cell-history call; `audit_billing_changes.py::_selective_cell_history_enrichment` (~line 875) is confirmed a stub (`history_meta["history_available"] = True` hardcoded, never calls the API) — do not use it as a reference implementation.

**Env-var-driven cap/pace/deadline pattern** (`pipeline/snapshot_drift.py:82-97, 371-374`):
```python
def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        return default

def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        return default

max_rows = _int_env("SNAPSHOT_DRIFT_MAX_ROWS", 40)
pace_sec = _float_env("SNAPSHOT_DRIFT_PACE_SEC", 2.0)
max_minutes = _float_env("SNAPSHOT_DRIFT_MAX_MINUTES", 5.0)
```
Rename the env vars for the new script (e.g. `CELL_HISTORY_BACKFILL_MAX_ROWS` / `_PACE_SEC` / `_MAX_MINUTES`) but keep the same three-knob shape plus the request cap from spec §3 row 5 (default 3,000 requests/run).

**Self-paced fetch + deadline loop** (`pipeline/snapshot_drift.py:400-438`):
```python
deadline = datetime.datetime.now() + datetime.timedelta(minutes=max_minutes)
called_once = [False]

def _fetch_history(sheet_id: int, row_id: int, column_id: int) -> Any:
    # Self-pacing: sleep between calls, never before the first one this run.
    if called_once[0]:
        time.sleep(pace_sec)
    called_once[0] = True
    return client.Cells.get_cell_history(
        sheet_id, row_id, column_id, include_all=True
    )

for index, candidate in enumerate(ordered):
    if index >= max_rows:
        candidate["classification"] = _CLASSIFICATION_UNCLASSIFIED
        continue
    if datetime.datetime.now() >= deadline:
        candidate["classification"] = _CLASSIFICATION_UNCLASSIFIED
        continue
    # ... call _fetch_history(...) ...
```

**Pre-flight session-budget guard** (`pipeline/snapshot_drift.py:374-396`, mirrors `pipeline/orchestrate.py:683-685`):
```python
time_budget_minutes = _float_env("TIME_BUDGET_MINUTES", 0.0)
github_actions_mode = os.getenv("GITHUB_ACTIONS") == "true"
if time_budget_minutes and github_actions_mode:
    elapsed_min = (datetime.datetime.now() - session_start).total_seconds() / 60.0
    remaining_min = time_budget_minutes - elapsed_min
    if remaining_min < max_minutes:
        # degrade to unclassified for the WHOLE run, never stall it
        ...
```

**Never-raises classification wrapper** (`pipeline/snapshot_drift.py:285-355`): wrap each row's classification/attribution attempt in `try/except Exception:` → log a warning, mark unresolved, continue. Fits spec §5's "rows with conflicting evidence ... always left unresolved and listed."

**Isolation constraint (Pitfall 5, locked decision):** this script and its workflow are the ONLY place `client.Cells.get_cell_history` may be called for this feature — never inside `generate_weekly_pdfs.py` / `pipeline/orchestrate.py`, and never gated by an env-var flag read from the production script.

---

### `.github/workflows/cell-history-backfill.yml` (NEW)

**Analog:** `.github/workflows/weekly-excel-generation.yml` (823 lines; read 1-345 this session).

**Concurrency + schedule shape** (lines 14-22):
```yaml
concurrency:
  group: weekly-excel-${{ github.ref }}
  cancel-in-progress: false

on:
  schedule:
    - cron: '0 5 * * 1'      # adapt to Sat-midnight-Central / Sun 05:00Z
  workflow_dispatch:
    inputs:
      dry_run:
        description: 'Dry run (true/false)'
        required: false
        default: 'true'
        type: choice
        options: ['true','false']
```
Use a DISTINCT `concurrency.group` (e.g. `cell-history-backfill-${{ github.ref }}`) — never share the production workflow's group, or a slow backfill run would block/queue behind the production cron and vice versa.

**Job/env/secret-binding shape** (lines 121-145, 211-228):
```yaml
jobs:
  backfill:
    runs-on: ubuntu-latest
    timeout-minutes: <cap> # size for CELL_HISTORY_BACKFILL_MAX_MINUTES + margin
    env:
      PYTHONUNBUFFERED: 1
      GITHUB_ACTIONS: 'true'
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run cell-history backfill
        env:
          SMARTSHEET_API_TOKEN: ${{ secrets.SMARTSHEET_API_TOKEN }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: python scripts/backfill_cell_history_attribution.py ...
```

**Untrusted-input handling** (lines 186-210): if the workflow exposes a free-text `advanced_options`-style input, bind it to `env:` first (never interpolate `${{ }}` directly into `run:` shell text) — this is the injection-prevention pattern already established for `remediate_claimers`/etc.

**Backlog self-disable (Open Question #4, Claude's discretion):** no existing workflow in this repo checks "is there still work to do" before running — the new workflow needs a first step that queries the remaining-sentinel-row count (via the new script's own `--check-backlog`-style flag or a lightweight Supabase read) and skips/no-ops the rest of the job when zero. There is no direct analog for this specific gate; document the decision inline in the new workflow rather than inventing a shared helper.

---

### `billing_audit/schema.sql` (MODIFIED) + owner-deployed `backfill_attribution` RPC SQL

**Analog A — contract-as-comment wrapper pattern** (`billing_audit/schema.sql:173-257`, full read):
```sql
-- ── freeze_attribution (RPC) ────────────────────────────────
-- The ``freeze_attribution`` Postgres function is NOT defined
-- here — its body is deployed and maintained directly in the
-- Supabase project, because it includes business-logic
-- attribution rules that are owned by the data team rather
-- than the pipeline. The pipeline's contract with it is:
--
--   PARAMETERS (all named, p_<name>):
--     p_wr               TEXT
--     ...
--   RETURNS: ...
--
-- The exact body lives in Supabase. Do NOT rename or change
-- the parameter names without the corresponding update in
-- ``billing_audit/writer.py:freeze_row``.
```
Add a matching `-- ── backfill_attribution (RPC) ──` block documenting `p_rows jsonb` and the `updated | skipped_real_name | skipped_no_row` per-row return shape (spec §4), plus a note that `attribution_snapshot` gains two new columns (`backfill_source`, `backfill_run_id`) whose exact DDL is owner-applied (Pitfall 1 / Open Question #2 — do not assert the underlying table's exact write-side column names as fact in this comment; phrase it as a contract the RPC honors, same as the `freeze_attribution` block does).

**Analog B — the one ACTUALLY-DEFINED `jsonb_to_recordset` RPC in this codebase**, for the owner-deployed SQL file's real body (`pipeline_memory/schema.sql:244-330`, full read):
```sql
CREATE OR REPLACE FUNCTION pipeline_memory.upsert_rows_bulk(
    p_sheet_id BIGINT,
    p_run_id   TEXT,
    p_rows     JSONB
)
RETURNS TABLE (wr TEXT, week_ending DATE)
LANGUAGE plpgsql
VOLATILE
SET search_path = ''
AS $$
BEGIN
    RETURN QUERY
    WITH incoming AS (
        SELECT
            q.row_id, q.wr, q.week_ending, ...
        FROM jsonb_to_recordset(p_rows) AS q(
            row_id             BIGINT,
            wr                 TEXT,
            week_ending        DATE,
            ...
        )
    )
    ...
END;
$$;
```
Model the `backfill_attribution(p_rows jsonb)` RPC body (shipped as a file for Juan per Locked Decision #5, NOT applied by pipeline code) on this exact shape: explicit typed `jsonb_to_recordset(p_rows) AS q(...)` column list (ASVS V5, per `.claude/rules` + RESEARCH.md Security Domain), `LANGUAGE plpgsql`, `SET search_path = ''`, fully schema-qualified references, `GRANT EXECUTE ... TO service_role` only (mirror `billing_audit/schema.sql:287,332` — not re-read this session, cite by line per RESEARCH.md). The `UPDATE ... WHERE frozen_<role> IS NULL OR is-sentinel` guard must be server-side in this function body, never trusted to the Python caller.

**`public.artifacts` filename source (Source 3) — table already defined, read-only** (`supabase/portal_schema.sql:24-38`, full read):
```sql
CREATE TABLE IF NOT EXISTS public.artifacts (
    id              uuid        NOT NULL DEFAULT gen_random_uuid(),
    work_request    text        NOT NULL,
    week_ending     date        NOT NULL,
    week_ending_fmt text        NOT NULL,
    variant         text        NOT NULL,
    filename        text        NOT NULL,
    ...
);
```
The new script reads `filename` (`_User_<name>`, `_Helper_<name>`, `_VacCrew_<name>` tokens) for `(work_request, week_ending)` — no write needed to this table, and it lives in a DIFFERENT Supabase schema (`public`, portal-v2) than `billing_audit`/`pipeline_memory`.

---

### `pipeline/cleanup.py` (MODIFIED — CR-01 fix)

**Analog:** itself — the defect and its fix site are the same file (`pipeline/cleanup.py:89-116`, `495-508`, both fully read this session).

**Current (buggy) code** (`pipeline/cleanup.py:89-116`):
```python
def _is_sentinel_identifier(identifier: str | None) -> bool:
    if not identifier:
        return False
    # ... a real person's sanitized name never starts with '_', so a
    # leading underscore IS the sanitized '#' ...  [THIS ASSUMPTION IS FALSE]
    if identifier.startswith('_'):
        return True
    try:
        from billing_audit.writer import is_sentinel_claimer  # noqa: PLC0415
    except Exception:  # pragma: no cover - defensive: writer unavailable
        return False
    return bool(is_sentinel_claimer(identifier))
```

**Root cause chain (verified, do not re-derive):**
1. `pipeline/config.py:28`: `_RE_SANITIZE_HELPER_NAME = re.compile(r'[^\w\-]')`.
2. `pipeline/excel.py:308,324,389` (helper and primary suffix builders) call `_RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]` / `_RE_SANITIZE_IDENTIFIER.sub('_', _pf)[:50]` with **no `.strip()` first**.
3. A real name like `" O'Brien"` (leading space) or `"(Contractor) Smith"` sanitizes to a leading `_...`, and `_is_sentinel_identifier` (step above) then misclassifies it as a placeholder.
4. `pipeline/cleanup.py:495-508` gates the sentinel-superseded attachment-delete on `_is_sentinel_identifier(_identifier)` — so a real person's historical attachment can be silently deleted.

**Fix shape (per RESEARCH.md Pitfall 2 recommendation — either is acceptable, executor's call):** either (a) narrow the leading-`_` heuristic to known sanitized error spellings only (`_REF_`, `_INVALID`, `_NO_MATCH`, …) instead of any leading `_`, or (b) `.strip()` the raw name in `pipeline/excel.py` BEFORE sanitizing so a leading space never produces a leading `_` in the first place. Ship the fix + a regression test in the same PR (this file is in the protected attachment-cleanup path).

**Call site to preserve exactly (do not touch the surrounding gate logic)** (`pipeline/cleanup.py:495-508`):
```python
if (
    _identifier
    and ident not in valid_wr_weeks
    and _is_sentinel_identifier(_identifier)
    and any(
        _vw[0] == wr
        and _vw[1] == week
        and _vw[2] == variant
        and _vw[3]
        and not _is_sentinel_identifier(_vw[3])
        and _vw in _row_attached_idents
        for _vw in valid_wr_weeks
    )
):
```

---

### `tests/test_cleanup.py` (NEW — CR-01 regression)

**Analog:** `tests/test_sentinel_never_a_claimer.py` `SentinelPredicateTests` (lines 1-100+, full-class read).

**Structure to mirror:**
```python
"""... docstring naming the Phase/requirement, owner-approval date, and
defect this test guards against ..."""
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


class SentinelIdentifierPredicateTests(unittest.TestCase):
    def test_sentinel_family_is_recognised(self):
        from pipeline.cleanup import _is_sentinel_identifier
        for value in ("Unknown_Foreman", "_NO_MATCH", "_REF_", ...):
            with self.subTest(value=value):
                self.assertTrue(_is_sentinel_identifier(value))

    def test_real_names_with_leading_punctuation_are_not_sentinels(self):
        from pipeline.cleanup import _is_sentinel_identifier
        # CR-01 regression: a real name whose FIRST char sanitizes to
        # '_' (leading space, apostrophe, paren) must NOT be flagged.
        for value in ("_O_Brien", "_Contractor_Smith", ...):
            with self.subTest(value=value):
                self.assertFalse(_is_sentinel_identifier(value))
```
Use `self.subTest(value=value)` per-value iteration exactly like `test_sentinel_family_is_recognised` (lines 75-95) — this is the house convention for enumerated-input predicate tests in this codebase, not a table-driven `pytest.mark.parametrize` (this repo's tests are `unittest.TestCase`-style throughout, per RESEARCH.md Validation Architecture).

---

### `tests/test_backfill_claim_time_attribution.py` (NEW)

**Analog:** `tests/test_billing_audit_shadow.py` — `BackfillCliDateValidationTests` (2589-2727, full read) for CLI/argparse-shape assertions, and `_make_fake_supabase_client` / `_fake_rpc_response` (135-220, full read) for mocking the Supabase RPC chain without hitting a live project.

**Fake-client harness to reuse (import, do not re-implement — `Don't Hand-Roll` per RESEARCH.md):**
```python
from tests.test_billing_audit_shadow import (
    _fake_rpc_response,
    _make_fake_supabase_client,
    _reset_all,
)
```
`_make_fake_supabase_client` (lines 147-220) already builds the chained `client.schema('billing_audit').rpc(name, params).execute()` mock shape the new script's `backfill_attribution` RPC call needs, plus the `.table(...).select(...).eq(...).execute()` chain for any `attribution_snapshot` reads the dry-run report performs.

**Grep-level source assertions for CLI contract shape** — mirror this exact idiom (`tests/test_billing_audit_shadow.py:31-47, 2624-2661`):
```python
def _read_source(relpath: str) -> str:
    return (_REPO_ROOT / relpath).read_text(encoding="utf-8")

def _collapse_ws(text: str) -> str:
    import re
    return re.sub(r"\s+", " ", text).strip()

# usage:
src = _read_source("scripts/backfill_claim_time_attribution.py")
collapsed = _collapse_ws(src)
self.assertRegex(collapsed, r"if\s+errored\s+or\s+local_exceptions\s*:")
```
Use this for asserting: (a) `--dry-run` defaults ON, (b) `--apply` requires `--i-approved-this`, (c) no source in the script's precedence list performs a cross-week lookup (grep for the literal string `last_known_before_week` must find ZERO matches — Pitfall 3's explicit warning sign), (d) the RPC call is never issued for a row whose fixture shows a non-sentinel `frozen_<role>` already present (never-overwrite-a-real-name).

**WR 19073866 known-good-sample fixture (OWN-03 dry-run correctness, per RESEARCH.md Phase Requirements → Test Map):** build a small fixture module/dict simulating sources 1-4 for WR 19073866, weeks 082425/083125/091425/092125, expecting `_User_Avery_Example` resolved via `backfill_hash_history` — assert the dry-run report's proposed name/source match.

---

### WR-01 structural test (lives in `tests/test_backfill_claim_time_attribution.py` or a small dedicated file)

**Analog:** `tests/test_billing_audit_shadow.py:2617-2638` `test_backfill_splits_dotenv_import_error_from_runtime_error` — same `_read_source` + `_collapse_ws` + `assertRegex` idiom, applied to `pipeline/orchestrate.py` instead.

**Guarded lazy-import pattern to assert against** (`pipeline/discovery.py:75-83`, full context read):
```python
def _fetch_folder_recursive(fid, depth=0, max_depth=5):
    ...
    try:
        with sentry_sdk.start_span(...) as span:
            from smartsheet.models.sheet import Sheet as _SmartsheetSheet
            from smartsheet.models.folder import Folder as _SmartsheetFolder
            ...
```
Currently `pipeline/orchestrate.py:43-45` imports `AttachmentParentType` at MODULE TOP LEVEL:
```python
from smartsheet.models.enums.attachment_parent_type import (
    AttachmentParentType,
)
```
used only inside `_is_row_attachment` (`pipeline/orchestrate.py:1282-1297`). The WR-01 fix moves this import to be function-local (inside `_is_row_attachment`, mirroring `discovery.py`'s function-local `from smartsheet.models.X import Y` pattern) so a module import-order/circular-import issue at top-level cannot break the whole orchestrate module for an enum used in exactly one narrow helper. Test asserts (grep-level, mirroring the cited test) that the top-level `from smartsheet.models.enums.attachment_parent_type import` line is GONE from the module preamble and a local import exists inside `_is_row_attachment`'s body.

---

## Shared Patterns

### Sentinel detection — single source of truth
**Source:** `billing_audit/writer.py:96-115` (`_SENTINEL_CLAIMERS` frozenset + `is_sentinel_claimer`)
**Apply to:** `scripts/backfill_claim_time_attribution.py` (never treat a sentinel as a valid backfill target's *current* value — only overwrite when current is sentinel), `pipeline/cleanup.py` CR-01 fix (imports this lazily already — keep doing so, do not reimplement).
```python
_SENTINEL_CLAIMERS: frozenset[str] = frozenset({
    "unknown foreman", "unknown", "unknown helper",
    "unknown vac crew", "no match",
})

def is_sentinel_claimer(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text or text.startswith("#"):
        return True
    normalized = " ".join(text.replace("_", " ").split()).casefold()
    return normalized in _SENTINEL_CLAIMERS
```

### WR sanitization — single source of truth
**Source:** `billing_audit/writer.py:77` (`_WR_SANITIZE = re.compile(r"[^\w\-]")`), used at `writer.py:869` (`_WR_SANITIZE.sub("_", str(wr).split(".")[0])[:50]`)
**Apply to:** `scripts/backfill_claim_time_attribution.py`'s source-3 (`public.artifacts` filename) matching and any WR-keyed lookups — reuse this compiled regex/pattern rather than writing a second sanitizer (RESEARCH.md `Don't Hand-Roll`: "Two independently-maintained sanitizers is the root cause of both CR-01 and the earlier PR #375 helper-path week-key miss").

### Reading frozen attribution — RPC contract, never raw `supabase.table(...)`
**Source:** `billing_audit/writer.py:824-908` (`_lookup_attribution_all`), `910-1056` (`prefetch_attribution`)
**Apply to:** the new backfill script's dry-run report generation (source 2 — "non-sentinel `attribution_snapshot` rows for the same row") should call these existing readers, not hand-roll a `.table("attribution_snapshot").select(...)` query — the RPC already normalizes `#`-tokens/blanks to NULL server-side.
```python
row, status = _lookup_attribution_all(wr, week_ending, row_id)
# status in {"success", "no_row", "fetch_failure", "unavailable"}
```

### Owner-deployed Supabase DDL/RPC — contract-as-comment, never applied by pipeline code
**Source:** `billing_audit/schema.sql:173-257`
**Apply to:** `billing_audit/schema.sql`'s new `backfill_attribution` comment block, and the owner-deployed SQL file itself (ships as a PR artifact for Juan to paste into the Supabase SQL editor — see Locked Decision #5). Never let any Python code in this PR execute `CREATE FUNCTION`/`ALTER TABLE` DDL at runtime.

### Rate-limited external API calls — self-pace, cap, deadline, never a bespoke retry loop
**Source:** `pipeline/snapshot_drift.py:82-97, 371-438`
**Apply to:** `scripts/backfill_cell_history_attribution.py` (Source 5) exclusively — this is the only new file that calls a rate-limited external API (`smartsheet-python-sdk`'s `client.Cells.get_cell_history`). Rely on the SDK's built-in 429 handling; do not add custom retry loops (`.claude/rules/smartsheet-python-optimization.md` §1).

### Grep-on-source structural tests for CLI/import-shape contracts
**Source:** `tests/test_billing_audit_shadow.py:31-47` (`_read_source`, `_collapse_ws`)
**Apply to:** `tests/test_backfill_claim_time_attribution.py` (CLI flag defaults, precedence rules, no-cross-week-lookup) and the WR-01 structural test — whichever file houses it.

---

## No Analog Found

None — every file in scope has at least a role-match analog (see table above). The one partial gap is the Source-5 workflow's "backlog exists" self-disable mechanism (Open Question #4): no existing workflow in this repo implements a comparable pre-flight backlog check, so that specific step must be designed fresh (documented inline above under the workflow's Pattern Assignment rather than listed here, since the surrounding workflow shape does have a strong analog).

## Metadata

**Analog search scope:** `scripts/`, `pipeline/`, `pipeline_memory/`, `billing_audit/`, `.github/workflows/`, `tests/`, `supabase/` (targeted `Read`/`Grep` — no bulk directory scan)
**Files scanned (read or grepped this session):** `scripts/backfill_attribution_snapshot.py` (full), `pipeline/snapshot_drift.py` (imports + lines 82-99, 280-438), `billing_audit/writer.py` (85-220, 520-670, 824-960, 1058-1146), `pipeline/cleanup.py` (1-130, 480-520), `pipeline/config.py` (25-31), `pipeline/excel.py` (85-130, 295-400), `pipeline/orchestrate.py` (1-55, 400-432, 1270-1304), `pipeline/discovery.py` (imports, 60-99, 320-333), `billing_audit/schema.sql` (160-260), `pipeline_memory/schema.sql` (30-330), `.github/workflows/weekly-excel-generation.yml` (1-345), `tests/test_billing_audit_shadow.py` (1-55, 135-220, 2589-2727), `tests/test_sentinel_never_a_claimer.py` (1-100), `supabase/portal_schema.sql` (20-51)
**Pattern extraction date:** 2026-09-02
