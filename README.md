# Smartsheet Weekly PDF Generator

Automated billing system that generates weekly Excel reports from Smartsheet data.

## 📊 Visual Documentation

**[View Interactive Diagrams & Architecture →](docs/index.md)**

See Mermaid-based flowcharts showing:
- System Architecture
- Data Flow Pipeline
- Filtering Logic
- Helper Row Detection
- Change Detection Flow
- GitHub Actions Workflow

## 🚀 Quick Start on Replit

This project is now configured to run on Replit! Here's how to get started:

### 1. Configure Your Environment

Create a `.env` file from the example:
```bash
cp .env.example .env
```

Then edit `.env` and add your Smartsheet API token:
```
SMARTSHEET_API_TOKEN=your_actual_api_token_here
```

### 2. Run the Generator

The main script generates weekly billing Excel files:
```bash
python generate_weekly_pdfs_complete_fixed.py
```

For local testing without uploading to Smartsheet:
```bash
SKIP_UPLOAD=true python generate_weekly_pdfs_complete_fixed.py
```

### 3. View Help & Available Scripts

Click the "Run" button or execute:
```bash
python run_info.py
```

## 📚 Available Scripts

### Main Scripts
- `generate_weekly_pdfs_complete_fixed.py` - **Primary production script** for generating weekly PDFs
- `generate_weekly_pdfs.py` - Alternative version of the generator

### Utility Scripts
- `audit_billing_changes.py` - Monitor Smartsheet for unauthorized billing changes
- `cleanup_excels.py` - Clean up old Excel files (typically for CI/CD)
- `analyze_excel_totals.py` - Diagnostic tool for analyzing Excel file totals
- `analyze_specific_excel.py` - Analyze specific Excel files
- `diagnose_pricing_issues.py` - Identify why work items are excluded due to pricing

### Testing
```bash
pytest tests/
```

## 🎯 What This Tool Does

1. **Connects to Smartsheet** - Pulls data from configured Smartsheet sheets
2. **Groups Data** - Organizes by work request number and week ending date
3. **Generates Excel Files** - Creates formatted billing reports with:
   - Company logo
   - Formatted headers and styling
   - Financial data and totals
   - Proper number formatting
4. **Uploads to Smartsheet** - Attaches generated reports (unless `SKIP_UPLOAD=true`)
5. **Audit Tracking** - Monitors for unauthorized billing changes

## ⚙️ Configuration

### Required Environment Variables
- `SMARTSHEET_API_TOKEN` - Your Smartsheet API token (required)

### Optional Environment Variables
- `TARGET_SHEET_ID` - Destination sheet for Excel attachments (default: 5723337641643908)
- `AUDIT_SHEET_ID` - Destination for audit rows/stats
- `SKIP_UPLOAD` - Skip Smartsheet uploads for local testing (default: false)
- `SKIP_CELL_HISTORY` - Skip cell history for performance (default: false)
- `RES_GROUPING_MODE` - Grouping mode: primary, helper, or both (default: both)
- `SENTRY_DSN` - Sentry.io DSN for error monitoring (optional)

## 📁 Output

Generated Excel files are saved to the `generated_docs/` directory.

## 🔐 Getting a Smartsheet API Token

1. Log into Smartsheet
2. Click your profile picture → Apps & Integrations
3. Click "API Access"
4. Click "Generate new access token"
5. Give it a name and copy the token
6. Add it to your `.env` file

## 🏗️ Azure DevOps Integration

This project includes complete Azure Pipeline configuration for automated GitHub to Azure DevOps synchronization:

- See `README_AZURE.md` for setup instructions
- See `AZURE_QUICKSTART.md` for quick 5-minute setup
- See `AZURE_PIPELINE_SETUP.md` for detailed configuration
- See `AZURE_ARCHITECTURE.md` for architecture details

## 🧪 Testing

Run the test suite:
```bash
pytest tests/
```

Run with coverage:
```bash
pytest tests/ --cov
```

## 📝 Features

✅ **WR 90093002 Excel generation fix** - Critical fix applied  
✅ **WR 89954686 specific handling** - Custom handling  
✅ **Concurrent processing** - ThreadPoolExecutor for performance  
✅ **Sentry integration** - Error monitoring and reporting  
✅ **Audit system** - Financial data validation  
✅ **Flexible grouping** - Multiple grouping modes supported  

## 🛠️ Development

This project uses:
- Python 3.11
- `smartsheet-python-sdk` for Smartsheet API
- `openpyxl` for Excel file generation
- `pandas` for data processing
- `pytest` for testing

## 📖 More Documentation

- `README_AZURE.md` - Azure DevOps pipeline documentation
- `AZURE_QUICKSTART.md` - Quick setup guide  
- `AZURE_PIPELINE_SETUP.md` - Complete setup guide
- `AZURE_ARCHITECTURE.md` - Architecture details

## 🆘 Support

For issues with:
- **Smartsheet connection**: Check your API token in `.env`
- **Excel generation**: Check logs in console output
- **Azure Pipeline**: See Azure documentation files

---

**Note**: This is a command-line tool. There is no web interface.
