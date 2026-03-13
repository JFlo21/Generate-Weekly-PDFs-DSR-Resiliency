"""Smartsheet API client wrapper for folder sync operations.

Provides a thin abstraction over the smartsheet-python-sdk for
listing sheets in folders, reading rows, and adding rows in batches.
"""

import logging
import os
import smartsheet

logger = logging.getLogger('smartsheet_client')

# Maximum rows per Smartsheet API add_rows call
MAX_ROWS_PER_BATCH = 500


def create_client(token=None):
    """Create an authenticated Smartsheet client.

    Parameters:
        token (str): Smartsheet API token. Falls back to the
            ``SMARTSHEET_API_TOKEN`` environment variable.

    Returns:
        smartsheet.Smartsheet: Configured client instance.

    Raises:
        ValueError: If no token is provided or found in the environment.
    """
    token = token or os.getenv('SMARTSHEET_API_TOKEN')
    if not token:
        raise ValueError(
            "Smartsheet API token required. Set SMARTSHEET_API_TOKEN or "
            "pass token= explicitly."
        )
    client = smartsheet.Smartsheet(token)
    client.errors_as_exceptions(True)
    return client


def list_folder_sheets(client, folder_id):
    """Return a list of sheet summary dicts for every sheet in *folder_id*.

    Parameters:
        client: Authenticated Smartsheet client.
        folder_id (int): Smartsheet folder ID.

    Returns:
        list[dict]: Each dict has keys ``id``, ``name``, and ``row_count``.
    """
    logger.info("Listing sheets in folder %s", folder_id)
    folder = client.Folders.get_folder(folder_id)
    sheets = []
    if hasattr(folder, 'sheets') and folder.sheets:
        for s in folder.sheets:
            sheets.append({
                'id': s.id,
                'name': s.name,
                'row_count': getattr(s, 'total_row_count', 0) or 0,
            })
    logger.info("Found %d sheets in folder %s", len(sheets), folder_id)
    return sheets


def get_sheet(client, sheet_id):
    """Fetch a full sheet (metadata + rows).

    Parameters:
        client: Authenticated Smartsheet client.
        sheet_id (int): Smartsheet sheet ID.

    Returns:
        smartsheet.models.Sheet: The sheet object.
    """
    sheet = client.Sheets.get_sheet(sheet_id)
    col_names = [c.title.lower() for c in sheet.columns]
    logger.info(
        "Sheet %s actual columns: %s",
        sheet_id,
        col_names,
    )
    return sheet


def get_column_map(sheet):
    """Build a case-insensitive column-name -> column-id mapping.

    Parameters:
        sheet: A Smartsheet sheet object.

    Returns:
        dict[str, int]: Lowercase column title to column ID.
    """
    return {c.title.lower(): c.id for c in sheet.columns}


def add_rows_batched(client, sheet_id, rows):
    """Add *rows* to a sheet in batches of up to 500.

    Batch failures are logged and counted but do **not** halt
    processing of remaining batches.  This allows partial progress
    when transient Smartsheet API errors occur (e.g. rate limits,
    temporary network issues).

    Parameters:
        client: Authenticated Smartsheet client.
        sheet_id (int): Target sheet ID.
        rows (list): Smartsheet Row objects to add.

    Returns:
        tuple[int, int]: (success_count, failure_count).
    """
    total = len(rows)
    added = 0
    failed = 0
    for i in range(0, total, MAX_ROWS_PER_BATCH):
        batch = rows[i:i + MAX_ROWS_PER_BATCH]
        try:
            client.Sheets.add_rows(sheet_id, batch)
            added += len(batch)
        except Exception:
            logger.exception(
                "Failed to add batch %d–%d to sheet %s",
                i, i + len(batch), sheet_id,
            )
            failed += len(batch)
    logger.info("Added %d/%d rows to sheet %s", added, total, sheet_id)
    return added, failed
