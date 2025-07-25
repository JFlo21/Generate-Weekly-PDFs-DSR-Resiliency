# ⚠️ IMPORTANT: Workflow File Cleanup Required

## Current Status
You have **2 workflow files** that will conflict:

### 🔴 **OLD FILE (MUST BE DELETED):**
- **File:** `.github/workflows/pdf_generator.yml`
- **Schedule:** Runs every 2 hours (conflicts with your Sunday-only requirement)
- **Status:** ❌ WILL INTERFERE with new workflow

### 🟢 **NEW FILE (KEEP THIS ONE):**
- **File:** `.github/workflows/weekly-excel-generation.yml`  
- **Schedule:** Runs Sunday 5-10 PM Central only
- **Status:** ✅ **READY FOR PRODUCTION**

## Required Action
**You must manually delete the old workflow file:**

1. **In Finder:**
   - Navigate to your project folder
   - Go to `.github/workflows/`
   - **Delete** `pdf_generator.yml`
   - **Keep** `weekly-excel-generation.yml`

2. **Or in Terminal:**
   ```bash
   # Try this command to remove the old file
   sudo rm .github/workflows/pdf_generator.yml
   ```

## Production Mode Settings ✅

Your new workflow is now configured for **PRODUCTION MODE**:

- **Scheduled Runs:** Automatically runs in production mode (uploads to Smartsheet)
- **Manual Runs:** Defaults to production mode, but you can choose test mode
- **Test Mode Option:** Available for manual testing without uploading to Smartsheet

## Next Steps

1. **Delete the old workflow file** (pdf_generator.yml)
2. **Add your API token** as a GitHub secret named `SMARTSHEET_API_TOKEN`
3. **Push changes** to GitHub
4. **First run:** This Sunday, July 27, 2025 at 5:00 PM Central

## Verification
After deleting the old file, you should only see:
```
.github/workflows/weekly-excel-generation.yml
```

The workflow will then run **every Sunday from 5-10 PM Central** in production mode, generating and uploading Excel files to Smartsheet automatically.
