# Work Request Exemption List

This document explains how to configure and use the Work Request exemption list feature to prevent specific Work Requests from generating Excel files.

## Overview

The exemption list allows you to specify Work Request numbers that should be excluded from Excel generation. This is useful for:
- Excluding test or invalid Work Requests
- Temporarily disabling Excel generation for specific WRs
- Managing special cases that don't need billing reports

## Configuration

### Exemption List File

The exemption list is stored in a JSON file (`exemption_list.json` by default) at the root of the repository.

**Default location:** `exemption_list.json`

**File format:**
```json
{
  "_comment": "Work Request numbers to exempt from Excel generation",
  "_instructions": "Add Work Request numbers (as strings) to the 'exempted_work_requests' array below.",
  "_example": "To exempt WR 12345678, add \"12345678\" to the array",
  "exempted_work_requests": [
    "12345678",
    "87654321"
  ]
}
```

### Adding Work Requests to the Exemption List

1. Open `exemption_list.json` in your editor
2. Add the Work Request number (as a string) to the `exempted_work_requests` array
3. Save the file
4. The next time the generator runs, those Work Requests will be skipped

**Example:**
```json
{
  "exempted_work_requests": [
    "90093002",
    "89954686",
    "12345678"
  ]
}
```

### Removing Work Requests from the Exemption List

1. Open `exemption_list.json`
2. Remove the Work Request number from the `exempted_work_requests` array
3. Save the file

### Important Notes

- **Format:** Work Request numbers should be entered as strings (enclosed in quotes)
- **Decimal points:** You can enter WR numbers with or without decimal points (e.g., "12345678" or "12345678.0" - both work)
- **Whitespace:** Leading and trailing whitespace is automatically removed
- **Comments:** Lines starting with "_" are comments and are ignored
- **Empty values:** Empty or null entries are automatically filtered out

## Environment Variable Override

You can specify a custom path to the exemption list file using the `EXEMPTION_LIST_PATH` environment variable:

```bash
EXEMPTION_LIST_PATH=/path/to/custom_exemption_list.json python generate_weekly_pdfs.py
```

## How It Works

1. When the generator starts, it loads the exemption list from the JSON file
2. During the grouping phase, any Work Request numbers in the exemption list are filtered out
3. Excel files are NOT generated for exempted Work Requests
4. The generator logs which Work Requests were exempted (if any)

## Logging

The generator provides detailed logging about exemptions:

```
📋 Loaded exemption list from 'exemption_list.json': 3 Work Request(s) will be exempted from Excel generation
   Exempted WRs: ['12345678', '87654321', '90093002']
```

During processing:
```
⛔ EXEMPTION SUMMARY: 3 Work Request(s) exempted from Excel generation
   Exempted WRs: ['12345678', '87654321', '90093002']
```

## Testing

To test the exemption functionality:

1. Add a Work Request to the exemption list
2. Run the generator in test mode:
   ```bash
   TEST_MODE=true python generate_weekly_pdfs.py
   ```
3. Verify that no Excel file is generated for the exempted Work Request

## Troubleshooting

### Exemption not working

1. Check the JSON file syntax is valid (use a JSON validator)
2. Verify the Work Request number exactly matches (no extra spaces or characters)
3. Check the logs to confirm the exemption list was loaded
4. Ensure the `exempted_work_requests` key is spelled correctly

### File not found

If you see "Exemption list file not found", verify:
1. The file exists in the expected location
2. The `EXEMPTION_LIST_PATH` environment variable (if set) points to the correct location
3. The file has proper read permissions

## Advanced Usage

### Programmatic Exemption

You can also exempt Work Requests programmatically by modifying the code. In the `main()` function, you can add additional WRs to the exemption set:

```python
# Load exemption list for Work Requests to skip
exemption_list = load_exemption_list(EXEMPTION_LIST_PATH)

# Add additional WRs programmatically (for special cases)
exemption_list.add("99999999")
exemption_list.add("88888888")
```

### Environment-Based Exemption

You can create different exemption lists for different environments:

```bash
# Production
EXEMPTION_LIST_PATH=exemption_list.prod.json python generate_weekly_pdfs.py

# Testing
EXEMPTION_LIST_PATH=exemption_list.test.json python generate_weekly_pdfs.py
```

## Examples

### Example 1: Basic Exemption

```json
{
  "exempted_work_requests": [
    "12345678"
  ]
}
```

This will prevent Excel generation for Work Request 12345678.

### Example 2: Multiple Exemptions

```json
{
  "exempted_work_requests": [
    "12345678",
    "87654321",
    "11111111",
    "22222222"
  ]
}
```

This will prevent Excel generation for all four Work Requests.

### Example 3: Empty Exemption List

```json
{
  "exempted_work_requests": []
}
```

This is the default - no Work Requests are exempted.
