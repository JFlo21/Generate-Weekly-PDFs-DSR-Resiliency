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
- ``HASH_FIELDS`` / ``compute_content_hash()`` / ``_row_to_payload()`` /
  ``upsert_rows_bulk()`` -- the Python<->SQL contract for ``row_state`` /
  ``upsert_rows_bulk``, mechanically verified against
  ``pipeline_memory/schema.sql`` in ``tests/test_pipeline_memory_shadow.py``.
  Plan 10-01 (Task 3) shipped a minimal, unchunked version of this
  contract; plan 10-02 (Task 2) is the authoritative version: RAW mapped
  columns for ``foreman_observed`` / ``helper_observed`` /
  ``vac_crew_observed`` (never the pipeline's resolved/gated derivatives),
  WR sanitization, caller-resolved ``week_ending`` / ``snapshot_date``,
  and ``_CHUNK_ROWS``-bounded chunking (10-RESEARCH.md Pitfall 4).
  ``upsert_rows_bulk()`` is wired from ``pipeline/orchestrate.py`` in
  plan 10-02 (Task 3) via a per-sheet loop with its own time sub-budget --
  this module still issues zero Smartsheet calls and owns none of that
  loop's control flow.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import re
import threading
from typing import Any, Callable

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


def _bump_counter_by(key: str, n: int) -> None:
    """Atomically increment ``_counters[key]`` by ``n`` (no-op if n<=0)."""
    if n <= 0:
        return
    with _counters_lock:
        _counters[key] = _counters.get(key, 0) + n


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
    ones default to 0), a ``mode`` override (default ``"full"`` -- Phase
    10 is always a full read, matching ``run_ledger_start``'s hard-coded
    call-site value), plus a ``status`` override (default ``"success"``).
    Everything else left in ``counters`` is folded into the JSON ``notes``
    column alongside the run's execution type -- so this phase adds NO
    new key to the frozen 21-key ``run_summary.json`` contract; memory
    counters live in ``run_ledger.notes`` instead.

    ``mode`` MUST be present in this upsert's payload even though the
    'start' row already set it: ``schema.sql``'s ``mode`` column is
    ``NOT NULL`` with no ``DEFAULT``, and PostgREST's merge-duplicates
    upsert builds a single ``INSERT ... ON CONFLICT (run_id) DO UPDATE``
    statement scoped to only the payload's own columns -- Postgres
    validates the proposed row against NOT NULL constraints before
    conflict resolution, so omitting ``mode`` here raises a real 23502
    (not_null_violation) even though the actual write is an UPDATE of an
    existing row, not an INSERT. Confirmed live against project
    poeyztlmsawfoqlanucc during plan 10-06 Task 3 (2026-08-25): every
    'finish' upsert failed 400/23502 until this fix, so no shadow run
    before this commit ever persisted its finish row.

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
    mode = counters.pop("mode", "full")
    row_columns = {
        key: counters.pop(key, 0) for key in _RUN_LEDGER_FINISH_COLUMNS
    }
    notes: dict[str, Any] = {
        "execution_type": os.getenv("EXECUTION_TYPE", "manual"),
    }
    notes.update(counters)  # whatever's left: memory-specific counters

    payload: dict[str, Any] = {
        "run_id": run_id,
        "mode": mode,
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


# ── sheet_registry payload contract (plan 10-03 Task 1) ────────────────────

def upsert_sheet_registry(
    sheets: list[dict[str, Any]],
    run_id: str,
    kind_resolver: Callable[[Any], str],
    sheet_versions: dict[Any, int] | None,
) -> None:
    """Best-effort bulk upsert of ``sheet_registry``. NEVER raises.

    ``sheets`` is ``discover_source_sheets()``'s return list verbatim
    (each dict: ``{'id', 'name', 'column_mapping'}`` -- Phase-09-frozen
    contract). ``kind_resolver`` and ``sheet_versions`` are supplied by
    the CALLER (``pipeline/orchestrate.py``) so this package keeps
    importing nothing from ``pipeline.*`` (the writer-boundary contract):
    the resolver reads ``pipeline.discovery``'s live-proxy globals
    (``SUBCONTRACTOR_SHEET_IDS`` / ``_FOLDER_DISCOVERED_SUB_IDS`` /
    ``_FOLDER_DISCOVERED_ORIG_IDS``) at call time, and ``sheet_versions``
    is ``pipeline.fetch.get_last_sheet_versions()``'s snapshot.

    ``folder_id`` is deliberately OMITTED from the payload -- it is not
    on the discovery return dict and stays a reserved, NULL column this
    phase (10-03-PLAN.md flagged assumption).

    Empty input performs ZERO calls, checked before the client/flag
    guards, same as ``upsert_rows_bulk``. Issues exactly ONE table
    upsert with ``on_conflict="sheet_id"`` -- so a single row's write
    failure fails the whole call; that's acceptable here (the whole
    registry is small, one call per run) unlike the row-level bulk path.
    ``run_id`` is accepted for call-site symmetry with the other writer
    entry points but is not a ``sheet_registry`` column (no ``run_id``
    column on this table).
    """
    del run_id

    if not sheets:
        return

    client = get_client()
    if client is None:
        return
    if not _client_write_enabled():
        return

    versions = sheet_versions or {}
    now = _utcnow_iso()
    payload: list[dict[str, Any]] = []
    for sheet in sheets:
        sheet_id = sheet.get("id")
        payload.append({
            "sheet_id": sheet_id,
            "name": sheet.get("name"),
            "kind": kind_resolver(sheet_id),
            "column_mapping": sheet.get("column_mapping") or {},
            "last_sheet_version": versions.get(sheet_id),
            "last_read_at": now,
            "last_full_read_at": now,
            "active": True,
            "updated_at": now,
        })

    def _invoke():
        return (
            client.schema("pipeline_memory")
            .table("sheet_registry")
            .upsert(payload, on_conflict="sheet_id")
            .execute()
        )

    result = with_retry(_invoke, op="sheet_registry_upsert")
    if result is None:
        _bump_counter_by("sheets_registry_errored", len(payload))
        return
    _bump_counter_by("sheets_registry_written", len(payload))


# ── group_state payload contract (plan 10-03 Task 2) ────────────────────────

def bump_group_state_withheld(n: int) -> None:
    """Record ``n`` ``group_state`` records withheld by the caller's
    crash-consistency gate (a group whose upload did not fully complete
    this run). A tiny public counter-only entry point -- the withhold
    DECISION stays in ``pipeline/orchestrate.py`` (which already owns
    the per-group upload-ok/had-error maps from the existing durable-
    hash flush), while the counter itself lives alongside every other
    ``pipeline_memory`` counter in this module's ``get_counters()``.
    """
    _bump_counter_by("group_state_withheld", n)


def upsert_group_state(records: list[dict[str, Any]], run_id: str) -> None:
    """Best-effort bulk upsert of ``group_state``. NEVER raises.

    Each ``records`` entry: ``wr``, ``week_ending`` (an ISO date string,
    already resolved by the caller), ``variant``, ``identifier``,
    ``target_sheet_id``, ``content_hash``, ``row_count``, and
    OPTIONALLY ``attachment_id`` / ``attachment_name``.

    Attachment keys are included in a payload row ONLY when a non-None
    ``attachment_id`` was supplied -- an omitted key relies on
    PostgREST building its ``ON CONFLICT DO UPDATE SET`` list from the
    payload's own keys, so a prior run's attachment id/name is never
    clobbered by a run whose leg reported ``'skipped'`` (nothing
    attached this run). Confirmed empirically at plan 10-05's live
    smoke; if this assumption does not hold in practice, the fix is a
    small COALESCE-based RPC, not a null write.

    Empty input performs ZERO calls, checked before the client/flag
    guards, same as ``upsert_rows_bulk`` / ``upsert_sheet_registry``.
    Issues exactly ONE table upsert with
    ``on_conflict="wr,week_ending,variant,identifier,target_sheet_id"``
    -- the five-part key promoted (over the design draft's four-part
    key) so a ``reduced_sub`` fan-out's two legs each get their own row
    instead of the second overwriting the first's ``attachment_id``
    (plan 10-01's assumption_delta_decision).
    """
    if not records:
        return

    client = get_client()
    if client is None:
        return
    if not _client_write_enabled():
        return

    payload: list[dict[str, Any]] = []
    for rec in records:
        row: dict[str, Any] = {
            "wr": rec.get("wr"),
            "week_ending": rec.get("week_ending"),
            "variant": rec.get("variant"),
            "identifier": rec.get("identifier") or "",
            "target_sheet_id": rec.get("target_sheet_id"),
            "content_hash": rec.get("content_hash"),
            "row_count": rec.get("row_count"),
            "source": "live",
            "last_generated_run": run_id,
            "last_verified_run": run_id,
        }
        attachment_id = rec.get("attachment_id")
        if attachment_id is not None:
            row["attachment_id"] = attachment_id
            row["attachment_name"] = rec.get("attachment_name")
        payload.append(row)

    def _invoke():
        return (
            client.schema("pipeline_memory")
            .table("group_state")
            .upsert(
                payload,
                on_conflict="wr,week_ending,variant,identifier,target_sheet_id",
            )
            .execute()
        )

    result = with_retry(_invoke, op="group_state_upsert")
    if result is None:
        _bump_counter_by("group_state_errored", len(payload))
        return
    _bump_counter_by("group_state_written", len(payload))


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


_CHUNK_ROWS = 500  # mirrors billing_audit/writer.py::prefetch_attribution's
# _CHUNK_SIZE precedent -- "one RPC per sheet" (MEM-03) means "not one RPC
# per row", not "unbounded". Largest observed source sheet is 6,054 rows
# (10-RESEARCH.md Pitfall 4); a row_state payload carries far more bytes
# per row than the sibling package's 2-field (wr, week_ending) pairs, so
# betting on the ~1MB PostgREST body limit for an unchunked per-sheet call
# is the failure mode Pitfall 4 describes.

# Mirrors billing_audit/writer.py::_WR_SANITIZE exactly, so row_state.wr
# joins with group_state.wr and with the history_key entries the pipeline
# already writes.
_WR_SANITIZE = re.compile(r"[^\w\-]")


def _sanitized_wr(row_data: dict[str, Any]) -> str:
    """Apply the pipeline's WR sanitizer to ``row_data['Work Request #']``.

    Mirrors ``billing_audit/writer.py::_sanitized_wr`` exactly (raw ->
    ``str(raw).split(".")[0]`` -> sanitize -> ``[:50]``). Returns ``""``
    when the field is missing -- never ``None`` -- because
    ``row_state.wr`` is NOT NULL and an empty string is a valid (if
    unhelpful) value, matching the sibling writer's own contract.
    """
    raw = row_data.get("Work Request #")
    if raw is None:
        return ""
    s = str(raw).split(".")[0]
    return _WR_SANITIZE.sub("_", s)[:50]


def _is_checked(value: Any) -> bool:
    """Inline clone of ``pipeline.utils.is_checked``.

    This package imports NOTHING from ``pipeline.*`` (the writer-boundary
    contract, mechanically verified in
    tests/test_pipeline_memory_shadow.py). Mirrors
    ``billing_audit/writer.py::_is_checked``, which exists for the
    identical reason -- keeping ``pipeline_memory`` independent of the
    facade/engine import graph.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in ("true", "checked", "yes", "1", "on")
    return False


def _coerce_date(value: Any) -> str | None:
    """Return an ISO-8601 date string, or ``None``.

    Mirrors ``billing_audit/writer.py::_coerce_week_ending``: accepts an
    ALREADY-RESOLVED ``datetime.date`` or ``datetime.datetime`` only, and
    explicitly REFUSES to parse a raw string -- the caller
    (``pipeline/orchestrate.py``) resolves ``'Weekly Reference Logged
    Date'`` / ``'Snapshot Date'`` with the same
    ``pipeline.utils.excel_serial_to_date`` parser ``group_source_rows``
    uses, and passes the already-resolved value through to
    ``upsert_rows_bulk`` / ``_row_to_payload``. Keeps this package
    importing nothing from ``pipeline.*``.
    """
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    return None


def _row_to_payload(
    row_data: dict[str, Any],
    run_id: str,
    week_ending: Any,
    snapshot_date: Any,
) -> dict[str, Any] | None:
    """Map one already-fetched Smartsheet row dict + its caller-resolved
    dates to an ``upsert_rows_bulk`` payload entry (one element of
    ``p_rows``).

    Returns ``None`` (never raises, never fabricates a value) when
    ``row_data['__row_id']`` is missing or not an ``int`` -- mirroring
    ``billing_audit/writer.py::freeze_row``'s identical guard. The caller
    (``upsert_rows_bulk``) is responsible for skipping a ``None`` and
    bumping ``rows_skipped_bad_row_id``; this function stays a pure
    mapper with no counter side effects, so it's directly testable.

    CRITICAL (10-RESEARCH.md Pitfall 2, CONFIRMED historical defect --
    .planning/debug/unknown-foreman-helper-shadow-2026-08-24.md):
    ``foreman_observed`` / ``helper_observed`` / ``vac_crew_observed``
    read the RAW mapped Smartsheet columns (``"Foreman"``,
    ``"Foreman Helping?"``, ``"VAC Crew Helping?"``) -- NEVER the
    pipeline's resolved/gated derivatives. ``__effective_user``
    substitutes the literal sentinel ``"Unknown Foreman"`` when the
    ``Foreman`` lookup is blank, and freezing that sentinel as a real
    person is exactly the defect that corrupted 93 WRs / 5,824 rows in
    ``billing_audit.attribution_snapshot``. ``__helper_foreman`` /
    ``__vac_crew_name`` are ABSENT on any row whose completion checkbox
    is unchecked (fetch.py's gating, lines ~537-624), which would
    silently drop a real observed name even though the row plainly shows
    who was helping. Memory records what was literally on the row, not
    the pipeline's Excel-generation business decision.

    Blank/absent values normalize to ``None`` (never a placeholder
    string) so a later re-observation can freely replace them.
    """
    del run_id  # per-call RPC parameter, not a per-row payload field

    row_id = row_data.get("__row_id")
    if not isinstance(row_id, int):
        return None

    cu = row_data.get("CU") or row_data.get("Billable Unit Code") or None
    pole = (
        row_data.get("Pole #")
        or row_data.get("Point #")
        or row_data.get("Point Number")
        or None
    )

    payload: dict[str, Any] = {
        "row_id": row_id,
        "wr": _sanitized_wr(row_data),
        "week_ending": _coerce_date(week_ending),
        "snapshot_date": _coerce_date(snapshot_date),
        "cu": cu,
        "pole": pole,
        "work_type": row_data.get("Work Type") or None,
        "quantity": row_data.get("Quantity"),
        "units_total_price": row_data.get("Units Total Price"),
        "units_completed": _is_checked(row_data.get("Units Completed?")),
        "foreman_observed": row_data.get("Foreman") or None,
        "helper_observed": row_data.get("Foreman Helping?") or None,
        "helper_completed": _is_checked(
            row_data.get("Helping Foreman Completed Unit?")
        ),
        "helper_dept": row_data.get("Helper Dept #") or None,
        "helper_job": row_data.get("Helper Job #") or None,
        "vac_crew_observed": row_data.get("VAC Crew Helping?") or None,
        "vac_completed": _is_checked(row_data.get("Vac Crew Completed Unit?")),
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

    Returns the affected ``(wr, week_ending)`` set from every SUCCESSFUL
    chunk (an empty set on total failure or a total no-op) -- callers
    MUST treat an empty return as "no memory update happened this
    sheet", NEVER as "nothing changed".

    Consumes rows ALREADY fetched by the pipeline this run -- never
    issues its own Smartsheet call (10-RESEARCH.md Anti-Pattern:
    duplicating the Smartsheet read). Each row's ``week_ending`` /
    ``snapshot_date`` are read from ``__mem_week_ending`` /
    ``__mem_snapshot_date`` -- the ALREADY-RESOLVED (datetime/date/None)
    values the caller (``pipeline/orchestrate.py``) sets onto each row
    dict using the SAME parser ``group_source_rows`` uses, before calling
    this function.

    Empty input is checked FIRST, before the client/flag guards, so it
    performs ZERO PostgREST calls (not even a client-construction
    attempt) -- distinct from "one row -> one call". A row with a
    missing/non-integer ``__row_id`` is skipped (counted, never sent).

    Chunked at ``_CHUNK_ROWS`` rows per RPC call (10-RESEARCH.md
    Pitfall 4): a chunk failure bumps ``rows_upsert_errored`` by that
    chunk's row count and moves on to the remaining chunks -- one
    aggregate WARNING covers the whole call, never one per chunk.
    """
    if not rows:
        return set()

    client = get_client()
    if client is None:
        return set()
    if not _client_write_enabled():
        return set()

    payloads: list[dict[str, Any]] = []
    for row in rows:
        payload = _row_to_payload(
            row,
            run_id,
            row.get("__mem_week_ending"),
            row.get("__mem_snapshot_date"),
        )
        if payload is None:
            _bump_counter("rows_skipped_bad_row_id")
            continue
        payloads.append(payload)

    if not payloads:
        return set()

    chunks = [
        payloads[i:i + _CHUNK_ROWS]
        for i in range(0, len(payloads), _CHUNK_ROWS)
    ]

    affected: set[tuple[Any, Any]] = set()
    errored_rows = 0
    for chunk in chunks:
        def _invoke(_p=chunk):
            return (
                client.schema("pipeline_memory")
                .rpc(
                    "upsert_rows_bulk",
                    {
                        "p_sheet_id": sheet_id,
                        "p_run_id": run_id,
                        "p_rows": _p,
                    },
                )
                .execute()
            )

        result = with_retry(_invoke, op="upsert_rows_bulk")
        if result is None:
            errored_rows += len(chunk)
            continue
        affected |= _parse_affected_set(result)

    _bump_counter_by("rows_upsert_sent", len(payloads))
    _bump_counter_by("rows_upsert_changed", len(affected))
    if errored_rows:
        _bump_counter_by("rows_upsert_errored", errored_rows)
        logging.warning(
            f"⚠️ pipeline_memory upsert_rows_bulk: {errored_rows}/"
            f"{len(payloads)} row(s) failed to upsert for sheet "
            f"{sheet_id} (across {len(chunks)} chunk(s))."
        )
    return affected
