import os
import datetime
import json
import logging
import time
from dateutil import parser
import smartsheet
from smartsheet.models import Row as SSRow, Cell as SSCell
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- AUDIT CONFIG ---
AUDIT_ENABLED = True
AUDIT_SHEET_ID = None  # Will be set from environment variable or config
TRACK_COLUMNS = ['Quantity', 'Redlined Total Price']  # which columns to watch
OUTPUT_FOLDER = "generated_docs"
RUN_STATE_PATH = os.path.join(OUTPUT_FOLDER, 'audit_state.json')  # remembers last run
MAX_ROWS_PER_RUN = 50  # Limit for safety - prevents overwhelming API on first run

class BillingAudit:
    """
    Billing Report Audit System
    
    Tracks changes to critical billing columns (Quantity, Redlined Total Price) 
    across all source sheets and logs them to a dedicated Smartsheet audit log.
    """
    
    def __init__(self, client, audit_sheet_id=None):
        """
        Initialize the audit system.
        
        Args:
            client: Smartsheet client instance
            audit_sheet_id: Sheet ID for the audit log (optional, will use env var if not provided)
        """
        self.client = client
        self.audit_sheet_id = audit_sheet_id or os.getenv("AUDIT_SHEET_ID")
        
        if not self.audit_sheet_id:
            logging.warning("⚠️ AUDIT_SHEET_ID not set. Audit functionality disabled.")
            self.enabled = False
        else:
            self.enabled = AUDIT_ENABLED
            logging.info(f"🔍 Audit system initialized for sheet ID: {self.audit_sheet_id}")
    
    def load_last_run_timestamp(self):
        """Load the timestamp of the last audit run from state file."""
        try:
            with open(RUN_STATE_PATH, 'r') as f:
                data = json.load(f)
            last_run_str = data.get('last_run')
            if last_run_str:
                return parser.parse(last_run_str)
        except Exception as e:
            logging.info(f"No previous audit run found or error loading state: {e}")
        return None  # first run
    
    def save_last_run_timestamp(self, timestamp):
        """Save the timestamp of the current audit run to state file."""
        try:
            os.makedirs(OUTPUT_FOLDER, exist_ok=True)
            with open(RUN_STATE_PATH, 'w') as f:
                json.dump({'last_run': timestamp.isoformat()}, f)
            logging.info(f"💾 Saved audit state: {timestamp.isoformat()}")
        except Exception as e:
            logging.error(f"❌ Failed to save audit state: {e}")
    
    def build_column_map_for_sheet(self, sheet_id):
        """Build a mapping of column titles to column IDs for a sheet."""
        try:
            sheet = self.client.Sheets.get_sheet(sheet_id)
            return {column.title: column.id for column in sheet.columns}
        except Exception as e:
            logging.error(f"❌ Failed to build column map for sheet {sheet_id}: {e}")
            return {}
    
    def fetch_cell_history(self, sheet_id, row_id, column_id):
        """
        Fetch the change history for a specific cell.
        
        Returns a list of revisions (oldest to newest) with keys:
        - value: the cell value
        - display_value: formatted display value
        - modified_at: datetime when changed
        - modified_by_name: name of user who made the change
        - modified_by_email: email of user who made the change
        """
        try:
            # Add rate limiting - wait 0.5 seconds between API calls
            time.sleep(0.5)
            
            # Try different SDK methods for cell history
            try:
                resp = self.client.Cells.list_cell_history(sheet_id, row_id, column_id, include_all=True)
                history = resp.data
            except AttributeError:
                # Some SDK versions use get_cell_history
                resp = self.client.Cells.get_cell_history(sheet_id, row_id, column_id, include_all=True)
                history = resp.data if hasattr(resp, 'data') else resp
            
            parsed_history = []
            for h in history:
                # Robust access across different SDK versions
                modified_by = getattr(h, 'modified_by', None)
                mod_name = getattr(modified_by, 'name', None) if modified_by else None
                mod_email = getattr(modified_by, 'email', None) if modified_by else None
                
                # Handle different timestamp attribute names
                mod_at = getattr(h, 'modified_at', None) or getattr(h, 'modifiedAt', None)
                if isinstance(mod_at, str):
                    mod_at = parser.parse(mod_at)
                
                parsed_history.append({
                    'value': getattr(h, 'value', None),
                    'display_value': getattr(h, 'display_value', None) or getattr(h, 'displayValue', None),
                    'modified_at': mod_at,
                    'modified_by_name': mod_name,
                    'modified_by_email': mod_email
                })
            
            # Sort oldest to newest (ensure consistent ordering)
            parsed_history.sort(key=lambda x: x['modified_at'] or datetime.datetime.min)
            return parsed_history
            
        except Exception as e:
            logging.warning(f"⚠️ Failed to fetch cell history for sheet {sheet_id}, row {row_id}, column {column_id}: {e}")
            return []
    
    def coerce_number(self, value, column_title):
        """Convert a value to a number appropriate for the column type."""
        if value is None:
            return None
        
        if column_title == 'Redlined Total Price':
            # Use the same price parsing logic as the main generator
            return self.parse_price(value)
        elif column_title == 'Quantity':
            try:
                # Quantities may arrive as '2', '2.0', or numeric
                return int(float(value))
            except Exception:
                return None
        else:
            # Fallback for other numeric columns
            try:
                return float(value)
            except Exception:
                return None
    
    def parse_price(self, price_str):
        """Safely convert a price string to a float (same logic as main generator)."""
        if not price_str:
            return 0.0
        try:
            return float(str(price_str).replace('$', '').replace(',', ''))
        except (ValueError, TypeError):
            return 0.0
    
    def find_change_since(self, history, since_datetime):
        """
        Find the first change that occurred after the specified datetime.
        
        Args:
            history: List of cell revisions sorted oldest to newest
            since_datetime: Look for changes after this time (None for first run)
        
        Returns:
            Tuple of (old_value, new_value, changed_by_name, changed_by_email, changed_at)
            or None if no relevant change found
        """
        if not history:
            return None
        
        if since_datetime is None:
            # First run: compare last two entries if available
            if len(history) < 2:
                return None
            old_entry = history[-2]
            new_entry = history[-1]
            return (
                old_entry['value'],
                new_entry['value'],
                new_entry['modified_by_name'],
                new_entry['modified_by_email'],
                new_entry['modified_at']
            )
        
        # Find the last entry BEFORE since_datetime and first entry AFTER
        before_entry = None
        after_entry = None
        
        for revision in history:
            if revision['modified_at'] and revision['modified_at'] <= since_datetime:
                before_entry = revision
            elif revision['modified_at'] and revision['modified_at'] > since_datetime:
                after_entry = revision
                break
        
        if before_entry and after_entry:
            return (
                before_entry['value'],
                after_entry['value'],
                after_entry['modified_by_name'],
                after_entry['modified_by_email'],
                after_entry['modified_at']
            )
        
        return None
    
    def calculate_week_ending(self, date_str):
        """Calculate the week ending date (Sunday) for a given date string."""
        try:
            date_obj = parser.parse(date_str)
        except Exception:
            return None
        
        # Same logic as the main generator: find the Sunday of the week
        if date_obj.weekday() == 6:  # Already Sunday
            week_ending = date_obj
        else:
            days_until_sunday = (6 - date_obj.weekday()) % 7
            week_ending = date_obj + datetime.timedelta(days=days_until_sunday)
        
        return week_ending.date()
    
    def is_historical_week(self, week_ending_date, change_made_at):
        """
        Check if a change was made to data from a week that has already ended.
        
        Args:
            week_ending_date: The week ending date of the timesheet data
            change_made_at: When the change was actually made
            
        Returns:
            True if this is an unauthorized change to locked historical data
        """
        if not week_ending_date or not change_made_at:
            return False
            
        # Convert change timestamp to date for comparison
        if isinstance(change_made_at, datetime.datetime):
            change_date = change_made_at.date()
        else:
            change_date = change_made_at
            
        # If the change was made AFTER the week had already ended, it's suspicious
        # Allow changes within the same week (before the Sunday cutoff)
        return change_date > week_ending_date
    
    def audit_changes_for_rows(self, rows, run_started_at):
        """
        Audit changes in tracked columns for all provided rows.
        
        Args:
            rows: List of row data from get_all_source_rows
            run_started_at: Timestamp when this audit run began
        """
        if not self.enabled:
            logging.info("🔍 Audit system disabled - skipping change detection")
            return
        
        logging.info(f"🔍 Starting audit for {len(rows)} rows - checking for UNAUTHORIZED changes to historical data...")
        
        # Get the last run timestamp
        last_run_timestamp = self.load_last_run_timestamp()
        if last_run_timestamp:
            logging.info(f"🔍 Checking for changes since: {last_run_timestamp.isoformat()}")
        else:
            logging.info("🔍 First audit run - will compare last two revisions if available")
        
        logging.info("🚨 AUDIT FOCUS: Only flagging changes made AFTER the week ending date (unauthorized historical edits)")
        
        # Prepare audit sheet column mapping
        try:
            audit_column_map = self.build_column_map_for_sheet(self.audit_sheet_id)
            if not audit_column_map:
                logging.error("❌ Could not build column map for audit sheet - aborting audit")
                return
        except Exception as e:
            logging.error(f"❌ Failed to access audit sheet {self.audit_sheet_id}: {e}")
            return
        
        # Deduplicate by (sheet_id, row_id) to avoid checking the same row multiple times
        unique_rows = {}
        for row in rows:
            sheet_id = row.get('__sheet_id')
            row_obj = row.get('__row_obj')
            if sheet_id and row_obj:
                key = (sheet_id, row_obj.id)
                if key not in unique_rows:
                    unique_rows[key] = row
        
        # Apply safety limit to prevent overwhelming the API
        if len(unique_rows) > MAX_ROWS_PER_RUN:
            logging.warning(f"⚠️  Limiting audit to first {MAX_ROWS_PER_RUN} rows out of {len(unique_rows)} to prevent API overload")
            unique_rows = dict(list(unique_rows.items())[:MAX_ROWS_PER_RUN])
        
        logging.info(f"🔍 Checking {len(unique_rows)} unique rows for changes...")
        
        # Collect audit entries
        audit_entries = []
        run_id = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        
        for (sheet_id, row_id), row_data in unique_rows.items():
            row_obj = row_data.get('__row_obj')
            column_map = row_data.get('__columns', {})
            
            # Extract work request info for the audit log
            wr_number = str(row_data.get('Work Request #')).split('.')[0] if row_data.get('Work Request #') else ''
            week_ending = self.calculate_week_ending(row_data.get('Weekly Referenced Logged Date'))
            
            if not column_map:
                continue
            
            # Check each tracked column for changes
            for column_title in TRACK_COLUMNS:
                if column_title not in column_map:
                    continue
                
                column_id = column_map[column_title]
                
                try:
                    # Get cell history
                    cell_history = self.fetch_cell_history(sheet_id, row_id, column_id)
                    
                    # Look for changes since last run
                    change_info = self.find_change_since(cell_history, last_run_timestamp)
                    
                    if not change_info:
                        continue  # No relevant changes
                    
                    old_value, new_value, changed_by_name, changed_by_email, changed_at = change_info
                    
                    # Convert values to numbers for comparison
                    old_number = self.coerce_number(old_value, column_title)
                    new_number = self.coerce_number(new_value, column_title)
                    
                    # Calculate delta
                    delta = None
                    if old_number is not None and new_number is not None:
                        delta = new_number - old_number
                    
                    # Only log if there's actually a meaningful change
                    if old_number != new_number:
                        # CRITICAL CHECK: Only flag changes to HISTORICAL data (past week endings)
                        if not self.is_historical_week(week_ending, changed_at):
                            continue  # Skip current week changes - these are normal and allowed
                        
                        # This is a suspicious change to locked historical data!
                        logging.warning(f"🚨 UNAUTHORIZED HISTORICAL CHANGE: WR {wr_number}, Week {week_ending}, {column_title}: {old_number} → {new_number}")
                        
                        # Create the direct link to the source sheet
                        sheet_url = f"https://app.smartsheet.com/sheets/{sheet_id}"
                        
                        audit_entry = self.create_audit_row(
                            audit_column_map,
                            work_request=wr_number,
                            week_ending=week_ending,
                            column_name=column_title,
                            old_value=old_number if old_number is not None else (old_value if old_value is not None else ""),
                            new_value=new_number if new_number is not None else (new_value if new_value is not None else ""),
                            delta=delta,
                            changed_by=changed_by_email or changed_by_name or "",
                            changed_at=changed_at,
                            source_sheet_id=str(sheet_id),
                            source_row_id=row_id,
                            sheet_reference=sheet_url,
                            run_at=run_started_at,
                            run_id=run_id
                        )
                        
                        if audit_entry:
                            audit_entries.append(audit_entry)
                            logging.info(f"📝 Change detected: WR {wr_number}, {column_title}: {old_number} → {new_number} (Δ {delta})")
                
                except Exception as e:
                    logging.warning(f"⚠️ Error checking {column_title} for row {row_id} in sheet {sheet_id}: {e}")
                    continue
        
        # Write audit entries to Smartsheet
        if audit_entries:
            self.write_audit_entries(audit_entries)
            logging.warning(f"🚨 CRITICAL: {len(audit_entries)} UNAUTHORIZED historical changes detected and logged!")
        else:
            logging.info("✅ Audit complete: no unauthorized historical changes detected")
        
        # Save the current run timestamp for next time
        self.save_last_run_timestamp(run_started_at)
    
    def create_audit_row(self, audit_column_map, **kwargs):
        """Create a Smartsheet row object for the audit log."""
        try:
            row = SSRow()
            row.to_top = True
            row.cells = []
            
            # Mapping of parameter names to audit sheet column names
            field_mapping = {
                'work_request': 'Work Request #',
                'week_ending': 'Week Ending',
                'column_name': 'Column',
                'old_value': 'Old Value',
                'new_value': 'New Value',
                'delta': 'Delta',
                'changed_by': 'Changed By',
                'changed_at': 'Changed At',
                'source_sheet_id': 'Source Sheet ID',
                'source_row_id': 'Source Row ID',
                'sheet_reference': 'Sheet Reference',
                'run_at': 'Run At',
                'run_id': 'Run ID'
            }
            
            # Add cells for each field
            for param_name, column_name in field_mapping.items():
                if column_name in audit_column_map:
                    value = kwargs.get(param_name)
                    
                    # Format datetime values
                    if isinstance(value, datetime.datetime):
                        value = value.isoformat()
                    elif isinstance(value, datetime.date):
                        value = value.isoformat()
                    
                    cell = SSCell()
                    cell.column_id = audit_column_map[column_name]
                    cell.value = value
                    row.cells.append(cell)
            
            # Add optional note field
            if 'Note' in audit_column_map:
                note_cell = SSCell()
                note_cell.column_id = audit_column_map['Note']
                note_cell.value = ''
                row.cells.append(note_cell)
            
            return row
            
        except Exception as e:
            logging.error(f"❌ Failed to create audit row: {e}")
            return None
    
    def write_audit_entries(self, audit_entries):
        """Write audit entries to the Smartsheet audit log in batches."""
        if not audit_entries:
            return
        
        # Process in batches to avoid API limits
        batch_size = 300
        total_written = 0
        
        for i in range(0, len(audit_entries), batch_size):
            batch = audit_entries[i:i + batch_size]
            
            try:
                response = self.client.Sheets.add_rows(self.audit_sheet_id, batch)
                total_written += len(batch)
                logging.info(f"📝 Wrote {len(batch)} audit entries to audit sheet (batch {i//batch_size + 1})")
                
            except Exception as e:
                logging.error(f"❌ Failed to write audit batch {i//batch_size + 1}: {e}")
                continue
        
        logging.info(f"✅ Total audit entries written: {total_written}")


def setup_audit_sheet_instructions():
    """
    Print instructions for setting up the audit sheet in Smartsheet.
    """
    instructions = """
    🔧 AUDIT SHEET SETUP INSTRUCTIONS - HISTORICAL DATA PROTECTION
    ═══════════════════════════════════════════════════════════════════
    
    To enable billing change auditing, create a new sheet in Smartsheet called 
    "Billing Report Audit Log" with these exact column titles:
    
    1. Work Request # (Text/Number)
    2. Week Ending (Date) — The original week ending date of the timesheet
    3. Column (Text/Number) — Which field was changed (Quantity or Redlined Total Price)
    4. Old Value (Text/Number) — The original value before unauthorized change
    5. New Value (Text/Number) — The new value after unauthorized change
    6. Delta (Text/Number) — The difference (New Value - Old Value) showing impact
    7. Changed By (Contact List) — Who made the unauthorized change
    8. Changed At (Date/Time) — When the unauthorized change was made
    9. Source Sheet ID (Text/Number)
    10. Source Row ID (Text/Number)
    11. Sheet Reference (Text/Number) — Direct link to investigate the source sheet
    12. Run At (Date/Time)
    13. Run ID (Text/Number)
    14. Note (Text/Number) — For investigation notes
    
    🚨 AUDIT FOCUS: This system ONLY flags changes made to historical data
    (timesheets from weeks that have already ended). Current week changes are
    normal and allowed - only PAST week changes trigger alerts.
    
    📊 DELTA COLUMN EXPLANATION:
    - Shows the numerical impact of unauthorized changes
    - Positive delta = increase in quantity/price
    - Negative delta = decrease in quantity/price
    - Helps assess financial impact of data manipulation
    
    After creating the sheet:
    1. Copy the Sheet ID from the URL
    2. Set the AUDIT_SHEET_ID environment variable in your .env file:
       AUDIT_SHEET_ID=your_sheet_id_here
    3. Or pass it directly when creating BillingAudit instance
    
    The audit system will track unauthorized changes to locked historical data
    and provide direct links for immediate investigation.
    
    ═══════════════════════════════════════════════════════════════════
    """
    print(instructions)


# Example usage and testing
if __name__ == "__main__":
    # This can be used for testing the audit system independently
    setup_audit_sheet_instructions()
    
    # Example of how to test with your existing client
    # from generate_weekly_pdfs import API_TOKEN
    # client = smartsheet.Smartsheet(API_TOKEN)
    # audit = BillingAudit(client, audit_sheet_id="your_audit_sheet_id")
    # 
    # # Test with some sample rows (would normally come from get_all_source_rows)
    # test_rows = []  # Your row data here
    # run_time = datetime.datetime.utcnow()
    # audit.audit_changes_for_rows(test_rows, run_time)
