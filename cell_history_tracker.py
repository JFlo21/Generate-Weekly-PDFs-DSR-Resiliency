#!/usr/bin/env python3
"""
Cell History Tracker Module
Tracks changes to "Modified By" column for each row in Smartsheet to differentiate 
Excel generation from direct Smartsheet modifications.
"""

import os
import json
import logging
import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict


class CellHistoryTracker:
    """
    Tracks cell modification history for "Modified By" column on each sheet.
    Offloads tracking data to a JSON file for audit and analysis purposes.
    """
    
    def __init__(self, client, output_folder: str = "generated_docs"):
        """
        Initialize the cell history tracker.
        
        Args:
            client: Smartsheet client instance
            output_folder: Folder to store the cell history JSON file
        """
        self.client = client
        self.output_folder = output_folder
        self.history_file = os.path.join(output_folder, "cell_history.json")
        self.logger = logging.getLogger(__name__)
        
        # Ensure output folder exists
        os.makedirs(output_folder, exist_ok=True)
        
        # Load existing history
        self.history_data = self._load_history()
        
        self.logger.info("📝 Cell History Tracker initialized")
    
    def _load_history(self) -> Dict:
        """Load existing cell history from JSON file."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                    self.logger.info(f"✅ Loaded existing cell history with {len(data.get('sheets', {}))} sheets")
                    return data
        except Exception as e:
            self.logger.warning(f"⚠️ Could not load cell history: {e}")
        
        return {
            "last_updated": None,
            "sheets": {},  # sheet_id -> row tracking data
            "summary": {
                "total_sheets_tracked": 0,
                "total_rows_tracked": 0,
                "total_modifications_tracked": 0
            }
        }
    
    def _save_history(self):
        """Save cell history to JSON file."""
        try:
            # Update summary statistics
            self.history_data["last_updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.history_data["summary"]["total_sheets_tracked"] = len(self.history_data["sheets"])
            
            total_rows = 0
            total_mods = 0
            for sheet_data in self.history_data["sheets"].values():
                total_rows += len(sheet_data.get("rows", {}))
                for row_data in sheet_data.get("rows", {}).values():
                    total_mods += len(row_data.get("history", []))
            
            self.history_data["summary"]["total_rows_tracked"] = total_rows
            self.history_data["summary"]["total_modifications_tracked"] = total_mods
            
            with open(self.history_file, 'w') as f:
                json.dump(self.history_data, f, indent=2, default=str)
            
            self.logger.info(f"💾 Cell history saved to {self.history_file}")
            self.logger.info(f"   Sheets: {total_rows}, Rows: {total_rows}, Modifications: {total_mods}")
        except Exception as e:
            self.logger.error(f"❌ Failed to save cell history: {e}")
    
    def track_modified_by_column(self, source_sheets: List[Dict], rows: List[Dict]) -> Dict:
        """
        Track "Modified By" column history for rows across all source sheets.
        
        Args:
            source_sheets: List of source sheet configurations with column mappings
            rows: List of row data dictionaries with __sheet_id and __row_id metadata
            
        Returns:
            Dictionary containing tracking results and statistics
        """
        tracking_start = datetime.datetime.now(datetime.timezone.utc)
        
        results = {
            "tracking_timestamp": tracking_start.isoformat(),
            "sheets_processed": 0,
            "rows_processed": 0,
            "history_entries_added": 0,
            "errors": []
        }
        
        # Build sheet ID to column mapping lookup
        sheet_column_map = {}
        for sheet in source_sheets:
            sheet_id = sheet['id']
            col_mapping = sheet.get('column_mapping', {})
            
            # Check if this sheet has a "Modified By" column mapped
            if 'Modified By' in col_mapping:
                sheet_column_map[sheet_id] = {
                    'modified_by_column_id': col_mapping['Modified By'],
                    'sheet_name': sheet['name']
                }
        
        if not sheet_column_map:
            self.logger.info("ℹ️ No sheets have 'Modified By' column mapped - skipping cell history tracking")
            return results
        
        # Group rows by sheet ID for efficient processing
        rows_by_sheet = defaultdict(list)
        for row in rows:
            sheet_id = row.get('__sheet_id')
            row_id = row.get('__row_id')
            wr_num = row.get('Work Request #')
            
            if sheet_id and row_id and sheet_id in sheet_column_map:
                rows_by_sheet[sheet_id].append({
                    'row_id': row_id,
                    'work_request': wr_num,
                    'row_data': row
                })
        
        # Process each sheet
        for sheet_id, sheet_rows in rows_by_sheet.items():
            try:
                sheet_info = sheet_column_map[sheet_id]
                modified_by_col_id = sheet_info['modified_by_column_id']
                sheet_name = sheet_info['sheet_name']
                
                self.logger.info(f"📊 Processing sheet: {sheet_name} (ID: {sheet_id}) - {len(sheet_rows)} rows")
                
                # Initialize sheet tracking data if needed
                sheet_key = str(sheet_id)
                if sheet_key not in self.history_data["sheets"]:
                    self.history_data["sheets"][sheet_key] = {
                        "sheet_id": sheet_id,
                        "sheet_name": sheet_name,
                        "rows": {}
                    }
                
                # Fetch cell history for each row
                for row_info in sheet_rows:
                    row_id = row_info['row_id']
                    wr_num = row_info['work_request']
                    
                    try:
                        # Fetch cell history for "Modified By" column
                        history = self._fetch_cell_history(
                            sheet_id, 
                            row_id, 
                            modified_by_col_id
                        )
                        
                        if history:
                            # Store history data
                            row_key = str(row_id)
                            if row_key not in self.history_data["sheets"][sheet_key]["rows"]:
                                self.history_data["sheets"][sheet_key]["rows"][row_key] = {
                                    "row_id": row_id,
                                    "work_request": wr_num,
                                    "history": []
                                }
                            
                            # Add new history entries
                            self.history_data["sheets"][sheet_key]["rows"][row_key]["history"] = history
                            results["history_entries_added"] += len(history)
                            results["rows_processed"] += 1
                        
                    except Exception as e:
                        error_msg = f"Error fetching history for row {row_id} in sheet {sheet_id}: {e}"
                        self.logger.warning(f"⚠️ {error_msg}")
                        results["errors"].append(error_msg)
                
                results["sheets_processed"] += 1
                
            except Exception as e:
                error_msg = f"Error processing sheet {sheet_id}: {e}"
                self.logger.error(f"❌ {error_msg}")
                results["errors"].append(error_msg)
        
        # Save updated history
        self._save_history()
        
        # Log summary
        self.logger.info(f"✅ Cell history tracking complete:")
        self.logger.info(f"   Sheets processed: {results['sheets_processed']}")
        self.logger.info(f"   Rows processed: {results['rows_processed']}")
        self.logger.info(f"   History entries added: {results['history_entries_added']}")
        if results["errors"]:
            self.logger.warning(f"   Errors encountered: {len(results['errors'])}")
        
        return results
    
    def _fetch_cell_history(self, sheet_id: int, row_id: int, column_id: int) -> List[Dict]:
        """
        Fetch cell history for a specific cell.
        
        Args:
            sheet_id: Smartsheet sheet ID
            row_id: Row ID
            column_id: Column ID
            
        Returns:
            List of history entries with modification details
        """
        try:
            # Use Smartsheet SDK to get cell history
            # The get_cell_history method is available through client.Cells
            response = self.client.Cells.get_cell_history(
                sheet_id=sheet_id,
                row_id=row_id,
                column_id=column_id,
                include_all=True
            )
            
            history_entries = []
            
            if hasattr(response, 'data') and response.data:
                for cell_history_item in response.data:
                    entry = {
                        "modified_at": getattr(cell_history_item, 'modified_at', None),
                        "modified_by": self._extract_modified_by(cell_history_item),
                        "value": getattr(cell_history_item, 'display_value', None) or getattr(cell_history_item, 'value', None)
                    }
                    
                    # Convert datetime to ISO string if present
                    if entry["modified_at"] and hasattr(entry["modified_at"], 'isoformat'):
                        entry["modified_at"] = entry["modified_at"].isoformat()
                    
                    history_entries.append(entry)
            
            return history_entries
            
        except Exception as e:
            # Don't log individual cell fetch errors as warnings - they're expected for some cells
            self.logger.debug(f"Could not fetch cell history for sheet {sheet_id}, row {row_id}, column {column_id}: {e}")
            return []
    
    def _extract_modified_by(self, cell_history_item) -> Optional[str]:
        """Extract the modified_by information from cell history item."""
        try:
            # The modified_by could be in different formats
            modified_by = getattr(cell_history_item, 'modified_by', None)
            
            if modified_by:
                # If it's a user object, extract the name or email
                if hasattr(modified_by, 'name'):
                    return modified_by.name
                elif hasattr(modified_by, 'email'):
                    return modified_by.email
                elif isinstance(modified_by, str):
                    return modified_by
                else:
                    return str(modified_by)
            
            return None
        except Exception:
            return None
    
    def get_history_summary(self) -> Dict:
        """Get a summary of tracked cell history."""
        return {
            "last_updated": self.history_data.get("last_updated"),
            "summary": self.history_data.get("summary", {}),
            "sheets_tracked": list(self.history_data.get("sheets", {}).keys())
        }
    
    def get_row_history(self, sheet_id: int, row_id: int) -> Optional[Dict]:
        """
        Get history for a specific row.
        
        Args:
            sheet_id: Sheet ID
            row_id: Row ID
            
        Returns:
            Row history data or None if not found
        """
        sheet_key = str(sheet_id)
        row_key = str(row_id)
        
        if sheet_key in self.history_data["sheets"]:
            return self.history_data["sheets"][sheet_key]["rows"].get(row_key)
        
        return None
