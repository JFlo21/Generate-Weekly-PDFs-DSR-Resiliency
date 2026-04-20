"""Tests for the Sentry Logs PII sanitizer and env gate parser.

These cover the module-scope helpers added to ``generate_weekly_pdfs``
for the Sentry Logs opt-in: ``sentry_before_send_log``,
``_parse_sentry_enable_logs``, and the ``_PII_LOG_MARKERS`` tuple.
"""

import generate_weekly_pdfs as gwp


class TestParseSentryEnableLogs:
    """Boolean parsing for the SENTRY_ENABLE_LOGS env var."""

    def test_none_is_false(self):
        assert gwp._parse_sentry_enable_logs(None) is False

    def test_empty_string_is_false(self):
        assert gwp._parse_sentry_enable_logs("") is False
        assert gwp._parse_sentry_enable_logs("   ") is False

    def test_explicit_false_values(self):
        for raw in ("false", "0", "no", "off", "disabled", "False"):
            assert gwp._parse_sentry_enable_logs(raw) is False, raw

    def test_truthy_values(self):
        for raw in ("1", "true", "yes", "on", "TRUE", "  True  ", "On"):
            assert gwp._parse_sentry_enable_logs(raw) is True, raw


class TestPiiLogMarkers:
    """The marker tuple drives the sanitizer; guard its shape."""

    def test_is_tuple_of_strings(self):
        assert isinstance(gwp._PII_LOG_MARKERS, tuple)
        assert all(isinstance(m, str) and m for m in gwp._PII_LOG_MARKERS)

    def test_covers_known_row_level_log_paths(self):
        # Sanity-check that the known INFO-level PII log bodies in the
        # billing engine are each represented by at least one marker.
        required = {
            "Row data sample",
            "ESSENTIAL FIELDS",
            "HELPER ROW DETECTED",
            "HELPER GROUP CREATED",
            "HELPER GROUP SUMMARY",
            "Helper group '",
            "Helper row for WR",
            "Sample Helper",
            "VAC Crew detection",
            "VAC CREW ROW DETECTED",
            "VAC CREW GROUP CREATED",
            "VAC CREW GROUP SUMMARY",
            "VAC Crew group '",
            "Rate recalculation",
            "Foreman Assignment",
            "foremen(top5)",
            "Excluding row",
            "EXCLUDING from main Excel",
            "Sample group keys",
            "Skip (unchanged",
            "Regenerating ",
            "_WeekEnding_",
            "Generated Excel",
            "Uploaded: ",
            "Upload failed for ",
            "Deleted: ",
        }
        assert required.issubset(set(gwp._PII_LOG_MARKERS))


class TestSentryBeforeSendLog:
    """Sanitizer drops records whose body matches a PII marker."""

    def test_drops_row_data_sample(self):
        record = {
            "body": (
                "🔍 Row data sample: WR=WR123, Price=$100.00, "
                "Date=2024-01-01, Units Completed=true"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_cell_dump(self):
        record = {"body": "   Cell 12345: 'Foreman' = 'Jane Doe'"}
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_essential_fields_dump(self):
        record = {
            "body": (
                "   ESSENTIAL FIELDS: {'Weekly Reference Logged Date': "
                "'2024-01-01', 'Snapshot Date': '2024-01-01', "
                "'Units Completed?': 'true', 'Units Total Price': "
                "'$100.00', 'Work Request #': 'WR123'}"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_helper_row_detected(self):
        record = {
            "body": (
                "🔧 HELPER ROW DETECTED [Row 5]: WR=WR42, Helper=John, "
                "Dept=200, Job=J7"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_rate_recalc(self):
        record = {
            "body": "Rate recalculation: CU 'X' not found, keeping SmartSheet price",
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_foreman_assignment(self):
        record = {"body": "📋 Foreman Assignment: Using 'Alice' (primary)"}
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_excluding_row(self):
        record = {
            "body": "🚫 Excluding row for WR WR99 due to CU 'NO MATCH'",
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_unchanged_log(self):
        record = {
            "body": (
                "⏩ Unchanged (primary WR 42 Week 010124) hash abc; skipping"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_force_generation(self):
        record = {
            "body": "⚐ FORCE GENERATION for primary WR 42 Week 010124",
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_sample_helper_line(self):
        record = {
            "body": (
                "   Sample Helper 1: WR=WR123, Helper=Jane Doe, "
                "Dept=200, Job=J7"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_vac_crew_row_detected(self):
        record = {
            "body": (
                "🚐 VAC CREW ROW DETECTED [Row 7]: WR=WR42, "
                "Name=Bob, Dept=300, Job=J9"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_vac_crew_group_created(self):
        record = {"body": "🏗️ VAC CREW GROUP CREATED: WR=WR42, Week=010124"}
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_helper_group_created(self):
        record = {
            "body": (
                "🔧 HELPER GROUP CREATED: WR=WR42, Week=010124, "
                "Helper=Jane, Dept=200, Job=J7"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_helper_group_summary(self):
        record = {
            "body": (
                "🔧 HELPER GROUP SUMMARY: Created 3 helper groups "
                "out of 12 total groups"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_helper_group_sample_line(self):
        # helper_key is "{week}_{wr}_HELPER_{sanitized_foreman_name}"
        record = {
            "body": "   Helper group '010124_WR42_HELPER_Jane_Doe': 7 rows",
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_vac_crew_group_summary(self):
        record = {
            "body": (
                "🏗️ VAC CREW GROUP SUMMARY: Created 2 VAC Crew "
                "group(s) out of 10 total groups"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_vac_crew_group_sample_line(self):
        record = {"body": "   VAC Crew group '010124_WR42_VACCREW': 5 rows"}
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_excluding_from_main_excel(self):
        record = {
            "body": (
                "➖ EXCLUDING from main Excel: WR=WR42, Week=010124 "
                "(Helper row with both checkboxes)"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_for_wr_hash_prefix(self):
        record = {
            "body": (
                "Could not parse Weekly Reference Logged Date 'xyz' "
                "for WR# WR42. Skipping row."
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_wr_hash_debug_line(self):
        record = {
            "body": (
                "WR# WR42: Week ending Monday, 01/01/2024 | "
                "User: Alice | Method: primary | Helper: False"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_sample_group_keys(self):
        record = {"body": "🔍 Sample group keys: [('WR42', '010124')]"}
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_skip_unchanged(self):
        record = {
            "body": "⏩ Skip (unchanged + attachment exists) primary WR 42 week 010124 hash abc",
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_regenerating(self):
        record = {
            "body": "🔁 Regenerating primary WR 42 week 010124 despite unchanged hash",
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_generated_excel_filename(self):
        # Filename embeds WR, week, helper foreman name, and hash.
        record = {
            "body": (
                "📄 Generated Excel: 'WR_WR42_WeekEnding_010124_"
                "20260420T120000Z_Helper_Jane_Doe_abcd1234.xlsx'"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_generating_excel_file(self):
        record = {
            "body": (
                "📊 Generating Excel file "
                "'WR_WR42_WeekEnding_010124_20260420T120000Z.xlsx' "
                "for WR#WR42"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_uploaded_filename(self):
        record = {
            "body": (
                "✅ Uploaded: "
                "WR_WR42_WeekEnding_010124_Helper_Jane_abcd.xlsx"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_upload_retry_and_rate_limit(self):
        for body in (
            "⚠️ Upload retry 2/5 for WR_WR42_WeekEnding_010124_abcd.xlsx (TimeoutError), backoff 1.0s",
            "⚠️ Rate limited on upload for WR_WR42_WeekEnding_010124_abcd.xlsx, backoff 2s (attempt 1/5)",
            "❌ Upload failed for WR_WR42_WeekEnding_010124_abcd.xlsx: boom",
        ):
            assert gwp.sentry_before_send_log({"body": body}, {}) is None, body

    def test_drops_attachment_delete_lifecycle(self):
        for body in (
            "   ✅ Deleted: WR_WR42_WeekEnding_010124_abcd.xlsx",
            "   ℹ️ Already gone: WR_WR42_WeekEnding_010124_abcd.xlsx",
            "   ⚠️ Delete failed WR_WR42_WeekEnding_010124_abcd.xlsx: boom",
        ):
            assert gwp.sentry_before_send_log({"body": body}, {}) is None, body

    def test_drops_weekending_substring_catchall(self):
        # Even outside the known prefixes, any body carrying a
        # canonical artifact filename (which always contains
        # ``_WeekEnding_``) must be dropped.
        record = {
            "body": (
                "some future log message referencing "
                "WR_WR42_WeekEnding_010124_Helper_Jane_abcd.xlsx"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_foremen_top5(self):
        record = {
            "body": (
                "   WR WR42: 12 rows seen, foremen(top5)={'Alice': 5, "
                "'Bob': 3}; exclusions={}"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_forwards_benign_message(self):
        record = {"body": "🛡️ Sentry.io error monitoring initialized (SDK 2.x)"}
        assert gwp.sentry_before_send_log(record, {}) is record

    def test_forwards_empty_body(self):
        record = {"body": ""}
        assert gwp.sentry_before_send_log(record, {}) is record

    def test_forwards_missing_body(self):
        record = {}
        assert gwp.sentry_before_send_log(record, {}) is record

    def test_fails_closed_on_non_string_body(self):
        # Defensive path: non-string bodies are uninspectable, so
        # fail closed (drop) rather than letting them bypass the
        # marker checks.
        record = {"body": 12345}
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_fails_closed_on_falsy_non_string_body(self):
        # Regression guard: falsy non-string bodies must also fail
        # closed. Previously a ``body or ""`` coercion converted
        # these to "" and forwarded them, bypassing the isinstance
        # check.
        for bogus in (0, False, [], {}, (), 0.0):
            record = {"body": bogus}
            assert gwp.sentry_before_send_log(record, {}) is None, bogus

    def test_fails_closed_on_falsy_non_string_attr_body(self):
        # Same regression guard for object-shaped records accessed
        # via getattr().
        class _Rec:
            body = 0

        rec = _Rec()
        assert gwp.sentry_before_send_log(rec, {}) is None

    def test_forwards_object_style_record(self):
        # Some SDK versions may pass an object with attributes rather
        # than a dict; the sanitizer uses ``getattr`` for that shape.
        class _Rec:
            body = "nothing sensitive here"

        rec = _Rec()
        assert gwp.sentry_before_send_log(rec, {}) is rec

    def test_fails_closed_on_exception(self):
        # A bogus record that raises on attribute/key access must not
        # propagate. The sanitizer fails closed (drops the record) so
        # uninspectable payloads never bypass the marker checks.
        class _Boom:
            def __getattribute__(self, name):
                raise RuntimeError("boom")

        rec = _Boom()
        assert gwp.sentry_before_send_log(rec, {}) is None
