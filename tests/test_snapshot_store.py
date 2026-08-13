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
import billing_audit.snapshot_store as snapshot_store

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


class TestUpsertSnapshotProvenanceChunking(SnapshotStoreTestBase):
    """A9 (RESEARCH C.4) + failing-chunk regression (T5, 260813-nhn,
    D-02): sibling defect to WR-02 on the write side -- an unchunked
    upsert at live scale (~2x10^5 records x ~200 B) is a ~40 MB POST
    body. U1-U4 above (T2 oracle) must still pass unmodified.
    """

    def test_a9_chunks_at_patched_size_preserves_order(self) -> None:
        """A9: chunk constant patched to 1000, 2500 records -> exactly
        3 upsert invocations; the concatenation of the three record
        batches equals the input in order; every call passes the same
        conflict-target string."""
        client, table = _make_fake_client()
        records = [
            {'sheet_id': 1, 'row_id': i, 'wr': f'WR{i}'}
            for i in range(2500)
        ]
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ), mock.patch.object(snapshot_store, '_UPSERT_CHUNK', 1000):
            upsert_snapshot_provenance(records)
        self.assertEqual(table.upsert.call_count, 3)
        seen: "list[dict]" = []
        for call in table.upsert.call_args_list:
            batch = call.args[0]
            self.assertEqual(
                call.kwargs.get('on_conflict'), 'sheet_id,row_id'
            )
            seen.extend(batch)
        self.assertEqual(seen, records)

    def test_failing_chunk_does_not_abort_remaining_chunks(
        self,
    ) -> None:
        """Regression: a chunk whose ``execute()`` raises must not
        raise out of the function and must not abort the remaining
        chunks -- a partial durable write is strictly better than
        none."""
        client, table = _make_fake_client()
        call_count = {'n': 0}

        def _flaky_execute():
            call_count['n'] += 1
            if call_count['n'] == 1:
                raise RuntimeError('chunk 1 exploded')
            return mock.Mock(data=[])

        table.upsert.return_value.execute.side_effect = _flaky_execute
        records = [{'sheet_id': 1, 'row_id': i} for i in range(2500)]
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ), mock.patch.object(snapshot_store, '_UPSERT_CHUNK', 1000):
            result = upsert_snapshot_provenance(records)
        self.assertIsNone(result)
        self.assertEqual(table.upsert.call_count, 3)


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


class RpcCharacterizationTestBase(SnapshotStoreTestBase):
    """Shared reset for the WR-02 RPC-first suite (T4, 260813-nhn).

    Adds the one-time degrade-log latch to the T2 cache-hygiene reset
    -- that module attribute did not exist when
    ``SnapshotStoreTestBase`` was written, so it is reset here rather
    than editing that (committed, oracle) base class.
    """

    def setUp(self) -> None:
        super().setUp()
        snapshot_store._rpc_missing_logged = False


def _configure_rpc(client, *, side_effect=None, response_rows=None):
    """Compose RPC support onto a client built by ``_make_fake_client``
    (T2) WITHOUT modifying that fixture -- ``.rpc`` is set directly
    on the already-built ``schema`` mock. Returns ``schema`` so tests
    can inspect ``schema.rpc.call_args`` / ``call_args_list``.
    """
    schema = client.schema.return_value
    rpc_obj = mock.Mock()
    if side_effect is not None:
        rpc_obj.execute.side_effect = side_effect
    else:
        rpc_obj.execute.return_value = mock.Mock(
            data=response_rows if response_rows is not None else []
        )
    schema.rpc.return_value = rpc_obj
    return schema


class TestFetchSnapshotProvenanceRpcFirst(RpcCharacterizationTestBase):
    """A1-A8 (RESEARCH C.4): the WR-02 RPC-first reader. The
    unmodified T2 suite above stays green throughout -- an
    unconfigured ``.rpc()`` chain is treated by the module the same
    way a genuinely-missing function is (falls back to the proven
    select path), which is exactly what a not-yet-deployed RPC looks
    like in production too.
    """

    def test_a1_rpc_available_select_not_called(self) -> None:
        """A1: RPC available -> ``.rpc(...)`` called; ``.table()
        .select()`` NOT called."""
        client, table = _make_fake_client()
        schema = _configure_rpc(client, response_rows=[])
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            rows, status = fetch_snapshot_provenance([(1, 2)])
        schema.rpc.assert_called_once()
        table.select.assert_not_called()
        self.assertEqual(status, 'no_row')
        self.assertEqual(rows, {})

    def test_a2_rpc_payload_shape(self) -> None:
        """A2: every element of ``p_keys`` is a dict of exactly
        ``sheet_id`` and ``row_id``, both ``int``."""
        client, _table = _make_fake_client()
        schema = _configure_rpc(
            client,
            response_rows=[{'sheet_id': 1, 'row_id': 2}],
        )
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            fetch_snapshot_provenance([(1, 2)])
        _name, args, _kwargs = schema.rpc.mock_calls[0]
        payload = args[1]['p_keys']
        for item in payload:
            self.assertEqual(set(item.keys()), {'sheet_id', 'row_id'})
            self.assertIsInstance(item['sheet_id'], int)
            self.assertIsInstance(item['row_id'], int)

    def test_a3_pgrst202_falls_back_to_select_success(self) -> None:
        """A3: RPC raises a PGRST202-shaped error -> falls back to
        the select path and returns ``'success'``; the returned
        status is one of the original four (never the internal
        ``'rpc_missing'`` marker, D-04)."""
        from postgrest.exceptions import APIError

        error = APIError({'code': 'PGRST202', 'message': 'missing'})
        client, table = _make_fake_client(
            select_response=[{'sheet_id': 1, 'row_id': 2}]
        )
        _configure_rpc(client, side_effect=error)
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            rows, status = fetch_snapshot_provenance([(1, 2)])
        self.assertIn(
            status, ('success', 'no_row', 'fetch_failure', 'unavailable')
        )
        self.assertEqual(status, 'success')
        self.assertIn((1, 2), rows)
        table.select.assert_called_once()

    def test_a4_rpc_missing_logs_exactly_once_per_process(self) -> None:
        """A4: two ``fetch_snapshot_provenance`` calls in one process
        with the RPC missing -> exactly ONE WARNING record."""
        from postgrest.exceptions import APIError

        error = APIError({'code': 'PGRST202', 'message': 'missing'})
        client, _table = _make_fake_client(select_response=[])
        _configure_rpc(client, side_effect=error)
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            with self.assertLogs(
                'billing_audit.snapshot_store', level='WARNING'
            ) as cm:
                fetch_snapshot_provenance([(1, 2)])
                fetch_snapshot_provenance([(3, 4)])
        self.assertEqual(len(cm.records), 1)

    def test_a5_transient_exhaustion_is_fetch_failure_no_fallback(
        self,
    ) -> None:
        """A5: RPC raises a transient error until retries exhaust ->
        ``'fetch_failure'`` and NO select fallback (the table chain
        is never touched) -- a transient outage must not double the
        request volume."""
        client, table = _make_fake_client()
        _configure_rpc(client, side_effect=ConnectionError('down'))
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ), mock.patch('billing_audit.client.time.sleep'):
            rows, status = fetch_snapshot_provenance([(1, 2)])
        self.assertEqual(rows, {})
        self.assertEqual(status, 'fetch_failure')
        table.select.assert_not_called()

    def test_a6_rpc_chunking_merges_all_chunks(self) -> None:
        """A6: RPC chunking -- ``_RPC_CHUNK_SIZE`` patched to 500,
        1200 keys -> exactly 3 rpc invocations, results from all
        three merge into one dict."""
        client, _table = _make_fake_client()
        schema = client.schema.return_value

        def _echo(_name, params):
            call_result = mock.Mock()
            keys = params.get('p_keys', [])
            call_result.execute.return_value = mock.Mock(
                data=[
                    {'sheet_id': k['sheet_id'], 'row_id': k['row_id']}
                    for k in keys
                ]
            )
            return call_result

        schema.rpc.side_effect = _echo
        keys = [(1, i) for i in range(1200)]
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ), mock.patch.object(snapshot_store, '_RPC_CHUNK_SIZE', 500):
            rows, status = fetch_snapshot_provenance(keys)
        self.assertEqual(status, 'success')
        self.assertEqual(schema.rpc.call_count, 3)
        self.assertEqual(len(rows), 1200)

    def test_a7_fallback_chunking_whole_sheet_ids_per_chunk(
        self,
    ) -> None:
        """A7: fallback chunking -- RPC missing, 1000 keys,
        ``_FALLBACK_ROW_ID_CHUNK`` at its module default of 200 ->
        exactly 5 select invocations, and the ``sheet_id`` list is
        passed WHOLE on each chunk (only the row axis chunks)."""
        from postgrest.exceptions import APIError

        error = APIError({'code': 'PGRST202', 'message': 'missing'})
        client, table = _make_fake_client(select_response=[])
        _configure_rpc(client, side_effect=error)
        # 1000 DISTINCT row ids (varying sheet_id among 3 values so
        # the sheet-id axis stays small) -> ceil(1000/200) = 5 chunks
        # on the row-id axis.
        keys = [(10 + (i % 3), i) for i in range(1000)]
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            fetch_snapshot_provenance(keys)
        self.assertEqual(table.select.call_count, 5)
        sheet_in_calls = table.select.return_value.in_.call_args_list
        row_in_calls = (
            table.select.return_value.in_.return_value.in_.call_args_list
        )
        self.assertEqual(len(sheet_in_calls), 5)
        expected_sheet_ids = sorted({s for s, _r in keys})
        for call in sheet_in_calls:
            self.assertEqual(call.args[1], expected_sheet_ids)
        self.assertEqual(len(row_in_calls), 5)
        for call in row_in_calls[:-1]:
            self.assertEqual(len(call.args[1]), 200)

    def test_a8_op_isolation_distinct_breaker_counters(self) -> None:
        """A8: op isolation -- RPC failures raise
        ``billing_audit.client._consecutive_failures
        ['lookup_snapshot_provenance_bulk']`` and leave the
        ``fetch_snapshot_provenance`` entry at 0."""
        from postgrest.exceptions import APIError

        error = APIError({'code': 'PGRST202', 'message': 'missing'})
        client, _table = _make_fake_client(
            select_response=[{'sheet_id': 1, 'row_id': 2}]
        )
        _configure_rpc(client, side_effect=error)
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            fetch_snapshot_provenance([(1, 2)])
        self.assertEqual(
            client_mod._consecutive_failures.get(
                snapshot_store._PROVENANCE_RPC, 0
            ),
            1,
        )
        self.assertEqual(
            client_mod._consecutive_failures.get(
                'fetch_snapshot_provenance', 0
            ),
            0,
        )


def _configure_corroboration_probe(client, *, rows=None, side_effect=None):
    """Compose the corroboration-probe select chain
    (``.select('sheet_id').limit(1).execute()``) onto a client built
    by ``_make_fake_client`` (T2), WITHOUT modifying that fixture --
    a distinct terminal chain from the fallback's ``.in_().in_()``
    shape, so both can be configured independently on the same
    ``table.select.return_value`` mock.
    """
    limit_obj = client.schema.return_value.table.return_value.select \
        .return_value.limit.return_value
    if side_effect is not None:
        limit_obj.execute.side_effect = side_effect
    else:
        limit_obj.execute.return_value = mock.Mock(
            data=rows if rows is not None else []
        )
    return limit_obj


class TestFetchSnapshotProvenanceRpcEmptyCorroboration(
    RpcCharacterizationTestBase
):
    """P2 fix (coordinator fix round, 260813-nhn): a wrongly-applied
    RPC that always returns ``[]`` must not be silently trusted as
    genuine first-sight for a large key set -- corroborated by a
    bounded existence probe against ``snapshot_provenance``.
    """

    def test_rpc_zero_table_nonempty_is_fetch_failure_with_error_log(
        self,
    ) -> None:
        """(a) RPC returns zero rows (success), the corroboration
        probe finds the table non-empty -> 'fetch_failure' + an ERROR
        log naming the RPC function."""
        client, _table = _make_fake_client()
        _configure_rpc(client, response_rows=[])
        _configure_corroboration_probe(
            client, rows=[{'sheet_id': 1}]
        )
        keys = [(1, i) for i in range(100)]
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            with self.assertLogs(
                'billing_audit.snapshot_store', level='ERROR'
            ) as cm:
                rows, status = fetch_snapshot_provenance(keys)
        self.assertEqual(rows, {})
        self.assertEqual(status, 'fetch_failure')
        self.assertTrue(
            any(
                snapshot_store._PROVENANCE_RPC in r.getMessage()
                for r in cm.records
            )
        )

    def test_rpc_zero_table_empty_is_no_row(self) -> None:
        """(b) RPC returns zero rows, the corroboration probe finds
        the table genuinely empty -> 'no_row' (first seed after a
        fresh DDL apply must keep working)."""
        client, _table = _make_fake_client()
        _configure_rpc(client, response_rows=[])
        _configure_corroboration_probe(client, rows=[])
        keys = [(1, i) for i in range(100)]
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            rows, status = fetch_snapshot_provenance(keys)
        self.assertEqual(rows, {})
        self.assertEqual(status, 'no_row')

    def test_small_key_set_skips_the_corroboration_probe(self) -> None:
        """(c) key count at/under
        ``_RPC_EMPTY_CORROBORATE_MIN_KEYS`` skips the probe entirely
        -- the fallback/corroboration select chain is never touched."""
        client, table = _make_fake_client()
        _configure_rpc(client, response_rows=[])
        keys = [(1, i) for i in range(10)]
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ):
            rows, status = fetch_snapshot_provenance(keys)
        self.assertEqual(rows, {})
        self.assertEqual(status, 'no_row')
        table.select.assert_not_called()


class TestFetchViaInFallbackChunkCap(SnapshotStoreTestBase):
    """P3 fix (coordinator fix round, 260813-nhn): the all-or-nothing
    fallback select must refuse to run rather than issue an unbounded
    number of serial GETs when the RPC is missing.
    """

    def test_over_cap_chunk_count_returns_fetch_failure_no_calls(
        self,
    ) -> None:
        """Key set implying more chunks than ``_FALLBACK_MAX_CHUNKS``
        -> 'fetch_failure' with ZERO select calls issued."""
        from postgrest.exceptions import APIError

        error = APIError({'code': 'PGRST202', 'message': 'missing'})
        client, table = _make_fake_client(select_response=[])
        _configure_rpc(client, side_effect=error)
        # 3 distinct row ids worth of 200-id chunks (600 keys) with
        # the cap patched to 2 -> 3 > 2, over the cap.
        keys = [(10, i) for i in range(600)]
        with mock.patch(
            'billing_audit.snapshot_store.get_client', return_value=client
        ), mock.patch.object(snapshot_store, '_FALLBACK_MAX_CHUNKS', 2):
            rows, status = fetch_snapshot_provenance(keys)
        self.assertEqual(rows, {})
        self.assertEqual(status, 'fetch_failure')
        table.select.assert_not_called()


if __name__ == '__main__':
    unittest.main()
