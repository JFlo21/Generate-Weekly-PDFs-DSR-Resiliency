"""pipeline.config -- environment parsing, derived constants, regex compile.

All import-time environment parsing for the billing engine lives here:
the ~60 ``os.getenv``-derived module constants, the four pre-compiled
sanitization regexes, the sheet/folder-ID parsers, the daemon thread-pool
executor, and the conditional RATE_CUTOFF_DATE / AEP-cutoff / hash-history
blocks.

Relocated verbatim from ``generate_weekly_pdfs.py`` (Phase 09 Wave 1, D-05
relocation-only). The dotenv environment load is intentionally NOT performed
here -- it stays in the facade body so the environment is populated before
this module is imported (D-04). This module imports ONLY the standard library
and never another ``pipeline`` module (D-04 import-cycle rule).
"""

import os
import datetime
import re
import logging
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures.thread as _cf_thread


# PERFORMANCE: pre-compiled regex patterns (relocated from facade L85-88)
_RE_SANITIZE_IDENTIFIER = re.compile(r'[^\w\-@.]')
_RE_SANITIZE_HELPER_NAME = re.compile(r'[^\w\-]')
_RE_EXTRACT_NUMBERS = re.compile(r'[^0-9.\-]')
_RE_ISO_DATE_PREFIX = re.compile(r'^\d{4}-\d{2}-\d{2}')

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
# Set to 0 to disable. The weekly workflow sets this to 165 (2h45m) with a matching
# timeout-minutes: 180 on the runner (15min cushion for cache/artifact save steps).
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
            q.put(None)  # type: ignore[arg-type]  # sentinel signals worker shutdown (matches CPython internals)

        num_threads = len(self._threads)
        if num_threads < self._max_workers:
            thread_name = '%s_%d' % (self._thread_name_prefix or self, num_threads)
            t = threading.Thread(
                name=thread_name,
                target=_cf_thread._worker,
                args=(weakref.ref(self, _weakref_cb),
                      self._work_queue,
                      getattr(self, '_initializer', None),
                      getattr(self, '_initargs', ())),
                daemon=True,
            )
            t.start()
            self._threads.add(t)  # type: ignore[attr-defined]  # CPython exposes _threads as a mutable set despite AbstractSet typing
            _cf_thread._threads_queues[t] = self._work_queue  # type: ignore[index]  # CPython internals expose this as a mutable dict despite Mapping typing


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


# Folder-based discovery: Smartsheet folder IDs whose child sheets should be auto-discovered
# Subcontractor folders (child sheets discovered and processed as subcontractor-
# priced sheets; see pipeline/pricing.py for the rate logic). NOTE: production
# keeps the Smartsheet/subcontractor pricing as-is — no reversion to original
# contract rates is performed (revert_subcontractor_price() exists but is only
# exercised by tests, never called in the live pipeline).
SUBCONTRACTOR_FOLDER_IDS = _parse_sheet_ids(os.getenv('SUBCONTRACTOR_FOLDER_IDS', '4232010517505924,2588197684307844'))
# Original contract folders (sheets already at original contract rates)
ORIGINAL_CONTRACT_FOLDER_IDS = _parse_sheet_ids(os.getenv('ORIGINAL_CONTRACT_FOLDER_IDS', '7644752003786628,8815193070299012'))
# VAC Crew detection is now row-level (column-presence-based, no folder/sheet ID config needed).
# Sheets with columns like 'VAC Crew Helping?' and 'Vac Crew Completed Unit?' automatically
# produce vac_crew variant rows during row processing.
# Legacy variables for backward compatibility with tests (no longer used in production)
VAC_CREW_SHEET_IDS = set(_parse_sheet_ids(os.getenv('VAC_CREW_SHEET_IDS', '')))
VAC_CREW_FOLDER_IDS = _parse_sheet_ids(os.getenv('VAC_CREW_FOLDER_IDS', ''))

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

SUBCONTRACTOR_RATE_VARIANTS_ENABLED = os.getenv(
    'SUBCONTRACTOR_RATE_VARIANTS_ENABLED', '1'
).lower() in ('1', 'true', 'yes', 'on')

# Phase 1.1 Bug A (D-02 / SUB-08): pre-acceptance rate-recalc rescue
# for subcontractor sheets. Default-on per the [2026-04-23 00:00]
# Living Ledger rule that any pre-acceptance / data-shape change must
# ship with a rollback flag. Setting '0' reverts Bug A behavior to
# the pre-fix state without affecting Bug B1, B2, or claim-history
# fixes. Pinned in workflow env: block per IN-04.
SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED = os.getenv(
    'SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')

# Phase 1.1 Bug C (D-14 / SUB-11): per-row claim-history attribution
# kill switch. Default-on per the [2026-04-23 00:00] Living Ledger
# rule. Setting '0' reverts Bug C behavior to Phase 1's full-row-set
# helper behavior (the same path as D-12 unconditionally —
# `lookup_attribution` is not invoked and the row's current
# `__helper_foreman` flows through to shadow-variant emission
# unchanged). Pinned in workflow env: block per IN-04.
SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED = os.getenv(
    'SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')

# Phase 1.1 UAT gap closure (SUB-09 helper dimension): default-ON
# kill switch for the one-time removal of pre-existing legacy
# `_Helper_<name>` (and bare-primary) attachments on TARGET_SHEET_ID
# for subcontractor WRs. These are duplicate-billing leftovers from
# pre-fix merged runs (Task 1 stops NEW ones; this removes OLD ones).
# Set to '0' to skip the destructive cleanup (the duplicates then
# persist until manually removed). Workflow-pinned per [2026-05-15
# 12:00] rule 7.
SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED = os.getenv(
    'SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')

# Subproject B (2026-05-20): default-ON kill switch for the one-time
# removal of legacy UNPARTITIONED `_ReducedSub` / `_AEPBillable`
# attachments (no `_User_` token, parsed identifier == '') on
# TARGET_SHEET_ID and SUBCONTRACTOR_PPP_SHEET_ID for subcontractor
# WRs. B re-partitions those variants by frozen primary claimer; the
# legacy one-file-per-WR attachments become duplicate-billing
# leftovers (the Phase 1.1 Bug B2 / SUB-09 trap). Set to '0' to skip
# the destructive cleanup (legacy files then persist until manually
# removed). Separate from SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED
# (which gates attribution resolution, NOT this cleanup). Workflow-
# pinned per [2026-05-15 12:00] rule 7.
SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED = os.getenv(
    'SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')

# Subproject C (2026-05-21): default-ON kill switch that enables
# per-claimer partitioning of ``_VacCrew`` Excel files. When enabled,
# each vac-crew Excel is partitioned by the FROZEN vac-crew claimer
# (``vac_crew`` role from ``billing_audit.attribution_snapshot`` via
# ``resolve_claimer``). When disabled, the legacy one-file-per-WR
# ``_VacCrew`` behavior is preserved exactly. Pinned in workflow
# env: block per [2026-05-15 12:00] rule 7.
VAC_CREW_CLAIM_ATTRIBUTION_ENABLED = os.getenv(
    'VAC_CREW_CLAIM_ATTRIBUTION_ENABLED', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')

# Subproject C (2026-05-21): default-ON kill switch for the one-time
# removal of legacy UNPARTITIONED ``_VacCrew`` attachments (no
# ``_User_`` token, parsed identifier == '') on TARGET_SHEET_ID for
# vac-crew WRs, once those variants are re-partitioned by frozen
# vac-crew claimer. Set to '0' to skip the destructive cleanup (legacy
# files then persist until removed manually). Separate from
# VAC_CREW_CLAIM_ATTRIBUTION_ENABLED (which gates attribution
# resolution, NOT this cleanup). Workflow-pinned per [2026-05-15
# 12:00] rule 7.
VAC_CREW_LEGACY_CLEANUP_ENABLED = os.getenv(
    'VAC_CREW_LEGACY_CLEANUP_ENABLED', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')

# Subproject D (2026-05-25): default-ON kill switch that enables
# per-claimer partitioning of the PRODUCTION primary Excel files. When
# enabled, each non-subcontractor primary Excel is partitioned by the
# FROZEN primary foreman (``primary`` role from
# ``billing_audit.attribution_snapshot`` via ``resolve_claimer``) and
# named ``_User_<claimer>``. When disabled, the legacy one-file-per-WR
# bare primary behavior is preserved exactly. Unlike Subproject B, the
# core primary path NEVER holds on a Supabase outage — it falls back to
# the current foreman and still generates (operator decision: this path
# covers every non-sub WR, so HOLD would suppress all primary billing
# during an outage). Pinned in workflow env: block per [2026-05-15
# 12:00] rule 7.
PRIMARY_CLAIM_ATTRIBUTION_ENABLED = os.getenv(
    'PRIMARY_CLAIM_ATTRIBUTION_ENABLED', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')

# Subproject D (2026-05-25): default-ON kill switch for the one-time
# removal of legacy UNPARTITIONED bare ``primary`` attachments (no
# ``_User_`` token; ``build_group_identity`` parses these to
# ``identifier=None``) on TARGET_SHEET_ID for
# non-subcontractor WRs, once those files are re-partitioned by frozen
# primary claimer. Set to '0' to skip the destructive cleanup (legacy
# duplicates then persist until removed manually). Separate from
# PRIMARY_CLAIM_ATTRIBUTION_ENABLED (which gates attribution
# resolution, NOT this cleanup). Workflow-pinned per [2026-05-15
# 12:00] rule 7.
LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED = os.getenv(
    'LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')

# Sub-project E (2026-05-25): durable Supabase change-detection hash store.
# WRITE (default ON): shadow-write the per-group content hash to Supabase
# every run. Harmless even while not authoritative — it populates the
# durable store so a later flip to authoritative finds current hashes and
# skips the one-time regeneration wave.
SUPABASE_HASH_STORE_WRITE_ENABLED = os.getenv(
    'SUPABASE_HASH_STORE_WRITE_ENABLED', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')
# AUTHORITATIVE (default OFF — ship dormant): when ON, (a) the change-
# detection skip gate reads the Supabase group hash (falling back to the
# hash_history.json cache, then regenerating on miss/outage — never
# skipping unsafely), (b) generated filenames DROP the _<timestamp>/_<hash>
# tokens (deterministic identity-only names), and (c)
# delete_old_excel_attachments stops relying on the filename-embedded hash.
# Flip to '1' only after the Supabase store is validated in production.
# This is the one-line master revert for all of Sub-project E.
SUPABASE_HASH_STORE_AUTHORITATIVE = os.getenv(
    'SUPABASE_HASH_STORE_AUTHORITATIVE', '0'
).strip().lower() in ('1', 'true', 'yes', 'on')

# Phase 2 Plan 05 gap-closure (CR-01): when the bulk lookup_attribution_bulk
# RPC is not yet deployed (PGRST202 -> prefetch status 'rpc_missing'), degrade
# to the already-deployed per-row lookup_attribution path instead of HOLDing
# every B/C/sub-helper row. Default ON so a code-before-RPC deploy ordering
# does NOT suppress billing. A genuine transient outage ('fetch_failure') still
# HOLDs B/C (D-04). The per-row fallback is bounded to the rows actually
# processed this run, so it cannot reintroduce the 137k per-row storm. Set to
# '0' to force the strict bulk-only behavior.
ATTRIBUTION_BULK_PREFETCH_FALLBACK = os.getenv(
    'ATTRIBUTION_BULK_PREFETCH_FALLBACK', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')

# ── Phase 2 Plan 03 (D-06/D-07/D-08): Isolated garbage-attachment remediation ──
# DEFAULT OFF: ``REMEDIATE_CLAIMERS='0'`` so the mode NEVER fires on a scheduled
# cron run. An operator must explicitly set '1' via workflow_dispatch or a local
# shell to activate the sweep. When active, ``main()`` returns immediately after
# the sweep (isolation — no Excel generation occurs in the same session).
REMEDIATE_CLAIMERS = os.getenv(
    'REMEDIATE_CLAIMERS', '0'
).strip().lower() in ('1', 'true', 'yes', 'on')
# DRY_RUN (default ON): first run reports counts without deleting (D-08). Set
# to '0' only after reviewing the dry-run log and confirming the scope is correct.
REMEDIATION_DRY_RUN = os.getenv(
    'REMEDIATION_DRY_RUN', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')
# WINDOW_WEEKS (default 26): sweep only attachments whose week-ending date is
# within the last N weeks. Limits blast radius; set 0 to disable the filter
# (unbounded sweep). Safe-parsed: invalid values fall back to the default with
# an operator WARNING.
_remediation_window_env = os.getenv('REMEDIATION_WINDOW_WEEKS', '26')
try:
    REMEDIATION_WINDOW_WEEKS: int = int(_remediation_window_env)
    if REMEDIATION_WINDOW_WEEKS < 0:
        raise ValueError("negative")
except (ValueError, TypeError):
    logging.warning(
        f"⚠️ REMEDIATION_WINDOW_WEEKS={_remediation_window_env!r} is not a valid "
        f"non-negative integer — falling back to default 26"
    )
    REMEDIATION_WINDOW_WEEKS = 26

# Recent-week scope for the per-row frozen-attribution pre-pass
# (perf hotfix 2026-05-26). The B/C/D claim-attribution pre-passes and
# the subcontractor-helper path each call the ``lookup_attribution``
# Supabase RPC once per completed row. Run unbounded, that resolves
# EVERY completed row across ALL historical weeks (observed: ~137k RPCs
# per run), even though change-detection skips the vast majority of old
# weeks (unchanged + attachment exists) — so the resolved claimer is
# never even used. That eager work scaled with accumulated history and
# blew the workflow time budget.
#
# This gate limits resolution to rows whose ``week_ending`` is within
# the last N weeks of today, making the pre-pass cost track ACTIVE work
# (current + recent edit horizon) instead of total history. Safe by
# construction: an out-of-scope row resolves to use-current at emission,
# but its group is one of two cases — (1) unchanged + attachment exists
# -> skipped, claimer unused (zero impact); or (2) the rare edit to a
# >N-week-old row -> regenerated with the CURRENT foreman (the same
# legacy/no_history fallback the feature already documents). The freeze
# (write) side is UNTOUCHED — every completed row is still frozen during
# generation — so the durable attribution data stays complete.
#
# Phase 2 Plan 02 (D-05): ATTRIBUTION_RESOLUTION_WEEKS removed. The bulk
# prefetch (prefetch_attribution) now covers the exact (wr, week_ending)
# pairs in the current run — no recency scope gate is needed. This fixes
# the production incident (run 26439205107) where the 8-week scope gate
# prevented historical frozen claimers from being resolved, producing
# 372 garbage _User__NO_MATCH / _User_Unknown_Foreman files.

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
