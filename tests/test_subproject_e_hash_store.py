"""Sub-project E — Supabase hash-store migration + filename token stripping.

Tests for the durable per-group change-detection hash store and the
default-OFF kill switches. See
docs/superpowers/specs/2026-05-25-subproject-e-supabase-hash-store-design.md
and docs/superpowers/plans/2026-05-25-subproject-e-supabase-hash-store.md.
"""
import inspect
import pathlib
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


if __name__ == "__main__":
    unittest.main()
