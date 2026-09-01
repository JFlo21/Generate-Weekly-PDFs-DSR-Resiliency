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
)
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
# Phase 11 Plan 02 (INC-01): the package's first READ surface, used by
# resolve_run_mode() below. Same independence rationale as _mem_writer.
from pipeline_memory import reader as _mem_reader
# Phase 11 Plan 05 (INC-04, D-07/D-08): the shadow-incremental parity
# proof -- computes and compares only, never acts. See pipeline/parity.py
# module docstring for the full contract.
from pipeline import parity as _parity

# Named re-export imports (byte-exact from the facade) so every bare sibling
# reference inside main()/testmode resolves identically (W1-W5 pattern). The
# 4 live-proxy globals (SUBCONTRACTOR_SHEET_IDS / _FOLDER_DISCOVERED_* /
# _RATES_FINGERPRINT) are intentionally absent — main() reads none of them.

from pipeline.config import (  # noqa: E402
    API_TOKEN,
    ATTACHMENT_REQUIRED_FOR_SKIP,
    NO_TARGET_ROW_MAX_MISS_RATIO,
    ATTRIBUTION_BULK_PREFETCH_FALLBACK,
    AUDIT_SHEET_ID,
    DEBUG_ESSENTIAL_ROWS,
    DEBUG_SAMPLE_ROWS,
    DISABLE_AUDIT_FOR_TESTING,
    EXCLUDE_WRS,
    EXTENDED_CHANGE_DETECTION,
    FILTER_DIAGNOSTICS,
    FORCE_GENERATION,
    FORCE_REDISCOVERY,
    FOREMAN_DIAGNOSTICS,
    GITHUB_ACTIONS_MODE,
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
    RUN_MEMORY_INCREMENTAL_ENABLED,
    RUN_MEMORY_SHADOW_GENERATION_HEADROOM_MIN,
    RUN_MEMORY_SHADOW_MAX_MINUTES,
    RUN_MEMORY_SHADOW_RPC_TIMEOUT_SEC,
    RUN_MEMORY_WRITE_ENABLED,
    RUN_MEMORY_WRITE_GENERATION_HEADROOM_MIN,
    RUN_MEMORY_WRITE_MAX_MINUTES,
    RUN_MEMORY_WRITE_RPC_TIMEOUT_SEC,
    SAFETY_WINDOW_MINUTES,
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
    VAC_CREW_CLAIM_ATTRIBUTION_ENABLED,
    VAC_CREW_FOLDER_IDS,
    VAC_CREW_LEGACY_CLEANUP_ENABLED,
    VAC_CREW_SHEET_IDS,
    WR_FILTER,
    _RE_EXTRACT_NUMBERS,
    _RE_ISO_DATE_PREFIX,
    _RE_SANITIZE_HELPER_NAME,
    _RE_SANITIZE_IDENTIFIER,
    _audit_sheet_id_int,
    _coerce_sheet_id,
    _cutoff_str,
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
    _compute_aggregated_content_hash,
    _resolve_unchanged_for_skip,
    build_group_identity,
    calculate_data_hash,
    canonical_first_row,
    extract_data_hash_from_filename,
    list_generated_excel_files,
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
    create_target_sheet_map_with_quarantine,
    create_target_sheet_map_for,
)
from pipeline.attribution import (  # noqa: E402
    BILLING_AUDIT_ROW_CACHE_MAX_ENTRIES,
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
    wrs = ['13792260', '17310321']
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


# ``group_key -> (wr, week_raw, variant)`` for the groups a run did NOT
# generate because the WR has no target-sheet row.
NoTargetRowGroups = dict[str, tuple[str, str, str]]


def derive_row_wr(row: dict[str, Any]) -> str:
    """The WR identifier the group loop derives from a source row -- the
    same three steps, so the pre-loop circuit breaker and the per-group
    gate agree byte-for-byte: ``str(raw).split('.')[0]``, then the
    filesystem sanitizer, then ``[:50]``. PURE.
    """
    raw = row.get('Work Request #') if isinstance(row, dict) else None
    wr = str(raw).split('.')[0] if raw else ''
    return _RE_SANITIZE_HELPER_NAME.sub('_', wr)[:50]


def derive_group_wr(group_rows: list[dict[str, Any]]) -> str:
    """``derive_row_wr`` of the group's first row ('' for an empty
    group) -- exactly what the loop reads. PURE."""
    return derive_row_wr(group_rows[0]) if group_rows else ''


def no_target_row_gate_enabled(
    rows: list[dict[str, Any]],
    target_map: dict[str, Any] | None,
    *,
    max_miss_ratio: float,
    quarantined: frozenset[str] | set[str] = frozenset(),
) -> tuple[bool, int, int, float]:
    """Circuit breaker for the no-target-row skip (risk review P1-A).

    A NON-EMPTY target map is not proof of a COMPLETE one: a wrong
    ``TARGET_SHEET_ID``, a sharing change that returns a row subset, or
    a mid-edit sheet all yield a populated-but-short map, and "absent
    from a partial read" must never become "never generate" (the same
    principle the source-read code states for deletions). Measured over
    *rows* -- every fetched source row, NOT the group mapping, which
    ``main()`` may already have scoped for incremental mode or
    ``MAX_GROUPS`` (a 1-of-1 scoped miss must not disable the gate).
    Keys the builder *quarantined* (target-sheet collisions) are not
    "missing": those WRs have target rows. Returns
    ``(enabled, missing, universe, ratio)`` where *universe* is the
    number of distinct non-empty WR values across *rows*. Enabled only
    when the map is populated AND ``ratio <= max_miss_ratio``; a
    disabled gate means the run falls back to generate-and-warn. PURE.
    """
    universe = {derive_row_wr(row) for row in (rows or [])}
    universe.discard('')
    if not target_map or not universe:
        return False, len(universe), len(universe), 1.0
    missing = len(universe - set(target_map) - set(quarantined))
    ratio = missing / len(universe)
    return ratio <= max_miss_ratio, missing, len(universe), ratio


def should_skip_no_target_row(
    wr_num: str,
    target_map: dict[str, Any] | None,
    *,
    attachment_required: bool,
    test_mode: bool,
    skip_upload: bool,
    quarantined: frozenset[str] | set[str] = frozenset(),
) -> bool:
    """Owner decision 2026-08-28: a group whose Work Request has no row
    on the target sheet is a data-entry error on the source sheet
    (malformed or unregistered ``Work Request #``) -- it is NOT
    generated and is listed as an error instead of regenerating on every
    run for a file that can never upload.

    PURE. True only when every guard holds: attachments are required
    for a skip (the same switch that makes the target map load at all),
    not TEST_MODE, not a SKIP_UPLOAD dry run (generating is the point of
    a dry run), the target map is POPULATED (an empty map means the
    sheet was unreachable -- never a skip; zero-row guard), the WR is
    absent from it AND the builder did not *quarantine* it (a
    target-sheet collision: two target rows sanitize to the same key,
    so the WR HAS rows -- the pre-existing "collision ... 'not found in
    target sheet'" path stays in charge of that outcome). Converges by
    itself: the moment the row appears the group is generated on the
    next run (its hash was never stored).

    Safe only because every upload leg requires the primary target row:
    ``pipeline/upload.py::_build_upload_tasks_for_group`` gates the
    reduced_sub PPP leg on ``primary_present`` too, so a WR absent from
    the target map has NO upload path for ANY variant (pinned by
    ``tests/test_skip_no_target_row.py``). Deliberately sits above
    ``FORCE_GENERATION`` / ``WR_FILTER`` / ``RESET_WR_LIST``: forcing
    cannot make a file uploadable.
    """
    if not attachment_required or test_mode or skip_upload:
        return False
    if not target_map:
        return False
    key = str(wr_num)
    if key in quarantined:
        return False
    return key not in target_map


def format_no_target_row_summary(
    groups: NoTargetRowGroups, target_sheet_id: object,
    max_values: int = 25,
) -> tuple[str, str]:
    """End-of-run audit for the groups NOT generated because the WR has
    no target-sheet row, as ``(error_line, values_line)``:

    * *error_line* (logged at ERROR -> a Sentry event, which has NO PII
      sanitizer) carries counts and guidance only -- never a value.
    * *values_line* (logged at WARNING) lists the offending
      ``Work Request #`` values -- the audit trail the owner asked for
      -- and starts with the registered ``_PII_LOG_MARKERS`` text
      ``"Work request "`` so the Sentry breadcrumb / Sentry Logs
      sanitizers drop it while the Actions log keeps it. Capped at
      *max_values* because a malformed cell can hold free text.

    PURE.
    """
    wrs = sorted({str(v[0]) for v in groups.values()})
    shown = ', '.join(wrs[:max_values])
    if len(wrs) > max_values:
        shown += f", ... and {len(wrs) - max_values} more"
    error_line = (
        f"❌ {len(groups)} group(s) across {len(wrs)} distinct 'Work "
        f"Request #' value(s) have no row on target sheet "
        f"{target_sheet_id} -- data-entry errors on the source sheets "
        f"(malformed or unregistered values); NOT generated. Fix the "
        f"source rows; the values are on the next log line."
    )
    values_line = f"Work request values with no target-sheet row: {shown}"
    return error_line, values_line


def derive_group_identity(
    first_row: dict,
    *,
    primary_claim_enabled: bool,
    vac_crew_claim_enabled: bool,
    res_grouping_mode: str,
) -> tuple[str, str]:
    """``(identifier, file_identifier)`` for the group whose canonical
    first row is ``first_row``.

    The ONE identity definition behind the three orchestrate identity
    sites -- Site 1 (main-loop ``identifier`` / ``file_identifier`` /
    ``history_key``), Site 2 (``valid_wr_weeks`` attachment-cleanup
    tuple) and Site 3 (``current_keys`` hash-history prune). Before this
    extraction each site carried its own copy of the branch chain; CR-01
    documents the bug shape when they drift (a fresh history key treated
    as stale, live attachments pruned, permanent regeneration churn).
    Copilot on PR #361 asked for the sites to be behaviourally testable;
    ``tests/test_group_identity_and_header_foreman.py`` pins the helper
    against the former inline chain for every branch.

    ``identifier`` is the history-key shape; ``file_identifier`` is the
    filename shape ``generate_excel`` / ``build_group_identity`` use.
    They differ only for the helper-style variants (``foreman|dept|job``
    vs the sanitized foreman). Kill switches are passed in because
    ``main()`` binds them from the facade at entry (test rebinds).

    Branches (all read the CANONICAL row, never arrival order):
    - helper / aep_billable_helper / reduced_sub_helper -> helper foreman
      + dept + job (CR-01 gate: the shadow variants must not fall through
      to the ``User`` branch).
    - vac_crew -> sanitized claimer, gated on the vac-crew kill switch
      (disabled mode reproduces the bare legacy identity).
    - reduced_sub / aep_billable -> sanitized frozen claimer.
    - primary -> sanitized frozen claimer when primary claim attribution
      is on AND the grouping mode partitions by claimer; else the legacy
      ``User`` field.
    """
    variant = first_row.get('__variant', 'primary')
    if variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):
        helper_foreman = first_row.get('__helper_foreman', '')
        helper_dept = first_row.get('__helper_dept', '')
        helper_job = first_row.get('__helper_job', '')
        identifier = f"{helper_foreman}|{helper_dept}|{helper_job}"
        file_identifier = (
            _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]
            if helper_foreman else ''
        )
        return identifier, file_identifier
    if variant == 'vac_crew':
        _vc = first_row.get('__current_foreman', '')
        identifier = (
            _RE_SANITIZE_IDENTIFIER.sub('_', _vc)[:50]
            if (vac_crew_claim_enabled and _vc) else ''
        )
        return identifier, identifier
    if variant in ('reduced_sub', 'aep_billable'):
        _b_claimer = first_row.get('__current_foreman', '')
        identifier = (
            _RE_SANITIZE_IDENTIFIER.sub('_', _b_claimer)[:50]
            if _b_claimer else ''
        )
        return identifier, identifier
    if primary_claim_enabled and res_grouping_mode in ('helper', 'both'):
        _pf = first_row.get('__current_foreman', '')
        identifier = (
            _RE_SANITIZE_IDENTIFIER.sub('_', _pf)[:50] if _pf else ''
        )
        return identifier, identifier
    # Legacy primary identity: the row's ``User`` field.
    user_val = first_row.get('User')
    identifier = (
        _RE_SANITIZE_IDENTIFIER.sub('_', user_val)[:50] if user_val else ''
    )
    return identifier, identifier


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
            "groups_skipped_no_target_row": 0,
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

    The affected ``(wr, week_ending)`` set was observability-only in
    Phase 10. Since Phase 11 Plan 04 the incremental path (PHASE 2a,
    ``_run_phase2_incremental``) reads it to scope regeneration -- and
    it may do so ONLY when ``memory_confirmed`` below is True. The
    per-group skip/regenerate/upload gate itself still lives entirely
    on the local group_state content-hash / durable group hash path
    (10-CONTEXT.md, plan success criteria; the local hash-history JSON
    cache this comment used to name is retired -- Phase 11 Plan 08,
    INC-05).

    Returns a dict of counts only (no PII, no per-row values):
    ``sheets_written``, ``sheets_errored``, ``rows_sent``,
    ``rows_changed``, ``affected`` (the (wr, week_ending) set),
    ``elapsed_seconds``, plus the Greptile P1 (PR #351) confirmation
    contract:

      - ``memory_confirmed``: True ONLY when every sheet's write reported
        a confirmed status (``ok`` / ``noop`` per
        ``pipeline_memory.writer.UPSERT_CONFIRMED_STATUSES``), no writer
        call raised, the pre-flight guard did not skip the phase, and the
        mid-loop budget break left no sheet unwritten. Under every other
        outcome an empty or partial ``affected`` set is indistinguishable
        from a genuine no-change run, so a caller scoping regeneration
        MUST widen to a full read instead of trusting it (T-11-18).
      - ``sheets_unconfirmed``: sheets whose status was not confirmed.
      - ``sheets_unwritten``: sheets never attempted (budget break).
      - ``unconfirmed_reason``: the FIRST reason, for ``fallback_reason``.

    NEVER raises -- every per-sheet write already goes through
    ``pipeline_memory.writer``'s own fail-open contract, and this
    function additionally isolates one sheet's unexpected exception from
    the rest of the loop.
    """
    result: dict[str, Any] = {
        "sheets_written": 0,
        "sheets_errored": 0,
        "rows_sent": 0,
        "rows_changed": 0,
        "affected": set(),
        "elapsed_seconds": 0.0,
        "memory_confirmed": False,
        "sheets_unconfirmed": 0,
        "sheets_unwritten": 0,
        "unconfirmed_reason": None,
    }

    if not (RUN_MEMORY_WRITE_ENABLED and not TEST_MODE):
        result["unconfirmed_reason"] = (
            "run-memory write disabled (RUN_MEMORY_WRITE_ENABLED off or "
            "TEST_MODE)"
        )
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
            result["unconfirmed_reason"] = (
                f"pre-flight budget guard skipped the phase "
                f"({_remaining_min:.1f}min remaining, need > "
                f"{_required_min}min)"
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
            _write = _mem_writer.upsert_rows_bulk_result(
                sheet_id, mem_run_id, bucket_rows,
            )
        except Exception as exc:
            logging.warning(
                "⚠️ pipeline_memory upsert_rows_bulk raised unexpectedly "
                f"for sheet {sheet_id} (non-fatal); treating as errored "
                "this run."
            )
            _write = {
                "affected": set(),
                "status": f"exception ({type(exc).__name__})",
                "rows_errored": len(bucket_rows),
            }

        sheet_affected = set(_write.get("affected") or ())
        _status = str(_write.get("status") or "unknown")
        # Greptile P1 (PR #351): only a CONFIRMED status lets an empty
        # affected set mean "nothing changed". Everything else -- no
        # client, writes disabled, every chunk failed, a PARTIAL chunk
        # failure, an exception -- is "cannot confirm what changed"; the
        # partial set (if any) is kept for observability but the caller
        # must never narrow regeneration scope on it (memory_confirmed
        # below stays False).
        if _status in _mem_writer.UPSERT_CONFIRMED_STATUSES:
            if sheet_affected:
                result["sheets_written"] += 1
        else:
            result["sheets_errored"] += 1
            result["sheets_unconfirmed"] += 1
            if sheet_affected:
                result["sheets_written"] += 1  # partial: some rows landed
            if result["unconfirmed_reason"] is None:
                _errored = _write.get("rows_errored") or 0
                result["unconfirmed_reason"] = (
                    f"sheet {sheet_id}: {_status}"
                    + (f" ({_errored} row(s) errored)" if _errored else "")
                )

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
                result["sheets_unwritten"] = _remaining_sheets
                if result["unconfirmed_reason"] is None:
                    result["unconfirmed_reason"] = (
                        f"run-memory sub-budget exhausted with "
                        f"{_remaining_sheets} sheet(s) unwritten"
                    )
                break

    result["memory_confirmed"] = (
        result["sheets_unconfirmed"] == 0
        and result["sheets_unwritten"] == 0
        and result["unconfirmed_reason"] is None
    )
    result["elapsed_seconds"] = (
        datetime.datetime.now() - _phase_start
    ).total_seconds()
    logging.info(
        f"⚡ Run-memory row writes: {result['sheets_written']} sheet(s) "
        f"written, {result['sheets_errored']} errored, "
        f"{result['rows_sent']} row(s) sent, {result['rows_changed']} "
        f"changed, {len(result['affected'])} group(s) affected, "
        f"confirmed={result['memory_confirmed']}, "
        f"{result['elapsed_seconds']:.1f}s elapsed."
    )
    return result


def _normalize_column_mapping(mapping: dict[str, Any]) -> dict[str, int]:
    """Normalize a ``column_mapping`` dict to ``{str(name): int(id)}``.

    A stored ``sheet_registry.column_mapping`` value has been through a
    JSONB round-trip (Supabase may return string-typed values for what
    Python wrote as ints); the freshly-discovered mapping from
    ``discover_source_sheets()`` has native int column ids. Comparing the
    two dicts directly would report a "drift" on every run purely from
    type representation, never from a real mapping change -- normalizing
    both sides before comparison (``resolve_run_mode`` trigger 2) avoids
    that false positive. An entry whose value cannot coerce to ``int`` is
    dropped rather than raising (defensive -- a malformed stored value
    should not crash mode resolution; it will simply compare unequal).
    """
    normalized: dict[str, int] = {}
    for key, value in mapping.items():
        try:
            normalized[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return normalized


def resolve_run_mode(
    source_sheets: list[dict[str, Any]],
    watermarks: dict[Any, dict[str, Any]],
    last_run_status: dict[str, Any] | None,
    *,
    incremental_enabled: bool,
    execution_type: str,
    auth_error_sheet_ids: set | None = None,
    reset_hash_history: bool = False,
    regen_weeks: set | None = None,
    reset_wr_list: set | None = None,
    force_generation: bool = False,
) -> tuple[str, str | None, dict[Any, str]]:
    """Resolve this run's mode: ``'full'`` or ``'incremental'`` (D-02).

    Implements all seven CONTEXT.md D-02 full-read escalation triggers
    plus the ``RUN_MEMORY_INCREMENTAL_ENABLED`` flag gate. Triggers 1-3
    are per-sheet and populate ``per_sheet_reasons`` WITHOUT by
    themselves forcing the whole run to full -- a later plan restructures
    PHASE 2 to read that map and force a per-sheet full read for those
    entries even when the whole-run mode is ``'incremental'``. Triggers
    4-7 (and the flag gate) force the WHOLE run to ``'full'``, checked in
    order, short-circuiting on the first one that fires.

    NOT wired into PHASE 2 by this plan -- ``all_rows`` still comes from
    today's single ``get_all_source_rows()`` full fetch (11-02-PLAN.md
    <objective>; plan 04 restructures PHASE 2 against this contract).
    ``auth_error_sheet_ids`` (trigger 3) has no live producer yet at this
    plan's call site either -- it is a real, directly-testable parameter
    ready for the per-sheet delta read plan 04 wires in.

    NEVER raises: any unexpected exception resolves to ``'full'`` with a
    ``fallback_reason`` naming the failure, mirroring
    ``_run_memory_write_phase``'s never-raise contract. Every full-mode
    resolution returns a non-empty ``fallback_reason`` (T-11-11 -- a
    silent fallback is prohibited).

    Returns ``(mode, fallback_reason, per_sheet_reasons)``:
      - ``mode``: ``'full'`` or ``'incremental'`` (the two
        ``run_ledger.mode`` CHECK values this phase uses; ``'targeted'``
        is reserved for a later phase).
      - ``fallback_reason``: a non-empty string naming the trigger when
        ``mode == 'full'``; ``None`` when ``mode == 'incremental'``.
      - ``per_sheet_reasons``: sheet id -> reason string for every sheet
        trigger 1/2/3 flagged, regardless of the whole-run mode.
    """
    try:
        auth_error_sheet_ids = auth_error_sheet_ids or set()
        regen_weeks = regen_weeks or set()
        reset_wr_list = reset_wr_list or set()
        per_sheet_reasons: dict[Any, str] = {}

        # Triggers 1-3 (per-sheet) -- always computed so the map is
        # complete for a caller even when the whole run is already forced
        # to full below.
        for source in source_sheets:
            sheet_id = source.get('id')

            if sheet_id in auth_error_sheet_ids:
                # Trigger 3: isolate, do NOT retry-as-full in a loop, do
                # NOT touch the watermark -- trigger 1 forces a full read
                # of this sheet once access returns (the watermark stays
                # stale/absent in the meantime).
                per_sheet_reasons[sheet_id] = (
                    "trigger3_auth_error: sheet isolated (401/403); "
                    "watermark left unrefreshed"
                )
                logging.warning(
                    f"🔐 resolve_run_mode: sheet {sheet_id} isolated "
                    "(401/403 auth error) -- not retried as full in a loop"
                )
                sentry_add_breadcrumb(
                    "resolve_run_mode",
                    f"Sheet {sheet_id} isolated (401/403 auth error)",
                    level="warning",
                    data={"sheet_id": sheet_id},
                )
                continue

            watermark = watermarks.get(sheet_id)
            if watermark is None or watermark.get('last_sheet_version') is None:
                # Trigger 1: new sheet, or a row with no version watermark
                # yet -> full read of THIS sheet.
                per_sheet_reasons[sheet_id] = (
                    "trigger1_no_watermark: no sheet_registry row, or "
                    "last_sheet_version is None"
                )
                continue

            fresh_mapping = _normalize_column_mapping(
                source.get('column_mapping') or {}
            )
            stored_mapping = _normalize_column_mapping(
                watermark.get('column_mapping') or {}
            )
            if fresh_mapping != stored_mapping:
                # Trigger 2: column_mapping drift -> full read of THIS
                # sheet + mapping refresh (never continue against a stale
                # mapping -- misgrouping is a billing-integrity risk).
                per_sheet_reasons[sheet_id] = (
                    "trigger2_column_mapping_drift: freshly-discovered "
                    "column_mapping differs from the stored "
                    "sheet_registry.column_mapping"
                )

        # Flag gate: RUN_MEMORY_INCREMENTAL_ENABLED unset resolves to
        # full REGARDLESS of every other input -- checked first so no
        # other trigger's reason can shadow it.
        if not incremental_enabled:
            return (
                "full",
                "flag_off: RUN_MEMORY_INCREMENTAL_ENABLED is not set",
                per_sheet_reasons,
            )

        # Trigger 4: empty watermark map (Supabase outage or missing
        # sheet_registry) resolves the WHOLE run to full -- the one place
        # "fail-open toward Supabase" means doing MORE work.
        if not watermarks:
            return (
                "full",
                "trigger4_empty_watermark_map: Supabase outage or missing "
                "sheet_registry (cannot confirm any sheet is unchanged)",
                per_sheet_reasons,
            )

        # Trigger 5: any operator reset/force flag -> ignore the
        # watermark; the simplest safe scope this plan is the WHOLE run.
        if reset_hash_history or regen_weeks or reset_wr_list or force_generation:
            fired = []
            if reset_hash_history:
                fired.append("RESET_HASH_HISTORY")
            if regen_weeks:
                fired.append("REGEN_WEEKS")
            if reset_wr_list:
                fired.append("RESET_WR_LIST")
            if force_generation:
                fired.append("FORCE_GENERATION")
            return (
                "full",
                f"trigger5_operator_flag: {'/'.join(fired)} set",
                per_sheet_reasons,
            )

        # Trigger 6: the previous run_ledger row has status != 'success'
        # or finished_at IS NULL -- a crashed run's partial watermark
        # updates are not a clean baseline. A read failure that resolves
        # last_run_status to None is the SAME failure class (11-RESEARCH.md
        # Open Question 3) and is handled identically here.
        if (
            last_run_status is None
            or last_run_status.get('status') != 'success'
            or last_run_status.get('finished_at') is None
        ):
            return (
                "full",
                "trigger6_previous_run_not_clean: previous run_ledger row "
                "missing, errored, unfinished, or unreadable",
                per_sheet_reasons,
            )

        # Trigger 7: only production_frequent may go incremental (D-11) --
        # weekend/weekly-deep/manual dispatches stay full.
        if execution_type != "production_frequent":
            return (
                "full",
                "trigger7_execution_type: EXECUTION_TYPE="
                f"{execution_type!r} is not 'production_frequent'",
                per_sheet_reasons,
            )

        return ("incremental", None, per_sheet_reasons)
    except Exception as exc:
        logging.warning(
            f"⚠️ resolve_run_mode raised unexpectedly ({type(exc).__name__}); "
            "resolving to full (fail-open)."
        )
        sentry_add_breadcrumb(
            "resolve_run_mode",
            f"Unexpected exception: {type(exc).__name__}",
            level="warning",
        )
        return (
            "full",
            f"trigger_unexpected_exception: {type(exc).__name__}: {exc}",
            {},
        )


def _build_registry_write_plan(
    source_sheets: list[dict[str, Any]],
    trigger3_sheet_ids: set,
    capture_time: str,
) -> tuple[list[dict[str, Any]], dict[Any, str], set]:
    """Compute the ``(sheets, capture_times, full_read_sheet_ids)`` triple
    both ``sheet_registry`` upsert passes need (Phase 11 Plan 02,
    D-01/D-02 trigger 3).

    PURE (no I/O, never raises internally) so it's directly
    unit-testable without invoking ``main()`` -- mirrors
    ``_build_group_state_flush``'s standalone-function testability
    pattern (10-03 key-decision).

    A sheet id present in ``trigger3_sheet_ids`` is EXCLUDED entirely
    from the returned sheets list -- neither ``last_read_at`` nor
    ``last_sheet_version`` is refreshed for it this run (D-02 trigger 3:
    isolate, don't touch the watermark, let trigger 1 force a full read
    once access returns). PHASE 2 this plan still performs a full fetch
    of every remaining sheet regardless of the resolved run mode, so
    every sheet this function returns IS marked full_read=True in the
    returned ``full_read_sheet_ids`` set, and every sheet gets the SAME
    ``capture_time`` (captured once by the caller, immediately before
    PHASE 2 issues its reads).
    """
    registry_sheets = [
        s for s in source_sheets if s.get('id') not in trigger3_sheet_ids
    ]
    capture_times = {s.get('id'): capture_time for s in registry_sheets}
    full_read_ids = {s.get('id') for s in registry_sheets}
    return registry_sheets, capture_times, full_read_ids


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


class _GroupStateAttachmentStub:
    """Minimal Smartsheet-``Attachment``-shaped stand-in for a
    ``pipeline_memory.group_state``-resolved attachment identity (Phase 11
    Plan 08, INC-05 retirement, CONTEXT.md D-12).

    ``pipeline.cleanup``'s identity-matching logic
    (``delete_old_excel_attachments``) reads exactly two attributes off
    each cached attachment -- ``getattr(a, 'name', '')`` (parsed by
    ``build_group_identity``) and ``a.id`` (passed to
    ``Attachments.delete_attachment``). This stub supplies both from a
    ``group_state`` row's ``attachment_id`` / ``attachment_name`` so that
    consumer can resolve an already-known identity without a Smartsheet
    ``list_row_attachments`` call, while remaining indistinguishable, to
    its unmodified filtering logic, from a real SDK ``Attachment`` object.

    NOT proof of existence (PR #373 review): a stub records what this
    pipeline last uploaded, not what is on the row NOW -- an attachment
    someone deleted by hand would still have a stub. The unchanged-group
    skip gate (``_has_existing_week_attachment``) therefore never reads
    stubs; it confirms against ``_live_row_attachments`` below.
    """

    __slots__ = ("id", "name")

    def __init__(self, attachment_id: Any, attachment_name: Any) -> None:
        self.id = attachment_id
        self.name = attachment_name


def _live_row_attachments(
    client: Any, sheet_id: Any, row_id: Any, memo: dict | None,
) -> 'list | None':
    """Fetch and memoize the LIVE attachment listing for one target row.

    INC-05 follow-up (PR #373 review): ``group_state``'s stored
    attachment identity proves what this pipeline last uploaded, not what
    exists on the row NOW. Trusting it in the unchanged-group skip gate
    would leave a manually deleted billing report missing forever (the
    group skips every run until its data changes). The skip gate
    therefore confirms existence against a live
    ``list_row_attachments`` call, memoized per ``row_id`` so each row
    costs at most one API call per run -- the retired bulk pre-fetch's
    budgeted phase stays gone.

    Returns the listing (possibly empty) on success; ``None`` on any
    transport failure WITHOUT memoizing it, so the caller's existing
    on-demand fallback makes the fail-safe call (a failed lookup reads
    as "no attachment" and forces a regeneration, never a skip).
    """
    if memo is not None and row_id in memo:
        return memo[row_id]
    try:
        listing = client.Attachments.list_row_attachments(
            sheet_id, row_id
        ).data
    except Exception:
        return None
    if memo is not None:
        memo[row_id] = listing
    return listing


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


def _shadow_parity_input_sets(
    candidate_hashes: dict[Any, Any],
    deferred_records: list[dict[str, Any]],
    upload_tasks: list[dict[str, Any]],
    unobservable: 'set[Any] | None' = None,
) -> tuple[dict[Any, Any], dict[Any, Any], int]:
    """Build the two group-hash mappings ``compare_shadow_parity`` sees.

    PURE (no I/O, never raises on well-formed input) so the 2026-08-27
    #2801 finding is directly unit-testable: the first real memory run
    compared the incremental candidate against EVERY generated group
    (158), 154 of which were the quarantined garbage-name groups
    (``_User__NO_MATCH`` / ``_User_Unknown_Foreman``) that regenerate on
    every run because their upload is withheld -- so they never gain an
    attachment -- and are never observable output. The candidate set
    (derived from changed rows) can never contain them, which made the
    D-07 group verdict ``fail`` by construction.

    "Actual" therefore means the generated groups that have at least one
    upload task (``_build_upload_tasks_for_group`` returns none when the
    WR is absent from every target sheet -- the same set the post-upload
    ``_build_group_state_flush`` can flush). A generated-but-withheld
    group is dropped from BOTH sides: it is unobservable whichever path
    produced it, so it can neither prove nor refute parity. A candidate
    group the full path did NOT generate at all (skipped as unchanged)
    stays in the candidate -- that is a real divergence the verdict must
    still report.

    *unobservable* (owner decision 2026-08-28): group keys the full path
    deliberately did NOT generate because the WR has no target-sheet
    row. They are the same never-observable set as a withheld group
    (nothing can ever upload for them), so they are dropped from the
    candidate as well and counted in ``withheld_excluded``.

    Returns ``(candidate, actual, withheld_excluded)``.
    """
    uploadable = {
        t.get('group_key') for t in (upload_tasks or [])
        if isinstance(t, dict)
    }
    actual: dict[Any, Any] = {}
    withheld: set = set()
    for rec in deferred_records or []:
        gk = rec.get('group_key')
        if gk in uploadable:
            actual[gk] = rec.get('data_hash')
        else:
            withheld.add(gk)
    withheld |= set(unobservable or ())
    candidate = {
        gk: h for gk, h in (candidate_hashes or {}).items()
        if gk not in withheld
    }
    return candidate, actual, len(withheld)


def _resolve_row_wr_week(row: dict[str, Any]) -> tuple[str, str | None]:
    """Resolve one source row's (WR, week-ending ISO string) using the
    SAME resolution ``group_source_rows`` uses for its own WR/week keys
    (Phase 11 Plan 04, D-04) -- never by re-parsing a group key string.

    WR: ``str(row['Work Request #']).split('.')[0]`` -- byte-identical to
    ``pipeline/grouping.py``'s ``wr_key`` derivation. Week: the SAME
    ``pipeline.utils.excel_serial_to_date`` parser ``_run_memory_write_
    phase`` uses for ``__mem_week_ending``, stringified through
    ``pipeline_memory.writer._coerce_date`` -- the SAME function the
    write path uses to turn that value into the ISO string that ends up
    in ``upsert_rows_bulk``'s returned affected set. Using the identical
    stringifier on both sides is what makes the two sets directly
    comparable by equality.

    PURE (no I/O, never raises internally) -- directly unit-testable
    without invoking ``main()``, mirroring ``_build_group_state_flush``'s
    standalone-function testability pattern.
    """
    wr_raw = row.get('Work Request #')
    wr_key = str(wr_raw).split('.')[0] if wr_raw else ''
    week_value = _utils.excel_serial_to_date(
        row.get('Weekly Reference Logged Date')
    )
    week_iso = _mem_writer._coerce_date(week_value)
    return wr_key, week_iso


def _filter_groups_to_affected(
    groups: dict[Any, list[dict[str, Any]]],
    affected_pairs: set[tuple[Any, Any]],
) -> dict[Any, list[dict[str, Any]]]:
    """Restrict *groups* to keys whose (WR, week-ending) resolves into
    *affected_pairs* -- Phase 11 Plan 04 (D-04): the affected-pair
    restriction applied AFTER the unmodified ``group_source_rows()`` call
    so cross-sheet groups stay intact (PHASE 2b already re-fetched every
    sheet holding a row for an affected pair) and no group is partially
    reconstructed -- a group key either survives here in full (every row
    ``group_source_rows`` assigned to it) or it doesn't survive at all.

    An empty *groups* input returns ``{}`` immediately (no-op, mirrors
    the empty-affected-set "successful run with zero groups" outcome).
    A group whose first row resolves to a pair NOT in *affected_pairs* is
    dropped entirely -- one row is representative because every row in a
    ``group_source_rows`` bucket shares the same (WR, week) by
    construction (that's what makes it one group).

    PURE (no I/O, never raises internally) -- directly unit-testable with
    synthetic ``groups`` dicts, no Smartsheet/Supabase mocking required.
    """
    if not groups:
        return {}
    filtered: dict[Any, list[dict[str, Any]]] = {}
    for key, rows in groups.items():
        if not rows:
            continue
        pair = _resolve_row_wr_week(rows[0])
        if pair in affected_pairs:
            filtered[key] = rows
    return filtered


def _run_phase2_incremental(
    client: Any,
    source_sheets: list[dict[str, Any]],
    watermarks: dict[Any, dict[str, Any]],
    per_sheet_reasons: dict[Any, str],
    mem_run_id: str,
    session_start: datetime.datetime,
) -> dict[str, Any]:
    """Phase 11 Plan 04 (D-04 Option C): PHASE 2a delta read -> the
    UNMODIFIED ``_run_memory_write_phase`` -> affected-set -> sheet
    mapping -> PHASE 2b scoped full re-fetch via the UNMODIFIED
    ``get_all_source_rows``.

    NEVER raises: any exception anywhere in this function -- a delta
    probe escalation, an unexpected ``_run_memory_write_phase`` failure,
    an empty (cannot-confirm) sheet mapping for a non-empty affected set,
    or any other unhandled exception -- resolves to ``ok=False`` with a
    non-empty ``fallback_reason``. The caller MUST then run today's
    single full ``get_all_source_rows`` call over EVERY source sheet:
    the regeneration scope can only ever be too WIDE, never too narrow
    (T-11-18).

    Per-sheet dispatch (``per_sheet_reasons`` from ``resolve_run_mode``):
      - a sheet flagged ``trigger3_auth_error`` is SKIPPED entirely this
        pass (D-02: isolate, do not touch the watermark, do not retry as
        full in a loop -- trigger 1 forces a full read once access
        returns).
      - a sheet flagged ``trigger1``/``trigger2`` (no watermark, or a
        stale ``column_mapping``) is fetched in FULL this pass via the
        unmodified ``get_all_source_rows`` -- planned incremental-mode
        behavior, not a failure.
      - every remaining sheet is delta-probed via
        ``pipeline.fetch.fetch_sheet_delta``. A probe that escalates
        (abbreviated response with no usable version, or any exception)
        aborts this WHOLE function -- a single bad probe on one sheet is
        never silently dropped from an otherwise-incremental run; the
        entire run falls back to full instead.

    The rows handed to ``_run_memory_write_phase`` carry only RAW mapped
    Smartsheet columns plus the ``__source_sheet_id``/``__row_id``/
    ``__row_modified_at`` provenance keys (``pipeline.fetch.
    map_delta_sheet_rows``) -- no business acceptance gate beyond "has a
    Work Request # and a Weekly Reference Logged Date" (the same minimum
    ``group_source_rows`` itself requires). That minimum gate is a
    STRICT SUPERSET of the full acceptance gate PHASE 2b's grouping
    phase applies (which additionally requires ``Units Completed?`` and a
    non-zero price), so PHASE 2a can only WIDEN the affected set relative
    to what PHASE 2b would actually group -- never narrow it.

    Returns a dict:
      ok: bool -- True when PHASE 2b's rows are ready to group.
      fallback_reason: str | None -- non-empty exactly when ok is False.
      all_rows: list[dict] -- PHASE 2b's rows (grouping input); present
          only when ok is True.
      affected: set[tuple] -- the (wr, week_ending) pairs
          ``_run_memory_write_phase`` reported. Empty is a legitimate
          "nothing changed" outcome ONLY because ``memory_confirmed``
          was True -- an unconfirmed write (no client, writes disabled,
          a failed or PARTIAL upsert, an exception, a budget skip) has
          already resolved to ``ok=False`` with
          ``trigger_memory_write_unconfirmed`` before this point
          (Greptile P1, PR #351). Present only when ok is True.
      mem_result: dict -- ``_run_memory_write_phase``'s own result dict,
          so the caller's existing ``_mem_*`` counter wiring is
          unaffected; present only when ok is True.
      delta_rows_count / delta_sheets_changed / mapped_sheet_count: int
          -- PHASE 2a/2b observability counters (notes-only, never a new
          ``run_summary.json`` key); present only when ok is True.
    """
    try:
        skip_ids = {
            sid for sid, reason in per_sheet_reasons.items()
            if reason.startswith('trigger3_auth_error')
        }
        full_read_ids = {
            sid for sid, reason in per_sheet_reasons.items()
            if sid not in skip_ids
        }
        delta_sources = [
            s for s in source_sheets
            if s.get('id') not in full_read_ids
            and s.get('id') not in skip_ids
        ]
        full_read_sources = [
            s for s in source_sheets if s.get('id') in full_read_ids
        ]

        delta_rows: list[dict[str, Any]] = []
        delta_sheets_changed = 0
        escalations: list[str] = []
        # Codex P1 (PR #353): modified rows the mapper dropped because
        # they lost their identity (blank WR # / week date / all cells)
        # -- their PRIOR (wr, week_ending) must still regenerate.
        dropped_row_ids_by_sheet: dict[Any, set[Any]] = {}

        def _probe(source):
            watermark = watermarks.get(source.get('id')) or {}
            last_version = watermark.get('last_sheet_version')
            last_read_at = watermark.get('last_read_at')
            rows_modified_since = (
                _fetch.compute_rows_modified_since(
                    last_read_at, SAFETY_WINDOW_MINUTES,
                )
                if last_read_at else None
            )
            return source, _fetch.fetch_sheet_delta(
                client, source, last_version, rows_modified_since,
            )

        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
            futures = [executor.submit(_probe, s) for s in delta_sources]
            for future in as_completed(futures):
                source, probe_result = future.result()
                if probe_result.get("escalate"):
                    escalations.append(
                        f"sheet {source.get('id')}: "
                        f"{probe_result.get('reason')}"
                    )
                    continue
                sheet = probe_result.get("sheet")
                if sheet is None:
                    continue  # unchanged -- zero rows, nothing to add
                delta_sheets_changed += 1
                delta_rows.extend(_fetch.map_delta_sheet_rows(
                    sheet, source,
                    dropped_row_ids=dropped_row_ids_by_sheet.setdefault(
                        source.get('id'), set(),
                    ),
                ))

        if escalations:
            return {
                "ok": False,
                "fallback_reason": (
                    "trigger_delta_probe_escalation: "
                    + "; ".join(escalations)
                ),
            }

        if full_read_sources:
            delta_rows.extend(get_all_source_rows(client, full_read_sources))

        try:
            mem_result = _run_memory_write_phase(
                delta_rows, mem_run_id, session_start,
            )
        except Exception:
            logging.warning(
                "⚠️ pipeline_memory row-write phase failed unexpectedly "
                "during PHASE 2a (non-fatal to Excel generation; "
                "resolving this run to full mode)."
            )
            return {
                "ok": False,
                "fallback_reason": (
                    "trigger_memory_write_exception: "
                    "_run_memory_write_phase raised during PHASE 2a"
                ),
            }

        # Greptile P1 (PR #351): a failed / unavailable / disabled /
        # PARTIAL memory write returns an affected set that is
        # indistinguishable from a genuine no-change run (empty) or that
        # silently under-covers what changed (partial). Refuse to narrow
        # regeneration scope on it -- widen to today's full read instead
        # (T-11-18: too wide, never too narrow). Fail-closed on a legacy
        # result dict that carries no flag at all.
        if not mem_result.get("memory_confirmed", False):
            _unconfirmed = (
                mem_result.get("unconfirmed_reason")
                or "run-memory write did not confirm every delta sheet"
            )
            logging.warning(
                "⚠️ PHASE 2a: run-memory write unconfirmed "
                f"({_unconfirmed}); the affected set cannot be trusted "
                "to scope regeneration -- resolving this run to full mode."
            )
            return {
                "ok": False,
                "fallback_reason": (
                    f"trigger_memory_write_unconfirmed: {_unconfirmed} "
                    "(an unconfirmed empty or partial affected set is "
                    "indistinguishable from a no-change run; resolving "
                    "this run to full mode)"
                ),
            }

        affected = set(mem_result.get("affected", set()) or ())

        # Codex P1 (PR #353): a modified row that lost its identity was
        # never upserted, so the RPC could not return its prior pair.
        # Look the stored identity up and widen the affected set with it;
        # a lookup that cannot confirm resolves the run to full mode.
        delta_rows_identity_lost = sum(
            len(ids) for ids in dropped_row_ids_by_sheet.values()
        )
        for _sid, _rids in dropped_row_ids_by_sheet.items():
            if not _rids:
                continue
            _prior_pairs = _mem_reader.get_row_state_pairs_for_rows(
                _sid, _rids,
            )
            if _prior_pairs is None:
                logging.warning(
                    "⚠️ PHASE 2a: could not confirm the prior identity of "
                    f"{len(_rids)} modified row(s) on sheet {_sid} that lost "
                    "their WR/week identity -- resolving this run to full "
                    "mode."
                )
                return {
                    "ok": False,
                    "fallback_reason": (
                        "trigger_prior_identity_lookup_failed: "
                        f"sheet {_sid}: {len(_rids)} identity-lost row(s) "
                        "could not be resolved to their stored "
                        "(wr, week_ending) (cannot confirm; resolving this "
                        "run to full mode)"
                    ),
                }
            if _prior_pairs:
                logging.info(
                    f"🧭 PHASE 2a: {len(_prior_pairs)} prior group(s) "
                    f"widened into the affected set from {len(_rids)} "
                    f"identity-lost row(s) on sheet {_sid}."
                )
                affected |= _prior_pairs

        if affected:
            mapped_sheet_ids = _mem_reader.map_affected_to_sheets(affected)
            if not mapped_sheet_ids:
                return {
                    "ok": False,
                    "fallback_reason": (
                        "trigger_affected_set_mapping_empty: "
                        "map_affected_to_sheets returned no sheets for a "
                        "non-empty affected set (cannot confirm; "
                        "resolving this run to full mode)"
                    ),
                }
        else:
            mapped_sheet_ids = set()

        narrowed_sheets = [
            s for s in source_sheets if s.get('id') in mapped_sheet_ids
        ]
        all_rows = (
            get_all_source_rows(client, narrowed_sheets)
            if narrowed_sheets else []
        )

        return {
            "ok": True,
            "fallback_reason": None,
            "all_rows": all_rows,
            "affected": affected,
            "mem_result": mem_result,
            "delta_rows_count": len(delta_rows),
            "delta_sheets_changed": delta_sheets_changed,
            "mapped_sheet_count": len(narrowed_sheets),
            "delta_rows_identity_lost": delta_rows_identity_lost,
        }
    except Exception as exc:
        logging.warning(
            "⚠️ PHASE 2a incremental read failed unexpectedly "
            f"({type(exc).__name__}); resolving this run to full mode."
        )
        return {
            "ok": False,
            "fallback_reason": (
                f"trigger_phase2a_unexpected_exception: "
                f"{type(exc).__name__}: {exc}"
            ),
        }


def _reconcile_deep_run_deletions(
    source_sheets: list[dict[str, Any]],
    live_row_ids_by_sheet: dict[Any, set],
    run_id: str,
    get_row_state_row_ids_fn=None,
    mark_rows_deleted_fn=None,
    failed_sheet_ids: set | None = None,
) -> dict[str, Any]:
    """Phase 11 Plan 06 (INC-03, CONTEXT.md D-03): the weekly deep run's
    deletion-reconciliation half.

    For each sheet in *source_sheets*, diffs the stored ``row_state``
    row-id set (``pipeline_memory.reader.get_row_state_row_ids``)
    against *live_row_ids_by_sheet* -- the row ids THIS run's own full
    read actually returned for that sheet (derived by the caller from
    ``all_rows``' ``__source_sheet_id`` / ``__row_id`` keys, never
    re-fetched here). A row id present in the stored set and absent
    from the live set is marked deleted via
    ``pipeline_memory.writer.mark_rows_deleted``.

    T-11-30 (critical, mitigated) -- two guards, both required:

      1. *failed_sheet_ids* (Greptile P1, PR #353): every sheet whose
         read did not complete cleanly this run -- the caller passes
         ``pipeline.fetch.get_last_full_read_failed_sheet_ids()``. A
         mid-sheet exception inside ``get_all_source_rows`` leaves a
         PARTIAL ``sheet_rows`` list that is still merged into
         ``all_rows``, so a NON-EMPTY live set is not proof of a
         complete read; such a sheet is skipped entirely (warning +
         Sentry breadcrumb, counted in ``sheets_skipped_failed_read``)
         and its ``row_state`` is left untouched for the next deep run.
      2. A sheet ABSENT from *live_row_ids_by_sheet*, or present with
         an EMPTY set, is skipped entirely (counted in
         ``sheets_skipped_zero_row``): a zero-row observation is far
         more likely an upstream failure than a mass deletion.

    Together: absence from a partial or empty read is never evidence of
    deletion; only a sheet that read cleanly AND returned rows is
    diffed. The regeneration scope can only be too wide, never too
    narrow (T-11-18).

    An EMPTY return from ``get_row_state_row_ids`` (genuinely zero rows
    stored, or a Supabase read failure -- the function's own fail-open
    contract makes the two indistinguishable) also skips that sheet's
    diff: it would be empty either way, so this is a documentation-only
    distinction, never a behavior difference.

    NEVER raises -- the caller (``main()``) wraps this call in its own
    outer try/except (mirrors every other ``pipeline_memory`` hook), and
    every per-sheet failure inside this function is itself absorbed by
    ``get_row_state_row_ids``/``mark_rows_deleted``'s own fail-open
    contracts, so one bad sheet cannot abort the loop for its siblings.

    Returns a dict: ``sheets_checked`` (sheets with a usable, non-empty
    live read this run), ``sheets_skipped_zero_row`` (sheets skipped per
    the guard above), ``rows_marked_deleted`` (total row count actually
    confirmed deleted this call, across every sheet), ``affected_pairs``
    (the union of every ``(wr, week_ending)`` pair ``mark_rows_deleted``
    returned).
    """
    get_row_state_row_ids_fn = (
        get_row_state_row_ids_fn or _mem_reader.get_row_state_row_ids
    )
    mark_rows_deleted_fn = (
        mark_rows_deleted_fn or _mem_writer.mark_rows_deleted
    )

    failed_sheet_ids = set(failed_sheet_ids or ())

    result: dict[str, Any] = {
        "sheets_checked": 0,
        "sheets_skipped_zero_row": 0,
        "sheets_skipped_failed_read": 0,
        "rows_marked_deleted": 0,
        "affected_pairs": set(),
    }

    for sheet in source_sheets:
        sheet_id = sheet.get("id")
        if sheet_id in failed_sheet_ids:
            result["sheets_skipped_failed_read"] += 1
            logging.warning(
                f"⚠️ Deep-run reconciliation: sheet {sheet_id} did not "
                "read cleanly this run (failed or partial full read) -- "
                "skipping deletion detection for this sheet; its live "
                "row set is not a complete read (T-11-30)."
            )
            sentry_add_breadcrumb(
                "pipeline_memory",
                f"Deep-run reconciliation skipped sheet {sheet_id}: "
                "failed/partial full read",
                level="warning",
                data={"sheet_id": sheet_id},
            )
            continue
        live_ids = live_row_ids_by_sheet.get(sheet_id) or set()
        if not live_ids:
            result["sheets_skipped_zero_row"] += 1
            logging.warning(
                f"⚠️ Deep-run reconciliation: sheet {sheet_id} full "
                "read returned zero rows (or was not successfully read "
                "in full) -- skipping deletion detection for this "
                "sheet this run (T-11-30: a zero/partial read is far "
                "more likely an upstream failure than a mass "
                "deletion)."
            )
            sentry_add_breadcrumb(
                "pipeline_memory",
                f"Deep-run reconciliation skipped sheet {sheet_id}: "
                "zero-row (or unread) full read",
                level="warning",
                data={"sheet_id": sheet_id},
            )
            continue

        result["sheets_checked"] += 1

        stored_ids = get_row_state_row_ids_fn(sheet_id)
        if not stored_ids:
            # Genuinely no stored rows for this sheet, or "cannot
            # confirm" -- either way the diff below is empty, so there
            # is nothing to mark deleted for this sheet this run.
            continue

        deleted_ids = stored_ids - live_ids
        if not deleted_ids:
            continue

        mark_result = mark_rows_deleted_fn(sheet_id, deleted_ids, run_id)
        count = mark_result.get("count", 0) if mark_result else 0
        pairs = mark_result.get("affected_pairs") if mark_result else None
        if count:
            result["rows_marked_deleted"] += count
        if pairs:
            result["affected_pairs"] |= pairs

    return result


def _repair_group_state_for_affected_pairs(
    affected_pairs: set,
    deferred_group_state: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Phase 11 Plan 06 (INC-03): the weekly deep run's ``group_state``
    repair for a deletion -- OBSERVABILITY only, never a second write.

    ``deferred_group_state`` (populated in the group loop -- see the
    ``_deferred_group_state.append`` call site) already carries every
    CURRENTLY-EXISTING group's freshly computed
    ``calculate_data_hash()`` value for THIS run, over ``all_rows``
    AFTER the deletion (a deleted row is simply absent from
    ``all_rows``, so ``group_source_rows()`` never assigned it to a
    group this run). The ordinary post-upload ``group_state`` flush
    (``_build_group_state_flush`` / ``upsert_group_state``) ALREADY
    upserts every one of those entries unconditionally each full run,
    with ``upsert_group_state``'s existing COALESCE-by-omission
    preserving whatever attachment id is already stored (records built
    from ``_deferred_group_state`` never carry ``attachment_id`` /
    ``attachment_name`` keys at all). This function's job is narrower:
    identify which of those entries belong to an affected
    (deletion-touched) pair, purely so the deep run can log/count
    exactly what got repaired.

    Returns the SUBSET of *deferred_group_state* whose
    ``(wr_num, week_iso)`` is in *affected_pairs* -- an empty list for
    an empty *affected_pairs* input (a deep run with zero deletions
    repairs nothing). PURE (no I/O, never raises) -- directly
    unit-testable.

    KNOWN LIMITATION (documented, not exercised by this plan's tests):
    a ``(wr, week_ending)`` pair whose LAST remaining row was deleted
    this run produces NO entry in *deferred_group_state* at all (the
    group no longer exists for ``group_source_rows()`` to build) -- its
    ``group_state`` row(s) are left stale (last-known content_hash /
    row_count) rather than actively cleared. Clearing a fully-emptied
    group's ``group_state`` row needs its stored ``target_sheet_id``(s),
    which this plan does not add a reader for; deferred to a future
    ``group_state`` hygiene pass.
    """
    if not affected_pairs:
        return []
    return [
        rec for rec in deferred_group_state
        if (rec.get("wr_num"), rec.get("week_iso")) in affected_pairs
    ]


def _compute_registry_mapping_sheets(
    is_deep_run: bool,
    source_sheets: list[dict[str, Any]],
    watermarks: dict[Any, dict[str, Any]],
) -> set | None:
    """Phase 11 Plan 06 (D-03): compute the value passed as
    ``upsert_sheet_registry``'s new ``column_mapping_sheets`` kwarg.

    ``is_deep_run`` True (``EXECUTION_TYPE == 'weekly_comprehensive'``,
    the Monday deep run by cron identity) -> ``None`` (every sheet's
    mapping is refreshed -- the deep run reads every sheet in full
    anyway, so there is no per-sheet "was it actually read" distinction
    left to make). ``is_deep_run`` False (a frequent run, or any other
    execution type) -> exactly the sheet ids ABSENT from *watermarks*
    (no existing ``sheet_registry`` row yet) -- those sheets get their
    FIRST-EVER ``column_mapping`` written on this run's INSERT (the
    column is ``NOT NULL`` with no default, so omitting it there would
    fail the whole upsert); every ALREADY-REGISTERED sheet's stored
    mapping is left untouched, so a frequent run can never silently
    adopt a drifted mapping (D-02 trigger 2 is what escalates that
    sheet to a full read instead).

    PURE (no I/O, never raises) -- directly unit-testable.
    """
    if is_deep_run:
        return None
    return {
        s.get("id") for s in source_sheets if s.get("id") not in watermarks
    }


def _log_column_mapping_drift(
    sheets: list[dict[str, Any]],
    watermarks: dict[Any, dict[str, Any]],
) -> list[Any]:
    """Phase 11 Plan 06 (INC-03/D-03): log + Sentry-breadcrumb the sheet
    ids whose freshly-discovered ``column_mapping`` differs from the
    STORED ``sheet_registry`` value, at the moment the weekly deep run
    is about to refresh it.

    Uses ``_normalize_column_mapping`` -- the SAME standalone helper
    ``resolve_run_mode``'s trigger 2 already uses for its own drift
    comparison (Phase 11 Plan 02) -- on BOTH sides, so the value
    compared here is byte-for-byte the same normalised shape trigger 2
    compares, never a second, potentially-drifting normalisation
    (11-RESEARCH.md Pitfall 6's closing half; plan 02 shipped the
    read-and-compare side, this plan adds the authoritative write).

    A sheet absent from *watermarks* entirely (no prior registry row --
    stored mapping normalises to ``{}``) is treated as drift when its
    fresh mapping is non-empty, which is correct: there is nothing
    stored yet for a brand-new sheet, so writing its first mapping is
    unconditionally logged as a "change" from nothing.

    Returns the list of sheet ids whose mapping differed (empty = no
    drift observed this run) -- directly assertable by a test without
    parsing log output. PURE aside from logging/Sentry side effects;
    never raises.
    """
    changed: list[Any] = []
    for sheet in sheets:
        sheet_id = sheet.get("id")
        fresh = _normalize_column_mapping(sheet.get("column_mapping") or {})
        stored_row = watermarks.get(sheet_id) or {}
        stored = _normalize_column_mapping(
            stored_row.get("column_mapping") or {}
        )
        if fresh != stored:
            changed.append(sheet_id)
            logging.warning(
                f"🗂️ Deep-run column_mapping refresh: sheet {sheet_id} "
                f"mapping changed. Before keys: {sorted(stored.keys())}. "
                f"After keys: {sorted(fresh.keys())}."
            )
            sentry_add_breadcrumb(
                "pipeline_memory",
                "sheet_registry.column_mapping refreshed for sheet "
                f"{sheet_id}",
                level="warning",
                data={
                    "sheet_id": sheet_id,
                    "before_keys": sorted(stored.keys()),
                    "after_keys": sorted(fresh.keys()),
                },
            )
    return changed


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
    # Kill switches + grouping mode for derive_group_identity(), bound
    # ONCE so Sites 1/2/3 cannot pass different values (PR #361 follow-up).
    _identity_switches = {
        'primary_claim_enabled': PRIMARY_CLAIM_ATTRIBUTION_ENABLED,
        'vac_crew_claim_enabled': VAC_CREW_CLAIM_ATTRIBUTION_ENABLED,
        'res_grouping_mode': RES_GROUPING_MODE,
    }
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
    # Greptile P1 (PR #351): False until _run_memory_write_phase confirms
    # every sheet this run -- gates the 11-05 shadow comparator and is
    # persisted as run_ledger.notes.mem_confirmed at both finish sites.
    _mem_memory_confirmed = False
    _mem_memory_unconfirmed_reason = None
    _mem_run_id = _mem_writer.resolve_run_id()
    # Phase 11 Plan 02 (INC-01/D-11): resolved run mode + its fallback
    # reason, hoisted for the same documented reason as the _mem_*
    # counters above -- the run_ledger_finish hooks reference these
    # unconditionally. 'full' / None is also the CORRECT value when the
    # resolve_run_mode block below never runs (RUN_MEMORY_WRITE_ENABLED
    # off, or TEST_MODE): run_ledger_start/finish already self-gate on the
    # identical condition, so these values are never actually written to
    # Supabase in that case.
    _resolved_mode = "full"
    _resolved_fallback_reason = None
    # Phase 11 Plan 04 (D-04/D-06/T-11-20): PHASE 2a/2b observability
    # counters + the "legitimately empty incremental run" sentinel,
    # hoisted for the same documented reason as the _mem_* counters
    # above -- the run_ledger_finish hooks and the post-PHASE-2
    # empty-data guards reference these unconditionally. Correct
    # defaults when PHASE 2a/2b never runs (full mode, or an early
    # exception before it): zero counters, sentinel False (an early
    # exception in full mode must still raise "No valid data rows
    # found" exactly as it does today).
    _incremental_delta_rows_count = 0
    _incremental_delta_sheets_changed = 0
    _incremental_mapped_sheet_count = 0
    _incremental_empty_affected_run = False
    # Phase 11 Plan 05 (INC-04, D-07/D-08): shadow parity verdict, hoisted
    # for the same documented reason as the _mem_* / _resolved_mode
    # defaults above -- both run_ledger_finish call sites reference these
    # unconditionally. None/empty is the CORRECT value whenever the
    # shadow hook (below, after the group loop) never runs: TEST_MODE,
    # RUN_MEMORY_WRITE_ENABLED off, RUN_MEMORY_INCREMENTAL_ENABLED on,
    # an incremental-mode run, or an early exception before the group
    # loop starts. The finish call sites only add parity_verdict/
    # parity_details to notes when _parity_verdict is not None, so a
    # None default here means "no key added", never a fabricated verdict.
    _parity_verdict = None
    _parity_details = {}
    # Phase 11 Plan 06 (INC-03): hoisted defaults for the weekly deep
    # run's deletion-reconciliation phase, for the SAME documented
    # reason as the _parity_verdict / _resolved_mode defaults above --
    # both run_ledger_finish call sites may reference these
    # unconditionally, and the reconciliation phase itself (below,
    # placed after the full read and the memory write) never runs on
    # any execution type other than 'weekly_comprehensive', or when
    # RUN_MEMORY_WRITE_ENABLED / TEST_MODE close the gate. False/0/an
    # empty set are the CORRECT values whenever the phase never runs.
    _reconcile_ran = False
    _reconcile_rows_marked_deleted = 0
    _reconcile_affected_pairs = set()
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

        # Phase 11 Plan 02 (INC-01/D-02/D-11): resolve this run's mode.
        # Needs source_sheets from PHASE 1 discovery above, which is why
        # this (and the run_ledger 'start' upsert right after it) moved
        # AFTER discovery -- the "weekly run started" Sentry log event
        # earlier in main() is unaffected; only the run_ledger 'start'
        # upsert's POSITION moved so it can carry the resolved mode
        # instead of a hard-coded "full". Guarded identically to every
        # other pipeline_memory hook (flag AND TEST_MODE) and wrapped so a
        # broken reader/resolver can never break Excel generation --
        # fail-open holds even if pipeline_memory has a bug, not just a
        # Supabase outage.
        #
        # PHASE 2 below is UNCHANGED this plan: all_rows still comes from
        # today's single get_all_source_rows() full fetch, regardless of
        # the mode resolved here -- plan 04 restructures PHASE 2 against
        # this contract once it has proven itself in shadow (D-08).
        _mem_trigger3_sheet_ids = set()
        # Phase 11 Plan 04: hoisted defaults so _run_phase2_incremental's
        # call site below can reference these unconditionally -- they are
        # only ever READ when _resolved_mode == 'incremental', which can
        # only happen after the try block below has already assigned real
        # values to both (resolve_run_mode's own incremental_enabled gate
        # is nested inside it); the except handler below always forces
        # _resolved_mode back to 'full' before these defaults could be
        # read unassigned.
        _watermarks = {}
        _per_sheet_reasons = {}
        _registry_capture_time = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        if RUN_MEMORY_WRITE_ENABLED and not TEST_MODE:
            try:
                _sheet_ids_for_watermarks = [
                    s.get('id') for s in source_sheets
                ]
                _watermarks = _mem_reader.get_sheet_watermarks(
                    _sheet_ids_for_watermarks
                )
                _last_run_status = _mem_reader.get_last_run_ledger_status()
                _resolved_mode, _resolved_fallback_reason, _per_sheet_reasons = (
                    resolve_run_mode(
                        source_sheets,
                        _watermarks,
                        _last_run_status,
                        incremental_enabled=RUN_MEMORY_INCREMENTAL_ENABLED,
                        execution_type=os.getenv('EXECUTION_TYPE', 'manual'),
                        reset_hash_history=RESET_HASH_HISTORY,
                        regen_weeks=REGEN_WEEKS,
                        reset_wr_list=RESET_WR_LIST,
                        force_generation=FORCE_GENERATION,
                    )
                )
                _mem_trigger3_sheet_ids = {
                    sid for sid, reason in _per_sheet_reasons.items()
                    if reason.startswith('trigger3_auth_error')
                }
                logging.info(
                    f"🧭 Run-memory mode resolved: {_resolved_mode}"
                    + (
                        f" (fallback_reason={_resolved_fallback_reason!r})"
                        if _resolved_fallback_reason else ""
                    )
                )
            except Exception:
                logging.warning(
                    "⚠️ pipeline_memory resolve_run_mode failed "
                    "unexpectedly (non-fatal); defaulting to mode='full' "
                    "this run."
                )
                _resolved_mode = "full"
                _resolved_fallback_reason = "trigger_resolve_exception"

        # Phase 10 (MEM-01/MEM-03): run_ledger 'start' row. Guarded by the
        # flag AND TEST_MODE (10-RESEARCH.md Pitfall 7 -- the synthetic
        # TEST_MODE path must never attempt a live Supabase call) and
        # wrapped in its own try/except so a broken writer module can
        # never break Excel generation (fail-open holds even if
        # pipeline_memory itself has a bug, not just a Supabase outage).
        # Phase 11 Plan 02: carries the resolved mode (Phase 10 hard-coded
        # "full" here -- every run WAS a full read).
        if RUN_MEMORY_WRITE_ENABLED and not TEST_MODE:
            try:
                _mem_writer.run_ledger_start(
                    _mem_run_id,
                    mode=_resolved_mode,
                    release=os.getenv('SENTRY_RELEASE', '') or '',
                )
            except Exception:
                logging.warning(
                    "⚠️ pipeline_memory run_ledger_start failed "
                    "(non-fatal); memory not written this run."
                )

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
        #
        # Phase 11 Plan 02 (D-01): every sheet not isolated by trigger 3
        # gets the SAME _registry_capture_time (captured once, immediately
        # above -- i.e. immediately before PHASE 2 below issues its reads)
        # for last_read_at, and is marked full_read=True: PHASE 2 still
        # performs today's full fetch of every sheet regardless of the
        # resolved mode, so every registry write this plan genuinely IS a
        # full read. A sheet isolated by trigger 3 is excluded from BOTH
        # registry passes entirely (neither last_read_at nor
        # last_sheet_version refreshed -- D-02 trigger 1 then forces a
        # full read of that sheet once access returns).
        _registry_sheets, _registry_capture_times, _registry_full_read_ids = (
            _build_registry_write_plan(
                source_sheets, _mem_trigger3_sheet_ids, _registry_capture_time,
            )
        )
        # Phase 11 Plan 06 (INC-03/D-03): column_mapping is refreshed on
        # BOTH sheet_registry passes ONLY on the weekly deep run
        # ('weekly_comprehensive' by cron identity, per CLAUDE.md's
        # cron-identity-not-wall-clock rule) -- a frequent run must
        # NEVER silently adopt a drifted mapping; D-02 trigger 2 already
        # escalates that sheet to a full read instead. NOT NULL safety
        # (see _compute_registry_mapping_sheets docstring): a sheet with
        # NO existing registry row still gets its first-ever mapping
        # written regardless of execution type.
        _is_deep_run = (
            os.getenv('EXECUTION_TYPE', 'manual') == 'weekly_comprehensive'
        )
        _registry_mapping_sheets = _compute_registry_mapping_sheets(
            _is_deep_run, source_sheets, _watermarks,
        )
        if RUN_MEMORY_WRITE_ENABLED and not TEST_MODE:
            try:
                _mem_writer.upsert_sheet_registry(
                    _registry_sheets, _mem_run_id, _resolve_mem_sheet_kind,
                    _fetch.get_last_sheet_versions(),
                    capture_times=_registry_capture_times,
                    full_read_sheets=_registry_full_read_ids,
                    column_mapping_sheets=_registry_mapping_sheets,
                    watermarks=_watermarks,
                )
            except Exception:
                logging.warning(
                    "⚠️ pipeline_memory sheet_registry upsert (pass 1) "
                    "failed unexpectedly (non-fatal); registry not "
                    "written this pass."
                )

        # Get all source rows.
        #
        # Phase 11 Plan 04 (D-04 Option C): incremental mode splits this
        # into a delta read (PHASE 2a) + a scoped full re-fetch (PHASE
        # 2b) via the standalone _run_phase2_incremental helper below.
        # Full mode is BYTE-FOR-BYTE the pre-Plan-04 single-call path --
        # same Sentry span name, same log banner, same
        # get_all_source_rows call -- and is also where an incremental
        # run lands after ANY PHASE 2a/2b failure (fail-open: the scope
        # can only widen, never narrow -- T-11-18).
        _phase_start = datetime.datetime.now()
        logging.info(f"\n{'='*60}")
        logging.info("📋 PHASE 2: Fetching source data...")
        logging.info(f"{'='*60}")

        if _resolved_mode == 'incremental':
            with sentry_sdk.start_span(
                op="smartsheet.fetch_rows_incremental",
                name="PHASE 2a/2b: incremental delta read + scoped re-fetch",
            ) as span:
                _phase2_result = _run_phase2_incremental(
                    client, source_sheets, _watermarks, _per_sheet_reasons,
                    _mem_run_id, session_start,
                )
                span.set_data("ok", _phase2_result.get("ok", False))
            if _phase2_result.get("ok"):
                all_rows = _phase2_result["all_rows"]
                _mem_result = _phase2_result["mem_result"]
                _mem_affected = _mem_result.get("affected", set())
                _incremental_delta_rows_count = (
                    _phase2_result["delta_rows_count"]
                )
                _incremental_delta_sheets_changed = (
                    _phase2_result["delta_sheets_changed"]
                )
                _incremental_mapped_sheet_count = (
                    _phase2_result["mapped_sheet_count"]
                )
                _incremental_empty_affected_run = not _mem_affected
                _mem_sheets_written = _mem_result["sheets_written"]
                _mem_sheets_errored = _mem_result["sheets_errored"]
                _mem_rows_sent = _mem_result["rows_sent"]
                _mem_rows_changed = _mem_result["rows_changed"]
                _mem_memory_confirmed = bool(
                    _mem_result.get("memory_confirmed", False)
                )
                _mem_memory_unconfirmed_reason = _mem_result.get(
                    "unconfirmed_reason"
                )
                logging.info(
                    f"🧭 PHASE 2a/2b complete: "
                    f"{_incremental_delta_rows_count} delta row(s) "
                    f"across {_incremental_delta_sheets_changed} changed "
                    f"sheet(s); PHASE 2b re-fetched "
                    f"{_incremental_mapped_sheet_count} sheet(s), "
                    f"{len(all_rows)} row(s)."
                )
            else:
                _resolved_mode = 'full'
                _resolved_fallback_reason = _phase2_result.get(
                    "fallback_reason"
                )
                logging.warning(
                    "⚠️ PHASE 2a/2b incremental read fell back to full "
                    f"mode: {_resolved_fallback_reason}"
                )

        if _resolved_mode == 'full':
            with sentry_sdk.start_span(op="smartsheet.fetch_rows", name="Fetch all source rows from Smartsheet") as span:
                all_rows = get_all_source_rows(client, source_sheets)
                span.set_data("source_sheets_count", len(source_sheets))
                span.set_data("rows_fetched", len(all_rows) if all_rows else 0)
        
        if not all_rows and not _incremental_empty_affected_run:
            raise Exception("No valid data rows found")
        
        _phase_elapsed = (datetime.datetime.now() - _phase_start).total_seconds()
        logging.info(f"⚡ Phase 2 complete: {len(all_rows)} rows fetched from {len(source_sheets)} sheets in {_phase_elapsed:.1f}s")
        sentry_add_breadcrumb("data", f"Fetched {len(all_rows)} source rows from {len(source_sheets)} sheets", data={
            "row_count": len(all_rows),
            "sheet_count": len(source_sheets),
        })

        # Phase 10 (MEM-02/MEM-03): per-sheet row-state shadow write.
        # Full mode ONLY (Phase 11 Plan 04) -- in incremental mode this
        # already happened inside _run_phase2_incremental (PHASE 2a fed
        # it the delta rows, not all_rows); a PHASE 2a/2b failure above
        # already reset _resolved_mode to 'full', so that fallback case
        # runs this block exactly like today. _run_memory_write_phase
        # self-gates on RUN_MEMORY_WRITE_ENABLED / TEST_MODE (mirrors the
        # run_ledger start/finish hooks' defense-in-depth double gate)
        # and never raises on its own -- this try/except is a second,
        # outer belt so an unexpected bug in the phase itself can never
        # reach the audit/grouping/Excel path below (fail-open holds
        # even if pipeline_memory has a bug, not just a Supabase
        # outage).
        if _resolved_mode == 'full':
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
            _mem_memory_confirmed = bool(
                _mem_result.get("memory_confirmed", False)
            )
            _mem_memory_unconfirmed_reason = _mem_result.get(
                "unconfirmed_reason"
            )

        # Phase 10 (MEM-01): sheet_registry shadow write, PASS 2. Now that
        # Phase 2 has fetched every sheet, pipeline.fetch's version-
        # watermark map is populated -- same guard, same fail-open
        # contract, same idempotent upsert key as pass 1 above.
        #
        # Phase 11 Plan 02 (D-01): reuses the SAME _registry_sheets /
        # _registry_capture_times / _registry_full_read_ids computed at
        # pass 1 above -- last_read_at must stay the capture-time instant
        # taken BEFORE the read was issued, never a fresh "now" recomputed
        # here after the read has already completed.
        if RUN_MEMORY_WRITE_ENABLED and not TEST_MODE:
            try:
                if _is_deep_run:
                    _log_column_mapping_drift(_registry_sheets, _watermarks)
                _mem_writer.upsert_sheet_registry(
                    _registry_sheets, _mem_run_id, _resolve_mem_sheet_kind,
                    _fetch.get_last_sheet_versions(),
                    capture_times=_registry_capture_times,
                    full_read_sheets=_registry_full_read_ids,
                    column_mapping_sheets=_registry_mapping_sheets,
                    watermarks=_watermarks,
                )
            except Exception:
                logging.warning(
                    "⚠️ pipeline_memory sheet_registry upsert (pass 2) "
                    "failed unexpectedly (non-fatal); registry version "
                    "watermark not updated this run."
                )

        # Phase 11 Plan 06 (INC-03, CONTEXT.md D-03): the weekly deep
        # run's deletion-reconciliation phase -- placed after BOTH the
        # full read (all_rows, above) and the memory write
        # (_run_memory_write_phase, above) complete, so a failed read
        # or a failed memory write can never cause a false deletion.
        # Gated on _is_deep_run (EXECUTION_TYPE == 'weekly_comprehensive'
        # by cron identity, NOT wall clock) PLUS the same
        # RUN_MEMORY_WRITE_ENABLED / TEST_MODE double gate every other
        # pipeline_memory hook in main() uses. Wrapped in its own outer
        # try/except (mirrors every other hook here) so an unexpected
        # bug can never affect Excel generation, upload, or cleanup
        # below.
        # Greptile P1 (PR #353): additionally gated on the resolved mode
        # being 'full' -- the live row-id set below is derived from
        # all_rows, which is only a complete per-sheet read in full mode
        # (PHASE 2b's narrowed rows would look like a mass deletion).
        if (
            _is_deep_run
            and _resolved_mode == 'full'
            and RUN_MEMORY_WRITE_ENABLED
            and not TEST_MODE
        ):
            try:
                _reconcile_live_ids_by_sheet = {}
                for _rr in all_rows:
                    _rsid = _rr.get('__source_sheet_id')
                    _rrid = _rr.get('__row_id')
                    if _rsid is not None and isinstance(_rrid, int):
                        _reconcile_live_ids_by_sheet.setdefault(
                            _rsid, set()
                        ).add(_rrid)

                _reconcile_result = _reconcile_deep_run_deletions(
                    source_sheets, _reconcile_live_ids_by_sheet, _mem_run_id,
                    # Greptile P1 (PR #353): sheets whose full read failed
                    # or was only partially processed are never diffed.
                    failed_sheet_ids=_fetch.get_last_full_read_failed_sheet_ids(),
                )
                _reconcile_ran = True
                _reconcile_affected_pairs = _reconcile_result[
                    'affected_pairs'
                ]
                _reconcile_rows_marked_deleted = _reconcile_result[
                    'rows_marked_deleted'
                ]
                if _reconcile_rows_marked_deleted:
                    logging.info(
                        f"🗑️ Deep-run reconciliation: "
                        f"{_reconcile_rows_marked_deleted} row(s) marked "
                        "deleted across "
                        f"{_reconcile_result['sheets_checked']} sheet(s) "
                        "checked "
                        f"({_reconcile_result['sheets_skipped_zero_row']} "
                        "sheet(s) skipped: zero-row full read; "
                        f"{_reconcile_result['sheets_skipped_failed_read']} "
                        "skipped: failed/partial read)."
                    )
            except Exception:
                logging.warning(
                    "⚠️ pipeline_memory deep-run deletion reconciliation "
                    "failed unexpectedly (non-fatal); "
                    "row_state.deleted_at not written this run."
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
            # Phase 11 Plan 04 (D-04): incremental-mode-only restriction to
            # the affected (WR, week) pairs, applied AFTER the unmodified
            # group_source_rows() call -- group_source_rows(),
            # pricing.py, attribution.py and excel.py are never modified;
            # only their input (here, which KEYS survive) is scoped. A
            # group either survives in full or is dropped entirely -- no
            # second grouping/Excel codepath (D-04's central promise).
            if _resolved_mode == 'incremental':
                _pre_filter_group_count = len(groups) if groups else 0
                groups = _filter_groups_to_affected(groups, _mem_affected)
                _post_filter_group_count = len(groups) if groups else 0
                span.set_data(
                    "pre_filter_group_count", _pre_filter_group_count
                )
                span.set_data(
                    "post_filter_group_count", _post_filter_group_count
                )
                logging.info(
                    f"🧭 Incremental group filter: "
                    f"{_pre_filter_group_count} -> "
                    f"{_post_filter_group_count} group(s) "
                    "(affected-set restricted)"
                )

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
        
        if not groups and not _incremental_empty_affected_run:
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
        # Sanitized WR keys the builder REMOVED for target-sheet collisions
        # (PR #365): such a WR HAS target rows, so the no-target-row skip
        # must never classify it as a missing source row.
        _target_map_quarantined: frozenset[str] = frozenset()
        if not TEST_MODE:
            with sentry_sdk.start_span(op="smartsheet.target_map", name="Create target sheet map for uploads") as span:
                (
                    target_map, _target_sheet_obj, _target_map_quarantined,
                ) = create_target_sheet_map_with_quarantine(
                    client, TARGET_SHEET_ID,
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

        # ──────────────────────────────────────────────────────────
        # Phase 11 Plan 08 (INC-05 retirement, CONTEXT.md D-12): the bulk
        # Smartsheet attachment pre-fetch (two phases: TARGET_SHEET_ID rows,
        # then SUBCONTRACTOR_PPP_SHEET_ID rows, plus their three
        # ATTACHMENT_PREFETCH_* sub-budget constants) is retired.
        # pipeline_memory.group_state already carries the attachment_id /
        # attachment_name this pipeline itself uploaded for every group it
        # has flushed (shadow-populated Phase 10, proven on the flip PR's
        # first real upload -- IN-01), so attachment identity is resolved
        # from there instead of a bulk Smartsheet call.
        #
        # Safety invariant (T-11-41): the consumer below
        # (pipeline.cleanup.delete_old_excel_attachments) already accepts
        # a missing cache entry and falls back, unmodified, to a per-row
        # on-demand `list_row_attachments` lookup -- that existing
        # fallback is what makes this retirement safe on a cold cache, a
        # Supabase outage, or a WR group_state has never flushed.
        # group_state's coverage is necessarily narrower than "every
        # attachment on the row" (it only knows what THIS pipeline
        # wrote), so cleanup_untracked_sheet_attachments -- which prunes
        # off-contract / duplicate / legacy attachments group_state was
        # never told about -- deliberately never reads this cache; see
        # the `_cleanup_cache = None` assignment below.
        #
        # Existence is different from identity (PR #373 review): the
        # unchanged-group skip gate (_has_existing_week_attachment) never
        # reads these stubs -- a stub proves only what was last uploaded,
        # so a manually deleted attachment would keep the group skipped
        # with its billing report missing. That gate confirms against
        # _live_row_attachments (one memoized live listing per row).
        # ──────────────────────────────────────────────────────────
        attachment_cache = {}  # row_id -> list of attachment-like objects
        # row_id -> LIVE list_row_attachments listing (skip-gate
        # confirmation; populated lazily by _live_row_attachments)
        _live_attachment_listings: dict = {}
        if not TEST_MODE:
            _group_state_wrs = set(target_map or {}) | set(target_map_ppp or {})
            if _group_state_wrs:
                with sentry_sdk.start_span(
                    op="pipeline_memory.group_state_attachments",
                    name="Resolve attachment identity from group_state",
                ) as gsa_span:
                    _gsa_start = datetime.datetime.now()
                    _resolved_by_wr = _mem_reader.get_group_state_attachments_by_wr(
                        _group_state_wrs
                    )
                    _gsa_cached = 0
                    for _wr, _entries in _resolved_by_wr.items():
                        for _entry in _entries:
                            _stub_row_id = None
                            if (
                                target_map
                                and _entry['target_sheet_id'] == TARGET_SHEET_ID
                            ):
                                _stub_row = target_map.get(_wr)
                                if _stub_row is not None:
                                    _stub_row_id = _stub_row.id
                            elif (
                                target_map_ppp
                                and _entry['target_sheet_id']
                                == SUBCONTRACTOR_PPP_SHEET_ID
                            ):
                                _stub_row = target_map_ppp.get(_wr)
                                if _stub_row is not None:
                                    _stub_row_id = _stub_row.id
                            if _stub_row_id is None:
                                continue
                            attachment_cache.setdefault(_stub_row_id, []).append(
                                _GroupStateAttachmentStub(
                                    _entry['attachment_id'],
                                    _entry['attachment_name'],
                                )
                            )
                            _gsa_cached += 1
                    _gsa_elapsed = (
                        datetime.datetime.now() - _gsa_start
                    ).total_seconds()
                    gsa_span.set_data("wrs_resolved", len(_resolved_by_wr))
                    gsa_span.set_data("attachments_cached", _gsa_cached)
                    logging.info(
                        f"🧾 Resolved {_gsa_cached} attachment identities "
                        f"from group_state for {len(_resolved_by_wr)} WRs "
                        f"in {_gsa_elapsed:.1f}s (per-row on-demand "
                        f"fallback covers every miss)"
                    )

        # ─────────────────────────────────────────────────────────
        # Phase 11 Plan 08 (INC-05 retirement, CONTEXT.md D-12):
        # the local hash-history JSON cache file is retired.
        # pipeline_memory.group_state.content_hash is now the sole local
        # change-detection skip gate; the four one-time migration prunes
        # below (Phase 1.1 / Subproject B / Subproject C / Subproject D)
        # operated on the retired hash_history dict and are removed --
        # their kill-switch version constants and helper functions stay
        # defined in pipeline/attribution.py (out of scope, harmless
        # uncalled) but are no longer invoked here. Batch-fetch this run's
        # group_state content hashes ONCE, mirroring the group_state
        # attachment-identity pre-fetch above, so the skip-decision loop
        # below does zero-I/O in-memory lookups per group.
        # ─────────────────────────────────────────────────────────
        _group_state_hashes: dict = {}
        if not TEST_MODE and _group_state_wrs:
            with sentry_sdk.start_span(
                op="pipeline_memory.group_state_hashes",
                name="Resolve content hashes from group_state",
            ) as gsh_span:
                _gsh_start = datetime.datetime.now()
                _hash_rows_by_wr = _mem_reader.get_group_state_content_hashes_by_wr(
                    _group_state_wrs
                )
                for _wr, _entries in _hash_rows_by_wr.items():
                    for _entry in _entries:
                        _week_ending = _entry.get('week_ending')
                        _week_ending_iso = (
                            _week_ending.isoformat()
                            if hasattr(_week_ending, 'isoformat')
                            else (_week_ending or '')
                        )
                        _key = (
                            f"{_wr}|{_week_ending_iso}|"
                            f"{_entry.get('variant') or ''}|"
                            f"{_entry.get('identifier') or ''}"
                        )
                        _group_state_hashes[_key] = {
                            'hash': _entry.get('content_hash'),
                        }
                _gsh_elapsed = (
                    datetime.datetime.now() - _gsh_start
                ).total_seconds()
                gsh_span.set_data("wrs_resolved", len(_hash_rows_by_wr))
                gsh_span.set_data("hashes_cached", len(_group_state_hashes))
                logging.info(
                    f"🧾 Resolved {len(_group_state_hashes)} content hashes "
                    f"from group_state for {len(_hash_rows_by_wr)} WRs in "
                    f"{_gsh_elapsed:.1f}s"
                )

        # Phase 11 Plan 08 (INC-05, D-12): generated_docs/billing_audit_
        # frozen_rows.json is retired. freeze_row / freeze_attribution are
        # already idempotent ("first-write-wins", billing_audit/schema.sql),
        # so this run-scoped dedupe set now starts empty every run instead
        # of being warm-started from a persisted file -- the only cost is a
        # few redundant (but safe) RPC calls per run.
        billing_audit_row_cache: set[str] = set()
        billing_audit_row_cache_dirty = False
        history_updates = 0
        _groups_skipped = 0
        _groups_skipped_no_target = 0
        # Groups NOT generated because the WR has no target-sheet row
        # (owner decision 2026-08-28).
        _no_target_row_groups: NoTargetRowGroups = {}
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
        # Phase 11 Plan 05 (INC-04, D-07): every processed group's
        # calculate_data_hash() value, captured unconditionally (a single
        # dict assignment per group, negligible cost) so the shadow-parity
        # candidate side -- which spans groups that may have been SKIPPED
        # as unchanged, not just the ones _deferred_group_state records --
        # can be compared without a second calculate_data_hash() call.
        _shadow_group_hashes = {}
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
        # exists" forever (root cause of the WR 11951363 / week 070526
        # incident, failed run 28752355941).
        _deferred_hash_upserts = []

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

        # Owner decision 2026-08-28 (no-target-row skip), risk-review
        # hardening: the primary target map was loaded ONCE, eagerly, at
        # the "Create target sheet map for production uploads" site above
        # (every non-TEST run). Record that ATTEMPT -- not whether rows
        # came back -- so an unreachable / empty / malformed sheet is
        # never re-fetched per group (the loader swallows errors and
        # returns {}). The circuit breaker runs BEFORE the loop over the
        # UNSCOPED fetched rows: a populated-but-partial map must fail
        # open to the pre-existing generate-and-warn behaviour.
        _target_map_load_attempted = not TEST_MODE
        _no_target_gate_on = False
        if ATTACHMENT_REQUIRED_FOR_SKIP and not TEST_MODE and not SKIP_UPLOAD:
            (
                _no_target_gate_on, _nt_missing, _nt_universe, _nt_ratio,
            ) = no_target_row_gate_enabled(
                all_rows, target_map,
                max_miss_ratio=NO_TARGET_ROW_MAX_MISS_RATIO,
                quarantined=_target_map_quarantined,
            )
            if target_map and not _no_target_gate_on:
                logging.error(
                    f"🛑 No-target-row skip DISABLED for this run: "
                    f"{_nt_missing} of {_nt_universe} Work Request values "
                    f"({_nt_ratio:.0%}) are absent from target sheet "
                    f"{TARGET_SHEET_ID}, above "
                    f"NO_TARGET_ROW_MAX_MISS_RATIO="
                    f"{NO_TARGET_ROW_MAX_MISS_RATIO:.2f}. The target map "
                    f"is probably partial or wrong (sheet id / sharing); "
                    f"falling back to generate-and-warn."
                )
                sentry_add_breadcrumb(
                    "group", "No-target-row skip disabled (miss ratio)",
                    level="error", data={
                        "missing": _nt_missing, "universe": _nt_universe,
                        "ratio": round(_nt_ratio, 3),
                    },
                )

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
                # Phase 11 Plan 05 (D-07): capture EVERY processed group's
                # hash for the shadow-parity candidate side (see
                # _shadow_group_hashes docstring above) -- never a second
                # calculate_data_hash() call, just recording the value
                # already computed on the line above.
                _shadow_group_hashes[group_key] = data_hash
                wr_num_raw = group_rows[0].get('Work Request #')
                wr_num = str(wr_num_raw).split('.')[0] if wr_num_raw else ''
                # Apply the same filesystem-safety sanitizer used inside
                # generate_excel so history keys, attachment prefix
                # matching, and Excel filenames all use the identical
                # WR identifier. Realistic numeric WR#s are unchanged;
                # path-traversal metacharacters get replaced with ``_``.
                wr_num = _RE_SANITIZE_HELPER_NAME.sub('_', wr_num)[:50]
                week_raw = group_key.split('_',1)[0] if '_' in group_key else ''

                # Extract variant and identifier for variant-aware hash
                # history. Every identity-bearing field below (helper
                # dept / job, claimer, User) is read from the row
                # calculate_data_hash treats as first -- the same row
                # generate_excel reads for its header -- never from
                # arrival-order group_rows[0]: the helper group key carries
                # no dept/job, so one group can hold rows from two
                # departments, and a stable hash must be looked up under a
                # stable history_key or the group regenerates and
                # re-uploads every run (Codex / Copilot, PR #361). Sites 2
                # and 3 derive from the same canonical row.
                first_row = canonical_first_row(group_rows)
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
                # CR-01 gap closure (Site 1 — main-loop identifier /
                # history_key / file_identifier): the identity is the ONE
                # shared definition, derive_group_identity() -- Sites 2 and 3
                # call the same function, so the three sites cannot drift
                # (Copilot on PR #361; CR-01 documents the bug shape).
                identifier, file_identifier = derive_group_identity(
                    first_row, **_identity_switches)

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

                # Phase 11 Plan 08 (INC-05, D-12): history_key is now keyed
                # by week_iso (matching group_state.week_ending, a DATE
                # column) rather than week_raw (MMDDYY) -- the retired
                # local hash-history JSON cache used week_raw because it
                # was the only week value computed at this point;
                # group_state's PK uses the ISO date, so the lookup key
                # must too.
                history_key = f"{wr_num}|{week_iso}|{variant}|{identifier}"

                # Pre-compute hash-change state before any optional side-effects.
                # Billing audit RPCs are the single most expensive per-group operation
                # in steady state, so we can safely skip them when the group hash is
                # unchanged versus group_state.content_hash (no row-content drift to
                # freeze or emit).
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
                # back to the group_state-sourced local cache on outage/miss
                # (Phase 11 Plan 08 / INC-05 -- the local hash-history JSON
                # cache is retired). See _resolve_unchanged_for_skip for
                # the full decision table. Default (authoritative OFF) is
                # group_state-cache-only.
                _hash_unchanged = (
                    _resolve_unchanged_for_skip(
                        history_key, data_hash, _group_state_hashes,
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

                # Owner decision 2026-08-28: a WR with no target-sheet
                # row is a data-entry error -- not generated, listed as
                # an error (see should_skip_no_target_row). Sits BEFORE
                # the billing-audit freeze / fingerprint block and the
                # hash decision, so such a group is neither tracked in
                # Supabase nor generated, whether or not its data
                # changed. The WARNING starts with the registered
                # ``_PII_LOG_MARKERS`` text "Work request " so the
                # Sentry breadcrumb is dropped; the Actions log keeps it.
                if (
                    _no_target_gate_on
                    and should_skip_no_target_row(
                        wr_num, target_map,
                        attachment_required=ATTACHMENT_REQUIRED_FOR_SKIP,
                        test_mode=TEST_MODE, skip_upload=SKIP_UPLOAD,
                        quarantined=_target_map_quarantined,
                    )
                ):
                    _no_target_row_groups[group_key] = (
                        wr_num, week_raw, variant,
                    )
                    _groups_skipped_no_target += 1
                    logging.warning(
                        f"⛔ Skip (no target-sheet row): Work request "
                        f"{wr_num} week {week_raw} {variant} -- "
                        f"data-entry error on the source sheet; NOT "
                        f"generated"
                    )
                    sentry_add_breadcrumb(
                        "group", "Skipped: no target-sheet row",
                        level="warning", data={
                            "wr": wr_num, "week": week_raw,
                            "variant": variant,
                        },
                    )
                    continue

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
                            if (
                                not target_map
                                and not _target_map_load_attempted
                            ):
                                _target_map_load_attempted = True
                                target_map, _target_sheet_obj = (
                                    create_target_sheet_map(client)
                                )
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
                                # PR #373 review: confirm existence
                                # against a LIVE listing (memoized per
                                # row), never the group_state stubs --
                                # a stub survives a manual deletion.
                                has_attachment = _has_existing_week_attachment(
                                    client, TARGET_SHEET_ID, target_row,
                                    str(wr_num), week_raw, variant,
                                    file_identifier,
                                    cached_attachments=_live_row_attachments(
                                        client, TARGET_SHEET_ID,
                                        target_row.id,
                                        _live_attachment_listings,
                                    ),
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
                                        cached_attachments=(
                                            _live_row_attachments(
                                                client,
                                                SUBCONTRACTOR_PPP_SHEET_ID,
                                                _ppp_skip_row.id,
                                                _live_attachment_listings,
                                            )
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

                # Phase 11 Plan 08 (INC-05, D-12): the local hash-history
                # JSON cache is retired. group_state.content_hash (via the existing
                # _deferred_group_state append below) is now the sole local
                # change-detection record. TEST_MODE has no upload phase to
                # defer against (and _deferred_group_state is itself gated
                # `not TEST_MODE`), so history_updates advances immediately
                # here for TEST_MODE, exactly mirroring its pre-retirement
                # immediate-write count; the production count is derived from
                # the group_state flush outcome below (mirrors the "hash
                # advances only after ALL upload legs succeed" contract the
                # retired json cache obeyed).
                if TEST_MODE:
                    history_updates += 1

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
        logging.info(
            f"⚡ Group processing phase: {_groups_generated} generated, "
            f"{_groups_skipped} skipped, {_groups_skipped_no_target} not "
            f"generated (no target-sheet row) in {_phase_group_elapsed:.1f}s"
            + (" (stopped early — time budget exceeded)"
               if _time_budget_exceeded else "")
        )
        if _no_target_row_groups:
            _nt_error_line, _nt_values_line = format_no_target_row_summary(
                _no_target_row_groups, TARGET_SHEET_ID,
            )
            logging.error(_nt_error_line)
            logging.warning(_nt_values_line)
            sentry_add_breadcrumb(
                "group", "Groups not generated: no target-sheet row",
                level="error", data={
                    "groups": len(_no_target_row_groups),
                    "work_requests": len(
                        {v[0] for v in _no_target_row_groups.values()}
                    ),
                },
            )

        # Phase 11 Plan 05 (INC-04, CONTEXT.md D-07/D-08): shadow-
        # incremental parity proof. Runs ONLY while
        # RUN_MEMORY_INCREMENTAL_ENABLED is OFF and RUN_MEMORY_WRITE_
        # ENABLED is ON (D-07) -- the full read this run already produced
        # is compared against what the incremental path WOULD have
        # regenerated from this run's own affected set. pipeline/
        # parity.py computes and compares only; it never alters what this
        # run generates, uploads, or deletes. Sub-budgeted exactly like
        # _run_memory_write_phase's own pre-flight guard so it can never
        # threaten TIME_BUDGET_MINUTES; a comparison that could not fully
        # execute is 'skipped' with a reason -- never a vacuous 'pass'.
        # Wrapped in its own outer try/except (belt-and-suspenders,
        # mirrors every other pipeline_memory hook in main()) so an
        # unexpected bug here can never affect Excel generation, upload,
        # or cleanup, which have ALL already completed processing their
        # decisions for this run's groups by this point in source order.
        if (
            _resolved_mode == 'full'
            and RUN_MEMORY_WRITE_ENABLED
            and not RUN_MEMORY_INCREMENTAL_ENABLED
            and not TEST_MODE
        ):
            try:
                _shadow_elapsed_min = (
                    (datetime.datetime.now() - session_start).total_seconds()
                    / 60.0
                )
                _shadow_remaining_min = (
                    TIME_BUDGET_MINUTES - _shadow_elapsed_min
                )
                _shadow_required_min = (
                    RUN_MEMORY_SHADOW_MAX_MINUTES
                    + RUN_MEMORY_SHADOW_GENERATION_HEADROOM_MIN
                )
                if (
                    TIME_BUDGET_MINUTES
                    and GITHUB_ACTIONS_MODE
                    and _shadow_remaining_min <= _shadow_required_min
                ):
                    logging.warning(
                        f"⏩ Skipping shadow parity check: "
                        f"{_shadow_elapsed_min:.1f}min already elapsed, "
                        f"only {_shadow_remaining_min:.1f}min left in "
                        f"session budget (need > {_shadow_required_min}min "
                        f"= {RUN_MEMORY_SHADOW_MAX_MINUTES}min shadow "
                        f"budget + "
                        f"{RUN_MEMORY_SHADOW_GENERATION_HEADROOM_MIN}min "
                        "generation headroom)."
                    )
                    sentry_add_breadcrumb(
                        "pipeline_memory",
                        "Shadow parity check skipped, "
                        f"{_shadow_remaining_min:.1f}min remaining",
                        level="warning",
                        data={
                            "elapsed_min": round(_shadow_elapsed_min, 1),
                            "remaining_min": round(_shadow_remaining_min, 1),
                            "required_remaining_min": _shadow_required_min,
                        },
                    )
                    _parity_verdict = "skipped"
                    _parity_details = {
                        "reason": "insufficient_session_budget",
                    }
                elif not _mem_memory_confirmed:
                    # Greptile P1 (PR #351): the candidate side of the
                    # comparison IS this run's memory-write affected set.
                    # If that write was not confirmed, the candidate is
                    # empty or partial for a transport reason, and a
                    # comparison against it would report a spurious
                    # parity 'fail' (or a vacuous 'pass' on a quiet run)
                    # about a write outage, not about the selector.
                    # D-07: a comparison that could not execute reports
                    # 'skipped' with a reason -- never a false verdict.
                    logging.warning(
                        "⏩ Skipping shadow parity check: run-memory write "
                        "unconfirmed this run "
                        f"({_mem_memory_unconfirmed_reason})."
                    )
                    sentry_add_breadcrumb(
                        "pipeline_memory",
                        "Shadow parity check skipped, memory write "
                        "unconfirmed",
                        level="warning",
                        data={
                            "reason": _mem_memory_unconfirmed_reason,
                            "mem_sheets_errored": _mem_sheets_errored,
                        },
                    )
                    _parity_verdict = "skipped"
                    _parity_details = {
                        "reason": "memory_write_unconfirmed",
                        "detail": _mem_memory_unconfirmed_reason,
                    }
                else:
                    _shadow_candidate_groups = _filter_groups_to_affected(
                        groups, _mem_affected,
                    )
                    _shadow_candidate_hashes = {
                        gk: _shadow_group_hashes.get(gk)
                        for gk in _shadow_candidate_groups
                    }
                    # "Actual" = generated groups with an upload task;
                    # generated-but-withheld groups (no target-sheet row,
                    # e.g. the quarantined garbage-name set) are dropped
                    # from both sides -- see _shadow_parity_input_sets.
                    (
                        _shadow_candidate_hashes,
                        _shadow_actual_hashes,
                        _shadow_withheld_excluded,
                    ) = _shadow_parity_input_sets(
                        _shadow_candidate_hashes,
                        _deferred_group_state,
                        _upload_tasks,
                        unobservable=set(_no_target_row_groups),
                    )
                    _shadow_group_result = _parity.compare_shadow_parity(
                        _shadow_candidate_hashes, _shadow_actual_hashes,
                    )
                    _shadow_changed_row_ids = (
                        _parity.get_changed_row_ids_by_sheet(_mem_run_id)
                    )
                    _shadow_read_result = _parity.run_shadow_delta_reads(
                        client=client,
                        source_sheets=source_sheets,
                        watermarks=_watermarks,
                        changed_row_ids_by_sheet=_shadow_changed_row_ids,
                        session_start=session_start,
                        fetch_sheet_delta_fn=_fetch.fetch_sheet_delta,
                        compute_rows_modified_since_fn=(
                            _fetch.compute_rows_modified_since
                        ),
                        safety_window_minutes=SAFETY_WINDOW_MINUTES,
                        max_minutes=RUN_MEMORY_SHADOW_MAX_MINUTES,
                        rpc_timeout_sec=RUN_MEMORY_SHADOW_RPC_TIMEOUT_SEC,
                        generation_headroom_min=(
                            RUN_MEMORY_SHADOW_GENERATION_HEADROOM_MIN
                        ),
                        time_budget_minutes=TIME_BUDGET_MINUTES,
                        github_actions_mode=GITHUB_ACTIONS_MODE,
                        parallel_workers=PARALLEL_WORKERS,
                    )
                    _parity_verdict = _parity.combine_verdicts(
                        _shadow_group_result["verdict"],
                        _shadow_read_result["read_verdict"],
                    )
                    _parity_details = {
                        "group": _shadow_group_result,
                        "read": _shadow_read_result,
                        "actual_withheld_excluded": _shadow_withheld_excluded,
                    }
                    if _parity_verdict == "fail":
                        logging.error(
                            "🚨 Shadow parity FAIL — incremental candidate "
                            "set diverges from the full run's actual "
                            "output (groups_compared="
                            f"{_shadow_group_result.get('groups_compared')}, "
                            f"run_id={_mem_run_id})."
                        )
                        sentry_capture_message_with_context(
                            "Shadow-incremental parity FAIL",
                            level="error",
                            context_name="parity_shadow",
                            context_data={
                                "run_id": _mem_run_id,
                                "group_verdict": (
                                    _shadow_group_result.get("verdict")
                                ),
                                "read_verdict": (
                                    _shadow_read_result.get("read_verdict")
                                ),
                                "groups_compared": (
                                    _shadow_group_result.get(
                                        "groups_compared",
                                    )
                                ),
                                "candidate_count": (
                                    _shadow_group_result.get(
                                        "candidate_count",
                                    )
                                ),
                                "actual_count": (
                                    _shadow_group_result.get("actual_count")
                                ),
                            },
                            tags={"parity_verdict": "fail"},
                        )
            except Exception as _parity_exc:
                logging.warning(
                    "⚠️ Shadow parity check failed unexpectedly "
                    f"(non-fatal): {type(_parity_exc).__name__}"
                )
                _parity_verdict = "skipped"
                _parity_details = {
                    "reason": (
                        f"unexpected_exception: "
                        f"{type(_parity_exc).__name__}"
                    ),
                }

        # Phase 11 Plan 06 (INC-03): the weekly deep run's group_state
        # repair confirmation -- OBSERVABILITY only (see
        # _repair_group_state_for_affected_pairs docstring: the
        # ordinary post-upload group_state flush below already upserts
        # every surviving group's freshly-computed content_hash this
        # run, attachment ids preserved by upsert_group_state's
        # existing COALESCE-by-omission). Runs only when the
        # deletion-reconciliation phase above actually marked something
        # deleted this run. Wrapped in its own outer try/except, mirrors
        # every other pipeline_memory hook in main().
        if _reconcile_affected_pairs:
            try:
                _reconcile_repaired = (
                    _repair_group_state_for_affected_pairs(
                        _reconcile_affected_pairs, _deferred_group_state,
                    )
                )
                _reconcile_repaired_pairs = {
                    (rec.get('wr_num'), rec.get('week_iso'))
                    for rec in _reconcile_repaired
                }
                _reconcile_orphaned_pairs = (
                    _reconcile_affected_pairs - _reconcile_repaired_pairs
                )
                logging.info(
                    "🧾 Deep-run deletion reconciliation: "
                    f"{len(_reconcile_repaired)} group(s) confirmed "
                    "still live (content hash already refreshed by the "
                    "ordinary group-state flush this run), "
                    f"{len(_reconcile_orphaned_pairs)} affected pair(s) "
                    "now fully empty (group_state row left as-is; "
                    "cross-group cleanup deferred)."
                )
                if _reconcile_orphaned_pairs:
                    sentry_add_breadcrumb(
                        "pipeline_memory",
                        "Deep-run reconciliation: affected pair(s) "
                        "fully emptied",
                        level="warning",
                        data={"count": len(_reconcile_orphaned_pairs)},
                    )
            except Exception:
                logging.warning(
                    "⚠️ pipeline_memory deep-run group_state repair "
                    "confirmation failed unexpectedly (non-fatal)."
                )

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
            if (
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
                # Codex P2 (PR #283, repair-path): a group withheld due to
                # a REAL upload 'error' has the durable row overwritten
                # with a 'withheld:'-prefixed sentinel that can never
                # equal a computed SHA256 (lookup mismatches -> regenerate;
                # the next successful upload overwrites it).
                # 'skip_upload' (SKIP_UPLOAD dry-run) does NOT
                # invalidate — a local dry run must never mutate prod
                # change-detection state in either direction. Phase 11
                # Plan 08 (INC-05, D-12): the local json hash_history
                # cache this comment used to describe is retired --
                # group_state.content_hash (flushed below) is now the
                # sole local record obeying this contract.
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
                        # Phase 11 Plan 08 (INC-05, D-12): history_updates
                        # (frozen run_summary.json key) previously counted
                        # local hash-history JSON cache entries actually
                        # written after upload success; group_state.content_hash
                        # is now that record, so the count moves here -- one per
                        # group _build_group_state_flush determined should
                        # be persisted (mirrors the retired json write,
                        # which also counted on the decision, not on a
                        # disk-write success check).
                        history_updates += len(_mem_group_records)
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
                # Identity row -- the canonical (hash-order) first row,
                # mirroring Site 1; never arrival-order group_rows[0].
                _first = canonical_first_row(group_rows)
                wr_raw = _first.get('Work Request #')
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
                variant = _first.get('__variant', 'primary')
                # CR-01 gap closure (Site 2 — mirror of Site 1): the
                # file identifier from the ONE shared definition.
                _, file_id = derive_group_identity(
                    _first, **_identity_switches)
                valid_wr_weeks.add((wr, week_raw, variant, file_id))
        if not TEST_MODE:
            # Phase 11 Plan 08 (INC-05 retirement): attachment_cache is now
            # sourced from pipeline_memory.group_state, which only knows
            # the identities THIS pipeline wrote -- it cannot prove a row
            # carries no OTHER (off-contract / duplicate / legacy)
            # attachment, which is exactly what
            # cleanup_untracked_sheet_attachments exists to find. This
            # consumer therefore always resolves via its per-row
            # on-demand `list_row_attachments` fallback (T-11-41) rather
            # than ever reading the group_state-seeded cache -- strictly
            # safer than the retired bulk-Smartsheet-prefetch cache it
            # used to (conditionally) receive.
            _cleanup_cache = None
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
                    # Phase 11 Plan 03 (CONTEXT.md D-06 — highest-severity
                    # finding of the phase): in incremental mode `groups`
                    # is a strict subset of the live groups, so
                    # `valid_wr_weeks` (built from `groups` above) is too
                    # — an identity absent from it means "not processed
                    # this run", never "no longer valid". Force the
                    # identity-loop's preservation gate on at this call
                    # boundary only: the global env-driven
                    # KEEP_HISTORICAL_WEEKS constant (and its facade
                    # rebind in pipeline/cleanup.py) is never flipped, so
                    # a full-mode run's cleanup decisions are
                    # byte-for-byte unchanged.
                    keep_historical=True if _resolved_mode == 'incremental' else None,
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
            # Cache semantics (Phase 11 Plan 08, INC-05 retirement):
            # ``_cleanup_cache`` is set ABOVE, unconditionally, to
            # ``None`` for BOTH passes -- ``cleanup_untracked_sheet_
            # attachments`` always resolves via its per-row on-demand
            # `list_row_attachments` fallback rather than the
            # group_state-seeded ``attachment_cache`` the identity-check
            # consumers above use, since group_state cannot prove a row
            # carries no OTHER (off-contract / legacy) attachment. See
            # the ``_cleanup_cache = None`` assignment's comment above
            # for the full rationale.
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
                        # Phase 11 Plan 03 (CONTEXT.md D-06): same
                        # incremental-mode override as the TARGET call
                        # site above — `valid_wr_weeks` is a strict
                        # subset in incremental mode, so an identity
                        # absent from it means "not processed this run",
                        # not "no longer valid". Call-boundary override
                        # only; KEEP_HISTORICAL_WEEKS itself is untouched.
                        keep_historical=True if _resolved_mode == 'incremental' else None,
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
        
        # Phase 11 Plan 08 (INC-05, D-12): the local hash-history JSON
        # cache and the local billing_audit frozen-rows JSON cache are
        # both retired -- no end-of-run prune or save for either.
        # group_state.content_hash
        # (flushed above, per group, right after upload) is the sole local
        # change-detection record now; billing_audit_row_cache stays an
        # in-run-only dedupe set (freeze_row / freeze_attribution are
        # already idempotent, so nothing is lost by not persisting it).

        # Phase 10 (MEM-01/MEM-03): run_ledger 'finish' row. Same guard
        # shape as the start hook. Reuses already-computed counters --
        # recomputes nothing. Memory counters live in run_ledger.notes,
        # NOT in the frozen 21-key run_summary.json below (interfaces
        # block: adding a key there means editing 3 places plus the
        # golden baseline, and pollutes the plan-10-05 control-run diff).
        if RUN_MEMORY_WRITE_ENABLED and not TEST_MODE:
            try:
                # Phase 11 Plan 02: carries the resolved mode; notes.
                # fallback_reason is included ONLY when non-empty (T-11-11
                # -- present+non-empty on a full-mode resolution, ABSENT
                # entirely -- never a null placeholder -- when mode is
                # 'incremental').
                # Phase 11 Plan 03 (D-11): groups_generated/groups_affected/
                # rows_seen below are scoped to whatever this run actually
                # covered -- on an incremental run that is a strict subset
                # of the live groups by design, so a small number here is
                # expected, not a regression. These counters are only
                # interpretable next to run_ledger.mode (set above); the
                # frozen run_summary.json 21-key contract is NOT overloaded
                # with a second meaning for this.
                _finish_kwargs = dict(
                    status="success",
                    mode=_resolved_mode,
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
                    # Greptile P1 (PR #351): notes-only flag -- did the
                    # memory write confirm every sheet this run? An
                    # unconfirmed incremental run has already fallen back
                    # to full mode (fallback_reason names it).
                    mem_confirmed=_mem_memory_confirmed,
                    mem_rows_sent=_mem_rows_sent,
                    # Phase 11 Plan 04 (D-06/T-11-20): notes-only counters
                    # distinguishing PHASE 2a's delta-read scope from
                    # PHASE 2b's re-fetch scope so neither is misread as
                    # the other; both are 0 on a full-mode run (PHASE 2a
                    # never executes this run). rows_seen above is the
                    # SCOPED PHASE 2b count on an incremental run --
                    # comparable only against another incremental run,
                    # never against a full run's rows_seen (D-11).
                    mem_phase2a_delta_rows=_incremental_delta_rows_count,
                    mem_phase2b_sheets_refetched=_incremental_mapped_sheet_count,
                )
                if _resolved_fallback_reason:
                    _finish_kwargs["fallback_reason"] = _resolved_fallback_reason
                # Phase 11 Plan 05 (INC-04, D-07/D-08): only present when
                # the shadow parity block actually ran this run (None
                # default means "never a fabricated verdict" -- see the
                # _parity_verdict hoist comment near the top of main()).
                if _parity_verdict is not None:
                    _finish_kwargs["parity_verdict"] = _parity_verdict
                    _finish_kwargs["parity_details"] = _parity_details
                # Phase 11 Plan 06 (INC-03): only present when the
                # deep-run reconciliation phase actually ran this run
                # (mirrors the _parity_verdict None-default contract
                # above -- never a fabricated 0 on a non-deep-run).
                if _reconcile_ran:
                    _finish_kwargs["mem_deep_run_rows_deleted"] = (
                        _reconcile_rows_marked_deleted
                    )
                _mem_writer.run_ledger_finish(_mem_run_id, **_finish_kwargs)
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
            "groups_skipped_no_target_row": _groups_skipped_no_target,
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
            scope.set_tag(
                "groups_skipped_no_target_row",
                str(_groups_skipped_no_target),
            )
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
                "groups_skipped_no_target_row": _groups_skipped_no_target,
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
                "group_state_hashes_resolved": len(_group_state_hashes) if '_group_state_hashes' in dir() else 0,
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
                # Phase 11 Plan 02: carries the resolved mode; see the
                # success-path call site above for the fallback_reason
                # presence/absence rationale.
                _finish_kwargs = dict(
                    status="failed",
                    mode=_resolved_mode,
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
                    # Greptile P1 (PR #351): notes-only flag -- did the
                    # memory write confirm every sheet this run? An
                    # unconfirmed incremental run has already fallen back
                    # to full mode (fallback_reason names it).
                    mem_confirmed=_mem_memory_confirmed,
                    mem_rows_sent=_mem_rows_sent,
                    # Phase 11 Plan 04 (D-06/T-11-20): see the success-path
                    # call site above for the full rationale -- same two
                    # notes-only counters, same D-11 comparability rule.
                    mem_phase2a_delta_rows=_incremental_delta_rows_count,
                    mem_phase2b_sheets_refetched=_incremental_mapped_sheet_count,
                )
                if _resolved_fallback_reason:
                    _finish_kwargs["fallback_reason"] = _resolved_fallback_reason
                # Phase 11 Plan 05 (INC-04, D-07/D-08): only present when
                # the shadow parity block actually ran this run (None
                # default means "never a fabricated verdict" -- see the
                # _parity_verdict hoist comment near the top of main()).
                if _parity_verdict is not None:
                    _finish_kwargs["parity_verdict"] = _parity_verdict
                    _finish_kwargs["parity_details"] = _parity_details
                # Phase 11 Plan 06 (INC-03): only present when the
                # deep-run reconciliation phase actually ran this run
                # (mirrors the _parity_verdict None-default contract
                # above -- never a fabricated 0 on a non-deep-run).
                if _reconcile_ran:
                    _finish_kwargs["mem_deep_run_rows_deleted"] = (
                        _reconcile_rows_marked_deleted
                    )
                _mem_writer.run_ledger_finish(_mem_run_id, **_finish_kwargs)
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
