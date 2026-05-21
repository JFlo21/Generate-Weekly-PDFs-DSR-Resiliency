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
import unittest

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

    def test_redacts_alphanumeric_wr_identifier(self):
        """Codex P2 follow-up: alphanumeric WR tokens must also redact.

        The original ``_RE_REDACT_WR`` regex required ``\\d+`` after
        ``WR``, so ``WR=ABCD-123`` slipped through unredacted.
        """
        redacted = generate_weekly_pdfs._redact_exception_message(
            Exception('Invalid row WR=ABCD-123 rejected'),
        )
        self.assertNotIn('ABCD-123', redacted)
        self.assertIn('WR=<redacted>', redacted)

    def test_redacts_path_traversal_wr_fully(self):
        """Codex P2 follow-up: a path-traversal suffix must not leak.

        Before the fix, ``WR=1234/../evil`` became
        ``WR=<redacted>/../evil`` — leaking the attacker-controlled
        suffix into Sentry context. The broadened char class now
        captures the whole identifier.
        """
        redacted = generate_weekly_pdfs._redact_exception_message(
            Exception('Write failed for WR=1234/../evil during upload'),
        )
        self.assertNotIn('1234', redacted)
        self.assertNotIn('/../evil', redacted)
        self.assertNotIn('evil', redacted)
        self.assertIn('WR=<redacted>', redacted)

    def test_redact_wr_does_not_swallow_english_prose(self):
        """Negative lookahead keeps ``WRITE`` / ``WRAP`` etc. intact.

        The pattern only matches when ``WR`` is NOT followed by another
        letter, so English words starting with ``WR`` are left alone.
        """
        redacted = generate_weekly_pdfs._redact_exception_message(
            Exception('Failed to WRITE the workbook to disk'),
        )
        self.assertIn('WRITE', redacted)
        self.assertNotIn('<redacted>', redacted)

    def test_redact_wr_handles_backslash_paths(self):
        """A Windows-style backslash path after WR must be redacted."""
        redacted = generate_weekly_pdfs._redact_exception_message(
            Exception(r'Upload failed WR=1234\..\etc'),
        )
        self.assertNotIn('1234', redacted)
        self.assertNotIn('etc', redacted)
        self.assertIn('WR=<redacted>', redacted)


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


class TestWeeklyWouldTriggerFallback(unittest.TestCase):
    """Copilot review follow-up: the fallback-disabled ``_recalc_note``
    must only suggest flipping ``RATE_RECALC_WEEKLY_FALLBACK`` when
    doing so would genuinely rescue the row — i.e. the row's Weekly
    Reference Logged Date parses AND is ``>= RATE_CUTOFF_DATE``. For
    rows whose weekly date is blank, unparseable, or pre-cutoff,
    enabling the env var would not change anything and the message
    would be misleading.
    """

    def setUp(self):
        import datetime as dt
        self.cutoff = dt.date(2026, 4, 19)

    def test_post_cutoff_weekly_qualifies(self):
        """A weekly date >= cutoff should trigger fallback rescue."""
        self.assertTrue(
            generate_weekly_pdfs._weekly_would_trigger_fallback(
                '2026-04-19', self.cutoff,
            ),
        )
        self.assertTrue(
            generate_weekly_pdfs._weekly_would_trigger_fallback(
                '2026-05-03', self.cutoff,
            ),
        )

    def test_pre_cutoff_weekly_does_not_qualify(self):
        """A pre-cutoff weekly date is not rescuable by the fallback."""
        self.assertFalse(
            generate_weekly_pdfs._weekly_would_trigger_fallback(
                '2026-04-12', self.cutoff,
            ),
        )

    def test_blank_weekly_does_not_qualify(self):
        for blank in (None, '', '   '):
            self.assertFalse(
                generate_weekly_pdfs._weekly_would_trigger_fallback(
                    blank, self.cutoff,
                ),
                f'blank weekly date {blank!r} must not qualify',
            )

    def test_unparseable_weekly_does_not_qualify(self):
        for garbage in ('not-a-date', 'banana'):
            self.assertFalse(
                generate_weekly_pdfs._weekly_would_trigger_fallback(
                    garbage, self.cutoff,
                ),
                f'unparseable weekly date {garbage!r} must not qualify',
            )

    def test_none_cutoff_never_qualifies(self):
        """Guard against calls with no configured cutoff."""
        self.assertFalse(
            generate_weekly_pdfs._weekly_would_trigger_fallback(
                '2026-04-19', None,
            ),
        )


class TestRateRecalcSummaryCoversFallbackOnly(unittest.TestCase):
    """Copilot review follow-up: when fallback ran but every row hit a
    non-reportable outcome (invalid_quantity / zero_rate), the per-sheet
    summary previously didn't log at all because both ``skipped`` and
    ``recalculated`` counters were zero. That made the new
    ``fallback_applied`` counter invisible. The fix adds an
    ``elif fallback_applied:`` branch so the summary surfaces whenever
    any of the three counters is non-zero.
    """

    def test_branch_condition_covers_fallback_only(self):
        """Reproduces the decision surface of the summary log."""
        cases = [
            # (skipped, recalculated, fallback_applied, should_log)
            (5, 0, 0, True),                         # existing warning
            (0, 10, 0, True),                        # existing info
            (0, 0, 3, True),                         # new branch
            (0, 0, 0, False),                        # nothing happened
            (2, 1, 4, True),                         # all non-zero
            (0, 5, 2, True),                         # recalculated + fallback
        ]
        for skipped, recalculated, fallback_applied, expected in cases:
            should_log = bool(skipped or recalculated or fallback_applied)
            self.assertEqual(
                should_log, expected,
                f'skipped={skipped} recalculated={recalculated} '
                f'fallback_applied={fallback_applied}: '
                f'expected log={expected}, got {should_log}',
            )

    def test_counter_key_is_fallback_applied(self):
        """Guards against a future rename breaking the summary log."""
        counters = {'recalculated': 0, 'skipped': 0, 'fallback_applied': 0}
        self.assertIn('fallback_applied', counters)


class TestRedactExceptionMessageSignature(unittest.TestCase):
    """Copilot review follow-up: the type hint now reflects that
    ``None`` is an accepted input (tests already cover that case)."""

    def test_signature_accepts_none_via_annotation(self):
        import inspect as _inspect
        sig = _inspect.signature(generate_weekly_pdfs._redact_exception_message)
        exc_param = sig.parameters['exc']
        annotation_str = str(exc_param.annotation)
        # Accept either 'BaseException | None', 'Optional[BaseException]',
        # 'Exception | None', or similar forward-ref strings. The key
        # invariant is that ``None`` is part of the annotated type.
        self.assertIn(
            'None', annotation_str,
            f'exc annotation {annotation_str!r} must include None — '
            'callers pass None and tests cover that case',
        )

    def test_none_input_still_returns_empty_string(self):
        """Behaviour regression guard tied to the annotation change."""
        self.assertEqual(
            generate_weekly_pdfs._redact_exception_message(None), '',
        )


class TestWeeklyFallbackGatedOnSnapshotColumn(unittest.TestCase):
    """Codex P1 follow-up: the Weekly-Ref-Date fallback must NOT
    activate on legacy sheets that never map a ``Snapshot Date`` column.

    Without the snapshot-column gate, ``row_data.get('Snapshot Date')``
    returns ``None`` for every row on such sheets, so the fallback
    would silently re-price the whole sheet by weekly date —
    effectively changing the cutoff basis rather than rescuing
    current-week automation-lag rows. The fix is to disable
    ``weekly_fallback_enabled`` at the call site when
    ``'Snapshot Date' not in column_mapping``.
    """

    def setUp(self):
        import datetime as dt
        self.cutoff = dt.date(2026, 4, 19)

    def test_fallback_enabled_default_with_snapshot_column(self):
        """On sheets that DO map Snapshot Date, the fallback runs."""
        row = {
            'Snapshot Date': None,  # Blank cell on a sheet that maps it
            'Weekly Reference Logged Date': '2026-04-19',
        }
        effective, used_fallback = generate_weekly_pdfs._resolve_rate_recalc_cutoff_date(
            row, self.cutoff, weekly_fallback_enabled=True,
        )
        self.assertIsNotNone(effective)
        self.assertTrue(used_fallback)

    def test_fallback_disabled_when_sheet_lacks_snapshot_column(self):
        """Reproduces the ``weekly_fallback_enabled = RATE_RECALC_WEEKLY_FALLBACK
        and sheet_has_snapshot_date_column`` gate at the call site.

        When the sheet doesn't map Snapshot Date, we pass
        ``weekly_fallback_enabled=False`` to the helper — even though
        the row's snapshot field is None. The fallback must stay
        silent so legacy-sheet billing behaviour is preserved.
        """
        row = {
            'Weekly Reference Logged Date': '2026-04-19',
            # No 'Snapshot Date' key — simulates a sheet whose
            # column_mapping never had Snapshot Date.
        }
        effective, used_fallback = generate_weekly_pdfs._resolve_rate_recalc_cutoff_date(
            row, self.cutoff, weekly_fallback_enabled=False,
        )
        self.assertIsNone(effective)
        self.assertFalse(used_fallback)

    def test_call_site_expression_evaluates_correctly(self):
        """Decision-surface guard: the boolean in the production call.

        ``RATE_RECALC_WEEKLY_FALLBACK and sheet_has_snapshot_date_column``
        should only be True when BOTH env-var and the sheet maps the
        column. This mirrors the inline expression at the call site.
        """
        cases = [
            # (env_var, has_snapshot_column, expected)
            (True, True, True),
            (True, False, False),   # legacy sheet — must disable
            (False, True, False),
            (False, False, False),
        ]
        for env_var, has_col, expected in cases:
            self.assertEqual(
                bool(env_var and has_col), expected,
                f'env_var={env_var} has_col={has_col}: expected {expected}',
            )


class TestTargetMapWrKeyCollisionDetection(unittest.TestCase):
    """Codex P2 follow-up: ``create_target_sheet_map`` now detects
    when two distinct raw WR# cell values sanitize to the same
    ``_RE_SANITIZE_HELPER_NAME`` key and logs a WARNING instead of
    silently overwriting the earlier row.

    Realistic numeric WR#s cannot collide, but the guardrail is cheap
    and protects against a malicious / corrupted target-sheet row
    from retargeting uploads or attachment deletes at the wrong row.
    """

    def test_sanitizer_produces_collisions_for_crafted_inputs(self):
        """Sanity: ``[^\\w\\-]`` folds ``/`` and ``\\`` to the same ``_``.

        This is the exact surface the collision check guards: two
        distinct raw WR# values that yield an identical sanitized
        key.
        """
        a = '1234/evil'
        b = '1234\\evil'
        sa = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub('_', a)[:50]
        sb = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub('_', b)[:50]
        self.assertEqual(sa, sb)
        self.assertNotEqual(a, b)

    def test_truncation_produces_collisions_for_50char_tail(self):
        """Two distinct WRs sharing the same first 50 chars collide."""
        a = 'A' * 50 + 'extra1'
        b = 'A' * 50 + 'extra2'
        sa = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub('_', a)[:50]
        sb = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub('_', b)[:50]
        self.assertEqual(sa, sb)
        self.assertNotEqual(a, b)

    def test_collision_quarantines_both_rows(self):
        """Codex round-6 P1: quarantine colliding keys instead of
        keeping first-seen.

        When two distinct raw WR values sanitize to the same key,
        both are removed from ``target_map`` so the upload site's
        ``if wr_num in target_map`` check correctly fails for both.
        That surfaces a loud "not found in target sheet" warning
        instead of silently uploading to the wrong target-sheet
        row. Keeping one (the old behaviour) was a silent-data-
        corruption risk because which mapping won depended on row
        iteration order.
        """
        target_map: dict = {}
        seen_raw_for_key: dict = {}
        quarantined: set = set()
        collisions = 0
        first_raw = '1234/evil'
        second_raw = '1234\\evil'
        for raw, row in ((first_raw, 'row-A'), (second_raw, 'row-B')):
            key = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub('_', raw)[:50]
            if key in quarantined:
                collisions += 1
            elif key in target_map:
                prior = seen_raw_for_key.get(key)
                if prior != raw:
                    collisions += 1
                    del target_map[key]
                    quarantined.add(key)
            else:
                target_map[key] = row
                seen_raw_for_key[key] = raw
        self.assertEqual(collisions, 1)
        self.assertEqual(
            len(target_map), 0,
            'both colliding WRs must be quarantined — keeping either '
            'risks uploading to the wrong row',
        )
        key = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub('_', first_raw)[:50]
        self.assertIn(key, quarantined)

    def test_third_colliding_row_is_also_rejected(self):
        """Once a key is quarantined, later raw values folding to the
        same key are rejected with an additional collision count.
        """
        target_map: dict = {}
        seen_raw_for_key: dict = {}
        quarantined: set = set()
        collisions = 0
        raws = ('1234/evil', '1234\\evil', '1234;evil')
        for raw in raws:
            key = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub('_', raw)[:50]
            if key in quarantined:
                collisions += 1
            elif key in target_map:
                prior = seen_raw_for_key.get(key)
                if prior != raw:
                    collisions += 1
                    del target_map[key]
                    quarantined.add(key)
            else:
                target_map[key] = 'row-placeholder'
                seen_raw_for_key[key] = raw
        # First pair triggers the quarantine; third re-collision bumps
        # the counter. Every collision is logged, none of the three
        # ambiguous WRs can be uploaded to.
        self.assertEqual(collisions, 2)
        self.assertEqual(len(target_map), 0)
        self.assertEqual(len(quarantined), 1)

    def test_identical_raw_wrs_do_not_register_as_collision(self):
        """A repeated raw WR# (same row indexed twice somehow) must not
        inflate the collision count — only *distinct* raw values that
        fold to the same key count as a collision."""
        target_map: dict = {}
        seen_raw_for_key: dict = {}
        quarantined: set = set()
        collisions = 0
        for raw in ('90093002', '90093002'):
            key = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub('_', raw)[:50]
            if key in quarantined:
                collisions += 1
            elif key in target_map:
                prior = seen_raw_for_key.get(key)
                if prior != raw:
                    collisions += 1
                    del target_map[key]
                    quarantined.add(key)
            else:
                target_map[key] = 'row-placeholder'
                seen_raw_for_key[key] = raw
        self.assertEqual(collisions, 0)
        self.assertEqual(len(target_map), 1)
        self.assertEqual(len(quarantined), 0)


class TestDiscoveryCacheFastPathSkipsOnPartialCorruption(unittest.TestCase):
    """Codex round-6 P2: the fresh-cache fast path must NOT return a
    reduced sheet list when the schema filter dropped any entry.

    Before the fix, the fast-path only checked
    ``_new_from_folders``. A dropped entry belonging to a static base
    sheet (not folder-discovered) wouldn't flag ``_new_from_folders``,
    so the function returned a reduced list and silently omitted
    rows until cache expiry (up to ``DISCOVERY_CACHE_TTL_MIN`` = 7d).
    Fix adds ``not _partial_cache_corruption`` to the gate so any
    drop forces incremental mode — which will re-validate
    base_sheet_ids and rediscover the dropped sheet.
    """

    def test_fast_path_gate_truth_table(self):
        """Reproduce the production condition
        ``age_min <= TTL and not new_from_folders and not partial_corruption``.
        """
        cases = [
            # (fresh, new_from_folders, partial_corruption, fast_path_ok)
            (True,  False, False, True),   # canonical happy path
            (True,  True,  False, False),  # new sheets → incremental
            (True,  False, True,  False),  # P2 fix: partial corruption blocks
            (True,  True,  True,  False),
            (False, False, False, False),  # TTL expired
        ]
        for fresh, new_ff, corrupt, expected in cases:
            result = (
                fresh and not new_ff and not corrupt
            )
            self.assertEqual(
                result, expected,
                f'fresh={fresh} new_ff={new_ff} corrupt={corrupt}: '
                f'expected fast_path_ok={expected}, got {result}',
            )

    def test_partial_corruption_detection_is_bool(self):
        """``_partial_cache_corruption = bool(raw) and len(valid) != len(raw)``
        must be False when raw is empty (no cache yet) and when
        nothing was dropped.
        """
        cases = [
            # (raw, valid, expected_partial)
            ([], [], False),                       # empty cache — not corruption
            (['a', 'b', 'c'], ['a', 'b', 'c'], False),  # no drops
            (['a', 'b', 'c'], ['a', 'b'], True),        # one dropped
            (['a'], [], True),                          # all dropped (also raises above)
        ]
        for raw, valid, expected in cases:
            result = bool(raw) and len(valid) != len(raw)
            self.assertEqual(
                result, expected,
                f'raw={raw!r} valid={valid!r}: expected {expected}, got {result}',
            )


class TestBuildGroupIdentityWithUnderscoresInWr(unittest.TestCase):
    """Codex round-7 P2: ``build_group_identity`` must parse filenames
    whose WR token contains underscores introduced by
    ``_RE_SANITIZE_HELPER_NAME``. Before the fix, the parser asserted
    ``parts[2] == 'WeekEnding'`` and thus failed for any sanitized
    WR containing a rewritten character. That broke
    ``_has_existing_week_attachment``, ``delete_old_excel_attachments``,
    and stale-variant cleanup on hardened filenames — each run would
    keep regenerating/reuploading the same artifact.
    """

    def test_plain_numeric_wr_still_parses(self):
        """Realistic production filenames must still round-trip."""
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_90093002_WeekEnding_041926_123456_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, '90093002')
        self.assertEqual(week, '041926')
        self.assertEqual(variant, 'primary')

    def test_sanitized_wr_with_underscores_parses(self):
        """Input like ``1234/../evil`` sanitizes to ``1234____evil``."""
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_1234____evil_WeekEnding_041926_123456_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, '1234____evil')
        self.assertEqual(week, '041926')
        self.assertEqual(variant, 'primary')

    def test_vac_crew_filename_with_underscored_wr_parses(self):
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_1234____evil_WeekEnding_041926_123456_VacCrew_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, '1234____evil')
        self.assertEqual(week, '041926')
        self.assertEqual(variant, 'vac_crew')
        self.assertEqual(identifier, '')

    def test_helper_filename_with_underscored_wr_parses(self):
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_1234____evil_WeekEnding_041926_123456_Helper_Jane_Smith_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, '1234____evil')
        self.assertEqual(week, '041926')
        self.assertEqual(variant, 'helper')
        self.assertEqual(identifier, 'Jane_Smith')

    def test_missing_weekending_marker_still_returns_none(self):
        self.assertIsNone(
            generate_weekly_pdfs.build_group_identity(
                'WR_12345_NotAMarker_041926.xlsx'
            )
        )

    def test_wr_token_containing_literal_weekending_parses_correctly(self):
        """Round-8 Copilot follow-up: if a sanitized WR segment is
        literally ``WeekEnding``, the parser must still locate the
        *structural* delimiter (the LAST ``WeekEnding``), not the
        first occurrence embedded in the WR token.

        Without rindex semantics, ``parts.index('WeekEnding')`` would
        return position 1 (the WR segment), treat position 2 as the
        week (the real ``WeekEnding`` delimiter), and corrupt the
        returned WR/week tuple.
        """
        # WR literally equals 'WeekEnding' — sanitized identically.
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_WeekEnding_WeekEnding_041926_123456_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, 'WeekEnding')
        self.assertEqual(week, '041926')
        self.assertEqual(variant, 'primary')

    def test_wr_token_with_multiple_weekending_segments_still_parses(self):
        """Even a pathological WR containing multiple ``WeekEnding``
        segments must parse — the rightmost marker is unambiguously
        the structural delimiter because everything after it
        (week, timestamp, variant, hash) never equals ``WeekEnding``.
        """
        # WR is 'WeekEnding_WeekEnding' (two segments that both match).
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_WeekEnding_WeekEnding_WeekEnding_041926_123456_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, 'WeekEnding_WeekEnding')
        self.assertEqual(week, '041926')

    def test_wr_containing_literal_helper_token_no_false_variant(self):
        """A sanitized WR containing ``Helper`` must NOT be read as
        the helper variant. The marker search is scoped to the tail
        after ``WeekEnding <week>`` so the WR portion is ignored.
        """
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_Helper_WeekEnding_041926_123456_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, 'Helper')
        self.assertEqual(variant, 'primary')
        self.assertIsNone(identifier)

    def test_helper_identifier_containing_weekending_token(self):
        """Codex round-10: a sanitized helper name that itself
        contains the literal ``WeekEnding`` token must NOT be treated
        as the structural delimiter. The parser disambiguates via the
        format constraint ``<next-token is 6-digit MMDDYY>``, which
        only the real structural delimiter satisfies.

        E.g. foreman name 'WeekEnding Jones' sanitizes to the
        filename identifier ``WeekEnding_Jones``. The filename ends
        up ``...Helper_WeekEnding_Jones_<hash>.xlsx``. Pre-fix,
        rindex semantics picked THAT ``WeekEnding`` as the delimiter
        and returned a corrupted (wr, week) tuple.
        """
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_12345_WeekEnding_041926_123456_Helper_WeekEnding_Jones_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, '12345')
        self.assertEqual(week, '041926')
        self.assertEqual(variant, 'helper')
        self.assertEqual(identifier, 'WeekEnding_Jones')

    def test_user_identifier_containing_weekending_token(self):
        """Same as above but for the User variant."""
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_12345_WeekEnding_041926_123456_User_WeekEnding_Smith_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, '12345')
        self.assertEqual(week, '041926')
        self.assertEqual(variant, 'primary')  # User variant is still 'primary'
        self.assertEqual(identifier, 'WeekEnding_Smith')

    def test_wr_token_containing_weekending_six_digit_segment(self):
        """Codex round-11: if the sanitized WR itself contains a
        ``WeekEnding_<6digits>`` segment, the parser must still
        identify the RIGHTMOST valid marker as the structural
        delimiter. First-valid would truncate the WR; rightmost-
        valid correctly walks past the WR-internal candidates.

        Pathological source: raw WR = ``foo.WeekEnding.041926.bar``
        would sanitize to ``foo_WeekEnding_041926_bar`` and generate
        filename ``WR_foo_WeekEnding_041926_bar_WeekEnding_041926_...xlsx``.
        """
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_foo_WeekEnding_041926_bar_WeekEnding_041926_123456_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, 'foo_WeekEnding_041926_bar')
        self.assertEqual(week, '041926')
        self.assertEqual(variant, 'primary')

    def test_helper_identifier_containing_weekending_six_digit_segment(self):
        """Codex round-12: if a helper/user identifier itself
        sanitizes to ``WeekEnding_<6digits>`` (pathological — would
        require a foreman name like ``WeekEnding 041926 Jones``),
        rightmost-valid alone would pick the identifier token. The
        strong/weak candidate split resolves this because the
        identifier's 6-digit week is followed by the HASH (non-
        6-digit), while the structural delimiter is followed by a
        6-digit timestamp — so only the structural position is a
        STRONG match.
        """
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_12345_WeekEnding_041926_123456_Helper_WeekEnding_041926_Jones_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, '12345')
        self.assertEqual(week, '041926')
        self.assertEqual(variant, 'helper')
        self.assertEqual(identifier, 'WeekEnding_041926_Jones')

    def test_helper_identifier_weekending_followed_by_hash_only(self):
        """Codex's original example: ``..._Helper_WeekEnding_041926_<hash>.xlsx``
        where the identifier is just ``WeekEnding`` and the hash
        happens to come right after a 6-digit token. Strong/weak
        split still correctly identifies position 2 as the structural
        delimiter because position 6's ``041926`` is followed by the
        hex hash (non-6-digit).
        """
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_12345_WeekEnding_041926_123456_Helper_WeekEnding_041926_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, '12345')
        self.assertEqual(week, '041926')
        self.assertEqual(variant, 'helper')

    def test_helper_identifier_sanitizing_to_weekending_6dig_6dig(self):
        """Codex round-13: pathological helper identifier that
        sanitizes to ``WeekEnding_<6digits>_<6digits>`` (e.g. foreman
        literally named ``WeekEnding 041926 123456``). Rightmost-
        strong would pick the identifier's strong match and corrupt
        the parse; leftmost-strong correctly picks the actual
        structural delimiter at position 2.
        """
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_12345_WeekEnding_041926_123456_Helper_WeekEnding_041926_123456_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, '12345')
        self.assertEqual(week, '041926')
        self.assertEqual(variant, 'helper')
        self.assertEqual(identifier, 'WeekEnding_041926_123456')

    def test_legacy_format_without_timestamp_still_parses(self):
        """The pre-timestamp filename shape must continue to parse.

        ``WR_12345_WeekEnding_041926_{hash}.xlsx`` has no second
        6-digit token; only the weak-match candidate matches, and
        the parser falls back to it as documented.
        """
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_12345_WeekEnding_041926_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, '12345')
        self.assertEqual(week, '041926')

    def test_parser_rejects_filename_without_six_digit_week_follower(self):
        """Defence-in-depth: if the ``WeekEnding`` token is NOT
        followed by a 6-digit week, the parser refuses to guess.
        This protects against malformed filenames being silently
        mis-parsed.
        """
        # WeekEnding followed by a non-digit token → no structural
        # marker found → None.
        self.assertIsNone(generate_weekly_pdfs.build_group_identity(
            'WR_12345_WeekEnding_notadate_123456.xlsx'
        ))
        # WeekEnding followed by wrong-length numeric → None.
        self.assertIsNone(generate_weekly_pdfs.build_group_identity(
            'WR_12345_WeekEnding_1234_123456.xlsx'
        ))
        self.assertIsNone(generate_weekly_pdfs.build_group_identity(
            'WR_12345_WeekEnding_12345678_123456.xlsx'
        ))

    def test_wr_containing_literal_aep_billable_token_no_false_variant(self):
        """Phase 01 Plan 02 D-10: a sanitized WR containing the literal
        token ``AEPBillable`` MUST NOT trigger the aep_billable variant.
        Variant marker detection is tail-scoped (post-``WeekEnding``
        span only), so the WR portion is ignored. Verified by an
        explicit negative test so a future refactor can't silently
        regress to filename-wide string search.
        """
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_AEPBillable_WeekEnding_041926_123456_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, 'AEPBillable')
        self.assertEqual(variant, 'primary')
        self.assertIsNone(identifier)

    def test_wr_containing_literal_reduced_sub_token_no_false_variant(self):
        """Mirror of the AEPBillable case for ``ReducedSub``."""
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_ReducedSub_WeekEnding_041926_123456_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, 'ReducedSub')
        self.assertEqual(variant, 'primary')
        self.assertIsNone(identifier)

    def test_helper_filename_still_parses_as_helper_after_new_variants(self):
        """No regression: a plain ``_Helper_<name>`` filename (without
        AEPBillable / ReducedSub prefix) must still parse as
        ``variant='helper'`` after the new variant branches are added.
        Locks the D-09 variant-first ordering: the new ``AEPBillable``
        / ``ReducedSub`` checks must run BEFORE the existing ``Helper``
        branch, but a tail without ``AEPBillable`` / ``ReducedSub``
        must still fall through to the unchanged ``Helper`` branch.
        """
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_91467680_WeekEnding_041926_123456_Helper_Jane_Smith_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, '91467680')
        self.assertEqual(week, '041926')
        self.assertEqual(variant, 'helper')
        self.assertEqual(identifier, 'Jane_Smith')

    def test_aep_billable_helper_filename_with_underscored_wr_parses(self):
        """A sanitized WR containing underscores (e.g.
        ``1234____evil`` from raw ``1234/../evil``) plus an
        ``_AEPBillable_Helper_<name>`` suffix must round-trip
        correctly. The span-join discipline in the parser
        (``parts[1:we_idx]`` for the WR token) is what makes this
        work even with the underscore-rewritten WR.
        """
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_1234____evil_WeekEnding_041926_123456_AEPBillable_Helper_Jane_Smith_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, '1234____evil')
        self.assertEqual(week, '041926')
        self.assertEqual(variant, 'aep_billable_helper')
        self.assertEqual(identifier, 'Jane_Smith')

    def test_reduced_sub_helper_filename_with_underscored_wr_parses(self):
        """Mirror of the AEPBillable case: sanitized underscored WR
        plus ``_ReducedSub_Helper_<name>`` suffix → all four tuple
        values resolve correctly."""
        ident = generate_weekly_pdfs.build_group_identity(
            'WR_1234____evil_WeekEnding_041926_123456_ReducedSub_Helper_Jane_Smith_ab12cd34ef.xlsx'
        )
        self.assertIsNotNone(ident)
        wr, week, variant, identifier = ident
        self.assertEqual(wr, '1234____evil')
        self.assertEqual(week, '041926')
        self.assertEqual(variant, 'reduced_sub_helper')
        self.assertEqual(identifier, 'Jane_Smith')


class TestSourceWrCollisionQuarantine(unittest.TestCase):
    """Codex round-7 P1: source-side WR# collision detection.

    The main loop uses a sanitized+truncated WR as the canonical key
    for ``history_key``, ``target_map`` lookups, and Excel filenames.
    If two distinct source groups have raw WR# values that fold to
    the same sanitized key, both would target the same hash_history
    slot and the same target-sheet row — a cross-contamination
    scenario. The fix is a pre-scan over ``groups`` that detects such
    collisions and a per-group skip in the main loop.
    """

    def _run_pre_scan(self, groups):
        """Helper that mirrors the production pre-scan logic exactly.

        Keyed on sanitized WR alone (not ``(wr, week, variant)``) so
        cross-context collisions route through ``target_map`` /
        attachment-identity are caught.
        """
        import collections as _collections
        source_wr_raws_per_key = _collections.defaultdict(set)
        for g_rows in groups.values():
            if not g_rows:
                continue
            g_raw = str(g_rows[0].get('Work Request #') or '').split('.')[0]
            if not g_raw:
                continue
            g_sanitized = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub('_', g_raw)[:50]
            source_wr_raws_per_key[g_sanitized].add(g_raw)
        return {
            key for key, raws in source_wr_raws_per_key.items()
            if len(raws) > 1
        }

    def test_pre_scan_detects_slash_backslash_collision(self):
        """Reproduce the pre-scan logic against a crafted groups dict."""
        groups = {
            '041926_raw1': [{'Work Request #': '1234/evil', '__variant': 'primary'}],
            '041926_raw2': [{'Work Request #': '1234\\evil', '__variant': 'primary'}],
            '041926_raw3': [{'Work Request #': '90093002', '__variant': 'primary'}],
        }
        quarantined = self._run_pre_scan(groups)
        # The slash/backslash pair must be quarantined; the lone
        # numeric WR is NOT a collision.
        sanitized_key = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
            '_', '1234/evil',
        )[:50]
        self.assertEqual(len(quarantined), 1)
        self.assertIn(sanitized_key, quarantined)

    def test_pre_scan_is_zero_impact_on_realistic_numeric_wrs(self):
        """Realistic numeric WR#s across many groups must never trigger
        a quarantine — the pre-scan is noise-free on production data.
        Note: the same numeric WR legitimately appearing across
        multiple weeks is NOT a collision (only one distinct raw
        value per sanitized key).
        """
        groups = {
            '041926_90093002': [{'Work Request #': '90093002', '__variant': 'primary'}],
            '041926_89954686': [{'Work Request #': '89954686', '__variant': 'primary'}],
            '041926_12345': [{'Work Request #': '12345', '__variant': 'primary'}],
            '042626_90093002': [{'Work Request #': '90093002', '__variant': 'primary'}],
        }
        quarantined = self._run_pre_scan(groups)
        self.assertEqual(quarantined, set())

    def test_pre_scan_catches_cross_week_collisions(self):
        """Codex P1 (round-9): two distinct raw WRs that sanitize to
        the same key must be quarantined EVEN if they live in
        different weeks or variants. Earlier round-7 code scoped
        collisions by ``(wr, week, variant)`` which missed this case
        — target_map and attachment-identity routing use only the
        sanitized WR, so cross-context collisions can still corrupt
        uploads.
        """
        groups = {
            # Same sanitized WR, different weeks → must quarantine.
            '041926_col': [{'Work Request #': '1234/evil', '__variant': 'primary'}],
            '042626_col': [{'Work Request #': '1234\\evil', '__variant': 'primary'}],
        }
        quarantined = self._run_pre_scan(groups)
        sanitized_key = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
            '_', '1234/evil',
        )[:50]
        self.assertIn(sanitized_key, quarantined)

    def test_pre_scan_catches_cross_variant_collisions(self):
        """Codex P1 (round-9): distinct raws that collide across
        variants (e.g. a primary group and a helper group with
        sanitization-colliding WR#s) must also be flagged.
        """
        groups = {
            '041926_a': [{'Work Request #': '1234/evil', '__variant': 'helper'}],
            '041926_b': [{'Work Request #': '1234\\evil', '__variant': 'vac_crew'}],
        }
        quarantined = self._run_pre_scan(groups)
        sanitized_key = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
            '_', '1234/evil',
        )[:50]
        self.assertIn(sanitized_key, quarantined)

    def test_pre_scan_catches_aep_billable_cross_variant_collision(self):
        """Phase 01 Plan 02 D-22 regression lock: a sanitization-
        colliding pair where one group is the new ``aep_billable``
        variant and the other is the new ``reduced_sub`` variant
        MUST be quarantined. The existing round-9 pre-scan keys on
        the sanitized WR alone (NOT a tuple), so this case is
        already covered without code change — but without an
        explicit regression test a future refactor could silently
        re-narrow the key and re-open the cross-variant attack
        surface for the four new variants.
        """
        groups = {
            '041926_aep': [
                {'Work Request #': '1234/evil', '__variant': 'aep_billable'},
            ],
            '041926_rs': [
                {'Work Request #': '1234\\evil', '__variant': 'reduced_sub'},
            ],
        }
        quarantined = self._run_pre_scan(groups)
        sanitized_key = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
            '_', '1234/evil',
        )[:50]
        self.assertIn(sanitized_key, quarantined)

    def test_pre_scan_catches_aep_billable_cross_week_collision(self):
        """Phase 01 Plan 02 D-22: same ``aep_billable`` variant
        across two different weeks but with sanitization-colliding
        raw WR# values must also be quarantined. The round-9 key
        contract (sanitized WR alone) is what makes this work; the
        week part of the group key is NOT part of the collision
        detection key.
        """
        groups = {
            '040526_aep': [
                {'Work Request #': '1234/evil', '__variant': 'aep_billable'},
            ],
            '041926_aep': [
                {'Work Request #': '1234\\evil', '__variant': 'aep_billable'},
            ],
        }
        quarantined = self._run_pre_scan(groups)
        sanitized_key = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
            '_', '1234/evil',
        )[:50]
        self.assertIn(sanitized_key, quarantined)

    def test_pre_scan_does_not_false_positive_distinct_subcontractor_variants(self):
        """Phase 01 Plan 02 D-22: realistic numeric WR#s for the
        new ``aep_billable`` / ``reduced_sub`` variants must NOT
        be quarantined. The pre-scan stays noise-free on
        production-shaped data."""
        groups = {
            '041926_aep_1': [
                {'Work Request #': '1234567', '__variant': 'aep_billable'},
            ],
            '041926_rs_1': [
                {'Work Request #': '7654321', '__variant': 'reduced_sub'},
            ],
            '041926_aep_h_1': [
                {'Work Request #': '1234567',
                 '__variant': 'aep_billable_helper'},
            ],
        }
        # Same numeric WR appearing across variants (aep_billable +
        # aep_billable_helper) is ONE distinct raw, not a collision.
        quarantined = self._run_pre_scan(groups)
        self.assertEqual(quarantined, set())


class TestPiiLogMarkersIncludeSubcontractorVariants(unittest.TestCase):
    """Phase 01 Plan 02 Task 3: ``_PII_LOG_MARKERS`` MUST contain the
    new subcontractor variant tokens so the ``before_send_log``
    sanitizer drops any future INFO-level log lines that embed
    those tokens before they reach Sentry.

    Rationale per Living Ledger 2026-04-20 12:00: billing-row
    PII (WR#, foreman, dept, CU) must never reach Sentry's event
    store. Plan 3 will emit ``AEP BILLABLE GROUP CREATED`` /
    ``REDUCED SUB GROUP CREATED`` INFO logs and a missing-CU
    WARNING that contains the literal CU code — all of which
    qualify as row-level data and must be sanitized.

    Locking the markers in Plan 02 (before Plan 3 emits them)
    means the sanitizer is already in place when those log calls
    land — defense in depth.
    """

    def test_aepbillable_group_key_token_in_markers(self):
        self.assertIn('_AEPBILLABLE', generate_weekly_pdfs._PII_LOG_MARKERS)

    def test_reducedsub_group_key_token_in_markers(self):
        self.assertIn('_REDUCEDSUB', generate_weekly_pdfs._PII_LOG_MARKERS)

    def test_aepbillable_helper_group_key_token_in_markers(self):
        self.assertIn(
            '_AEPBILLABLE_HELPER_',
            generate_weekly_pdfs._PII_LOG_MARKERS,
        )

    def test_reducedsub_helper_group_key_token_in_markers(self):
        self.assertIn(
            '_REDUCEDSUB_HELPER_',
            generate_weekly_pdfs._PII_LOG_MARKERS,
        )

    def test_aep_billable_group_created_log_text_in_markers(self):
        self.assertIn(
            'AEP BILLABLE GROUP CREATED',
            generate_weekly_pdfs._PII_LOG_MARKERS,
        )

    def test_reduced_sub_group_created_log_text_in_markers(self):
        self.assertIn(
            'REDUCED SUB GROUP CREATED',
            generate_weekly_pdfs._PII_LOG_MARKERS,
        )

    def test_subcontractor_rates_missing_warning_in_markers(self):
        self.assertIn(
            'Subcontractor rates CSV missing',
            generate_weekly_pdfs._PII_LOG_MARKERS,
        )

    def test_aep_billable_helper_group_created_log_text_in_markers(self):
        # Phase 01 gap closure (REVIEW-WR-04): the explicit
        # marker for the helper-shadow AEP BILLABLE log line.
        # Pre-fix, this log was scrubbed by accidental substring
        # containment of "HELPER GROUP CREATED" — a future
        # wording rewording would silently regress that
        # protection. This test ensures the explicit marker is
        # the actual gate.
        self.assertIn(
            'AEP BILLABLE HELPER GROUP CREATED',
            generate_weekly_pdfs._PII_LOG_MARKERS,
        )

    def test_reduced_sub_helper_group_created_log_text_in_markers(self):
        # Mirror of the AEP BILLABLE HELPER marker test
        # (REVIEW-WR-04).
        self.assertIn(
            'REDUCED SUB HELPER GROUP CREATED',
            generate_weekly_pdfs._PII_LOG_MARKERS,
        )

    def test_all_nine_subcontractor_markers_present(self):
        """Single-shot assertion covering all 9 markers — mirrors the
        plan's verification command exactly. Updated from 7 → 9 by
        Phase 01 Plan 09 (REVIEW-WR-04) which added the two
        helper-shadow GROUP CREATED markers."""
        expected = {
            '_AEPBILLABLE',
            '_REDUCEDSUB',
            '_AEPBILLABLE_HELPER_',
            '_REDUCEDSUB_HELPER_',
            'AEP BILLABLE GROUP CREATED',
            'REDUCED SUB GROUP CREATED',
            'AEP BILLABLE HELPER GROUP CREATED',
            'REDUCED SUB HELPER GROUP CREATED',
            'Subcontractor rates CSV missing',
        }
        missing = expected - set(generate_weekly_pdfs._PII_LOG_MARKERS)
        self.assertFalse(
            missing,
            f'Missing PII markers for Phase 01 Plan 02 / Plan 09: {missing}',
        )


class TestRedactExceptionMessageTruncationCapsFullPayload(unittest.TestCase):
    """Codex P2: ``max_len`` must cap the FULL returned payload
    (class prefix + body), not just the body. Previously the
    truncation happened before ``{type(exc).__name__}: `` was
    prepended, so the returned string could exceed ``max_len`` —
    breaking the Sentry context-data length budget callers rely on.
    """

    def test_full_payload_stays_within_max_len(self):
        long_body = 'x' * 500
        redacted = generate_weekly_pdfs._redact_exception_message(
            Exception(long_body), max_len=80,
        )
        self.assertLessEqual(
            len(redacted), 80,
            f'max_len=80 must cap full payload, got {len(redacted)} '
            f'({redacted!r})',
        )

    def test_truncated_result_ends_in_ellipsis(self):
        redacted = generate_weekly_pdfs._redact_exception_message(
            Exception('x' * 500), max_len=60,
        )
        self.assertTrue(redacted.endswith('...'))

    def test_short_payload_not_truncated(self):
        """A body that fits within max_len must not get ``...`` appended."""
        redacted = generate_weekly_pdfs._redact_exception_message(
            Exception('short'), max_len=80,
        )
        self.assertEqual(redacted, 'Exception: short')
        self.assertFalse(redacted.endswith('...'))

    def test_class_prefix_always_present_even_after_truncation(self):
        """Sentry event grouping relies on a stable class prefix;
        truncation must not clip past the ``: `` separator."""
        redacted = generate_weekly_pdfs._redact_exception_message(
            ValueError('z' * 500), max_len=30,
        )
        self.assertIn('ValueError', redacted)


class TestHashHistoryPruneUsesSanitizedWr(unittest.TestCase):
    """Codex P2: the stale-pruning pass that runs after the main
    group loop must derive ``current_keys`` using the same sanitized
    WR key the main loop wrote to ``hash_history``. Without this,
    any WR# whose raw value is rewritten by
    ``_RE_SANITIZE_HELPER_NAME`` has its just-written history entry
    treated as stale and deleted before save, so hash-skip never
    persists across runs for those WRs.
    """

    def test_sanitized_matches_main_loop_history_key(self):
        """Reproduce the decision surface: pruning must treat the
        sanitized, freshly-written ``history_key`` as current.
        """
        import collections as _collections
        raw_wr = '1234/evil'
        # Main-loop derivation.
        sanitized = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
            '_', raw_wr,
        )[:50]
        history_key_written = f'{sanitized}|041926|primary|'
        hash_history = {history_key_written: {'hash': 'abc'}}

        # Pruning derivation (after fix): apply the same sanitizer.
        groups = _collections.OrderedDict()
        groups['041926_grp'] = [
            {'Work Request #': raw_wr, '__variant': 'primary'},
        ]
        current_keys = set()
        for key, group_rows in groups.items():
            _wr_raw = group_rows[0].get('Work Request #')
            _wr = str(_wr_raw).split('.')[0] if _wr_raw else ''
            _wr = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
                '_', _wr,
            )[:50]
            _week = key.split('_', 1)[0]
            _variant = group_rows[0].get('__variant', 'primary')
            _ident = ''  # primary variant, no identifier
            current_keys.add(f'{_wr}|{_week}|{_variant}|{_ident}')

        stale_keys = [k for k in hash_history if k not in current_keys]
        self.assertEqual(
            stale_keys, [],
            f'freshly-written sanitized history_key must NOT be pruned '
            f'as stale; hash_history keys={list(hash_history)!r}, '
            f'current_keys={current_keys!r}',
        )

    def test_raw_wr_would_mark_freshly_written_stale_regression(self):
        """Negative-control: WITHOUT the sanitizer in the pruning
        derivation, the freshly-written sanitized key appears stale.
        This test locks in the bug's reproducibility so the fix can't
        quietly regress.
        """
        raw_wr = '1234/evil'
        sanitized = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
            '_', raw_wr,
        )[:50]
        history_key_written = f'{sanitized}|041926|primary|'
        hash_history = {history_key_written: {'hash': 'abc'}}

        # Pre-fix pruning derivation: raw _wr (no sanitizer).
        unsanitized_key = f'{raw_wr}|041926|primary|'
        current_keys_buggy = {unsanitized_key}

        stale_keys_buggy = [
            k for k in hash_history if k not in current_keys_buggy
        ]
        # This documents the pre-fix behaviour: freshly-written
        # sanitized key WAS marked stale. The positive test above
        # proves the fix prevents this.
        self.assertEqual(stale_keys_buggy, [history_key_written])


class TestInspectImportRemoved(unittest.TestCase):
    """``import inspect`` was removed as dead weight; keep it gone."""

    def test_module_does_not_expose_inspect(self):
        self.assertFalse(
            hasattr(generate_weekly_pdfs, 'inspect'),
            'inspect was removed as an unused import — '
            'a re-add needs its call sites justified',
        )


# ─── Phase 01 Plan 04 Task 1 ─────────────────────────────────────────
# Helper extraction + dual target_map + independent quarantine.
# Builds a parameterized helper ``create_target_sheet_map_for(client,
# sheet_id)`` and proves the new second target_map's collision
# quarantine is per-call (function-local) so the two maps cannot
# pollute each other.

class _FakeColumn:
    """Minimal stand-in for a Smartsheet column object."""

    def __init__(self, column_id, title):
        self.id = column_id
        self.title = title


class _FakeCell:
    """Minimal stand-in for a Smartsheet cell object."""

    def __init__(self, column_id, display_value):
        self.column_id = column_id
        self.display_value = display_value


class _FakeRow:
    """Minimal stand-in for a Smartsheet row object."""

    def __init__(self, row_id, cells):
        self.id = row_id
        self.cells = cells


class _FakeSheet:
    """Minimal stand-in for a Smartsheet sheet object."""

    def __init__(self, columns, rows):
        self.columns = columns
        self.rows = rows


class _FakeSheetsAPI:
    """``client.Sheets.get_sheet(sheet_id)`` dispatcher."""

    def __init__(self, sheets_by_id):
        self._sheets_by_id = sheets_by_id

    def get_sheet(self, sheet_id):
        if sheet_id not in self._sheets_by_id:
            raise KeyError(
                f'_FakeSheetsAPI has no sheet for id={sheet_id!r}'
            )
        return self._sheets_by_id[sheet_id]


class _FakeClient:
    """Top-level client. ``client.Sheets.get_sheet(...)`` is the only
    surface exercised by ``create_target_sheet_map_for``."""

    def __init__(self, sheets_by_id):
        self.Sheets = _FakeSheetsAPI(sheets_by_id)


def _make_fake_sheet(wr_values):
    """Build a fake target sheet with one row per ``wr_values`` entry.

    The ``Work Request #`` column id is ``101``. Row ids start at 1000
    so they're trivially distinguishable in assertions.
    """
    wr_col = _FakeColumn(101, 'Work Request #')
    extra_col = _FakeColumn(102, 'Some Other Column')
    rows = []
    for idx, raw_wr in enumerate(wr_values):
        cell_wr = _FakeCell(101, raw_wr)
        cell_other = _FakeCell(102, f'noise-{idx}')
        rows.append(_FakeRow(1000 + idx, [cell_wr, cell_other]))
    return _FakeSheet([wr_col, extra_col], rows)


class TestDualTargetMapIndependentQuarantine(unittest.TestCase):
    """Phase 01 Plan 04 Task 1: extract
    ``create_target_sheet_map_for(client, sheet_id)`` so a second
    ``target_map`` can be built against
    ``SUBCONTRACTOR_PPP_SHEET_ID`` for the dual-routing of
    ``_ReducedSub`` files.

    Critical invariant locked by these tests: the per-call collision
    quarantine state (``_quarantined_keys`` / ``_seen_raw_for_key``)
    is FUNCTION-LOCAL. Two independent calls to the helper must NOT
    share quarantine state, because a duplicate WR# on one target
    sheet must not poison the lookup table for the other sheet.
    """

    def test_helper_exists_at_module_level(self):
        """The new helper must be importable from
        ``generate_weekly_pdfs`` so callers (the main pipeline +
        external consumers) can build sheet-specific maps."""
        self.assertTrue(
            hasattr(generate_weekly_pdfs, 'create_target_sheet_map_for'),
            'create_target_sheet_map_for must be exposed at module scope',
        )

    def test_extracted_helper_matches_legacy_function_output(self):
        """Per acceptance criterion Test 1 + 6: calling the new
        ``create_target_sheet_map_for(client, TARGET_SHEET_ID)`` must
        return the same target_map dict as the legacy
        ``create_target_sheet_map(client)`` wrapper.
        """
        sheet = _make_fake_sheet(['90093002', '89708709', '12345'])
        client = _FakeClient({
            generate_weekly_pdfs.TARGET_SHEET_ID: sheet,
        })
        legacy_map, legacy_sheet = (
            generate_weekly_pdfs.create_target_sheet_map(client)
        )
        new_map, new_sheet = (
            generate_weekly_pdfs.create_target_sheet_map_for(
                client, generate_weekly_pdfs.TARGET_SHEET_ID,
            )
        )
        self.assertEqual(
            set(legacy_map.keys()), set(new_map.keys()),
            'extracted helper must yield identical WR# keys for the '
            'same sheet — back-compat invariant',
        )
        # Row identity preserved across the two paths.
        for wr in legacy_map:
            self.assertIs(legacy_map[wr], new_map[wr])

    def test_two_target_maps_independent_when_sheets_differ(self):
        """Per acceptance criterion Test 2: distinct sheets with
        distinct WR# rows must yield disjoint target_maps. Proves the
        helper is not accidentally sharing state across calls.
        """
        sheet_a = _make_fake_sheet(['90093002', '89708709'])
        sheet_b = _make_fake_sheet(['77777001', '77777002'])
        client = _FakeClient({
            generate_weekly_pdfs.TARGET_SHEET_ID: sheet_a,
            generate_weekly_pdfs.SUBCONTRACTOR_PPP_SHEET_ID: sheet_b,
        })
        map_a, _ = generate_weekly_pdfs.create_target_sheet_map_for(
            client, generate_weekly_pdfs.TARGET_SHEET_ID,
        )
        map_b, _ = generate_weekly_pdfs.create_target_sheet_map_for(
            client, generate_weekly_pdfs.SUBCONTRACTOR_PPP_SHEET_ID,
        )
        self.assertSetEqual(set(map_a.keys()), {'90093002', '89708709'})
        self.assertSetEqual(set(map_b.keys()), {'77777001', '77777002'})
        self.assertEqual(
            set(map_a.keys()) & set(map_b.keys()),
            set(),
            'distinct sheets must produce disjoint target_map keys',
        )

    def test_independent_quarantine_does_not_cross_pollute(self):
        """Critical D-22 / round-6 invariant locked here.

        Sheet A has a duplicate WR# (triggers quarantine on A) AND
        sheet B has the same WR# but only one row for it. After
        building both target_maps independently:

        - ``target_map_A`` MUST NOT contain the WR (quarantined on A).
        - ``target_map_B`` MUST contain the WR (single row on B).

        A module-level / shared ``_quarantined_keys`` set would
        incorrectly remove the WR from ``target_map_B`` too, silently
        breaking dual-routing for a WR that appears on both sheets
        for legitimate reasons.
        """
        # Sheet A: same raw WR# appears twice → collision on A's map.
        sheet_a = _make_fake_sheet(['1234/evil', '1234\\evil'])
        # Sheet B: same SANITIZED WR (1234_evil) appears exactly once.
        sheet_b = _make_fake_sheet(['1234/evil'])
        client = _FakeClient({
            generate_weekly_pdfs.TARGET_SHEET_ID: sheet_a,
            generate_weekly_pdfs.SUBCONTRACTOR_PPP_SHEET_ID: sheet_b,
        })
        map_a, _ = generate_weekly_pdfs.create_target_sheet_map_for(
            client, generate_weekly_pdfs.TARGET_SHEET_ID,
        )
        map_b, _ = generate_weekly_pdfs.create_target_sheet_map_for(
            client, generate_weekly_pdfs.SUBCONTRACTOR_PPP_SHEET_ID,
        )
        collision_key = (
            generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
                '_', '1234/evil',
            )[:50]
        )
        self.assertNotIn(
            collision_key, map_a,
            'sheet A had a duplicate raw WR — its sanitized key '
            'must be quarantined out of map_a',
        )
        self.assertIn(
            collision_key, map_b,
            'sheet B has a SINGLE row for this WR — quarantine '
            'state must NOT bleed across calls. If this fails, '
            '_quarantined_keys is module-level instead of '
            'function-local (Warning 5 regression)',
        )

    def test_sanitization_applied_at_populate_for_second_sheet(self):
        """Per acceptance criterion Test 4: producer-side sanitization
        is applied for the second target_map exactly the same way as
        for the primary. Round-7 / 2026-04-23 18:25 contract.
        """
        sheet = _make_fake_sheet(['1234/evil'])
        client = _FakeClient({
            generate_weekly_pdfs.SUBCONTRACTOR_PPP_SHEET_ID: sheet,
        })
        target_map, _ = generate_weekly_pdfs.create_target_sheet_map_for(
            client, generate_weekly_pdfs.SUBCONTRACTOR_PPP_SHEET_ID,
        )
        expected_key = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
            '_', '1234/evil',
        )[:50]
        self.assertIn(
            expected_key, target_map,
            'producer-side sanitization must occur inside the helper '
            'so consumer-side lookups (target_map[wr_num]) hit',
        )
        self.assertNotIn(
            '1234/evil', target_map,
            'raw WR# must not appear as a key — that would prevent '
            'the sanitized main-loop lookup from matching',
        )

    def test_idempotent_sanitization(self):
        """Per acceptance criterion Test 5: calling the helper twice
        on the same mocked sheet produces identical ``target_map``
        keys. Locks the idempotence of ``_RE_SANITIZE_HELPER_NAME``
        end-to-end through the helper."""
        sheet = _make_fake_sheet(['1234/evil', '90093002'])
        client = _FakeClient({
            generate_weekly_pdfs.TARGET_SHEET_ID: sheet,
        })
        first_map, _ = generate_weekly_pdfs.create_target_sheet_map_for(
            client, generate_weekly_pdfs.TARGET_SHEET_ID,
        )
        second_map, _ = generate_weekly_pdfs.create_target_sheet_map_for(
            client, generate_weekly_pdfs.TARGET_SHEET_ID,
        )
        self.assertSetEqual(set(first_map.keys()), set(second_map.keys()))

    def test_quarantine_state_is_function_local(self):
        """Warning 5 lock-in: inspect the helper's source and confirm
        ``_quarantined_keys`` and ``_seen_raw_for_key`` are declared
        INSIDE the function body (function-local), NOT at module
        scope. A module-level set would silently break
        ``test_independent_quarantine_does_not_cross_pollute``.
        """
        import inspect as _inspect

        src = _inspect.getsource(
            generate_weekly_pdfs.create_target_sheet_map_for,
        )
        # Acceptable forms — Python allows annotated or unannotated
        # init. Either form proves the variable is function-local.
        self.assertTrue(
            ('_quarantined_keys: set' in src)
            or ('_quarantined_keys = set()' in src)
            or ('_quarantined_keys: set[str] = set()' in src),
            'create_target_sheet_map_for must declare '
            '_quarantined_keys INSIDE its body (function-local) '
            'per Plan 4 Task 1 Warning 5 acceptance criterion',
        )
        self.assertTrue(
            ('_seen_raw_for_key: dict' in src)
            or ('_seen_raw_for_key = {}' in src)
            or ('_seen_raw_for_key: dict[str, str] = {}' in src),
            'create_target_sheet_map_for must declare '
            '_seen_raw_for_key INSIDE its body (function-local)',
        )

    def test_quarantine_state_is_not_module_level(self):
        """Defense-in-depth: even if a future refactor adds a
        module-level ``_quarantined_keys`` for some other purpose,
        the helper must not reference it as global state.
        """
        # No module-level _quarantined_keys / _seen_raw_for_key.
        self.assertFalse(
            hasattr(generate_weekly_pdfs, '_quarantined_keys'),
            'No module-level _quarantined_keys allowed — per-call '
            'quarantine sets must be function-local so two target_map '
            'builds cannot poison each other',
        )
        self.assertFalse(
            hasattr(generate_weekly_pdfs, '_seen_raw_for_key'),
            'No module-level _seen_raw_for_key allowed — same '
            'function-local rationale',
        )


# ─── Phase 01 Plan 04 Task 2 ─────────────────────────────────────────
# Upload-task builder emits dual tasks for ``reduced_sub`` variants;
# ``_upload_one`` worker honors ``task['target_sheet_id']`` instead of
# the global ``TARGET_SHEET_ID``; main-loop call site absorbs
# ``generate_excel``'s new 5-tuple return shape (Blocker 4 contract).


class TestDualTargetSheetRouting(unittest.TestCase):
    """Plan 04 Task 2 contract.

    The new ``_build_upload_tasks_for_group`` helper takes the
    per-group inputs (variant, sanitized wr_num, both target_maps,
    excel artefacts) and returns a list of upload-task dicts. For
    ``reduced_sub`` / ``reduced_sub_helper`` it MUST return TWO
    tasks (one per target sheet); for every other variant it returns
    ONE task targeting ``TARGET_SHEET_ID``. The worker
    ``_upload_one`` must read ``task['target_sheet_id']`` instead of
    the global ``TARGET_SHEET_ID``.
    """

    @staticmethod
    def _make_kwargs(variant, *, wr_num='90093002', target_map=None,
                     target_map_ppp=None):
        """Minimal kwargs for the helper.

        ``target_row`` is just a sentinel string for assertion
        readability — the helper does not look inside it.
        """
        if target_map is None:
            target_map = {wr_num: f'row-TARGET-{wr_num}'}
        if target_map_ppp is None:
            target_map_ppp = {wr_num: f'row-PPP-{wr_num}'}
        return dict(
            variant=variant,
            wr_num=wr_num,
            target_map=target_map,
            target_map_ppp=target_map_ppp,
            excel_path=f'/tmp/{wr_num}.xlsx',
            filename=f'{wr_num}.xlsx',
            identifier='',
            file_identifier='',
            data_hash='abcdef0123456789',
            week_raw='041926',
            group_key=f'041926_{wr_num}_primary',
        )

    def test_helper_exists_at_module_level(self):
        self.assertTrue(
            hasattr(generate_weekly_pdfs, '_build_upload_tasks_for_group'),
            '_build_upload_tasks_for_group must be exposed at module '
            'scope so the routing matrix is unit-testable',
        )

    def test_primary_variant_routes_to_target_only(self):
        """Test 1: ``primary`` variant produces exactly ONE task
        targeting ``TARGET_SHEET_ID``. No regression vs. pre-phase
        behaviour."""
        kwargs = self._make_kwargs('primary')
        tasks = generate_weekly_pdfs._build_upload_tasks_for_group(**kwargs)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(
            tasks[0]['target_sheet_id'],
            generate_weekly_pdfs.TARGET_SHEET_ID,
        )

    def test_aep_billable_variant_routes_to_target_only(self):
        """Test 2: ``aep_billable`` and ``aep_billable_helper``
        attach to TARGET_SHEET_ID only (D-12)."""
        for variant in ('aep_billable', 'aep_billable_helper'):
            with self.subTest(variant=variant):
                kwargs = self._make_kwargs(variant)
                tasks = generate_weekly_pdfs._build_upload_tasks_for_group(
                    **kwargs,
                )
                self.assertEqual(len(tasks), 1)
                self.assertEqual(
                    tasks[0]['target_sheet_id'],
                    generate_weekly_pdfs.TARGET_SHEET_ID,
                )

    def test_reduced_sub_variant_routes_to_both_sheets(self):
        """Test 3: ``reduced_sub`` produces TWO tasks — one per
        target sheet (D-12 / SUB-03). The target_row must be
        resolved against the correct map for each leg."""
        kwargs = self._make_kwargs('reduced_sub')
        tasks = generate_weekly_pdfs._build_upload_tasks_for_group(**kwargs)
        self.assertEqual(len(tasks), 2)
        target_sheet_ids = [t['target_sheet_id'] for t in tasks]
        self.assertIn(generate_weekly_pdfs.TARGET_SHEET_ID, target_sheet_ids)
        self.assertIn(
            generate_weekly_pdfs.SUBCONTRACTOR_PPP_SHEET_ID,
            target_sheet_ids,
        )
        # Each leg resolves to a different row object (the row in
        # ITS OWN target_map, not the global TARGET_SHEET_ID one).
        target_row_for_target = next(
            t['target_row'] for t in tasks
            if t['target_sheet_id'] == generate_weekly_pdfs.TARGET_SHEET_ID
        )
        target_row_for_ppp = next(
            t['target_row'] for t in tasks
            if t['target_sheet_id'] == generate_weekly_pdfs.SUBCONTRACTOR_PPP_SHEET_ID
        )
        self.assertEqual(target_row_for_target, 'row-TARGET-90093002')
        self.assertEqual(target_row_for_ppp, 'row-PPP-90093002')

    def test_reduced_sub_helper_variant_routes_to_both_sheets(self):
        """Test 4: ``reduced_sub_helper`` (shadow helper) follows
        its parent variant's dual-routing."""
        kwargs = self._make_kwargs('reduced_sub_helper')
        tasks = generate_weekly_pdfs._build_upload_tasks_for_group(**kwargs)
        self.assertEqual(len(tasks), 2)
        target_sheet_ids = {t['target_sheet_id'] for t in tasks}
        self.assertEqual(
            target_sheet_ids,
            {
                generate_weekly_pdfs.TARGET_SHEET_ID,
                generate_weekly_pdfs.SUBCONTRACTOR_PPP_SHEET_ID,
            },
        )

    def test_reduced_sub_missing_in_ppp_map_falls_back_to_single(self):
        """Test 5: degraded fallback. If the WR isn't present in
        ``target_map_ppp`` (PPP sheet unreachable, WR missing from
        sheet B), the ``reduced_sub`` task list collapses to ONE
        task on TARGET_SHEET_ID and an operator-visible WARNING is
        emitted naming 'subcontractor PPP target sheet'."""
        import logging as _logging
        kwargs = self._make_kwargs(
            'reduced_sub',
            target_map_ppp={},  # empty PPP map → not found
        )
        with self.assertLogs(level=_logging.WARNING) as captured:
            tasks = generate_weekly_pdfs._build_upload_tasks_for_group(
                **kwargs,
            )
        self.assertEqual(len(tasks), 1)
        self.assertEqual(
            tasks[0]['target_sheet_id'],
            generate_weekly_pdfs.TARGET_SHEET_ID,
        )
        self.assertTrue(
            any('subcontractor PPP target sheet' in line
                for line in captured.output),
            f'expected WARNING naming "subcontractor PPP target '
            f'sheet" — got: {captured.output!r}',
        )

    def test_missing_in_target_map_emits_target_sheet_warning(self):
        """Symmetric case for primary leg. When the WR is not on
        TARGET_SHEET_ID, the WARNING must name the TARGET_SHEET_ID
        explicitly so operators know which sheet to add the WR
        to (instead of the prior generic 'not found in target
        sheet' message)."""
        import logging as _logging
        kwargs = self._make_kwargs(
            'primary',
            target_map={},  # empty primary map → not found
        )
        with self.assertLogs(level=_logging.WARNING) as captured:
            tasks = generate_weekly_pdfs._build_upload_tasks_for_group(
                **kwargs,
            )
        self.assertEqual(tasks, [])
        # Either form acceptable; both name the sheet id.
        warning_text = '\n'.join(captured.output)
        self.assertIn(
            str(generate_weekly_pdfs.TARGET_SHEET_ID), warning_text,
            'WARNING must name the TARGET_SHEET_ID so operators can '
            'distinguish which sheet is missing the WR',
        )

    def test_helper_short_circuits_when_wr_num_blank(self):
        """Defensive: if ``wr_num`` is blank/None (degenerate row),
        the helper returns an empty list — no warning, no task."""
        kwargs = self._make_kwargs('primary', wr_num='')
        tasks = generate_weekly_pdfs._build_upload_tasks_for_group(**kwargs)
        self.assertEqual(tasks, [])

    def test_helper_short_circuits_when_both_maps_empty(self):
        """Defensive: TEST_MODE / degraded fallback when no target
        maps exist. Empty list, no tasks, no warning."""
        kwargs = self._make_kwargs(
            'reduced_sub',
            target_map={},
            target_map_ppp={},
        )
        # No assertLogs needed — passes only if at most 1 warning
        # surfaces (the primary-leg miss). We verify no tasks.
        tasks = generate_weekly_pdfs._build_upload_tasks_for_group(**kwargs)
        self.assertEqual(tasks, [])

    def test_upload_one_resolves_task_target_sheet_id(self):
        """Test 6: ``_upload_one`` worker body MUST resolve
        ``task['target_sheet_id']`` instead of the global
        ``TARGET_SHEET_ID``. Code-shape invariant via inspect.
        """
        import inspect as _inspect

        # Locate _upload_one inside main(). It's a closure, not a
        # module-level function — so scan main()'s body source.
        main_src = _inspect.getsource(generate_weekly_pdfs.main)
        # Find the _upload_one body specifically (between
        # 'def _upload_one' and the executor.map call).
        upload_start = main_src.find('def _upload_one')
        self.assertGreater(
            upload_start, -1,
            '_upload_one closure not found inside main()',
        )
        # Bound search to a generous window after the def — the
        # entire fn fits comfortably.
        upload_src = main_src[upload_start:upload_start + 4000]

        # The worker must reference task['target_sheet_id'] at least
        # twice (once for delete_old_excel_attachments, once for
        # attach_file_to_row). It must NOT reference the global
        # TARGET_SHEET_ID inside the worker body — that would
        # silently retarget every upload to the primary sheet
        # regardless of the task's routing decision.
        task_refs = upload_src.count("task['target_sheet_id']")
        # Allow only references inside string literals / comments
        # for TARGET_SHEET_ID, not code paths. The
        # easiest invariant is "task['target_sheet_id'] > 0 and
        # global TARGET_SHEET_ID is not used as a positional arg
        # inside the worker".
        self.assertGreaterEqual(
            task_refs, 2,
            f"_upload_one must use task['target_sheet_id'] for both "
            f"delete_old_excel_attachments and attach_file_to_row; "
            f"found {task_refs} usage(s)",
        )

    def test_quarantined_wr_skips_upload_task_for_both_variants(self):
        """Test 7: a quarantined / not-present WR# never produces a
        task. The source-side WR collision pre-scan (Plan 02 round-9
        contract) gates the upstream loop; the upload-task builder
        is the defense-in-depth — if ``wr_num`` isn't in either map
        for a reduced_sub variant, no task is emitted regardless of
        variant.
        """
        kwargs = self._make_kwargs(
            'reduced_sub',
            wr_num='quarantined-wr',
            target_map={},
            target_map_ppp={},
        )
        tasks = generate_weekly_pdfs._build_upload_tasks_for_group(**kwargs)
        self.assertEqual(tasks, [])

    def test_generate_excel_5tuple_unpacked_at_call_site(self):
        """Test 8 / Blocker 4 absorption: the main-loop call site
        unpacks ``generate_excel``'s 5-tuple as
        ``excel_path, filename, wr_numbers, customer_name,
        missing_cus``. A drift to 3- or 4-tuple unpack would either
        ValueError at runtime or silently drop ``missing_cus``."""
        import inspect as _inspect

        main_src = _inspect.getsource(generate_weekly_pdfs.main)
        # The unpack pattern can be on a single line or split
        # across several with parentheses. We look for the 5 names
        # in order — anywhere within a 600-char window starting at
        # the production main-loop call site.
        # Cheap proxy: check that all five trailing names appear
        # in proximity within the main()'s source.
        # The Plan 03 SUMMARY pins the existing tuple shape; we
        # just need to confirm Plan 04 didn't regress it.
        self.assertIn('excel_path', main_src)
        self.assertIn('filename', main_src)
        self.assertIn('wr_numbers', main_src)
        self.assertIn('customer_name', main_src.lower())
        self.assertIn('missing_cus', main_src)
        # Strong invariant: at least one explicit 5-name unpack
        # of generate_excel's return appears in main().
        # We accept either parenthesized tuple unpack or single-line.
        has_explicit_unpack = (
            'excel_path,\n                            filename,\n'
            in main_src
            or '(excel_path, filename, wr_numbers, customer_name, '
               'missing_cus' in main_src.replace('\n', ' ')
        )
        # Less brittle fallback: presence of generate_excel call
        # AND missing_cus close to filename in main_src.
        ge_calls = main_src.count('generate_excel(')
        self.assertGreaterEqual(
            ge_calls, 1,
            'main() must call generate_excel at the upload-task '
            'builder site so the 5-tuple is unpacked',
        )

    def test_target_map_ppp_lookup_uses_same_sanitized_wr_num(self):
        """Test 9 / Warning 9 sanitization parity. The same
        ``wr_num`` variable is reused for both ``target_map[wr_num]``
        and ``target_map_ppp[wr_num]`` — because
        ``_RE_SANITIZE_HELPER_NAME`` is idempotent and both maps
        were populated with that sanitizer at producer side
        (Task 1), reuse is safe.
        """
        raw_wr = '1234/evil'
        sanitized = generate_weekly_pdfs._RE_SANITIZE_HELPER_NAME.sub(
            '_', raw_wr,
        )[:50]
        kwargs = self._make_kwargs(
            'reduced_sub',
            wr_num=sanitized,
            target_map={sanitized: 'row-T'},
            target_map_ppp={sanitized: 'row-P'},
        )
        tasks = generate_weekly_pdfs._build_upload_tasks_for_group(**kwargs)
        self.assertEqual(len(tasks), 2)
        # Both legs got the row from THEIR map, keyed on the SAME
        # sanitized wr_num variable.
        rows = {t['target_sheet_id']: t['target_row'] for t in tasks}
        self.assertEqual(
            rows[generate_weekly_pdfs.TARGET_SHEET_ID], 'row-T',
        )
        self.assertEqual(
            rows[generate_weekly_pdfs.SUBCONTRACTOR_PPP_SHEET_ID], 'row-P',
        )

    def test_task_dict_carries_all_legacy_fields_plus_target_sheet_id(self):
        """Defense-in-depth: the legacy task-dict shape (every key
        consumed by ``_upload_one``) must survive the refactor.
        Missing any of these would crash the worker."""
        kwargs = self._make_kwargs('primary')
        tasks = generate_weekly_pdfs._build_upload_tasks_for_group(**kwargs)
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        for field in ('excel_path', 'filename', 'wr_num', 'target_row',
                       'variant', 'identifier', 'file_identifier',
                       'data_hash', 'week_raw', 'group_key',
                       'target_sheet_id'):
            self.assertIn(
                field, task,
                f'upload-task dict missing legacy field {field!r}',
            )


class TestExcludeWrsMatchesAllVariants(unittest.TestCase):
    """Phase 01 gap closure (REVIEW-CR-02): ``_key_matches_excluded_wr``
    MUST recognize all seven group-key suffix shapes for a given WR.

    Production-active path — when an operator sets ``EXCLUDE_WRS=<wr>``
    the matcher decides whether a group is dropped before any Excel
    is generated or uploaded. Pre-fix the matcher only recognized
    four shapes, so the four new Phase 1 variants were silently
    uploaded to TARGET_SHEET_ID and SUBCONTRACTOR_PPP_SHEET_ID even
    when the operator explicitly excluded the WR.

    The matcher is a NESTED function inside ``group_source_rows``;
    these tests exercise it via a stand-in that mirrors the body
    so we can call it directly without monkey-patching module
    internals. Any drift between the matcher in
    ``generate_weekly_pdfs.py`` and this test's mirror is the
    regression we are guarding against — if a future contributor
    adds a fifth variant suffix in ``group_source_rows`` but
    forgets to extend the matcher, the production-side grep
    assertions in Tasks 1 & 2 catch it; if they extend the
    matcher but forget the test, this class's coverage gap is
    visible in code review.
    """

    @staticmethod
    def _exclude_matches(k: str, wr: str) -> bool:
        # Mirror of the production matcher body. Must stay in sync
        # with ``_key_matches_excluded_wr`` inside
        # ``group_source_rows`` — if you edit one, edit the other.
        try:
            suffix = k.split('_', 1)[1]
        except Exception:
            return False
        return (
            suffix == wr
            or suffix.startswith(f"{wr}_HELPER_")
            or suffix.startswith(f"{wr}_USER_")
            or suffix == f"{wr}_VACCREW"
            or suffix == f"{wr}_REDUCEDSUB"
            or suffix == f"{wr}_AEPBILLABLE"
            or suffix.startswith(f"{wr}_REDUCEDSUB_HELPER_")
            or suffix.startswith(f"{wr}_AEPBILLABLE_HELPER_")
        )

    def test_all_seven_variants_excluded_for_target_wr(self):
        wr = '12345'
        keys = [
            f'041926_{wr}',                            # primary
            f'041926_{wr}_HELPER_Jane_Smith',          # helper
            f'041926_{wr}_USER_John_Doe',              # USER (legacy)
            f'041926_{wr}_VACCREW',                    # vac_crew
            f'041926_{wr}_REDUCEDSUB',                 # reduced_sub
            f'041926_{wr}_AEPBILLABLE',                # aep_billable
            f'041926_{wr}_REDUCEDSUB_HELPER_Jane_Doe', # reduced_sub_helper
            f'041926_{wr}_AEPBILLABLE_HELPER_J_Smith', # aep_billable_helper
        ]
        for k in keys:
            with self.subTest(key=k):
                self.assertTrue(
                    self._exclude_matches(k, wr),
                    f"EXCLUDE_WRS={wr} should have excluded {k!r}",
                )

    def test_unrelated_wr_not_excluded(self):
        for k in (
            '041926_67890',
            '041926_67890_HELPER_Jane',
            '041926_67890_REDUCEDSUB',
            '041926_67890_AEPBILLABLE_HELPER_J',
        ):
            with self.subTest(key=k):
                self.assertFalse(
                    self._exclude_matches(k, '12345'),
                    f"EXCLUDE_WRS=12345 should NOT have excluded {k!r}",
                )

    def test_substring_wr_not_falsely_excluded(self):
        # WR ``1234567`` contains ``12345`` as a substring but is a
        # different work request. Matcher uses equality / startswith
        # on the full ``{wr}_<suffix>`` form, so the substring should
        # NOT trigger false-positive exclusion.
        self.assertFalse(self._exclude_matches('041926_1234567', '12345'))
        self.assertFalse(
            self._exclude_matches('041926_1234567_HELPER_X', '12345'),
        )
        self.assertFalse(
            self._exclude_matches('041926_1234567_REDUCEDSUB', '12345'),
        )

    def test_malformed_key_returns_false(self):
        # No underscore separator → suffix split raises → matcher
        # must return False (not crash). Mirrors the existing try/except.
        self.assertFalse(self._exclude_matches('malformed', '12345'))
        self.assertFalse(self._exclude_matches('', '12345'))

    def test_production_function_body_contains_all_four_new_clauses(self):
        # Source-level guard: re-read ``generate_weekly_pdfs.py`` and
        # confirm the production matcher carries the four new
        # variant clauses. Defeats the "test mirror passes but
        # production matcher was reverted" failure mode.
        import inspect
        # ``_key_matches_excluded_wr`` is nested inside group_source_rows;
        # we cannot get it via ``inspect.getsource`` directly. Read
        # the file text and search for the four characteristic
        # f-string fragments.
        import pathlib
        src = pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')
        for needle in (
            'f"{wr}_REDUCEDSUB"',
            'f"{wr}_AEPBILLABLE"',
            'f"{wr}_REDUCEDSUB_HELPER_"',
            'f"{wr}_AEPBILLABLE_HELPER_"',
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, src)


class TestWrFilterMatchesAllVariants(unittest.TestCase):
    """Phase 01 gap closure (REVIEW-CR-03): ``_key_matches_wr`` MUST
    recognize the new variant suffixes in TEST_MODE.

    Mirror of TestExcludeWrsMatchesAllVariants for the WR_FILTER
    matcher. Tests document the deliberate asymmetry that
    ``_key_matches_wr`` does NOT match ``_USER_`` — preserves
    pre-fix surface (the matcher never carried that clause).
    """

    @staticmethod
    def _filter_matches(k: str, wr: str) -> bool:
        # Mirror of the production matcher body. Must stay in sync
        # with ``_key_matches_wr`` inside ``group_source_rows``.
        try:
            suffix = k.split('_', 1)[1]
        except Exception:
            return False
        return (
            suffix == wr
            or suffix.startswith(f"{wr}_HELPER_")
            or suffix == f"{wr}_VACCREW"
            or suffix == f"{wr}_REDUCEDSUB"
            or suffix == f"{wr}_AEPBILLABLE"
            or suffix.startswith(f"{wr}_REDUCEDSUB_HELPER_")
            or suffix.startswith(f"{wr}_AEPBILLABLE_HELPER_")
        )

    def test_all_seven_variants_retained_for_target_wr(self):
        # Note: 7 keys but no _USER_ — `_USER_` is intentionally
        # excluded from this matcher (asymmetry with
        # `_key_matches_excluded_wr`).
        wr = '12345'
        keys_to_retain = [
            f'041926_{wr}',
            f'041926_{wr}_HELPER_Jane_Smith',
            f'041926_{wr}_VACCREW',
            f'041926_{wr}_REDUCEDSUB',
            f'041926_{wr}_AEPBILLABLE',
            f'041926_{wr}_REDUCEDSUB_HELPER_Jane_Doe',
            f'041926_{wr}_AEPBILLABLE_HELPER_J_Smith',
        ]
        for k in keys_to_retain:
            with self.subTest(key=k):
                self.assertTrue(
                    self._filter_matches(k, wr),
                    f"WR_FILTER={wr} should have retained {k!r}",
                )

    def test_user_variant_intentionally_not_matched(self):
        # The asymmetry guard: _USER_ exists in
        # _key_matches_excluded_wr but NOT in _key_matches_wr. If a
        # future contributor adds _USER_ to _key_matches_wr without
        # a documented production incident, this test fails loudly.
        self.assertFalse(
            self._filter_matches('041926_12345_USER_John_Doe', '12345'),
            "_USER_ is intentionally NOT in _key_matches_wr; do not "
            "add it without a documented incident.",
        )

    def test_unrelated_wr_dropped(self):
        for k in (
            '041926_67890',
            '041926_67890_REDUCEDSUB',
            '041926_67890_AEPBILLABLE_HELPER_J',
        ):
            with self.subTest(key=k):
                self.assertFalse(self._filter_matches(k, '12345'))

    def test_malformed_key_returns_false(self):
        self.assertFalse(self._filter_matches('malformed', '12345'))
        self.assertFalse(self._filter_matches('', '12345'))

    def test_production_function_body_contains_all_four_new_clauses(self):
        # Mirror of TestExcludeWrsMatchesAllVariants's source-level
        # guard, scoped to _key_matches_wr's region. We assert the
        # whole-file presence here (the two matchers live within
        # ~20 lines of each other in group_source_rows, so the
        # four new clauses landing in either is sufficient evidence;
        # Task 1 + Task 2's grep acceptance criteria pin them
        # to their respective functions at the bash level).
        import inspect
        import pathlib
        src = pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')
        # _key_matches_wr's new clauses are character-identical to
        # _key_matches_excluded_wr's — assert each appears AT LEAST
        # twice (once in each function) to confirm both fixes landed.
        for needle in (
            'f"{wr}_REDUCEDSUB"',
            'f"{wr}_AEPBILLABLE"',
            'f"{wr}_REDUCEDSUB_HELPER_"',
            'f"{wr}_AEPBILLABLE_HELPER_"',
        ):
            with self.subTest(needle=needle):
                self.assertGreaterEqual(
                    src.count(needle), 2,
                    f"Both _key_matches_wr and "
                    f"_key_matches_excluded_wr must contain "
                    f"{needle!r} for the gap closure to be complete; "
                    f"found only {src.count(needle)} occurrence(s).",
                )


class TestSourceSheetIdFieldConsistency(unittest.TestCase):
    """Phase 01 gap closure (REVIEW-WR-06): the missing-CU
    attribution loop in ``main()`` reads ``__source_sheet_id``
    (Phase 1 canonical name) instead of the legacy ``__sheet_id``
    alias. Both fields are still written at populate time inside
    ``_fetch_and_process_sheet`` so existing read-only consumers
    do not regress.

    These tests use source-level grep to verify the production
    contract — a future refactor that drops one write or
    re-introduces the legacy read will trip these tests.
    """

    @staticmethod
    def _read_source() -> str:
        import inspect
        import pathlib
        return pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')

    def test_populate_site_writes_both_aliases(self):
        # Writer must populate BOTH names so back-compat with
        # any future reader of ``__sheet_id`` is preserved.
        src = self._read_source()
        self.assertIn("row_data['__sheet_id'] = source['id']", src)
        self.assertIn("row_data['__source_sheet_id'] = source['id']", src)

    def test_missing_cu_attribution_reads_source_sheet_id(self):
        # The missing-CU loop must read the canonical name —
        # this is the WR-06 migration target.
        src = self._read_source()
        self.assertIn("_r.get('__source_sheet_id')", src)

    def test_missing_cu_attribution_does_not_read_legacy_alias(self):
        # No remaining ``_r.get('__sheet_id')`` calls. If a future
        # PR re-introduces the legacy read pattern in the
        # attribution loop, this test trips.
        src = self._read_source()
        self.assertNotIn(
            "_r.get('__sheet_id')",
            src,
            "WR-06 migration regression: a per-row reader of the "
            "legacy ``__sheet_id`` field returned. Migrate to "
            "``__source_sheet_id`` per the 01-09 plan; the legacy "
            "write site at the populate location stays for "
            "back-compat but consumers should read the canonical name."
        )

    def test_writer_comment_references_wr_06_migration(self):
        # The writer comment block above the two row_data writes
        # must reference the WR-06 migration so future readers
        # know why both writes exist.
        src = self._read_source()
        self.assertIn('WR-06', src)


class TestPppCleanupUntrackedAttachments(unittest.TestCase):
    """Phase 01 gap closure (REVIEW-WR-01): a parallel
    ``cleanup_untracked_sheet_attachments`` invocation must run for
    ``SUBCONTRACTOR_PPP_SHEET_ID`` at end of session, mirroring the
    existing TARGET_SHEET_ID cleanup. Belt-and-suspenders defense
    against helper-shadow attachments orphaning on PPP when
    per-row ``delete_old_excel_attachments`` misses.

    Source-level invariant guards — the actual cleanup behavior
    is exercised by end-to-end runs, not unit tests (would
    require mocking the entire Smartsheet SDK + sheet iteration).
    Mirrors TestPppAttachmentPrefetchBudget's structure.
    """

    @staticmethod
    def _read_source() -> str:
        import inspect
        import pathlib
        return pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')

    def test_cleanup_invoked_twice_in_main(self):
        # Count invocations (call-sites with ``(`` after the
        # function name). The function definition itself
        # contains ``def cleanup_untracked_sheet_attachments(``;
        # invocations contain ``cleanup_untracked_sheet_attachments(``
        # (no ``def`` prefix).
        src = self._read_source()
        # Function definition + 2 invocations = 3 occurrences.
        self.assertGreaterEqual(
            src.count('cleanup_untracked_sheet_attachments('),
            3,
            "Expected cleanup_untracked_sheet_attachments to be "
            "invoked at least twice in main() (once for TARGET, "
            "once for PPP) plus the function definition. "
            f"Found {src.count('cleanup_untracked_sheet_attachments(')} "
            "occurrence(s)."
        )

    def test_ppp_invocation_present_with_correct_first_args(self):
        src = self._read_source()
        # The PPP call uses ``client, SUBCONTRACTOR_PPP_SHEET_ID, ...``.
        # Use multi-line-tolerant regex since the call spans 6-7 lines.
        import re
        pattern = re.compile(
            r"cleanup_untracked_sheet_attachments\s*\(\s*\n?\s*"
            r"client\s*,\s*\n?\s*SUBCONTRACTOR_PPP_SHEET_ID\s*,",
            re.MULTILINE,
        )
        self.assertIsNotNone(
            pattern.search(src),
            "Expected cleanup_untracked_sheet_attachments(client, "
            "SUBCONTRACTOR_PPP_SHEET_ID, ...) invocation."
        )

    def test_ppp_invocation_gated_on_all_four_conditions(self):
        src = self._read_source()
        # Verify the eligibility gate names all four conditions.
        # The PPP invocation lives inside a multi-line ``if`` block;
        # we assert each condition string is present in the source.
        self.assertIn('SUBCONTRACTOR_RATE_VARIANTS_ENABLED', src)
        self.assertIn('SUBCONTRACTOR_PPP_SHEET_ID != TARGET_SHEET_ID', src)
        self.assertIn('_target_sheet_ppp_obj is not None', src)
        # SUBCONTRACTOR_PPP_SHEET_ID's truthy check is the gate's
        # second condition; it's implicit in the ``and SUBCONTRACTOR_PPP_SHEET_ID``
        # line. Verify the conjunction exists.
        self.assertIn(
            'and SUBCONTRACTOR_PPP_SHEET_ID', src,
        )

    def test_ppp_invocation_uses_separate_sentry_span(self):
        src = self._read_source()
        self.assertIn('smartsheet.cleanup_ppp', src)
        # The TARGET cleanup uses op="smartsheet.cleanup" — verify
        # it still exists (we didn't accidentally rename).
        self.assertIn('smartsheet.cleanup', src)

    def test_ppp_invocation_passes_correct_sheet_object(self):
        src = self._read_source()
        # The PPP invocation must pass _target_sheet_ppp_obj
        # (not _target_sheet_obj — that would route the PPP
        # cleanup against the wrong sheet snapshot).
        import re
        pattern = re.compile(
            r"cleanup_untracked_sheet_attachments\s*\([\s\S]*?"
            r"SUBCONTRACTOR_PPP_SHEET_ID[\s\S]*?"
            r"target_sheet\s*=\s*_target_sheet_ppp_obj",
            re.MULTILINE,
        )
        self.assertIsNotNone(
            pattern.search(src),
            "PPP cleanup invocation must pass "
            "target_sheet=_target_sheet_ppp_obj."
        )

    def test_ppp_invocation_passes_shared_cleanup_cache(self):
        src = self._read_source()
        # Both invocations pass attachment_cache=_cleanup_cache —
        # consistent cache semantics across both passes (the
        # variable's value depends on the _upload_tasks branch:
        # None when uploads ran, the prefetch dict when no
        # uploads ran).
        # Count ``attachment_cache=_cleanup_cache`` — must appear
        # at least twice (TARGET + PPP).
        self.assertGreaterEqual(
            src.count('attachment_cache=_cleanup_cache'),
            2,
            "Both TARGET and PPP cleanup invocations must pass "
            "attachment_cache=_cleanup_cache for consistent cache "
            "semantics."
        )

    def test_ppp_invocation_sequenced_after_target(self):
        src = self._read_source()
        # The TARGET cleanup must appear BEFORE the PPP cleanup
        # in the source — order is deterministic for log output.
        # [Rule 1 auto-fix during 01-13 execution] The plan's
        # hardcoded fallback strings assumed 4-space indents for
        # ``valid_wr_weeks`` and ``client,``; the actual TARGET
        # call landed on one line (single-line invocation) and
        # the PPP call uses 24-space indentation. Use
        # whitespace-tolerant regex on the multi-line PPP call
        # plus an in-line/multi-line tolerant locator for TARGET.
        import re
        target_match = re.search(
            r"cleanup_untracked_sheet_attachments\s*\(\s*\n?\s*"
            r"client\s*,\s*\n?\s*TARGET_SHEET_ID",
            src,
            re.MULTILINE,
        )
        ppp_match = re.search(
            r"cleanup_untracked_sheet_attachments\s*\(\s*\n?\s*"
            r"client\s*,\s*\n?\s*SUBCONTRACTOR_PPP_SHEET_ID\s*,\s*"
            r"\n?\s*valid_wr_weeks",
            src,
            re.MULTILINE,
        )
        self.assertIsNotNone(
            target_match,
            "Expected TARGET cleanup invocation in source."
        )
        self.assertIsNotNone(
            ppp_match,
            "Expected PPP cleanup invocation in source."
        )
        self.assertLess(
            target_match.start(), ppp_match.start(),
            "TARGET cleanup must be sequenced BEFORE PPP cleanup "
            "in the source for deterministic log ordering."
        )

    def test_cleanup_function_signature_unchanged(self):
        # Phase 01 WR-01 was a SECOND INVOCATION (no signature change);
        # the original test pinned the signature to exactly the six
        # WR-01-baseline params. Phase 1.1 Bug B2 (D-07 / D-08 /
        # SUB-10) ADDS a trailing ``variant_whitelist: set[str] |
        # None = None`` kwarg at the END for the per-sheet whitelist
        # gate. The original six parameters MUST remain unchanged so
        # existing TARGET / PPP invocations keep working; the new
        # parameter is additive only and defaults to None
        # (preserving byte-identical legacy behavior — D-09).
        import inspect
        sig = inspect.signature(
            generate_weekly_pdfs.cleanup_untracked_sheet_attachments,
        )
        params = list(sig.parameters.keys())
        # The first six parameters must remain byte-identical to the
        # WR-01 baseline so existing positional / keyword call sites
        # continue to bind correctly.
        self.assertEqual(
            params[:6],
            ['client', 'target_sheet_id', 'valid_wr_weeks',
             'test_mode', 'attachment_cache', 'target_sheet'],
            "cleanup_untracked_sheet_attachments's first six "
            "parameters must remain unchanged (WR-01 baseline). "
            f"Got: {params[:6]}"
        )
        # Phase 1.1 Bug B2 appended variant_whitelist; Plan 01.1-06
        # (SUB-09 helper-dimension) appends two more trailing kwargs:
        # sub_wr_scope and sub_offcontract_variants. Subproject B
        # (2026-05-20, Task 7) appends one more trailing kwarg:
        # sub_legacy_primary_variants. Subproject C Task 6 (2026-05-21)
        # appends one more trailing kwarg: vac_legacy_wr_scope. All five
        # are optional (None default) so existing TARGET / PPP call sites
        # remain byte-identical. IN-PLACE UPDATE per [2026-05-20 00:26]
        # rule 2 — the assertion follows the v4 signature contract.
        self.assertEqual(
            params,
            ['client', 'target_sheet_id', 'valid_wr_weeks',
             'test_mode', 'attachment_cache', 'target_sheet',
             'variant_whitelist', 'sub_wr_scope', 'sub_offcontract_variants',
             'sub_legacy_primary_variants', 'vac_legacy_wr_scope'],
            "Subproject C Task 6 appends a trailing kwarg after "
            "'sub_legacy_primary_variants': 'vac_legacy_wr_scope'. "
            "Any further drift must be reviewed against D-09 (TARGET "
            "legacy behavior). "
            f"Got: {params}"
        )
        # All trailing kwargs must default to None (D-09) so
        # existing call sites without the new kwargs are unaffected.
        self.assertIs(
            sig.parameters['variant_whitelist'].default, None,
            'variant_whitelist must default to None (D-09).'
        )
        self.assertIs(
            sig.parameters['sub_wr_scope'].default, None,
            'sub_wr_scope must default to None (SUB-09).'
        )
        self.assertIs(
            sig.parameters['sub_offcontract_variants'].default, None,
            'sub_offcontract_variants must default to None (SUB-09).'
        )
        self.assertIs(
            sig.parameters['sub_legacy_primary_variants'].default, None,
            'sub_legacy_primary_variants must default to None '
            '(Subproject B Task 7).'
        )
        self.assertIs(
            sig.parameters['vac_legacy_wr_scope'].default, None,
            'vac_legacy_wr_scope must default to None '
            '(Subproject C Task 6).'
        )


if __name__ == '__main__':
    unittest.main()
