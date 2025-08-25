# Enhanced Audit System V2 - Enterprise Grade Billing Audit Platform

## 🚀 Overview

The Enhanced Audit System V2 is a comprehensive, enterprise-grade billing audit platform that implements all the robust auditing features you requested. This system provides real-time monitoring, predictive analytics, automated backups, and comprehensive security measures.

## ✨ New Features Implemented

### 1. **Real-time Webhooks** 🔗
- **Smartsheet webhook integration** for instant change notifications
- **Real-time processing** of billing changes as they happen
- **Immediate risk assessment** and anomaly detection
- **Automatic alerts** for high-risk changes

### 2. **Enhanced User Training & Access Control** 👥
- **User permission management** with role-based access control
- **Monthly automated permission reviews** with recommendations
- **Access level tracking** and supervisor assignment
- **Login tracking** and session management
- **Inactive user detection** and access recommendations

### 3. **Backup & Recovery System** 💾
- **Automated daily backups** of critical billing data
- **Database and Smartsheet data backup**
- **Checksum verification** for backup integrity
- **Backup logging** and status tracking
- **Configurable retention policies**

### 4. **Audit Trail Enhancement** 🔍
- **Extended logging** with IP addresses and device information
- **Session tracking** and user agent logging
- **Enhanced audit events** with comprehensive metadata
- **Database-backed audit trail** for long-term storage
- **Webhook event logging** for real-time change tracking

### 5. **Predictive Analytics & ML** 🧠
- **Machine Learning models** for anomaly detection
- **Risk score calculation** based on multiple factors
- **Predictive change categorization**
- **Automated model retraining** with new data
- **Historical pattern analysis**

### 6. **Dashboard Integration** 📊
- **Real-time monitoring dashboard** with live updates
- **Interactive charts** for risk scores and anomalies
- **User activity monitoring** and visualization
- **High-risk event alerts** and notifications
- **Management oversight** with comprehensive metrics

### 7. **Advanced Security Features** 🔒
- **Webhook signature verification** for secure communications
- **Email alert system** for immediate notifications
- **Session management** and timeout controls
- **Multi-factor authentication support**
- **Comprehensive logging** for security audit trails

## 🏗️ Architecture

```
Enhanced Audit System V2
├── Core Audit Engine
│   ├── BillingAudit Integration
│   ├── Real-time Processing
│   └── ML-powered Analysis
├── Web Services
│   ├── Flask Webhook Server (Port 5000)
│   ├── Dash Dashboard (Port 8050)
│   └── Health Check Endpoints
├── Data Layer
│   ├── SQLite Database
│   ├── Smartsheet Integration
│   └── File-based Backups
├── ML Pipeline
│   ├── Anomaly Detection
│   ├── Risk Assessment
│   └── Predictive Analytics
└── Background Services
    ├── Scheduled Tasks
    ├── Backup Automation
    └── Model Training
```

## 📦 Installation & Setup

### Prerequisites
- Python 3.8 or higher
- Smartsheet API access
- Valid Smartsheet API token
- Audit sheet configured in Smartsheet

### Quick Setup
```bash
# 1. Run the setup script
python setup_enhanced_audit_v2.py

# 2. Configure environment variables
cp .env.template .env
# Edit .env with your credentials

# 3. Start the system
./start_enhanced_audit.sh
# Or manually: python enhanced_audit_system_v2.py
```

### Manual Setup
```bash
# Install requirements
pip install -r requirements-enhanced-v2.txt

# Initialize database and create directories
python setup_enhanced_audit_v2.py

# Configure your environment
# Edit .env and config.json files

# Start the enhanced audit system
python enhanced_audit_system_v2.py
```

## 🔧 Configuration

### Environment Variables (.env)
```bash
SMARTSHEET_API_TOKEN=your_token_here
AUDIT_SHEET_ID=your_sheet_id_here
WEBHOOK_SECRET=your_webhook_secret
EMAIL_USERNAME=alerts@company.com
EMAIL_PASSWORD=your_app_password
```

### System Configuration (config.json)
```json
{
  "webhook": {
    "url": "https://your-domain.com/webhook",
    "port": 5000
  },
  "ml": {
    "anomaly_threshold": 0.1,
    "risk_score_threshold": 0.7
  },
  "alerts": {
    "email": {
      "enabled": true,
      "recipients": ["admin@company.com"]
    }
  }
}
```

## 🎯 Key Components

### 1. Enhanced Audit Events
```python
@dataclass
class AuditEvent:
    # Original audit fields
    timestamp: str
    sheet_id: str
    work_request: str
    violation_type: str
    # Enhanced tracking
    ip_address: Optional[str]
    device_info: Optional[str]
    risk_score: Optional[float]
    anomaly_score: Optional[float]
```

### 2. Real-time Webhook Processing
- Instant notification when changes occur
- Signature verification for security
- Immediate risk assessment
- Automatic anomaly detection
- Alert generation for high-risk changes

### 3. Machine Learning Pipeline
- **Isolation Forest** for anomaly detection
- **Risk scoring** based on multiple factors
- **Automated retraining** with new data
- **Feature extraction** from audit events

### 4. User Permission Management
```python
@dataclass
class UserPermission:
    user_id: str
    email: str
    role: str
    access_level: int
    last_review_date: str
```

## 📊 Dashboard Features

### Real-time Monitoring
- **Live risk score distribution**
- **Anomaly detection timeline**
- **User activity tracking**
- **Recent high-risk events**

### Access URLs
- **Dashboard**: http://localhost:8050/dashboard/
- **Webhook**: http://localhost:5000/webhook
- **Health Check**: http://localhost:5000/health

## 🔄 Automated Processes

### Daily Tasks
- **Automated backups** at 2:00 AM
- **Database maintenance**
- **Log rotation**

### Weekly Tasks
- **ML model retraining**
- **Performance analytics**
- **System health reports**

### Monthly Tasks
- **User permission review**
- **Access level audit**
- **Comprehensive reporting**

## 🚨 Alert System

### Immediate Alerts (Real-time)
- High risk score changes (>0.7)
- Anomaly detection triggers (>0.1)
- Unauthorized historical data changes
- After-hours modifications

### Alert Channels
- **Email notifications**
- **Dashboard alerts**
- **Log file entries**
- **Database audit trail**

## 📈 Risk Scoring Factors

### Time-based Risk
- Changes outside business hours (+0.3)
- Weekend modifications (+0.2)
- Holiday period changes (+0.25)

### User-based Risk
- Low access level users (+0.2)
- Overdue permission reviews (+0.25)
- Inactive user accounts (+0.4)

### Data-based Risk
- Historical data modifications (+0.4)
- Large value changes (+0.3)
- Multiple rapid changes (+0.35)

## 🔍 Audit Trail Enhancement

### Extended Logging Fields
- **IP Address tracking**
- **Device information**
- **Session identifiers**
- **User agent strings**
- **Geographic location** (if enabled)

### Audit Database Schema
```sql
CREATE TABLE audit_events (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    work_request TEXT NOT NULL,
    violation_type TEXT NOT NULL,
    -- Enhanced fields
    ip_address TEXT,
    device_info TEXT,
    risk_score REAL,
    anomaly_score REAL,
    -- ... other fields
);
```

## 💾 Backup & Recovery

### Automated Backups
- **Daily database backups** with compression
- **Smartsheet data export** to Excel
- **Configuration file backups**
- **ML model checkpoints**

### Backup Verification
- **SHA256 checksums** for integrity
- **File size validation**
- **Restore testing** (optional)

### Retention Policy
- **30-day retention** by default
- **Configurable retention periods**
- **Automatic cleanup** of old backups

## 🤖 Machine Learning Features

### Anomaly Detection
- **Isolation Forest algorithm**
- **Real-time scoring**
- **Adaptive thresholds**
- **Feature engineering**

### Predictive Analytics
- **Change pattern recognition**
- **Risk prediction**
- **User behavior analysis**
- **Seasonal adjustment**

### Model Management
- **Automated retraining**
- **Model versioning**
- **Performance monitoring**
- **A/B testing support**

## 🔐 Security Features

### Authentication & Authorization
- **Role-based access control**
- **Session management**
- **Multi-factor authentication** (ready)
- **Permission auditing**

### Data Protection
- **Webhook signature verification**
- **Database encryption** (configurable)
- **Secure communication** (HTTPS ready)
- **Audit trail integrity**

### Monitoring & Alerts
- **Failed login tracking**
- **Unauthorized access attempts**
- **Privilege escalation detection**
- **Data exfiltration monitoring**

## 📋 API Endpoints

### Webhook Endpoints
- `POST /webhook` - Smartsheet webhook handler
- `GET /health` - System health check
- `GET /status` - System status information

### Dashboard APIs
- Real-time data updates
- Interactive chart data
- User activity metrics
- Alert management

## 🛠️ Maintenance & Monitoring

### System Health Monitoring
- **Resource usage tracking**
- **Performance metrics**
- **Error rate monitoring**
- **Service availability**

### Log Management
- **Structured logging**
- **Log rotation**
- **Error aggregation**
- **Performance profiling**

### Database Maintenance
- **Index optimization**
- **Query performance**
- **Storage management**
- **Backup verification**

## 🔄 Integration with Existing System

The Enhanced Audit System V2 seamlessly integrates with your existing billing audit system:

1. **Maintains compatibility** with existing `audit_billing_changes.py`
2. **Extends functionality** without breaking changes
3. **Preserves existing Excel generation** and Smartsheet integration
4. **Adds enhanced features** as optional components

## 📞 Support & Troubleshooting

### Common Issues
1. **Webhook not receiving events**: Check firewall and URL configuration
2. **ML models not training**: Ensure sufficient historical data
3. **Dashboard not loading**: Verify port 8050 is available
4. **Email alerts not sending**: Check SMTP configuration

### Debug Mode
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Test webhook connectivity
curl -X POST http://localhost:5000/health

# Check dashboard status
curl http://localhost:8050/dashboard/
```

## 🚀 Getting Started

1. **Run setup**: `python setup_enhanced_audit_v2.py`
2. **Configure environment**: Edit `.env` file
3. **Start system**: `./start_enhanced_audit.sh`
4. **Access dashboard**: http://localhost:8050/dashboard/
5. **Setup webhook**: Configure in Smartsheet
6. **Monitor alerts**: Check email and dashboard

The Enhanced Audit System V2 provides enterprise-grade auditing capabilities with real-time monitoring, predictive analytics, and comprehensive security - everything you need for robust billing audit management!
