# Project Brief: Generate Weekly PDFs (DSR Resiliency)

## Overview
Automated weekly PDF/Excel report generator for Linetec Services' Resiliency division. Reads daily status report (DSR) data from Smartsheet, groups rows by Work Request (WR) number and week ending date, generates Excel files with billing data, and uploads them back to Smartsheet as row-level attachments.

## Core Requirements
1. **Data Source**: Smartsheet API — fetches rows from 20+ Promax Database sheets
2. **Grouping**: Rows grouped by WR# + week-ending date + variant (primary / helper / vac_crew)
3. **Change Detection**: SHA256 hash-based — only regenerates Excel files when row data changes
4. **Pricing**: CU (Constructable Unit) lookup tables for unit pricing, with subcontractor vs. original contract rate variants
5. **Upload**: Attaches generated `.xlsx` files to the corresponding WR row in a target Smartsheet
6. **Variants**: Three output types per group:
   - **Primary**: Standard crew work
   - **Helper**: Rows where another foreman is helping (detected by `Foreman Helping?` + `Helping Foreman Completed Unit?` columns)
   - **VAC Crew**: Rows where a VAC Crew is doing the work (detected by `VAC Crew Helping?` + `Vac Crew Completed Unit?` columns)

## Environment
- Python 3.11+
- Runs on GitHub Actions (CI/CD) or locally
- Smartsheet Python SDK
- Portal frontend: Node.js (v1) / Vite + React + Supabase (v2)

## Key Constraints
- Smartsheet API rate limits (must use parallel workers carefully)
- Large sheets can cause Error 4000 (mitigated by fetching only needed columns)
- Hash history persists across runs to avoid redundant regeneration
- Discovery cache (TTL-based) reduces API calls for sheet enumeration
