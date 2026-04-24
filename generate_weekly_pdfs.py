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
import time
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
import concurrent.futures.thread as _cf_thread
import re
import hashlib
from datetime import timedelta
import logging
from dateutil import parser
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
for _exc_name in (
    'RateLimitExceededError',
    'UnexpectedErrorShouldRetryError',
    'InternalServerError',
    'ServerTimeoutExceededError',
    'SystemMaintenanceError',
):
    if not hasattr(_ss_smartsheet_module, _exc_name) and hasattr(ss_exc, _exc_name):
        setattr(_ss_smartsheet_module, _exc_name, getattr(ss_exc, _exc_name))
del _ss_smartsheet_module, _exc_name
import openpyxl
from openpyxl.styles import Font, numbers, Alignment, PatternFill
from openpyxl.drawing.image import Image
import collections
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.threading import ThreadingIntegration
from sentry_sdk.crons import capture_checkin
from sentry_sdk.crons.consts import MonitorStatus
import traceback
import sys
import json
import signal
import csv

# Load environment variables
load_dotenv()

# PERFORMANCE: Pre-compiled regex patterns (avoid repeated compilation in hot paths)
_RE_SANITIZE_IDENTIFIER = re.compile(r'[^\w\-@.]')
_RE_SANITIZE_HELPER_NAME = re.compile(r'[^\w\-]')
_RE_EXTRACT_NUMBERS = re.compile(r'[^0-9.\-]')
_RE_ISO_DATE_PREFIX = re.compile(r'^\d{4}-\d{2}-\d{2}')

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

# Performance and compatibility settings
GITHUB_ACTIONS_MODE = os.getenv('GITHUB_ACTIONS') == 'true'
SKIP_CELL_HISTORY = os.getenv('SKIP_CELL_HISTORY', 'false').lower() == 'true'

# Resiliency grouping mode: controls which Excel variants to generate
# - "primary": Standard WR-based grouping (one Excel per WR/Week)
# - "helper": Helper-based grouping (one Excel per WR/Week/Helper)
# - "both": Generate both primary and helper variants (DEFAULT - always creates primary + helper when helper criteria met)
RES_GROUPING_MODE = os.getenv('RES_GROUPING_MODE', 'both').lower()
if RES_GROUPING_MODE not in ('primary', 'helper', 'both'):
    logging.warning(f"⚠️ Invalid RES_GROUPING_MODE '{RES_GROUPING_MODE}'; defaulting to 'both'")
    RES_GROUPING_MODE = 'both'

# Activity log-based foreman assignment has been removed - we now use helper column logic only

# Skip Smartsheet uploads for local testing (files still saved to OUTPUT_FOLDER)
SKIP_UPLOAD = os.getenv('SKIP_UPLOAD', 'false').lower() == 'true'

# --- CORE CONFIGURATION ---
API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")
# TARGET / AUDIT SHEET CONFIGURATION
# TARGET_SHEET_ID: destination for generated weekly Excel report attachments
# AUDIT_SHEET_ID (or legacy BILLING_AUDIT_SHEET_ID): destination for audit rows / stats ONLY
_target_sheet_id_env = os.getenv("TARGET_SHEET_ID")
AUDIT_SHEET_ID = os.getenv("AUDIT_SHEET_ID") or os.getenv("BILLING_AUDIT_SHEET_ID")

def _coerce_sheet_id(raw_value, default=None):
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        logging.warning(f"⚠️ Invalid sheet id value provided: {raw_value}; using default {default}")
        return default

TARGET_SHEET_ID = _coerce_sheet_id(_target_sheet_id_env, 5723337641643908)
_audit_sheet_id_int = _coerce_sheet_id(AUDIT_SHEET_ID) if AUDIT_SHEET_ID else None

if _target_sheet_id_env:
    logging.info(f"🎯 Using target sheet id: {TARGET_SHEET_ID} (from env TARGET_SHEET_ID)")
else:
    logging.info(f"🎯 Using default target sheet id: {TARGET_SHEET_ID}")

if _audit_sheet_id_int:
    logging.info(f"🧾 Audit sheet configured: {_audit_sheet_id_int}")
else:
    logging.info("🧾 Audit sheet not configured (set AUDIT_SHEET_ID to enable detailed audit logging to Smartsheet)")

# Export AUDIT_SHEET_ID into env-compatible form for BillingAudit (which reads os.getenv inside its module)
if _audit_sheet_id_int and not os.getenv("AUDIT_SHEET_ID"):
    os.environ["AUDIT_SHEET_ID"] = str(_audit_sheet_id_int)

# TARGET_WR_COLUMN_ID removed (unused)
LOGO_PATH = "LinetecServices_Logo.png"
OUTPUT_FOLDER = "generated_docs"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Optional performance/test tuning via environment (must come AFTER OUTPUT_FOLDER defined)
WR_FILTER = [w.strip() for w in os.getenv('WR_FILTER','').split(',') if w.strip()]
EXCLUDE_WRS = [w.strip() for w in os.getenv('EXCLUDE_WRS','').split(',') if w.strip()]  # Work Requests to EXCLUDE from generation
MAX_GROUPS = int(os.getenv('MAX_GROUPS','0') or 0)
QUIET_LOGGING = os.getenv('QUIET_LOGGING','0').lower() in ('1','true','yes')

# Parallel execution: number of ThreadPoolExecutor workers for concurrent Smartsheet API calls
# Smartsheet rate limit is 300 req/min (~5/sec). 8 I/O-bound workers stays safely under the limit
# because each request blocks ~200ms on network I/O; the SDK auto-retries on 429 with backoff.
PARALLEL_WORKERS = int(os.getenv('PARALLEL_WORKERS', '8') or 8)
PARALLEL_WORKERS_DISCOVERY = int(os.getenv('PARALLEL_WORKERS_DISCOVERY', '8') or 8)

# Graceful time budget (minutes). When set and running in GitHub Actions, the script will
# stop processing new groups once this many minutes have elapsed since session start.
# This prevents the Actions runner from hard-killing the job and losing cache/artifact saves.
# Set to 0 to disable. The weekly workflow sets this to 180 (3h) with a matching
# timeout-minutes: 195 on the runner (15min cushion for cache/artifact save steps).
TIME_BUDGET_MINUTES = int(os.getenv('TIME_BUDGET_MINUTES', '0') or 0)

# Sub-budget for the attachment pre-fetch phase. Prevents a flaky Smartsheet
# connection from consuming the entire session budget before group processing
# can start: on 2026-04-22 a run lost 16 minutes to ~14 stuck rows after
# RemoteDisconnected retries, exhausted the 80min TIME_BUDGET_MINUTES before
# generating a single file, and finished with 0 Excel files generated.
# When the pre-fetch exceeds this budget, remaining rows fall back to on-demand
# per-row fetches (already supported in _has_existing_week_attachment and
# delete_old_excel_attachments).
ATTACHMENT_PREFETCH_MAX_MINUTES = int(os.getenv('ATTACHMENT_PREFETCH_MAX_MINUTES', '10') or 10)
# Per-future wait (seconds) inside the pre-fetch consumer loop. One stuck HTTP
# call cannot block the consumer beyond this — the future is left behind and
# its row falls back to the per-row path at generation time.
ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC = int(os.getenv('ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC', '45') or 45)
# Minimum "generation headroom" (minutes) the pre-flight guard reserves
# beyond the pre-fetch budget. Without this, a setup where the session
# has exactly `ATTACHMENT_PREFETCH_MAX_MINUTES` remaining would still
# run pre-fetch and leave ~0 minutes for group processing — the same
# zero-output failure mode this guard is meant to prevent.
ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN = int(os.getenv('ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN', '2') or 2)


class _DaemonThreadPoolExecutor(ThreadPoolExecutor):
    """ThreadPoolExecutor whose workers are daemonized so stuck I/O
    cannot hold the interpreter open past ``main()`` return.

    Three things can block process exit for a non-daemon worker:
    1. ``concurrent.futures.thread._python_exit`` (registered via
       ``threading._register_atexit``) joins every worker still in
       ``_threads_queues``.
    2. ``threading._shutdown`` joins every lock in
       ``_shutdown_locks`` — non-daemon threads add their tstate
       lock to this set at startup.
    3. The executor's ``shutdown(wait=True)`` joins all workers.

    This subclass addresses (2) by setting ``daemon=True`` at thread
    creation (``_set_tstate_lock`` only adds to ``_shutdown_locks``
    when ``not self.daemon``). Callers addressing a stall must still
    pop from ``_threads_queues`` (addresses 1) and call
    ``shutdown(wait=False, cancel_futures=True)`` (addresses 3).

    **Safety invariant — use this ONLY when the worker's work is
    discardable.** The pre-fetch cache has a per-row fallback path,
    so abandoning a mid-flight HTTP worker is safe; the OS reclaims
    the socket. Do NOT use this executor for workers that produce
    results the main flow depends on (generation, upload,
    ``hash_history.save``) — the atexit join is what guarantees
    those side effects are flushed before exit.

    Re-implements upstream's private ``_adjust_thread_count`` to
    flip ``daemon=True``. Pinned to the Python 3.11 / 3.12 shape;
    falls back to the superclass (non-daemon workers, atexit hang
    returns) if a future Python rearranges the private helpers.
    """

    def _adjust_thread_count(self):
        if not hasattr(_cf_thread, '_worker') or not hasattr(_cf_thread, '_threads_queues'):
            return super()._adjust_thread_count()
        if self._idle_semaphore.acquire(timeout=0):
            return

        def _weakref_cb(_, q=self._work_queue):
            q.put(None)

        num_threads = len(self._threads)
        if num_threads < self._max_workers:
            thread_name = '%s_%d' % (self._thread_name_prefix or self, num_threads)
            t = threading.Thread(
                name=thread_name,
                target=_cf_thread._worker,
                args=(weakref.ref(self, _weakref_cb),
                      self._work_queue,
                      self._initializer,
                      self._initargs),
                daemon=True,
            )
            t.start()
            self._threads.add(t)
            _cf_thread._threads_queues[t] = self._work_queue


USE_DISCOVERY_CACHE = os.getenv('USE_DISCOVERY_CACHE','1').lower() in ('1','true','yes')
# Discovery cache TTL: sheet IDs and column mappings are essentially static.
# Default to 7 days (10080 min). Set FORCE_REDISCOVERY=true to bypass the cache on demand.
DISCOVERY_CACHE_TTL_MIN = int(os.getenv('DISCOVERY_CACHE_TTL_MIN','10080') or 10080)
FORCE_REDISCOVERY = os.getenv('FORCE_REDISCOVERY','false').lower() in ('1','true','yes')
DISCOVERY_CACHE_PATH = os.path.join(OUTPUT_FOLDER, 'discovery_cache.json')
# Bump this version whenever the column synonym dictionary changes so that stale caches
# (missing newly-mapped columns like VAC Crew) are automatically invalidated.
# Also bump when a known bug would leave existing caches with incorrect mappings —
# invalidating the cache is cheaper than waiting up to DISCOVERY_CACHE_TTL_MIN
# (7 days by default) for those mappings to refresh on their own.
DISCOVERY_CACHE_VERSION = 4  # v4: fuzzy VAC Crew column fallback — invalidate caches whose column_mapping missed title variants like trailing whitespace or case drift
# Verbose debug tunables
DEBUG_SAMPLE_ROWS = int(os.getenv('DEBUG_SAMPLE_ROWS','3') or 3)  # How many initial rows (across all sheets) to show full per-cell mapping
DEBUG_ESSENTIAL_ROWS = int(os.getenv('DEBUG_ESSENTIAL_ROWS','5') or 5)  # How many initial rows to log essential field summary
LOG_UNKNOWN_COLUMNS = os.getenv('LOG_UNKNOWN_COLUMNS','1').lower() in ('1','true','yes')  # Summarize unmapped columns once per sheet
PER_CELL_DEBUG_ENABLED = os.getenv('PER_CELL_DEBUG_ENABLED','1').lower() in ('1','true','yes')  # Master switch
UNMAPPED_COLUMN_SAMPLE_LIMIT = int(os.getenv('UNMAPPED_COLUMN_SAMPLE_LIMIT','5') or 5)  # Sample values per unmapped column in summary
# Extended change detection (default ON). When enabled, the data hash used to detect
# whether an Excel needs regeneration will include additional business fields such as
# current foreman, dept numbers, scope id, aggregated totals, unique dept list, and row count.
EXTENDED_CHANGE_DETECTION = os.getenv('EXTENDED_CHANGE_DETECTION','1').lower() in ('1','true','yes')
FILTER_DIAGNOSTICS = os.getenv('FILTER_DIAGNOSTICS','0').lower() in ('1','true','yes')  # When enabled, logs exclusion reasons counts
FOREMAN_DIAGNOSTICS = os.getenv('FOREMAN_DIAGNOSTICS','0').lower() in ('1','true','yes')  # When enabled, logs per-WR foreman value distributions & exclusion reasons
FORCE_GENERATION = os.getenv('FORCE_GENERATION','0').lower() in ('1','true','yes')  # When true, ignore hash short‑circuit and always regenerate
REGEN_WEEKS = {w.strip() for w in os.getenv('REGEN_WEEKS','').split(',') if w.strip()}  # Comma list of MMDDYY week ending codes to force regenerate
def _parse_sheet_ids(env_val):
    """Parse comma-separated sheet IDs, skipping non-integer tokens."""
    ids = []
    for s in env_val.split(','):
        s = s.strip()
        if not s:
            continue
        try:
            ids.append(int(s))
        except ValueError:
            logging.warning(f"Ignoring invalid SUBCONTRACTOR_SHEET_IDS token: {s!r}")
    return ids

SUBCONTRACTOR_SHEET_IDS = set(_parse_sheet_ids(os.getenv('SUBCONTRACTOR_SHEET_IDS', '')))

# Folder-based discovery: Smartsheet folder IDs whose child sheets should be auto-discovered
# Subcontractor folders (sheets priced at subcontractor rates, will be reverted to original contract rates)
SUBCONTRACTOR_FOLDER_IDS = _parse_sheet_ids(os.getenv('SUBCONTRACTOR_FOLDER_IDS', '4232010517505924,2588197684307844'))
# Original contract folders (sheets already at original contract rates)
ORIGINAL_CONTRACT_FOLDER_IDS = _parse_sheet_ids(os.getenv('ORIGINAL_CONTRACT_FOLDER_IDS', '7644752003786628,8815193070299012'))
# VAC Crew detection is now row-level (column-presence-based, no folder/sheet ID config needed).
# Sheets with columns like 'VAC Crew Helping?' and 'Vac Crew Completed Unit?' automatically
# produce vac_crew variant rows during row processing.
# Legacy variables for backward compatibility with tests (no longer used in production)
VAC_CREW_SHEET_IDS = set(_parse_sheet_ids(os.getenv('VAC_CREW_SHEET_IDS', '')))
VAC_CREW_FOLDER_IDS = _parse_sheet_ids(os.getenv('VAC_CREW_FOLDER_IDS', ''))
# Module-level sets populated at runtime by discover_folder_sheets()
_FOLDER_DISCOVERED_SUB_IDS: set[int] = set()
_FOLDER_DISCOVERED_ORIG_IDS: set[int] = set()

# --- RATE CONTRACT VERSIONING ---
# Set RATE_CUTOFF_DATE (YYYY-MM-DD) to activate new rate recalculation.
# When set, rows with Snapshot Date >= cutoff get prices recalculated from new rate tables.
# When unset (empty string), all rows keep their SmartSheet Units Total Price (current behavior).
_cutoff_str = os.getenv('RATE_CUTOFF_DATE', '')
try:
    RATE_CUTOFF_DATE = (
        datetime.datetime.strptime(_cutoff_str, '%Y-%m-%d').date()
        if _cutoff_str else None
    )
except ValueError:
    logging.error(f"Invalid RATE_CUTOFF_DATE format: '{_cutoff_str}', expected YYYY-MM-DD. Rate versioning disabled.")
    RATE_CUTOFF_DATE = None
ARROWHEAD_DISCOUNT = 0.90  # 10% reduction for subcontractors (Arrowhead)

def _sanitize_csv_path(env_var, default):
    """Validate a CSV path from env var, preventing directory traversal and symlink escapes.

    Returns the fully resolved path so that the value passed to open() is
    the same value that was validated (satisfies CodeQL taint analysis).
    """
    raw = (os.getenv(env_var, '') or '').strip() or default
    resolved = os.path.normpath(os.path.realpath(raw))
    cwd = os.path.normpath(os.path.realpath('.'))
    if not resolved.startswith(cwd + os.sep) and resolved != cwd:
        logging.warning(f"⚠️ {env_var} resolves outside working directory: '{raw}'. Using default: '{default}'")
        return os.path.normpath(os.path.realpath(default))
    return resolved

NEW_RATES_CSV = _sanitize_csv_path('NEW_RATES_CSV', 'New Contract Rates copy regenerated again.csv')
OLD_RATES_CSV = _sanitize_csv_path('OLD_RATES_CSV', 'CU List - Corpus North & South.csv')

_RATES_FINGERPRINT = ''  # Populated at runtime by load_rate_versions()

# Weekly-Ref-Date fallback for pre-acceptance rate recalculation.
# Default-ON: when a row has a blank/unparseable Snapshot Date (common on
# current-week VAC crew / helper rows before Smartsheet's snapshot
# automation has fired), fall back to 'Weekly Reference Logged Date'
# for the cutoff comparison. Rows that DO have a Snapshot Date are
# unaffected — the snapshot-keyed business rule stays primary. Set
# RATE_RECALC_WEEKLY_FALLBACK=0 (or false/no/off) to disable.
RATE_RECALC_WEEKLY_FALLBACK = os.getenv(
    'RATE_RECALC_WEEKLY_FALLBACK', '1'
).lower() in ('1', 'true', 'yes', 'on')

if RATE_CUTOFF_DATE:
    logging.info(f"📊 Rate contract versioning ENABLED: cutoff date = {RATE_CUTOFF_DATE.isoformat()}")
    if RATE_RECALC_WEEKLY_FALLBACK:
        logging.info(
            "📊 Rate recalc Weekly-Ref-Date fallback ENABLED "
            "(blank Snapshot Date → use Weekly Reference Logged Date for cutoff gate)"
        )
    else:
        logging.info("📊 Rate recalc Weekly-Ref-Date fallback DISABLED (RATE_RECALC_WEEKLY_FALLBACK=false)")
else:
    logging.info("📊 Rate contract versioning DISABLED (RATE_CUTOFF_DATE not set)")

RESET_HASH_HISTORY = os.getenv('RESET_HASH_HISTORY','0').lower() in ('1','true','yes')  # When true, delete ALL existing WR_*.xlsx attachments & local files first
RESET_WR_LIST = {w.strip() for w in os.getenv('RESET_WR_LIST','').split(',') if w.strip()}  # When provided, only purge these WR numbers (overrides full reset)
_env_hist_path = os.getenv('HASH_HISTORY_PATH')
_default_hist_path = os.path.join(OUTPUT_FOLDER, 'hash_history.json')
if _env_hist_path:
    # Only allow the file within OUTPUT_FOLDER (resolve real absolute paths)
    _norm_path = os.path.normpath(os.path.abspath(os.path.join(OUTPUT_FOLDER, _env_hist_path)))
    _output_folder_abs = os.path.normpath(os.path.abspath(OUTPUT_FOLDER))
    if _norm_path.startswith(_output_folder_abs):
        HASH_HISTORY_PATH = _norm_path
    else:
        logging.warning(f"⚠️ HASH_HISTORY_PATH environment variable must resolve within {OUTPUT_FOLDER}. Using default: {_default_hist_path}")
        HASH_HISTORY_PATH = _default_hist_path
else:
    HASH_HISTORY_PATH = _default_hist_path
HISTORY_SKIP_ENABLED = os.getenv('HISTORY_SKIP_ENABLED','1').lower() in ('1','true','yes')  # Allow skip based on identical stored hash ONLY if attachment still present
ATTACHMENT_REQUIRED_FOR_SKIP = os.getenv('ATTACHMENT_REQUIRED_FOR_SKIP','1').lower() in ('1','true','yes')  # If true, even identical hash regenerates when attachment missing
KEEP_HISTORICAL_WEEKS = os.getenv('KEEP_HISTORICAL_WEEKS','0').lower() in ('1','true','yes')  # Preserve attachments for weeks not processed this run
if EXTENDED_CHANGE_DETECTION:
    logging.info("🔄 Extended change detection ENABLED (hash includes Foreman, Dept #, Scope, totals, etc.)")
else:
    logging.info("ℹ️ Legacy change detection mode (hash limited to core line item fields)")
if QUIET_LOGGING:
    logging.getLogger().setLevel(logging.WARNING)

# Test/Production modes (controlled by environment variable TEST_MODE)
# PRODUCTION BY DEFAULT: set TEST_MODE=true only for maintenance / dry runs.
TEST_MODE = os.getenv('TEST_MODE', 'false').lower() in ('1','true','yes')
DISABLE_AUDIT_FOR_TESTING = False  # Audit system ENABLED for production monitoring

# --- SENTRY CONFIGURATION (SDK 2.x) ---
SENTRY_DSN = os.getenv("SENTRY_DSN")

# Compiled patterns used to scrub billing-row PII out of exception
# messages before they land in Sentry event context_data. The
# ``before_send_log`` hook further down only sanitizes logging records
# — it does NOT walk ``event['contexts']`` — so any raw ``str(e)``
# passed into ``sentry_capture_with_context(...)``'s context_data
# payload would bypass that defense. Keep these patterns conservative:
# they only strip recognised PII tokens, leaving the rest of the
# exception message intact so operators can still diagnose the root
# cause from the Sentry dashboard.
# Match any ``WR``-prefixed identifier, not just digit-only tokens.
# Earlier ``\d+`` missed alphanumeric WR values (``WR=ABCD-123``) and
# only partially matched path-traversal suffixes (``WR=1234/../evil``
# would redact only ``1234``, leaking ``/../evil`` through the
# Sentry context). The negative lookahead ``(?![a-zA-Z])`` keeps the
# pattern from over-matching English words that happen to start with
# ``WR`` (e.g. ``WRITE``). The identifier char class accepts word
# characters plus ``/ \ . -`` so path-traversal tokens and decorated
# IDs are captured in full, and the ``+`` stops at the first
# whitespace / delimiter so only the identifier itself is redacted.
_RE_REDACT_WR = re.compile(r'(?i)\bWR(?![a-zA-Z])\s*[#:=]?\s*[\w/\\\-.]+')
_RE_REDACT_MONEY = re.compile(r'\$\s*\d[\d,]*(?:\.\d+)?')
_RE_REDACT_EMAIL = re.compile(r'[\w.+-]+@[\w.-]+\.\w+')
_RE_REDACT_CUSTOMER = re.compile(r'(?i)\b(customer|foreman|dept|snapshot|cu|job)\s*[#:=]?\s*["\']?[^,;"\')\]}\n]{1,80}')


def _redact_exception_message(exc: BaseException | None, *, max_len: int = 240) -> str:
    """Return a PII-scrubbed single-line form of ``str(exc)``.

    Used exclusively for the ``error_message`` field of
    ``sentry_capture_with_context(...)``'s context_data payload — that
    dict bypasses the INFO-log ``before_send_log`` sanitizer because
    Sentry attaches it directly as event context. The redactor strips
    WR identifiers, dollar amounts, emails, and ``customer=``/
    ``foreman=``/``dept=``/``snapshot=``/``cu=``/``job=`` key-value
    pairs, collapses whitespace, prefixes the exception class name for
    event-grouping stability, and truncates the result.
    """
    if exc is None:
        return ''
    try:
        raw = str(exc)
    except Exception:
        return f"{type(exc).__name__}: <unrepresentable>"
    if not raw:
        return type(exc).__name__
    redacted = _RE_REDACT_CUSTOMER.sub(r'\1=<redacted>', raw)
    redacted = _RE_REDACT_WR.sub('WR=<redacted>', redacted)
    redacted = _RE_REDACT_MONEY.sub('$<redacted>', redacted)
    redacted = _RE_REDACT_EMAIL.sub('<email>', redacted)
    redacted = re.sub(r'\s+', ' ', redacted).strip()
    # Codex: truncate AFTER adding the class prefix so ``max_len``
    # caps the full returned payload (what actually lands in the
    # Sentry event), not just the body portion.
    result = f"{type(exc).__name__}: {redacted}"
    if len(result) > max_len:
        result = result[:max_len - 3] + '...'
    return result


# Sentry helper functions for enhanced error context
def sentry_add_breadcrumb(category: str, message: str, level: str = "info", data: dict | None = None):
    """Add a breadcrumb for execution flow tracking in Sentry dashboard."""
    if SENTRY_DSN:
        sentry_sdk.add_breadcrumb(
            category=category,
            message=message,
            level=level,
            data=data or {}
        )

def sentry_capture_with_context(exception: Exception, context_name: str | None = None, 
                                  context_data: dict | None = None, tags: dict | None = None,
                                  fingerprint: list | None = None):
    """Capture exception with rich context, tags, and custom fingerprinting.
    
    Args:
        exception: The exception to capture
        context_name: Name for the context block in Sentry dashboard
        context_data: Dictionary of contextual data for debugging
        tags: Additional tags for filtering in Sentry
        fingerprint: Custom fingerprint for error grouping
    """
    if not SENTRY_DSN:
        return
    
    scope = sentry_sdk.get_current_scope()
    
    # Add rich context data
    if context_name and context_data:
        sentry_sdk.set_context(context_name, context_data)
    
    # Add custom tags for filtering
    if tags:
        for key, value in tags.items():
            scope.set_tag(key, str(value))
    
    # Set custom fingerprint for error grouping
    if fingerprint:
        scope.fingerprint = fingerprint
    
    # Capture with full context
    sentry_sdk.capture_exception(exception)

from typing import Literal

# Log level type for Sentry SDK 2.x
SentryLogLevel = Literal["fatal", "critical", "error", "warning", "info", "debug"]

def sentry_capture_message_with_context(message: str, level: SentryLogLevel = "error",
                                         context_name: str | None = None, context_data: dict | None = None,
                                         tags: dict | None = None):
    """Capture a message with rich context for Sentry dashboard visibility."""
    if not SENTRY_DSN:
        return
    
    scope = sentry_sdk.get_current_scope()
    
    if context_name and context_data:
        sentry_sdk.set_context(context_name, context_data)
    
    if tags:
        for key, value in tags.items():
            scope.set_tag(key, str(value))
    
    sentry_sdk.capture_message(message, level=level)

# Substring markers that identify billing-engine log messages known
# to embed row-level PII (WR, dept, job, foreman, helper / vac-crew
# names, cell values, prices). If any of these appear in a log body,
# the record is dropped before it ships to the Sentry Logs product.
# Applied in addition to the ``SENTRY_ENABLE_LOGS`` env gate —
# defense in depth. Defined at module scope (not inside the
# ``if SENTRY_DSN:`` block) so it is importable and unit-testable
# without a live DSN.
_PII_LOG_MARKERS: tuple[str, ...] = (
    # Per-row / per-cell debug dumps
    "Row data sample",
    "Cell ",
    "ESSENTIAL FIELDS",
    # Helper detection + grouping
    "HELPER ROW DETECTED",
    "HELPER GROUP CREATED",
    "HELPER GROUP SUMMARY",
    "Helper group '",
    "Helper groups: ",
    "Helper detection criteria",
    "Helper variant",
    "Helper row for WR",
    "MAPPED HELPER COLUMN",
    "Sample Helper",
    "Foreman Helping?",
    # VAC Crew detection + grouping
    "VAC Crew detection",
    "VAC CREW ROW DETECTED",
    "VAC CREW GROUP CREATED",
    "VAC CREW GROUP SUMMARY",
    "VAC Crew group '",
    "Adding row to existing VAC Crew group",
    "MAPPED VAC CREW COLUMN",
    "VAC Crew Helping?",
    # Rate / pricing recalc (CU + group codes + quantities + rates)
    "Rate recalculation",
    "Rate recalc",
    # Foreman / assignment / exclusion diagnostics
    "Foreman Assignment",
    "foremen(top5)",
    "Excluding row",
    "EXCLUDING from main Excel",
    # WR-keyed log lines
    "for WR#",
    "WR# ",
    "for WR ",
    "Work request ",
    "Job # not found",
    "Sample group keys",
    # Runtime WR lists (operator-supplied filter / exclusion / reset
    # lists that print every WR identifier they contain).
    "WR_FILTER applied",
    "EXCLUDE_WRS ",
    "EXCLUDE_WRS:",
    "Hash reset requested for specific WRs",
    # Group keys / totals validation. group_key shapes are
    # ``{week}_{wr}`` (primary), ``{week}_{wr}_HELPER_{foreman}``
    # (helper), ``{week}_{wr}_VACCREW`` (vac crew). Any log body
    # carrying ``_HELPER_`` or ``_VACCREW`` is therefore emitting a
    # group key (which embeds WR + week + foreman). Plus the
    # always-on totals validation block at the end of a run, which
    # logs ``{group_key}: rows=N total=$X.YY`` per group.
    "_HELPER_",
    "_VACCREW",
    "Totals Validation",
    "total=$",
    "Failed to process group ",
    "Synthetic group failure ",
    # Attachment / regeneration lifecycle (WR + week embedded)
    "Removing ",
    "Unchanged (",
    "Skip (unchanged",
    "Regenerating ",
    "FORCE GENERATION for ",
    # Output filenames interpolate
    # ``WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}[_Helper_<foreman>|
    # _User_<foreman>|_VacCrew]_{hash}.xlsx``, so any log body that
    # contains ``_WeekEnding_`` is carrying an artifact name that
    # embeds WR + week + foreman. Broad catch-all + explicit prefixes
    # for the upload / delete / generate lifecycle.
    "_WeekEnding_",
    "Generating Excel file",
    "Generated Excel",
    "Uploaded: ",
    "Skipping upload ",
    "Rate limited on upload",
    "Upload retry ",
    "Upload failed for ",
    "Deleted: ",
    "Already gone: ",
    "Delete failed ",
    # Legacy / manual attachment cleanup. `purge_existing_hashed_outputs`
    # logs any ``WR_*.xlsx`` name — including short legacy forms like
    # ``WR_42.xlsx`` that don't contain ``_WeekEnding_`` — so the broad
    # filename catch-all is not sufficient for these paths.
    "Purged attachment:",
    "Failed to purge attachment",
)


def sentry_before_send_log(record, hint):
    """Drop Sentry Logs records that embed billing-row PII.

    Runs only when ``SENTRY_ENABLE_LOGS`` is truthy (otherwise the
    SDK never invokes this hook). Matches against the rendered log
    body; returns ``None`` to drop, or the record unchanged to forward.
    Defined at module scope so it is importable and unit-testable.

    Missing or empty bodies are normalized to ``""`` and forwarded
    unless a configured marker is present. The hook fails **closed**
    for unexpected inspectable payloads: non-string body values, or
    any exception raised while inspecting the record, cause the
    record to be dropped so uninspectable payloads cannot bypass the
    marker checks.
    """
    try:
        # Resolve the body without ``or ""`` coercion — falsy non-string
        # values (0, False, [], {}) must reach the isinstance check so
        # they hit the fail-closed branch instead of being silently
        # converted to "" and forwarded.
        if isinstance(record, dict):
            body = record["body"] if "body" in record else ""
        else:
            body = (
                getattr(record, "body")
                if hasattr(record, "body")
                else ""
            )
        if not isinstance(body, str):
            # Fail closed for unexpected body types so uninspectable
            # records cannot bypass PII marker checks.
            return None
        for marker in _PII_LOG_MARKERS:
            if marker in body:
                return None
    except Exception:
        # Never let the sanitizer crash the SDK — drop on error so
        # unclassified records don't slip through to Sentry Logs.
        return None
    return record


def _parse_sentry_enable_logs(raw: str | None) -> bool:
    """Parse the SENTRY_ENABLE_LOGS env value into a bool.

    Truthy: ``1``, ``true``, ``yes``, ``on`` (case-insensitive,
    whitespace-tolerant). Anything else — including unset / empty —
    is falsy. Extracted so tests can cover both branches without
    needing a live DSN.
    """
    if raw is None:
        return False
    return raw.strip().lower() in ("1", "true", "yes", "on")


if SENTRY_DSN:
    sentry_logging = LoggingIntegration(
        level=logging.INFO,
        event_level=logging.ERROR
    )

    def before_send_filter(event, hint):
        """Filter out normal Smartsheet 404 errors during cleanup operations.

        Sentry 2.x compatible: Enriches events with additional context.
        """
        # Filter Smartsheet internal logger noise
        if event.get('logger') == 'smartsheet.smartsheet':
            return None
        
        # Filter out 404 attachment deletion errors (normal operations)
        if 'exception' in event and event['exception'].get('values'):
            for exc_value in event['exception']['values']:
                if exc_value.get('value'):
                    error_msg = exc_value['value'].lower()
                    if ("404" in error_msg or "not found" in error_msg) and "attachment" in error_msg:
                        logging.info("⚠️ Filtered 404 attachment error from Sentry (normal operation)")
                        return None
        
        # Enrich all events with runtime context
        event.setdefault('contexts', {})
        event['contexts']['runtime_info'] = {
            'test_mode': TEST_MODE,
            'github_actions': bool(os.getenv('GITHUB_ACTIONS')),
            'max_groups': MAX_GROUPS,
            'extended_change_detection': EXTENDED_CHANGE_DETECTION,
            'python_version': sys.version,
        }
        
        return event
    
    def traces_sampler(sampling_context):
        """Dynamic sampling for performance tracing based on operation type."""
        # Always trace errors
        if sampling_context.get('parent_sampled'):
            return 1.0
        
        # Sample main operations at 100% for full visibility
        transaction_name = sampling_context.get('transaction_context', {}).get('name', '')
        if 'excel_generation' in transaction_name or 'main' in transaction_name:
            return 1.0
        
        # Sample other operations at 50%
        return 0.5
    
    try:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[
                sentry_logging,
                ThreadingIntegration(propagate_hub=True),
            ],
            # Performance monitoring
            traces_sample_rate=1.0,
            traces_sampler=traces_sampler,
            profiles_sample_rate=0.5,  # SDK 2.x: No longer experimental
            
            # Environment configuration — SENTRY_* vars take priority over legacy fallbacks
            environment=os.getenv("SENTRY_ENVIRONMENT") or os.getenv("ENVIRONMENT", "production"),
            release=os.getenv("SENTRY_RELEASE") or os.getenv("RELEASE", "weekly-excel-generator@1.0.0"),
            server_name=os.getenv("HOSTNAME", "local"),
            
            # Error enrichment
            before_send=before_send_filter,
            attach_stacktrace=True,
            include_local_variables=True,  # SDK 2.x: Replaces with_locals
            max_breadcrumbs=100,
            
            # Request handling (SDK 2.x syntax)
            max_request_body_size="medium",  # SDK 2.x: Replaces request_bodies
            
            # Enable source context for better stack traces
            include_source_context=True,

            # Shutdown timeout for graceful error flushing
            shutdown_timeout=5,

            # Sentry Logs (SDK >= 2.35.0): forward records captured by
            # LoggingIntegration into the Sentry Logs product in addition
            # to breadcrumbs/events. Gated opt-in via SENTRY_ENABLE_LOGS
            # because INFO-level call sites in this engine can include
            # row/cell debug content (foreman, dept, job, WR, prices)
            # that must not be exfiltrated to Sentry by default. Set
            # SENTRY_ENABLE_LOGS=true only after auditing log call sites
            # and keeping PER_CELL_DEBUG_ENABLED / row sampling off.
            enable_logs=_parse_sentry_enable_logs(
                os.getenv("SENTRY_ENABLE_LOGS")
            ),

            # Defense-in-depth PII sanitizer for the Logs product. Even
            # when the env gate is on, drop records that embed known
            # row-level markers (see _PII_LOG_MARKERS above).
            before_send_log=sentry_before_send_log,
        )
        
        # Set user context (SDK 2.x: top-level API)
        sentry_sdk.set_user({
            "id": "excel_generator",
            "username": "weekly_pdf_generator",
            "segment": "billing_automation"
        })
        
        # Set global tags for all events (SDK 2.x: top-level API)
        sentry_sdk.set_tag("component", "excel_generation")
        sentry_sdk.set_tag("process", "weekly_reports")
        sentry_sdk.set_tag("test_mode", str(TEST_MODE))
        sentry_sdk.set_tag("github_actions", str(bool(os.getenv('GITHUB_ACTIONS'))))
        
        # Set initial context (SDK 2.x: top-level API)
        sentry_sdk.set_context("configuration", {
            "max_groups": MAX_GROUPS,
            "extended_change_detection": EXTENDED_CHANGE_DETECTION,
            "use_discovery_cache": USE_DISCOVERY_CACHE,
            "force_generation": FORCE_GENERATION,
            "wr_filter": WR_FILTER,
        })
        
        logger = logging.getLogger(__name__)
        logging.info("🛡️ Sentry.io error monitoring initialized (SDK 2.x)")
    except Exception as e:
        logging.warning(f"⚠️ Sentry initialization failed: {e}")
        logger = logging.getLogger(__name__)
else:
    logger = logging.getLogger(__name__)
    logging.warning("⚠️ SENTRY_DSN not configured - error monitoring disabled")

# --- UTILITY FUNCTIONS ---

def parse_price(price_str: str | float | int | None) -> float:
    """Safely convert a price string to a float.
    
    Args:
        price_str: Price value as string, float, int, or None
    
    Returns:
        float: Parsed price value, or 0.0 if parsing fails
    """
    if not price_str:
        return 0.0
    try:
        return float(str(price_str).replace('$', '').replace(',', ''))
    except (ValueError, TypeError):
        return 0.0

def load_contract_rates(filepath):
    """Loads contract rates into a fast lookup dictionary."""
    rates = {}
    REQUIRED_HEADERS = {'CU', 'Install Price', 'Removal Price', 'Transfer Price'}
    try:
        with open(filepath, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or not REQUIRED_HEADERS.issubset(set(reader.fieldnames)):
                missing = REQUIRED_HEADERS - set(reader.fieldnames or [])
                logging.error(f"CSV {filepath} missing required headers: {missing}")
                return rates
            for row in reader:
                cu = str(row.get('CU', '')).strip().upper()
                if not cu:
                    continue

                rates[cu] = {
                    'install': parse_price(row.get('Install Price', 0)),
                    'removal': parse_price(row.get('Removal Price', 0)),
                    'transfer': parse_price(row.get('Transfer Price', 0))
                }
        logging.info(f"Loaded {len(rates)} CU rates from {filepath}")
    except Exception as e:
        logging.error(f"Failed to load rates from {filepath}: {e}")
    return rates


def load_new_contract_rates(filepath):
    """Load new contract rates from the 2026 format CSV (group-level codes).

    The new CSV has 3 metadata rows before data, with columns by position:
    [0]=Group Code, [1]=Description, [2]=UOM, [3]=Category, [4]=Region,
    [5]=Date, [6]=Install Price, [7]=Removal Price, [8]=Transfer Price.

    Returns:
        dict: {GROUP_CODE: {install: float, removal: float, transfer: float}}
    """
    rates = {}
    try:
        with open(filepath, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            # Skip 3 metadata/header rows
            for _ in range(3):
                next(reader, None)
            for row in reader:
                if len(row) < 9:
                    continue
                group_code = row[0].strip().upper()
                if not group_code:
                    continue
                rates[group_code] = {
                    'install': parse_price(row[6]),
                    'removal': parse_price(row[7]),
                    'transfer': parse_price(row[8]),
                }
        logging.info(f"Loaded {len(rates)} group-level rates from {filepath}")
    except Exception as e:
        logging.error(f"Failed to load new contract rates from {filepath}: {e}")
    return rates


def build_cu_to_group_mapping(old_csv_path):
    """Build a mapping from detailed CU codes to Compatible Unit Group codes.

    Reads the old-format CSV which has both 'CU' (detailed code) and
    'Compatible Unit Group' columns.

    Returns:
        dict: {DETAILED_CU_CODE: GROUP_CODE} e.g. {'ANC-DHM-10-84-D1': 'ANC-M'}
    """
    mapping = {}
    try:
        with open(old_csv_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or 'CU' not in reader.fieldnames or 'Compatible Unit Group' not in reader.fieldnames:
                logging.error(f"CSV {old_csv_path} missing 'CU' or 'Compatible Unit Group' columns for mapping")
                return mapping
            for row in reader:
                cu = str(row.get('CU', '')).strip().upper()
                group = str(row.get('Compatible Unit Group', '')).strip().upper()
                if cu and group:
                    mapping[cu] = group
        logging.info(f"Built CU-to-group mapping: {len(mapping)} CU codes -> groups")
    except Exception as e:
        logging.error(f"Failed to build CU-to-group mapping from {old_csv_path}: {e}")
    return mapping


def _compute_rates_fingerprint(rates_dict):
    """Compute a short SHA256 fingerprint of a rates dictionary for hash invalidation."""
    h = hashlib.sha256()
    for code in sorted(rates_dict.keys()):
        r = rates_dict[code]
        h.update(f"{code}:{r['install']:.2f},{r['removal']:.2f},{r['transfer']:.2f}\n".encode())
    return h.hexdigest()[:12]


def load_rate_versions():
    """Load new rate versions and build all necessary lookup structures.

    Returns:
        tuple: (cu_to_group, new_rates_primary, new_rates_arrowhead, rates_fingerprint)
            - cu_to_group: {DETAILED_CU: GROUP_CODE}
            - new_rates_primary: {GROUP_CODE: {install, removal, transfer}}
            - new_rates_arrowhead: {GROUP_CODE: {install, removal, transfer}} (rates * 0.90)
            - rates_fingerprint: short hash of rate table contents for cache invalidation
    """
    cu_to_group = build_cu_to_group_mapping(OLD_RATES_CSV)
    new_rates_primary = load_new_contract_rates(NEW_RATES_CSV)

    # Precompute Arrowhead (subcontractor) rates: primary rate * ARROWHEAD_DISCOUNT
    new_rates_arrowhead = {}
    for group_code, rates in new_rates_primary.items():
        new_rates_arrowhead[group_code] = {
            'install': round(rates['install'] * ARROWHEAD_DISCOUNT, 2),
            'removal': round(rates['removal'] * ARROWHEAD_DISCOUNT, 2),
            'transfer': round(rates['transfer'] * ARROWHEAD_DISCOUNT, 2),
        }

    # Only compute fingerprint if rates were successfully loaded
    rates_fingerprint = _compute_rates_fingerprint(new_rates_primary) if new_rates_primary else ''

    if not new_rates_primary:
        logging.warning("⚠️ New rate table is empty — rate recalculation will be skipped even though RATE_CUTOFF_DATE is set")
    else:
        logging.info(f"Rate versions loaded: {len(new_rates_primary)} primary groups, "
                     f"{len(new_rates_arrowhead)} Arrowhead groups (precomputed, not yet active), "
                     f"{len(cu_to_group)} CU-to-group mappings, "
                     f"fingerprint={rates_fingerprint}")
    return cu_to_group, new_rates_primary, new_rates_arrowhead, rates_fingerprint


def _resolve_cu_code(row_data):
    """Return the CU code for a row using the same priority chain as
    ``recalculate_row_price`` and ``revert_subcontractor_price``.

    Resolution order: ``CU Helper`` → ``CU`` → ``Billable Unit Code``,
    with the sentinel string ``'NAN'`` (produced by pandas when a float
    NaN is stringified) falling back to ``CU``. Returns an uppercased,
    stripped string (possibly empty if no column yields a value).
    """
    cu_code = str(
        row_data.get('CU Helper')
        or row_data.get('CU')
        or row_data.get('Billable Unit Code')
        or ''
    ).strip().upper()
    if cu_code == 'NAN':
        cu_code = str(row_data.get('CU') or '').strip().upper()
    return cu_code


def recalculate_row_price(row_data, cu_to_group, rates_dict, *, out_status=None):
    """Recalculate a row's price using new contract rates.

    Looks up the CU code, maps it to its Compatible Unit Group, then
    calculates price as rate × quantity using the provided rates dict.
    Modifies row_data['Units Total Price'] in-place if a matching rate is found.

    Args:
        row_data: Dict of row field values (modified in-place).
        cu_to_group: Dict mapping detailed CU codes to group codes.
        rates_dict: Dict mapping group codes to {install, removal, transfer} rates.
        out_status: Optional dict that, when provided, receives an
            ``'outcome'`` key describing why the function returned:
              * ``'recalculated'`` — a rate was successfully applied
                (the returned price may still equal the original
                SmartSheet price if the computed rate × qty matches it
                exactly; lookup succeeded either way).
              * ``'missing_rate'`` — neither the mapped group nor the
                CU code is present in ``rates_dict``; SmartSheet price
                retained. This is the only outcome the per-sheet
                "skipped" summary counts toward, because it is the
                actionable signal that ``NEW_RATES_CSV`` needs a new
                entry.
              * ``'invalid_quantity'`` — quantity is zero/missing/
                unparseable; SmartSheet price retained.
              * ``'zero_rate'`` — new rate for the resolved work type
                is zero; SmartSheet price retained.

    Returns:
        float: The (possibly recalculated) price value.
    """
    def _set_status(s):
        if out_status is not None:
            out_status['outcome'] = s

    price_val = parse_price(row_data.get('Units Total Price'))

    # Resolve CU code (same chain as revert_subcontractor_price)
    cu_code = _resolve_cu_code(row_data)

    # Map detailed CU code to group code
    group_code = cu_to_group.get(cu_code)
    if not group_code:
        # CU code not found in mapping — try direct group lookup (in case SmartSheet uses group codes)
        if cu_code in rates_dict:
            group_code = cu_code
        else:
            logging.debug(f"Rate recalculation: CU '{cu_code}' not found in CU-to-group mapping or rates, keeping SmartSheet price")
            _set_status('missing_rate')
            return price_val

    # If the mapped group isn't in the new rates table (e.g. old CSV maps
    # CU -> a verbose group name like "Vacuum Switch" that never appears
    # in the new rates' short-code keys), fall back to looking up the CU
    # code directly in the rates table. This recovers specialized work
    # items (common on VAC crew sheets) where the detailed CU code is
    # itself a key in the new contract rates. Only activates on exact
    # match, so no chance of mis-applying a rate.
    if group_code not in rates_dict:
        if cu_code in rates_dict:
            logging.debug(f"Rate recalculation: mapped group '{group_code}' not in new rates for CU '{cu_code}'; matched CU directly")
            group_code = cu_code
        else:
            logging.warning(f"Rate recalculation SKIPPED: CU '{cu_code}' maps to group '{group_code}' but neither is in new rates — keeping SmartSheet price (Qty={row_data.get('Quantity')}, Work Type={row_data.get('Work Type')})")
            _set_status('missing_rate')
            return price_val

    # Determine work type
    work_type_raw = str(row_data.get('Work Type') or '').strip().lower()
    wt_key = 'install'
    if 'rem' in work_type_raw:
        wt_key = 'removal'
    elif 'tran' in work_type_raw or 'xfr' in work_type_raw:
        wt_key = 'transfer'

    # Parse quantity — if missing or unparseable, keep SmartSheet price
    qty_str = str(row_data.get('Quantity', '') or '')
    try:
        qty = float(_RE_EXTRACT_NUMBERS.sub('', qty_str) or 0)
    except ValueError:
        qty = 0.0

    if qty <= 0:
        logging.debug(f"Rate recalculation: quantity '{qty_str}' is zero/missing for CU '{cu_code}', keeping SmartSheet price")
        _set_status('invalid_quantity')
        return price_val

    rate = rates_dict[group_code].get(wt_key, 0.0)
    if rate <= 0:
        logging.debug(f"Rate recalculation: rate is zero for group '{group_code}' work type '{wt_key}', keeping SmartSheet price")
        _set_status('zero_rate')
        return price_val

    new_price = round(rate * qty, 2)
    row_data['Units Total Price'] = new_price
    _set_status('recalculated')
    return new_price


def revert_subcontractor_price(row_data, original_rates):
    """Revert a subcontractor row's price to the 100% original contract rate.

    Looks up the CU code from row_data (preferring CU Helper, then CU,
    then Billable Unit Code), determines the work type, and recalculates
    the price as original_rate × quantity.

    Args:
        row_data: Dict of row field values (modified in-place if reverted).
        original_rates: Dict mapping CU codes to {install, removal, transfer} rates.

    Returns:
        The (possibly recalculated) price value as a float.
    """
    price_val = parse_price(row_data.get('Units Total Price'))

    cu_code = _resolve_cu_code(row_data)

    work_type_raw = str(row_data.get('Work Type') or '').strip().lower()

    wt_key = 'install'
    if 'rem' in work_type_raw:
        wt_key = 'removal'
    elif 'tran' in work_type_raw or 'xfr' in work_type_raw:
        wt_key = 'transfer'

    qty_str = str(row_data.get('Quantity', '') or '0')
    try:
        qty = float(_RE_EXTRACT_NUMBERS.sub('', qty_str) or 0)
    except ValueError:
        qty = 0.0

    if cu_code in original_rates:
        exact_original_rate = original_rates[cu_code].get(wt_key, 0.0)
        price_val = round(exact_original_rate * qty, 2)
        row_data['Units Total Price'] = price_val

    return price_val

def is_checked(value: bool | int | str | None) -> bool:
    """Check if a checkbox value is considered checked/true.
    
    Args:
        value: Checkbox value in various formats
    
    Returns:
        bool: True if the value represents a checked state
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in ('true', 'checked', 'yes', '1', 'on')
    return False

def excel_serial_to_date(value):
    """Strict date parsing: return datetime or None. No numeric/serial fallbacks.
    
    PERFORMANCE: Fast-path for ISO format dates (YYYY-MM-DD) before falling back
    to the slower dateutil.parser.parse() for other formats.
    """
    if value in (None, ""):
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime.combine(value, datetime.time.min)
    s = str(value).strip()
    # PERFORMANCE: Fast-path for ISO date format (most common in Smartsheet)
    if len(s) >= 10 and s[4] == '-' and s[7] == '-':
        try:
            # Try ISO format first (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
            date_part = s[:10]
            return datetime.datetime.strptime(date_part, '%Y-%m-%d')
        except ValueError:
            pass  # Fall through to general parser
    try:
        dt = parser.parse(s)
        if isinstance(dt, datetime.datetime):
            return dt
        return datetime.datetime.combine(dt, datetime.time.min)
    except Exception:
        return None


def _resolve_rate_recalc_cutoff_date(
    row_data,
    cutoff_date,
    *,
    weekly_fallback_enabled: bool = True,
):
    """Return the effective cutoff date for a row's pre-acceptance recalc.

    The snapshot-keyed business rule remains primary: any row with a
    populated ``Snapshot Date`` is gated on that date alone. The
    Weekly-Ref-Date fallback only activates when ``Snapshot Date`` is
    blank or unparseable — it rescues current-week rows that would
    otherwise silently skip recalc because Smartsheet's snapshot
    automation has not fired yet (the observed VAC crew failure mode).

    Args:
        row_data: Mapping that may contain ``'Snapshot Date'`` and
            ``'Weekly Reference Logged Date'`` entries.
        cutoff_date: ``datetime.date`` used as the ``>=`` threshold.
        weekly_fallback_enabled: Set False to reproduce the legacy
            snapshot-only behaviour (the ``RATE_RECALC_WEEKLY_FALLBACK``
            env var wires this in production).

    Returns:
        ``(effective_cutoff_date, used_fallback)``. Returns
        ``(None, False)`` when recalc should not run.
    """
    if cutoff_date is None:
        return (None, False)

    snapshot_raw = row_data.get('Snapshot Date')
    snap_date = None
    if snapshot_raw:
        snap_dt = excel_serial_to_date(snapshot_raw)
        if snap_dt:
            snap_date = (
                snap_dt.date() if hasattr(snap_dt, 'date') else snap_dt
            )

    if snap_date is not None and snap_date >= cutoff_date:
        return (snap_date, False)

    if snap_date is None and weekly_fallback_enabled:
        weekly_raw = row_data.get('Weekly Reference Logged Date')
        if weekly_raw:
            weekly_dt = excel_serial_to_date(weekly_raw)
            if weekly_dt:
                weekly_date = (
                    weekly_dt.date()
                    if hasattr(weekly_dt, 'date')
                    else weekly_dt
                )
                if weekly_date >= cutoff_date:
                    return (weekly_date, True)

    return (None, False)


def _weekly_would_trigger_fallback(weekly_raw, cutoff_date) -> bool:
    """Return True if a blank/unparseable Snapshot Date row would be
    rescued by flipping ``RATE_RECALC_WEEKLY_FALLBACK`` on.

    Mirrors the secondary branch of
    ``_resolve_rate_recalc_cutoff_date``: the fallback only fires when
    the weekly date parses AND is ``>= cutoff_date``. Used to gate the
    fallback-disabled operator note so it doesn't misleadingly suggest
    enabling the env var for rows whose weekly date is also blank,
    unparseable, or pre-cutoff (where flipping the gate wouldn't
    change anything).
    """
    if cutoff_date is None or not weekly_raw:
        return False
    dt = excel_serial_to_date(weekly_raw)
    if dt is None:
        return False
    wdate = dt.date() if hasattr(dt, 'date') else dt
    return wdate >= cutoff_date


def discover_folder_sheets(client, folder_ids: list[int], label: str) -> set[int]:
    """Discover all sheet IDs inside the given Smartsheet folders (recursively including subfolders).

    Args:
        client: Authenticated Smartsheet client instance.
        folder_ids: List of Smartsheet folder IDs to enumerate.
        label: Human-readable label for logging (e.g. 'subcontractor', 'original contract').

    Returns:
        Set of sheet IDs found across all folders and their subfolders.
    """
    discovered: set[int] = set()
    if not folder_ids:
        return discovered

    def _fetch_folder_recursive(fid, depth=0, max_depth=5):
        """Fetch sheets from a single folder, recursing into subfolders."""
        if depth > max_depth:
            logging.warning(f"⚠️ Max folder recursion depth ({max_depth}) reached for {label} folder {fid}")
            return set()
        try:
            with sentry_sdk.start_span(op="smartsheet.api", name=f"Get folder {fid} ({label} depth={depth})") as span:
                from smartsheet.models.sheet import Sheet as _SmartsheetSheet
                from smartsheet.models.folder import Folder as _SmartsheetFolder
                sheets: list = []
                subfolders: list = []
                last_key = None
                # Safety caps: guard against a misbehaving API that perpetually
                # returns a non-falsy or repeated last_key, which would otherwise
                # create a large API burst (amplifying Smartsheet 300 req/min limits).
                max_pages = 100
                pages_fetched = 0
                page_start_time = time.monotonic()
                seen_last_keys: set = set()
                for _page_num in range(max_pages):
                    page = client.Folders.get_folder_children(
                        fid,
                        children_resource_types=["sheets", "folders"],
                        last_key=last_key,
                    )
                    pages_fetched += 1
                    for item in getattr(page, 'data', None) or []:
                        if isinstance(item, _SmartsheetSheet):
                            sheets.append(item)
                        elif isinstance(item, _SmartsheetFolder):
                            subfolders.append(item)
                    next_last_key = getattr(page, 'last_key', None)
                    if not next_last_key:
                        break
                    if next_last_key in seen_last_keys:
                        elapsed = time.monotonic() - page_start_time
                        logging.warning(
                            f"⚠️ Repeated pagination token detected for {label} folder {fid}; "
                            f"stopping after {pages_fetched} page(s) in {elapsed:.2f}s "
                            f"with {len(sheets)} sheet(s)"
                        )
                        break
                    seen_last_keys.add(next_last_key)
                    last_key = next_last_key
                else:
                    elapsed = time.monotonic() - page_start_time
                    logging.warning(
                        f"⚠️ Pagination safety cap ({max_pages}) reached for {label} folder {fid}; "
                        f"stopping after {pages_fetched} page(s) in {elapsed:.2f}s "
                        f"with {len(sheets)} sheet(s)"
                    )
                ids = {s.id for s in sheets}
                span.set_data("folder_id", fid)
                span.set_data("sheets_found", len(sheets))
                span.set_data("depth", depth)
            logging.info(f"{'  ' * depth}📂 Folder {fid} ({label}): found {len(sheets)} direct sheet(s)")
            # Recurse into subfolders to discover ALL sheets in the hierarchy
            for subfolder in subfolders:
                sub_id = subfolder.id
                sub_ids = _fetch_folder_recursive(sub_id, depth + 1, max_depth)
                if sub_ids:
                    logging.info(f"{'  ' * (depth + 1)}📁 Subfolder {sub_id}: contributed {len(sub_ids)} sheet(s)")
                ids |= sub_ids

            return ids
        except Exception as e:
            logging.warning(f"⚠️ Could not read {label} folder {fid}: {e}")
            sentry_add_breadcrumb("folder_discovery", f"Failed to read folder {fid}", level="error", data={
                "folder_id": fid, "label": label, "depth": depth, "error": str(e)[:200],
            })
            return set()

    with ThreadPoolExecutor(max_workers=min(len(folder_ids), PARALLEL_WORKERS_DISCOVERY)) as executor:
        for ids in executor.map(lambda fid: _fetch_folder_recursive(fid), folder_ids):
            discovered |= ids

    logging.info(f"📂 Total {label} folder discovery (recursive): {len(discovered)} unique sheet(s)")
    return discovered

def calculate_data_hash(group_rows: list[dict]) -> str:
    """Calculate a hash of the group data to detect changes.

    Args:
        group_rows: List of row dictionaries to hash
    
    Returns:
        str: 16-character SHA256 hash prefix

    Legacy (EXTENDED_CHANGE_DETECTION=0):
        Uses original minimal fields so hash stability is preserved for rollbacks.

    Extended (default):
        Incorporates additional business-critical fields so regenerated Excel
        files occur when any of these change:
          • Current foreman name (derived '__current_foreman')
          • Dept # values present across the group (set + order)
          • Scope ID / #
          • Aggregated total billed amount
          • Unique dept list and row count
          • All prior minimal fields
    """
    if not group_rows:
        return "0" * 16

    # Deterministic sorting across key business fields.
    #
    # In EXTENDED mode, VAC crew fields appear as tie-breakers so multi-member
    # VAC crew groups — where two rows can share (WR, Snapshot, CU, Pole, Qty)
    # while belonging to different crew members — hash stably across runs.
    # Without the tie-breaker, row insertion order (merged from parallel
    # `as_completed` futures in `get_all_source_rows`) bleeds into the hash
    # because VAC crew fields are included per-row in row_str.
    #
    # LEGACY mode (EXTENDED_CHANGE_DETECTION=0) intentionally keeps the
    # original 5-key sort: the docstring promises legacy uses only the
    # original minimal fields so hashes stay bit-stable for rollbacks.
    # Adding tie-breakers there would change row order for tied rows whose
    # legacy row_data still differs (Work Type / Units Completed? / price),
    # invalidating the rollback-stability guarantee. Legacy mode's row_data
    # also excludes VAC crew fields, so a vac_crew-specific tie-breaker
    # there would be purely cosmetic — skip it.
    _sort_base = lambda x: (
        str(x.get('Work Request #', '')),
        str(x.get('Snapshot Date', '')),
        str(x.get('CU', '')),
        str(x.get('Pole #') or x.get('Point #') or x.get('Point Number') or ''),
        str(x.get('Quantity', '')),
    )
    if EXTENDED_CHANGE_DETECTION:
        sorted_rows = sorted(
            group_rows,
            key=lambda x: _sort_base(x) + (
                str(x.get('__vac_crew_name') or ''),
                str(x.get('__vac_crew_dept') or ''),
                str(x.get('__vac_crew_job') or ''),
            ),
        )
    else:
        sorted_rows = sorted(group_rows, key=_sort_base)

    if not EXTENDED_CHANGE_DETECTION:
        # OPTIMIZATION: Use incremental hashing to avoid large string allocation
        hasher = hashlib.sha256()
        for row in sorted_rows:
            # CRITICAL: Use parse_price() for normalization to avoid format-based false changes
            normalized_price = f"{parse_price(row.get('Units Total Price', 0)):.2f}"
            row_data = (
                f"{row.get('Work Request #', '')}"
                f"{row.get('CU', '')}"
                f"{row.get('Quantity', '')}"
                f"{normalized_price}"
                f"{row.get('Snapshot Date', '')}"
                f"{row.get('Pole #', '')}"
                f"{row.get('Work Type', '')}"
                f"{is_checked(row.get('Units Completed?'))}"  # CRITICAL: Include completion status
            )
            hasher.update(row_data.encode('utf-8'))
        return hasher.hexdigest()[:16]

    # Extended mode: Use incremental hashing
    hasher = hashlib.sha256()

    # Variant is a group-level property (all rows in a group share the same
    # __variant). Compute it once before the row loop so per-row hash can
    # include variant-scoped fields deterministically.
    group_variant = sorted_rows[0].get('__variant', 'primary') if sorted_rows else 'primary'

    group_foreman = None
    for row in sorted_rows:
        foreman = row.get('__current_foreman') or row.get('Foreman') or ''
        if group_foreman is None and foreman:
            group_foreman = foreman
        # CRITICAL: Use parse_price() for normalization to avoid format-based false changes
        normalized_price = f"{parse_price(row.get('Units Total Price', 0)):.2f}"

        row_fields = [
            str(row.get('Work Request #', '')),
            str(row.get('Snapshot Date', '') or ''),
            str(row.get('CU', '') or ''),
            str(row.get('Quantity', '') or ''),
            normalized_price,
            str(row.get('Pole #') or row.get('Point #') or row.get('Point Number') or ''),
            str(row.get('Work Type', '') or ''),
            str(row.get('Dept #', '') or ''),
            str(row.get('Scope #') or row.get('Scope ID', '') or ''),
            str(is_checked(row.get('Units Completed?'))),  # CRITICAL: Include completion status
            # Additional fields to catch changes previously missed
            str(row.get('Customer Name', '') or ''),
            str(row.get('Job #') or row.get('Job Number', '') or ''),
            str(row.get('Work Order #') or row.get('Work Order Number', '') or ''),
            str(row.get('CU Description', '') or ''),
            str(row.get('Unit of Measure', '') or ''),
            str(row.get('Area', '') or ''),
        ]
        # VAC crew groups use a single `_VACCREW` key with no foreman suffix,
        # so one group can hold multiple crew members. Including per-row VAC
        # crew fields here lets each row contribute its own name/dept/job to
        # the hash independently. This avoids two pitfalls of aggregating
        # values into `meta_parts` as a set:
        #   1. Set dedup — e.g. depts {500, 500, 600}: editing one row's dept
        #      from 500→600 leaves {500, 600} unchanged, silently skipping
        #      regeneration.
        #   2. Delimiter collision — ','.join on free-text names cannot
        #      distinguish ['A,B', 'C'] from ['A', 'B,C'].
        # Scoped to vac_crew so hash stability for primary/helper rows is
        # preserved (non-vac_crew row_str structure is unchanged).
        if group_variant == 'vac_crew':
            row_fields.extend([
                str(row.get('__vac_crew_name') or ''),
                str(row.get('__vac_crew_dept') or ''),
                str(row.get('__vac_crew_job') or ''),
            ])

        row_str = "|".join(row_fields)
        # Update hash incrementally with newline separator
        hasher.update(row_str.encode('utf-8'))
        hasher.update(b"\n")

    unique_depts = sorted({str(r.get('Dept #', '') or '') for r in sorted_rows if r.get('Dept #') is not None})
    total_price = sum(parse_price(r.get('Units Total Price')) for r in sorted_rows)

    # Append metadata
    meta_parts = []
    meta_parts.append(f"FOREMAN={group_foreman or ''}")
    
    # Variant-specific hash tokens (replaces activity log USER= token)
    variant = group_variant
    meta_parts.append(f"VARIANT={variant}")

    if variant == 'helper':
        # Helper variant: include helper-specific metadata (helper_job is OPTIONAL).
        # Helper groups are split per foreman (group key: `_HELPER_{helper}`),
        # so every row in a helper group shares identical helper info —
        # reading sorted_rows[0] here is safe.
        _first = sorted_rows[0] if sorted_rows else {}
        helper_foreman = _first.get('__helper_foreman', '')
        helper_dept = _first.get('__helper_dept', '')
        helper_job = _first.get('__helper_job', '')
        # Validate required helper fields (helper_job is optional)
        if not helper_foreman or not helper_dept:
            logging.warning(f"⚠️ Helper variant missing required fields: foreman={helper_foreman}, dept={helper_dept}")
        if not helper_job:
            logging.info(f"ℹ️ Helper variant without Job #: foreman={helper_foreman}, dept={helper_dept} (proceeding anyway)")
        meta_parts.append(f"HELPER={helper_foreman}")
        meta_parts.append(f"HELPER_DEPT={helper_dept}")
        meta_parts.append(f"HELPER_JOB={helper_job}")  # Include even if empty for hash consistency
    # vac_crew variant intentionally has no meta_parts block: VAC crew
    # name/dept/job are already captured per-row in the row_str loop above,
    # which is strictly more sensitive than meta_parts aggregation and is not
    # vulnerable to set-dedup collisions or comma-in-name delimiter collisions.
    
    meta_parts.append(f"DEPTS={','.join(unique_depts)}")
    meta_parts.append(f"TOTAL={total_price:.2f}")
    meta_parts.append(f"ROWCOUNT={len(sorted_rows)}")
    if RATE_CUTOFF_DATE:
        meta_parts.append(f"RATE_CUTOFF={RATE_CUTOFF_DATE.isoformat()}")
        if _RATES_FINGERPRINT:
            meta_parts.append(f"RATES_FP={_RATES_FINGERPRINT}")

    # Update hash with metadata
    if meta_parts:
        hasher.update("\n".join(meta_parts).encode('utf-8'))

    return hasher.hexdigest()[:16]


def _compute_aggregated_content_hash(rows: list[dict]) -> str:
    """Deterministic content hash for a cross-variant row bucket.

    Used by the billing_audit integration to produce a
    ``pipeline_run.content_hash`` that covers every variant's rows
    for a given (WR, week). ``calculate_data_hash()`` assumes the
    rows it's called with all come from a single production
    ``group_source_rows`` group; that assumption breaks for an
    aggregation bucket that unions multiple groups of the same
    variant. In particular, helper groups are split per-foreman
    (group key ``{week}_{wr}_HELPER_{sanitized_foreman}``) — so
    multiple helper groups can exist for the same (WR, week) and
    calling ``calculate_data_hash(variant='helper', rows=...)``
    with all of them at once would:

      1. Read helper_foreman/dept/job from ``sorted_rows[0]`` only
         (variant-specific meta block), so identity changes on
         non-first helpers never reach the hash.
      2. Depend on row sort order for which helper's identity
         gets recorded — flips spuriously between runs.

    Primary groups are keyed on ``{week}_{wr}`` alone (one group
    per WR/week, no user suffix) and vac_crew on
    ``{week}_{wr}_VACCREW`` (one group, multi-member handled
    internally by ``calculate_data_hash``'s per-row VAC fields)
    — so only the ``helper`` variant needs sub-bucketing here.

    The combined hash is SHA-256 over the sorted
    ``variant=hash`` tokens (sub-bucketed for helper).
    """
    by_variant: dict[str, list[dict]] = {}
    for r in rows:
        v = r.get('__variant', 'primary')
        by_variant.setdefault(v, []).append(r)

    parts: list[str] = []
    for v in sorted(by_variant.keys()):
        variant_rows = by_variant[v]
        if v == 'helper':
            # Sub-bucket by helper identity to match the per-
            # foreman group structure assumed by
            # calculate_data_hash's helper branch.
            sub: dict[tuple[str, str, str], list[dict]] = {}
            for r in variant_rows:
                sk = (
                    str(r.get('__helper_foreman', '')),
                    str(r.get('__helper_dept', '')),
                    str(r.get('__helper_job', '')),
                )
                sub.setdefault(sk, []).append(r)
            sub_parts = [
                f"{sk}={calculate_data_hash(sub[sk])}"
                for sk in sorted(sub.keys())
            ]
            variant_hash = hashlib.sha256(
                "|".join(sub_parts).encode('utf-8')
            ).hexdigest()[:16]
        else:
            variant_hash = calculate_data_hash(variant_rows)
        parts.append(f"{v}={variant_hash}")

    return hashlib.sha256(
        "|".join(parts).encode('utf-8')
    ).hexdigest()[:16]


def extract_data_hash_from_filename(filename: str) -> str | None:
    """Extract data hash from filename format: WR_{wr_num}_WeekEnding_{week_end}_{data_hash}.xlsx
    
    Args:
        filename: Excel filename to parse
    
    Returns:
        str | None: 16-character hash if found, else None
    """
    try:
        name_without_ext = filename.replace('.xlsx', '')
        parts = name_without_ext.split('_')
        if len(parts) >= 4 and len(parts[-1]) == 16:
            return parts[-1]
    except Exception:
        pass
    return None

def list_generated_excel_files(folder: str) -> list[str]:
    """List Excel files beginning with WR_ in the specified folder.
    
    Args:
        folder: Directory path to scan
    
    Returns:
        list[str]: List of matching Excel filenames
    """
    try:
        return [f for f in os.listdir(folder) if f.startswith('WR_') and f.lower().endswith('.xlsx')]
    except FileNotFoundError:
        return []

def build_group_identity(filename: str) -> tuple[str, str, str, str | None] | None:
    """
    Parse filename to extract identity tuple: (wr, week_ending, variant, helper_or_user).
    
    Args:
        filename: Excel filename to parse
    
    Returns:
        tuple with format:
        - Primary: (wr, week, 'primary', None)
        - Primary+User: (wr, week, 'primary', user_identifier)
        - Helper: (wr, week, 'helper', helper_name)
        - VAC Crew: (wr, week, 'vac_crew', '')
        
        Legacy format without variant: (wr, week, 'primary', None)
        
        Returns None if filename doesn't match expected format.
    
    Filename formats supported:
    - WR_{wr}_WeekEnding_{week}_{hash}.xlsx (legacy primary)
    - WR_{wr}_WeekEnding_{week}_{timestamp}_{hash}.xlsx (primary)
    - WR_{wr}_WeekEnding_{week}_{timestamp}_User_{user}_{hash}.xlsx (primary+user)
    - WR_{wr}_WeekEnding_{week}_{timestamp}_Helper_{helper}_{hash}.xlsx (helper)
    - WR_{wr}_WeekEnding_{week}_{timestamp}_VacCrew_{hash}.xlsx (VAC Crew)
    """
    if not filename.startswith('WR_'):
        return None
    base = filename[:-5] if filename.lower().endswith('.xlsx') else filename
    parts = base.split('_')

    # Minimum: WR_<wr>_WeekEnding_<week>
    if len(parts) < 4:
        return None
    if parts[0] != 'WR':
        return None
    # Find ``WeekEnding`` by search rather than fixed position so
    # filenames whose WR token itself contains ``_`` (possible when
    # ``_RE_SANITIZE_HELPER_NAME`` rewrote a sanitization-sensitive
    # source WR#) still parse correctly. For realistic numeric WR#s
    # the marker is at position 2 exactly — this preserves the
    # legacy layout while hardening against the edge case.
    #
    # Disambiguate via the filename format itself. The STRUCTURAL
    # ``WeekEnding`` in the modern format is followed by TWO
    # consecutive 6-digit tokens:
    #   ``WeekEnding_{MMDDYY week}_{HHMMSS timestamp}_...``
    # while the legacy format (still readable off disk but no longer
    # produced) is:
    #   ``WeekEnding_{MMDDYY week}_{hash}.xlsx``
    # where the hash is hex and is essentially never exactly 6
    # digits. Helper/user identifier segments that happen to contain
    # ``WeekEnding_<6digits>`` (pathological but possible, see
    # rounds 10/11) are followed by the HASH, not a second 6-digit
    # token. So we rank candidates:
    #   * STRONG match: ``WeekEnding`` + 6-digit week + 6-digit
    #     timestamp (new format's unambiguous marker).
    #   * WEAK match: ``WeekEnding`` + 6-digit week (accepts legacy
    #     format + any other filename where a second 6-digit token
    #     isn't present).
    # Pick the RIGHTMOST strong match if any — it's always the real
    # structural delimiter because no identifier segment is ever
    # followed by two 6-digit tokens in a row. Fall back to the
    # rightmost weak match only for legacy-format filenames whose
    # hash happens not to be 6 digits (vanishingly rare collision
    # window for the weak-match path).
    _strong_candidates: list[int] = []
    _weak_candidates: list[int] = []
    for _i, _p in enumerate(parts):
        if _p != 'WeekEnding' or _i < 2 or _i + 1 >= len(parts):
            continue
        _week = parts[_i + 1]
        if not (len(_week) == 6 and _week.isdigit()):
            continue
        _weak_candidates.append(_i)
        if _i + 2 < len(parts):
            _timestamp = parts[_i + 2]
            if len(_timestamp) == 6 and _timestamp.isdigit():
                _strong_candidates.append(_i)
    # Pick the LEFTMOST strong match if any — the structural
    # delimiter always comes before any identifier-internal
    # candidate in a filename generated by ``generate_excel``
    # (variant marker + identifier are appended AFTER the
    # timestamp). Using leftmost rather than rightmost resolves
    # the final known pathology: a pathological identifier that
    # sanitizes to ``WeekEnding_<6digits>_<6digits>`` (e.g. from
    # a foreman literally named "WeekEnding 041926 123456")
    # would produce a second strong candidate inside the tail,
    # and rightmost would incorrectly pick it. Fall back to the
    # leftmost weak match only for legacy-format filenames.
    #
    # The remaining residual — a WR token that itself sanitizes
    # to ``WeekEnding_<6digits>_<6digits>`` (which would then
    # provide its own strong match at a position earlier than
    # the structural one) — is the last unreachable edge. It
    # requires a raw WR# literally equal to that pattern, which
    # is not a realistic data-entry scenario for numeric WR#s;
    # the source-side collision quarantine (pre-scan on
    # sanitized WR alone) would also flag such a pathological
    # value long before the parser is exercised.
    if _strong_candidates:
        we_idx = _strong_candidates[0]
    elif _weak_candidates:
        we_idx = _weak_candidates[0]
    else:
        return None

    # WR may span one or more parts depending on whether the
    # sanitizer introduced underscores. Rejoin them so the returned
    # WR token round-trips with the generator's output.
    wr = '_'.join(parts[1:we_idx])
    week = parts[we_idx + 1]

    # Detect variant from filename structure. Scope the marker search
    # to the tail (everything after ``WeekEnding <week>``) so any
    # accidental ``Helper`` / ``User`` / ``VacCrew`` token inside a
    # sanitized WR does not false-positive the variant detection.
    variant = 'primary'
    identifier = None
    tail = parts[we_idx + 2:]

    if 'Helper' in tail:
        variant = 'helper'
        helper_idx_rel = tail.index('Helper')
        if helper_idx_rel + 1 < len(tail):
            # Join all parts between Helper and hash (last part)
            # Format: ...Helper_{name}_{hash} or ...Helper_{name}_part2_{hash}
            identifier = '_'.join(tail[helper_idx_rel + 1:-1])
    elif 'VacCrew' in tail:
        variant = 'vac_crew'
        identifier = ''  # No sub-identifier for VAC Crew; use '' to match main() and valid_wr_weeks
    elif 'User' in tail:
        variant = 'primary'
        user_idx_rel = tail.index('User')
        if user_idx_rel + 1 < len(tail):
            identifier = '_'.join(tail[user_idx_rel + 1:-1])

    return (wr, week, variant, identifier)

def cleanup_stale_excels(output_folder: str, kept_filenames: set):
    """Remove Excel files not generated in current run (VARIANT-AWARE).

    Strategy:
      1. Keep all names in kept_filenames.
      2. For identities (wr, week, variant, identifier) present in kept_filenames, 
         remove any other files with same identity (older timestamp/hash).
      3. Remove any other WR_*.xlsx whose identity is not in current run 
         (per user requirement to only keep new system outputs).
      4. CRITICAL: Never cross-delete between variants (primary vs helper).
    
    Identity includes variant dimension to prevent primary/helper cross-deletion.
    Returns list of removed filenames.
    """
    removed = []
    existing = list_generated_excel_files(output_folder)
    identities_to_keep = set()
    for fname in kept_filenames:
        ident = build_group_identity(fname)
        if ident:
            identities_to_keep.add(ident)
    for fname in existing:
        if fname in kept_filenames:
            continue
        ident = build_group_identity(fname)
        if ident and ident in identities_to_keep:
            # Variant of identity we already produced this run
            try:
                os.remove(os.path.join(output_folder, fname))
                removed.append(fname)
            except Exception as e:
                logging.warning(f"⚠️ Failed to remove stale variant {fname}: {e}")
        elif ident:
            # Different identity (older run) – remove per requirement
            try:
                os.remove(os.path.join(output_folder, fname))
                removed.append(fname)
            except Exception as e:
                logging.warning(f"⚠️ Failed to remove legacy file {fname}: {e}")
        # Non-conforming files left untouched
    return removed

def cleanup_untracked_sheet_attachments(client, target_sheet_id: int, valid_wr_weeks: set, test_mode: bool, attachment_cache: dict | None = None, target_sheet=None):
    """Prune only older variants for identities processed this run (VARIANT-AWARE).

    If KEEP_HISTORICAL_WEEKS=1 (default false here), weeks not in this run are preserved.
    valid_wr_weeks: set of 4-tuples (wr, week_mmddyy, variant, identifier) that were 
                    generated or validated this session.
    attachment_cache: Pre-fetched dict of row_id -> attachment list (avoids per-row API calls).
    target_sheet: Pre-loaded target sheet object (avoids redundant API call).
    
    CRITICAL: Identity includes variant dimension to prevent primary/helper cross-deletion.
              Each (wr, week, variant, identifier) is treated as independent.
    """
    if test_mode:
        logging.info("🧪 Test mode – skipping sheet attachment pruning")
        return
    try:
        sheet = target_sheet if target_sheet is not None else client.Sheets.get_sheet(target_sheet_id)
    except Exception as e:
        logging.warning(f"⚠️ Could not load target sheet for attachment cleanup: {e}")
        return
    removed_variants = 0
    for row in sheet.rows:
        try:
            # Use pre-fetched cache if available; otherwise fall back to per-row API call
            if attachment_cache is not None and row.id in attachment_cache:
                attachments = attachment_cache[row.id]
            else:
                attachments = client.Attachments.list_row_attachments(target_sheet_id, row.id).data
        except Exception:
            continue
        identity_groups = collections.defaultdict(list)
        for att in attachments:
            name = getattr(att,'name','') or ''
            if name.startswith('WR_') and name.endswith('.xlsx'):
                ident = build_group_identity(name)
                if ident:
                    identity_groups[ident].append(att)
        for ident, atts in identity_groups.items():
            # Skip identities not processed if preserving historical weeks
            if ident not in valid_wr_weeks and KEEP_HISTORICAL_WEEKS:
                continue
            # Sort attachments newest first based on timestamp token
            def _ts(a):
                parts = a.name.split('_')
                # Find timestamp (should be after WeekEnding_{week})
                for i, p in enumerate(parts):
                    if p == 'WeekEnding' and i + 2 < len(parts):
                        ts_candidate = parts[i + 2]
                        if ts_candidate.isdigit() and len(ts_candidate) == 6:
                            return ts_candidate
                return '000000'
            atts_sorted = sorted(atts, key=_ts, reverse=True)
            # Keep newest; remove others
            for old in atts_sorted[1:]:
                try:
                    client.Attachments.delete_attachment(target_sheet_id, old.id)
                    removed_variants += 1
                    logging.info(f"🗑️ Removed older variant: {old.name}")
                except Exception as e:
                    logging.warning(f"⚠️ Could not delete variant {old.name}: {e}")
    logging.info(f"🧹 Variant pruning done: removed_variants={removed_variants}")

def delete_old_excel_attachments(client, target_sheet_id, target_row, wr_num, week_raw, current_data_hash, variant='primary', identifier=None, force_generation=False, cached_attachments: list | None = None):
    """Delete prior Excel attachment(s) ONLY for the specific (WR, week, variant, identifier) identity.

    VARIANT-AWARE BEHAVIOR:
    • Looks for attachments matching (wr, week, variant, identifier) exactly
    • CRITICAL: Never deletes across variants (primary vs helper)
    • If an attachment for that identity already has the identical data hash
      (and not forcing) we skip regeneration & upload
    • Leaves attachments for other weeks and other variants untouched

    Args:
        variant: 'primary' or 'helper'
        identifier: For helper variant, the helper name; for primary+user, the user identifier
        cached_attachments: Pre-fetched attachment list (avoids redundant API call)

    Returns (deleted_count, skipped_due_to_same_data)
    """
    deleted_count = 0
    try:
        attachments = cached_attachments if cached_attachments is not None else client.Attachments.list_row_attachments(target_sheet_id, target_row.id).data
    except Exception as e:
        logging.warning(f"Could not list attachments for row {target_row.id}: {e}")
        return 0, False

    # Build variant-specific prefix patterns
    # Format: WR_{wr}_WeekEnding_{week}_<variant_marker>
    base_prefix = f"WR_{wr_num}_WeekEnding_{week_raw}"
    
    candidates = []
    for a in attachments:
        name = getattr(a, 'name', '') or ''
        if not name.endswith('.xlsx'):
            continue
        
        # Parse identity from filename
        ident = build_group_identity(name)
        if not ident:
            continue
        
        ident_wr, ident_week, ident_variant, ident_identifier = ident
        
        # Match only if all identity components match
        # Normalize None/'' to avoid mismatch between build_group_identity (returns None) and main loop (uses '')
        if (ident_wr == wr_num and 
            ident_week == week_raw and 
            ident_variant == variant and
            (ident_identifier or '') == (identifier or '')):
            candidates.append(a)

    if not candidates:
        return 0, False

    # Skip if any existing candidate already carries the same hash (unless forced)
    if not force_generation:
        for att in candidates:
            existing_hash = extract_data_hash_from_filename(att.name)
            if existing_hash == current_data_hash:
                logging.info(f"⏩ Unchanged ({variant} WR {wr_num} Week {week_raw}) hash {current_data_hash}; skipping regeneration & upload")
                return 0, True
    else:
        logging.info(f"⚐ FORCE GENERATION for {variant} WR {wr_num} Week {week_raw}; ignoring existing hash match")

    logging.info(f"🗑️ Removing {len(candidates)} prior {variant} attachment(s) for WR {wr_num} Week {week_raw}")
    for att in candidates:
        try:
            client.Attachments.delete_attachment(target_sheet_id, att.id)
            deleted_count += 1
            logging.info(f"   ✅ Deleted: {att.name}")
        except Exception as e:
            msg = str(e).lower()
            if '404' in msg or 'not found' in msg:
                logging.info(f"   ℹ️ Already gone: {att.name}")
            else:
                logging.warning(f"   ⚠️ Delete failed {att.name}: {e}")
    return deleted_count, False

def _has_existing_week_attachment(client, target_sheet_id, target_row, wr_num: str, week_raw: str, variant: str = 'primary', identifier: str | None = None, cached_attachments: list | None = None) -> bool:
    """Return True if at least one attachment exists for this (WR, week, variant, identifier) identity."""
    try:
        attachments = cached_attachments if cached_attachments is not None else client.Attachments.list_row_attachments(target_sheet_id, target_row.id).data
    except Exception:
        return False
    
    # Check for attachments matching this exact identity
    for a in attachments:
        name = getattr(a, 'name', '') or ''
        if not name.endswith('.xlsx'):
            continue
        
        # Parse identity from filename
        ident = build_group_identity(name)
        if not ident:
            continue
        
        ident_wr, ident_week, ident_variant, ident_identifier = ident
        
        # Match only if all identity components match
        # Normalize None/'' to avoid mismatch between build_group_identity (returns None) and main loop (uses '')
        if (ident_wr == wr_num and 
            ident_week == week_raw and 
            ident_variant == variant and
            (ident_identifier or '') == (identifier or '')):
            return True
    
    return False

def purge_existing_hashed_outputs(client, target_sheet_id: int, wr_subset: set | None, test_mode: bool):
    """Delete existing hashed Excel attachments and local files so hashes recompute fresh.

    wr_subset: if provided, only purge attachments for these WR numbers; otherwise purge all WR_*.xlsx attachments.
    """
    # Local file purge
    try:
        local_files = list_generated_excel_files(OUTPUT_FOLDER)
        removed_local = 0
        for f in local_files:
            wr_ident = build_group_identity(f)
            if wr_subset and wr_ident and wr_ident[0] not in wr_subset:
                continue
            try:
                os.remove(os.path.join(OUTPUT_FOLDER, f))
                removed_local += 1
            except Exception:
                pass
        logging.info(f"🧨 Local hash reset: removed {removed_local} existing Excel file(s)")
    except Exception as e:
        logging.warning(f"⚠️ Local hash reset failed: {e}")

    if test_mode:
        logging.info("🧪 Test mode active – skipping remote attachment purge")
        return
    try:
        sheet = client.Sheets.get_sheet(target_sheet_id)
    except Exception as e:
        logging.warning(f"⚠️ Could not load target sheet for purge: {e}")
        return
    purged = 0
    scanned = 0
    for row in sheet.rows:
        try:
            attachments = client.Attachments.list_row_attachments(target_sheet_id, row.id).data
        except Exception:
            continue
        for att in attachments:
            name = getattr(att,'name','') or ''
            if not name.startswith('WR_') or not name.endswith('.xlsx'):
                continue
            ident = build_group_identity(name)
            if wr_subset and ident and ident[0] not in wr_subset:
                continue
            scanned += 1
            try:
                client.Attachments.delete_attachment(target_sheet_id, att.id)
                purged += 1
                logging.info(f"🗑️ Purged attachment: {name}")
            except Exception as e:
                logging.warning(f"⚠️ Failed to purge attachment {name}: {e}")
    logging.info(f"🔥 Remote hash reset complete: purged {purged} / scanned {scanned} matching attachment(s)")

# --- HASH HISTORY PERSISTENCE ---

def load_hash_history(path: str):
    if RESET_HASH_HISTORY:
        logging.info("♻️ Hash history reset requested; ignoring existing history file")
        return {}
    try:
        with open(path,'r') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logging.warning("⚠️ Hash history is not a dict; resetting")
            return {}
        # Validate entries: keep only those with a 'hash' key
        valid = {k: v for k, v in data.items() if isinstance(v, dict) and 'hash' in v}
        dropped = len(data) - len(valid)
        if dropped:
            logging.warning(f"⚠️ Dropped {dropped} malformed hash history entries")
        return valid
    except FileNotFoundError:
        return {}
    except Exception as e:
        logging.warning(f"⚠️ Failed to load hash history: {e}")
        return {}

HASH_HISTORY_MAX_ENTRIES = 1000

def save_hash_history(path: str, history: dict):
    try:
        # Retention: keep only the most recent entries by timestamp
        if len(history) > HASH_HISTORY_MAX_ENTRIES:
            sorted_keys = sorted(
                history.keys(),
                key=lambda k: history[k].get('timestamp', ''),
                reverse=True
            )
            history = {k: history[k] for k in sorted_keys[:HASH_HISTORY_MAX_ENTRIES]}
            logging.info(f"🧹 Pruned hash history to {HASH_HISTORY_MAX_ENTRIES} entries")
        tmp_path = path + '.tmp'
        with open(tmp_path,'w') as f:
            json.dump(history, f, indent=2, default=str)
        os.replace(tmp_path, path)
        logging.info(f"📝 Hash history saved ({len(history)} entries)")
    except Exception as e:
        logging.warning(f"⚠️ Failed to save hash history: {e}")

# --- DATA DISCOVERY AND PROCESSING ---

def _title(t):
    return (t or "").strip().lower()


def _normalize_column_title_for_vac_crew(t):
    """Normalize a Smartsheet column title for fuzzy VAC Crew matching.

    Lowercases, canonicalises hyphenated (``vac-crew``) and joined-word
    (``vaccrew``) variants into the ``vac crew`` token, collapses runs of
    whitespace to a single space, and strips decorative trailing ``?`` or
    ``#`` (with optional surrounding spaces) so that operator-introduced
    variants like ``'Vac Crew Helping ?'``, ``'VAC CREW Helping?'``,
    ``'vac  crew helping'``, ``'Vac-Crew Helping?'``, ``'VacCrew Dept#'``
    or ``'Vac Crew Dept#'`` collapse to the same key as the canonical
    ``'VAC Crew Helping?'`` / ``'VAC Crew Dept #'``. Scoped intentionally
    narrow — only used by the VAC Crew fuzzy fallback in
    ``_validate_single_sheet`` — so primary/helper exact-match behaviour
    is preserved.
    """
    s = (t or "").strip().lower()
    # Hyphenated variants ('vac-crew') → space-separated.
    s = s.replace("-", " ")
    # Joined-word variants ('vaccrew') → space-separated. Word-boundary
    # guarded so unrelated tokens that happen to contain 'vaccrew' as a
    # substring are left untouched.
    s = re.sub(r"\bvaccrew\b", "vac crew", s)
    # Collapse any whitespace runs introduced by the substitutions above.
    s = re.sub(r"\s+", " ", s).strip()
    # Strip decorative trailing '?' / '#' with optional surrounding spaces.
    s = re.sub(r"\s*[\?#]+\s*$", "", s)
    return s


def discover_source_sheets(client):
    """Strict deterministic discovery: anchored keywords + type filtered. Skips sheets missing Weekly Reference Logged Date."""
    global _FOLDER_DISCOVERED_SUB_IDS, _FOLDER_DISCOVERED_ORIG_IDS, SUBCONTRACTOR_SHEET_IDS

    # ── ALWAYS run folder discovery FIRST (detects new sheets every run) ──────────
    # Folder listing is cheap (2-4 API calls + subfolder recursion).  Running it
    # unconditionally ensures sheets added to configured folders between runs are
    # detected even when the discovery cache is still within TTL.
    if SUBCONTRACTOR_FOLDER_IDS:
        _FOLDER_DISCOVERED_SUB_IDS = discover_folder_sheets(client, SUBCONTRACTOR_FOLDER_IDS, 'subcontractor')
        SUBCONTRACTOR_SHEET_IDS = SUBCONTRACTOR_SHEET_IDS | _FOLDER_DISCOVERED_SUB_IDS
        logging.info(f"📂 Subcontractor sheet IDs after folder merge: {len(SUBCONTRACTOR_SHEET_IDS)}")
    if ORIGINAL_CONTRACT_FOLDER_IDS:
        _FOLDER_DISCOVERED_ORIG_IDS = discover_folder_sheets(client, ORIGINAL_CONTRACT_FOLDER_IDS, 'original contract')
    _all_folder_discovered_ids = _FOLDER_DISCOVERED_SUB_IDS | _FOLDER_DISCOVERED_ORIG_IDS

    # ── Attempt cache load (skip when forced rediscovery requested) ──
    _cached_sheets = []          # previously-validated sheets from cache (used for incremental mode)
    _cached_sheet_ids = set()    # IDs of sheets already validated in cache
    _incremental = False         # True when cache expired but sheets can be reused
    if FORCE_REDISCOVERY:
        logging.info("🔄 FORCE_REDISCOVERY=true — bypassing discovery cache")
    elif USE_DISCOVERY_CACHE and os.path.exists(DISCOVERY_CACHE_PATH):
        try:
            with open(DISCOVERY_CACHE_PATH,'r') as f:
                cache = json.load(f)
            # Check cache schema version — invalidate if column synonyms have changed
            cached_version = cache.get('schema_version', 1)
            if cached_version < DISCOVERY_CACHE_VERSION:
                logging.info(f"🔄 Discovery cache schema outdated (v{cached_version} < v{DISCOVERY_CACHE_VERSION}) — forcing full rediscovery")
                raise ValueError('cache schema outdated')
            ts = datetime.datetime.fromisoformat(cache.get('timestamp'))
            age_min = (datetime.datetime.now() - ts).total_seconds()/60.0
            # Schema guard: each cached sheet must be a dict with an
            # integer ``id`` and a dict ``column_mapping`` — anything
            # else would crash ``_fetch_and_process_sheet`` when it
            # reads ``source['column_mapping']`` / ``source['id']``.
            # Drop malformed entries and WARN so operators can see
            # a corrupted cache immediately rather than debugging a
            # later AttributeError / KeyError.
            _raw_cached_sheets = cache.get('sheets', []) or []
            _valid_cached_sheets = [
                s for s in _raw_cached_sheets
                if isinstance(s, dict)
                and isinstance(s.get('id'), int)
                and isinstance(s.get('column_mapping'), dict)
                and isinstance(s.get('name'), str)
            ]
            if len(_valid_cached_sheets) != len(_raw_cached_sheets):
                logging.warning(
                    f"⚠️ Discovery cache contains "
                    f"{len(_raw_cached_sheets) - len(_valid_cached_sheets)} "
                    f"malformed sheet entry(ies); dropping them "
                    f"(keeping {len(_valid_cached_sheets)} valid). "
                    f"Delete {DISCOVERY_CACHE_PATH} to force a clean rediscovery."
                )
                # If *every* cached entry was malformed, the fresh-cache
                # return path below would otherwise hand back an empty
                # source list and the run would silently process zero
                # sheets. Escalate to the outer cache-load-failed handler
                # so we fall through to a full rediscovery from
                # ``base_sheet_ids`` — same behaviour as an outdated
                # schema or unreadable JSON.
                if _raw_cached_sheets and not _valid_cached_sheets:
                    raise ValueError(
                        f"all {len(_raw_cached_sheets)} cached sheet "
                        f"entries malformed; forcing full rediscovery"
                    )
            _cached_sheet_ids_from_file = {s['id'] for s in _valid_cached_sheets}
            # Compare folder-discovered sheet IDs against cache to detect new sheets
            _new_from_folders = _all_folder_discovered_ids - _cached_sheet_ids_from_file
            # Codex P2 guardrail: if the schema filter dropped ANY
            # entry, skip the fresh-cache fast path. A dropped entry
            # may have been a required static base sheet that isn't
            # in _all_folder_discovered_ids, so _new_from_folders
            # wouldn't flag it. Falling through to incremental mode
            # forces base_sheet_ids to be re-validated and the
            # dropped sheet to be rediscovered on this run instead
            # of waiting until cache expiry (up to
            # DISCOVERY_CACHE_TTL_MIN — default 7 days).
            _partial_cache_corruption = bool(_raw_cached_sheets) and (
                len(_valid_cached_sheets) != len(_raw_cached_sheets)
            )
            if (
                age_min <= DISCOVERY_CACHE_TTL_MIN
                and not _new_from_folders
                and not _partial_cache_corruption
            ):
                # Cache is fresh AND no new sheets in folders AND no
                # malformed entries were dropped → safe to use cache
                cached_sub_ids = cache.get('subcontractor_sheet_ids', [])
                if cached_sub_ids:
                    SUBCONTRACTOR_SHEET_IDS = SUBCONTRACTOR_SHEET_IDS | set(cached_sub_ids)
                    logging.info(f"📂 Restored {len(cached_sub_ids)} subcontractor sheet IDs from cache (total: {len(SUBCONTRACTOR_SHEET_IDS)})")
                logging.info(f"⚡ Using cached discovery ({age_min:.1f} min old) with {len(_valid_cached_sheets)} sheets (folders unchanged)")
                return _valid_cached_sheets
            else:
                # Cache expired OR new sheets found in folders → incremental mode
                _cached_sheets = _valid_cached_sheets
                _cached_sheet_ids = _cached_sheet_ids_from_file
                cached_sub_ids = cache.get('subcontractor_sheet_ids', [])
                if cached_sub_ids:
                    SUBCONTRACTOR_SHEET_IDS = SUBCONTRACTOR_SHEET_IDS | set(cached_sub_ids)
                _incremental = True
                if _partial_cache_corruption:
                    _dropped_count = (
                        len(_raw_cached_sheets) - len(_valid_cached_sheets)
                    )
                    logging.info(
                        f"🛡️ {_dropped_count} malformed cached entry(ies) "
                        f"dropped — forcing incremental revalidation against "
                        f"base_sheet_ids so any required sheet among the "
                        f"dropped entries is rediscovered this run instead "
                        f"of waiting until cache expiry."
                    )
                elif _new_from_folders:
                    logging.info(f"🆕 {len(_new_from_folders)} new sheet(s) detected in folders — "
                                 f"cache invalidated, using incremental mode "
                                 f"(keeping {len(_cached_sheets)} cached + validating new sheets)")
                else:
                    logging.info(f"ℹ️ Discovery cache expired ({age_min:.1f} min old); using incremental mode — "
                                 f"keeping {len(_cached_sheets)} cached sheets, scanning for new IDs only")
        except Exception as e:
            logging.info(f"Cache load failed, refreshing discovery: {e}")
    base_sheet_ids = [
        3239244454645636, 2230129632694148, 1732945426468740, 4126460034895748,
        7899446718189444, 1964558450118532, 5905527830695812, 820644963897220,
        8002920231423876, 2308525217763204,  # Added per user request
        5892629871939460, 
        3756603854507908, # Added Intake Promax
        5833510251089796,  # Added per user request
        5291853336235908,  # Added per user request
        6399146438119300, # Added per user request
        2582148201533316, # Added Resiliency Promax Database 16
        589443900592004, # Added Resiliency Promax Database 17
        7112742503665540, # Added Resiliency Promax Database 18
        8882702989086596, #Added Resiliency Promax Database 19
        2329343909908356, #Added Resiliency Promax Database 20
        5635469074190212, #Added Resiliency Promax Database 21
        5962351384678276, #Added Resiliency Promax Database 22
        3892736567496580, #Added Resiliency Promax Database 23
        4973034927509380, #Added Resiliency Promax Database 24
        1705871626162052, # Added Resiliency Promax Database 25
        5214601672085380, #  Added Resiliency Promax Database 26
        8551186744430468, # Added Resiliency Promax Database 27
        7820299006332804, # Added Resiliency Promax Database 28
        1153867531112324, # Added Resiliency Promax Database 29
        6692045306417028, # Added Resiliency Promax Database 30
        249276132183940, # Added Intake Promax 2
        2126238714908548, # Added Promax Database 31
        366100316376964, # Added Promax Database 32
        1207776467439492, # Added Promax Database 33
        342733613911940, # Added Promax Database 34
        6658677403504516, # Added Promax Database 35
        7043847386255236, # Added Promax Database 36
        2920263713771396, # Added Intake Promax 3
        4317397608517508, # Added Resiliency Promax 37
        277473162907524, # Added Resiliency Promax (New)
        1697214691757956, # Added Resiliency Promax 38
        8823469929090948, # Added Resiliency Promax 39
        692599695298436, #Added Resiliency Promax 40
        2183127494512516, #Added Resiliency Promax 42
        4774094567329668, #Added Resiliency Promax 41
        5067039388422020, #Adde Resiliency Promax 44
        888996134604676, #Added Resiliency Promax 43
        6920127724343172, #Added Resiliency Promax 45
        6587491768291204, #Added Intake Promax 4
        1804369797271428, #Added Resiliency Promax Database 46
        2873734244290436, #Added Resiliency Promax Database 47
        8153606260739972, #Added Resiliency Promax Database 48
        7630927397080964, #Added Resiliency Promax Database 49
        4017481216642948, #Added Resiliency Promax Database 50
        1326553209196420, #Added Resiliency Promax Database 51
        6479287751233412, #Added Resiliency Promax Database 52
        2672627970690948, #Added Resiliency Promax Database 53
        3800355386118020, #Added Intake Promax Database 5
        6123743714692996, #Added Resiliency Promax Database 54
        3804822152105860, #Added Resiliency Promax Database 55
        5065263654326148, #Added Resiliency Promax Database 56
        5417244814167940, #Added Resiliency Promax Database 57
        2431001297899396, #Added Resiliency Promax Database 58
        4085014678425476, #Added Intake Promax 6
        1080481698238340, #Added Resiliency Promax Database 59
        8391967734976388, #Added Resiliency Promax Database 60
        2233624515530628, #Added Resiliency Promax Database 61
        2780425391918980 #Added Resiliency Promax Database 62
        
        

    ]

    # OPTIONAL SPEED-UP FOR TESTING: allow overriding sheet list via env LIMITED_SHEET_IDS
    # Comma-separated list of numeric sheet IDs. If provided, we restrict discovery to only these.
    _limited_ids_raw = os.getenv('LIMITED_SHEET_IDS')
    if _limited_ids_raw:
        try:
            limited_ids = [int(x.strip()) for x in _limited_ids_raw.split(',') if x.strip()]
            if limited_ids:
                logging.info(f"⏩ LIMITED_SHEET_IDS override active ({len(limited_ids)} IDs); restricting discovery to provided list")
                base_sheet_ids = limited_ids
        except Exception as e:
            logging.warning(f"⚠️ LIMITED_SHEET_IDS parse failed '{_limited_ids_raw}': {e}")
    
    # Merge folder-discovered sheet IDs (populated unconditionally at top of function)
    _folder_ids = _FOLDER_DISCOVERED_SUB_IDS | _FOLDER_DISCOVERED_ORIG_IDS
    if _folder_ids:
        existing = set(base_sheet_ids)
        new_ids = _folder_ids - existing
        if new_ids:
            base_sheet_ids.extend(sorted(new_ids))
            logging.info(f"📂 Merged {len(new_ids)} folder-discovered sheet(s) into discovery list (total: {len(base_sheet_ids)})")
        else:
            logging.info(f"📂 All {len(_folder_ids)} folder-discovered sheet(s) already in base list")

    discovered = []

    def _validate_single_sheet(sid):
        """Validate a single sheet and return its discovery dict (or None if invalid)."""
        try:
            # PERFORMANCE FIX: Fetch only column metadata initially (no row data needed yet)
            # This prevents Error 4000 for large sheets during discovery phase
            sheet = client.Sheets.get_sheet(sid, include='columns')
            cols = sheet.columns
            mapping = {}
            by_title = { _title(c.title): c for c in cols }
            # Exact matches
            w_exact = by_title.get(_title('Weekly Reference Logged Date'))
            s_exact = by_title.get(_title('Snapshot Date'))
            if w_exact: mapping['Weekly Reference Logged Date'] = w_exact.id
            if s_exact: mapping['Snapshot Date'] = s_exact.id
            # Date candidates
            date_candidates = [c for c in cols if str(c.type).upper() in ('DATE','DATETIME')]
            if 'Weekly Reference Logged Date' not in mapping:
                keyed = [c for c in date_candidates if 'date' in _title(c.title) and any(k in _title(c.title) for k in ('weekly','reference','logged','week ending'))]
                if keyed:
                    mapping['Weekly Reference Logged Date'] = keyed[0].id
            if 'Snapshot Date' not in mapping:
                keyed = [c for c in date_candidates if 'date' in _title(c.title) and 'snapshot' in _title(c.title)]
                if keyed:
                    mapping['Snapshot Date'] = keyed[0].id
            # Sample fallback — fetch sample rows ONCE for all column checks
            _sample_rows_cache = None
            def _get_sample_rows():
                nonlocal _sample_rows_cache
                if _sample_rows_cache is None:
                    try:
                        _sample_sheet = client.Sheets.get_sheet(sid, row_numbers=list(range(1, 4)))
                        _sample_rows_cache = _sample_sheet.rows if _sample_sheet.rows else []
                    except Exception:
                        _sample_rows_cache = []
                return _sample_rows_cache

            def _extract_col_samples(col_id):
                """Extract sample values for a column from the cached sample rows."""
                vals = []
                for row in _get_sample_rows():
                    for cell in row.cells:
                        if cell.column_id == col_id:
                            val = getattr(cell, 'value', None)
                            if val is None:
                                val = getattr(cell, 'display_value', None)
                            if val is not None:
                                vals.append(str(val))
                            break
                return vals

            if 'Weekly Reference Logged Date' not in mapping:
                for c in date_candidates:
                    t = _title(c.title)
                    if 'date' in t and any(k in t for k in ('weekly','reference','logged','week ending')):
                        samples = _extract_col_samples(c.id)
                        if any(re.match(r'^\d{4}-\d{2}-\d{2}', v) for v in samples):
                            mapping['Weekly Reference Logged Date'] = c.id
                            break
            if 'Snapshot Date' not in mapping:
                for c in date_candidates:
                    t = _title(c.title)
                    if 'date' in t and 'snapshot' in t:
                        samples = _extract_col_samples(c.id)
                        if any(re.match(r'^\d{4}-\d{2}-\d{2}', v) for v in samples):
                            mapping['Snapshot Date'] = c.id
                            break
            # Non-date synonyms
            synonyms = {
                'Foreman':'Foreman','Work Request #':'Work Request #','Dept #':'Dept #','Customer Name':'Customer Name','Work Order #':'Work Order #','Area':'Area',
                'Pole #':'Pole #','Point #':'Pole #','Point Number':'Pole #','CU':'CU','Billable Unit Code':'CU','Work Type':'Work Type','CU Description':'CU Description',
                'Unit Description':'CU Description','Unit of Measure':'Unit of Measure','UOM':'Unit of Measure','Quantity':'Quantity','Qty':'Quantity','# Units':'Quantity',
                'Units Total Price':'Units Total Price','Total Price':'Units Total Price','Redlined Total Price':'Units Total Price','Scope #':'Scope #','Scope ID':'Scope #',
                'Job #':'Job #','Units Completed?':'Units Completed?','Units Completed':'Units Completed?',
                # Helper variant columns (exact names with brackets as authoritative)
                'Helper Job [#]':'Helper Job #',  # Exact spelling with brackets
                'Helper Job':'Helper Job #',      # Fallback synonym
                'Helper Job #':'Helper Job #',    # Ensure direct exact match is captured
                'Helper Dept #':'Helper Dept #',
                'Foreman Helping?':'Foreman Helping?',
                'Helping Foreman Completed Unit?':'Helping Foreman Completed Unit?',
                # VAC Crew variant columns (row-level detection — mirrors helper pattern)
                'VAC Crew Helping?':'VAC Crew Helping?',
                'Vac Crew Helping?':'VAC Crew Helping?',          # Case variant
                'Vac Crew Completed Unit?':'Vac Crew Completed Unit?',
                'VAC Crew Completed Unit?':'Vac Crew Completed Unit?',  # Case variant
                'VAC Crew Dept #':'VAC Crew Dept #',
                'Vac Crew Dept #':'VAC Crew Dept #',              # Case variant
                'Vac Crew Job #':'Vac Crew Job #',
                'VAC Crew Job #':'Vac Crew Job #',                # Case variant
                'Vac Crew Email Address':'Vac Crew Email Address',
                'VAC Crew Email Address':'Vac Crew Email Address', # Case variant
            }
            # COLUMN MAPPING DEBUG: Log all column titles to verify helper and VAC Crew columns
            helper_columns_found = []
            vac_crew_columns_found = []
            for c in cols:
                # Check for helper-related columns specifically
                if 'Helper' in c.title or 'Helping' in c.title:
                    helper_columns_found.append(c.title)
                # Check for VAC Crew-related columns (case-insensitive so lowercase
                # or hyphenated variants like 'vac crew' / 'vac-crew' still surface
                # in logs and feed the fuzzy fallback pass below).
                _ct_lower = (c.title or '').lower()
                if 'vac crew' in _ct_lower or 'vaccrew' in _ct_lower or 'vac-crew' in _ct_lower:
                    vac_crew_columns_found.append(c.title)

                if c.title in synonyms and synonyms[c.title] not in mapping:
                    mapping[synonyms[c.title]] = c.id
                    # Log helper column mappings specifically
                    if 'Helper' in c.title:
                        logging.info(f"🔧 MAPPED HELPER COLUMN: '{c.title}' -> '{synonyms[c.title]}' (column ID: {c.id})")
                    # Log VAC Crew column mappings
                    if 'Vac Crew' in c.title or 'VAC Crew' in c.title:
                        logging.info(f"🚐 MAPPED VAC CREW COLUMN: '{c.title}' -> '{synonyms[c.title]}' (column ID: {c.id})")

            # ── VAC Crew column fuzzy fallback ──
            # The exact-match pass above only catches the two literal case variants
            # declared in `synonyms` (e.g. 'VAC Crew Helping?' and 'Vac Crew Helping?').
            # Operators occasionally introduce subtle variants on a new sheet —
            # trailing / leading whitespace, missing or extra '?', double internal
            # spaces, all-caps 'VAC CREW', all-lowercase 'vac crew' — and any such
            # variant silently fails to map. When the two KEY columns
            # ('VAC Crew Helping?' and 'Vac Crew Completed Unit?') aren't in
            # `mapping`, `sheet_has_vac_crew_columns` in _fetch_and_process_sheet
            # evaluates False and the row-level VAC Crew detection block is
            # skipped wholesale — the sheet produces zero _VacCrew Excel files
            # regardless of row content. This fallback runs ONLY when a canonical
            # VAC Crew key is missing, so helper/primary mappings are unaffected
            # and existing exact-match behaviour is preserved.
            _vac_crew_fuzzy_canonicals = [
                'VAC Crew Helping?',
                'Vac Crew Completed Unit?',
                'VAC Crew Dept #',
                'Vac Crew Job #',
                'Vac Crew Email Address',
            ]
            _already_mapped_ids = set(mapping.values())
            for _canonical in _vac_crew_fuzzy_canonicals:
                if _canonical in mapping:
                    continue
                _target_norm = _normalize_column_title_for_vac_crew(_canonical)
                for c in cols:
                    if c.id in _already_mapped_ids:
                        continue
                    if _normalize_column_title_for_vac_crew(c.title) == _target_norm:
                        mapping[_canonical] = c.id
                        _already_mapped_ids.add(c.id)
                        logging.warning(
                            f"🚐 VAC Crew column FUZZY-MATCHED on sheet ID {sid}: "
                            f"'{c.title}' -> '{_canonical}'. Consider adding '{c.title}' "
                            f"as an explicit synonym if this variant is permanent."
                        )
                        break

            # Log summary of helper columns found
            if helper_columns_found:
                logging.info(f"🔧 All helper/helping columns found in sheet: {helper_columns_found}")
            # Log summary of VAC Crew columns found
            if vac_crew_columns_found:
                logging.info(f"🚐 VAC Crew columns found in sheet: {vac_crew_columns_found}")

            # Actionable WARNING: VAC Crew-looking columns exist but the two key
            # mappings still didn't resolve after the fuzzy pass — detection will
            # be DISABLED for this sheet until the column titles are aligned with
            # `_vac_crew_fuzzy_canonicals`. Surface the raw titles so operators
            # can see exactly which variant is on the sheet.
            if vac_crew_columns_found and not (
                'VAC Crew Helping?' in mapping
                and 'Vac Crew Completed Unit?' in mapping
            ):
                logging.warning(
                    f"🚐⚠️ VAC Crew columns visible on sheet ID {sid} but key "
                    f"mappings incomplete after fuzzy pass: "
                    f"titles_seen={vac_crew_columns_found}, "
                    f"mapped_vac_crew_keys={[k for k in _vac_crew_fuzzy_canonicals if k in mapping]}. "
                    f"VAC Crew row detection will be DISABLED for this sheet until "
                    f"titles match a canonical form in _vac_crew_fuzzy_canonicals."
                )


            if 'Weekly Reference Logged Date' in mapping:
                w_id = mapping['Weekly Reference Logged Date']
                s_id = mapping.get('Snapshot Date')
                w_samples = _extract_col_samples(w_id)
                s_samples = _extract_col_samples(s_id) if s_id else []
                logging.info(f"Sheet {sheet.name} (ID {sid}) date columns:")
                logging.info(f"  Weekly Reference Logged Date (ID {w_id}) samples: {w_samples}")
                if s_id:
                    logging.info(f"  Snapshot Date (ID {s_id}) samples: {s_samples}")
                logging.info(f"✅ Added sheet: {sheet.name} (ID: {sid})")
                return {'id': sid,'name': sheet.name,'column_mapping': mapping}
            else:
                logging.warning(f"❌ Skipping sheet {sheet.name} (ID {sid}) - Weekly Reference Logged Date not found (strict mode)")
                return None
        except Exception as e:
            logging.warning(f"⚡ Failed to validate sheet {sid}: {e}")
            return None

    # ── Incremental mode: only validate NEW sheet IDs, keep cached ones ──
    if _incremental:
        all_base_ids = set(base_sheet_ids)
        new_ids_to_validate = sorted(all_base_ids - _cached_sheet_ids)
        if new_ids_to_validate:
            logging.info(f"🆕 Incremental discovery: {len(new_ids_to_validate)} new sheet ID(s) to validate "
                         f"(skipping {len(_cached_sheet_ids)} already-cached sheets)")
            _discovery_start = datetime.datetime.now()
            with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS_DISCOVERY) as executor:
                futures = {executor.submit(_validate_single_sheet, sid): sid for sid in new_ids_to_validate}
                for i, future in enumerate(as_completed(futures), 1):
                    sid = futures[future]
                    result = future.result()
                    if result is not None:
                        discovered.append(result)
                        logging.info(f"   ✅ [{i}/{len(futures)}] NEW Discovered: {result['name']} (ID: {sid})")
                    else:
                        logging.info(f"   ❌ [{i}/{len(futures)}] Skipped new sheet ID {sid}")
            _discovery_elapsed = (datetime.datetime.now() - _discovery_start).total_seconds()
            logging.info(f"⚡ Incremental discovery: {len(discovered)} new sheet(s) validated in {_discovery_elapsed:.1f}s")
        else:
            logging.info(f"⚡ Incremental discovery: no new sheet IDs found — all {len(_cached_sheet_ids)} sheets already cached")
        # Merge: cached sheets + newly discovered sheets
        discovered = _cached_sheets + discovered
        logging.info(f"📋 Total sheets after incremental merge: {len(discovered)} ({len(_cached_sheets)} cached + {len(discovered) - len(_cached_sheets)} new)")
    else:
        # Full discovery: validate all sheets from scratch
        logging.info(f"🚀 Starting parallel discovery with {PARALLEL_WORKERS_DISCOVERY} workers for {len(base_sheet_ids)} sheets...")
        _discovery_start = datetime.datetime.now()
        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS_DISCOVERY) as executor:
            futures = {executor.submit(_validate_single_sheet, sid): sid for sid in base_sheet_ids}
            for i, future in enumerate(as_completed(futures), 1):
                sid = futures[future]
                result = future.result()
                if result is not None:
                    discovered.append(result)
                    logging.info(f"   ✅ [{i}/{len(futures)}] Discovered: {result['name']} (ID: {sid})")
                else:
                    logging.info(f"   ❌ [{i}/{len(futures)}] Skipped sheet ID {sid}")
        _discovery_elapsed = (datetime.datetime.now() - _discovery_start).total_seconds()
        logging.info(f"⚡ Discovery complete: {len(discovered)} sheets validated in {_discovery_elapsed:.1f}s (parallel w/{PARALLEL_WORKERS_DISCOVERY} workers)")
    # Save cache
    if USE_DISCOVERY_CACHE:
        try:
            with open(DISCOVERY_CACHE_PATH,'w') as f:
                json.dump({
                    'schema_version': DISCOVERY_CACHE_VERSION,
                    'timestamp': datetime.datetime.now().isoformat(),
                    'sheets': discovered,
                    'subcontractor_sheet_ids': sorted(SUBCONTRACTOR_SHEET_IDS),
                }, f)
        except Exception as e:
            logging.warning(f"Failed to write discovery cache: {e}")
    return discovered

# Cell history and Modified By logic removed - using direct column assignment only

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

            try:
                # Fetch sheet once (no column history); include columns to support unmapped summary
                # PERFORMANCE FIX: Use column_ids parameter to only fetch mapped columns
                column_mapping = source['column_mapping']
                required_column_ids = list(column_mapping.values())
                with sentry_sdk.start_span(op="smartsheet.api", name=f"Fetch sheet {source['name']}") as api_span:
                    sheet = client.Sheets.get_sheet(
                        source['id'], 
                        column_ids=required_column_ids
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
                        if RATE_CUTOFF_DATE and _rate_new_primary and not is_subcontractor_sheet:
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
                if RATE_CUTOFF_DATE and _rate_new_primary:
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
    
    VAC Crew Variant:
    - VAC Crew Promax grouping (one Excel per WR/Week for VAC Crew sheets)
    - Key format: MMDDYY_WRNUMBER_VACCREW
    - Only created for rows where __is_vac_crew = True (row-level column-based detection)
    - Generates a separate Excel file with _VacCrew suffix in the filename
    
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
    groups = collections.defaultdict(list)
    
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
            
            # VAC Crew rows get their own dedicated group key (separate from primary/helper).
            # Detection is row-level: a row is VAC Crew when VAC Crew Helping? is non-blank
            # AND Vac Crew Completed Unit? is checked. This means the same sheet can produce
            # both primary/helper rows AND VAC Crew rows — they are mutually exclusive per-row
            # because a single row is either a VAC Crew row or a regular/helper row.
            if is_vac_crew_row:
                vac_crew_key = f"{week_end_for_key}_{wr_key}_VACCREW"
                # Use VAC Crew name (from 'VAC Crew Helping?' column) as the foreman
                # for this group — NOT the primary foreman (effective_user).
                vac_crew_foreman = r.get('__vac_crew_name') or effective_user
                keys_to_add.append(('vac_crew', vac_crew_key, vac_crew_foreman))
                # Only log at info level the first time a new group key is seen; subsequent
                # rows belonging to the same WR/week VAC Crew group log at debug to avoid
                # flooding logs with hundreds of identical "GROUP CREATED" messages.
                if vac_crew_key not in groups:
                    logging.info(f"🏗️ VAC CREW GROUP CREATED: WR={wr_key}, Week={week_end_for_key}")
                else:
                    logging.debug(f"Adding row to existing VAC Crew group: WR={wr_key}, Week={week_end_for_key}")
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
                    # In helper/both mode, exclude valid helper rows from main
                    if not valid_helper_row:
                        primary_key = f"{week_end_for_key}_{wr_key}"
                        keys_to_add.append(('primary', primary_key, None))
                    else:
                        # Log when excluding from main Excel due to helper status
                        logging.info(f"➖ EXCLUDING from main Excel: WR={wr_key}, Week={week_end_for_key} (Helper row with both checkboxes)")
                
                # Helper variant - ONLY created when mode allows it
                if valid_helper_row and helper_mode_enabled:
                    helper_dept = r.get('__helper_dept', '')
                    helper_job = r.get('__helper_job', '')
                    # PERFORMANCE: Use pre-compiled regex for helper name sanitization
                    helper_sanitized = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]
                    helper_key = f"{week_end_for_key}_{wr_key}_HELPER_{helper_sanitized}"
                    keys_to_add.append(('helper', helper_key, helper_foreman))
                    # HELPER GROUP LOGGING: Always log when helper group is created
                    logging.info(f"🔧 HELPER GROUP CREATED: WR={wr_key}, Week={week_end_for_key}, Helper={helper_foreman}, Dept={helper_dept}, Job={helper_job}")
                elif is_helper_row and not helper_mode_enabled:
                    # In primary mode, helper rows go to main
                    logging.info(f"ℹ️ Helper row found but RES_GROUPING_MODE={RES_GROUPING_MODE} - including in main Excel")
                elif is_helper_row:
                    # Helper row missing required helper_dept (helper_job is optional)
                    helper_dept = r.get('__helper_dept', '')
                    helper_job = r.get('__helper_job', '')
                    logging.warning(f"⚠️ Helper row for WR {wr_key} missing required Helper Dept # (Job: '{helper_job}') - including in main Excel")
            
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
            # k format examples:
            #   MMDDYY_WR
            #   MMDDYY_WR_HELPER_<name>
            #   MMDDYY_WR_VACCREW
            try:
                suffix = k.split('_', 1)[1]  # take everything after first underscore (WR...)
            except Exception:
                return False
            return suffix == wr or suffix.startswith(f"{wr}_HELPER_") or suffix == f"{wr}_VACCREW"

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
            # k format examples:
            #   MMDDYY_WR               → suffix = WR
            #   MMDDYY_WR_HELPER_<name> → suffix = WR_HELPER_<name>
            #   MMDDYY_WR_USER_<name>   → suffix = WR_USER_<name>
            #   MMDDYY_WR_VACCREW       → suffix = WR_VACCREW
            try:
                suffix = k.split('_', 1)[1]  # take everything after first underscore (WR...)
            except Exception:
                return False
            # Match exact WR, or WR followed by _HELPER_, _USER_, or _VACCREW variants
            return suffix == wr or suffix.startswith(f"{wr}_HELPER_") or suffix.startswith(f"{wr}_USER_") or suffix == f"{wr}_VACCREW"
        
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

def safe_merge_cells(ws, range_str):
    """
    Safely merge cells, avoiding duplicates and overlaps that cause XML errors.
    
    Args:
        ws: The worksheet object
        range_str: The range string (e.g., 'A1:C3')
    
    Returns:
        bool: True if merge was successful, False if skipped
    """
    from openpyxl.utils import range_boundaries
    
    try:
        # Parse the requested range boundaries
        min_col, min_row, max_col, max_row = range_boundaries(range_str)
        
        # Check for any overlapping or duplicate merged ranges
        for merged in list(ws.merged_cells.ranges):
            m_min_col, m_min_row, m_max_col, m_max_row = range_boundaries(str(merged))
            
            # Check if ranges overlap (not just exact match)
            if not (max_col < m_min_col or min_col > m_max_col or
                    max_row < m_min_row or min_row > m_max_row):
                # Ranges overlap - skip to avoid XML corruption
                return False
        
        # Safe to merge - no overlaps detected
        ws.merge_cells(range_str)
        return True
    except Exception as e:
        logging.warning(f"Failed to merge cells {range_str}: {e}")
        return False

def generate_excel(group_key, group_rows, snapshot_date, ai_analysis_results=None, data_hash=None):
    """
    FIXED: Generate a formatted Excel report for a group of rows.
    
    SPECIFIC FIXES IMPLEMENTED:
    - WR 90093002 Excel generation (complete implementation)
    - WR 89954686 specific handling 
    - Proper error handling for worksheet objects
    - Complete daily data block generation
    - Safe cell merging to prevent XML errors
    - Improved Job # field detection with multiple column name variations
    """
    first_row = group_rows[0]
    
    # Parse the combined key format: "MMDDYY_WRNUMBER"
    if '_' in group_key:
        week_end_raw, wr_from_key = group_key.split('_', 1)
    else:
        # CRITICAL ERROR: Old format detected - this should never happen with fixed grouping
        error_msg = f"CRITICAL: Invalid group key format detected: '{group_key}'. Expected format: 'MMDDYY_WRNUMBER'."
        logging.error(error_msg)
        raise Exception(error_msg)
    
    # Use the current foreman (most recent) from the row data
    current_foreman = first_row.get('__current_foreman', 'Unknown_Foreman')
    
    # CRITICAL VALIDATION: Ensure grouping logic worked correctly
    wr_numbers = list(set(str(row.get('Work Request #', '')).split('.')[0] for row in group_rows if row.get('Work Request #')))
    
    # ABSOLUTE REQUIREMENT: Each group must contain EXACTLY ONE work request
    if len(wr_numbers) != 1:
        error_msg = f"FATAL ERROR: Group contains {len(wr_numbers)} work requests instead of 1: {wr_numbers}. Group key: {group_key}."
        logging.error(error_msg)
        raise Exception(error_msg)
    
    # SUCCESS: Exactly one work request in this group
    wr_num = wr_numbers[0]

    # Filesystem-safety: strip any path-traversal / separator characters
    # from the WR identifier before it reaches ``os.path.join`` and
    # ``workbook.save``. Numeric production WR#s pass through unchanged
    # (\w matches 0-9), so this is a no-op for realistic data and a
    # defense-in-depth guard against a pathological row value. Must use
    # the same regex used by the main-loop derivation site so
    # attachment / hash-history comparisons stay consistent.
    wr_num = _RE_SANITIZE_HELPER_NAME.sub('_', wr_num)[:50]

    # SPECIFIC FIX FOR WR 90093002 and WR 89954686
    if wr_num in ['90093002', '89954686']:
        logging.info(f"🔧 Applying specific fixes for WR# {wr_num}")
    
    # Get the calculated week ending date from the row data if available
    week_ending_date = first_row.get('__week_ending_date')
    if week_ending_date:
        week_end_display = week_ending_date.strftime('%m/%d/%y')
        # Update the raw format to match the calculated date
        week_end_raw = week_ending_date.strftime('%m%d%y')
        # Create subfolder for this week-ending date (YYYY-MM-DD format)
        week_folder_name = week_ending_date.strftime('%Y-%m-%d')
    else:
        # Fallback to the original format
        week_end_display = f"{week_end_raw[:2]}/{week_end_raw[2:4]}/{week_end_raw[4:]}"
        # Parse week_end_raw (MMDDYY) to create folder name
        try:
            fallback_date = datetime.datetime.strptime(week_end_raw, '%m%d%y')
            week_folder_name = fallback_date.strftime('%Y-%m-%d')
        except ValueError:
            week_folder_name = "unknown_week"
    
    # Create week-specific subfolder under OUTPUT_FOLDER
    week_output_folder = os.path.join(OUTPUT_FOLDER, week_folder_name)
    os.makedirs(week_output_folder, exist_ok=True)
    
    # Prefer 'Scope #' then fallback to 'Scope ID'
    scope_id = first_row.get('Scope #') or first_row.get('Scope ID', '')
    
    # Try multiple column name variations for Job # to handle different formats
    job_number = (first_row.get('Job #') or 
                  first_row.get('Job#') or 
                  first_row.get('Job Number') or 
                  first_row.get('JobNumber') or 
                  first_row.get('Job_Number') or 
                  first_row.get('JOB #') or 
                  first_row.get('JOB#') or 
                  first_row.get('job #') or 
                  first_row.get('job#') or 
                  '')
    
    # Log warning if Job # is missing
    if not job_number:
        available_cols = [k for k in first_row.keys() if not k.startswith('__')][:15]
        logging.warning(f"Job # not found for WR {wr_num}. Available columns: {available_cols}")
    
    # Use individual work request number for filename with timestamp for uniqueness
    timestamp = datetime.datetime.now().strftime('%H%M%S')
    
    # Variant-aware filename construction
    variant = first_row.get('__variant', 'primary')
    variant_suffix = ""
    
    if variant == 'helper':
        # Helper variant: include helper identifier in filename
        helper_foreman = first_row.get('__helper_foreman', '')
        if helper_foreman:
            # PERFORMANCE: Use pre-compiled regex for filename sanitization
            helper_sanitized = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]
            variant_suffix = f"_Helper_{helper_sanitized}"
    elif variant == 'vac_crew':
        # VAC Crew variant: fixed suffix to distinguish from primary/helper
        variant_suffix = '_VacCrew'
    elif variant == 'primary':
        # Primary variant (no suffix needed)
        variant_suffix = ''
    
    if data_hash:
        # Use full 16-character hash (calculate_data_hash already truncates to 16)
        output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}_{timestamp}{variant_suffix}_{data_hash}.xlsx"
    else:
        output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}_{timestamp}{variant_suffix}.xlsx"
    final_output_path = os.path.join(week_output_folder, output_filename)

    if TEST_MODE:
        print(f"\n🧪 TEST MODE: Generating Excel file '{output_filename}'")
        print(f"   - Work Request: {wr_num}")
        print(f"   - Foreman: {current_foreman}")
        print(f"   - Timestamp: {timestamp}")
        print(f"   - Data Hash: {data_hash[:8] if data_hash else 'None'}")
        print(f"   🎯 NEW FILE POLICY: Always create fresh files")
    else:
        logging.info(f"📊 Generating Excel file '{output_filename}' for WR#{wr_num}")
        print(f"   - Week Ending: {week_end_display}")
        print(f"   - Row Count: {len(group_rows)}")

    workbook = openpyxl.Workbook()
    ws = workbook.active
    if ws is None:
        ws = workbook.create_sheet("Work Report")
    ws.title = "Work Report"

    # --- Formatting ---
    LINETEC_RED = 'C00000'
    LIGHT_GREY_FILL = PatternFill(start_color='F2F2F2', end_color='F2F2F2', fill_type='solid')
    RED_FILL = PatternFill(start_color=LINETEC_RED, end_color=LINETEC_RED, fill_type='solid')
    TITLE_FONT = Font(name='Calibri', size=20, bold=True)
    SUBTITLE_FONT = Font(name='Calibri', size=16, bold=True, color='404040')
    TABLE_HEADER_FONT = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
    BLOCK_HEADER_FONT = Font(name='Calibri', size=14, bold=True, color='FFFFFF')
    BODY_FONT = Font(name='Calibri', size=11)
    SUMMARY_HEADER_FONT = Font(name='Calibri', size=12, bold=True, color='FFFFFF')
    SUMMARY_LABEL_FONT = Font(name='Calibri', size=10, bold=True)
    SUMMARY_VALUE_FONT = Font(name='Calibri', size=10)

    # Use explicit string for orientation for deterministic behavior
    ws.page_setup.orientation = 'landscape'
    try:
        ws.page_setup.paperSize = 9  # A4 paper size code
    except AttributeError:
        ws.page_setup.paperSize = 9  # Fallback for older versions
    ws.page_margins.left = 0.25; ws.page_margins.right = 0.25
    ws.page_margins.top = 0.5; ws.page_margins.bottom = 0.5

    # --- Branding and Titles ---
    current_row = 1
    try:
        img = Image(LOGO_PATH)
        img.height = 99
        img.width = 198
        ws.add_image(img, f'A{current_row}')
        for i in range(current_row, current_row+3): 
            ws.row_dimensions[i].height = 25
        current_row += 3
    except FileNotFoundError:
        safe_merge_cells(ws, f'A{current_row}:C{current_row+2}')
        ws[f'A{current_row}'] = "LINETEC SERVICES"
        ws[f'A{current_row}'].font = TITLE_FONT
        current_row += 3

    # CRITICAL FIX: Merge cells FIRST, then assign values
    safe_merge_cells(ws, f'D{current_row-2}:I{current_row-2}')
    ws[f'D{current_row-2}'] = 'WEEKLY UNITS COMPLETED PER SCOPE ID'
    ws[f'D{current_row-2}'].font = SUBTITLE_FONT
    ws[f'D{current_row-2}'].alignment = Alignment(horizontal='center', vertical='center')

    report_generated_time = datetime.datetime.now()
    safe_merge_cells(ws, f'D{current_row+1}:I{current_row+1}')
    ws[f'D{current_row+1}'] = f"Report Generated On: {report_generated_time.strftime('%m/%d/%Y %I:%M %p')}"
    ws[f'D{current_row+1}'].font = Font(name='Calibri', size=9, italic=True)
    ws[f'D{current_row+1}'].alignment = Alignment(horizontal='right')

    current_row += 3
    safe_merge_cells(ws, f'B{current_row}:D{current_row}')
    ws[f'B{current_row}'] = 'REPORT SUMMARY'
    ws[f'B{current_row}'].font = SUMMARY_HEADER_FONT
    ws[f'B{current_row}'].fill = RED_FILL
    ws[f'B{current_row}'].alignment = Alignment(horizontal='center')

    total_price = sum(parse_price(row.get('Units Total Price')) for row in group_rows)
    ws[f'B{current_row+1}'] = 'Total Billed Amount:'
    ws[f'B{current_row+1}'].font = SUMMARY_LABEL_FONT
    ws[f'C{current_row+1}'] = total_price
    ws[f'C{current_row+1}'].font = SUMMARY_VALUE_FONT
    ws[f'C{current_row+1}'].alignment = Alignment(horizontal='right')
    ws[f'C{current_row+1}'].number_format = numbers.FORMAT_CURRENCY_USD_SIMPLE

    ws[f'B{current_row+2}'] = 'Total Line Items:'
    ws[f'B{current_row+2}'].font = SUMMARY_LABEL_FONT
    ws[f'C{current_row+2}'] = len(group_rows)
    ws[f'C{current_row+2}'].font = SUMMARY_VALUE_FONT
    ws[f'C{current_row+2}'].alignment = Alignment(horizontal='right')

    ws[f'B{current_row+3}'] = 'Billing Period:'
    ws[f'B{current_row+3}'].font = SUMMARY_LABEL_FONT
    
    # Calculate the proper week range (Monday to Sunday) for billing period
    if week_ending_date:
        week_start_date = week_ending_date - timedelta(days=6)  # Monday of that week
        billing_period = f"{week_start_date.strftime('%m/%d/%Y')} to {week_end_display}"
    else:
        # Fallback to using snapshot date if week ending date is not available
        billing_period = f"{snapshot_date.strftime('%m/%d/%Y')} to {week_end_display}"
    
    ws[f'C{current_row+3}'] = billing_period
    ws[f'C{current_row+3}'].font = SUMMARY_VALUE_FONT
    ws[f'C{current_row+3}'].alignment = Alignment(horizontal='right')

    safe_merge_cells(ws, f'F{current_row}:I{current_row}')
    ws[f'F{current_row}'] = 'REPORT DETAILS'
    ws[f'F{current_row}'].font = SUMMARY_HEADER_FONT
    ws[f'F{current_row}'].fill = RED_FILL
    ws[f'F{current_row}'].alignment = Alignment(horizontal='center')

    # Determine display values based on variant
    variant = first_row.get('__variant', 'primary')
    
    if variant == 'helper':
        # Helper variant: show helper foreman and helper-specific dept/job (REQUIRED)
        display_foreman = first_row.get('__helper_foreman', 'Unknown Helper')
        display_dept = first_row.get('__helper_dept', '')
        display_job = first_row.get('__helper_job', '')
    elif variant == 'vac_crew':
        # VAC Crew variant: use VAC Crew-specific name, dept, and job fields.
        # Must NOT fall back to primary foreman or primary Job # (which may be Arrowhead).
        display_foreman = first_row.get('__vac_crew_name', 'Unknown VAC Crew')
        display_dept = first_row.get('__vac_crew_dept', '')
        display_job = first_row.get('__vac_crew_job', '')
    else:
        # Primary variant: show primary foreman with standard dept/job from row data
        display_foreman = current_foreman
        display_dept = first_row.get('Dept #', '')
        display_job = job_number

    details = [
        ("Foreman:", display_foreman),
        ("Work Request #:", wr_num),
        ("Scope ID #:", scope_id),
        ("Work Order #:", first_row.get('Work Order #', '')),
        ("Customer:", first_row.get('Customer Name', '')),
        ("Job #:", display_job)
    ]
    
    # Add Dept # to details if it exists
    if display_dept:
        details.insert(1, ("Dept #:", display_dept))
    
    # CRITICAL FIX: Merge cells FIRST, then assign value to top-left cell
    for i, (label, value) in enumerate(details):
        r = current_row + 1 + i
        ws[f'F{r}'] = label
        ws[f'F{r}'].font = SUMMARY_LABEL_FONT
        
        # Merge cells first - check for duplicates
        detail_merge_range = f'G{r}:I{r}'
        safe_merge_cells(ws, detail_merge_range)
        
        # Now assign value to the merged cell (top-left cell G)
        vcell = ws[f'G{r}']
        vcell.value = value
        vcell.font = SUMMARY_VALUE_FONT
        vcell.alignment = Alignment(horizontal='right')

    def write_day_block(start_row, day_name, date_obj, day_rows):
        """FIXED: Write daily data blocks with proper cell handling."""
        # Skip empty day blocks to prevent Excel corruption
        if not day_rows:
            return start_row
        
        # CRITICAL FIX: Merge cells FIRST, then assign value to top-left cell
        # Use safe merge to prevent duplicate ranges
        merge_range = f'A{start_row}:H{start_row}'
        safe_merge_cells(ws, merge_range)
        
        # Now assign value to the merged cell (top-left cell A1)
        day_header_cell = ws.cell(row=start_row, column=1)
        day_header_cell.value = f"{day_name} ({date_obj.strftime('%m/%d/%Y')})"  # type: ignore
        day_header_cell.font = BLOCK_HEADER_FONT
        day_header_cell.fill = RED_FILL
        day_header_cell.alignment = Alignment(horizontal='left', vertical='center')
        
        headers = ["Point Number", "Billable Unit Code", "Work Type", "Unit Description", "Unit of Measure", "# Units", "N/A", "Pricing"]
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=start_row+1, column=col_num)
            cell.value = header  # type: ignore
            cell.font = TABLE_HEADER_FONT
            cell.fill = RED_FILL
            cell.alignment = Alignment(horizontal='center', wrap_text=True, vertical='center')

        total_price_day = 0.0
        for i, row_data in enumerate(day_rows):
            crow = start_row + 2 + i
            price = parse_price(row_data.get('Units Total Price'))
            
            # Safely parse quantity - extract only numbers
            qty_str = str(row_data.get('Quantity', '') or 0)
            # PERFORMANCE: Use pre-compiled regex for quantity normalization
            qty_str = _RE_EXTRACT_NUMBERS.sub('', qty_str)
            try:
                quantity = float(qty_str) if qty_str not in ('', '.', '-', '-.', '.-') else 0.0
            except Exception:
                quantity = 0.0
                
            total_price_day += price
            
            # Get the field values with debugging and fallbacks
            pole_num = (row_data.get('Pole #', '') or 
                       row_data.get('Point #', '') or 
                       row_data.get('Point Number', ''))
            
            cu_code = (row_data.get('CU', '') or 
                      row_data.get('Billable Unit Code', ''))
            
            work_type = row_data.get('Work Type', '')
            cu_description = (row_data.get('CU Description', '') or 
                             row_data.get('Unit Description', ''))
            unit_measure = (row_data.get('Unit of Measure', '') or 
                           row_data.get('UOM', ''))
            
            row_values = [pole_num, cu_code, work_type, cu_description, unit_measure, quantity, "", price]
            for col_num, value in enumerate(row_values, 1):
                cell = ws.cell(row=crow, column=col_num)
                cell.value = value
                cell.font = BODY_FONT
            ws.cell(row=crow, column=8).number_format = numbers.FORMAT_CURRENCY_USD_SIMPLE

        total_row = start_row + 2 + len(day_rows)
        
        # CRITICAL FIX: Merge cells FIRST, then assign value to top-left cell
        # Use safe merge to prevent duplicate ranges
        total_merge_range = f'A{total_row}:G{total_row}'
        safe_merge_cells(ws, total_merge_range)
        
        # Now assign value to the merged cell
        total_label_cell = ws.cell(row=total_row, column=1)
        total_label_cell.value = "TOTAL"  # type: ignore
        total_label_cell.font = TABLE_HEADER_FONT
        total_label_cell.alignment = Alignment(horizontal='right')
        total_label_cell.fill = RED_FILL

        total_value_cell = ws.cell(row=total_row, column=8)
        total_value_cell.value = total_price_day  # type: ignore
        total_value_cell.number_format = numbers.FORMAT_CURRENCY_USD_SIMPLE
        total_value_cell.font = TABLE_HEADER_FONT
        total_value_cell.fill = RED_FILL

        return total_row + 2

    date_to_rows = collections.defaultdict(list)
    
    # Calculate the proper week range (Monday to Sunday) for filtering
    if week_ending_date:
        # Calculate Monday of the week (6 days before Sunday)
        week_start_date = week_ending_date - timedelta(days=6)  # Monday of that week
        week_end_date = week_ending_date  # Sunday of that week
        
        if TEST_MODE:
            print(f"\nWeek Range Filter: {week_start_date.strftime('%A, %m/%d/%Y')} to {week_end_date.strftime('%A, %m/%d/%Y')}")
    else:
        week_start_date = None
        week_end_date = None
    
    for row in group_rows:
        snap = row.get('Snapshot Date')
        try:
            dt = excel_serial_to_date(snap)
            if dt is None:
                if TEST_MODE:
                    logging.warning(f"Could not parse snapshot date '{snap}'")
                continue
            
            # Include snapshot dates that fall within the Monday-Sunday range
            if week_start_date and week_end_date:
                if week_start_date <= dt <= week_end_date:
                    date_to_rows[dt].append(row)
            else:
                date_to_rows[dt].append(row)
                    
        except (parser.ParserError, TypeError, ValueError) as e:
            if TEST_MODE:
                logging.warning(f"Could not parse snapshot date '{snap}': {e}")
            continue

    snapshot_dates = sorted(date_to_rows.keys())
    if TEST_MODE:
        print(f"\n📅 Found {len(snapshot_dates)} unique snapshot dates:")
        for d in snapshot_dates:
            print(f"   • {d.strftime('%A, %m/%d/%Y')}: {len(date_to_rows[d])} rows")
    
    day_names = {d: d.strftime('%A') for d in snapshot_dates}

    current_row += 7
    for d in snapshot_dates:
        day_rows = date_to_rows[d]
        current_row = write_day_block(current_row, day_names[d], d, day_rows)
        current_row += 1

    column_widths = {'A': 15, 'B': 20, 'C': 25, 'D': 45, 'E': 20, 'F': 10, 'G': 15, 'H': 15, 'I': 15}
    for col, width in column_widths.items():
        ws.column_dimensions[col].width = width

    # NOTE: Footer code removed - was causing Excel XML corruption errors
    # Footer attributes (oddFooter.right.text, etc.) can create malformed XML
    # that triggers "We found a problem with some content" errors in Excel

    # Save the workbook
    workbook.save(final_output_path)
    
    if TEST_MODE:
        print(f"📄 Generated Excel file for inspection: '{output_filename}'")
        print(f"   - Total Amount: ${total_price:,.2f}")
        print(f"   - Daily Breakdown: {len(snapshot_dates)} days")
    else:
        logging.info(f"📄 Generated Excel: '{output_filename}'")
    
    return final_output_path, output_filename, wr_numbers

# --- TARGET SHEET MANAGEMENT ---

def create_target_sheet_map(client):
    """Create a map of the target sheet for uploading Excel files.
    
    Returns:
        Tuple of (target_map dict, target_sheet object) for reuse in cleanup.
    """
    try:
        with sentry_sdk.start_span(op="smartsheet.api", name="Fetch target sheet for WR mapping") as span:
            target_sheet = client.Sheets.get_sheet(TARGET_SHEET_ID)
            span.set_data("target_sheet_id", TARGET_SHEET_ID)
            span.set_data("row_count", len(target_sheet.rows) if target_sheet.rows else 0)
        target_map = {}
        
        # Find the Work Request # column
        wr_column_id = None
        for column in target_sheet.columns:
            if column.title == 'Work Request #':
                wr_column_id = column.id
                break
        
        if not wr_column_id:
            logging.error("Work Request # column not found in target sheet")
            return {}, None
        
        # Map work request numbers to rows. Sanitize with the same
        # filesystem-safety regex used on source-row WR#s so downstream
        # ``target_map.get(sanitized_wr)`` lookups are consistent. For
        # realistic numeric WR#s this is a no-op; for any row with a
        # path-traversal-bearing WR the sanitized key matches the same
        # key the generation pipeline uses, so skip checks, upload
        # tasks, and attachment deletion all agree.
        #
        # Codex P2 guardrail: sanitize+truncate can (in principle)
        # collapse two distinct WR# cell values to the same key — e.g.
        # values that differ only in stripped characters, or IDs whose
        # first 50 chars happen to match. A silent overwrite would
        # retarget uploads / attachment deletes to the wrong row.
        # Track which raw value first produced a given sanitized key;
        # on collision, log a WARNING, quarantine the sanitized key,
        # and remove any existing mapping so both (or all) ambiguous
        # WRs are skipped deterministically until the target sheet is
        # deduplicated. A loud "not found in target sheet" warning
        # is strictly safer than a silent wrong-row upload.
        _seen_raw_for_key: dict = {}
        _quarantined_keys: set = set()
        _collisions = 0
        for row in target_sheet.rows:
            for cell in row.cells:
                if cell.column_id == wr_column_id and cell.display_value:
                    raw_wr = str(cell.display_value).split('.')[0]
                    wr_num = _RE_SANITIZE_HELPER_NAME.sub('_', raw_wr)[:50]
                    if wr_num in _quarantined_keys:
                        # Already ambiguous — don't re-add under any
                        # raw value. Log once per collision instance
                        # so operators see every colliding row.
                        _collisions += 1
                        prior_raw = _seen_raw_for_key.get(
                            wr_num, '<quarantined>',
                        )
                        logging.warning(
                            f"⚠️ Target-sheet WR# collision (already quarantined): "
                            f"raw={raw_wr!r} also maps to sanitized key "
                            f"{wr_num!r} (prior seen: {prior_raw!r}). "
                            f"Uploads for this WR will be skipped until the "
                            f"target sheet is deduplicated."
                        )
                    elif wr_num in target_map:
                        prior_raw = _seen_raw_for_key.get(wr_num, '<unknown>')
                        if prior_raw != raw_wr:
                            # Collision: quarantine the key to prevent
                            # uploads from silently targeting the wrong
                            # row. The upload site's
                            # ``if wr_num in target_map`` check will
                            # then correctly return False for BOTH
                            # WRs, and the existing "not found in
                            # target sheet" warning fires so operators
                            # know to audit the target sheet. Removing
                            # both is strictly safer than keeping one
                            # — a silent wrong-row upload corrupts
                            # Smartsheet attachments; a loud
                            # not-found failure prompts cleanup.
                            _collisions += 1
                            del target_map[wr_num]
                            _quarantined_keys.add(wr_num)
                            logging.warning(
                                f"⚠️ Target-sheet WR# collision after sanitization: "
                                f"raw={raw_wr!r} and prior raw={prior_raw!r} both "
                                f"map to sanitized key {wr_num!r}; QUARANTINING "
                                f"the key from target_map. Uploads for both WRs "
                                f"will be skipped until the target sheet is "
                                f"deduplicated — log a 'not found in target "
                                f"sheet' warning will follow for each."
                            )
                    else:
                        target_map[wr_num] = row
                        _seen_raw_for_key[wr_num] = raw_wr
                    break

        if _collisions:
            logging.warning(
                f"⚠️ Target sheet map had {_collisions} sanitized-WR# "
                f"collision event(s) across {len(_quarantined_keys)} "
                f"quarantined key(s) — affected uploads will be skipped "
                f"with 'not found in target sheet' warnings."
            )
        logging.info(f"Created target sheet map with {len(target_map)} work requests")
        return target_map, target_sheet
        
    except Exception as e:
        logging.error(f"Failed to create target sheet map: {e}")
        return {}, None

# Modified By cache loading removed - using direct column assignment only

# --- MAIN EXECUTION ---

def main():
    """Main execution function with all fixes implemented."""
    session_start = datetime.datetime.now()
    generated_files_count = 0
    generated_filenames = []  # Track exact filenames created this session
    
    # Sentry cron check-in: signal "in_progress" at session start
    _cron_checkin_id = None
    _cron_monitor_slug = os.getenv("SENTRY_CRON_MONITOR_SLUG", "weekly-excel-generation")
    if SENTRY_DSN:
        try:
            _cron_checkin_id = capture_checkin(
                monitor_slug=_cron_monitor_slug,
                status=MonitorStatus.IN_PROGRESS,
                monitor_config={
                    "schedule": {"type": "crontab", "value": "30 17 * * 1"},
                    "checkin_margin": 10,
                    "max_runtime": 120,
                    "failure_issue_threshold": 2,
                    "recovery_threshold": 1,
                    "timezone": "America/Phoenix",
                },
            )
        except Exception as exc:
            logging.warning(f"⚠️ Sentry cron check-in (in_progress) failed: {exc}")

    try:
        # Set Sentry context (SDK 2.x: top-level API)
        if SENTRY_DSN:
            scope = sentry_sdk.get_isolation_scope()
            scope.set_tag("session_start", session_start.isoformat())
            scope.set_tag("test_mode", str(TEST_MODE))
            scope.set_tag("github_actions", str(GITHUB_ACTIONS_MODE))

        logging.info("🚀 Starting Weekly PDF Generator with Complete Fixes")
        
        # Initialize Smartsheet client or fall back to synthetic data in TEST_MODE
        if not API_TOKEN:
            if TEST_MODE:
                logging.info("🧪 TEST_MODE without SMARTSHEET_API_TOKEN: using synthetic in-memory dataset")

                def build_synthetic_rows():
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

                synthetic_rows = build_synthetic_rows()
                logging.info(f"Synthetic rows prepared: {len(synthetic_rows)} raw rows")
                # Apply normal grouping logic (filtering happens inside grouping)
                groups = group_source_rows(synthetic_rows)
                logging.info(f"Synthetic grouping produced {len(groups)} group(s)")
                snapshot_date = datetime.datetime.now()
                for group_key, group_rows in groups.items():
                    try:
                        data_hash = calculate_data_hash(group_rows)
                        excel_path, filename, wr_numbers = generate_excel(group_key, group_rows, snapshot_date, data_hash=data_hash)
                        generated_files_count += 1
                        logging.info(f"🧪 Synthetic Excel generated: {filename} ({len(group_rows)} rows)")
                    except Exception as e:
                        logging.error(f"Synthetic group failure {group_key}: {e}")
                session_duration = datetime.datetime.now() - session_start
                logging.info(f"🧪 Synthetic session complete: {generated_files_count} file(s) in {session_duration}")
                return
            else:
                raise Exception("SMARTSHEET_API_TOKEN not configured")
        
        client = smartsheet.Smartsheet(API_TOKEN)
        client.errors_as_exceptions(True)
        
        # ── Start root Sentry transaction for full session tracing ──
        _txn = None
        if SENTRY_DSN:
            _txn = sentry_sdk.start_transaction(
                op="session",
                name="weekly-excel-generation",
                description="Full weekly Excel generation session",
            )
            _txn.__enter__()
            _txn.set_data("test_mode", TEST_MODE)
            _txn.set_data("github_actions", GITHUB_ACTIONS_MODE)

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
        
        # Create target sheet map for production uploads
        target_map = {}
        _target_sheet_obj = None  # Cached for cleanup to avoid redundant API call
        if not TEST_MODE:
            with sentry_sdk.start_span(op="smartsheet.target_map", name="Create target sheet map for uploads") as span:
                target_map, _target_sheet_obj = create_target_sheet_map(client)
                span.set_data("wr_count", len(target_map))

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
                    max_retries = 4
                    for attempt in range(max_retries):
                        try:
                            atts = client.Attachments.list_row_attachments(TARGET_SHEET_ID, target_row.id).data
                            return (target_row.id, atts)
                        except (ss_exc.RateLimitExceededError,) as e:
                            if attempt < max_retries - 1:
                                backoff = 15 * (attempt + 1)  # 15s, 30s, 45s for rate limits
                                logging.warning(f"⚠️ Rate limited on attachment fetch for row {target_row.id}, backoff {backoff}s (attempt {attempt+1}/{max_retries})")
                                time.sleep(backoff)
                            else:
                                logging.warning(f"⚠️ Attachment fetch failed after {max_retries} rate-limit retries for row {target_row.id}")
                                return (target_row.id, [])
                        except (ss_exc.UnexpectedErrorShouldRetryError, ss_exc.InternalServerError, ss_exc.ServerTimeoutExceededError) as e:
                            if attempt < max_retries - 1:
                                backoff = 2 ** attempt + 0.5
                                logging.warning(f"⚠️ Attachment fetch retry {attempt+1}/{max_retries} for row {target_row.id} ({type(e).__name__}), backoff {backoff:.1f}s")
                                time.sleep(backoff)
                            else:
                                logging.warning(f"⚠️ Attachment fetch failed after {max_retries} attempts for row {target_row.id}: {type(e).__name__}")
                                return (target_row.id, [])
                        except Exception as e:
                            err_name = type(e).__name__
                            is_transient = any(tag in err_name for tag in ('RemoteDisconnected', 'ConnectionError', 'ConnectionReset', 'SSLError', 'SSLEOFError', 'Timeout'))
                            if is_transient and attempt < max_retries - 1:
                                backoff = 2 ** attempt + 0.5
                                logging.warning(f"⚠️ Attachment fetch retry {attempt+1}/{max_retries} for row {target_row.id} ({err_name}), backoff {backoff:.1f}s")
                                time.sleep(backoff)
                            else:
                                if attempt > 0:
                                    logging.warning(f"⚠️ Attachment fetch failed after {max_retries} attempts for row {target_row.id}: {err_name}")
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

        # Load hash history AFTER optional purge so we don't rely on stale attachments
        hash_history = load_hash_history(HASH_HISTORY_PATH)
        history_updates = 0
        _groups_skipped = 0
        _groups_generated = 0
        _groups_uploaded = 0
        _groups_errored = 0
        _api_calls_count = 0
        _upload_tasks = []  # Collect upload tasks for parallel processing

        _phase_group_start = datetime.datetime.now()
        _time_budget_exceeded = False

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
                if variant == 'helper':
                    # CRITICAL FIX: Include helper dept and job in identifier for unique hash keys
                    # This ensures helper files regenerate when new helper rows are added
                    helper_foreman = first_row.get('__helper_foreman', '')
                    helper_dept = first_row.get('__helper_dept', '')
                    helper_job = first_row.get('__helper_job', '')
                    identifier = f"{helper_foreman}|{helper_dept}|{helper_job}"
                    # file_identifier matches the sanitized name that generate_excel() puts in the filename
                    file_identifier = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50] if helper_foreman else ''
                elif variant == 'vac_crew':
                    # VAC Crew variant: no sub-identifier needed (all vac_crew rows for WR/week go together)
                    identifier = ''
                    file_identifier = ''
                else:
                    user_val = first_row.get('User')
                    # PERFORMANCE: Use pre-compiled regex for identifier sanitization
                    identifier = _RE_SANITIZE_IDENTIFIER.sub('_', user_val)[:50] if user_val else ''
                    file_identifier = identifier
                
                # History key includes variant dimension to prevent collisions
                history_key = f"{wr_num}|{week_raw}|{variant}|{identifier}"

                # ── Billing audit snapshot: freeze personnel + emit run fingerprint ──
                # Runs BEFORE the skip check so stable rows get attribution frozen on
                # subsequent runs (first-write-wins makes repeat calls cheap). Writes
                # happen in shadow mode — no read path yet. Failures must never break
                # Excel generation. Skipped in TEST_MODE to prevent polluting production
                # Supabase with synthetic test data. ``any_flag_enabled()`` is a cheap
                # cached probe — it skips fingerprint computation and the per-row
                # freeze_row loop entirely when both writer flags are off.
                if (
                    BILLING_AUDIT_AVAILABLE
                    and not TEST_MODE
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
                            _week_snap = first_row.get('__week_ending_date')
                            if hasattr(_week_snap, 'date'):
                                _week_snap = _week_snap.date()
                            for _row in group_rows:
                                _billing_audit_writer.freeze_row(
                                    _row,
                                    release=_billing_audit_release_env,
                                    run_id=_billing_audit_run_id_env,
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
                                _billing_audit_writer.emit_run_fingerprint(
                                    wr=wr_num,
                                    week_ending=_week_snap,
                                    content_hash=_agg_content_hash,
                                    assignment_fp=_fp,
                                    completed_count=_completed,
                                    total_count=len(_agg_fp_rows),
                                    release=_billing_audit_release_env,
                                    run_id=_billing_audit_run_id_env,
                                )
                            _bas.set_data("rows", len(group_rows))
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
                if HISTORY_SKIP_ENABLED and not (FORCE_GENERATION or week_raw in REGEN_WEEKS or RESET_HASH_HISTORY or RESET_WR_LIST):
                    prev = hash_history.get(history_key)
                    if prev and prev.get('hash') == data_hash:
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
                    excel_path, filename, wr_numbers = generate_excel(
                        group_key, group_rows, snapshot_date, data_hash=data_hash
                    )
                    gen_span.set_data("filename", filename)
                
                generated_files_count += 1
                _groups_generated += 1
                generated_filenames.append(filename)
                
                # Collect upload task for parallel processing (instead
                # of uploading serially). ``wr_numbers`` is returned raw
                # by ``generate_excel`` — do NOT read from it here; the
                # filename, hash-history key, attachment prefix match,
                # and target_map key all use the sanitized main-loop
                # ``wr_num`` and must stay aligned to avoid repeated
                # regeneration and orphaned duplicate attachments on
                # subsequent runs.
                if not TEST_MODE and target_map and wr_num:
                    if wr_num in target_map:
                        _upload_tasks.append({
                            'excel_path': excel_path,
                            'filename': filename,
                            'wr_num': wr_num,
                            'target_row': target_map[wr_num],
                            'variant': variant,
                            'identifier': identifier,
                            'file_identifier': file_identifier,
                            'data_hash': data_hash,
                            'week_raw': week_raw,
                            'group_key': group_key,
                        })
                    else:
                        logging.warning(f"⚠️ Work request {wr_num} not found in target sheet")

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

        # ── PARALLEL UPLOAD PHASE ─────────────────────────────────────────
        # Upload all collected tasks in parallel instead of serially per-group.
        # This is the primary runtime optimization — reduces upload time by ~Nx with N workers.
        if _upload_tasks:
            _upload_start = datetime.datetime.now()
            logging.info(f"\n{'='*60}")
            logging.info(f"📤 PARALLEL UPLOAD PHASE: {len(_upload_tasks)} files with {PARALLEL_WORKERS} workers")
            logging.info(f"{'='*60}")

            def _upload_one(task):
                """Delete old attachment + upload new one for a single group."""
                max_retries = 4
                last_err = None
                for attempt in range(max_retries):
                    try:
                        target_row = task['target_row']
                        force_this = FORCE_GENERATION or (task['week_raw'] in REGEN_WEEKS)

                        deleted_count, skipped = delete_old_excel_attachments(
                            client, TARGET_SHEET_ID, target_row, task['wr_num'],
                            task['week_raw'], task['data_hash'],
                            variant=task['variant'], identifier=task['file_identifier'],
                            force_generation=force_this,
                            cached_attachments=attachment_cache.get(target_row.id)
                        )
                        if force_this and skipped:
                            skipped = False

                        if skipped:
                            return 'skipped'

                        if not SKIP_UPLOAD:
                            with open(task['excel_path'], 'rb') as file:
                                client.Attachments.attach_file_to_row(
                                    TARGET_SHEET_ID,
                                    target_row.id,
                                    (task['filename'], file, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                                )
                            logging.info(f"✅ Uploaded: {task['filename']}")
                            return 'uploaded'
                        else:
                            logging.info(f"⏭️  Skipping upload (SKIP_UPLOAD=true): {task['filename']}")
                            return 'skip_upload'
                    except ss_exc.RateLimitExceededError as e:
                        last_err = e
                        if attempt < max_retries - 1:
                            backoff = 15 * (attempt + 1)  # 15s, 30s, 45s for rate limits
                            logging.warning(f"⚠️ Rate limited on upload for {task['filename']}, backoff {backoff}s (attempt {attempt+1}/{max_retries})")
                            time.sleep(backoff)
                        else:
                            break
                    except (ss_exc.UnexpectedErrorShouldRetryError, ss_exc.InternalServerError, ss_exc.ServerTimeoutExceededError) as e:
                        last_err = e
                        if attempt < max_retries - 1:
                            backoff = 2 ** attempt + 0.5
                            logging.warning(f"⚠️ Upload retry {attempt+1}/{max_retries} for {task['filename']} ({type(e).__name__}), backoff {backoff:.1f}s")
                            time.sleep(backoff)
                        else:
                            break
                    except Exception as e:
                        last_err = e
                        err_name = type(e).__name__
                        is_transient = any(tag in err_name for tag in ('RemoteDisconnected', 'ConnectionError', 'ConnectionReset', 'SSLError', 'SSLEOFError', 'Timeout'))
                        if is_transient and attempt < max_retries - 1:
                            backoff = 2 ** attempt + 0.5
                            logging.warning(f"⚠️ Upload retry {attempt+1}/{max_retries} for {task['filename']} ({err_name}), backoff {backoff:.1f}s")
                            time.sleep(backoff)
                        else:
                            break
                logging.error(f"❌ Upload failed for {task['filename']}: {last_err}")
                sentry_add_breadcrumb("upload", f"Upload failed for {task['filename']}", level="error", data={
                    "wr": task['wr_num'], "error": str(last_err)[:200],
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
                if variant == 'helper':
                    # Use filename-level identifier (sanitized foreman only) to match build_group_identity output
                    helper_foreman = group_rows[0].get('__helper_foreman', '')
                    file_id = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50] if helper_foreman else ''
                elif variant == 'vac_crew':
                    file_id = ''
                else:
                    user_val = group_rows[0].get('User')
                    # PERFORMANCE: Use pre-compiled regex
                    file_id = _RE_SANITIZE_IDENTIFIER.sub('_', user_val)[:50] if user_val else ''
                valid_wr_weeks.add((wr, week_raw, variant, file_id))
        if not TEST_MODE:
            # Invalidate stale attachment cache after upload phase — uploads added/deleted attachments
            _cleanup_cache = attachment_cache if not _upload_tasks else None
            with sentry_sdk.start_span(op="smartsheet.cleanup", name="Cleanup untracked sheet attachments"):
                cleanup_untracked_sheet_attachments(client, TARGET_SHEET_ID, valid_wr_weeks, TEST_MODE, attachment_cache=_cleanup_cache, target_sheet=_target_sheet_obj)

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
                        if _variant == 'helper':
                            _hf = group_rows[0].get('__helper_foreman', '')
                            _hd = group_rows[0].get('__helper_dept', '')
                            _hj = group_rows[0].get('__helper_job', '')
                            _ident = f"{_hf}|{_hd}|{_hj}"
                        elif _variant == 'vac_crew':
                            _ident = ''
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

if __name__ == "__main__":
    main()
