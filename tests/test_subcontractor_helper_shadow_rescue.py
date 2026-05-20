"""Phase 1.1 end-to-end + regression tests (Plan 01.1-05).

D-20 / Pitfall 6 closure: drives ``_subcontractor_rescue_price`` +
``group_source_rows`` + ``cleanup_untracked_sheet_attachments`` +
``_run_phase_1_1_hash_prune`` on synthetic Smartsheet payloads that
exercise all four upstream fixes (Bug A pre-acceptance rescue,
Bug B1 partitioning, Bug B2 cleanup whitelist, Bug C claim-history
attribution) AND the SUB-12 hash-history one-time prune.

Closes the structural weakness of
``tests/test_subcontractor_pricing.py::TestHelperShadowVariantFileIdentifier``
which is a mirror class — it bypasses both the upstream classifier
and the has_price gate, so it passes EVEN IF Bug A or Bug B1 is
broken in production (the failure mode that allowed Phase 1 to
ship with both bugs latent).

Per the Phase 1.1 Living Ledger entry rule (d): any plan that fixes
a row-flow bug — acceptance gate, ``group_source_rows``,
``generate_excel`` — MUST add at least one true end-to-end test
driving the full pipeline. Static mirror classes don't count.
"""

from __future__ import annotations

import datetime
import importlib
import inspect
import json
import os
import pathlib
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Reuse fixture helpers from the existing billing_audit test file.
# Co-locating them in this Phase 1.1 file would duplicate the chained-
# mock builder; importing keeps the SoR single (see PATTERNS.md
# anchor 6 — "structural mirror" pattern).
from tests.test_billing_audit_shadow import (
    _reset_all,
    _ensure_smartsheet_mocked,
    _make_fake_supabase_client,
    _fake_rpc_response,
)

_ensure_smartsheet_mocked()
import generate_weekly_pdfs  # noqa: E402 — must come after mock injection


def _safe_reload_gwp():
    """Reload generate_weekly_pdfs.py with Sentry init suppressed.

    Mirrors the pattern in ``tests/test_performance_optimizations.py``
    — a dev shell with a real ``SENTRY_DSN`` would otherwise fire a
    live Sentry init on every reload. Phase 1.1 introduces two new
    module-level kill switches that the tests need to flip via env
    vars, so reload-with-suppression is the canonical setup pattern.
    """
    with mock.patch.dict(os.environ, {"SENTRY_DSN": ""}, clear=False), \
         mock.patch("sentry_sdk.init"):
        importlib.reload(generate_weekly_pdfs)


class TestEndToEndPipeline(unittest.TestCase):
    """D-20 / Pitfall 6: pipeline coverage for the four upstream fixes.

    Exercises SUB-08 (Bug A), SUB-09 (Bug B1), SUB-11 (Bug C) through
    real production code paths. The synthetic Smartsheet payload
    travels through ``_subcontractor_rescue_price`` (post-rescue
    price simulated for non-Bug-A tests) and ``group_source_rows``
    (variant emission + per-row attribution). Assertions are on
    observable outputs (group dict keys) NOT on internal helper
    return values.
    """

    _SUB_SHEET_ID = 8162920222379908
    _NON_SUB_SHEET_ID = 9999999999

    def setUp(self):
        _reset_all()
        # Snapshot module state so mutations don't leak across tests
        self._orig_enabled = generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED
        self._orig_bug_a = generate_weekly_pdfs.SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED
        self._orig_bug_c = generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED
        self._orig_sub_ids = set(generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS)
        self._orig_orig_ids = set(generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS)
        self._orig_rates = dict(generate_weekly_pdfs._SUBCONTRACTOR_RATES)
        # Defaults for the test scenarios
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED = True
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED = True
        generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED = True
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.add(self._SUB_SHEET_ID)
        # Seed a rate so Bug A rescue can fire
        generate_weekly_pdfs._SUBCONTRACTOR_RATES['ANC-M'] = {
            'new_install_price': 75.0,
            'reduced_install_price': 50.0,
            'new_remove_price': 60.0,
            'reduced_remove_price': 45.0,
            'new_transfer_price': 80.0,
            'reduced_transfer_price': 55.0,
        }

    def tearDown(self):
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_VARIANTS_ENABLED = self._orig_enabled
        generate_weekly_pdfs.SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED = self._orig_bug_a
        generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED = self._orig_bug_c
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_SUB_IDS.update(self._orig_sub_ids)
        generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS.clear()
        generate_weekly_pdfs._FOLDER_DISCOVERED_ORIG_IDS.update(self._orig_orig_ids)
        generate_weekly_pdfs._SUBCONTRACTOR_RATES.clear()
        generate_weekly_pdfs._SUBCONTRACTOR_RATES.update(self._orig_rates)
        _reset_all()

    def _make_synth_helper_row(
        self,
        wr='91467680',
        helper_foreman='ReplacementForeman',
        units_price='$100.00',
        snapshot='2026-04-19',
        row_id=12345,
        source_sheet_id=None,
    ):
        """Synthetic helper row that triggers Bug B1 partitioning + Bug C
        attribution. ``units_price`` defaults to ``'$100.00'`` (post-rescue
        state — Bug A's rescue is upstream of ``group_source_rows`` so the
        downstream tests simulate the post-rescue row directly per
        RESEARCH.md Pitfall 6: "the test can drive the rescue helper
        independently if needed").
        """
        return {
            '__row_id': row_id,
            'Work Request #': wr,
            'Weekly Reference Logged Date': '2026-04-19',
            'Snapshot Date': snapshot,
            'Units Completed?': True,
            'Foreman Helping?': helper_foreman,
            'Helping Foreman Completed Unit?': True,
            'Units Total Price': units_price,
            'CU': 'ANC-M',
            'Work Type': 'Inst',
            'Quantity': 2,
            '__effective_user': 'PrimaryForeman',
            '__assignment_method': 'FOREMAN_COLUMN',
            '__is_helper_row': True,
            '__helper_foreman': helper_foreman,
            '__helper_dept': '500',
            '__helper_job': 'JOB-A',
            '__is_vac_crew': False,
            '__source_sheet_id': source_sheet_id or self._SUB_SHEET_ID,
        }

    def _make_synth_non_helper_row(
        self,
        wr='91467680',
        units_price='$100.00',
        snapshot='2026-04-19',
        source_sheet_id=None,
    ):
        """Synthetic non-helper subcontractor row for Bug B1 partitioning."""
        return {
            'Work Request #': wr,
            'Weekly Reference Logged Date': '2026-04-19',
            'Snapshot Date': snapshot,
            'Units Completed?': True,
            'Units Total Price': units_price,
            'CU': 'ANC-M',
            'Work Type': 'Inst',
            'Quantity': 2,
            '__effective_user': 'PrimaryForeman',
            '__assignment_method': 'FOREMAN_COLUMN',
            '__is_helper_row': False,
            '__helper_foreman': '',
            '__helper_dept': '',
            '__helper_job': '',
            '__is_vac_crew': False,
            '__source_sheet_id': source_sheet_id or self._SUB_SHEET_ID,
        }

    # ─── Bug A rescue ────────────────────────────────────────────

    def test_bug_a_rescue_returns_expected_price_for_install(self):
        """Bug A rescue: reduced_install × qty for Inst work-type."""
        rescued = generate_weekly_pdfs._subcontractor_rescue_price({
            'CU': 'ANC-M',
            'Work Type': 'Inst',
            'Quantity': 2,
        })
        self.assertEqual(rescued, 100.0)

    def test_bug_a_rescue_returns_zero_for_unknown_cu(self):
        """Bug A rescue: unknown CU falls through to 0.0 (caller drops row)."""
        rescued = generate_weekly_pdfs._subcontractor_rescue_price({
            'CU': 'UNKNOWN-XYZ',
            'Work Type': 'Inst',
            'Quantity': 2,
        })
        self.assertEqual(rescued, 0.0)

    def test_bug_a_rescue_returns_zero_for_unknown_work_type(self):
        rescued = generate_weekly_pdfs._subcontractor_rescue_price({
            'CU': 'ANC-M',
            'Work Type': 'BogusOp',
            'Quantity': 2,
        })
        self.assertEqual(rescued, 0.0)

    # ─── Bug B1 partitioning ─────────────────────────────────────

    def test_subcontractor_non_helper_row_only_emits_variant_keys(self):
        """Bug B1 partitioning core assertion."""
        row = self._make_synth_non_helper_row(wr='WR_B1')
        groups = generate_weekly_pdfs.group_source_rows([row])
        keys = list(groups.keys())
        # NO legacy primary key
        legacy_primary = '041926_WR_B1'
        self.assertNotIn(
            legacy_primary, keys,
            f"Bug B1 partitioning: subcontractor non-helper row must "
            f"NOT emit legacy primary key; got: {keys}",
        )
        # Variant keys must be present
        self.assertTrue(
            any('REDUCEDSUB' in k and 'HELPER' not in k for k in keys),
            f"Bug B1 must still emit _REDUCEDSUB; got: {keys}",
        )

    def test_non_subcontractor_helper_row_unchanged(self):
        """D-15 scope: non-subcontractor helper rows preserve Phase 1 behavior."""
        row = self._make_synth_helper_row(source_sheet_id=self._NON_SUB_SHEET_ID)
        # Patch lookup_attribution to assert it's never called for non-sub rows
        with mock.patch(
            'billing_audit.writer.lookup_attribution',
            return_value={'helper': 'FrozenHelper'},
        ) as mock_lookup:
            groups = generate_weekly_pdfs.group_source_rows([row])
            mock_lookup.assert_not_called()
        keys = list(groups.keys())
        self.assertTrue(
            any('HELPER_ReplacementForeman' in k and 'REDUCEDSUB' not in k for k in keys),
            f"Non-subcontractor helper row should emit legacy "
            f"_HELPER_<name>; got: {keys}",
        )

    # ─── Bug C attribution ───────────────────────────────────────

    def test_bug_c_attribution_partitions_row_to_frozen_helper(self):
        """Bug C core assertion: frozen helper wins over current helper
        in SHADOW-variant emission (D-15 scope).

        The Bug C contract is scoped to subcontractor helper-shadow
        files (``_REDUCEDSUB_HELPER_<name>`` / ``_AEPBILLABLE_HELPER_<name>``).
        The legacy ``_HELPER_<name>`` group key continues to use the
        current Smartsheet ``Foreman Helping?`` value unchanged — D-15
        explicitly preserves Phase 1's legacy helper flow when Bug C
        is active.
        """
        with mock.patch(
            'billing_audit.writer.lookup_attribution',
            return_value={
                'helper': 'OriginalForeman',
                'helper_dept': '500',
                'source_run_id': 'run-1234',
            },
        ):
            row = self._make_synth_helper_row(helper_foreman='ReplacementForeman')
            groups = generate_weekly_pdfs.group_source_rows([row])
        keys = list(groups.keys())
        # Bug C: shadow-variant emission uses the FROZEN helper
        self.assertTrue(
            any('REDUCEDSUB_HELPER_OriginalForeman' in k for k in keys),
            f"Bug C: row's shadow file should use frozen helper; got: {keys}",
        )
        self.assertTrue(
            any('AEPBILLABLE_HELPER_OriginalForeman' in k for k in keys),
            f"Bug C: post-cutoff AEP shadow file should use frozen "
            f"helper; got: {keys}",
        )
        # Bug C: shadow-variant emission MUST NOT use the current helper
        self.assertFalse(
            any('REDUCEDSUB_HELPER_ReplacementForeman' in k for k in keys),
            f"Bug C: shadow file should NOT use current helper; got: {keys}",
        )
        self.assertFalse(
            any('AEPBILLABLE_HELPER_ReplacementForeman' in k for k in keys),
            f"Bug C: shadow file should NOT use current helper; got: {keys}",
        )
        # D-15 scope: the LEGACY helper variant key uses the current
        # Smartsheet `Foreman Helping?` value unchanged — Bug C does
        # NOT touch the Phase 1 legacy helper flow.
        self.assertTrue(
            any(
                k == '041926_91467680_HELPER_ReplacementForeman'
                for k in keys
            ),
            f"D-15: legacy _HELPER_<name> key should still use current "
            f"helper; got: {keys}",
        )

    def test_bug_c_no_history_falls_back_to_current_helper_with_warning(self):
        """D-12 no_history fallback + WARNING discipline."""
        # Ensure not in fetch_failure state
        from billing_audit import client as ba_client
        ba_client._global_disable_reason = None
        with mock.patch(
            'billing_audit.writer.lookup_attribution',
            return_value=None,
        ), self.assertLogs(level='WARNING') as log_cm:
            row = self._make_synth_helper_row()
            groups = generate_weekly_pdfs.group_source_rows([row])
        warning_bodies = '\n'.join(log_cm.output)
        self.assertIn(
            'Subcontractor helper claim attribution fallback',
            warning_bodies,
        )
        self.assertIn('reason=no_history', warning_bodies)
        # Row falls back to current helper
        keys = list(groups.keys())
        self.assertTrue(
            any('ReplacementForeman' in k for k in keys),
            f"D-12 fallback: row should be in current helper's file; got: {keys}",
        )

    def test_bug_c_fetch_failure_falls_back_with_correct_reason(self):
        """Distinguish no_history vs fetch_failure per D-12."""
        from billing_audit import client as ba_client
        ba_client._global_disable_reason = 'PGRST106'
        try:
            with mock.patch(
                'billing_audit.writer.lookup_attribution',
                return_value=None,
            ), self.assertLogs(level='WARNING') as log_cm:
                row = self._make_synth_helper_row()
                generate_weekly_pdfs.group_source_rows([row])
            warning_bodies = '\n'.join(log_cm.output)
            self.assertIn('reason=fetch_failure', warning_bodies)
        finally:
            ba_client._global_disable_reason = None

    def test_bug_c_warning_dedupe_per_wr_helper(self):
        """Per-WR WARNING fires ONCE per (wr, week, helper) tuple."""
        from billing_audit import client as ba_client
        ba_client._global_disable_reason = None
        with mock.patch(
            'billing_audit.writer.lookup_attribution',
            return_value=None,
        ), self.assertLogs(level='WARNING') as log_cm:
            rows = [
                self._make_synth_helper_row(row_id=i)
                for i in range(100, 105)
            ]
            generate_weekly_pdfs.group_source_rows(rows)
        fallback_warnings = [
            line for line in log_cm.output
            if 'Subcontractor helper claim attribution fallback' in line
        ]
        self.assertEqual(
            len(fallback_warnings), 1,
            f"Per-WR dedupe broken: expected 1 WARNING, got "
            f"{len(fallback_warnings)}: {fallback_warnings}",
        )

    def test_bug_c_kill_switch_off_uses_current_helper(self):
        """Bug C kill switch — flips to D-12 unconditional fallback."""
        generate_weekly_pdfs.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED = False
        with mock.patch(
            'billing_audit.writer.lookup_attribution',
            return_value={'helper': 'OriginalForeman'},
        ) as mock_lookup:
            row = self._make_synth_helper_row()
            groups = generate_weekly_pdfs.group_source_rows([row])
            mock_lookup.assert_not_called()
        keys = list(groups.keys())
        self.assertTrue(
            any('REDUCEDSUB_HELPER_ReplacementForeman' in k for k in keys),
            f"Bug C kill-switch-off: row should go to current helper; "
            f"got: {keys}",
        )


class TestBugB2WhitelistE2E(unittest.TestCase):
    """D-21(c): PPP cleanup whitelist defense-in-depth."""

    def setUp(self):
        _ensure_smartsheet_mocked()

    def _make_attachment(self, name, att_id):
        att = mock.MagicMock()
        att.name = name
        att.id = att_id
        return att

    def _build_client_with_attachments(self, attachments):
        client = mock.MagicMock()
        sheet = mock.MagicMock()
        row = mock.MagicMock()
        row.id = 1
        client.Attachments.list_row_attachments.return_value.data = attachments
        sheet.rows = [row]
        client.Sheets.get_sheet.return_value = sheet
        return client, sheet

    def test_ppp_off_contract_primary_attachment_deleted(self):
        """Off-contract variant on PPP is unconditionally deleted."""
        att_primary = self._make_attachment(
            'WR_91467680_WeekEnding_041926_120000_abc123.xlsx', 10
        )
        att_reduced = self._make_attachment(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_def456.xlsx', 20
        )
        client, sheet = self._build_client_with_attachments(
            [att_primary, att_reduced]
        )
        generate_weekly_pdfs.cleanup_untracked_sheet_attachments(
            client,
            target_sheet_id=8162920222379908,
            valid_wr_weeks=set(),
            test_mode=False,
            target_sheet=sheet,
            variant_whitelist={'reduced_sub', 'reduced_sub_helper'},
        )
        deletes = [
            call.args for call in client.Attachments.delete_attachment.call_args_list
        ]
        self.assertIn(
            (8162920222379908, 10), deletes,
            f"primary attachment must be deleted (off-contract for PPP); "
            f"got deletes={deletes}"
        )
        # reduced_sub attachment should NOT be deleted as off-contract.
        # It IS in identity_groups; with empty valid_wr_weeks and the
        # default KEEP_HISTORICAL_WEEKS=False, the legacy path may
        # still delete it via the variant-keep-newest cleanup OR may
        # leave it (depends on whether it's a "newest" or "older"
        # variant in the single-element identity group; single-element
        # groups always have only one entry so atts_sorted[1:] is empty
        # and no delete fires). So the reduced_sub MUST NOT be in the
        # off-contract delete batch even though it may be deleted by
        # other paths — the assertion focuses on the off-contract
        # invariant.
        # In fact for this single-attachment identity group there's
        # nothing to delete, so verify the only delete was the
        # off-contract primary:
        self.assertEqual(
            len(deletes), 1,
            f"Only the off-contract primary attachment should be "
            f"deleted; got: {deletes}"
        )

    def test_target_cleanup_with_none_whitelist_preserves_legacy(self):
        """TARGET cleanup with variant_whitelist=None preserves Phase 1 behavior."""
        att_primary = self._make_attachment(
            'WR_91467680_WeekEnding_041926_120000_abc123.xlsx', 10
        )
        client, sheet = self._build_client_with_attachments([att_primary])
        generate_weekly_pdfs.cleanup_untracked_sheet_attachments(
            client,
            target_sheet_id=5723337641643908,
            valid_wr_weeks={('91467680', '041926', 'primary', '')},
            test_mode=False,
            target_sheet=sheet,
            variant_whitelist=None,
        )
        deletes = [
            call.args for call in client.Attachments.delete_attachment.call_args_list
        ]
        # With whitelist=None, the off-contract loop is skipped entirely.
        # The single-attachment identity group has no older variants to
        # delete (atts_sorted[1:] is empty), so no deletes fire.
        self.assertEqual(
            deletes, [],
            f"TARGET with whitelist=None should not unconditionally "
            f"delete; got: {deletes}"
        )

    def test_ppp_with_only_whitelisted_attachments_no_delete(self):
        """PPP with only whitelisted variants performs zero off-contract deletes."""
        att_reduced = self._make_attachment(
            'WR_91467680_WeekEnding_041926_120000_ReducedSub_def456.xlsx', 20
        )
        client, sheet = self._build_client_with_attachments([att_reduced])
        generate_weekly_pdfs.cleanup_untracked_sheet_attachments(
            client,
            target_sheet_id=8162920222379908,
            valid_wr_weeks=set(),
            test_mode=False,
            target_sheet=sheet,
            variant_whitelist={'reduced_sub', 'reduced_sub_helper'},
        )
        deletes = [
            call.args for call in client.Attachments.delete_attachment.call_args_list
        ]
        self.assertEqual(
            deletes, [],
            f"PPP with only whitelisted variant attachment must not "
            f"trigger off-contract delete; got: {deletes}"
        )


class TestHashPruneIdempotency(unittest.TestCase):
    """D-21(e) + SUB-12 + Pitfall 4 closure."""

    def setUp(self):
        _ensure_smartsheet_mocked()
        self._tmpdir = tempfile.TemporaryDirectory()
        self._hist_path = os.path.join(self._tmpdir.name, 'hash_history.json')

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_history_via_save(self, payload):
        """Persist via the production save helper so the on-disk shape
        matches what the production load would observe."""
        generate_weekly_pdfs.save_hash_history(self._hist_path, dict(payload))

    def _make_groups_with_reducedsub(self, wrs):
        """Build a synthetic groups dict containing _REDUCEDSUB-suffixed
        keys for the given WRs — drives ``_run_phase_1_1_hash_prune``'s
        simplified D-18 detection."""
        groups = {}
        for wr in wrs:
            key = f"041926_{wr}_REDUCEDSUB"
            groups[key] = [{
                'Work Request #': wr,
                '__source_sheet_id': 8162920222379908,
            }]
        return groups

    # ─── Pitfall 4 sentinel round-trip ───────────────────────────

    def test_phase_prune_version_survives_round_trip(self):
        """Pitfall 4 regression guard — sentinel survives load/save."""
        payload = {
            '91467680|041926|primary|': {'hash': 'h1', 'timestamp': '2026-01-01'},
            '_phase_prune_version': 1,
        }
        generate_weekly_pdfs.save_hash_history(self._hist_path, dict(payload))
        loaded = generate_weekly_pdfs.load_hash_history(self._hist_path)
        self.assertIn(
            '_phase_prune_version', loaded,
            f"Sentinel must survive round trip; got: {list(loaded.keys())}"
        )
        self.assertEqual(loaded['_phase_prune_version'], 1)
        self.assertIn('91467680|041926|primary|', loaded)

    def test_save_handles_int_sentinel_in_retention_sort(self):
        """Save must not AttributeError on int sentinel during retention."""
        # Cap + 1 real entries + sentinel
        cap = generate_weekly_pdfs.HASH_HISTORY_MAX_ENTRIES
        payload = {
            f'wr_{i:04d}|041926|primary|': {
                'hash': f'h{i}',
                # Vary timestamp so retention sort discriminates them
                'timestamp': f'2026-01-{(i % 28) + 1:02d}',
            }
            for i in range(cap + 1)
        }
        payload['_phase_prune_version'] = 1
        generate_weekly_pdfs.save_hash_history(self._hist_path, dict(payload))
        loaded = generate_weekly_pdfs.load_hash_history(self._hist_path)
        self.assertIn('_phase_prune_version', loaded)
        # Real entries capped at HASH_HISTORY_MAX_ENTRIES
        real_entries = [k for k in loaded if not k.startswith('_')]
        self.assertEqual(len(real_entries), cap)

    # ─── Prune behavior ──────────────────────────────────────────

    def test_first_run_advances_version_and_drops_orphans(self):
        """Version 0 → 1: orphans dropped, sentinel persists, log fires."""
        hash_history = {
            '91467680|041926|primary|': {'hash': 'h1', 'timestamp': '2026-01-01'},
            '91467681|041926|primary|': {'hash': 'h2', 'timestamp': '2026-01-02'},
            '91467682|041926|primary|': {'hash': 'h3', 'timestamp': '2026-01-03'},
            # Unaffected entries — non-subcontractor WR
            '12345|041926|primary|': {'hash': 'h4', 'timestamp': '2026-01-04'},
            # Unaffected entry — non-primary variant for a subcontractor WR
            '91467680|041926|reduced_sub|': {
                'hash': 'h5', 'timestamp': '2026-01-05',
            },
        }
        groups = self._make_groups_with_reducedsub(
            ['91467680', '91467681', '91467682']
        )
        with self.assertLogs(level='INFO') as log_cm:
            generate_weekly_pdfs._run_phase_1_1_hash_prune(hash_history, groups)
        # 3 orphans dropped
        self.assertNotIn('91467680|041926|primary|', hash_history)
        self.assertNotIn('91467681|041926|primary|', hash_history)
        self.assertNotIn('91467682|041926|primary|', hash_history)
        # Unaffected entries preserved
        self.assertIn('12345|041926|primary|', hash_history)
        self.assertIn('91467680|041926|reduced_sub|', hash_history)
        # Sentinel persists
        self.assertEqual(
            hash_history['_phase_prune_version'],
            generate_weekly_pdfs.PHASE_1_1_HASH_PRUNE_VERSION,
        )
        # ONE info log mentioning the dropped count
        prune_logs = [
            line for line in log_cm.output
            if 'Phase 1.1 hash-history prune' in line
        ]
        self.assertEqual(len(prune_logs), 1, f"Expected 1 prune log; got: {prune_logs}")
        self.assertIn('dropped 3', prune_logs[0])

    def test_subsequent_run_at_current_version_is_noop(self):
        """Sentinel already at current version → no-op (no entries dropped)."""
        hash_history = {
            '91467680|041926|primary|': {'hash': 'h1', 'timestamp': '2026-01-01'},
            '_phase_prune_version': generate_weekly_pdfs.PHASE_1_1_HASH_PRUNE_VERSION,
        }
        groups = self._make_groups_with_reducedsub(['91467680'])
        generate_weekly_pdfs._run_phase_1_1_hash_prune(hash_history, groups)
        # Orphan preserved (no-op path)
        self.assertIn('91467680|041926|primary|', hash_history)
        # Sentinel preserved at current value
        self.assertEqual(
            hash_history['_phase_prune_version'],
            generate_weekly_pdfs.PHASE_1_1_HASH_PRUNE_VERSION,
        )

    def test_prune_excludes_non_subcontractor_primary(self):
        """D-18 scope: only WRs whose groups contain _REDUCEDSUB are in-scope."""
        hash_history = {
            '99999|041926|primary|': {'hash': 'h1', 'timestamp': '2026-01-01'},
        }
        # groups dict has NO _REDUCEDSUB key for WR 99999
        groups = self._make_groups_with_reducedsub(['some_other_wr'])
        generate_weekly_pdfs._run_phase_1_1_hash_prune(hash_history, groups)
        # 99999 entry preserved (out of scope)
        self.assertIn('99999|041926|primary|', hash_history)

    def test_prune_excludes_non_primary_subcontractor_variants(self):
        """D-17 scope: only variant='primary' AND identifier='' entries dropped."""
        hash_history = {
            '91467680|041926|reduced_sub|': {
                'hash': 'h1', 'timestamp': '2026-01-01',
            },
            '91467680|041926|aep_billable|': {
                'hash': 'h2', 'timestamp': '2026-01-02',
            },
            '91467680|041926|reduced_sub_helper|Foreman': {
                'hash': 'h3', 'timestamp': '2026-01-03',
            },
            '91467680|041926|helper|Foreman': {
                'hash': 'h4', 'timestamp': '2026-01-04',
            },
        }
        groups = self._make_groups_with_reducedsub(['91467680'])
        generate_weekly_pdfs._run_phase_1_1_hash_prune(hash_history, groups)
        # None of these should be dropped
        self.assertIn('91467680|041926|reduced_sub|', hash_history)
        self.assertIn('91467680|041926|aep_billable|', hash_history)
        self.assertIn('91467680|041926|reduced_sub_helper|Foreman', hash_history)
        self.assertIn('91467680|041926|helper|Foreman', hash_history)

    def test_reset_hash_history_followed_by_prune_is_noop(self):
        """RESET_HASH_HISTORY=true → empty dict → prune writes sentinel + 0 drops."""
        hash_history = {}  # simulates load_hash_history after RESET
        groups = self._make_groups_with_reducedsub(['91467680'])
        with self.assertLogs(level='INFO') as log_cm:
            generate_weekly_pdfs._run_phase_1_1_hash_prune(hash_history, groups)
        # 0 entries dropped (nothing was there), sentinel persists
        self.assertEqual(
            hash_history['_phase_prune_version'],
            generate_weekly_pdfs.PHASE_1_1_HASH_PRUNE_VERSION,
        )
        # ONE info log — "no orphans to drop" path
        prune_logs = [
            line for line in log_cm.output
            if 'Phase 1.1 hash-history prune' in line
        ]
        self.assertEqual(len(prune_logs), 1)
        self.assertIn('no orphans to drop', prune_logs[0])

    def test_first_run_with_no_orphans_logs_no_orphan_branch(self):
        """Version 0 + groups with _REDUCEDSUB + no matching orphans → log + noop."""
        hash_history = {
            'other_wr|041926|primary|': {'hash': 'h1', 'timestamp': '2026-01-01'},
        }
        groups = self._make_groups_with_reducedsub(['91467680'])
        with self.assertLogs(level='INFO') as log_cm:
            generate_weekly_pdfs._run_phase_1_1_hash_prune(hash_history, groups)
        # Non-subcontractor entry preserved
        self.assertIn('other_wr|041926|primary|', hash_history)
        # Sentinel persists
        self.assertEqual(
            hash_history['_phase_prune_version'],
            generate_weekly_pdfs.PHASE_1_1_HASH_PRUNE_VERSION,
        )
        prune_logs = [
            line for line in log_cm.output
            if 'Phase 1.1 hash-history prune' in line
        ]
        self.assertEqual(len(prune_logs), 1)
        self.assertIn('no orphans to drop', prune_logs[0])


class TestProductionCodeSiteInvariants(unittest.TestCase):
    """Source-level grep guards — defeat the 'mirror passes but
    production reverted' failure mode that allowed Phase 1 to ship
    with Bugs A and B1 latent.
    """

    @classmethod
    def setUpClass(cls):
        cls._src = pathlib.Path(
            inspect.getsourcefile(generate_weekly_pdfs)
        ).read_text(encoding='utf-8')

    def test_bug_a_rescue_gate_present_in_production(self):
        """Bug A rescue gate: is_subcontractor_sheet + kill switch."""
        # Look for the multiline conditional block — both names appear
        # consecutively gated by ``and`` in the production source.
        self.assertRegex(
            self._src,
            r'is_subcontractor_sheet\s*\n\s*and SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED',
            "Bug A rescue gate must be present in production",
        )
        self.assertIn('_subcontractor_rescue_price', self._src)

    def test_bug_b1_partitioning_gate_present_in_production(self):
        """Bug B1 partitioning gate."""
        self.assertIn(
            'if not is_subcontractor_row and not valid_helper_row:',
            self._src,
            "Bug B1 partitioning gate must be present in production",
        )

    def test_bug_b2_whitelist_signature_present_in_production(self):
        """Bug B2 whitelist kwarg signature."""
        self.assertRegex(
            self._src,
            r'variant_whitelist: set\[str\] \| None = None',
            "Bug B2 whitelist kwarg signature must be present in production",
        )

    def test_bug_c_reader_invocation_site_present_in_production(self):
        """Bug C reader invocation site."""
        self.assertIn('lookup_attribution(', self._src)
        self.assertIn(
            'from billing_audit.writer import lookup_attribution',
            self._src,
        )
        self.assertIn('SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED', self._src)

    def test_hash_prune_version_constant_present_in_production(self):
        """Hash-prune version constant per D-17/D-19."""
        self.assertRegex(
            self._src,
            r'(?m)^PHASE_1_1_HASH_PRUNE_VERSION = 1$',
            "Hash-prune version constant must be present in production",
        )

    def test_hash_prune_helper_callable(self):
        """Helper function `_run_phase_1_1_hash_prune` is callable."""
        self.assertTrue(
            callable(generate_weekly_pdfs._run_phase_1_1_hash_prune),
            "Hash-prune helper must be a module-level callable",
        )

    def test_phase_1_1_hash_prune_pii_marker_present(self):
        """Prune-pass PII marker registered per [2026-05-15 12:00] rule 3."""
        self.assertIn(
            'Phase 1.1 hash-history prune',
            generate_weekly_pdfs._PII_LOG_MARKERS,
        )


if __name__ == '__main__':
    unittest.main()
