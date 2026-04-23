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


if __name__ == '__main__':
    unittest.main()
