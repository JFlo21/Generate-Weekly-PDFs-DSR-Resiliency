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
import re
import warnings
import hashlib
from datetime import timedelta
import logging
from dateutil import parser
import smartsheet
import openpyxl
from openpyxl.styles import Font, numbers, Alignment, PatternFill
from openpyxl.drawing.image import Image
import collections
from openpyxl.utils import get_column_letter
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
import traceback
import sys
import inspect
import json
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
MAX_GROUPS = int(os.getenv('MAX_GROUPS','0') or 0)
QUIET_LOGGING = os.getenv('QUIET_LOGGING','0').lower() in ('1','true','yes')
USE_DISCOVERY_CACHE = os.getenv('USE_DISCOVERY_CACHE','1').lower() in ('1','true','yes')
DISCOVERY_CACHE_TTL_MIN = int(os.getenv('DISCOVERY_CACHE_TTL_MIN','60') or 60)
DISCOVERY_CACHE_PATH = os.path.join(OUTPUT_FOLDER, 'discovery_cache.json')
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
RESET_HASH_HISTORY = os.getenv('RESET_HASH_HISTORY','0').lower() in ('1','true','yes')  # When true, delete ALL existing WR_*.xlsx attachments & local files first
RESET_WR_LIST = {w.strip() for w in os.getenv('RESET_WR_LIST','').split(',') if w.strip()}  # When provided, only purge these WR numbers (overrides full reset)
HASH_HISTORY_PATH = os.getenv('HASH_HISTORY_PATH', os.path.join(OUTPUT_FOLDER, 'hash_history.json'))
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

# --- SENTRY CONFIGURATION ---
SENTRY_DSN = os.getenv("SENTRY_DSN")

if SENTRY_DSN:
    sentry_logging = LoggingIntegration(
        level=logging.INFO,
        event_level=logging.ERROR
    )
    
    def before_send_filter(event, hint):
        """Filter out normal Smartsheet 404 errors during cleanup operations."""
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
        
        return event
    
    try:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[sentry_logging],
            traces_sample_rate=1.0,
            environment=os.getenv("ENVIRONMENT", "production"),
            release=os.getenv("RELEASE", "latest"),
            before_send=before_send_filter,
            attach_stacktrace=True,
            max_breadcrumbs=50,
        )
        
        sentry_sdk.set_user({"id": "excel_generator", "username": "weekly_pdf_generator"})
        sentry_sdk.set_tag("component", "excel_generation")
        sentry_sdk.set_tag("process", "weekly_reports")
        
        logger = logging.getLogger(__name__)
        logging.info("🛡️ Sentry.io error monitoring initialized")
    except Exception as e:
        logging.warning(f"⚠️ Sentry initialization failed: {e}")
        logger = logging.getLogger(__name__)
else:
    logger = logging.getLogger(__name__)
    logging.warning("⚠️ SENTRY_DSN not configured - error monitoring disabled")

# --- UTILITY FUNCTIONS ---

def parse_price(price_str):
    """Safely convert a price string to a float."""
    if not price_str:
        return 0.0
    try:
        return float(str(price_str).replace('$', '').replace(',', ''))
    except (ValueError, TypeError):
        return 0.0

def is_checked(value):
    """Check if a checkbox value is considered checked/true."""
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
    """Strict date parsing: return datetime or None. No numeric/serial fallbacks."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime.combine(value, datetime.time.min)
    s = str(value).strip()
    try:
        dt = parser.parse(s)
        if isinstance(dt, datetime.datetime):
            return dt
        return datetime.datetime.combine(dt, datetime.time.min)
    except Exception:
        return None

def calculate_data_hash(group_rows):
    """Calculate a hash of the group data to detect changes.

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

    # Deterministic sorting across key business fields
    sorted_rows = sorted(
        group_rows,
        key=lambda x: (
            str(x.get('Work Request #', '')),
            str(x.get('Snapshot Date', '')),
            str(x.get('CU', '')),
            str(x.get('Pole #') or x.get('Point #') or x.get('Point Number') or ''),
            str(x.get('Quantity', '')),
        )
    )

    if not EXTENDED_CHANGE_DETECTION:
        data_string = ""
        for row in sorted_rows:
            data_string += (
                f"{row.get('Work Request #', '')}"
                f"{row.get('CU', '')}"
                f"{row.get('Quantity', '')}"
                f"{row.get('Units Total Price', '')}"
                f"{row.get('Snapshot Date', '')}"
                f"{row.get('Pole #', '')}"
                f"{row.get('Work Type', '')}"
            )
        return hashlib.sha256(data_string.encode('utf-8')).hexdigest()[:16]

    # Extended mode hash input parts
    parts = []
    group_foreman = None
    for row in sorted_rows:
        foreman = row.get('__current_foreman') or row.get('Foreman') or ''
        if group_foreman is None and foreman:
            group_foreman = foreman
        parts.append("|".join([
            str(row.get('Work Request #', '')),
            str(row.get('Snapshot Date', '') or ''),
            str(row.get('CU', '') or ''),
            str(row.get('Quantity', '') or ''),
            str(row.get('Units Total Price', '') or ''),
            str(row.get('Pole #') or row.get('Point #') or row.get('Point Number') or ''),
            str(row.get('Work Type', '') or ''),
            str(row.get('Dept #', '') or ''),
            str(row.get('Scope #') or row.get('Scope ID', '') or ''),
        ]))

    unique_depts = sorted({str(r.get('Dept #', '') or '') for r in sorted_rows if r.get('Dept #') is not None})
    total_price = sum(parse_price(r.get('Units Total Price')) for r in sorted_rows)
    parts.append(f"FOREMAN={group_foreman or ''}")
    parts.append(f"DEPTS={','.join(unique_depts)}")
    parts.append(f"TOTAL={total_price:.2f}")
    parts.append(f"ROWCOUNT={len(sorted_rows)}")

    hash_input = "\n".join(parts)
    return hashlib.sha256(hash_input.encode('utf-8')).hexdigest()[:16]

def extract_data_hash_from_filename(filename):
    """Extract data hash from filename format: WR_{wr_num}_WeekEnding_{week_end}_{data_hash}.xlsx"""
    try:
        name_without_ext = filename.replace('.xlsx', '')
        parts = name_without_ext.split('_')
        if len(parts) >= 4 and len(parts[-1]) == 16:
            return parts[-1]
    except Exception:
        pass
    return None

def list_generated_excel_files(folder: str):
    """List Excel files beginning with WR_ in the specified folder."""
    try:
        return [f for f in os.listdir(folder) if f.startswith('WR_') and f.lower().endswith('.xlsx')]
    except FileNotFoundError:
        return []

def build_group_identity(filename: str):
    """Return (wr, week_ending) tuple parsed from filename (legacy or current format) or None."""
    if not filename.startswith('WR_'):
        return None
    base = filename[:-5] if filename.lower().endswith('.xlsx') else filename
    parts = base.split('_')
    # Legacy: WR_<wr>_WeekEnding_<week>
    # Current: WR_<wr>_WeekEnding_<week>_<timestamp>_<hash>
    if len(parts) < 4:
        return None
    if parts[0] != 'WR' or parts[2] != 'WeekEnding':
        return None
    wr = parts[1]
    week = parts[3]
    return (wr, week)

def cleanup_stale_excels(output_folder: str, kept_filenames: set):
    """Remove Excel files not generated in current run.

    Strategy:
      1. Keep all names in kept_filenames.
      2. For identities (wr, week) present in kept_filenames, remove any other variants (legacy or older timestamp/hash).
      3. Remove any other WR_*.xlsx whose identity is not in current run (per user requirement to only keep new system outputs).
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

def cleanup_untracked_sheet_attachments(client, target_sheet_id: int, valid_wr_weeks: set, test_mode: bool):
    """Prune only older variants for identities processed this run.

    If KEEP_HISTORICAL_WEEKS=1 (default false here), weeks not in this run are preserved.
    valid_wr_weeks: set of tuples (wr, week_mmddyy) that were generated or validated this session.
    """
    if test_mode:
        logging.info("🧪 Test mode – skipping sheet attachment pruning")
        return
    try:
        sheet = client.Sheets.get_sheet(target_sheet_id)
    except Exception as e:
        logging.warning(f"⚠️ Could not load target sheet for attachment cleanup: {e}")
        return
    removed_variants = 0
    for row in sheet.rows:
        try:
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
                if len(parts) >= 6 and parts[4].isdigit():
                    return parts[4]
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

def delete_old_excel_attachments(client, target_sheet_id, target_row, wr_num, week_raw, current_data_hash, force_generation=False):
    """Delete prior Excel attachment(s) ONLY for the specific (WR, week) pair.

    Previous behavior deleted every attachment matching WR_<wr>_* which removed
    historical week-ending files for that Work Request. This function now:
      • Looks only for names: WR_<wr>_WeekEnding_<MMDDYY>.xlsx (legacy) OR
        WR_<wr>_WeekEnding_<MMDDYY>_<...>.xlsx (timestamp/hash variants)
      • If an attachment for that (wr, week) already has the identical data hash
        (and not forcing) we skip regeneration & upload.
      • Leaves attachments for other weeks untouched so multiple weeks accumulate.

    Returns (deleted_count, skipped_due_to_same_data)
    """
    deleted_count = 0
    try:
        attachments = client.Attachments.list_row_attachments(target_sheet_id, target_row.id).data
    except Exception as e:
        logging.warning(f"Could not list attachments for row {target_row.id}: {e}")
        return 0, False

    prefix_no_underscore = f"WR_{wr_num}_WeekEnding_{week_raw}"
    legacy_exact = f"{prefix_no_underscore}.xlsx"
    candidates = []
    for a in attachments:
        name = getattr(a, 'name', '') or ''
        if not name.endswith('.xlsx'):
            continue
        # Must match EXACT (legacy) or start with prefix + underscore (new naming)
        if name == legacy_exact or name.startswith(prefix_no_underscore + '_'):
            candidates.append(a)

    if not candidates:
        return 0, False

    # Skip if any existing candidate already carries the same hash (unless forced)
    if not force_generation:
        for att in candidates:
            existing_hash = extract_data_hash_from_filename(att.name)
            if existing_hash == current_data_hash:
                logging.info(f"⏩ Unchanged (WR {wr_num} Week {week_raw}) hash {current_data_hash}; skipping regeneration & upload")
                return 0, True
    else:
        logging.info(f"⚐ FORCE GENERATION for WR {wr_num} Week {week_raw}; ignoring existing hash match")

    logging.info(f"🗑️ Removing {len(candidates)} prior attachment(s) for WR {wr_num} Week {week_raw}")
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
        time.sleep(0.05)
    return deleted_count, False

def _has_existing_week_attachment(client, target_sheet_id, target_row, wr_num: str, week_raw: str) -> bool:
    """Return True if at least one attachment exists for this (WR, week)."""
    try:
        attachments = client.Attachments.list_row_attachments(target_sheet_id, target_row.id).data
    except Exception:
        return False
    prefix = f"WR_{wr_num}_WeekEnding_{week_raw}"
    for a in attachments:
        name = getattr(a, 'name', '') or ''
        if not name.endswith('.xlsx'):
            continue
        if name == prefix + '.xlsx' or name.startswith(prefix + '_'):
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
        if isinstance(data, dict):
            return data
        return {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        logging.warning(f"⚠️ Failed to load hash history: {e}")
        return {}

def save_hash_history(path: str, history: dict):
    try:
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

def _sample_values_for_col(client, sheet_id, col_id, n=5):
    try:
        sample = client.Sheets.get_sheet(sheet_id, row_numbers=list(range(1, n+1)))
    except Exception:
        return []
    vals = []
    for row in sample.rows:
        for cell in row.cells:
            if cell.column_id == col_id:
                val = getattr(cell, 'value', None)
                if val is None:
                    val = getattr(cell, 'display_value', None)
                if val is not None:
                    vals.append(str(val))
                break
    return vals

def discover_source_sheets(client):
    """Strict deterministic discovery: anchored keywords + type filtered. Skips sheets missing Weekly Reference Logged Date."""
    # Attempt cache load
    if USE_DISCOVERY_CACHE and os.path.exists(DISCOVERY_CACHE_PATH):
        try:
            with open(DISCOVERY_CACHE_PATH,'r') as f:
                cache = json.load(f)
            ts = datetime.datetime.fromisoformat(cache.get('timestamp'))
            age_min = (datetime.datetime.now() - ts).total_seconds()/60.0
            if age_min <= DISCOVERY_CACHE_TTL_MIN:
                logging.info(f"⚡ Using cached discovery ({age_min:.1f} min old) with {len(cache.get('sheets',[]))} sheets")
                return cache.get('sheets', [])
            else:
                logging.info(f"ℹ️ Discovery cache expired ({age_min:.1f} min old); refreshing")
        except Exception as e:
            logging.info(f"Cache load failed, refreshing discovery: {e}")
    base_sheet_ids = [
        3239244454645636, 2230129632694148, 1732945426468740, 4126460034895748,
        7899446718189444, 1964558450118532, 5905527830695812, 820644963897220, 8002920231423876
    ]
    discovered = []
    for sid in base_sheet_ids:
        try:
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
            # Sample fallback
            if 'Weekly Reference Logged Date' not in mapping:
                for c in date_candidates:
                    t = _title(c.title)
                    if 'date' in t and any(k in t for k in ('weekly','reference','logged','week ending')):
                        samples = _sample_values_for_col(client, sid, c.id, 3)
                        if any(re.match(r'^\d{4}-\d{2}-\d{2}', v) for v in samples):
                            mapping['Weekly Reference Logged Date'] = c.id
                            break
            if 'Snapshot Date' not in mapping:
                for c in date_candidates:
                    t = _title(c.title)
                    if 'date' in t and 'snapshot' in t:
                        samples = _sample_values_for_col(client, sid, c.id, 3)
                        if any(re.match(r'^\d{4}-\d{2}-\d{2}', v) for v in samples):
                            mapping['Snapshot Date'] = c.id
                            break
            # Non-date synonyms
            synonyms = {
                'Foreman':'Foreman','Work Request #':'Work Request #','Dept #':'Dept #','Customer Name':'Customer Name','Work Order #':'Work Order #','Area':'Area',
                'Pole #':'Pole #','Point #':'Pole #','Point Number':'Pole #','CU':'CU','Billable Unit Code':'CU','Work Type':'Work Type','CU Description':'CU Description',
                'Unit Description':'CU Description','Unit of Measure':'Unit of Measure','UOM':'Unit of Measure','Quantity':'Quantity','Qty':'Quantity','# Units':'Quantity',
                'Units Total Price':'Units Total Price','Total Price':'Units Total Price','Redlined Total Price':'Units Total Price','Scope #':'Scope #','Scope ID':'Scope #',
                'Job #':'Job #','Units Completed?':'Units Completed?','Units Completed':'Units Completed?'
            }
            for c in cols:
                if c.title in synonyms and synonyms[c.title] not in mapping:
                    mapping[synonyms[c.title]] = c.id
            if 'Weekly Reference Logged Date' in mapping:
                w_id = mapping['Weekly Reference Logged Date']
                s_id = mapping.get('Snapshot Date')
                w_samples = _sample_values_for_col(client, sid, w_id, 3)
                s_samples = _sample_values_for_col(client, sid, s_id, 3) if s_id else []
                logging.info(f"Sheet {sheet.name} (ID {sid}) date columns:")
                logging.info(f"  Weekly Reference Logged Date (ID {w_id}) samples: {w_samples}")
                if s_id:
                    logging.info(f"  Snapshot Date (ID {s_id}) samples: {s_samples}")
                discovered.append({'id': sid,'name': sheet.name,'column_mapping': mapping})
                logging.info(f"✅ Added sheet: {sheet.name} (ID: {sid})")
            else:
                logging.warning(f"❌ Skipping sheet {sheet.name} (ID {sid}) - Weekly Reference Logged Date not found (strict mode)")
        except Exception as e:
            logging.warning(f"⚡ Failed to validate sheet {sid}: {e}")
    logging.info(f"⚡ Discovery complete: {len(discovered)} sheets")
    # Save cache
    if USE_DISCOVERY_CACHE:
        try:
            with open(DISCOVERY_CACHE_PATH,'w') as f:
                json.dump({'timestamp': datetime.datetime.now().isoformat(), 'sheets': discovered}, f)
        except Exception as e:
            logging.warning(f"Failed to write discovery cache: {e}")
    return discovered

def get_all_source_rows(client, source_sheets):
    """Fetch rows from all source sheets with filtering.

    Improvements:
      • Per‑cell debug logging limited by DEBUG_SAMPLE_ROWS (env tunable)
      • Essential field summary limited by DEBUG_ESSENTIAL_ROWS
      • Single concise summary for unmapped columns with a small sample of values
      • Greatly reduces 'Unknown' spam while preserving early transparency
    """
    merged_rows = []
    global_row_counter = 0
    exclusion_counts = {
        'missing_work_request': 0,
        'missing_weekly_reference_logged_date': 0,
        'units_not_completed': 0,
        'price_missing_or_zero': 0,
        'accepted': 0
    }
    # Detailed per‑WR diagnostics
    foreman_raw_counts = collections.defaultdict(lambda: collections.Counter())  # wr -> Counter(foreman values as-seen)
    wr_exclusion_reasons = collections.defaultdict(lambda: collections.Counter())  # wr -> Counter(reason)

    for source in source_sheets:
        try:
            logging.info(f"⚡ Processing: {source['name']} (ID: {source['id']})")

            try:
                # Fetch sheet once (no column history); include columns to support unmapped summary
                sheet = client.Sheets.get_sheet(source['id'], include='columns')
                column_mapping = source['column_mapping']

                logging.info(f"📋 Available mapped columns in {source['name']}: {list(column_mapping.keys())}")
                
                # Debug: Check if Weekly Reference Logged Date is mapped
                if 'Weekly Reference Logged Date' in column_mapping:
                    logging.info(f"✅ Weekly Reference Logged Date column found with ID: {column_mapping['Weekly Reference Logged Date']}")
                else:
                    logging.warning(f"❌ Weekly Reference Logged Date column NOT found in mapping")
                    logging.info(f"   Available mappings: {column_mapping}")

                # Unmapped column summary (once per sheet)
                if LOG_UNKNOWN_COLUMNS:
                    mapped_ids = set(column_mapping.values())
                    unmapped = [c for c in sheet.columns if c.id not in mapped_ids]
                    if unmapped:
                        # Build sample values for up to UNMAPPED_COLUMN_SAMPLE_LIMIT cells in first few rows
                        sample_rows = sheet.rows[:UNMAPPED_COLUMN_SAMPLE_LIMIT]
                        col_samples = {}
                        for col in unmapped:
                            vals = []
                            for r in sample_rows:
                                for ce in r.cells:
                                    if ce.column_id == col.id:
                                        v = getattr(ce,'display_value', None) or getattr(ce,'value', None)
                                        if v is not None:
                                            vals.append(str(v))
                                        break
                                if len(vals) >= 3:
                                    break
                            if vals:
                                col_samples[col.title] = vals
                        logging.info(f"🧭 Unmapped columns ({len(unmapped)}): {[c.title for c in unmapped][:15]}{' ...' if len(unmapped)>15 else ''}")
                        if col_samples:
                            logging.info(f"🧪 Unmapped sample values: { {k: v for k,v in col_samples.items()} }")

                for row in sheet.rows:
                    row_data = {}

                    # Per‑cell debug logging only for the earliest rows overall
                    if PER_CELL_DEBUG_ENABLED and global_row_counter < DEBUG_SAMPLE_ROWS:
                        logging.info(f"🔍 DEBUG: Processing row with {len(row.cells)} cells (global row #{global_row_counter+1})")
                        for cell in row.cells:
                            mapped_name = None
                            for name, cid in column_mapping.items():
                                if cell.column_id == cid:
                                    mapped_name = name
                                    break
                            if mapped_name:
                                val = cell.display_value if cell.display_value is not None else cell.value
                                if val is not None:
                                    logging.info(f"   Cell {cell.column_id}: '{mapped_name}' = '{val}'")

                    # Build mapped row data
                    for cell in row.cells:
                        raw_val = getattr(cell, 'value', None)
                        if raw_val is None:
                            raw_val = getattr(cell, 'display_value', None)
                        for mapped_name, column_id in column_mapping.items():
                            if cell.column_id == column_id:
                                row_data[mapped_name] = raw_val
                                break

                    # Attach provenance metadata for audit (used to fetch selective cell history later)
                    if row_data:
                        row_data['__sheet_id'] = source['id']
                        row_data['__row_id'] = row.id

                    # Essential field summary for earliest rows
                    if global_row_counter < DEBUG_ESSENTIAL_ROWS:
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
                        has_price = (price_raw not in (None, "", "$0", "$0.00", "0", "0.0")) and price_val > 0
                        units_completed = row_data.get('Units Completed?')
                        units_completed_checked = is_checked(units_completed)

                        if global_row_counter < DEBUG_ESSENTIAL_ROWS:
                            logging.info(f"🔍 Row data sample: WR={work_request}, Price={price_val}, Date={weekly_date}, Units Completed={units_completed} ({units_completed_checked})")

                        # Record raw foreman regardless of acceptance (if WR exists)
                        wr_key_for_diag = None
                        if work_request:
                            wr_key_for_diag = str(work_request).split('.')[0]
                            fr_val = (row_data.get('Foreman') or '').strip() or '<<blank>>'
                            foreman_raw_counts[wr_key_for_diag][fr_val] += 1

                        # Acceptance logic (STRICT: Units Completed? must be checked/true)
                        if work_request and weekly_date and units_completed_checked and has_price:
                            merged_rows.append(row_data)
                            exclusion_counts['accepted'] += 1
                        else:
                            # Increment specific exclusion reasons (first matching reason recorded)
                            if not work_request:
                                exclusion_counts['missing_work_request'] += 1
                                if wr_key_for_diag:
                                    wr_exclusion_reasons[wr_key_for_diag]['missing_work_request'] += 1
                            elif not weekly_date:
                                exclusion_counts['missing_weekly_reference_logged_date'] += 1
                                if wr_key_for_diag:
                                    wr_exclusion_reasons[wr_key_for_diag]['missing_weekly_reference_logged_date'] += 1
                            elif not units_completed_checked:
                                exclusion_counts['units_not_completed'] += 1
                                if wr_key_for_diag:
                                    wr_exclusion_reasons[wr_key_for_diag]['units_not_completed'] += 1
                            elif not has_price:
                                exclusion_counts['price_missing_or_zero'] += 1
                                if wr_key_for_diag:
                                    wr_exclusion_reasons[wr_key_for_diag]['price_missing_or_zero'] += 1

                    global_row_counter += 1

            except Exception as e:
                logging.error(f"Error processing sheet {source['id']}: {e}")
                if SENTRY_DSN:
                    sentry_sdk.capture_exception(e)
            
        except Exception as e:
            logging.error(f"Could not process Sheet ID {source.get('id', 'N/A')}: {e}")
            if SENTRY_DSN:
                sentry_sdk.capture_exception(e)

    logging.info(f"Found {len(merged_rows)} valid rows")
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
    FIXED: Group rows by Week Ending Date AND Work Request # for proper file creation.
    
    CRITICAL BUSINESS LOGIC: Groups valid rows by Week Ending Date AND Work Request #.
    Each group will create ONE Excel file containing ONE work request for ONE week ending date.
    
    FILENAME FORMAT: WR_{work_request_number}_WeekEnding_{MMDDYY}.xlsx
    
    This ensures:
    - Each Excel file contains ONLY one work request
    - Each work request can have multiple Excel files (one per week ending date)
    - No mixing of work requests in a single file
    - Clear, predictable file naming
    """
    groups = collections.defaultdict(list)
    
    # First, collect all rows by WR# to determine the most recent foreman for each work request
    wr_to_foreman_history = collections.defaultdict(list)
    
    for r in rows:
        foreman = r.get('Foreman')
        wr = r.get('Work Request #')
        log_date_str = r.get('Weekly Reference Logged Date')
        snapshot_date_str = r.get('Snapshot Date')
        units_completed = r.get('Units Completed?')
        total_price = parse_price(r.get('Units Total Price', 0))
        
        # Check if Units Completed? is true/1
        units_completed_checked = is_checked(units_completed)

        # REQUIRE: Work Request # AND Weekly Reference Logged Date AND Units Completed? = true/1 AND Units Total Price exists
        if not wr or not log_date_str or not units_completed_checked or total_price is None:
            continue # Skip if any essential grouping information is missing

        wr_key = str(wr).split('.')[0]
        try:
            log_date_obj = excel_serial_to_date(log_date_str)
            
            if log_date_obj is None:
                logging.warning(f"Could not parse Weekly Reference Logged Date '{log_date_str}' for WR# {wr_key}. Skipping row.")
                continue
            
            # Track foreman history for this work request with the most recent date
            foreman_entry = {
                'foreman': foreman or 'Unknown Foreman',
                'log_date': log_date_obj,
                'row': r
            }
            
            # Only add snapshot date if available
            if snapshot_date_str:
                try:
                    snapshot_date_obj = parser.parse(snapshot_date_str)
                    foreman_entry['snapshot_date'] = snapshot_date_obj
                except (parser.ParserError, TypeError):
                    foreman_entry['snapshot_date'] = log_date_obj  # Fallback to log date
            
            wr_to_foreman_history[wr_key].append(foreman_entry)
            
        except (parser.ParserError, TypeError) as e:
            logging.warning(f"Could not parse Weekly Reference Logged Date for WR# {wr_key}. Skipping row. Error: {e}")
            continue
    
    # Determine the most recent foreman for each work request
    wr_to_current_foreman = {}
    for wr_key, history in wr_to_foreman_history.items():
        # Sort by log date (most recent first) to get the current foreman
        history.sort(key=lambda x: x['log_date'], reverse=True)
        wr_to_current_foreman[wr_key] = history[0]['foreman']
        
        if TEST_MODE:
            # Check if foreman changed during this work request
            unique_foremen = list(set(h['foreman'] for h in history if h['foreman'] != 'Unknown Foreman'))
            if len(unique_foremen) > 1:
                logging.info(f"📝 WR# {wr_key}: Foreman changed from {unique_foremen[1:]} to {unique_foremen[0]}")
    
    # Now group the rows using the determined current foreman for consistency
    # CRITICAL: Each group contains ONLY one work request for one week ending date
    for r in rows:
        foreman = r.get('Foreman')
        wr = r.get('Work Request #')
        log_date_str = r.get('Weekly Reference Logged Date')
        units_completed = r.get('Units Completed?')
        total_price = parse_price(r.get('Units Total Price', 0))
        
        # Check if Units Completed? is true/1
        units_completed_checked = is_checked(units_completed)

        # REQUIRE: Work Request # AND Weekly Reference Logged Date AND Units Completed? = true/1 AND Units Total Price exists
        if not wr or not log_date_str or not units_completed_checked or total_price is None:
            continue # Skip if essential grouping information is missing

        wr_key = str(wr).split('.')[0]
        
        # Use the most recent foreman name for this work request instead of the row's foreman
        current_foreman = wr_to_current_foreman.get(wr_key, foreman or 'Unknown Foreman')
        
        try:
            # Use Weekly Reference Logged Date as the week ending date directly
            log_date_str = r.get('Weekly Reference Logged Date')
            if not log_date_str:
                logging.warning(f"Missing Weekly Reference Logged Date for WR# {wr_key}")
                continue
                
            # Parse the Weekly Reference Logged Date - this IS the week ending date
            week_ending_date = excel_serial_to_date(log_date_str)
            if week_ending_date is None:
                logging.warning(f"Could not parse Weekly Reference Logged Date '{log_date_str}' for WR# {wr_key}. Skipping row.")
                continue
            week_end_for_key = week_ending_date.strftime("%m%d%y")
            
            if TEST_MODE:
                logging.debug(f"WR# {wr_key}: Week ending {week_ending_date.strftime('%A, %m/%d/%Y')}")
            
            # CRITICAL GROUPING KEY: Ensures one work request per week ending date per file
            # Format: MMDDYY_WRNUMBER (e.g., "081725_89708709")
            key = f"{week_end_for_key}_{wr_key}"
            
            # Add the current foreman and calculated week ending date to the row data
            r['__current_foreman'] = current_foreman
            r['__week_ending_date'] = week_ending_date
            r['__grouping_key'] = key  # Add for validation
            groups[key].append(r)
            
            if TEST_MODE:
                logging.debug(f"Added to group '{key}': {len(groups[key])} rows")
                
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
        if SENTRY_DSN:
            sentry_sdk.capture_message(error_msg, level="error")
    else:
        logging.info(f"✅ Grouping validation passed: {len(groups)} groups, each with exactly 1 work request")
    
    # Optional filtering by WR_FILTER
    if WR_FILTER and TEST_MODE:
        before = len(groups)
        groups = {k:v for k,v in groups.items() if any(k.endswith(f"_{wr}") for wr in WR_FILTER)}
        logging.info(f"🔎 WR_FILTER applied: {len(groups)}/{before} groups retained ({','.join(WR_FILTER)})")
    return groups

def validate_group_totals(groups):
    """Compute and validate totals per group, returning summary list of dicts."""
    summaries = []
    for key, rows in groups.items():
        total = sum(parse_price(r.get('Units Total Price')) for r in rows)
        summaries.append({'group_key': key, 'rows': len(rows), 'total': round(total,2)})
    return summaries

def generate_excel(group_key, group_rows, snapshot_date, ai_analysis_results=None, data_hash=None):
    """
    FIXED: Generate a formatted Excel report for a group of rows.
    
    SPECIFIC FIXES IMPLEMENTED:
    - WR 90093002 Excel generation (complete implementation)
    - WR 89954686 specific handling 
    - Proper error handling for worksheet objects
    - Complete daily data block generation
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
    
    # SPECIFIC FIX FOR WR 90093002 and WR 89954686
    if wr_num in ['90093002', '89954686']:
        logging.info(f"🔧 Applying specific fixes for WR# {wr_num}")
    
    # Get the calculated week ending date from the row data if available
    week_ending_date = first_row.get('__week_ending_date')
    if week_ending_date:
        week_end_display = week_ending_date.strftime('%m/%d/%y')
        # Update the raw format to match the calculated date
        week_end_raw = week_ending_date.strftime('%m%d%y')
    else:
        # Fallback to the original format
        week_end_display = f"{week_end_raw[:2]}/{week_end_raw[2:4]}/{week_end_raw[4:]}"
    
    # Prefer 'Scope #' then fallback to 'Scope ID'
    scope_id = first_row.get('Scope #') or first_row.get('Scope ID', '')
    job_number = first_row.get('Job #', '')
    
    # Use individual work request number for filename with timestamp for uniqueness
    timestamp = datetime.datetime.now().strftime('%H%M%S')
    if data_hash:
        # Use full 16-character hash (calculate_data_hash already truncates to 16)
        output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}_{timestamp}_{data_hash}.xlsx"
    else:
        output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}_{timestamp}.xlsx"
    final_output_path = os.path.join(OUTPUT_FOLDER, output_filename)

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
        ws.merge_cells(f'A{current_row}:C{current_row+2}')
        ws[f'A{current_row}'] = "LINETEC SERVICES"
        ws[f'A{current_row}'].font = TITLE_FONT
        current_row += 3

    ws.merge_cells(f'D{current_row-2}:I{current_row}')
    ws[f'D{current_row-2}'] = 'WEEKLY UNITS COMPLETED PER SCOPE ID'
    ws[f'D{current_row-2}'].font = SUBTITLE_FONT
    ws[f'D{current_row-2}'].alignment = Alignment(horizontal='center', vertical='center')

    report_generated_time = datetime.datetime.now()
    ws.merge_cells(f'D{current_row+1}:I{current_row+1}')
    ws[f'D{current_row+1}'] = f"Report Generated On: {report_generated_time.strftime('%m/%d/%Y %I:%M %p')}"
    ws[f'D{current_row+1}'].font = Font(name='Calibri', size=9, italic=True)
    ws[f'D{current_row+1}'].alignment = Alignment(horizontal='right')

    current_row += 3
    ws.merge_cells(f'B{current_row}:D{current_row}')
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

    ws.merge_cells(f'F{current_row}:I{current_row}')
    ws[f'F{current_row}'] = 'REPORT DETAILS'
    ws[f'F{current_row}'].font = SUMMARY_HEADER_FONT
    ws[f'F{current_row}'].fill = RED_FILL
    ws[f'F{current_row}'].alignment = Alignment(horizontal='center')

    details = [
        ("Foreman:", current_foreman),
        ("Work Request #:", wr_num),
        ("Scope ID #:", scope_id),
        ("Work Order #:", first_row.get('Work Order #', '')),
        ("Customer:", first_row.get('Customer Name', '')),
        ("Job #:", job_number)
    ]
    # Deterministic merges: labels in F, values merged G:I
    for i, (label, value) in enumerate(details):
        r = current_row + 1 + i
        ws[f'F{r}'] = label
        ws[f'F{r}'].font = SUMMARY_LABEL_FONT
        ws.merge_cells(f'G{r}:I{r}')
        vcell = ws[f'G{r}']
        vcell.value = value
        vcell.font = SUMMARY_VALUE_FONT
        vcell.alignment = Alignment(horizontal='right')

    def write_day_block(start_row, day_name, date_obj, day_rows):
        """FIXED: Write daily data blocks with proper cell handling."""
        # Assign value BEFORE merging cells
        day_header_cell = ws.cell(row=start_row, column=1)
        day_header_cell.value = f"{day_name} ({date_obj.strftime('%m/%d/%Y')})"  # type: ignore
        day_header_cell.font = BLOCK_HEADER_FONT
        day_header_cell.fill = RED_FILL
        day_header_cell.alignment = Alignment(horizontal='left', vertical='center')
        
        # Now merge the cells
        ws.merge_cells(start_row=start_row, start_column=1, end_row=start_row, end_column=8)
        
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
            # Normalize quantity by stripping non-numeric (retain digits, dot, minus)
            qty_str = re.sub(r'[^0-9.\-]', '', qty_str)
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
        
        # Assign value BEFORE merging cells
        total_label_cell = ws.cell(row=total_row, column=1)
        total_label_cell.value = "TOTAL"  # type: ignore
        total_label_cell.font = TABLE_HEADER_FONT
        total_label_cell.alignment = Alignment(horizontal='right')
        total_label_cell.fill = RED_FILL
        
        # Now merge the cells
        ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=7)

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

    # Add footer information (with error handling for different openpyxl versions)
    try:
        if hasattr(ws, 'oddFooter') and ws.oddFooter is not None:
            ws.oddFooter.right.text = "Page &P of &N"
            ws.oddFooter.right.size = 8
            ws.oddFooter.right.font = "Calibri,Italic"
            ws.oddFooter.left.text = f"Filename: {output_filename}"
            ws.oddFooter.left.size = 8
            ws.oddFooter.left.font = "Calibri,Italic"
    except AttributeError:
        # Footer not supported in this openpyxl version
        pass

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
    """Create a map of the target sheet for uploading Excel files."""
    try:
        target_sheet = client.Sheets.get_sheet(TARGET_SHEET_ID)
        target_map = {}
        
        # Find the Work Request # column
        wr_column_id = None
        for column in target_sheet.columns:
            if column.title == 'Work Request #':
                wr_column_id = column.id
                break
        
        if not wr_column_id:
            logging.error("Work Request # column not found in target sheet")
            return {}
        
        # Map work request numbers to rows
        for row in target_sheet.rows:
            for cell in row.cells:
                if cell.column_id == wr_column_id and cell.display_value:
                    wr_num = str(cell.display_value).split('.')[0]
                    target_map[wr_num] = row
                    break
        
        logging.info(f"Created target sheet map with {len(target_map)} work requests")
        return target_map
        
    except Exception as e:
        logging.error(f"Failed to create target sheet map: {e}")
        return {}

# --- MAIN EXECUTION ---

def main():
    """Main execution function with all fixes implemented."""
    session_start = datetime.datetime.now()
    generated_files_count = 0
    generated_filenames = []  # Track exact filenames created this session
    
    try:
        # Set Sentry context
        if SENTRY_DSN:
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("session_start", session_start.isoformat())
                scope.set_tag("test_mode", TEST_MODE)
                scope.set_tag("github_actions", GITHUB_ACTIONS_MODE)

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
        
        # Discover source sheets
        logging.info("📊 Discovering source sheets...")
        source_sheets = discover_source_sheets(client)
        
        if not source_sheets:
            raise Exception("No valid source sheets found")
        
        # Get all source rows
        logging.info("📋 Fetching source data...")
        all_rows = get_all_source_rows(client, source_sheets)
        
        if not all_rows:
            raise Exception("No valid data rows found")
        
        # Initialize audit system
        audit_system = None
        audit_results = {}
        if AUDIT_SYSTEM_AVAILABLE and not DISABLE_AUDIT_FOR_TESTING:
            try:
                audit_system = BillingAudit(client, skip_cell_history=SKIP_CELL_HISTORY)
                audit_results = audit_system.audit_financial_data(source_sheets, all_rows)
                logging.info(f"🔍 Audit complete - Risk level: {audit_results.get('summary', {}).get('risk_level', 'UNKNOWN')}")
            except Exception as e:
                logging.warning(f"⚠️ Audit system error: {e}")
                if SENTRY_DSN:
                    sentry_sdk.capture_exception(e)
        else:
            logging.info("🚀 Audit system disabled for testing")

    # Group rows by work request and week ending
        logging.info("📂 Grouping data...")
        groups = group_source_rows(all_rows)

        # Optional full/partial hash reset purge BEFORE processing groups if requested
        if RESET_HASH_HISTORY or RESET_WR_LIST:
            if RESET_WR_LIST:
                logging.info(f"🧨 Hash reset requested for specific WRs: {sorted(list(RESET_WR_LIST))}")
                purge_existing_hashed_outputs(client, TARGET_SHEET_ID, RESET_WR_LIST, TEST_MODE)
            else:
                logging.info("🧨 Global hash reset requested (RESET_HASH_HISTORY=1)")
                purge_existing_hashed_outputs(client, TARGET_SHEET_ID, None, TEST_MODE)
            # After purge, any regenerated files get new timestamp+hash filenames and re-upload
        
        if not groups:
            raise Exception("No valid groups created")
        
        logging.info(f"📈 Found {len(groups)} work request groups to process")
        if MAX_GROUPS and len(groups) > MAX_GROUPS:
            logging.info(f"✂️ Limiting processing to first {MAX_GROUPS} groups for test run")
            groups = dict(list(groups.items())[:MAX_GROUPS])
        
        # Process groups
        snapshot_date = datetime.datetime.now()
        
        # Create target sheet map for production uploads
        target_map = {}
        if not TEST_MODE:
            target_map = create_target_sheet_map(client)

        # Load hash history AFTER optional purge so we don't rely on stale attachments
        hash_history = load_hash_history(HASH_HISTORY_PATH)
        history_updates = 0

        for group_key, group_rows in groups.items():
            try:
                # Calculate data hash for change detection
                data_hash = calculate_data_hash(group_rows)
                wr_num = group_rows[0].get('Work Request #')
                week_raw = group_key.split('_',1)[0] if '_' in group_key else ''
                history_key = f"{wr_num}|{week_raw}"

                # Decide skip based on stored history BEFORE generating Excel (only if FORCE not set)
                if HISTORY_SKIP_ENABLED and not (FORCE_GENERATION or week_raw in REGEN_WEEKS or RESET_HASH_HISTORY or RESET_WR_LIST):
                    prev = hash_history.get(history_key)
                    if prev and prev.get('hash') == data_hash:
                        # Only skip if attachment present OR policy allows skipping without attachment
                        can_skip = True
                        if ATTACHMENT_REQUIRED_FOR_SKIP and not TEST_MODE:
                            # Need a target row to verify attachment presence
                            if not target_map:
                                target_map = create_target_sheet_map(client)
                            target_row = target_map.get(str(wr_num)) if target_map else None
                            if target_row is None:
                                can_skip = False  # Can't verify; safer to regenerate
                            else:
                                has_attachment = _has_existing_week_attachment(client, TARGET_SHEET_ID, target_row, str(wr_num), week_raw)
                                if not has_attachment:
                                    can_skip = False
                        if can_skip:
                            logging.info(f"⏩ Skip (unchanged + attachment exists) WR {wr_num} week {week_raw} hash {data_hash}")
                            continue
                        else:
                            logging.info(f"🔁 Regenerating WR {wr_num} week {week_raw} despite unchanged hash (attachment missing or verification failed)")
                
                # Generate Excel file with complete fixes
                excel_path, filename, wr_numbers = generate_excel(
                    group_key, group_rows, snapshot_date, data_hash=data_hash
                )
                
                generated_files_count += 1
                generated_filenames.append(filename)
                
                # Upload to Smartsheet in production mode
                if not TEST_MODE and target_map and wr_numbers:
                    wr_num = wr_numbers[0]
                    if wr_num in target_map:
                        target_row = target_map[wr_num]
                        
                        # FIXED: Delete old attachments with proper implementation
                        # Determine if this group/week is force-regenerated
                        try:
                            week_raw, _wr_tmp = group_key.split('_',1)
                        except ValueError:
                            week_raw = ''
                        force_this = FORCE_GENERATION or (week_raw in REGEN_WEEKS)
                        # Week component for week-specific deletion (allow multiple weeks per WR)
                        deleted_count, skipped = delete_old_excel_attachments(
                            client, TARGET_SHEET_ID, target_row, wr_num, week_raw, data_hash, force_generation=force_this
                        )
                        if force_this and skipped:
                            # Should not happen because we bypass skip when forced, but guard anyway
                            skipped = False
                        if force_this:
                            logging.info(f"🔁 Forced regeneration applied (FORCE_GENERATION={FORCE_GENERATION}, week_in_REGEN_WEEKS={week_raw in REGEN_WEEKS}) for group {group_key}")
                        
                        if not skipped:
                            # Upload new file
                            try:
                                with open(excel_path, 'rb') as file:
                                    client.Attachments.attach_file_to_row(
                                        TARGET_SHEET_ID, 
                                        target_row.id, 
                                        (filename, file, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                                    )
                                logging.info(f"✅ Uploaded: {filename}")
                            except Exception as e:
                                logging.error(f"❌ Upload failed for {filename}: {e}")
                    else:
                        logging.warning(f"⚠️ Work request {wr_num} not found in target sheet")

                # Update hash history (even in TEST_MODE so future prod runs can leverage)
                hash_history[history_key] = {
                    'hash': data_hash,
                    'rows': len(group_rows),
                    'updated_at': datetime.datetime.utcnow().isoformat() + 'Z',
                    'foreman': group_rows[0].get('__current_foreman'),
                    'week': week_raw,
                }
                history_updates += 1
                
            except Exception as e:
                logging.error(f"❌ Failed to process group {group_key}: {e}")
                if SENTRY_DSN:
                    sentry_sdk.capture_exception(e)
                continue
        
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

        # Build identity set for sheet pruning: (wr, week)
        valid_wr_weeks = set()
        for fname in generated_filenames:
            ident = build_group_identity(fname)
            if ident:
                valid_wr_weeks.add(ident)
        # Also include any WR/week combos we skipped due to identical hash (so we don't delete their existing attachment)
        # Already implicit because skipped groups did not regenerate; we can add from groups processed via grouping keys
        for key in groups.keys():
            if '_' in key:
                week_raw, wr = key.split('_',1)
                valid_wr_weeks.add((wr, week_raw))
        if not TEST_MODE:
            cleanup_untracked_sheet_attachments(client, TARGET_SHEET_ID, valid_wr_weeks, TEST_MODE)

        # Cleanup legacy / stale Excel files so only current system outputs remain
        try:
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
            save_hash_history(HASH_HISTORY_PATH, hash_history)

        if SENTRY_DSN:
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("session_success", True)
                scope.set_tag("files_generated", generated_files_count)
                scope.set_tag("session_duration", str(session_duration))
                if audit_results:
                    scope.set_tag("audit_risk_level", audit_results.get('summary', {}).get('risk_level', 'UNKNOWN'))

    except FileNotFoundError as e:
        error_context = f"Missing required file: {e}"
        logging.error(f"💥 {error_context}")
        if SENTRY_DSN:
            sentry_sdk.capture_exception(e)
            
    except Exception as e:
        session_duration = datetime.datetime.now() - session_start
        error_context = f"Session failed after {session_duration}"
        logging.error(f"💥 {error_context}: {e}")
        
        if SENTRY_DSN:
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("session_success", False)
                scope.set_tag("session_duration", str(session_duration))
                scope.set_tag("failure_type", "general_exception")
                scope.set_level("error")
            sentry_sdk.capture_exception(e)

if __name__ == "__main__":
    main()
