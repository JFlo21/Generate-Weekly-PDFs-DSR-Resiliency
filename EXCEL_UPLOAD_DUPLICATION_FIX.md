# Excel Upload Duplication and Data Accuracy Fix

## Problem Solved

This fix addresses the critical issue where old Excel files with incorrect revenue data (like the $17,000/$4,000 discrepancies) were persisting on Smartsheet due to:

1. **Missing deletion logic**: The main script wasn't actually deleting old Excel attachments before uploading new ones
2. **Unreliable filename replacement**: Code relied on Smartsheet's automatic replacement which doesn't work consistently
3. **No change detection**: Files were uploaded even when data hadn't changed, causing unnecessary duplicates
4. **Old artifact persistence**: Previous Excel files remained as "artifacts" causing confusion and data accuracy issues

## Solution Implemented

### 1. **Smart Data Change Detection**
- Added `calculate_data_hash()` function that creates a SHA-256 hash of key data fields
- Hash includes: Work Request #, CU, Quantity, Units Total Price, Snapshot Date, Pole #, Work Type
- Only uploads when data has actually changed

### 2. **Explicit Deletion Logic**
- Added `delete_old_excel_attachments()` function that properly deletes old Excel files
- Includes smart error handling for 404 errors (treats them as successful deletions)
- Prevents duplication by ensuring clean state before upload

### 3. **Data Hash in Filename**
- New filename format: `WR_{wr_num}_WeekEnding_{week_end}_{data_hash}.xlsx`
- Allows tracking what data was last uploaded
- Enables skip logic when data hasn't changed

### 4. **Enhanced Upload Logic**
- **Step 1**: Check existing files and compare data hashes
- **Step 2**: Skip upload if data unchanged (prevents unnecessary uploads)
- **Step 3**: Delete old files if data has changed
- **Step 4**: Upload new file with current data hash

## Key Changes Made

### File: `generate_weekly_pdfs.py`

1. **Added new functions** (lines ~334-395):
   ```python
   def extract_data_hash_from_filename(filename)
   def delete_old_excel_attachments(client, target_sheet_id, target_row, wr_num, current_data_hash)
   ```

2. **Enhanced `generate_excel()` function** (line ~1051):
   - Now accepts `data_hash` parameter
   - Includes hash in filename when provided

3. **Updated filename generation** (lines ~1169-1175):
   ```python
   if data_hash:
       output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}_{data_hash}.xlsx"
   else:
       output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}.xlsx"
   ```

4. **Completely replaced upload logic** (lines ~2187-2251):
   - Removed unreliable "replacement" approach
   - Added explicit deletion before upload
   - Added data change detection to prevent unnecessary uploads
   - Improved error handling and logging

## Benefits

### For Data Accuracy
- ✅ **Eliminates old incorrect data**: Old Excel files with wrong revenue amounts are properly deleted
- ✅ **Prevents $17K/$4K discrepancies**: Only current data is uploaded, old artifacts removed
- ✅ **Ensures data consistency**: Each work request has exactly one current Excel file

### For Performance  
- ✅ **Reduces unnecessary uploads**: Skips upload when data hasn't changed
- ✅ **Eliminates duplication**: No more multiple Excel files per work request
- ✅ **Cleaner Smartsheet state**: Only relevant, current files remain

### for Operations
- ✅ **Clear audit trail**: Data hash in filename shows what data was uploaded
- ✅ **Better error handling**: 404 deletion errors treated as success
- ✅ **Improved logging**: Clear indication of what actions were taken

## Testing Performed

The fix was validated with:
1. **Syntax verification**: Script compiles without errors
2. **Core logic testing**: Data hash calculation and extraction work correctly
3. **Edge case handling**: Proper handling of files without data hashes (backward compatibility)

## Why This Fix Works

1. **Addresses root cause**: Actually deletes old files instead of relying on unreliable replacement
2. **Prevents unnecessary work**: Only uploads when data has genuinely changed
3. **Provides clear tracking**: Data hash in filename enables precise change detection
4. **Maintains backward compatibility**: Handles both old and new filename formats
5. **Robust error handling**: Treats 404 deletion errors correctly as successful operations

This fix directly resolves the issue described in the problem statement where "old excel sheets with incorrect information are also uploading onto the smartsheet sheet" and ensures that only current, accurate revenue data is present.