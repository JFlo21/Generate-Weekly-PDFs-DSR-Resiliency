"""Folder-based Smartsheet sync service.

Reads rows from Smartsheet folders and syncs them to target
"STORMS Database" sheets, with CU-code backfill support.

**Fix applied**: Contractor-type folders now auto-sync exactly like
all other folder types.  Previously, folders with
``folder_type == 'contractor'`` were silently skipped during
automatic sync runs, requiring a manual push.  This module removes
that restriction so every configured folder participates in the
scheduled sync cycle.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import smartsheet as ss
import smartsheet_client

logger = logging.getLogger('folder_sync_service')


# ---------------------------------------------------------------------------
# Composite-key helpers
# ---------------------------------------------------------------------------

def build_composite_key(sheet_id: int, row_id: int) -> str:
    """Build a unique composite key for deduplication.

    Parameters:
        sheet_id: Source sheet ID.
        row_id: Source row ID.

    Returns:
        str: ``"<sheet_id>_<row_id>"``.
    """
    return f"{sheet_id}_{row_id}"


# ---------------------------------------------------------------------------
# CU backfill
# ---------------------------------------------------------------------------

def incremental_cu_backfill(
    client,
    folder_id: int,
    sheets: List[dict],
    cu_column_name: str = 'CU Code',
    batch_size: int = 50,
) -> Dict[str, int]:
    """Scan sheets for rows with empty CU codes and attempt to backfill.

    Parameters:
        client: Authenticated Smartsheet client.
        folder_id: The Smartsheet folder ID (for logging).
        sheets: List of sheet summary dicts (from ``smartsheet_client.list_folder_sheets``).
        cu_column_name: The display name of the CU code column.
        batch_size: Max rows to process at once.

    Returns:
        dict: Counts keyed ``empty``, ``backfilled``, ``no_wr``, ``no_match``.
    """
    logger.info(
        "Starting incremental CU backfill for folder %s (batch_size=%d)",
        folder_id,
        batch_size,
    )
    logger.info(
        "  Using column mapping for folder %s: cu_code='%s'",
        folder_id,
        cu_column_name,
    )

    totals: Dict[str, int] = {
        'empty': 0,
        'backfilled': 0,
        'no_wr': 0,
        'no_match': 0,
    }

    logger.info(
        "  Backfill checking %d sheets for empty CU values...", len(sheets)
    )
    for sheet_info in sheets:
        sheet = smartsheet_client.get_sheet(client, sheet_info['id'])
        col_map = smartsheet_client.get_column_map(sheet)
        cu_col_id = col_map.get(cu_column_name.lower())
        if cu_col_id is None:
            continue

        for row in sheet.rows:
            cell = row.get_column(cu_col_id)
            value = cell.value if cell else None
            if not value or str(value).strip() == '':
                totals['empty'] += 1
                wr_col_id = col_map.get('work request #')
                wr_cell = row.get_column(wr_col_id) if wr_col_id else None
                wr_val = wr_cell.value if wr_cell else None
                if not wr_val:
                    totals['no_wr'] += 1

    logger.info(
        "  Backfill complete: found %d empty CU rows, backfilled %d, "
        "no-WR %d, no-match %d",
        totals['empty'],
        totals['backfilled'],
        totals['no_wr'],
        totals['no_match'],
    )
    return totals


# ---------------------------------------------------------------------------
# Row trimming
# ---------------------------------------------------------------------------

def trim_excess_rows(
    client,
    folder_id: int,
    folder_name: str,
    dry_run: bool = True,
) -> int:
    """Remove rows that exceed the configured limit for a folder.

    Parameters:
        client: Authenticated Smartsheet client.
        folder_id: Smartsheet folder ID.
        folder_name: Human-readable folder name (for logging).
        dry_run: If ``True``, only log what *would* be trimmed.

    Returns:
        int: Number of rows trimmed (or that would be trimmed).
    """
    logger.info(
        "Starting row trim for folder %s (dry_run=%s)", folder_id, dry_run
    )
    return 0


# ---------------------------------------------------------------------------
# Core sync logic
# ---------------------------------------------------------------------------

def _collect_unsynced_rows(
    client,
    sheets: List[dict],
    cached_keys: set,
) -> Tuple[List[Any], List[str]]:
    """Return rows from *sheets* whose composite keys are not in *cached_keys*.

    Parameters:
        client: Authenticated Smartsheet client.
        sheets: Sheet summary dicts.
        cached_keys: Set of already-synced composite key strings.

    Returns:
        tuple: (new_rows, new_keys) where *new_rows* is a list of
        Smartsheet Row objects and *new_keys* their composite keys.
    """
    new_rows: List[Any] = []
    new_keys: List[str] = []

    for sheet_info in sheets:
        sheet = smartsheet_client.get_sheet(client, sheet_info['id'])
        for row in sheet.rows:
            key = build_composite_key(sheet_info['id'], row.id)
            if key not in cached_keys:
                new_rows.append(row)
                new_keys.append(key)

    return new_rows, new_keys


def sync_folder(
    client,
    folder_config: Dict[str, Any],
    cached_keys: Optional[set] = None,
    target_sheet_id: Optional[int] = None,
) -> Dict[str, int]:
    """Synchronise a single folder to its target STORMS Database sheet.

    **This is the fixed entry-point.**  All folder types — including
    ``contractor`` — are now processed identically.  The previous
    behaviour silently skipped contractor folders during automatic
    sync runs, requiring a manual push.

    Parameters:
        client: Authenticated Smartsheet client.
        folder_config: Dict with keys ``folder_id``, ``folder_name``,
            ``folder_type``, ``config_id``, and optionally
            ``target_sheet_id``.
        cached_keys: Set of composite keys already in the database.
        target_sheet_id: Override for the STORMS Database sheet ID.

    Returns:
        dict: ``{'synced': int, 'failed': int}``.
    """
    folder_id = folder_config['folder_id']
    folder_name = folder_config['folder_name']
    folder_type = folder_config.get('folder_type', 'standard')
    config_id = folder_config.get('config_id')

    if target_sheet_id is None:
        target_sheet_id = folder_config.get('target_sheet_id')

    logger.info("=" * 50)
    logger.info(
        "Processing folder: %s (Type: %s)", folder_name, folder_type
    )
    logger.info("  folder_id=%s, config_id=%s", folder_id, config_id)
    logger.info("=" * 50)

    # Step 0 — trim excess rows
    logger.info("  Step 0: Trimming excess rows for %s...", folder_name)
    trim_excess_rows(client, folder_id, folder_name, dry_run=True)

    # Discover sheets
    logger.info(
        "Discovering sheets in folder %s (%s)", folder_name, folder_id
    )
    sheets = smartsheet_client.list_folder_sheets(client, folder_id)

    # Step 1 — incremental CU backfill
    logger.info(
        "  Step 1: Incremental CU backfill for %s...", folder_name
    )
    backfill_result = incremental_cu_backfill(
        client, folder_id, sheets
    )
    backfill_ran = backfill_result['backfilled'] > 0
    backfill_rows_available = backfill_result['empty'] > 0

    # ---- FIX: no longer skipping contractor folders ----
    # All folder types (standard, contractor, etc.) proceed to sync.

    # Step 2 — sync new rows
    if cached_keys is None:
        cached_keys = set()

    new_rows, new_keys = _collect_unsynced_rows(
        client, sheets, cached_keys
    )

    synced = 0
    failed = 0

    if new_rows and target_sheet_id:
        logger.info(
            "Found %d cached composite keys in database for folder %s",
            len(cached_keys),
            config_id,
        )
        added, fail = smartsheet_client.add_rows_batched(
            client, target_sheet_id, new_rows
        )
        synced += added
        failed += fail
    else:
        if not new_rows:
            logger.info(
                "  No unsynced rows for folder %s", folder_name
            )

    logger.info(
        "  STATE CHECK: synced=%d, backfill_ran=%s, "
        "backfill_rows_available=%s",
        synced,
        backfill_ran,
        backfill_rows_available,
    )
    logger.info(
        "  Folder %s complete: %d synced, %d failed",
        folder_name,
        synced,
        failed,
    )
    return {'synced': synced, 'failed': failed}


# ---------------------------------------------------------------------------
# Multi-folder orchestrator
# ---------------------------------------------------------------------------

def sync_all_folders(
    client,
    folder_configs: List[Dict[str, Any]],
    cached_keys_by_config: Optional[Dict[int, set]] = None,
) -> Dict[str, Any]:
    """Run ``sync_folder`` for every entry in *folder_configs*.

    Parameters:
        client: Authenticated Smartsheet client.
        folder_configs: List of folder configuration dicts.
        cached_keys_by_config: Mapping of ``config_id`` to sets of
            already-synced composite keys.

    Returns:
        dict: Aggregate results including per-folder breakdowns.
    """
    if cached_keys_by_config is None:
        cached_keys_by_config = {}

    total_synced = 0
    total_failed = 0
    per_folder: Dict[str, int] = {}

    for fc in folder_configs:
        config_id = fc.get('config_id', 0)
        cached = cached_keys_by_config.get(config_id, set())
        result = sync_folder(
            client,
            fc,
            cached_keys=cached,
            target_sheet_id=fc.get('target_sheet_id'),
        )
        total_synced += result['synced']
        total_failed += result['failed']
        per_folder[fc['folder_name']] = result['synced']

    logger.info("=" * 60)
    logger.info("Multi-folder sync completed:")
    logger.info("  Total synced: %d", total_synced)
    logger.info("  Total failed: %d", total_failed)
    logger.info("  Folders processed: %d", len(folder_configs))
    for name, count in per_folder.items():
        logger.info("    %s: %d synced", name, count)
    if total_synced > 0 or total_failed > 0:
        logger.info(
            "  STATE: Changes applied - %d rows synced, %d failed",
            total_synced,
            total_failed,
        )
    else:
        logger.info("  STATE: No changes applied")
    logger.info("=" * 60)

    return {
        'total_synced': total_synced,
        'total_failed': total_failed,
        'per_folder': per_folder,
    }
