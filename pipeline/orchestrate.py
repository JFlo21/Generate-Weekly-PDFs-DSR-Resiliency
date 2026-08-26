#!/usr/bin/env python3
"""pipeline.orchestrate — top-level pipeline orchestration (Phase 09 W6).

``main()`` is the production entry point, relocated byte-for-byte from
``generate_weekly_pdfs.py`` with NO internal decomposition (D-05).  The two
testmode helpers ``_build_synthetic_rows`` and ``_run_synthetic_test_mode``
fold in here (RESEARCH Assumption A1 — both are called only from ``main()``).

This is the highest fan-in consumer; it imports from every other pipeline
module.  The facade (``generate_weekly_pdfs.py``) re-exports ``main`` and the
``if __name__ == "__main__"`` entry delegates here.

Facade-read prelude (D-06 + W2-W5 pattern): ``main()`` binds the test-rebound /
facade-resident names it reads from the facade at call time (see the prelude at
the top of ``main``), so a test rebind on the facade is honored and the
``_billing_audit_writer`` injection restores the authoritative Supabase hash
lookup.
"""
from __future__ import annotations

import os
import datetime
from datetime import timedelta
import threading
import json
import re
import signal
import collections
import traceback
import logging
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
    TimeoutError as FuturesTimeoutError,
)
import concurrent.futures.thread as _cf_thread
from typing import Any

from dateutil import parser
import smartsheet
import sentry_sdk
from sentry_sdk.crons import capture_checkin
from sentry_sdk.crons.consts import MonitorStatus

# Phase 09 W6: import ALL pipeline modules (aliased) per the orchestrate
# pattern. main() references its siblings by the bare re-exported names
# below (byte-for-byte body); the aliases satisfy the package convention
# and are available for module-qualified reads.
from pipeline import config as _cfg
from pipeline import observability as _obs
from pipeline import utils as _utils
from pipeline import pricing as _pricing
from pipeline import change_detection as _cd
from pipeline import discovery as _discovery
from pipeline import fetch as _fetch
from pipeline import grouping as _grouping
from pipeline import excel as _excel
from pipeline import cleanup as _cleanup
from pipeline import upload as _upload
from pipeline import attribution as _attr
from pipeline.retry import smartsheet_call_with_retry
# Phase 10 (MEM-01/MEM-03): independent run-memory shadow-write package --
# NOT a ``pipeline`` submodule (deliberately outside the D-04 import-cycle
# rule's scope; see pipeline_memory/__init__.py). Off by default via
# RUN_MEMORY_WRITE_ENABLED; every call site below is fail-open.
from pipeline_memory import writer as _mem_writer

# Named re-export imports (byte-exact from the facade) so every bare sibling
# reference inside main()/testmode resolves identically (W1-W5 pattern). The
# 4 live-proxy globals (SUBCONTRACTOR_SHEET_IDS / _FOLDER_DISCOVERED_* /
# _RATES_FINGERPRINT) are intentionally absent — main() reads none of them.

from pipeline.config import (  # noqa: E402
    API_TOKEN,
    ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC,
    ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN,
    ATTACHMENT_PREFETCH_MAX_MINUTES,
    ATTACHMENT_REQUIRED_FOR_SKIP,
    ATTRIBUTION_BULK_PREFETCH_FALLBACK,
    AUDIT_SHEET_ID,
    DEBUG_ESSENTIAL_ROWS,
    DEBUG_SAMPLE_ROWS,
    DISABLE_AUDIT_FOR_TESTING,
    DISCOVERY_CACHE_PATH,
    DISCOVERY_CACHE_TTL_MIN,
    DISCOVERY_CACHE_VERSION,
    EXCLUDE_WRS,
    EXTENDED_CHANGE_DETECTION,
    FILTER_DIAGNOSTICS,
    FORCE_GENERATION,
    FORCE_REDISCOVERY,
    FOREMAN_DIAGNOSTICS,
    GITHUB_ACTIONS_MODE,
    HASH_HISTORY_PATH,
    HISTORY_SKIP_ENABLED,
    KEEP_HISTORICAL_WEEKS,
    LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED,
    LOGO_PATH,
    LOG_UNKNOWN_COLUMNS,
    MAX_GROUPS,
    ORIGINAL_CONTRACT_FOLDER_IDS,
    OUTPUT_FOLDER,
    PARALLEL_WORKERS,
    PARALLEL_WORKERS_DISCOVERY,
    PER_CELL_DEBUG_ENABLED,
    PRIMARY_CLAIM_ATTRIBUTION_ENABLED,
    QUIET_LOGGING,
    RATE_CUTOFF_DATE,
    REGEN_WEEKS,
    REMEDIATE_CLAIMERS,
    REMEDIATION_DRY_RUN,
    REMEDIATION_WINDOW_WEEKS,
    RESET_HASH_HISTORY,
    RESET_WR_LIST,
    RES_GROUPING_MODE,
    RUN_MEMORY_WRITE_ENABLED,
    RUN_MEMORY_WRITE_GENERATION_HEADROOM_MIN,
    RUN_MEMORY_WRITE_MAX_MINUTES,
    RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC,
    SKIP_CELL_HISTORY,
    SKIP_UPLOAD,
    SUBCONTRACTOR_FOLDER_IDS,
    SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED,
    SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED,
    SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED,
    SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED,
    SUBCONTRACTOR_RATE_VARIANTS_ENABLED,
    SUPABASE_HASH_STORE_AUTHORITATIVE,
    SUPABASE_HASH_STORE_WRITE_ENABLED,
    TARGET_SHEET_ID,
    TEST_MODE,
    TIME_BUDGET_MINUTES,
    UNMAPPED_COLUMN_SAMPLE_LIMIT,
    USE_DISCOVERY_CACHE,
    VAC_CREW_CLAIM_ATTRIBUTION_ENABLED,
    VAC_CREW_FOLDER_IDS,
    VAC_CREW_LEGACY_CLEANUP_ENABLED,
    VAC_CREW_SHEET_IDS,
    WR_FILTER,
    _DaemonThreadPoolExecutor,
    _RE_EXTRACT_NUMBERS,
    _RE_ISO_DATE_PREFIX,
    _RE_SANITIZE_HELPER_NAME,
    _RE_SANITIZE_IDENTIFIER,
    _audit_sheet_id_int,
    _coerce_sheet_id,
    _cutoff_str,
    _default_hist_path,
    _env_hist_path,
    _parse_sheet_ids,
    _remediation_window_env,
    _sanitize_csv_path,
    _target_sheet_id_env,
)
from pipeline.pricing import (  # noqa: E402
    ARROWHEAD_DISCOUNT,
    NEW_RATES_CSV,
    OLD_RATES_CSV,
    RATE_RECALC_SKIP_ORIGINAL_CONTRACT,
    RATE_RECALC_WEEKLY_FALLBACK,
    SUBCONTRACTOR_RATES_CSV,
    _SUBCONTRACTOR_RATES,
    _SUBCONTRACTOR_RATES_FINGERPRINT,
    _SUBCONTRACTOR_RATES_REQUIRED_HEADERS,
    _compute_rates_fingerprint,
    _compute_subcontractor_rates_fingerprint,
    _resolve_cu_code,
    _resolve_row_price,
    _strip_csv_fieldnames,
    _subcontractor_rescue_price,
    build_cu_to_group_mapping,
    load_contract_rates,
    load_new_contract_rates,
    load_rate_versions,
    load_subcontractor_rates,
    parse_price,
    recalculate_row_price,
    revert_subcontractor_price,
)
from pipeline.observability import (  # noqa: E402,F401
    SENTRY_DSN,
    SentryLogLevel,
    _ALWAYS_GARBAGE_PATTERNS,
    _CRON_MONITOR_SCHEDULE,
    _GARBAGE_PATTERNS,
    _PII_LOG_MARKERS,
    _RE_REDACT_CUSTOMER,
    _RE_REDACT_EMAIL,
    _RE_REDACT_MONEY,
    _RE_REDACT_WR,
    _build_cron_monitor_config,
    _build_run_context_snapshot,
    _build_run_kpis,
    _parse_sentry_enable_logs,
    _redact_exception_message,
    _sentry_cron_checkin_start,
    _sentry_log_event,
    _set_sentry_session_tags,
    logger,
    sentry_add_breadcrumb,
    sentry_before_send_log,
    sentry_capture_message_with_context,
    sentry_capture_with_context,
)
from pipeline.utils import (  # noqa: E402
    is_checked,
    excel_serial_to_date,
    _resolve_rate_recalc_cutoff_date,
    _weekly_would_trigger_fallback,
)
from pipeline.change_detection import (  # noqa: E402
    HASH_HISTORY_MAX_ENTRIES,
    _compute_aggregated_content_hash,
    _resolve_unchanged_for_skip,
    build_group_identity,
    calculate_data_hash,
    extract_data_hash_from_filename,
    list_generated_excel_files,
    load_hash_history,
    save_hash_history,
)
from pipeline.discovery import (  # noqa: E402
    _normalize_column_title_for_vac_crew,
    discover_folder_sheets,
    discover_source_sheets,
)
from pipeline.fetch import get_all_source_rows  # noqa: E402
from pipeline.grouping import (  # noqa: E402
    group_source_rows,
    validate_group_totals,
)
from pipeline.excel import (  # noqa: E402
    _subcontractor_primary_variant_suffix,
    _vac_crew_variant_suffix,
    generate_excel,
    safe_merge_cells,
)
from pipeline.cleanup import (  # noqa: E402
    _has_existing_week_attachment,
    cleanup_stale_excels,
    cleanup_untracked_sheet_attachments,
    delete_old_excel_attachments,
    purge_existing_hashed_outputs,
)
from pipeline.upload import (  # noqa: E402
    _build_upload_tasks_for_group,
    create_target_sheet_map,
    create_target_sheet_map_for,
)
from pipeline.attribution import (  # noqa: E402
    BILLING_AUDIT_ROW_CACHE_MAX_ENTRIES,
    BILLING_AUDIT_ROW_CACHE_PATH,
    PHASE_1_1_HASH_PRUNE_VERSION,
    SUBPROJECT_B_HASH_PRUNE_VERSION,
    SUBPROJECT_D_HASH_PRUNE_VERSION,
    VAC_CREW_HASH_PRUNE_VERSION,
    _SUBCONTRACTOR_SCOPE_VARIANTS,
    _build_primary_wr_scope,
    _build_subcontractor_wr_scope,
    _build_vac_crew_wr_scope,
    _run_phase_1_1_hash_prune,
    _run_subproject_b_hash_prune,
    _run_subproject_d_hash_prune,
    _run_vac_crew_hash_prune,
    load_billing_audit_row_cache,
    run_claimer_remediation,
    save_billing_audit_row_cache,
)
from pipeline.snapshot_drift import apply_snapshot_drift_holds  # noqa: E402


def _build_synthetic_rows():
    """Build an in-memory synthetic dataset for TEST_MODE runs without an API token."""
    base_week_end = datetime.datetime.now()
    # Snap week ending to coming Sunday for consistency
    base_week_end = base_week_end + datetime.timedelta(days=(6 - base_week_end.weekday()))
    week_end_iso = base_week_end.strftime('%Y-%m-%d')
    rows = []
    wrs = ['90093002', '89708709']
    foremen = ['Alice Foreman', 'Bob Foreman']
    daily_prices = [1200.50, 800.00, 950.75, 0, 1300.25, 600.00, 1450.00]
    for idx, wr in enumerate(wrs):
        foreman = foremen[idx]
        for offset, price in enumerate(daily_prices):
            snap_date = (base_week_end - datetime.timedelta(days=(6 - offset)))
            row = {
                'Work Request #': wr,
                'Weekly Reference Logged Date': week_end_iso,  # same week ending for all
                'Snapshot Date': snap_date.strftime('%Y-%m-%d'),
                'Units Total Price': f"${price:,.2f}",
                'Quantity': str(1 + (offset % 3)),
                'Units Completed?': True,
                'Foreman': foreman,
                'CU': f"CU{100+offset}",
                'CU Description': f"Synthetic Work Item {offset+1}",
                'Unit of Measure': 'EA',
                'Pole #': f"P-{offset+1:03d}",
                'Work Type': 'Maintenance',
                'Scope #': f"SCP-{wr[-3:]}"
            }
            # Include a zero price row intentionally (price==0) to confirm exclusion
            rows.append(row)
    return rows


def _run_synthetic_test_mode(session_start):
    """Execute the synthetic TEST_MODE path. Returns number of files generated."""
    logging.info("🧪 TEST_MODE without SMARTSHEET_API_TOKEN: using synthetic in-memory dataset")
    synthetic_rows = _build_synthetic_rows()
    logging.info(f"Synthetic rows prepared: {len(synthetic_rows)} raw rows")
    # Apply normal grouping logic (filtering happens inside grouping)
    groups = group_source_rows(synthetic_rows)
    logging.info(f"Synthetic grouping produced {len(groups)} group(s)")
    snapshot_date = datetime.datetime.now()
    generated_files_count = 0
    for group_key, group_rows in groups.items():
        try:
            data_hash = calculate_data_hash(group_rows)
            # Phase 01 Plan 03 Task 2 / Blocker 4: unpack
            # the new 5-tuple shape. Synthetic path doesn't
            # consume ``customer_name`` / ``missing_cus``
            # (no per-sheet WARNING context here), but the
            # unpack MUST match so a contract drift is
            # surfaced loudly rather than silently dropped.
            (
                _excel_path,
                filename,
                _wr_numbers,
                _customer_name,
                _missing_cus,
            ) = generate_excel(
                group_key, group_rows, snapshot_date,
                data_hash=data_hash,
            )
            generated_files_count += 1
            logging.info(f"🧪 Synthetic Excel generated: {filename} ({len(group_rows)} rows)")
        except Exception as e:
            logging.error(f"Synthetic group failure {group_key}: {e}")
    session_duration = datetime.datetime.now() - session_start
    logging.info(f"🧪 Synthetic session complete: {generated_files_count} file(s) in {session_duration}")
    # Emit run_summary.json on the synthetic path too (Codex P2 / 09-UAT
    # note). Gate 6 (scripts/check_run_summary_structure.py) reads the
    # gitignored generated_docs/run_summary.json; without this, a clean
    # checkout / CI job with no SMARTSHEET_API_TOKEN takes this synthetic
    # branch, never writes the file, and Gate 6 either crashes
    # (FileNotFoundError) or validates a STALE artifact from an earlier run.
    # Mirror the real path's 21-key structure with synthetic values so the
    # structural oracle validates a FRESH artifact every run.
    try:
        _synth_secs = session_duration.total_seconds()
        _synth_summary = {
            "timestamp": datetime.datetime.now().isoformat(),
            "mode": "synthetic",
            "success": True,
            "duration_seconds": round(_synth_secs, 3),
            "duration_minutes": round(_synth_secs / 60.0, 3),
            "sheets_discovered": 0,
            "rows_fetched": len(synthetic_rows),
            "groups_total": len(groups),
            "groups_generated": generated_files_count,
            "groups_uploaded": 0,
            "groups_skipped": 0,
            "groups_errored": len(groups) - generated_files_count,
            "files_generated": generated_files_count,
            "history_updates": 0,
            "fingerprint_changes_detected": 0,
            "api_calls": 0,
            "audit_risk_level": "NONE",
            "attribution_rows_held": 0,
            "snapshots_written": 0,
            "snapshots_already_frozen": 0,
            "snapshots_errored": 0,
        }
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)
        with open(os.path.join(OUTPUT_FOLDER, 'run_summary.json'), 'w') as _rsf:
            json.dump(_synth_summary, _rsf, indent=2)
    except Exception as _rse:
        logging.warning(f"⚠️ Could not write synthetic run_summary.json: {_rse}")
    return generated_files_count


# --- MAIN EXECUTION ---


def _run_memory_write_phase(
    all_rows: list[dict],
    mem_run_id: str,
    session_start: datetime.datetime,
) -> dict[str, Any]:
    """Phase 10 (MEM-02/MEM-03): shadow-write every accepted row's current
    state to ``pipeline_memory.row_state`` / ``row_event``, bucketed by
    source sheet, ONE bulk RPC per sheet.

    Consumes rows ALREADY fetched this run (``all_rows``, from
    ``get_all_source_rows``) -- never issues its own Smartsheet call and
    never spins up a thread pool: this loop is sequential BY DESIGN so the
    per-iteration sub-budget check below can stop it mid-loop
    (10-RESEARCH.md Pitfall 6 -- the attachment pre-fetch's single
    collective ``as_completed(timeout=...)`` is NOT the model here).

    Self-gated on ``RUN_MEMORY_WRITE_ENABLED`` / ``TEST_MODE`` (the same
    module-level constants ``main()`` already checks at its two run_ledger
    hook call sites -- defense-in-depth, mirrors that double-gate) so this
    function is directly callable -- and testable -- with zero writer-
    module calls when the flag is off, independent of how ``main()``
    itself is invoked.

    The affected ``(wr, week_ending)`` set is accumulated for
    OBSERVABILITY ONLY -- nothing in this function, and nothing in its
    caller, may read it back to decide whether a group is skipped,
    regenerated, or uploaded. That gate stays entirely on the existing
    local ``hash_history.json`` / durable group hash path (10-CONTEXT.md,
    plan success criteria).

    Returns a dict of counts only (no PII, no per-row values):
    ``sheets_written``, ``sheets_errored``, ``rows_sent``,
    ``rows_changed``, ``affected`` (the (wr, week_ending) set),
    ``elapsed_seconds``. NEVER raises -- every per-sheet write already
    goes through ``pipeline_memory.writer``'s own fail-open contract, and
    this function additionally isolates one sheet's unexpected exception
    from the rest of the loop.
    """
    result: dict[str, Any] = {
        "sheets_written": 0,
        "sheets_errored": 0,
        "rows_sent": 0,
        "rows_changed": 0,
        "affected": set(),
        "elapsed_seconds": 0.0,
    }

    if not (RUN_MEMORY_WRITE_ENABLED and not TEST_MODE):
        return result

    _phase_start = datetime.datetime.now()

    # Pre-flight sub-budget guard -- mirrors the attachment pre-fetch
    # guard's elapsed -> remaining -> required shape (lines ~766-791
    # above) verbatim: skip the ENTIRE phase, never a partial start, when
    # too little session budget remains for it plus generation headroom.
    if TIME_BUDGET_MINUTES and GITHUB_ACTIONS_MODE:
        _pre_elapsed_min = (
            (datetime.datetime.now() - session_start).total_seconds() / 60.0
        )
        _remaining_min = TIME_BUDGET_MINUTES - _pre_elapsed_min
        _required_min = (
            RUN_MEMORY_WRITE_MAX_MINUTES
            + RUN_MEMORY_WRITE_GENERATION_HEADROOM_MIN
        )
        if _remaining_min <= _required_min:
            logging.warning(
                f"⏩ Skipping run-memory row writes: {_pre_elapsed_min:.1f}min "
                f"already elapsed, only {_remaining_min:.1f}min left in "
                f"session budget (need > {_required_min}min = "
                f"{RUN_MEMORY_WRITE_MAX_MINUTES}min memory-write budget + "
                f"{RUN_MEMORY_WRITE_GENERATION_HEADROOM_MIN}min generation "
                "headroom)."
            )
            sentry_add_breadcrumb(
                "pipeline_memory",
                f"Row-write phase skipped, {_remaining_min:.1f}min remaining",
                level="warning",
                data={
                    "elapsed_min": round(_pre_elapsed_min, 1),
                    "remaining_min": round(_remaining_min, 1),
                    "required_remaining_min": _required_min,
                },
            )
            return result

    # Bucket already-fetched rows by source sheet. No re-fetch, no
    # get_sheet call, no ThreadPoolExecutor -- sequential on purpose.
    buckets: dict[Any, list[dict]] = {}
    for row in all_rows:
        buckets.setdefault(row.get('__source_sheet_id'), []).append(row)
    sheet_items = list(buckets.items())

    for idx, (sheet_id, bucket_rows) in enumerate(sheet_items, 1):
        # Resolve week_ending / snapshot_date with the SAME parser
        # grouping uses (pipeline.utils.excel_serial_to_date), so memory
        # stores the SAME dates the grouping phase computes. Stashed
        # under NEW double-underscore keys on each row dict -- invisible
        # to excel.py's column sampler and to calculate_data_hash() (the
        # existing group hash reads only explicitly named business
        # fields), same convention as __row_modified_at. A row whose
        # week-ending can't be resolved passes through with week_ending
        # None rather than being dropped -- row_state.week_ending is
        # nullable and memory records what was observed.
        for row in bucket_rows:
            row['__mem_week_ending'] = _utils.excel_serial_to_date(
                row.get('Weekly Reference Logged Date')
            )
            row['__mem_snapshot_date'] = _utils.excel_serial_to_date(
                row.get('Snapshot Date')
            )
            # WR-01 (10-REVIEW.md): pre-parse the two NUMERIC-bound
            # cells with the engine's own parsers (pipeline.pricing) so
            # a decorated value ("$1,234.50", "12 ea") never reaches
            # upsert_rows_bulk as a raw string -- that fails the
            # Postgres NUMERIC cast and, under the fail-open contract,
            # silently drops the WHOLE 500-row chunk with no error
            # surfaced. An empty/absent cell stays None (a clean
            # nullable NUMERIC) rather than pricing's own 0.0-for-
            # missing business default, which would fabricate an
            # observed zero quantity that was never actually on the
            # row. Stashed under the SAME double-underscore convention
            # as the two date keys above -- invisible to excel.py's
            # column sampler and to calculate_data_hash() -- but NOTE
            # quantity/units_total_price ARE HASH_FIELDS members on the
            # pipeline_memory side (row_state.content_hash), so this
            # changes that hash for any row whose cell carried
            # decoration; harmless today only because the write path is
            # OFF and no rows are stored yet.
            _raw_qty = row.get('Quantity')
            row['__mem_quantity'] = (
                None if _raw_qty in (None, '')
                else _pricing._parse_quantity(_raw_qty)
            )
            _raw_utp = row.get('Units Total Price')
            row['__mem_units_total_price'] = (
                None if _raw_utp in (None, '')
                else _pricing.parse_price(_raw_utp)
            )

        try:
            sheet_affected = _mem_writer.upsert_rows_bulk(
                sheet_id, mem_run_id, bucket_rows,
            )
        except Exception:
            logging.warning(
                "⚠️ pipeline_memory upsert_rows_bulk raised unexpectedly "
                f"for sheet {sheet_id} (non-fatal); treating as errored "
                "this run."
            )
            sheet_affected = set()
            result["sheets_errored"] += 1
        else:
            if sheet_affected:
                result["sheets_written"] += 1

        result["rows_sent"] += len(bucket_rows)
        result["rows_changed"] += len(sheet_affected)
        result["affected"] |= sheet_affected

        # Per-iteration sub-budget check -- AFTER each sheet's call, not
        # once before the loop (10-RESEARCH.md Pitfall 6): a slow
        # Supabase response stops memory writes for the REMAINING sheets
        # instead of consuming the whole session budget. Gated the same
        # way as the pre-flight guard and the main group loop's own
        # per-iteration check (pipeline/orchestrate.py lines ~1418-1431).
        if TIME_BUDGET_MINUTES and GITHUB_ACTIONS_MODE:
            _loop_elapsed_min = (
                (datetime.datetime.now() - _phase_start).total_seconds()
                / 60.0
            )
            if _loop_elapsed_min >= RUN_MEMORY_WRITE_MAX_MINUTES:
                _remaining_sheets = len(sheet_items) - idx
                logging.warning(
                    f"⏰ Run-memory sub-budget exhausted "
                    f"({_loop_elapsed_min:.1f}min >= "
                    f"{RUN_MEMORY_WRITE_MAX_MINUTES}min). Stopping with "
                    f"{_remaining_sheets} sheet(s) unwritten this run."
                )
                sentry_add_breadcrumb(
                    "pipeline_memory",
                    f"Row-write budget exhausted after {idx} sheet(s)",
                    level="warning",
                    data={
                        "elapsed_min": round(_loop_elapsed_min, 1),
                        "sheets_remaining": _remaining_sheets,
                    },
                )
                break

    result["elapsed_seconds"] = (
        datetime.datetime.now() - _phase_start
    ).total_seconds()
    logging.info(
        f"⚡ Run-memory row writes: {result['sheets_written']} sheet(s) "
        f"written, {result['sheets_errored']} errored, "
        f"{result['rows_sent']} row(s) sent, {result['rows_changed']} "
        f"changed, {len(result['affected'])} group(s) affected, "
        f"{result['elapsed_seconds']:.1f}s elapsed."
    )
    return result


def _resolve_mem_sheet_kind(sheet_id: Any) -> str:
    """Classify a discovered sheet's ``sheet_registry.kind`` (MEM-01).

    Reads ``pipeline.discovery``'s live-proxy globals AT CALL TIME via
    the ``_discovery`` module alias -- never a module-level from-import,
    which would snapshot the pre-discovery (empty) sets (Phase 09 D-01
    live-proxy contract; 10-03-PLAN.md <interfaces>).

    Order: ``SUBCONTRACTOR_SHEET_IDS`` or ``_FOLDER_DISCOVERED_SUB_IDS``
    -> ``'subcontractor'``; ``_FOLDER_DISCOVERED_ORIG_IDS`` ->
    ``'original_contract'``; otherwise ``'primary'``. Every returned
    value is one of the three the DDL's ``sheet_registry.kind`` CHECK
    constraint accepts (``pipeline_memory/schema.sql``) -- ``'vac_crew'``
    is deliberately never returned (10-RESEARCH.md Assumption A4: VAC
    Crew capability is column-presence-driven on primary/subcontractor
    sheets, not a discovered sheet-id bucket).

    Standalone module-level function (not a closure nested inside
    ``main()``) so it is directly unit-testable via
    ``mock.patch.object(pipeline.discovery, ...)`` without invoking any
    of ``main()``'s Smartsheet/Excel/Sentry machinery -- same
    testability rationale as ``_run_memory_write_phase`` (10-02 key-
    decision). The "read at call time" property this exists for is
    identical either way: a module-level function reading
    ``_discovery.NAME`` is just as live as a nested closure doing the
    same read.
    """
    if sheet_id in (
        _discovery.SUBCONTRACTOR_SHEET_IDS
        | _discovery._FOLDER_DISCOVERED_SUB_IDS
    ):
        return "subcontractor"
    if sheet_id in _discovery._FOLDER_DISCOVERED_ORIG_IDS:
        return "original_contract"
    return "primary"


def _extract_attachment_id_name(attach_result: Any) -> tuple[Any, Any]:
    """Defensively extract ``(id, name)`` from a Smartsheet SDK
    attach-call result. NEVER raises -- returns ``(None, None)`` on any
    unexpected shape.

    The SDK's successful ``Attachments.attach_file_to_row(...)`` call
    returns a ``Result`` whose ``.data`` is the created ``Attachment``
    carrying ``.id`` and ``.name`` (10-03-PLAN.md <interfaces>). PURE /
    stateless (no I/O, no module state) so it's directly unit-testable
    without invoking the nested ``_upload_one`` upload worker.
    """
    try:
        data = getattr(attach_result, 'data', None)
        return getattr(data, 'id', None), getattr(data, 'name', None)
    except Exception:
        return None, None


def _build_group_state_flush(
    deferred_records: list[dict[str, Any]],
    group_upload_ok: dict[Any, bool],
    upload_tasks: list[dict[str, Any]],
    attachment_side_channel: dict[Any, dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Compute the ``group_state`` records to write and the withheld
    count from the post-upload flush's already-built state. PURE (no
    I/O, no module-level state, never raises internally) so it's
    directly unit-testable without invoking ``main()`` -- mirrors
    ``_run_memory_write_phase``'s standalone-function testability
    pattern (10-02 key-decision).

    For each deferred record (one per group, appended in the group
    loop -- see the ``_deferred_group_state.append`` call site):
      - upload NOT ok for the group (``group_upload_ok`` false/absent)
        -> WITHHOLD: counted, no record produced. Unlike the durable
        hash store, ``group_state`` is not read by anything in Phase
        10, so there is no sentinel to write and nothing to actively
        invalidate -- a withheld group simply has no memory row until
        a run whose upload completes.
      - upload ok -> expand into ONE row per matching upload-task
        ``target_sheet_id`` (a ``reduced_sub`` group contributes ONE
        deferred record but produced up to TWO upload tasks -- this
        expansion is driven from the ACTUAL upload-task list, never a
        hard-coded sheet-id pair, so a future third leg needs no
        change here), looking up the attachment id/name from the side
        channel by the 4-part ``(group_key, variant, file_identifier,
        target_sheet_id)`` key. A leg with no side-channel entry (e.g.
        it reported ``'skipped'`` -- nothing was attached this run)
        contributes ``None`` for both attachment fields, which
        ``upsert_group_state`` then omits from the payload entirely.
    """
    records: list[dict[str, Any]] = []
    withheld = 0
    for rec in deferred_records:
        if not group_upload_ok.get(rec['group_key']):
            withheld += 1
            continue
        matching_sheet_ids = {
            t['target_sheet_id'] for t in upload_tasks
            if t.get('group_key') == rec['group_key']
        }
        for target_sheet_id in matching_sheet_ids:
            side_key = (
                rec['group_key'], rec['variant'],
                rec.get('file_identifier') or '', target_sheet_id,
            )
            attach = attachment_side_channel.get(side_key, {})
            records.append({
                'wr': rec['wr_num'],
                'week_ending': rec['week_iso'],
                'variant': rec['variant'],
                'identifier': rec.get('identifier') or '',
                'target_sheet_id': target_sheet_id,
                'content_hash': rec['data_hash'],
                'row_count': rec['row_count'],
                'attachment_id': attach.get('attachment_id'),
                'attachment_name': attach.get('attachment_name'),
            })
    return records, withheld


def main():  # pyright: ignore[reportGeneralTypeIssues]
    """Main execution function with all fixes implemented.

    NOTE: Pyright reports ``reportGeneralTypeIssues`` ("Code is too complex
    to analyze") on this function because it exceeds the analyzer's internal
    branch/path budget. The behavior is correct and exercised by CI; the
    warning is suppressed at the def line so type-checking of the rest of
    the module remains clean. A full refactor into subroutines is tracked
    separately — many of the local variables here participate in the
    ``except``/``finally`` blocks at the bottom, so extraction requires
    care to preserve the existing error-reporting + cron-checkin contract.
    """
    # ── Phase 09 W6 facade-read prelude (D-06 + W2-W5 pattern) ─────
    # main() was relocated from generate_weekly_pdfs.py to
    # pipeline.orchestrate.  Test-rebound / facade-resident names main()
    # reads must resolve to the facade's *current* binding at call time; a
    # module-level from-import here would snapshot the import-time value and
    # miss a test rebind on the facade.  Bind them from the facade once at
    # entry.  The _billing_audit_writer injection (D-06) at the
    # _resolve_unchanged_for_skip call site reads the facade attribute
    # directly so the authoritative Supabase hash lookup is NOT silently
    # disabled.
    import generate_weekly_pdfs as _gwp
    TEST_MODE = _gwp.TEST_MODE
    SENTRY_DSN = _gwp.SENTRY_DSN
    RES_GROUPING_MODE = _gwp.RES_GROUPING_MODE
    OUTPUT_FOLDER = _gwp.OUTPUT_FOLDER
    KEEP_HISTORICAL_WEEKS = _gwp.KEEP_HISTORICAL_WEEKS
    PRIMARY_CLAIM_ATTRIBUTION_ENABLED = _gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED
    VAC_CREW_CLAIM_ATTRIBUTION_ENABLED = _gwp.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED
    SUBCONTRACTOR_RATE_VARIANTS_ENABLED = (
        _gwp.SUBCONTRACTOR_RATE_VARIANTS_ENABLED
    )
    SUBCONTRACTOR_PPP_SHEET_ID = _gwp.SUBCONTRACTOR_PPP_SHEET_ID
    AUDIT_SYSTEM_AVAILABLE = _gwp.AUDIT_SYSTEM_AVAILABLE
    BILLING_AUDIT_AVAILABLE = _gwp.BILLING_AUDIT_AVAILABLE
    BillingAudit = _gwp.BillingAudit
    _billing_audit_writer = _gwp._billing_audit_writer
    compute_assignment_fingerprint = getattr(
        _gwp, "compute_assignment_fingerprint", None
    )
    session_start = datetime.datetime.now()
    generated_files_count = 0
    generated_filenames = []  # Track exact filenames created this session
    # Sentry session-transaction handle. Hoisted to the top of main() so the
    # except/finally blocks at the bottom of this function always see _txn
    # bound. Synthetic TEST_MODE returns and the "no SMARTSHEET_API_TOKEN"
    # raise both short-circuit past the in-place start-transaction block
    # further down, which would otherwise leave _txn unbound and turn any
    # main() exit through finally into an UnboundLocalError.
    _txn = None
    # Group-processing counters. Hoisted for the same reason as _txn:
    # the general except handler and the finally-block cron check-in
    # reference these unconditionally, but their in-flow initialization
    # sits AFTER the discovery/fetch phases. An early failure (e.g.
    # "No valid data rows found" raised in Phase 2 — the 2026-08-05
    # all-sheets-403 incident) previously turned the real error into
    # ``UnboundLocalError: _groups_errored`` inside the handler,
    # masking the root cause in both the log and Sentry. The later
    # in-flow re-initialization is kept (harmless re-zeroing).
    _groups_skipped = 0
    _groups_generated = 0
    _groups_uploaded = 0
    _groups_errored = 0
    _api_calls_count = 0
    history_updates = 0
    # Phase 10 (MEM-01/MEM-02/MEM-03): run-memory counters, hoisted for the
    # same documented reason as the _groups_* family above -- the
    # run-finish hook near the bottom of main() references these
    # unconditionally, so an early Phase-1/2 exception must not turn a
    # real error into an UnboundLocalError. Populated by
    # _run_memory_write_phase() (called right after Phase 2 completes,
    # below) -- zero defaults here cover the case where that phase never
    # runs (flag off, TEST_MODE, or an exception before Phase 2 finishes).
    _mem_sheets_written = 0
    _mem_sheets_errored = 0
    _mem_rows_sent = 0
    _mem_rows_changed = 0
    _mem_affected = set()
    _mem_run_id = _mem_writer.resolve_run_id()
    # Explicit session-failure sentinel for the finally-block cron
    # check-in (Copilot review, PR #297): _groups_errored == 0 alone
    # cannot distinguish "clean run" from "died before any group was
    # processed" — a pre-group exception (e.g. the all-sheets-403
    # authorization failure) would otherwise check in as OK. Set True
    # in every except handler below.
    _session_failed = False

    # Sentry cron check-in: signal "in_progress" at session start
    _cron_monitor_slug = os.getenv("SENTRY_CRON_MONITOR_SLUG", "weekly-excel-generation")
    _cron_checkin_id = _sentry_cron_checkin_start(_cron_monitor_slug)

    try:
        # Set Sentry context (SDK 2.x: top-level API)
        _set_sentry_session_tags(session_start)

        logging.info("🚀 Starting Weekly PDF Generator with Complete Fixes")
        
        # Initialize Smartsheet client or fall back to synthetic data in TEST_MODE
        if not API_TOKEN:
            if not TEST_MODE:
                raise Exception("SMARTSHEET_API_TOKEN not configured")
            _run_synthetic_test_mode(session_start)
            return
        
        client = smartsheet.Smartsheet(API_TOKEN)
        client.errors_as_exceptions(True)

        # ── Phase 2 Plan 03: isolated garbage-attachment remediation mode ──
        # REMEDIATE_CLAIMERS defaults OFF ('0') — never fires on scheduled cron.
        # When active, the sweep runs and main() returns immediately (isolation:
        # no Excel generation occurs in this session).
        if REMEDIATE_CLAIMERS:
            _effective_dry_run = REMEDIATION_DRY_RUN or SKIP_UPLOAD
            logging.info(
                f"🧹 REMEDIATE_CLAIMERS=True — running isolated claimer "
                f"remediation sweep (dry_run={_effective_dry_run}, "
                f"window_weeks={REMEDIATION_WINDOW_WEEKS})"
            )
            run_claimer_remediation(
                client,
                dry_run=_effective_dry_run,
                window_weeks=REMEDIATION_WINDOW_WEEKS,
                valid_wr_weeks=None,  # isolated path: no live-identity set
            )
            return

        # ── Start root Sentry transaction for full session tracing ──
        # _txn handle is already initialized to None at the top of main().
        if SENTRY_DSN:
            _txn = sentry_sdk.start_transaction(
                op="session",
                name="weekly-excel-generation",
                description="Full weekly Excel generation session",
            )
            _txn.__enter__()
            _txn.set_data("test_mode", TEST_MODE)
            _txn.set_data("github_actions", GITHUB_ACTIONS_MODE)

        # #7 - milestone structured log: run start (counts/booleans only)
        _sentry_log_event(
            "info",
            "weekly run started",
            test_mode=TEST_MODE,
            github_actions=GITHUB_ACTIONS_MODE,
        )

        # Phase 10 (MEM-01/MEM-03): run_ledger 'start' row. Guarded by the
        # flag AND TEST_MODE (10-RESEARCH.md Pitfall 7 -- the synthetic
        # TEST_MODE path must never attempt a live Supabase call) and
        # wrapped in its own try/except so a broken writer module can
        # never break Excel generation (fail-open holds even if
        # pipeline_memory itself has a bug, not just a Supabase outage).
        if RUN_MEMORY_WRITE_ENABLED and not TEST_MODE:
            try:
                _mem_writer.run_ledger_start(
                    _mem_run_id,
                    mode="full",
                    release=os.getenv('SENTRY_RELEASE', '') or '',
                )
            except Exception:
                logging.warning(
                    "⚠️ pipeline_memory run_ledger_start failed "
                    "(non-fatal); memory not written this run."
                )

        # ── Source sheet discovery (includes folder discovery on cache miss) ──
        _phase_start = datetime.datetime.now()
        logging.info(f"\n{'='*60}")
        logging.info("📊 PHASE 1: Discovering source sheets...")
        logging.info(f"{'='*60}")
        sentry_add_breadcrumb("discovery", "Starting source sheet discovery")
        with sentry_sdk.start_span(op="smartsheet.discovery", name="Discover and validate source sheets") as span:
            source_sheets = discover_source_sheets(client)
            span.set_data("sheets_discovered", len(source_sheets) if source_sheets else 0)
        
        if not source_sheets:
            raise Exception("No valid source sheets found")
        
        _phase_elapsed = (datetime.datetime.now() - _phase_start).total_seconds()
        logging.info(f"⚡ Phase 1 complete: {len(source_sheets)} sheets discovered in {_phase_elapsed:.1f}s")
        sentry_add_breadcrumb("discovery", f"Discovered {len(source_sheets)} source sheets", data={"count": len(source_sheets)})

        # Phase 10 (MEM-01): sheet_registry shadow write, PASS 1 (pre-fetch).
        # Called TWICE this run -- here, right after discovery, and again
        # right after the row-write phase below (PASS 2) once
        # pipeline.fetch's version-watermark map is populated (this pass
        # runs BEFORE Phase 2 fetches anything, so last_sheet_version is
        # still empty on pass 1). Both calls are idempotent upserts on the
        # same key (sheet_id) -- documented two-pass ordering, not
        # accidental duplication. Guarded the same way as the run_ledger
        # hooks (flag AND TEST_MODE) and wrapped in its own try/except so a
        # broken writer module can never break Excel generation.
        if RUN_MEMORY_WRITE_ENABLED and not TEST_MODE:
            try:
                _mem_writer.upsert_sheet_registry(
                    source_sheets, _mem_run_id, _resolve_mem_sheet_kind,
                    _fetch.get_last_sheet_versions(),
                )
            except Exception:
                logging.warning(
                    "⚠️ pipeline_memory sheet_registry upsert (pass 1) "
                    "failed unexpectedly (non-fatal); registry not "
                    "written this pass."
                )

        # Get all source rows
        _phase_start = datetime.datetime.now()
        logging.info(f"\n{'='*60}")
        logging.info("📋 PHASE 2: Fetching source data...")
        logging.info(f"{'='*60}")
        with sentry_sdk.start_span(op="smartsheet.fetch_rows", name="Fetch all source rows from Smartsheet") as span:
            all_rows = get_all_source_rows(client, source_sheets)
            span.set_data("source_sheets_count", len(source_sheets))
            span.set_data("rows_fetched", len(all_rows) if all_rows else 0)
        
        if not all_rows:
            raise Exception("No valid data rows found")
        
        _phase_elapsed = (datetime.datetime.now() - _phase_start).total_seconds()
        logging.info(f"⚡ Phase 2 complete: {len(all_rows)} rows fetched from {len(source_sheets)} sheets in {_phase_elapsed:.1f}s")
        sentry_add_breadcrumb("data", f"Fetched {len(all_rows)} source rows from {len(source_sheets)} sheets", data={
            "row_count": len(all_rows),
            "sheet_count": len(source_sheets),
        })

        # Phase 10 (MEM-02/MEM-03): per-sheet row-state shadow write.
        # _run_memory_write_phase self-gates on RUN_MEMORY_WRITE_ENABLED /
        # TEST_MODE (mirrors the run_ledger start/finish hooks' defense-
        # in-depth double gate) and never raises on its own -- this
        # try/except is a second, outer belt so an unexpected bug in the
        # phase itself can never reach the audit/grouping/Excel path
        # below (fail-open holds even if pipeline_memory has a bug, not
        # just a Supabase outage).
        try:
            _mem_result = _run_memory_write_phase(
                all_rows, _mem_run_id, session_start,
            )
        except Exception:
            logging.warning(
                "⚠️ pipeline_memory row-write phase failed unexpectedly "
                "(non-fatal); memory rows not written this run."
            )
            _mem_result = {
                "sheets_written": 0, "sheets_errored": 0,
                "rows_sent": 0, "rows_changed": 0, "affected": set(),
            }
        _mem_sheets_written = _mem_result["sheets_written"]
        _mem_sheets_errored = _mem_result["sheets_errored"]
        _mem_rows_sent = _mem_result["rows_sent"]
        _mem_rows_changed = _mem_result["rows_changed"]
        _mem_affected = _mem_result.get("affected", set())

        # Phase 10 (MEM-01): sheet_registry shadow write, PASS 2. Now that
        # Phase 2 has fetched every sheet, pipeline.fetch's version-
        # watermark map is populated -- same guard, same fail-open
        # contract, same idempotent upsert key as pass 1 above.
        if RUN_MEMORY_WRITE_ENABLED and not TEST_MODE:
            try:
                _mem_writer.upsert_sheet_registry(
                    source_sheets, _mem_run_id, _resolve_mem_sheet_kind,
                    _fetch.get_last_sheet_versions(),
                )
            except Exception:
                logging.warning(
                    "⚠️ pipeline_memory sheet_registry upsert (pass 2) "
                    "failed unexpectedly (non-fatal); registry version "
                    "watermark not updated this run."
                )

        # Initialize audit system
        audit_system = None
        audit_results = {}
        if AUDIT_SYSTEM_AVAILABLE and not DISABLE_AUDIT_FOR_TESTING:
            try:
                sentry_add_breadcrumb("audit", "Starting billing audit", data={"skip_cell_history": SKIP_CELL_HISTORY})
                with sentry_sdk.start_span(op="audit.financial", name="Run billing audit on source data") as audit_span:
                    audit_system = BillingAudit(client, skip_cell_history=SKIP_CELL_HISTORY)
                    audit_results = audit_system.audit_financial_data(source_sheets, all_rows)
                    audit_span.set_data("risk_level", audit_results.get('summary', {}).get('risk_level', 'UNKNOWN'))
                    audit_span.set_data("total_anomalies", audit_results.get('summary', {}).get('total_anomalies', 0))
                logging.info(f"🔍 Audit complete - Risk level: {audit_results.get('summary', {}).get('risk_level', 'UNKNOWN')}")
                sentry_add_breadcrumb("audit", "Audit completed", data={
                    "risk_level": audit_results.get('summary', {}).get('risk_level', 'UNKNOWN'),
                    "total_anomalies": audit_results.get('summary', {}).get('total_anomalies', 0)
                })
            except Exception as e:
                logging.warning(f"⚠️ Audit system error: {e}")
                sentry_capture_with_context(
                    exception=e,
                    context_name="audit_system_error",
                    context_data={
                        "source_sheets_count": len(source_sheets),
                        "total_rows": len(all_rows),
                        "skip_cell_history": SKIP_CELL_HISTORY,
                        "error_type": type(e).__name__,
                        "error_message": _redact_exception_message(e),
                    },
                    tags={"error_location": "audit_system", "subsystem": "billing_audit"},
                    fingerprint=["audit-system", type(e).__name__]
                )
        else:
            logging.info("🚀 Audit system disabled for testing")

        # ── Snapshot-date drift audit (260812-jqx) ──────────────────
        # Pre-grouping seam: runs upstream of every Weekly Reference
        # Logged Date pre-pass reader in pipeline/grouping.py and of
        # the single week computation there, so zero grouping.py edits
        # are needed. Own try/except: a drift-audit failure must never
        # block the billing run (D-07).
        try:
            _snapshot_drift_summary = apply_snapshot_drift_holds(
                all_rows, source_sheets, client, session_start,
            )
            # Only touch audit_results['summary'] when the audit ran
            # (D-08 off-switch equivalence: with the switch off,
            # audit_results['summary'] must stay byte-identical to
            # today's shape).
            if _snapshot_drift_summary.get('enabled') and isinstance(
                audit_results.get('summary'), dict
            ):
                from audit_billing_changes import (  # noqa: PLC0415
                    escalate_risk_for_snapshot_drift,
                )
                escalate_risk_for_snapshot_drift(
                    audit_results['summary'],
                    _snapshot_drift_summary.get(
                        'automation_self_fire_holds', 0
                    ),
                )
                _snap_holds = _snapshot_drift_summary.get(
                    'automation_self_fire_holds', 0
                )
                if _snap_holds > 0:
                    sentry_capture_message_with_context(
                        f"Snapshot-drift hold applied to {_snap_holds} "
                        "row(s)",
                        level="warning",
                        context_name="snapshot_drift",
                        context_data=_snapshot_drift_summary,
                        tags={"subsystem": "snapshot_drift"},
                    )
        except Exception as _snap_exc:
            logging.warning(f"⚠️ Snapshot-drift audit error: {_snap_exc}")
            _snapshot_drift_summary = {'enabled': False}

    # Group rows by work request and week ending
        logging.info("📂 Grouping data...")
        with sentry_sdk.start_span(op="data.grouping", name="Group source rows by WR/week/variant") as span:
            groups = group_source_rows(all_rows)
            span.set_data("input_rows", len(all_rows))
            span.set_data("groups_created", len(groups) if groups else 0)

        # Optional full/partial hash reset purge BEFORE processing groups if requested
        if RESET_HASH_HISTORY or RESET_WR_LIST:
            with sentry_sdk.start_span(op="smartsheet.purge", name="Purge existing hashed outputs") as span:
                if RESET_WR_LIST:
                    logging.info(f"🧨 Hash reset requested for specific WRs: {sorted(list(RESET_WR_LIST))}")
                    span.set_data("purge_type", "wr_subset")
                    span.set_data("wr_count", len(RESET_WR_LIST))
                    purge_existing_hashed_outputs(client, TARGET_SHEET_ID, RESET_WR_LIST, TEST_MODE, dry_run=SKIP_UPLOAD)
                else:
                    logging.info("🧨 Global hash reset requested (RESET_HASH_HISTORY=1)")
                    span.set_data("purge_type", "global")
                    purge_existing_hashed_outputs(client, TARGET_SHEET_ID, None, TEST_MODE, dry_run=SKIP_UPLOAD)
            # After purge, any regenerated files get new timestamp+hash filenames and re-upload
        
        if not groups:
            raise Exception("No valid groups created")
        
        logging.info(f"📈 Found {len(groups)} work request groups to process")
        sentry_add_breadcrumb("grouping", f"Created {len(groups)} groups from {len(all_rows)} rows", data={
            "group_count": len(groups),
            "row_count": len(all_rows),
        })
        if MAX_GROUPS and len(groups) > MAX_GROUPS:
            logging.info(f"✂️ Limiting processing to first {MAX_GROUPS} groups for test run")
            groups = dict(list(groups.items())[:MAX_GROUPS])
        
        # Process groups
        snapshot_date = datetime.datetime.now()
        
        # Create target sheet map for production uploads.
        target_map = {}
        _target_sheet_obj = None  # Cached for cleanup to avoid redundant API call
        if not TEST_MODE:
            with sentry_sdk.start_span(op="smartsheet.target_map", name="Create target sheet map for uploads") as span:
                target_map, _target_sheet_obj = (
                    create_target_sheet_map_for(client, TARGET_SHEET_ID)
                )
                span.set_data("wr_count", len(target_map))

        # Phase 01 Plan 04 Task 1: build a SECOND target_map for the
        # subcontractor PPP sheet. Only ``_ReducedSub`` /
        # ``_ReducedSub_Helper_<name>`` upload tasks consume this map
        # (D-12 / SUB-03); ``primary`` / ``helper`` / ``vac_crew`` /
        # ``aep_billable`` continue to route through ``target_map``
        # alone, so a missing or unreachable PPP sheet only degrades
        # the second leg of the reduced-sub fan-out — the rest of the
        # pipeline is unaffected.
        #
        # Per Plan 04 acceptance criterion: only attempt the build
        # when the kill switch is on AND a distinct sheet id was
        # configured. Defense against an operator setting
        # ``SUBCONTRACTOR_PPP_SHEET_ID=<same as TARGET_SHEET_ID>``
        # which would otherwise cause every reduced-sub upload to
        # double-attach to the SAME target row.
        target_map_ppp: dict = {}
        _target_sheet_ppp_obj = None
        if (not TEST_MODE
                and SUBCONTRACTOR_RATE_VARIANTS_ENABLED
                and SUBCONTRACTOR_PPP_SHEET_ID
                and SUBCONTRACTOR_PPP_SHEET_ID != TARGET_SHEET_ID):
            try:
                with sentry_sdk.start_span(op="smartsheet.target_map_ppp", name="Create PPP target sheet map") as span:
                    target_map_ppp, _target_sheet_ppp_obj = create_target_sheet_map_for(client, SUBCONTRACTOR_PPP_SHEET_ID)
                    span.set_data("wr_count", len(target_map_ppp))
                logging.info(
                    f"🎯 Subcontractor PPP target sheet: "
                    f"{SUBCONTRACTOR_PPP_SHEET_ID}, "
                    f"{len(target_map_ppp)} WR# entries mapped"
                )
            except Exception as _ppp_exc:
                # Fail-safe: if the PPP sheet is unreachable (access
                # revoked, renamed, deleted), log + degrade to single-
                # sheet routing for this run. Per D-22 / Living
                # Ledger 2026-04-23 12:00, the exception body is
                # sanitised via ``_redact_exception_message`` before
                # reaching Sentry's ``event['contexts']``.
                logging.error(
                    f"Failed to load subcontractor PPP target sheet "
                    f"{SUBCONTRACTOR_PPP_SHEET_ID}: "
                    f"{_redact_exception_message(_ppp_exc)}"
                )
                target_map_ppp = {}
                _target_sheet_ppp_obj = None

        # PERFORMANCE: Pre-fetch all target row attachments into cache to eliminate
        # redundant per-row API calls in _has_existing_week_attachment and delete_old_excel_attachments.
        # Each row's attachments are fetched once here instead of 2-3 times in the group loop.
        attachment_cache = {}  # row_id -> list of attachment objects
        target_map_to_prefetch = {}
        if target_map and not TEST_MODE:
            target_map_to_prefetch = target_map
            # Pre-flight session-budget guard: if discovery + row fetch already consumed most
            # of TIME_BUDGET_MINUTES, skip pre-fetch entirely so we have time for generation.
            # Reserve ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN beyond the pre-fetch budget
            # so we don't end up with exactly enough time to pre-fetch and then zero time to
            # generate — that would recreate the original incident's zero-output failure mode.
            # Per-row fallback paths handle an empty cache transparently.
            if TIME_BUDGET_MINUTES and GITHUB_ACTIONS_MODE:
                _pre_elapsed_min = (datetime.datetime.now() - session_start).total_seconds() / 60.0
                _remaining_min = TIME_BUDGET_MINUTES - _pre_elapsed_min
                _required_remaining_min = ATTACHMENT_PREFETCH_MAX_MINUTES + ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN
                if _remaining_min <= _required_remaining_min:
                    logging.warning(
                        f"⏩ Skipping attachment pre-fetch: {_pre_elapsed_min:.1f}min already elapsed, "
                        f"only {_remaining_min:.1f}min left in session budget "
                        f"(need > {_required_remaining_min}min = "
                        f"{ATTACHMENT_PREFETCH_MAX_MINUTES}min pre-fetch budget + "
                        f"{ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN}min generation headroom). "
                        f"Attachment lookups will fall back to per-row fetches during generation."
                    )
                    sentry_add_breadcrumb(
                        "prefetch_skipped",
                        f"Pre-fetch skipped, {_remaining_min:.1f}min remaining",
                        level="warning",
                        data={
                            "elapsed_min": round(_pre_elapsed_min, 1),
                            "remaining_min": round(_remaining_min, 1),
                            "prefetch_budget_min": ATTACHMENT_PREFETCH_MAX_MINUTES,
                            "generation_headroom_min": ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN,
                            "required_remaining_min": _required_remaining_min,
                        },
                    )
                    target_map_to_prefetch = {}

        if target_map_to_prefetch:
            with sentry_sdk.start_span(op="smartsheet.attachment_prefetch", name="Pre-fetch row attachments") as span:
                logging.info(f"🚀 Starting parallel attachment pre-fetch with {PARALLEL_WORKERS} workers for {len(target_map_to_prefetch)} target rows (max {ATTACHMENT_PREFETCH_MAX_MINUTES}min)...")
                _att_start = datetime.datetime.now()

                def _fetch_row_attachments(row_item):
                    # row_item is (wr_num, target_row); only target_row is needed.
                    _, target_row = row_item
                    # Phase 10: retry transient failures via the shared helper
                    # (API 4000, server timeout, rate limit, network drop —
                    # bounded total backoff). Degrade to no-attachments on
                    # persistent failure, exactly as before (the row then falls
                    # back to per-row on-demand lookup at generation time).
                    try:
                        atts = smartsheet_call_with_retry(
                            client.Attachments.list_row_attachments,
                            TARGET_SHEET_ID, target_row.id,
                            label=f"attachment fetch row {target_row.id}",
                        ).data
                        return (target_row.id, atts)
                    except Exception:
                        return (target_row.id, [])

                _prefetch_budget_exceeded = False
                _prefetch_stuck_futures = 0     # future.result timed out after as_completed yielded
                _prefetch_cancelled = 0         # queued futures we successfully cancelled
                _prefetch_still_running = 0     # in-flight futures we abandoned to the background
                # Manual executor lifecycle with daemon workers. Three things can
                # block process exit for a non-daemon worker and all three matter
                # here: (1) _python_exit joins _threads_queues, (2) threading.
                # _shutdown joins _shutdown_locks, (3) executor.shutdown(wait=True)
                # joins via the `with` block. Using _DaemonThreadPoolExecutor
                # addresses (2) — daemon threads don't add their tstate lock to
                # _shutdown_locks. Using explicit shutdown(wait=False,
                # cancel_futures=True) in finally addresses (3). The detach helper
                # below addresses (1) — but only on the budget-exceeded path
                # (Copilot review: don't touch private APIs when everything
                # completed normally; the workers are already done and there's
                # nothing to skip). See _DaemonThreadPoolExecutor docstring for
                # the full three-defense story and the safety invariant.
                executor = _DaemonThreadPoolExecutor(max_workers=PARALLEL_WORKERS)
                futures = [executor.submit(_fetch_row_attachments, item) for item in target_map_to_prefetch.items()]
                total_futures = len(futures)
                _phase_budget_sec = ATTACHMENT_PREFETCH_MAX_MINUTES * 60

                # Helper: pop workers from concurrent.futures' atexit join
                # registry so _python_exit doesn't t.join() them at interpreter
                # shutdown (daemon-ness doesn't help here — join() blocks
                # unconditionally). Called only when we're abandoning in-flight
                # work. Uses private APIs; getattr guards keep the main path
                # working if a future Python rearranges the names.
                def _detach_from_atexit_registry():
                    try:
                        registry = getattr(_cf_thread, '_threads_queues', None)
                        if registry is None:
                            return
                        for _t in list(getattr(executor, '_threads', ()) or ()):
                            registry.pop(_t, None)
                    except Exception as _det_e:
                        logging.debug(f"Could not detach pre-fetch workers from atexit registry: {_det_e}")
                try:
                    try:
                        # timeout= is measured from this call; the iterator itself raises
                        # FuturesTimeoutError if nothing else completes within that window,
                        # so a stuck HTTP call can't pin the consumer loop.
                        for i, future in enumerate(as_completed(futures, timeout=_phase_budget_sec), 1):
                            try:
                                row_id, atts = future.result(timeout=ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC)
                            except FuturesTimeoutError:
                                # Defensive — as_completed only yields done futures, so in
                                # practice this branch is unreachable; keep it so a future
                                # refactor that yields not-yet-done futures still degrades
                                # gracefully instead of raising.
                                _prefetch_stuck_futures += 1
                                continue
                            attachment_cache[row_id] = atts
                            if i % 25 == 0 or i == total_futures:
                                logging.info(f"   📎 [{i}/{total_futures}] Attachment pre-fetch progress...")
                    except FuturesTimeoutError:
                        # Phase sub-budget exhausted — stuck HTTP call(s) held the iterator.
                        # Bail out; remaining rows fall back to the per-row path.
                        _prefetch_budget_exceeded = True
                finally:
                    # Classify remaining work so the log / Sentry span reflects reality:
                    # cancel() returns True only for queued futures that hadn't started
                    # (Copilot review: the old code overcounted by calling `not f.done()`
                    # alone, conflating started-but-running with still-queued).
                    for f in futures:
                        if f.done():
                            continue
                        if f.cancel():
                            _prefetch_cancelled += 1
                        else:
                            _prefetch_still_running += 1
                    # wait=False so stuck in-flight threads don't block the critical path
                    # (the main generation loop). They'll either complete via SDK retry
                    # backoff or be hard-killed by the workflow's timeout-minutes ceiling.
                    # Only touch the atexit registry when we're actually abandoning
                    # work (budget exceeded + still-running threads remain).
                    # Normal completion leaves the workers done; _python_exit will
                    # find them complete and return immediately from its join().
                    if _prefetch_still_running:
                        _detach_from_atexit_registry()
                    executor.shutdown(wait=False, cancel_futures=True)

                _att_elapsed = (datetime.datetime.now() - _att_start).total_seconds()
                span.set_data("rows_cached", len(attachment_cache))
                span.set_data("rows_cancelled", _prefetch_cancelled)
                span.set_data("rows_still_running", _prefetch_still_running)
                span.set_data("rows_stuck", _prefetch_stuck_futures)
                if _prefetch_budget_exceeded:
                    logging.warning(
                        f"⏰ Attachment pre-fetch budget hit ({ATTACHMENT_PREFETCH_MAX_MINUTES}min). "
                        f"Cached {len(attachment_cache)}/{total_futures} rows in {_att_elapsed:.1f}s; "
                        f"{_prefetch_cancelled} cancelled, {_prefetch_still_running} still running in background, "
                        f"{_prefetch_stuck_futures} stuck. Remaining rows will use per-row fallback."
                    )
                    sentry_add_breadcrumb(
                        "prefetch_truncated",
                        f"Pre-fetch truncated at {ATTACHMENT_PREFETCH_MAX_MINUTES}min",
                        level="warning",
                        data={
                            "cached": len(attachment_cache),
                            "total": total_futures,
                            "cancelled": _prefetch_cancelled,
                            "still_running": _prefetch_still_running,
                            "stuck": _prefetch_stuck_futures,
                        },
                    )
                else:
                    logging.info(f"⚡ Pre-fetched attachments for {len(attachment_cache)} target rows in {_att_elapsed:.1f}s (parallel w/{PARALLEL_WORKERS} workers)")

        # ──────────────────────────────────────────────────────────
        # Phase 01 gap closure (REVIEW-WR-05): secondary attachment
        # prefetch for SUBCONTRACTOR_PPP_SHEET_ID rows. Without it,
        # every _ReducedSub / _ReducedSub_Helper_* upload to the PPP
        # sheet pays an extra ``list_row_attachments`` API call (for
        # delete_old_excel_attachments matching). The PPP sheet has
        # far fewer rows than TARGET_SHEET_ID — only the subset that
        # needs _ReducedSub* — so the cost amortizes quickly.
        #
        # Defense-in-depth contract (Living Ledger 2026-04-22 16:05):
        #   - _DaemonThreadPoolExecutor (NOT ThreadPoolExecutor)
        #   - as_completed(futures, timeout=...) for the wait
        #   - executor.shutdown(wait=False, cancel_futures=True)
        #   - _detach_ppp_from_atexit_registry() on budget-exceed path
        #   - Pre-flight skip if session budget < (PREFETCH_MAX +
        #     GENERATION_HEADROOM)
        # Safety invariant: PPP prefetch is OPTIONAL — both
        # delete_old_excel_attachments and _has_existing_week_attachment
        # accept cached_attachments=None and fall back to per-row API.
        # Do NOT add new consumers that assume the PPP cache is
        # populated.
        # ──────────────────────────────────────────────────────────
        _ppp_prefetch_eligible = (
            SUBCONTRACTOR_RATE_VARIANTS_ENABLED
            and SUBCONTRACTOR_PPP_SHEET_ID
            and SUBCONTRACTOR_PPP_SHEET_ID != TARGET_SHEET_ID
            and not TEST_MODE
            and target_map_ppp is not None
            and len(target_map_ppp) > 0
        )
        if _ppp_prefetch_eligible:
            # Pre-flight budget guard (Living Ledger 2026-04-22 16:05
            # rule 7): skip entirely if remaining budget < (prefetch
            # phase budget + generation headroom). Without the
            # headroom reservation, an edge case where session
            # budget == prefetch budget would still trigger the
            # prefetch and leave zero time for the main loop.
            if TIME_BUDGET_MINUTES > 0:
                _ppp_elapsed_min = (
                    datetime.datetime.now() - session_start
                ).total_seconds() / 60.0
                _ppp_remaining_min = TIME_BUDGET_MINUTES - _ppp_elapsed_min
                _ppp_required_min = (
                    ATTACHMENT_PREFETCH_MAX_MINUTES
                    + ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN
                )
                if _ppp_remaining_min < _ppp_required_min:
                    logging.info(
                        f"🛡️ Skipping PPP attachment prefetch: only "
                        f"{_ppp_remaining_min:.1f}min of session budget "
                        f"remain (need >= {_ppp_required_min:.0f}min for "
                        f"prefetch + generation headroom). PPP target "
                        f"rows will fall back to per-row API calls — "
                        f"correctness is preserved."
                    )
                    _ppp_prefetch_eligible = False
        if _ppp_prefetch_eligible:
            with sentry_sdk.start_span(
                op="smartsheet.attachment_prefetch_ppp",
                name="Pre-fetch PPP row attachments",
            ) as ppp_span:
                logging.info(
                    f"🚀 Starting parallel PPP attachment pre-fetch "
                    f"with {PARALLEL_WORKERS} workers for "
                    f"{len(target_map_ppp)} PPP target rows (max "
                    f"{ATTACHMENT_PREFETCH_MAX_MINUTES}min)..."
                )
                _ppp_att_start = datetime.datetime.now()

                def _fetch_ppp_row_attachments(row_item):
                    # row_item is (wr_num, target_row); only target_row is needed.
                    _, target_row = row_item
                    # Phase 10: same shared-helper retry as the target prefetch
                    # above (bounded backoff; degrade to no-attachments on
                    # persistent failure → per-row on-demand fallback).
                    try:
                        atts = smartsheet_call_with_retry(
                            client.Attachments.list_row_attachments,
                            SUBCONTRACTOR_PPP_SHEET_ID, target_row.id,
                            label=f"PPP attachment fetch row {target_row.id}",
                        ).data
                        return (target_row.id, atts)
                    except Exception:
                        return (target_row.id, [])

                _ppp_prefetch_budget_exceeded = False
                _ppp_prefetch_cancelled = 0
                _ppp_prefetch_still_running = 0

                ppp_executor = _DaemonThreadPoolExecutor(
                    max_workers=PARALLEL_WORKERS,
                )
                ppp_futures = [
                    ppp_executor.submit(_fetch_ppp_row_attachments, item)
                    for item in target_map_ppp.items()
                ]
                _ppp_phase_budget_sec = ATTACHMENT_PREFETCH_MAX_MINUTES * 60

                def _detach_ppp_from_atexit_registry():
                    try:
                        registry = getattr(
                            _cf_thread, '_threads_queues', None,
                        )
                        if registry is None:
                            return
                        for _t in list(
                            getattr(ppp_executor, '_threads', ()) or ()
                        ):
                            registry.pop(_t, None)
                    except Exception as _det_e:
                        logging.debug(
                            f"Could not detach PPP pre-fetch workers from "
                            f"atexit registry: {_det_e}"
                        )

                try:
                    for fut in as_completed(
                        ppp_futures, timeout=_ppp_phase_budget_sec,
                    ):
                        try:
                            row_id, atts = fut.result()
                            attachment_cache[row_id] = atts
                        except Exception as e:
                            # Worker exceptions already logged inside
                            # the worker — fall through to per-row.
                            logging.debug(
                                f"PPP prefetch future raised; row will "
                                f"fall back to per-row: {type(e).__name__}"
                            )
                except FuturesTimeoutError:
                    _ppp_prefetch_budget_exceeded = True
                    logging.warning(
                        f"⚠️ PPP attachment prefetch exceeded "
                        f"{ATTACHMENT_PREFETCH_MAX_MINUTES}min sub-budget; "
                        f"abandoning in-flight workers. Affected PPP rows "
                        f"will fall back to per-row API calls — correctness "
                        f"is preserved."
                    )
                finally:
                    # Three defenses against interpreter-exit hang:
                    # (1) atexit registry detach (only on budget-exceed,
                    #     per Copilot review — don't touch private APIs
                    #     when workers completed normally)
                    # (2) _DaemonThreadPoolExecutor handles tstate_lock
                    # (3) explicit shutdown(wait=False, cancel_futures=True)
                    if _ppp_prefetch_budget_exceeded:
                        _detach_ppp_from_atexit_registry()
                    for _fut in ppp_futures:
                        if _fut.cancel():
                            _ppp_prefetch_cancelled += 1
                        elif not _fut.done():
                            _ppp_prefetch_still_running += 1
                    ppp_executor.shutdown(wait=False, cancel_futures=True)

                _ppp_elapsed = (
                    datetime.datetime.now() - _ppp_att_start
                ).total_seconds()
                logging.info(
                    f"🏁 PPP attachment prefetch complete in "
                    f"{_ppp_elapsed:.1f}s: {len(target_map_ppp)} rows, "
                    f"{_ppp_prefetch_cancelled} cancelled, "
                    f"{_ppp_prefetch_still_running} still_running"
                )
                ppp_span.set_data("rows_prefetched", len(target_map_ppp))
                ppp_span.set_data("budget_exceeded", _ppp_prefetch_budget_exceeded)
                ppp_span.set_data("cancelled", _ppp_prefetch_cancelled)
                ppp_span.set_data("still_running", _ppp_prefetch_still_running)

        # Load hash history AFTER optional purge so we don't rely on stale attachments
        hash_history = load_hash_history(HASH_HISTORY_PATH)

        # ─────────────────────────────────────────────────────────
        # Phase 1.1 SUB-12 / D-17..D-19: idempotent hash-history prune.
        # ─────────────────────────────────────────────────────────
        # Runs once per migration version. The constant
        # ``PHASE_1_1_HASH_PRUNE_VERSION`` IS the kill switch (D-19);
        # the helper handles the version-gate + simplified-D-18 scope
        # detection + INFO logging. Mutates ``hash_history`` in place
        # so the sentinel + dropped-orphan side-effects survive the
        # subsequent ``save_hash_history`` write at end of run.
        # ``groups`` was built upstream at the ``group_source_rows``
        # call site; if grouping failed and execution reached here,
        # the helper degrades gracefully (empty groups → empty
        # _sub_wr_scope → no orphans dropped → sentinel still written).
        # Codex P2: track whether either one-time migration prune mutated
        # hash_history so we can persist it even on a run with no group
        # updates (the history_updates-gated save below would otherwise skip
        # it, making the migration re-run every no-update execution).
        _hash_history_migration_dirty = False
        try:
            if _run_phase_1_1_hash_prune(hash_history, groups):
                _hash_history_migration_dirty = True
        except Exception as _prune_exc:
            # Fail-safe per [2026-04-22 16:05] rule 4 — the prune
            # is an optimization. A failed prune MUST NOT break the
            # billing pipeline. Log + continue with the unmodified
            # hash_history (the sentinel will not advance, the prune
            # retries next run, the orphans remain harmless).
            logging.warning(
                f"⚠️ Phase 1.1 hash-history prune failed; continuing "
                f"with existing history: {_prune_exc!r}"
            )

        # Subproject B: one-time prune of legacy blank-identifier
        # reduced_sub/aep_billable orphans (kill switch is the version
        # constant). Fail-safe — a failed prune must not break the run.
        try:
            if _run_subproject_b_hash_prune(hash_history, groups):
                _hash_history_migration_dirty = True
        except Exception as _b_prune_exc:
            logging.warning(
                f"⚠️ Subproject B hash-history prune failed; continuing "
                f"with existing history: {_b_prune_exc!r}"
            )

        # Subproject C: one-time prune of legacy blank-identifier vac_crew
        # orphans (kill switch is the version constant). Fail-safe — a
        # failed prune must not break the run.
        try:
            if _run_vac_crew_hash_prune(hash_history, groups):
                _hash_history_migration_dirty = True
        except Exception as _vc_prune_exc:
            logging.warning(
                f"⚠️ Vac crew hash-history prune failed; continuing "
                f"with existing history: {_vc_prune_exc!r}"
            )

        # Subproject D: one-time prune of legacy blank-identifier primary
        # orphans (kill switch is PRIMARY_CLAIM_ATTRIBUTION_ENABLED + the
        # version constant). Fail-safe — a failed prune must not break the
        # run.
        try:
            if _run_subproject_d_hash_prune(hash_history, groups):
                _hash_history_migration_dirty = True
        except Exception as _d_prune_exc:
            logging.warning(
                f"⚠️ Subproject D hash-history prune failed; continuing "
                f"with existing history: {_d_prune_exc!r}"
            )

        billing_audit_row_cache: set[str] = set()
        billing_audit_row_cache_dirty = False
        if BILLING_AUDIT_AVAILABLE and not TEST_MODE:
            billing_audit_row_cache = load_billing_audit_row_cache(
                BILLING_AUDIT_ROW_CACHE_PATH
            )
            # Ensure the cache file exists on disk even when no rows have been
            # frozen yet. The GitHub Actions cache/save step will fail with
            # "Path does not exist" when the file is absent, which can happen
            # on the very first run or when all rows were already cached from a
            # prior run (billing_audit_row_cache_dirty stays False, so the
            # save at the end of the run is skipped).  Writing an empty list
            # now is cheap and makes the CI step reliably no-op safe.
            if not os.path.exists(BILLING_AUDIT_ROW_CACHE_PATH):
                save_billing_audit_row_cache(
                    BILLING_AUDIT_ROW_CACHE_PATH, billing_audit_row_cache
                )
        history_updates = 0
        _groups_skipped = 0
        _groups_generated = 0
        _groups_uploaded = 0
        _groups_errored = 0
        _api_calls_count = 0
        _upload_tasks = []  # Collect upload tasks for parallel processing
        # Phase 10 (MEM-01/MEM-03): group_state deferred records + the
        # attachment side channel. Hoisted here (not with the other _mem_*
        # counters at the top of main()) because both are upload-phase-
        # scoped state, not run-scoped counters -- mirrors _upload_tasks /
        # _deferred_hash_upserts, the two closest existing analogs.
        _deferred_group_state = []
        # Keyed by (group_key, variant, file_identifier, target_sheet_id)
        # -- the same 4-part key a reduced_sub fan-out's two upload tasks
        # differ on ONLY in target_sheet_id, so this key never collapses
        # the two legs' attachment ids into one entry. threading.Lock-
        # guarded: up to PARALLEL_WORKERS (<=8) worker threads write
        # concurrently inside _upload_one below.
        _mem_attachment_side_channel = {}
        _mem_attachment_side_channel_lock = threading.Lock()
        # Sub-project E crash-consistency (2026-07-06): per-group durable
        # hash upserts are DEFERRED until after this group's attachment
        # upload actually succeeds. Records are appended in the emission
        # loop and flushed after the parallel upload phase. Writing the
        # hash before the upload executes lets a mid-run crash (e.g. a
        # lost runner) mark content as published while Smartsheet still
        # holds the stale attachment — with clean (hash-less) filenames
        # the skip gate then deadlocks on "unchanged + attachment
        # exists" forever (root cause of the WR 90968595 / week 070526
        # incident, failed run 28752355941).
        _deferred_hash_upserts = []
        # Codex P2 (PR #283): the LOCAL json hash_history entry is
        # deferred through the SAME gate. The json cache is the
        # documented fallback the skip gate consults on Supabase
        # outage (fetch_failure/unavailable) and the sole decider when
        # authoritative mode is OFF — persisting it at emission would
        # let a failed/dry-run upload still be skipped as "unchanged"
        # next run through that fallback, the same staleness one layer
        # down. TEST_MODE keeps the immediate write (no upload phase
        # exists there; see the emission-site comment).
        _deferred_history_updates = []

        _phase_group_start = datetime.datetime.now()
        _time_budget_exceeded = False

        # Phase 01 Plan 03 Task 2 (D-16/D-17): per-sheet accumulator
        # of subcontractor CU codes that fell through to SmartSheet
        # pricing during ``generate_excel``. ``_resolve_row_price``
        # records each missing CU into a per-call Counter that
        # ``generate_excel`` returns in the 5-tuple's trailing slot;
        # the per-group loop below attributes each group's missing
        # CUs to the source sheet(s) that contributed rows. After the
        # loop completes, exactly ONE WARNING per affected sheet is
        # emitted (D-17), naming the first 10 codes alphabetically.
        # The PII sanitizer's ``_PII_LOG_MARKERS`` already includes
        # the WARNING's stable marker ("Subcontractor rates CSV
        # missing") so it is dropped from Sentry before send.
        _missing_cus_by_sheet: dict[int, collections.Counter] = (
            collections.defaultdict(collections.Counter)
        )

        # Codex P1: source-side WR# collision quarantine.
        # ``_RE_SANITIZE_HELPER_NAME`` on the raw row value is a lossy
        # transform — two distinct raw WR# values may fold to the
        # same sanitized key. Downstream routing uses that sanitized
        # key for ``target_map`` lookups AND for attachment-identity
        # matching (filenames, hash_history), so an unquarantined
        # collision can cause cross-WR data corruption:
        #   * If target_map has BOTH colliding raws, round-6 quarantine
        #     removes the key from target_map so both uploads fail
        #     loudly at ``if wr_num in target_map`` — safe.
        #   * If target_map has only ONE of the raws (the other WR
        #     simply isn't in the target sheet yet), the source-side
        #     scan is the only defence. The second raw's group would
        #     otherwise resolve ``target_map[sanitized]`` to the first
        #     raw's row and upload to the wrong row.
        # We therefore key the quarantine on the sanitized WR ALONE
        # (not on ``(wr, week, variant)``): any pair of distinct raw
        # WRs that fold to the same sanitized key, anywhere in the
        # run's groups, is a collision regardless of week or variant.
        # Realistic numeric WR#s can't collide, so the scan is
        # zero-impact on production data.
        _source_wr_raws_per_key: dict = collections.defaultdict(set)
        for _g_rows in groups.values():
            if not _g_rows:
                continue
            _g_raw = str(_g_rows[0].get('Work Request #') or '').split('.')[0]
            if not _g_raw:
                continue
            _g_sanitized = _RE_SANITIZE_HELPER_NAME.sub('_', _g_raw)[:50]
            _source_wr_raws_per_key[_g_sanitized].add(_g_raw)
        _quarantined_source_wr_keys: set = {
            key for key, raws in _source_wr_raws_per_key.items()
            if len(raws) > 1
        }
        if _quarantined_source_wr_keys:
            for _qk in _quarantined_source_wr_keys:
                _raws = sorted(_source_wr_raws_per_key[_qk])
                logging.warning(
                    f"⚠️ Source WR# sanitization collision: raws={_raws} "
                    f"all fold to sanitized_key={_qk!r}. All affected "
                    f"groups (across every week + variant combination) "
                    f"will be SKIPPED to prevent cross-WR contamination "
                    f"of target_map uploads and attachment identity. "
                    f"Deduplicate the source WR# values and rerun."
                )
            logging.warning(
                f"⚠️ Total source WR# collision quarantines: "
                f"{len(_quarantined_source_wr_keys)} sanitized key(s); "
                f"see preceding warnings for raw values."
            )

        # Hoist static env var lookups once per run (not per row) —
        # these never change during execution and were previously
        # being read on every freeze_row call for every row in every
        # group. One-time read. Empty-string defaults (instead of
        # None) keep the values valid as Supabase RPC parameters
        # whether or not the deployment target applies NOT NULL to
        # ``release`` / ``run_id``.
        #
        # NOTE: the fingerprint flag state is NOT hoisted here. Flag
        # reads are per-call so a transient early-run ``get_flag``
        # failure (which deliberately isn't cached per the
        # non-caching-on-failure fix) can recover on subsequent
        # calls. Hoisting the boolean would lock the whole run into
        # the first-read result and silently drop pipeline_run rows.
        _billing_audit_release_env = os.getenv('SENTRY_RELEASE', '') or ''
        # ``run_id`` is part of the ``pipeline_run`` on_conflict key
        # ``(wr, week_ending, run_id)``. An empty string would make
        # every non-GitHub-Actions execution (manual reruns, local
        # debugging, crontab on a bare host, etc.) collide into the
        # same row for a given (wr, week), overwriting prior runs'
        # records and destroying run history.
        #
        # GitHub Actions re-runs preserve ``GITHUB_RUN_ID`` and only
        # increment ``GITHUB_RUN_ATTEMPT``. Appending the attempt
        # number makes each rerun create a distinct pipeline_run
        # row instead of overwriting the prior attempt — critical
        # for preserving drift-detection context when an earlier
        # attempt already wrote the key. Falls back to a microsecond
        # timestamp outside Actions.
        _ga_run_id = os.getenv('GITHUB_RUN_ID', '')
        _ga_run_attempt = os.getenv('GITHUB_RUN_ATTEMPT', '')
        if _ga_run_id:
            _billing_audit_run_id_env = (
                f"{_ga_run_id}.{_ga_run_attempt}"
                if _ga_run_attempt
                else _ga_run_id
            )
        else:
            _billing_audit_run_id_env = (
                f"local-{datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%S%fZ')}"
            )

        # Pre-aggregate rows per (sanitized_wr, week) across ALL
        # variants so the assignment fingerprint captures the full
        # personnel picture. ``group_source_rows`` splits helper-
        # completed rows out of the primary group (to prevent
        # double-counting in Excel generation), so each group only
        # carries ONE variant's rows. With the writer's per-
        # (wr, week, run_id) dedup, only the first variant emitted
        # actually writes — meaning a naive fingerprint would miss
        # helper / vac_crew personnel entirely, defeating the whole
        # point of this PR (mid-week helper swaps wouldn't change
        # the primary-only fingerprint → no drift alert).
        #
        # Walking ``groups.items()`` once here is O(total rows)
        # and negligible compared to per-group work.
        _billing_audit_fp_buckets: dict[tuple[str, str], list[dict]] = {}
        # Aggregated content hash per (wr, week). Like assignment_fp,
        # the emit_run_fingerprint dedup writes exactly one
        # ``pipeline_run`` row per (wr, week, run_id) — so
        # ``content_hash`` must reflect the UNION of all variants'
        # rows, not whichever variant was iterated first. Without
        # this, a source-ordering change between runs flips the
        # stored hash even when the underlying work set is
        # unchanged, making downstream run comparisons noisy.
        _billing_audit_agg_content_hashes: dict[tuple[str, str], str] = {}
        # Split the cheap work from the expensive work:
        #   • Bucket assembly (dict appends across rows) — runs
        #     when billing_audit is available AND at least one
        #     writer flag is enabled (or the flag state is
        #     indeterminate via a transient read blip).
        #     ``any_flag_enabled()`` fails OPEN — a transient
        #     feature_flag read blip returns True so we still
        #     build buckets and don't miss the first-write-wins
        #     freeze window for this run's completed rows. Cost
        #     is O(total rows) of dict appends.
        #   • ``calculate_data_hash`` per bucket — LAZY, memoized
        #     into ``_billing_audit_agg_content_hashes`` at first
        #     emit attempt inside the per-group block. The emit is
        #     already fingerprint-flag-gated, so flag-off runs
        #     never pay this cost, and flag-on runs pay it exactly
        #     once per bucket regardless of variant count (dedup
        #     no-ops reuse the memo).
        #
        # Wrapped in try/except Exception so any unexpected failure
        # (malformed row data, novel exception from ``any_flag_enabled``,
        # future code additions that introduce a bug) degrades
        # gracefully: buckets stay empty, the per-group emit falls
        # back to ``group_rows`` / ``data_hash`` via its
        # ``.get(key, fallback)`` calls, and Excel generation is
        # completely untouched. Class-name-only logging preserves
        # the _PII_LOG_MARKERS discipline.
        try:
            if (
                BILLING_AUDIT_AVAILABLE
                and not TEST_MODE
                and _billing_audit_writer.any_flag_enabled()
            ):
                for _agg_gk, _agg_rows in groups.items():
                    if not _agg_rows:
                        continue
                    # Defensive isinstance: group_source_rows always
                    # emits dicts, but a future mutation or bug
                    # upstream could violate that — don't let it
                    # raise AttributeError into the main loop.
                    _first = _agg_rows[0]
                    if not isinstance(_first, dict):
                        continue
                    _raw_wr = _first.get('Work Request #')
                    _wr_str = str(_raw_wr).split('.')[0] if _raw_wr else ''
                    _wr_san = _RE_SANITIZE_HELPER_NAME.sub('_', _wr_str)[:50]
                    _week_part = (
                        _agg_gk.split('_', 1)[0] if '_' in _agg_gk else ''
                    )
                    if not _wr_san or not _week_part:
                        continue
                    _billing_audit_fp_buckets.setdefault(
                        (_wr_san, _week_part), []
                    ).extend(_agg_rows)
        except Exception as _preloop_err:
            # Graceful degradation. Empty buckets + the per-group
            # emit's ``.get(key, fallback)`` calls preserve correct
            # Excel generation; only cross-variant fingerprint
            # aggregation is lost for this run.
            logging.warning(
                "⚠️ Billing audit pre-loop aggregation failed "
                f"(suppressed details): {type(_preloop_err).__name__}"
            )
            sentry_add_breadcrumb(
                "billing_audit",
                "Pre-loop aggregation failure",
                level="warning",
                data={"error_type": type(_preloop_err).__name__},
            )
            _billing_audit_fp_buckets = {}
            _billing_audit_agg_content_hashes = {}

        for group_idx, (group_key, group_rows) in enumerate(groups.items(), 1):
            # Graceful time budget: stop before Actions hard-kills the job
            if TIME_BUDGET_MINUTES and GITHUB_ACTIONS_MODE:
                elapsed_min = (datetime.datetime.now() - session_start).total_seconds() / 60.0
                if elapsed_min >= TIME_BUDGET_MINUTES:
                    remaining = len(groups) - group_idx + 1
                    logging.warning(f"⏰ Time budget exhausted ({elapsed_min:.1f}min >= {TIME_BUDGET_MINUTES}min). "
                                    f"Stopping with {remaining} group(s) remaining. "
                                    f"They will be processed on the next run (hash history preserved).")
                    _time_budget_exceeded = True
                    sentry_add_breadcrumb("time_budget", f"Budget exceeded after {elapsed_min:.1f}min", level="warning", data={
                        "groups_remaining": remaining, "groups_processed": group_idx - 1,
                    })
                    break
            try:
                # Calculate data hash for change detection
                data_hash = calculate_data_hash(group_rows)
                wr_num_raw = group_rows[0].get('Work Request #')
                wr_num = str(wr_num_raw).split('.')[0] if wr_num_raw else ''
                # Apply the same filesystem-safety sanitizer used inside
                # generate_excel so history keys, attachment prefix
                # matching, and Excel filenames all use the identical
                # WR identifier. Realistic numeric WR#s are unchanged;
                # path-traversal metacharacters get replaced with ``_``.
                wr_num = _RE_SANITIZE_HELPER_NAME.sub('_', wr_num)[:50]
                week_raw = group_key.split('_',1)[0] if '_' in group_key else ''

                # Extract variant and identifier for variant-aware hash history
                first_row = group_rows[0] if group_rows else {}
                variant = first_row.get('__variant', 'primary')

                # Source-side collision quarantine (see pre-scan above).
                # If this group's sanitized WR was flagged as colliding
                # with another group's raw WR anywhere in the run —
                # regardless of week or variant — skip it entirely. The
                # broader key is required because downstream
                # ``target_map`` lookups and attachment-identity
                # matching use only the sanitized WR; they do not
                # disambiguate by week or variant, so an unquarantined
                # cross-context collision can still route uploads /
                # deletes to the wrong target-sheet row.
                if wr_num in _quarantined_source_wr_keys:
                    logging.warning(
                        f"⚠️ Skipping group {group_key}: sanitized WR# "
                        f"{wr_num!r} collides with another group (see "
                        f"'Source WR# sanitization collision' WARNING "
                        f"above for the full raw-value list)."
                    )
                    _groups_skipped += 1
                    continue
                if variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):
                    # CRITICAL FIX: Include helper dept and job in identifier for unique hash keys
                    # This ensures helper files regenerate when new helper rows are added.
                    #
                    # CR-01 gap closure (Site 1 — main-loop identifier):
                    # helper, aep_billable_helper, and reduced_sub_helper all
                    # derive identifier / file_identifier from __helper_foreman
                    # so the round-trip with build_group_identity (which parses
                    # the helper-shadow filename's _Helper_<name>_<hash> tail in
                    # Plan 02) succeeds. Pre-fix, the two shadow variants fell
                    # through to the ``else`` branch that reads ``User`` —
                    # typically blank for shadow rows — producing
                    # file_identifier='' and a (parsed='Jane_Smith') == ('')
                    # mismatch in _has_existing_week_attachment. Result:
                    # permanent regeneration churn and orphan accumulation on
                    # SUBCONTRACTOR_PPP_SHEET_ID. The change is additive — the
                    # legacy ``helper`` body is preserved exactly; we just
                    # expand the gate to include the two helper-shadow variants.
                    # Sites 2 (valid_wr_weeks builder) and 3 (current_keys
                    # hash-history prune) carry the same gate — drift between
                    # the three sites is exactly the bug shape CR-01 documents.
                    helper_foreman = first_row.get('__helper_foreman', '')
                    helper_dept = first_row.get('__helper_dept', '')
                    helper_job = first_row.get('__helper_job', '')
                    identifier = f"{helper_foreman}|{helper_dept}|{helper_job}"
                    # file_identifier matches the sanitized name that generate_excel() puts in the filename
                    file_identifier = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50] if helper_foreman else ''
                elif variant == 'vac_crew':
                    # Subproject C identity site (Site 1 — main-loop identifier /
                    # history_key / file_identifier). GATED on the kill switch:
                    # disabled mode MUST reproduce the exact legacy '' identifier
                    # (bare _VacCrew filename, bare history_key) so existing
                    # attachments are not treated as stale and regeneration churn
                    # is not triggered. Enabled mode uses the sanitized claimer.
                    _vc = first_row.get('__current_foreman', '')
                    identifier = (
                        _RE_SANITIZE_IDENTIFIER.sub('_', _vc)[:50]
                        if (VAC_CREW_CLAIM_ATTRIBUTION_ENABLED and _vc) else ''
                    )
                    file_identifier = identifier
                elif variant in ('reduced_sub', 'aep_billable'):
                    # Subproject B identity site (Site 1 — main-loop
                    # identifier). Partitioned by the frozen primary
                    # claimer (__current_foreman). identifier ==
                    # file_identifier == sanitized claimer, matching the
                    # _ReducedSub_User_<name> filename and Sites 2 & 3.
                    _b_claimer = first_row.get('__current_foreman', '')
                    identifier = (
                        _RE_SANITIZE_IDENTIFIER.sub('_', _b_claimer)[:50]
                        if _b_claimer else ''
                    )
                    file_identifier = identifier
                else:
                    # Subproject D (2026-05-25): Site 1 — main-loop primary
                    # identity (history_key / file_identifier). Gated on kill
                    # switch: enabled → frozen claimer (__current_foreman);
                    # disabled → legacy ``User`` field ('' in production).
                    if (
                        PRIMARY_CLAIM_ATTRIBUTION_ENABLED
                        and RES_GROUPING_MODE in ('helper', 'both')
                    ):
                        _pf = first_row.get('__current_foreman', '')
                        identifier = (
                            _RE_SANITIZE_IDENTIFIER.sub('_', _pf)[:50]
                            if _pf else ''
                        )
                        file_identifier = identifier
                    else:
                        # Legacy primary variant: identifier derived from
                        # the row's ``User`` field.
                        user_val = first_row.get('User')
                        # PERFORMANCE: Use pre-compiled regex for identifier sanitization
                        identifier = _RE_SANITIZE_IDENTIFIER.sub('_', user_val)[:50] if user_val else ''
                        file_identifier = identifier
                
                # History key includes variant dimension to prevent collisions
                history_key = f"{wr_num}|{week_raw}|{variant}|{identifier}"

                # Sub-project E: ISO week-ending date for the durable
                # Supabase hash store (group_content_hash.week_ending is a
                # DATE column). Derived from the SAME __week_ending_date the
                # billing_audit freeze / fingerprint calls use (see the
                # _week_snap normalization below), so the durable 4-tuple key
                # matches across the reader, the writer, and those callers.
                # Falls back to '' when the date is absent — the lookup then
                # returns no_row and the upsert is keyed on '', both of which
                # fail safe to "regenerate".
                _wed = group_rows[0].get('__week_ending_date')
                if hasattr(_wed, 'date'):
                    _wed = _wed.date()
                week_iso = _wed.isoformat() if hasattr(_wed, 'isoformat') else ''

                # Pre-compute hash-change state before any optional side-effects.
                # Billing audit RPCs are the single most expensive per-group operation
                # in steady state, so we can safely skip them when the group hash is
                # unchanged versus hash_history (no row-content drift to freeze or emit).
                _history_eligible_for_skip = (
                    HISTORY_SKIP_ENABLED
                    and not (
                        FORCE_GENERATION
                        or week_raw in REGEN_WEEKS
                        or RESET_HASH_HISTORY
                        or RESET_WR_LIST
                    )
                )
                # Sub-project E: the unchanged decision now consults the
                # durable Supabase hash store when authoritative, falling
                # back to the local hash_history json cache on outage/miss.
                # See _resolve_unchanged_for_skip for the full decision
                # table. Default (authoritative OFF) is json-cache-only —
                # byte-identical to the pre-E behavior.
                _hash_unchanged = (
                    _resolve_unchanged_for_skip(
                        history_key, data_hash, hash_history,
                        wr_num, week_iso, variant, identifier,
                        billing_audit_writer=getattr(_gwp, "_billing_audit_writer", None),
                    )
                    if _history_eligible_for_skip
                    else False
                )

                # Pre-compute whether any eligible row in this group is absent
                # from the freeze cache. When _hash_unchanged is True but some
                # rows are uncached (e.g., freeze_attribution failed transiently
                # in a prior run), we still need to attempt those rows so they
                # are not permanently left unfrozen. This allows recovery without
                # waiting for the group's content hash to change again.
                #
                # Use set-difference rather than an any()-generator so that for
                # large groups (50-150 rows is typical) the membership test is
                # O(len(eligible_keys)) via a single set operation instead of
                # potentially scanning all rows in the worst case.
                _has_uncached_freeze_candidates: bool = False
                if BILLING_AUDIT_AVAILABLE and not TEST_MODE:
                    _eligible_freeze_keys = {
                        f"{wr_num}|{week_raw}|{_r.get('__row_id')}"
                        for _r in group_rows
                        if isinstance(_r.get("__row_id"), int)
                        and is_checked(_r.get("Units Completed?"))
                    }
                    _has_uncached_freeze_candidates = bool(
                        _eligible_freeze_keys - billing_audit_row_cache
                    )

                # ── Billing audit snapshot: freeze personnel + emit run fingerprint ──
                # Runs when the group hash has changed/is new, OR when some rows
                # were not successfully frozen in a prior run (transient failure
                # recovery). Skipped only when hash is unchanged AND every
                # eligible row is already in the freeze cache.
                # Failures must never break Excel generation.
                if (
                    BILLING_AUDIT_AVAILABLE
                    and not TEST_MODE
                    and (not _hash_unchanged or _has_uncached_freeze_candidates)
                    and _billing_audit_writer.any_flag_enabled()
                ):
                    try:
                        # Generic span name — the WR number is
                        # attached as span data below. The pipeline's
                        # _PII_LOG_MARKERS (see log sanitizer) treats
                        # "for WR " as a PII signal that gets
                        # dropped from Sentry Logs; span names
                        # bypass that sanitizer entirely and end up
                        # in performance/trace data regardless. Keep
                        # the name structural and route the
                        # identifier through set_data where it can
                        # be scoped, filtered, and (if needed) later
                        # scrubbed via before_send.
                        with sentry_sdk.start_span(
                            op="billing_audit.freeze",
                            name="billing_audit.freeze_attribution",
                        ) as _bas:
                            _bas.set_data("wr", wr_num)
                            _rows_to_freeze: list[dict] = []
                            _freeze_row_keys: dict[int, str] = {}
                            for _row in group_rows:
                                _row_id = _row.get("__row_id")
                                if not isinstance(_row_id, int):
                                    continue
                                if not is_checked(_row.get("Units Completed?")):
                                    continue
                                _cache_key = f"{wr_num}|{week_raw}|{_row_id}"
                                if _cache_key in billing_audit_row_cache:
                                    continue
                                _rows_to_freeze.append(_row)
                                _freeze_row_keys[id(_row)] = _cache_key
                            _bas.set_data("row_count", len(_rows_to_freeze))
                            _week_snap = first_row.get('__week_ending_date')
                            if hasattr(_week_snap, 'date'):
                                _week_snap = _week_snap.date()
                            # Parallelize per-row freeze_row calls so a
                            # group with N rows costs ~ceil(N/W) ×
                            # round-trip latency instead of N × latency.
                            # Pre-2026-04-25 this was a serial loop;
                            # at ~120ms per Supabase RPC, large groups
                            # (50-150 rows is typical for a busy WR
                            # week) burned 6-18 seconds of wall-clock
                            # purely on serial HTTP. Across 1900+
                            # groups in a weekly run that compounded
                            # into ~2 hours of new latency on top of
                            # the pre-billing_audit ~1h baseline,
                            # consuming TIME_BUDGET_MINUTES before the
                            # main loop reached Excel generation.
                            #
                            # ``freeze_row`` is intended to be fail-
                            # safe: it handles routine errors
                            # internally and records best-effort
                            # diagnostic counters. Counter writes are
                            # protected by ``_counters_lock`` so the
                            # totals stay exact even under concurrent
                            # invocation (the bare ``dict[k] += 1``
                            # is a multi-bytecode read-modify-write
                            # and CAN lose increments without the
                            # lock). A future raising here is still
                            # unexpected; log it (with sanitized row
                            # id) and continue with the rest of the
                            # group's writes.
                            #
                            # Executor reuse: ``get_freeze_row_executor()``
                            # returns a process-wide singleton lazily
                            # created on first use. With ~1900 groups
                            # per typical run, creating a per-group
                            # executor would mean ~1900 executor
                            # constructions and ~15,000 thread-join
                            # operations — each cheap individually
                            # but non-trivial in aggregate, and
                            # noisy in operational debugging.
                            # ``atexit`` handles shutdown when the
                            # interpreter exits.
                            if len(_rows_to_freeze) <= 1:
                                for _row in _rows_to_freeze:
                                    # Per D-18 / SUB-07 Path B: variant is
                                    # accepted by freeze_row for signature
                                    # symmetry but is NOT injected into the
                                    # freeze_attribution RPC params dict.
                                    # The variant lives on pipeline_run via
                                    # emit_run_fingerprint below. Default
                                    # 'primary' for pre-Phase-1 rows whose
                                    # __variant field isn't set (legacy
                                    # primary/helper/vac_crew rows from
                                    # before Plan 03 tagged them).
                                    _ok = _billing_audit_writer.freeze_row(
                                        _row,
                                        release=_billing_audit_release_env,
                                        run_id=_billing_audit_run_id_env,
                                        variant=_row.get('__variant', 'primary'),
                                    )
                                    if _ok:
                                        _rk = _freeze_row_keys.get(id(_row))
                                        if _rk:
                                            billing_audit_row_cache.add(_rk)
                                            billing_audit_row_cache_dirty = True
                            else:
                                # Singleton executor sized once at
                                # first use; subsequent calls share
                                # the same worker pool.
                                _bas_ex = (
                                    _billing_audit_writer
                                    .get_freeze_row_executor(
                                        max_workers=PARALLEL_WORKERS,
                                    )
                                )
                                _bas.set_data(
                                    "in_flight", len(_rows_to_freeze)
                                )
                                # Track future → row so an unexpected
                                # raise can be pinpointed to the
                                # specific row that triggered it,
                                # not just the WR — useful when one
                                # row in a 100-row group has malformed
                                # data the writer didn't anticipate.
                                _bas_future_to_row: dict[Any, dict] = {}
                                for _row in _rows_to_freeze:
                                    # Per D-18 / SUB-07 Path B: variant
                                    # threads through the parallelized
                                    # worker fn but does NOT reach the
                                    # RPC params dict. See the single-row
                                    # branch above for the full rationale.
                                    _bas_f = _bas_ex.submit(
                                        _billing_audit_writer.freeze_row,
                                        _row,
                                        release=_billing_audit_release_env,
                                        run_id=_billing_audit_run_id_env,
                                        variant=_row.get('__variant', 'primary'),
                                    )
                                    _bas_future_to_row[_bas_f] = _row
                                for _bas_f in as_completed(_bas_future_to_row):
                                    try:
                                        _ok = _bas_f.result()
                                        if _ok:
                                            _good_row = _bas_future_to_row.get(
                                                _bas_f, {}
                                            )
                                            _rk = _freeze_row_keys.get(
                                                id(_good_row)
                                            )
                                            if _rk:
                                                billing_audit_row_cache.add(_rk)
                                                billing_audit_row_cache_dirty = True
                                    except Exception:
                                        # Sanitized row identifier:
                                        # ``__row_id`` is a Smartsheet
                                        # numeric ID (not PII) — safe
                                        # to log. Skip Pole / CU /
                                        # Foreman fields per the
                                        # _PII_LOG_MARKERS rule.
                                        _bad_row = _bas_future_to_row.get(_bas_f, {})
                                        _bad_row_id = _bad_row.get("__row_id")
                                        logging.exception(
                                            "billing_audit.freeze_row "
                                            "raised unexpectedly for "
                                            "WR %s row_id=%s",
                                            wr_num,
                                            _bad_row_id,
                                        )
                            # Skip fingerprint compute + completed
                            # count when the fingerprint flag is off
                            # — emit_run_fingerprint would no-op
                            # inside otherwise, wasting per-group
                            # work. Checked per-group (not hoisted)
                            # so a transient early-run flag-read
                            # failure doesn't suppress fingerprint
                            # emission for the rest of the run.
                            # ``get_flag`` caches successful reads,
                            # so the steady-state cost is a single
                            # dict lookup per group.
                            if _billing_audit_writer.fingerprint_flag_enabled():
                                # Use the cross-variant aggregation
                                # so the fingerprint AND content hash
                                # cover all personnel + all rows
                                # (primary + helper + vac) for this
                                # (wr, week). Falls back to
                                # ``group_rows`` / ``data_hash`` only
                                # if the bucket is empty (shouldn't
                                # happen — the bucket is built from
                                # the same groups dict we're
                                # iterating).
                                _agg_key = (wr_num, week_raw)
                                _agg_fp_rows = _billing_audit_fp_buckets.get(
                                    _agg_key, group_rows
                                )
                                # Lazy + memoized content-hash
                                # computation. First emit attempt
                                # for a bucket pays the hashing
                                # cost once and caches the result;
                                # subsequent variants that
                                # dedup-no-op inside
                                # emit_run_fingerprint get a cache
                                # hit for free.
                                #
                                # ``calculate_data_hash`` assumes
                                # all rows share one ``__variant``
                                # (it reads sorted_rows[0]'s
                                # variant and conditionally
                                # includes VAC / helper fields
                                # based on it). Passing it the raw
                                # cross-variant bucket would make
                                # the result depend on sort order
                                # and can miss VAC personnel
                                # entirely. Instead: bucket rows by
                                # variant, hash each subset with
                                # the production helper (so each
                                # variant gets its own correct
                                # fields), then SHA-256 the
                                # variant-sorted
                                # ``variant=hash`` tokens. Result
                                # is deterministic and covers
                                # every variant's full field set.
                                if _agg_key in _billing_audit_fp_buckets:
                                    _agg_content_hash = (
                                        _billing_audit_agg_content_hashes.get(
                                            _agg_key
                                        )
                                    )
                                    if _agg_content_hash is None:
                                        # Variant-aware aggregated
                                        # hash, with per-helper sub-
                                        # bucketing so multi-helper
                                        # WRs produce a stable
                                        # content_hash (see
                                        # _compute_aggregated_content_hash).
                                        _agg_content_hash = (
                                            _compute_aggregated_content_hash(
                                                _agg_fp_rows
                                            )
                                        )
                                        _billing_audit_agg_content_hashes[
                                            _agg_key
                                        ] = _agg_content_hash
                                else:
                                    _agg_content_hash = data_hash
                                _fp = compute_assignment_fingerprint(_agg_fp_rows)
                                _completed = sum(
                                    1 for _r in _agg_fp_rows
                                    if is_checked(_r.get('Units Completed?'))
                                )
                                # Per D-18 / SUB-07 Path B: variant is
                                # recorded on pipeline_run via this call.
                                # All rows in a group share the same
                                # __variant by construction in
                                # group_source_rows (Plan 03), so reading
                                # group_rows[0] is canonical. Falls back to
                                # 'primary' when the row hasn't been
                                # tagged (legacy / non-variant-aware
                                # call paths) — matches the writer's
                                # None-coercion sentinel.
                                _group_variant = (
                                    group_rows[0].get('__variant', 'primary')
                                    if group_rows else 'primary'
                                )
                                _billing_audit_writer.emit_run_fingerprint(
                                    wr=wr_num,
                                    week_ending=_week_snap,
                                    content_hash=_agg_content_hash,
                                    assignment_fp=_fp,
                                    completed_count=_completed,
                                    total_count=len(_agg_fp_rows),
                                    release=_billing_audit_release_env,
                                    run_id=_billing_audit_run_id_env,
                                    variant=_group_variant,
                                )
                            _bas.set_data("rows", len(group_rows))
                            _bas.set_data("freeze_candidates", len(_rows_to_freeze))
                            _bas.set_data("variant", variant)
                    except Exception as _audit_err:
                        # Class name only — avoids leaking WR / foreman /
                        # helper names via log bodies (see _PII_LOG_MARKERS).
                        logging.warning(
                            f"⚠️ Billing audit snapshot failed for group (suppressed details): "
                            f"{type(_audit_err).__name__}"
                        )
                        sentry_add_breadcrumb(
                            "billing_audit",
                            "Snapshot failure (group-level)",
                            level="warning",
                            data={"error_type": type(_audit_err).__name__},
                        )

                # Decide skip based on stored history BEFORE generating Excel (only if FORCE not set)
                if _history_eligible_for_skip:
                    if _hash_unchanged:
                        # Only skip if attachment present OR policy allows skipping without attachment
                        can_skip = True
                        if ATTACHMENT_REQUIRED_FOR_SKIP and not TEST_MODE:
                            # Need a target row to verify attachment presence
                            if not target_map:
                                target_map, _target_sheet_obj = create_target_sheet_map(client)
                            target_row = target_map.get(str(wr_num)) if target_map else None
                            if target_row is None:
                                can_skip = False  # Can't verify; safer to regenerate
                            else:
                                # Use file_identifier (the value
                                # actually embedded in the filename)
                                # rather than identifier (the
                                # hash-history-tuple form that includes
                                # helper_dept/helper_job). For the
                                # helper variant the two diverge —
                                # filename only carries the sanitized
                                # helper_foreman, so comparing against
                                # the tuple form would always miss and
                                # force regeneration of unchanged
                                # helper groups.
                                has_attachment = _has_existing_week_attachment(
                                    client, TARGET_SHEET_ID, target_row,
                                    str(wr_num), week_raw, variant,
                                    file_identifier,
                                    cached_attachments=attachment_cache.get(target_row.id),
                                )
                                if not has_attachment:
                                    can_skip = False
                            # Codex P2 / Greptile P1 (PR #283):
                            # reduced_sub groups fan out to a second
                            # upload leg on the subcontractor PPP
                            # sheet. When the WR was absent from the
                            # PPP map at upload time, that leg was
                            # never attempted — so "unchanged +
                            # TARGET attachment exists" is not
                            # sufficient to skip once the WR appears
                            # on the PPP sheet. Require the PPP
                            # attachment too whenever the WR is
                            # CURRENTLY in the PPP map; a WR (still)
                            # absent from the map adds no requirement,
                            # so legitimately single-leg groups do not
                            # churn. Fail-safe direction only: this
                            # can force a regeneration (which uploads
                            # both legs and converges), never add a
                            # skip.
                            if (
                                can_skip
                                and variant in (
                                    'reduced_sub', 'reduced_sub_helper',
                                )
                                and target_map_ppp
                            ):
                                _ppp_skip_row = target_map_ppp.get(
                                    str(wr_num)
                                )
                                if (
                                    _ppp_skip_row is not None
                                    and not _has_existing_week_attachment(
                                        client,
                                        SUBCONTRACTOR_PPP_SHEET_ID,
                                        _ppp_skip_row,
                                        str(wr_num), week_raw, variant,
                                        file_identifier,
                                        cached_attachments=attachment_cache.get(
                                            _ppp_skip_row.id
                                        ),
                                    )
                                ):
                                    can_skip = False
                        if can_skip:
                            logging.info(f"⏩ Skip (unchanged + attachment exists) {variant} WR {wr_num} week {week_raw} hash {data_hash}")
                            _groups_skipped += 1
                            sentry_add_breadcrumb("group", f"Skipped unchanged group", level="info", data={
                                "wr": wr_num, "week": week_raw, "variant": variant, "hash": data_hash,
                            })
                            continue
                        else:
                            logging.info(f"🔁 Regenerating {variant} WR {wr_num} week {week_raw} despite unchanged hash (attachment missing or verification failed)")
                            sentry_add_breadcrumb("group", f"Regenerating despite same hash (attachment missing)", level="warning", data={
                                "wr": wr_num, "week": week_raw, "variant": variant,
                            })
                
                # Generate Excel file with complete fixes
                with sentry_sdk.start_span(op="excel.generate", name=f"Generate Excel for WR {wr_num}") as gen_span:
                    gen_span.set_data("group_key", group_key)
                    gen_span.set_data("row_count", len(group_rows))
                    gen_span.set_data("variant", variant)
                    gen_span.set_data("group_index", group_idx)
                    # Phase 01 Plan 03 Task 2 / Blocker 4: 5-tuple
                    # return. ``customer_name`` is forwarded to Plan 04's
                    # upload-task builder; ``missing_cus`` accumulates
                    # per source sheet into ``_missing_cus_by_sheet``
                    # for the D-17 end-of-loop WARNING.
                    (
                        excel_path,
                        filename,
                        wr_numbers,
                        _customer_name,
                        _missing_cus_for_group,
                    ) = generate_excel(
                        group_key, group_rows, snapshot_date, data_hash=data_hash
                    )
                    gen_span.set_data("filename", filename)

                # Attribute missing CUs to each source sheet that
                # contributed rows to this group (a single group can
                # span sheets when multiple sheets carry the same WR).
                # Distinct sheets get their own bucket so the per-sheet
                # WARNING surfaces the correct sheet id; rows missing
                # ``__source_sheet_id`` are bucketed under -1 so they
                # still surface in operator logs without crashing the
                # attribution loop.
                #
                # Phase 01 gap closure (REVIEW-WR-06): standardized on
                # ``__source_sheet_id`` (Phase 1 canonical field name)
                # instead of the legacy alias ``__sheet_id``. Both
                # fields are written to the same ``source['id']`` value
                # at populate time in ``_fetch_and_process_sheet``, so
                # the runtime behavior is unchanged today. The
                # migration ensures a future refactor that splits the
                # two field names cannot silently route missing-CU
                # WARNINGs to sheet -1 (the fallback bucket).
                if _missing_cus_for_group:
                    _contributing_sheet_ids: set[int] = set()
                    for _r in group_rows:
                        _sid = _r.get('__source_sheet_id')
                        if isinstance(_sid, int):
                            _contributing_sheet_ids.add(_sid)
                    if not _contributing_sheet_ids:
                        _contributing_sheet_ids = {-1}
                    for _sid in _contributing_sheet_ids:
                        _missing_cus_by_sheet[_sid].update(_missing_cus_for_group)
                
                generated_files_count += 1
                _groups_generated += 1
                generated_filenames.append(filename)
                
                # Collect upload task(s) for parallel processing
                # (instead of uploading serially). ``wr_numbers`` is
                # returned raw by ``generate_excel`` — do NOT read
                # from it here; the filename, hash-history key,
                # attachment prefix match, and target_map key all use
                # the sanitised main-loop ``wr_num`` and must stay
                # aligned to avoid repeated regeneration and orphaned
                # duplicate attachments on subsequent runs.
                #
                # Phase 01 Plan 04 Task 2: dispatch routing decisions
                # to ``_build_upload_tasks_for_group``. For
                # ``reduced_sub`` / ``reduced_sub_helper`` variants the
                # helper returns TWO tasks (one per target sheet); for
                # every other variant it returns ONE task on
                # ``TARGET_SHEET_ID``. Each task carries its own
                # ``target_sheet_id`` so the ``_upload_one`` worker
                # routes to the correct sheet without consulting a
                # global.
                if not TEST_MODE and wr_num:
                    _new_upload_tasks = _build_upload_tasks_for_group(
                        variant=variant,
                        wr_num=wr_num,
                        target_map=target_map,
                        target_map_ppp=target_map_ppp,
                        excel_path=excel_path,
                        filename=filename,
                        identifier=identifier,
                        file_identifier=file_identifier,
                        data_hash=data_hash,
                        week_raw=week_raw,
                        group_key=group_key,
                    )
                    _upload_tasks.extend(_new_upload_tasks)

                # Update hash history with variant-aware key. TEST_MODE
                # writes immediately (documented intent: "so future
                # prod runs can leverage"; there is no upload phase to
                # defer against). Production defers the entry through
                # the post-upload flush gate — the json cache is the
                # skip gate's fallback when Supabase is unreachable and
                # its sole source when authoritative mode is OFF, so it
                # must obey the same "hash advances only after ALL
                # upload legs succeed" contract as the durable store
                # (Codex P2, PR #283).
                _history_entry = {
                    'hash': data_hash,
                    'rows': len(group_rows),
                    'updated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'foreman': group_rows[0].get('__current_foreman'),
                    'week': week_raw,
                    'variant': variant,
                    'identifier': identifier,
                }
                if TEST_MODE:
                    hash_history[history_key] = _history_entry
                    history_updates += 1
                else:
                    _deferred_history_updates.append({
                        'group_key': group_key,
                        'history_key': history_key,
                        'entry': _history_entry,
                    })

                # Sub-project E: durable per-group content hash for
                # Supabase (billing_audit.group_content_hash). Gated on
                # SUPABASE_HASH_STORE_WRITE_ENABLED (default ON).
                # CRASH-CONSISTENCY (2026-07-06): the upsert is NOT
                # executed here — the record is deferred and flushed
                # after the parallel upload phase, and ONLY for groups
                # whose attachment upload succeeded. The store's contract
                # is "hash of the content currently attached in
                # Smartsheet"; writing it before the upload executes
                # breaks that contract on any mid-run crash and (in
                # authoritative clean-filename mode) permanently deadlocks
                # the skip gate for the affected group. ``week_iso`` is
                # the ISO DATE the column expects (NOT the MMDDYY
                # week_raw), kept consistent with lookup_group_hash in
                # the skip gate above; it is guarded truthy because
                # week_ending is a DATE column and an empty string would
                # be a PostgREST type error that could trip the per-op
                # circuit breaker.
                if (
                    SUPABASE_HASH_STORE_WRITE_ENABLED
                    and BILLING_AUDIT_AVAILABLE
                    and not TEST_MODE
                    and week_iso
                ):
                    _deferred_hash_upserts.append({
                        'group_key': group_key,
                        'wr_num': wr_num,
                        'week_iso': week_iso,
                        'variant': variant,
                        'identifier': identifier or '',
                        'data_hash': data_hash,
                    })

                # Phase 10 (MEM-01/MEM-03): group_state deferred record,
                # mirroring the durable-hash deferred append immediately
                # above -- SAME crash-consistency shape (write only after
                # upload succeeds), but gated INDEPENDENTLY on
                # RUN_MEMORY_WRITE_ENABLED, never on the audit package's
                # flags (10-RESEARCH.md Pitfall 5 isolation requirement --
                # a billing_audit misconfiguration must not silently
                # disable memory, and vice versa).
                if (
                    RUN_MEMORY_WRITE_ENABLED
                    and not TEST_MODE
                    and week_iso
                ):
                    _deferred_group_state.append({
                        'group_key': group_key,
                        'wr_num': wr_num,
                        'week_iso': week_iso,
                        'variant': variant,
                        'identifier': identifier or '',
                        'file_identifier': file_identifier or '',
                        'data_hash': data_hash,
                        'row_count': len(group_rows),
                    })

            except Exception as e:
                _groups_errored += 1
                logging.error(f"❌ Failed to process group {group_key}: {e}")
                sentry_capture_with_context(
                    exception=e,
                    context_name="group_processing_error",
                    context_data={
                        "group_key": group_key,
                        "group_index": group_idx,
                        "total_groups": len(groups),
                        "wr_number": wr_num if 'wr_num' in dir() else 'unknown',
                        "week_ending": week_raw if 'week_raw' in dir() else 'unknown',
                        "variant": variant if 'variant' in dir() else 'unknown',
                        "row_count": len(group_rows),
                        "error_type": type(e).__name__,
                        "error_message": _redact_exception_message(e),
                        "traceback": traceback.format_exc(),
                    },
                    tags={
                        "error_location": "group_processing",
                        "group_key": group_key[:50],  # Truncate for tag limit
                    },
                    fingerprint=["group-processing", type(e).__name__]
                )
                continue
        
        _phase_group_elapsed = (datetime.datetime.now() - _phase_group_start).total_seconds()
        logging.info(f"⚡ Group processing phase: {_groups_generated} generated, {_groups_skipped} skipped in {_phase_group_elapsed:.1f}s"
                     + (f" (stopped early — time budget exceeded)" if _time_budget_exceeded else ""))

        # Phase 01 Plan 03 Task 2 Change 3 (D-17): emit exactly ONE
        # WARNING per source sheet whose subcontractor variant
        # generation fell through to SmartSheet pricing on missing
        # CU codes. The first 10 CU codes (alphabetical) are named so
        # operators get an immediate, bounded, actionable surface
        # without log-line blowout when many CUs are missing at once.
        # Suppressed entirely when the kill switch is off — there is
        # no subcontractor variant work to surface in that case. The
        # WARNING template includes the stable marker "Subcontractor
        # rates CSV missing" so Plan 02's ``_PII_LOG_MARKERS``
        # extension drops it from Sentry before send.
        if SUBCONTRACTOR_RATE_VARIANTS_ENABLED and _missing_cus_by_sheet:
            for _sid, _sheet_missing_cus in _missing_cus_by_sheet.items():
                if not _sheet_missing_cus:
                    continue
                N = len(_sheet_missing_cus)
                first_10 = ', '.join(sorted(_sheet_missing_cus)[:10])
                ellipsis = '...' if N > 10 else ''
                logging.warning(
                    f"Subcontractor rates CSV missing {N} CU code(s) on "
                    f"sheet {_sid}: {first_10}{ellipsis}. Add to "
                    f"{SUBCONTRACTOR_RATES_CSV} to enable rate recalc for "
                    f"these rows. Sheet rows fell through to SmartSheet pricing."
                )

        # ── PARALLEL UPLOAD PHASE ─────────────────────────────────────────
        # Upload all collected tasks in parallel instead of serially per-group.
        # This is the primary runtime optimization — reduces upload time by ~Nx with N workers.
        if _upload_tasks:
            _upload_start = datetime.datetime.now()
            logging.info(f"\n{'='*60}")
            logging.info(f"📤 PARALLEL UPLOAD PHASE: {len(_upload_tasks)} files with {PARALLEL_WORKERS} workers")
            logging.info(f"{'='*60}")

            def _upload_one(task):
                """Delete old attachment + upload new one for a single group.

                Phase 01 Plan 04 Task 2: routing target is resolved
                from ``task['target_sheet_id']`` instead of the
                module-level primary sheet id. The upload-task
                builder (``_build_upload_tasks_for_group``) sets the
                sheet id per-task — ``primary`` / ``aep_billable``
                / etc. point at the primary sheet; the second leg
                of a ``reduced_sub`` fan-out points at the
                subcontractor PPP sheet. The worker is otherwise
                oblivious to which sheet it is uploading to — and
                that's the point: routing decisions live in the
                builder, mutations live in the worker.
                """
                def _do_upload_attempt():
                    target_row = task['target_row']
                    force_this = FORCE_GENERATION or (task['week_raw'] in REGEN_WEEKS)

                    # Retry idempotency note (Codex P2 thread, PR #281): this
                    # delete+upload op is wrapped in smartsheet_call_with_retry
                    # and is behavior-preserving vs the original inline loop —
                    # it passes the prefetched attachment_cache on every attempt.
                    # Making the retry STRICTLY idempotent is not achievable by
                    # attachment inspection in SUPABASE_HASH_STORE_AUTHORITATIVE
                    # clean-filename mode (ON in production:
                    # weekly-excel-generation.yml). Clean names carry no
                    # timestamp/hash (excel.py:401-407), so a freshly committed
                    # file is INDISTINGUISHABLE from a stale same-identity one —
                    # both "live-delete-then-reupload" (risks data loss if the
                    # re-upload fails) and "preserve any same-identity file"
                    # (risks reporting a stale Excel as success) are unsafe. The
                    # only residual issue with the current behavior is a benign,
                    # self-healing DUPLICATE on the rare commit-then-transient
                    # retry, which the next scheduled run's delete→upload
                    # reconciles. A proper fix (upload-then-delete-by-attachment-
                    # age) changes the delete→upload ordering guardrail and is
                    # deferred to a dedicated PR. Do NOT re-introduce a retry
                    # special-case here without that ordering change.
                    deleted_count, skipped = delete_old_excel_attachments(
                        client, task['target_sheet_id'], target_row, task['wr_num'],
                        task['week_raw'], task['data_hash'],
                        variant=task['variant'], identifier=task['file_identifier'],
                        force_generation=force_this,
                        cached_attachments=attachment_cache.get(target_row.id),
                        dry_run=SKIP_UPLOAD
                    )
                    if force_this and skipped:
                        skipped = False

                    if skipped:
                        return 'skipped'

                    if not SKIP_UPLOAD:
                        with open(task['excel_path'], 'rb') as file:
                            _attach_result = client.Attachments.attach_file_to_row(
                                task['target_sheet_id'],
                                target_row.id,
                                (task['filename'], file, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                            )
                        # Phase 10 (MEM-01/MEM-03): capture the created
                        # attachment's id/name into the side channel for
                        # group_state's post-upload flush. A read-only
                        # extraction of the SDK's OWN return value -- does
                        # NOT change the delete-then-upload order, the
                        # retry wrapper, or this function's return
                        # contract. Wrapped in its own swallow-everything
                        # try/except so a side-channel bug can never turn
                        # a successful upload into an error (T-10-10).
                        try:
                            _attach_id, _attach_name = (
                                _extract_attachment_id_name(_attach_result)
                            )
                            _mem_key = (
                                task['group_key'], task['variant'],
                                task['file_identifier'], task['target_sheet_id'],
                            )
                            with _mem_attachment_side_channel_lock:
                                _mem_attachment_side_channel[_mem_key] = {
                                    'attachment_id': _attach_id,
                                    'attachment_name': _attach_name,
                                }
                        except Exception:
                            pass
                        logging.info(
                            f"✅ Uploaded: {task['filename']} → sheet "
                            f"{task['target_sheet_id']}"
                        )
                        return 'uploaded'
                    else:
                        logging.info(f"⏭️  Skipping upload (SKIP_UPLOAD=true): {task['filename']}")
                        return 'skip_upload'

                # Phase 10: retry the whole delete+upload op via the shared
                # helper (transient API 4000 / server timeout / rate limit /
                # network drop, bounded backoff). On persistent failure, fail
                # loud — error log + Sentry breadcrumb — and report 'error',
                # exactly as the previous inline retry loop did.
                try:
                    return smartsheet_call_with_retry(
                        _do_upload_attempt,
                        label=f"upload {task['filename']}",
                    )
                except Exception as e:
                    logging.error(f"❌ Upload failed for {task['filename']}: {e}")
                    sentry_add_breadcrumb("upload", f"Upload failed for {task['filename']}", level="error", data={
                        "wr": task['wr_num'], "error": str(e)[:200],
                    })
                    return 'error'

            with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
                upload_results = list(executor.map(_upload_one, _upload_tasks))

            _groups_uploaded = sum(1 for r in upload_results if r == 'uploaded')
            _upload_errors = sum(1 for r in upload_results if r == 'error')
            _groups_errored += _upload_errors
            _api_calls_count = _groups_uploaded

            _upload_elapsed = (datetime.datetime.now() - _upload_start).total_seconds()
            logging.info(f"⚡ Upload phase complete: {_groups_uploaded} uploaded, {_upload_errors} errors in {_upload_elapsed:.1f}s (parallel w/{PARALLEL_WORKERS} workers)")

            # Sub-project E crash-consistency flush (2026-07-06): persist
            # the durable group hash ONLY for groups whose attachment
            # upload actually completed in THIS run. Outcome semantics:
            #   'uploaded'    -> attachment replaced, hash is now true
            #   'skipped'     -> delete helper verified the existing
            #                    attachment already matches this hash
            #   'skip_upload' -> SKIP_UPLOAD dry-run: nothing published,
            #                    hash MUST NOT advance (a dry run with
            #                    prod Supabase creds would otherwise
            #                    poison change detection exactly like a
            #                    mid-run crash)
            #   'error'       -> upload failed: withhold the hash so the
            #                    next run regenerates and re-uploads
            # A reduced_sub fan-out group produces TWO tasks; the hash
            # advances only when EVERY leg succeeded. Withholding on
            # failure fails safe: worst case is one extra regenerate +
            # delete-then-upload next run, never a stale file reported
            # as current. upsert_group_hash is fail-safe/no-op when
            # Supabase is unavailable and never raises past the guard.
            if _deferred_history_updates or (
                SUPABASE_HASH_STORE_WRITE_ENABLED
                and _deferred_hash_upserts
            ) or (
                RUN_MEMORY_WRITE_ENABLED
                and _deferred_group_state
            ):
                _group_upload_ok: dict = {}
                _group_had_error: dict = {}
                for _task, _res in zip(_upload_tasks, upload_results):
                    _gk = _task.get('group_key')
                    _ok = _res in ('uploaded', 'skipped')
                    _group_upload_ok[_gk] = (
                        _group_upload_ok.get(_gk, True) and _ok
                    )
                    if _res == 'error':
                        _group_had_error[_gk] = True
                # Codex P2 (PR #283, repair-path): withholding the NEW
                # hash is not enough when a forced/regen run was
                # repairing a group whose STORED hash already equals
                # the computed one (exactly the incident-remediation
                # scenario) — if the re-upload then fails, the stale
                # stored hash would let the next non-forced run skip
                # the group and the repair would never retry. For
                # groups withheld due to a REAL upload 'error' we
                # therefore actively invalidate both layers: pop the
                # json entry, and overwrite the durable row with a
                # 'withheld:'-prefixed sentinel that can never equal a
                # computed SHA256 (lookup mismatches -> regenerate;
                # the next successful upload overwrites it).
                # 'skip_upload' (SKIP_UPLOAD dry-run) does NOT
                # invalidate — a local dry run must never mutate prod
                # change-detection state in either direction.
                # Local json cache first (Codex P2, PR #283): it is the
                # fallback layer the skip gate consults on Supabase
                # outage and the sole decider with authoritative OFF,
                # so it must never advance for a withheld group. Note
                # this flush is NOT gated on the Supabase write flag —
                # the json contract holds in every mode.
                _json_withheld = 0
                for _rec in _deferred_history_updates:
                    if not _group_upload_ok.get(_rec['group_key']):
                        _json_withheld += 1
                        if _group_had_error.get(_rec['group_key']):
                            if hash_history.pop(
                                _rec['history_key'], None,
                            ) is not None:
                                history_updates += 1
                        continue
                    hash_history[_rec['history_key']] = _rec['entry']
                    history_updates += 1
                if _json_withheld:
                    logging.warning(
                        f"⚠️ Local hash-history entry withheld for "
                        f"{_json_withheld} group(s) whose upload did "
                        f"not complete — they will regenerate next run"
                    )
                if (
                    SUPABASE_HASH_STORE_WRITE_ENABLED
                    and _deferred_hash_upserts
                ):
                    _hashes_flushed = 0
                    _hashes_withheld = 0
                    for _rec in _deferred_hash_upserts:
                        if not _group_upload_ok.get(_rec['group_key']):
                            _hashes_withheld += 1
                            if _group_had_error.get(_rec['group_key']):
                                try:
                                    _billing_audit_writer.upsert_group_hash(
                                        _rec['wr_num'], _rec['week_iso'],
                                        _rec['variant'],
                                        _rec['identifier'],
                                        'withheld:' + _rec['data_hash'],
                                    )
                                except Exception:
                                    logging.exception(
                                        "E hash invalidation failed "
                                        "(non-fatal)")
                            continue
                        try:
                            _billing_audit_writer.upsert_group_hash(
                                _rec['wr_num'], _rec['week_iso'],
                                _rec['variant'], _rec['identifier'],
                                _rec['data_hash'],
                            )
                            _hashes_flushed += 1
                        except Exception:
                            logging.exception(
                                "E hash write failed (non-fatal)")
                    if _hashes_withheld:
                        logging.warning(
                            f"⚠️ Durable hash withheld for {_hashes_withheld} "
                            f"group(s) whose upload did not complete — they "
                            f"will regenerate next run"
                        )
                    logging.info(
                        f"🧾 Durable hash store: {_hashes_flushed} flushed, "
                        f"{_hashes_withheld} withheld"
                    )

                # Phase 10 (MEM-01/MEM-03): group_state flush -- THIRD and
                # LAST, placed after both existing flushes so it can never
                # affect either. Gated independently on
                # RUN_MEMORY_WRITE_ENABLED only (never on
                # SUPABASE_HASH_STORE_WRITE_ENABLED / BILLING_AUDIT_AVAILABLE
                # -- the isolation requirement from 10-RESEARCH.md
                # Pitfall 5). Reuses _group_upload_ok built above -- never
                # re-derives it.
                if RUN_MEMORY_WRITE_ENABLED and _deferred_group_state:
                    # Outer try/except (belt-and-suspenders, mirrors the
                    # sheet_registry / run_ledger hooks elsewhere in
                    # main()): _build_group_state_flush is a pure function
                    # proven not to raise given this call site's own
                    # consistent _deferred_group_state dict shape, but an
                    # unexpected future change here must still be unable
                    # to prevent the two EARLIER, production-critical
                    # flushes above from having already completed (T-10-11
                    # -- they execute strictly before this block in source
                    # order, so they are unaffected either way).
                    try:
                        _mem_group_records, _mem_group_withheld = (
                            _build_group_state_flush(
                                _deferred_group_state, _group_upload_ok,
                                _upload_tasks, _mem_attachment_side_channel,
                            )
                        )
                        if _mem_group_withheld:
                            _mem_writer.bump_group_state_withheld(
                                _mem_group_withheld
                            )
                        try:
                            _mem_writer.upsert_group_state(
                                _mem_group_records, _mem_run_id,
                            )
                        except Exception:
                            logging.warning(
                                "⚠️ pipeline_memory group_state flush "
                                "failed unexpectedly (non-fatal); "
                                "group_state not written this run."
                            )
                        logging.info(
                            f"🧾 group_state: {len(_mem_group_records)} "
                            f"flushed, {_mem_group_withheld} withheld"
                        )
                    except Exception:
                        logging.warning(
                            "⚠️ pipeline_memory group_state flush "
                            "computation failed unexpectedly (non-fatal); "
                            "group_state not written this run."
                        )

        # Validation summary
        summaries = validate_group_totals(groups)
        if summaries:
            logging.info("🧮 Totals Validation (first 10 groups):")
            for s in summaries[:10]:
                logging.info(f"   {s['group_key']}: rows={s['rows']} total=${s['total']}")

        # Session summary
        session_duration = datetime.datetime.now() - session_start
        logging.info(f"✅ Session complete!")
        logging.info(f"   • Files generated: {generated_files_count}")
        logging.info(f"   • Duration: {session_duration}")
        logging.info(f"   • Mode: {'TEST' if TEST_MODE else 'PRODUCTION'}")

        # Build identity set for sheet pruning: (wr, week, variant, identifier) 4-tuples
        valid_wr_weeks = set()
        for fname in generated_filenames:
            ident = build_group_identity(fname)
            if ident:
                valid_wr_weeks.add(ident)  # Already returns 4-tuple
        # Also include any WR/week/variant/identifier combos we skipped due to identical hash (so we don't delete their existing attachment)
        # Already implicit because skipped groups did not regenerate; we can add from groups processed via grouping keys
        for key, group_rows in groups.items():
            if '_' in key:
                week_raw = key.split('_',1)[0]
                wr_raw = group_rows[0].get('Work Request #')
                wr = str(wr_raw).split('.')[0] if wr_raw else ''
                # Apply the same sanitizer used at every other site
                # (generate_excel, main-loop derivation, hash-prune
                # loop, create_target_sheet_map). Without this,
                # ``build_group_identity`` (which returns sanitized
                # WR tokens for filenames with rewritten WR#s) would
                # produce identity tuples that don't match the
                # unsanitized entries this loop adds to
                # valid_wr_weeks — causing
                # cleanup_untracked_sheet_attachments to incorrectly
                # prune attachments for sanitization-sensitive WRs
                # when KEEP_HISTORICAL_WEEKS is enabled.
                wr = _RE_SANITIZE_HELPER_NAME.sub('_', wr)[:50]
                variant = group_rows[0].get('__variant', 'primary')
                if variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):
                    # CR-01 gap closure (Site 2 — mirror of Site 1).
                    # build_group_identity returns the sanitized helper
                    # foreman as the parsed identifier for all three
                    # helper-style variants; valid_wr_weeks must match
                    # that tuple shape so
                    # cleanup_untracked_sheet_attachments correctly
                    # identifies which helper-shadow attachments are
                    # "live" and which are stale. Pre-fix, shadow
                    # variants fell through to the ``User``-derived
                    # ``else`` branch and produced file_id='' tuples
                    # that NEVER matched the parser's 'Jane_Smith'
                    # identifier — risking cleanup either pruning
                    # legitimate attachments or missing orphans.
                    # Sites 1 and 3 carry the same gate.
                    helper_foreman = group_rows[0].get('__helper_foreman', '')
                    file_id = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50] if helper_foreman else ''
                elif variant == 'vac_crew':
                    # Subproject C identity site (Site 2 — valid_wr_weeks).
                    # GATED on the kill switch (mirrors Site 1): disabled mode
                    # produces file_id='' so the 4-tuple matches the bare
                    # _VacCrew attachment identity and cleanup does not delete
                    # live legacy-mode attachments.
                    _vc = group_rows[0].get('__current_foreman', '')
                    file_id = (
                        _RE_SANITIZE_IDENTIFIER.sub('_', _vc)[:50]
                        if (VAC_CREW_CLAIM_ATTRIBUTION_ENABLED and _vc) else ''
                    )
                elif variant in ('reduced_sub', 'aep_billable'):
                    # Subproject B identity site (Site 2 — valid_wr_weeks).
                    # Mirror Site 1 so attachment cleanup keeps the live
                    # per-claimer file.
                    _b_claimer = group_rows[0].get('__current_foreman', '')
                    file_id = (
                        _RE_SANITIZE_IDENTIFIER.sub('_', _b_claimer)[:50]
                        if _b_claimer else ''
                    )
                else:
                    # Subproject D (2026-05-25): primary identity site
                    # (Site 2 — valid_wr_weeks). Mirror Site 1 so attachment
                    # cleanup keeps the live per-claimer primary file.
                    # Disabled mode preserves the legacy ``User``-field path.
                    if (
                        PRIMARY_CLAIM_ATTRIBUTION_ENABLED
                        and RES_GROUPING_MODE in ('helper', 'both')
                    ):
                        _pf = group_rows[0].get('__current_foreman', '')
                        file_id = (
                            _RE_SANITIZE_IDENTIFIER.sub('_', _pf)[:50]
                            if (PRIMARY_CLAIM_ATTRIBUTION_ENABLED and _pf) else ''
                        )
                    else:
                        user_val = group_rows[0].get('User')
                        # PERFORMANCE: Use pre-compiled regex
                        file_id = _RE_SANITIZE_IDENTIFIER.sub('_', user_val)[:50] if user_val else ''
                valid_wr_weeks.add((wr, week_raw, variant, file_id))
        if not TEST_MODE:
            # Invalidate stale attachment cache after upload phase — uploads added/deleted attachments
            _cleanup_cache = attachment_cache if not _upload_tasks else None
            # Phase 1.1 Bug B2 (D-09): TARGET_SHEET_ID cleanup is UNCHANGED —
            # accepts every variant currently routed to it (primary, helper,
            # vac_crew, aep_billable, reduced_sub, aep_billable_helper,
            # reduced_sub_helper). The whitelist is per-sheet; passing
            # variant_whitelist=None (default — kwarg omitted below)
            # preserves byte-identical legacy behaviour on TARGET.
            #
            # Phase 1.1 UAT gap closure (SUB-09 helper dimension): build the
            # subcontractor WR scope from this run's groups (shared helper)
            # and pass it to the TARGET cleanup to delete pre-existing legacy
            # _Helper_<name> and bare-primary attachments. Kill-switch-gated:
            # SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED=0 reverts to
            # byte-identical pre-fix TARGET behaviour (sub orphans persist).
            # Subproject B: build the subcontractor WR scope when EITHER
            # the legacy-helper cleanup (SUB-09) OR the legacy-primary
            # cleanup (Subproject B) is enabled — the two share the scope.
            _need_sub_scope = (
                SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED
                or SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED
            )
            _sub_scope = (
                _build_subcontractor_wr_scope(groups)
                if _need_sub_scope
                else None
            )
            _target_offcontract = set()
            if _sub_scope and SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED:
                _target_offcontract |= {'helper', 'primary'}
            _target_legacy_primary = (
                {'reduced_sub', 'aep_billable'}
                if _sub_scope and SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED
                else None
            )
            # Subproject C Task 6 (2026-05-21): build the vac_crew WR scope
            # for legacy bare _VacCrew cleanup on TARGET. vac_crew files route
            # to TARGET_SHEET_ID only (never PPP) — do NOT pass this to PPP.
            # Kill-switch-gated: VAC_CREW_LEGACY_CLEANUP_ENABLED=0 reverts to
            # byte-identical pre-fix TARGET behaviour (vac orphans persist).
            _vac_scope = (
                _build_vac_crew_wr_scope(groups)
                if VAC_CREW_LEGACY_CLEANUP_ENABLED
                else None
            )
            # Subproject D (2026-05-25): build the non-subcontractor
            # primary WR scope for legacy bare-primary cleanup on TARGET.
            # Gated on BOTH the attribution kill switch (the partitioned
            # _USER_ groups only exist when attribution is on) AND the
            # cleanup kill switch. primary files route to TARGET only —
            # do NOT pass this to PPP.
            _primary_scope = (
                _build_primary_wr_scope(groups)
                if (
                    PRIMARY_CLAIM_ATTRIBUTION_ENABLED
                    and LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED
                )
                else None
            )
            with sentry_sdk.start_span(op="smartsheet.cleanup", name="Cleanup untracked sheet attachments"):
                cleanup_untracked_sheet_attachments(
                    client, TARGET_SHEET_ID, valid_wr_weeks, TEST_MODE,
                    attachment_cache=_cleanup_cache, target_sheet=_target_sheet_obj,
                    sub_wr_scope=_sub_scope,
                    # Empty set means the SUB-09 helper cleanup is off; coerce
                    # to None so the off-contract gate no-ops (the gate keys on
                    # `is not None`, not truthiness).
                    sub_offcontract_variants=(_target_offcontract or None),
                    sub_legacy_primary_variants=_target_legacy_primary,
                    vac_legacy_wr_scope=_vac_scope,
                    primary_wr_scope=_primary_scope,
                    dry_run=SKIP_UPLOAD,
                )

            # Phase 01 gap closure (REVIEW-WR-01): parallel cleanup pass
            # for SUBCONTRACTOR_PPP_SHEET_ID. The TARGET_SHEET_ID
            # cleanup above iterates one sheet only; without an
            # equivalent pass on PPP, any helper-shadow attachment
            # (``_AEPBillable_Helper_*`` / ``_ReducedSub_Helper_*``)
            # whose per-row ``delete_old_excel_attachments`` call
            # missed (CR-01 pre-fix bug, timestamp-identity drift,
            # future refactor) orphans permanently on PPP. This
            # invocation is the belt-and-suspenders defense: it
            # iterates PPP rows, groups attachments by parsed identity
            # tuple, and prunes everything-but-newest per identity.
            #
            # ``valid_wr_weeks`` is the SHARED authority — Plan 08
            # (CR-01) ensured shadow-variant entries are correctly
            # included so live attachments are not pruned.
            #
            # Cache semantics: ``_cleanup_cache`` is computed ABOVE
            # both invocations as ``attachment_cache if not _upload_tasks
            # else None``. In the normal production case (uploads ran
            # this session, ``_upload_tasks`` truthy), ``_cleanup_cache``
            # is ``None`` for BOTH passes because uploads invalidate
            # the prefetch snapshot. When no uploads ran (TEST_MODE
            # skip path, or no-changes branch), both passes share
            # WR-05's prefetched dict transparently. WR-05's prefetch
            # primarily amortizes per-row ``_upload_one`` API calls
            # (its real value); the cleanup-time benefit is only on
            # the no-uploads path. Either way, passing the same
            # ``_cleanup_cache`` keeps cache semantics consistent
            # across both passes.
            #
            # Gates (in order, short-circuit on first False):
            #   1. SUBCONTRACTOR_RATE_VARIANTS_ENABLED (kill switch)
            #   2. SUBCONTRACTOR_PPP_SHEET_ID is truthy (disable case)
            #   3. SUBCONTRACTOR_PPP_SHEET_ID != TARGET_SHEET_ID
            #      (skip redundant pass if operator points both to
            #       the same sheet — unusual but supported)
            #   4. _target_sheet_ppp_obj is not None (Plan 04 only
            #      populates this when target_map_ppp was successfully
            #      built; None means PPP routing was unreachable this
            #      run and we should not iterate the sheet)
            if (
                SUBCONTRACTOR_RATE_VARIANTS_ENABLED
                and SUBCONTRACTOR_PPP_SHEET_ID
                and SUBCONTRACTOR_PPP_SHEET_ID != TARGET_SHEET_ID
                and _target_sheet_ppp_obj is not None
            ):
                with sentry_sdk.start_span(op="smartsheet.cleanup_ppp", name="Cleanup untracked PPP sheet attachments"):
                    # Phase 1.1 Bug B2 (D-07 / D-08 / SUB-10):
                    # per-sheet variant whitelist. PPP receives only
                    # `_ReducedSub` / `_ReducedSub_Helper_*` from
                    # Phase 1's routing matrix (per
                    # _build_upload_tasks_for_group). Any other
                    # variant parsed from a filename on PPP is
                    # off-contract and unconditionally pruned —
                    # defense in depth against Bug B1 regressions
                    # AND against future routing-matrix drift.
                    # Hardcoded at the call site per D-08 (no env
                    # var, no config). If a future plan adds a new
                    # variant to PPP routing (e.g., aep_billable),
                    # this literal whitelist MUST be updated in the
                    # SAME PR — coupling is documented in the
                    # 01.1-03 SUMMARY.
                    cleanup_untracked_sheet_attachments(
                        client,
                        SUBCONTRACTOR_PPP_SHEET_ID,
                        valid_wr_weeks,
                        TEST_MODE,
                        attachment_cache=_cleanup_cache,
                        target_sheet=_target_sheet_ppp_obj,
                        variant_whitelist={'reduced_sub', 'reduced_sub_helper'},
                        sub_wr_scope=_sub_scope,
                        sub_legacy_primary_variants=(
                            {'reduced_sub'}
                            if _sub_scope and SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED
                            else None
                        ),
                        dry_run=SKIP_UPLOAD,
                    )

        # Cleanup legacy / stale Excel files so only current system outputs remain
        try:
            with sentry_sdk.start_span(op="file.cleanup", name="Cleanup stale local Excel files"):
                removed = cleanup_stale_excels(OUTPUT_FOLDER, set(generated_filenames))
            logging.info(f"🧹 Cleanup complete: removed {len(removed)} stale file(s)")
        except Exception as e:
            logging.warning(f"⚠️ Cleanup step failed: {e}")
        
        # Audit summary
        if audit_results:
            audit_summary = audit_results.get('summary', {})
            logging.info(f"🔍 Audit Summary:")
            logging.info(f"   • Risk Level: {audit_summary.get('risk_level', 'UNKNOWN')}")
            logging.info(f"   • Anomalies: {audit_summary.get('total_anomalies', 0)}")
            logging.info(f"   • Data Issues: {audit_summary.get('total_data_issues', 0)}")
        
        # Persist hash history if updated
        if history_updates:
            # Prune stale hash_history entries for groups no longer in source data.
            # Only prune on FULL runs (not time-budget-truncated runs) to avoid
            # deleting entries for groups that simply weren't reached this run.
            if not _time_budget_exceeded:
                current_keys = set()
                for key, group_rows in groups.items():
                    if '_' in key:
                        _wr_raw = group_rows[0].get('Work Request #')
                        _wr = str(_wr_raw).split('.')[0] if _wr_raw else ''
                        # Codex P2: apply the same filesystem-safety
                        # sanitizer used by the main loop (line ~4493)
                        # so the current_keys tuple matches the
                        # history_key actually written for this group.
                        # Without this, any WR# containing
                        # sanitization-sensitive characters would have
                        # its freshly-written entry treated as stale
                        # and deleted before save, so hash-skip could
                        # never persist across runs for those WRs.
                        _wr = _RE_SANITIZE_HELPER_NAME.sub('_', _wr)[:50]
                        _week = key.split('_',1)[0]
                        _variant = group_rows[0].get('__variant', 'primary')
                        if _variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):
                            # CR-01 gap closure (Site 3 — mirror of Site 1).
                            # Site 1 writes the helper-shadow history_key as
                            # f"{wr}|{week}|{variant}|{foreman}|{dept}|{job}" —
                            # this prune-key reconstruction MUST match it
                            # byte-for-byte or the entry written this run is
                            # treated as stale and deleted before
                            # save_hash_history runs. Pre-fix, both Sites 1
                            # and 3 fell through to the same ``User``-derived
                            # branch, so the two stayed aligned by accident
                            # (both produced '' identifiers). With Site 1 now
                            # correctly deriving from __helper_foreman, Site 3
                            # must follow or the alignment breaks the OTHER
                            # way and we permanently lose hash-skip for
                            # helper-shadow variants. Note: ``_ident`` here is
                            # the HISTORY-KEY shape (pipe-joined triple), NOT
                            # the FILE-IDENTIFIER shape (Site 1 builds both;
                            # this site reconstructs the history-key shape
                            # only — the same pattern as the legacy helper
                            # branch).
                            _hf = group_rows[0].get('__helper_foreman', '')
                            _hd = group_rows[0].get('__helper_dept', '')
                            _hj = group_rows[0].get('__helper_job', '')
                            _ident = f"{_hf}|{_hd}|{_hj}"
                        elif _variant == 'vac_crew':
                            # Subproject C identity site (Site 3 —
                            # current_keys). GATED on the kill switch (mirrors
                            # Site 1): disabled mode produces _ident='' so the
                            # reconstructed current_keys entry matches the
                            # bare history_key written by Site 1 and the fresh
                            # entry is not treated as stale and deleted.
                            _vc = group_rows[0].get('__current_foreman', '')
                            _ident = (
                                _RE_SANITIZE_IDENTIFIER.sub('_', _vc)[:50]
                                if (VAC_CREW_CLAIM_ATTRIBUTION_ENABLED and _vc) else ''
                            )
                        elif _variant in ('reduced_sub', 'aep_billable'):
                            # Subproject B identity site (Site 3 —
                            # current_keys). Must match the history_key
                            # written at Site 1 byte-for-byte (sanitized
                            # claimer) or the freshly-written entry is
                            # treated as stale and deleted before save.
                            _b_claimer = group_rows[0].get('__current_foreman', '')
                            _ident = (
                                _RE_SANITIZE_IDENTIFIER.sub('_', _b_claimer)[:50]
                                if _b_claimer else ''
                            )
                        else:
                            # Subproject D (2026-05-25): primary identity
                            # site (Site 3 — current_keys). Must match the
                            # history_key written at Site 1 byte-for-byte
                            # (sanitized claimer when on, legacy User-field
                            # when off) or the freshly-written entry is
                            # treated as stale and deleted before save.
                            if (
                                PRIMARY_CLAIM_ATTRIBUTION_ENABLED
                                and RES_GROUPING_MODE in ('helper', 'both')
                            ):
                                _pf = group_rows[0].get('__current_foreman', '')
                                _ident = (
                                    _RE_SANITIZE_IDENTIFIER.sub('_', _pf)[:50]
                                    if (PRIMARY_CLAIM_ATTRIBUTION_ENABLED and _pf) else ''
                                )
                            else:
                                _uv = group_rows[0].get('User')
                                _ident = _RE_SANITIZE_IDENTIFIER.sub('_', _uv)[:50] if _uv else ''
                        current_keys.add(f"{_wr}|{_week}|{_variant}|{_ident}")
                stale_keys = [k for k in hash_history if k not in current_keys]
                if stale_keys:
                    for sk in stale_keys:
                        del hash_history[sk]
                    logging.info(f"🧹 Pruned {len(stale_keys)} stale hash history entries (groups no longer in source data)")
            save_hash_history(HASH_HISTORY_PATH, hash_history)
        elif _hash_history_migration_dirty:
            # Codex P2: no group updates this run, but a one-time migration
            # prune (Phase 1.1 / Subproject B / Subproject C) mutated hash_history. Persist
            # it now so the migration is durable and does not re-run every
            # execution. Do NOT run the stale-prune on this path — groups
            # were not fully processed, so current_keys would be incomplete
            # and could delete freshly-skipped live entries.
            save_hash_history(HASH_HISTORY_PATH, hash_history)
        if (
            BILLING_AUDIT_AVAILABLE
            and not TEST_MODE
            and billing_audit_row_cache_dirty
        ):
            save_billing_audit_row_cache(
                BILLING_AUDIT_ROW_CACHE_PATH,
                billing_audit_row_cache,
            )

        # Phase 10 (MEM-01/MEM-03): run_ledger 'finish' row. Same guard
        # shape as the start hook. Reuses already-computed counters --
        # recomputes nothing. Memory counters live in run_ledger.notes,
        # NOT in the frozen 21-key run_summary.json below (interfaces
        # block: adding a key there means editing 3 places plus the
        # golden baseline, and pollutes the plan-10-05 control-run diff).
        if RUN_MEMORY_WRITE_ENABLED and not TEST_MODE:
            try:
                _mem_writer.run_ledger_finish(
                    _mem_run_id,
                    status="success",
                    sheets_checked=len(source_sheets) if 'source_sheets' in dir() else 0,
                    rows_seen=len(all_rows) if 'all_rows' in dir() else 0,
                    rows_changed=_mem_rows_changed,
                    groups_generated=_groups_generated,
                    groups_affected=len(_mem_affected),
                    # WR-04 (CONTEXT.md D-10): sheets_changed is a real
                    # run_ledger column (_RUN_LEDGER_FINISH_COLUMNS in
                    # pipeline_memory/writer.py); mem_sheets_written below
                    # is a separate notes-JSON counter Phase 10 dashboards
                    # already read -- the two are not duplicates.
                    sheets_changed=_mem_sheets_written,
                    mem_sheets_written=_mem_sheets_written,
                    mem_sheets_errored=_mem_sheets_errored,
                    mem_rows_sent=_mem_rows_sent,
                )
            except Exception:
                logging.warning(
                    "⚠️ pipeline_memory run_ledger_finish failed "
                    "(non-fatal); memory not written this run."
                )

        # Write run summary JSON for downstream consumers (Notion sync, dashboards)
        _run_summary = {
            "success": True,
            "files_generated": generated_files_count,
            "groups_total": len(groups),
            "groups_skipped": _groups_skipped,
            "groups_generated": _groups_generated,
            "groups_uploaded": _groups_uploaded,
            "groups_errored": _groups_errored,
            "duration_seconds": session_duration.total_seconds(),
            "duration_minutes": round(session_duration.total_seconds() / 60.0, 2),
            "history_updates": history_updates,
            "sheets_discovered": len(source_sheets) if 'source_sheets' in dir() else 0,
            "rows_fetched": len(all_rows) if 'all_rows' in dir() else 0,
            "api_calls": _api_calls_count,
            "audit_risk_level": audit_results.get('summary', {}).get('risk_level', 'UNKNOWN') if audit_results else 'UNKNOWN',
            "mode": "TEST" if TEST_MODE else "PRODUCTION",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "snapshots_written": 0,
            "snapshots_already_frozen": 0,
            "snapshots_errored": 0,
            "fingerprint_changes_detected": 0,
        }
        if BILLING_AUDIT_AVAILABLE:
            try:
                _run_summary.update(_billing_audit_writer.get_counters())
            except Exception:
                pass  # Counter retrieval must never fail the run summary write.
            # Subproject B / Subproject C: emit ONE aggregate WARNING if any
            # rows were held this run pending attribution (Supabase outage).
            # B is the first consumer of Foundation A's HOLD machinery; C
            # (vac_crew) also records holds via the same counter. This is
            # the single end-of-run summary call. PII-safe (counts +
            # sanitized WR list only). Never fail the run summary write.
            try:
                _billing_audit_writer.summarize_attribution_holds()
            except Exception:
                pass
        try:
            with open(os.path.join(OUTPUT_FOLDER, 'run_summary.json'), 'w') as _rsf:
                json.dump(_run_summary, _rsf, indent=2)
        except Exception as _rse:
            logging.warning(f"⚠️ Could not write run_summary.json: {_rse}")

        # SDK 2.x: Use get_isolation_scope() instead of configure_scope()
        if SENTRY_DSN:
            scope = sentry_sdk.get_isolation_scope()
            scope.set_tag("session_success", "true")
            scope.set_tag("files_generated", str(generated_files_count))
            scope.set_tag("groups_skipped", str(_groups_skipped))
            scope.set_tag("groups_generated", str(_groups_generated))
            scope.set_tag("groups_uploaded", str(_groups_uploaded))
            scope.set_tag("groups_errored", str(_groups_errored))
            scope.set_tag("session_duration_seconds", str(session_duration.total_seconds()))
            if audit_results:
                scope.set_tag("audit_risk_level", audit_results.get('summary', {}).get('risk_level', 'UNKNOWN'))
            
            # Set final session context for dashboard visibility
            sentry_sdk.set_context("session_summary", {
                "success": True,
                "files_generated": generated_files_count,
                "groups_total": len(groups),
                "groups_skipped": _groups_skipped,
                "groups_generated": _groups_generated,
                "groups_uploaded": _groups_uploaded,
                "groups_errored": _groups_errored,
                "duration_seconds": session_duration.total_seconds(),
                "duration_human": str(session_duration),
                "history_updates": history_updates,
                "mode": "TEST" if TEST_MODE else "PRODUCTION",
                "audit_risk_level": audit_results.get('summary', {}).get('risk_level', 'UNKNOWN') if audit_results else None,
            })
            sentry_sdk.set_context("data_pipeline", {
                "source_sheets": len(source_sheets) if 'source_sheets' in dir() else 0,
                "total_rows_fetched": len(all_rows) if 'all_rows' in dir() else 0,
                "groups_created": len(groups),
                "hash_history_entries": len(hash_history) if 'hash_history' in dir() else 0,
                "api_calls_upload": _api_calls_count,
            })
            sentry_add_breadcrumb("session", "Session completed successfully", level="info", data={
                "files_generated": generated_files_count,
                "duration": str(session_duration),
                "skipped": _groups_skipped,
                "errored": _groups_errored,
            })
            
            # #6 - SUCCESS-path root-transaction KPIs (counts only, no PII)
            if _txn:
                for _k, _v in _build_run_kpis(
                    files_generated=generated_files_count,
                    groups_total=len(groups),
                    groups_skipped=_groups_skipped,
                    groups_generated=_groups_generated,
                    groups_uploaded=_groups_uploaded,
                    groups_errored=_groups_errored,
                    duration_seconds=session_duration.total_seconds(),
                    sheets_discovered=len(source_sheets) if 'source_sheets' in dir() else 0,
                    rows_fetched=len(all_rows) if 'all_rows' in dir() else 0,
                    api_calls=_api_calls_count,
                ).items():
                    _txn.set_data(_k, _v)

            # #7 - milestone structured log: run complete (counts only, no PII)
            _sentry_log_event(
                "info",
                "weekly run complete",
                files_generated=generated_files_count,
                groups_generated=_groups_generated,
                groups_uploaded=_groups_uploaded,
                groups_errored=_groups_errored,
                duration_seconds=session_duration.total_seconds(),
            )

            # Finish the root transaction
            if _txn:
                _txn.set_status("ok")
                _txn.__exit__(None, None, None)
                _txn = None

    except FileNotFoundError as e:
        _session_failed = True
        error_context = f"Missing required file: {e}"
        logging.error(f"💥 {error_context}")
        sentry_capture_with_context(
            exception=e,
            context_name="file_not_found",
            context_data={
                "missing_file": str(e),
                "working_directory": os.getcwd(),
                "error_type": "FileNotFoundError",
            },
            tags={"error_location": "main", "error_type": "file_not_found"},
            fingerprint=["file-not-found", str(e)]
        )
        # Close transaction with error
        if _txn:
            _txn.set_status("internal_error")
            _txn.__exit__(type(e), e, e.__traceback__)
            _txn = None
            
    except Exception as e:
        _session_failed = True
        session_duration = datetime.datetime.now() - session_start
        error_context = f"Session failed after {session_duration}"
        logging.error(f"💥 {error_context}: {e}")
        
        # SDK 2.x: Use get_isolation_scope() instead of configure_scope()
        if SENTRY_DSN:
            scope = sentry_sdk.get_isolation_scope()
            scope.set_tag("session_success", "false")
            scope.set_tag("session_duration_seconds", str(session_duration.total_seconds()))
            scope.set_tag("failure_type", "general_exception")
            scope.set_tag("groups_errored", str(_groups_errored))
            scope.set_level("error")

            # #5 - FAILURE-path PII-safe attachment (counts/booleans only)
            # add_attachment bypasses before_send_log — this try/except guard
            # ensures a telemetry failure can NEVER mask the real exception.
            try:
                _snap = _build_run_context_snapshot(
                    success=False,
                    duration_seconds=session_duration.total_seconds(),
                    groups_attempted=len(groups) if 'groups' in dir() else 0,
                    groups_generated=_groups_generated,
                    groups_uploaded=_groups_uploaded if '_groups_uploaded' in dir() else 0,
                    groups_errored=_groups_errored,
                    error_type=type(e).__name__,
                )
                scope.add_attachment(
                    bytes=json.dumps(_snap, indent=2).encode("utf-8"),
                    filename="run-context.json",
                    content_type="application/json",
                )
            except Exception:
                pass  # telemetry must never mask the real failure

            sentry_capture_with_context(
                exception=e,
                context_name="session_failure",
                context_data={
                    "duration_seconds": session_duration.total_seconds(),
                    "duration_human": str(session_duration),
                    "error_type": type(e).__name__,
                    "error_message": _redact_exception_message(e),
                    "traceback": traceback.format_exc(),
                    "test_mode": TEST_MODE,
                    "groups_attempted": len(groups) if 'groups' in dir() else 'unknown',
                    "groups_generated": _groups_generated,
                    "groups_errored": _groups_errored,
                },
                tags={"error_location": "main", "session_phase": "execution"},
                fingerprint=["session-failure", type(e).__name__]
            )
        # Close transaction with error
        if _txn:
            _txn.set_status("internal_error")
            _txn.__exit__(type(e), e, e.__traceback__)
            _txn = None
    
    finally:
        # Phase 10 (MEM-01/MEM-03) failure-path finalization (10-REVIEW.md
        # WR-03 / PR #350 review): the success-path run_ledger_finish above
        # is never reached when an exception lands in the except handlers,
        # which left that run's row at status='running' / finished_at=NULL
        # forever -- indistinguishable from a run still in progress.
        # Same flag + TEST_MODE guards as the start/finish hooks, wrapped so
        # a Supabase outage here can never mask the real session failure or
        # the cron check-in below. _session_failed / _mem_run_id / the
        # counters are all hoisted above the try, so no dir() guard.
        if _session_failed and RUN_MEMORY_WRITE_ENABLED and not TEST_MODE:
            try:
                _mem_writer.run_ledger_finish(
                    _mem_run_id,
                    status="failed",
                    groups_generated=_groups_generated,
                    groups_affected=len(_mem_affected),
                    groups_errored=_groups_errored,
                    # WR-04 (CONTEXT.md D-10): sheets_changed is a real
                    # run_ledger column; mem_sheets_written below is a
                    # separate notes-JSON counter -- see the success-path
                    # call site above for the full rationale.
                    sheets_changed=_mem_sheets_written,
                    mem_sheets_written=_mem_sheets_written,
                    mem_sheets_errored=_mem_sheets_errored,
                    mem_rows_sent=_mem_rows_sent,
                )
            except Exception as _mem_exc:
                logging.warning(
                    "⚠️ pipeline_memory run_ledger_finish (failure path) "
                    f"failed (non-fatal): {type(_mem_exc).__name__}"
                )

        # Sentry cron check-in: signal final status
        if SENTRY_DSN and _cron_checkin_id:
            try:
                # Session failure dominates: a run that died before (or
                # during) group processing must check in ERROR even with
                # zero per-group errors (Copilot review, PR #297). Both
                # names are hoisted above the try, so no dir() guard is
                # needed.
                _cron_ok = (not _session_failed) and _groups_errored == 0
                capture_checkin(
                    monitor_slug=_cron_monitor_slug,
                    check_in_id=_cron_checkin_id,
                    status=MonitorStatus.OK if _cron_ok else MonitorStatus.ERROR,
                )
            except Exception as exc:
                logging.warning(f"⚠️ Sentry cron check-in (final) failed: {exc}")
        
        # Ensure any open transaction is closed
        if _txn:
            _txn.set_status("unknown")
            _txn.__exit__(None, None, None)
        
        # Flush Sentry events before process exits
        if SENTRY_DSN:
            sentry_sdk.flush(timeout=10)
