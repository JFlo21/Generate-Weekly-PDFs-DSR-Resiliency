"""Direct tests for ``billing_audit/snapshot_store.py``.

Started as the IN-05 fix lock (260812-jqx review): the
``fetch_snapshot_provenance`` "NEVER raises" contract had a hole --
``get_client()``, the ``_global_disable_reason`` peek, and the key
coercions ran OUTSIDE the try/except, so an exception there escaped
despite the docstring. These tests pin the contract at the module
boundary (the caller-side wrap in ``pipeline/snapshot_drift.py`` is
belt-and-suspenders, not the contract). Chips at WR-05 (zero direct
snapshot_store coverage); the fuller suite remains a follow-up.
"""

from __future__ import annotations

import unittest
from unittest import mock

from billing_audit.snapshot_store import fetch_snapshot_provenance


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


if __name__ == '__main__':
    unittest.main()
