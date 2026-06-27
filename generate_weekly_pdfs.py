#!/usr/bin/env python3
"""
Weekly PDF Generator with Complete Fixes
Generates Excel reports from Smartsheet data for weekly billing periods.

FIXES IMPLEMENTED:
- WR 90093002 Excel generation fix
- WR 89954686 specific handling 
- Proper file deletion logic
- Complete audit system integration
- All incomplete code sections completed
"""

import os
import datetime
import logging
import smartsheet
import smartsheet.exceptions as ss_exc

# Upstream SDK workaround: smartsheet-python-sdk 3.8.0 raises an
# AttributeError from smartsheet.smartsheet.Smartsheet._request_with_retry
# whenever the API returns a retryable error (429, 5xx). At
# smartsheet/smartsheet.py:303 it does
# ``getattr(sys.modules[__name__], native.result.name)`` to look up the
# exception class to raise, but that module's top-level imports only
# expose ApiError / HttpError / UnexpectedRequestError. The retryable
# exception classes (RateLimitExceededError, UnexpectedErrorShouldRetry-
# Error, InternalServerError, ServerTimeoutExceededError, SystemMainte-
# nanceError) live in smartsheet.exceptions and were never re-exported
# into smartsheet.smartsheet, so the getattr fails and our retry
# wrapper never gets the real exception. Re-export the missing names
# here so the SDK's internal lookup succeeds. The ``if not hasattr``
# guard makes this a no-op if the upstream SDK ever re-exports them.
import smartsheet.smartsheet as _ss_smartsheet_module
_exc_name = None
for _exc_name in (
    'RateLimitExceededError',
    'UnexpectedErrorShouldRetryError',
    'InternalServerError',
    'ServerTimeoutExceededError',
    'SystemMaintenanceError',
):
    if not hasattr(_ss_smartsheet_module, _exc_name) and hasattr(ss_exc, _exc_name):
        setattr(_ss_smartsheet_module, _exc_name, getattr(ss_exc, _exc_name))
del _ss_smartsheet_module
del _exc_name
from dotenv import load_dotenv
import signal

# Load environment variables
load_dotenv()


# Suppress BrokenPipeError when piping output (e.g. | head, | grep -m) so it doesn't surface as an exception
try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # type: ignore[attr-defined]
except Exception:
    pass

# Import audit system with error handling
try:
    from audit_billing_changes import BillingAudit  # type: ignore
    AUDIT_SYSTEM_AVAILABLE = True
    print("🔍 Billing audit system loaded successfully")
except ImportError as e:
    print(f"⚠️ Billing audit system not available: {e}")
    AUDIT_SYSTEM_AVAILABLE = False
    class BillingAudit:
        def __init__(self, *args, **kwargs):
            pass
        def audit_financial_data(self, *args, **kwargs):
            return {"summary": {"risk_level": "UNKNOWN"}}

# Import billing audit attribution snapshot writer (shadow mode).
# Failures here must NEVER break Excel generation — the writer is a
# strictly additive, flag-gated, no-op-on-failure surface. Catch
# broad Exception (not just ImportError) so a runtime error inside
# billing_audit/* during module init cannot crash the pipeline. We
# log the class name only to avoid leaking any contextual detail.
try:
    from billing_audit import writer as _billing_audit_writer
    from billing_audit.fingerprint import compute_assignment_fingerprint
    BILLING_AUDIT_AVAILABLE = True
    print("❄️ Billing audit snapshot writer loaded successfully")
except Exception as e:
    print(
        "⚠️ Billing audit snapshot writer not available: "
        f"{type(e).__name__}"
    )
    BILLING_AUDIT_AVAILABLE = False
    # Bind the writer to None on failure so the eager
    # ``billing_audit_writer=_billing_audit_writer`` reference at the
    # ``_resolve_unchanged_for_skip`` call site (gated only by
    # ``_history_eligible_for_skip``, NOT by BILLING_AUDIT_AVAILABLE)
    # degrades to None instead of raising NameError. The consumer's
    # ``_writer is not None`` guard then falls back to the JSON cache.
    # This preserves the no-op-on-failure invariant above. The
    # success-path import binds this name to a Module, so mypy flags
    # the None rebind; None is exactly the graceful-degradation
    # sentinel the consumer guard expects, hence the inline ignore.
    _billing_audit_writer = None  # type: ignore[assignment]

# 🎯 SHOW OUR FIXES ARE ACTIVE
print("✅ CRITICAL FIXES APPLIED:")
print("   • WR 90093002 Excel generation fix - ACTIVE")
print("   • WR 89954686 specific handling - ACTIVE")
print("   • MergedCell assignment errors - FIXED")
print("   • Type ignore comments - APPLIED")
print("🚀 SYSTEM READY FOR PRODUCTION")
print("=" * 60)

# Configure logging early
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('smartsheet.smartsheet').setLevel(logging.CRITICAL)


# -------------------------------------------------------------------------
# Phase 09 Wave 1: configuration relocated to pipeline/config.py.
# Imported FIRST so its import-time env parsing / regex compile / folder-ID
# parsing / startup banners fire in the original order (D-04). load_dotenv()
# above has already populated os.environ before this import runs.
# -------------------------------------------------------------------------
from pipeline import config  # noqa: E402,F401  (import-time env-parse side effects)
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

# Constants relocated in later Phase 09 waves (W2 pricing, W3 discovery/fetch,
# W5 attribution) stay in the facade for now and resolve the config helpers
# above (``_parse_sheet_ids`` / ``_sanitize_csv_path`` / ``_coerce_sheet_id``)
# via the re-import block:


# -- Phase 09 W2: pricing relocated to pipeline/pricing.py (D-02) --------
# Rate loaders, price resolution, the RATE_RECALC legacy gate, and the
# subcontractor rates table now live in pipeline/pricing.py. Re-imported
# here (before the import-time rate banners below) so the public surface and
# the startup banners that report these resolved values stay byte-identical.
# SUBCONTRACTOR_PPP_SHEET_ID + _RATES_FINGERPRINT stay facade-resident
# (reload-recompute test / W3 fetch ownership).
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

# ── Subcontractor rate variants (Phase 1 SUB-01..07) ───────────────────
# See .planning/phases/01-subcontractor-rate-logic-modification/
# 01-CONTEXT.md decisions D-03, D-12, D-13. These three env vars
# scaffold the new ``_AEPBillable`` and ``_ReducedSub`` variant
# pipeline:
#
#   SUBCONTRACTOR_RATES_CSV — path to the operator-managed contract
#       CSV (17 columns, currency-formatted). Default
#       ``data/subcontractor_rates.csv``. Resolved through the same
#       ``_sanitize_csv_path`` helper used by the retired
#       ``NEW_RATES_CSV`` / ``OLD_RATES_CSV`` env vars, which guards
#       against directory traversal and symlink escape per the CodeQL
#       taint-analysis pattern.
#   SUBCONTRACTOR_PPP_SHEET_ID — second target sheet for ``_ReducedSub``
#       attachments. Default ``8162920222379908``. Parsed through
#       ``_coerce_sheet_id`` for parse-error fallback.
#   SUBCONTRACTOR_RATE_VARIANTS_ENABLED — default-on kill switch for
#       the entire new variant pipeline. Pattern mirrors
#       ``RATE_RECALC_SKIP_ORIGINAL_CONTRACT`` and
#       ``RATE_RECALC_WEEKLY_FALLBACK``. Flipping this to ``0`` /
#       ``false`` / ``no`` / ``off`` reverts subcontractor-folder
#       sheets to pre-change behavior on the next run.
#
# Per Living Ledger 2026-04-24 14:30: do NOT re-introduce
# ``RATE_CUTOFF_DATE`` / ``NEW_RATES_CSV`` / ``OLD_RATES_CSV``. The
# new env vars are the subcontractor-specific replacement.
SUBCONTRACTOR_PPP_SHEET_ID = _coerce_sheet_id(
    os.getenv('SUBCONTRACTOR_PPP_SHEET_ID', '8162920222379908'),
    8162920222379908,
)
# Phase 01 gap closure (REVIEW-WR-02): treat an explicitly-empty
# ``SUBCONTRACTOR_PPP_SHEET_ID=''`` as "disable dual routing,"
# matching the operator-facing documentation in
# website/docs/reference/environment.md and the operator's likely
# intent. ``_coerce_sheet_id`` itself stays as-is because it is
# shared with ``TARGET_SHEET_ID`` where default-fallback is the
# correct behavior (TARGET_SHEET_ID has no "disabled" state).
# Setting to ``0`` also disables (already worked pre-fix; the
# downstream gate ``and SUBCONTRACTOR_PPP_SHEET_ID`` evaluates
# False on int(0)). After this fix, both ``0`` and ``''`` disable.
# Any other non-integer / non-empty value falls back to the
# hardcoded default with the existing _coerce_sheet_id WARNING.
if os.getenv('SUBCONTRACTOR_PPP_SHEET_ID', '8162920222379908') == '':
    SUBCONTRACTOR_PPP_SHEET_ID = 0

# Cutoff date for ``_AEPBillable`` variant generation. Awarded to
# Linetec on 2026-04-12 (subcontractor rate contract). Plan 2 (parser
# extension) and Plan 3 (variant emission) gate variant emission on
# ``Snapshot Date >= _AEP_BILLABLE_CUTOFF``. Exposed at module level
# so downstream plans can reference a single source of truth.
#
# Phase 01 gap closure (REVIEW-IN-01): exposed as
# ``AEP_BILLABLE_CUTOFF`` env var with safe parse + fallback to
# the contract-award default. Operators can roll forward (or back,
# for retroactive billing decisions) without a code change.
# Format: ``YYYY-MM-DD``. Invalid format logs an error and falls
# back to the default. Default is byte-identical to the pre-fix
# constant — IN-01 is additive (override path), no behavior
# regression for the unset / valid-format cases. The ``RATE_CUTOFF_DATE``
# env var (retired 2026-04-24 14:30) is NOT reused — this is a new
# distinct env var with explicit subcontractor-variant scope.
_aep_billable_cutoff_env = os.getenv('AEP_BILLABLE_CUTOFF', '')
try:
    _AEP_BILLABLE_CUTOFF = (
        datetime.datetime.strptime(
            _aep_billable_cutoff_env, '%Y-%m-%d'
        ).date()
        if _aep_billable_cutoff_env
        else datetime.date(2026, 4, 12)
    )
except ValueError:
    logging.error(
        f"⚠️ Invalid AEP_BILLABLE_CUTOFF format: "
        f"{_aep_billable_cutoff_env!r}; expected YYYY-MM-DD. "
        f"Falling back to default 2026-04-12."
    )
    _AEP_BILLABLE_CUTOFF = datetime.date(2026, 4, 12)

if RATE_CUTOFF_DATE:
    logging.info(f"📊 Rate contract versioning ENABLED: cutoff date = {RATE_CUTOFF_DATE.isoformat()}")
    # The CSV-side rate recalc was retired in production on
    # 2026-04-24 because Smartsheet now emits the authoritative
    # Units Total Price natively for ORIGINAL_CONTRACT_FOLDER_IDS
    # post-cutoff rows. The production workflow pins
    # RATE_CUTOFF_DATE='' so this branch should not fire on
    # scheduled runs anymore. If it DOES fire, something has
    # bypassed the workflow pinning (local dev shell, an ad-hoc
    # script, a re-introduced repo Variable) — surface that loudly
    # so operators can double-check the pricing source before
    # trusting the output.
    logging.warning(
        "⚠️ RATE_CUTOFF_DATE is set, but the Python CSV-side rate "
        "recalc feature has been retired — Smartsheet now emits "
        "the authoritative Units Total Price natively on "
        "ORIGINAL_CONTRACT_FOLDER_IDS sheets, and the production "
        "workflow pins RATE_CUTOFF_DATE='' as of 2026-04-24. "
        "Unset RATE_CUTOFF_DATE to silence this warning. See "
        "CLAUDE.md Living Ledger entry [2026-04-24] for context."
    )
    if RATE_RECALC_WEEKLY_FALLBACK:
        logging.info(
            "📊 Rate recalc Weekly-Ref-Date fallback ENABLED "
            "(blank Snapshot Date → use Weekly Reference Logged Date for cutoff gate)"
        )
    else:
        logging.info("📊 Rate recalc Weekly-Ref-Date fallback DISABLED (RATE_RECALC_WEEKLY_FALLBACK=false)")
    if RATE_RECALC_SKIP_ORIGINAL_CONTRACT:
        logging.info(
            "📊 Rate recalc ORIGINAL_CONTRACT folder skip ENABLED "
            "(sheets discovered via ORIGINAL_CONTRACT_FOLDER_IDS keep "
            "Smartsheet-native Units Total Price, no CSV-side recalc)"
        )
    else:
        logging.info(
            "📊 Rate recalc ORIGINAL_CONTRACT folder skip DISABLED "
            "(RATE_RECALC_SKIP_ORIGINAL_CONTRACT=false) — recalc will "
            "run on original-contract folder sheets too"
        )
else:
    logging.info("📊 Rate contract versioning DISABLED (RATE_CUTOFF_DATE not set)")

# Subcontractor rate variants startup banner (Phase 1 D-13). The
# fingerprint line is appended later in the rate-loading section once
# ``_SUBCONTRACTOR_RATES_FINGERPRINT`` has been computed by Task 2's
# module-level loader call — see ``load_subcontractor_rates`` below.
# These banner lines embed NO row content (just resolved config
# values), so per D-22 no ``_PII_LOG_MARKERS`` extension is required.
if SUBCONTRACTOR_RATE_VARIANTS_ENABLED:
    logging.info(
        "📊 Subcontractor rate variants ENABLED "
        f"(SUBCONTRACTOR_RATES_CSV='{SUBCONTRACTOR_RATES_CSV}', "
        f"SUBCONTRACTOR_PPP_SHEET_ID={SUBCONTRACTOR_PPP_SHEET_ID})"
    )
else:
    logging.info(
        "📊 Subcontractor rate variants DISABLED "
        "(SUBCONTRACTOR_RATE_VARIANTS_ENABLED=false)"
    )

# Phase 01 gap closure (REVIEW-WR-02): name the PPP-routing
# state explicitly so operators tailing the startup banner see
# the resolved active value (or "DISABLED") without inferring
# from the integer 0. Purely additive — does not replace the
# existing banner block above. Only emitted when the umbrella
# variants kill switch is ON (when off, PPP routing is moot).
if SUBCONTRACTOR_RATE_VARIANTS_ENABLED and SUBCONTRACTOR_PPP_SHEET_ID:
    logging.info(
        f"📊 Subcontractor PPP routing ENABLED "
        f"(target sheet id: {SUBCONTRACTOR_PPP_SHEET_ID})"
    )
elif SUBCONTRACTOR_RATE_VARIANTS_ENABLED:
    logging.info(
        "📊 Subcontractor PPP routing DISABLED "
        "(SUBCONTRACTOR_PPP_SHEET_ID='' or 0)"
    )

# Phase 01 gap closure (REVIEW-IN-01): name the resolved AEP cutoff
# in the startup banner so operators tailing the log see the active
# value at a glance. Only emitted when the umbrella variants kill
# switch is ON (when off, the cutoff is moot — no _AEPBillable
# variant emission occurs regardless of the cutoff value).
if SUBCONTRACTOR_RATE_VARIANTS_ENABLED:
    logging.info(
        f"📊 AEP Billable cutoff: {_AEP_BILLABLE_CUTOFF.isoformat()} "
        f"({'env override' if _aep_billable_cutoff_env else 'default'})"
    )

# Phase 1.1 Bug A: surface the resolved kill-switch state at startup
# so operators grepping the banner can see the active feature state
# at a glance (per [2026-04-23 00:00] ledger rule 3). Banner body
# carries no row PII (just the resolved bool value) — no marker
# required.
logging.info(
    f"📋 SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED="
    f"{SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED}"
)

# Phase 1.1 Bug C: surface resolved kill-switch state at startup
# so operators grepping the banner can see the active feature state
# at a glance.
logging.info(
    f"📋 SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED="
    f"{SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED}"
)

# Phase 1.1 UAT gap closure (SUB-09 helper dimension): surface resolved
# kill-switch state at startup so operators grepping the banner can see
# the active feature state at a glance (per [2026-04-23 00:00] ledger
# rule 3). Banner body carries no row PII (just the resolved bool).
logging.info(
    f"📋 SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED="
    f"{SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED}"
)

# Subproject B: surface resolved kill-switch state at startup so
# operators grepping the banner see the active feature state at a
# glance. Banner body carries no row PII (just the resolved bool).
logging.info(
    f"📋 SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED="
    f"{SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED}"
)

# Subproject C: surface resolved kill-switch state at startup so
# operators grepping the banner see the active feature state at a
# glance. Banner body carries no row PII (just the resolved bools).
logging.info(
    f"📋 VAC Crew claim attribution: "
    f"{'ENABLED' if VAC_CREW_CLAIM_ATTRIBUTION_ENABLED else 'DISABLED'}"
)
logging.info(
    f"📋 VAC Crew legacy cleanup: "
    f"{'ENABLED' if VAC_CREW_LEGACY_CLEANUP_ENABLED else 'DISABLED'}"
)
# Subproject D: surface resolved kill-switch state at startup so
# operators grepping the banner see the active feature state at a
# glance. Banner body carries no row PII (just the resolved bools).
logging.info(
    f"📋 PRIMARY_CLAIM_ATTRIBUTION_ENABLED="
    f"{PRIMARY_CLAIM_ATTRIBUTION_ENABLED}"
)
logging.info(
    f"📋 LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED="
    f"{LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED}"
)
# Sub-project E: surface the durable hash-store kill switches at startup.
logging.info(
    f"📋 SUPABASE_HASH_STORE_WRITE_ENABLED="
    f"{SUPABASE_HASH_STORE_WRITE_ENABLED}"
)
logging.info(
    f"📋 SUPABASE_HASH_STORE_AUTHORITATIVE="
    f"{SUPABASE_HASH_STORE_AUTHORITATIVE}"
)
# Phase 2 Plan 03: remediation kill switches surfaced at startup.
logging.info(
    f"📋 REMEDIATE_CLAIMERS={REMEDIATE_CLAIMERS} "
    f"DRY_RUN={REMEDIATION_DRY_RUN} "
    f"WINDOW_WEEKS={REMEDIATION_WINDOW_WEEKS}"
)
# Phase 2 Plan 05 (CR-01): surface the bulk-prefetch fallback state at startup.
logging.info(
    f"📋 ATTRIBUTION_BULK_PREFETCH_FALLBACK={ATTRIBUTION_BULK_PREFETCH_FALLBACK}"
)

# --- Sentry / observability (relocated to pipeline/observability.py, Wave 1) ---
# config is already imported above. observability DEFINES (does not run)
# init_sentry(); call it here to preserve the EXACT import-time Sentry trigger
# the engine had when the init block lived at module scope (D-04).
from pipeline import observability as _pipeline_observability  # noqa: E402,F401
_pipeline_observability.init_sentry()
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

# --- UTILITY FUNCTIONS ---


if SUBCONTRACTOR_RATE_VARIANTS_ENABLED and _SUBCONTRACTOR_RATES:
    logging.info(
        f"📊 Subcontractor rates loaded: "
        f"{len(_SUBCONTRACTOR_RATES)} CUs, "
        f"fingerprint={_SUBCONTRACTOR_RATES_FINGERPRINT}"
    )
elif SUBCONTRACTOR_RATE_VARIANTS_ENABLED:
    # Kill switch is on but the dict is empty — the loader's own
    # ``logging.error`` already surfaced the failure cause; flag it
    # here too so operators tailing the startup banner notice that
    # the downstream variant pipeline will be a no-op this run.
    logging.warning(
        "⚠️ Subcontractor rates table is empty — _AEPBillable / "
        "_ReducedSub variant generation will be skipped this run "
        f"(SUBCONTRACTOR_RATES_CSV='{SUBCONTRACTOR_RATES_CSV}')"
    )


# Phase 09 Wave 1: the 4 pure utility helpers were relocated to
# pipeline/utils.py. Re-imported here (same binding point) so every
# in-facade caller and ``gwp.NAME`` access keeps resolving unchanged.
from pipeline.utils import (  # noqa: E402
    is_checked,
    excel_serial_to_date,
    _resolve_rate_recalc_cutoff_date,
    _weekly_would_trigger_fallback,
)


# -- Phase 09 W2: change_detection relocated to pipeline/change_detection.py --
# Hashing + group identity now live in pipeline/change_detection.py. Re-imported
# here so the public surface stays byte-identical. The skip-gate helper
# _resolve_unchanged_for_skip now takes the billing_audit writer as an explicit
# kwarg (D-06); main()'s call site below injects _billing_audit_writer.
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

# ── Phase 09 W3: discovery relocated to pipeline/discovery.py (D-02) ──────
# Sheet discovery + the three runtime-rebound set globals now live in
# pipeline/discovery.py. Re-export the public functions only. The three set
# globals (SUBCONTRACTOR_SHEET_IDS / _FOLDER_DISCOVERED_*) are EXCLUDED from
# this static block and served via the __getattr__ live-proxy (D-01).
from pipeline.discovery import (  # noqa: E402
    _normalize_column_title_for_vac_crew,
    discover_folder_sheets,
    discover_source_sheets,
)

# ── Phase 09 W3: fetch relocated to pipeline/fetch.py (D-02) ─────────────
# get_all_source_rows + the runtime-rebound _RATES_FINGERPRINT now live in
# pipeline/fetch.py. Re-export the function only; _RATES_FINGERPRINT is
# EXCLUDED from this static block and served via __getattr__ (D-01).
from pipeline.fetch import get_all_source_rows  # noqa: E402

# Module aliases for the live-proxy delegation + in-root qualified reads (D-01).
# Still-in-root readers of the runtime-rebound globals (e.g. group_source_rows,
# W4-pending) reference _pipeline_discovery.NAME so they always see the current
# submodule binding; the __getattr__ live-proxy (end of file) uses the same
# aliases. When those readers later relocate (W4/W5/W6) the reference becomes
# the destination module's local _discovery.NAME / _fetch.NAME.
from pipeline import discovery as _pipeline_discovery  # noqa: E402,F401
from pipeline import fetch as _pipeline_fetch  # noqa: E402,F401

# -- Phase 09 W4: grouping relocated to pipeline/grouping.py (D-02) -------
# group_source_rows (highest-fan-in transform) + validate_group_totals now
# live in pipeline/grouping.py.  Re-export them; the discovery live-proxy
# globals they read are accessed via pipeline.discovery (_discovery.NAME).
from pipeline.grouping import (  # noqa: E402
    group_source_rows,
    validate_group_totals,
)

# -- Phase 09 W4: excel relocated to pipeline/excel.py (D-02) ------------
# safe_merge_cells (the overlap-detecting merge guard) + the two
# variant-suffix helpers + generate_excel now live in pipeline/excel.py
# (openpyxl-only generation).  Re-export them.
from pipeline.excel import (  # noqa: E402
    _subcontractor_primary_variant_suffix,
    _vac_crew_variant_suffix,
    generate_excel,
    safe_merge_cells,
)

# -- Phase 09 W5: cleanup relocated to pipeline/cleanup.py (D-02) -------
# Stale-Excel pruning + Smartsheet attachment cleanup/replace + purge now
# live in pipeline/cleanup.py.  Re-export them; the (wr, week, variant,
# identifier) identity guard (no primary/helper cross-deletion) and the
# KEEP_HISTORICAL_WEEKS / off-contract / legacy-migration gates are unchanged.
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


# --- DATA DISCOVERY AND PROCESSING ---


# Cell history and Modified By logic removed - using direct column assignment only


# --- TARGET SHEET MANAGEMENT ---


# Modified By cache loading removed - using direct column assignment only


# ── Phase 09 W6: main() + testmode relocated to pipeline/orchestrate.py (D-02) ──
# main() (the 2380-line production entry point) and the two synthetic
# TEST_MODE helpers now live in pipeline/orchestrate.py, relocated
# byte-for-byte (D-05, no internal decomposition). Re-export main so
# ``gwp.main`` resolves for consumers and the facade-completeness gate.
from pipeline.orchestrate import main  # noqa: E402

# ─── PEP-562 live-proxy for the 4 runtime-rebound globals (D-01) ──────────────
# GUARD: SUBCONTRACTOR_SHEET_IDS, _FOLDER_DISCOVERED_SUB_IDS,
# _FOLDER_DISCOVERED_ORIG_IDS (owner: pipeline.discovery) and _RATES_FINGERPRINT
# (owner: pipeline.fetch) are EXCLUDED from this module's static namespace and
# delegated on every read to their owning submodule. DO NOT add any of these
# four names to a `from pipeline.X import ...` block above — a static bind
# captures the pre-run value and shadows __getattr__, silently re-introducing
# the stale-read bug (RESEARCH Pitfall 1: subcontractor vs original-contract
# mis-classification + a weakened change-detection hash).
_LIVE_PROXY: dict[str, tuple[object, str]] = {
    'SUBCONTRACTOR_SHEET_IDS':     (_pipeline_discovery, 'SUBCONTRACTOR_SHEET_IDS'),
    '_FOLDER_DISCOVERED_SUB_IDS':  (_pipeline_discovery, '_FOLDER_DISCOVERED_SUB_IDS'),
    '_FOLDER_DISCOVERED_ORIG_IDS': (_pipeline_discovery, '_FOLDER_DISCOVERED_ORIG_IDS'),
    '_RATES_FINGERPRINT':          (_pipeline_fetch,     '_RATES_FINGERPRINT'),
}


def __getattr__(name: str) -> object:
    """PEP-562 live-proxy for the runtime-rebound globals (D-01).

    Reads of the four live-proxy names delegate to the current binding in their
    owning submodule, so ``gwp.NAME`` never goes stale across the facade
    boundary (reflects rebinds and returns the same object for in-place
    mutations). All other unknown attributes raise ``AttributeError``.
    """
    proxied = _LIVE_PROXY.get(name)
    if proxied is not None:
        mod, attr = proxied
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Include the live-proxy names in dir() / IDE autocomplete (D-01)."""
    return sorted(set(globals().keys()) | set(_LIVE_PROXY.keys()))


if __name__ == "__main__":
    from pipeline.orchestrate import main
    main()
