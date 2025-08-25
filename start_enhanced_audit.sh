#!/bin/bash
# Enhanced Audit System V2 Startup Script

echo "🚀 Starting Enhanced Audit System V2..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/upgrade requirements
echo "📦 Installing requirements..."
pip install -r requirements-enhanced-v2.txt

# Start the enhanced audit system
echo "🎯 Starting Enhanced Audit System..."
python enhanced_audit_system_v2.py

echo "✅ Enhanced Audit System V2 started successfully!"
echo "📊 Dashboard: http://localhost:8050/dashboard/"
echo "🔗 Webhook: http://localhost:5000/webhook"
