#!/usr/bin/env python3
"""
Comprehensive diagnostic script for pricing issues in completed work items.

This script analyzes why rows marked as "Units Completed? = true" with valid dates
might not appear in the generated reports, focusing on pricing-related exclusions.
"""

import os
import json
import logging
import smartsheet
from datetime import datetime
from collections import defaultdict, Counter
from generate_weekly_pdfs import (
    discover_source_sheets, get_all_source_rows, 
    parse_price, is_checked, excel_serial_to_date
)

# Enable comprehensive diagnostics
os.environ['TEST_MODE'] = 'true'
os.environ['FILTER_DIAGNOSTICS'] = 'true' 
os.environ['DEBUG_SAMPLE_ROWS'] = '10'
os.environ['DEBUG_ESSENTIAL_ROWS'] = '10'
os.environ['FOREMAN_DIAGNOSTICS'] = 'true'
os.environ['LOG_UNKNOWN_COLUMNS'] = 'true'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def analyze_pricing_issues():
    """Comprehensive analysis of pricing issues in completed work items."""
    
    print("🔍 PRICING DIAGNOSTIC ANALYSIS")
    print("=" * 80)
    
    try:
        # Initialize client
        API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")
        if not API_TOKEN:
            print("⚠️ No SMARTSHEET_API_TOKEN found - running basic analysis on generate_weekly_pdfs.py logic")
            analyze_filtering_logic()
            return
        
        client = smartsheet.Smartsheet(API_TOKEN)
        client.errors_as_exceptions(True)
        
        source_sheets = discover_source_sheets(client)
        
        print(f"\n📊 Found {len(source_sheets)} source sheets")
        for i, sheet in enumerate(source_sheets, 1):
            print(f"   {i}. {sheet['name']} (ID: {sheet['id']})")
        
        # Get all rows with detailed diagnostics
        all_rows = get_all_source_rows(client, source_sheets)
        
        print(f"\n✅ Retrieved {len(all_rows)} valid rows after filtering")
        
        # Analyze excluded rows by re-processing with detailed logging
        print("\n" + "="*80)
        print("🔬 DETAILED ROW-BY-ROW ANALYSIS")
        print("="*80)
        
        completed_with_dates_stats = analyze_completed_rows_with_dates(client, source_sheets)
        pricing_analysis = analyze_pricing_patterns(all_rows)
        
        print("\n" + "="*80)
        print("📋 SUMMARY REPORT")
        print("="*80)
        
        print_summary_report(completed_with_dates_stats, pricing_analysis, len(all_rows))
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()

def analyze_completed_rows_with_dates(client, source_sheets):
    """Analyze all rows marked as completed with valid dates to find pricing issues."""
    
    stats = {
        'total_rows_processed': 0,
        'completed_with_dates': 0,
        'completed_with_dates_and_price': 0,
        'completed_with_dates_no_price': 0,
        'completed_with_dates_zero_price': 0,
        'completed_with_dates_invalid_price': 0,
        'price_format_issues': [],
        'missing_fields_analysis': defaultdict(int),
        'sample_excluded_rows': []
    }
    
    for source in source_sheets:
        try:
            print(f"\n🔍 Analyzing sheet: {source['name']}")
            sheet = client.Sheets.get_sheet(source['id'])
            column_mapping = source['column_mapping']
            
            for row in sheet.rows:
                stats['total_rows_processed'] += 1
                row_data = {}
                
                # Extract all mapped data
                for cell in row.cells:
                    for mapped_name, column_id in column_mapping.items():
                        if cell.column_id == column_id:
                            row_data[mapped_name] = cell.display_value or cell.value
                            break
                
                # Check if this row is marked as completed
                units_completed = row_data.get('Units Completed?')
                if not is_checked(units_completed):
                    continue
                
                # Check if it has valid dates
                snapshot_date = row_data.get('Snapshot Date')
                weekly_date = row_data.get('Weekly Reference Logged Date')
                work_request = row_data.get('Work Request #')
                
                if not (snapshot_date and weekly_date and work_request):
                    continue
                
                stats['completed_with_dates'] += 1
                
                # Now analyze the pricing
                price_raw = row_data.get('Units Total Price')
                print(f"\n   📝 Row analysis:")
                print(f"      WR: {work_request}")
                print(f"      Snapshot Date: {snapshot_date}")
                print(f"      Weekly Date: {weekly_date}")
                print(f"      Units Completed?: {units_completed} -> {is_checked(units_completed)}")
                print(f"      Raw Price: {price_raw!r}")
                
                if price_raw is None or price_raw == "":
                    stats['completed_with_dates_no_price'] += 1
                    stats['missing_fields_analysis']['price_completely_missing'] += 1
                    print(f"      ❌ ISSUE: Price field is completely missing/empty")
                    
                    if len(stats['sample_excluded_rows']) < 5:
                        stats['sample_excluded_rows'].append({
                            'wr': work_request,
                            'issue': 'Price field missing/empty',
                            'raw_price': price_raw,
                            'sheet': source['name']
                        })
                    continue
                
                try:
                    price_val = parse_price(price_raw)
                    print(f"      Parsed Price: ${price_val:.2f}")
                    
                    if price_val <= 0:
                        stats['completed_with_dates_zero_price'] += 1
                        stats['missing_fields_analysis']['price_zero_or_negative'] += 1
                        print(f"      ❌ ISSUE: Price is zero or negative")
                        
                        if len(stats['sample_excluded_rows']) < 5:
                            stats['sample_excluded_rows'].append({
                                'wr': work_request,
                                'issue': 'Price is zero/negative',
                                'raw_price': price_raw,
                                'parsed_price': price_val,
                                'sheet': source['name']
                            })
                    else:
                        stats['completed_with_dates_and_price'] += 1
                        print(f"      ✅ VALID: Row should be included in report")
                        
                except Exception as e:
                    stats['completed_with_dates_invalid_price'] += 1
                    stats['missing_fields_analysis']['price_parse_error'] += 1
                    stats['price_format_issues'].append({
                        'raw_value': price_raw,
                        'error': str(e),
                        'wr': work_request,
                        'sheet': source['name']
                    })
                    print(f"      ❌ ISSUE: Price parsing failed - {e}")
                    
                    if len(stats['sample_excluded_rows']) < 5:
                        stats['sample_excluded_rows'].append({
                            'wr': work_request,
                            'issue': f'Price parsing error: {e}',
                            'raw_price': price_raw,
                            'sheet': source['name']
                        })
        
        except Exception as e:
            print(f"❌ Error processing sheet {source['name']}: {e}")
    
    return stats

def analyze_pricing_patterns(valid_rows):
    """Analyze pricing patterns in the valid rows that made it through filtering."""
    
    analysis = {
        'total_valid_rows': len(valid_rows),
        'price_ranges': defaultdict(int),
        'zero_prices_included': 0,
        'missing_prices_included': 0,
        'price_format_variety': Counter(),
        'work_requests_with_pricing_issues': defaultdict(list)
    }
    
    for row in valid_rows:
        price_raw = row.get('Units Total Price')
        wr = row.get('Work Request #')
        
        if price_raw is None or price_raw == "":
            analysis['missing_prices_included'] += 1
            analysis['work_requests_with_pricing_issues'][wr].append('Missing price in valid row')
            continue
        
        try:
            price_val = parse_price(price_raw)
            
            if price_val <= 0:
                analysis['zero_prices_included'] += 1
                analysis['work_requests_with_pricing_issues'][wr].append(f'Zero price: {price_raw}')
            
            # Categorize price ranges
            if price_val == 0:
                analysis['price_ranges']['$0'] += 1
            elif price_val < 100:
                analysis['price_ranges']['$0.01-$99.99'] += 1
            elif price_val < 1000:
                analysis['price_ranges']['$100-$999.99'] += 1
            elif price_val < 5000:
                analysis['price_ranges']['$1,000-$4,999.99'] += 1
            else:
                analysis['price_ranges']['$5,000+'] += 1
            
            # Track price format variety
            analysis['price_format_variety'][str(type(price_raw).__name__)] += 1
            
        except Exception as e:
            analysis['work_requests_with_pricing_issues'][wr].append(f'Price parse error: {e}')
    
    return analysis

def print_summary_report(completed_stats, pricing_analysis, valid_rows_count):
    """Print a comprehensive summary report."""
    
    print("📊 COMPLETED ROWS WITH DATES ANALYSIS:")
    print(f"   Total rows processed: {completed_stats['total_rows_processed']:,}")
    print(f"   Completed + valid dates: {completed_stats['completed_with_dates']:,}")
    print(f"   Completed + dates + valid price: {completed_stats['completed_with_dates_and_price']:,}")
    print(f"   Completed + dates + NO price: {completed_stats['completed_with_dates_no_price']:,}")
    print(f"   Completed + dates + ZERO price: {completed_stats['completed_with_dates_zero_price']:,}")
    print(f"   Completed + dates + INVALID price: {completed_stats['completed_with_dates_invalid_price']:,}")
    
    if completed_stats['completed_with_dates'] > 0:
        inclusion_rate = (completed_stats['completed_with_dates_and_price'] / completed_stats['completed_with_dates']) * 100
        print(f"\n📈 INCLUSION RATE: {inclusion_rate:.1f}% of completed+dated rows have valid pricing")
    
    print(f"\n🔍 MISSING FIELD BREAKDOWN:")
    for issue, count in completed_stats['missing_fields_analysis'].items():
        print(f"   {issue}: {count:,}")
    
    if completed_stats['price_format_issues']:
        print(f"\n⚠️ PRICE FORMAT ISSUES ({len(completed_stats['price_format_issues'])} cases):")
        for issue in completed_stats['price_format_issues'][:5]:  # Show first 5
            print(f"   WR {issue['wr']}: '{issue['raw_value']}' -> {issue['error']}")
    
    if completed_stats['sample_excluded_rows']:
        print(f"\n❌ SAMPLE EXCLUDED ROWS:")
        for sample in completed_stats['sample_excluded_rows']:
            print(f"   WR {sample['wr']} ({sample['sheet']}): {sample['issue']}")
            if 'parsed_price' in sample:
                print(f"      Raw: {sample['raw_price']!r} -> Parsed: ${sample['parsed_price']:.2f}")
    
    print(f"\n✅ FINAL VALIDATION:")
    print(f"   Rows that passed all filters: {valid_rows_count:,}")
    print(f"   Expected based on completed+dated+priced: {completed_stats['completed_with_dates_and_price']:,}")
    
    if valid_rows_count != completed_stats['completed_with_dates_and_price']:
        print(f"   ⚠️ DISCREPANCY: {abs(valid_rows_count - completed_stats['completed_with_dates_and_price'])} row difference!")
        print("      This suggests additional filtering beyond pricing may be occurring.")
    else:
        print("   ✅ Numbers match - filtering is working as expected.")
    
    print(f"\n💰 PRICING PATTERNS IN VALID ROWS:")
    for price_range, count in sorted(pricing_analysis['price_ranges'].items()):
        print(f"   {price_range}: {count:,} rows")
    
    if pricing_analysis['zero_prices_included'] > 0:
        print(f"\n⚠️ WARNING: {pricing_analysis['zero_prices_included']} valid rows have $0 prices!")
    
    if pricing_analysis['work_requests_with_pricing_issues']:
        print(f"\n🔧 WORK REQUESTS WITH ISSUES ({len(pricing_analysis['work_requests_with_pricing_issues'])} WRs):")
        for wr, issues in list(pricing_analysis['work_requests_with_pricing_issues'].items())[:5]:
            print(f"   WR {wr}: {', '.join(issues)}")

def save_diagnostic_results(stats, analysis):
    """Save diagnostic results to JSON for further analysis."""
    
    results = {
        'timestamp': str(datetime.now()),
        'completed_rows_stats': stats,
        'pricing_analysis': dict(analysis),
        'recommendations': generate_recommendations(stats, analysis)
    }
    
    with open('generated_docs/pricing_diagnostic_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Diagnostic results saved to: generated_docs/pricing_diagnostic_results.json")

def generate_recommendations(stats, analysis):
    """Generate actionable recommendations based on the analysis."""
    
    recommendations = []
    
    if stats['completed_with_dates_no_price'] > 0:
        recommendations.append({
            'issue': 'Missing price fields',
            'count': stats['completed_with_dates_no_price'],
            'recommendation': 'Check column mapping for Units Total Price field in source sheets'
        })
    
    if stats['completed_with_dates_zero_price'] > 0:
        recommendations.append({
            'issue': 'Zero/negative prices',
            'count': stats['completed_with_dates_zero_price'], 
            'recommendation': 'Review data entry processes - completed work should have pricing'
        })
    
    if stats['completed_with_dates_invalid_price'] > 0:
        recommendations.append({
            'issue': 'Invalid price formats',
            'count': stats['completed_with_dates_invalid_price'],
            'recommendation': 'Standardize price field format or enhance parse_price() function'
        })
    
    return recommendations

def analyze_filtering_logic():
    """Analyze the filtering logic to identify potential pricing issues without API access."""
    
    print("\n🔍 ANALYZING FILTERING LOGIC FROM CODE")
    print("=" * 80)
    
    print("\n📋 REQUIRED CONDITIONS FOR ROW INCLUSION:")
    print("   1. ✅ Work Request # must exist and not be empty")
    print("   2. ✅ Weekly Reference Logged Date must exist and not be empty") 
    print("   3. ✅ Units Completed? must be checked/true (using is_checked() function)")
    print("   4. ✅ Units Total Price must exist, be parseable, and > 0")
    
    print("\n🔍 COMMON EXCLUSION REASONS:")
    print("   • Missing Work Request # field")
    print("   • Missing or invalid Weekly Reference Logged Date")
    print("   • Units Completed? not checked (false, 0, empty, etc.)")
    print("   • Units Total Price is missing, empty, $0, $0.00, or unparseable")
    
    print("\n💰 PRICE PARSING LOGIC:")
    print("   • Uses parse_price() function to convert string values to float")
    print("   • Handles formats like: '$1,250.00', '1250.00', '$1250', etc.")
    print("   • Excludes any row where parsed price <= 0")
    
    print("\n⚠️ POTENTIAL ISSUES TO CHECK:")
    print("   1. Column Mapping: Verify 'Units Total Price' column is correctly mapped")
    print("      - Check for alternate names: 'Total Price', 'Redlined Total Price'")
    print("   2. Data Format: Ensure price values are in recognizable format")
    print("      - Avoid special characters, extra spaces, or text in price fields")
    print("   3. Completion Status: Verify Units Completed? uses standard true/false values")
    print("      - Acceptable: true, 1, 'true', 'yes', checked boxes")
    print("      - Rejected: false, 0, '', 'false', 'no', unchecked boxes")
    
    print("\n🛠️ DIAGNOSTIC STEPS:")
    print("   1. Run with FILTER_DIAGNOSTICS=true to see exclusion counts")
    print("   2. Run with DEBUG_SAMPLE_ROWS=10 to see detailed row analysis")
    print("   3. Check generated logs for 'price_missing_or_zero' exclusions")
    print("   4. Verify column mappings in discovered source sheets")
    
    print("\n📊 TO RUN FULL DIAGNOSTIC WITH REAL DATA:")
    print("   1. Set SMARTSHEET_API_TOKEN environment variable")
    print("   2. Run: python diagnose_pricing_issues.py")
    print("   3. Or run: FILTER_DIAGNOSTICS=true python generate_weekly_pdfs.py")

if __name__ == "__main__":
    analyze_pricing_issues()