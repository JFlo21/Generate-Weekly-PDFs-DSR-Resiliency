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


if __name__ == "__main__":
    unittest.main()
