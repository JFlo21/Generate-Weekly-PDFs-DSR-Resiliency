# Sub-project D — Primary-Workflow Primary Claim Attribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Partition the production primary Excel files by the FROZEN primary foreman who claimed each line item (`resolve_claimer('primary', …)`), naming each file `_User_<claimer>`, with a fall-back-to-current-and-generate policy on attribution unavailability (no HOLD), and a B/C-style one-time migration of the legacy bare-primary attachments + hash keys.

**Architecture:** Mirror Sub-projects B and C. A bounded `ThreadPoolExecutor` pre-pass resolves each completed non-subcontractor primary row's frozen claimer into `_primary_claimer_map` before the grouping loop. The production primary emission partitions the bare `{week}_{wr}` key into `{week}_{wr}_USER_{claimer}`. The four identity surfaces (main-loop `history_key`, `valid_wr_weeks`, `current_keys`, `build_group_identity` parser) plus the `generate_excel` filename suffix are kept in lockstep, all gated on a new default-on kill switch so OFF reproduces exact legacy behavior. A one-time version-sentinel hash prune + a forced bare-primary attachment cleanup on `TARGET_SHEET_ID` migrate existing deployments.

**Tech Stack:** Python 3.10+, `openpyxl`, Smartsheet SDK, `billing_audit` (Supabase reader — NOT modified), `concurrent.futures.ThreadPoolExecutor`, `unittest` + `unittest.mock`, pytest.

**Spec:** `docs/superpowers/specs/2026-05-25-subproject-d-primary-claim-attribution-design.md`

**Branch:** `feat/subproject-d-primary-claim-attribution` (already created off `origin/master`).

---

## Critical context for the implementer (read before Task 1)

You are editing `generate_weekly_pdfs.py` — a ~8,800-line production billing engine. **Do not refactor anything not named in a task.** Every change is additive and gated on a kill switch. The four prior sub-projects (Phase 1.1, B, C) established the exact patterns you are mirroring; when in doubt, find the `reduced_sub` / `vac_crew` analog and copy its shape.

**The non-negotiable invariants (from CLAUDE.md Living Ledger + the spec):**

1. **CR-01 four-site lockstep.** A variant's claimer identifier must be byte-identical at (a) the main-loop `identifier`/`file_identifier`/`history_key` site, (b) the `valid_wr_weeks` builder, (c) the `current_keys` hash-prune set, and (d) the `build_group_identity` parser. For D, the parser (d) ALREADY handles `_User_<name>` → `('primary', wr, week, name)` — you do NOT change it (but Task 11 adds a regression test). Sites (a)/(b)/(c) + the `generate_excel` filename suffix are the surfaces you change.
2. **Kill-switch gates every identity surface.** `PRIMARY_CLAIM_ATTRIBUTION_ENABLED=0` must reproduce EXACT legacy: bare `{week}_{wr}` key, `''` identifier, bare filename, `{wr}|{week}|primary|` history key, no migration.
3. **Mirror-matcher rule.** `_key_matches_wr` (WR_FILTER) needs the `_USER_` clause added; `_key_matches_excluded_wr` (EXCLUDE_WRS) already has it. Both keep `suffix == wr` for OFF.
4. **No HOLD.** D treats `resolve_claimer` `action=='hold'` (Supabase outage) the same as map-miss/disabled → use current `effective_user` and still generate. D NEVER calls `record_attribution_hold` and emits no hold summary.
5. **Per-row attribution I/O in a bounded pre-pass**, never the hot loop.
6. **`billing_audit/` is NOT modified.** `resolve_claimer('primary', …)` already maps to `primary_foreman` via `ROLE_BY_VARIANT`.

**Key facts you will rely on (verified against the C-merged base, commit `8f546ae`; line numbers are anchors that may drift — search for the quoted code):**

- The emission foreman propagates: `group_source_rows` line ~5750 does `r_copy['__current_foreman'] = current_foreman or effective_user`. Whatever you put in the `keys_to_add` tuple's 3rd element becomes `__current_foreman`.
- `_RE_SANITIZE_IDENTIFIER` is the claimer sanitizer used by B/C (`.sub('_', name)[:50]`). Use it for D too. Do NOT invent a new regex.
- `ResolveOutcome` (from `billing_audit.writer`) has fields `action` (`'use'`/`'hold'`), `name`, `source`, `status`.
- The production primary emission is the `if not is_subcontractor_row and not valid_helper_row:` branch inside the `elif RES_GROUPING_MODE in ('helper', 'both'):` block. `valid_helper_row` and `is_subcontractor_row` are both in scope there.

**Validation commands (run from repo root):**
- Single test: `pytest tests/test_primary_claim_attribution.py::ClassName::test_name -v`
- Full suite (must stay green; baseline 814 passed / 26 skipped / 60 subtests): `pytest tests/`
- Syntax: `python -m py_compile generate_weekly_pdfs.py`

---

## File structure

| File | Change | Responsibility |
|------|--------|----------------|
| `generate_weekly_pdfs.py` | Modify | Config (Task 1), `generate_excel` filename suffix (Task 2), pre-pass (Task 3), emission (Task 4), identity sites a/b/c (Tasks 5–6), WR_FILTER matcher (Task 7), `_build_primary_wr_scope` (Task 8), `_run_subproject_d_hash_prune` + wiring (Task 9), cleanup param/gate/call-site (Task 10) |
| `tests/test_primary_claim_attribution.py` | Create | All D unit + E2E + source-grep tests |
| `.github/workflows/weekly-excel-generation.yml` | Modify | Pin both new env vars (Task 12) |
| `website/docs/reference/environment.md` | Modify | Document both new env vars (Task 12) |
| `CLAUDE.md` | Modify | Living Ledger entry (Task 13) |

---

## Task 1: Config — version constant, two kill-switch env vars, startup banner

**Files:**
- Modify: `generate_weekly_pdfs.py` (constants block ~line 325; env-var block ~line 552; banner ~line 714)
- Test: `tests/test_primary_claim_attribution.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_primary_claim_attribution.py` with:

```python
"""Sub-project D — primary-workflow primary claim attribution tests."""
import datetime
import inspect
import unittest
from unittest import mock

import generate_weekly_pdfs  # noqa: E402
from tests.test_billing_audit_shadow import _ensure_smartsheet_mocked, _reset_all  # noqa: E402

_ensure_smartsheet_mocked()

from billing_audit.writer import ResolveOutcome  # noqa: E402

gwp = generate_weekly_pdfs


class TestConfigConstants(unittest.TestCase):
    """Task 1: D config surface exists with the right defaults."""

    def test_hash_prune_version_constant(self):
        self.assertEqual(gwp.SUBPROJECT_D_HASH_PRUNE_VERSION, 1)

    def test_attribution_flag_is_bool(self):
        self.assertIsInstance(gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED, bool)

    def test_cleanup_flag_is_bool(self):
        self.assertIsInstance(
            gwp.LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED, bool
        )

    def test_banner_logs_attribution_flag(self):
        src = inspect.getsource(generate_weekly_pdfs)
        self.assertIn(
            "📋 PRIMARY_CLAIM_ATTRIBUTION_ENABLED=", src
        )
        self.assertIn(
            "📋 LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED=", src
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_primary_claim_attribution.py::TestConfigConstants -v`
Expected: FAIL — `AttributeError: module 'generate_weekly_pdfs' has no attribute 'SUBPROJECT_D_HASH_PRUNE_VERSION'`.

- [ ] **Step 3a: Add the version constant**

In `generate_weekly_pdfs.py`, immediately after the `VAC_CREW_HASH_PRUNE_VERSION = 1` line (~line 325), add:

```python
# Subproject D (2026-05-25): one-time hash-history prune version for
# dropping LEGACY blank-identifier `primary` orphans left behind when
# D re-partitions the production primary variant by frozen primary
# claimer. Separate sentinel (`_subproject_d_prune_version`) from
# Phase 1.1, Subproject B, and Subproject C so all four migrations are
# independent + auditable. Advancing this constant is the kill switch
# (re-run trigger).
SUBPROJECT_D_HASH_PRUNE_VERSION = 1
```

- [ ] **Step 3b: Add the two env vars**

In `generate_weekly_pdfs.py`, immediately after the `VAC_CREW_LEGACY_CLEANUP_ENABLED = os.getenv(...)` block ends (~line 552, before the `# Cutoff date for _AEPBillable` comment ~line 554), add:

```python
# Subproject D (2026-05-25): default-ON kill switch that enables
# per-claimer partitioning of the PRODUCTION primary Excel files. When
# enabled, each non-subcontractor primary Excel is partitioned by the
# FROZEN primary foreman (``primary`` role from
# ``billing_audit.attribution_snapshot`` via ``resolve_claimer``) and
# named ``_User_<claimer>``. When disabled, the legacy one-file-per-WR
# bare primary behavior is preserved exactly. Unlike Subproject B, the
# core primary path NEVER holds on a Supabase outage — it falls back to
# the current foreman and still generates (operator decision: this path
# covers every non-sub WR, so HOLD would suppress all primary billing
# during an outage). Pinned in workflow env: block per [2026-05-15
# 12:00] rule 7.
PRIMARY_CLAIM_ATTRIBUTION_ENABLED = os.getenv(
    'PRIMARY_CLAIM_ATTRIBUTION_ENABLED', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')

# Subproject D (2026-05-25): default-ON kill switch for the one-time
# removal of legacy UNPARTITIONED bare ``primary`` attachments (no
# ``_User_`` token, parsed identifier == '') on TARGET_SHEET_ID for
# non-subcontractor WRs, once those files are re-partitioned by frozen
# primary claimer. Set to '0' to skip the destructive cleanup (legacy
# duplicates then persist until removed manually). Separate from
# PRIMARY_CLAIM_ATTRIBUTION_ENABLED (which gates attribution
# resolution, NOT this cleanup). Workflow-pinned per [2026-05-15
# 12:00] rule 7.
LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED = os.getenv(
    'LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')
```

- [ ] **Step 3c: Add the startup banner logs**

In `generate_weekly_pdfs.py`, find the Subproject C banner block (the `logging.info(...)` that prints `📋 VAC_CREW_*` ~line 714) and add AFTER that block:

```python
# Subproject D: surface resolved kill-switch state at startup so
# operators grepping the banner see the active feature state at a
# glance. Banner body carries no row PII (just the resolved bools).
logging.info(
    f"📋 PRIMARY_CLAIM_ATTRIBUTION_ENABLED="
    f"{PRIMARY_CLAIM_ATTRIBUTION_ENABLED}"
)
logging.info(
    f"📋 LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED="
    f"{LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED}"
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_primary_claim_attribution.py::TestConfigConstants -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Syntax check + commit**

```bash
python -m py_compile generate_weekly_pdfs.py
git add generate_weekly_pdfs.py tests/test_primary_claim_attribution.py
git commit -m "feat(billing): Subproject D config — primary claim attribution kill switches"
```

---

## Task 2: `generate_excel` — emit `_User_<claimer>` filename suffix for primary variant

This is the surface that produces the per-claimer filename. Without it, all of a WR's per-claimer primary groups generate to the SAME bare filename and collide.

**Files:**
- Modify: `generate_weekly_pdfs.py` (the `elif variant == 'primary':` filename-suffix branch ~line 6221-6223)
- Test: `tests/test_primary_claim_attribution.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_primary_claim_attribution.py`:

```python
class TestPrimaryFilenameSuffix(unittest.TestCase):
    """Task 2: generate_excel emits _User_<claimer> for primary variant
    when attribution is enabled, bare otherwise."""

    def setUp(self):
        self._orig = gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED

    def tearDown(self):
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = self._orig

    def _suffix_for(self, enabled, current_foreman):
        # Drive the suffix branch in isolation by reading the source and
        # confirming the gated construction exists (the branch lives deep
        # inside generate_excel; a source-level assertion is the reliable
        # unit check, paired with the E2E filename test in Task 4).
        src = inspect.getsource(generate_weekly_pdfs)
        return src

    def test_primary_branch_builds_user_suffix_gated(self):
        src = inspect.getsource(generate_weekly_pdfs)
        # The primary branch must build _User_<sanitized claimer> gated on
        # the kill switch + a non-empty __current_foreman.
        self.assertIn("_User_", src)
        # Confirm the gate wording is present in the primary suffix branch.
        self.assertRegex(
            src,
            r"PRIMARY_CLAIM_ATTRIBUTION_ENABLED and _pf"
            r"[\s\S]{0,200}_User_\{",
        )
```

> Note: the deep-nested `generate_excel` suffix branch is verified here by source assertion; the *behavioral* round-trip (filename actually contains `_User_<claimer>` and parses back) is covered end-to-end in Task 4 Step 1's `test_two_claimers_distinct_filenames` and Task 11's parser round-trip.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_primary_claim_attribution.py::TestPrimaryFilenameSuffix -v`
Expected: FAIL — the regex `PRIMARY_CLAIM_ATTRIBUTION_ENABLED and _pf ... _User_{` is not yet present.

- [ ] **Step 3: Replace the primary suffix branch**

In `generate_weekly_pdfs.py`, find:

```python
    elif variant == 'primary':
        # Primary variant (no suffix needed)
        variant_suffix = ''
```

Replace with:

```python
    elif variant == 'primary':
        # Subproject D (2026-05-25): partition the production primary
        # file by the FROZEN primary claimer (__current_foreman is the
        # resolved claimer set in group_source_rows' emission tuple).
        # GATED on the kill switch (mirrors the vac_crew branch above):
        #   • Enabled + claimer present -> _User_<sanitized claimer> so
        #     each claimer's file is distinct and round-trips through
        #     build_group_identity as ('primary', wr, week, claimer).
        #   • Disabled (or no claimer) -> exact legacy bare suffix '',
        #     preserving byte-identical filenames with pre-D attachments.
        # __current_foreman in disabled mode is effective_user (the
        # emission passes None -> `current_foreman or effective_user`),
        # but the kill-switch gate keeps the suffix bare in that case.
        _pf = first_row.get('__current_foreman', '')
        if PRIMARY_CLAIM_ATTRIBUTION_ENABLED and _pf:
            variant_suffix = (
                f"_User_{_RE_SANITIZE_IDENTIFIER.sub('_', _pf)[:50]}"
            )
        else:
            variant_suffix = ''
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_primary_claim_attribution.py::TestPrimaryFilenameSuffix -v`
Expected: PASS.

- [ ] **Step 5: Syntax check + commit**

```bash
python -m py_compile generate_weekly_pdfs.py
git add generate_weekly_pdfs.py tests/test_primary_claim_attribution.py
git commit -m "feat(billing): Subproject D — _User_<claimer> primary filename suffix"
```

---

## Task 3: Pre-pass — `_primary_claimer_map` in `group_source_rows`

**Files:**
- Modify: `generate_weekly_pdfs.py` (after the Subproject C vac-crew pre-pass block, which ends ~line 5144, just before `for r in rows:`)
- Test: `tests/test_primary_claim_attribution.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_primary_claim_attribution.py`:

```python
def _make_primary_row(
    row_id,
    wr='90001',
    week_serial=46100,  # arbitrary Excel serial -> a real date
    effective_user='CurrentForeman',
    source_sheet_id=99999,  # NOT in _FOLDER_DISCOVERED_SUB_IDS
):
    """Build a synthetic NON-subcontractor, completed, non-helper,
    non-vac primary row for group_source_rows."""
    return {
        '__row_id': row_id,
        '__source_sheet_id': source_sheet_id,
        '__effective_user': effective_user,
        '__is_helper_row': False,
        '__is_vac_crew': False,
        'Work Request #': wr,
        'Weekly Reference Logged Date': week_serial,
        'Units Completed?': True,
        'Units Total Price': 100.0,
        'Dept #': '500',
        'Job #': 'J-1',
    }


class TestPrimaryPrePass(unittest.TestCase):
    """Task 3: the pre-pass resolves frozen claimers for non-sub
    completed primary rows into _primary_claimer_map."""

    def setUp(self):
        _ensure_smartsheet_mocked()
        _reset_all()
        self._saved = {
            'attr': gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED,
            'avail': gwp.BILLING_AUDIT_AVAILABLE,
            'mode': gwp.RES_GROUPING_MODE,
            'sub': set(gwp._FOLDER_DISCOVERED_SUB_IDS),
        }
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = True
        gwp.BILLING_AUDIT_AVAILABLE = True
        gwp.RES_GROUPING_MODE = 'both'
        gwp._FOLDER_DISCOVERED_SUB_IDS.clear()  # row sheet 99999 is non-sub

    def tearDown(self):
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = self._saved['attr']
        gwp.BILLING_AUDIT_AVAILABLE = self._saved['avail']
        gwp.RES_GROUPING_MODE = self._saved['mode']
        gwp._FOLDER_DISCOVERED_SUB_IDS.clear()
        gwp._FOLDER_DISCOVERED_SUB_IDS.update(self._saved['sub'])

    def test_prepass_resolves_frozen_claimer_into_group_key(self):
        rows = [_make_primary_row(1001, effective_user='CurrentFM')]
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'FrozenFM', 'frozen', 'success'),
        ):
            groups = gwp.group_source_rows(rows)
        keys = list(groups.keys())
        self.assertTrue(
            any(k.endswith('_USER_FrozenFM') for k in keys),
            f"expected a _USER_FrozenFM primary group, got {keys}",
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_primary_claim_attribution.py::TestPrimaryPrePass -v`
Expected: FAIL — no `_USER_FrozenFM` key (emission not partitioned yet; the pre-pass map isn't built/consumed).

> This test exercises Task 3 (pre-pass) AND Task 4 (emission) together. It will fully pass only after Task 4. After Task 3 alone, it still fails (emission unchanged), which is expected — keep it red until Task 4. To confirm Task 3 in isolation, add the source-grep assertion below.

- [ ] **Step 3: Implement the pre-pass**

In `generate_weekly_pdfs.py`, immediately AFTER the Subproject C vac-crew pre-pass block (the one ending with `_vac_crew_claimer_map = {}` in its outer `except`, ~line 5144) and BEFORE `for r in rows:`, add:

```python
    # Subproject D (2026-05-25): resolve the FROZEN primary claimer for
    # every completed NON-subcontractor, non-vac primary row BEFORE the
    # grouping loop, so no per-row Supabase round-trip runs inside the
    # hot loop (honors [2026-04-25 14:00] latency lesson). The map is
    # keyed by __row_id and consumed by the production primary emission
    # branch. A row absent from the map (attribution disabled, pre-pass
    # skipped, missing __row_id, or unexpected per-row error) resolves to
    # use-current at emission. Unlike B/C, a ``hold`` outcome (Supabase
    # outage) is ALSO consumed as use-current at emission — D never
    # defers a primary file (operator decision: the core path prioritizes
    # availability). resolve_claimer is still called so frozen attribution
    # is used whenever Supabase is healthy.
    _primary_claimer_map: dict = {}
    if BILLING_AUDIT_AVAILABLE and PRIMARY_CLAIM_ATTRIBUTION_ENABLED:
        _d_pre_rows = []
        for _r in rows:
            _rid = _r.get('__row_id')
            if not isinstance(_rid, int):
                continue
            if _r.get('__is_vac_crew'):
                continue
            _sid = _r.get('__source_sheet_id')
            if _sid is not None and _sid in _FOLDER_DISCOVERED_SUB_IDS:
                continue  # subcontractor rows are Sub-project B's domain
            _wr_raw = _r.get('Work Request #')
            _ld = _r.get('Weekly Reference Logged Date')
            if not _wr_raw or not _ld or not is_checked(_r.get('Units Completed?')):
                continue
            _we = excel_serial_to_date(_ld)
            if _we is None:
                continue
            _d_pre_rows.append((
                _rid,
                str(_wr_raw).split('.')[0],
                _we.date() if isinstance(_we, datetime.datetime) else _we,
                _r.get('__effective_user', 'Unknown Foreman'),
            ))
        if _d_pre_rows:
            try:
                from billing_audit.writer import resolve_claimer as _resolve_claimer_primary

                def _resolve_one_primary(_item):
                    _rid, _wr, _we_date, _eu = _item
                    return _rid, _resolve_claimer_primary(
                        'primary', _eu,
                        wr=_wr, week_ending=_we_date, row_id=_rid,
                        enabled=PRIMARY_CLAIM_ATTRIBUTION_ENABLED,
                    )

                if len(_d_pre_rows) <= 1:
                    for _item in _d_pre_rows:
                        _rid, _out = _resolve_one_primary(_item)
                        _primary_claimer_map[_rid] = _out
                else:
                    _workers = min(PARALLEL_WORKERS, len(_d_pre_rows))
                    with ThreadPoolExecutor(max_workers=_workers) as _ex:
                        _futs = [_ex.submit(_resolve_one_primary, _it) for _it in _d_pre_rows]
                        for _fut in as_completed(_futs):
                            try:
                                _rid, _out = _fut.result()
                                _primary_claimer_map[_rid] = _out
                            except Exception:
                                logging.exception(
                                    "⚠️ Subproject D attribution pre-pass: "
                                    "unexpected error for one row (treating "
                                    "as use-current)"
                                )
            except Exception:
                logging.exception(
                    "⚠️ Subproject D attribution pre-pass failed; falling "
                    "back to current foreman for all primary rows"
                )
                _primary_claimer_map = {}
```

- [ ] **Step 4: Add a source-grep confirmation for Task 3 (keeps Task 3 verifiable before Task 4)**

Append to `tests/test_primary_claim_attribution.py`:

```python
class TestPrimaryPrePassSource(unittest.TestCase):
    """Task 3: the pre-pass exists with the right shape."""

    def test_prepass_block_present(self):
        src = inspect.getsource(generate_weekly_pdfs)
        self.assertIn("_primary_claimer_map", src)
        self.assertRegex(
            src,
            r"resolve_claimer_primary\(\s*'primary'",
        )
        # Pre-pass must exclude subcontractor + vac rows.
        self.assertRegex(
            src,
            r"_primary_claimer_map[\s\S]{0,600}_FOLDER_DISCOVERED_SUB_IDS",
        )
```

- [ ] **Step 5: Run + commit**

Run: `pytest tests/test_primary_claim_attribution.py::TestPrimaryPrePassSource -v`
Expected: PASS.
(`TestPrimaryPrePass::test_prepass_resolves_frozen_claimer_into_group_key` stays RED until Task 4.)

```bash
python -m py_compile generate_weekly_pdfs.py
git add generate_weekly_pdfs.py tests/test_primary_claim_attribution.py
git commit -m "feat(billing): Subproject D — primary claimer attribution pre-pass"
```

---

## Task 4: Emission — partition the production primary key by claimer

**Files:**
- Modify: `generate_weekly_pdfs.py` (the production primary emission branch ~line 5303-5305)
- Test: `tests/test_primary_claim_attribution.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_primary_claim_attribution.py`:

```python
class TestPrimaryEmission(unittest.TestCase):
    """Task 4: production primary emission partitions by claimer when on,
    bare when off; never holds."""

    def setUp(self):
        _ensure_smartsheet_mocked()
        _reset_all()
        self._saved = {
            'attr': gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED,
            'avail': gwp.BILLING_AUDIT_AVAILABLE,
            'mode': gwp.RES_GROUPING_MODE,
            'sub': set(gwp._FOLDER_DISCOVERED_SUB_IDS),
        }
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = True
        gwp.BILLING_AUDIT_AVAILABLE = True
        gwp.RES_GROUPING_MODE = 'both'
        gwp._FOLDER_DISCOVERED_SUB_IDS.clear()

    def tearDown(self):
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = self._saved['attr']
        gwp.BILLING_AUDIT_AVAILABLE = self._saved['avail']
        gwp.RES_GROUPING_MODE = self._saved['mode']
        gwp._FOLDER_DISCOVERED_SUB_IDS.clear()
        gwp._FOLDER_DISCOVERED_SUB_IDS.update(self._saved['sub'])

    def test_frozen_claimer_partitions_key(self):
        rows = [_make_primary_row(1, effective_user='CurFM')]
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'FrozenFM', 'frozen', 'success'),
        ):
            groups = gwp.group_source_rows(rows)
        self.assertTrue(any(k.endswith('_USER_FrozenFM') for k in groups))
        # The legacy bare primary key must NOT be present.
        self.assertFalse(
            any(k.split('_USER_')[0] == k and '_USER_' not in k
                and k.count('_') == 1 for k in groups),
        )

    def test_two_claimers_two_groups(self):
        rows = [
            _make_primary_row(1, wr='90001', effective_user='A'),
            _make_primary_row(2, wr='90001', effective_user='B'),
        ]

        def _resolve(variant, current, *, wr, week_ending, row_id, enabled):
            return ResolveOutcome(
                'use', 'Alice' if row_id == 1 else 'Bob', 'frozen', 'success'
            )

        with mock.patch('billing_audit.writer.resolve_claimer', side_effect=_resolve):
            groups = gwp.group_source_rows(rows)
        self.assertTrue(any(k.endswith('_USER_Alice') for k in groups))
        self.assertTrue(any(k.endswith('_USER_Bob') for k in groups))

    def test_no_history_falls_back_to_current(self):
        rows = [_make_primary_row(1, effective_user='CurFM')]
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'CurFM', 'current', 'no_history'),
        ):
            groups = gwp.group_source_rows(rows)
        self.assertTrue(any(k.endswith('_USER_CurFM') for k in groups))

    def test_hold_outage_still_emits_under_current(self):
        rows = [_make_primary_row(1, effective_user='CurFM')]
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('hold', None, None, 'fetch_failure'),
        ), mock.patch(
            'billing_audit.writer.record_attribution_hold'
        ) as _rec:
            groups = gwp.group_source_rows(rows)
        # D never holds: a primary group IS emitted under current foreman.
        self.assertTrue(any(k.endswith('_USER_CurFM') for k in groups))
        # And record_attribution_hold is NEVER called for the primary path.
        _rec.assert_not_called()

    def test_kill_switch_off_emits_bare_legacy_key(self):
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = False
        rows = [_make_primary_row(1, wr='90001', effective_user='CurFM')]
        # No mock needed — pre-pass is gated off, emission is legacy.
        groups = gwp.group_source_rows(rows)
        bare = [k for k in groups if '_USER_' not in k]
        self.assertTrue(bare, f"expected a bare primary key, got {list(groups)}")
        # bare key shape is {week}_{wr}
        self.assertTrue(any(k.endswith('_90001') for k in bare))
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/test_primary_claim_attribution.py::TestPrimaryEmission -v`
Expected: the ON tests FAIL (no `_USER_` keys yet); `test_kill_switch_off_emits_bare_legacy_key` PASSES already (legacy path unchanged).

- [ ] **Step 3: Modify the emission branch**

In `generate_weekly_pdfs.py`, find the production primary emission (inside `elif RES_GROUPING_MODE in ('helper', 'both'):`):

```python
                    if not is_subcontractor_row and not valid_helper_row:
                        primary_key = f"{week_end_for_key}_{wr_key}"
                        keys_to_add.append(('primary', primary_key, None))
```

Replace with:

```python
                    if not is_subcontractor_row and not valid_helper_row:
                        # Subproject D (2026-05-25): partition the
                        # production primary file by the FROZEN primary
                        # claimer. Consume the pre-pass map. ``use`` ->
                        # partition by claimer; ``hold`` (Supabase outage),
                        # map miss, or disabled -> use the current
                        # effective_user and STILL emit (D never holds —
                        # operator decision for the core path). Empty
                        # claimer -> 'Unknown Foreman' sentinel so the
                        # _User_ suffix builder never gets an empty
                        # identifier (mirrors B's Codex-P1 fix).
                        if PRIMARY_CLAIM_ATTRIBUTION_ENABLED:
                            _d_outcome = _primary_claimer_map.get(r.get('__row_id'))
                            if _d_outcome is not None and _d_outcome.action == 'use':
                                _d_claimer = (
                                    _d_outcome.name or effective_user or 'Unknown Foreman'
                                )
                            else:
                                # hold / map-miss / disabled / None -> current.
                                _d_claimer = effective_user or 'Unknown Foreman'
                            _d_claimer_sanitized = _RE_SANITIZE_IDENTIFIER.sub(
                                '_', _d_claimer
                            )[:50]
                            primary_key = (
                                f"{week_end_for_key}_{wr_key}_USER_"
                                f"{_d_claimer_sanitized}"
                            )
                            keys_to_add.append(('primary', primary_key, _d_claimer))
                            if primary_key not in groups:
                                logging.info(
                                    f"🧑 PRIMARY GROUP CREATED: WR={wr_key}, "
                                    f"Week={week_end_for_key}"
                                )
                        else:
                            # Kill switch OFF -> exact legacy bare primary.
                            primary_key = f"{week_end_for_key}_{wr_key}"
                            keys_to_add.append(('primary', primary_key, None))
```

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/test_primary_claim_attribution.py::TestPrimaryEmission tests/test_primary_claim_attribution.py::TestPrimaryPrePass -v`
Expected: PASS (all TestPrimaryEmission + the previously-red TestPrimaryPrePass test).

- [ ] **Step 5: Add a two-claimer distinct-filename E2E (round-trip) test**

Append to `tests/test_primary_claim_attribution.py`:

```python
class TestPrimaryFilenameRoundTrip(unittest.TestCase):
    """Task 2+4: two claimers on one WR+week produce two distinct
    _User_ filenames that round-trip through build_group_identity as
    distinct primary identities (coexistence; no cross-delete)."""

    def test_distinct_identities_for_two_claimers(self):
        a = gwp.build_group_identity(
            "WR_90001_WeekEnding_041926_120000_User_Alice_abcdef0123456789.xlsx"
        )
        b = gwp.build_group_identity(
            "WR_90001_WeekEnding_041926_120000_User_Bob_abcdef0123456789.xlsx"
        )
        self.assertEqual(a, ('90001', '041926', 'primary', 'Alice'))
        self.assertEqual(b, ('90001', '041926', 'primary', 'Bob'))
        self.assertNotEqual(a, b)  # distinct -> cleanup keeps both
```

- [ ] **Step 6: Run + commit**

Run: `pytest tests/test_primary_claim_attribution.py -v`
Expected: PASS.

```bash
python -m py_compile generate_weekly_pdfs.py
git add generate_weekly_pdfs.py tests/test_primary_claim_attribution.py
git commit -m "feat(billing): Subproject D — partition production primary by frozen claimer"
```

---

## Task 5: Site (a) — main-loop identity (`history_key` / `file_identifier`)

**Files:**
- Modify: `generate_weekly_pdfs.py` (the primary `else` branch of the variant identity cascade ~line 8051-8057)
- Test: `tests/test_primary_claim_attribution.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_primary_claim_attribution.py`:

```python
class TestSiteAMainLoopIdentity(unittest.TestCase):
    """Task 5: main-loop primary identity derives from __current_foreman
    when attribution is on (gated), legacy User field when off."""

    def test_site_a_gated_primary_identity(self):
        src = inspect.getsource(generate_weekly_pdfs)
        # The primary identity branch must derive from __current_foreman
        # gated on PRIMARY_CLAIM_ATTRIBUTION_ENABLED, and keep the legacy
        # User-field path for the disabled case.
        self.assertRegex(
            src,
            r"PRIMARY_CLAIM_ATTRIBUTION_ENABLED[\s\S]{0,300}"
            r"__current_foreman[\s\S]{0,300}"
            r"first_row\.get\('User'\)",
        )
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_primary_claim_attribution.py::TestSiteAMainLoopIdentity -v`
Expected: FAIL.

- [ ] **Step 3: Modify the main-loop primary identity branch**

In `generate_weekly_pdfs.py`, find the `else` branch (~line 8051):

```python
                else:
                    # Legacy primary variant: identifier derived from the
                    # row's ``User`` field.
                    user_val = first_row.get('User')
                    # PERFORMANCE: Use pre-compiled regex for identifier sanitization
                    identifier = _RE_SANITIZE_IDENTIFIER.sub('_', user_val)[:50] if user_val else ''
                    file_identifier = identifier
```

Replace with:

```python
                else:
                    # Subproject D (2026-05-25): primary identity site
                    # (Site 1 — main-loop identifier / history_key /
                    # file_identifier). GATED on the kill switch (mirrors
                    # the reduced_sub / vac_crew sites above): enabled mode
                    # derives identifier == file_identifier from the FROZEN
                    # claimer (__current_foreman, the partition key set in
                    # group_source_rows' emission tuple) so the round-trip
                    # with the _User_<claimer> filename + Sites 2 & 3
                    # succeeds. Disabled mode preserves the EXACT legacy
                    # ``User``-field path (identifier '' in production
                    # because the User column is unpopulated) so a bare
                    # primary attachment is not treated as stale.
                    if PRIMARY_CLAIM_ATTRIBUTION_ENABLED:
                        _pf = first_row.get('__current_foreman', '')
                        identifier = (
                            _RE_SANITIZE_IDENTIFIER.sub('_', _pf)[:50]
                            if _pf else ''
                        )
                        file_identifier = identifier
                    else:
                        # Legacy primary variant: identifier derived from
                        # the row's ``User`` field.
                        user_val = first_row.get('User')
                        # PERFORMANCE: Use pre-compiled regex for identifier sanitization
                        identifier = _RE_SANITIZE_IDENTIFIER.sub('_', user_val)[:50] if user_val else ''
                        file_identifier = identifier
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_primary_claim_attribution.py::TestSiteAMainLoopIdentity -v`
Expected: PASS.

- [ ] **Step 5: Syntax check + commit**

```bash
python -m py_compile generate_weekly_pdfs.py
git add generate_weekly_pdfs.py tests/test_primary_claim_attribution.py
git commit -m "feat(billing): Subproject D — Site 1 main-loop primary identity"
```

---

## Task 6: Sites (b) `valid_wr_weeks` + (c) `current_keys`

**Files:**
- Modify: `generate_weekly_pdfs.py` (the `else` branch of the `valid_wr_weeks` builder ~line 8782-8785, and the `else` branch of the `current_keys` builder ~line 9010-9012)
- Test: `tests/test_primary_claim_attribution.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_primary_claim_attribution.py`:

```python
class TestSitesBCIdentity(unittest.TestCase):
    """Task 6: valid_wr_weeks (Site 2) and current_keys (Site 3) primary
    branches derive from __current_foreman gated on the kill switch."""

    def test_sites_b_and_c_gated_primary_identity(self):
        src = inspect.getsource(generate_weekly_pdfs)
        # Site 2 (valid_wr_weeks builder): the else branch builds file_id
        # from __current_foreman gated on PRIMARY_CLAIM_ATTRIBUTION_ENABLED.
        self.assertRegex(
            src,
            r"file_id = \(\s*_RE_SANITIZE_IDENTIFIER\.sub\('_', _pf\)\[:50\]"
            r"\s*if \(PRIMARY_CLAIM_ATTRIBUTION_ENABLED and _pf\)",
        )
        # Site 3 (current_keys builder): the else branch builds _ident
        # from __current_foreman gated on PRIMARY_CLAIM_ATTRIBUTION_ENABLED.
        self.assertRegex(
            src,
            r"_ident = \(\s*_RE_SANITIZE_IDENTIFIER\.sub\('_', _pf\)\[:50\]"
            r"\s*if \(PRIMARY_CLAIM_ATTRIBUTION_ENABLED and _pf\)",
        )
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_primary_claim_attribution.py::TestSitesBCIdentity -v`
Expected: FAIL.

- [ ] **Step 3a: Modify Site (b) — `valid_wr_weeks` else branch**

In `generate_weekly_pdfs.py`, find (~line 8782):

```python
                else:
                    user_val = group_rows[0].get('User')
                    # PERFORMANCE: Use pre-compiled regex
                    file_id = _RE_SANITIZE_IDENTIFIER.sub('_', user_val)[:50] if user_val else ''
                valid_wr_weeks.add((wr, week_raw, variant, file_id))
```

Replace with:

```python
                else:
                    # Subproject D (2026-05-25): primary identity site
                    # (Site 2 — valid_wr_weeks). Mirror Site 1 so attachment
                    # cleanup keeps the live per-claimer primary file.
                    # Disabled mode preserves the legacy ``User``-field path.
                    if PRIMARY_CLAIM_ATTRIBUTION_ENABLED:
                        _pf = group_rows[0].get('__current_foreman', '')
                        file_id = (
                            _RE_SANITIZE_IDENTIFIER.sub('_', _pf)[:50]
                            if (PRIMARY_CLAIM_ATTRIBUTION_ENABLED and _pf) else ''
                        )
                    else:
                        user_val = group_rows[0].get('User')
                        # PERFORMANCE: Use pre-compiled regex
                        file_id = _RE_SANITIZE_IDENTIFIER.sub('_', user_val)[:50] if user_val else ''
                valid_wr_weeks.add((wr, week_raw, variant, file_id))
```

- [ ] **Step 3b: Modify Site (c) — `current_keys` else branch**

In `generate_weekly_pdfs.py`, find (~line 9010):

```python
                        else:
                            _uv = group_rows[0].get('User')
                            _ident = _RE_SANITIZE_IDENTIFIER.sub('_', _uv)[:50] if _uv else ''
                        current_keys.add(f"{_wr}|{_week}|{_variant}|{_ident}")
```

Replace with:

```python
                        else:
                            # Subproject D (2026-05-25): primary identity
                            # site (Site 3 — current_keys). Must match the
                            # history_key written at Site 1 byte-for-byte
                            # (sanitized claimer when on, legacy User-field
                            # when off) or the freshly-written entry is
                            # treated as stale and deleted before save.
                            if PRIMARY_CLAIM_ATTRIBUTION_ENABLED:
                                _pf = group_rows[0].get('__current_foreman', '')
                                _ident = (
                                    _RE_SANITIZE_IDENTIFIER.sub('_', _pf)[:50]
                                    if (PRIMARY_CLAIM_ATTRIBUTION_ENABLED and _pf) else ''
                                )
                            else:
                                _uv = group_rows[0].get('User')
                                _ident = _RE_SANITIZE_IDENTIFIER.sub('_', _uv)[:50] if _uv else ''
                        current_keys.add(f"{_wr}|{_week}|{_variant}|{_ident}")
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_primary_claim_attribution.py::TestSitesBCIdentity -v`
Expected: PASS.

- [ ] **Step 5: Syntax check + commit**

```bash
python -m py_compile generate_weekly_pdfs.py
git add generate_weekly_pdfs.py tests/test_primary_claim_attribution.py
git commit -m "feat(billing): Subproject D — Sites 2 & 3 primary identity lockstep"
```

---

## Task 7: WR_FILTER matcher — add `_USER_` clause to `_key_matches_wr`

**Files:**
- Modify: `generate_weekly_pdfs.py` (`_key_matches_wr` return expression ~line 5833-5846)
- Test: `tests/test_primary_claim_attribution.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_primary_claim_attribution.py`:

```python
class TestWrFilterMatchesUserVariant(unittest.TestCase):
    """Task 7: WR_FILTER (_key_matches_wr) retains _USER_ primary groups;
    EXCLUDE_WRS (_key_matches_excluded_wr) already does."""

    def setUp(self):
        _ensure_smartsheet_mocked()
        _reset_all()
        self._saved = {
            'attr': gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED,
            'avail': gwp.BILLING_AUDIT_AVAILABLE,
            'mode': gwp.RES_GROUPING_MODE,
            'sub': set(gwp._FOLDER_DISCOVERED_SUB_IDS),
            'tm': gwp.TEST_MODE,
            'wf': list(gwp.WR_FILTER),
            'ex': list(gwp.EXCLUDE_WRS),
        }
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = True
        gwp.BILLING_AUDIT_AVAILABLE = True
        gwp.RES_GROUPING_MODE = 'both'
        gwp._FOLDER_DISCOVERED_SUB_IDS.clear()

    def tearDown(self):
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = self._saved['attr']
        gwp.BILLING_AUDIT_AVAILABLE = self._saved['avail']
        gwp.RES_GROUPING_MODE = self._saved['mode']
        gwp._FOLDER_DISCOVERED_SUB_IDS.clear()
        gwp._FOLDER_DISCOVERED_SUB_IDS.update(self._saved['sub'])
        gwp.TEST_MODE = self._saved['tm']
        gwp.WR_FILTER = self._saved['wf']
        gwp.EXCLUDE_WRS = self._saved['ex']

    def test_wr_filter_retains_user_primary_group(self):
        gwp.TEST_MODE = True
        gwp.WR_FILTER = ['90001']
        rows = [_make_primary_row(1, wr='90001', effective_user='CurFM')]
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'FrozenFM', 'frozen', 'success'),
        ):
            groups = gwp.group_source_rows(rows)
        self.assertTrue(
            any(k.endswith('_USER_FrozenFM') for k in groups),
            f"WR_FILTER dropped the _USER_ primary group: {list(groups)}",
        )

    def test_exclude_wrs_drops_user_primary_group(self):
        gwp.EXCLUDE_WRS = ['90001']
        rows = [_make_primary_row(1, wr='90001', effective_user='CurFM')]
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'FrozenFM', 'frozen', 'success'),
        ):
            groups = gwp.group_source_rows(rows)
        self.assertEqual(
            [k for k in groups if k.endswith('_USER_FrozenFM')], [],
            f"EXCLUDE_WRS failed to drop the _USER_ primary group: {list(groups)}",
        )
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_primary_claim_attribution.py::TestWrFilterMatchesUserVariant -v`
Expected: `test_wr_filter_retains_user_primary_group` FAILS (matcher drops the `_USER_` group); `test_exclude_wrs_drops_user_primary_group` PASSES (exclude matcher already has the `_USER_` clause).

- [ ] **Step 3: Add the `_USER_` clause to `_key_matches_wr`**

In `generate_weekly_pdfs.py`, in `_key_matches_wr`'s return expression (~line 5833), find:

```python
            return (
                suffix == wr
                or suffix.startswith(f"{wr}_HELPER_")
                or suffix == f"{wr}_VACCREW"
                # Subproject C: per-claimer vac key {wr}_VACCREW_<claimer>
                # (attribution on). Prefix-match so EXCLUDE_WRS / WR_FILTER
                # cover both the legacy bare and the per-claimer shapes.
                or suffix.startswith(f"{wr}_VACCREW_")
                # Phase 1 subcontractor variants (REVIEW-CR-03).
                or suffix == f"{wr}_REDUCEDSUB"
                or suffix == f"{wr}_AEPBILLABLE"
                or suffix.startswith(f"{wr}_REDUCEDSUB_HELPER_")
                or suffix.startswith(f"{wr}_AEPBILLABLE_HELPER_")
            )
```

Insert the `_USER_` clause after the `suffix == wr` line:

```python
            return (
                suffix == wr
                # Subproject D: per-claimer primary key {wr}_USER_<claimer>
                # (attribution on). Mirror of the _key_matches_excluded_wr
                # clause below — the two matchers MUST stay in sync.
                or suffix.startswith(f"{wr}_USER_")
                or suffix.startswith(f"{wr}_HELPER_")
                or suffix == f"{wr}_VACCREW"
                # Subproject C: per-claimer vac key {wr}_VACCREW_<claimer>
                # (attribution on). Prefix-match so EXCLUDE_WRS / WR_FILTER
                # cover both the legacy bare and the per-claimer shapes.
                or suffix.startswith(f"{wr}_VACCREW_")
                # Phase 1 subcontractor variants (REVIEW-CR-03).
                or suffix == f"{wr}_REDUCEDSUB"
                or suffix == f"{wr}_AEPBILLABLE"
                or suffix.startswith(f"{wr}_REDUCEDSUB_HELPER_")
                or suffix.startswith(f"{wr}_AEPBILLABLE_HELPER_")
            )
```

> Also update the comment block above `_key_matches_wr` (the `# k format examples` list, ~line 5826) — change the parenthetical "minus the `_USER_` legacy clause, which has never been a WR_FILTER target" note to reflect that `_USER_` is now matched (Subproject D). Add a `MMDDYY_WR_USER_<name>  → primary (Subproject D)` line to the examples comment for both matchers if not already present.

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_primary_claim_attribution.py::TestWrFilterMatchesUserVariant -v`
Expected: PASS (both).

- [ ] **Step 5: Syntax check + commit**

```bash
python -m py_compile generate_weekly_pdfs.py
git add generate_weekly_pdfs.py tests/test_primary_claim_attribution.py
git commit -m "feat(billing): Subproject D — WR_FILTER matcher covers _USER_ primary key"
```

---

## Task 8: `_build_primary_wr_scope` helper

**Files:**
- Modify: `generate_weekly_pdfs.py` (new helper after `_build_vac_crew_wr_scope`, ~line 3303)
- Test: `tests/test_primary_claim_attribution.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_primary_claim_attribution.py`:

```python
class TestBuildPrimaryWrScope(unittest.TestCase):
    """Task 8: scope helper returns sanitized WRs with a partitioned
    _USER_ primary group in this run."""

    def test_scope_collects_partitioned_primary_wrs(self):
        groups = {
            '041926_90001_USER_Alice': [{'Work Request #': '90001'}],
            '041926_90002_USER_Bob': [{'Work Request #': '90002'}],
            '041926_90003_HELPER_Carol': [{'Work Request #': '90003'}],
            '041926_90004_VACCREW_Dan': [{'Work Request #': '90004'}],
            '041926_90005_REDUCEDSUB_USER_Eve': [{'Work Request #': '90005'}],
            '041926_90006': [{'Work Request #': '90006'}],  # bare primary (OFF mode)
        }
        scope = gwp._build_primary_wr_scope(groups)
        self.assertIn('90001', scope)
        self.assertIn('90002', scope)
        # Helper / vac / subcontractor / bare-primary groups are NOT scope.
        self.assertNotIn('90003', scope)
        self.assertNotIn('90004', scope)
        self.assertNotIn('90005', scope)  # REDUCEDSUB_USER is B's, not D's
        self.assertNotIn('90006', scope)

    def test_empty_groups(self):
        self.assertEqual(gwp._build_primary_wr_scope({}), set())
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_primary_claim_attribution.py::TestBuildPrimaryWrScope -v`
Expected: FAIL — `AttributeError: ... has no attribute '_build_primary_wr_scope'`.

- [ ] **Step 3: Implement the helper**

In `generate_weekly_pdfs.py`, immediately after the `_build_vac_crew_wr_scope` function ends (~line 3303, before `def _run_phase_1_1_hash_prune`), add:

```python
def _build_primary_wr_scope(groups: dict) -> set[str]:
    """Return the set of sanitized WR tokens that have a partitioned
    production-primary ``_USER_`` group in this run (Subproject D).

    A group key is a partitioned primary iff it contains ``'_USER_'`` AND
    is NOT a subcontractor primary variant (``'_REDUCEDSUB'`` /
    ``'_AEPBILLABLE'`` — those carry ``_USER_`` too but are owned by
    Subproject B and route through B's own scope/cleanup). Helper
    (``_HELPER_``) and vac (``_VACCREW``) groups never match because they
    do not contain ``_USER_``.

    Shared by ``_run_subproject_d_hash_prune`` (hash-prune scope) and the
    TARGET ``cleanup_untracked_sheet_attachments`` call site (bare-primary
    migration scope). A single implementation prevents the scope-build
    drift that the [2026-05-15 12:00] three-site invariant warns against.
    """
    _scope: set[str] = set()
    for _key, _g_rows in groups.items():
        if (
            '_USER_' in _key
            and '_REDUCEDSUB' not in _key
            and '_AEPBILLABLE' not in _key
            and _g_rows
        ):
            _g_wr_raw = _g_rows[0].get('Work Request #', '')
            _g_wr = str(_g_wr_raw).split('.')[0]
            _g_wr = _RE_SANITIZE_HELPER_NAME.sub('_', _g_wr)[:50]
            if _g_wr:
                _scope.add(_g_wr)
    return _scope
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_primary_claim_attribution.py::TestBuildPrimaryWrScope -v`
Expected: PASS.

- [ ] **Step 5: Syntax check + commit**

```bash
python -m py_compile generate_weekly_pdfs.py
git add generate_weekly_pdfs.py tests/test_primary_claim_attribution.py
git commit -m "feat(billing): Subproject D — _build_primary_wr_scope helper"
```

---

## Task 9: `_run_subproject_d_hash_prune` + wire into the prune call site

**Files:**
- Modify: `generate_weekly_pdfs.py` (new function after `_run_vac_crew_hash_prune` ~line 3589; call-site wiring ~line 7715)
- Test: `tests/test_primary_claim_attribution.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_primary_claim_attribution.py`:

```python
class TestSubprojectDHashPrune(unittest.TestCase):
    """Task 9: one-time prune of legacy bare-primary orphans, gated +
    idempotent + migration-dirty bool."""

    def setUp(self):
        _ensure_smartsheet_mocked()
        self._attr = gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = True

    def tearDown(self):
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = self._attr

    def _groups(self):
        return {'041926_90001_USER_Alice': [{'Work Request #': '90001'}]}

    def test_drops_bare_primary_orphan_for_in_scope_wr(self):
        hist = {
            '90001|041926|primary|': {'hash': 'x'},   # legacy bare orphan
            '90001|041926|primary|Alice': {'hash': 'y'},  # new per-claimer (kept)
            '90002|041926|primary|': {'hash': 'z'},   # out-of-scope (kept)
        }
        mutated = gwp._run_subproject_d_hash_prune(hist, self._groups())
        self.assertTrue(mutated)
        self.assertNotIn('90001|041926|primary|', hist)
        self.assertIn('90001|041926|primary|Alice', hist)
        self.assertIn('90002|041926|primary|', hist)
        self.assertEqual(
            hist['_subproject_d_prune_version'],
            gwp.SUBPROJECT_D_HASH_PRUNE_VERSION,
        )

    def test_idempotent_second_run_is_noop(self):
        hist = {'_subproject_d_prune_version': gwp.SUBPROJECT_D_HASH_PRUNE_VERSION}
        mutated = gwp._run_subproject_d_hash_prune(hist, self._groups())
        self.assertFalse(mutated)

    def test_kill_switch_off_skips_and_no_sentinel_advance(self):
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = False
        hist = {'90001|041926|primary|': {'hash': 'x'}}
        mutated = gwp._run_subproject_d_hash_prune(hist, self._groups())
        self.assertFalse(mutated)
        # OFF: the bare key is the ACTIVE legacy format — must NOT be dropped.
        self.assertIn('90001|041926|primary|', hist)
        self.assertNotIn('_subproject_d_prune_version', hist)

    def test_call_site_wired_into_migration_dirty(self):
        src = inspect.getsource(generate_weekly_pdfs)
        self.assertRegex(
            src,
            r"if _run_subproject_d_hash_prune\(hash_history, groups\):"
            r"\s*\n\s*_hash_history_migration_dirty = True",
        )
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_primary_claim_attribution.py::TestSubprojectDHashPrune -v`
Expected: FAIL — function not defined.

- [ ] **Step 3a: Implement `_run_subproject_d_hash_prune`**

In `generate_weekly_pdfs.py`, immediately after `_run_vac_crew_hash_prune` ends (~line 3589, before `def load_billing_audit_row_cache`), add:

```python
def _run_subproject_d_hash_prune(hash_history: dict, groups: dict) -> bool:
    """Subproject D (2026-05-25): idempotent one-time hash-history prune.

    Drops LEGACY blank-identifier production-primary orphans — 4-part keys
    ``wr|week|primary|`` with an EMPTY identifier — for WRs that have a
    partitioned ``_USER_`` primary group in this run. D re-partitions the
    production primary variant by frozen claimer (new keys carry a
    non-empty identifier), so the blank-identifier entries are obsolete.
    The normal stale-prune at the end of the run would clear them
    eventually; this makes the migration deterministic on the first run
    and survives interrupted / no-update runs.

    Scope-building delegates to ``_build_primary_wr_scope`` (shared with
    the TARGET cleanup call site — no drift, per the [2026-05-15 12:00]
    three-site invariant). Sentinel key ``_subproject_d_prune_version`` is
    DISTINCT from the Phase 1.1 / Subproject B / Subproject C sentinels so
    all four migrations are independent. Mutates ``hash_history`` in place.
    Dropping a hash entry costs at most one benign regeneration — never
    data loss — so no live-identity exemption is needed on this drop path
    (unlike the every-run attachment cleanup).

    GATED on ``PRIMARY_CLAIM_ATTRIBUTION_ENABLED``: when OFF, the
    blank-identifier ``wr|week|primary|`` key is the ACTIVE legacy format
    (the kill-switch-OFF path emits the bare primary key), so pruning it
    would delete valid current history and force regeneration churn —
    breaking the exact-legacy contract. Skip entirely when the flag is
    off, and do NOT advance the sentinel, so the one-time migration still
    runs if attribution is later enabled. (Mirrors the Subproject C
    ``_run_vac_crew_hash_prune`` kill-switch guard.)
    """
    if not PRIMARY_CLAIM_ATTRIBUTION_ENABLED:
        return False
    _persisted = hash_history.pop('_subproject_d_prune_version', 0)
    if (
        isinstance(_persisted, int)
        and _persisted >= SUBPROJECT_D_HASH_PRUNE_VERSION
    ):
        hash_history['_subproject_d_prune_version'] = _persisted
        return False

    _scope = _build_primary_wr_scope(groups)
    _orphans: list[str] = []
    for _hk in list(hash_history.keys()):
        if isinstance(_hk, str) and _hk.startswith('_'):
            continue
        _parts = str(_hk).split('|')
        if len(_parts) != 4:
            continue
        _hk_wr, _hk_week, _hk_variant, _hk_ident = _parts
        if (
            _hk_wr in _scope
            and _hk_variant == 'primary'
            and _hk_ident == ''
        ):
            _orphans.append(_hk)
    for _ok in _orphans:
        del hash_history[_ok]
    hash_history['_subproject_d_prune_version'] = SUBPROJECT_D_HASH_PRUNE_VERSION
    if _orphans:
        _wr_sample = sorted({k.split('|')[0] for k in _orphans})[:20]
        logging.info(
            f"🧹 Subproject D hash-history prune: dropped {len(_orphans)} "
            f"legacy unpartitioned primary orphan(s) "
            f"(affected WRs first 20: {_wr_sample})"
        )
    else:
        logging.info(
            "🧹 Subproject D hash-history prune: no legacy unpartitioned "
            "primary orphans to drop"
        )
    return True
```

- [ ] **Step 3b: Register the PII log marker**

The new INFO log body `"Subproject D hash-history prune"` embeds no PII (only counts + sanitized WR numbers), matching the B/C prune logs. Find the `_PII_LOG_MARKERS` list and confirm the B entry `"Subproject B hash-history prune"` is present; add a sibling entry `"Subproject D hash-history prune"` directly after the C/B prune markers for consistency with the [2026-05-15 12:00] rule 3 (explicit marker per new INFO group log). Search for `"Subproject B hash-history prune"` in the `_PII_LOG_MARKERS` definition and add:

```python
    "Subproject D hash-history prune",
```

- [ ] **Step 3c: Wire into the prune call site**

In `generate_weekly_pdfs.py`, after the Subproject C prune block (~line 7715, the `try: if _run_vac_crew_hash_prune(...)` ... `except Exception as _vc_prune_exc:` block), add:

```python
        # Subproject D: one-time prune of legacy blank-identifier primary
        # orphans (kill switch is PRIMARY_CLAIM_ATTRIBUTION_ENABLED + the
        # version constant). Fail-safe — a failed prune must not break the
        # run.
        try:
            if _run_subproject_d_hash_prune(hash_history, groups):
                _hash_history_migration_dirty = True
        except Exception as _d_prune_exc:
            logging.warning(
                f"⚠️ Subproject D hash-history prune failed; continuing "
                f"with existing history: {_d_prune_exc!r}"
            )
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_primary_claim_attribution.py::TestSubprojectDHashPrune -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Syntax check + commit**

```bash
python -m py_compile generate_weekly_pdfs.py
git add generate_weekly_pdfs.py tests/test_primary_claim_attribution.py
git commit -m "feat(billing): Subproject D — one-time bare-primary hash prune"
```

---

## Task 10: `cleanup_untracked_sheet_attachments` — `primary_wr_scope` param, gate, TARGET call site

**Files:**
- Modify: `generate_weekly_pdfs.py` (function signature + docstring ~line 2760-2842; new gate in the attachment loop ~line 2963; TARGET call site ~line 8834)
- Test: `tests/test_primary_claim_attribution.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_primary_claim_attribution.py`:

```python
class TestBarePrimaryCleanup(unittest.TestCase):
    """Task 10: forced bare-primary attachment cleanup on TARGET, gated +
    valid_wr_weeks-exempt."""

    def setUp(self):
        _ensure_smartsheet_mocked()

    def _att(self, name):
        a = mock.MagicMock()
        a.name = name
        a.id = name
        return a

    def _run(self, attachments, valid_wr_weeks, primary_wr_scope):
        client = mock.MagicMock()
        sheet = mock.MagicMock()
        row = mock.MagicMock()
        row.id = 1
        sheet.rows = [row]
        client.Attachments.list_row_attachments.return_value.data = attachments
        deleted = []
        client.Attachments.delete_attachment.side_effect = (
            lambda sid, aid: deleted.append(aid)
        )
        gwp.cleanup_untracked_sheet_attachments(
            client, 12345, valid_wr_weeks, False,
            target_sheet=sheet,
            primary_wr_scope=primary_wr_scope,
        )
        return deleted

    def test_in_scope_bare_primary_deleted(self):
        bare = self._att("WR_90001_WeekEnding_041926_120000_aaaaaaaaaaaaaaaa.xlsx")
        deleted = self._run([bare], valid_wr_weeks=set(), primary_wr_scope={'90001'})
        self.assertIn(bare.id, deleted)

    def test_live_per_claimer_not_deleted(self):
        live = self._att("WR_90001_WeekEnding_041926_120000_User_Alice_aaaaaaaaaaaaaaaa.xlsx")
        # Per-claimer file is identity ('90001','041926','primary','Alice');
        # it's in valid_wr_weeks this run and has a non-empty identifier.
        vww = {('90001', '041926', 'primary', 'Alice')}
        deleted = self._run([live], valid_wr_weeks=vww, primary_wr_scope={'90001'})
        self.assertNotIn(live.id, deleted)

    def test_overlapping_live_bare_exempt_via_valid_wr_weeks(self):
        # A bare primary whose identity IS in valid_wr_weeks (e.g. OFF for
        # those rows) must be exempt.
        bare = self._att("WR_90001_WeekEnding_041926_120000_aaaaaaaaaaaaaaaa.xlsx")
        vww = {('90001', '041926', 'primary', None)}
        deleted = self._run([bare], valid_wr_weeks=vww, primary_wr_scope={'90001'})
        self.assertNotIn(bare.id, deleted)

    def test_out_of_scope_bare_primary_kept(self):
        bare = self._att("WR_90099_WeekEnding_041926_120000_aaaaaaaaaaaaaaaa.xlsx")
        deleted = self._run([bare], valid_wr_weeks=set(), primary_wr_scope={'90001'})
        self.assertNotIn(bare.id, deleted)

    def test_none_scope_is_noop(self):
        bare = self._att("WR_90001_WeekEnding_041926_120000_aaaaaaaaaaaaaaaa.xlsx")
        deleted = self._run([bare], valid_wr_weeks=set(), primary_wr_scope=None)
        self.assertNotIn(bare.id, deleted)
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_primary_claim_attribution.py::TestBarePrimaryCleanup -v`
Expected: FAIL — `cleanup_untracked_sheet_attachments() got an unexpected keyword argument 'primary_wr_scope'`.

- [ ] **Step 3a: Add the parameter to the signature**

In `generate_weekly_pdfs.py`, in the `cleanup_untracked_sheet_attachments` signature (~line 2760-2772), add a new parameter after `vac_legacy_wr_scope`:

```python
    vac_legacy_wr_scope: set[str] | None = None,
    primary_wr_scope: set[str] | None = None,
):
```

- [ ] **Step 3b: Add the docstring entry**

In the docstring, after the `vac_legacy_wr_scope:` paragraph (~line 2836), add:

```python
    primary_wr_scope: Subproject D (2026-05-25) one-time migration. When
        provided, any attachment whose parsed ``wr`` is in this set, whose
        parsed ``variant`` is ``'primary'``, and whose parsed ``identifier``
        is empty (legacy unpartitioned bare ``primary``) is unconditionally
        deleted — UNLESS its identity is in ``valid_wr_weeks`` (live-identity
        exemption). Per-claimer files (non-empty identifier like
        ``_User_Alice``) are never matched. When None (default), this gate
        is skipped — byte-identical legacy behaviour for callers that do
        not pass the parameter. Gated at the TARGET call site by
        PRIMARY_CLAIM_ATTRIBUTION_ENABLED and
        LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED. Non-subcontractor primary
        files route to TARGET_SHEET_ID only — the PPP call site must NOT
        receive this parameter.
```

- [ ] **Step 3c: Add the gate inside the attachment loop**

In `generate_weekly_pdfs.py`, immediately after the `vac_legacy_wr_scope` gate block (the one ending `off_contract_attachments.append(att)` / `continue` ~line 2963) and BEFORE `identity_groups[ident].append(att)`, add:

```python
                    # Subproject D (2026-05-25): one-time migration —
                    # delete LEGACY UNPARTITIONED bare ``primary``
                    # attachments (parsed identifier == '') for in-scope
                    # NON-subcontractor WRs. D re-partitions production
                    # primary files by frozen claimer (``_User_<name>``),
                    # so the old bare one-file-per-WR attachment is an
                    # obsolete duplicate. The ``not _identifier`` check is
                    # the precise legacy selector: new per-claimer files
                    # carry a non-empty identifier and are NOT deleted here.
                    # WR-01 live-identity exemption: an attachment whose
                    # identity IS in ``valid_wr_weeks`` is kept — this
                    # protects a legitimate bare-primary file the current
                    # run produced (e.g. an overlapping WR still emitting
                    # bare primary because attribution was disabled for
                    # those rows) from an every-run delete/regenerate churn.
                    if (
                        primary_wr_scope is not None
                        and wr in primary_wr_scope
                        and variant == 'primary'
                        and not _identifier
                        and ident not in valid_wr_weeks
                    ):
                        off_contract_attachments.append(att)
                        continue
```

- [ ] **Step 3d: Wire the TARGET call site**

In `generate_weekly_pdfs.py`, find the `_vac_scope = (...)` block immediately before the TARGET `cleanup_untracked_sheet_attachments(...)` call (~line 8828-8832) and add after it:

```python
            # Subproject D (2026-05-25): build the non-subcontractor
            # primary WR scope for legacy bare-primary cleanup on TARGET.
            # Gated on BOTH the attribution kill switch (the partitioned
            # _USER_ groups only exist when attribution is on) AND the
            # cleanup kill switch. primary files route to TARGET only —
            # do NOT pass this to PPP.
            _primary_scope = (
                _build_primary_wr_scope(groups)
                if (
                    PRIMARY_CLAIM_ATTRIBUTION_ENABLED
                    and LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED
                )
                else None
            )
```

Then in the TARGET `cleanup_untracked_sheet_attachments(...)` call (~line 8834), add the new kwarg after `vac_legacy_wr_scope=_vac_scope,`:

```python
                    vac_legacy_wr_scope=_vac_scope,
                    primary_wr_scope=_primary_scope,
                )
```

> Do NOT add `primary_wr_scope` to the PPP call site (~line 8908). Non-subcontractor primary files never route to PPP.

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_primary_claim_attribution.py::TestBarePrimaryCleanup -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Syntax check + commit**

```bash
python -m py_compile generate_weekly_pdfs.py
git add generate_weekly_pdfs.py tests/test_primary_claim_attribution.py
git commit -m "feat(billing): Subproject D — forced bare-primary cleanup on TARGET"
```

---

## Task 11: `build_group_identity` round-trip regression + production-invariants source-grep

No production code change — the parser already handles `_User_<name>`. This task locks the contract and the four-site lockstep against silent regression.

**Files:**
- Test: `tests/test_primary_claim_attribution.py`

- [ ] **Step 1: Write the tests**

Append to `tests/test_primary_claim_attribution.py`:

```python
class TestBuildGroupIdentityPrimaryUserRoundTrip(unittest.TestCase):
    """Task 11: parser round-trips D's _User_<claimer> primary filename."""

    def test_plain_claimer(self):
        self.assertEqual(
            gwp.build_group_identity(
                "WR_90001_WeekEnding_041926_120000_User_Alice_aaaaaaaaaaaaaaaa.xlsx"
            ),
            ('90001', '041926', 'primary', 'Alice'),
        )

    def test_underscored_claimer(self):
        self.assertEqual(
            gwp.build_group_identity(
                "WR_90001_WeekEnding_041926_120000_User_Jane_Smith_aaaaaaaaaaaaaaaa.xlsx"
            ),
            ('90001', '041926', 'primary', 'Jane_Smith'),
        )

    def test_bare_primary_still_parses(self):
        # OFF-mode legacy bare primary -> identifier None.
        self.assertEqual(
            gwp.build_group_identity(
                "WR_90001_WeekEnding_041926_120000_aaaaaaaaaaaaaaaa.xlsx"
            ),
            ('90001', '041926', 'primary', None),
        )


class TestSubprojectDProductionInvariants(unittest.TestCase):
    """Task 11: source-grep guards for the four-site lockstep + matcher
    mirror + filename suffix + prune-kill-switch gate."""

    @classmethod
    def setUpClass(cls):
        with open(inspect.getsourcefile(generate_weekly_pdfs), encoding='utf-8') as f:
            cls.src = f.read()

    def test_filename_suffix_user_gated(self):
        self.assertRegex(
            self.src,
            r"PRIMARY_CLAIM_ATTRIBUTION_ENABLED and _pf[\s\S]{0,200}_User_\{",
        )

    def test_wr_filter_matcher_has_user_clause(self):
        # Both matchers must carry the _USER_ prefix clause (count >= 2).
        self.assertGreaterEqual(
            self.src.count('startswith(f"{wr}_USER_")'), 2,
            "both _key_matches_wr and _key_matches_excluded_wr must match _USER_",
        )

    def test_prune_gated_on_kill_switch(self):
        self.assertRegex(
            self.src,
            r"def _run_subproject_d_hash_prune[\s\S]{0,400}"
            r"if not PRIMARY_CLAIM_ATTRIBUTION_ENABLED:\s*\n\s*return False",
        )

    def test_prune_wired_into_call_site(self):
        self.assertIn("_run_subproject_d_hash_prune(hash_history, groups)", self.src)

    def test_cleanup_has_primary_wr_scope_param(self):
        self.assertIn("primary_wr_scope: set[str] | None = None", self.src)
```

- [ ] **Step 2: Run to verify they pass**

Run: `pytest tests/test_primary_claim_attribution.py::TestBuildGroupIdentityPrimaryUserRoundTrip tests/test_primary_claim_attribution.py::TestSubprojectDProductionInvariants -v`
Expected: PASS (all). If any source-grep fails, an earlier task's edit drifted from the plan — fix the earlier edit, do not weaken the test.

- [ ] **Step 3: Commit**

```bash
git add tests/test_primary_claim_attribution.py
git commit -m "test(billing): Subproject D — parser round-trip + production invariants"
```

---

## Task 12: Workflow pin + environment.md documentation

**Files:**
- Modify: `.github/workflows/weekly-excel-generation.yml` (env block ~line 393, after `VAC_CREW_LEGACY_CLEANUP_ENABLED: '1'`)
- Modify: `website/docs/reference/environment.md` (after the `VAC_CREW_LEGACY_CLEANUP_ENABLED` section ~line 420+)

- [ ] **Step 1: Pin both env vars in the workflow**

In `.github/workflows/weekly-excel-generation.yml`, after the `VAC_CREW_LEGACY_CLEANUP_ENABLED: '1'` line (~line 393), add:

```yaml

          # Sub-project D (2026-05-25): kill switch for per-claimer
          # partitioning of the PRODUCTION primary Excel files by frozen
          # primary foreman from billing_audit.attribution_snapshot. Set
          # to '0' to preserve legacy one-file-per-WR bare primary
          # behavior. Unlike Subproject B, the core primary path never
          # holds on a Supabase outage — it falls back to the current
          # foreman and still generates. Living Ledger [2026-05-25].
          PRIMARY_CLAIM_ATTRIBUTION_ENABLED: '1'
          # Sub-project D (2026-05-25): kill switch for the one-time
          # removal of legacy UNPARTITIONED bare primary attachments (no
          # _User_ token) on TARGET_SHEET_ID for non-subcontractor WRs.
          # Set to '0' to skip the destructive cleanup (legacy duplicates
          # persist until removed manually). Separate from
          # PRIMARY_CLAIM_ATTRIBUTION_ENABLED (which gates attribution
          # resolution, NOT this cleanup). Living Ledger [2026-05-25].
          LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED: '1'
```

- [ ] **Step 2: Document both env vars**

In `website/docs/reference/environment.md`, after the `VAC_CREW_LEGACY_CLEANUP_ENABLED` section (find the `### `VAC_CREW_LEGACY_CLEANUP_ENABLED`` heading and the end of its body), add two new sections that mirror the C sections' structure:

```markdown
### `PRIMARY_CLAIM_ATTRIBUTION_ENABLED`

**Default:** `1` (enabled). Truthy values: `1`, `true`, `yes`, `on`.

Sub-project D. When enabled, the production primary Excel files (every
non-subcontractor WR) are partitioned by the **frozen primary foreman**
who claimed each line item — read from `billing_audit.attribution_snapshot`
via `resolve_claimer('primary', …)` — and named
`WR_..._WeekEnding_..._User_<claimer>_<hash>.xlsx`. A WR+week claimed by
two foremen produces two files, one per claimer.

Unlike Sub-project B (subcontractor primary), the core primary path
**never holds** on a Supabase outage: if attribution can't be read
(`fetch_failure`), or there is no frozen row yet (`no_history`), the row
falls back to the **current** foreman and the file is still generated.
This is deliberate — D covers every non-subcontractor WR, so holding on an
outage would suppress all primary billing for that run.

Set to `0` to revert to the legacy one-file-per-WR bare primary behavior
(`WR_..._WeekEnding_..._<hash>.xlsx`). The resolved value is printed at
startup as `📋 PRIMARY_CLAIM_ATTRIBUTION_ENABLED=<bool>`. Pinned to `1`
in the `weekly-excel-generation.yml` `env:` block.

### `LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED`

**Default:** `1` (enabled). Truthy values: `1`, `true`, `yes`, `on`.

Sub-project D one-time migration. When enabled, the legacy UNPARTITIONED
bare primary attachments (no `_User_` token) on `TARGET_SHEET_ID` for
non-subcontractor WRs that now produce a partitioned `_User_<claimer>`
file are deleted — UNLESS the bare file's identity is live this run
(`valid_wr_weeks` exemption). A matching one-time hash-history prune
(`_subproject_d_prune_version` sentinel) drops the stale
`{wr}|{week}|primary|` entries.

**Separate from `PRIMARY_CLAIM_ATTRIBUTION_ENABLED`,** which gates
attribution resolution, NOT this cleanup. Set to `0` to skip the
destructive cleanup (legacy bare-primary duplicates persist until removed
manually). The resolved value is printed at startup as
`📋 LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED=<bool>`. Pinned to `1` in the
`weekly-excel-generation.yml` `env:` block alongside
`PRIMARY_CLAIM_ATTRIBUTION_ENABLED`.
```

- [ ] **Step 3: Validate docs build**

```bash
cd website && npm run typecheck && npm run build && cd ..
```
Expected: build succeeds, no broken links.

> If `npm` is unavailable in the execution environment, skip the build but visually confirm the two new sections render as valid Markdown (headings, code fences balanced).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/weekly-excel-generation.yml website/docs/reference/environment.md
git commit -m "docs(billing): Subproject D — pin + document primary attribution env vars"
```

---

## Task 13: Living Ledger entry + full-suite verification

**Files:**
- Modify: `CLAUDE.md` (append to the Living Ledger section at the bottom)

- [ ] **Step 1: Run the full suite (baseline gate)**

Run: `pytest tests/`
Expected: all green; net new D tests added (target ≥ 30 new test methods); total should be ~844+ passed (was 814), 0 failed.
If anything is red, fix the offending task's code before proceeding — do NOT write the ledger entry on a red suite.

- [ ] **Step 2: Syntax + smoke check**

```bash
python -m py_compile generate_weekly_pdfs.py
TEST_MODE=true SKIP_UPLOAD=true python generate_weekly_pdfs.py
```
Expected: `py_compile` silent (success); `TEST_MODE` run completes without traceback and the startup banner shows
`📋 PRIMARY_CLAIM_ATTRIBUTION_ENABLED=True` and
`📋 LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED=True`.

> On Windows PowerShell, set env vars inline differently: `$env:TEST_MODE='true'; $env:SKIP_UPLOAD='true'; python generate_weekly_pdfs.py` (then clear them).

- [ ] **Step 3: Append the Living Ledger entry**

In `CLAUDE.md`, append a new dated entry to the Living Ledger (use the actual completion timestamp). The entry MUST cover: the goal (production primary partitioned by frozen claimer → `_User_<claimer>`); the no-HOLD operator decision and WHY (core path covers every WR; HOLD would suppress all primary billing on outage); the two kill switches; the corrected spec finding (generate_excel primary filename branch needed the `_User_` suffix — it was `''` unconditionally); the four-site lockstep + the WR_FILTER matcher mirror; the migration (forced bare-primary TARGET cleanup + one-time prune, distinct `_subproject_d_prune_version` sentinel, gated on the attribution kill switch); and the regression test file `tests/test_primary_claim_attribution.py`. Follow the prose style of the existing `[2026-05-21 …]` Subproject B/C entries.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(billing): Living Ledger — Subproject D primary claim attribution"
```

- [ ] **Step 5: Final full-suite confirmation before review**

Run: `pytest tests/`
Expected: green. The branch is now ready for `superpowers:finishing-a-development-branch` (PR + cross-AI review).

---

## Self-review checklist (completed during plan authoring)

- **Spec coverage:** Every spec section maps to a task — config/kill switches (T1), filename suffix correction (T2), pre-pass (T3), emission partition (T4), four-site lockstep sites a/b/c (T5/T6; parser is no-change, regression in T11), WR matcher mirror (T7), migration scope helper (T8) + hash prune (T9) + forced bare-primary cleanup (T10), no-HOLD policy (T3/T4 emission consume `hold` as current), workflow pin + docs (T12), ledger (T13). No gaps.
- **Placeholder scan:** No TBD/TODO; every code step shows complete code; every test step shows real assertions.
- **Type/name consistency:** `_primary_claimer_map`, `_build_primary_wr_scope`, `_run_subproject_d_hash_prune`, `_subproject_d_prune_version`, `SUBPROJECT_D_HASH_PRUNE_VERSION`, `PRIMARY_CLAIM_ATTRIBUTION_ENABLED`, `LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED`, `primary_wr_scope`, `_User_<claimer>` token, `_RE_SANITIZE_IDENTIFIER` — used identically across all tasks. `resolve_claimer('primary', …)` matches `ROLE_BY_VARIANT['primary']`.
