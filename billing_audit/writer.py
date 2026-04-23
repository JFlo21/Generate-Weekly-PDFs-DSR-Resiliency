"""Supabase attribution snapshot writer (shadow mode).

Writes only. No read / hydration path — that lands in the follow-up
PR. All public functions are silent no-ops when:
- Supabase credentials are unset or TEST_MODE is on.
- The relevant feature flag in ``billing_audit.feature_flag`` is off.
- A row does not meet the freeze criteria (missing row id, or
  ``Units Completed?`` unchecked).

Logging discipline: NEVER emit per-row details (WR, foreman, helper,
vac_crew names). Only aggregate counter summaries at INFO. This
mirrors the pipeline's ``_PII_LOG_MARKERS`` defense — billing-row
identifiers are PII and must not leak into Sentry Logs.
"""

from __future__ import annotations

import datetime
import logging
import re
from typing import Any

from billing_audit.client import get_client, get_flag, with_retry

# Mirrors ``_RE_SANITIZE_HELPER_NAME`` in ``generate_weekly_pdfs.py``.
# Anything that is not a word character (``[A-Za-z0-9_]``) or a dash
# is replaced with ``_``. The main loop applies the same sanitizer to
# ``wr_num`` before constructing ``history_key`` — the snapshot must
# agree so subsequent correlation between Supabase rows and the hash
# history survives.
_WR_SANITIZE = re.compile(r"[^\w\-]")

_FLAG_WRITE = "write_attribution_snapshot"
_FLAG_FINGERPRINT = "emit_assignment_fingerprint"


def _is_checked(value: Any) -> bool:
    """Inline ``is_checked`` clone — mirrors
    ``generate_weekly_pdfs.is_checked`` without importing it.

    The pipeline runs as ``python generate_weekly_pdfs.py``, so the
    running module is ``__main__``. Doing
    ``from generate_weekly_pdfs import is_checked`` from inside the
    freeze_row hot path would load a SECOND copy of the script
    module, re-executing Sentry init and every other module-level
    side effect. Keeping this inline is the only safe option for a
    writer that's called per-row in a tight loop.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in (
            "true", "checked", "yes", "1", "on"
        )
    return False

# Module-level counters. Exposed via ``get_counters()`` for
# ``run_summary.json``.
_counters: dict[str, int] = {
    "snapshots_written": 0,
    "snapshots_already_frozen": 0,
    "snapshots_errored": 0,
    "fingerprint_changes_detected": 0,
}

# Deduplication set for ``emit_run_fingerprint``. The
# ``pipeline_run`` PK is ``(wr, week_ending, run_id)`` — no variant
# dimension — so calling ``emit_run_fingerprint`` once per
# ``(wr, week, variant)`` group from the main loop would overwrite
# the same row multiple times per run AND cause spurious drift
# alerts when variants legitimately differ in fingerprint
# (primary rows vs helper rows vs VAC crew rows carry different
# personnel populations by construction). First-seen-wins matches
# the schema's PK intent.
_emitted_run_keys: set[tuple[str, str, str]] = set()


def _reset_counters_for_tests() -> None:
    """Zero the module counters. Test-only helper."""
    for k in _counters:
        _counters[k] = 0
    _emitted_run_keys.clear()


def get_counters() -> dict:
    """Return a snapshot of module counters for ``run_summary.json``.

    Keys: ``snapshots_written``, ``snapshots_already_frozen``,
    ``snapshots_errored``, ``fingerprint_changes_detected``.
    """
    return dict(_counters)


def any_flag_enabled() -> bool:
    """Cheap probe for whether any writer flag is currently on.

    Returns True if either ``write_attribution_snapshot`` or
    ``emit_assignment_fingerprint`` is enabled AND the Supabase
    client is reachable. Callers in the main pipeline can use this
    to skip per-group work (fingerprint computation, row loops) when
    both flags are off — otherwise we'd do the expensive prep for
    every group only for the writer to early-return inside each call.

    Flag reads are cached inside ``get_flag`` on success, so the
    first call fires one Supabase read and every subsequent call is
    a dict lookup.
    """
    if get_client() is None:
        return False
    return (
        get_flag(_FLAG_WRITE, default=False)
        or get_flag(_FLAG_FINGERPRINT, default=False)
    )


def fingerprint_flag_enabled() -> bool:
    """Narrower probe for just the fingerprint flag.

    Lets callers skip ``compute_assignment_fingerprint()`` and the
    per-group completed-count aggregation when only the snapshot
    write flag is on — the fingerprint path would no-op inside
    ``emit_run_fingerprint`` otherwise, wasting per-group work.
    Cached through ``get_flag``.
    """
    if get_client() is None:
        return False
    return get_flag(_FLAG_FINGERPRINT, default=False)


def _coerce_week_ending(value: Any) -> datetime.date | None:
    """Return a ``datetime.date`` or ``None``.

    The group processing loop stores ``__week_ending_date`` as a
    ``datetime.datetime``; accept either shape. Do NOT re-parse
    ``Weekly Reference Logged Date`` — the caller must pass the
    already-resolved value.
    """
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return None


def _sanitized_wr(row: dict) -> str:
    """Apply the pipeline's WR sanitizer to a row's Work Request #.

    Returns an empty string if the field is missing. Matches the
    main-loop ``wr_num`` construction exactly so snapshots correlate
    with ``history_key`` entries.
    """
    raw = row.get("Work Request #")
    if raw is None:
        return ""
    s = str(raw).split(".")[0]
    return _WR_SANITIZE.sub("_", s)[:50]


def _sentry_capture_warning(tag_key: str, tag_value: Any,
                            extras: dict | None = None) -> None:
    """Emit a Sentry warning for a mid-week assignment change.

    Uses ``sentry_sdk.capture_message`` directly inside a
    ``push_scope()`` so the tags scope cleanly and don't leak into
    unrelated events. The pipeline's
    ``sentry_capture_message_with_context`` helper is deliberately
    avoided here to keep this path callable from the backfill script
    (which does not import ``generate_weekly_pdfs``). No per-row PII
    is included — tags/extras are aggregate identifiers only (WR
    number and week ending, which are operational context, not
    personnel).
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
                "Mid-week assignment change detected "
                "(billing_audit fingerprint drift)",
                level="warning",
            )
    except Exception:
        # Never let Sentry plumbing break the pipeline.
        pass


def freeze_row(row: dict, release: str | None,
               run_id: str | None) -> None:
    """Upsert one row's personnel into ``attribution_snapshot``.

    First-write-wins via the ``billing_audit.freeze_attribution`` RPC.
    Silent no-op if the Supabase client is unavailable, the
    ``write_attribution_snapshot`` flag is off, or the row does not
    meet the freeze criteria. Failures are counted and logged in
    aggregate only.
    """
    client = get_client()
    if client is None:
        return
    if not get_flag(_FLAG_WRITE, default=False):
        return

    row_id = row.get("__row_id")
    if not isinstance(row_id, int):
        logging.warning(
            "⚠️ billing_audit.freeze_row: skipping row with missing or "
            "non-integer __row_id"
        )
        return

    if not _is_checked(row.get("Units Completed?")):
        return

    wr = _sanitized_wr(row)
    week_ending = _coerce_week_ending(row.get("__week_ending_date"))
    if not wr or week_ending is None:
        return

    # Normalize release / run_id to empty-string sentinels so RPC
    # params stay valid even when the deployment applies NOT NULL
    # to audit-metadata columns. Mirrors the main pipeline's
    # hoisted-env normalization and emit_run_fingerprint's own
    # coercion — keeps the writer API safe regardless of whether
    # the caller passed ``None`` (typed as Optional) or ``""``.
    release = release or ""
    run_id = run_id or ""

    params = {
        "p_wr": wr,
        "p_week_ending": week_ending.isoformat(),
        "p_smartsheet_row_id": row_id,
        "p_primary": row.get("Foreman"),
        "p_helper": row.get("__helper_foreman"),
        "p_helper_dept": row.get("__helper_dept"),
        "p_vac_crew": row.get("__vac_crew_name"),
        "p_pole": (
            row.get("Pole #")
            or row.get("Point #")
            or row.get("Point Number")
        ),
        "p_cu": row.get("CU") or row.get("Billable Unit Code"),
        "p_work_type": row.get("Work Type"),
        "p_release": release,
        "p_run_id": run_id,
    }

    def _invoke():
        return (
            client.schema("billing_audit")
            .rpc("freeze_attribution", params)
            .execute()
        )

    result = with_retry(_invoke, op="freeze_attribution")
    if result is None:
        _counters["snapshots_errored"] += 1
        return

    data = getattr(result, "data", None)
    source_run_id: Any = None
    if isinstance(data, dict):
        source_run_id = data.get("source_run_id")
    elif isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            source_run_id = first.get("source_run_id")
    else:
        source_run_id = data  # Some clients return scalar.

    if source_run_id is not None and str(source_run_id) == str(run_id or ""):
        _counters["snapshots_written"] += 1
    else:
        _counters["snapshots_already_frozen"] += 1


def emit_run_fingerprint(wr: str, week_ending: datetime.date,
                         content_hash: str, assignment_fp: str,
                         completed_count: int, total_count: int,
                         release: str, run_id: str) -> None:
    """Upsert one row into ``billing_audit.pipeline_run``.

    Before writing, fetch the prior run's ``assignment_fp`` for
    ``(wr, week_ending)``. If it exists, differs from the new value,
    AND at least one row in this group has ``Units Completed?``
    checked, emit a Sentry warning tagged
    ``billing.mid_week_assignment_change=True``. Silent no-op if the
    ``emit_assignment_fingerprint`` flag is off.
    """
    client = get_client()
    if client is None:
        return
    if not get_flag(_FLAG_FINGERPRINT, default=False):
        return
    if not wr or week_ending is None:
        return

    wr_sanitized = _WR_SANITIZE.sub("_", str(wr).split(".")[0])[:50]

    # Dedup: emit at most once per (wr, week_ending, run_id) in this
    # process. Subsequent callers for the same key (e.g. helper /
    # vac_crew variants in the same group loop) no-op. Matches the
    # ``pipeline_run`` schema PK and avoids pipeline_run overwrites
    # + cross-variant drift false-positives. The dedup key is
    # recorded only AFTER a successful upsert so a transient failure
    # on the first variant doesn't permanently suppress the fallback
    # attempts from subsequent variants in the same run.
    dedup_key = (wr_sanitized, week_ending.isoformat(), run_id or "")
    if dedup_key in _emitted_run_keys:
        return

    # ── Look up prior fingerprint for this (wr, week_ending) ──
    def _fetch_prior():
        return (
            client.schema("billing_audit")
            .table("pipeline_run")
            .select("assignment_fp,run_id")
            .eq("wr", wr_sanitized)
            .eq("week_ending", week_ending.isoformat())
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

    prior = with_retry(_fetch_prior, op="pipeline_run")
    prior_fp: str | None = None
    if prior is not None:
        rows = getattr(prior, "data", None) or []
        if rows and isinstance(rows[0], dict):
            prior_fp = rows[0].get("assignment_fp")

    # ── Insert / upsert the new run row ──
    payload = {
        "wr": wr_sanitized,
        "week_ending": week_ending.isoformat(),
        "run_id": run_id or "",
        "content_hash": content_hash,
        "assignment_fp": assignment_fp,
        "completed_count": int(completed_count),
        "total_count": int(total_count),
        "release": release or "",
    }

    def _upsert():
        return (
            client.schema("billing_audit")
            .table("pipeline_run")
            .upsert(payload, on_conflict="wr,week_ending,run_id")
            .execute()
        )

    upsert_result = with_retry(_upsert, op="pipeline_run")
    if upsert_result is None:
        # Upsert exhausted its retry budget. Do NOT record the dedup
        # key — a subsequent variant call in the same run gets a
        # fresh attempt, which is the intended resilience behavior
        # for transient Supabase/network failures.
        return

    # Only now is it safe to dedup. The row is in Supabase.
    _emitted_run_keys.add(dedup_key)

    # ── Drift detection ──
    if (
        prior_fp is not None
        and prior_fp != assignment_fp
        and completed_count > 0
    ):
        _counters["fingerprint_changes_detected"] += 1
        _sentry_capture_warning(
            "billing.mid_week_assignment_change",
            True,
            extras={
                "billing.wr": wr_sanitized,
                "billing.week_ending": week_ending.isoformat(),
            },
        )
