# Billing Report Audit System

## Overview

The Billing Report Audit System tracks changes to critical billing columns (`Quantity` and `Redlined Total Price`) across all your source sheets. It creates a detailed audit log showing who changed what, when, and by how much.

## Features

- **Change Tracking**: Monitors `Quantity` and `Redlined Total Price` columns for any modifications
- **Who, What, When**: Records the user, timestamp, and exact values for each change
- **Delta Calculation**: Shows the difference between old and new values
- **Automated Integration**: Runs as part of your existing Excel generation process
- **Deduplication**: Efficiently handles multiple references to the same source row
- **First Run Support**: On initial run, compares the last two revisions if available

## Setup Instructions

### 1. Create the Audit Sheet

You have two options:

#### Option A: Automatic Setup (Recommended)
```bash
python setup_audit_sheet.py
```

#### Option B: Manual Setup
1. Create a new sheet in Smartsheet named: **"Billing Report Audit Log"**
2. Create these columns in this exact order:
   - `Work Request #` (Text/Number) - Primary Column
   - `Week Ending` (Date)
   - `Column` (Text/Number)
   - `Old Value` (Text/Number)
   - `New Value` (Text/Number)
   - `Delta` (Text/Number)
   - `Changed By` (Contact List)
   - `Changed At` (Date/Time)
   - `Source Sheet ID` (Text/Number)
   - `Source Row ID` (Text/Number)
   - `Run At` (Date/Time)
   - `Run ID` (Text/Number)
   - `Note` (Text/Number)

### 2. Configure Environment Variables

Add this line to your `.env` file:
```env
AUDIT_SHEET_ID=your_audit_sheet_id_here
```

Replace `your_audit_sheet_id_here` with the actual Sheet ID from your audit sheet URL.

### 3. Enable Audit (Already Done)

The audit system is automatically integrated into your existing `generate_weekly_pdfs.py` script. No additional changes needed!

## How It Works

### Integration with Main Script

The audit system integrates seamlessly with your existing workflow:

1. **Data Collection**: Uses the same `all_valid_rows` data from your Excel generation
2. **Change Detection**: Compares current values with the last audit run
3. **Audit Logging**: Records any changes to the audit sheet
4. **State Management**: Remembers the last run timestamp for incremental auditing

### What Gets Tracked

- **Quantity Changes**: Any modifications to the Quantity column
- **Price Changes**: Any modifications to the Redlined Total Price column
- **User Information**: Who made the change (from Smartsheet cell history)
- **Timestamps**: Exact date/time when the change occurred
- **Context**: Work Request #, Week Ending, Source Sheet/Row

### Audit Log Columns Explained

| Column | Description |
|--------|-------------|
| Work Request # | The work request number for the changed data |
| Week Ending | The calculated week ending date for billing |
| Column | Which column was changed (Quantity or Redlined Total Price) |
| Old Value | The value before the change |
| New Value | The value after the change |
| Delta | The difference (New - Old) |
| Changed By | Email/name of the user who made the change |
| Changed At | Exact timestamp when the change occurred |
| Source Sheet ID | ID of the sheet containing the changed data |
| Source Row ID | ID of the specific row that was changed |
| Run At | When this audit run occurred |
| Run ID | Unique identifier for this audit batch |
| Note | Optional field for additional context |

## File Structure

```
├── generate_weekly_pdfs.py          # Main script (modified with audit integration)
├── audit_billing_changes.py         # Audit system module
├── setup_audit_sheet.py            # One-time setup script
├── .env.audit.example               # Environment variable example
└── generated_docs/
    └── audit_state.json             # Tracks last audit run timestamp
```

## Configuration Options

### Environment Variables

```env
# Required for audit functionality
AUDIT_SHEET_ID=1234567890123456

# Your existing Smartsheet API token (already configured)
SMARTSHEET_API_TOKEN=your_token_here
```

### Audit Settings (in audit_billing_changes.py)

```python
# Enable/disable audit functionality
AUDIT_ENABLED = True

# Columns to track for changes
TRACK_COLUMNS = ['Quantity', 'Redlined Total Price']
```

## Usage

### Normal Operation

The audit system runs automatically when you execute your main script:

```bash
python generate_weekly_pdfs.py
```

**Test Mode**: Audit is disabled in test mode to avoid cluttering the audit log with test data.

**Production Mode**: Audit runs automatically and logs real changes.

### Manual Testing

To test the audit system independently:

```python
from audit_billing_changes import BillingAudit
import smartsheet

client = smartsheet.Smartsheet("your_api_token")
audit = BillingAudit(client, audit_sheet_id="your_audit_sheet_id")

# Test with your existing data
run_time = datetime.datetime.utcnow()
audit.audit_changes_for_rows(your_row_data, run_time)
```

## Troubleshooting

### Common Issues

1. **"Audit system disabled"**: Check that `AUDIT_SHEET_ID` is set in your `.env` file
2. **Import errors**: The audit module uses the same dependencies as your main script
3. **No changes detected**: This is normal if no one modified tracked columns since the last run
4. **Permission errors**: Ensure your API token has access to the audit sheet

### Logs

The audit system provides detailed logging:
- `🔍` Audit start/completion messages
- `📝` Individual change detections
- `✅` Successful batch writes to audit sheet
- `❌` Errors or warnings

### State Management

The audit system maintains state in `generated_docs/audit_state.json`:
```json
{
  "last_run": "2024-08-15T10:30:00.000Z"
}
```

If this file is missing, the audit system treats it as a first run.

## Performance Notes

- **API Efficiency**: Only checks unique (sheet, row) combinations to minimize API calls
- **Batch Processing**: Writes audit entries in batches of 300 to stay within API limits
- **Incremental**: Only processes changes since the last run, not all historical data
- **Deduplication**: Avoids redundant checks when the same source row appears in multiple work requests

## Integration with GitHub Actions

The audit system works seamlessly with your existing GitHub Actions workflow:

1. **Automatic Runs**: Auditing happens every time your scheduled job runs
2. **State Persistence**: Consider storing the audit state in a more permanent location for GitHub Actions
3. **Error Handling**: Audit failures won't break your main Excel generation process

## Security and Privacy

- **User Tracking**: Records who made changes using Smartsheet's built-in cell history
- **Data Integrity**: Only tracks the specific columns you configure (Quantity, Redlined Total Price)
- **Audit Trail**: Creates an immutable log of changes for compliance and accountability

## Future Enhancements

Potential improvements you might consider:

1. **Real-time Auditing**: Use Smartsheet webhooks for immediate change detection
2. **Additional Columns**: Extend `TRACK_COLUMNS` to monitor other fields
3. **Reporting**: Create summary reports of changes by user, time period, or work request
4. **Alerts**: Notify stakeholders of significant changes via email or Slack

## Support

For questions or issues with the audit system:

1. Check the logs for detailed error messages
2. Verify your audit sheet structure matches the requirements
3. Ensure environment variables are correctly set
4. Test with a small dataset first
