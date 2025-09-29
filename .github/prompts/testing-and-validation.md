````markdown
# Testing & Validation Prompts

## Comprehensive Testing Strategy Prompt
```
You are working with testing and validation in the Generate-Weekly-PDFs-DSR-Resiliency production billing system.

TESTING CONTEXT:
This system processes ~550 weekly billing rows from 8+ Smartsheet sources in production. The comprehensive testing strategy includes synthetic data generation, TEST_MODE functionality, and validation patterns that ensure business logic correctness without requiring production API access.

TEST_MODE ARCHITECTURE:
The system includes a sophisticated synthetic data generation engine that creates realistic test scenarios covering all major business patterns and edge cases encountered in production billing operations.

SYNTHETIC DATA GENERATION SYSTEM:
```python
def generate_comprehensive_synthetic_data():
    """
    Creates realistic billing data for development and testing
    Covers 8+ Work Requests with production-like patterns
    """
    
    # WORK REQUEST VARIETY (realistic production patterns)
    work_requests = [
        "WR_90093002",  # High-complexity emergency repair (15-20 rows)
        "WR_82131472",  # Standard maintenance (8-12 rows) 
        "WR_83812901",  # Transformer installation (10-15 rows)
        "WR_89954686",  # Line extension (12-18 rows)
        "WR_77445123",  # Pole replacement (5-8 rows)
        "WR_66332211",  # Conductor repair (6-10 rows)
        "WR_55443322",  # Emergency storm damage (8-14 rows)
        "WR_44556677"   # Scheduled inspection (4-7 rows)
    ]
    
    # FIELD CREW REALISM (geographic and skill diversity)
    foremen = ["Johnson", "Smith", "Rodriguez", "Chen", "Williams", "Davis"]
    departments = ["100", "200", "300", "150", "250"]  # Business unit codes
    areas = ["North District", "South District", "Central", "East Zone", "West Zone"]
    
    # EQUIPMENT & WORK TYPES (production CU codes)
    equipment_types = [
        {"CU": "T001", "desc": "Transformer Installation", "base_price": 2500, "measure": "EA"},
        {"CU": "P002", "desc": "Pole Replacement", "base_price": 1200, "measure": "EA"},
        {"CU": "C003", "desc": "Conductor Repair", "base_price": 45, "measure": "FT"},
        {"CU": "M004", "desc": "Meter Installation", "base_price": 350, "measure": "EA"},
        {"CU": "S005", "desc": "Service Connection", "base_price": 800, "measure": "EA"},
        {"CU": "R006", "desc": "Recloser Maintenance", "base_price": 1800, "measure": "EA"}
    ]
    
    # BUSINESS SCENARIO PATTERNS
    scenarios = {
        "emergency_repair": {"price_variance": 1.3, "qty_range": (2, 8), "complexity": "high"},
        "scheduled_maintenance": {"price_variance": 1.0, "qty_range": (1, 5), "complexity": "medium"},
        "installation_project": {"price_variance": 1.1, "qty_range": (3, 12), "complexity": "high"},
        "routine_inspection": {"price_variance": 0.9, "qty_range": (1, 3), "complexity": "low"}
    }
    
    return generated_rows  # ~80+ rows with realistic distribution
```

AUDIT ANOMALY INJECTION:
```python
def inject_audit_test_cases(synthetic_rows):
    """
    Includes known anomalies for audit system validation
    Tests price variance detection, data consistency checks
    """
    
    # PRICE ANOMALY TEST CASES
    # Inject 2-3 rows with >50% price variance within same WR
    anomaly_wr = "WR_90093002"
    base_price = 1200.00
    
    anomaly_rows = [
        {"Units Total Price": base_price},      # Normal
        {"Units Total Price": base_price * 1.8}, # 80% higher (should trigger alert)
        {"Units Total Price": base_price * 0.3}  # 70% lower (should trigger alert)
    ]
    
    # DATA CONSISTENCY TEST CASES  
    consistency_issues = [
        {"Units Total Price": -500.00},          # Negative price
        {"Quantity": 0},                        # Zero quantity
        {"Work Request #": ""},                 # Missing WR number
        {"Units Completed?": False}             # Not completed
    ]
    
    # TREND ANALYSIS TEST DATA
    # Historical data points for trend detection validation
    
    return enhanced_synthetic_data
```

TEST_MODE ENVIRONMENT CONTROLS:
```bash
# Core Testing Mode
TEST_MODE=true                    # Enable synthetic data generation

# Testing Behavior Controls  
SKIP_FILE_OPERATIONS=true        # Prevent actual file creation during tests
DRY_RUN_UPLOADS=true            # Simulate Smartsheet uploads without API calls
MOCK_SMARTSHEET_UPLOAD=true     # Mock all external API operations

# Synthetic Data Customization
SYNTHETIC_WR_COUNT=8            # Number of Work Requests to generate (default: 8)
SYNTHETIC_ROW_VARIANCE=15       # Row count variation per WR (±15 rows)
ENABLE_AUDIT_ANOMALIES=true     # Include pricing anomalies for audit testing

# Test Scope Filtering
WR_FILTER=WR_90093002,WR_82131472  # Test specific Work Requests only
DEBUG_SAMPLE_ROWS=10            # Show detailed output for first N rows
```

VALIDATION TESTING PATTERNS:
```python
# Business Logic Validation
def test_row_validation_logic():
    """Validates the 3 critical business conditions"""
    
    test_cases = [
        # Valid row (should pass)
        {"Work Request #": "WR123", "Units Completed?": True, "Units Total Price": "100.50", "Weekly Reference Logged Date": "2024-08-17"},
        
        # Missing WR (should fail)  
        {"Work Request #": "", "Units Completed?": True, "Units Total Price": "100.50", "Weekly Reference Logged Date": "2024-08-17"},
        
        # Not completed (should fail)
        {"Work Request #": "WR123", "Units Completed?": False, "Units Total Price": "100.50", "Weekly Reference Logged Date": "2024-08-17"},
        
        # Zero price (should fail)
        {"Work Request #": "WR123", "Units Completed?": True, "Units Total Price": "0.00", "Weekly Reference Logged Date": "2024-08-17"},
        
        # Missing date (should fail)
        {"Work Request #": "WR123", "Units Completed?": True, "Units Total Price": "100.50", "Weekly Reference Logged Date": ""}
    ]
    
    for test_row in test_cases:
        is_valid, reason = is_valid_row(test_row)
        # Assert expected validation results

# Column Mapping Validation
def test_synonym_mapping():
    """Validates flexible column synonym system"""
    
    synonym_tests = [
        {"input": "Total Price", "expected": "Units Total Price"},
        {"input": "Redlined Total Price", "expected": "Units Total Price"}, 
        {"input": "Point #", "expected": "Pole #"},
        {"input": "Qty", "expected": "Quantity"},
        {"input": "Units Completed", "expected": "Units Completed?"}
    ]
    
    for test in synonym_tests:
        mapped = apply_column_synonyms(test["input"])
        assert mapped == test["expected"]

# Hash-Based Change Detection Testing  
def test_change_detection():
    """Validates hash generation and change detection logic"""
    
    # Identical data should generate same hash
    rows1 = generate_test_rows("WR123", base_data=True)
    rows2 = generate_test_rows("WR123", base_data=True)  # Same data
    hash1 = calculate_data_hash(rows1)
    hash2 = calculate_data_hash(rows2)
    assert hash1 == hash2, "Identical data should produce identical hashes"
    
    # Modified data should generate different hash
    rows3 = generate_test_rows("WR123", modify_price=True)  # Change price
    hash3 = calculate_data_hash(rows3)
    assert hash1 != hash3, "Modified data should produce different hash"
    
    # Extended vs standard change detection
    if EXTENDED_CHANGE_DETECTION:
        # Changes in foreman/dept should affect hash in extended mode
        rows4 = generate_test_rows("WR123", modify_foreman=True)
        hash4 = calculate_data_hash(rows4)
        assert hash1 != hash4, "Foreman change should affect hash in extended mode"
```

AUDIT SYSTEM TESTING:
```python
def test_audit_anomaly_detection():
    """Validates price anomaly detection with known test cases"""
    
    # Generate synthetic data with known anomalies
    test_rows = generate_anomaly_test_data()
    audit_system = BillingAudit(mock_client=True)
    results = audit_system.audit_financial_data([], test_rows)
    
    # Should detect price variance anomalies
    anomalies = results.get("anomalies_detected", [])
    assert len(anomalies) >= 1, "Should detect injected price anomalies"
    
    # Should calculate appropriate risk level
    risk_level = results.get("summary", {}).get("risk_level", "UNKNOWN")
    assert risk_level in ["LOW", "MEDIUM", "HIGH"], "Should assign valid risk level"

def test_audit_trend_analysis():
    """Validates trend detection between audit runs"""
    
    # First audit run (baseline)
    baseline_results = run_audit_with_test_data(issue_count=1)
    
    # Second audit run (increased issues)  
    current_results = run_audit_with_test_data(issue_count=3)
    
    # Should detect worsening trend
    trend = current_results.get("trend", {})
    assert trend.get("risk_direction") == "worsening", "Should detect increasing issues"
    assert trend.get("issues_delta") == 2, "Should calculate correct issue delta"
```

EXCEL GENERATION TESTING:
```python
def test_excel_formatting():
    """Validates Excel file generation and formatting"""
    
    test_rows = generate_test_rows("WR_TEST123", row_count=5)
    
    # Generate Excel in test mode
    with patch('openpyxl.Workbook') as mock_wb:
        excel_path = generate_excel("WR_TEST123", test_rows, datetime.now())
        
        # Should create workbook with proper structure
        mock_wb.assert_called_once()
        
        # Should apply corporate formatting
        # Should include logo (if available)
        # Should have proper column headers
        # Should calculate totals correctly

def test_filename_generation():
    """Validates file naming convention and hash integration"""
    
    test_wr = "WR_90093002"
    test_date = "081725"
    test_hash = "90f4f758"
    
    filename = generate_filename(test_wr, test_date, test_hash)
    
    # Should match expected pattern
    expected_pattern = f"WR_{test_wr}_WeekEnding_{test_date}_*_{test_hash[:8]}.xlsx"
    assert re.match(expected_pattern.replace('*', r'\d{6}'), filename), "Should match naming convention"
```

INTEGRATION TESTING PATTERNS:
```python
def test_end_to_end_workflow():
    """Full workflow test using synthetic data"""
    
    # Setup TEST_MODE environment
    os.environ['TEST_MODE'] = 'true'
    os.environ['SKIP_FILE_OPERATIONS'] = 'true'
    os.environ['DEBUG_SAMPLE_ROWS'] = '3'
    
    # Run main workflow
    result = run_main_workflow()
    
    # Validate expected outcomes
    assert result['groups_processed'] >= 8, "Should process expected WR groups"
    assert result['total_rows'] >= 80, "Should process expected row count" 
    assert result['audit_completed'], "Should complete audit analysis"
    assert result['risk_level'] in ['LOW', 'MEDIUM', 'HIGH'], "Should assign risk level"

def test_error_resilience():
    """Tests system behavior under error conditions"""
    
    # Test with missing API token (should gracefully degrade)
    os.environ.pop('SMARTSHEET_API_TOKEN', None)
    result = run_with_error_conditions()
    assert result['completed_with_degradation'], "Should handle missing token gracefully"
    
    # Test with invalid sheet ID (should skip problematic sheets)
    invalid_sheet_test()
    
    # Test with malformed data (should filter invalid rows)
    malformed_data_test()
```

PERFORMANCE TESTING:
```python
def test_synthetic_data_performance():
    """Validates synthetic data generation performance"""
    
    import time
    
    start_time = time.time()
    synthetic_data = generate_comprehensive_synthetic_data()
    generation_time = time.time() - start_time
    
    # Should generate reasonable amount of data quickly
    assert len(synthetic_data) >= 80, "Should generate sufficient test data"
    assert generation_time < 5.0, "Should generate data within 5 seconds"
    
    # Should have realistic distribution
    wr_counts = {}
    for row in synthetic_data:
        wr = row.get('Work Request #')
        wr_counts[wr] = wr_counts.get(wr, 0) + 1
    
    assert len(wr_counts) >= 8, "Should have multiple Work Requests"
    assert all(count >= 5 for count in wr_counts.values()), "Each WR should have multiple rows"
```

TESTING WORKFLOW COMMANDS:
```bash
# Development Testing
TEST_MODE=true DEBUG_SAMPLE_ROWS=5 python generate_weekly_pdfs.py

# Logic Testing (no files)  
TEST_MODE=true SKIP_FILE_OPERATIONS=true python generate_weekly_pdfs.py

# Audit System Testing
TEST_MODE=true ENABLE_AUDIT_ANOMALIES=true python audit_billing_changes.py

# Specific WR Testing
TEST_MODE=true WR_FILTER=WR_90093002 PER_CELL_DEBUG_ENABLED=true python generate_weekly_pdfs.py

# Performance Testing
TEST_MODE=true SYNTHETIC_WR_COUNT=15 SYNTHETIC_ROW_VARIANCE=25 time python generate_weekly_pdfs.py

# Hash Detection Testing
TEST_MODE=true EXTENDED_CHANGE_DETECTION=true python generate_weekly_pdfs.py
TEST_MODE=true FORCE_GENERATION=true python generate_weekly_pdfs.py  # Second run should skip due to hash
```

VALIDATION CHECKLIST:
- [ ] Synthetic data generation produces realistic business patterns
- [ ] All business validation rules correctly implemented  
- [ ] Column synonym mapping handles production variations
- [ ] Hash-based change detection works in both standard and extended modes
- [ ] Audit system detects injected anomalies and calculates risk levels
- [ ] Excel generation maintains corporate formatting standards
- [ ] Error handling provides graceful degradation under failure conditions
- [ ] Performance remains acceptable with synthetic data generation
- [ ] Integration with GitHub Actions workflows functions correctly
- [ ] Environment variable controls behave as documented

The testing system provides comprehensive validation coverage while enabling rapid development and debugging without requiring production API access or real Smartsheet data.
```

## Test Data Generation Prompt
```
You are creating realistic test data for the Generate-Weekly-PDFs-DSR-Resiliency billing system.

TEST DATA REQUIREMENTS:
Create comprehensive synthetic billing data that mirrors production patterns while providing comprehensive test coverage for all system components including business logic validation, audit anomaly detection, and Excel generation formatting.

REALISTIC WORK REQUEST PATTERNS:
```python
def create_realistic_wr_scenarios():
    """
    Generate Work Requests that mirror actual utility field operations
    Each WR represents different types of electrical utility work
    """
    
    scenarios = {
        # Emergency Storm Damage Repair
        "WR_90093002": {
            "type": "emergency_repair",
            "complexity": "high",
            "crew_size": "large", 
            "equipment": ["transformers", "poles", "conductors"],
            "row_count": (15, 20),
            "price_variance": 1.3,  # Emergency work costs more
            "foreman": "Johnson",
            "dept": "100",
            "area": "North District",
            "scenario": "Storm damage with multiple equipment failures"
        },
        
        # Scheduled Maintenance Project  
        "WR_82131472": {
            "type": "scheduled_maintenance",
            "complexity": "medium",
            "crew_size": "standard",
            "equipment": ["reclosers", "switches", "meters"], 
            "row_count": (8, 12),
            "price_variance": 1.0,  # Standard pricing
            "foreman": "Smith",
            "dept": "200", 
            "area": "South District",
            "scenario": "Quarterly equipment inspection and maintenance"
        },
        
        # New Service Installation
        "WR_83812901": {
            "type": "installation_project", 
            "complexity": "high",
            "crew_size": "large",
            "equipment": ["transformers", "service_connections", "meters"],
            "row_count": (10, 15),
            "price_variance": 1.1,  # Project work slightly higher
            "foreman": "Rodriguez", 
            "dept": "150",
            "area": "Central",
            "scenario": "New residential subdivision electrical service"
        }
    }
    
    return scenarios

def generate_realistic_equipment_data():
    """
    Create equipment and CU codes that match utility industry standards
    """
    
    equipment_catalog = {
        # Transformer Work
        "T001": {"desc": "Transformer Installation - 25KVA", "base_price": 2500, "unit": "EA", "complexity": "high"},
        "T002": {"desc": "Transformer Replacement - 50KVA", "base_price": 3200, "unit": "EA", "complexity": "high"},
        "T003": {"desc": "Transformer Maintenance", "base_price": 450, "unit": "EA", "complexity": "medium"},
        
        # Pole Operations
        "P001": {"desc": "Pole Installation - 35ft Class 4", "base_price": 1200, "unit": "EA", "complexity": "high"},
        "P002": {"desc": "Pole Replacement - Storm Damage", "base_price": 1500, "unit": "EA", "complexity": "high"}, 
        "P003": {"desc": "Pole Inspection", "base_price": 85, "unit": "EA", "complexity": "low"},
        
        # Conductor & Cable Work
        "C001": {"desc": "Primary Conductor Repair", "base_price": 45, "unit": "FT", "complexity": "medium"},
        "C002": {"desc": "Service Cable Installation", "base_price": 12, "unit": "FT", "complexity": "medium"},
        "C003": {"desc": "Underground Cable Splicing", "base_price": 180, "unit": "EA", "complexity": "high"},
        
        # Metering & Services  
        "M001": {"desc": "Residential Meter Installation", "base_price": 350, "unit": "EA", "complexity": "medium"},
        "M002": {"desc": "Commercial Meter Installation", "base_price": 750, "unit": "EA", "complexity": "high"},
        "M003": {"desc": "Service Connection - Overhead", "base_price": 800, "unit": "EA", "complexity": "medium"},
        
        # Protection & Control
        "R001": {"desc": "Recloser Installation", "base_price": 4500, "unit": "EA", "complexity": "high"},
        "R002": {"desc": "Recloser Maintenance", "base_price": 380, "unit": "EA", "complexity": "medium"},
        "S001": {"desc": "Switch Operation", "base_price": 120, "unit": "EA", "complexity": "low"}
    }
    
    return equipment_catalog
```

GEOGRAPHIC AND CREW DIVERSITY:
```python
def create_crew_assignments():
    """
    Realistic field crew assignments with geographic distribution
    """
    
    crew_data = {
        "foremen": [
            {"name": "Johnson", "dept": "100", "area": "North District", "specialty": "emergency_response"},
            {"name": "Smith", "dept": "200", "area": "South District", "specialty": "maintenance"}, 
            {"name": "Rodriguez", "dept": "150", "area": "Central", "specialty": "construction"},
            {"name": "Chen", "dept": "300", "area": "East Zone", "specialty": "metering"},
            {"name": "Williams", "dept": "250", "area": "West Zone", "specialty": "underground"}, 
            {"name": "Davis", "dept": "100", "area": "North District", "specialty": "storm_repair"}
        ],
        
        "service_areas": [
            "North District", "South District", "Central", "East Zone", "West Zone",
            "Industrial Park", "Downtown Core", "Residential West", "Commercial East"
        ],
        
        "customer_types": [
            "ABC Manufacturing", "Smith Residence", "Downtown Office Complex", 
            "City Municipal Building", "Retail Shopping Center", "Johnson Farm",
            "Miller Warehouse", "Community Center", "School District #5"
        ]
    }
    
    return crew_data

def assign_realistic_locations():
    """
    Generate realistic pole numbers and work locations
    """
    
    # Pole numbering follows utility conventions
    pole_prefixes = ["N", "S", "E", "W", "C"]  # Geographic quadrants
    pole_numbers = []
    
    for prefix in pole_prefixes:
        for i in range(100, 999, 50):  # Realistic pole number spacing
            pole_numbers.append(f"{prefix}{i}")
    
    return pole_numbers
```

BUSINESS LOGIC TEST CASES:
```python
def create_validation_test_scenarios():
    """
    Specific test cases for business rule validation
    """
    
    test_scenarios = {
        # Valid billing scenarios (should pass all validation)
        "valid_standard_work": {
            "Work Request #": "WR_TEST001",
            "Units Completed?": True,
            "Units Total Price": "1250.00", 
            "Weekly Reference Logged Date": "2024-08-17",
            "Foreman": "Johnson",
            "CU": "P001",
            "Quantity": "1"
        },
        
        # Edge case scenarios
        "minimum_valid_price": {
            "Units Total Price": "0.01"  # Smallest valid price
        },
        
        "maximum_realistic_price": {
            "Units Total Price": "25000.00"  # Large equipment installation
        },
        
        # Boundary condition testing
        "date_boundary_cases": [
            "2024-08-11",  # Week start
            "2024-08-17",  # Week end  
            "2024-08-10",  # Previous week (should be excluded)
            "2024-08-18"   # Next week (should be excluded)
        ],
        
        # Data quality test cases (should fail validation)
        "invalid_scenarios": [
            {"Work Request #": "", "reason": "missing_wr_number"},
            {"Units Completed?": False, "reason": "not_completed"}, 
            {"Units Total Price": "0.00", "reason": "zero_price"},
            {"Units Total Price": "-100.00", "reason": "negative_price"},
            {"Weekly Reference Logged Date": "", "reason": "missing_date"},
            {"Weekly Reference Logged Date": "invalid-date", "reason": "malformed_date"}
        ]
    }
    
    return test_scenarios
```

AUDIT ANOMALY INJECTION:
```python
def inject_known_audit_anomalies():
    """
    Create specific anomalies for audit system testing
    """
    
    anomaly_patterns = {
        # Price variance anomaly (>50% difference within WR)
        "price_variance_wr90093002": [
            {"Work Request #": "WR_90093002", "CU": "T001", "Units Total Price": "2500.00"},  # Normal
            {"Work Request #": "WR_90093002", "CU": "T001", "Units Total Price": "4800.00"},  # 92% higher
            {"Work Request #": "WR_90093002", "CU": "T001", "Units Total Price": "1100.00"}   # 56% lower
        ],
        
        # Data consistency issues 
        "data_integrity_issues": [
            {"Work Request #": "WR_82131472", "Units Total Price": "-500.00"},  # Negative price
            {"Work Request #": "WR_83812901", "Quantity": "0"},                # Zero quantity
            {"Work Request #": "", "Units Total Price": "1200.00"}             # Missing WR
        ],
        
        # Trend analysis test data (simulate historical progression)
        "trend_progression": {
            "previous_audit": {"total_issues": 1, "risk_level": "LOW"},
            "current_audit": {"total_issues": 4, "risk_level": "HIGH"},  # Worsening trend
        }
    }
    
    return anomaly_patterns
```

DATE AND TIMING PATTERNS:
```python
def generate_realistic_date_patterns():
    """
    Create date patterns that match business operations
    """
    
    # Week ending August 17, 2024 (Saturday)
    base_week_end = datetime(2024, 8, 17)
    week_start = base_week_end - timedelta(days=6)  # Previous Sunday
    
    date_patterns = {
        # Normal work distribution (heavier early/mid week)
        "weekday_distribution": {
            "monday": 25,    # 25% of work
            "tuesday": 20,   # 20% of work  
            "wednesday": 20, # 20% of work
            "thursday": 15,  # 15% of work
            "friday": 12,    # 12% of work
            "saturday": 5,   # 5% of work (emergency only)
            "sunday": 3      # 3% of work (emergency only)
        },
        
        # Emergency work can occur any day
        "emergency_patterns": {
            "storm_damage": "any_day_including_weekends",
            "power_outage": "24x7_response", 
            "safety_hazard": "immediate_response"
        }
    }
    
    # Generate specific dates within the week
    work_dates = []
    for i in range(7):  # 7 days in billing week
        work_date = week_start + timedelta(days=i)
        work_dates.append(work_date.strftime("%Y-%m-%d"))
    
    return work_dates, date_patterns
```

TEST DATA ASSEMBLY:
```python
def assemble_comprehensive_test_dataset():
    """
    Combine all patterns into complete synthetic dataset
    """
    
    scenarios = create_realistic_wr_scenarios()
    equipment = generate_realistic_equipment_data() 
    crews = create_crew_assignments()
    validation_cases = create_validation_test_scenarios()
    audit_anomalies = inject_known_audit_anomalies()
    dates, date_patterns = generate_realistic_date_patterns()
    
    complete_dataset = []
    
    # Generate rows for each Work Request scenario
    for wr_id, scenario in scenarios.items():
        row_count = random.randint(*scenario["row_count"])
        
        for i in range(row_count):
            # Select equipment appropriate to scenario
            available_equipment = [eq for eq in equipment.values() 
                                 if any(equip in eq["desc"].lower() 
                                       for equip in scenario["equipment"])]
            
            selected_equipment = random.choice(available_equipment)
            
            # Create realistic row
            row = {
                "Work Request #": wr_id,
                "Foreman": scenario["foreman"], 
                "Dept #": scenario["dept"],
                "Area": scenario["area"],
                "Weekly Reference Logged Date": random.choice(dates),
                "CU": random.choice(list(equipment.keys())),
                "CU Description": selected_equipment["desc"],
                "Unit of Measure": selected_equipment["unit"], 
                "Quantity": str(random.uniform(1, 10)),
                "Units Total Price": str(selected_equipment["base_price"] * scenario["price_variance"] * random.uniform(0.8, 1.2)),
                "Units Completed?": True,
                "Customer Name": random.choice(crews["customer_types"]),
                "Pole #": random.choice(assign_realistic_locations())
            }
            
            complete_dataset.append(row)
    
    # Add validation test cases
    complete_dataset.extend(create_specific_validation_rows())
    
    # Inject audit anomalies  
    complete_dataset.extend(create_audit_anomaly_rows(audit_anomalies))
    
    return complete_dataset  # ~80+ realistic rows for comprehensive testing
```

This test data generation system creates comprehensive, realistic synthetic data that enables thorough testing of all system components while maintaining production-like patterns and business logic scenarios.
```

## CRITICAL CHANGE DETECTION TESTING

### Hash Calculation Validation Tests
Test the dual critical fixes implemented for accurate change detection:

```python
# TEST 1: Units Completed? Field Detection
def test_units_completed_change_detection():
    """Verify hash changes when Units Completed? status changes"""
    base_row = {
        'Work Request #': 'WR_TEST_001',
        'Units Total Price': '$1,250.00',
        'CU': 'T123', 'Quantity': '5',
        'Snapshot Date': '2024-08-17'
    }
    
    # Test completion status changes
    row_incomplete = {**base_row, 'Units Completed?': False}
    row_complete = {**base_row, 'Units Completed?': True}
    
    hash_incomplete = calculate_data_hash([row_incomplete])  
    hash_complete = calculate_data_hash([row_complete])
    
    # EXPECTED: Different hashes for different completion status
    assert hash_incomplete != hash_complete, "Units Completed? changes must trigger hash change"
    
# TEST 2: Price Format Normalization  
def test_price_format_normalization():
    """Verify same economic value = same hash regardless of format"""
    base_row = {
        'Work Request #': 'WR_TEST_002',
        'Units Completed?': True,
        'CU': 'T456', 'Quantity': '3',
        'Snapshot Date': '2024-08-17'
    }
    
    # Same economic value in different formats
    price_formats = ['$1,250.00', '1250.00', '$1250', '1,250.00', 1250.0]
    hashes = []
    
    for price_format in price_formats:
        test_row = {**base_row, 'Units Total Price': price_format}
        hash_value = calculate_data_hash([test_row])
        hashes.append(hash_value)
    
    # EXPECTED: All hashes identical for same economic value
    assert len(set(hashes)) == 1, "Same economic value must produce identical hash"
    
# TEST 3: Actual Price Change Detection
def test_actual_price_changes():
    """Verify different economic values = different hashes"""
    base_row = {
        'Work Request #': 'WR_TEST_003', 
        'Units Completed?': True,
        'CU': 'T789', 'Quantity': '2',
        'Snapshot Date': '2024-08-17'
    }
    
    # Different actual price values
    price_values = ['$500.00', '$1,250.00', '$2,500.00']
    hashes = []
    
    for price in price_values:
        test_row = {**base_row, 'Units Total Price': price}
        hash_value = calculate_data_hash([test_row])
        hashes.append(hash_value)
    
    # EXPECTED: All hashes different for different economic values
    assert len(set(hashes)) == len(hashes), "Different prices must produce different hashes"

# INTEGRATION TEST: Complete Change Detection Workflow
def test_complete_change_detection_workflow():
    """Test end-to-end change detection with realistic scenarios"""
    
    # Scenario 1: Work completion (Units Completed? false → true)
    # Should trigger regeneration
    
    # Scenario 2: Price format change only ($1,250.00 → 1250.00)  
    # Should NOT trigger regeneration (same economic value)
    
    # Scenario 3: Actual price increase ($1,250.00 → $1,500.00)
    # Should trigger regeneration
    
    # Scenario 4: Multiple field changes (completion + price + quantity)
    # Should trigger regeneration
    
    pass  # Implement based on specific testing needs
```

### Change Detection Validation Checklist
- ✅ Units Completed? status changes detected
- ✅ Price format variations normalized  
- ✅ Actual price changes detected
- ✅ No false positives from format differences
- ✅ Hash consistency across system restarts
- ✅ Performance impact acceptable (<100ms for 550 rows)

````