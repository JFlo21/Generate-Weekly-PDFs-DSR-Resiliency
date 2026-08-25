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
- ``HASH_FIELDS`` / ``compute_content_hash()`` / ``build_row_payload()`` /
  ``upsert_rows_bulk()`` -- Task 3's Python<->SQL contract lock for
  ``row_state`` / ``upsert_rows_bulk`` (mechanically verified against
  ``pipeline_memory/schema.sql`` in ``tests/test_pipeline_memory_shadow.py``).
  SCOPE NOTE: this is the payload-builder + single-call RPC wrapper only,
  deliberately unchunked and NOT wired from ``pipeline/orchestrate.py`` --
  plan 10-02 owns the per-sheet loop, chunking for the largest sheets
  (10-RESEARCH.md Pitfall 4), its own time sub-budget, and the
  orchestrator wiring. Reuse these functions there rather than
  reimplementing the hash/payload contract a second time.
"""

from __future__ import annotations

import datetime
import hashlib
import json
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


# ── row_state payload contract (Task 3 -- see module docstring SCOPE NOTE) ─

# The fixed, explicitly enumerated field tuple that feeds
# ``row_state.content_hash``, IN THIS ORDER, so two observations of the
# same row produce a byte-identical hash regardless of the source dict's
# own key order (MEM-02 ordering invariant, 10-RESEARCH.md Code Examples).
# Deliberately EXCLUDES ``row_modified_at`` / ``first_seen_run`` /
# ``last_seen_run`` / ``last_changed_run`` -- including a run-varying
# field would make the hash change on every re-read regardless of
# billing content, producing a ``row_event`` on every run and failing
# MEM-02's "second run with no edits adds zero row_event rows"
# acceptance criterion (10-RESEARCH.md Pitfall 3).
HASH_FIELDS: tuple[str, ...] = (
    "wr",
    "week_ending",
    "snapshot_date",
    "cu",
    "pole",
    "work_type",
    "quantity",
    "units_total_price",
    "units_completed",
    "foreman_observed",
    "helper_observed",
    "helper_completed",
    "helper_dept",
    "helper_job",
    "vac_crew_observed",
    "vac_completed",
)


def compute_content_hash(payload: dict[str, Any]) -> str:
    """SHA-256 hex digest over ``HASH_FIELDS``, read in ``HASH_FIELDS``'
    fixed order from ``payload`` -- deterministic regardless of
    ``payload``'s own key insertion order (mirrors
    ``pipeline/change_detection.py::calculate_data_hash``'s sorted-key
    discipline). Missing keys hash as ``None`` via ``dict.get``, so a
    blank/absent observation still produces a stable, non-empty hash.
    """
    ordered = {key: payload.get(key) for key in HASH_FIELDS}
    canonical = json.dumps(ordered, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_row_payload(row_data: dict[str, Any], run_id: str) -> dict[str, Any]:
    """Map one already-fetched Smartsheet row dict to an
    ``upsert_rows_bulk`` payload entry (one element of ``p_rows``).

    CRITICAL (10-RESEARCH.md Pitfall 2, CONFIRMED historical defect --
    .planning/debug/unknown-foreman-helper-shadow-2026-08-24.md):
    ``foreman_observed`` reads the RAW ``"Foreman"`` column, NEVER
    ``row_data["__effective_user"]`` (the pipeline's *resolved* value,
    which substitutes the sentinel ``"Unknown Foreman"`` when blank --
    freezing that sentinel is exactly what corrupted 93 WRs / 5,824 rows
    in ``billing_audit.attribution_snapshot``). ``helper_observed`` /
    ``vac_crew_observed`` read the already-raw ``__helper_foreman`` /
    ``__vac_crew_name`` fields directly -- no sentinel fallback exists on
    those, so they are safe to read as-is (10-RESEARCH.md Code Examples).

    Blank/absent values are normalized to ``None`` (never a placeholder
    string) so a re-observation can freely replace them later.
    ``run_id`` is accepted for parity with the RPC's per-sheet call
    shape (``p_run_id`` is a call-level parameter, not a per-row payload
    field) -- unused here but kept in the signature so callers don't
    need a separate no-arg builder.
    """
    del run_id  # per-call RPC parameter, not a per-row payload field
    payload: dict[str, Any] = {
        "row_id": row_data.get("__row_id"),
        "wr": row_data.get("Work Request #") or None,
        "week_ending": row_data.get("__week_ending_iso") or None,
        "snapshot_date": row_data.get("__snapshot_date_iso") or None,
        "cu": row_data.get("CU") or None,
        "pole": row_data.get("Pole #") or None,
        "work_type": row_data.get("Work Type") or None,
        "quantity": row_data.get("Quantity"),
        "units_total_price": row_data.get("Units Total Price"),
        "units_completed": bool(row_data.get("Units Completed?")),
        "foreman_observed": row_data.get("Foreman") or None,
        "helper_observed": row_data.get("__helper_foreman") or None,
        "helper_completed": bool(
            row_data.get("Helping Foreman Completed Unit?")
        ),
        "helper_dept": row_data.get("__helper_dept") or None,
        "helper_job": row_data.get("__helper_job") or None,
        "vac_crew_observed": row_data.get("__vac_crew_name") or None,
        "vac_completed": bool(row_data.get("Vac Crew Completed Unit?")),
        "row_modified_at": row_data.get("__row_modified_at"),
    }
    payload["content_hash"] = compute_content_hash(payload)
    return payload


def _parse_affected_set(result: Any) -> set[tuple[Any, Any]]:
    """Extract the ``(wr, week_ending)`` affected set from an RPC
    response. Tolerant of any non-list-of-dicts shape (returns an empty
    set rather than raising) -- fail-open extends to response parsing,
    not just the transport call.
    """
    data = getattr(result, "data", None) or []
    affected: set[tuple[Any, Any]] = set()
    for row in data:
        if isinstance(row, dict):
            affected.add((row.get("wr"), row.get("week_ending")))
    return affected


def upsert_rows_bulk(sheet_id: int, run_id: str,
                      rows: list[dict[str, Any]]) -> set[tuple[Any, Any]]:
    """Best-effort bulk row upsert for ONE sheet. NEVER raises.

    Returns the affected ``(wr, week_ending)`` set on success, or an
    EMPTY set on any no-op or failure (empty input, client unavailable,
    flag off, RPC error) -- callers MUST treat an empty return as "no
    memory update happened this sheet", NEVER as "nothing changed".

    Consumes rows ALREADY fetched by the pipeline this run -- never
    issues its own Smartsheet call (10-RESEARCH.md Anti-Pattern:
    duplicating the Smartsheet read).

    Empty input is checked FIRST, before the client/flag guards, so it
    performs ZERO PostgREST calls (not even a client-construction
    attempt) -- distinct from "one row -> one call".
    """
    if not rows:
        return set()

    client = get_client()
    if client is None:
        return set()
    if not _client_write_enabled():
        return set()

    payload = [build_row_payload(row, run_id) for row in rows]

    def _invoke():
        return (
            client.schema("pipeline_memory")
            .rpc(
                "upsert_rows_bulk",
                {
                    "p_sheet_id": sheet_id,
                    "p_run_id": run_id,
                    "p_rows": payload,
                },
            )
            .execute()
        )

    result = with_retry(_invoke, op="upsert_rows_bulk")
    if result is None:
        _bump_counter("rows_upsert_errored")
        return set()
    _bump_counter("rows_upsert_written")
    return _parse_affected_set(result)
