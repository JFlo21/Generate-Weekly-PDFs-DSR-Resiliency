"""Supabase attribution snapshot writer + reader.

Public surface:
- Writers: ``freeze_row`` (per-row attribution freeze) and
  ``emit_run_fingerprint`` (per-WR/week run fingerprint upsert).
- Reader: ``lookup_attribution(wr, week_ending, smartsheet_row_id)``
  (Phase 1.1 / Bug C / SUB-11) — returns the frozen attribution dict
  ``{helper, helper_dept, source_run_id}`` for ONE row, or ``None``
  if no snapshot exists yet. Calls the ``lookup_attribution``
  PostgREST RPC documented in ``billing_audit/schema.sql``.
- Resolution contract (Foundation A): ``resolve_claimer(variant,
  current_value, *, wr, week_ending, row_id, enabled) ->
  ResolveOutcome`` maps ONE row to use-frozen / use-current / HOLD via
  ``ROLE_BY_VARIANT``. Consumers (sub-projects B/C/D) group/name files
  by ``outcome.name`` or defer the row when ``outcome.action == 'hold'``.
- HOLD accounting (Foundation A): ``record_attribution_hold`` tallies a
  deferred row (dormant — no production caller yet) and
  ``summarize_attribution_holds`` emits one PII-safe aggregate WARNING
  at end-of-run so a Supabase outage that suppresses files is visible.

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
vac_crew names). Only aggregate summaries — INFO for counters, and
WARNING for the attribution-HOLD summary (``summarize_attribution_holds``,
which emits sanitized WR identifiers + counts only). This mirrors the
pipeline's ``_PII_LOG_MARKERS`` defense — billing-row identifiers are
PII and must not leak into Sentry Logs.

**Reader PII-out exceptions:** the read surfaces return per-row PII as
*values* (not log lines) — the one place PII leaves the package as a
value. These are: ``lookup_attribution`` (the ``helper`` string in its
return dict), ``_lookup_attribution_all`` (the full role row —
``primary_foreman`` / ``helper`` / ``vac_crew``), and ``resolve_claimer``
(``ResolveOutcome.name``, a frozen or current foreman name). Callers
MUST treat every such returned name as PII (group-key embedding,
filename embedding) and follow the same redaction rules they use for
live Smartsheet ``Foreman Helping?`` values.
"""

from __future__ import annotations

import atexit
import datetime
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, NamedTuple

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
    # Foundation A: rows held this run pending attribution (dormant
    # until a consumer acts on resolve_claimer's HOLD outcome).
    # Pre-seeded to 0 so get_counters() has a stable schema even on
    # runs with zero holds.
    "attribution_rows_held": 0,
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

# Attribution HOLD accumulator (Foundation A, dormant until a consumer
# calls resolve_claimer and acts on action == 'hold'). Tracks rows held
# this run pending attribution, keyed by (sanitized_wr, week_iso,
# variant). PII discipline: only counts + sanitized WR identifiers ever
# leave this structure — never foreman/helper/dept/job.
_attribution_holds: dict[tuple[str, str, str], int] = {}
_attribution_holds_lock = threading.Lock()


def _reset_counters_for_tests() -> None:
    """Zero the module counters and tear down the singleton
    executor. Test-only helper.
    """
    with _counters_lock:
        for k in _counters:
            _counters[k] = 0
    _emitted_run_keys.clear()
    _reset_executor_for_tests()
    with _attribution_holds_lock:
        _attribution_holds.clear()


def get_counters() -> dict[str, int]:
    """Return a snapshot of module counters for ``run_summary.json``.

    Keys: ``snapshots_written``, ``snapshots_already_frozen``,
    ``snapshots_errored``, ``fingerprint_changes_detected``,
    ``attribution_rows_held``.

    Takes ``_counters_lock`` so the snapshot is internally consistent
    even if another thread is mid-``_bump_counter`` — without it the
    sum of returned values could disagree with a per-key total under
    high write contention.
    """
    with _counters_lock:
        return dict(_counters)


def record_attribution_hold(
    wr: str,
    week_ending: datetime.date | None,
    variant: str,
) -> None:
    """Record one row held this run (resolve_claimer → action 'hold').

    Atomically increments the per-(wr, week, variant) accumulator and
    the aggregate ``attribution_rows_held`` counter. Thread-safe via
    ``_attribution_holds_lock``.

    PII discipline: only the sanitized WR identifier is stored —
    never foreman/helper/dept/job names.
    """
    wr_sanitized = _WR_SANITIZE.sub("_", str(wr).split(".")[0])[:50]
    week_iso = week_ending.isoformat() if week_ending else ""
    key = (wr_sanitized, week_iso, variant)
    with _attribution_holds_lock:
        _attribution_holds[key] = _attribution_holds.get(key, 0) + 1
    _bump_counter("attribution_rows_held")


def summarize_attribution_holds() -> str | None:
    """Emit one aggregate WARNING if any rows were held; return the
    message (for testing) or None if nothing was held.

    Each call emits one WARNING — the caller (sub-project B's
    end-of-run hook) is responsible for invoking this exactly once
    per run. PII-safe: counts + sanitized WR list only. The pipeline's
    logging→Sentry bridge surfaces this WARNING; a consumer wiring
    this into the run may escalate to an explicit Sentry capture.

    Returns ``None`` when no holds have been recorded this run.
    """
    with _attribution_holds_lock:
        if not _attribution_holds:
            return None
        total_rows = sum(_attribution_holds.values())
        wrs = sorted({k[0] for k in _attribution_holds})
    wr_sample = wrs[:20]
    suffix = "" if len(wrs) <= 20 else f" (+{len(wrs) - 20} more)"
    msg = (
        f"⚠️ Attribution HOLD: {total_rows} row(s) across "
        f"{len(wrs)} WR(s) held this run pending attribution "
        f"(reason=fetch_failure). Affected WRs (first 20): "
        f"{wr_sample}{suffix}"
    )
    logging.warning(msg)
    return msg


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


def _lookup_attribution_all(
    wr: str,
    week_ending: datetime.date | None,
    smartsheet_row_id: int,
) -> tuple[dict | None, str]:
    """Fetch the full frozen-attribution row for ONE row, with status.

    Foundation A (2026-05-20). Returns a ``(row, status)`` tuple:

    - ``'success'``      : RPC succeeded and a row was found (row is
                           the dict of all roles).
    - ``'no_row'``       : RPC succeeded but no row exists, OR the
                           input is invalid (row is None).
    - ``'fetch_failure'``: the call failed — retries exhausted /
                           permanent error / run-global kill tripped
                           (row is None). Consumers HOLD on this.
    - ``'unavailable'``  : no client (TEST_MODE / missing creds) and
                           NOT an outage (row is None). Consumers use
                           the current value.

    The row dict, when present, carries the RPC columns
    ``primary_foreman, helper, helper_dept, vac_crew, source_run_id``
    (already #NO MATCH/blank-normalized to NULL per role by the RPC).
    Shares the ``op="lookup_attribution"`` retry/circuit-breaker with
    the public ``lookup_attribution`` wrapper.

    PII-out: the returned row dict carries per-row PII
    (``primary_foreman`` / ``helper`` / ``vac_crew`` names); callers
    MUST treat every returned field as PII and follow the same
    redaction rules they use for live Smartsheet values.
    """
    from billing_audit import client as _client_mod

    client = get_client()
    if client is None:
        if _client_mod._global_disable_reason is not None:
            return None, "fetch_failure"
        return None, "unavailable"
    if (
        not wr
        or week_ending is None
        or not isinstance(smartsheet_row_id, int)
    ):
        return None, "no_row"

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

    try:
        result = with_retry(_invoke, op="lookup_attribution")
        if result is None:
            return None, "fetch_failure"
        data = getattr(result, "data", None)
        if isinstance(data, dict) and data:
            return data, "success"
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                return first, "success"
        return None, "no_row"
    except Exception:
        # Spec §8: this reader MUST NEVER raise on a Supabase failure.
        # ``with_retry`` already classifies the known APIError/transient
        # surface; this belt-and-suspenders guard catches an unexpected
        # failure in result-object handling and maps it to
        # ``fetch_failure`` so the consumer HOLDs (correctness over
        # availability) rather than mis-attributing. PII-safe: the log
        # carries no row content.
        logging.warning(
            "⚠️ Attribution lookup hit an unexpected error; "
            "treating as fetch_failure (HOLD)."
        )
        return None, "fetch_failure"


def prefetch_attribution(
    pairs: "set[tuple[str, datetime.date]]",
) -> "tuple[dict[tuple[str, datetime.date, int], dict], str]":
    """Bulk-load frozen attribution for the run's (wr, week_ending) set.

    Phase 2 (2026-05-26). Returns a ``((wr, week_ending, smartsheet_row_id)
    -> roles-dict, status)`` tuple.
    status in {'success', 'no_row', 'fetch_failure', 'rpc_missing',
    'unavailable'}.

    rpc_missing = the lookup_attribution_bulk RPC is not deployed (PGRST202);
    the caller may degrade to the per-row lookup_attribution path
    (correctness-preserving — the deployed per-row RPC returns the SAME frozen
    data, just slower). fetch_failure = a transient outage; the caller
    preserves the D-04 HOLD contract for B/C.

    Fail-safe: NEVER raises; a Supabase failure returns ({}, 'fetch_failure')
    so resolve_claimer applies each variant's documented fallback.

    TOTAL-FAILURE CONTRACT (D-04): the function signals total failure ONLY via
    the RETURN status 'fetch_failure' (with an empty map). It does NOT re-issue
    any RPC. The CALLER inspects this status and applies each variant's policy
    DIRECTLY (B/C construct a HOLD ResolveOutcome; D uses-current) — the caller
    must NEVER fall back to the per-row resolve_claimer RPC path on failure, or
    an outage becomes a per-row retry storm.

    Reuses with_retry(op="lookup_attribution_bulk") — DISTINCT op id so a
    bulk-read outage cannot disable freeze_attribution / pipeline_run_* /
    lookup_attribution / lookup_group_hash (op-isolation, D-13).
    """
    if not pairs:
        return {}, "no_row"

    from billing_audit import client as _client_mod

    client = get_client()
    if client is None:
        if _client_mod._global_disable_reason is not None:
            return {}, "fetch_failure"
        return {}, "unavailable"

    # Chunk pairs (≤ 500/payload — ~45 bytes/pair; 500 is two orders of
    # magnitude under the ~1 MB PostgREST body limit; T-02-05 accept).
    _CHUNK_SIZE = 500
    pair_list = list(pairs)
    chunks = [pair_list[i:i + _CHUNK_SIZE]
              for i in range(0, len(pair_list), _CHUNK_SIZE)]

    result_map: "dict[tuple[str, datetime.date, int], dict]" = {}
    overall_status = "no_row"

    for chunk in chunks:
        payload = [
            {"wr": _WR_SANITIZE.sub("_", str(wr).split(".")[0])[:50],
             "week_ending": we.isoformat()}
            for wr, we in chunk
        ]

        def _invoke(_p=payload):
            return (
                client.schema("billing_audit")
                .rpc("lookup_attribution_bulk", {"p_wr_weeks": _p})
                .execute()
            )

        try:
            result = with_retry(_invoke, op="lookup_attribution_bulk")
            if result is None:
                # with_retry swallows the APIError and returns only None,
                # discarding the reason_code. CR-01 (Plan 05): distinguish a
                # MISSING RPC (PGRST202 "function not found" — permanent, the
                # caller can degrade to the deployed per-row path) from a
                # transient outage (the caller preserves the D-04 HOLD).
                # Bounded probe: ONE extra call only on the already-failed
                # path, so it cannot reintroduce the per-row storm. Fail-safe
                # default: anything not provably PGRST202 -> fetch_failure.
                try:
                    from postgrest import APIError as _APIError
                except Exception:  # postgrest absent / import shape changed
                    _APIError = ()
                try:
                    _invoke()
                    # Re-invoke succeeded where with_retry didn't — treat the
                    # original failure as transient (do NOT claim rpc_missing).
                    return {}, "fetch_failure"
                except Exception as _probe_exc:
                    if isinstance(_probe_exc, _APIError) and (
                        _client_mod._classify_postgrest_error(_probe_exc)[2]
                        == "PGRST202"
                    ):
                        return {}, "rpc_missing"
                    return {}, "fetch_failure"
            data = getattr(result, "data", None) or []
            if isinstance(data, dict):
                data = [data] if data else []
            for row in data:
                if not isinstance(row, dict):
                    continue
                try:
                    key = (
                        str(row["wr"]),
                        datetime.date.fromisoformat(str(row["week_ending"])),
                        int(row["smartsheet_row_id"]),
                    )
                except (KeyError, ValueError, TypeError):
                    continue
                result_map[key] = row
            if data:
                overall_status = "success"
        except Exception:
            logging.warning(
                "⚠️ Attribution bulk prefetch hit an unexpected error; "
                "treating as fetch_failure (HOLD for B/C, use-current for D)."
            )
            return {}, "fetch_failure"

    return result_map, overall_status


class ResolveOutcome(NamedTuple):
    """Result of resolving the claiming foreman for ONE row.

    action : 'use' to group/name by ``name``; 'hold' to defer the row
             this run (attribution unavailable — correctness over
             availability).
    name   : the claimer name when action == 'use'; None on 'hold'.
    source : 'frozen' | 'current' | None — provenance for audit/log.
    reason : 'success' | 'no_history' | 'disabled' | 'fetch_failure'.
    """

    action: str
    name: str | None
    source: str | None
    reason: str


# Variant → which frozen role column governs that file's claimer.
ROLE_BY_VARIANT: dict[str, str] = {
    "primary": "primary_foreman",
    "reduced_sub": "primary_foreman",
    "aep_billable": "primary_foreman",
    "helper": "helper",
    "reduced_sub_helper": "helper",
    "aep_billable_helper": "helper",
    "vac_crew": "vac_crew",
}


def resolve_claimer(
    variant: str,
    current_value: str | None,
    *,
    wr: str,
    week_ending: datetime.date | None,
    row_id: int,
    enabled: bool,
    prefetched_map: "dict | None" = None,
) -> ResolveOutcome:
    """Resolve the claiming foreman for ONE row (Foundation A contract).

    See docs/superpowers/specs/2026-05-20-claim-attribution-
    foundation-design.md §5 for the full decision table. ``enabled``
    is the caller's kill switch — A does not own a flag.
    ``current_value`` is the live Smartsheet value for this variant's
    role (the fallback).

    HOLD is returned ONLY on a genuine outage (``fetch_failure``); a
    brand-new claim (``no_history``) uses the current value because
    this run is what freezes it.

    D-03: when ``prefetched_map`` is provided (not None), the (wr,
    week_ending, row_id) key is looked up O(1) from the preloaded map
    instead of issuing a per-row RPC. The (row, status) shape is
    identical to ``_lookup_attribution_all`` so the decision table
    below is unchanged.

    D-04 TOTAL-FAILURE CONTRACT: On a total bulk-load failure the
    CALLER does NOT pass prefetched_map and does NOT re-invoke this
    resolver — it constructs the per-variant fetch_failure outcome
    DIRECTLY (B/C: ResolveOutcome('hold', None, None, 'fetch_failure');
    D: use-current) so an outage triggers ZERO additional Supabase calls.
    """
    if not enabled:
        return ResolveOutcome("use", current_value, "current", "disabled")

    # D-03: O(1) map read when a preloaded map is provided. Same (row, status)
    # shape as _lookup_attribution_all so the decision table below is unchanged.
    if prefetched_map is not None:
        # WR-01: prefetch_attribution builds the map key from the SANITIZED
        # WR (the RPC echoes back s.wr, which freeze_row wrote sanitized), so
        # the lookup key MUST be sanitized identically or a valid frozen
        # claimer is silently dropped (split-brain). Numeric WR#s are a no-op
        # under _WR_SANITIZE so production data is unaffected. Per CLAUDE.md
        # [2026-04-23 18:25]: every downstream consumer of the identifier MUST
        # consume the sanitized value.
        _wr_key = _WR_SANITIZE.sub("_", str(wr).split(".")[0])[:50]
        _key = (_wr_key, week_ending, row_id) if (week_ending and row_id) else None
        if _key is not None and _key in prefetched_map:
            row, status = prefetched_map[_key], "success"
        else:
            row, status = None, "no_row"
    else:
        row, status = _lookup_attribution_all(wr, week_ending, row_id)
    if status == "unavailable":
        return ResolveOutcome("use", current_value, "current", "disabled")
    if status == "fetch_failure":
        return ResolveOutcome("hold", None, None, "fetch_failure")
    if status == "no_row" or row is None:
        return ResolveOutcome(
            "use", current_value, "current", "no_history")

    role = ROLE_BY_VARIANT.get(variant, "primary_foreman")
    frozen = row.get(role)
    # Strip first, then test truthiness, so a whitespace-only value is
    # treated as no-claimer (no_history) rather than an empty name. The
    # RPC already normalizes blank/#-token roles to NULL; this is a
    # defense-in-depth guard so the returned name is never empty.
    frozen_str = str(frozen).strip() if frozen is not None else ""
    if frozen_str:
        return ResolveOutcome("use", frozen_str, "frozen", "success")
    return ResolveOutcome("use", current_value, "current", "no_history")


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
        On success, the RPC row dict (keys ``primary_foreman, helper,
        helper_dept, vac_crew, source_run_id``) — guaranteed to have a
        non-empty ``helper`` field because this wrapper is helper-gated.
        See ``billing_audit/schema.sql`` and RESEARCH.md §C Assumption A3.
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

    Thin helper-gated wrapper over ``_lookup_attribution_all`` since
    Foundation A (2026-05-20); external behavior is unchanged.
    """
    row, status = _lookup_attribution_all(wr, week_ending, smartsheet_row_id)
    if status != "success" or row is None:
        return None
    # Preserve the historical helper-gated contract: callers of this
    # public function get the row only when a helper is present.
    return row if row.get("helper") else None


def lookup_group_hash(wr, week_ending, variant, identifier):
    """Read the durable per-group content hash from Supabase.

    Sub-project E (2026-05-25). Returns a ``(content_hash | None,
    status)`` tuple where status is one of:

    - ``'success'``      : a row exists; content_hash is its stored
                           hash (may be None only if the column were
                           ever NULL, which the NOT NULL schema
                           prevents).
    - ``'no_row'``       : the query succeeded with zero rows — this
                           group has never been stored. Consumers
                           regenerate (the safe default).
    - ``'fetch_failure'``: the call failed — retries exhausted /
                           permanent error / run-global kill tripped.
                           Consumers fall back to the json cache.
    - ``'unavailable'``  : no client (TEST_MODE / missing creds) and
                           NOT an outage. Consumers fall back to json.

    Keyed on the same 4-tuple as the engine's ``history_key``
    (``f"{wr}|{week}|{variant}|{identifier}"``). Shares the
    ``with_retry`` / per-op circuit breaker / run-global kill switch
    used by the rest of this module via the ``op="lookup_group_hash"``
    identifier (DISTINCT from the attribution / pipeline_run ops so a
    hash-store outage cannot cascade into disabling those writers).
    NEVER raises — a Supabase failure degrades to ``fetch_failure``
    so the caller regenerates rather than mis-skips.
    """
    from billing_audit import client as _client_mod

    client = get_client()
    if client is None:
        if _client_mod._global_disable_reason is not None:
            return None, "fetch_failure"
        return None, "unavailable"

    def _op():
        return (
            client.schema("billing_audit")
            .table("group_content_hash")
            .select("content_hash")
            .eq("wr", str(wr))
            .eq("week_ending", str(week_ending))
            .eq("variant", str(variant))
            .eq("identifier", identifier or "")
            .limit(1)
            .execute()
        )

    try:
        resp = with_retry(_op, op="lookup_group_hash")
        if resp is None:
            return None, "fetch_failure"
        data = getattr(resp, "data", None)
        if isinstance(data, dict):
            data = [data] if data else []
        rows = data or []
        if not rows:
            return None, "no_row"
        first = rows[0]
        if isinstance(first, dict):
            return first.get("content_hash"), "success"
        return None, "no_row"
    except Exception:
        # Belt-and-suspenders: this reader MUST NEVER raise. Map any
        # unexpected failure to fetch_failure so the skip gate falls
        # back to the json cache / regenerates. ``with_retry`` already
        # absorbs the classified PostgREST surface (returning None), so
        # this handler only fires on an unexpected local error (e.g.
        # result-object handling) whose traceback carries no row content
        # — logging.exception aids diagnosis while staying PII-safe.
        logging.exception(
            "⚠️ Group-hash lookup hit an unexpected error; "
            "treating as fetch_failure (fall back to json cache)."
        )
        return None, "fetch_failure"


def upsert_group_hash(wr, week_ending, variant, identifier, content_hash):
    """Best-effort durable write of a per-group content hash.

    Sub-project E (2026-05-25). Fail-safe: catches its own errors and
    NEVER raises (mirrors ``freeze_row`` / ``emit_run_fingerprint``),
    so a Supabase problem can never break the billing pipeline. Keyed
    on the 4-tuple PK ``(wr, week_ending, variant, identifier)`` — the
    same identity as the engine's ``history_key``. ``identifier`` is
    normalized to ``''`` for bare-primary / legacy-shape groups so the
    NOT NULL DEFAULT '' column stays consistent with the reader.
    """
    client = get_client()
    if client is None:
        return
    payload = {
        "wr": str(wr),
        "week_ending": str(week_ending),
        "variant": str(variant),
        "identifier": identifier or "",
        "content_hash": content_hash,
    }

    def _op():
        return (
            client.schema("billing_audit")
            .table("group_content_hash")
            .upsert(payload, on_conflict="wr,week_ending,variant,identifier")
            .execute()
        )

    try:
        with_retry(_op, op="upsert_group_hash")
    except Exception:
        # Fail-safe (Spec §8): a durable-write failure is non-fatal.
        # The json cache + filename-hash backstop still protect change
        # detection. ``with_retry`` absorbs the classified PostgREST
        # surface, so this only fires on an unexpected local error;
        # logging.exception surfaces WHY the durable store isn't being
        # populated (PII-safe — no row content in the traceback).
        logging.exception(
            "⚠️ Group-hash upsert failed (non-fatal); "
            "durable store not updated this run."
        )
