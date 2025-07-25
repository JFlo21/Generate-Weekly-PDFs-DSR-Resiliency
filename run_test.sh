#!/bin/bash

# Test runner script for the Generate Weekly PDFs application
# This script activates the virtual environment and runs the main script in test mode

echo "🧪 Starting Real Test with Your Smartsheet Data"
echo "=============================================="

# Activate virtual environment
source venv/bin/activate

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create a .env file with your SMARTSHEET_API_TOKEN"
    exit 1
fi

# Run the main script in test mode
echo "📡 Connecting to your Smartsheet account..."
echo "🔍 This will show what would happen without making any changes"
echo ""

python3 generate_weekly_pdfs.py

echo ""
echo "✅ Test completed!"
echo "💡 To run in production mode, change TEST_MODE = False in generate_weekly_pdfs.py"
