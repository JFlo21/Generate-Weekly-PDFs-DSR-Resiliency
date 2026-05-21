# Subproject B — Subcontractor Primary Claim Attribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-partition the subcontractor primary Excel variants (`reduced_sub` / `aep_billable`) by the frozen primary claimer from `billing_audit`, consuming Foundation A's `resolve_claimer` + HOLD contract, with a clean migration of legacy unpartitioned files.

**Architecture:** A parallel attribution pre-pass at the top of `group_source_rows` builds a `{__row_id: ResolveOutcome}` map (one `resolve_claimer` call per subcontractor row, in a bounded `ThreadPoolExecutor`). The subcontractor variant-emission block reads the map: `use` → group/name by the claimer (`_ReducedSub_User_<name>` / `_AEPBillable_User_<name>`); `hold` → defer the row and record a HOLD. The filename parser, three main-loop identity sites, attachment-cleanup migration, and a one-time hash-history prune are extended in lockstep. The Phase 1.1 helper-shadow path is left untouched.

**Tech Stack:** Python 3.10+, `openpyxl`, Smartsheet SDK, Supabase (via `billing_audit`), `unittest`/`pytest`, GitHub Actions.

---

## Background the engineer needs

- **Foundation A** (`billing_audit/writer.py`) already provides:
  - `resolve_claimer(variant, current_value, *, wr, week_ending, row_id, enabled) -> ResolveOutcome` where `ResolveOutcome = NamedTuple(action: 'use'|'hold', name: str|None, source, reason)`.
  - `ROLE_BY_VARIANT` maps `reduced_sub`/`aep_billable` → `primary_foreman`.
  - `record_attribution_hold(wr, week_ending, variant)` and `summarize_attribution_holds() -> str|None` (dormant — B is the first consumer).
  - `_reset_counters_for_tests()` clears counters AND `_attribution_holds`.
- **Do not modify `billing_audit/`** — everything B needs is already there.
- **Spec:** `docs/superpowers/specs/2026-05-20-subproject-b-subcontractor-primary-claim-attribution-design.md`.
- **Repo rules that govern this work** (CLAUDE.md Living Ledger):
  - The three identity sites + parser MUST stay in lockstep ([2026-05-15] CR-01).
  - Destructive cleanup paths get their own default-on kill switch ([2026-05-19 22:00] #4).
  - Row-flow changes need TRUE end-to-end tests, not static mirrors ([2026-05-20 00:26] #4).
  - New env vars are workflow-pinned ([2026-05-15 12:00] #7).
  - New INFO log bodies get explicit `_PII_LOG_MARKERS` entries ([2026-05-15 12:00] #3).

## Run commands

- Full suite (must pass before any push): `pytest tests/ -v`
- Single new file: `pytest tests/test_subcontractor_primary_claim_attribution.py -v`
- Syntax check: `python -m py_compile generate_weekly_pdfs.py`

## File structure

- **Create:** `tests/test_subcontractor_primary_claim_attribution.py` — the entire B test suite.
- **Modify:** `generate_weekly_pdfs.py` — parser, config, filename helper, pre-pass+emission, three identity sites, HOLD summary call, cleanup param + call sites, hash-prune helper + version + call site + PII marker.
- **Modify:** `.github/workflows/weekly-excel-generation.yml` — pin `SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED`.
- **Modify:** `website/docs/reference/environment.md` — document new var + broaden the attribution flag's scope.
- **Modify:** `CLAUDE.md` — Living Ledger entry (final task).
- **Not modified:** `billing_audit/`.

---

## Task 1: Parser — `build_group_identity` parses `_User_` token in ReducedSub/AEPBillable

**Files:**
- Modify: `generate_weekly_pdfs.py:2575-2585` (the `'ReducedSub' in tail` / `'AEPBillable' in tail` else-branches)
- Test: `tests/test_subcontractor_primary_claim_attribution.py`

- [ ] **Step 1: Create the test file header + write the failing test**

Create `tests/test_subcontractor_primary_claim_attribution.py` with this content:

```python
"""Subproject B — subcontractor primary claim attribution tests.

Drives the real production code paths (parser, group_source_rows
pre-pass + emission, generate_excel filename builder, migration
cleanup, hash prune, HOLD wiring) per the [2026-05-20 00:26] rule 4:
row-flow changes require TRUE end-to-end tests, not static mirrors.
"""

from __future__ import annotations

import datetime
import importlib
import inspect
import os
import pathlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.test_billing_audit_shadow import (
    _reset_all,
    _ensure_smartsheet_mocked,
)

_ensure_smartsheet_mocked()
import generate_weekly_pdfs  # noqa: E402


class TestBuildGroupIdentityParsesPrimaryUserToken(unittest.TestCase):
    """Task 1: _User_ token parses for reduced_sub / aep_billable."""

    def test_reducedsub_user_token_parses_claimer(self):
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_User_John_Doe_abc123.xlsx'
        )
        self.assertEqual(ident, ('91467680', '041926', 'reduced_sub', 'John_Doe'))

    def test_aepbillable_user_token_parses_claimer(self):
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_120000_AEPBillable_User_John_Doe_abc123.xlsx'
        )
        self.assertEqual(ident, ('91467680', '041926', 'aep_billable', 'John_Doe'))

    def test_legacy_reducedsub_parses_empty_identifier(self):
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_abc123.xlsx'
        )
        self.assertEqual(ident, ('91467680', '041926', 'reduced_sub', ''))

    def test_legacy_aepbillable_parses_empty_identifier(self):
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_120000_AEPBillable_abc123.xlsx'
        )
        self.assertEqual(ident, ('91467680', '041926', 'aep_billable', ''))

    def test_reducedsub_helper_still_parses_helper(self):
        # Regression: the new User branch must not break helper-shadow parsing.
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_Helper_Jane_Smith_def456.xlsx'
        )
        self.assertEqual(ident, ('91467680', '041926', 'reduced_sub_helper', 'Jane_Smith'))


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run the failing tests**

Run: `pytest tests/test_subcontractor_primary_claim_attribution.py::TestBuildGroupIdentityParsesPrimaryUserToken -v`
Expected: `test_reducedsub_user_token_parses_claimer` and `test_aepbillable_user_token_parses_claimer` FAIL (legacy parser returns identifier `''`, not `'John_Doe'`). The three other tests PASS.

- [ ] **Step 3: Implement the parser change**

In `generate_weekly_pdfs.py`, replace the `'AEPBillable' in tail` / `'ReducedSub' in tail` blocks (currently lines ~2561-2585) with:

```python
    if 'AEPBillable' in tail:
        aep_idx_rel = tail.index('AEPBillable')
        post_aep = tail[aep_idx_rel + 1:]
        if 'Helper' in post_aep:
            variant = 'aep_billable_helper'
            helper_idx_rel = post_aep.index('Helper')
            if helper_idx_rel + 1 < len(post_aep):
                identifier = '_'.join(post_aep[helper_idx_rel + 1:-1])
        elif post_aep and post_aep[0] == 'User':
            # Subproject B: _AEPBillable_User_<claimer>_<hash>. The
            # 'User' token marks a primary-claimer identifier (reserved,
            # unambiguous vs the 'Helper' token). Span-join so an
            # underscored claimer name survives intact.
            variant = 'aep_billable'
            identifier = '_'.join(post_aep[1:-1])
        else:
            # Legacy unpartitioned _AEPBillable_<hash> (no User token).
            variant = 'aep_billable'
            identifier = ''
    elif 'ReducedSub' in tail:
        rs_idx_rel = tail.index('ReducedSub')
        post_rs = tail[rs_idx_rel + 1:]
        if 'Helper' in post_rs:
            variant = 'reduced_sub_helper'
            helper_idx_rel = post_rs.index('Helper')
            if helper_idx_rel + 1 < len(post_rs):
                identifier = '_'.join(post_rs[helper_idx_rel + 1:-1])
        elif post_rs and post_rs[0] == 'User':
            # Subproject B: _ReducedSub_User_<claimer>_<hash>.
            variant = 'reduced_sub'
            identifier = '_'.join(post_rs[1:-1])
        else:
            # Legacy unpartitioned _ReducedSub_<hash> (no User token).
            variant = 'reduced_sub'
            identifier = ''
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_subcontractor_primary_claim_attribution.py::TestBuildGroupIdentityParsesPrimaryUserToken -v`
Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_subcontractor_primary_claim_attribution.py
git commit -m "feat(billing): parse _User_ primary-claimer token in subcontractor variant filenames (Subproject B)"
```

---

## Task 2: Config — `SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED` kill switch + banner

**Files:**
- Modify: `generate_weekly_pdfs.py:497-499` (after `SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED`), and `:645-648` (banner)
- Test: `tests/test_subcontractor_primary_claim_attribution.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_subcontractor_primary_claim_attribution.py`:

```python
class TestLegacyPrimaryCleanupKillSwitch(unittest.TestCase):
    """Task 2: destructive-migration kill switch + startup banner."""

    def test_kill_switch_attribute_exists_and_is_bool(self):
        self.assertIsInstance(
            generate_weekly_pdfs.SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED,
            bool,
        )

    def test_kill_switch_default_on(self):
        # Default (unset env) resolves to True.
        self.assertTrue(
            generate_weekly_pdfs.SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED,
        )

    def test_banner_line_present_in_source(self):
        src = pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')
        self.assertIn('SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED=', src)
```

- [ ] **Step 2: Run the failing test**

Run: `pytest tests/test_subcontractor_primary_claim_attribution.py::TestLegacyPrimaryCleanupKillSwitch -v`
Expected: FAIL with `AttributeError: module 'generate_weekly_pdfs' has no attribute 'SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED'`.

- [ ] **Step 3: Add the env var**

In `generate_weekly_pdfs.py`, immediately after the `SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED = os.getenv(...)` block (ends ~line 499), add:

```python
# Subproject B (2026-05-20): default-ON kill switch for the one-time
# removal of legacy UNPARTITIONED `_ReducedSub` / `_AEPBillable`
# attachments (no `_User_` token, parsed identifier == '') on
# TARGET_SHEET_ID and SUBCONTRACTOR_PPP_SHEET_ID for subcontractor
# WRs. B re-partitions those variants by frozen primary claimer; the
# legacy one-file-per-WR attachments become duplicate-billing
# leftovers (the Phase 1.1 Bug B2 / SUB-09 trap). Set to '0' to skip
# the destructive cleanup (legacy files then persist until manually
# removed). Separate from SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED
# (which gates attribution resolution, NOT this cleanup). Workflow-
# pinned per [2026-05-15 12:00] rule 7.
SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED = os.getenv(
    'SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')
```

- [ ] **Step 4: Add the banner line**

In `generate_weekly_pdfs.py`, immediately after the `SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED=` banner `logging.info(...)` block (ends ~line 648), add:

```python
# Subproject B: surface resolved kill-switch state at startup so
# operators grepping the banner see the active feature state at a
# glance. Banner body carries no row PII (just the resolved bool).
logging.info(
    f"📋 SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED="
    f"{SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED}"
)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_subcontractor_primary_claim_attribution.py::TestLegacyPrimaryCleanupKillSwitch -v`
Expected: all 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_subcontractor_primary_claim_attribution.py
git commit -m "feat(billing): add SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED kill switch + banner (Subproject B)"
```

---

## Task 3: Filename builder — `_ReducedSub_User_<claimer>` / `_AEPBillable_User_<claimer>`

**Files:**
- Modify: `generate_weekly_pdfs.py` — add module-level helper `_subcontractor_primary_variant_suffix`; rewire the `reduced_sub` / `aep_billable` branches in `generate_excel` (lines ~5408-5411)
- Test: `tests/test_subcontractor_primary_claim_attribution.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_subcontractor_primary_claim_attribution.py`:

```python
class TestPrimaryVariantSuffixHelper(unittest.TestCase):
    """Task 3: variant-suffix helper for subcontractor primary files."""

    def test_reduced_sub_suffix_embeds_user_token(self):
        suffix = generate_weekly_pdfs._subcontractor_primary_variant_suffix(
            'reduced_sub', 'John Doe', '91467680', '041926'
        )
        self.assertEqual(suffix, '_ReducedSub_User_John_Doe')

    def test_aep_billable_suffix_embeds_user_token(self):
        suffix = generate_weekly_pdfs._subcontractor_primary_variant_suffix(
            'aep_billable', 'John Doe', '91467680', '041926'
        )
        self.assertEqual(suffix, '_AEPBillable_User_John_Doe')

    def test_empty_claimer_raises(self):
        with self.assertRaises(ValueError):
            generate_weekly_pdfs._subcontractor_primary_variant_suffix(
                'reduced_sub', '', '91467680', '041926'
            )

    def test_suffix_round_trips_through_parser(self):
        suffix = generate_weekly_pdfs._subcontractor_primary_variant_suffix(
            'reduced_sub', 'John Doe', '91467680', '041926'
        )
        fname = f'WR_91467680_WeekEnding_041926_120000{suffix}_abc123.xlsx'
        self.assertEqual(
            generate_weekly_pdfs.build_group_identity(fname),
            ('91467680', '041926', 'reduced_sub', 'John_Doe'),
        )
```

- [ ] **Step 2: Run the failing test**

Run: `pytest tests/test_subcontractor_primary_claim_attribution.py::TestPrimaryVariantSuffixHelper -v`
Expected: FAIL with `AttributeError: ... has no attribute '_subcontractor_primary_variant_suffix'`.

- [ ] **Step 3: Add the helper**

In `generate_weekly_pdfs.py`, add this module-level function immediately BEFORE `def generate_excel(` (line ~5298):

```python
def _subcontractor_primary_variant_suffix(
    variant: str, claimer: str, wr_num: str, week_end_raw: str
) -> str:
    """Build the filename suffix for a subcontractor PRIMARY variant.

    Subproject B (2026-05-20): subcontractor primary files are
    partitioned by frozen primary claimer and named with the reserved
    ``_User_`` token (mirrors the primary-workflow convention).
    ``reduced_sub`` -> ``_ReducedSub_User_<sanitized>`` and
    ``aep_billable`` -> ``_AEPBillable_User_<sanitized>``.

    Raises ``ValueError`` if ``claimer`` is empty — production never
    hits this because ``resolve_claimer``'s ``use`` outcome always
    returns a non-empty name (falling back to ``effective_user`` /
    ``'Unknown Foreman'``). The raise mirrors the helper-shadow
    defensive raises and surfaces data drift loudly instead of
    producing a primary-looking filename that misroutes downstream.
    """
    if not claimer:
        logging.error(
            f"⚠️ {variant} variant row missing __current_foreman for "
            f"WR {wr_num} week {week_end_raw}; filename would be "
            f"ambiguous — raising to surface data drift."
        )
        raise ValueError(
            f"{variant} requires a non-empty claimer; got empty for "
            f"WR={wr_num} week={week_end_raw}"
        )
    claimer_sanitized = _RE_SANITIZE_IDENTIFIER.sub('_', claimer)[:50]
    token = '_AEPBillable' if variant == 'aep_billable' else '_ReducedSub'
    return f"{token}_User_{claimer_sanitized}"
```

- [ ] **Step 4: Rewire `generate_excel`**

In `generate_weekly_pdfs.py`, replace these two lines in `generate_excel` (lines ~5408-5411):

```python
    if variant == 'aep_billable':
        variant_suffix = '_AEPBillable'
    elif variant == 'reduced_sub':
        variant_suffix = '_ReducedSub'
```

with:

```python
    if variant in ('aep_billable', 'reduced_sub'):
        # Subproject B: partition by frozen primary claimer
        # (__current_foreman is the resolved claimer set in
        # group_source_rows). Helper-shadow branches below are
        # unchanged.
        variant_suffix = _subcontractor_primary_variant_suffix(
            variant,
            first_row.get('__current_foreman', ''),
            wr_num,
            week_end_raw,
        )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_subcontractor_primary_claim_attribution.py::TestPrimaryVariantSuffixHelper -v`
Expected: all 4 PASS.

- [ ] **Step 6: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_subcontractor_primary_claim_attribution.py
git commit -m "feat(billing): name subcontractor primary files by frozen claimer (_ReducedSub_User_<name>) (Subproject B)"
```

---

## Task 4: Pre-pass + emission in `group_source_rows` (the core)

**Files:**
- Modify: `generate_weekly_pdfs.py` — add the attribution pre-pass after `_bug_c_warning_seen` init (~line 4638); rewrite the subcontractor `reduced_sub`/`aep_billable` emission block (~lines 4855-4888)
- Test: `tests/test_subcontractor_primary_claim_attribution.py`

- [ ] **Step 1: Verify the concurrency imports exist**

Run: `grep -n "from concurrent.futures import" generate_weekly_pdfs.py`
Expected: a line importing `ThreadPoolExecutor` and `as_completed`. If `as_completed` is missing from that import, add it (the attachment-prefetch code already uses it, so it should be present). Record what you find; do not commit yet.

- [ ] **Step 2: Write the failing end-to-end tests**

Append to `tests/test_subcontractor_primary_claim_attribution.py`:

```python
from billing_audit.writer import ResolveOutcome


def _make_sub_primary_row(
    wr='91467680', row_id=5001, units_price='$100.00',
    snapshot='2026-04-19', effective_user='CurrentForeman',
    source_sheet_id=8162920222379908,
):
    """Synthetic completed non-helper subcontractor row."""
    return {
        '__row_id': row_id,
        'Work Request #': wr,
        'Weekly Reference Logged Date': '2026-04-19',
        'Snapshot Date': snapshot,
        'Units Completed?': True,
        'Units Total Price': units_price,
        'CU': 'ANC-M',
        'Work Type': 'Inst',
        'Quantity': 2,
        '__effective_user': effective_user,
        '__assignment_method': 'FOREMAN_COLUMN',
        '__is_helper_row': False,
        '__helper_foreman': '',
        '__helper_dept': '',
        '__helper_job': '',
        '__is_vac_crew': False,
        '__source_sheet_id': source_sheet_id,
    }


class TestPrePassEmission(unittest.TestCase):
    """Task 4: pre-pass + emission partition subcontractor primary by claimer."""

    _SUB_SHEET_ID = 8162920222379908

    def setUp(self):
        _reset_all()
        self._orig_variants = generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED
        self._orig_attr = generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED
        self._orig_sub_ids = set(generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS)
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED = True
        generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED = True
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.add(self._SUB_SHEET_ID)

    def tearDown(self):
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED = self._orig_variants
        generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED = self._orig_attr
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.update(self._orig_sub_ids)
        _reset_all()

    def test_frozen_claimer_partitions_reducedsub_and_aep(self):
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'FrozenPrimary', 'frozen', 'success'),
        ):
            groups = generate_weekly_pdfs.group_source_rows([_make_sub_primary_row()])
        keys = list(groups.keys())
        self.assertTrue(
            any('REDUCEDSUB_USER_FrozenPrimary' in k for k in keys),
            f"reduced_sub must partition by frozen claimer; got {keys}",
        )
        self.assertTrue(
            any('AEPBILLABLE_USER_FrozenPrimary' in k for k in keys),
            f"aep_billable (post-cutoff) must partition by frozen claimer; got {keys}",
        )

    def test_no_history_falls_back_to_current_foreman(self):
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'CurrentForeman', 'current', 'no_history'),
        ):
            groups = generate_weekly_pdfs.group_source_rows(
                [_make_sub_primary_row(effective_user='CurrentForeman')]
            )
        keys = list(groups.keys())
        self.assertTrue(
            any('REDUCEDSUB_USER_CurrentForeman' in k for k in keys),
            f"no_history must fall back to current foreman; got {keys}",
        )

    def test_hold_suppresses_primary_variants_and_records_hold(self):
        from billing_audit.writer import get_counters
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('hold', None, None, 'fetch_failure'),
        ):
            groups = generate_weekly_pdfs.group_source_rows([_make_sub_primary_row()])
        keys = list(groups.keys())
        self.assertFalse(
            any('REDUCEDSUB' in k for k in keys),
            f"HOLD must suppress reduced_sub emission; got {keys}",
        )
        self.assertFalse(
            any('AEPBILLABLE' in k for k in keys),
            f"HOLD must suppress aep_billable emission; got {keys}",
        )
        self.assertEqual(get_counters()['attribution_rows_held'], 1)

    def test_attribution_disabled_uses_current_foreman(self):
        # No mock — real resolve_claimer with enabled=False short-circuits
        # to use-current without any Supabase call.
        generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED = False
        groups = generate_weekly_pdfs.group_source_rows(
            [_make_sub_primary_row(effective_user='CurrentForeman')]
        )
        keys = list(groups.keys())
        self.assertTrue(
            any('REDUCEDSUB_USER_CurrentForeman' in k for k in keys),
            f"disabled attribution must use current foreman; got {keys}",
        )

    def test_two_claimers_same_wr_week_coexist(self):
        # Foundation A §2 coexistence invariant.
        def _resolve(variant, current, *, wr, week_ending, row_id, enabled):
            name = 'ForemanA' if row_id == 5001 else 'ForemanB'
            return ResolveOutcome('use', name, 'frozen', 'success')
        with mock.patch('billing_audit.writer.resolve_claimer', side_effect=_resolve):
            groups = generate_weekly_pdfs.group_source_rows([
                _make_sub_primary_row(row_id=5001),
                _make_sub_primary_row(row_id=5002),
            ])
        keys = list(groups.keys())
        self.assertTrue(any('REDUCEDSUB_USER_ForemanA' in k for k in keys))
        self.assertTrue(any('REDUCEDSUB_USER_ForemanB' in k for k in keys))

    def test_non_subcontractor_row_unaffected(self):
        # A non-sub completed row must still emit the legacy primary key
        # and must NOT trigger resolve_claimer.
        row = _make_sub_primary_row(source_sheet_id=99999999)
        with mock.patch(
            'billing_audit.writer.resolve_claimer',
            return_value=ResolveOutcome('use', 'X', 'frozen', 'success'),
        ) as m:
            groups = generate_weekly_pdfs.group_source_rows([row])
            m.assert_not_called()
        self.assertIn('041926_91467680', groups)
```

- [ ] **Step 3: Run the failing tests**

Run: `pytest tests/test_subcontractor_primary_claim_attribution.py::TestPrePassEmission -v`
Expected: FAIL — the partition keys are still `…_REDUCEDSUB` (no `_USER_<claimer>`), HOLD is not honored, and `resolve_claimer` is never called.

- [ ] **Step 4: Add the attribution pre-pass**

In `generate_weekly_pdfs.py`, in `group_source_rows`, immediately after the `_bug_c_warning_seen: set[...] = set()` line (~line 4638) and before `for r in rows:`, add:

```python
    # ── Subproject B (2026-05-20): parallel attribution pre-pass ──
    # Resolve the FROZEN primary claimer for every completed
    # subcontractor row BEFORE the grouping loop, so no per-row
    # Supabase round-trip runs inside the hot loop (honors the
    # [2026-04-25 14:00] latency lesson). The map is consumed by the
    # subcontractor variant-emission block. A row absent from the map
    # (attribution disabled, pre-pass skipped, missing __row_id, or an
    # unexpected per-row error) resolves to use-current at emission —
    # NEVER HOLD — so a plumbing fault can never silently suppress a
    # billing file. resolve_claimer's own fetch_failure -> HOLD is the
    # only path that defers a row.
    _sub_primary_claimer_map: dict = {}
    if BILLING_AUDIT_AVAILABLE and SUBCONTRACTOR_RATE_VARIANTS_ENABLED:
        _b_pre_rows = []
        for _r in rows:
            _sid = _r.get('__source_sheet_id')
            if _sid is None or _sid not in _FOLDER_DISCOVERED_SUB_IDS:
                continue
            _rid = _r.get('__row_id')
            if not isinstance(_rid, int):
                continue
            _wr_raw = _r.get('Work Request #')
            _ld = _r.get('Weekly Reference Logged Date')
            if not _wr_raw or not _ld or not is_checked(_r.get('Units Completed?')):
                continue
            _we = excel_serial_to_date(_ld)
            if _we is None:
                continue
            _b_pre_rows.append((
                _rid,
                str(_wr_raw).split('.')[0],
                _we.date() if isinstance(_we, datetime.datetime) else _we,
                _r.get('__effective_user', 'Unknown Foreman'),
            ))
        if _b_pre_rows:
            try:
                from billing_audit.writer import resolve_claimer as _resolve_claimer

                def _resolve_one(_item):
                    _rid, _wr, _we_date, _eu = _item
                    return _rid, _resolve_claimer(
                        'reduced_sub', _eu,
                        wr=_wr, week_ending=_we_date, row_id=_rid,
                        enabled=SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED,
                    )

                if len(_b_pre_rows) <= 1:
                    for _item in _b_pre_rows:
                        _rid, _out = _resolve_one(_item)
                        _sub_primary_claimer_map[_rid] = _out
                else:
                    _workers = min(PARALLEL_WORKERS, len(_b_pre_rows))
                    with ThreadPoolExecutor(max_workers=_workers) as _ex:
                        _futs = [_ex.submit(_resolve_one, _it) for _it in _b_pre_rows]
                        for _fut in as_completed(_futs):
                            try:
                                _rid, _out = _fut.result()
                                _sub_primary_claimer_map[_rid] = _out
                            except Exception:
                                logging.exception(
                                    "⚠️ Subproject B attribution pre-pass: "
                                    "unexpected error for one row (treating "
                                    "as use-current)"
                                )
            except Exception:
                logging.exception(
                    "⚠️ Subproject B attribution pre-pass failed; falling "
                    "back to current foreman for all subcontractor rows"
                )
                _sub_primary_claimer_map = {}
```

- [ ] **Step 5: Rewrite the subcontractor primary emission block**

In `generate_weekly_pdfs.py`, replace the `reduced_sub` + `aep_billable` emission (currently lines ~4855-4888, from `if is_subcontractor_row and SUBCONTRACTOR_RATE_VARIANTS_ENABLED:` down to the end of the `aep_key` block, STOPPING before the `# Helper-shadow variants:` comment) with:

```python
            if is_subcontractor_row and SUBCONTRACTOR_RATE_VARIANTS_ENABLED:
                # Snapshot cutoff is needed by BOTH the primary block
                # here and the helper-shadow block below, so compute it
                # once. ``excel_serial_to_date`` returns None for
                # blank/unparseable values (D-16 fall-through safety).
                _snap_for_cutoff = excel_serial_to_date(r.get('Snapshot Date'))

                # Subproject B: resolve the FROZEN primary claimer from
                # the pre-pass map. ``use`` -> partition by the claimer;
                # ``hold`` -> defer this row's primary variants this run
                # (correctness over availability) and record a HOLD; map
                # miss -> use the current effective_user.
                _b_outcome = _sub_primary_claimer_map.get(r.get('__row_id'))
                if _b_outcome is not None and _b_outcome.action == 'hold':
                    _b_primary_claimer = None
                    try:
                        from billing_audit.writer import record_attribution_hold
                        record_attribution_hold(
                            wr_key, week_ending_date, 'reduced_sub'
                        )
                    except Exception:
                        logging.exception(
                            "⚠️ Subproject B: record_attribution_hold failed"
                        )
                elif _b_outcome is not None and _b_outcome.action == 'use':
                    _b_primary_claimer = _b_outcome.name or effective_user
                else:
                    _b_primary_claimer = effective_user

                if _b_primary_claimer is not None:
                    _b_claimer_sanitized = _RE_SANITIZE_IDENTIFIER.sub(
                        '_', _b_primary_claimer
                    )[:50]
                    # ReducedSub: unconditional per SUB-02 / D-08, now
                    # partitioned by frozen primary claimer (Subproject B).
                    reduced_key = (
                        f"{week_end_for_key}_{wr_key}_REDUCEDSUB_USER_"
                        f"{_b_claimer_sanitized}"
                    )
                    keys_to_add.append(
                        ('reduced_sub', reduced_key, _b_primary_claimer)
                    )
                    if reduced_key not in groups:
                        logging.info(
                            f"🔻 REDUCED SUB GROUP CREATED: WR={wr_key}, "
                            f"Week={week_end_for_key}"
                        )

                    # AEPBillable: snapshot-cutoff-gated per SUB-01 / D-08
                    # / Living Ledger 2026-04-21 22:35 (snapshot is
                    # authoritative; Weekly Reference Logged Date is NOT a
                    # valid fallback here).
                    if (
                        _snap_for_cutoff is not None
                        and _snap_for_cutoff.date() >= _AEP_BILLABLE_CUTOFF
                    ):
                        aep_key = (
                            f"{week_end_for_key}_{wr_key}_AEPBILLABLE_USER_"
                            f"{_b_claimer_sanitized}"
                        )
                        keys_to_add.append(
                            ('aep_billable', aep_key, _b_primary_claimer)
                        )
                        if aep_key not in groups:
                            logging.info(
                                f"💲 AEP BILLABLE GROUP CREATED: WR={wr_key}, "
                                f"Week={week_end_for_key}"
                            )
```

NOTE: the existing helper-shadow block that follows (the `# Helper-shadow variants:` comment through the `aep_helper_key` emission) is UNCHANGED and continues to reference `_snap_for_cutoff`, which is now computed at the top of this block. Do not touch it.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest tests/test_subcontractor_primary_claim_attribution.py::TestPrePassEmission -v`
Expected: all 6 PASS.

- [ ] **Step 7: Run the Phase 1.1 helper-shadow suite to confirm no regression**

Run: `pytest tests/test_subcontractor_helper_shadow_rescue.py -v`
Expected: all PASS (the helper-shadow path is untouched; `_snap_for_cutoff` hoist preserves its behavior).

- [ ] **Step 8: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_subcontractor_primary_claim_attribution.py
git commit -m "feat(billing): partition subcontractor primary variants by frozen claimer with HOLD (Subproject B)"
```

---

## Task 5: Three identity sites (Site 1, Site 2, Site 3)

**Files:**
- Modify: `generate_weekly_pdfs.py` — Site 1 (~lines 7230-7240), Site 2 (~lines 7945-7951), Site 3 (~lines 8118-8121)
- Test: `tests/test_subcontractor_primary_claim_attribution.py`

- [ ] **Step 1: Write the failing source-invariant test**

Append to `tests/test_subcontractor_primary_claim_attribution.py`:

```python
class TestThreeIdentitySitesCarryClaimer(unittest.TestCase):
    """Task 5: all three identity sites derive reduced_sub/aep_billable
    identifier from __current_foreman (the CR-01 lockstep invariant)."""

    @classmethod
    def setUpClass(cls):
        cls._src = pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')

    def test_site1_derives_identifier_from_current_foreman(self):
        # Site 1 (main-loop identifier) must read __current_foreman for
        # the subcontractor primary variants.
        self.assertRegex(
            self._src,
            r"variant in \('reduced_sub', 'aep_billable'\)",
            "Site 1 must branch on the subcontractor primary variants",
        )

    def test_sites_reference_current_foreman_for_primary_variants(self):
        # All three sites use the marker comment so the lockstep is
        # auditable.
        self.assertEqual(
            self._src.count('Subproject B identity site'),
            3,
            "Exactly three identity sites must carry the Subproject B branch",
        )
```

- [ ] **Step 2: Run the failing test**

Run: `pytest tests/test_subcontractor_primary_claim_attribution.py::TestThreeIdentitySitesCarryClaimer -v`
Expected: FAIL (the marker comment is absent and Site 1 has no `reduced_sub`/`aep_billable` branch).

- [ ] **Step 3: Update Site 1 (main-loop identifier / file_identifier)**

In `generate_weekly_pdfs.py`, in the main loop (~lines 7226-7240), the structure is `if variant in ('helper', ...): … elif variant == 'vac_crew': … else: …`. Insert a new `elif` BEFORE the final `else:` (the `else` that reads `User`):

```python
                elif variant in ('reduced_sub', 'aep_billable'):
                    # Subproject B identity site (Site 1 — main-loop
                    # identifier). These variants are now partitioned by
                    # the frozen primary claimer (set as __current_foreman
                    # in group_source_rows). identifier == file_identifier
                    # == the sanitized claimer, matching the
                    # _ReducedSub_User_<name> filename and Sites 2 & 3.
                    _b_claimer = first_row.get('__current_foreman', '')
                    identifier = (
                        _RE_SANITIZE_IDENTIFIER.sub('_', _b_claimer)[:50]
                        if _b_claimer else ''
                    )
                    file_identifier = identifier
```

(Leave the existing `else:` branch — which reads `first_row.get('User')` for the legacy `primary` variant — unchanged.)

- [ ] **Step 4: Update Site 2 (`valid_wr_weeks` builder)**

In `generate_weekly_pdfs.py` (~lines 7928-7951), the structure is `if variant in ('helper', ...): … elif variant == 'vac_crew': … else: …`. Insert a new `elif` BEFORE the final `else:`:

```python
                elif variant in ('reduced_sub', 'aep_billable'):
                    # Subproject B identity site (Site 2 — valid_wr_weeks).
                    # Mirror Site 1 so attachment cleanup keeps the live
                    # per-claimer file.
                    _b_claimer = group_rows[0].get('__current_foreman', '')
                    file_id = (
                        _RE_SANITIZE_IDENTIFIER.sub('_', _b_claimer)[:50]
                        if _b_claimer else ''
                    )
```

- [ ] **Step 5: Update Site 3 (`current_keys` hash-history prune)**

In `generate_weekly_pdfs.py` (~lines 8092-8121), the structure is `if _variant in ('helper', ...): … elif _variant == 'vac_crew': … else: …`. Insert a new `elif` BEFORE the final `else:`:

```python
                        elif _variant in ('reduced_sub', 'aep_billable'):
                            # Subproject B identity site (Site 3 —
                            # current_keys). Must match the history_key
                            # written at Site 1 byte-for-byte
                            # (sanitized claimer) or the freshly-written
                            # entry is treated as stale and deleted before
                            # save.
                            _b_claimer = group_rows[0].get('__current_foreman', '')
                            _ident = (
                                _RE_SANITIZE_IDENTIFIER.sub('_', _b_claimer)[:50]
                                if _b_claimer else ''
                            )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest tests/test_subcontractor_primary_claim_attribution.py::TestThreeIdentitySitesCarryClaimer -v`
Expected: both PASS.

- [ ] **Step 7: Syntax check + full suite**

Run: `python -m py_compile generate_weekly_pdfs.py && pytest tests/ -v`
Expected: compile OK; suite PASS.

- [ ] **Step 8: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_subcontractor_primary_claim_attribution.py
git commit -m "feat(billing): carry frozen claimer through all 3 identity sites (Subproject B CR-01 lockstep)"
```

---

## Task 6: HOLD end-of-run summary call in `main()`

**Files:**
- Modify: `generate_weekly_pdfs.py:8161-8165` (inside the `if BILLING_AUDIT_AVAILABLE:` run-summary block)
- Test: `tests/test_subcontractor_primary_claim_attribution.py`

- [ ] **Step 1: Write the failing source-invariant test**

Append to `tests/test_subcontractor_primary_claim_attribution.py`:

```python
class TestHoldSummaryWiredIntoMain(unittest.TestCase):
    """Task 6: summarize_attribution_holds is invoked once at end-of-run."""

    def test_summary_call_present_in_source(self):
        src = pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')
        self.assertIn('summarize_attribution_holds()', src)
```

- [ ] **Step 2: Run the failing test**

Run: `pytest tests/test_subcontractor_primary_claim_attribution.py::TestHoldSummaryWiredIntoMain -v`
Expected: FAIL (call absent).

- [ ] **Step 3: Wire the call**

In `generate_weekly_pdfs.py`, inside the run-summary `if BILLING_AUDIT_AVAILABLE:` block (~lines 8161-8165), after the `_run_summary.update(_billing_audit_writer.get_counters())` try/except, add:

```python
            # Subproject B: emit ONE aggregate WARNING if any rows were
            # held this run pending attribution (Supabase outage). B is
            # the first consumer of Foundation A's HOLD machinery; this
            # is the single end-of-run summary call. PII-safe (counts +
            # sanitized WR list only). Never fail the run summary write.
            try:
                _billing_audit_writer.summarize_attribution_holds()
            except Exception:
                pass
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_subcontractor_primary_claim_attribution.py::TestHoldSummaryWiredIntoMain -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_subcontractor_primary_claim_attribution.py
git commit -m "feat(billing): emit end-of-run attribution HOLD summary (Subproject B)"
```

---

## Task 7: Migration cleanup — `sub_legacy_primary_variants` parameter + call sites

**Files:**
- Modify: `generate_weekly_pdfs.py` — add `sub_legacy_primary_variants` param + gate to `cleanup_untracked_sheet_attachments` (~lines 2646-2776); update the TARGET call site (~lines 7968-7979) and the PPP call site (~lines 8043-8051)
- Test: `tests/test_subcontractor_primary_claim_attribution.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_subcontractor_primary_claim_attribution.py`:

```python
class TestMigrationCleanup(unittest.TestCase):
    """Task 7: legacy unpartitioned primary attachments deleted; new
    per-claimer files exempt; non-sub WRs untouched."""

    def setUp(self):
        _ensure_smartsheet_mocked()

    def _att(self, name, att_id):
        a = mock.MagicMock()
        a.name = name
        a.id = att_id
        return a

    def _client(self, attachments):
        client = mock.MagicMock()
        sheet = mock.MagicMock()
        row = mock.MagicMock()
        row.id = 1
        client.Attachments.list_row_attachments.return_value.data = attachments
        sheet.rows = [row]
        client.Sheets.get_sheet.return_value = sheet
        return client, sheet

    def test_legacy_reducedsub_deleted_new_claimer_exempt(self):
        legacy = self._att(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_abc123.xlsx', 10
        )
        new_file = self._att(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_User_John_Doe_def456.xlsx',
            20,
        )
        client, sheet = self._client([legacy, new_file])
        generate_weekly_pdfs.cleanup_untracked_sheet_attachments(
            client,
            target_sheet_id=5723337641643908,
            valid_wr_weeks={('91467680', '041926', 'reduced_sub', 'John_Doe')},
            test_mode=False,
            target_sheet=sheet,
            sub_wr_scope={'91467680'},
            sub_legacy_primary_variants={'reduced_sub', 'aep_billable'},
        )
        deletes = [c.args for c in client.Attachments.delete_attachment.call_args_list]
        self.assertIn((5723337641643908, 10), deletes,
                      f"legacy _ReducedSub must be deleted; got {deletes}")
        self.assertNotIn((5723337641643908, 20), deletes,
                         f"new per-claimer file must be exempt; got {deletes}")

    def test_legacy_aepbillable_deleted(self):
        legacy = self._att(
            'WR_91467680_WeekEnding_041926_120000_AEPBillable_abc123.xlsx', 30
        )
        client, sheet = self._client([legacy])
        generate_weekly_pdfs.cleanup_untracked_sheet_attachments(
            client,
            target_sheet_id=5723337641643908,
            valid_wr_weeks=set(),
            test_mode=False,
            target_sheet=sheet,
            sub_wr_scope={'91467680'},
            sub_legacy_primary_variants={'reduced_sub', 'aep_billable'},
        )
        deletes = [c.args for c in client.Attachments.delete_attachment.call_args_list]
        self.assertIn((5723337641643908, 30), deletes)

    def test_non_sub_wr_legacy_reducedsub_preserved(self):
        legacy = self._att(
            'WR_99999999_WeekEnding_041926_120000_ReducedSub_abc123.xlsx', 40
        )
        client, sheet = self._client([legacy])
        generate_weekly_pdfs.cleanup_untracked_sheet_attachments(
            client,
            target_sheet_id=5723337641643908,
            valid_wr_weeks=set(),
            test_mode=False,
            target_sheet=sheet,
            sub_wr_scope={'91467680'},  # 99999999 NOT in scope
            sub_legacy_primary_variants={'reduced_sub', 'aep_billable'},
        )
        deletes = [c.args for c in client.Attachments.delete_attachment.call_args_list]
        self.assertNotIn((5723337641643908, 40), deletes)

    def test_param_omitted_is_noop(self):
        legacy = self._att(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_abc123.xlsx', 50
        )
        client, sheet = self._client([legacy])
        generate_weekly_pdfs.cleanup_untracked_sheet_attachments(
            client,
            target_sheet_id=5723337641643908,
            valid_wr_weeks={('91467680', '041926', 'reduced_sub', '')},
            test_mode=False,
            target_sheet=sheet,
        )
        deletes = [c.args for c in client.Attachments.delete_attachment.call_args_list]
        self.assertEqual(deletes, [], f"omitted param must be a no-op; got {deletes}")
```

- [ ] **Step 2: Run the failing tests**

Run: `pytest tests/test_subcontractor_primary_claim_attribution.py::TestMigrationCleanup -v`
Expected: FAIL with `TypeError: cleanup_untracked_sheet_attachments() got an unexpected keyword argument 'sub_legacy_primary_variants'`.

- [ ] **Step 3: Add the parameter to the signature**

In `generate_weekly_pdfs.py`, add a parameter to `cleanup_untracked_sheet_attachments` (after `sub_offcontract_variants`, ~line 2655):

```python
    sub_offcontract_variants: set[str] | None = None,
    sub_legacy_primary_variants: set[str] | None = None,
):
```

- [ ] **Step 4: Add the migration gate**

In `cleanup_untracked_sheet_attachments`, immediately AFTER the existing `sub_wr_scope` / `sub_offcontract_variants` gate block (the one ending `off_contract_attachments.append(att)` + `continue` at ~line 2775) and BEFORE `identity_groups[ident].append(att)`, add:

```python
                    # Subproject B (2026-05-20): one-time migration —
                    # delete LEGACY UNPARTITIONED `_ReducedSub` /
                    # `_AEPBillable` attachments (parsed identifier == '')
                    # for in-scope subcontractor WRs. B re-partitions
                    # these by frozen claimer, so the bare one-file-per-WR
                    # attachment is an obsolete duplicate. The
                    # ``not _identifier`` check is the precise legacy
                    # selector: new per-claimer files carry a non-empty
                    # identifier and are NOT deleted here. The
                    # ``ident not in valid_wr_weeks`` guard is
                    # belt-and-suspenders (B never emits an empty
                    # identifier, so a live file is never empty-id) per the
                    # [2026-05-19 23:45] WR-01 live-identity rule.
                    if (
                        sub_wr_scope is not None
                        and wr in sub_wr_scope
                        and sub_legacy_primary_variants is not None
                        and variant in sub_legacy_primary_variants
                        and not _identifier
                        and ident not in valid_wr_weeks
                    ):
                        off_contract_attachments.append(att)
                        continue
```

- [ ] **Step 5: Update the docstring**

In the `cleanup_untracked_sheet_attachments` docstring, after the `sub_offcontract_variants:` paragraph, add:

```
    sub_legacy_primary_variants: Subproject B (2026-05-20) one-time
        migration. When provided, any attachment whose parsed ``wr`` is
        in ``sub_wr_scope``, whose parsed ``variant`` is in this set, and
        whose parsed ``identifier`` is empty (legacy unpartitioned
        ``_ReducedSub`` / ``_AEPBillable``) is unconditionally deleted —
        UNLESS its identity is in ``valid_wr_weeks`` (live-identity
        exemption). New per-claimer files (non-empty identifier) are
        never matched. When None (default), this gate is skipped.
        Gated at the call sites by SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED.
```

- [ ] **Step 6: Run the cleanup tests to verify they pass**

Run: `pytest tests/test_subcontractor_primary_claim_attribution.py::TestMigrationCleanup -v`
Expected: all 4 PASS.

- [ ] **Step 7: Update the TARGET call site**

In `generate_weekly_pdfs.py` (~lines 7968-7979), replace the `_sub_scope = (...)` assignment and the TARGET `cleanup_untracked_sheet_attachments(...)` call with:

```python
            # Subproject B: build the subcontractor WR scope when EITHER
            # the legacy-helper cleanup (SUB-09) OR the legacy-primary
            # cleanup (Subproject B) is enabled — the two share the scope.
            _need_sub_scope = (
                SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED
                or SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED
            )
            _sub_scope = (
                _build_subcontractor_wr_scope(groups)
                if _need_sub_scope
                else None
            )
            _target_offcontract = set()
            if _sub_scope and SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED:
                _target_offcontract |= {'helper', 'primary'}
            _target_legacy_primary = (
                {'reduced_sub', 'aep_billable'}
                if _sub_scope and SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED
                else None
            )
            with sentry_sdk.start_span(op="smartsheet.cleanup", name="Cleanup untracked sheet attachments"):
                cleanup_untracked_sheet_attachments(
                    client, TARGET_SHEET_ID, valid_wr_weeks, TEST_MODE,
                    attachment_cache=_cleanup_cache, target_sheet=_target_sheet_obj,
                    sub_wr_scope=_sub_scope,
                    sub_offcontract_variants=(_target_offcontract or None),
                    sub_legacy_primary_variants=_target_legacy_primary,
                )
```

- [ ] **Step 8: Update the PPP call site**

In `generate_weekly_pdfs.py` (~lines 8043-8051), replace the PPP `cleanup_untracked_sheet_attachments(...)` call with:

```python
                    cleanup_untracked_sheet_attachments(
                        client,
                        SUBCONTRACTOR_PPP_SHEET_ID,
                        valid_wr_weeks,
                        TEST_MODE,
                        attachment_cache=_cleanup_cache,
                        target_sheet=_target_sheet_ppp_obj,
                        variant_whitelist={'reduced_sub', 'reduced_sub_helper'},
                        sub_wr_scope=_sub_scope,
                        sub_legacy_primary_variants=(
                            {'reduced_sub'}
                            if _sub_scope and SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED
                            else None
                        ),
                    )
```

(PPP only receives `reduced_sub` from the routing matrix, so its legacy-primary set is `{'reduced_sub'}` — `aep_billable` never routes to PPP.)

- [ ] **Step 9: Update the existing cleanup-signature regression test**

Adding the `sub_legacy_primary_variants` parameter changes the signature of `cleanup_untracked_sheet_attachments`, which an existing test asserts. Find it:

Run: `grep -rn "signature" tests/test_security_audit_followup.py`
Expected: a test (per the [2026-05-19 23:45] ledger, `TestPppCleanupUntrackedAttachments.test_cleanup_function_signature_unchanged`) that introspects the function's parameters. Update its expected parameter set to include `sub_legacy_primary_variants` so it reflects the new signature. If the test enumerates exact parameter names, add `'sub_legacy_primary_variants'`; if it counts parameters, increment the expected count by one. Make the minimal edit that keeps the assertion true for the new signature.

- [ ] **Step 10: Syntax check + full suite**

Run: `python -m py_compile generate_weekly_pdfs.py && pytest tests/ -v`
Expected: compile OK; suite PASS (including the existing `TestLegacyHelperTargetCleanupE2E` — the `_sub_scope` decoupling preserves its behavior since `SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED` still drives `{'helper','primary'}` — and the updated signature test).

- [ ] **Step 11: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_subcontractor_primary_claim_attribution.py
git commit -m "feat(billing): migrate legacy unpartitioned subcontractor primary attachments (Subproject B)"
```

---

## Task 8: One-time hash-history prune for legacy `reduced_sub`/`aep_billable` orphans

**Files:**
- Modify: `generate_weekly_pdfs.py` — add `SUBPROJECT_B_HASH_PRUNE_VERSION` constant; add `_run_subproject_b_hash_prune`; register PII marker; call after `_run_phase_1_1_hash_prune` (~line 6905)
- Test: `tests/test_subcontractor_primary_claim_attribution.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_subcontractor_primary_claim_attribution.py`:

```python
class TestSubprojectBHashPrune(unittest.TestCase):
    """Task 8: one-time prune of legacy blank-identifier reduced_sub /
    aep_billable orphans for in-scope subcontractor WRs."""

    def setUp(self):
        _ensure_smartsheet_mocked()

    def _groups(self, wrs):
        groups = {}
        for wr in wrs:
            key = f"041926_{wr}_REDUCEDSUB_USER_John"
            groups[key] = [{'Work Request #': wr, '__source_sheet_id': 8162920222379908}]
        return groups

    def test_first_run_drops_legacy_primary_variant_orphans(self):
        hist = {
            '91467680|041926|reduced_sub|': {'hash': 'h1', 'timestamp': '2026-01-01'},
            '91467680|041926|aep_billable|': {'hash': 'h2', 'timestamp': '2026-01-02'},
            # New per-claimer entry — must survive
            '91467680|041926|reduced_sub|John': {'hash': 'h3', 'timestamp': '2026-01-03'},
            # Non-sub WR — must survive
            '12345|041926|reduced_sub|': {'hash': 'h4', 'timestamp': '2026-01-04'},
        }
        with self.assertLogs(level='INFO') as log_cm:
            generate_weekly_pdfs._run_subproject_b_hash_prune(hist, self._groups(['91467680']))
        self.assertNotIn('91467680|041926|reduced_sub|', hist)
        self.assertNotIn('91467680|041926|aep_billable|', hist)
        self.assertIn('91467680|041926|reduced_sub|John', hist)
        self.assertIn('12345|041926|reduced_sub|', hist)
        self.assertEqual(
            hist['_subproject_b_prune_version'],
            generate_weekly_pdfs.SUBPROJECT_B_HASH_PRUNE_VERSION,
        )
        prune_logs = [l for l in log_cm.output if 'Subproject B hash-history prune' in l]
        self.assertEqual(len(prune_logs), 1)
        self.assertIn('dropped 2', prune_logs[0])

    def test_idempotent_when_sentinel_current(self):
        hist = {
            '91467680|041926|reduced_sub|': {'hash': 'h1', 'timestamp': '2026-01-01'},
            '_subproject_b_prune_version': generate_weekly_pdfs.SUBPROJECT_B_HASH_PRUNE_VERSION,
        }
        generate_weekly_pdfs._run_subproject_b_hash_prune(hist, self._groups(['91467680']))
        self.assertIn('91467680|041926|reduced_sub|', hist)  # no-op
        self.assertEqual(
            hist['_subproject_b_prune_version'],
            generate_weekly_pdfs.SUBPROJECT_B_HASH_PRUNE_VERSION,
        )

    def test_pii_marker_registered(self):
        self.assertIn(
            'Subproject B hash-history prune',
            generate_weekly_pdfs._PII_LOG_MARKERS,
        )

    def test_version_constant_present_in_source(self):
        src = pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')
        self.assertRegex(src, r'(?m)^SUBPROJECT_B_HASH_PRUNE_VERSION = 1$')

    def test_call_site_present_in_source(self):
        src = pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')
        self.assertIn('_run_subproject_b_hash_prune(hash_history, groups)', src)
```

- [ ] **Step 2: Run the failing tests**

Run: `pytest tests/test_subcontractor_primary_claim_attribution.py::TestSubprojectBHashPrune -v`
Expected: FAIL (`SUBPROJECT_B_HASH_PRUNE_VERSION` / `_run_subproject_b_hash_prune` absent, marker not registered).

- [ ] **Step 3: Add the version constant**

In `generate_weekly_pdfs.py`, immediately after the `PHASE_1_1_HASH_PRUNE_VERSION = 2` line (line 311), add:

```python
# Subproject B (2026-05-20): one-time hash-history prune version for
# dropping LEGACY blank-identifier `reduced_sub` / `aep_billable`
# orphans left behind when B re-partitions those variants by frozen
# claimer. Separate sentinel (`_subproject_b_prune_version`) from the
# Phase 1.1 prune so the two migrations are independent + auditable.
# Advancing this constant is the kill switch (re-run trigger).
SUBPROJECT_B_HASH_PRUNE_VERSION = 1
```

- [ ] **Step 4: Add the prune helper**

In `generate_weekly_pdfs.py`, immediately after `_run_phase_1_1_hash_prune` ends (find the end of that function, after its final orphan-drop/log block ~line 3230), add:

```python
def _run_subproject_b_hash_prune(hash_history: dict, groups: dict) -> None:
    """Subproject B (2026-05-20): idempotent one-time hash-history prune.

    Drops LEGACY blank-identifier subcontractor primary orphans —
    4-part keys ``wr|week|reduced_sub|`` and ``wr|week|aep_billable|``
    with an EMPTY identifier — for WRs that are subcontractor in this
    run. B re-partitions those variants by frozen claimer (new keys
    carry a non-empty identifier), so the blank-identifier entries are
    obsolete. The normal stale-prune at the end of the run would clear
    them eventually; this makes the migration deterministic on the first
    run and survives interrupted / no-update runs.

    Scope-building delegates to ``_build_subcontractor_wr_scope`` (shared
    with the cleanup call site — no drift, per the [2026-05-15 12:00]
    three-site invariant). Sentinel key ``_subproject_b_prune_version``
    is distinct from the Phase 1.1 ``_phase_prune_version`` so the two
    migrations are independent. Mutates ``hash_history`` in place.
    Dropping a hash entry costs at most one benign regeneration — never
    data loss — so no live-identity exemption is needed on this drop
    path (unlike the every-run attachment cleanup).
    """
    _persisted = hash_history.pop('_subproject_b_prune_version', 0)
    if (
        isinstance(_persisted, int)
        and _persisted >= SUBPROJECT_B_HASH_PRUNE_VERSION
    ):
        hash_history['_subproject_b_prune_version'] = _persisted
        return

    _scope = _build_subcontractor_wr_scope(groups)
    _orphans = []
    for _hk in list(hash_history.keys()):
        if isinstance(_hk, str) and _hk.startswith('_'):
            continue
        _parts = str(_hk).split('|')
        if len(_parts) != 4:
            continue
        _hk_wr, _hk_week, _hk_variant, _hk_ident = _parts
        if (
            _hk_wr in _scope
            and _hk_variant in ('reduced_sub', 'aep_billable')
            and _hk_ident == ''
        ):
            _orphans.append(_hk)
    for _ok in _orphans:
        del hash_history[_ok]
    hash_history['_subproject_b_prune_version'] = SUBPROJECT_B_HASH_PRUNE_VERSION
    if _orphans:
        _wr_sample = sorted({k.split('|')[0] for k in _orphans})[:20]
        logging.info(
            f"🧹 Subproject B hash-history prune: dropped {len(_orphans)} "
            f"legacy unpartitioned reduced_sub/aep_billable orphan(s) "
            f"(affected WRs first 20: {_wr_sample})"
        )
    else:
        logging.info(
            "🧹 Subproject B hash-history prune: no legacy unpartitioned "
            "reduced_sub/aep_billable orphans to drop"
        )
```

- [ ] **Step 5: Register the PII marker**

In `generate_weekly_pdfs.py`, in the `_PII_LOG_MARKERS` list, add (alongside the existing subcontractor markers ~line 938):

```python
    "Subproject B hash-history prune",
```

- [ ] **Step 6: Add the call site**

In `generate_weekly_pdfs.py`, immediately after the `_run_phase_1_1_hash_prune(hash_history, groups)` try/except block (~lines 6904-6915), add:

```python
        # Subproject B: one-time prune of legacy blank-identifier
        # reduced_sub/aep_billable orphans (kill switch is the version
        # constant). Fail-safe — a failed prune must not break the run.
        try:
            _run_subproject_b_hash_prune(hash_history, groups)
        except Exception as _b_prune_exc:
            logging.warning(
                f"⚠️ Subproject B hash-history prune failed; continuing "
                f"with existing history: {_b_prune_exc!r}"
            )
```

- [ ] **Step 7: Run the prune tests to verify they pass**

Run: `pytest tests/test_subcontractor_primary_claim_attribution.py::TestSubprojectBHashPrune -v`
Expected: all 5 PASS.

- [ ] **Step 8: Confirm the Phase 1.1 prune suite still passes**

Run: `pytest tests/test_subcontractor_helper_shadow_rescue.py::TestHashPruneIdempotency -v`
Expected: all PASS (the Phase 1.1 prune + its sentinel are untouched; `save_hash_history`/`load_hash_history` already preserve any `_`-prefixed sentinel).

- [ ] **Step 9: Commit**

```bash
git add generate_weekly_pdfs.py tests/test_subcontractor_primary_claim_attribution.py
git commit -m "feat(billing): one-time hash-history prune of legacy primary-variant orphans (Subproject B)"
```

---

## Task 9: Byte-identical preservation + production-invariant regression tests

**Files:**
- Test: `tests/test_subcontractor_primary_claim_attribution.py`

- [ ] **Step 1: Write the regression tests**

Append to `tests/test_subcontractor_primary_claim_attribution.py`:

```python
class TestNonSubVariantsPreserved(unittest.TestCase):
    """Task 9: B does not change primary / vac_crew / helper-shadow grouping."""

    _SUB_SHEET_ID = 8162920222379908

    def setUp(self):
        _reset_all()
        self._orig_variants = generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED
        self._orig_sub_ids = set(generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS)
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED = True
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.add(self._SUB_SHEET_ID)

    def tearDown(self):
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED = self._orig_variants
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.update(self._orig_sub_ids)
        _reset_all()

    def test_non_subcontractor_primary_row_emits_legacy_primary_key(self):
        row = _make_sub_primary_row(source_sheet_id=99999999)
        groups = generate_weekly_pdfs.group_source_rows([row])
        self.assertIn('041926_91467680', groups)
        # No subcontractor variant keys for a non-sub row.
        self.assertFalse(any('REDUCEDSUB' in k for k in groups))

    def test_vac_crew_row_unaffected(self):
        row = _make_sub_primary_row(source_sheet_id=99999999)
        row['__is_vac_crew'] = True
        row['__vac_crew_name'] = 'VacGuy'
        groups = generate_weekly_pdfs.group_source_rows([row])
        self.assertTrue(any(k.endswith('_VACCREW') for k in groups))


class TestPrePassConcurrency(unittest.TestCase):
    """Task 9: the parallel pre-pass resolves many rows correctly with no
    lost/duplicated map entries (spec §12 concurrency coverage)."""

    _SUB_SHEET_ID = 8162920222379908

    def setUp(self):
        _reset_all()
        self._orig_variants = generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED
        self._orig_attr = generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED
        self._orig_sub_ids = set(generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS)
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED = True
        generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED = True
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.add(self._SUB_SHEET_ID)

    def tearDown(self):
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED = self._orig_variants
        generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED = self._orig_attr
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.update(self._orig_sub_ids)
        _reset_all()

    def test_fifty_rows_each_partition_to_their_own_claimer(self):
        # Each row's claimer is keyed to its row_id; assert every row
        # lands in its own claimer's group with no loss/duplication.
        def _resolve(variant, current, *, wr, week_ending, row_id, enabled):
            return ResolveOutcome('use', f'Foreman{row_id}', 'frozen', 'success')
        rows = [
            _make_sub_primary_row(wr='WRSAME', row_id=6000 + i)
            for i in range(50)
        ]
        with mock.patch('billing_audit.writer.resolve_claimer', side_effect=_resolve):
            groups = generate_weekly_pdfs.group_source_rows(rows)
        keys = list(groups.keys())
        for i in range(50):
            self.assertTrue(
                any(f'REDUCEDSUB_USER_Foreman{6000 + i}' in k for k in keys),
                f"row {6000 + i} missing from its claimer group; got {len(keys)} keys",
            )


class TestSubprojectBProductionInvariants(unittest.TestCase):
    """Task 9: source-grep guards defeating the 'mirror passes but
    production reverted' failure mode."""

    @classmethod
    def setUpClass(cls):
        cls._src = pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')

    def test_prepass_present(self):
        self.assertIn('_sub_primary_claimer_map', self._src)
        self.assertIn('Subproject B attribution pre-pass', self._src)

    def test_emission_uses_user_token_keys(self):
        self.assertIn('_REDUCEDSUB_USER_', self._src)
        self.assertIn('_AEPBILLABLE_USER_', self._src)

    def test_hold_record_present(self):
        self.assertIn('record_attribution_hold', self._src)

    def test_cleanup_param_signature_present(self):
        self.assertRegex(
            self._src,
            r'sub_legacy_primary_variants: set\[str\] \| None = None',
        )
```

- [ ] **Step 2: Run the regression tests**

Run: `pytest tests/test_subcontractor_primary_claim_attribution.py::TestNonSubVariantsPreserved tests/test_subcontractor_primary_claim_attribution.py::TestPrePassConcurrency tests/test_subcontractor_primary_claim_attribution.py::TestSubprojectBProductionInvariants -v`
Expected: all PASS (these assert the work done in Tasks 1-8).

- [ ] **Step 3: Run the FULL suite**

Run: `pytest tests/ -v`
Expected: exit 0, zero failures. If any pre-existing test fails, investigate — B must not regress any existing behavior. The most likely candidates to check are `tests/test_subcontractor_pricing.py` (variant filenames), `tests/test_security_audit_followup.py` (cleanup signature — note Task 7 added a param; if a signature-arity test exists there, update it to include `sub_legacy_primary_variants`), and `tests/test_subcontractor_helper_shadow_rescue.py`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_subcontractor_primary_claim_attribution.py
git commit -m "test(billing): coexistence + non-sub preservation + production invariants (Subproject B)"
```

---

## Task 10: Docs + workflow pinning

**Files:**
- Modify: `.github/workflows/weekly-excel-generation.yml`
- Modify: `website/docs/reference/environment.md`

- [ ] **Step 1: Pin the new env var in the workflow**

In `.github/workflows/weekly-excel-generation.yml`, locate the `env:` block of the `core` job where `SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED` is pinned. Add immediately after it:

```yaml
          SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED: '1'
```

(Match the surrounding indentation exactly. If `SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED` is not pinned in the workflow, add both under the same `env:` block.)

- [ ] **Step 2: Verify the pin**

Run: `grep -n "SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED" .github/workflows/weekly-excel-generation.yml`
Expected: one match showing the pinned `'1'`.

- [ ] **Step 3: Document in environment.md**

In `website/docs/reference/environment.md`, locate the subcontractor section that documents `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED` and `SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED`. (a) Broaden the `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED` description to note it now also gates the **subcontractor primary** (`ReducedSub` / `AEPBillable`) claim attribution introduced by Subproject B, not only the helper-shadow path. (b) Add a new row/entry:

```markdown
### `SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED`

- **Default:** `1` (on)
- **Scope:** Subproject B one-time migration.
- Gates the destructive removal of legacy UNPARTITIONED `_ReducedSub` /
  `_AEPBillable` attachments (no `_User_` token) on `TARGET_SHEET_ID`
  and `SUBCONTRACTOR_PPP_SHEET_ID` for subcontractor WRs, once those
  variants are re-partitioned by frozen primary claimer. Set to `0` to
  skip the cleanup (legacy duplicates persist until removed manually).
  Separate from `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED` (which
  gates attribution resolution, not this cleanup).
```

- [ ] **Step 4: Validate the docs build**

Run: `cd website && npm run typecheck && npm run build`
Expected: typecheck + build succeed with no broken links. (If `website/` deps are not installed in this environment, run `npm install` first; if the docs build cannot run here, note that and rely on CI.)

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/weekly-excel-generation.yml website/docs/reference/environment.md
git commit -m "docs(billing): pin SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED + document Subproject B"
```

---

## Task 11: Living Ledger entry + final full-suite verification

**Files:**
- Modify: `CLAUDE.md` (Living Ledger section)

- [ ] **Step 1: Run the full suite one final time and record the count**

Run: `pytest tests/ -v`
Expected: exit 0. Record the `N passed / M skipped / K subtests` line — it goes in the ledger entry.

- [ ] **Step 2: Append the Living Ledger entry**

In `CLAUDE.md`, under the `## Living Ledger (Auto-Updated Context)` section, append a new entry (prepend the current date+timestamp in `[YYYY-MM-DD HH:MM]` format). Cover, in prose consistent with the existing entries:
- What shipped: Subproject B — subcontractor primary (`reduced_sub` / `aep_billable`) variants re-partitioned by frozen primary claimer via Foundation A's `resolve_claimer`; B is the first consumer of the HOLD machinery.
- The five operator decisions (fallback-to-current; reuse `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED`; `_ReducedSub_User_<name>` filename; explicit forced cleanup + version-sentinel prune; HOLD on outage).
- The parallel pre-pass wiring (Approach A) and why (the [2026-04-25 14:00] latency lesson).
- The new env var `SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED` (workflow-pinned) and the new `SUBPROJECT_B_HASH_PRUNE_VERSION` sentinel.
- The accepted asymmetry: primary HOLDs on outage; the unchanged Phase 1.1 helper-shadow path still falls back.
- The CR-01 three-site lockstep extended for the new variants.
- The new test file and the final `pytest tests/` count from Step 1.

- [ ] **Step 3: Final verification**

Run: `python -m py_compile generate_weekly_pdfs.py && pytest tests/`
Expected: compile OK; exit 0.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: Living Ledger — Subproject B subcontractor primary claim attribution"
```

---

## After execution — GSD quality gates

Per the brainstorm decision (superpowers plan + GSD gates), after all tasks pass:
1. `/gsd-code-review` on the branch diff.
2. `/gsd-verify-work` UAT.

Address any HIGH/BLOCKER findings before merge.
