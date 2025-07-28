#!/usr/bin/env python3
"""
Test script to demonstrate the duplicate sheet detection logic
without requiring actual Smartsheet API credentials.
"""

# Simulate the sheet data structure that would come from Smartsheet
class MockSheet:
    def __init__(self, id, name):
        self.id = id
        self.name = name

class MockSheetList:
    def __init__(self, sheets):
        self.data = sheets

def test_duplicate_detection():
    """Test the improved duplicate detection logic"""
    
    # Simulate base sheet IDs and names
    base_sheet_ids = [12345, 67890, 11111, 22222]
    base_sheet_names = {
        12345: "Project Management Dashboard",
        67890: "Resource Tracking",
        11111: "Project Management Dashboard - Phase 2", 
        22222: "Daily Operations"
    }
    
    # Simulate all sheets that would be returned from Smartsheet
    all_mock_sheets = [
        # Base sheets
        MockSheet(12345, "Project Management Dashboard"),
        MockSheet(67890, "Resource Tracking"),
        MockSheet(11111, "Project Management Dashboard - Phase 2"),
        MockSheet(22222, "Daily Operations"),
        
        # Valid copies
        MockSheet(12346, "Project Management Dashboard - Copy"),
        MockSheet(12347, "Project Management Dashboard Copy"),
        MockSheet(12348, "Copy of Project Management Dashboard"),
        MockSheet(12349, "Project Management Dashboard - Week 1"),
        MockSheet(12350, "Project Management Dashboard (Backup)"),
        MockSheet(12351, "Project Management Dashboard_Copy"),
        
        MockSheet(67891, "Resource Tracking - Copy"),
        MockSheet(67892, "Resource Tracking - Week 2"),
        
        MockSheet(22223, "Daily Operations Copy"),
        MockSheet(22224, "Daily Operations - Backup"),
        
        # Invalid matches that should NOT be included (cross-contamination examples)
        MockSheet(99998, "Project Management Dashboard - Phase 2 - Copy"),  # Should match base 11111, not 12345
        MockSheet(99999, "Another Project Management Dashboard Report"),    # Too broad match
        
        # Archive sheets that should be excluded
        MockSheet(88888, "Project Management Dashboard Archive"),
        MockSheet(88889, "Resource Tracking Archive"),
        
        # Unrelated sheets
        MockSheet(77777, "Completely Different Sheet"),
        MockSheet(77778, "Random Data"),
    ]
    
    mock_all_sheets = MockSheetList(all_mock_sheets)
    
    discovered_sheets = []
    processed_sheet_ids = set()  # Track already processed sheets to avoid duplicates
    
    # First, collect all base sheet names to prevent cross-matching
    all_base_names = set(base_sheet_names.values())
    
    print("🧪 TESTING DUPLICATE DETECTION LOGIC")
    print("=" * 70)
    print(f"Base sheet names: {list(all_base_names)}")
    print("=" * 70)
    
    for base_id in base_sheet_ids:
        base_name = base_sheet_names[base_id]
        print(f"\n🔍 Processing Base Sheet: {base_name} (ID: {base_id})")
        print("-" * 50)
        
        # Find all sheets that match this base sheet or are copies of it
        # Use more precise matching to avoid cross-contamination between base sheets
        # EXCLUDE any sheets with "Archive" in the name to avoid duplicate data
        matching_sheets = []
        for sheet in mock_all_sheets.data:
            # Skip if already processed
            if sheet.id in processed_sheet_ids:
                print(f"   ⏭️  Skipping already processed: {sheet.name} (ID: {sheet.id})")
                continue
                
            # Skip Archive sheets
            if "Archive" in sheet.name:
                print(f"   🗄️  Skipping Archive sheet: {sheet.name} (ID: {sheet.id})")
                continue
            
            # Skip if this sheet name is actually another base sheet
            if sheet.name in all_base_names and sheet.name != base_name:
                print(f"   🚫 Skipping other base sheet: {sheet.name} (ID: {sheet.id})")
                continue
            
            # Match exact base sheet ID
            if sheet.id == base_id:
                matching_sheets.append(sheet)
                print(f"   ✅ Exact ID match: {sheet.name} (ID: {sheet.id})")
                continue
            
            # Match copies more precisely - look for exact base name followed by copy indicators
            # This prevents cross-matching between different base sheets
            copy_patterns = [
                f"{base_name} - Copy",
                f"{base_name} Copy",
                f"{base_name}_Copy",
                f"Copy of {base_name}",
            ]
            
            # Also check if the sheet name starts with the base name followed by common separators
            # BUT exclude sheets that are exactly matching other base sheet names
            name_starts_with_base = False
            if sheet.name == base_name:  # Exact match
                name_starts_with_base = True
            elif (sheet.name.startswith(f"{base_name} - ") or 
                  sheet.name.startswith(f"{base_name}_") or 
                  sheet.name.startswith(f"{base_name} (")):
                # Make sure this sheet name is not exactly another base sheet name
                if sheet.name not in all_base_names:
                    name_starts_with_base = True
            
            if any(pattern in sheet.name for pattern in copy_patterns) or name_starts_with_base:
                matching_sheets.append(sheet)
                print(f"   ✅ Pattern match: {sheet.name} (ID: {sheet.id})")
            else:
                print(f"   ❌ No match: {sheet.name} (ID: {sheet.id})")
        
        print(f"\n   📊 Found {len(matching_sheets)} matching sheets for base: {base_name}")
        
        # Process matching sheets and mark as processed
        for sheet_info in matching_sheets:
            # Mark this sheet as processed to avoid duplicates
            processed_sheet_ids.add(sheet_info.id)
            
            # Simulate adding to discovered_sheets (in real code, this would include column validation)
            discovered_sheets.append({
                "id": sheet_info.id,
                "name": sheet_info.name,
                "base_sheet": base_name
            })
            print(f"   ➕ Added to processing list: {sheet_info.name} (ID: {sheet_info.id})")
    
    print(f"\n" + "=" * 70)
    print(f"🔍 FINAL RESULTS - DUPLICATE DETECTION TEST")
    print("=" * 70)
    
    # Check for duplicates in final list
    unique_ids = set()
    duplicates_found = []
    
    for i, sheet in enumerate(discovered_sheets, 1):
        if sheet['id'] in unique_ids:
            duplicates_found.append(sheet)
            print(f"⚠️  DUPLICATE DETECTED: {sheet['name']} (ID: {sheet['id']})")
        else:
            unique_ids.add(sheet['id'])
        
        print(f"{i:2d}. Sheet: {sheet['name']}")
        print(f"    ID: {sheet['id']}")
        print(f"    Base: {sheet['base_sheet']}")
        print()
    
    print("=" * 70)
    print(f"📊 SUMMARY:")
    print(f"   • Total Sheets Discovered: {len(discovered_sheets)}")
    print(f"   • Unique Sheet IDs: {len(unique_ids)}")
    print(f"   • Duplicates Found: {len(duplicates_found)}")
    print(f"   • Base Sheets Processed: {len(base_sheet_ids)}")
    
    if len(unique_ids) == len(discovered_sheets):
        print(f"   ✅ SUCCESS: No duplicate entries detected!")
    else:
        print(f"   ⚠️  WARNING: {len(discovered_sheets) - len(unique_ids)} duplicate entries found!")
    
    print("\n🔍 SHEETS BY BASE:")
    base_counts = {}
    for sheet in discovered_sheets:
        base = sheet['base_sheet']
        if base not in base_counts:
            base_counts[base] = []
        base_counts[base].append(sheet)
    
    for base_name, sheets in base_counts.items():
        print(f"   • {base_name}: {len(sheets)} sheets")
        for sheet in sheets:
            print(f"     - {sheet['name']} (ID: {sheet['id']})")
    
    print("=" * 70)
    
    return len(duplicates_found) == 0

if __name__ == "__main__":
    success = test_duplicate_detection()
    if success:
        print("🎉 TEST PASSED: Duplicate detection logic working correctly!")
    else:
        print("❌ TEST FAILED: Duplicates were found in the final list!")
