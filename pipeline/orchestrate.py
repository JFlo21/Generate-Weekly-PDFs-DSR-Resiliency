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
            logging.info(
                f"🧹 REMEDIATE_CLAIMERS=True — running isolated claimer "
                f"remediation sweep (dry_run={REMEDIATION_DRY_RUN}, "
                f"window_weeks={REMEDIATION_WINDOW_WEEKS})"
            )
            run_claimer_remediation(
                client,
                dry_run=REMEDIATION_DRY_RUN,
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
                    purge_existing_hashed_outputs(client, TARGET_SHEET_ID, RESET_WR_LIST, TEST_MODE)
                else:
                    logging.info("🧨 Global hash reset requested (RESET_HASH_HISTORY=1)")
                    span.set_data("purge_type", "global")
                    purge_existing_hashed_outputs(client, TARGET_SHEET_ID, None, TEST_MODE)
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

                # Update hash history with variant-aware key (even in TEST_MODE so future prod runs can leverage)
                hash_history[history_key] = {
                    'hash': data_hash,
                    'rows': len(group_rows),
                    'updated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'foreman': group_rows[0].get('__current_foreman'),
                    'week': week_raw,
                    'variant': variant,
                    'identifier': identifier,
                }
                history_updates += 1

                # Sub-project E: shadow-write the durable per-group content
                # hash to Supabase alongside the local json cache. Gated on
                # SUPABASE_HASH_STORE_WRITE_ENABLED (default ON) — harmless
                # while the store is not yet authoritative: it just populates
                # billing_audit.group_content_hash so the eventual
                # authoritative flip has data to read. ``upsert_group_hash``
                # is fail-safe (returns a no-op when Supabase is unavailable /
                # TEST_MODE and never raises); the extra guard keeps a future
                # regression from breaking the generation path. ``week_iso``
                # is the ISO DATE the column expects (NOT the MMDDYY
                # week_raw), kept consistent with lookup_group_hash in the
                # skip gate above.
                if (
                    SUPABASE_HASH_STORE_WRITE_ENABLED
                    and BILLING_AUDIT_AVAILABLE
                    and not TEST_MODE
                    and week_iso
                ):
                    # ``week_iso`` is guarded truthy: week_ending is a DATE
                    # column, so an empty string (missing __week_ending_date)
                    # would be a PostgREST type error that could trip the
                    # per-op circuit breaker. Skipping the shadow write for
                    # such an edge-case group is harmless — the json cache
                    # and (until authoritative) the filename hash still drive
                    # change detection.
                    try:
                        _billing_audit_writer.upsert_group_hash(
                            wr_num, week_iso, variant,
                            identifier or '', data_hash,
                        )
                    except Exception:
                        logging.exception(
                            "E shadow hash write failed (non-fatal)")
                
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
                # Per-task attempt counter (local → thread-safe under the
                # executor.map fan-out below; each _upload_one call owns its
                # own dict). Drives the retry idempotency guard in the closure.
                _upload_attempt = {'n': 0}

                def _do_upload_attempt():
                    _upload_attempt['n'] += 1
                    _is_retry = _upload_attempt['n'] > 1
                    target_row = task['target_row']
                    force_this = FORCE_GENERATION or (task['week_raw'] in REGEN_WEEKS)

                    # Codex P2 — retry idempotency / data-loss guard. The
                    # prefetched attachment_cache is a PRE-UPLOAD snapshot, so on
                    # a retry it is stale. A prior attempt may have uploaded the
                    # workbook successfully but had the SDK raise a transient
                    # before we observed the response (commit-then-report-fail).
                    # In SUPABASE_HASH_STORE_AUTHORITATIVE mode filenames are
                    # clean (no hash token), so delete_old_excel_attachments has
                    # NO filename-hash skip and would DELETE that committed copy
                    # then re-upload — leaving the row with NO workbook if the
                    # re-upload then fails (data loss, strictly worse than a
                    # duplicate). So on a retry: fetch the row's LIVE attachment
                    # state ONCE, and if the same-identity workbook is already
                    # present (a prior committed attempt), PRESERVE it and report
                    # success instead of delete-then-reupload. Reuse that same
                    # live snapshot for the delete so it sees the row's true
                    # state. force_this is exempt (force always regenerates).
                    if _is_retry:
                        try:
                            _live_atts = client.Attachments.list_row_attachments(
                                task['target_sheet_id'], target_row.id
                            ).data
                        except Exception:
                            _live_atts = None  # fall back to per-call live lookup
                        if (
                            not force_this
                            and not SKIP_UPLOAD
                            and _has_existing_week_attachment(
                                client, task['target_sheet_id'], target_row,
                                task['wr_num'], task['week_raw'],
                                variant=task['variant'],
                                identifier=task['file_identifier'],
                                cached_attachments=_live_atts,
                            )
                        ):
                            logging.info(
                                f"✅ Retry: {task['filename']} already on row "
                                f"{target_row.id} from a prior committed "
                                f"attempt; preserving (treating as uploaded)."
                            )
                            return 'uploaded'
                        _cached_attachments = _live_atts
                    else:
                        _cached_attachments = attachment_cache.get(target_row.id)
                    deleted_count, skipped = delete_old_excel_attachments(
                        client, task['target_sheet_id'], target_row, task['wr_num'],
                        task['week_raw'], task['data_hash'],
                        variant=task['variant'], identifier=task['file_identifier'],
                        force_generation=force_this,
                        cached_attachments=_cached_attachments
                    )
                    if force_this and skipped:
                        skipped = False

                    if skipped:
                        return 'skipped'

                    if not SKIP_UPLOAD:
                        with open(task['excel_path'], 'rb') as file:
                            client.Attachments.attach_file_to_row(
                                task['target_sheet_id'],
                                target_row.id,
                                (task['filename'], file, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                            )
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
        # Sentry cron check-in: signal final status
        if SENTRY_DSN and _cron_checkin_id:
            try:
                _cron_ok = '_groups_errored' not in dir() or _groups_errored == 0
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
