#!/usr/bin/env python3
"""
Setup script for Enhanced Audit System V2
This script initializes the enhanced audit system with all required components.
"""

import os
import sys
import subprocess
import sqlite3
import json
import datetime
from typing import Dict, Any

def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True

def install_requirements():
    """Install required packages."""
    try:
        print("📦 Installing required packages...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements-enhanced-v2.txt"
        ])
        print("✅ Packages installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing packages: {e}")
        return False

def create_directories():
    """Create necessary directories."""
    directories = [
        'models',
        'backups',
        'reports',
        'logs',
        'static',
        'templates'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Created directory: {directory}")

def setup_database():
    """Initialize the enhanced audit database."""
    try:
        print("🗄️ Setting up enhanced audit database...")
        
        # Import and initialize the enhanced system to create tables
        from enhanced_audit_system_v2 import EnhancedAuditSystem
        import smartsheet
        from dotenv import load_dotenv
        
        load_dotenv()
        api_token = os.getenv("SMARTSHEET_API_TOKEN")
        audit_sheet_id = os.getenv("AUDIT_SHEET_ID")
        
        if not api_token or not audit_sheet_id:
            print("⚠️ Smartsheet credentials not found. Database tables will be created without connection.")
            # Create database manually
            conn = sqlite3.connect('enhanced_audit.db')
            cursor = conn.cursor()
            
            # Create tables (from the EnhancedAuditSystem._init_database method)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    sheet_id TEXT NOT NULL,
                    row_id TEXT NOT NULL,
                    work_request TEXT NOT NULL,
                    column_name TEXT NOT NULL,
                    violation_type TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    delta REAL,
                    changed_by TEXT NOT NULL,
                    changed_at TEXT NOT NULL,
                    week_ending TEXT,
                    is_historical BOOLEAN,
                    audit_run_id TEXT,
                    severity TEXT,
                    issue_description TEXT,
                    suggested_fix TEXT,
                    sheet_reference TEXT,
                    ip_address TEXT,
                    device_info TEXT,
                    session_id TEXT,
                    user_agent TEXT,
                    risk_score REAL,
                    anomaly_score REAL,
                    predicted_category TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_permissions (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    role TEXT NOT NULL,
                    permissions TEXT NOT NULL,
                    last_login TEXT,
                    access_level INTEGER,
                    department TEXT,
                    supervisor TEXT,
                    active BOOLEAN,
                    last_review_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backup_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backup_date TEXT NOT NULL,
                    backup_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    checksum TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS webhook_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    webhook_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    sheet_id TEXT NOT NULL,
                    row_id TEXT,
                    column_id TEXT,
                    user_id TEXT,
                    timestamp TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    processed BOOLEAN DEFAULT FALSE,
                    processed_at TEXT,
                    error_message TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
        else:
            # Initialize with actual connection
            client = smartsheet.Smartsheet(api_token)
            enhanced_audit = EnhancedAuditSystem(client, audit_sheet_id)
        
        print("✅ Database setup completed")
        return True
        
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        return False

def create_sample_users():
    """Create sample user permissions."""
    try:
        print("👥 Creating sample user permissions...")
        
        conn = sqlite3.connect('enhanced_audit.db')
        cursor = conn.cursor()
        
        sample_users = [
            {
                'user_id': 'admin001',
                'email': 'admin@company.com',
                'role': 'Administrator',
                'permissions': json.dumps(['read', 'write', 'delete', 'admin']),
                'access_level': 10,
                'department': 'IT',
                'supervisor': 'CTO',
                'active': True,
                'last_review_date': datetime.datetime.now().isoformat()
            },
            {
                'user_id': 'audit001',
                'email': 'auditor@company.com',
                'role': 'Auditor',
                'permissions': json.dumps(['read', 'audit', 'report']),
                'access_level': 7,
                'department': 'Finance',
                'supervisor': 'CFO',
                'active': True,
                'last_review_date': datetime.datetime.now().isoformat()
            },
            {
                'user_id': 'user001',
                'email': 'user@company.com',
                'role': 'User',
                'permissions': json.dumps(['read', 'write']),
                'access_level': 3,
                'department': 'Operations',
                'supervisor': 'Operations Manager',
                'active': True,
                'last_review_date': datetime.datetime.now().isoformat()
            }
        ]
        
        for user in sample_users:
            cursor.execute('''
                INSERT OR REPLACE INTO user_permissions 
                (user_id, email, role, permissions, access_level, department, supervisor, active, last_review_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user['user_id'],
                user['email'],
                user['role'],
                user['permissions'],
                user['access_level'],
                user['department'],
                user['supervisor'],
                user['active'],
                user['last_review_date']
            ))
        
        conn.commit()
        conn.close()
        
        print("✅ Sample users created")
        return True
        
    except Exception as e:
        print(f"❌ Error creating sample users: {e}")
        return False

def create_config_file():
    """Create configuration file."""
    try:
        print("⚙️ Creating configuration file...")
        
        config = {
            "system": {
                "name": "Enhanced Audit System V2",
                "version": "2.0.0",
                "environment": "production"
            },
            "webhook": {
                "url": "https://your-domain.com/webhook",
                "secret": "audit_webhook_secret_2025",
                "port": 5000
            },
            "dashboard": {
                "port": 8050,
                "host": "0.0.0.0",
                "debug": False
            },
            "ml": {
                "anomaly_threshold": 0.1,
                "risk_score_threshold": 0.7,
                "retrain_interval_days": 7
            },
            "backup": {
                "schedule": "02:00",
                "retention_days": 30,
                "compression": True
            },
            "alerts": {
                "email": {
                    "enabled": False,
                    "smtp_server": "smtp.gmail.com",
                    "smtp_port": 587,
                    "username": "",
                    "password": "",
                    "recipients": []
                },
                "slack": {
                    "enabled": False,
                    "webhook_url": ""
                }
            },
            "security": {
                "session_timeout": 3600,
                "max_login_attempts": 5,
                "password_complexity": True
            }
        }
        
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)
        
        print("✅ Configuration file created: config.json")
        return True
        
    except Exception as e:
        print(f"❌ Error creating config file: {e}")
        return False

def create_environment_template():
    """Create .env template file."""
    try:
        print("🔐 Creating environment template...")
        
        env_template = """# Enhanced Audit System V2 Environment Variables
# Copy this file to .env and fill in your actual values

# Smartsheet Configuration
SMARTSHEET_API_TOKEN=your_smartsheet_api_token_here
AUDIT_SHEET_ID=your_audit_sheet_id_here

# Database Configuration
DATABASE_URL=sqlite:///enhanced_audit.db

# Flask Configuration
FLASK_SECRET_KEY=your_flask_secret_key_here
FLASK_ENV=production

# Email Configuration (Optional)
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password_here
EMAIL_ALERT_RECIPIENTS=admin@company.com,security@company.com

# Webhook Configuration
WEBHOOK_SECRET=audit_webhook_secret_2025
WEBHOOK_URL=https://your-domain.com/webhook

# ML Model Configuration
MODEL_RETRAIN_INTERVAL=7
ANOMALY_THRESHOLD=0.1
RISK_THRESHOLD=0.7

# Security Configuration
SESSION_TIMEOUT=3600
MAX_LOGIN_ATTEMPTS=5
"""
        
        with open('.env.template', 'w') as f:
            f.write(env_template)
        
        print("✅ Environment template created: .env.template")
        print("📝 Please copy .env.template to .env and fill in your actual values")
        return True
        
    except Exception as e:
        print(f"❌ Error creating environment template: {e}")
        return False

def create_startup_script():
    """Create startup script."""
    try:
        print("🚀 Creating startup script...")
        
        startup_script = """#!/bin/bash
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
"""
        
        with open('start_enhanced_audit.sh', 'w') as f:
            f.write(startup_script)
        
        # Make script executable
        os.chmod('start_enhanced_audit.sh', 0o755)
        
        print("✅ Startup script created: start_enhanced_audit.sh")
        return True
        
    except Exception as e:
        print(f"❌ Error creating startup script: {e}")
        return False

def main():
    """Main setup function."""
    print("🔧 ENHANCED AUDIT SYSTEM V2 SETUP")
    print("=" * 50)
    
    success = True
    
    # Check Python version
    if not check_python_version():
        return False
    
    # Install requirements
    if not install_requirements():
        success = False
    
    # Create directories
    create_directories()
    
    # Setup database
    if not setup_database():
        success = False
    
    # Create sample users
    if not create_sample_users():
        success = False
    
    # Create config file
    if not create_config_file():
        success = False
    
    # Create environment template
    if not create_environment_template():
        success = False
    
    # Create startup script
    if not create_startup_script():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 SETUP COMPLETED SUCCESSFULLY!")
        print("\n📋 Next Steps:")
        print("1. Copy .env.template to .env and fill in your credentials")
        print("2. Update config.json with your specific settings")
        print("3. Run: python enhanced_audit_system_v2.py")
        print("4. Or use: ./start_enhanced_audit.sh")
        print("\n🌐 Access Points:")
        print("• Dashboard: http://localhost:8050/dashboard/")
        print("• Webhook: http://localhost:5000/webhook")
        print("• Health Check: http://localhost:5000/health")
    else:
        print("❌ SETUP COMPLETED WITH SOME ERRORS")
        print("Please check the error messages above and resolve them.")
    
    return success

if __name__ == "__main__":
    main()
