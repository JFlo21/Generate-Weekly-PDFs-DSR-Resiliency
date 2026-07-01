"""pipeline.fetch — parallel row fetching from Smartsheet source sheets (W3).

Owns the runtime-rebound live-proxy global ``_RATES_FINGERPRINT`` (str),
delegated from the ``generate_weekly_pdfs`` facade via PEP-562 ``__getattr__``
(D-01).  ``get_all_source_rows`` rebinds it (``global _RATES_FINGERPRINT``)
from ``load_rate_versions()`` when a rate cutoff is configured.

GUARD: ``_RATES_FINGERPRINT`` MUST NOT be added to the facade's static
``from pipeline.fetch import ...`` block — a static bind captures the pre-run
value and shadows ``__getattr__``, breaking the change-detection hash (rate
changes would stop triggering regeneration).  ``pipeline.change_detection``
late-imports this module to read the live value (never a module-level import,
to avoid the W2 forward-reference cycle).

PII discipline: aggregate-only logging is preserved byte-for-byte; no per-row
WR / foreman / helper / vac-crew identifiers are emitted at INFO/WARNING.
``PARALLEL_WORKERS`` (<= 8) usage is unchanged (MOD-04).

Symbols relocated from ``generate_weekly_pdfs.py`` (W3):
  get_all_source_rows, _RATES_FINGERPRINT (live-proxy global)
"""
from __future__ import annotations

import collections
import datetime
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import sentry_sdk

from pipeline.config import (
    DEBUG_ESSENTIAL_ROWS,
    DEBUG_SAMPLE_ROWS,
    FILTER_DIAGNOSTICS,
    FOREMAN_DIAGNOSTICS,
    PARALLEL_WORKERS,
    PER_CELL_DEBUG_ENABLED,
)
from pipeline.retry import smartsheet_call_with_retry
from pipeline.pricing import (
    OLD_RATES_CSV,
    RATE_RECALC_WEEKLY_FALLBACK,
    _resolve_cu_code,
    _subcontractor_rescue_price,
    load_contract_rates,
    load_rate_versions,
    parse_price,
    recalculate_row_price,
)
from pipeline.utils import (
    _resolve_rate_recalc_cutoff_date,
    _weekly_would_trigger_fallback,
    excel_serial_to_date,
    is_checked,
)
from pipeline.observability import (
    _redact_exception_message,
    sentry_add_breadcrumb,
    sentry_capture_with_context,
)

logger = logging.getLogger(__name__)

# ── Live-proxy global (D-01) — served to the facade via __getattr__ ──────────
# GUARD: do NOT statically re-export this from the facade (see module docstring).
_RATES_FINGERPRINT: str = ''   # rebound inside get_all_source_rows via `global`


def get_all_source_rows(client, source_sheets):
    """Fetch rows from all source sheets with filtering.
    
    Implements direct column-based foreman assignment with helper row detection.
    
    Args:
        client: Smartsheet client instance
        source_sheets: List of source sheet configurations
    
    Foreman assignment logic:
    - Primary: Use "Foreman Assigned?" column if present
    - Fallback: Use "Foreman" column text
    - Final fallback: "Unknown Foreman"
    
    Helper row detection:
    - Identifies rows where "Foreman Helping?" has a value AND
      both "Helping Foreman Completed Unit?" and "Units Completed?" are checked
    - Helper rows are tagged with __is_helper_row=True and helper metadata
    - No matching, no cache lookup, completely unchanged behavior
    - Triggers when: no cache, no cache entry, no matches found

    Improvements:
      • Per‑cell debug logging limited by DEBUG_SAMPLE_ROWS (env tunable)
      • Essential field summary limited by DEBUG_ESSENTIAL_ROWS
      • Single concise summary for unmapped columns with a small sample of values
      • Greatly reduces 'Unknown' spam while preserving early transparency
    """
    # Phase 09 W3 (D-01): bind the runtime-mutable rate/recalc inputs and the
    # discovery live-proxy globals from the facade so test-time rebinds on
    # generate_weekly_pdfs.NAME are honoured and the post-discovery
    # SUBCONTRACTOR_SHEET_IDS / _FOLDER_DISCOVERED_ORIG_IDS bindings are seen.
    # _RATES_FINGERPRINT stays this module's own global (rebound below).
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    RATE_CUTOFF_DATE = _gwp.RATE_CUTOFF_DATE
    RATE_RECALC_SKIP_ORIGINAL_CONTRACT = _gwp.RATE_RECALC_SKIP_ORIGINAL_CONTRACT
    SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED = (
        _gwp.SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED
    )
    SUBCONTRACTOR_SHEET_IDS = _gwp.SUBCONTRACTOR_SHEET_IDS
    _FOLDER_DISCOVERED_ORIG_IDS = _gwp._FOLDER_DISCOVERED_ORIG_IDS
    merged_rows = []
    global_row_counter = 0
    original_rates = load_contract_rates(OLD_RATES_CSV)
    # Load new rate versions if rate cutoff is configured
    global _RATES_FINGERPRINT
    _rate_cu_to_group = {}
    _rate_new_primary = {}
    _rate_new_arrowhead = {}
    if RATE_CUTOFF_DATE:
        _rate_cu_to_group, _rate_new_primary, _rate_new_arrowhead, _RATES_FINGERPRINT = load_rate_versions()
    exclusion_counts = {
        'missing_work_request': 0,
        'missing_weekly_reference_logged_date': 0,
        'units_not_completed': 0,
        'price_missing_or_zero': 0,
        'cu_no_match': 0,
        'accepted': 0
    }
    # Detailed per‑WR diagnostics
    foreman_raw_counts = collections.defaultdict(lambda: collections.Counter())  # wr -> Counter(foreman values as-seen)
    wr_exclusion_reasons = collections.defaultdict(lambda: collections.Counter())  # wr -> Counter(reason)

    def _fetch_and_process_sheet(source):
        """Fetch and process a single source sheet. Returns (rows, sheet_exclusion_counts, sheet_foreman_counts, sheet_wr_exclusion_reasons, row_count)."""
        sheet_rows = []
        sheet_exclusion_counts = {
            'missing_work_request': 0,
            'missing_weekly_reference_logged_date': 0,
            'units_not_completed': 0,
            'price_missing_or_zero': 0,
            'cu_no_match': 0,
            'accepted': 0
        }
        sheet_foreman_counts = collections.defaultdict(lambda: collections.Counter())
        sheet_wr_exclusion_reasons = collections.defaultdict(lambda: collections.Counter())
        sheet_row_counter = 0
        # Track post-cutoff rate recalc outcomes for operator visibility
        # ('skipped' covers rows where Snapshot Date>=cutoff but the new
        # rates table has no matching group/CU, so the SmartSheet price
        # is retained — the known VAC-crew pricing-lag signal).
        # 'fallback_applied' counts rows routed through the
        # Weekly-Ref-Date fallback (blank Snapshot Date with
        # Weekly Reference Logged Date>=cutoff); it is path-tracking and
        # is independent of recalc outcome, so it is NOT mutually
        # exclusive with 'recalculated' / 'skipped'.
        sheet_rate_recalc_counts = {
            'recalculated': 0,
            'skipped': 0,
            'fallback_applied': 0,
        }
        sheet_rate_recalc_skipped_cus = collections.Counter()
        try:
            logging.info(f"⚡ Processing: {source['name']} (ID: {source['id']})")
            is_subcontractor_sheet = source['id'] in SUBCONTRACTOR_SHEET_IDS
            # Smartsheet-native pricing guard: sheets discovered via
            # ORIGINAL_CONTRACT_FOLDER_IDS already produce their
            # Units Total Price from Smartsheet's internal formula for
            # post-cutoff rows with Units Completed? = true. The
            # Python-side recalc must NOT overwrite that value.
            # See RATE_RECALC_SKIP_ORIGINAL_CONTRACT env var declaration
            # for the full rationale and the kill-switch.
            is_original_contract_sheet = source['id'] in _FOLDER_DISCOVERED_ORIG_IDS
            _skip_recalc_original_contract = (
                RATE_CUTOFF_DATE is not None
                and RATE_RECALC_SKIP_ORIGINAL_CONTRACT
                and is_original_contract_sheet
                and not is_subcontractor_sheet
            )
            if _skip_recalc_original_contract:
                logging.info(
                    f"🛡️ Skipping Python rate recalc for {source['name']} "
                    f"(ID: {source['id']}) — sheet is in ORIGINAL_CONTRACT_FOLDER_IDS "
                    f"and Smartsheet-native pricing is authoritative for post-cutoff rows"
                )

            try:
                # Fetch sheet once (no column history); include columns to support unmapped summary
                # PERFORMANCE FIX: Use column_ids parameter to only fetch mapped columns
                column_mapping = source['column_mapping']
                required_column_ids = list(column_mapping.values())
                with sentry_sdk.start_span(op="smartsheet.api", name=f"Fetch sheet {source['name']}") as api_span:
                    # Retry transient API errors (4000 on large sheets, server
                    # timeouts, network drops) before the existing per-sheet
                    # handler drops the sheet. Bounded total backoff respects
                    # PARALLEL_WORKERS / TIME_BUDGET (see pipeline.retry).
                    sheet = smartsheet_call_with_retry(
                        client.Sheets.get_sheet,
                        source['id'],
                        column_ids=required_column_ids,
                        label=f"fetch sheet {source['name']}",
                    )
                    api_span.set_data("sheet_id", source['id'])
                    api_span.set_data("sheet_name", source['name'])
                    api_span.set_data("row_count", len(sheet.rows) if sheet.rows else 0)
                    api_span.set_data("column_count", len(required_column_ids))

                logging.info(f"📋 Available mapped columns in {source['name']}: {list(column_mapping.keys())}")
                
                # PERFORMANCE: Pre-build reverse mapping for O(1) cell lookups (column_id -> field_name)
                reverse_column_map = {cid: name for name, cid in column_mapping.items()}
                
                # Debug: Check if Weekly Reference Logged Date is mapped
                if 'Weekly Reference Logged Date' in column_mapping:
                    logging.info(f"✅ Weekly Reference Logged Date column found with ID: {column_mapping['Weekly Reference Logged Date']}")
                else:
                    logging.warning(f"❌ Weekly Reference Logged Date column NOT found in mapping")
                    logging.info(f"   Available mappings: {column_mapping}")
                
                # HELPER DETECTION LOGGING: Check if helper columns are present
                helper_columns = ['Foreman Helping?', 'Helping Foreman Completed Unit?', 'Helper Dept #', 'Helper Job #']
                found_helper_cols = [col for col in helper_columns if col in column_mapping]
                if found_helper_cols:
                    logging.info(f"🔧 Helper columns found in {source['name']}: {found_helper_cols}")
                    if len(found_helper_cols) == 4:
                        logging.info(f"✅ All 4 helper columns present - helper detection will be active for this sheet")
                    else:
                        missing = [col for col in helper_columns if col not in column_mapping]
                        logging.warning(f"⚠️ Missing helper columns in {source['name']}: {missing}")
                else:
                    logging.info(f"ℹ️ No helper columns found in {source['name']} - helper detection disabled for this sheet")

                # VAC CREW DETECTION: Check if VAC Crew columns are present (row-level detection)
                vac_crew_columns = ['VAC Crew Helping?', 'Vac Crew Completed Unit?', 'VAC Crew Dept #', 'Vac Crew Job #']
                found_vac_crew_cols = [col for col in vac_crew_columns if col in column_mapping]
                # Sheet has VAC Crew capability if at least the two key columns are mapped
                sheet_has_vac_crew_columns = 'VAC Crew Helping?' in column_mapping and 'Vac Crew Completed Unit?' in column_mapping
                # Codex P1 guardrail: the Weekly-Ref-Date recalc
                # fallback is ONLY meaningful on sheets that actually
                # map a Snapshot Date column. When a (legacy) sheet
                # has ``Weekly Reference Logged Date`` but no
                # ``Snapshot Date`` mapping, ``row_data.get('Snapshot
                # Date')`` is None for every row and the fallback
                # would silently re-price the whole sheet by weekly
                # date — changing the cutoff basis rather than
                # rescuing current-week automation-lag rows. Gate the
                # fallback on the column's presence so legacy sheets
                # preserve exactly the pre-fix behaviour (no recalc
                # when Snapshot Date is absent).
                sheet_has_snapshot_date_column = 'Snapshot Date' in column_mapping
                if found_vac_crew_cols:
                    logging.info(f"🚐 VAC Crew columns found in {source['name']}: {found_vac_crew_cols}")
                    if sheet_has_vac_crew_columns:
                        logging.info(f"✅ VAC Crew detection active for this sheet (key columns present)")
                    else:
                        missing = [col for col in vac_crew_columns if col not in column_mapping]
                        logging.warning(f"⚠️ Missing VAC Crew columns in {source['name']}: {missing}")
                else:
                    logging.debug(f"ℹ️ No VAC Crew columns in {source['name']} - VAC Crew detection disabled for this sheet")

                # Note: Unmapped column logging skipped - we now only fetch mapped columns for performance
                # This reduces API payload size by ~64% and prevents Error 4000 for large sheets

                # Process all rows
                for row in sheet.rows:
                    row_data = {}

                    # Per‑cell debug logging only for the earliest rows overall
                    # PERFORMANCE: Use early continue to avoid logging overhead in production
                    _should_debug_cells = PER_CELL_DEBUG_ENABLED and sheet_row_counter < DEBUG_SAMPLE_ROWS
                    if _should_debug_cells:
                        logging.info(f"🔍 DEBUG: Processing row with {len(row.cells)} cells (sheet row #{sheet_row_counter+1})")
                        for cell in row.cells:
                            mapped_name = reverse_column_map.get(cell.column_id)
                            if mapped_name:
                                val = cell.display_value if cell.display_value is not None else cell.value
                                if val is not None:
                                    logging.info(f"   Cell {cell.column_id}: '{mapped_name}' = '{val}'")

                    # Build mapped row data using pre-built reverse mapping for O(1) lookup
                    for cell in row.cells:
                        mapped_name = reverse_column_map.get(cell.column_id)
                        if mapped_name:
                            raw_val = getattr(cell, 'value', None)
                            if raw_val is None:
                                raw_val = getattr(cell, 'display_value', None)
                            row_data[mapped_name] = raw_val

                    # Attach provenance metadata for audit (used to fetch selective cell history later)
                    if row_data:
                        row_data['__sheet_id'] = source['id']
                        # Phase 01 Plan 03 / Plan 09 (WR-06): also expose
                        # the sheet id under the canonical
                        # ``__source_sheet_id`` name. Phase 1's
                        # subcontractor variant gate in
                        # ``group_source_rows`` AND the missing-CU
                        # attribution loop in ``main()`` both read
                        # ``__source_sheet_id`` per WR-06. The legacy
                        # ``__sheet_id`` write is retained above for
                        # back-compat with any future reader that
                        # might still touch it — drop in a follow-up
                        # cleanup once a full pass confirms no other
                        # reader exists.
                        row_data['__source_sheet_id'] = source['id']
                        row_data['__row_id'] = row.id

                    # Essential field summary for earliest rows (gated to reduce I/O)
                    _should_log_essentials = sheet_row_counter < DEBUG_ESSENTIAL_ROWS
                    if _should_log_essentials:
                        essential_fields = [
                            'Weekly Reference Logged Date', 'Snapshot Date', 'Units Completed?',
                            'Units Total Price', 'Work Request #'
                        ]
                        debug_essentials = {f: row_data.get(f) for f in essential_fields}
                        logging.info(f"   ESSENTIAL FIELDS: {debug_essentials}")

                    # Process row if it has any mapped data
                    if row_data:
                        work_request = row_data.get('Work Request #')
                        weekly_date = row_data.get('Weekly Reference Logged Date')
                        price_raw = row_data.get('Units Total Price')
                        price_val = parse_price(price_raw)

                        # --- SUBCONTRACTOR PRICING ---
                        # Subcontractor (Arrowhead) sheets always keep their SmartSheet
                        # pricing as-is. Rate recalculation only applies to primary
                        # (non-subcontractor) sheets. Subcontractor new rates will be
                        # enabled separately when a subcontractor cutoff date is provided.
                        # --- END SUBCONTRACTOR PRICING ---

                        # Pre-acceptance rate recalculation: for cutoff-eligible rows,
                        # recalculate price BEFORE the has_price check so rows with
                        # zero/blank SmartSheet prices can still be accepted if the
                        # new rate produces a valid non-zero amount.
                        # NOTE: Subcontractor (Arrowhead) sheets are EXCLUDED from
                        # recalculation until a separate subcontractor cutoff date is
                        # provided. They keep SmartSheet pricing as-is for now.
                        _rate_recalc_ran_for_row = False
                        _recalc_outcome = None
                        _recalc_via_fallback = False
                        # ``_skip_recalc_original_contract`` is sheet-level
                        # (computed once above, logged once per sheet) —
                        # adding it to this row-level gate avoids per-row
                        # log spam while still short-circuiting every row
                        # on an original-contract folder sheet. Subcontractor
                        # exclusion stays primary; the original-contract
                        # skip only kicks in when Smartsheet-native pricing
                        # is authoritative for the whole sheet.
                        if (
                            RATE_CUTOFF_DATE
                            and _rate_new_primary
                            and not is_subcontractor_sheet
                            and not _skip_recalc_original_contract
                        ):
                            # Primary gate is Snapshot Date; the helper
                            # transparently falls back to Weekly
                            # Reference Logged Date when Snapshot Date
                            # is blank AND RATE_RECALC_WEEKLY_FALLBACK
                            # is enabled. This rescues current-week
                            # rows (VAC crew / helper) that would
                            # otherwise silently drop at the has_price
                            # gate with zero price.
                            effective_cutoff_date, _recalc_via_fallback = (
                                _resolve_rate_recalc_cutoff_date(
                                    row_data,
                                    RATE_CUTOFF_DATE,
                                    # See ``sheet_has_snapshot_date_column``
                                    # — disable the fallback on sheets
                                    # that never map Snapshot Date so
                                    # we don't re-price whole legacy
                                    # sheets by weekly date.
                                    weekly_fallback_enabled=(
                                        RATE_RECALC_WEEKLY_FALLBACK
                                        and sheet_has_snapshot_date_column
                                    ),
                                )
                            )

                            if effective_cutoff_date is not None:
                                old_price = price_val
                                _recalc_status = {}
                                price_val = recalculate_row_price(
                                    row_data,
                                    _rate_cu_to_group,
                                    _rate_new_primary,
                                    out_status=_recalc_status,
                                )
                                _rate_recalc_ran_for_row = True
                                _recalc_outcome = _recalc_status.get('outcome')
                                if _recalc_via_fallback:
                                    sheet_rate_recalc_counts['fallback_applied'] += 1
                                if _recalc_outcome == 'recalculated':
                                    sheet_rate_recalc_counts['recalculated'] += 1
                                    if price_val != old_price:
                                        _via = ' via Weekly-Ref-Date fallback' if _recalc_via_fallback else ''
                                        logging.debug(
                                            f"Rate recalc{_via}: CU={row_data.get('CU')}, "
                                            f"old=${old_price:.2f} -> new=${price_val:.2f}, "
                                            f"effective_cutoff_date={effective_cutoff_date}"
                                        )
                                elif _recalc_outcome == 'missing_rate':
                                    # Only count as "skipped" in the
                                    # per-sheet summary when recalc
                                    # explicitly reported that neither
                                    # the mapped group nor the CU code
                                    # is in the new rates table — that
                                    # is the actionable signal for
                                    # updating NEW_RATES_CSV. Outcomes
                                    # like 'invalid_quantity' /
                                    # 'zero_rate' are data-entry or
                                    # contract gaps and are intentionally
                                    # excluded so the summary WARNING
                                    # and top-CU list stay accurate.
                                    sheet_rate_recalc_counts['skipped'] += 1
                                    # Always attribute the skip to a
                                    # CU bucket so the per-sheet
                                    # "N skipped / Top CUs: ..." summary
                                    # totals stay aligned. Blank CU rows
                                    # are attributed to '<blank>' so
                                    # operators can see that category
                                    # and investigate the missing CU
                                    # code separately.
                                    cu_val = _resolve_cu_code(row_data) or '<blank>'
                                    sheet_rate_recalc_skipped_cus[cu_val] += 1

                        # Phase 1.1 Bug A (D-01..D-03 / SUB-08):
                        # pre-acceptance rate-recalc rescue for
                        # subcontractor sheets. Mirrors the
                        # [2026-04-23 00:00] VAC-crew Weekly-Ref-Date
                        # fallback pattern (additive branch alongside
                        # the existing primary-rate gate above, NOT a
                        # modification of it). Subcontractor operators
                        # populate helper-foreman events BEFORE pricing
                        # is finalized; SmartSheet ``Units Total Price``
                        # is commonly blank/zero on those rows. Without
                        # this rescue, the row drops at the has_price
                        # gate below and helper-detection never fires.
                        # Mutates row_data['Units Total Price'] in
                        # addition to price_val so the has_price gate's
                        # ``price_raw not in (None, "", "$0", ...)``
                        # clause also passes — same in-place pattern
                        # as ``recalculate_row_price`` at L1751.
                        if (
                            is_subcontractor_sheet
                            and SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED
                            and price_val <= 0
                        ):
                            _rescued = _subcontractor_rescue_price(row_data)
                            if _rescued > 0:
                                price_val = _rescued
                                row_data['Units Total Price'] = _rescued
                                # Telemetry hook for downstream Sentry
                                # breadcrumbs + the e2e regression
                                # test in Plan 01.1-05.
                                row_data['__subcontractor_rescued'] = True
                                if FILTER_DIAGNOSTICS and sheet_row_counter < DEBUG_ESSENTIAL_ROWS:
                                    # PII marker "Subcontractor pre-
                                    # acceptance rescue" added to
                                    # _PII_LOG_MARKERS in Task 1. Log
                                    # body embeds WR + CU. ``wr_key_for_diag``
                                    # is not yet initialized in this
                                    # scope (it lands at L3723 below),
                                    # so derive it here from the row's
                                    # raw Work Request # via the same
                                    # ``str(work_request).split('.')[0]``
                                    # pattern.
                                    _wr_diag = (
                                        str(work_request).split('.')[0]
                                        if work_request else '<unknown>'
                                    )
                                    logging.info(
                                        f"💲 Subcontractor pre-acceptance rescue: "
                                        f"WR={_wr_diag}, "
                                        f"CU={row_data.get('CU')}, "
                                        f"rescued=${_rescued:.2f}"
                                    )

                        price_raw = row_data.get('Units Total Price')
                        has_price = (price_raw not in (None, "", "$0", "$0.00", "0", "0.0")) and price_val > 0
                        units_completed = row_data.get('Units Completed?')
                        units_completed_checked = is_checked(units_completed)

                        if sheet_row_counter < DEBUG_ESSENTIAL_ROWS:
                            logging.info(f"🔍 Row data sample: WR={work_request}, Price={price_val}, Date={weekly_date}, Units Completed={units_completed} ({units_completed_checked})")

                        # Record raw foreman regardless of acceptance (if WR exists)
                        wr_key_for_diag = None
                        if work_request:
                            wr_key_for_diag = str(work_request).split('.')[0]
                            fr_val = (row_data.get('Foreman') or '').strip() or '<<blank>>'
                            sheet_foreman_counts[wr_key_for_diag][fr_val] += 1

                        # Acceptance logic (STRICT: Units Completed? must be checked/true)
                        if work_request and weekly_date and units_completed_checked and has_price:
                            # CU no-match exclusion: drop backend placeholder rows like "#NO MATCH..."
                            cu_raw = (row_data.get('CU') or row_data.get('Billable Unit Code') or '')
                            cu_text = str(cu_raw).strip().upper()
                            # Exclude any backend placeholder variants like '#NO MATCH' or 'NO MATCH'
                            if 'NO MATCH' in cu_text:
                                sheet_exclusion_counts['cu_no_match'] += 1
                                if wr_key_for_diag:
                                    sheet_wr_exclusion_reasons[wr_key_for_diag]['cu_no_match'] += 1
                                if FILTER_DIAGNOSTICS and sheet_row_counter < DEBUG_ESSENTIAL_ROWS:
                                    logging.info(f"🚫 Excluding row for WR {wr_key_for_diag} due to CU 'NO MATCH' placeholder: raw='{cu_raw}'")
                                # Skip appending this row
                                sheet_row_counter += 1
                                continue
                            # Helper row detection (before foreman assignment)
                            # Helper criteria: Foreman Helping? non-blank AND both checkboxes checked
                            # Handle None values safely with defensive str() conversion to prevent float/strip errors
                            foreman_helping_val = row_data.get('Foreman Helping?')
                            helper_name = str(foreman_helping_val).strip() if foreman_helping_val else ''
                            helping_foreman_completed = row_data.get('Helping Foreman Completed Unit?')
                            helping_foreman_completed_checked = is_checked(helping_foreman_completed)
                            
                            is_helper_row = bool(helper_name and helping_foreman_completed_checked and units_completed_checked)
                            
                            # HELPER DETECTION LOGGING: Log criteria evaluation for sample rows (gated behind FILTER_DIAGNOSTICS)
                            if FILTER_DIAGNOSTICS and sheet_row_counter < DEBUG_ESSENTIAL_ROWS:
                                logging.info(f"🔧 Helper detection criteria for row {sheet_row_counter+1}:")
                                logging.info(f"   Foreman Helping?: '{foreman_helping_val}' -> helper_name='{helper_name}'")
                                logging.info(f"   Helping Foreman Completed Unit?: {helping_foreman_completed} -> checked={helping_foreman_completed_checked}")
                                logging.info(f"   Units Completed?: {units_completed} -> checked={units_completed_checked}")
                                logging.info(f"   is_helper_row: {is_helper_row}")
                            
                            if is_helper_row:
                                # Populate helper metadata (with safe None handling and defensive str() conversion)
                                row_data['__is_helper_row'] = True
                                row_data['__helper_foreman'] = helper_name
                                helper_dept_val = row_data.get('Helper Dept #')
                                helper_job_val = row_data.get('Helper Job #')
                                row_data['__helper_dept'] = str(helper_dept_val).strip() if helper_dept_val else ''
                                row_data['__helper_job'] = str(helper_job_val).strip() if helper_job_val else ''
                                
                                # HELPER DETECTION LOGGING: Log first 10 helper rows per sheet for transparency (gated behind FILTER_DIAGNOSTICS)
                                if FILTER_DIAGNOSTICS and sheet_row_counter < 10:
                                    logging.info(f"🔧 HELPER ROW DETECTED [Row {sheet_row_counter+1}]: WR={wr_key_for_diag}, Helper={helper_name}, Dept={row_data['__helper_dept']}, Job={row_data['__helper_job']}")
                            else:
                                row_data['__is_helper_row'] = False
                            
                            # Direct column-based foreman assignment
                            effective_user = None
                            assignment_method = None
                            # Use Foreman Assigned? column, fallback to Foreman column
                            foreman_assigned = row_data.get('Foreman Assigned?')
                            if foreman_assigned:
                                # Use the value directly (could be email, name, or text)
                                effective_user = str(foreman_assigned).strip()
                                assignment_method = 'FOREMAN_ASSIGNED'
                            else:
                                # Fallback to primary Foreman text if available (defensive str() conversion to prevent float errors)
                                foreman_val = row_data.get('Foreman')
                                primary_foreman_text = str(foreman_val).strip() if foreman_val else ''
                                if primary_foreman_text:
                                    effective_user = primary_foreman_text
                                    assignment_method = 'FOREMAN_COLUMN'
                                else:
                                    effective_user = 'Unknown Foreman'
                                    assignment_method = 'NO_FOREMAN'
                            
                            if sheet_row_counter < DEBUG_ESSENTIAL_ROWS:
                                logging.info(f"📋 Foreman Assignment: Using '{effective_user}' ({assignment_method})")
                            
                            # Store effective user and method for grouping
                            row_data['__effective_user'] = effective_user
                            row_data['__assignment_method'] = assignment_method
                            
                            # VAC Crew row-level detection (mirrors helper pattern)
                            # A row is VAC Crew when: VAC Crew Helping? is non-blank AND
                            # Vac Crew Completed Unit? checkbox is checked.
                            # This is column-presence-driven — only sheets with these columns
                            # can produce VAC Crew rows, no sheet-level ID tagging needed.
                            is_vac_crew_row = False
                            if sheet_has_vac_crew_columns:
                                vac_crew_helping_val = row_data.get('VAC Crew Helping?')
                                vac_crew_name = str(vac_crew_helping_val).strip() if vac_crew_helping_val else ''
                                vac_crew_completed = row_data.get('Vac Crew Completed Unit?')
                                vac_crew_completed_checked = is_checked(vac_crew_completed)
                                is_vac_crew_row = bool(vac_crew_name and vac_crew_completed_checked and units_completed_checked)
                                
                                if FILTER_DIAGNOSTICS and sheet_row_counter < DEBUG_ESSENTIAL_ROWS:
                                    logging.info(f"🚐 VAC Crew detection for row {sheet_row_counter+1}:")
                                    logging.info(f"   VAC Crew Helping?: '{vac_crew_helping_val}' -> name='{vac_crew_name}'")
                                    logging.info(f"   Vac Crew Completed Unit?: {vac_crew_completed} -> checked={vac_crew_completed_checked}")
                                    logging.info(f"   is_vac_crew_row: {is_vac_crew_row}")
                                
                                if is_vac_crew_row:
                                    vac_crew_dept_val = row_data.get('VAC Crew Dept #')
                                    vac_crew_job_val = row_data.get('Vac Crew Job #')
                                    row_data['__vac_crew_name'] = vac_crew_name
                                    row_data['__vac_crew_dept'] = str(vac_crew_dept_val).strip() if vac_crew_dept_val else ''
                                    row_data['__vac_crew_job'] = str(vac_crew_job_val).strip() if vac_crew_job_val else ''
                                    vac_crew_email_val = row_data.get('Vac Crew Email Address')
                                    row_data['__vac_crew_email'] = str(vac_crew_email_val).strip() if vac_crew_email_val else ''
                                    if FILTER_DIAGNOSTICS and sheet_row_counter < 10:
                                        logging.info(f"🚐 VAC CREW ROW DETECTED [Row {sheet_row_counter+1}]: WR={wr_key_for_diag}, Name={vac_crew_name}, Dept={row_data['__vac_crew_dept']}, Job={row_data['__vac_crew_job']}")
                            
                            row_data['__is_vac_crew'] = is_vac_crew_row
                            row_data['__is_subcontractor'] = is_subcontractor_sheet

                            sheet_rows.append(row_data)
                            sheet_exclusion_counts['accepted'] += 1
                        else:
                            # Increment specific exclusion reasons (first matching reason recorded)
                            if not work_request:
                                sheet_exclusion_counts['missing_work_request'] += 1
                                if wr_key_for_diag:
                                    sheet_wr_exclusion_reasons[wr_key_for_diag]['missing_work_request'] += 1
                            elif not weekly_date:
                                sheet_exclusion_counts['missing_weekly_reference_logged_date'] += 1
                                if wr_key_for_diag:
                                    sheet_wr_exclusion_reasons[wr_key_for_diag]['missing_weekly_reference_logged_date'] += 1
                            elif not units_completed_checked:
                                sheet_exclusion_counts['units_not_completed'] += 1
                                if wr_key_for_diag:
                                    sheet_wr_exclusion_reasons[wr_key_for_diag]['units_not_completed'] += 1
                            elif not has_price:
                                sheet_exclusion_counts['price_missing_or_zero'] += 1
                                if wr_key_for_diag:
                                    sheet_wr_exclusion_reasons[wr_key_for_diag]['price_missing_or_zero'] += 1
                                # Row-level visibility: surface drops that
                                # otherwise look "correct" to operators —
                                # specifically VAC crew / helper rows whose
                                # only missing piece is a zero or blank
                                # SmartSheet price. These previously
                                # disappeared into the per-sheet counter
                                # with no per-row log, which is why VAC
                                # crew / helping-foreman Excel files could
                                # silently fail to generate even after
                                # RESET_HASH_HISTORY.
                                _vc_helping = str(row_data.get('VAC Crew Helping?') or '').strip()
                                _vc_completed = is_checked(row_data.get('Vac Crew Completed Unit?'))
                                _fh_helping = str(row_data.get('Foreman Helping?') or '').strip()
                                _fh_completed = is_checked(row_data.get('Helping Foreman Completed Unit?'))
                                _is_specialized = (
                                    (bool(_vc_helping) and _vc_completed)
                                    or (bool(_fh_helping) and _fh_completed)
                                )
                                if _is_specialized:
                                    _variant_tag = 'VAC crew' if (_vc_helping and _vc_completed) else 'helper'
                                    # Only point operators at the per-sheet
                                    # "Rate recalc summary" WARNING when that
                                    # summary will actually contain this row:
                                    # the summary is emitted only when at
                                    # least one row in the sheet has outcome
                                    # 'missing_rate', so the note is valid
                                    # exactly when this row's outcome is
                                    # 'missing_rate'. For other outcomes
                                    # ('invalid_quantity', 'zero_rate', or
                                    # recalc-bypassed rows where
                                    # RATE_CUTOFF_DATE is unset, pre-cutoff,
                                    # Snapshot Date blank, or subcontractor
                                    # sheet), skip the breadcrumb so we
                                    # don't send operators hunting for a
                                    # summary line that isn't there.
                                    if _rate_recalc_ran_for_row and _recalc_outcome == 'missing_rate':
                                        _via_txt = (
                                            ' via Weekly-Ref-Date fallback'
                                            if _recalc_via_fallback else ''
                                        )
                                        _recalc_note = (
                                            f" Rate recalc ran{_via_txt} and reported no matching new-contract rate for this CU; "
                                            "see 'Rate recalc summary' WARNING on this sheet for the full CU list."
                                        )
                                    elif (
                                        not _rate_recalc_ran_for_row
                                        and RATE_CUTOFF_DATE
                                        and not RATE_RECALC_WEEKLY_FALLBACK
                                        # The Weekly-Ref-Date-fallback note
                                        # is only valid when recalc was
                                        # genuinely eligible to run on this
                                        # sheet. Original-contract folder
                                        # sheets skip recalc by design
                                        # (Smartsheet-native pricing is
                                        # authoritative), so enabling the
                                        # fallback env var would not change
                                        # anything on those sheets.
                                        and not _skip_recalc_original_contract
                                        # Use the same parser the recalc
                                        # gate uses so an unparseable
                                        # Snapshot Date (treated as blank
                                        # by _resolve_rate_recalc_cutoff_date)
                                        # triggers this note too — raw
                                        # truthiness would miss it and
                                        # leave operators chasing a
                                        # missing-rate explanation that
                                        # doesn't apply.
                                        and excel_serial_to_date(
                                            row_data.get('Snapshot Date')
                                        ) is None
                                        # Only advise enabling the
                                        # fallback when doing so would
                                        # actually rescue the row —
                                        # i.e. the Weekly Reference
                                        # Logged Date parses AND is
                                        # >= RATE_CUTOFF_DATE. For rows
                                        # whose weekly date is blank /
                                        # unparseable / pre-cutoff,
                                        # enabling the env var wouldn't
                                        # change anything, and the
                                        # message would send operators
                                        # on a false lead.
                                        and _weekly_would_trigger_fallback(
                                            row_data.get('Weekly Reference Logged Date'),
                                            RATE_CUTOFF_DATE,
                                        )
                                    ):
                                        # Snapshot Date is blank or
                                        # unparseable, Weekly Reference
                                        # Logged Date IS post-cutoff,
                                        # and the fallback is disabled.
                                        # Enabling RATE_RECALC_WEEKLY_FALLBACK
                                        # would genuinely rescue this
                                        # row — tell operators so they
                                        # don't hunt the CU in
                                        # NEW_RATES_CSV instead.
                                        _recalc_note = (
                                            " Rate recalc skipped because Snapshot Date is blank or unparseable "
                                            "and RATE_RECALC_WEEKLY_FALLBACK is disabled; Weekly Reference Logged "
                                            "Date is >= RATE_CUTOFF_DATE so setting the env var to '1' (default) "
                                            "would let this row get priced from the new-contract rates table."
                                        )
                                    else:
                                        _recalc_note = ""
                                    logging.warning(
                                        f"⚠️ Dropped {_variant_tag} row (price missing or zero): "
                                        f"WR={wr_key_for_diag}, Weekly={weekly_date}, "
                                        f"Snapshot={row_data.get('Snapshot Date') or '<blank>'}, "
                                        f"CU={_resolve_cu_code(row_data) or '<blank>'}, "
                                        f"Qty={row_data.get('Quantity') or '<blank>'}, "
                                        f"SmartSheet price={row_data.get('Units Total Price') or '<blank>'}. "
                                        f"Row has VAC/helper criteria checked but Units Total Price is zero/blank."
                                        f"{_recalc_note}"
                                    )

                    sheet_row_counter += 1

                sentry_add_breadcrumb("sheet_processing", f"Processed sheet {source['name']}", data={
                    "sheet_id": source['id'],
                    "rows_in_sheet": len(sheet.rows) if sheet.rows else 0,
                    "accepted_so_far": sheet_exclusion_counts['accepted'],
                    "is_subcontractor": is_subcontractor_sheet,
                })

                # Per-sheet summary of post-cutoff rate-recalc outcomes.
                # A non-zero 'skipped' count means rows qualified by
                # Snapshot Date but the new rates table could not price
                # them, so they kept their SmartSheet price. This is the
                # signal operators need to investigate missing entries
                # in NEW_RATES_CSV (common on VAC crew specialized work
                # like vacuum switches, softswitches, switched banks).
                # Suppress the summary entirely on sheets where the
                # original-contract skip fired — every counter is zero by
                # construction, so the summary would be noise. The
                # single "🛡️ Skipping Python rate recalc…" info log
                # emitted at the start of _fetch_and_process_sheet is
                # the authoritative per-sheet signal here.
                if (
                    RATE_CUTOFF_DATE
                    and _rate_new_primary
                    and not _skip_recalc_original_contract
                ):
                    skipped = sheet_rate_recalc_counts['skipped']
                    recalculated = sheet_rate_recalc_counts['recalculated']
                    fallback_applied = sheet_rate_recalc_counts['fallback_applied']
                    _fallback_suffix = (
                        f" ({fallback_applied} via Weekly-Ref-Date fallback)"
                        if fallback_applied else ""
                    )
                    if skipped:
                        top_cus = ', '.join(f"{cu}×{cnt}" for cu, cnt in sheet_rate_recalc_skipped_cus.most_common(10))
                        logging.warning(
                            f"⚠️ Rate recalc summary for {source['name']}: "
                            f"{recalculated} recalculated, {skipped} skipped{_fallback_suffix} "
                            f"(post-cutoff rows that kept SmartSheet price because no matching "
                            f"new-contract rate was found). Top CUs: {top_cus}"
                        )
                    elif recalculated:
                        logging.info(
                            f"📊 Rate recalc summary for {source['name']}: "
                            f"{recalculated} rows recalculated, 0 skipped{_fallback_suffix}"
                        )
                    elif fallback_applied:
                        # Fallback ran but every row hit a non-reportable
                        # outcome (invalid_quantity / zero_rate / etc.).
                        # Without this branch the new fallback_applied
                        # counter would be completely invisible in the
                        # logs for those runs — operators would have no
                        # visibility into whether the Weekly-Ref-Date
                        # fallback ever fired.
                        logging.info(
                            f"📊 Rate recalc summary for {source['name']}: "
                            f"0 recalculated, 0 skipped{_fallback_suffix}"
                        )

            except Exception as e:
                logging.error(f"Error processing sheet {source['id']}: {e}")
                sentry_capture_with_context(
                    exception=e,
                    context_name="sheet_processing_error",
                    context_data={
                        "sheet_id": source['id'],
                        "sheet_name": source.get('name', 'Unknown'),
                        "rows_processed": sheet_row_counter,
                        "error_type": type(e).__name__,
                        "error_message": _redact_exception_message(e),
                    },
                    tags={"error_location": "sheet_row_processing", "sheet_id": source['id']},
                    fingerprint=["sheet-processing", str(source['id']), type(e).__name__]
                )
            
        except Exception as e:
            logging.error(f"Could not process Sheet ID {source.get('id', 'N/A')}: {e}")
            sentry_capture_with_context(
                exception=e,
                context_name="sheet_access_error",
                context_data={
                    "sheet_id": source.get('id', 'N/A'),
                    "sheet_name": source.get('name', 'Unknown'),
                    "error_type": type(e).__name__,
                    "error_message": _redact_exception_message(e),
                },
                tags={"error_location": "sheet_access", "sheet_id": str(source.get('id', 'N/A'))},
                fingerprint=["sheet-access", str(source.get('id', 'N/A')), type(e).__name__]
            )

        return (sheet_rows, sheet_exclusion_counts, sheet_foreman_counts, sheet_wr_exclusion_reasons, sheet_row_counter)

    # Parallel sheet fetching: submit all sources to ThreadPoolExecutor
    logging.info(f"🚀 Starting parallel data fetch with {PARALLEL_WORKERS} workers for {len(source_sheets)} sheets...")
    _fetch_start = datetime.datetime.now()
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        futures = {executor.submit(_fetch_and_process_sheet, source): source for source in source_sheets}
        for i, future in enumerate(as_completed(futures), 1):
            source = futures[future]
            try:
                sheet_rows, sheet_exc, sheet_fc, sheet_wr_exc, sheet_rc = future.result()
                # Merge rows
                merged_rows.extend(sheet_rows)
                # Merge exclusion counts
                for k in exclusion_counts:
                    exclusion_counts[k] += sheet_exc[k]
                # Merge foreman raw counts
                for wr_key, ctr in sheet_fc.items():
                    foreman_raw_counts[wr_key] += ctr
                # Merge WR exclusion reasons
                for wr_key, ctr in sheet_wr_exc.items():
                    wr_exclusion_reasons[wr_key] += ctr
                global_row_counter += sheet_rc
                logging.info(f"   📋 [{i}/{len(futures)}] Fetched {sheet_exc['accepted']} rows from {source.get('name', 'unknown')} ({sheet_rc} total processed)")
            except Exception as e:
                logging.error(f"   ⚠️ [{i}/{len(futures)}] Sheet worker failed for {source.get('name', 'unknown')}: {e}")
    _fetch_elapsed = (datetime.datetime.now() - _fetch_start).total_seconds()
    logging.info(f"⚡ Data fetch complete: {len(merged_rows)} valid rows in {_fetch_elapsed:.1f}s (parallel w/{PARALLEL_WORKERS} workers)")
    
    # HELPER DETECTION SUMMARY LOGGING
    helper_row_count = sum(1 for r in merged_rows if r.get('__is_helper_row', False))
    if helper_row_count > 0:
        logging.info(f"🔧 HELPER DETECTION SUMMARY: {helper_row_count} helper rows detected out of {len(merged_rows)} total valid rows ({helper_row_count/len(merged_rows)*100:.1f}%)")
        # Log sample helper rows for verification
        sample_helpers = [r for r in merged_rows if r.get('__is_helper_row', False)][:5]
        for idx, helper in enumerate(sample_helpers, 1):
            logging.info(f"   Sample Helper {idx}: WR={helper.get('Work Request #')}, Helper={helper.get('__helper_foreman')}, Dept={helper.get('__helper_dept')}, Job={helper.get('__helper_job')}")
    else:
        logging.warning(f"⚠️ HELPER DETECTION SUMMARY: No helper rows detected in {len(merged_rows)} valid rows - check if helper columns exist and criteria are met")
    
    if FILTER_DIAGNOSTICS:
        total_excluded = sum(v for k,v in exclusion_counts.items() if k != 'accepted')
        logging.info("🧪 FILTER DIAGNOSTICS:")
        for k,v in exclusion_counts.items():
            logging.info(f"   {k}: {v}")
        logging.info(f"   total_excluded: {total_excluded}")
    if FOREMAN_DIAGNOSTICS and foreman_raw_counts:
        logging.info("🧪 FOREMAN DIAGNOSTICS (first 25 WRs):")
        for wr_key, ctr in list(foreman_raw_counts.items())[:25]:
            top = ctr.most_common(5)
            excl = wr_exclusion_reasons.get(wr_key, {})
            logging.info(f"   WR {wr_key}: {sum(ctr.values())} rows seen, foremen(top5)={top}; exclusions={dict(excl)}")

    if merged_rows:
        logging.info(f"✅ UPDATED FILTERING SUCCESS: Found {len(merged_rows)} rows (Work Request # + Weekly Reference Logged Date + Units Completed? + Units Total Price exists required)")
        logging.info("🎯 Change detection ACTIVE: Existing attachment with matching data hash will skip regeneration & upload")
    else:
        logging.warning("⚠️ No valid rows found with updated filtering (missing Work Request #, Weekly Reference Logged Date, Units Completed?, or Units Total Price)")

    return merged_rows
