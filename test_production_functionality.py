#!/usr/bin/env python3
"""
Test the actual production script in test mode to verify functionality
"""
import os
import subprocess
import sys

def run_production_test():
    """Run the production script in test mode"""
    
    print("🔧 Testing the production Excel generation script...")
    print("=" * 60)
    
    # Check if environment is properly set up
    if not os.path.exists('.env'):
        print("❌ No .env file found. Please ensure your environment is configured.")
        return False
    
    # Run the actual script in test mode
    try:
        # Set environment variable to avoid AI components that might not be installed
        env = os.environ.copy()
        env['ULTRA_LIGHT_MODE'] = 'true'
        env['SKIP_CELL_HISTORY'] = 'true'
        
        print("📋 Running: python generate_weekly_pdfs.py --test")
        print("   Environment: Ultra-light mode (no AI components)")
        print("   Skipping: Cell history for performance")
        print("")
        
        result = subprocess.run([
            sys.executable, 'generate_weekly_pdfs.py', '--test'
        ], 
        env=env,
        capture_output=True, 
        text=True, 
        timeout=300  # 5 minute timeout
        )
        
        print("📤 Script Output:")
        print("-" * 40)
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print("⚠️ Warnings/Errors:")
            print(result.stderr)
        
        print("-" * 40)
        print(f"📊 Exit Code: {result.returncode}")
        
        if result.returncode == 0:
            print("✅ Script completed successfully!")
            
            # Check if any Excel files were generated
            if os.path.exists('generated_docs'):
                excel_files = [f for f in os.listdir('generated_docs') if f.endswith('.xlsx')]
                print(f"📁 Found {len(excel_files)} Excel files in generated_docs/")
                
                # Show recent files
                recent_files = sorted(excel_files)[-5:]  # Last 5 files
                print("📄 Recent files:")
                for file in recent_files:
                    file_path = os.path.join('generated_docs', file)
                    file_size = os.path.getsize(file_path)
                    print(f"   • {file} ({file_size:,} bytes)")
            
            return True
        else:
            print(f"❌ Script failed with exit code {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ Script timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"❌ Error running script: {e}")
        return False

def check_recent_files():
    """Check if recent Excel files have reasonable content"""
    
    print("\n🔍 Checking recent Excel files for validation...")
    print("=" * 60)
    
    if not os.path.exists('generated_docs'):
        print("❌ No generated_docs directory found")
        return
    
    excel_files = [f for f in os.listdir('generated_docs') if f.endswith('.xlsx') and not f.startswith('AUDIT_')]
    if not excel_files:
        print("❌ No Excel files found")
        return
    
    # Check a few recent files
    recent_files = sorted(excel_files)[-3:]  # Last 3 files
    
    for file in recent_files:
        file_path = os.path.join('generated_docs', file)
        file_size = os.path.getsize(file_path)
        
        print(f"\n📄 File: {file}")
        print(f"   Size: {file_size:,} bytes")
        
        if file_size < 5000:
            print("   ⚠️ Warning: File seems very small")
        elif file_size > 50000:
            print("   ✅ Good: File has substantial content")
        else:
            print("   ✅ OK: File appears normal")
        
        # Try to detect date format issues from filename
        if '_3_' in file or 'WeekEnding_3_' in file:
            print("   ❌ ERROR: Filename shows incorrect date formatting!")
        elif 'WeekEnding_' in file and len(file.split('_')) >= 3:
            date_part = file.split('_')[1]
            if len(date_part) == 6 and date_part.isdigit():
                print("   ✅ Good: Date format appears correct (MMDDYY)")
            else:
                print(f"   ⚠️ Warning: Unusual date format: '{date_part}'")

if __name__ == "__main__":
    # First check existing files
    check_recent_files()
    
    # Then run a test
    print("\n" + "=" * 60)
    success = run_production_test()
    
    if success:
        print("\n🎉 Production test completed successfully!")
        print("🔧 The Excel generation functionality appears to be working correctly.")
        print("📧 If you're still seeing $0 values in production, please share:")
        print("   • A specific filename that shows $0 values")
        print("   • The expected vs actual week ending date")
        print("   • Any error messages from the production runs")
    else:
        print("\n❌ Production test failed!")
        print("🔧 There may be configuration or dependency issues.")
