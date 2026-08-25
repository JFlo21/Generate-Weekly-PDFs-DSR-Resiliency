"""Supabase pipeline_memory writer.

Fail-open contract: no function in this module ever raises. A failure
here means "memory was not written this run" -- it must NEVER be
interpreted by a caller as "nothing changed" or be allowed to affect
Excel generation, the upload path, or the process exit code.

Logging discipline: personnel names observed on billing rows
(``foreman_observed`` / ``helper_observed`` / ``vac_crew_observed``, wired
in a later plan) are PII exactly like ``billing_audit``'s frozen names.
This module logs COUNTS and ERROR CODES ONLY -- never a per-row value.
Plan 10-01 only wires ``run_ledger`` (one row per run, no per-row PII),
but this discipline is documented here up front because every later
``pipeline_memory.writer`` function (row_state / row_event / group_state)
must follow it too.

Public surface (this plan):
- ``resolve_run_id()`` -- pure helper mirroring
  ``pipeline/orchestrate.py``'s run-id derivation (GITHUB_RUN_ID[.ATTEMPT]
  or a unique ``local-`` timestamp). Deliberately NOT a refactor/import of
  the original -- this module must stay independent of the facade.
- ``run_ledger_start(run_id, mode, release)`` / ``run_ledger_finish(run_id,
  **counters)`` -- the two ``pipeline_memory.run_ledger`` upserts, wired
  from ``pipeline/orchestrate.py::main()`` immediately after the
  "weekly run started" log event and immediately before the frozen
  ``run_summary.json`` write, respectively.
- ``get_counters()`` / ``_reset_counters_for_tests()`` -- module counters
  for observability; deliberately NOT added to the frozen 21-key
  ``run_summary.json`` contract (they live in ``run_ledger.notes`` and in
  one aggregate log line instead).
"""

from __future__ import annotations

import datetime
import logging
import os
import threading
from typing import Any

from pipeline_memory.client import get_client, with_retry
from pipeline_memory.client import _write_enabled as _client_write_enabled

# ── Module-level counters ───────────────────────────────────────────────
# Protected by ``_counters_lock`` for the same reason as
# ``billing_audit.writer``'s counters: even though Phase 10 only calls
# ``run_ledger_start``/``run_ledger_finish`` once each per run (no
# concurrency yet), later plans add a per-sheet loop that may parallelize.
_counters_lock = threading.Lock()
_counters: dict[str, int] = {
    "run_ledger_written": 0,
    "run_ledger_errored": 0,
}


def _bump_counter(key: str) -> None:
    """Atomically increment ``_counters[key]`` by 1, creating it if new."""
    with _counters_lock:
        _counters[key] = _counters.get(key, 0) + 1


def get_counters() -> dict[str, int]:
    """Return a snapshot of module counters (for ``run_ledger.notes``)."""
    with _counters_lock:
        return dict(_counters)


def _reset_counters_for_tests() -> None:
    """Zero the module counters. Test-only helper."""
    with _counters_lock:
        for k in list(_counters):
            _counters[k] = 0


def _sentry_capture_warning(tag_key: str, tag_value: Any,
                            extras: dict | None = None) -> None:
    """Emit a Sentry warning for a pipeline_memory write issue.

    Mirrors ``billing_audit/writer.py::_sentry_capture_warning`` --
    ``push_scope()`` so tags scope cleanly, never raises. No per-row PII
    is included -- tags/extras are aggregate identifiers only.
    """
    try:
        import sentry_sdk  # type: ignore
    except Exception:
        return
    try:
        with sentry_sdk.push_scope() as scope:
            scope.set_level("warning")
            scope.set_tag(tag_key, tag_value)
            for k, v in (extras or {}).items():
                scope.set_tag(k, v)
            sentry_sdk.capture_message(
                "pipeline_memory write issue",
                level="warning",
            )
    except Exception:
        # Never let Sentry plumbing break the pipeline.
        pass


def resolve_run_id() -> str:
    """Derive this run's memory run id.

    MIRRORS (does not import or refactor) the derivation at
    ``pipeline/orchestrate.py`` lines ~1270-1281:
        - ``f"{GITHUB_RUN_ID}.{GITHUB_RUN_ATTEMPT}"`` when both are set
        - the bare ``GITHUB_RUN_ID`` when only the id is set
        - a unique ``"local-"``-prefixed microsecond timestamp otherwise

    Deliberately independent of the facade's ``_billing_audit_run_id_env``
    local -- this module must not import ``generate_weekly_pdfs`` (that
    would load a second copy of the script and re-run its module-level
    side effects; see ``client.py``'s ``_sentry_breadcrumb`` docstring for
    the same rationale).
    """
    ga_run_id = os.getenv("GITHUB_RUN_ID", "")
    ga_run_attempt = os.getenv("GITHUB_RUN_ATTEMPT", "")
    if ga_run_id:
        if ga_run_attempt:
            return f"{ga_run_id}.{ga_run_attempt}"
        return ga_run_id
    return (
        f"local-{datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%S%fZ')}"
    )


def _utcnow_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def run_ledger_start(run_id: str, mode: str,
                      release: str | None = None) -> None:
    """Upsert the ``run_ledger`` 'start' row. NEVER raises.

    ``mode`` is always ``"full"`` in Phase 10 (D-07 -- every run is still
    a full read in shadow mode). Client-none guard -> flag guard -> build
    params -> ``with_retry``-wrapped upsert -> counter bump -> no return
    value (fail-open: callers cannot distinguish "wrote" from "skipped"
    by return value, matching the fire-and-forget shape at both call
    sites in ``orchestrate.py``).
    """
    client = get_client()
    if client is None:
        return
    if not _client_write_enabled():
        return

    payload = {
        "run_id": run_id,
        "mode": mode,
        "started_at": _utcnow_iso(),
        "release": release or "",
        "status": "running",
    }

    def _invoke():
        return (
            client.schema("pipeline_memory")
            .table("run_ledger")
            .upsert(payload, on_conflict="run_id")
            .execute()
        )

    result = with_retry(_invoke, op="run_ledger_upsert")
    if result is None:
        _bump_counter("run_ledger_errored")
        return
    _bump_counter("run_ledger_written")


# Direct ``run_ledger`` columns ``run_ledger_finish`` accepts by keyword.
# Anything else passed in ``**counters`` (e.g. the per-sheet memory-write
# counters wired in a later plan) is folded into the JSON ``notes`` column
# instead of becoming its own SQL column -- see the module docstring.
_RUN_LEDGER_FINISH_COLUMNS = (
    "sheets_checked",
    "sheets_changed",
    "rows_seen",
    "rows_changed",
    "groups_affected",
    "groups_generated",
)


def run_ledger_finish(run_id: str, **counters: Any) -> None:
    """Upsert the ``run_ledger`` 'finish' row. NEVER raises.

    ``counters`` may carry any of ``_RUN_LEDGER_FINISH_COLUMNS`` (missing
    ones default to 0) plus a ``status`` override (default ``"success"``).
    Everything else left in ``counters`` is folded into the JSON ``notes``
    column alongside the run's execution type -- so this phase adds NO
    new key to the frozen 21-key ``run_summary.json`` contract; memory
    counters live in ``run_ledger.notes`` instead.

    ``notes.execution_type`` reads the ``EXECUTION_TYPE`` env var (the
    same variable ``scripts/notion_sync.py`` already consumes, computed
    by the workflow's "Determine execution type" step: ``manual`` on
    ``workflow_dispatch``, ``weekly_comprehensive`` on the Monday
    ``0 5 * * 1`` deep run identified by cron identity, ``weekend_maintenance``
    on Sat/Sun, else ``production_frequent``; defaults to ``"manual"``
    outside GitHub Actions).
    """
    client = get_client()
    if client is None:
        return
    if not _client_write_enabled():
        return

    counters = dict(counters)  # local copy -- caller's dict is untouched
    status = counters.pop("status", "success")
    row_columns = {
        key: counters.pop(key, 0) for key in _RUN_LEDGER_FINISH_COLUMNS
    }
    notes: dict[str, Any] = {
        "execution_type": os.getenv("EXECUTION_TYPE", "manual"),
    }
    notes.update(counters)  # whatever's left: memory-specific counters

    payload: dict[str, Any] = {
        "run_id": run_id,
        "finished_at": _utcnow_iso(),
        "status": status,
        "notes": notes,
        **row_columns,
    }

    def _invoke():
        return (
            client.schema("pipeline_memory")
            .table("run_ledger")
            .upsert(payload, on_conflict="run_id")
            .execute()
        )

    result = with_retry(_invoke, op="run_ledger_upsert")
    if result is None:
        _bump_counter("run_ledger_errored")
        return
    _bump_counter("run_ledger_written")
