"""Supabase attribution snapshot writer + reader.

Public surface:
- Writers: ``freeze_row`` (per-row attribution freeze) and
  ``emit_run_fingerprint`` (per-WR/week run fingerprint upsert).
- Reader: ``lookup_attribution(wr, week_ending, smartsheet_row_id)``
  (Phase 1.1 / Bug C / SUB-11) — returns the frozen attribution dict
  ``{helper, helper_dept, source_run_id}`` for ONE row, or ``None``
  if no snapshot exists yet. Calls the ``lookup_attribution``
  PostgREST RPC documented in ``billing_audit/schema.sql``.

All public functions are silent no-ops when:
- Supabase credentials are unset or TEST_MODE is on.
- The relevant feature flag in ``billing_audit.feature_flag`` is
  off (writers only — the reader's kill switch is at the caller via
  ``SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED`` because per-call
  reads must be globally fast-skippable without a round-trip to the
  flag table).
- The PostgREST schema is not exposed / auth has expired (PGRST106 /
  PGRST301 / PGRST302 trip the run-global kill switch per
  ``billing_audit.client._classify_postgrest_error``, after which
  ``get_client()`` returns ``None`` and all subsequent ops short-circuit).
- A row does not meet the freeze criteria (missing row id, or
  ``Units Completed?`` unchecked).

Logging discipline: NEVER emit per-row details (WR, foreman, helper,
vac_crew names). Only aggregate counter summaries at INFO. This
mirrors the pipeline's ``_PII_LOG_MARKERS`` defense — billing-row
identifiers are PII and must not leak into Sentry Logs.

**Reader PII-out exception:** ``lookup_attribution`` returns helper
TEXT in its return dict — this is the one place per-row PII leaves
the package as a *value*, not as a log line. Callers MUST treat the
returned ``helper`` string as PII (group-key embedding, filename
embedding) and follow the same redaction rules they use for live
Smartsheet ``Foreman Helping?`` values.
"""

from __future__ import annotations

import atexit
import datetime
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from billing_audit.client import (
    get_client,
    get_flag,
    is_flag_resolved,
    with_retry,
)

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
# ``run_summary.json``. Protected by ``_counters_lock`` so concurrent
# ``freeze_row`` callers (parallelized via ThreadPoolExecutor in the
# main pipeline since 2026-04-25) cannot lose increments to a
# read-modify-write race. ``dict[k] += 1`` compiles to multiple
# bytecodes (``BINARY_SUBSCR`` + ``BINARY_ADD`` + ``STORE_SUBSCR``);
# the GIL holds each bytecode atomic but a thread can be preempted
# between them, so two concurrent threads can both read the same
# starting value, both compute +1, and store the same final value
# — losing one increment. The lock makes counter writes exact even
# under contention; ``get_counters()`` also takes the lock so the
# returned snapshot is internally consistent.
_counters_lock = threading.Lock()
_counters: dict[str, int] = {
    "snapshots_written": 0,
    "snapshots_already_frozen": 0,
    "snapshots_errored": 0,
    "fingerprint_changes_detected": 0,
}


def _bump_counter(key: str) -> None:
    """Atomically increment ``_counters[key]`` by 1.

    Use this instead of ``_counters[key] += 1`` everywhere — the
    bare augmented-assignment is NOT atomic across threads (see
    ``_counters_lock`` docstring).
    """
    with _counters_lock:
        _counters[key] = _counters.get(key, 0) + 1


# ── Shared ThreadPoolExecutor for parallel freeze_row dispatch ─────
# The main pipeline parallelizes per-row ``freeze_row`` calls within
# each group via ThreadPoolExecutor. With ~1900 groups per typical
# run, creating a new executor per group would mean ~1900 executor
# constructions and ~15,000 thread-join operations (8 workers ×
# 1900 groups) — small per-event but non-trivial in aggregate, and
# noisy in operational debugging (thread-name collisions across
# overlapping shutdown windows). Hoisting to a single process-wide
# executor reuses the same worker pool for the whole run.
#
# Lazy: the singleton is only created on first ``get_freeze_row_executor()``
# call, so runs where billing_audit is disabled (TEST_MODE, missing
# Supabase creds, all flags off) pay zero executor cost.
#
# Cleanup: ``atexit`` ensures the executor shuts down cleanly when
# the interpreter exits, including the typical case where the main
# script returns normally without explicit teardown. ``_reset_executor_for_tests``
# is the test-only escape hatch — pytest must not leak a singleton
# executor across test cases when each case mocks Supabase
# differently.
_freeze_row_executor: ThreadPoolExecutor | None = None
_freeze_row_executor_lock = threading.Lock()


def get_freeze_row_executor(max_workers: int | None = None) -> ThreadPoolExecutor:
    """Return the process-wide freeze_row ThreadPoolExecutor.

    Creates the singleton on first call (lazy). Thread-safe: the
    creation guard is double-checked under ``_freeze_row_executor_lock``
    so two concurrent first-callers cannot create two executors.

    ``max_workers`` defaults to ``BILLING_AUDIT_FREEZE_WORKERS`` env
    var (or 8 if unset), capped at a hard upper bound of 32 to keep
    Supabase connection usage bounded even if an operator
    misconfigures the env. The chosen value is used only for the
    FIRST creation — subsequent calls return the existing executor
    regardless of the ``max_workers`` argument.
    """
    global _freeze_row_executor
    if _freeze_row_executor is not None:
        return _freeze_row_executor
    with _freeze_row_executor_lock:
        if _freeze_row_executor is not None:
            return _freeze_row_executor
        if max_workers is None:
            try:
                max_workers = int(
                    os.getenv("BILLING_AUDIT_FREEZE_WORKERS", "8") or 8
                )
            except (TypeError, ValueError):
                max_workers = 8
        max_workers = max(1, min(max_workers, 32))
        _freeze_row_executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="freeze_row",
        )
        atexit.register(_freeze_row_executor.shutdown, wait=True)
        return _freeze_row_executor


def _reset_executor_for_tests() -> None:
    """Tear down the singleton executor between tests.

    Tests that exercise the parallelization path or mock Supabase
    differently per case must not share thread state across cases.
    Idempotent — safe to call when no executor was ever created.
    """
    global _freeze_row_executor
    with _freeze_row_executor_lock:
        ex = _freeze_row_executor
        _freeze_row_executor = None
    if ex is not None:
        ex.shutdown(wait=False, cancel_futures=True)

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
    """Zero the module counters and tear down the singleton
    executor. Test-only helper.
    """
    with _counters_lock:
        for k in _counters:
            _counters[k] = 0
    _emitted_run_keys.clear()
    _reset_executor_for_tests()


def get_counters() -> dict[str, int]:
    """Return a snapshot of module counters for ``run_summary.json``.

    Keys: ``snapshots_written``, ``snapshots_already_frozen``,
    ``snapshots_errored``, ``fingerprint_changes_detected``.

    Takes ``_counters_lock`` so the snapshot is internally consistent
    even if another thread is mid-``_bump_counter`` — without it the
    sum of returned values could disagree with a per-key total under
    high write contention.
    """
    with _counters_lock:
        return dict(_counters)


def _flag_enabled_or_unknown(key: str) -> bool:
    """Fail-open flag probe: True if the flag reads True OR its
    state is indeterminate (read failure).

    A naive ``if not get_flag(key, default=False): return`` check
    treats a transient read blip (retries exhausted → default=False)
    identically to a definitive off-state. Because
    ``freeze_attribution`` is first-write-wins, letting such blips
    suppress writes means completed rows can lose their correct
    freeze window permanently if personnel change before the next
    pipeline run. Failing open here is safe because:

    1. The write RPC has its own ``with_retry`` + circuit breaker
       (op=``freeze_attribution`` / ``pipeline_run_*``), so an
       actual write-endpoint outage is bounded separately.
    2. A genuinely-off flag stays off-cached and this probe returns
       False for it — operators retain the ability to disable
       writes via the feature_flag table.
    """
    if get_flag(key, default=False):
        return True
    # get_flag returned False. If the read was definitively resolved
    # (value is cached), it's a real off-state. If not cached, the
    # read blipped — treat as unknown and fail open.
    return not is_flag_resolved(key)


def any_flag_enabled() -> bool:
    """Probe for whether any writer flag is currently on — fail-open.

    Returns True when:
    - Either ``write_attribution_snapshot`` or
      ``emit_assignment_fingerprint`` reads as True, OR
    - A flag read failed (``get_flag`` exhausted retries and
      returned its default) so the true state is indeterminate.

    The fail-open semantics are load-bearing: a transient
    feature_flag read blip would otherwise look identical to
    "flags are off" and cause the main pipeline to skip the whole
    per-group writer block for that group. Because
    ``freeze_attribution`` is first-write-wins, missing the
    current-run's freeze window for a completed row can
    permanently record the wrong personnel if assignments change
    before the next pipeline run. Failing open here just means
    "let the per-row ``freeze_row`` / ``emit_run_fingerprint``
    calls decide" — they gate internally on their own flag reads,
    so a genuinely-off flag still no-ops correctly even when this
    outer probe fails open.

    Returns False only when:
    - The Supabase client is unreachable (definitive), OR
    - Both flags are DEFINITIVELY known-off (both cached False
      via successful reads).

    Startup cost:
    - Client unreachable → ZERO flag reads.
    - ``write_attribution_snapshot=True`` → ONE read (short-circuit).
    - Otherwise → up to TWO reads on first call; dict lookups after.
    """
    if get_client() is None:
        return False
    return (
        _flag_enabled_or_unknown(_FLAG_WRITE)
        or _flag_enabled_or_unknown(_FLAG_FINGERPRINT)
    )


def fingerprint_flag_enabled() -> bool:
    """Narrower probe for just the fingerprint flag — fail-open.

    Lets callers skip ``compute_assignment_fingerprint()`` and the
    per-group completed-count aggregation when only the snapshot
    write flag is on — the fingerprint path would no-op inside
    ``emit_run_fingerprint`` otherwise, wasting per-group work.
    Fails open on indeterminate flag state (see
    ``_flag_enabled_or_unknown``) so a transient read blip cannot
    silently suppress fingerprint emission for this run.
    """
    if get_client() is None:
        return False
    return _flag_enabled_or_unknown(_FLAG_FINGERPRINT)


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
               run_id: str | None = None,
               variant: str | None = None) -> bool:
    """Upsert one row's personnel into ``attribution_snapshot``.

    First-write-wins via the ``billing_audit.freeze_attribution`` RPC.

    Returns:
        ``True`` if an RPC was attempted and completed without error
        (whether the row was newly written or was already frozen from
        a prior run).  ``False`` in all other cases — client
        unavailable, ``write_attribution_snapshot`` flag is
        definitively off, row is ineligible (missing/non-integer
        ``__row_id``, ``Units Completed?`` not checked, missing WR or
        week-ending), or the RPC call itself failed after retries.

    Silent no-op side-effects (returns ``False``) if the Supabase
    client is unavailable, the ``write_attribution_snapshot`` flag is
    off, or the row does not meet the freeze criteria.  Failures are
    counted and logged in aggregate only.

    Parameters
    ----------
    variant : str | None, default None
        Per D-18 / SUB-07 (Phase 1 Blocker 1 Path B): accepted for
        signature symmetry with ``emit_run_fingerprint`` and
        forward-compat instrumentation. Valid values are the 7
        variant strings ``primary | helper | vac_crew |
        aep_billable | reduced_sub | aep_billable_helper |
        reduced_sub_helper``.

        **This kwarg is NOT injected into the ``freeze_attribution``
        RPC params dict.** Reason: the RPC writes to
        ``attribution_snapshot`` (a different table than
        ``pipeline_run``), and the RPC's parameter contract is owned
        by the Supabase Dashboard (documented in
        ``billing_audit/schema.sql``). Changing it requires
        coordinated DDL + function updates. The variant is recorded
        on the ``pipeline_run`` row by ``emit_run_fingerprint``; the
        kwarg here is purely for signature symmetry + forward-compat.
    """
    # Path B contract: ``variant`` is accepted at the boundary but
    # never reaches the RPC params dict — see docstring. Touching it
    # to silence linters would risk a later regression that
    # accidentally injects it; an explicit acknowledgement here
    # documents the intentional drop.
    del variant
    client = get_client()
    if client is None:
        return False
    # Fail-open on indeterminate flag state — see
    # _flag_enabled_or_unknown for the rationale. A transient
    # feature_flag read blip must not be treated as definitive
    # off-state or we silently drop writes for this run and can
    # permanently miss the first-write-wins freeze window for
    # completed rows.
    if not _flag_enabled_or_unknown(_FLAG_WRITE):
        return False

    row_id = row.get("__row_id")
    if not isinstance(row_id, int):
        logging.warning(
            "⚠️ billing_audit.freeze_row: skipping row with missing or "
            "non-integer __row_id"
        )
        return False

    if not _is_checked(row.get("Units Completed?")):
        return False

    wr = _sanitized_wr(row)
    week_ending = _coerce_week_ending(row.get("__week_ending_date"))
    if not wr or week_ending is None:
        return False

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
        # ``__effective_user`` is the pipeline's RESOLVED primary
        # foreman: set at row-ingest time via the
        # ``Foreman Assigned?`` → ``Foreman`` → ``"Unknown Foreman"``
        # fallback chain, and is variant-agnostic (identical across
        # primary / helper / vac_crew copies of the row).
        #
        # Do NOT use ``__current_foreman`` here — that field is
        # variant-scoped in ``group_source_rows``: it holds the
        # helper foreman for helper variants and the VAC crew
        # member's name for vac_crew variants. Using it would
        # duplicate ``p_helper`` / ``p_vac_crew`` into
        # ``p_primary`` and lose the true primary assignment.
        # Raw ``Foreman`` is the final fallback for edge-case
        # rows missing ``__effective_user``.
        "p_primary": (
            row.get("__effective_user")
            or row.get("Foreman")
            or None
        ),
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
        _bump_counter("snapshots_errored")
        return False

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
        _bump_counter("snapshots_written")
    else:
        _bump_counter("snapshots_already_frozen")
    return True


def emit_run_fingerprint(wr: str, week_ending: datetime.date,
                         content_hash: str, assignment_fp: str,
                         completed_count: int, total_count: int,
                         release: str, run_id: str,
                         variant: str | None = None) -> None:
    """Upsert one row into ``billing_audit.pipeline_run``.

    Before writing, fetch the prior run's ``assignment_fp`` for
    ``(wr, week_ending)``. If it exists, differs from the new value,
    AND at least one row in this group has ``Units Completed?``
    checked, emit a Sentry warning tagged
    ``billing.mid_week_assignment_change=True``. Silent no-op if the
    ``emit_assignment_fingerprint`` flag is off.

    Parameters
    ----------
    variant : str | None, default None
        Per D-18 / SUB-07 (Phase 1 Blocker 1 Path B): the variant
        string for this (wr, week_ending, run_id) row, recorded on
        ``pipeline_run.variant``. Valid values: ``primary | helper |
        vac_crew | aep_billable | reduced_sub | aep_billable_helper
        | reduced_sub_helper``. ``None`` (or omitted) coerces to
        ``'primary'`` for back-compat with pre-Phase-1 call sites.

        First-variant-wins via the existing ``_emitted_run_keys``
        dedup: variant is NOT part of the PK
        (``wr, week_ending, run_id``) so subsequent calls with a
        different variant for the same (wr, week, run_id) are a
        no-op — the first variant emitted is the one recorded.
    """
    client = get_client()
    if client is None:
        return
    # Fail-open on indeterminate flag state (see _flag_enabled_or_unknown).
    if not _flag_enabled_or_unknown(_FLAG_FINGERPRINT):
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

    # Distinct ops for the prior-read vs the upsert so the circuit
    # breaker measures each endpoint independently. Sharing one op
    # would let a healthy SELECT continually reset the counter and
    # mask a sustained UPSERT outage from ever tripping the breaker.
    prior = with_retry(_fetch_prior, op="pipeline_run_select")
    prior_fp: str | None = None
    if prior is not None:
        rows = getattr(prior, "data", None) or []
        if rows and isinstance(rows[0], dict):
            prior_fp = rows[0].get("assignment_fp")

    # Coerce variant to its production sentinel: callers that don't
    # yet pass the kwarg (or explicitly pass None) record the
    # 'primary' variant, matching pre-Phase-1 default behavior.
    # Phase 1 Plan 03 emits the variant string at row-tagging time
    # via group_source_rows; the main loop forwards it here.
    effective_variant = variant if variant else 'primary'

    # ── Insert / upsert the new run row ──
    # Path B (Blocker 1): ``variant`` is recorded EXCLUSIVELY here,
    # in the pipeline_run upsert payload. The freeze_attribution
    # RPC params dict in freeze_row stays unchanged — variant lives
    # on pipeline_run only.
    payload = {
        "wr": wr_sanitized,
        "week_ending": week_ending.isoformat(),
        "run_id": run_id or "",
        "content_hash": content_hash,
        "assignment_fp": assignment_fp,
        "completed_count": int(completed_count),
        "total_count": int(total_count),
        "release": release or "",
        "variant": effective_variant,
    }

    def _upsert():
        return (
            client.schema("billing_audit")
            .table("pipeline_run")
            .upsert(payload, on_conflict="wr,week_ending,run_id")
            .execute()
        )

    upsert_result = with_retry(_upsert, op="pipeline_run_upsert")
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
        _bump_counter("fingerprint_changes_detected")
        _sentry_capture_warning(
            "billing.mid_week_assignment_change",
            True,
            extras={
                "billing.wr": wr_sanitized,
                "billing.week_ending": week_ending.isoformat(),
            },
        )


def lookup_attribution(
    wr: str,
    week_ending: datetime.date,
    smartsheet_row_id: int,
) -> dict | None:
    """Return the frozen helper attribution for ONE row, or None.

    Phase 1.1 Bug C reader (D-10..D-16 / SUB-11). Subcontractor
    workflow only — gated at the caller per D-15. First-write-wins
    semantics already match the per-row "first observed checked"
    definition (D-11) because the source-of-truth
    ``billing_audit.attribution_snapshot`` was populated row-level
    by every cron run since Phase 01's ``freeze_row`` shipped.

    Reuses the ``with_retry`` + ``_classify_postgrest_error`` retry
    contract from [2026-04-25 12:00] / [2026-04-25 14:00] unchanged:
    PGRST101 (no rows) → returns None; PGRST106 (schema not exposed)
    / PGRST301 / PGRST302 (auth) → trips the run-global kill, all
    subsequent calls short-circuit via ``get_client()``; HTTP 5xx →
    transient (retried by ``with_retry``); HTTP 4xx → permanent
    (single attempt, returns None). The ``op="lookup_attribution"``
    identifier is DISTINCT from ``freeze_attribution`` /
    ``pipeline_run_select`` / ``pipeline_run_upsert`` so an
    attribution-read outage cannot cascade into disabling those
    correctness-critical writers (op-isolation invariant per the
    [2026-04-25 14:00] ledger rule).

    Parameters
    ----------
    wr : str
        Work Request identifier. Sanitized at the producer site via
        ``_WR_SANITIZE`` (idempotent regex per [2026-04-23 18:25] —
        callers may pass either raw or pre-sanitized WR; both produce
        the same RPC payload). Numeric-suffix WRs like ``'91467680.0'``
        have the ``.0`` decimal suffix stripped via ``.split('.')[0]``
        before sanitization.
    week_ending : datetime.date
        The row's week-ending date. ISO-format string passed to the
        RPC (``2026-04-19``). The PRIMARY KEY shape on
        ``attribution_snapshot`` is (wr, week_ending, smartsheet_row_id)
        — all three are required for an unambiguous lookup.
    smartsheet_row_id : int
        The Smartsheet row ID; the per-row partition key. Non-int
        inputs return None without dispatch.

    Returns
    -------
    dict | None
        On success, a dict with keys ``{'helper', 'helper_dept',
        'source_run_id'}`` (data-team-owned RPC return shape; see
        ``billing_audit/schema.sql`` and RESEARCH.md §C Assumption A3).
        Returns None for ALL of:
        - ``get_client()`` returned None (TEST_MODE / missing creds /
          global-kill tripped),
        - Invalid input (empty WR, None week_ending, non-int row_id),
        - RPC failure (transient retries exhausted OR permanent
          error after one attempt),
        - RPC returned ``data=None``, an empty dict, an empty list,
          or a result with no ``helper`` field populated (the
          ``no_history`` case — there's no frozen attribution for
          this row yet; caller falls back to current helper per D-12).

        Returning None for both ``no_history`` and ``fetch_failure``
        matches the D-12 contract — the caller distinguishes the
        two reasons via per-WR local state (it has NOT issued a read
        in the no_history case yet, so first-call-returns-None on
        a brand-new WR is no_history; subsequent-call-returns-None
        after a prior PGRST exception was logged is fetch_failure).
    """
    client = get_client()
    if client is None:
        return None
    if not wr or week_ending is None or not isinstance(smartsheet_row_id, int):
        return None

    wr_sanitized = _WR_SANITIZE.sub("_", str(wr).split(".")[0])[:50]

    params = {
        "p_wr": wr_sanitized,
        "p_week_ending": week_ending.isoformat(),
        "p_smartsheet_row_id": smartsheet_row_id,
    }

    def _invoke():
        return (
            client.schema("billing_audit")
            .rpc("lookup_attribution", params)
            .execute()
        )

    # Distinct op so the breaker measures lookup independently of
    # writer paths. Sharing op="freeze_attribution" would let a
    # healthy attribution read continually reset the breaker
    # counter and mask a sustained writer outage — the inverse of
    # the [2026-04-25 12:00] pipeline_run select/upsert split.
    result = with_retry(_invoke, op="lookup_attribution")
    if result is None:
        return None

    data = getattr(result, "data", None)
    if isinstance(data, dict):
        return data if data.get("helper") else None
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and first.get("helper"):
            return first
    return None
