"""Phase 15 plan 02 Task 3: note normaliser, digests, globals component."""
import itertools
import re
import unittest

from pipeline import foreman_notes as fn

# noqa: E731 - module is tested without change_detection
IDENT = lambda r: r['CU']


def _row(cu, note, wr='90003'):
    return {'Work Request #': wr, 'CU': cu, fn.NOTES_KEY: note}


class NormNoteTests(unittest.TestCase):
    def test_none_and_numbers(self):
        self.assertEqual(fn.norm_note(None), '')
        self.assertEqual(fn.norm_note(12.5), '12.5')

    def test_illegal_chars_removed_then_trimmed(self):
        # illegal char removed first, then strip; inner whitespace is preserved
        self.assertEqual(fn.norm_note('  hi \x01there '), 'hi there')
        self.assertEqual(fn.norm_note('\x01 \x02'), '')
        self.assertEqual(fn.norm_note(' \x01x'), 'x')

    def test_cap(self):
        self.assertEqual(len(fn.norm_note('a' * 40000)), 32767)

    def test_formula_text_kept_verbatim(self):
        self.assertEqual(fn.norm_note('=SUM(A1)'), '=SUM(A1)')


class RowComponentTests(unittest.TestCase):
    def tearDown(self):
        fn.reset_state()

    def test_off_and_non_pilot_are_none(self):
        row = _row('CU1', ' hello ')
        self.assertIsNone(fn.row_notes_component(row))
        fn.set_state(fn.FnState(scope='pilot', pilot_wrs=frozenset({'90003'})))
        self.assertIsNone(fn.row_notes_component(_row('CU1', 'x', wr='11111')))

    def test_pilot_row(self):
        fn.set_state(fn.FnState(scope='pilot', pilot_wrs=frozenset({'90003'})))
        self.assertEqual(
            fn.row_notes_component(_row('CU1', ' hello \x01')), 'hello'
        )
        self.assertEqual(fn.row_notes_component(_row('CU1', None)), '')
        self.assertEqual(
            fn.row_notes_component({'Work Request #': '90003'}), ''
        )


class GroupTokenTests(unittest.TestCase):
    def setUp(self):
        fn.set_state(fn.FnState(scope='pilot', pilot_wrs=frozenset({'90003'})))

    def tearDown(self):
        fn.reset_state()

    def test_non_pilot_is_empty(self):
        rows = [_row('CU1', 'x', wr='11111')]
        self.assertEqual(fn.group_notes_token(rows, IDENT), '')
        self.assertEqual(fn.group_notes_token([], IDENT), '')
        fn.reset_state()
        self.assertEqual(fn.group_notes_token([_row('CU1', 'x')], IDENT), '')

    def test_shape(self):
        tok = fn.group_notes_token([_row('CU1', 'a'), _row('CU2', 'b')], IDENT)
        self.assertRegex(tok, r'^[0-9a-f]{16}$')

    def test_permutation_invariant_including_ties(self):
        rows = [_row('CU1', 'a'), _row('CU1', 'b'), _row('CU2', 'c')]
        toks = {fn.group_notes_token(list(p), IDENT)
                for p in itertools.permutations(rows)}
        self.assertEqual(len(toks), 1)

    def test_note_change_flips(self):
        a = fn.group_notes_token([_row('CU1', 'a'), _row('CU2', 'b')], IDENT)
        b = fn.group_notes_token([_row('CU1', 'a'), _row('CU2', 'B')], IDENT)
        self.assertNotEqual(a, b)

    def test_tie_notes_swap_between_identities_flips(self):
        a = fn.group_notes_token([_row('CU1', 'a'), _row('CU2', 'b')], IDENT)
        b = fn.group_notes_token([_row('CU1', 'b'), _row('CU2', 'a')], IDENT)
        self.assertNotEqual(a, b)

    def test_whitespace_only_change_is_stable(self):
        a = fn.group_notes_token([_row('CU1', 'a')], IDENT)
        b = fn.group_notes_token([_row('CU1', '  a \n')], IDENT)
        self.assertEqual(a, b)

    def test_all_blank_is_deterministic_non_empty(self):
        a = fn.group_notes_token([_row('CU1', None), _row('CU2', '  ')], IDENT)
        b = fn.group_notes_token([_row('CU2', ''), _row('CU1', None)], IDENT)
        self.assertTrue(a)
        self.assertEqual(a, b)

    def test_identity_failure_is_empty_not_raise(self):
        def bad(r):
            raise RuntimeError('x')
        with self.assertLogs(level='WARNING'):
            self.assertEqual(fn.group_notes_token([_row('CU1', 'a')], bad), '')


class GlobalsComponentTests(unittest.TestCase):
    def tearDown(self):
        fn.reset_state()

    def test_off_is_empty(self):
        self.assertEqual(fn.globals_component(), '')

    def test_changes_with_inputs(self):
        def comp(**kw):
            fn.set_state(fn.FnState(**kw))
            return fn.globals_component()
        base = comp(
            scope='pilot', allowlist=frozenset({'a'}),
            pilot_wrs=frozenset({'1'})
        )
        self.assertRegex(base, r'^[0-9a-f]{16}$')
        self.assertEqual(
            base, comp(
                scope='pilot', allowlist=frozenset({'a'}),
                pilot_wrs=frozenset({'1'})
            ))
        self.assertNotEqual(
            base, comp(
                scope='all', allowlist=frozenset({'a'}),
                pilot_wrs=frozenset({'1'})
            ))
        self.assertNotEqual(
            base, comp(
                scope='pilot', allowlist=frozenset({'a', 'b'}),
                pilot_wrs=frozenset({'1'})
            ))
        self.assertNotEqual(
            base, comp(
                scope='pilot', allowlist=frozenset({'a'}),
                pilot_wrs=frozenset({'1', '2'})
            ))


class ModuleBoundaryTests(unittest.TestCase):
    def test_no_hash_function_reads_style_key(self):
        import inspect
        for fnc in (fn.norm_note, fn.row_notes_component, fn.group_notes_token,
                    fn.globals_component):
            self.assertNotIn('STYLE_KEY', inspect.getsource(fnc))
            self.assertNotIn('__fn_style', inspect.getsource(fnc))


if __name__ == '__main__':
    unittest.main()
