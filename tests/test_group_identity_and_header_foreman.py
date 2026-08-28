"""Follow-up to PR #361 (Codex 3876992815 / 3876992822, Copilot 3877822173).

1. ``derive_group_identity()`` is the ONE identity definition behind the
   three orchestrate identity sites (Site 1 main-loop ``history_key`` /
   ``file_identifier``, Site 2 ``valid_wr_weeks`` cleanup tuple, Site 3
   ``current_keys`` prune). A two-order test asserts the history key,
   cleanup tuple and prune key are identical for both arrival orders,
   and a table test proves the helper reproduces every branch of the
   former inline chains (both kill-switch states, every grouping mode).
2. ``canonical_foreman()`` is the hash's ``FOREMAN=`` rule -- the first
   non-empty ``__current_foreman`` (else ``Foreman``) in canonical order
   -- and the PRIMARY workbook header now shows it (helper-shadow /
   subcontractor headers keep the attributed claimer). Golden digests on
   the pre-change code, pin the hash byte-identical through the
   extraction.
3. ``canonical_first_row()`` is deterministic in legacy mode too, while
   the legacy hash stays byte-identical (golden digest).
"""

from __future__ import annotations

import datetime
import inspect
import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import generate_weekly_pdfs  # noqa: E402
import pipeline.orchestrate  # noqa: E402
from pipeline import change_detection  # noqa: E402
from pipeline.config import (  # noqa: E402
    _RE_SANITIZE_HELPER_NAME,
    _RE_SANITIZE_IDENTIFIER,
)
from pipeline.orchestrate import derive_group_identity  # noqa: E402

# Digests from the pre-change code (2026-08-28, master b23b7af) for the
# fixtures below. Any drift here means the FOREMAN= extraction or the
# legacy-mode change altered a hash.
GOLDEN_MIXED_PRIMARY = '4f5d44a9fe2ba3f4'
GOLDEN_RAW_FALLBACK = 'b8da636059f26ffe'
GOLDEN_HELPER = 'c5dbeb790ed43c0c'
GOLDEN_LEGACY_HELPER = '4d8eea56b2fefe65'


def _row(**extra):
    row = {
        'Work Request #': '90003',
        'Snapshot Date': '2026-07-30',
        'CU': 'CU-100',
        'Quantity': 1,
        'Units Total Price': '$50.00',
        'Pole #': 'P-7',
        'Work Type': 'Install',
        'Dept #': '520',
        'Units Completed?': True,
        'Foreman': '',
        '__current_foreman': '',
        '__variant': 'primary',
    }
    row.update(extra)
    return row


def _mixed_primary():
    return [
        _row(CU='CU-100'),
        _row(CU='CU-200', __current_foreman='Pat Example'),
        _row(CU='CU-300', Foreman='Raw Foreman'),
    ]


def _helper_pair():
    return [
        _row(CU='CU-100', __variant='helper', __helper_foreman='Sam Sample',
             __helper_dept='NA-03', __helper_job='J-1',
             __current_foreman='Pat Example'),
        _row(CU='CU-100', __variant='helper', __helper_foreman='Sam Sample',
             __helper_dept='NA-04', __helper_job='J-2',
             __current_foreman='Pat Example'),
    ]


class _HashModeMixin:
    def setUp(self):
        self._saved = {k: getattr(generate_weekly_pdfs, k) for k in
                       ('EXTENDED_CHANGE_DETECTION', 'RATE_CUTOFF_DATE',
                        '_RATES_FINGERPRINT')}
        generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION = True
        generate_weekly_pdfs.RATE_CUTOFF_DATE = None
        generate_weekly_pdfs._RATES_FINGERPRINT = ''

    def tearDown(self):
        for k, v in self._saved.items():
            setattr(generate_weekly_pdfs, k, v)


def _reference_site1(first_row, pca, vca, mode):
    """The Site 1 chain exactly as it stood inline on master `b23b7af`
    (before extraction). The helper must reproduce it for every input."""
    variant = first_row.get('__variant', 'primary')
    if variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):
        helper_foreman = first_row.get('__helper_foreman', '')
        helper_dept = first_row.get('__helper_dept', '')
        helper_job = first_row.get('__helper_job', '')
        identifier = f"{helper_foreman}|{helper_dept}|{helper_job}"
        file_identifier = (_RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)
                           [:50] if helper_foreman else '')
    elif variant == 'vac_crew':
        _vc = first_row.get('__current_foreman', '')
        identifier = (_RE_SANITIZE_IDENTIFIER.sub('_', _vc)[:50]
                      if (vca and _vc) else '')
        file_identifier = identifier
    elif variant in ('reduced_sub', 'aep_billable'):
        _b = first_row.get('__current_foreman', '')
        identifier = _RE_SANITIZE_IDENTIFIER.sub('_', _b)[:50] if _b else ''
        file_identifier = identifier
    else:
        if pca and mode in ('helper', 'both'):
            _pf = first_row.get('__current_foreman', '')
            identifier = (_RE_SANITIZE_IDENTIFIER.sub('_', _pf)[:50]
                          if _pf else '')
        else:
            user_val = first_row.get('User')
            identifier = (_RE_SANITIZE_IDENTIFIER.sub('_', user_val)[:50]
                          if user_val else '')
        file_identifier = identifier
    return identifier, file_identifier


class DeriveGroupIdentityTests(unittest.TestCase):
    """The helper is byte-for-byte the former inline chain."""

    ROWS = [
        {'__variant': 'helper', '__helper_foreman': 'Sam Sample',
         '__helper_dept': 'NA-03', '__helper_job': 'J-1'},
        {'__variant': 'aep_billable_helper', '__helper_foreman': 'A/B C',
         '__helper_dept': '', '__helper_job': ''},
        {'__variant': 'reduced_sub_helper', '__helper_foreman': '',
         '__helper_dept': 'NA-04'},
        {'__variant': 'vac_crew', '__current_foreman': 'Vac Lead'},
        {'__variant': 'vac_crew', '__current_foreman': ''},
        {'__variant': 'reduced_sub', '__current_foreman': 'Sub Claimer'},
        {'__variant': 'aep_billable', '__current_foreman': ''},
        {'__variant': 'primary', '__current_foreman': 'Pat Example',
         'User': 'legacy user'},
        {'__variant': 'primary', '__current_foreman': '',
         'User': 'legacy user'},
        {'__variant': 'primary', '__current_foreman': 'Pat Example'},
        {'__current_foreman': 'x' * 80, 'User': 'y' * 80},
        {},
    ]

    def test_matches_the_inline_chain_for_every_branch(self):
        for row in self.ROWS:
            for pca in (True, False):
                for vca in (True, False):
                    for mode in ('primary', 'helper', 'both'):
                        with self.subTest(row=row, pca=pca, vca=vca,
                                          mode=mode):
                            self.assertEqual(
                                derive_group_identity(
                                    row, primary_claim_enabled=pca,
                                    vac_crew_claim_enabled=vca,
                                    res_grouping_mode=mode),
                                _reference_site1(row, pca, vca, mode))

    def test_helper_family_history_and_file_shapes_differ(self):
        ident, file_id = derive_group_identity(
            self.ROWS[0], primary_claim_enabled=True,
            vac_crew_claim_enabled=True, res_grouping_mode='both')
        self.assertEqual(ident, 'Sam Sample|NA-03|J-1')
        self.assertEqual(file_id, 'Sam_Sample')


class SitesTwoOrderTests(_HashModeMixin, unittest.TestCase):
    """Copilot 3877822173: process both row orders and assert identical
    history keys (Site 1), cleanup tuples (Site 2) and prune keys
    (Site 3) -- built exactly the way the sites build them, from the
    shared helper over the canonical row."""

    def _keys(self, group_key, rows, **switches):
        first = change_detection.canonical_first_row(rows)
        wr = str(first.get('Work Request #')).split('.')[0]
        wr = _RE_SANITIZE_HELPER_NAME.sub('_', wr)[:50]
        week = group_key.split('_', 1)[0]
        variant = first.get('__variant', 'primary')
        identifier, file_identifier = derive_group_identity(
            first, **switches)
        history_key = f"{wr}|{week}|{variant}|{identifier}"
        cleanup_tuple = (wr, week, variant, file_identifier)
        prune_key = f"{wr}|{week}|{variant}|{identifier}"
        return history_key, cleanup_tuple, prune_key

    def _assert_order_independent(self, group_key, rows, **switches):
        seen = {self._keys(group_key, list(order), **switches)
                for order in (rows, rows[::-1])}
        self.assertEqual(len(seen), 1, seen)
        hashes = {generate_weekly_pdfs.calculate_data_hash(list(order))
                  for order in (rows, rows[::-1])}
        self.assertEqual(len(hashes), 1)
        return next(iter(seen))

    def test_mixed_department_helper_group(self):
        hk, ct, pk = self._assert_order_independent(
            '073026_90003_HELPER_Sam_Sample', _helper_pair(),
            primary_claim_enabled=True, vac_crew_claim_enabled=True,
            res_grouping_mode='both')
        self.assertEqual(hk, '90003|073026|helper|Sam Sample|NA-03|J-1')
        self.assertEqual(ct, ('90003', '073026', 'helper', 'Sam_Sample'))
        self.assertEqual(pk, hk)

    def test_primary_group_with_mixed_users_legacy_identity(self):
        rows = [_row(CU='CU-100', User='alice'),
                _row(CU='CU-100', User='bob')]
        hk, ct, pk = self._assert_order_independent(
            '073026_90003', rows, primary_claim_enabled=False,
            vac_crew_claim_enabled=False, res_grouping_mode='both')
        self.assertEqual(hk, '90003|073026|primary|alice')
        self.assertEqual(ct, ('90003', '073026', 'primary', 'alice'))

    def test_primary_group_with_mixed_claimers_attributed(self):
        rows = [_row(CU='CU-100', __current_foreman='Pat Example'),
                _row(CU='CU-100', __current_foreman='')]
        hk, ct, pk = self._assert_order_independent(
            '073026_90003', rows, primary_claim_enabled=True,
            vac_crew_claim_enabled=False, res_grouping_mode='both')
        self.assertEqual(ct, ('90003', '073026', 'primary', ''))
        self.assertEqual(hk, '90003|073026|primary|')


class SitesWiringTests(unittest.TestCase):
    """The three sites really call the helper (with the run's kill
    switches) and carry no inline identity chain any more."""

    @classmethod
    def setUpClass(cls):
        cls._main = inspect.getsource(pipeline.orchestrate.main)

    def test_each_site_calls_the_shared_helper_with_the_run_switches(self):
        calls = re.findall(
            r"= derive_group_identity\(\s*\w+, \*\*_identity_switches\)",
            self._main)
        self.assertEqual(len(calls), 3, calls)
        # ...and the switches are bound ONCE from the run's facade values.
        self.assertRegex(
            self._main,
            r"_identity_switches = \{\s*"
            r"'primary_claim_enabled': PRIMARY_CLAIM_ATTRIBUTION_ENABLED,\s*"
            r"'vac_crew_claim_enabled': VAC_CREW_CLAIM_ATTRIBUTION_ENABLED,"
            r"\s*'res_grouping_mode': RES_GROUPING_MODE,\s*\}")
        self.assertEqual(self._main.count("_identity_switches = {"), 1)

    def test_no_inline_identity_chain_remains_in_main(self):
        for needle in ("get('__helper_foreman'", "get('__helper_dept'",
                       "get('__helper_job'", "get('User')",
                       "_RE_SANITIZE_IDENTIFIER.sub('_', _vc)",
                       "_RE_SANITIZE_IDENTIFIER.sub('_', _pf)",
                       "_RE_SANITIZE_IDENTIFIER.sub('_', _b_claimer)"):
            self.assertNotIn(needle, self._main, needle)


class CanonicalForemanTests(_HashModeMixin, unittest.TestCase):

    def test_hash_is_byte_identical_through_the_extraction(self):
        for rows, golden in ((_mixed_primary(), GOLDEN_MIXED_PRIMARY),
                             ([_row(CU='CU-100', Foreman='Raw Foreman'),
                               _row(CU='CU-200')], GOLDEN_RAW_FALLBACK),
                             (_helper_pair(), GOLDEN_HELPER)):
            for order in (rows, rows[::-1]):
                self.assertEqual(
                    generate_weekly_pdfs.calculate_data_hash(list(order)),
                    golden)

    def test_first_nonempty_rule_matches_the_hash_token(self):
        rows = _mixed_primary()
        for order in (rows, rows[::-1]):
            self.assertEqual(change_detection.canonical_foreman(order),
                             'Pat Example')
        # The canonical FIRST row is blank -- the rule must look past it.
        self.assertEqual(
            change_detection.canonical_first_row(rows)['__current_foreman'],
            '')
        self.assertEqual(change_detection.canonical_foreman(
            [_row(CU='CU-100', Foreman='Raw Foreman'), _row(CU='CU-200')]),
            'Raw Foreman')
        self.assertEqual(change_detection.canonical_foreman(
            [_row(CU='CU-100'), _row(CU='CU-200')]), '')
        self.assertEqual(change_detection.canonical_foreman([]), '')

    def test_only_the_primary_header_consults_the_hash_rule(self):
        """Production-risk review: helper / helper-shadow / subcontractor
        headers must keep naming the attributed claimer (the partition
        key) -- the raw ``Foreman`` column is the primary crew's foreman,
        so the hash rule may only feed the PRIMARY header."""
        import tempfile
        from unittest import mock
        saved = {k: getattr(generate_weekly_pdfs, k) for k in
                 ('OUTPUT_FOLDER', 'RES_GROUPING_MODE',
                  'PRIMARY_CLAIM_ATTRIBUTION_ENABLED')}
        tmp = tempfile.TemporaryDirectory()
        generate_weekly_pdfs.OUTPUT_FOLDER = tmp.name
        generate_weekly_pdfs.RES_GROUPING_MODE = 'both'
        generate_weekly_pdfs.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = False
        try:
            # Every partitioned variant: the header is the partition key
            # (frozen claimer / attributed helper), never the hash rule.
            for i, variant in enumerate(('helper', 'reduced_sub_helper',
                                         'aep_billable_helper', 'vac_crew',
                                         'reduced_sub', 'aep_billable')):
                rows = [_row(**{
                    'Work Request #': '90001',
                    'Weekly Reference Logged Date': '2026-07-26',
                    '__week_ending_date': datetime.datetime(2026, 7, 26),
                    '__variant': variant,
                    '__helper_foreman': 'Sam Sample',
                    '__helper_dept': 'NA-03', '__helper_job': 'J-1',
                    '__effective_user': 'Sam Sample',
                    '__current_foreman': 'Frozen Claimer',
                    'Foreman': 'Primary Person'})]
                key = ('072626_90001_HELPER_Sam_Sample'
                       if variant.endswith('helper') else '072626_90001')
                with self.subTest(variant=variant), mock.patch(
                        'pipeline.excel.canonical_foreman',
                        side_effect=AssertionError(
                            'hash rule consulted for %s' % variant)):
                    generate_weekly_pdfs.generate_excel(
                        key, rows, datetime.datetime(2026, 7, 26),
                        data_hash='deadbeefcafe%04d' % (10 + i))
            primary_rows = [dict(r, **{
                'Weekly Reference Logged Date': '2026-07-26',
                '__week_ending_date': datetime.datetime(2026, 7, 26)})
                for r in _mixed_primary()]
            with mock.patch('pipeline.excel.canonical_foreman',
                            return_value='From Hash Rule') as rule:
                generate_weekly_pdfs.generate_excel(
                    '072626_90003', primary_rows,
                    datetime.datetime(2026, 7, 26),
                    data_hash='deadbeefcafe0005')
            self.assertEqual(rule.call_count, 1)
        finally:
            for k, v in saved.items():
                setattr(generate_weekly_pdfs, k, v)
            tmp.cleanup()

    def test_workbook_header_shows_the_hash_foreman_in_both_orders(self):
        import tempfile
        import openpyxl
        saved = {k: getattr(generate_weekly_pdfs, k) for k in
                 ('OUTPUT_FOLDER', 'RES_GROUPING_MODE',
                  'PRIMARY_CLAIM_ATTRIBUTION_ENABLED')}
        tmp = tempfile.TemporaryDirectory()
        generate_weekly_pdfs.OUTPUT_FOLDER = tmp.name
        generate_weekly_pdfs.RES_GROUPING_MODE = 'primary'
        generate_weekly_pdfs.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = False
        try:
            rows = [dict(r, **{
                'Weekly Reference Logged Date': '2026-07-26',
                '__week_ending_date': datetime.datetime(2026, 7, 26)})
                for r in _mixed_primary()]
            shown = set()
            for order in (rows, rows[::-1]):
                path = generate_weekly_pdfs.generate_excel(
                    '072626_90003', list(order),
                    datetime.datetime(2026, 7, 26),
                    data_hash='deadbeefcafe0003')[0]
                ws = openpyxl.load_workbook(path).active
                for cells in ws.iter_rows(values_only=True):
                    for i, v in enumerate(cells):
                        if v == 'Foreman:':
                            shown.add(cells[i + 1])
            self.assertEqual(shown, {'Pat Example'})
        finally:
            for k, v in saved.items():
                setattr(generate_weekly_pdfs, k, v)
            tmp.cleanup()


class LegacyHeaderDeterminismTests(_HashModeMixin, unittest.TestCase):
    """Codex 3876992815: keep the legacy hash algorithm, but select the
    header / identity row deterministically."""

    def setUp(self):
        super().setUp()
        generate_weekly_pdfs.EXTENDED_CHANGE_DETECTION = False

    def test_legacy_hash_byte_identical_and_order_independent(self):
        rows = _helper_pair()
        for order in (rows, rows[::-1]):
            self.assertEqual(
                generate_weekly_pdfs.calculate_data_hash(list(order)),
                GOLDEN_LEGACY_HELPER)

    def test_legacy_header_row_is_order_independent(self):
        a, b = _helper_pair()
        self.assertIs(change_detection.canonical_first_row([a, b]),
                      change_detection.canonical_first_row([b, a]))
        self.assertEqual(
            change_detection.canonical_first_row([b, a])['__helper_dept'],
            'NA-03')
        # ...and so are the identity keys the sites build from it.
        keys = set()
        for order in ([a, b], [b, a]):
            first = change_detection.canonical_first_row(order)
            keys.add(derive_group_identity(
                first, primary_claim_enabled=True,
                vac_crew_claim_enabled=True, res_grouping_mode='both'))
        self.assertEqual(keys, {('Sam Sample|NA-03|J-1', 'Sam_Sample')})

    def test_legacy_foreman_rule_is_order_independent(self):
        rows = _mixed_primary()
        for order in (rows, rows[::-1]):
            self.assertEqual(change_detection.canonical_foreman(order),
                             'Pat Example')

    def test_legacy_hash_still_hashes_tied_rows_in_arrival_order(self):
        # Unchanged legacy semantics (test_legacy_mode_untouched): a
        # hashed-field difference on tied rows still flips the hash.
        rows = [_row(**{'Work Type': 'Install'}),
                _row(**{'Work Type': 'Remove'})]
        self.assertNotEqual(
            generate_weekly_pdfs.calculate_data_hash(rows),
            generate_weekly_pdfs.calculate_data_hash(rows[::-1]))


if __name__ == "__main__":
    unittest.main()
