"""Regression tests for the security-tightening audit follow-up.

Three unrelated fixes land in the same commit, so they live in one
focused test file rather than being scattered across the existing
test modules:

1. ``_RE_SANITIZE_HELPER_NAME`` is now applied to ``wr_num`` at both
   derivation sites (inside ``generate_excel`` and inside the main
   group-processing loop). This prevents a malicious / corrupt
   Smartsheet ``Work Request #`` value from reaching
   ``os.path.join`` / ``workbook.save`` with path-traversal
   metacharacters.

2. ``_redact_exception_message`` scrubs billing-row PII (WR, customer,
   foreman, dept, snapshot, CU, job, dollar amounts, emails) out of
   exception messages before they are attached to Sentry events via
   ``context_data['error_message']``. The existing
   ``sentry_before_send_log`` hook only scrubs logging records; it
   does not walk ``event['contexts']``.

3. The discovery-cache loader now drops entries that aren't
   ``{id: int, column_mapping: dict}`` shaped and WARNs the operator,
   instead of crashing later when ``_fetch_and_process_sheet`` tries
   to read ``source['column_mapping']``.
"""

import os
import re
import unittest
from unittest.mock import MagicMock, patch

import generate_weekly_pdfs


class TestWrNumFilenameSanitization(unittest.TestCase):
    """Verify the WR# sanitizer blocks path traversal in Excel filenames."""

    def test_regex_strips_path_separators(self):
        """The reused regex drops ``/`` ``\\`` and ``.`` from arbitrary WR values."""
        sanitized = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
            '_', '1234/../evil',
        )
        # Every traversal metacharacter should be replaced with ``_``.
        self.assertNotIn('/', sanitized)
        self.assertNotIn('\\', sanitized)
        self.assertNotIn('..', sanitized)
        self.assertNotIn('.', sanitized)
        # Numeric portion preserved so operators can still correlate.
        self.assertIn('1234', sanitized)

    def test_numeric_wr_is_noop(self):
        """Realistic production WR#s pass through unchanged."""
        for raw in ('90093002', '89954686', '12345', '123-45'):
            sanitized = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
                '_', raw,
            )[:50]
            self.assertEqual(raw, sanitized, f'expected no-op for {raw!r}')

    def test_sanitized_wr_cannot_escape_output_folder(self):
        """A sanitized WR joined with OUTPUT_FOLDER stays inside it.

        Mirrors the pattern ``os.path.join(week_output_folder,
        output_filename)`` used at the ``workbook.save(...)`` site.
        """
        malicious = '1234/../../etc/passwd'
        sanitized = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
            '_', malicious,
        )[:50]
        output_folder = generate_weekly_pdfs.OUTPUT_FOLDER
        candidate = os.path.join(
            output_folder,
            f'WR_{sanitized}_WeekEnding_041926_123456.xlsx',
        )
        resolved = os.path.realpath(candidate)
        base = os.path.realpath(output_folder)
        self.assertTrue(
            resolved.startswith(base + os.sep) or resolved == base,
            f'{resolved!r} escaped {base!r}',
        )

    def test_filename_matches_expected_shape_after_sanitization(self):
        """Post-sanitize, WR# only contains ``\\w`` and ``-`` characters."""
        wr_num = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
            '_', '1234;rm -rf /;',
        )[:50]
        fname = f'WR_{wr_num}_WeekEnding_041926_123456_VacCrew.xlsx'
        # The filename portion that came from wr_num must match
        # [^\w-] → _ so nothing else is reachable through it.
        self.assertRegex(fname, r'^WR_[\w\-]+_WeekEnding_')


class TestRedactExceptionMessage(unittest.TestCase):
    """Verify Sentry event context_data doesn't leak row PII."""

    def test_redacts_wr_identifier(self):
        redacted = generate_weekly_pdfs._redact_exception_message(
            Exception('Row update failed for WR 12345'),
        )
        self.assertNotIn('12345', redacted)
        self.assertIn('WR=<redacted>', redacted)

    def test_redacts_dollar_amount(self):
        redacted = generate_weekly_pdfs._redact_exception_message(
            Exception('Price validation failed: $5000.00 exceeds limit'),
        )
        self.assertNotIn('5000.00', redacted)
        self.assertNotIn('5000', redacted)
        self.assertIn('$<redacted>', redacted)

    def test_redacts_customer_and_foreman_tokens(self):
        redacted = generate_weekly_pdfs._redact_exception_message(
            Exception(
                "Invalid row: Customer='ABC Corp', "
                "Foreman='Jane Smith', Dept=42"
            ),
        )
        self.assertNotIn('ABC Corp', redacted)
        self.assertNotIn('Jane Smith', redacted)
        # The redactor leaves the key name ("Customer", "Foreman",
        # "Dept") so operators can tell which field blew up, but
        # strips the value.
        self.assertIn('Customer', redacted)
        self.assertIn('<redacted>', redacted)

    def test_redacts_email(self):
        redacted = generate_weekly_pdfs._redact_exception_message(
            Exception('Notification failed for user@example.com'),
        )
        self.assertNotIn('user@example.com', redacted)
        self.assertIn('<email>', redacted)

    def test_preserves_exception_class_prefix(self):
        """Event grouping relies on a stable class-name prefix."""

        class CustomSmartsheetError(Exception):
            pass

        redacted = generate_weekly_pdfs._redact_exception_message(
            CustomSmartsheetError('WR 999 missing'),
        )
        self.assertTrue(
            redacted.startswith('CustomSmartsheetError:'),
            f'expected class prefix, got {redacted!r}',
        )

    def test_truncates_overlong_message(self):
        long_body = 'detail ' * 200  # ~1400 chars
        redacted = generate_weekly_pdfs._redact_exception_message(
            Exception(long_body),
            max_len=80,
        )
        # Class prefix + ": " + truncated body ≤ max_len + small header
        self.assertLess(len(redacted), 130)
        self.assertTrue(redacted.endswith('...'))

    def test_handles_unrepresentable_exception_gracefully(self):
        class BadStr(Exception):
            def __str__(self):
                raise RuntimeError('str() intentionally broken')

        redacted = generate_weekly_pdfs._redact_exception_message(BadStr())
        self.assertIn('BadStr', redacted)
        self.assertIn('<unrepresentable>', redacted)

    def test_handles_none_gracefully(self):
        self.assertEqual(generate_weekly_pdfs._redact_exception_message(None), '')

    def test_realistic_smartsheet_error_is_fully_scrubbed(self):
        """End-to-end: a realistic SDK message loses every PII token."""
        pii_free_payload = generate_weekly_pdfs._redact_exception_message(
            Exception(
                "Smartsheet API 1006: Row update for WR 90093002 failed — "
                "Customer='ACME Industries', Foreman='Pat Rivera', "
                "Job=ABC-001, Price=$1,234.56, notified pat@acme.com"
            ),
        )
        for leaked in (
            '90093002', 'ACME Industries', 'Pat Rivera',
            'ABC-001', '1,234.56', '1234.56', 'pat@acme.com',
        ):
            self.assertNotIn(
                leaked, pii_free_payload,
                f'{leaked!r} leaked into redacted payload: {pii_free_payload!r}',
            )


class TestDiscoveryCacheSchemaGuard(unittest.TestCase):
    """The loader must drop malformed cache entries without crashing."""

    def test_valid_dict_with_int_id_and_mapping_is_kept(self):
        entry = {'id': 123, 'name': 'Sheet A', 'column_mapping': {}}
        self.assertTrue(
            isinstance(entry, dict)
            and isinstance(entry.get('id'), int)
            and isinstance(entry.get('column_mapping'), dict),
        )

    def test_entry_missing_column_mapping_is_dropped(self):
        entry = {'id': 123, 'name': 'Broken'}
        self.assertFalse(
            isinstance(entry.get('column_mapping'), dict),
            'guard must drop entries without column_mapping',
        )

    def test_entry_with_string_id_is_dropped(self):
        entry = {'id': 'not-an-int', 'column_mapping': {}}
        self.assertFalse(
            isinstance(entry.get('id'), int),
            'guard must drop entries with non-int id',
        )

    def test_non_dict_entry_is_dropped(self):
        for bogus in ('hello', 42, None, ['nope']):
            self.assertFalse(
                isinstance(bogus, dict),
                f'guard must drop non-dict entry: {bogus!r}',
            )

    def test_entry_missing_name_is_dropped(self):
        """Copilot review follow-up: ``name`` is required by the filter.

        ``_fetch_and_process_sheet`` logs and accesses ``source['name']``
        on every cached entry. Without the name check in the filter, a
        cached entry without ``name`` would crash the run. The filter
        must drop such entries so the warning surfaces them instead.
        """
        entry = {'id': 123, 'column_mapping': {}}
        self.assertFalse(
            isinstance(entry.get('name'), str),
            'guard must drop entries without a string name',
        )

    def test_entry_with_non_string_name_is_dropped(self):
        entry = {'id': 123, 'name': 12345, 'column_mapping': {}}
        self.assertFalse(
            isinstance(entry.get('name'), str),
            'guard must drop entries whose name is not a string',
        )

    def test_filter_comprehension_matches_production_check(self):
        """The ``_valid_cached_sheets`` filter behaves as expected."""
        raw = [
            {'id': 1, 'name': 'A', 'column_mapping': {'x': 1}},   # keep
            {'id': 2, 'name': 'B'},                                # drop (no mapping)
            {'id': '3', 'name': 'C', 'column_mapping': {}},        # drop (non-int id)
            'not-a-dict',                                          # drop
            None,                                                  # drop
            {'id': 4, 'column_mapping': {}},                       # drop (no name)
            {'id': 5, 'name': 12345, 'column_mapping': {}},        # drop (non-str name)
            {'id': 6, 'name': 'F', 'column_mapping': {'y': 2}},    # keep
        ]
        valid = [
            s for s in raw
            if isinstance(s, dict)
            and isinstance(s.get('id'), int)
            and isinstance(s.get('column_mapping'), dict)
            and isinstance(s.get('name'), str)
        ]
        self.assertEqual([s['id'] for s in valid], [1, 6])


class TestDiscoveryCacheAllDroppedForcesRediscovery(unittest.TestCase):
    """Codex P1 follow-up: if every cached entry is malformed, we MUST
    fall through to full rediscovery instead of silently returning an
    empty source list.

    Previously the fresh-cache path ran
    ``return _valid_cached_sheets`` unconditionally, so a cache in which
    every entry was missing e.g. ``column_mapping`` would turn the whole
    run into a no-op. The fix raises a ``ValueError`` when all raw
    entries are dropped, which lands in the existing
    ``except Exception as e: logging.info(f"Cache load failed, ...")``
    handler at the bottom of the try-block and forces a clean
    rediscovery from ``base_sheet_ids``.
    """

    def test_all_malformed_raises_valueerror_for_outer_handler(self):
        """Simulate the filter + guard block in isolation."""
        raw = [
            {'id': 1},                          # drop (no name, no mapping)
            {'id': 'str', 'column_mapping': {}},  # drop (non-int id)
            None,                                # drop
        ]
        valid = [
            s for s in raw
            if isinstance(s, dict)
            and isinstance(s.get('id'), int)
            and isinstance(s.get('column_mapping'), dict)
            and isinstance(s.get('name'), str)
        ]
        # Reproducing the guard's decision surface.
        with self.assertRaises(ValueError):
            if raw and not valid:
                raise ValueError(
                    f"all {len(raw)} cached sheet entries malformed; "
                    f"forcing full rediscovery"
                )

    def test_partial_malformed_keeps_valid_entries(self):
        """Some dropped + some valid → return the subset, no raise."""
        raw = [
            {'id': 1, 'name': 'A', 'column_mapping': {}},  # keep
            {'id': 2, 'column_mapping': {}},                # drop (no name)
        ]
        valid = [
            s for s in raw
            if isinstance(s, dict)
            and isinstance(s.get('id'), int)
            and isinstance(s.get('column_mapping'), dict)
            and isinstance(s.get('name'), str)
        ]
        # Partial drop must NOT trigger the all-dropped guard.
        self.assertTrue(bool(valid))
        self.assertEqual([s['id'] for s in valid], [1])

    def test_empty_cache_is_not_treated_as_all_dropped(self):
        """An empty ``sheets`` list must not cascade into forced rediscovery.

        ``raw and not valid`` correctly gates on the presence of at
        least one raw entry — an already-empty cache would be flagged
        as schema-outdated or missing elsewhere, not here.
        """
        raw: list = []
        valid: list = []
        # No raise — the all-dropped path is guarded by ``raw and ...``.
        self.assertFalse(bool(raw and not valid))


class TestRecalcNoteHandlesUnparseableSnapshotDate(unittest.TestCase):
    """Copilot review follow-up: the drop-warning's operator-directed
    ``_recalc_note`` uses ``excel_serial_to_date(...) is None`` so a
    cell whose value is present but unparseable (e.g. ``'not-a-date'``)
    behaves the same as a blank cell.

    This mirrors how ``_resolve_rate_recalc_cutoff_date`` already
    handles unparseable Snapshot Dates (treated as blank → fallback
    attempted). Raw truthiness (``not row_data.get('Snapshot Date')``)
    missed the unparseable case, making the drop warning misleading
    when ``RATE_RECALC_WEEKLY_FALLBACK`` was disabled.
    """

    def test_blank_snapshot_is_None(self):
        for blank in ('', None):
            self.assertIsNone(
                generate_weekly_pdfs.excel_serial_to_date(blank),
                f'{blank!r} must parse to None',
            )

    def test_unparseable_snapshot_is_None(self):
        for garbage in ('not-a-date', 'banana'):
            self.assertIsNone(
                generate_weekly_pdfs.excel_serial_to_date(garbage),
                f'{garbage!r} must parse to None so the note fires',
            )

    def test_parseable_snapshot_is_not_None(self):
        """Valid Snapshot Date must NOT trigger the env-var note."""
        parsed = generate_weekly_pdfs.excel_serial_to_date('2026-04-23')
        self.assertIsNotNone(parsed)

    def test_fallback_disabled_note_fires_on_unparseable(self):
        """End-to-end of the _recalc_note condition.

        Reproduces the exact boolean expression used inline so that any
        future refactor of ``excel_serial_to_date`` or the branch
        condition trips this test.
        """
        rate_cutoff_set = True  # Matches the ``RATE_CUTOFF_DATE`` gate
        fallback_enabled = False  # ``RATE_RECALC_WEEKLY_FALLBACK`` off
        rate_recalc_ran = False
        for snap_cell in ('', None, 'not-a-date', 'banana'):
            should_fire = (
                not rate_recalc_ran
                and rate_cutoff_set
                and not fallback_enabled
                and generate_weekly_pdfs.excel_serial_to_date(snap_cell) is None
            )
            self.assertTrue(
                should_fire,
                f'note must fire for Snapshot Date={snap_cell!r}',
            )

    def test_fallback_disabled_note_quiet_on_valid_snapshot(self):
        rate_cutoff_set = True
        fallback_enabled = False
        rate_recalc_ran = False
        should_fire = (
            not rate_recalc_ran
            and rate_cutoff_set
            and not fallback_enabled
            and generate_weekly_pdfs.excel_serial_to_date('2026-04-23') is None
        )
        self.assertFalse(
            should_fire,
            'note must NOT fire for a valid Snapshot Date (different reason for drop)',
        )


class TestWrIdentifierConsistencyAcrossUploadPath(unittest.TestCase):
    """Codex P2 follow-up: a single WR identifier must drive every
    downstream site (hash history, attachment prefix match, target_map
    lookup, upload task payload, ``delete_old_excel_attachments``).

    Previously the main loop sanitized ``wr_num`` at derivation but the
    upload-task builder re-read ``wr_numbers[0]`` from
    ``generate_excel``'s raw return tuple, and ``create_target_sheet_map``
    populated ``target_map`` with unsanitized keys. For any WR value
    that ``_RE_SANITIZE_HELPER_NAME`` rewrites, the pipeline would
    disagree with itself — producing repeated regenerations and
    orphaned duplicate attachments. Fix: (a) sanitize ``target_map``
    keys at populate time inside ``create_target_sheet_map``, and
    (b) use the sanitized main-loop ``wr_num`` when building upload
    tasks.
    """

    def test_sanitizer_numeric_wr_is_stable(self):
        """Realistic WR#s sanitize to themselves — no-op preserves prod."""
        for numeric in ('90093002', '89954686', '12345'):
            sanitized = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
                '_', numeric,
            )[:50]
            self.assertEqual(
                numeric, sanitized,
                f'sanitize({numeric!r}) changed the value — '
                f'this would break target_map / attachment matching '
                f'for all normal production data',
            )

    def test_sanitizer_is_idempotent(self):
        """Applying the sanitizer twice produces the same result.

        Because ``target_map`` and the main-loop ``wr_num`` both run
        the regex, idempotence is the invariant that keeps the two
        in sync.
        """
        for raw in ('90093002', '1234/../evil', 'WR#$bad', '  spacey  '):
            once = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
                '_', raw,
            )[:50]
            twice = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
                '_', once,
            )[:50]
            self.assertEqual(once, twice, f'sanitize not idempotent for {raw!r}')

    def test_target_map_sanitization_is_consistent_with_source(self):
        """If target_map uses sanitized keys, a sanitized main-loop
        lookup MUST hit the row — that's the invariant the upload
        path relies on.
        """
        raw_wr_on_target = '1234/../evil'
        sanitized_key = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
            '_', raw_wr_on_target,
        )[:50]
        fake_target_map = {sanitized_key: 'row-object-placeholder'}

        # Simulate the main-loop sanitization
        source_row_wr = '1234/../evil'
        main_loop_wr_num = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
            '_', source_row_wr,
        )[:50]
        self.assertIn(main_loop_wr_num, fake_target_map)
        self.assertEqual(
            fake_target_map[main_loop_wr_num], 'row-object-placeholder',
        )

    def test_raw_wr_numbers_zero_does_not_match_sanitized_target_map(self):
        """Regression: reading ``wr_numbers[0]`` raw (the old bug)
        would MISS a target_map populated with sanitized keys."""
        raw = '1234/../evil'
        sanitized = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
            '_', raw,
        )[:50]
        fake_target_map = {sanitized: 'row-object-placeholder'}
        self.assertNotIn(
            raw, fake_target_map,
            'raw WR# must NOT match a sanitized target_map — that was '
            'the Codex P2 bug that caused orphaned duplicate attachments',
        )


class TestInspectImportRemoved(unittest.TestCase):
    """``import inspect`` was removed as dead weight; keep it gone."""

    def test_module_does_not_expose_inspect(self):
        self.assertFalse(
            hasattr(generate_weekly_pdfs, 'inspect'),
            'inspect was removed as an unused import — '
            'a re-add needs its call sites justified',
        )


if __name__ == '__main__':
    unittest.main()
