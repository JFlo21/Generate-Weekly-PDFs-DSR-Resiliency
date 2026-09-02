"""Freeze-row cache warm start (Phase 11 Plan 08 / INC-05 D-12 follow-up).

INC-05 retired the persisted ``billing_audit_frozen_rows.json`` warm start,
so ``billing_audit_row_cache`` started empty every run and every completed
row (~214k on run 33570018457, 2026-09-01) was re-sent to the first-write-
wins ``freeze_attribution`` RPC: 84.6 minutes of a 106-minute group phase.
The grouping phase already fetches every frozen row for every WR-week
through ``lookup_attribution_bulk`` under the SAME eligibility rule the
freeze loop uses (``Units Completed?`` checked, integer row id), so its key
set IS the warm start. These tests pin:

1. the helper writes keys in the exact ``wr|MMDDYY|row_id`` format the
   freeze loop checks;
2. ``group_source_rows`` exposes the prefetched keys only after a
   successful prefetch (fetch_failure / disabled -> empty -> unchanged
   behaviour);
3. a seeded key removes its row from the freeze loop's candidate set (no
   RPC for it) and the loop's key literal has not drifted from the helper;
4. ``pipeline.orchestrate`` seeds the cache after creating it and before
   the group loop starts.

All identifiers are fictional.
"""
import datetime
import unittest
from unittest import mock

import generate_weekly_pdfs  # noqa: E402
from tests.test_billing_audit_shadow import (  # noqa: E402
    _ensure_smartsheet_mocked, _read_source, _reset_all,
)

_ensure_smartsheet_mocked()
gwp = generate_weekly_pdfs

_WEEK = datetime.date(2026, 8, 30)
_WR = '12345678'


class WarmCacheHelperTests(unittest.TestCase):
    """``warm_billing_audit_row_cache`` mirrors the freeze loop's key."""

    @staticmethod
    def _helper():
        from pipeline.attribution import warm_billing_audit_row_cache
        return warm_billing_audit_row_cache

    def test_seeds_the_freeze_loop_key_format(self):
        cache: set[str] = set()
        added = self._helper()(cache, {(_WR, _WEEK, 4242)})
        self.assertEqual(added, 1)
        self.assertEqual(cache, {'12345678|083026|4242'})

    def test_counts_only_new_keys(self):
        cache = {'12345678|083026|4242'}
        keys = {(_WR, _WEEK, 4242), (_WR, _WEEK, 4243)}
        self.assertEqual(self._helper()(cache, keys), 1)
        self.assertEqual(
            cache, {'12345678|083026|4242', '12345678|083026|4243'},
        )

    def test_empty_prefetch_seeds_nothing(self):
        cache: set[str] = set()
        self.assertEqual(self._helper()(cache, frozenset()), 0)
        self.assertEqual(cache, set())


class SanitizerEquivalenceTests(unittest.TestCase):
    """The seed's WR (written by freeze_row, echoed by the RPC) must equal
    the loop's WR. Both sides sanitize with their own regex; a divergence
    would turn into silent false skips, so pin them (risk review, PR #378)."""

    def test_writer_and_config_sanitizers_are_identical(self):
        from billing_audit.writer import _WR_SANITIZE
        from pipeline.config import _RE_SANITIZE_HELPER_NAME
        self.assertEqual(
            _RE_SANITIZE_HELPER_NAME.pattern, _WR_SANITIZE.pattern,
        )
        self.assertEqual(_RE_SANITIZE_HELPER_NAME.flags, _WR_SANITIZE.flags)

    def test_non_numeric_wr_sanitizes_the_same_on_both_sides(self):
        from billing_audit.writer import _WR_SANITIZE
        from pipeline.config import _RE_SANITIZE_HELPER_NAME
        for raw in ('123/45', 'WR 123', '12345678.0', '1234-56', 'a' * 60):
            with self.subTest(raw=raw):
                loop_side = _RE_SANITIZE_HELPER_NAME.sub(
                    '_', str(raw).split('.')[0])[:50]
                writer_side = _WR_SANITIZE.sub(
                    '_', str(raw).split('.')[0])[:50]
                self.assertEqual(loop_side, writer_side)


class PrefetchedFrozenKeysTests(unittest.TestCase):
    """``group_source_rows`` publishes the prefetch keys on success only."""

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

    @staticmethod
    def _accessor():
        from pipeline.grouping import get_prefetched_frozen_row_keys
        return get_prefetched_frozen_row_keys

    @staticmethod
    def _row(row_id: int = 4242) -> dict:
        return {
            '__row_id': row_id,
            '__source_sheet_id': 99999,
            '__effective_user': 'Pat Example',
            '__is_helper_row': False,
            '__is_vac_crew': False,
            'Work Request #': _WR,
            'Weekly Reference Logged Date': _WEEK.isoformat(),
            'Units Completed?': True,
            'Units Total Price': 100.0,
            'Dept #': '500',
            'Job #': 'J-1',
        }

    def _run(self, status: str) -> None:
        frozen_map = {(_WR, _WEEK, 4242): {'primary_foreman': 'Pat Example'}}
        with mock.patch(
            'billing_audit.writer.prefetch_attribution',
            return_value=(frozen_map, status),
        ):
            gwp.group_source_rows([self._row()])

    def test_exposes_keys_after_successful_prefetch(self):
        self._run('success')
        self.assertEqual(set(self._accessor()()), {(_WR, _WEEK, 4242)})

    def test_exposes_nothing_on_fetch_failure(self):
        self._run('fetch_failure')
        self.assertEqual(self._accessor()(), frozenset())

    def test_exposes_nothing_on_the_other_failure_statuses(self):
        for status in ('rpc_missing', 'unavailable', 'no_row'):
            with self.subTest(status=status):
                self._run(status)
                self.assertEqual(self._accessor()(), frozenset())

    def test_resets_when_the_next_call_has_no_prefetch(self):
        self._run('success')
        gwp.BILLING_AUDIT_AVAILABLE = False
        gwp.group_source_rows([self._row()])
        self.assertEqual(self._accessor()(), frozenset())


class SeededKeySkipsFreezeRpcTests(unittest.TestCase):
    """A seeded key drops its row from the freeze candidates (no RPC)."""

    def test_loop_key_literal_matches_the_helper(self):
        src = _read_source('pipeline/orchestrate.py')
        self.assertIn('f"{wr_num}|{week_raw}|{_row_id}"', src)
        self.assertIn('if _cache_key in billing_audit_row_cache:', src)

    def test_seeded_row_is_not_a_freeze_candidate(self):
        from pipeline.attribution import warm_billing_audit_row_cache
        cache: set[str] = set()
        warm_billing_audit_row_cache(cache, {(_WR, _WEEK, 4242)})
        wr_num, week_raw = _WR, '083026'  # what the loop derives per group
        rows = [
            {'__row_id': 4242, 'Units Completed?': True},
            {'__row_id': 4243, 'Units Completed?': True},
        ]
        # The freeze loop's candidate filter, verbatim.
        _rows_to_freeze = [
            r for r in rows
            if isinstance(r.get('__row_id'), int)
            and gwp.is_checked(r.get('Units Completed?'))
            and f"{wr_num}|{week_raw}|{r['__row_id']}" not in cache
        ]
        freeze_row = mock.Mock(return_value=True)
        for r in _rows_to_freeze:
            freeze_row(r)
        self.assertEqual([r['__row_id'] for r in _rows_to_freeze], [4243])
        freeze_row.assert_called_once_with(rows[1])


class OrchestrateWiringTests(unittest.TestCase):
    """The seed happens after the cache is created, before the group loop."""

    def test_cache_is_seeded_before_the_group_loop(self):
        src = _read_source('pipeline/orchestrate.py')
        init = src.find('billing_audit_row_cache: set[str] = set()')
        seed = src.find(
            'warm_billing_audit_row_cache(\n'
            '            billing_audit_row_cache, '
            'get_prefetched_frozen_row_keys()'
        )
        loop = src.find(
            'for group_idx, (group_key, group_rows) in '
            'enumerate(groups.items(), 1):'
        )
        self.assertGreater(init, 0, 'cache init missing')
        self.assertGreater(seed, init, 'seed must follow the cache init')
        self.assertGreater(loop, seed, 'seed must precede the group loop')


if __name__ == '__main__':
    unittest.main()
