# Product Context

## Why This Project Exists
Linetec Services' Resiliency division performs utility construction work tracked in Smartsheet. Each work crew logs daily status reports (DSR) with constructable units completed, billing data, and crew information. Management needs weekly Excel summaries grouped by Work Request number for billing reconciliation and project tracking.

## Problems It Solves
1. **Manual report generation**: Previously, creating weekly billing summaries was manual and error-prone
2. **Change tracking**: Only regenerates reports when underlying data changes (hash-based)
3. **Multi-crew support**: Handles primary crews, helper crews (foremen helping on other WRs), and VAC Crews
4. **Pricing accuracy**: Applies correct CU pricing based on contract type (subcontractor vs. original)

## How It Should Work
1. Enumerate all configured Smartsheet folders recursively to find Promax Database sheets
2. Fetch all rows, filter by completion status (`Units Completed?` checked)
3. Detect row variant: primary, helper, or VAC Crew (based on column values per row)
4. Group rows by WR# + week-ending date + variant
5. Generate Excel file per group with detailed billing line items
6. Compare hash against previous run — skip unchanged groups
7. Upload changed Excel files to Smartsheet target sheet as row attachments

## User Experience Goals
- Fully automated via GitHub Actions (scheduled or manual trigger)
- Detailed logging for debugging (with emoji markers for quick scanning)
- Incremental discovery caching to minimize API calls
- Portal dashboards for monitoring run status and viewing generated artifacts
