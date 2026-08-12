"""Tests for the snapshot-date drift audit (quick task 260812-jqx).

RED-first suite covering the 9 research cases: detection with zero
extra Smartsheet API calls, first-sight seeding, classification via
targeted cell-history lookups (capped/paced/budget-aware), the
hold-prior-week override (both fields), and the audit risk-level
wiring. Mirrors ``tests/test_rate_sanity_audit.py`` (no-network
fixture pattern) and ``tests/test_billing_audit_shadow.py`` (Supabase
writer mocks).

Task 1 covers detection only: no classifier and no hold override
exist yet at this point in the suite's history, so drift candidates
are asserted generically (not pinned to a specific classification
value) -- Task 2 adds the classifier and Task 3 adds the hold
override in later sections of this file.
"""

from __future__ import annotations

import datetime
import unittest
from unittest import mock

from pipeline.snapshot_drift import apply_snapshot_drift_holds


def _row(
    sheet_id: int = 111,
    row_id: int = 222,
    wr: str = "90001",
    cu: str = "ABC-123",
    week: str = "2026-08-09",
    snapshot: str = "2026-08-05",
) -> dict:
    return {
        "__source_sheet_id": sheet_id,
        "__row_id": row_id,
        "Work Request #": wr,
        "CU": cu,
        "Weekly Reference Logged Date": week,
        "Snapshot Date": snapshot,
    }


def _baseline(
    sheet_id: int = 111,
    row_id: int = 222,
    billed_week: str = "2026-08-09",
    snapshot_date: str = "2026-08-05",
    wr: str = "90001",
    cu: str = "ABC-123",
    first_seen_at: str = "2026-07-01T00:00:00+00:00",
) -> dict:
    return {
        "sheet_id": sheet_id,
        "row_id": row_id,
        "wr": wr,
        "cu": cu,
        "snapshot_date": snapshot_date,
        "billed_week": billed_week,
        "run_id": "prior-run",
        "first_seen_at": first_seen_at,
        "last_seen_at": "2026-08-05T00:00:00+00:00",
    }


class SnapshotDriftDetectionTestBase(unittest.TestCase):
    """Shared patches for the Supabase snapshot_store surface."""

    def setUp(self) -> None:
        self.session_start = datetime.datetime.now()
        self.client = mock.MagicMock()

        self._fetch_patch = mock.patch(
            "billing_audit.snapshot_store.fetch_snapshot_provenance"
        )
        self._upsert_patch = mock.patch(
            "billing_audit.snapshot_store.upsert_snapshot_provenance"
        )
        self._insert_patch = mock.patch(
            "billing_audit.snapshot_store.insert_snapshot_drift_events"
        )
        self.mock_fetch = self._fetch_patch.start()
        self.mock_upsert = self._upsert_patch.start()
        self.mock_insert = self._insert_patch.start()
        self.addCleanup(self._fetch_patch.stop)
        self.addCleanup(self._upsert_patch.stop)
        self.addCleanup(self._insert_patch.stop)


class TestTask1NoBaselineSeeds(SnapshotDriftDetectionTestBase):
    """No provenance baseline -> silent seed, zero drift, zero API (D-09)."""

    def test_no_baseline_seeds_silently(self) -> None:
        self.mock_fetch.return_value = ({}, "no_row")
        row = _row()

        summary = apply_snapshot_drift_holds(
            [row], [], self.client, self.session_start
        )

        self.assertTrue(summary["enabled"])
        self.assertEqual(summary["candidates"], 0)
        self.assertEqual(summary["seeded"], 1)
        self.client.Cells.get_cell_history.assert_not_called()
        self.mock_upsert.assert_called_once()
        records = self.mock_upsert.call_args[0][0]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["sheet_id"], 111)
        self.assertEqual(records[0]["row_id"], 222)
        # No baseline -> no drift -> no event written.
        self.mock_insert.assert_called_once_with([])


class TestTask1WeekUnchangedCostsNothing(SnapshotDriftDetectionTestBase):
    """Computed week == baseline billed_week -> zero drift, zero API (D-04)."""

    def test_unchanged_week_costs_zero_api_calls(self) -> None:
        self.mock_fetch.return_value = (
            {(111, 222): _baseline(billed_week="2026-08-09")},
            "success",
        )
        row = _row(week="2026-08-09")

        summary = apply_snapshot_drift_holds(
            [row], [], self.client, self.session_start
        )

        self.assertEqual(summary["candidates"], 0)
        self.assertEqual(summary["unchanged"], 1)
        self.client.Cells.get_cell_history.assert_not_called()
        self.mock_insert.assert_called_once_with([])


class TestTask1WeekDriftIsACandidate(SnapshotDriftDetectionTestBase):
    """Computed week != baseline billed_week -> candidate, not held,
    row fields left untouched at this point in the audit (Task 1)."""

    def test_drifted_week_emits_candidate_without_mutation(self) -> None:
        self.mock_fetch.return_value = (
            {(111, 222): _baseline(
                billed_week="2026-08-02", snapshot_date="2026-07-29"
            )},
            "success",
        )
        row = _row(week="2026-08-09", snapshot="2026-08-05")

        summary = apply_snapshot_drift_holds(
            [row], [], self.client, self.session_start
        )

        self.assertEqual(summary["candidates"], 1)
        self.assertEqual(summary["automation_self_fire_holds"], 0)
        # Task 1 never mutates rows.
        self.assertEqual(row["Weekly Reference Logged Date"], "2026-08-09")
        self.assertEqual(row["Snapshot Date"], "2026-08-05")

        self.mock_insert.assert_called_once()
        events = self.mock_insert.call_args[0][0]
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["sheet_id"], 111)
        self.assertEqual(event["row_id"], 222)
        self.assertEqual(event["prior_billed_week"], "2026-08-02")
        self.assertEqual(event["new_week"], "2026-08-09")
        self.assertFalse(event["held"])
        self.assertTrue(event["classification"])  # non-empty placeholder/real


class TestTask1KillSwitchDisabled(SnapshotDriftDetectionTestBase):
    """SNAPSHOT_DRIFT_AUDIT_ENABLED=false -> zeroed summary, no
    Supabase call, rows byte-identical (D-08)."""

    def test_disabled_is_a_pure_noop(self) -> None:
        row = _row()
        original = dict(row)

        with mock.patch.dict(
            "os.environ", {"SNAPSHOT_DRIFT_AUDIT_ENABLED": "false"}
        ):
            summary = apply_snapshot_drift_holds(
                [row], [], self.client, self.session_start
            )

        self.assertFalse(summary["enabled"])
        self.assertEqual(summary["candidates"], 0)
        self.mock_fetch.assert_not_called()
        self.mock_upsert.assert_not_called()
        self.mock_insert.assert_not_called()
        self.assertEqual(row, original)


class TestTask1ClientUnavailable(SnapshotDriftDetectionTestBase):
    """get_client() unavailable -> flagged unavailable, no exception."""

    def test_unavailable_client_flags_summary_and_does_not_raise(self) -> None:
        self.mock_fetch.return_value = ({}, "unavailable")
        row = _row()

        summary = apply_snapshot_drift_holds(
            [row], [], self.client, self.session_start
        )

        self.assertFalse(summary["available"])
        self.assertEqual(summary["candidates"], 0)
        self.client.Cells.get_cell_history.assert_not_called()


class TestTask1FetchRaisesDegradesToSeed(SnapshotDriftDetectionTestBase):
    """A raised exception from the bulk read is swallowed and
    degrades to the no-baseline (seed) path."""

    def test_fetch_exception_is_swallowed(self) -> None:
        self.mock_fetch.side_effect = Exception("boom")
        row = _row()

        summary = apply_snapshot_drift_holds(
            [row], [], self.client, self.session_start
        )

        self.assertFalse(summary["available"])
        self.assertEqual(summary["seeded"], 1)
        self.assertEqual(summary["candidates"], 0)


class TestTask1BatchedProvenanceUpsert(SnapshotDriftDetectionTestBase):
    """Provenance upsert is invoked at most once per run with a
    batched payload -- never once per row (RESEARCH caveat 6)."""

    def test_upsert_called_once_with_batched_payload(self) -> None:
        self.mock_fetch.return_value = (
            {
                (111, 222): _baseline(sheet_id=111, row_id=222, billed_week="2026-08-09"),
            },
            "success",
        )
        rows = [
            _row(sheet_id=111, row_id=222, wr="90001", week="2026-08-09"),
            _row(sheet_id=111, row_id=333, wr="90002", week="2026-08-09"),
            _row(sheet_id=222, row_id=444, wr="90003", week="2026-08-09"),
        ]

        summary = apply_snapshot_drift_holds(
            rows, [], self.client, self.session_start
        )

        self.assertEqual(self.mock_upsert.call_count, 1)
        records = self.mock_upsert.call_args[0][0]
        self.assertEqual(len(records), 3)
        self.assertEqual(summary["seeded"] + summary["unchanged"], 3)


if __name__ == "__main__":
    unittest.main()
