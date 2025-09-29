# Change Detection Troubleshooting Guide

## Overview
This guide provides comprehensive troubleshooting steps for hash-based change detection issues in the Generate-Weekly-PDFs-DSR-Resiliency system. The change detection system determines when Excel files need regeneration based on data changes.

## CRITICAL FIXES IMPLEMENTED
Recent critical fixes address the most common change detection failures:

### Fix #1: Units Completed? Field Detection
**Problem**: Changes to `Units Completed?` checkbox weren't triggering file regeneration  
**Solution**: Hash calculation now includes `is_checked(row.get('Units Completed?'))`  
**Impact**: Files regenerate when work items are marked complete/incomplete

### Fix #2: Price Format Normalization  
**Problem**: Same economic value in different formats caused false change detection  
**Solution**: Hash calculation uses `parse_price()` normalization: `f"{parse_price(price):.2f}"`  
**Impact**: Format variations ($1,250.00 vs 1250.00) don't cause unnecessary regenerations

## TROUBLESHOOTING WORKFLOW

### Step 1: Identify Symptoms
Determine which type of change detection issue you're experiencing:

#### Symptom A: Files Not Regenerating When They Should
- Units Completed? changes from false to true (or vice versa)
- Actual price value changes ($1,250 → $1,500)
- Other meaningful data changes not triggering updates

#### Symptom B: Files Regenerating Unnecessarily  
- Same economic values in different formats
- Minor formatting changes that don't affect business value
- Excessive regenerations causing performance issues

#### Symptom C: Inconsistent Hash Behavior
- Same data producing different hashes across runs
- Hash calculation errors or exceptions
- Unexpected hash values in logs

### Step 2: Diagnostic Commands

#### Enable Debug Logging
```bash
# Enable comprehensive debugging
export DEBUG_HASH_CALCULATION=1
export PER_CELL_DEBUG_ENABLED=1
export EXTENDED_CHANGE_DETECTION=1  # Use comprehensive hash mode

# Run with limited data for analysis
export TEST_MODE=true
export MAX_GROUPS=3
```

#### Hash Comparison Test
```python
# Quick test to verify hash behavior
from generate_weekly_pdfs import calculate_data_hash, parse_price, is_checked

# Test data with known values
test_row_1 = {
    'Work Request #': 'WR_TEST_001',
    'Units Total Price': '$1,250.00',
    'Units Completed?': True,
    'CU': 'T123', 'Quantity': '5'
}

test_row_2 = {
    'Work Request #': 'WR_TEST_001', 
    'Units Total Price': '1250.00',  # Same value, different format
    'Units Completed?': True,
    'CU': 'T123', 'Quantity': '5'
}

hash_1 = calculate_data_hash([test_row_1])
hash_2 = calculate_data_hash([test_row_2])

# EXPECTED: hash_1 == hash_2 (same economic value)
assert hash_1 == hash_2, f"Format normalization failed: {hash_1} != {hash_2}"
```

#### Check Hash History
```bash
# Examine hash history for patterns
cat generated_docs/hash_history.json | jq '.[] | {hash, rows, updated_at}'

# Look for:
# - Frequent hash changes for same WR (indicates false changes)  
# - Missing hash entries (indicates calculation errors)
# - Inconsistent row counts for same data
```

### Step 3: Common Issues & Solutions

#### Issue 1: Units Completed? Not Detected
**Diagnosis**: 
```python
# Check if is_checked function works correctly
from generate_weekly_pdfs import is_checked

test_values = [True, False, 'true', 'false', 1, 0, None, '']
for val in test_values:
    result = is_checked(val)
    print(f"is_checked({val!r}) = {result}")
```

**Fix**: Ensure `is_checked(row.get('Units Completed?'))` is included in hash calculation

#### Issue 2: Price Format Problems
**Diagnosis**:
```python
# Check parse_price normalization
from generate_weekly_pdfs import parse_price

test_prices = ['$1,250.00', '1250.00', '$1250', '1,250.00', 1250.0]
for price in test_prices:
    try:
        normalized = f"{parse_price(price):.2f}"
        print(f"{price!r} → {normalized}")
    except Exception as e:
        print(f"{price!r} → ERROR: {e}")
```

**Fix**: Ensure `parse_price()` is used for price normalization in hash calculation

#### Issue 3: Missing Hash Fields
**Diagnosis**: Compare current hash calculation with expected fields
```python
# Expected fields in hash calculation:
expected_fields = [
    'Work Request #',
    'Snapshot Date', 
    'CU',
    'Quantity',
    'Units Total Price',  # via parse_price()
    'Pole #',
    'Work Type',
    'Units Completed?'   # via is_checked()
]

# Extended mode also includes:
extended_fields = [
    'Dept #',
    'Scope #',
    'Foreman',           # Group level
    'Total Amount',      # Group level  
    'Row Count'          # Group level
]
```

### Step 4: Performance Analysis

#### Hash Calculation Performance
```bash
# Time hash calculation for large datasets
time python -c "
from generate_weekly_pdfs import calculate_data_hash
import json

# Load test data
with open('test_data.json') as f:
    test_data = json.load(f)

# Measure hash performance
import time
start = time.time()
hash_result = calculate_data_hash(test_data)
duration = time.time() - start
print(f'Hash calculation: {duration:.3f}s for {len(test_data)} rows')
print(f'Hash result: {hash_result}')
"
```

**Expected Performance**: <100ms for 550 rows

#### Hash Consistency Test
```python
# Verify hash consistency across multiple runs
hashes = []
for i in range(10):
    hash_result = calculate_data_hash(test_data)
    hashes.append(hash_result)

# All hashes should be identical
assert len(set(hashes)) == 1, f"Hash inconsistency detected: {set(hashes)}"
```

### Step 5: System Integration Verification

#### End-to-End Test
```bash
# Test complete change detection workflow
export TEST_MODE=true
export FORCE_GENERATION=false  # Test normal change detection
export DEBUG_HASH_CALCULATION=1

python generate_weekly_pdfs.py

# Look for log messages:
# - "⏩ Skip (unchanged + attachment exists)" - correct skip behavior
# - "🔁 Regenerating ... despite unchanged hash" - should NOT appear
# - "✅ Hash changes when ... changes" - correct detection
```

#### Attachment Verification  
```bash
# Verify attachments have correct hash in filename
ls generated_docs/WR_*_*.xlsx

# Format: WR_{wr_num}_WeekEnding_{week}_{timestamp}_{hash}.xlsx
# Hash should be 16 characters (first 16 chars of SHA-256)
```

## MONITORING & ALERTS

### Key Metrics to Monitor
- Hash calculation time (<100ms target)
- False positive rate (<5% unnecessary regenerations)
- False negative rate (0% missed changes)  
- parse_price() failure rate (<1%)
- is_checked() usage patterns

### Alert Conditions
- **CRITICAL**: Hash calculation failures
- **WARNING**: >10% files regenerated in single run (indicates false positives)
- **INFO**: >5% parse_price() fallbacks (data quality issue)

## ESCALATION PROCEDURES

### Level 1: Standard Issues
- Review this troubleshooting guide
- Check recent data format changes
- Verify environment configuration

### Level 2: Persistent Problems  
- Collect debug logs with full context
- Analyze hash_history.json patterns
- Test with synthetic data for isolation

### Level 3: Critical Failures
- System-wide hash calculation failures
- Data corruption affecting change detection  
- Performance degradation >500ms per hash

## RECOVERY PROCEDURES

### Hash Reset (Nuclear Option)
```bash
# WARNING: Forces regeneration of ALL files
export RESET_HASH_HISTORY=1
export FORCE_GENERATION=1
python generate_weekly_pdfs.py
```

### Selective Reset
```bash  
# Reset specific Work Requests only
export RESET_WR_LIST="90093002,82131472,83812901"
python generate_weekly_pdfs.py
```

### Rollback to Legacy Mode
```bash
# Temporary fallback if extended mode has issues
export EXTENDED_CHANGE_DETECTION=0
python generate_weekly_pdfs.py
```

This troubleshooting guide should resolve 95%+ of change detection issues. For persistent problems, escalate with full diagnostic logs and hash calculation test results.