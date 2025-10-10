# Quick Start: Azure Pipeline Sync Setup

This guide helps you quickly set up the Azure Pipeline to sync your GitHub master branch to Azure DevOps.

## ⚡ Quick Setup (5 Minutes)

### 1. Prerequisites Checklist
- [ ] Azure DevOps account and organization
- [ ] Azure DevOps project created
- [ ] Git repository created in Azure DevOps project
- [ ] Note your Azure DevOps repository URL

### 2. Get Your Repository URL
Your Azure DevOps repository URL should look like:
```
https://dev.azure.com/{organization}/{project}/_git/{repository}
```

**Example:**
```
https://dev.azure.com/mycompany/MyProject/_git/Generate-Weekly-PDFs-DSR-Resiliency
```

### 3. Create Pipeline in Azure DevOps

1. **Navigate to Pipelines**
   - Open your Azure DevOps project
   - Click **Pipelines** → **Create Pipeline**

2. **Connect GitHub**
   - Select **GitHub** as source
   - Authenticate if needed
   - Choose: `JFlo21/Generate-Weekly-PDFs-DSR-Resiliency`

3. **Use Existing YAML**
   - Azure DevOps will detect `azure-pipelines.yml`
   - Click **Continue**

### 4. Add Repository URL Variable

1. **Before first run:**
   - Click **Variables** button (top right)
   - Click **New variable**
   - Set:
     - Name: `AzureDevOpsRepoUrl`
     - Value: `https://dev.azure.com/{org}/{project}/_git/{repo}`
   - Click **OK** → **Save**

### 5. Configure Permissions

1. **Enable OAuth Token:**
   - Click **Edit** → **⋯** (More) → **Triggers**
   - Find: "Allow scripts to access the OAuth token"
   - ✅ Check this box
   - Click **Save**

2. **Grant Build Service Access:**
   - Go to **Project Settings** (bottom left)
   - Click **Repositories** → Select your repo
   - Click **Security** tab
   - Find: `{Project} Build Service ({Organization})`
   - Set permissions to **Allow**:
     - ✅ Contribute
     - ✅ Force Push
     - ✅ Create Branch

### 6. Test the Pipeline

1. Click **Run pipeline**
2. Wait for completion
3. Check logs for: `✅ Successfully synced to Azure DevOps!`

## ✅ Verification

After setup, the pipeline will:
- ✅ Auto-run when you push to master branch in GitHub
- ✅ Sync all changes to Azure DevOps repository
- ✅ Show detailed logs of sync operation
- ✅ Verify commits match between repos

## 🔍 What Gets Synced?

- ✅ All commits to master branch
- ✅ Complete git history
- ✅ Commit messages and authors
- ✅ File changes
- ❌ README.md changes (excluded)
- ❌ .github/ directory changes (excluded)

## 🚨 Common Issues

### Issue: "Azure DevOps repository URL is not configured"
**Fix:** Add the `AzureDevOpsRepoUrl` variable (see Step 4)

### Issue: "Permission denied" or "Authentication failed"
**Fix:** 
1. Enable OAuth token access (Step 5.1)
2. Grant Build Service permissions (Step 5.2)

### Issue: Pipeline doesn't trigger
**Fix:** Ensure you're pushing to the `master` branch (not other branches)

## 📖 Full Documentation

For detailed information, see: [AZURE_PIPELINE_SETUP.md](./AZURE_PIPELINE_SETUP.md)

## 🎯 Next Steps

Once setup is complete:
1. ✅ Push a test commit to master branch
2. ✅ Watch the pipeline run in Azure DevOps
3. ✅ Verify changes appear in Azure DevOps repository
4. ✅ Check pipeline logs for success message

---

**Setup Time:** ~5 minutes  
**Automation:** Fully automated after initial setup  
**Maintenance:** Zero - runs automatically on master branch changes
