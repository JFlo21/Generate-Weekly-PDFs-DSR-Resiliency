# Automated Weekly Excel Generation Setup

## Overview
This repository is configured to automatically generate Excel reports every Sunday between 5:00 PM - 10:00 PM Central Time using GitHub Actions.

## Setup Instructions

### 1. Add Smartsheet API Token Secret
1. Go to your GitHub repository settings
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `SMARTSHEET_API_TOKEN`
5. Value: Your Smartsheet API token (from your .env file)
6. Click **Add secret**

### 2. Workflow Schedule
The workflow runs at these times every Sunday (Central Time):
- **5:00 PM** (22:00 UTC Sunday)
- **7:00 PM** (00:00 UTC Monday)  
- **9:00 PM** (02:00 UTC Monday)

Only one execution per week will actually run - the others will be skipped if already completed.

### 3. Manual Testing
You can manually trigger the workflow:
1. Go to **Actions** tab in GitHub
2. Select **Weekly Excel Report Generation**
3. Click **Run workflow**
4. Choose test mode (true/false)
5. Click **Run workflow**

## How It Works

### Automatic Execution
- Runs only on Sundays between 5-10 PM Central Time
- Automatically sets `TEST_MODE = False` for production
- Generates Excel files and uploads them to Smartsheet
- Stores generated files as GitHub artifacts for 30 days

### Time Zone Handling
- All scheduling is in Central Time (America/Chicago)
- Accounts for both CDT (UTC-5) and CST (UTC-6)
- Multiple cron schedules ensure execution during daylight saving transitions

### Safety Features
- ✅ Time window validation (only runs Sunday 5-10 PM Central)
- ✅ API token verification
- ✅ Duplicate run prevention within same week
- ✅ Manual override capability for testing
- ✅ Artifact backup of all generated files

## File Structure
```
.github/
  workflows/
    weekly-excel-generation.yml    # Main workflow file
generate_weekly_pdfs.py           # Excel generation script
requirements.txt                  # Python dependencies
.env                             # Local API token (not in GitHub)
```

## Monitoring
- Check the **Actions** tab for workflow execution history
- View logs to see which files were generated
- Download artifacts to see the generated Excel files
- Failure notifications will be sent to repository administrators

## Next Scheduled Run
Starting **Sunday, July 27, 2025** at 5:00 PM Central Time, then every Sunday thereafter.

## Troubleshooting

### Workflow Not Running
1. Verify the `SMARTSHEET_API_TOKEN` secret is set correctly
2. Check that the repository has Actions enabled
3. Ensure the workflow file is in the correct location

### API Errors
1. Verify your Smartsheet API token is still valid
2. Check that the target sheet ID hasn't changed
3. Ensure the source sheets still exist and have correct columns

### Time Zone Issues
The workflow automatically handles daylight saving time transitions between CDT and CST.
