"""Tests for the Sentry Logs PII sanitizer and env gate parser.

These cover the module-scope helpers added to ``generate_weekly_pdfs``
for the Sentry Logs opt-in: ``sentry_before_send_log``,
``_parse_sentry_enable_logs``, and the ``_PII_LOG_MARKERS`` tuple.
"""

import importlib
import os
from unittest.mock import patch

# Import under a patched environment so a developer's real SENTRY_DSN
# cannot trigger import-time Sentry initialization (and the network /
# side effects it entails) during pytest collection. The init-wiring
# tests below reload the module explicitly with their own env patches.
with patch.dict(os.environ, {"SENTRY_DSN": ""}, clear=False):
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
            "for WR ",
            "Work request ",
            "Job # not found",
            "WR_FILTER applied",
            "EXCLUDE_WRS:",
            "Hash reset requested for specific WRs",
            "_HELPER_",
            "_VACCREW",
            "Totals Validation",
            "total=$",
            "Skip (unchanged",
            "Regenerating ",
            "_WeekEnding_",
            "Generated Excel",
            "Uploaded: ",
            "Upload failed for ",
            "Deleted: ",
            "Purged attachment:",
            "Failed to purge attachment",
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

    def test_drops_work_request_not_found(self):
        # "Work request {wr_num_upload} not found in target sheet"
        record = {
            "body": "⚠️ Work request WR42 not found in target sheet",
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_job_not_found_for_wr(self):
        # "Job # not found for WR {wr_num}. Available columns: ..."
        record = {
            "body": (
                "Job # not found for WR WR42. Available columns: "
                "['Col A', 'Col B']"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_generic_for_wr_line(self):
        # Forward-compat: any future log matching the "... for WR
        # {wr}" shape should be dropped via the "for WR " marker.
        record = {
            "body": "Something unexpected happened for WR WR42 during run",
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_wr_filter_applied(self):
        record = {
            "body": (
                "🔎 WR_FILTER applied (primary + helper + vac_crew): "
                "3/12 groups retained (WR42,WR99,WR123)"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_exclude_wrs_lines(self):
        for body in (
            "🔍 EXCLUDE_WRS check: Attempting to exclude WRs "
            "['WR42', 'WR99'] from 12 groups",
            "🚫 EXCLUDE_WRS applied: 2 groups excluded (WR42,WR99) "
            "- 10 groups remaining",
            "🚫 EXCLUDE_WRS specified but no matching groups found "
            "to exclude (WR42,WR99)",
        ):
            assert gwp.sentry_before_send_log({"body": body}, {}) is None, body

    def test_drops_hash_reset_specific_wrs(self):
        record = {
            "body": (
                "🧨 Hash reset requested for specific WRs: "
                "['WR42', 'WR99', 'WR123']"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_totals_validation_header(self):
        record = {"body": "🧮 Totals Validation (first 10 groups):"}
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_totals_validation_per_group_line(self):
        # group_key shapes:
        #   {week}_{wr}                          → primary
        #   {week}_{wr}_HELPER_{sanitized_name}  → helper
        #   {week}_{wr}_VACCREW                  → vac crew
        for body in (
            "   010124_WR42: rows=5 total=$1234.56",
            "   010124_WR42_HELPER_Jane_Doe: rows=3 total=$789.00",
            "   010124_WR42_VACCREW: rows=2 total=$420.69",
        ):
            assert gwp.sentry_before_send_log({"body": body}, {}) is None, body

    def test_drops_helper_groupkey_catchall(self):
        # Any log body containing the helper group_key infix must be
        # dropped (e.g. error logs that interpolate the raw key).
        record = {
            "body": (
                "❌ Failed to process group "
                "010124_WR42_HELPER_Jane_Doe: KeyError('foo')"
            ),
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_vaccrew_groupkey_catchall(self):
        record = {
            "body": (
                "Synthetic group failure 010124_WR42_VACCREW: boom"
            ),
        }
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

    def test_drops_legacy_wr_only_purge_logs(self):
        # purge_existing_hashed_outputs scans every ``WR_*.xlsx`` and
        # logs the raw name — including short / legacy forms that do
        # not contain the ``_WeekEnding_`` catch-all substring. The
        # `Purged attachment:` and `Failed to purge attachment`
        # prefixes must drop those records regardless of filename
        # shape.
        for body in (
            "🗑️ Purged attachment: WR_42.xlsx",
            "🗑️ Purged attachment: WR_WR42_WeekEnding_010124_abcd.xlsx",
            "⚠️ Failed to purge attachment WR_42.xlsx: boom",
            "⚠️ Failed to purge attachment WR_WR99_Legacy_Name.xlsx: timeout",
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

    def test_drops_case_insensitive_body(self):
        # Case-sensitive ``in`` would have let these through. The
        # sanitizer now matches against the lowercase mirror.
        for body in (
            "row data sample: WR=WR42, Price=$100.00",
            "RATE RECALCULATION: CU 'X' not found",
            "FOREMAN ASSIGNMENT: Using 'Alice'",
            "some future log: _weekending_010124_abcd.xlsx",
        ):
            assert gwp.sentry_before_send_log({"body": body}, {}) is None, body

    def test_drops_pii_in_string_attribute(self):
        # Sentry log records may ship context via ``attributes``;
        # body-only scanning would miss PII forwarded that way.
        record = {
            "body": "benign message",
            "attributes": {
                "source": "pipeline",
                "detail": "HELPER ROW DETECTED [Row 5]: WR=WR42",
            },
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_drops_pii_in_wrapped_attribute(self):
        # SDK-wrapped attribute shape: ``{"value": ..., "type": ...}``.
        record = {
            "body": "benign message",
            "attributes": {
                "custom.detail": {
                    "value": "Rate recalculation: CU not found",
                    "type": "string",
                },
            },
        }
        assert gwp.sentry_before_send_log(record, {}) is None

    def test_forwards_benign_attributes(self):
        # Attributes containing no PII markers must not cause a drop.
        record = {
            "body": "startup complete",
            "attributes": {"component": "excel_generator", "retries": 3},
        }
        assert gwp.sentry_before_send_log(record, {}) is record


class TestScrubFrameLocals:
    """Redact PII from ``event['exception'|'threads'].values[*].stacktrace.frames[*].vars``."""

    def _event_with_vars(self, vars_):
        return {
            "exception": {
                "values": [
                    {
                        "stacktrace": {
                            "frames": [
                                {"filename": "generate_weekly_pdfs.py", "vars": vars_},
                            ],
                        },
                    },
                ],
            },
        }

    def _frame_vars(self, event):
        return event["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]

    def test_scrubs_row_dict_by_name(self):
        event = self._event_with_vars({
            "row": {"Work Request #": "WR42", "Foreman": "Alice"},
            "benign_count": 5,
        })
        gwp._scrub_frame_locals(event)
        vars_ = self._frame_vars(event)
        assert vars_["row"] == gwp._SCRUBBED_SENTINEL
        assert vars_["benign_count"] == 5

    def test_scrubs_pii_value_by_content(self):
        # Variable name doesn't match a hint but value embeds WR.
        event = self._event_with_vars({
            "message": "Processing WR42 for Alice",
            "count": 7,
        })
        gwp._scrub_frame_locals(event)
        vars_ = self._frame_vars(event)
        assert vars_["message"] == gwp._SCRUBBED_SENTINEL
        assert vars_["count"] == 7

    def test_scrubs_dollar_price_value(self):
        event = self._event_with_vars({"audit_note": "delta $1,234.56"})
        gwp._scrub_frame_locals(event)
        assert (
            self._frame_vars(event)["audit_note"]
            == gwp._SCRUBBED_SENTINEL
        )

    def test_walks_threads_container(self):
        event = {
            "threads": {
                "values": [
                    {
                        "stacktrace": {
                            "frames": [
                                {"vars": {"foreman": "Bob"}},
                            ],
                        },
                    },
                ],
            },
        }
        gwp._scrub_frame_locals(event)
        assert (
            event["threads"]["values"][0]["stacktrace"]["frames"][0]
            ["vars"]["foreman"] == gwp._SCRUBBED_SENTINEL
        )

    def test_no_raise_on_malformed_event(self):
        # Invalid shapes must not crash the send path.
        for event in (None, "not a dict", {}, {"exception": None}):
            gwp._scrub_frame_locals(event)

    def test_preserves_non_pii_frames(self):
        event = self._event_with_vars({
            "response_code": 500,
            "elapsed_ms": 1234,
            "flag": True,
        })
        gwp._scrub_frame_locals(event)
        vars_ = self._frame_vars(event)
        assert vars_["response_code"] == 500
        assert vars_["elapsed_ms"] == 1234
        assert vars_["flag"] is True


def _reload_gwp_with_env(env_overrides):
    """Reload ``generate_weekly_pdfs`` under the given env overrides
    with ``sentry_sdk.init`` patched. Returns the mock (so the caller
    can inspect ``call_args``) and the freshly reloaded module.

    The module's Sentry init block runs at import time inside
    ``if SENTRY_DSN:``, so reloading with a fake DSN while the real
    ``sentry_sdk.init`` is replaced by a ``MagicMock`` is the only way
    to verify the init kwargs without a live DSN.
    """
    with patch.dict(os.environ, env_overrides, clear=False):
        with patch("sentry_sdk.init") as mock_init:
            importlib.reload(gwp)
            return mock_init, gwp


class TestSentryInitWiring:
    """Integration-style tests for the kwargs passed to ``sentry_sdk.init``.

    The unit tests for ``sentry_before_send_log`` and
    ``_parse_sentry_enable_logs`` cover the helpers in isolation, but
    neither exercises the real init block (which only runs when
    ``SENTRY_DSN`` is set). These tests guard against typos / SDK
    keyword mismatches in the ``sentry_sdk.init(...)`` call itself:
    ``enable_logs`` must honor the env gate and ``before_send_log``
    must point at the sanitizer.
    """

    @classmethod
    def teardown_class(cls):
        # Restore the module to its unpatched, DSN-less state so any
        # subsequent tests in the run see the production code path.
        with patch.dict(
            os.environ,
            {"SENTRY_DSN": "", "SENTRY_ENABLE_LOGS": ""},
            clear=False,
        ):
            importlib.reload(gwp)

    def test_init_called_when_dsn_is_set(self):
        mock_init, _ = _reload_gwp_with_env({
            "SENTRY_DSN": "https://fake@localhost/0",
            "SENTRY_ENABLE_LOGS": "",
        })
        assert mock_init.called, "sentry_sdk.init should run when SENTRY_DSN is set"

    def test_enable_logs_defaults_to_false(self):
        mock_init, _ = _reload_gwp_with_env({
            "SENTRY_DSN": "https://fake@localhost/0",
            "SENTRY_ENABLE_LOGS": "",
        })
        kwargs = mock_init.call_args.kwargs
        assert "enable_logs" in kwargs, (
            "sentry_sdk.init must receive the enable_logs keyword"
        )
        assert kwargs["enable_logs"] is False

    def test_enable_logs_honors_env_gate_true(self):
        mock_init, _ = _reload_gwp_with_env({
            "SENTRY_DSN": "https://fake@localhost/0",
            "SENTRY_ENABLE_LOGS": "true",
        })
        kwargs = mock_init.call_args.kwargs
        assert kwargs["enable_logs"] is True

    def test_enable_logs_matches_parse_helper(self):
        # Sanity: whatever enable_logs value is wired into init must
        # equal the parser's opinion for the same env input. This
        # catches drift if the env var name or parser is ever changed
        # without updating the init call site.
        for raw, expected in (
            ("", False),
            ("0", False),
            ("false", False),
            ("1", True),
            ("true", True),
            ("On", True),
        ):
            mock_init, reloaded = _reload_gwp_with_env({
                "SENTRY_DSN": "https://fake@localhost/0",
                "SENTRY_ENABLE_LOGS": raw,
            })
            kwargs = mock_init.call_args.kwargs
            assert kwargs["enable_logs"] is expected, raw
            assert (
                kwargs["enable_logs"]
                == reloaded._parse_sentry_enable_logs(raw)
            ), raw

    def test_before_send_log_is_sanitizer(self):
        mock_init, reloaded = _reload_gwp_with_env({
            "SENTRY_DSN": "https://fake@localhost/0",
        })
        kwargs = mock_init.call_args.kwargs
        assert "before_send_log" in kwargs, (
            "sentry_sdk.init must receive the before_send_log keyword"
        )
        # Guard against a typo / stale reference: the hook must be the
        # module-scope sanitizer so the PII markers apply.
        assert kwargs["before_send_log"] is reloaded.sentry_before_send_log

    def test_installed_sdk_accepts_enable_logs_and_before_send_log(self):
        """Verify the *real* sentry_sdk.init accepts both new kwargs.

        The other tests in this class patch ``sentry_sdk.init`` with a
        ``MagicMock``, which happily swallows any keyword. If the
        installed SDK ever dropped / renamed ``enable_logs`` or
        ``before_send_log`` (or pinned to a version that predates
        them), production would raise ``TypeError`` at init time but
        the mocked tests above would still pass. This test calls the
        real SDK with ``dsn=None`` (no transport, no network) to surface
        a keyword mismatch at test time.
        """
        import sentry_sdk

        # ``dsn=None`` disables the transport — no data is sent.
        # A TypeError on an unknown kwarg would fail the test.
        sentry_sdk.init(
            dsn=None,
            enable_logs=False,
            before_send_log=lambda record, hint: record,
        )
