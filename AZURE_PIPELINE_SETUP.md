# Azure Pipelines - GitHub to Azure DevOps Sync

This Azure Pipeline automatically syncs changes from the GitHub master branch to your Azure DevOps repository.

## 📋 Overview

The `azure-pipelines.yml` workflow:
- ✅ Automatically triggers on any push to the `master` branch
- ✅ Syncs the complete repository history to Azure DevOps
- ✅ Preserves commit messages, authors, and timestamps
- ✅ Verifies successful synchronization
- ✅ Provides detailed logging and error reporting

## 🚀 Setup Instructions

### Prerequisites

1. **Azure DevOps Organization and Project**
   - Have an Azure DevOps organization set up
   - Create a project in Azure DevOps
   - Create a Git repository in your Azure DevOps project

2. **Azure DevOps Repository URL**
   - Note your repository URL format:
     ```
     https://dev.azure.com/{organization}/{project}/_git/{repository}
     ```
   - Example:
     ```
     https://dev.azure.com/mycompany/MyProject/_git/Generate-Weekly-PDFs-DSR-Resiliency
     ```

### Step 1: Import azure-pipelines.yml to Azure DevOps

1. **Navigate to Azure Pipelines**
   - Go to your Azure DevOps project
   - Click on **Pipelines** in the left sidebar
   - Click **New Pipeline**

2. **Connect to GitHub**
   - Select **GitHub** as your code source
   - Authenticate with GitHub (if not already connected)
   - Select the `JFlo21/Generate-Weekly-PDFs-DSR-Resiliency` repository

3. **Configure Pipeline**
   - Azure DevOps will detect the `azure-pipelines.yml` file
   - Click **Run** to use the existing YAML configuration

### Step 2: Configure Pipeline Variables

1. **Add Azure DevOps Repository URL Variable**
   - In your pipeline, click **Edit**
   - Click **Variables** (top right)
   - Click **New variable**
   - Add the following:
     - **Name:** `AzureDevOpsRepoUrl`
     - **Value:** Your Azure DevOps repository URL
       ```
       https://dev.azure.com/{organization}/{project}/_git/{repository}
       ```
     - **Keep this value secret:** No (unless your URL contains sensitive info)
   - Click **OK** and **Save**

### Step 3: Configure Permissions

The pipeline uses the `System.AccessToken` to authenticate with Azure DevOps. You need to ensure the build service has permission to push to your repository:

1. **Grant Repository Permissions**
   - Go to **Project Settings** (bottom left in Azure DevOps)
   - Navigate to **Repositories** → Select your repository
   - Click on **Security** tab
   - Find **{Project} Build Service ({Organization})**
   - Grant the following permissions:
     - ✅ **Contribute:** Allow
     - ✅ **Force Push:** Allow (required for sync)
     - ✅ **Create Branch:** Allow

2. **Enable OAuth Token Access**
   - Go to your pipeline
   - Click **Edit** → **...** (More options) → **Triggers**
   - Select the **YAML** tab
   - Under **Advanced settings** section:
     - Enable **Allow scripts to access the OAuth token**
   - **Save**

### Step 4: Trigger Configuration

The pipeline is configured to:
- ✅ **Trigger on:** Any push to `master` branch
- ✅ **Exclude:** Changes to README.md and .github/ directory
- ❌ **No PR triggers:** Only direct pushes to master are synced

To modify triggers, edit the `trigger` section in `azure-pipelines.yml`:

```yaml
trigger:
  branches:
    include:
      - master
      - main  # Add if you also use 'main' branch
  paths:
    exclude:
      - README.md
      - .github/**
      - docs/**  # Add more exclusions as needed
```

## 🔧 Configuration Options

### Custom Git User

Modify the Git user information in the pipeline:

```yaml
variables:
  GIT_USER_NAME: 'Your Sync Bot Name'
  GIT_USER_EMAIL: 'your-bot@example.com'
```

### Branch Mapping

To sync to a different branch in Azure DevOps, modify the push command:

```bash
# Current: pushes master to master
push azure-devops master:master

# Example: push master to develop
push azure-devops master:develop

# Example: push to same-named branch
push azure-devops HEAD:$(Build.SourceBranchName)
```

### Force Push vs Regular Push

Current configuration uses `--force` to ensure sync:
```bash
git push azure-devops master:master --force
```

For regular push (requires Azure DevOps to be in sync):
```bash
git push azure-devops master:master
```

## 📊 Monitoring and Logs

### View Pipeline Runs

1. Go to **Pipelines** in Azure DevOps
2. Select your sync pipeline
3. View run history and logs

### Log Output Includes

- ✅ Source and target repository URLs
- ✅ Current commit SHA, author, and message
- ✅ Git remote configuration
- ✅ Push operation results
- ✅ Sync verification (commit comparison)
- ✅ Success/failure status

### Sync Verification

The pipeline automatically verifies sync by:
1. Fetching the latest commit from Azure DevOps
2. Comparing GitHub commit SHA with Azure DevOps commit SHA
3. Reporting match/mismatch status

## 🔐 Security Considerations

1. **System.AccessToken**
   - Automatically provided by Azure Pipelines
   - Limited to pipeline execution scope
   - No need to create personal access tokens

2. **Repository URL Variable**
   - Can be marked as secret if it contains sensitive information
   - Accessible only to the pipeline

3. **Branch Protection**
   - Consider enabling branch policies on Azure DevOps
   - Protect against accidental overwrites

## 🛠️ Troubleshooting

### Common Issues

**1. Authentication Errors**
```
Error: Authentication failed
```
**Solution:** Ensure "Allow scripts to access the OAuth token" is enabled in pipeline settings.

**2. Permission Denied**
```
Error: Permission denied (publickey/forbidden)
```
**Solution:** Grant Build Service "Contribute" and "Force Push" permissions on the repository.

**3. Repository URL Not Set**
```
ERROR: Azure DevOps repository URL is not configured!
```
**Solution:** Add the `AzureDevOpsRepoUrl` variable in pipeline settings.

**4. Commits Don't Match Warning**
```
⚠️ Warning: Commits do not match
```
**Solution:** This can happen if Azure DevOps has commits not in GitHub. Review both repositories and decide if you need to force sync.

### Debug Steps

1. **Check Pipeline Variables**
   ```
   Pipeline → Edit → Variables → Verify AzureDevOpsRepoUrl
   ```

2. **Verify Build Service Permissions**
   ```
   Project Settings → Repositories → Security → Check Build Service permissions
   ```

3. **Review Pipeline Logs**
   ```
   Pipeline Run → Select failed job → View detailed logs
   ```

4. **Test Git Remote**
   - Use the pipeline logs to see the exact git commands
   - Verify the Azure DevOps URL is accessible

## 🔄 Alternative Sync Methods

If you need different sync behavior, consider these alternatives:

### 1. Mirror Sync (All Branches and Tags)
```yaml
- script: |
    git push azure-devops --mirror
  displayName: 'Mirror all branches and tags'
```

### 2. Selective Branch Sync
```yaml
- script: |
    # Sync multiple branches
    git push azure-devops master:master
    git push azure-devops develop:develop
    git push azure-devops release/*:release/*
  displayName: 'Sync multiple branches'
```

### 3. Sync with Pull Request
Instead of force push, create a PR in Azure DevOps:
- Use Azure DevOps API to create PR
- Allows review before merging
- Better for compliance requirements

## 📚 Additional Resources

- [Azure Pipelines YAML Schema](https://docs.microsoft.com/en-us/azure/devops/pipelines/yaml-schema)
- [Git Authentication in Azure Pipelines](https://docs.microsoft.com/en-us/azure/devops/pipelines/scripts/git-commands)
- [Pipeline Triggers](https://docs.microsoft.com/en-us/azure/devops/pipelines/build/triggers)
- [Build Service Permissions](https://docs.microsoft.com/en-us/azure/devops/pipelines/process/access-tokens)

## 📝 Notes

- The pipeline uses full fetch depth (`fetchDepth: 0`) to sync complete history
- Force push ensures Azure DevOps stays in perfect sync with GitHub
- The pipeline runs only on master branch changes (PR triggers disabled)
- Sync verification step helps detect any sync issues early

## 🆘 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review Azure Pipeline logs for detailed error messages
3. Verify all prerequisites are met
4. Ensure build service has proper permissions
5. Test the Azure DevOps repository URL manually

---

**Created:** 2025
**Last Updated:** 2025-10-10
