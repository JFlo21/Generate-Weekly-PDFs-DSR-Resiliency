"""Direct tests for ``billing_audit/snapshot_store.py``.

Started as the IN-05 fix lock (260812-jqx review): the
``fetch_snapshot_provenance`` "NEVER raises" contract had a hole --
``get_client()``, the ``_global_disable_reason`` peek, and the key
coercions ran OUTSIDE the try/except, so an exception there escaped
despite the docstring. ``TestFetchSnapshotProvenanceNeverRaises``
pins the contract at the module boundary (the caller-side wrap in
``pipeline/snapshot_drift.py`` is belt-and-suspenders, not the
contract).

Expanded for WR-05 (260813-nhn) into the full characterization
suite: F1-F13 / U1-U4 / I1-I4 / M1 (RESEARCH C.3), written against
and passing on the UNMODIFIED module. This suite is the behavioural
ORACLE for the WR-02 RPC-first refactor -- it must stay green,
unchanged, before and after that refactor lands.
"""

from __future__ import annotations

import unittest
from unittest import mock

import billing_audit.client as client_mod
import billing_audit.writer as writer
from billing_audit.snapshot_store import (
    fetch_snapshot_provenance,
    insert_snapshot_drift_events,
    sanitized_wr,
    upsert_snapshot_provenance,
)

_UNSET = object()


def _make_fake_client(
    *,
    select_response=_UNSET,
    select_side_effect=None,
    upsert_side_effect=None,
    insert_side_effect=None,
):
    """Build a Mock Supabase client honoring the chain shapes used by
    ``billing_audit.snapshot_store``:

    - ``schema('billing_audit').table(t).select(c).in_(a).in_(b).execute()``
    - ``schema('billing_audit').table(t).upsert(records, on_conflict=...).execute()``
    - ``schema('billing_audit').table(t).insert(events).execute()``

    Extends the chain shape already proven at
    ``tests/test_billing_audit_shadow.py:141-220``
    (``_make_fake_supabase_client``) rather than inventing a new
    harness. Returns ``(client, table)`` so tests can assert on
    ``table.select.call_args`` / ``table.upsert.call_args`` /
    ``table.insert.call_args``.
    """
    client = mock.Mock()
    schema = mock.Mock()
    client.schema.return_value = schema
    table = mock.Mock()
    schema.table.return_value = table

    select_obj = mock.Mock()
    table.select.return_value = select_obj
    in1_obj = mock.Mock()
    select_obj.in_.return_value = in1_obj
    in2_obj = mock.Mock()
    in1_obj.in_.return_value = in2_obj
    if select_side_effect is not None:
        in2_obj.execute.side_effect = select_side_effect
    else:
        resp = mock.Mock()
        resp.data = [] if select_response is _UNSET else select_response
        in2_obj.execute.return_value = resp

    upsert_obj = mock.Mock()
    table.upsert.return_value = upsert_obj
    if upsert_side_effect is not None:
        upsert_obj.execute.side_effect = upsert_side_effect
    else:
        upsert_obj.execute.return_value = mock.Mock(data=[])

    insert_obj = mock.Mock()
    table.insert.return_value = insert_obj
    if insert_side_effect is not None:
        insert_obj.execute.side_effect = insert_side_effect
    else:
        insert_obj.execute.return_value = mock.Mock(data=[])

    return client, table


class SnapshotStoreTestBase(unittest.TestCase):
    """Shared cache hygiene for the characterization suite.

    Resets ``billing_audit.client``'s module-level caches
    (``_open_circuits``, ``_consecutive_failures``,
    ``_global_disable_reason``) before AND after each test so state
    cannot leak between tests (RESEARCH C.2).
    """

    def setUp(self) -> None:
        client_mod.reset_cache_for_tests()
        self.addCleanup(client_mod.reset_cache_for_tests)


class TestFetchSnapshotProvenanceNeverRaises(unittest.TestCase):
    def test_get_client_raising_degrades_to_fetch_failure(self) -> None:
        """A crash in client acquisition must degrade, not escape."""
        with mock.patch(
            'billing_audit.snapshot_store.get_client',
            side_effect=RuntimeError('client bootstrap exploded'),
        ):
            rows, status = fetch_snapshot_provenance([(1, 2)])
        self.assertEqual(rows, {})
        self.assertEqual(status, 'fetch_failure')

    def test_uncoercible_key_degrades_to_fetch_failure(self) -> None:
        """Non-numeric key parts crash the sorted-set coercions --
        that too must degrade to fetch_failure, never raise."""
        with mock.patch(
            'billing_audit.snapshot_store.get_client',
            return_value=mock.MagicMock(),
        ):
            rows, status = fetch_snapshot_provenance(
                [('not-a-sheet-id', 'not-a-row-id')]  # type: ignore[list-item]
            )
        self.assertEqual(rows, {})
        self.assertEqual(status, 'fetch_failure')


class TestFetchSnapshotProvenanceCharacterization(SnapshotStoreTestBase):
    """F1-F13 (RESEARCH C.3): the pre-RPC behavioural oracle for
    ``fetch_snapshot_provenance``. Every case here MUST pass against
    the unmodified module -- this class is the regression anchor for
    the WR-02 RPC-first refactor (T4).
    """

    def test_f1_empty_keys_short_circuits(self) -> None:
        """F1: keys=[] -> ({}, 'no_row'); get_client never called."""
        with mock.patch(
            'billing_audit.snapshot_store.get_client'
        ) as mock_get_client:
            rows, status = fetch_snapshot_provenance([])
        self.assertEqual(rows, {})
        self.assertEqual(status, 'no_row')
        mock_get_client.assert_not_called()

    def test_f2_client_none_no_disable_reason_is_unavailable(
        self,
    ) -> None:
        """F2: client None, ``_global_disable_reason`` is None ->
        ``'unavailable'``."""
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=None
        ):
            rows, status = fetch_snapshot_provenance([(1, 2)])
        self.assertEqual(rows, {})
        self.assertEqual(status, 'unavailable')

    def test_f3_client_none_with_disable_reason_is_fetch_failure(
        self,
    ) -> None:
        """F3: client None, ``_global_disable_reason='PGRST106'`` ->
        ``'fetch_failure'``."""
        client_mod._global_disable_reason = 'PGRST106'
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=None
        ):
            rows, status = fetch_snapshot_provenance([(1, 2)])
        self.assertEqual(rows, {})
        self.assertEqual(status, 'fetch_failure')

    def test_f4_empty_data_list_is_no_row(self) -> None:
        """F4: ``resp.data == []`` -> ``'no_row'``."""
        client, _table = _make_fake_client(select_response=[])
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            rows, status = fetch_snapshot_provenance([(1, 2)])
        self.assertEqual(rows, {})
        self.assertEqual(status, 'no_row')

    def test_f5_none_data_is_no_row(self) -> None:
        """F5: ``resp.data is None`` -> ``'no_row'``."""
        client, _table = _make_fake_client(select_response=None)
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            rows, status = fetch_snapshot_provenance([(1, 2)])
        self.assertEqual(rows, {})
        self.assertEqual(status, 'no_row')

    def test_f6_bare_dict_data_normalizes_to_one_row(self) -> None:
        """F6: ``resp.data`` is a bare dict -> normalized to a
        1-item list -> ``'success'``."""
        client, _table = _make_fake_client(
            select_response={'sheet_id': 1, 'row_id': 2, 'wr': 'WR1'}
        )
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            rows, status = fetch_snapshot_provenance([(1, 2)])
        self.assertEqual(status, 'success')
        self.assertEqual(rows[(1, 2)]['wr'], 'WR1')

    def test_f7_cross_product_extra_row_is_filtered_out(self) -> None:
        """F7: the response includes an unrequested cross-product
        pair -- filtered out client-side; only the wanted pair
        returns; status ``'success'``."""
        client, _table = _make_fake_client(
            select_response=[
                {'sheet_id': 1, 'row_id': 2, 'wr': 'wanted'},
                {'sheet_id': 1, 'row_id': 99, 'wr': 'unrequested'},
            ]
        )
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            rows, status = fetch_snapshot_provenance([(1, 2)])
        self.assertEqual(status, 'success')
        self.assertEqual(set(rows.keys()), {(1, 2)})
        self.assertEqual(rows[(1, 2)]['wr'], 'wanted')

    def test_f8_unparseable_row_ids_are_skipped_without_raising(
        self,
    ) -> None:
        """F8: response rows with ``sheet_id=None`` / ``'abc'`` are
        skipped, never raise; no wanted key survives -> ``'no_row'``."""
        client, _table = _make_fake_client(
            select_response=[
                {'sheet_id': None, 'row_id': 2},
                {'sheet_id': 'abc', 'row_id': 2},
            ]
        )
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            rows, status = fetch_snapshot_provenance([(1, 2)])
        self.assertEqual(rows, {})
        self.assertEqual(status, 'no_row')

    def test_f9_rows_returned_but_none_in_wanted_is_no_row(
        self,
    ) -> None:
        """F9: rows returned but NONE are in ``wanted`` ->
        ``'no_row'`` (not ``'success'``)."""
        client, _table = _make_fake_client(
            select_response=[{'sheet_id': 5, 'row_id': 6}]
        )
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            rows, status = fetch_snapshot_provenance([(1, 2)])
        self.assertEqual(rows, {})
        self.assertEqual(status, 'no_row')

    def test_f10_permanent_api_error_is_fetch_failure(self) -> None:
        """F10: ``with_retry`` -> None (``execute()`` always raises a
        permanent ``APIError``) -> ``'fetch_failure'``."""
        from postgrest.exceptions import APIError

        error = APIError({'code': '23505', 'message': 'conflict'})
        client, _table = _make_fake_client(select_side_effect=error)
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            rows, status = fetch_snapshot_provenance([(1, 2)])
        self.assertEqual(rows, {})
        self.assertEqual(status, 'fetch_failure')

    def test_f11_string_response_ids_coerce_via_int(self) -> None:
        """F11: response ids as strings (``"123"``-shaped) -> ``int()``
        coercion matches the key."""
        client, _table = _make_fake_client(
            select_response=[{'sheet_id': '1', 'row_id': '2'}]
        )
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            rows, status = fetch_snapshot_provenance([(1, 2)])
        self.assertEqual(status, 'success')
        self.assertIn((1, 2), rows)

    def test_f12_select_chain_raising_is_fetch_failure(self) -> None:
        """F12: the ``.select()`` chain itself raises ``TypeError``
        -> ``'fetch_failure'``, never raises out."""
        client, table = _make_fake_client()
        table.select.side_effect = TypeError('chain construction blew up')
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            rows, status = fetch_snapshot_provenance([(1, 2)])
        self.assertEqual(rows, {})
        self.assertEqual(status, 'fetch_failure')

    def test_f13_select_uses_exact_provenance_columns(self) -> None:
        """F13: ``select`` is called with the exact
        ``_PROVENANCE_COLUMNS`` string (9 columns, matching the table
        at ``billing_audit/schema.sql:355-366``) -- pins the read
        contract against the schema."""
        client, table = _make_fake_client(
            select_response=[{'sheet_id': 1, 'row_id': 2}]
        )
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            fetch_snapshot_provenance([(1, 2)])
        table.select.assert_called_once_with(
            'sheet_id,row_id,wr,cu,snapshot_date,billed_week,run_id,'
            'first_seen_at,last_seen_at'
        )


class TestUpsertSnapshotProvenanceCharacterization(SnapshotStoreTestBase):
    """U1-U4 (RESEARCH C.3): ``upsert_snapshot_provenance``."""

    def test_u1_empty_records_short_circuits(self) -> None:
        """U1: ``records=[]`` -> no client call at all."""
        with mock.patch(
            'billing_audit.snapshot_store.get_client'
        ) as mock_get_client:
            upsert_snapshot_provenance([])
        mock_get_client.assert_not_called()

    def test_u2_client_none_is_a_noop(self) -> None:
        """U2: client None -> no-op, returns None."""
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=None
        ):
            result = upsert_snapshot_provenance([{'sheet_id': 1}])
        self.assertIsNone(result)

    def test_u3_happy_path_calls_upsert_with_conflict_target(
        self,
    ) -> None:
        """U3: ``.upsert(records, on_conflict="sheet_id,row_id")``
        verbatim -- pins the PK contract against
        ``schema.sql:365``."""
        client, table = _make_fake_client()
        records = [{'sheet_id': 1, 'row_id': 2, 'wr': 'WR1'}]
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            upsert_snapshot_provenance(records)
        table.upsert.assert_called_once_with(
            records, on_conflict='sheet_id,row_id'
        )

    def test_u4_execute_raising_never_raises(self) -> None:
        """U4: ``execute()`` raises -> returns None, never raises,
        logs."""
        client, _table = _make_fake_client(
            upsert_side_effect=RuntimeError('upsert exploded')
        )
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            result = upsert_snapshot_provenance([{'sheet_id': 1}])
        self.assertIsNone(result)


class TestInsertSnapshotDriftEventsCharacterization(SnapshotStoreTestBase):
    """I1-I4 (RESEARCH C.3): ``insert_snapshot_drift_events``."""

    def test_i1_empty_events_short_circuits(self) -> None:
        """I1: ``events=[]`` -> no client call."""
        with mock.patch(
            'billing_audit.snapshot_store.get_client'
        ) as mock_get_client:
            insert_snapshot_drift_events([])
        mock_get_client.assert_not_called()

    def test_i2_client_none_is_a_noop(self) -> None:
        """I2: client None -> no-op."""
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=None
        ):
            result = insert_snapshot_drift_events([{'sheet_id': 1}])
        self.assertIsNone(result)

    def test_i3_happy_path_single_insert_call(self) -> None:
        """I3: single ``.insert(list(events))``, one ``execute()``."""
        client, table = _make_fake_client()
        events = [{'sheet_id': 1, 'row_id': 2}]
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            insert_snapshot_drift_events(events)
        table.insert.assert_called_once_with(events)
        table.insert.return_value.execute.assert_called_once()

    def test_i4_execute_raising_never_raises(self) -> None:
        """I4: ``execute()`` raises -> never raises out."""
        client, _table = _make_fake_client(
            insert_side_effect=RuntimeError('insert exploded')
        )
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            result = insert_snapshot_drift_events([{'sheet_id': 1}])
        self.assertIsNone(result)


class TestSnapshotStoreModuleContract(unittest.TestCase):
    """M1 (RESEARCH C.3): guards the ``noqa: F401`` re-export."""

    def test_m1_sanitized_wr_reexport_identity(self) -> None:
        """``snapshot_store.sanitized_wr`` IS
        ``writer._sanitized_wr`` -- same function object, not a
        copy."""
        self.assertIs(sanitized_wr, writer._sanitized_wr)


if __name__ == '__main__':
    unittest.main()
