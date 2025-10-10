# Azure Pipeline - GitHub to Azure DevOps Sync

## 📚 Documentation Index

This repository includes a complete Azure Pipeline setup for automatically syncing the GitHub master branch to your Azure DevOps repository.

### Quick Links

1. **[Quick Start Guide](./AZURE_QUICKSTART.md)** ⚡
   - 5-minute setup guide
   - Step-by-step checklist
   - Common issues and fixes

2. **[Complete Setup Guide](./AZURE_PIPELINE_SETUP.md)** 📖
   - Detailed configuration instructions
   - Security considerations
   - Troubleshooting guide
   - Advanced options

3. **[Architecture & Flow](./AZURE_ARCHITECTURE.md)** 🏗️
   - Visual diagrams
   - Data flow charts
   - Authentication flow
   - Sync process details

4. **[Pipeline Configuration](./azure-pipelines.yml)** ⚙️
   - The actual YAML configuration
   - Ready to use in Azure DevOps

## 🎯 What This Pipeline Does

✅ **Automatic Sync**: Every push to the GitHub `master` branch automatically syncs to Azure DevOps  
✅ **Full History**: Syncs complete git history with all commits  
✅ **Preserves Data**: Maintains commit messages, authors, and timestamps  
✅ **Verification**: Automatically verifies successful sync  
✅ **Detailed Logs**: Comprehensive logging for monitoring and debugging  

## 🚀 Getting Started

### For Quick Setup (5 minutes)
Start with: **[AZURE_QUICKSTART.md](./AZURE_QUICKSTART.md)**

### For Detailed Setup
Read: **[AZURE_PIPELINE_SETUP.md](./AZURE_PIPELINE_SETUP.md)**

### To Understand the Architecture
See: **[AZURE_ARCHITECTURE.md](./AZURE_ARCHITECTURE.md)**

## 📋 Prerequisites

- [x] Azure DevOps account and organization
- [x] Azure DevOps project with Git repository
- [x] Azure DevOps repository URL
- [x] GitHub repository access (already configured)

## ⚙️ Files Included

| File | Purpose |
|------|---------|
| `azure-pipelines.yml` | Main pipeline configuration (use this in Azure DevOps) |
| `AZURE_QUICKSTART.md` | Quick 5-minute setup guide |
| `AZURE_PIPELINE_SETUP.md` | Complete setup and configuration guide |
| `AZURE_ARCHITECTURE.md` | Architecture diagrams and flow charts |
| `README_AZURE.md` | This file - documentation index |

## 🔄 How It Works

```
GitHub (master branch)
        ↓ (push)
Azure Pipeline (triggers)
        ↓ (sync)
Azure DevOps (master branch)
```

1. Developer pushes to GitHub master branch
2. Azure Pipeline automatically triggers
3. Pipeline clones GitHub repository
4. Pipeline pushes to Azure DevOps using OAuth authentication
5. Pipeline verifies sync was successful
6. Azure DevOps master branch is now in sync with GitHub

## 🔐 Security Features

- ✅ Uses Azure DevOps System.AccessToken (OAuth)
- ✅ No manual token management required
- ✅ Scoped permissions (Build Service)
- ✅ Secure variable configuration
- ✅ Force push protected by permissions

## 🎛️ Configuration Required

You need to configure **one variable** in Azure DevOps:

| Variable | Value | Example |
|----------|-------|---------|
| `AzureDevOpsRepoUrl` | Your Azure DevOps repo URL | `https://dev.azure.com/myorg/myproject/_git/myrepo` |

See [AZURE_QUICKSTART.md](./AZURE_QUICKSTART.md) for setup instructions.

## 📊 What Gets Synced

✅ **Synced:**
- All commits to master branch
- Complete git history
- Commit messages and authors
- File changes

❌ **Not Synced:**
- Other branches (only master)
- README.md changes (excluded)
- .github/ directory changes (excluded)

## 🔧 Customization

The pipeline can be customized for:
- Different branch mappings
- Multiple branch sync
- Mirror sync (all branches)
- Custom exclusion paths
- Different authentication methods

See [AZURE_PIPELINE_SETUP.md](./AZURE_PIPELINE_SETUP.md) for customization options.

## 🆘 Support & Troubleshooting

### Common Issues

**Problem:** Pipeline doesn't trigger  
**Solution:** Ensure trigger is on `master` branch and pipeline is enabled

**Problem:** Authentication fails  
**Solution:** Enable "Allow scripts to access OAuth token" in pipeline settings

**Problem:** Permission denied  
**Solution:** Grant Build Service "Contribute" and "Force Push" permissions

See [AZURE_PIPELINE_SETUP.md](./AZURE_PIPELINE_SETUP.md#troubleshooting) for more help.

## 📈 Monitoring

The pipeline provides:
- ✅ Detailed step-by-step logs
- ✅ Commit SHA verification
- ✅ Success/failure notifications
- ✅ Sync status reporting
- ✅ Published sync reports

## 🎓 Learning Resources

- [Azure Pipelines YAML Reference](https://docs.microsoft.com/en-us/azure/devops/pipelines/yaml-schema)
- [Git Authentication in Azure Pipelines](https://docs.microsoft.com/en-us/azure/devops/pipelines/scripts/git-commands)
- [Build Service Permissions](https://docs.microsoft.com/en-us/azure/devops/pipelines/process/access-tokens)

## ✅ Validation Checklist

After setup, verify:
- [ ] Pipeline triggers on master branch push
- [ ] Azure DevOps repo receives commits
- [ ] Commit SHAs match between GitHub and Azure DevOps
- [ ] Pipeline logs show success messages
- [ ] No authentication errors
- [ ] Sync verification passes

## 🔄 Maintenance

Once configured, the pipeline:
- ✅ Runs automatically (no manual intervention)
- ✅ Self-validates sync success
- ✅ Logs all operations
- ✅ Requires zero maintenance

## 📞 Getting Help

1. Check [AZURE_QUICKSTART.md](./AZURE_QUICKSTART.md) for quick fixes
2. Review [AZURE_PIPELINE_SETUP.md](./AZURE_PIPELINE_SETUP.md) troubleshooting section
3. Examine [AZURE_ARCHITECTURE.md](./AZURE_ARCHITECTURE.md) to understand the flow
4. Review pipeline logs in Azure DevOps
5. Check Build Service permissions

## 🎉 Success Indicators

You'll know it's working when:
- ✅ Pipeline runs automatically on GitHub pushes
- ✅ Azure DevOps shows latest commits from GitHub
- ✅ Logs display: "Successfully synced to Azure DevOps!"
- ✅ Verification step shows matching commits
- ✅ No errors in pipeline execution

---

**Created:** 2025-10-10  
**Version:** 1.0  
**Status:** Production Ready  
**Maintenance:** Zero-touch after setup
