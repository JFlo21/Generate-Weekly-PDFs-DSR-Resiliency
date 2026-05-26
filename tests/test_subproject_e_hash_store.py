"""Sub-project E — Supabase hash-store migration + filename token stripping.

Tests for the durable per-group change-detection hash store and the
default-OFF kill switches. See
docs/superpowers/specs/2026-05-25-subproject-e-supabase-hash-store-design.md
and docs/superpowers/plans/2026-05-25-subproject-e-supabase-hash-store.md.
"""
import datetime
import inspect
import os
import pathlib
import tempfile
import unittest
from unittest import mock

from tests.test_billing_audit_shadow import _ensure_smartsheet_mocked

_ensure_smartsheet_mocked()

import generate_weekly_pdfs as gwp  # noqa: E402


class TestConfigFlags(unittest.TestCase):
    """Task 1: the two E kill switches exist with the right defaults."""

    def test_write_flag_default_on_is_bool(self):
        self.assertIsInstance(gwp.SUPABASE_HASH_STORE_WRITE_ENABLED, bool)

    def test_authoritative_flag_is_bool(self):
        self.assertIsInstance(gwp.SUPABASE_HASH_STORE_AUTHORITATIVE, bool)

    def test_banner_logs_both_flags(self):
        src = inspect.getsource(gwp)
        self.assertIn("📋 SUPABASE_HASH_STORE_WRITE_ENABLED=", src)
        self.assertIn("📋 SUPABASE_HASH_STORE_AUTHORITATIVE=", src)


class TestSchemaHasGroupContentHash(unittest.TestCase):
    """Task 1: schema.sql defines the durable per-group hash table."""

    def test_schema_defines_group_content_hash_table(self):
        sql = pathlib.Path("billing_audit/schema.sql").read_text(encoding="utf-8")
        self.assertIn("billing_audit.group_content_hash", sql)
        for col in (
            "wr", "week_ending", "variant", "identifier",
            "content_hash", "updated_at",
        ):
            self.assertIn(col, sql)


class TestBuildGroupIdentityCleanNames(unittest.TestCase):
    """Task 4 (KEY RISK): build_group_identity parses token-LESS clean
    names (no _<timestamp>/_<hash>) for every variant AND still parses
    legacy token-bearing names (both coexist during migration)."""

    def _id(self, name):
        return gwp.build_group_identity(name)

    def test_clean_bare_primary(self):
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926.xlsx"),
            ("90001", "041926", "primary", None),
        )

    def test_clean_primary_user(self):
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926_User_Jane_Smith.xlsx"),
            ("90001", "041926", "primary", "Jane_Smith"),
        )

    def test_clean_helper(self):
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926_Helper_Bob.xlsx"),
            ("90001", "041926", "helper", "Bob"),
        )

    def test_clean_helper_underscored_name(self):
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926_Helper_Bob_Jones.xlsx"),
            ("90001", "041926", "helper", "Bob_Jones"),
        )

    def test_clean_vaccrew_named(self):
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926_VacCrew_Vic.xlsx"),
            ("90001", "041926", "vac_crew", "Vic"),
        )

    def test_clean_vaccrew_bare(self):
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926_VacCrew.xlsx"),
            ("90001", "041926", "vac_crew", ""),
        )

    def test_clean_reducedsub_user(self):
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926_ReducedSub_User_Sue.xlsx"),
            ("90001", "041926", "reduced_sub", "Sue"),
        )

    def test_clean_aepbillable_user(self):
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926_AEPBillable_User_Sue.xlsx"),
            ("90001", "041926", "aep_billable", "Sue"),
        )

    def test_clean_reducedsub_helper(self):
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926_ReducedSub_Helper_Bob.xlsx"),
            ("90001", "041926", "reduced_sub_helper", "Bob"),
        )

    def test_clean_legacy_unpartitioned_reducedsub(self):
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926_ReducedSub.xlsx"),
            ("90001", "041926", "reduced_sub", ""),
        )

    def test_clean_identifier_with_reserved_word_in_name(self):
        # Foreman literally named "Pat Helper" -> sanitized "Pat_Helper".
        # Clean name: primary _User_ partition; identifier keeps both
        # segments and variant stays 'primary' (earliest reserved token
        # is 'User').
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926_User_Pat_Helper.xlsx"),
            ("90001", "041926", "primary", "Pat_Helper"),
        )

    def test_clean_identifier_containing_weekending_token(self):
        # Pathological clean name: identifier sanitizes to
        # WeekEnding_<6digits>. The leftmost-weak structural WeekEnding
        # must win; the identifier round-trips intact.
        self.assertEqual(
            self._id("WR_90001_WeekEnding_041926_User_WeekEnding_041926.xlsx"),
            ("90001", "041926", "primary", "WeekEnding_041926"),
        )

    # --- Legacy token-bearing names MUST still parse (coexistence) ---

    def test_legacy_tokened_primary_user(self):
        self.assertEqual(
            self._id(
                "WR_90001_WeekEnding_041926_120000_User_Jane_Smith_"
                "abcdef0123456789.xlsx"),
            ("90001", "041926", "primary", "Jane_Smith"),
        )

    def test_legacy_tokened_helper(self):
        self.assertEqual(
            self._id(
                "WR_90001_WeekEnding_041926_120000_Helper_Bob_Jones_"
                "abcdef0123456789.xlsx"),
            ("90001", "041926", "helper", "Bob_Jones"),
        )

    def test_legacy_tokened_vaccrew_bare(self):
        self.assertEqual(
            self._id(
                "WR_90001_WeekEnding_041926_120000_VacCrew_"
                "abcdef0123456789.xlsx"),
            ("90001", "041926", "vac_crew", ""),
        )

    def test_legacy_tokened_reducedsub_helper(self):
        self.assertEqual(
            self._id(
                "WR_90001_WeekEnding_041926_120000_ReducedSub_Helper_Bob_"
                "abcdef0123456789.xlsx"),
            ("90001", "041926", "reduced_sub_helper", "Bob"),
        )

    def test_legacy_no_timestamp_bare_primary(self):
        # Oldest format: WR_{wr}_WeekEnding_{week}_{hash}.xlsx.
        self.assertEqual(
            self._id(
                "WR_90001_WeekEnding_041926_abcdef0123456789.xlsx"),
            ("90001", "041926", "primary", None),
        )


class TestCleanFilename(unittest.TestCase):
    """Task 5: when SUPABASE_HASH_STORE_AUTHORITATIVE is on, generate_excel
    produces a deterministic clean name (no _<timestamp>/_<hash>); when off
    it keeps the legacy timestamp+hash tokens (byte-identical to today)."""

    def setUp(self):
        self._saved = {
            'auth': gwp.SUPABASE_HASH_STORE_AUTHORITATIVE,
            'attr': gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED,
            'mode': gwp.RES_GROUPING_MODE,
            'out': gwp.OUTPUT_FOLDER,
        }
        self._tmp = tempfile.TemporaryDirectory()
        gwp.OUTPUT_FOLDER = self._tmp.name
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = True
        gwp.RES_GROUPING_MODE = 'both'

    def tearDown(self):
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = self._saved['auth']
        gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED = self._saved['attr']
        gwp.RES_GROUPING_MODE = self._saved['mode']
        gwp.OUTPUT_FOLDER = self._saved['out']
        self._tmp.cleanup()

    def _row(self, foreman="PF"):
        return {
            'Work Request #': '90001',
            'Weekly Reference Logged Date': '2026-04-19',
            'Units Completed?': True,
            'Units Total Price': '$100.00',
            'CU': 'XYZ',
            'Work Type': 'Install',
            'Quantity': 1,
            'Customer Name': 'TestCustomer',
            'Foreman': foreman,
            'Dept #': '500',
            'Job #': 'J-1',
            '__effective_user': foreman,
            '__current_foreman': foreman,
            '__variant': 'primary',
            '__week_ending_date': datetime.datetime(2026, 4, 19),
        }

    def _name(self):
        result = gwp.generate_excel(
            '041926_90001', [self._row()],
            datetime.datetime(2026, 4, 19), data_hash='deadbeefcafe0001',
        )
        return os.path.basename(result[0])

    def test_authoritative_on_strips_timestamp_and_hash(self):
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = True
        name = self._name()
        self.assertEqual(name, 'WR_90001_WeekEnding_041926_User_PF.xlsx')

    def test_authoritative_off_keeps_tokens(self):
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = False
        name = self._name()
        self.assertIn('deadbeefcafe0001', name)
        self.assertIn('_User_PF', name)
        self.assertTrue(name.endswith('.xlsx'))

    def test_clean_name_round_trips_through_parser(self):
        # The clean name generate_excel emits must parse back to the
        # same identity tuple via build_group_identity (Task 4).
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = True
        name = self._name()
        self.assertEqual(
            gwp.build_group_identity(name),
            ('90001', '041926', 'primary', 'PF'),
        )


class TestShadowWrite(unittest.TestCase):
    """Task 6: the generation path shadow-writes the per-group hash to
    Supabase, gated on SUPABASE_HASH_STORE_WRITE_ENABLED + fail-safe."""

    def setUp(self):
        self.src = inspect.getsource(gwp)

    def test_upsert_call_present(self):
        self.assertIn("upsert_group_hash(", self.src)

    def test_upsert_gated_on_write_flag(self):
        self.assertRegex(
            self.src,
            r"SUPABASE_HASH_STORE_WRITE_ENABLED[\s\S]{0,500}"
            r"upsert_group_hash\(",
        )

    def test_upsert_uses_iso_week(self):
        # The shadow write must pass the ISO week-ending date (the DATE
        # column representation), not the MMDDYY week_raw string.
        self.assertRegex(
            self.src,
            r"upsert_group_hash\(\s*[\s\S]{0,80}week_iso",
        )


class TestAuthoritativeSkipGate(unittest.TestCase):
    """Task 7: when authoritative, the unchanged decision reads Supabase
    (json fallback on outage; regenerate on miss). The pure helper
    _resolve_unchanged_for_skip makes the decision unit-testable."""

    def setUp(self):
        self._saved = {
            'auth': gwp.SUPABASE_HASH_STORE_AUTHORITATIVE,
            'avail': gwp.BILLING_AUDIT_AVAILABLE,
            'test': gwp.TEST_MODE,
        }

    def tearDown(self):
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = self._saved['auth']
        gwp.BILLING_AUDIT_AVAILABLE = self._saved['avail']
        gwp.TEST_MODE = self._saved['test']

    # ── Source-level guards ────────────────────────────────────────────
    def test_gate_reads_supabase_when_authoritative(self):
        src = inspect.getsource(gwp)
        self.assertRegex(
            src,
            r"SUPABASE_HASH_STORE_AUTHORITATIVE[\s\S]{0,600}"
            r"lookup_group_hash\(",
        )

    def test_json_fallback_remains_reachable(self):
        # The helper must still consult the local hash_history cache.
        src = inspect.getsource(gwp._resolve_unchanged_for_skip)
        self.assertIn("hash_history.get(history_key)", src)

    def test_attachment_required_preserved(self):
        self.assertIn("ATTACHMENT_REQUIRED_FOR_SKIP", inspect.getsource(gwp))

    # ── Behavioral: _resolve_unchanged_for_skip decision table ─────────
    def _resolve(self, **kw):
        defaults = dict(
            history_key="90001|041926|primary|",
            data_hash="h", hash_history={}, wr_num="90001",
            week_iso="2026-04-19", variant="primary", identifier="",
        )
        defaults.update(kw)
        return gwp._resolve_unchanged_for_skip(**defaults)

    def _set_authoritative(self):
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = True
        gwp.BILLING_AUDIT_AVAILABLE = True
        gwp.TEST_MODE = False

    def test_authoritative_success_match_is_unchanged(self):
        self._set_authoritative()
        with mock.patch.object(
            gwp._billing_audit_writer, "lookup_group_hash",
            return_value=("h", "success"),
        ):
            self.assertTrue(self._resolve(data_hash="h"))

    def test_authoritative_success_mismatch_is_changed(self):
        self._set_authoritative()
        with mock.patch.object(
            gwp._billing_audit_writer, "lookup_group_hash",
            return_value=("OTHER", "success"),
        ):
            self.assertFalse(self._resolve(data_hash="h"))

    def test_authoritative_no_row_regenerates(self):
        self._set_authoritative()
        with mock.patch.object(
            gwp._billing_audit_writer, "lookup_group_hash",
            return_value=(None, "no_row"),
        ):
            # Even with a matching json cache entry, a no_row in the
            # authoritative store means "never durably stored" -> regenerate.
            self.assertFalse(self._resolve(
                data_hash="h",
                hash_history={"90001|041926|primary|": {"hash": "h"}},
            ))

    def test_authoritative_fetch_failure_falls_back_to_json_true(self):
        self._set_authoritative()
        with mock.patch.object(
            gwp._billing_audit_writer, "lookup_group_hash",
            return_value=(None, "fetch_failure"),
        ):
            self.assertTrue(self._resolve(
                data_hash="h",
                hash_history={"90001|041926|primary|": {"hash": "h"}},
            ))

    def test_authoritative_fetch_failure_falls_back_to_json_false(self):
        self._set_authoritative()
        with mock.patch.object(
            gwp._billing_audit_writer, "lookup_group_hash",
            return_value=(None, "fetch_failure"),
        ):
            self.assertFalse(self._resolve(
                data_hash="h",
                hash_history={"90001|041926|primary|": {"hash": "STALE"}},
            ))

    def test_authoritative_unavailable_falls_back_to_json(self):
        self._set_authoritative()
        with mock.patch.object(
            gwp._billing_audit_writer, "lookup_group_hash",
            return_value=(None, "unavailable"),
        ):
            self.assertTrue(self._resolve(
                data_hash="h",
                hash_history={"90001|041926|primary|": {"hash": "h"}},
            ))

    def test_not_authoritative_uses_json_only(self):
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = False
        gwp.BILLING_AUDIT_AVAILABLE = True
        gwp.TEST_MODE = False
        # lookup_group_hash must NOT be consulted when not authoritative.
        with mock.patch.object(
            gwp._billing_audit_writer, "lookup_group_hash",
            side_effect=AssertionError("should not read Supabase"),
        ):
            self.assertTrue(self._resolve(
                data_hash="h",
                hash_history={"90001|041926|primary|": {"hash": "h"}},
            ))
            self.assertFalse(self._resolve(
                data_hash="h", hash_history={}))


class _FakeAtt:
    def __init__(self, name, id_):
        self.name = name
        self.id = id_


class TestDeleteOldCleanNames(unittest.TestCase):
    """Task 8: delete_old_excel_attachments must not rely on the filename
    hash short-circuit when authoritative (clean names carry no hash);
    identity-based replacement of the prior attachment still runs."""

    def setUp(self):
        self._saved_auth = gwp.SUPABASE_HASH_STORE_AUTHORITATIVE

    def tearDown(self):
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = self._saved_auth

    def _client(self):
        c = mock.Mock()
        c.Attachments.delete_attachment.return_value = None
        return c

    def _row(self):
        r = mock.Mock()
        r.id = 99
        return r

    def test_source_references_authoritative_flag(self):
        src = inspect.getsource(gwp.delete_old_excel_attachments)
        self.assertIn("SUPABASE_HASH_STORE_AUTHORITATIVE", src)

    def test_authoritative_off_legacy_hash_skip_preserved(self):
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = False
        att = _FakeAtt(
            "WR_90001_WeekEnding_041926_120000_deadbeefcafe0001.xlsx", 1)
        client = self._client()
        deleted, skipped = gwp.delete_old_excel_attachments(
            client, 123, self._row(), "90001", "041926",
            "deadbeefcafe0001", variant="primary", identifier=None,
            cached_attachments=[att])
        self.assertEqual((deleted, skipped), (0, True))
        client.Attachments.delete_attachment.assert_not_called()

    def test_authoritative_on_skips_filename_hash_short_circuit(self):
        # A legacy token-named file whose hash matches must NOT short-
        # circuit when authoritative — the durable gate decided upstream;
        # here the prior attachment is replaced.
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = True
        att = _FakeAtt(
            "WR_90001_WeekEnding_041926_120000_deadbeefcafe0001.xlsx", 1)
        client = self._client()
        deleted, skipped = gwp.delete_old_excel_attachments(
            client, 123, self._row(), "90001", "041926",
            "deadbeefcafe0001", variant="primary", identifier=None,
            cached_attachments=[att])
        self.assertFalse(skipped)
        self.assertEqual(deleted, 1)
        client.Attachments.delete_attachment.assert_called_once_with(123, 1)

    def test_authoritative_on_clean_name_identity_replacement(self):
        # A clean prior attachment for the same identity is replaced.
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = True
        clean = _FakeAtt("WR_90001_WeekEnding_041926_User_PF.xlsx", 7)
        client = self._client()
        deleted, skipped = gwp.delete_old_excel_attachments(
            client, 123, self._row(), "90001", "041926",
            "newhash0000000000", variant="primary", identifier="PF",
            cached_attachments=[clean])
        self.assertFalse(skipped)
        self.assertEqual(deleted, 1)
        client.Attachments.delete_attachment.assert_called_once_with(123, 7)

    def test_extract_hash_returns_none_for_clean_name(self):
        self.assertIsNone(
            gwp.extract_data_hash_from_filename(
                "WR_90001_WeekEnding_041926_User_PF.xlsx"))


class TestMigrationCutover(unittest.TestCase):
    """Task 9: the no-bulk-migration self-healing cutover. The first
    authoritative run sees an empty store and regenerates everything once
    (populating it); subsequent runs skip; an outage degrades to the json
    cache; clean names carry no filename hash."""

    def setUp(self):
        self._saved = (
            gwp.SUPABASE_HASH_STORE_AUTHORITATIVE,
            gwp.BILLING_AUDIT_AVAILABLE,
            gwp.TEST_MODE,
        )

    def tearDown(self):
        (gwp.SUPABASE_HASH_STORE_AUTHORITATIVE,
         gwp.BILLING_AUDIT_AVAILABLE,
         gwp.TEST_MODE) = self._saved

    def _authoritative(self):
        gwp.SUPABASE_HASH_STORE_AUTHORITATIVE = True
        gwp.BILLING_AUDIT_AVAILABLE = True
        gwp.TEST_MODE = False

    def test_first_authoritative_run_regenerates_on_empty_store(self):
        self._authoritative()
        with mock.patch.object(
            gwp._billing_audit_writer, "lookup_group_hash",
            return_value=(None, "no_row"),
        ):
            self.assertFalse(gwp._resolve_unchanged_for_skip(
                "90001|041926|primary|", "h", {},
                "90001", "2026-04-19", "primary", ""))

    def test_shadow_populated_store_allows_skip(self):
        self._authoritative()
        with mock.patch.object(
            gwp._billing_audit_writer, "lookup_group_hash",
            return_value=("h", "success"),
        ):
            self.assertTrue(gwp._resolve_unchanged_for_skip(
                "90001|041926|primary|", "h", {},
                "90001", "2026-04-19", "primary", ""))

    def test_outage_during_cutover_falls_back_to_json(self):
        self._authoritative()
        with mock.patch.object(
            gwp._billing_audit_writer, "lookup_group_hash",
            return_value=(None, "fetch_failure"),
        ):
            # Cache miss -> regenerate (safe).
            self.assertFalse(gwp._resolve_unchanged_for_skip(
                "90001|041926|primary|", "h", {},
                "90001", "2026-04-19", "primary", ""))
            # Cache hit -> skip (the json cache survives a brief outage).
            self.assertTrue(gwp._resolve_unchanged_for_skip(
                "90001|041926|primary|", "h",
                {"90001|041926|primary|": {"hash": "h"}},
                "90001", "2026-04-19", "primary", ""))

    def test_extract_hash_returns_none_for_clean_name(self):
        self.assertIsNone(gwp.extract_data_hash_from_filename(
            "WR_90001_WeekEnding_041926_User_PF.xlsx"))


if __name__ == "__main__":
    unittest.main()
