"""
Setup script for the Billing Report Audit Log sheet.

This script helps create the required audit sheet structure in Smartsheet.
Run this once to set up the audit functionality.
"""

import os
import smartsheet
from dotenv import load_dotenv

load_dotenv()

def create_audit_sheet():
    """Create the Billing Report Audit Log sheet with the correct column structure."""
    
    API_TOKEN = os.getenv("SMARTSHEET_API_TOKEN")
    if not API_TOKEN:
        print("❌ Error: SMARTSHEET_API_TOKEN not found in environment variables")
        return None
    
    client = smartsheet.Smartsheet(API_TOKEN)
    client.errors_as_exceptions(True)
    
    # Define the audit sheet structure
    columns = [
        {'title': 'Work Request #', 'type': 'TEXT_NUMBER', 'primary': True},
        {'title': 'Week Ending', 'type': 'DATE'},
        {'title': 'Column', 'type': 'TEXT_NUMBER'},
        {'title': 'Old Value', 'type': 'TEXT_NUMBER'},
        {'title': 'New Value', 'type': 'TEXT_NUMBER'},
        {'title': 'Delta', 'type': 'TEXT_NUMBER'},
        {'title': 'Changed By', 'type': 'CONTACT_LIST'},
        {'title': 'Changed At', 'type': 'DATETIME'},
        {'title': 'Source Sheet ID', 'type': 'TEXT_NUMBER'},
        {'title': 'Source Row ID', 'type': 'TEXT_NUMBER'},
        {'title': 'Run At', 'type': 'DATETIME'},
        {'title': 'Run ID', 'type': 'TEXT_NUMBER'},
        {'title': 'Note', 'type': 'TEXT_NUMBER'}
    ]
    
    # Create sheet
    try:
        from smartsheet.models import Sheet, Column
        
        sheet = Sheet({
            'name': 'Billing Report Audit Log',
            'columns': [Column(col) for col in columns]
        })
        
        response = client.Sheets.create_sheet(sheet)
        sheet_id = response.result.id
        
        print(f"✅ Successfully created audit sheet!")
        print(f"📋 Sheet Name: Billing Report Audit Log")
        print(f"🆔 Sheet ID: {sheet_id}")
        print(f"\n📝 Next steps:")
        print(f"1. Add this to your .env file:")
        print(f"   AUDIT_SHEET_ID={sheet_id}")
        print(f"2. The audit system will now track changes to Quantity and Redlined Total Price")
        print(f"3. Run your main script to start auditing changes")
        
        return sheet_id
        
    except Exception as e:
        print(f"❌ Error creating audit sheet: {e}")
        return None

def show_manual_setup_instructions():
    """Show instructions for manually creating the audit sheet."""
    
    print("\n" + "="*80)
    print("📋 MANUAL AUDIT SHEET SETUP INSTRUCTIONS")
    print("="*80)
    print("\nIf the automatic creation didn't work, create the sheet manually:")
    print("\n1. Create a new sheet in Smartsheet named: 'Billing Report Audit Log'")
    print("\n2. Create these columns (in this order):")
    
    columns = [
        "Work Request # (Text/Number) - Primary Column",
        "Week Ending (Date)",
        "Column (Text/Number)",
        "Old Value (Text/Number)",
        "New Value (Text/Number)",
        "Delta (Text/Number)",
        "Changed By (Contact List)",
        "Changed At (Date/Time)",
        "Source Sheet ID (Text/Number)",
        "Source Row ID (Text/Number)",
        "Run At (Date/Time)",
        "Run ID (Text/Number)",
        "Note (Text/Number)"
    ]
    
    for i, col in enumerate(columns, 1):
        print(f"   {i:2d}. {col}")
    
    print(f"\n3. Copy the Sheet ID from the URL")
    print(f"4. Add to your .env file: AUDIT_SHEET_ID=your_sheet_id_here")
    print("="*80)

if __name__ == "__main__":
    print("🔧 Billing Report Audit Log Setup")
    print("="*40)
    
    try:
        sheet_id = create_audit_sheet()
        if not sheet_id:
            show_manual_setup_instructions()
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        show_manual_setup_instructions()
