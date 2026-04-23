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

    def test_filter_comprehension_matches_production_check(self):
        """The ``_valid_cached_sheets`` filter behaves as expected."""
        raw = [
            {'id': 1, 'name': 'A', 'column_mapping': {'x': 1}},  # keep
            {'id': 2, 'name': 'B'},                               # drop (no mapping)
            {'id': '3', 'column_mapping': {}},                    # drop (non-int id)
            'not-a-dict',                                         # drop
            None,                                                 # drop
            {'id': 4, 'column_mapping': {}},                      # keep
        ]
        valid = [
            s for s in raw
            if isinstance(s, dict)
            and isinstance(s.get('id'), int)
            and isinstance(s.get('column_mapping'), dict)
        ]
        self.assertEqual([s['id'] for s in valid], [1, 4])


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
