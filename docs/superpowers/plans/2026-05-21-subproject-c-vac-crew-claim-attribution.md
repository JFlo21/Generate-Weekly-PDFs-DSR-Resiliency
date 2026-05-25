# Sub-project C — VAC Crew Claim Attribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-partition `vac_crew` Excel files by the frozen vac-crew claimer (`frozen_vac_crew` via Foundation A `resolve_claimer`), naming each file `_VacCrew_<name>`, with HOLD-on-outage and one-time legacy migration — mirroring Sub-project B.

**Architecture:** A bounded `ThreadPoolExecutor` pre-pass resolves each completed vac_crew row's frozen claimer into a `{__row_id: ResolveOutcome}` map before `group_source_rows`' grouping loop (no per-row Supabase I/O in the hot loop). The vac_crew emission then partitions the single `{week}_{wr}_VACCREW` group into per-claimer `{week}_{wr}_VACCREW_{claimer}` groups. Identity is kept consistent across the four CR-01 sites (group key, `valid_wr_weeks`, `current_keys`, `build_group_identity`). A default-on kill switch reverts to exact legacy behavior; a separate default-on switch gates the destructive legacy-attachment cleanup. `billing_audit/` is NOT modified.

**Tech Stack:** Python 3.10+, `openpyxl`, Smartsheet SDK, `concurrent.futures.ThreadPoolExecutor`, `unittest`/`pytest`, Supabase (via the existing `billing_audit` package). Spec: `docs/superpowers/specs/2026-05-21-subproject-c-vac-crew-claim-attribution-design.md`.

**Reference implementation (real, in-repo):** Sub-project B's now-merged code is the closest analog for nearly every task. Concrete templates to read while implementing:
- `_subcontractor_primary_variant_suffix` (filename suffix helper, raises on empty claimer)
- the `_sub_primary_claimer_map` pre-pass + the `reduced_sub`/`aep_billable` emission block in `group_source_rows`
- the `reduced_sub`/`aep_billable` branches in `build_group_identity` (reserved-token-first, span-join)
- `_run_subproject_b_hash_prune` + `_build_subcontractor_wr_scope` + the `_hash_history_migration_dirty` save path
- the `sub_legacy_primary_variants` gate in `cleanup_untracked_sheet_attachments`

---

## File Structure

- **Modify `generate_weekly_pdfs.py`** (the engine — all logic):
  - Config constants near the other attribution flags (search `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED`).
  - Startup banner block (search the banner that prints `RATE_RECALC_WEEKLY_FALLBACK` / attribution-flag state).
  - `build_group_identity` — `VacCrew` parse branch (currently ~line 2650).
  - New module-level `_vac_crew_variant_suffix(...)` helper near `_subcontractor_primary_variant_suffix`.
  - `group_source_rows` — new vac_crew pre-pass + the `if is_vac_crew_row:` emission block (currently ~line 4943) + the `valid_wr_weeks` builder + the `current_keys` builder.
  - `generate_excel` — vac_crew filename `variant_suffix` (~line 5855) + the vac_crew display branch (~line 6029).
  - `_build_vac_crew_wr_scope(groups)` near `_build_subcontractor_wr_scope`.
  - `cleanup_untracked_sheet_attachments` — new vac_crew legacy-cleanup gate.
  - `_run_vac_crew_hash_prune(...)` + `VAC_CREW_HASH_PRUNE_VERSION` constant + `_vac_crew_prune_version` sentinel; call site near the B prune call (~line 7262); `_hash_history_migration_dirty` wiring.
  - `_PII_LOG_MARKERS` — add the prune marker.
- **Create `tests/test_vac_crew_claim_attribution.py`** — all C tests (true end-to-end).
- **Modify `.github/workflows/weekly-excel-generation.yml`** — pin the two new env vars.
- **Modify `website/docs/reference/environment.md`** — document the two new env vars.
- **Modify `CLAUDE.md`** — Living Ledger entry.

**Test imports note:** mirror the B test file header. `tests/test_subcontractor_primary_claim_attribution.py` imports `_ensure_smartsheet_mocked, _reset_all` from `tests.test_billing_audit_shadow`, calls `_ensure_smartsheet_mocked()` before `import generate_weekly_pdfs`, and imports `ResolveOutcome` from `billing_audit.writer`. Reuse that exact pattern.

---

## Task 1: Config — kill switches + startup banner + workflow pin

**Files:**
- Modify: `generate_weekly_pdfs.py` (config block + startup banner)
- Modify: `.github/workflows/weekly-excel-generation.yml`
- Test: `tests/test_vac_crew_claim_attribution.py`

- [ ] **Step 1: Write the failing test** (create the file with the B-style header)

```python
"""Sub-project C — VAC Crew claim attribution tests.

Drives real production code paths (parser, group_source_rows pre-pass +
emission, generate_excel, migration cleanup, hash prune, HOLD wiring) per
the [2026-05-20 00:26] rule 4: row-flow changes require TRUE end-to-end
tests, not static mirrors.
"""
from __future__ import annotations

import inspect
import pathlib
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.test_billing_audit_shadow import _ensure_smartsheet_mocked, _reset_all

_ensure_smartsheet_mocked()
import generate_weekly_pdfs  # noqa: E402
from billing_audit.writer import ResolveOutcome  # noqa: E402


class TestVacCrewConfigFlags(unittest.TestCase):
    def test_attribution_flag_exists_and_is_bool_default_on(self):
        self.assertIsInstance(
            generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED, bool
        )

    def test_legacy_cleanup_flag_exists_and_is_bool(self):
        self.assertIsInstance(
            generate_weekly_pdfs.VAC_CREW_LEGACY_CLEANUP_ENABLED, bool
        )

    def test_flags_pinned_in_workflow(self):
        wf = (_REPO_ROOT / ".github/workflows/weekly-excel-generation.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("VAC_CREW_CLAIM_ATTRIBUTION_ENABLED", wf)
        self.assertIn("VAC_CREW_LEGACY_CLEANUP_ENABLED", wf)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vac_crew_claim_attribution.py::TestVacCrewConfigFlags -v`
Expected: FAIL — `AttributeError: module 'generate_weekly_pdfs' has no attribute 'VAC_CREW_CLAIM_ATTRIBUTION_ENABLED'`.

- [ ] **Step 3: Add the constants** (next to `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED`; reuse the same truthy parse)

```python
VAC_CREW_CLAIM_ATTRIBUTION_ENABLED = os.getenv(
    'VAC_CREW_CLAIM_ATTRIBUTION_ENABLED', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')

VAC_CREW_LEGACY_CLEANUP_ENABLED = os.getenv(
    'VAC_CREW_LEGACY_CLEANUP_ENABLED', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')
```

- [ ] **Step 4: Surface in the startup banner** (in the same block that logs the other attribution/recalc flag states)

```python
logging.info(
    f"🚐 VAC Crew claim attribution: "
    f"{'ENABLED' if VAC_CREW_CLAIM_ATTRIBUTION_ENABLED else 'DISABLED'}; "
    f"legacy cleanup: "
    f"{'ENABLED' if VAC_CREW_LEGACY_CLEANUP_ENABLED else 'DISABLED'}"
)
```

- [ ] **Step 5: Pin in the workflow** (`.github/workflows/weekly-excel-generation.yml`, in the `env:` block of the `core` job alongside `SUBCONTRACTOR_*`)

```yaml
      VAC_CREW_CLAIM_ATTRIBUTION_ENABLED: '1'
      VAC_CREW_LEGACY_CLEANUP_ENABLED: '1'
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_vac_crew_claim_attribution.py::TestVacCrewConfigFlags -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_vac_crew_claim_attribution.py .github/workflows/weekly-excel-generation.yml
git commit -m "feat(vac-crew): add VAC_CREW_* kill switches + banner + workflow pin"
```

---

## Task 2: Filename suffix helper + parser (`build_group_identity`)

**Files:**
- Modify: `generate_weekly_pdfs.py` (new `_vac_crew_variant_suffix`; `build_group_identity` VacCrew branch)
- Test: `tests/test_vac_crew_claim_attribution.py`

- [ ] **Step 1: Write the failing tests**

```python
class TestVacCrewSuffixAndParser(unittest.TestCase):
    def test_suffix_embeds_name(self):
        self.assertEqual(
            generate_weekly_pdfs._vac_crew_variant_suffix('John Smith', '91467680', '041926'),
            '_VacCrew_John_Smith',
        )

    def test_suffix_empty_claimer_raises(self):
        with self.assertRaises(ValueError):
            generate_weekly_pdfs._vac_crew_variant_suffix('', '91467680', '041926')

    def test_parser_vaccrew_name_round_trips(self):
        fname = 'WR_91467680_WeekEnding_041926_120000_VacCrew_John_Smith_abc123.xlsx'
        self.assertEqual(
            generate_weekly_pdfs.build_group_identity(fname),
            ('91467680', '041926', 'vac_crew', 'John_Smith'),
        )

    def test_parser_name_containing_helper_token_stays_vac_crew(self):
        # A crew member whose name contains 'Helper' must NOT misparse as a
        # helper variant — VacCrew is checked before the Helper scan.
        fname = 'WR_91467680_WeekEnding_041926_120000_VacCrew_Pat_Helper_abc123.xlsx'
        self.assertEqual(
            generate_weekly_pdfs.build_group_identity(fname),
            ('91467680', '041926', 'vac_crew', 'Pat_Helper'),
        )

    def test_parser_legacy_vaccrew_no_name(self):
        fname = 'WR_91467680_WeekEnding_041926_120000_VacCrew_abc123.xlsx'
        self.assertEqual(
            generate_weekly_pdfs.build_group_identity(fname),
            ('91467680', '041926', 'vac_crew', ''),
        )
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_vac_crew_claim_attribution.py::TestVacCrewSuffixAndParser -v`
Expected: FAIL — `_vac_crew_variant_suffix` missing; `test_parser_name_containing_helper_token_stays_vac_crew` returns `('91467680','041926','helper','Pat')` (current Helper-first order); `test_parser_vaccrew_name_round_trips` returns identifier `''`.

- [ ] **Step 3: Add the suffix helper** (near `_subcontractor_primary_variant_suffix`)

```python
def _vac_crew_variant_suffix(claimer: str, wr_num: str, week_end_raw: str) -> str:
    """Build the filename suffix for a per-claimer VAC crew file.

    Sub-project C (2026-05-21): vac_crew files are partitioned by frozen
    vac-crew claimer and named ``_VacCrew_<sanitized name>``. Raises on an
    empty claimer (production never hits this — the emission falls back to
    'Unknown'); the raise surfaces data drift instead of an ambiguous name.
    """
    if not claimer:
        logging.error(
            f"⚠️ vac_crew variant row missing claimer for WR {wr_num} "
            f"week {week_end_raw}; filename would be ambiguous — raising."
        )
        raise ValueError(
            f"vac_crew requires a non-empty claimer; got empty for "
            f"WR={wr_num} week={week_end_raw}"
        )
    return f"_VacCrew_{_RE_SANITIZE_IDENTIFIER.sub('_', claimer)[:50]}"
```

- [ ] **Step 4: Reorder + extend the parser** — in `build_group_identity`, MOVE the `elif 'VacCrew' in tail:` branch ABOVE the `elif 'Helper' in tail:` branch and extract the name via span-join:

```python
    elif 'VacCrew' in tail:
        # Sub-project C: _VacCrew_<name>_<hash>. Checked BEFORE the 'Helper'
        # scan so a crew name containing the 'Helper' token isn't
        # misclassified as a helper variant (B round-7 lesson). Span-join so
        # an underscored name survives. Legacy _VacCrew (no name) → ''.
        variant = 'vac_crew'
        vac_idx_rel = tail.index('VacCrew')
        identifier = '_'.join(tail[vac_idx_rel + 1:-1])
```

(Delete the old `elif 'VacCrew' in tail: variant='vac_crew'; identifier=''` block at its previous position. Leave the `Helper` and `User` branches intact.)

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest tests/test_vac_crew_claim_attribution.py::TestVacCrewSuffixAndParser -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Run the full build_group_identity regression set** (ensure no other variant regressed)

Run: `python -m pytest tests/test_subcontractor_primary_claim_attribution.py tests/test_security_audit_followup.py -q`
Expected: PASS (no regressions in helper/primary/aep/reduced parsing).

- [ ] **Step 7: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_vac_crew_claim_attribution.py
git commit -m "feat(vac-crew): _VacCrew_<name> suffix + parser (VacCrew before Helper)"
```

---

## Task 3: Pre-pass — resolve frozen claimers into a map

**Files:**
- Modify: `generate_weekly_pdfs.py` (`group_source_rows`, before the grouping loop)
- Test: `tests/test_vac_crew_claim_attribution.py`

Read the B pre-pass (`_sub_primary_claimer_map`) as the exact template. The vac_crew pre-pass resolves only completed vac_crew rows.

- [ ] **Step 1: Write the failing test**

```python
def _make_vac_row(row_id=6001, wr='91467680', name='CurrentCrew', snapshot='2026-04-19'):
    return {
        '__row_id': row_id,
        'Work Request #': wr,
        'Weekly Reference Logged Date': '2026-04-19',
        'Snapshot Date': snapshot,
        'Units Completed?': True,
        'Units Total Price': '$100.00',
        'CU': 'ANC-M', 'Work Type': 'Inst', 'Quantity': 2,
        '__effective_user': 'PrimaryForeman',
        '__is_helper_row': False, '__helper_foreman': '', '__helper_dept': '', '__helper_job': '',
        '__is_vac_crew': True,
        '__vac_crew_name': name, '__vac_crew_dept': '700', '__vac_crew_job': 'VJ-1',
        '__source_sheet_id': 8162920222379908,
    }


class TestVacCrewPrePassConcurrency(unittest.TestCase):
    def setUp(self):
        _reset_all()
        self._orig = generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED
        generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED = True

    def tearDown(self):
        generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED = self._orig
        _reset_all()

    def test_fifty_rows_each_partition_to_their_own_claimer(self):
        def _resolve(variant, current, *, wr, week_ending, row_id, enabled):
            return ResolveOutcome('use', f'Crew{row_id}', 'frozen', 'success')
        rows = [_make_vac_row(row_id=7000 + i) for i in range(50)]
        with mock.patch('billing_audit.writer.resolve_claimer', side_effect=_resolve):
            groups = generate_weekly_pdfs.group_source_rows(rows)
        keys = list(groups.keys())
        for i in range(50):
            self.assertTrue(
                any(f'VACCREW_Crew{7000 + i}' in k for k in keys),
                f"row {7000+i} must partition to its own claimer; got {keys[:5]}…",
            )
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_vac_crew_claim_attribution.py::TestVacCrewPrePassConcurrency -v`
Expected: FAIL — keys are the single legacy `…_VACCREW` (no per-claimer suffix) because emission isn't wired yet. (This test goes green at the end of Task 4; it is RED now to lock the contract.)

- [ ] **Step 3: Add the pre-pass** — in `group_source_rows`, BEFORE the per-row grouping loop (mirror the B `_sub_primary_claimer_map` block exactly, swapping the predicate and variant):

```python
    # Sub-project C: resolve frozen vac-crew claimers for completed vac_crew
    # rows in a bounded pre-pass (NO Supabase I/O inside the grouping loop —
    # [2026-05-21 09:21] rule 2). Map: {__row_id: ResolveOutcome}. Only runs
    # when attribution is enabled; otherwise the emission uses the legacy key.
    _vac_crew_claimer_map: dict = {}
    if VAC_CREW_CLAIM_ATTRIBUTION_ENABLED:
        _vac_rows = [
            r for r in source_rows
            if r.get('__is_vac_crew')
            and r.get('__row_id') is not None
        ]
        if _vac_rows:
            from billing_audit.writer import resolve_claimer

            def _resolve_one(_r):
                _we = _r.get('__week_ending_date')
                _we = _we.date() if isinstance(_we, datetime.datetime) else _we
                return _r.get('__row_id'), resolve_claimer(
                    'vac_crew',
                    _r.get('__vac_crew_name') or '',
                    wr=str(_r.get('Work Request #', '')).split('.')[0],
                    week_ending=_we,
                    row_id=_r.get('__row_id'),
                    enabled=VAC_CREW_CLAIM_ATTRIBUTION_ENABLED,
                )

            if len(_vac_rows) <= 1:
                for _r in _vac_rows:
                    try:
                        _rid, _out = _resolve_one(_r)
                        _vac_crew_claimer_map[_rid] = _out
                    except Exception:
                        logging.exception("⚠️ Sub-project C: vac claimer pre-pass row failed")
            else:
                from concurrent.futures import ThreadPoolExecutor, as_completed
                _workers = min(PARALLEL_WORKERS, len(_vac_rows))
                with ThreadPoolExecutor(max_workers=_workers) as _ex:
                    _futs = [_ex.submit(_resolve_one, _r) for _r in _vac_rows]
                    for _f in as_completed(_futs):
                        try:
                            _rid, _out = _f.result()
                            _vac_crew_claimer_map[_rid] = _out
                        except Exception:
                            logging.exception("⚠️ Sub-project C: vac claimer pre-pass row failed")
```

> Note: confirm the source-rows parameter name in `group_source_rows` (the B pre-pass iterates the same input list — match it). Confirm `__week_ending_date` is present on rows at this point (it is set during fetch and used downstream); if the per-row week is derived differently in this function, mirror exactly how the B pre-pass obtained `week_ending`.

- [ ] **Step 4: (no standalone run yet)** — the pre-pass populates the map but emission (Task 4) consumes it. Proceed to Task 4; this test is verified green at Task 4 Step 6.

- [ ] **Step 5: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_vac_crew_claim_attribution.py
git commit -m "feat(vac-crew): parallel pre-pass resolving frozen vac claimers"
```

---

## Task 4: Emission — partition by claimer (Site 1) with kill-switch + HOLD

**Files:**
- Modify: `generate_weekly_pdfs.py` (`group_source_rows`, the `if is_vac_crew_row:` block, currently ~4943)
- Test: `tests/test_vac_crew_claim_attribution.py`

- [ ] **Step 1: Write the failing tests**

```python
class TestVacCrewEmission(unittest.TestCase):
    def setUp(self):
        _reset_all()
        self._orig = generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED
        generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED = True

    def tearDown(self):
        generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED = self._orig
        _reset_all()

    def test_frozen_claimer_partitions(self):
        with mock.patch('billing_audit.writer.resolve_claimer',
                        return_value=ResolveOutcome('use', 'FrozenCrew', 'frozen', 'success')):
            groups = generate_weekly_pdfs.group_source_rows([_make_vac_row()])
        self.assertTrue(any('VACCREW_FrozenCrew' in k for k in groups))

    def test_no_history_falls_back_to_current_name(self):
        with mock.patch('billing_audit.writer.resolve_claimer',
                        return_value=ResolveOutcome('use', 'CurrentCrew', 'current', 'no_history')):
            groups = generate_weekly_pdfs.group_source_rows([_make_vac_row(name='CurrentCrew')])
        self.assertTrue(any('VACCREW_CurrentCrew' in k for k in groups))

    def test_hold_suppresses_and_records(self):
        from billing_audit.writer import get_counters
        with mock.patch('billing_audit.writer.resolve_claimer',
                        return_value=ResolveOutcome('hold', None, None, 'fetch_failure')):
            groups = generate_weekly_pdfs.group_source_rows([_make_vac_row()])
        self.assertFalse(any('VACCREW' in k for k in groups))
        self.assertEqual(get_counters()['attribution_rows_held'], 1)

    def test_disabled_emits_exact_legacy_key(self):
        generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED = False
        with mock.patch('billing_audit.writer.resolve_claimer') as m:
            groups = generate_weekly_pdfs.group_source_rows([_make_vac_row(name='CurrentCrew')])
            m.assert_not_called()
        self.assertIn('041926_91467680_VACCREW', groups)
        self.assertFalse(any('VACCREW_' in k for k in groups))  # no claimer suffix

    def test_map_miss_uses_current_name_not_hold(self):
        # __row_id absent → not in map → use current, never HOLD.
        from billing_audit.writer import get_counters
        row = _make_vac_row()
        del row['__row_id']
        with mock.patch('billing_audit.writer.resolve_claimer',
                        return_value=ResolveOutcome('use', 'X', 'frozen', 'success')):
            groups = generate_weekly_pdfs.group_source_rows([row])
        self.assertTrue(any('VACCREW_CurrentCrew' in k for k in groups))
        self.assertEqual(get_counters()['attribution_rows_held'], 0)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_vac_crew_claim_attribution.py::TestVacCrewEmission -v`
Expected: FAIL — current emission always produces the single `…_VACCREW` key; no partitioning, no HOLD.

- [ ] **Step 3: Replace the `if is_vac_crew_row:` block** with the kill-switch-gated, map-consuming version:

```python
            if is_vac_crew_row:
                if not VAC_CREW_CLAIM_ATTRIBUTION_ENABLED:
                    # Kill switch OFF → exact legacy behavior: one group per
                    # WR+week, no per-claimer partition.
                    vac_crew_key = f"{week_end_for_key}_{wr_key}_VACCREW"
                    vac_crew_foreman = r.get('__vac_crew_name') or effective_user
                    keys_to_add.append(('vac_crew', vac_crew_key, vac_crew_foreman))
                    if vac_crew_key not in groups:
                        logging.info(f"🏗️ VAC CREW GROUP CREATED: WR={wr_key}, Week={week_end_for_key}")
                else:
                    # Sub-project C: partition by frozen vac-crew claimer.
                    _vac_current = r.get('__vac_crew_name') or effective_user
                    _c_vac_claimer = None
                    _vac_outcome = _vac_crew_claimer_map.get(r.get('__row_id'))
                    if _vac_outcome is not None and _vac_outcome.action == 'hold':
                        _c_vac_claimer = None  # defer — correctness over availability
                        try:
                            from billing_audit.writer import record_attribution_hold
                            record_attribution_hold(
                                wr_key,
                                week_ending_date.date()
                                if isinstance(week_ending_date, datetime.datetime)
                                else week_ending_date,
                                'vac_crew',
                            )
                        except Exception:
                            logging.exception("⚠️ Sub-project C: record_attribution_hold failed")
                    elif _vac_outcome is not None and _vac_outcome.action == 'use':
                        _c_vac_claimer = _vac_outcome.name or _vac_current or 'Unknown'
                    else:
                        # map-miss / disabled / no_history default → use current
                        _c_vac_claimer = _vac_current or 'Unknown'

                    if _c_vac_claimer is not None:
                        _c_vac_sanitized = _RE_SANITIZE_IDENTIFIER.sub('_', _c_vac_claimer)[:50]
                        vac_crew_key = f"{week_end_for_key}_{wr_key}_VACCREW_{_c_vac_sanitized}"
                        keys_to_add.append(('vac_crew', vac_crew_key, _c_vac_claimer))
                        if vac_crew_key not in groups:
                            logging.info(f"🏗️ VAC CREW GROUP CREATED: WR={wr_key}, Week={week_end_for_key}")
```

> `week_ending_date` must be in scope here exactly as it is at the B HOLD call site; if this block uses `week_end_for_key`/another local for the week, obtain the `datetime`/`date` the same way B's vac-adjacent emission does. Keep `('vac_crew', ...)` as the variant tag so `r_copy['__variant']` stays `'vac_crew'` and `__current_foreman` becomes the claimer.

- [ ] **Step 4: Run the emission tests**

Run: `python -m pytest tests/test_vac_crew_claim_attribution.py::TestVacCrewEmission -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the pre-pass test (now green)**

Run: `python -m pytest tests/test_vac_crew_claim_attribution.py::TestVacCrewPrePassConcurrency -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_vac_crew_claim_attribution.py
git commit -m "feat(vac-crew): partition emission by frozen claimer + HOLD + legacy switch"
```

---

## Task 5: Sites 2 & 3 (valid_wr_weeks + current_keys) + generate_excel display/filename

**Files:**
- Modify: `generate_weekly_pdfs.py` (`valid_wr_weeks` builder; `current_keys` builder; `generate_excel` filename suffix + display branch)
- Test: `tests/test_vac_crew_claim_attribution.py`

- [ ] **Step 1: Write the failing tests**

```python
class TestVacCrewIdentitySitesAndDisplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._src = pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')

    def test_current_keys_site_carries_vac_claimer(self):
        # Site 3: the hash-prune current_keys reconstruction must derive the
        # vac_crew identifier from __current_foreman, not hard-code ''.
        self.assertNotRegex(
            self._src,
            r"_variant == 'vac_crew':\s*\n\s*_ident = ''",
            "current_keys must derive vac_crew identifier from the claimer",
        )

    def test_generate_excel_vac_crew_file_named_by_claimer(self):
        import datetime as dt, tempfile, os, openpyxl
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        orig = generate_weekly_pdfs.OUTPUT_FOLDER
        generate_weekly_pdfs.OUTPUT_FOLDER = tmp.name
        self.addCleanup(lambda: setattr(generate_weekly_pdfs, 'OUTPUT_FOLDER', orig))
        row = {
            'Work Request #': '91467680', 'Units Completed?': True,
            'Units Total Price': '$100.00', 'Customer Name': 'Cust',
            'Dept #': '500', 'Job #': 'J-1', 'CU': 'ANC-M', 'Work Type': 'Inst', 'Quantity': 2,
            '__variant': 'vac_crew', '__current_foreman': 'FrozenCrew',
            '__vac_crew_name': 'CurrentCrew', '__vac_crew_dept': '700', '__vac_crew_job': 'VJ-1',
            '__week_ending_date': dt.datetime(2026, 4, 19),
        }
        result = generate_weekly_pdfs.generate_excel(
            '041926_91467680_VACCREW_FrozenCrew', [row], dt.datetime(2026, 4, 19),
            data_hash='deadbeefcafe0c01',
        )
        excel_path, filename = result[0], result[1]
        self.assertIn('_VacCrew_FrozenCrew', filename)
        wb = openpyxl.load_workbook(excel_path)
        ws = wb.active
        foreman = next(
            (ws.cell(row=r, column=7).value for r in range(1, ws.max_row + 1)
             if ws.cell(row=r, column=6).value == 'Foreman:'),
            None,
        )
        self.assertEqual(foreman, 'FrozenCrew')  # display = attributed claimer
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_vac_crew_claim_attribution.py::TestVacCrewIdentitySitesAndDisplay -v`
Expected: FAIL — `current_keys` still hard-codes `_ident=''` for vac_crew; `generate_excel` filename is `_VacCrew` (no name) and display foreman uses `__vac_crew_name` (`'CurrentCrew'`).

- [ ] **Step 3: Fix Site 2 (`valid_wr_weeks` builder).** Find where `valid_wr_weeks.add((...))` is built per variant. For vac_crew it currently contributes identifier `''`. Change it to the sanitized claimer:

```python
                elif _variant == 'vac_crew':
                    _vc = group_rows[0].get('__current_foreman', '')
                    _ident = _RE_SANITIZE_IDENTIFIER.sub('_', _vc)[:50] if _vc else ''
```

(Match the exact surrounding shape of the existing per-variant `if/elif` in the `valid_wr_weeks` builder.)

- [ ] **Step 4: Fix Site 3 (`current_keys` builder).** In the hash-prune `current_keys` block, the `elif _variant == 'vac_crew': _ident = ''` becomes:

```python
                        elif _variant == 'vac_crew':
                            # Subproject C identity site (Site 3). Must match
                            # the history_key written at Site 1 (sanitized
                            # claimer) or the fresh entry is treated as stale.
                            _vc = group_rows[0].get('__current_foreman', '')
                            _ident = (
                                _RE_SANITIZE_IDENTIFIER.sub('_', _vc)[:50]
                                if _vc else ''
                            )
```

- [ ] **Step 5: Fix `generate_excel` filename suffix** (the `variant_suffix = '_VacCrew'` line):

```python
        variant_suffix = _vac_crew_variant_suffix(
            first_row.get('__current_foreman') or first_row.get('__vac_crew_name', ''),
            wr_num, week_end_raw,
        )
```

- [ ] **Step 6: Fix `generate_excel` vac_crew display branch** — foreman = the claimer (`__current_foreman`), dept/job stay from vac fields:

```python
    elif variant == 'vac_crew':
        # Per-claimer (Sub-project C): show the ATTRIBUTED claimer
        # (__current_foreman, the partition key), with VAC-specific dept/job.
        display_foreman = first_row.get('__current_foreman') or first_row.get('__vac_crew_name', 'Unknown VAC Crew')
        display_dept = first_row.get('__vac_crew_dept', '')
        display_job = first_row.get('__vac_crew_job', '')
```

- [ ] **Step 7: Run to verify pass**

Run: `python -m pytest tests/test_vac_crew_claim_attribution.py::TestVacCrewIdentitySitesAndDisplay -v`
Expected: PASS (2 tests).

- [ ] **Step 8: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_vac_crew_claim_attribution.py
git commit -m "feat(vac-crew): carry claimer through valid_wr_weeks/current_keys + generate_excel"
```

---

## Task 6: Migration — `_build_vac_crew_wr_scope` + TARGET legacy cleanup

**Files:**
- Modify: `generate_weekly_pdfs.py` (`_build_vac_crew_wr_scope`; `cleanup_untracked_sheet_attachments`; the TARGET cleanup call site)
- Test: `tests/test_vac_crew_claim_attribution.py`

Read `_build_subcontractor_wr_scope` and the `sub_legacy_primary_variants` gate in `cleanup_untracked_sheet_attachments` as the template.

- [ ] **Step 1: Write the failing tests**

```python
class TestVacCrewLegacyCleanup(unittest.TestCase):
    def setUp(self):
        _ensure_smartsheet_mocked()

    def test_scope_builder_collects_vac_wrs(self):
        groups = {
            '041926_91467680_VACCREW_John': [{'Work Request #': '91467680'}],
            '041926_55555_REDUCEDSUB_USER_X': [{'Work Request #': '55555'}],
        }
        scope = generate_weekly_pdfs._build_vac_crew_wr_scope(groups)
        self.assertIn('91467680', scope)
        self.assertNotIn('55555', scope)

    def test_legacy_vaccrew_deleted_live_claimer_exempt(self):
        # Build a fake client recording deletes; an in-scope WR has a stale
        # legacy _VacCrew (no name → identity NOT in valid_wr_weeks → deleted)
        # AND a live _VacCrew_John (identity in valid_wr_weeks → exempt).
        # Assert only the legacy one is deleted.
        ...  # mirror TestLegacyHelperTargetCleanupE2E from the sub-helper rescue tests
```

> Implement the second test by mirroring `TestLegacyHelperTargetCleanupE2E::test_target_cleanup_exempts_live_helper_for_overlapping_sub_wr` in `tests/test_subcontractor_helper_shadow_rescue.py`: construct attachments named `WR_..._VacCrew_<hash>` (legacy) and `WR_..._VacCrew_John_<hash>` (live), put the live identity tuple in `valid_wr_weeks`, drive `cleanup_untracked_sheet_attachments(...)` with the new vac params, and assert `delete_attachment` is called only for the legacy one.

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_vac_crew_claim_attribution.py::TestVacCrewLegacyCleanup -v`
Expected: FAIL — `_build_vac_crew_wr_scope` missing; cleanup has no vac gate.

- [ ] **Step 3: Add `_build_vac_crew_wr_scope`** (near `_build_subcontractor_wr_scope`):

```python
def _build_vac_crew_wr_scope(groups: dict) -> set:
    """WRs that have any vac_crew group this run (for legacy-_VacCrew cleanup
    + hash prune). Shared by both call sites so scopes never drift."""
    scope = set()
    for key, rows in groups.items():
        if '_VACCREW' in key and rows:
            wr = str(rows[0].get('Work Request #', '')).split('.')[0]
            wr = _RE_SANITIZE_HELPER_NAME.sub('_', wr)[:50]
            if wr:
                scope.add(wr)
    return scope
```

- [ ] **Step 4: Add the vac gate to `cleanup_untracked_sheet_attachments`** — add a kwarg `vac_legacy_wr_scope: set | None = None` and, inside the per-attachment loop, mirror the `sub_legacy_primary_variants` off-contract gate: when `vac_legacy_wr_scope` is provided and the parsed identity is `(wr in scope, variant == 'vac_crew', identifier == '')` AND `ident not in valid_wr_weeks`, unconditionally delete (regardless of `KEEP_HISTORICAL_WEEKS`). Match B's exact gate shape including the `valid_wr_weeks` live-identity exemption.

- [ ] **Step 5: Wire the TARGET call site** — where `cleanup_untracked_sheet_attachments` is called for `TARGET_SHEET_ID`, pass `vac_legacy_wr_scope=_build_vac_crew_wr_scope(groups) if VAC_CREW_LEGACY_CLEANUP_ENABLED else None`.

- [ ] **Step 6: Run to verify pass**

Run: `python -m pytest tests/test_vac_crew_claim_attribution.py::TestVacCrewLegacyCleanup -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_vac_crew_claim_attribution.py
git commit -m "feat(vac-crew): legacy _VacCrew TARGET cleanup with live-identity exemption"
```

---

## Task 7: One-time hash prune

**Files:**
- Modify: `generate_weekly_pdfs.py` (`VAC_CREW_HASH_PRUNE_VERSION`; `_run_vac_crew_hash_prune`; call site; `_hash_history_migration_dirty` wiring; `_PII_LOG_MARKERS`)
- Test: `tests/test_vac_crew_claim_attribution.py`

Read `_run_subproject_b_hash_prune` (returns `bool`) as the exact template.

- [ ] **Step 1: Write the failing tests**

```python
class TestVacCrewHashPrune(unittest.TestCase):
    def setUp(self):
        _ensure_smartsheet_mocked()

    def _groups(self, wrs):
        return {f"041926_{wr}_VACCREW_John": [{'Work Request #': wr}] for wr in wrs}

    def test_drops_legacy_vaccrew_orphans_returns_true(self):
        hist = {
            '91467680|041926|vac_crew|': {'hash': 'h1'},
            '91467680|041926|vac_crew|John': {'hash': 'h2'},  # new — survives
            '55555|041926|vac_crew|': {'hash': 'h3'},          # non-scope — survives
        }
        changed = generate_weekly_pdfs._run_vac_crew_hash_prune(hist, self._groups(['91467680']))
        self.assertIs(changed, True)
        self.assertNotIn('91467680|041926|vac_crew|', hist)
        self.assertIn('91467680|041926|vac_crew|John', hist)
        self.assertIn('55555|041926|vac_crew|', hist)
        self.assertEqual(hist['_vac_crew_prune_version'],
                         generate_weekly_pdfs.VAC_CREW_HASH_PRUNE_VERSION)

    def test_idempotent_returns_false(self):
        hist = {'_vac_crew_prune_version': generate_weekly_pdfs.VAC_CREW_HASH_PRUNE_VERSION}
        self.assertIs(
            generate_weekly_pdfs._run_vac_crew_hash_prune(hist, self._groups(['91467680'])),
            False,
        )

    def test_pii_marker_registered(self):
        self.assertIn('Vac crew hash-history prune', generate_weekly_pdfs._PII_LOG_MARKERS)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_vac_crew_claim_attribution.py::TestVacCrewHashPrune -v`
Expected: FAIL — function + constant + marker missing.

- [ ] **Step 3: Add the constant** (near `SUBPROJECT_B_HASH_PRUNE_VERSION`):

```python
VAC_CREW_HASH_PRUNE_VERSION = 1
```

- [ ] **Step 4: Add the prune** (mirror `_run_subproject_b_hash_prune`, returning `bool`):

```python
def _run_vac_crew_hash_prune(hash_history: dict, groups: dict) -> bool:
    """Sub-project C: idempotent one-time prune of legacy blank-identifier
    vac_crew orphans (``wr|week|vac_crew|``) for WRs that are vac_crew in this
    run. Returns True if it mutated hash_history (so the caller persists it
    even on a no-update run). Distinct sentinel ``_vac_crew_prune_version``."""
    _persisted = hash_history.pop('_vac_crew_prune_version', 0)
    if isinstance(_persisted, int) and _persisted >= VAC_CREW_HASH_PRUNE_VERSION:
        hash_history['_vac_crew_prune_version'] = _persisted
        return False
    _scope = _build_vac_crew_wr_scope(groups)
    _orphans = []
    for _hk in list(hash_history.keys()):
        if isinstance(_hk, str) and _hk.startswith('_'):
            continue
        _parts = str(_hk).split('|')
        if len(_parts) != 4:
            continue
        _wr, _wk, _var, _id = _parts
        if _wr in _scope and _var == 'vac_crew' and _id == '':
            _orphans.append(_hk)
    for _ok in _orphans:
        del hash_history[_ok]
    hash_history['_vac_crew_prune_version'] = VAC_CREW_HASH_PRUNE_VERSION
    if _orphans:
        logging.info(
            f"🧹 Vac crew hash-history prune: dropped {len(_orphans)} legacy "
            f"unpartitioned vac_crew orphan(s) "
            f"(WRs first 20: {sorted({k.split('|')[0] for k in _orphans})[:20]})"
        )
    else:
        logging.info("🧹 Vac crew hash-history prune: no legacy vac_crew orphans to drop")
    return True
```

- [ ] **Step 5: Register the PII marker** — add `"Vac crew hash-history prune"` to the `_PII_LOG_MARKERS` collection.

- [ ] **Step 6: Wire the call site + migration-dirty flag** — next to the B prune call (`if _run_subproject_b_hash_prune(...)`), add:

```python
        try:
            if _run_vac_crew_hash_prune(hash_history, groups):
                _hash_history_migration_dirty = True
        except Exception as _vc_prune_exc:
            logging.warning(
                f"⚠️ Vac crew hash-history prune failed; continuing "
                f"with existing history: {_vc_prune_exc!r}"
            )
```

- [ ] **Step 7: Run to verify pass**

Run: `python -m pytest tests/test_vac_crew_claim_attribution.py::TestVacCrewHashPrune -v`
Expected: PASS (3 tests).

- [ ] **Step 8: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_vac_crew_claim_attribution.py
git commit -m "feat(vac-crew): one-time legacy hash prune wired into migration-dirty save"
```

---

## Task 8: End-to-end coexistence, non-vac preservation, production-site invariants

**Files:**
- Test: `tests/test_vac_crew_claim_attribution.py`
- (No production change expected; if a test reveals a gap, fix it under TDD.)

- [ ] **Step 1: Write the tests**

```python
class TestVacCrewEndToEnd(unittest.TestCase):
    def setUp(self):
        _reset_all()
        self._orig = generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED
        generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED = True

    def tearDown(self):
        generate_weekly_pdfs.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED = self._orig
        _reset_all()

    def test_two_claimers_same_wr_week_coexist(self):
        def _resolve(variant, current, *, wr, week_ending, row_id, enabled):
            return ResolveOutcome('use', 'CrewA' if row_id == 6001 else 'CrewB', 'frozen', 'success')
        with mock.patch('billing_audit.writer.resolve_claimer', side_effect=_resolve):
            groups = generate_weekly_pdfs.group_source_rows(
                [_make_vac_row(row_id=6001), _make_vac_row(row_id=6002)]
            )
        self.assertTrue(any('VACCREW_CrewA' in k for k in groups))
        self.assertTrue(any('VACCREW_CrewB' in k for k in groups))

    def test_non_vac_primary_row_unaffected(self):
        # A non-vac, non-helper primary row still groups exactly as before.
        row = {
            'Work Request #': '91467680', 'Weekly Reference Logged Date': '2026-04-19',
            'Snapshot Date': '2026-04-19', 'Units Completed?': True, 'Units Total Price': '$10.00',
            'CU': 'X', 'Work Type': 'Inst', 'Quantity': 1,
            '__effective_user': 'Boss', '__is_helper_row': False, '__is_vac_crew': False,
            '__helper_foreman': '', '__helper_dept': '', '__helper_job': '',
            '__source_sheet_id': 99999999, '__row_id': 1,
        }
        groups = generate_weekly_pdfs.group_source_rows([row])
        self.assertTrue(any(k.startswith('041926_91467680') and 'VACCREW' not in k for k in groups))


class TestVacCrewProductionInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._src = pathlib.Path(inspect.getsourcefile(generate_weekly_pdfs)).read_text(encoding='utf-8')

    def test_prepass_present(self):
        self.assertIn('_vac_crew_claimer_map', self._src)

    def test_emission_uses_claimer_key(self):
        self.assertIn('_VACCREW_{_c_vac_sanitized}', self._src)

    def test_prune_version_constant(self):
        self.assertRegex(self._src, r'(?m)^VAC_CREW_HASH_PRUNE_VERSION = 1$')

    def test_prune_call_site_present(self):
        self.assertIn('_run_vac_crew_hash_prune(hash_history, groups)', self._src)
```

- [ ] **Step 2: Run to verify** (these should pass if Tasks 3–7 are correct; if any fail, fix the production gap under TDD)

Run: `python -m pytest tests/test_vac_crew_claim_attribution.py::TestVacCrewEndToEnd tests/test_vac_crew_claim_attribution.py::TestVacCrewProductionInvariants -v`
Expected: PASS.

- [ ] **Step 3: Run the FULL suite (zero regressions gate)**

Run: `python -m pytest tests/ -q`
Expected: PASS — all prior tests green, plus the new vac_crew tests. No vac_crew test in `tests/test_vac_crew.py` (the legacy detection/hash tests) regresses; if one does, it is asserting the legacy single-group key — update it in place with a docstring citing this plan (per the [2026-05-20 00:26] rule-2 contract-override discipline) and add a sibling test asserting the new per-claimer invariant.

- [ ] **Step 4: Commit**

```bash
git add tests/test_vac_crew_claim_attribution.py
git commit -m "test(vac-crew): end-to-end coexistence + non-vac preservation + invariants"
```

---

## Task 9: Docs + Living Ledger

**Files:**
- Modify: `website/docs/reference/environment.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Document the env vars** — add `VAC_CREW_CLAIM_ATTRIBUTION_ENABLED` and `VAC_CREW_LEGACY_CLEANUP_ENABLED` to `environment.md` (default `'1'`, what they gate, and that OFF reverts to the legacy single `_VacCrew` file). Follow the format of the `SUBCONTRACTOR_*` entries.

- [ ] **Step 2: Append the Living Ledger entry** to `CLAUDE.md` (prepend `[2026-05-21 HH:MM]`), covering: what shipped (vac_crew per-frozen-claimer partition), the all-sheets scope + new `VAC_CREW_*` flags, the kill-switch-OFF=exact-legacy contract, the parser reorder (VacCrew before Helper), TARGET-only migration + distinct prune sentinel, the preemptive B-lessons applied, and the final `pytest tests/` count.

- [ ] **Step 3: Validate docs build** (if touched beyond the table)

Run: `cd website && npm run build` (only if structural doc changes were made; a table-row addition needs no build).

- [ ] **Step 4: Final full-suite confirmation**

Run: `python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add website/docs/reference/environment.md CLAUDE.md
git commit -m "docs(vac-crew): env vars + Living Ledger for Sub-project C"
```

---

## Self-Review

**Spec coverage:**
- Decision 1 (all-sheets scope) → Task 3 pre-pass predicate is sheet-agnostic (`__is_vac_crew`); Task 6/7 scope by `_VACCREW` group key (any sheet). ✓
- Decision 2 (`_VacCrew_<name>`) → Task 2 (suffix + parser), Task 5 (filename). ✓
- Decision 3 (fallback-to-current) → Task 4 emission (`use`/`no_history`/map-miss → current). ✓
- Decision 4 (two new flags) → Task 1; OFF=legacy → Task 4 disabled branch + test. ✓
- Decision 5 (HOLD on outage) → Task 4 (`hold` → defer + `record_attribution_hold`); summary already wired from B. ✓
- CR-01 four sites → Task 4 (Site 1), Task 5 (Sites 2 & 3), Task 2 (parser). ✓
- Migration (cleanup + prune, distinct sentinel, live-identity exemption, migration-dirty save) → Tasks 6 & 7. ✓
- Preemptive B-lessons (empty-claimer sentinel, `.date()`, defensive raise) → Task 4 (`or 'Unknown'`, `.date()`), Task 2 (suffix raise). ✓
- Hash retained / `billing_audit` untouched → no task modifies the hash content algorithm or `billing_audit/`. ✓
- Testing (true e2e) → Tasks 3–8 drive real `group_source_rows`/`generate_excel`/cleanup/prune. ✓

**Placeholder scan:** Task 6 Step 1 second test and Step 4 reference the B analog rather than re-pasting (`TestLegacyHelperTargetCleanupE2E`, the `sub_legacy_primary_variants` gate) — these are REAL in-repo code the implementer reads, not forward task references; the adaptation (vac variant, `'vac_crew'`, empty-identifier) is spelled out. Acceptable.

**Type consistency:** `_vac_crew_variant_suffix(claimer, wr_num, week_end_raw)`, `_build_vac_crew_wr_scope(groups)`, `_run_vac_crew_hash_prune(hash_history, groups) -> bool`, `_vac_crew_claimer_map`, `_vac_crew_prune_version`, `VAC_CREW_HASH_PRUNE_VERSION`, `VAC_CREW_CLAIM_ATTRIBUTION_ENABLED`, `VAC_CREW_LEGACY_CLEANUP_ENABLED` — names consistent across tasks. `ResolveOutcome(action, name, source, status)` matches B test usage. ✓

**Two implementation notes flagged for the executor** (verify against the live code, do not guess): (a) the exact parameter name of the row list in `group_source_rows` for the pre-pass loop; (b) the exact local holding the week `datetime`/`date` in scope at the vac_crew emission block (mirror B's HOLD-call site precisely).
