"""INC-06 — abandoned shadow-parity workers must not hold the interpreter open.

Run 33579406295 (2026-09-02) finished every phase by 05:37Z and then sat 42
minutes in interpreter shutdown: ``run_shadow_delta_reads`` abandons stuck
delta-probe workers with ``shutdown(wait=False, cancel_futures=True)``, but
``_DaemonThreadPoolExecutor`` still registers each worker in
``concurrent.futures.thread._threads_queues`` and nothing removed them, so
``_python_exit`` (the ``threading._register_atexit`` hook) joined them until
Smartsheet closed the hung sockets. The job then crossed the 180-minute
runner ceiling during its last upload steps.

These tests pin that all three documented exit blockers are handled:

1. ``detach()`` removes this executor's workers from the atexit registry and
   is idempotent / safe on an executor that never started a worker.
2. A real child interpreter with a worker blocked forever exits promptly
   after ``shutdown + detach``; the control case without ``detach`` hangs
   (the failure mode the fix addresses).
3. ``run_shadow_delta_reads`` calls ``detach()`` after its abandon
   ``shutdown()``.
"""
import datetime
import pathlib
import subprocess
import sys
import threading
import unittest
from unittest import mock

import concurrent.futures.thread as _cf_thread

from pipeline.config import _DaemonThreadPoolExecutor

_REPO = str(pathlib.Path(__file__).resolve().parents[1])

# A worker blocked on an Event that is never set stands in for a delta-probe
# stuck in a socket read that Smartsheet has not closed yet.
_CHILD = """
import sys, threading
sys.path.insert(0, {repo!r})
from pipeline.config import _DaemonThreadPoolExecutor
ex = _DaemonThreadPoolExecutor(max_workers=2)
gate = threading.Event()
ex.submit(gate.wait)
ex.shutdown(wait=False, cancel_futures=True)
{detach}
print("ready", flush=True)
"""


class DetachTests(unittest.TestCase):

    def test_detach_removes_blocked_worker_from_atexit_registry(self):
        gate = threading.Event()
        ex = _DaemonThreadPoolExecutor(max_workers=2)
        try:
            ex.submit(gate.wait)
            workers = list(ex._threads)
            self.assertTrue(workers, "worker thread should exist")
            self.assertTrue(
                all(t in _cf_thread._threads_queues for t in workers),
                "workers are registered for the atexit join before detach",
            )
            ex.shutdown(wait=False, cancel_futures=True)
            detached = ex.detach()
            self.assertEqual(detached, len(workers))
            self.assertFalse(
                any(t in _cf_thread._threads_queues for t in workers),
                "detach must remove every worker from _threads_queues",
            )
        finally:
            gate.set()

    def test_detach_is_idempotent_and_safe_before_any_worker(self):
        ex = _DaemonThreadPoolExecutor(max_workers=1)
        self.assertEqual(ex.detach(), 0)
        gate = threading.Event()
        try:
            ex.submit(gate.wait)
            ex.shutdown(wait=False, cancel_futures=True)
            self.assertEqual(ex.detach(), 1)
            self.assertEqual(ex.detach(), 0)
        finally:
            gate.set()


class InterpreterExitTests(unittest.TestCase):
    """Real child interpreters: the only honest test of an atexit join."""

    @staticmethod
    def _spawn(detach_line: str) -> subprocess.Popen:
        code = _CHILD.format(repo=_REPO, detach=detach_line)
        return subprocess.Popen(
            [sys.executable, "-c", code],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            cwd=_REPO,
        )

    def test_exits_promptly_after_shutdown_and_detach(self):
        proc = self._spawn("ex.detach()")
        try:
            out, _ = proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _ = proc.communicate()
            self.fail("interpreter did not exit within 15 s after detach; "
                      f"child output: {out!r}")
        self.assertEqual(proc.returncode, 0, out)
        self.assertEqual(out.strip(), "ready")

    def test_control_hangs_without_detach(self):
        proc = self._spawn("pass")
        try:
            with self.assertRaises(subprocess.TimeoutExpired):
                proc.communicate(timeout=5)
        finally:
            proc.kill()
            proc.communicate()


class ParityDetachTests(unittest.TestCase):

    def test_run_shadow_delta_reads_detaches_after_abandon_shutdown(self):
        from pipeline import parity
        calls: list[str] = []

        class _Spy(_DaemonThreadPoolExecutor):
            def shutdown(self, wait=True, *, cancel_futures=False):
                calls.append(f"shutdown(wait={wait},cancel={cancel_futures})")
                return super().shutdown(
                    wait=wait, cancel_futures=cancel_futures)

            def detach(self):
                calls.append("detach")
                return super().detach()

        def fake_fetch(client, source, last_version, rows_modified_since):
            return {"escalate": False, "sheet": None, "version": 1,
                    "calls": 1}

        with mock.patch("pipeline.parity._DaemonThreadPoolExecutor", _Spy):
            parity.run_shadow_delta_reads(
                client=object(),
                source_sheets=[
                    {"id": 1, "name": "sheet-1", "column_mapping": {}}],
                watermarks={}, changed_row_ids_by_sheet={},
                session_start=datetime.datetime.now(),
                fetch_sheet_delta_fn=fake_fetch,
                compute_rows_modified_since_fn=lambda *a, **k: None,
                safety_window_minutes=15, max_minutes=10,
                rpc_timeout_sec=45, generation_headroom_min=2,
                time_budget_minutes=0, github_actions_mode=False,
                parallel_workers=2,
            )
        self.assertEqual(
            calls, ["shutdown(wait=False,cancel=True)", "detach"],
            "detach must follow the abandon shutdown, exactly once",
        )


if __name__ == "__main__":
    unittest.main()
