"""pipeline.grouping -- row grouping and group validation (W4).

``group_source_rows`` is the highest-fan-in data transform (~1145 lines).
It is relocated byte-for-byte with NO internal decomposition (D-05).

Billing guards preserved verbatim (MOD-04):
- the ``(WR, week, variant, foreman, dept, job)`` change-detection grouping key;
- the helper dual-checkbox exclusion (helper rows need ``helper_dept`` +
  ``helper_foreman``; dual-checkbox rows are excluded from the main file);
- the Job # column synonyms are not collapsed.

The runtime-rebound discovery globals (``SUBCONTRACTOR_SHEET_IDS`` /
``_FOLDER_DISCOVERED_*``) are read live via ``_discovery.NAME`` (this replaces
the W3 in-root ``_pipeline_discovery.NAME`` qualification).  Test-mutable /
facade-resident flags are bound from the ``generate_weekly_pdfs`` facade at
function entry (behaviour-preserving prelude) so test-time rebinds on
``generate_weekly_pdfs.NAME`` are honoured.

PII discipline: foreman / helper / vac-crew names are never emitted in logs;
existing log levels are unchanged.

Symbols relocated from ``generate_weekly_pdfs.py`` (W4):
  group_source_rows, validate_group_totals
"""
from __future__ import annotations

import collections
import datetime
import logging

from dateutil import parser  # type: ignore[import-untyped]  # untyped third-party (matches facade)

import pipeline.discovery as _discovery
from pipeline.config import (
    _RE_SANITIZE_HELPER_NAME,
    _RE_SANITIZE_IDENTIFIER,
)
from pipeline.observability import sentry_capture_message_with_context
from pipeline.pricing import parse_price
from pipeline.utils import (
    excel_serial_to_date,
    is_checked,
)

logger = logging.getLogger(__name__)



def group_source_rows(rows):
    """
    VARIANT-AWARE GROUPING: Groups rows by Work Request #, Week Ending Date, and Variant (primary/helper/vac_crew).
    
    Primary Variant:
    - Standard WR-based grouping (one Excel per WR/Week)
    - Key format: MMDDYY_WRNUMBER
    
    Helper Variant:
    - Helper-based grouping (one Excel per WR/Week/Helper)
    - Key format: MMDDYY_WRNUMBER_HELPER_<sanitized_helper_name>
    - Only created for rows where __is_helper_row = True
    
    VAC Crew Variant (Sub-project C — per-claimer partitioning):
    - Only created for rows where __is_vac_crew = True (row-level column-based detection)
    - Two key shapes, gated on VAC_CREW_CLAIM_ATTRIBUTION_ENABLED:
      * ON (default): partitioned by FROZEN vac-crew claimer →
        MMDDYY_WRNUMBER_VACCREW_<sanitized_claimer>, one Excel per
        WR/Week/claimer, filename suffix _VacCrew_<claimer>. Claimer is
        resolved in the pre-pass (frozen_vac_crew; falls back to the current
        vac-crew name on no_history; HOLD defers the row on a Supabase
        fetch_failure).
      * OFF (exact legacy): single group per WR/Week →
        MMDDYY_WRNUMBER_VACCREW, filename suffix _VacCrew (no claimer).
    - VAC crew rows never also emit the subcontractor primary variants
      (the subcontractor block is gated on `not is_vac_crew_row`).
    
    Activity Log (DECOMMISSIONED - only in primary mode):
    - No longer uses Modified By cache - direct column assignment only
    - Appends user identifier: MMDDYY_WRNUMBER_USER_<sanitized_user>
    
    RES_GROUPING_MODE controls primary/helper variants only (not vac_crew):
    - "primary": Only primary variant (may include user if activity log enabled)
    - "helper": Helper variant for helper rows + primary variant for non-helper rows (conditional filter)
    - "both": Both primary and helper variants for all applicable rows
    
    CRITICAL BUSINESS LOGIC: Groups valid rows by Week Ending Date AND Work Request #.
    Each group will create ONE Excel file containing ONE work request for ONE week ending date.
    
    FILENAME FORMAT: 
    - Primary: WR_{work_request_number}_WeekEnding_{MMDDYY}_{hash}.xlsx
    - Primary+User: WR_{work_request_number}_WeekEnding_{MMDDYY}_User_{user_sanitized}_{hash}.xlsx
    - Helper: WR_{work_request_number}_WeekEnding_{MMDDYY}_Helper_{helper_sanitized}_{hash}.xlsx
    - VAC Crew: WR_{work_request_number}_WeekEnding_{MMDDYY}_VacCrew_{hash}.xlsx
    
    This ensures:
    - Each Excel file contains ONLY one work request
    - Each work request can have multiple Excel files (one per week ending date and/or variant)
    - No mixing of work requests or variants in a single file
    - Clear, predictable file naming with variant identification
    """
    # Phase 09 W4 (behaviour-preserving relocation): bind the
    # test-mutable / facade-resident constants from the
    # generate_weekly_pdfs facade so test-time rebinds on
    # generate_weekly_pdfs.NAME are honoured (production value is
    # identical -- the facade re-exports pipeline.config).  The three
    # discovery live-proxy globals are read via _discovery.NAME (live).
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    ATTRIBUTION_BULK_PREFETCH_FALLBACK = _gwp.ATTRIBUTION_BULK_PREFETCH_FALLBACK
    BILLING_AUDIT_AVAILABLE = _gwp.BILLING_AUDIT_AVAILABLE
    EXCLUDE_WRS = _gwp.EXCLUDE_WRS
    PRIMARY_CLAIM_ATTRIBUTION_ENABLED = _gwp.PRIMARY_CLAIM_ATTRIBUTION_ENABLED
    RES_GROUPING_MODE = _gwp.RES_GROUPING_MODE
    SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED = (
        _gwp.SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED
    )
    SUBCONTRACTOR_RATE_VARIANTS_ENABLED = (
        _gwp.SUBCONTRACTOR_RATE_VARIANTS_ENABLED
    )
    TEST_MODE = _gwp.TEST_MODE
    VAC_CREW_CLAIM_ATTRIBUTION_ENABLED = _gwp.VAC_CREW_CLAIM_ATTRIBUTION_ENABLED
    WR_FILTER = _gwp.WR_FILTER
    _AEP_BILLABLE_CUTOFF = _gwp._AEP_BILLABLE_CUTOFF
    groups = collections.defaultdict(list)

    # Phase 1.1 Bug C (D-12 / SUB-11): per-WR dedupe set for the
    # fall-back WARNING. Keyed on (wr_key, week_end_for_key,
    # sanitized_helper_foreman) so we log ONE WARNING per unique
    # attribution-read failure context per run (not per-row). A
    # 100-row WR with the same helper falling back would otherwise
    # log 100 identical WARNINGs — exactly the kind of operator-log
    # spam the [2026-04-25 12:00] / [2026-04-24 10:50] ledger rules
    # call out as a P0 noise hazard.
    _bug_c_warning_seen: set[tuple[str, str, str]] = set()

    # ── Phase 2 Plan 02: Single bulk attribution prefetch (D-02) ──
    # Replace four separate per-row lookup_attribution RPC pre-passes
    # (B/C/D/Phase-1.1-sub-helper, ~137k calls/run on full history) with
    # ONE prefetch_attribution call that fetches ALL (wr, week_ending)
    # pairs in the current row set in bulk, building a shared
    #   {(wr, week_ending, row_id) -> roles_dict}
    # map for O(1) per-row resolution (D-03: map-aware resolve_claimer).
    #
    # D-04 direct-HOLD contract: on fetch_failure, B and C construct
    # ResolveOutcome('hold', None, None, 'fetch_failure') DIRECTLY from the
    # status — zero additional Supabase calls. D uses-current (never HOLDs)
    # per operator decision (core primary path prioritizes availability).
    #
    # D-05 scope removal: ATTRIBUTION_RESOLUTION_WEEKS and its scope gate
    # have been deleted. The bulk prefetch covers the EXACT (wr, week_ending)
    # pairs in the current run — no recency gate needed. Historical rows
    # with valid frozen claimers are now correctly resolved regardless of age
    # (fixes incident run 26439205107: 372 garbage _User__NO_MATCH files).
    _attr_map: dict = {}
    _attr_status: str = 'disabled'
    if BILLING_AUDIT_AVAILABLE and (
        SUBCONTRACTOR_RATE_VARIANTS_ENABLED
        or VAC_CREW_CLAIM_ATTRIBUTION_ENABLED
        or PRIMARY_CLAIM_ATTRIBUTION_ENABLED
        or SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED
    ):
        # Build (wr, week_ending, row_id) pairs from all completed rows
        # that any of the four attribution consumers will process.
        _prefetch_pairs: set[tuple[str, datetime.date, int]] = set()
        for _r in rows:
            _rid = _r.get('__row_id')
            if not isinstance(_rid, int):
                continue
            if not is_checked(_r.get('Units Completed?')):
                continue
            _wr_raw = _r.get('Work Request #')
            _ld = _r.get('Weekly Reference Logged Date')
            if not _wr_raw or not _ld:
                continue
            _we = excel_serial_to_date(_ld)
            if _we is None:
                continue
            _we_d = _we.date() if isinstance(_we, datetime.datetime) else _we
            _prefetch_pairs.add((str(_wr_raw).split('.')[0], _we_d, _rid))

        try:
            from billing_audit.writer import (
                prefetch_attribution as _prefetch_attribution,
            )
            _prefetch_pairs_filtered = {(wr, we) for wr, we, _ in _prefetch_pairs}
            _attr_map, _attr_status = _prefetch_attribution(_prefetch_pairs_filtered)
            if _attr_status == 'fetch_failure':
                logging.warning(
                    "⚠️ Attribution bulk prefetch failed "
                    f"(status={_attr_status}); B/C will HOLD affected rows, "
                    "D/sub-helper will use current foreman (D-04 contract)."
                )
        except Exception:
            logging.exception(
                "⚠️ Attribution bulk prefetch: unexpected error; "
                "falling back to use-current for all attribution consumers."
            )
            _attr_map, _attr_status = {}, 'fetch_failure'

    # CR-01 graceful degradation: a MISSING RPC (rpc_missing) is correctness-
    # preserving to fall back per-row (the deployed lookup_attribution returns
    # the SAME frozen data, just slower) — NOT a D-04 violation. A transient
    # outage (fetch_failure) still HOLDs B/C. The fallback is bounded: per-row
    # resolution only happens for the rows B/C/sub-helper actually process this
    # run, so it cannot reintroduce the 137k per-row storm.
    _attr_use_per_row_fallback = (
        _attr_status == 'rpc_missing' and ATTRIBUTION_BULK_PREFETCH_FALLBACK
    )
    if _attr_use_per_row_fallback:
        logging.warning(
            "⚠️ Attribution bulk RPC missing (rpc_missing); "
            "ATTRIBUTION_BULK_PREFETCH_FALLBACK=1 -> degrading to per-row "
            "lookup_attribution for B/C/sub-helper (deploy lookup_attribution_bulk "
            "to restore bulk; see runbook E re-activation Step 1)."
        )

    # ── Subproject B: O(1) map read for sub-primary claimers (D-03) ──
    # The ThreadPoolExecutor per-row RPC block is replaced by O(1) lookups
    # from the shared _attr_map. On fetch_failure, ResolveOutcome is
    # constructed directly (D-04 direct-HOLD, zero additional Supabase calls).
    _sub_primary_claimer_map: dict = {}
    if BILLING_AUDIT_AVAILABLE and SUBCONTRACTOR_RATE_VARIANTS_ENABLED:
        try:
            from billing_audit.writer import (
                resolve_claimer as _resolve_claimer_b,
                ResolveOutcome as _ResolveOutcome_b,
            )
            for _r in rows:
                _sid = _r.get('__source_sheet_id')
                if _sid is None or _sid not in _discovery._FOLDER_DISCOVERED_SUB_IDS:
                    continue
                _rid = _r.get('__row_id')
                if not isinstance(_rid, int):
                    continue
                _wr_raw = _r.get('Work Request #')
                _ld = _r.get('Weekly Reference Logged Date')
                if not _wr_raw or not _ld or not is_checked(_r.get('Units Completed?')):
                    continue
                _we = excel_serial_to_date(_ld)
                if _we is None:
                    continue
                _we_d = _we.date() if isinstance(_we, datetime.datetime) else _we
                _eu = _r.get('__effective_user', 'Unknown Foreman')
                _wr_key_b = str(_wr_raw).split('.')[0]
                # HOLD only on a genuine transient outage, or on rpc_missing
                # when the operator has disabled the per-row fallback. On
                # rpc_missing WITH fallback on, route per-row (prefetched_map=
                # None) so B still generates with the real frozen claimer.
                if _attr_status == 'fetch_failure' or (
                    _attr_status == 'rpc_missing'
                    and not ATTRIBUTION_BULK_PREFETCH_FALLBACK
                ):
                    # D-04: construct HOLD directly, zero additional RPC calls.
                    _sub_primary_claimer_map[_rid] = _ResolveOutcome_b(
                        'hold', None, None, 'fetch_failure'
                    )
                else:
                    _sub_primary_claimer_map[_rid] = _resolve_claimer_b(
                        'reduced_sub', _eu,
                        wr=_wr_key_b,
                        week_ending=_we_d,
                        row_id=_rid,
                        enabled=SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED,
                        prefetched_map=(
                            None if _attr_use_per_row_fallback else _attr_map
                        ),
                    )
        except Exception:
            logging.exception(
                "⚠️ Subproject B attribution map-read failed; falling "
                "back to current foreman for all subcontractor rows"
            )
            _sub_primary_claimer_map = {}

    # ── Subproject C: O(1) map read for vac-crew claimers (D-03) ──
    # D-04 direct-HOLD on fetch_failure, zero additional Supabase calls.
    _vac_crew_claimer_map: dict = {}
    if BILLING_AUDIT_AVAILABLE and VAC_CREW_CLAIM_ATTRIBUTION_ENABLED:
        try:
            from billing_audit.writer import (
                resolve_claimer as _resolve_claimer_c,
                ResolveOutcome as _ResolveOutcome_c,
            )
            for _r in rows:
                _rid = _r.get('__row_id')
                if not isinstance(_rid, int):
                    continue
                if not _r.get('__is_vac_crew'):
                    continue
                _wr_raw = _r.get('Work Request #')
                _ld = _r.get('Weekly Reference Logged Date')
                if not _wr_raw or not _ld or not is_checked(_r.get('Units Completed?')):
                    continue
                _we = excel_serial_to_date(_ld)
                if _we is None:
                    continue
                _we_d = _we.date() if isinstance(_we, datetime.datetime) else _we
                _current_vac = _r.get('__vac_crew_name') or ''
                _wr_key_c = str(_wr_raw).split('.')[0]
                # HOLD only on a genuine transient outage, or on rpc_missing
                # when the operator has disabled the per-row fallback. On
                # rpc_missing WITH fallback on, route per-row (prefetched_map=
                # None) so C still generates with the real frozen claimer.
                if _attr_status == 'fetch_failure' or (
                    _attr_status == 'rpc_missing'
                    and not ATTRIBUTION_BULK_PREFETCH_FALLBACK
                ):
                    # D-04: construct HOLD directly, zero additional RPC calls.
                    _vac_crew_claimer_map[_rid] = _ResolveOutcome_c(
                        'hold', None, None, 'fetch_failure'
                    )
                else:
                    _vac_crew_claimer_map[_rid] = _resolve_claimer_c(
                        'vac_crew', _current_vac,
                        wr=_wr_key_c,
                        week_ending=_we_d,
                        row_id=_rid,
                        enabled=VAC_CREW_CLAIM_ATTRIBUTION_ENABLED,
                        prefetched_map=(
                            None if _attr_use_per_row_fallback else _attr_map
                        ),
                    )
        except Exception:
            logging.exception(
                "⚠️ Subproject C attribution map-read failed; falling "
                "back to current vac-crew name for all VAC Crew rows"
            )
            _vac_crew_claimer_map = {}

    # ── Subproject D: O(1) map read for primary claimers (D-03) ──
    # Unlike B/C, D never HOLDs on fetch_failure — the core primary path
    # prioritizes availability (operator decision; D uses-current on any
    # failure so all primary billing still ships).
    _primary_claimer_map: dict = {}
    if (
        BILLING_AUDIT_AVAILABLE
        and PRIMARY_CLAIM_ATTRIBUTION_ENABLED
        and RES_GROUPING_MODE in ('helper', 'both')
    ):
        try:
            from billing_audit.writer import (
                resolve_claimer as _resolve_claimer_d,
            )
            for _r in rows:
                _rid = _r.get('__row_id')
                if not isinstance(_rid, int):
                    continue
                if _r.get('__is_vac_crew'):
                    continue
                # Valid helper rows are excluded from the primary emission
                # path, so resolving their primary claimer is pure overhead.
                if (
                    _r.get('__is_helper_row')
                    and _r.get('__helper_foreman')
                    and _r.get('__helper_dept')
                ):
                    continue
                _sid = _r.get('__source_sheet_id')
                if _sid is not None and _sid in _discovery._FOLDER_DISCOVERED_SUB_IDS:
                    continue  # subcontractor rows are Sub-project B's domain
                _wr_raw = _r.get('Work Request #')
                _ld = _r.get('Weekly Reference Logged Date')
                if not _wr_raw or not _ld or not is_checked(_r.get('Units Completed?')):
                    continue
                _we = excel_serial_to_date(_ld)
                if _we is None:
                    continue
                _we_d = _we.date() if isinstance(_we, datetime.datetime) else _we
                _eu = _r.get('__effective_user', 'Unknown Foreman')
                _wr_key_d = str(_wr_raw).split('.')[0]
                # WR-03: D never HOLDs. On fetch_failure the bulk map is empty,
                # so the prefetched-map miss yields a ('use', current,
                # 'no_history') outcome and D emits with the current foreman —
                # D never HOLDs by design (core primary path prioritizes
                # availability). On rpc_missing with fallback on,
                # prefetched_map=None routes the per-row lookup_attribution
                # which returns the real frozen claimer.
                _primary_claimer_map[_rid] = _resolve_claimer_d(
                    'primary', _eu,
                    wr=_wr_key_d,
                    week_ending=_we_d,
                    row_id=_rid,
                    enabled=PRIMARY_CLAIM_ATTRIBUTION_ENABLED,
                    prefetched_map=(
                        None if _attr_use_per_row_fallback else _attr_map
                    ),
                )
        except Exception:
            logging.exception(
                "⚠️ Subproject D attribution map-read failed; falling "
                "back to current foreman for all primary rows"
            )
            _primary_claimer_map = {}

    # ── VAC-crew cross-row unit reconciliation (operator contract
    # 2026-06-08). A WR can span multiple source sheets: a foreman /
    # original-contract sheet (no VAC columns) AND a VAC-crew sheet (VAC
    # columns). The SAME physical unit can then exist as two rows — only the
    # VAC-sheet copy carries the VAC claim, so the row-local predicate cannot
    # see the claim on the foreman's copy and the unit leaks onto the foreman
    # sheet (duplicated with the VacCrew sheet). Build the set of VAC-claimed
    # unit identities up front so the non-VAC emission below can drop any unit
    # that is VAC-claimed on ANY row. Keyed at the UNIT grain
    # (WR + week + Point + CU) — NOT the pole — so the foreman's OTHER units on
    # the same pole are retained (operator: per-unit, not per-pole).
    _vac_claimed_units = set()
    for _vr in rows:
        if not _vr.get('__is_vac_crew'):
            continue
        # LOW-01 hardening (2026-06-27): mirror the consumer emission gate's
        # Units Completed? rule. A VAC claim may only suppress the
        # foreman/helper copy when the VAC crew is ACTUALLY billed for the
        # unit (Units Completed? checked). A VAC row without it is dropped
        # downstream, so suppressing the foreman's completed copy would bill
        # the unit to nobody (silent under-billing).
        if not is_checked(_vr.get('Units Completed?')):
            continue
        _vwr = _vr.get('Work Request #')
        _vdate_raw = _vr.get('Weekly Reference Logged Date')
        if not _vwr or not _vdate_raw:
            continue
        _vweek_date = excel_serial_to_date(_vdate_raw)
        if _vweek_date is None:
            continue
        _vpoint = str(
            _vr.get('Pole #') or _vr.get('Point #')
            or _vr.get('Point Number') or ''
        ).strip()
        _vcu = str(
            _vr.get('CU') or _vr.get('Billable Unit Code') or ''
        ).strip()
        if _vpoint and _vcu:
            _vac_claimed_units.add((
                str(_vwr).split('.')[0],
                _vweek_date.strftime("%m%d%y"),
                _vpoint,
                _vcu,
            ))

    for r in rows:
        wr = r.get('Work Request #')
        log_date_str = r.get('Weekly Reference Logged Date')
        units_completed = r.get('Units Completed?')
        total_price = parse_price(r.get('Units Total Price', 0))
        
        # Use __effective_user (set by dual-logic system in get_all_source_rows)
        effective_user = r.get('__effective_user', 'Unknown Foreman')
        assignment_method = r.get('__assignment_method', 'PATH_B_NO_CACHE_FILE')
        
        # Helper row metadata
        is_helper_row = r.get('__is_helper_row', False)
        helper_foreman = r.get('__helper_foreman', '')
        
        # Check if Units Completed? is true/1
        units_completed_checked = is_checked(units_completed)

        # REQUIRE: Work Request # AND Weekly Reference Logged Date AND Units Completed? = true/1 AND Units Total Price exists
        if not wr or not log_date_str or not units_completed_checked or total_price is None:
            continue # Skip if any essential grouping information is missing

        wr_key = str(wr).split('.')[0]
        
        try:
            # Parse the Weekly Reference Logged Date - this IS the week ending date
            week_ending_date = excel_serial_to_date(log_date_str)
            if week_ending_date is None:
                logging.warning(f"Could not parse Weekly Reference Logged Date '{log_date_str}' for WR# {wr_key}. Skipping row.")
                continue
            week_end_for_key = week_ending_date.strftime("%m%d%y")
            
            if TEST_MODE:
                logging.debug(f"WR# {wr_key}: Week ending {week_ending_date.strftime('%A, %m/%d/%Y')} | User: {effective_user} | Method: {assignment_method} | Helper: {is_helper_row}")
            
            # VARIANT-AWARE GROUPING: Build keys based on RES_GROUPING_MODE and row type
            keys_to_add = []
            
            # Check if this row was detected as VAC Crew (row-level column-based detection)
            is_vac_crew_row = r.get('__is_vac_crew', False)

            # Cross-row unit reconciliation: a non-VAC row whose unit
            # (WR + week + Point + CU) is VAC-claimed on ANOTHER source row is
            # the duplicate foreman/helper copy of a unit the VAC crew earns.
            # Drop it from ALL non-VAC variants (primary, helper, and the
            # subcontractor variants below) so the unit appears ONLY on the
            # VacCrew sheet (operator contract 2026-06-08; per-unit, not
            # per-pole). The VAC crew's own row is untouched.
            if not is_vac_crew_row:
                _unit_point = str(
                    r.get('Pole #') or r.get('Point #')
                    or r.get('Point Number') or ''
                ).strip()
                _unit_cu = str(
                    r.get('CU') or r.get('Billable Unit Code') or ''
                ).strip()
                if _unit_point and _unit_cu and (
                    wr_key, week_end_for_key, _unit_point, _unit_cu
                ) in _vac_claimed_units:
                    logging.info(
                        "➖ EXCLUDING from foreman/helper (unit VAC-claimed "
                        f"on another row): WR={wr_key}, "
                        f"Week={week_end_for_key}, Point={_unit_point}, "
                        f"CU={_unit_cu}"
                    )
                    continue

            # Phase 1.1 Bug B1 (D-04 / SUB-09): hoist
            # is_subcontractor_row to BEFORE the primary-emission
            # cascade AND the subcontractor variant emission block.
            # Both dependencies (r.get('__source_sheet_id') and
            # _FOLDER_DISCOVERED_SUB_IDS) are in scope at function
            # entry (verified per RESEARCH.md Pitfall 5). The same
            # computation was previously duplicated immediately before
            # the variant emission block downstream — that duplicate
            # site is now removed and the variable resolves to this
            # hoisted definition for BOTH the new partitioning gate
            # and the existing variant emission block. Hoist lives
            # OUTSIDE the ``if is_vac_crew_row:`` cascade so the
            # variant emission block (at per-row loop scope) still
            # sees the variable even when the row is VAC Crew (in
            # that case the variant block's outer
            # ``if is_subcontractor_row and ...`` gate still resolves
            # correctly).
            _row_sheet_id = r.get('__source_sheet_id')
            is_subcontractor_row = (
                _row_sheet_id is not None
                and _row_sheet_id in _discovery._FOLDER_DISCOVERED_SUB_IDS
            )

            # VAC Crew rows get their own dedicated group key (separate from primary/helper).
            # Detection is row-level: a row is VAC Crew when VAC Crew Helping? is non-blank
            # AND Vac Crew Completed Unit? is checked. This means the same sheet can produce
            # both primary/helper rows AND VAC Crew rows — they are mutually exclusive per-row
            # because a single row is either a VAC Crew row or a regular/helper row.
            if is_vac_crew_row:
                if not VAC_CREW_CLAIM_ATTRIBUTION_ENABLED:
                    # Kill switch OFF -> exact legacy behavior: one group per
                    # WR+week, no per-claimer partition.
                    vac_crew_key = f"{week_end_for_key}_{wr_key}_VACCREW"
                    # Use VAC Crew name (from 'VAC Crew Helping?' column) as the foreman
                    # for this group — NOT the primary foreman (effective_user).
                    vac_crew_foreman = r.get('__vac_crew_name') or effective_user
                    keys_to_add.append(('vac_crew', vac_crew_key, vac_crew_foreman))
                    # Only log at info level the first time a new group key is seen;
                    # subsequent rows belonging to the same WR/week VAC Crew group log at
                    # debug to avoid flooding logs with identical "GROUP CREATED" messages.
                    if vac_crew_key not in groups:
                        logging.info(f"🏗️ VAC CREW GROUP CREATED: WR={wr_key}, Week={week_end_for_key}")
                else:
                    # Subproject C: partition by frozen vac-crew claimer.
                    # Consume the pre-pass map. ``use`` -> partition by claimer;
                    # ``hold`` -> defer this row (correctness over availability);
                    # map miss (missing __row_id, pre-pass skipped, plumbing fault)
                    # -> use-current, NEVER HOLD.
                    _vac_current = r.get('__vac_crew_name') or effective_user
                    _c_vac_claimer = None
                    _vac_outcome = _vac_crew_claimer_map.get(r.get('__row_id'))
                    if _vac_outcome is not None and _vac_outcome.action == 'hold':
                        _c_vac_claimer = None  # defer — correctness over availability
                        try:
                            from billing_audit.writer import record_attribution_hold
                            record_attribution_hold(
                                wr_key,
                                week_ending_date.date()
                                if isinstance(week_ending_date, datetime.datetime)
                                else week_ending_date,
                                'vac_crew',
                            )
                        except Exception:
                            logging.exception(
                                "⚠️ Subproject C: record_attribution_hold failed"
                            )
                    elif _vac_outcome is not None and _vac_outcome.action == 'use':
                        _c_vac_claimer = _vac_outcome.name or _vac_current or 'Unknown'
                    else:
                        # Map miss (row absent from pre-pass) or unknown action:
                        # fall back to current name, never HOLD.
                        _c_vac_claimer = _vac_current or 'Unknown'

                    if _c_vac_claimer is not None:
                        _c_vac_sanitized = _RE_SANITIZE_IDENTIFIER.sub(
                            '_', _c_vac_claimer
                        )[:50]
                        vac_crew_key = (
                            f"{week_end_for_key}_{wr_key}_VACCREW_{_c_vac_sanitized}"
                        )
                        keys_to_add.append(('vac_crew', vac_crew_key, _c_vac_claimer))
                        if vac_crew_key not in groups:
                            logging.info(
                                f"🏗️ VAC CREW GROUP CREATED: WR={wr_key}, "
                                f"Week={week_end_for_key}"
                            )
            else:
                # Check if helper mode is enabled
                helper_mode_enabled = RES_GROUPING_MODE in ('helper', 'both')
                
                # Check if this is a valid helper row (both checkboxes checked, has helper info)
                valid_helper_row = False
                if helper_mode_enabled and is_helper_row and helper_foreman:
                    helper_dept = r.get('__helper_dept', '')
                    helper_job = r.get('__helper_job', '')
                    # Validate helper row: helper_dept is required, helper_job is OPTIONAL
                    # This allows rows to sync even when Helper Job # is missing
                    if helper_dept:  # helper_job is now optional
                        valid_helper_row = True
                
                # Primary variant logic
                if RES_GROUPING_MODE == 'primary':
                    # In primary mode, ALL rows go to main (including helper rows)
                    primary_key = f"{week_end_for_key}_{wr_key}"
                    keys_to_add.append(('primary', primary_key, None))
                elif RES_GROUPING_MODE in ('helper', 'both'):
                    # Phase 1.1 Bug B1 (D-04 / SUB-09): partitioning
                    # gate. Subcontractor non-helper rows do NOT emit
                    # the legacy primary key — their content lives
                    # exclusively in the _REDUCEDSUB (always) and
                    # _AEPBILLABLE (post-cutoff) variant files
                    # produced by the subcontractor variant block
                    # below. Primary / original-contract / vac_crew
                    # rows fall through unchanged. Plan 01-03 Test 1's
                    # "additive" contract is overridden per D-22;
                    # Living Ledger entry [Phase 1.1 timestamp]
                    # documents the design-intent change.
                    if not is_subcontractor_row and not valid_helper_row:
                        # Subproject D (2026-05-25): partition the
                        # production primary file by the FROZEN primary
                        # claimer. Consume the pre-pass map. ``use`` ->
                        # partition by claimer; ``hold`` (Supabase outage),
                        # map miss, or disabled -> use the current
                        # effective_user and STILL emit (D never holds —
                        # operator decision for the core path). Empty
                        # claimer -> 'Unknown Foreman' sentinel so the
                        # _User_ suffix builder never gets an empty
                        # identifier (mirrors B's Codex-P1 fix).
                        if PRIMARY_CLAIM_ATTRIBUTION_ENABLED:
                            _d_outcome = _primary_claimer_map.get(r.get('__row_id'))
                            if _d_outcome is not None and _d_outcome.action == 'use':
                                _d_claimer = (
                                    _d_outcome.name or effective_user or 'Unknown Foreman'
                                )
                            else:
                                # hold / map-miss / disabled / None -> current.
                                _d_claimer = effective_user or 'Unknown Foreman'
                            _d_claimer_sanitized = _RE_SANITIZE_IDENTIFIER.sub(
                                '_', _d_claimer
                            )[:50]
                            primary_key = (
                                f"{week_end_for_key}_{wr_key}_USER_"
                                f"{_d_claimer_sanitized}"
                            )
                            keys_to_add.append(('primary', primary_key, _d_claimer))
                            if primary_key not in groups:
                                logging.info(
                                    f"🧑 PRIMARY GROUP CREATED: WR={wr_key}, "
                                    f"Week={week_end_for_key}"
                                )
                        else:
                            # Kill switch OFF -> exact legacy bare primary.
                            primary_key = f"{week_end_for_key}_{wr_key}"
                            keys_to_add.append(('primary', primary_key, None))
                    elif is_subcontractor_row and not valid_helper_row:
                        # Diagnostic log only — no group emission.
                        # Operators can confirm the partition is
                        # firing by grepping for this prefix. PII
                        # marker "EXCLUDING from main Excel" already
                        # covers this body via existing
                        # _PII_LOG_MARKERS entry.
                        logging.debug(
                            f"➖ EXCLUDING from main Excel (subcontractor row): "
                            f"WR={wr_key}, Week={week_end_for_key}"
                        )
                    elif valid_helper_row:
                        # UNCHANGED legacy behaviour — helper row
                        # excluded from main Excel regardless of
                        # subcontractor/non-subcontractor.
                        logging.info(f"➖ EXCLUDING from main Excel: WR={wr_key}, Week={week_end_for_key} (Helper row with both checkboxes)")
                
                # Helper variant - ONLY created when mode allows it
                if valid_helper_row and helper_mode_enabled:
                    helper_dept = r.get('__helper_dept', '')
                    helper_job = r.get('__helper_job', '')
                    # PERFORMANCE: Use pre-compiled regex for helper name sanitization
                    helper_sanitized = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]
                    helper_key = f"{week_end_for_key}_{wr_key}_HELPER_{helper_sanitized}"
                    # Phase 1.1 UAT gap closure (SUB-09 helper dimension):
                    # mirror Bug B1's non-helper primary partition onto the
                    # helper path. Subcontractor helper rows do NOT emit the
                    # legacy `_HELPER_<name>` key — their line items live
                    # exclusively in the `_REDUCEDSUB_HELPER_<name>` (always)
                    # and `_AEPBILLABLE_HELPER_<name>` (post-cutoff) shadow
                    # files produced by the subcontractor variant block below.
                    # Pre-fix this append fired for ALL helper rows including
                    # subcontractor ones (the D-09 additive intent), producing
                    # a duplicate `_Helper_<name>` file on TARGET_SHEET_ID that
                    # duplicated the shadow file's line items. The guard is
                    # strictly `is_subcontractor_row`-scoped so primary /
                    # original-contract / vac_crew helper rows are byte-identical
                    # (ROADMAP success criterion #5). Living Ledger entry
                    # [2026-05-19] documents the asymmetry + fix.
                    if not is_subcontractor_row:
                        keys_to_add.append(('helper', helper_key, helper_foreman))
                        # HELPER GROUP LOGGING: Always log when helper group is created
                        logging.info(f"🔧 HELPER GROUP CREATED: WR={wr_key}, Week={week_end_for_key}, Helper={helper_foreman}, Dept={helper_dept}, Job={helper_job}")
                    else:
                        # Diagnostic log only — no legacy-helper group emission for
                        # subcontractor rows. Operators can confirm the partition
                        # is firing by grepping this prefix. PII marker
                        # "EXCLUDING from main Excel" already covers this body via
                        # the existing _PII_LOG_MARKERS entry.
                        logging.debug(
                            f"➖ EXCLUDING from main Excel (subcontractor legacy helper): "
                            f"WR={wr_key}, Week={week_end_for_key}, Helper={helper_foreman}"
                        )
                elif is_helper_row and not helper_mode_enabled:
                    # In primary mode, helper rows go to main
                    logging.info(f"ℹ️ Helper row found but RES_GROUPING_MODE={RES_GROUPING_MODE} - including in main Excel")
                elif is_helper_row:
                    # Helper row missing required helper_dept (helper_job is optional)
                    helper_dept = r.get('__helper_dept', '')
                    helper_job = r.get('__helper_job', '')
                    logging.warning(f"⚠️ Helper row for WR {wr_key} missing required Helper Dept # (Job: '{helper_job}') - including in main Excel")

            # ── Phase 01 Plan 03 (D-08/D-09/D-13/D-22): Subcontractor
            # rate variants. Per the committed Blocker 3 plumbing
            # decision the gate is PER-ROW, evaluated against the
            # row's ``__source_sheet_id`` (populated upstream by
            # ``_fetch_and_process_sheet``) and the kill-switch env
            # var. A subcontractor row produces:
            #   • a ``_REDUCEDSUB`` group key unconditionally (D-08
            #     / SUB-02 — every sub WR group always gets a
            #     reduced-sub Excel),
            #   • a ``_AEPBILLABLE`` group key when the row's
            #     ``Snapshot Date >= _AEP_BILLABLE_CUTOFF`` (D-08 /
            #     SUB-01 — snapshot is authoritative per Living
            #     Ledger 2026-04-21 22:35; never use Weekly Reference
            #     Logged Date here),
            #   • two ``_HELPER_<name>`` shadow keys when the
            #     existing helper-foreman event fires on this row
            #     (D-09 — shadows piggyback on the same
            #     ``valid_helper_row + helper_mode_enabled`` gate the
            #     legacy ``_HELPER_<name>`` key uses; the
            #     subcontractor sheet only contributes the new
            #     prefix tokens).
            # Non-subcontractor rows fall through with zero behaviour
            # change (per-row gate ensures no key bleed across rows
            # in the same call). Helper names are sanitized at the
            # producer site via ``_RE_SANITIZE_HELPER_NAME`` (D-22 /
            # Living Ledger 2026-04-23 18:25 — idempotent regex, so
            # the consumer site in ``generate_excel`` can safely
            # re-apply).
            #
            # Phase 1.1 Bug B1 (D-04 / SUB-09): the
            # ``is_subcontractor_row`` computation that used to live
            # here has been HOISTED to BEFORE the primary-emission
            # cascade above so the new partitioning gate can read it.
            # The hoisted variable is in scope for this block (Python
            # locals introduced earlier in the same function body
            # remain in scope), so the variant emission block below
            # reads the SAME boolean — no behavioural change to the
            # variant emission contract.
            # Copilot (PR #219): ``not is_vac_crew_row`` excludes VAC crew
            # rows from the subcontractor variant emission. ``__is_vac_crew``
            # is set by column presence (not sheet membership), so a VAC crew
            # row can come from a subcontractor-folder sheet; without this
            # gate it would be DOUBLE-emitted (VACCREW + REDUCEDSUB/AEPBILLABLE)
            # and a vac ``hold`` outcome would be bypassed by the sub variants.
            # A vac row already produced its own group above; it must not also
            # emit subcontractor primary variants.
            if is_subcontractor_row and not is_vac_crew_row and SUBCONTRACTOR_RATE_VARIANTS_ENABLED:
                # Snapshot cutoff is needed by BOTH the primary block
                # here and the helper-shadow block below, so compute it
                # once up front. ``excel_serial_to_date`` returns ``None``
                # for blank/unparseable values (D-16 fall-through safety).
                # Hoisted above the helper-completed guard so the
                # helper-shadow block still sees it even when the primary
                # emission is skipped.
                _snap_for_cutoff = excel_serial_to_date(r.get('Snapshot Date'))

                # 2026-05-21 hotfix (carried into Subproject B's _USER_
                # partitioning): a helper-COMPLETED subcontractor row
                # (``Units Completed?`` AND ``Helping Foreman Completed
                # Unit?`` both checked, with a valid ``Foreman Helping?``
                # + helper dept) belongs SOLELY to the helper-shadow files
                # below — the helper, not the primary foreman, earns the
                # credit for that line item on Smartsheet. Emitting a
                # primary ``_REDUCEDSUB_USER_`` / ``_AEPBILLABLE_USER_`` key
                # here would double-count the row (it would appear in BOTH
                # the primary and the helper file) and wrongly credit the
                # primary. Mirrors the legacy main-file ``valid_helper_row``
                # exclusion. Computed locally because the else-branch
                # ``valid_helper_row`` is out of scope for vac_crew rows;
                # uses the same inputs as the helper-shadow recompute below.
                _sub_is_valid_helper_row = (
                    not is_vac_crew_row
                    and RES_GROUPING_MODE in ('helper', 'both')
                    and is_helper_row
                    and bool(helper_foreman)
                    and bool(r.get('__helper_dept', ''))
                )

                # Subproject B: resolve the FROZEN primary claimer from
                # the pre-pass map. ``use`` -> partition by the claimer;
                # ``hold`` -> defer this row's primary variants this run
                # (correctness over availability) and record a HOLD; map
                # miss -> use the current effective_user. Skipped for
                # helper-completed rows — they are not primary claims, so
                # no claimer is resolved and no HOLD is recorded; the
                # ``None`` default routes through the
                # ``if _b_primary_claimer is not None`` gate below and
                # suppresses the primary _USER_ emission.
                _b_primary_claimer = None
                if not _sub_is_valid_helper_row:
                    _b_outcome = _sub_primary_claimer_map.get(r.get('__row_id'))
                    if _b_outcome is not None and _b_outcome.action == 'hold':
                        _b_primary_claimer = None
                        try:
                            from billing_audit.writer import record_attribution_hold
                            # Copilot: record_attribution_hold is typed
                            # ``datetime.date | None``; normalize the datetime
                            # week_ending_date to a pure date so the hold key
                            # is 'YYYY-MM-DD' (matching the pre-pass
                            # normalization for resolve_claimer), not
                            # 'YYYY-MM-DDT00:00:00'.
                            record_attribution_hold(
                                wr_key,
                                week_ending_date.date()
                                if isinstance(
                                    week_ending_date, datetime.datetime
                                )
                                else week_ending_date,
                                'reduced_sub',
                            )
                        except Exception:
                            logging.exception(
                                "⚠️ Subproject B: record_attribution_hold failed"
                            )
                    elif _b_outcome is not None and _b_outcome.action == 'use':
                        # Codex P1: fall back to a non-empty sentinel. A
                        # whitespace-only "Foreman Assigned?" yields an empty
                        # __effective_user upstream, and resolve_claimer's
                        # use/no_history then returns an empty name. Without
                        # this guard ``_b_primary_claimer`` would be '' yet
                        # still pass the ``is not None`` gate below, creating a
                        # _USER_ key with an empty claimer that crashes
                        # generate_excel at the suffix raise. 'Unknown Foreman'
                        # mirrors the foreman-assignment fallback sentinel and
                        # keeps the row's billing in a (clearly-flagged) file.
                        _b_primary_claimer = (
                            _b_outcome.name or effective_user or 'Unknown Foreman'
                        )
                    else:
                        _b_primary_claimer = effective_user or 'Unknown Foreman'

                if _b_primary_claimer is not None:
                    _b_claimer_sanitized = _RE_SANITIZE_IDENTIFIER.sub(
                        '_', _b_primary_claimer
                    )[:50]
                    # ReducedSub: unconditional per SUB-02 / D-08, now
                    # partitioned by frozen primary claimer (Subproject B).
                    reduced_key = (
                        f"{week_end_for_key}_{wr_key}_REDUCEDSUB_USER_"
                        f"{_b_claimer_sanitized}"
                    )
                    keys_to_add.append(
                        ('reduced_sub', reduced_key, _b_primary_claimer)
                    )
                    if reduced_key not in groups:
                        logging.info(
                            f"🔻 REDUCED SUB GROUP CREATED: WR={wr_key}, "
                            f"Week={week_end_for_key}"
                        )

                    # AEPBillable: snapshot-cutoff-gated per SUB-01 / D-08
                    # / Living Ledger 2026-04-21 22:35 (snapshot is
                    # authoritative; Weekly Reference Logged Date is NOT a
                    # valid fallback here).
                    if (
                        _snap_for_cutoff is not None
                        and _snap_for_cutoff.date() >= _AEP_BILLABLE_CUTOFF
                    ):
                        aep_key = (
                            f"{week_end_for_key}_{wr_key}_AEPBILLABLE_USER_"
                            f"{_b_claimer_sanitized}"
                        )
                        keys_to_add.append(
                            ('aep_billable', aep_key, _b_primary_claimer)
                        )
                        if aep_key not in groups:
                            logging.info(
                                f"💲 AEP BILLABLE GROUP CREATED: WR={wr_key}, "
                                f"Week={week_end_for_key}"
                            )

                # Helper-shadow variants: piggyback on the EXISTING
                # helper detection. The two gates that already
                # qualify a row for the legacy ``_HELPER_<name>``
                # key (valid_helper_row + helper_mode_enabled) also
                # qualify it for the shadow variants when the sheet
                # is subcontractor. This means a single helper-row
                # event on a subcontractor WR produces:
                #   • the legacy ``_HELPER_<name>`` group (already
                #     added above by the legacy branch when the
                #     gates fire),
                #   • the new ``_REDUCEDSUB_HELPER_<name>`` group
                #     (unconditional),
                #   • the new ``_AEPBILLABLE_HELPER_<name>`` group
                #     when snapshot >= cutoff.
                # ``helper_mode_enabled`` and ``valid_helper_row``
                # are computed in the non-vac_crew else-branch above
                # — they are out of scope here for vac_crew rows
                # (``is_vac_crew_row`` short-circuits this entire
                # else block). Re-evaluate the same gates locally to
                # keep the new code self-contained and to avoid
                # depending on the order of variable definitions in
                # the enclosing block (the legacy primary-vs-helper
                # cascade lives in the else branch but the new sub
                # block is at function scope inside the for-loop, so
                # mirror its inputs here for clarity).
                if not is_vac_crew_row:
                    _helper_mode_enabled = RES_GROUPING_MODE in ('helper', 'both')
                    _valid_helper_row = False
                    if _helper_mode_enabled and is_helper_row and helper_foreman:
                        _helper_dept_local = r.get('__helper_dept', '')
                        if _helper_dept_local:
                            _valid_helper_row = True
                    if _valid_helper_row and _helper_mode_enabled:
                        # Phase 1.1 Bug C (D-10..D-16 / SUB-11):
                        # per-row claim-history attribution. For
                        # subcontractor rows ONLY (D-15), partition
                        # shadow-variant rows by the FROZEN helper
                        # foreman in
                        # ``billing_audit.attribution_snapshot``
                        # rather than the current Smartsheet
                        # ``Foreman Helping?`` value. This is what
                        # makes a foreman who helped Mon-Tue keep
                        # their partitioned helper file even after a
                        # Wed swap on the Smartsheet column.
                        #
                        # Fall-back contract (D-12): when the reader
                        # returns None (no frozen row yet →
                        # no_history, OR PostgREST outage →
                        # fetch_failure, OR kill switch off →
                        # disabled), the row joins the helper file of
                        # the CURRENT ``helper_foreman`` from
                        # Smartsheet. Safe default — helper files
                        # never silently empty.
                        #
                        # Per-WR dedupe (RESEARCH.md §C Pitfall 1):
                        # the fall-back WARNING fires ONCE per
                        # (wr, week, current_helper) tuple, NOT
                        # per-row. Without the dedupe, a 100-row
                        # fall-back run would log 100 identical
                        # WARNINGs.
                        _attributed_helper = helper_foreman  # D-12 default
                        _attribution_reason: str | None = None
                        # Phase 2 Plan 02 (D-03): O(1) map read from the
                        # shared _attr_map built by prefetch_attribution.
                        # No per-row Supabase RPC; no recency scope gate
                        # (D-05 removed ATTRIBUTION_RESOLUTION_WEEKS entirely).
                        if (
                            is_subcontractor_row
                            and SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED
                            and (
                                _attr_status == 'fetch_failure'
                                or (
                                    _attr_status == 'rpc_missing'
                                    and not ATTRIBUTION_BULK_PREFETCH_FALLBACK
                                )
                            )
                        ):
                            # WR-05: surface the outage explicitly. Sub-helper
                            # does NOT HOLD (Phase 1.1 design) — it falls back
                            # to the current `Foreman Helping?` (D-12 default),
                            # but now LOGS the reason via the per-WR WARNING
                            # below, restoring the Bug C observability the bulk
                            # path dropped. No per-row RPC issued on this path.
                            _attribution_reason = 'fetch_failure'
                        elif (
                            is_subcontractor_row
                            and SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED
                        ):
                            try:
                                from billing_audit.writer import (
                                    resolve_claimer as _resolve_claimer_sh,
                                )
                                _sh_rid = r.get('__row_id')
                                _sh_out = _resolve_claimer_sh(
                                    'helper', helper_foreman,
                                    wr=wr_key,
                                    week_ending=week_ending_date,
                                    row_id=_sh_rid,
                                    enabled=SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED,
                                    prefetched_map=(
                                        None if _attr_use_per_row_fallback
                                        else _attr_map
                                    ),
                                )
                                if _sh_out.action == 'use':
                                    _attributed_helper = (
                                        _sh_out.name or helper_foreman
                                    )
                                    # F1 fix: a genuine no-history row returns
                                    # action='use' with reason='no_history'
                                    # (writer.py:1048-1049, 1060). Propagate
                                    # it so the per-WR fallback WARNING below
                                    # fires; a real frozen/current 'success'
                                    # attribution stays silent (reason=None).
                                    _attribution_reason = (
                                        'no_history'
                                        if _sh_out.reason == 'no_history'
                                        else None
                                    )
                                elif _sh_out.action == 'hold':
                                    # fetch_failure: D-12 default (current
                                    # helper), flag for WARNING below.
                                    _attribution_reason = 'fetch_failure'
                                else:
                                    # 'disabled' or 'no_history': use D-12 default
                                    _attribution_reason = (
                                        _sh_out.reason
                                        if _sh_out.reason in ('no_history', 'fetch_failure')
                                        else None
                                    )
                            except Exception:
                                # Defense-in-depth: pipeline MUST NEVER
                                # crash on a reader failure — D-12 default.
                                logging.exception(
                                    "⚠️ Subcontractor helper claim "
                                    "attribution map-read: unexpected "
                                    "error (treating as fetch_failure)"
                                )
                                _attribution_reason = 'fetch_failure'

                        # Per-WR dedupe WARNING — operator-actionable,
                        # names the reason. `_bug_c_warning_seen` is
                        # initialized at function scope (set
                        # construction at top of `group_source_rows`).
                        # Tuple key uses sanitized helper for
                        # set-membership stability.
                        if (
                            is_subcontractor_row
                            and SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED
                            and _attribution_reason in ('no_history', 'fetch_failure')
                        ):
                            _warning_helper_key = _RE_SANITIZE_HELPER_NAME.sub(
                                '_', helper_foreman
                            )[:50]
                            _warning_key = (
                                wr_key, week_end_for_key, _warning_helper_key
                            )
                            if _warning_key not in _bug_c_warning_seen:
                                _bug_c_warning_seen.add(_warning_key)
                                # Remediation text branches by reason. The two
                                # fallback reasons are NOT the same severity:
                                #   fetch_failure → a genuine PostgREST outage
                                #     (the lookup RPC errored): point the
                                #     operator at Supabase Logs to confirm and
                                #     clear the outage.
                                #   no_history → the BENIGN brand-new-claim
                                #     case: the lookup SUCCEEDED, there is just
                                #     no frozen row yet (this run freezes it).
                                #     A PGRST outage hunt here is a false lead —
                                #     so the remediation must NOT cite PGRST.
                                if _attribution_reason == 'fetch_failure':
                                    _remediation = (
                                        "To investigate: check Supabase Logs "
                                        "for PGRST106/PGRST301/PGRST404 on the "
                                        "'lookup_attribution' op."
                                    )
                                else:  # no_history
                                    _remediation = (
                                        "No frozen attribution exists yet — "
                                        "this run freezes it; no action needed "
                                        "unless a prior frozen claim was "
                                        "expected for this helper."
                                    )
                                # PII marker: "Subcontractor helper
                                # claim attribution fallback" — added
                                # to _PII_LOG_MARKERS in Step 2.
                                logging.warning(
                                    f"⚠️ Subcontractor helper claim "
                                    f"attribution fallback for "
                                    f"WR={wr_key} week={week_end_for_key} "
                                    f"helper={_warning_helper_key} "
                                    f"(reason={_attribution_reason}). "
                                    f"Helper file rows will fall back to "
                                    f"the current `Foreman Helping?` "
                                    f"value. {_remediation}"
                                )

                        # Use the attributed helper (or current helper
                        # on fall-back) for shadow-variant
                        # sanitization. Phase 1 emission body
                        # downstream is UNCHANGED — only the input
                        # value to the sanitizer changes.
                        _helper_sanitized = (
                            _RE_SANITIZE_HELPER_NAME.sub('_', _attributed_helper)[:50]
                        )
                        rs_helper_key = (
                            f"{week_end_for_key}_{wr_key}_REDUCEDSUB_HELPER_"
                            f"{_helper_sanitized}"
                        )
                        keys_to_add.append(
                            ('reduced_sub_helper', rs_helper_key, _attributed_helper)
                        )
                        if rs_helper_key not in groups:
                            logging.info(
                                f"🔻 REDUCED SUB HELPER GROUP CREATED: "
                                f"WR={wr_key}, Week={week_end_for_key}, "
                                f"Helper={_attributed_helper}"
                            )
                        if (
                            _snap_for_cutoff is not None
                            and _snap_for_cutoff.date() >= _AEP_BILLABLE_CUTOFF
                        ):
                            aep_helper_key = (
                                f"{week_end_for_key}_{wr_key}_AEPBILLABLE_HELPER_"
                                f"{_helper_sanitized}"
                            )
                            keys_to_add.append(
                                (
                                    'aep_billable_helper',
                                    aep_helper_key,
                                    _attributed_helper,
                                )
                            )
                            if aep_helper_key not in groups:
                                logging.info(
                                    f"💲 AEP BILLABLE HELPER GROUP CREATED: "
                                    f"WR={wr_key}, Week={week_end_for_key}, "
                                    f"Helper={_attributed_helper}"
                                )

            # Add row to all applicable groups
            for variant, key, current_foreman in keys_to_add:
                # Add calculated values to row data
                r_copy = r.copy()
                r_copy['__variant'] = variant
                r_copy['__current_foreman'] = current_foreman or effective_user
                r_copy['__week_ending_date'] = week_ending_date
                r_copy['__grouping_key'] = key
                groups[key].append(r_copy)
                
                if TEST_MODE:
                    logging.debug(f"Added to {variant} group '{key}': {len(groups[key])} rows")
                
        except (parser.ParserError, TypeError) as e:
            logging.warning(f"Could not parse Weekly Reference Logged Date '{log_date_str}' for WR# {wr_key}. Skipping row. Error: {e}")
            continue
    
    # FINAL VALIDATION: Ensure each group contains only one work request
    validation_errors = []
    for group_key, group_rows in groups.items():
        unique_wrs = list(set(str(row.get('Work Request #', '')).split('.')[0] for row in group_rows))
        if len(unique_wrs) != 1:
            validation_errors.append(f"Group {group_key} contains {len(unique_wrs)} work requests: {unique_wrs}")
    
    if validation_errors:
        error_msg = "CRITICAL GROUPING ERRORS: " + "; ".join(validation_errors)
        logging.error(error_msg)
        sentry_capture_message_with_context(
            message=error_msg,
            level="error",
            context_name="grouping_validation",
            context_data={
                "total_groups": len(groups),
                "validation_errors": validation_errors,
                "error_count": len(validation_errors),
            },
            tags={"error_location": "group_validation", "error_type": "data_integrity"}
        )
    else:
        logging.info(f"✅ Grouping validation passed: {len(groups)} groups, each with exactly 1 work request")
    
    # HELPER GROUP SUMMARY LOGGING
    helper_groups = [k for k in groups.keys() if '_HELPER_' in k]
    vac_crew_groups = [k for k in groups.keys() if '_VACCREW' in k]
    primary_groups = [k for k in groups.keys() if '_HELPER_' not in k and '_VACCREW' not in k]
    if helper_groups:
        logging.info(f"🔧 HELPER GROUP SUMMARY: Created {len(helper_groups)} helper groups out of {len(groups)} total groups")
        logging.info(f"   Primary groups: {len(primary_groups)}")
        logging.info(f"   Helper groups: {len(helper_groups)}")
        # Log sample helper groups
        for helper_key in helper_groups[:5]:
            row_count = len(groups[helper_key])
            logging.info(f"   Helper group '{helper_key}': {row_count} rows")
    else:
        logging.warning(f"⚠️ HELPER GROUP SUMMARY: No helper groups created out of {len(groups)} total groups - check RES_GROUPING_MODE and helper row detection")
    if vac_crew_groups:
        logging.info(f"🏗️ VAC CREW GROUP SUMMARY: Created {len(vac_crew_groups)} VAC Crew group(s) out of {len(groups)} total groups")
        for vac_key in vac_crew_groups[:5]:
            logging.info(f"   VAC Crew group '{vac_key}': {len(groups[vac_key])} rows")
    
    # Optional filtering by WR_FILTER (retain primary, helper, and vac_crew variants)
    if WR_FILTER and TEST_MODE:
        before = len(groups)
        def _key_matches_wr(k: str, wr: str) -> bool:
            # k format examples (all eleven shapes emitted by group_source_rows):
            #   MMDDYY_WR                                   → primary
            #   MMDDYY_WR_USER_<name>                       → primary (Subproject D)
            #   MMDDYY_WR_HELPER_<name>                     → helper
            #   MMDDYY_WR_VACCREW                           → vac_crew
            #   MMDDYY_WR_VACCREW_<claimer>                 → vac_crew (Subproject C)
            #   MMDDYY_WR_REDUCEDSUB                        → reduced_sub  (Phase 1)
            #   MMDDYY_WR_AEPBILLABLE                       → aep_billable (Phase 1)
            #   MMDDYY_WR_REDUCEDSUB_HELPER_<name>          → reduced_sub_helper  (Phase 1)
            #   MMDDYY_WR_AEPBILLABLE_HELPER_<name>         → aep_billable_helper (Phase 1)
            #   MMDDYY_WR_REDUCEDSUB_USER_<claimer>         → reduced_sub  (Subproject B)
            #   MMDDYY_WR_AEPBILLABLE_USER_<claimer>        → aep_billable (Subproject B)
            #
            # Phase 01 gap closure (REVIEW-CR-03): mirror of the
            # ``_key_matches_excluded_wr`` fix immediately below. Without the
            # new variant clauses, ``TEST_MODE=true WR_FILTER=<wr>`` drops
            # the new-variant groups before generation runs, silently
            # producing zero ``_AEPBillable`` / ``_ReducedSub`` output for the
            # filtered WR — which makes the Step B operator diagnostic
            # documented in 01-VERIFICATION.md unexercisable. Match shape is
            # IDENTICAL to ``_key_matches_excluded_wr``. The two matchers
            # MUST stay in sync — any future variant added in
            # ``group_source_rows`` must extend BOTH.
            try:
                suffix = k.split('_', 1)[1]  # take everything after first underscore (WR...)
            except Exception:
                return False
            return (
                suffix == wr
                # Subproject D: per-claimer primary key {wr}_USER_<claimer>
                # (attribution on). Mirror of the _key_matches_excluded_wr
                # clause below — the two matchers MUST stay in sync.
                or suffix.startswith(f"{wr}_USER_")
                or suffix.startswith(f"{wr}_HELPER_")
                or suffix == f"{wr}_VACCREW"
                # Subproject C: per-claimer vac key {wr}_VACCREW_<claimer>
                # (attribution on). Prefix-match so EXCLUDE_WRS / WR_FILTER
                # cover both the legacy bare and the per-claimer shapes.
                or suffix.startswith(f"{wr}_VACCREW_")
                # Phase 1 subcontractor variants (REVIEW-CR-03).
                or suffix == f"{wr}_REDUCEDSUB"
                or suffix == f"{wr}_AEPBILLABLE"
                or suffix.startswith(f"{wr}_REDUCEDSUB_HELPER_")
                or suffix.startswith(f"{wr}_AEPBILLABLE_HELPER_")
                # Subproject B: per-claimer subcontractor primary keys
                # {wr}_REDUCEDSUB_USER_<claimer> / {wr}_AEPBILLABLE_USER_<claimer>
                # (attribution on — the production default). Prefix-match so
                # WR_FILTER / EXCLUDE_WRS cover the partitioned shape, not just
                # the bare _REDUCEDSUB / _AEPBILLABLE. Mirror in BOTH matchers.
                or suffix.startswith(f"{wr}_REDUCEDSUB_USER_")
                or suffix.startswith(f"{wr}_AEPBILLABLE_USER_")
            )

        groups = {k: v for k, v in groups.items() if any(_key_matches_wr(k, wr) for wr in WR_FILTER)}
        logging.info(f"🔎 WR_FILTER applied (primary + helper + vac_crew): {len(groups)}/{before} groups retained ({','.join(WR_FILTER)})")
    
    # EXCLUDE_WRS: Remove specific Work Requests from generation (applies always, not just TEST_MODE)
    if EXCLUDE_WRS:
        before_exclude = len(groups)
        logging.info(f"🔍 EXCLUDE_WRS check: Attempting to exclude WRs {EXCLUDE_WRS} from {before_exclude} groups")
        
        # Debug: Show sample group keys for troubleshooting
        sample_keys = list(groups.keys())[:5]
        logging.info(f"🔍 Sample group keys: {sample_keys}")
        
        def _key_matches_excluded_wr(k: str, wr: str) -> bool:
            # k format examples (all eleven shapes emitted by group_source_rows):
            #   MMDDYY_WR                                   → primary
            #   MMDDYY_WR_USER_<name>                       → primary (Subproject D)
            #   MMDDYY_WR_HELPER_<name>                     → helper
            #   MMDDYY_WR_VACCREW                           → vac_crew
            #   MMDDYY_WR_VACCREW_<claimer>                 → vac_crew (Subproject C)
            #   MMDDYY_WR_REDUCEDSUB                        → reduced_sub  (Phase 1)
            #   MMDDYY_WR_AEPBILLABLE                       → aep_billable (Phase 1)
            #   MMDDYY_WR_REDUCEDSUB_HELPER_<name>          → reduced_sub_helper  (Phase 1)
            #   MMDDYY_WR_AEPBILLABLE_HELPER_<name>         → aep_billable_helper (Phase 1)
            #   MMDDYY_WR_REDUCEDSUB_USER_<claimer>         → reduced_sub  (Subproject B)
            #   MMDDYY_WR_AEPBILLABLE_USER_<claimer>        → aep_billable (Subproject B)
            #
            # Phase 01 gap closure (REVIEW-CR-02): before this fix the matcher
            # only recognized the first four shapes, so EXCLUDE_WRS=<wr>
            # silently uploaded the four new variant files to TARGET_SHEET_ID
            # and SUBCONTRACTOR_PPP_SHEET_ID even when the operator's intent
            # was "do not bill yet." The additive ``or`` clauses below close
            # that gap. Match shape mirrors ``_key_matches_wr``; the two
            # matchers are siblings and MUST stay in sync — any future
            # variant added in ``group_source_rows`` must extend BOTH.
            try:
                suffix = k.split('_', 1)[1]  # take everything after first underscore (WR...)
            except Exception:
                return False
            return (
                suffix == wr
                or suffix.startswith(f"{wr}_HELPER_")
                or suffix.startswith(f"{wr}_USER_")
                or suffix == f"{wr}_VACCREW"
                # Subproject C: per-claimer vac key {wr}_VACCREW_<claimer>
                # (attribution on). Prefix-match so EXCLUDE_WRS / WR_FILTER
                # cover both the legacy bare and the per-claimer shapes.
                or suffix.startswith(f"{wr}_VACCREW_")
                # Phase 1 subcontractor variants (REVIEW-CR-02).
                or suffix == f"{wr}_REDUCEDSUB"
                or suffix == f"{wr}_AEPBILLABLE"
                or suffix.startswith(f"{wr}_REDUCEDSUB_HELPER_")
                or suffix.startswith(f"{wr}_AEPBILLABLE_HELPER_")
                # Subproject B: per-claimer subcontractor primary keys
                # {wr}_REDUCEDSUB_USER_<claimer> / {wr}_AEPBILLABLE_USER_<claimer>
                # (attribution on — the production default). EXCLUDE_WRS is
                # production-active, so without these the operator's "do not
                # bill yet" intent silently failed for partitioned sub primary
                # files. Mirror of _key_matches_wr — the two MUST stay in sync.
                or suffix.startswith(f"{wr}_REDUCEDSUB_USER_")
                or suffix.startswith(f"{wr}_AEPBILLABLE_USER_")
            )
        
        # Remove groups that match any excluded WR
        groups = {k: v for k, v in groups.items() if not any(_key_matches_excluded_wr(k, wr) for wr in EXCLUDE_WRS)}
        excluded_count = before_exclude - len(groups)
        if excluded_count > 0:
            logging.info(f"🚫 EXCLUDE_WRS applied: {excluded_count} groups excluded ({','.join(EXCLUDE_WRS)}) - {len(groups)} groups remaining")
        else:
            logging.info(f"🚫 EXCLUDE_WRS specified but no matching groups found to exclude ({','.join(EXCLUDE_WRS)})")
    
    return groups


def validate_group_totals(groups):
    """Compute and validate totals per group, returning summary list of dicts."""
    summaries = []
    for key, rows in groups.items():
        total = sum(parse_price(r.get('Units Total Price')) for r in rows)
        summaries.append({'group_key': key, 'rows': len(rows), 'total': round(total,2)})
    return summaries
