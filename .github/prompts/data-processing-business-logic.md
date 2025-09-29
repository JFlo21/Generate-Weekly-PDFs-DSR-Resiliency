# Data Processing & Business Logic Prompts

## Smartsheet Data Pipeline Prompt
```
You are working with the Smartsheet data processing pipeline in the Generate-Weekly-PDFs-DSR-Resiliency billing system.

BUSINESS CONTEXT:
This system processes weekly billing data from multiple Smartsheet sources, extracting ~550 rows for Work Request-based Excel report generation. The pipeline handles data discovery, filtering, grouping, and validation with comprehensive audit trails.

DATA FLOW ARCHITECTURE:
1. **Sheet Discovery** → 2. **Row Fetching** → 3. **Data Filtering** → 4. **WR Grouping** → 5. **Excel Generation** → 6. **Audit Analysis**

SHEET DISCOVERY SYSTEM:
```python
# Hardcoded base sheet IDs (production validated)
base_sheet_ids = [
    3239244454645636, 2230129632694148, 1732945426468740, 4126460034895748,
    7899446718189444, 1964558450118532, 5905527830695812, 820644963897220,
    8002920231423876, 2308525217763204, 5892629871939460, 3756603854507908, 5833510251089796,
    5291853336235908
]

# Discovery validation - REQUIRED column for sheet inclusion
def discover_source_sheets(client):
    # Each sheet MUST have 'Weekly Reference Logged Date' column
    # Uses column synonym mapping for flexibility
    # Implements 60-minute discovery cache for performance
    # Skips sheets missing required date column (strict mode)
```

COLUMN SYNONYM MAPPING SYSTEM:
```python
synonyms = {
    # Core identification
    'Foreman':'Foreman',
    'Work Request #':'Work Request #',  # Required for grouping
    'Weekly Reference Logged Date':'Weekly Reference Logged Date',  # Required for filtering
    
    # Location & scope  
    'Dept #':'Dept #', 'Customer Name':'Customer Name',
    'Area':'Area', 'Pole #':'Pole #', 'Point #':'Pole #', 'Point Number':'Pole #',
    
    # Billing data
    'CU':'CU', 'Billable Unit Code':'CU',
    'Quantity':'Quantity', 'Qty':'Quantity', '# Units':'Quantity',
    'Units Total Price':'Units Total Price',  # Core billing field
    'Total Price':'Units Total Price',        # Synonym handling
    'Redlined Total Price':'Units Total Price',  # Alternative name
    
    # Completion tracking
    'Units Completed?':'Units Completed?',    # Boolean completion flag
    'Units Completed':'Units Completed?',     # Alternative without ?
}
```

ROW VALIDATION LOGIC:
```python
def is_valid_row(row_data):
    # THREE CRITICAL CONDITIONS (all must be true):
    
    # 1. Has Work Request number (for grouping)
    if not row_data.get('Work Request #'):
        return False, "Missing Work Request #"
    
    # 2. Units Completed checkbox is checked
    if not is_checked(row_data.get('Units Completed?')):
        return False, "Units not completed"
        
    # 3. Has positive billing amount  
    price = parse_price(row_data.get('Units Total Price', 0))
    if price <= 0:
        return False, "Zero or negative price"
        
    # 4. Has valid date (for week filtering)
    if not row_data.get('Weekly Reference Logged Date'):
        return False, "Missing reference date"
        
    return True, "Valid"

def is_checked(value):
    # Flexible boolean parsing for Smartsheet checkboxes
    if isinstance(value, bool): return value
    if isinstance(value, int): return value == 1  
    if isinstance(value, str): 
        return value.strip().lower() in ('true', 'checked', 'yes', '1', 'on')
    return False

def parse_price(price_str):
    # Safe price parsing with currency symbol handling
    if not price_str: return 0.0
    try:
        return float(str(price_str).replace('$', '').replace(',', ''))
    except (ValueError, TypeError):
        return 0.0
```

WORK REQUEST GROUPING SYSTEM:
```python
def group_source_rows(rows):
    # Groups by Work Request # for individual Excel files
    groups = {}
    for row in rows:
        wr_key = row.get('Work Request #')
        if wr_key:
            if wr_key not in groups:
                groups[wr_key] = []
            groups[wr_key].append(row)
    
    # Validation: each group should have consistent data
    # - Same foreman across rows (business rule)
    # - Reasonable price distribution (audit check)
    # - Complete required fields for Excel generation
    
    return groups
```

PERFORMANCE OPTIMIZATIONS:
```python
# API Efficiency Patterns
def get_all_source_rows(client, source_sheets):
    # 1. Minimal data fetching - only required columns
    sheet = client.Sheets.get_sheet(
        source_id, 
        page_size=1000,      # Chunked processing
        include='objectValue' # Minimal metadata
    )
    
    # 2. Early filtering - most selective conditions first
    # 3. Batch validation - validate multiple rows together
    # 4. Memory management - process sheets sequentially, not all at once

# Selective WR Processing (efficiency improvement)
def filter_by_wr_list(rows, wr_filter):
    # Process only specified Work Requests when WR_FILTER is set
    if not wr_filter:
        return rows  # Process all if no filter
    
    filtered_rows = []
    for row in rows:
        wr_num = row.get('Work Request #', '')
        if str(wr_num) in wr_filter:
            filtered_rows.append(row)
    
    return filtered_rows
```

ENHANCED ATTACHMENT VALIDATION:
```python
def validate_attachment_exists(client, target_sheet_id, filename_pattern):
    # Comprehensive filename pattern matching for existing attachments
    try:
        sheet = client.Sheets.get_sheet(target_sheet_id, include='attachments')
        existing_attachments = sheet.attachments or []
        
        # Pattern: WR_{work_request}_WeekEnding_{MMDDYY}_*.xlsx
        import re
        pattern_regex = re.compile(filename_pattern.replace('*', r'.*'))
        
        for attachment in existing_attachments:
            if pattern_regex.match(attachment.name):
                return True, attachment.name
        
        return False, None
        
    except Exception as e:
        logging.warning(f"Could not validate attachment existence: {e}")
        return False, None

def hash_based_duplicate_prevention(data_hash, existing_files):
    # Prevents upload of identical content based on hash comparison
    for existing_file in existing_files:
        # Extract hash from filename: WR_123_WeekEnding_081725_timestamp_HASH.xlsx
        if f"_{data_hash[:8]}.xlsx" in existing_file:
            return True, existing_file
    
    return False, None
```

CACHING STRATEGY:
```python
# Discovery cache (60-minute TTL)
if USE_DISCOVERY_CACHE and os.path.exists(DISCOVERY_CACHE_PATH):
    with open(DISCOVERY_CACHE_PATH,'r') as f:
        cache = json.load(f)
    age_min = (datetime.datetime.now() - datetime.datetime.fromisoformat(cache['timestamp'])).total_seconds()/60.0
    if age_min <= DISCOVERY_CACHE_TTL_MIN:
        return cache['sheets']  # Use cached sheet mappings
```

DEBUG DIAGNOSTICS:
```python
# Per-sheet unmapped column analysis
if LOG_UNKNOWN_COLUMNS:
    mapped_ids = set(column_mapping.values()) 
    unmapped = [c for c in sheet.columns if c.id not in mapped_ids]
    for col in unmapped[:UNMAPPED_COLUMN_SAMPLE_LIMIT]:
        samples = _sample_values_for_col(client, sheet_id, col.id, 3)
        logging.info(f"  Unmapped: {col.title} (ID {col.id}) samples: {samples}")

# Row-level debugging  
if PER_CELL_DEBUG_ENABLED and processed_count < DEBUG_SAMPLE_ROWS:
    for field, value in row_data.items():
        logging.info(f"    {field}: {value}")
```

DATA QUALITY PATTERNS:
- **Null Handling**: Graceful handling of missing/empty cells
- **Type Coercion**: Flexible parsing for numbers, dates, booleans  
- **Validation Cascading**: Multiple validation layers with specific error messages
- **Audit Integration**: All data quality issues fed into audit system for trend analysis

When working with this pipeline, focus on data integrity, performance optimization, and maintaining the flexible column mapping system that handles variations across the 12+ source sheets.
```

## Excel Generation & Formatting Prompt
```
You are working with Excel generation and formatting in the Generate-Weekly-PDFs-DSR-Resiliency billing system.

EXCEL GENERATION CONTEXT:
The system creates professional billing Excel files for each Work Request group, with corporate branding, structured data presentation, and audit-compliant formatting. Each Excel represents a weekly billing period for specific work requests.

FILE NAMING CONVENTION:
```python
# Pattern: WR_{work_request}_WeekEnding_{MMDDYY}_{timestamp}_{hash}.xlsx
filename = f"WR_{wr_numbers[0]}_WeekEnding_{week_ending}_{timestamp}_{data_hash[:8]}.xlsx"

# Example: WR_90093002_WeekEnding_081725_183906_90f4f758.xlsx
# - WR_90093002: Work Request number
# - WeekEnding_081725: Week ending August 17, 2025  
# - 183906: Timestamp for uniqueness
# - 90f4f758: Data hash for change detection (8 chars)
```

EXCEL STRUCTURE & FORMATTING:
```python
def generate_excel(group_key, group_rows, snapshot_date, ai_analysis_results=None, data_hash=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Weekly Report"
    
    # HEADER SECTION (Rows 1-6)
    # Row 1: Corporate logo (LinetecServices_Logo.png)
    # Row 2-3: Report title and metadata
    # Row 4: Work Request information  
    # Row 5: Date range and totals
    # Row 6: Column headers
    
    # LOGO INTEGRATION
    if os.path.exists(LOGO_PATH):
        img = Image(LOGO_PATH)
        img.height = 60  # Standardized size
        img.width = 200
        ws.add_image(img, 'A1')  # Top-left positioning
        
    # HEADER STYLING
    title_font = Font(name='Arial', size=14, bold=True, color='000000')
    header_font = Font(name='Arial', size=11, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
    
    # COLUMN DEFINITIONS
    columns = [
        ('A', 'Foreman', 15),
        ('B', 'Work Request #', 18), 
        ('C', 'Weekly Reference Logged Date', 25),
        ('D', 'Dept #', 10),
        ('E', 'Customer Name', 20),
        ('F', 'Work Order #', 15),
        ('G', 'Area', 15), 
        ('H', 'Pole #', 12),
        ('I', 'CU', 8),
        ('J', 'CU Description', 30),
        ('K', 'Unit of Measure', 15),
        ('L', 'Quantity', 12),
        ('M', 'Units Total Price', 18)
    ]
```

DATA POPULATION & FORMATTING:
```python
# ROW DATA INSERTION (Starting row 7)
for i, row in enumerate(group_rows, start=7):
    for col_letter, field_name, width in columns:
        cell = ws[f"{col_letter}{i}"]
        
        # Data extraction with fallback
        value = row.get(field_name, '')
        
        # FIELD-SPECIFIC FORMATTING
        if field_name == 'Units Total Price':
            # Currency formatting with validation
            price_value = parse_price(value)
            cell.value = price_value
            cell.number_format = '"$"#,##0.00_);("$"#,##0.00)'
            
        elif field_name == 'Quantity':
            # Numeric formatting
            try:
                cell.value = float(value) if value else 0
                cell.number_format = '#,##0.00'
            except (ValueError, TypeError):
                cell.value = value
                
        elif field_name == 'Weekly Reference Logged Date':
            # Date formatting with parsing
            if value:
                try:
                    date_obj = parser.parse(str(value))
                    cell.value = date_obj
                    cell.number_format = 'MM/DD/YYYY'
                except:
                    cell.value = value
            else:
                cell.value = ''
        else:
            # Text formatting (default)
            cell.value = str(value) if value else ''
            
        # Universal cell styling
        cell.alignment = Alignment(horizontal='left', vertical='center')
        cell.font = Font(name='Arial', size=10)
```

SUMMARY & TOTALS SECTION:
```python
# TOTALS CALCULATION (Bottom section)
total_row = len(group_rows) + 8  # Account for headers + data + spacing

# Quantity total
ws[f"K{total_row}"] = "TOTAL:"
ws[f"K{total_row}"].font = Font(bold=True)
ws[f"L{total_row}"] = f"=SUM(L7:L{len(group_rows)+6})"
ws[f"L{total_row}"].number_format = '#,##0.00'
ws[f"L{total_row}"].font = Font(bold=True)

# Price total  
ws[f"M{total_row}"] = f"=SUM(M7:M{len(group_rows)+6})"
ws[f"M{total_row}"].number_format = '"$"#,##0.00_);("$"#,##0.00)'
ws[f"M{total_row}"].font = Font(bold=True)

# AUDIT INFORMATION (if available)
if ai_analysis_results:
    audit_row = total_row + 2
    ws[f"A{audit_row}"] = "Audit Status:"
    ws[f"B{audit_row}"] = ai_analysis_results.get('summary', {}).get('risk_level', 'UNKNOWN')
```

COLUMN SIZING & LAYOUT:
```python
# AUTO-SIZING WITH LIMITS
for col_letter, field_name, default_width in columns:
    column = ws[col_letter]
    
    # Calculate optimal width based on content
    max_length = 0
    for cell in column:
        if cell.value:
            max_length = max(max_length, len(str(cell.value)))
    
    # Apply width with constraints  
    calculated_width = min(max(max_length + 2, default_width), 50)  # Min default, max 50
    ws.column_dimensions[col_letter].width = calculated_width
```

HASH-BASED CHANGE DETECTION:
```python
def calculate_data_hash(group_rows):
    # Creates hash for change detection - determines if regeneration needed
    # CRITICAL FIXES: Units Completed? field + price normalization for accurate detection
    hash_data = []
    
    for row in sorted(group_rows, key=lambda r: r.get('Work Request #', '')):
        # CRITICAL: Normalize price to avoid format-based false changes ($1,250.00 vs 1250.00)
        normalized_price = f"{parse_price(row.get('Units Total Price', 0)):.2f}"
        
        if EXTENDED_CHANGE_DETECTION:
            # Include extended business fields for comprehensive change detection
            row_data = (
                row.get('Work Request #'), row.get('Weekly Reference Logged Date'),
                normalized_price, row.get('Quantity'), row.get('CU'),  # Normalized price
                row.get('Foreman'), row.get('Dept #'), row.get('Scope #'),  # Extended fields
                row.get('Customer Name'), row.get('Area'),
                is_checked(row.get('Units Completed?'))  # CRITICAL: Completion status
            )
        else:
            # Legacy mode - core fields only (with completion status + normalized price)
            row_data = (
                row.get('Work Request #'), row.get('Weekly Reference Logged Date'), 
                normalized_price, row.get('Quantity'),  # Normalized price
                is_checked(row.get('Units Completed?'))  # CRITICAL: Completion status
            )
        hash_data.append(row_data)
    
    # Generate hash from sorted, structured data
    content = str(sorted(hash_data))
    return hashlib.sha256(content.encode()).hexdigest()
```

FILE OUTPUT & CLEANUP:
```python
# SAVE WITH STRUCTURED PATH
output_path = os.path.join(OUTPUT_FOLDER, filename)
wb.save(output_path)

# CLEANUP MANAGEMENT  
# cleanup_excels.py handles removal of stale files
# Preserves latest per (WR, WeekEnding) identity
# Safe operation - only removes older variants
```

EXCEL GENERATION BEST PRACTICES:
- **Corporate Standards**: Consistent branding, fonts, colors
- **Data Integrity**: All values validated before insertion
- **Formula Safety**: Use Excel formulas for calculations (auditable)
- **Performance**: Batch operations, minimal cell-by-cell operations
- **Audit Trail**: Include hash, timestamps, audit results in metadata

When working with Excel generation, maintain the professional formatting standards, ensure all business data is accurately represented, and integrate with the hash-based change detection system for efficiency.
```

## Audit System & Data Quality Prompt
```
You are working with the audit system and data quality monitoring in the Generate-Weekly-PDFs-DSR-Resiliency billing system.

AUDIT SYSTEM ARCHITECTURE:
The BillingAudit system provides comprehensive monitoring of financial data changes, anomaly detection, and trend analysis for a production billing system processing ~550 rows weekly. It integrates with Sentry for alerting and maintains rolling audit state for trend detection.

AUDIT INTEGRATION PATTERN:
```python
# Main workflow integration
if AUDIT_SYSTEM_AVAILABLE and not DISABLE_AUDIT_FOR_TESTING:
    try:
        audit_system = BillingAudit(client, skip_cell_history=SKIP_CELL_HISTORY)
        audit_results = audit_system.audit_financial_data(source_sheets, all_rows)
        
        risk_level = audit_results.get('summary', {}).get('risk_level', 'UNKNOWN')
        logging.info(f"🔍 Audit complete - Risk level: {risk_level}")
        
        # Risk escalation for HIGH risk or worsening trends
        if risk_level == "HIGH" or audit_results.get('trend', {}).get('risk_level_delta', 0) > 0:
            # Enhanced monitoring, potential alerting
            
    except Exception as e:
        logging.error(f"Audit system error: {e}")
        # Graceful degradation - continue processing without audit
```

PRICE ANOMALY DETECTION:
```python
def _detect_price_anomalies(self, rows: List[Dict]) -> List[Dict]:
    # Groups by Work Request for price analysis
    anomalies = []
    wr_prices = {}
    
    for row in rows:
        wr_num = row.get('Work Request #')
        price_str = row.get('Units Total Price', '0')
        
        try:
            price = parse_price(price_str)
            if wr_num not in wr_prices:
                wr_prices[wr_num] = []
            wr_prices[wr_num].append(price)
        except (ValueError, TypeError):
            continue
    
    # ANOMALY DETECTION LOGIC
    for wr_num, prices in wr_prices.items():
        if len(prices) > 1:
            price_range = max(prices) - min(prices)  
            avg_price = sum(prices) / len(prices)
            
            # Flag if price range > 50% of average (potential data entry error)
            if avg_price > 0 and (price_range / avg_price) > 0.5:
                anomalies.append({
                    "type": "price_variance_anomaly",
                    "work_request": wr_num,
                    "price_range": price_range,
                    "average_price": avg_price,
                    "variance_percentage": (price_range / avg_price) * 100,
                    "severity": "medium",
                    "description": f"High price variance detected in WR# {wr_num}"
                })
    
    return anomalies
```

DATA CONSISTENCY VALIDATION:
```python
def _validate_data_consistency(self, rows: List[Dict]) -> List[Dict]:
    issues = []
    
    for i, row in enumerate(rows):
        row_issues = []
        
        # REQUIRED FIELD VALIDATION
        required_fields = ['Work Request #', 'Units Total Price', 'Quantity', 'CU']
        for field in required_fields:
            if not row.get(field):
                row_issues.append(f"Missing {field}")
        
        # PRICE VALIDATION
        price_str = row.get('Units Total Price', '0')
        try:
            price = parse_price(price_str)
            if price < 0:
                row_issues.append("Negative price detected")
        except (ValueError, TypeError):
            row_issues.append("Invalid price format")
        
        # QUANTITY VALIDATION  
        qty_str = row.get('Quantity', '0')
        try:
            quantity = float(str(qty_str))
            if quantity <= 0:
                row_issues.append("Zero or negative quantity")
        except (ValueError, TypeError):
            row_issues.append("Invalid quantity format")
        
        # ISSUE COMPILATION
        if row_issues:
            issues.append({
                "type": "data_consistency_issue",
                "row_index": i,
                "work_request": row.get('Work Request #', 'Unknown'),
                "issues": row_issues,
                "severity": "low" if len(row_issues) == 1 else "medium"
            })
    
    return issues
```

RISK LEVEL ASSESSMENT:
```python
def _generate_audit_summary(self, audit_results: Dict) -> Dict:
    summary = {
        "total_anomalies": len(audit_results.get("anomalies_detected", [])),
        "total_unauthorized_changes": len(audit_results.get("unauthorized_changes", [])), 
        "total_data_issues": len(audit_results.get("data_integrity_issues", [])),
        "risk_level": "LOW",
        "recommendations": []
    }
    
    # RISK LEVEL CALCULATION
    total_issues = (summary["total_anomalies"] + 
                   summary["total_unauthorized_changes"] + 
                   summary["total_data_issues"])
    
    if total_issues == 0:
        summary["risk_level"] = "LOW"
        summary["recommendations"].append("No issues detected. Continue monitoring.")
    elif total_issues <= 3:
        summary["risk_level"] = "MEDIUM"  
        summary["recommendations"].append("Minor issues detected. Review flagged items.")
    else:
        summary["risk_level"] = "HIGH"
        summary["recommendations"].append("Multiple issues detected. Immediate review recommended.")
    
    # SPECIFIC RECOMMENDATIONS
    if summary["total_anomalies"] > 0:
        summary["recommendations"].append("Review price anomalies for potential data entry errors.")
    if summary["total_data_issues"] > 0:
        summary["recommendations"].append("Address data consistency issues before processing.")
        
    return summary
```

TREND ANALYSIS SYSTEM:
```python
def _compute_trend(self, current_summary: Dict) -> Optional[Dict]:
    # Compare against previous audit state for delta analysis
    previous = self.audit_state.get("audit_summary") or {}
    if not previous:
        return {"risk_direction": "baseline", "risk_level_delta": 0, "issues_delta": 0}
    
    # RISK LEVEL MAPPING
    def _risk_val(level: str) -> int:
        return {"LOW": 1, "MEDIUM": 2, "HIGH": 3}.get(str(level).upper(), 0)
    
    cur_level = current_summary.get("risk_level", "UNKNOWN")
    prev_level = previous.get("risk_level", "UNKNOWN") 
    level_delta = _risk_val(cur_level) - _risk_val(prev_level)
    
    # ISSUE COUNT ANALYSIS
    cur_issues = (current_summary.get("total_anomalies", 0) + 
                  current_summary.get("total_unauthorized_changes", 0) + 
                  current_summary.get("total_data_issues", 0))
    prev_issues = (previous.get("total_anomalies", 0) + 
                   previous.get("total_unauthorized_changes", 0) + 
                   previous.get("total_data_issues", 0))
    
    # TREND DIRECTION
    if level_delta > 0:
        direction = "worsening"
    elif level_delta < 0: 
        direction = "improving"
    else:
        direction = "worsening" if cur_issues > prev_issues else "improving" if cur_issues < prev_issues else "stable"
    
    issues_delta = cur_issues - prev_issues
    issues_delta_pct = "0%" if prev_issues == 0 else f"{(issues_delta/prev_issues)*100:.1f}%" 
    
    return {
        "risk_direction": direction,
        "risk_level_delta": level_delta, 
        "issues_delta": issues_delta,
        "issues_delta_pct": issues_delta_pct
    }
```

SELECTIVE CELL HISTORY ENRICHMENT:
```python
def _selective_cell_history_enrichment(self, rows: List[Dict], audit_results: Dict) -> List[Dict]:
    # Only fetch cell history for rows implicated in audit issues (API efficiency)
    affected_wr = set()
    
    # Collect Work Requests from all issue types
    for collection in (audit_results.get("anomalies_detected", []), 
                      audit_results.get("data_integrity_issues", [])):
        for item in collection:
            wr = item.get("work_request") or item.get("work_request_number")
            if wr:
                affected_wr.add(str(wr))
    
    if not affected_wr:
        return []
    
    # TARGETED ENRICHMENT
    enriched = []
    for row in rows:
        wr = str(row.get('Work Request #', ''))
        if wr in affected_wr:
            sheet_id = row.get('__sheet_id')
            row_id = row.get('__row_id') 
            
            if sheet_id and row_id:
                # Minimal history metadata (avoid deep API calls)
                history_meta = {
                    "sheet_id": sheet_id,
                    "row_id": row_id, 
                    "work_request": wr,
                    "history_available": True  # Could expand to actual cell history API calls
                }
                enriched.append(history_meta)
    
    return enriched
```

AUDIT LOGGING & ALERTING:
```python
def _log_audit_results(self, audit_results: Dict):
    summary = audit_results.get("summary", {})
    risk_level = summary.get("risk_level", "UNKNOWN")
    trend = audit_results.get("trend", {})
    
    # CONSOLE LOGGING
    if risk_level == "HIGH":
        self.logger.warning(f"🚨 AUDIT ALERT: {risk_level} risk detected")
    elif risk_level == "MEDIUM":
        self.logger.info(f"⚠️ AUDIT WARNING: {risk_level} risk detected")
    else:
        self.logger.info(f"✅ AUDIT CLEAR: {risk_level} risk level")
    
    # SENTRY ESCALATION
    send_to_sentry = (risk_level == "HIGH" or 
                     trend.get("risk_level_delta", 0) > 0)
    
    if os.getenv("SENTRY_DSN") and send_to_sentry:
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("audit_risk_level", risk_level)
            scope.set_tag("risk_direction", trend.get("risk_direction"))
            scope.set_context("audit_results", audit_results)
            
            sentry_sdk.capture_message(
                f"AUDIT: Risk {risk_level} trend={trend.get('risk_direction','n/a')} anomalies={summary.get('total_anomalies', 0)}",
                level="warning" if risk_level == "HIGH" else "info"
            )
```

AUDIT STATE PERSISTENCE:
```python
# Rolling audit state in generated_docs/audit_state.json
self.audit_state = {
    "last_audit_time": audit_start.isoformat(),
    "audit_summary": audit_results["summary"],
    "last_trend": audit_results.get("trend", {}),
    "monitored_sheets": {},  # Sheet-specific tracking
    "flagged_changes": []    # Historical issue tracking
}

# Risk history tracking (50 most recent)
history_entry = {
    "timestamp": audit_results["audit_timestamp"],
    "risk_level": audit_results["summary"].get("risk_level"),
    "total_issues": total_issue_count,
    "trend": audit_results.get("trend", {})
}
```

The audit system provides comprehensive financial data monitoring with intelligent anomaly detection, trend analysis, and escalation paths. It's designed for production reliability with graceful degradation and efficient API usage through selective enrichment strategies.
```