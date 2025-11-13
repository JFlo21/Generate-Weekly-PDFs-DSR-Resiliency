# Cell History Tracking

## Overview

The Cell History Tracking feature tracks changes to the "Modified By" column for each row in Smartsheet source sheets. This allows you to differentiate between Excel generation and direct Smartsheet modifications, providing an audit trail of who made changes to the data.

## Features

- **Automatic Discovery**: Automatically detects "Modified By" columns in source sheets
- **Per-Row Tracking**: Tracks modification history for each row with granular detail
- **JSON Export**: Saves all tracking data to a JSON file for easy analysis
- **Sheet-Level Organization**: Organizes history data by sheet and row for efficient lookup
- **Error Resilient**: Gracefully handles missing columns or API errors
- **Configurable**: Can be enabled/disabled via environment variable

## Configuration

### Environment Variables

- `ENABLE_CELL_HISTORY_TRACKING`: Enable or disable cell history tracking (default: `true`)
  - Set to `false` to disable tracking
  - Set to `true` to enable tracking

### Example Configuration

```bash
# Enable cell history tracking (default)
export ENABLE_CELL_HISTORY_TRACKING=true

# Disable cell history tracking
export ENABLE_CELL_HISTORY_TRACKING=false
```

## Output File

The cell history data is saved to:
```
generated_docs/cell_history.json
```

### JSON Structure

```json
{
  "last_updated": "2024-01-15T10:30:00Z",
  "sheets": {
    "123456789": {
      "sheet_id": 123456789,
      "sheet_name": "Resiliency Promax Database 1",
      "rows": {
        "987654321": {
          "row_id": 987654321,
          "work_request": "WR-90093002",
          "history": [
            {
              "modified_at": "2024-01-15T09:00:00Z",
              "modified_by": "John Doe",
              "value": "John Doe"
            },
            {
              "modified_at": "2024-01-14T14:30:00Z",
              "modified_by": "Jane Smith",
              "value": "Jane Smith"
            }
          ]
        }
      }
    }
  },
  "summary": {
    "total_sheets_tracked": 27,
    "total_rows_tracked": 1234,
    "total_modifications_tracked": 5678
  }
}
```

### Field Descriptions

- `last_updated`: Timestamp of when the history was last updated
- `sheets`: Dictionary of sheets being tracked, keyed by sheet ID
  - `sheet_id`: Smartsheet ID of the source sheet
  - `sheet_name`: Human-readable name of the sheet
  - `rows`: Dictionary of rows being tracked, keyed by row ID
    - `row_id`: Smartsheet row ID
    - `work_request`: Work Request number associated with this row
    - `history`: Array of modification events (most recent first)
      - `modified_at`: Timestamp of the modification
      - `modified_by`: User who made the modification (name or email)
      - `value`: Value of the "Modified By" cell at that time
- `summary`: Aggregate statistics
  - `total_sheets_tracked`: Number of sheets with tracked data
  - `total_rows_tracked`: Total number of rows tracked across all sheets
  - `total_modifications_tracked`: Total number of modification events recorded

## How It Works

1. **Sheet Discovery**: During the normal sheet discovery phase, the system identifies sheets that have a "Modified By" column
2. **Data Fetching**: As rows are fetched from source sheets, metadata (`__sheet_id` and `__row_id`) is attached
3. **History Tracking**: After data fetching is complete, the system:
   - Groups rows by sheet ID
   - For each row in sheets with "Modified By" column, fetches cell history via Smartsheet API
   - Stores modification events with timestamp, user, and value
4. **JSON Export**: All history data is saved to `generated_docs/cell_history.json`

## Usage Example

### Programmatic Access

```python
from cell_history_tracker import CellHistoryTracker

# Initialize tracker
client = smartsheet.Smartsheet(API_TOKEN)
tracker = CellHistoryTracker(client, "generated_docs")

# Track history for source sheets and rows
results = tracker.track_modified_by_column(source_sheets, all_rows)

print(f"Processed {results['sheets_processed']} sheets")
print(f"Tracked {results['rows_processed']} rows")

# Get summary
summary = tracker.get_history_summary()
print(f"Total sheets tracked: {summary['summary']['total_sheets_tracked']}")

# Get history for specific row
history = tracker.get_row_history(sheet_id=123456789, row_id=987654321)
if history:
    print(f"Found {len(history['history'])} modifications")
```

### Analyzing the JSON File

```python
import json

# Load cell history data
with open('generated_docs/cell_history.json', 'r') as f:
    data = json.load(f)

# Find all rows modified by a specific user
target_user = "John Doe"
for sheet_id, sheet_data in data['sheets'].items():
    for row_id, row_data in sheet_data['rows'].items():
        for modification in row_data['history']:
            if modification['modified_by'] == target_user:
                print(f"Row {row_id} in sheet {sheet_id} was modified by {target_user}")
```

## Integration Points

The cell history tracker integrates with the main workflow at these points:

1. **Sheet Discovery** (`discover_source_sheets`): "Modified By" column is added to column mappings
2. **Row Fetching** (`get_all_source_rows`): Sheet and row IDs are attached to each row for later lookup
3. **Main Execution** (`main`): Cell history tracking runs after audit system, before Excel generation

## Performance Considerations

- **API Calls**: Each tracked row requires one API call to fetch cell history
- **Rate Limiting**: The tracker handles API errors gracefully but may be slow for large datasets
- **Incremental Updates**: History data is cumulative - each run updates the JSON file
- **Filtering**: Only rows from sheets with "Modified By" column are processed

## Troubleshooting

### No History Data Generated

**Symptom**: `cell_history.json` is empty or has no rows

**Solutions**:
1. Check that source sheets have a "Modified By" column
2. Verify `ENABLE_CELL_HISTORY_TRACKING=true` in environment
3. Check logs for error messages during tracking

### Missing "Modified By" Column

**Symptom**: Sheets are skipped in tracking

**Solution**: The "Modified By" column must exist in Smartsheet and be mapped. The system automatically detects columns named:
- "Modified By" (exact match)
- Any column with "modified" and "by" in the title (case-insensitive)

### Slow Performance

**Symptom**: Cell history tracking takes a long time

**Solutions**:
1. Disable tracking for non-critical runs: `ENABLE_CELL_HISTORY_TRACKING=false`
2. Reduce the number of source sheets
3. Use the `SKIP_CELL_HISTORY` option in audit system to skip redundant checks

## API Reference

### CellHistoryTracker

```python
class CellHistoryTracker:
    def __init__(self, client, output_folder="generated_docs")
    def track_modified_by_column(self, source_sheets: List[Dict], rows: List[Dict]) -> Dict
    def get_history_summary(self) -> Dict
    def get_row_history(self, sheet_id: int, row_id: int) -> Optional[Dict]
```

### Methods

#### `track_modified_by_column(source_sheets, rows)`

Tracks "Modified By" column history for all rows.

**Parameters:**
- `source_sheets`: List of sheet configurations with column mappings
- `rows`: List of row data with `__sheet_id` and `__row_id` metadata

**Returns:**
```python
{
    "tracking_timestamp": "2024-01-15T10:30:00Z",
    "sheets_processed": 5,
    "rows_processed": 100,
    "history_entries_added": 250,
    "errors": []
}
```

#### `get_history_summary()`

Returns summary statistics.

**Returns:**
```python
{
    "last_updated": "2024-01-15T10:30:00Z",
    "summary": {
        "total_sheets_tracked": 5,
        "total_rows_tracked": 100
    },
    "sheets_tracked": ["123", "456"]
}
```

#### `get_row_history(sheet_id, row_id)`

Retrieves history for a specific row.

**Parameters:**
- `sheet_id`: Smartsheet sheet ID
- `row_id`: Row ID

**Returns:**
```python
{
    "row_id": 987654321,
    "work_request": "WR-90093002",
    "history": [...]
}
```

## Testing

The module includes comprehensive tests in `tests/test_cell_history_tracker.py`:

```bash
# Run cell history tests
pytest tests/test_cell_history_tracker.py -v

# Run all tests
pytest tests/ -v
```

## License

Part of the Generate Weekly PDFs DSR Resiliency project.
