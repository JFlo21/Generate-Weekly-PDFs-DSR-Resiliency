# Azure Pipelines - GitHub to Azure DevOps Sync

This Azure Pipeline automatically syncs changes from the GitHub master branch to your Azure DevOps repository.

## 📋 Overview

The `azure-pipelines.yml` workflow:
- ✅ Automatically triggers on any push to the `master` branch
- ✅ Syncs the complete repository history to Azure DevOps
- ✅ Preserves commit messages, authors, and timestamps
- ✅ Uses `--force-with-lease`, so concurrent Azure DevOps changes are not silently overwritten
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

1. **Add the Azure DevOps PAT Secret Variable**
   - In your pipeline, click **Edit**
   - Click **Variables** (top right)
   - Click **New variable**
   - Add the following:
     - **Name:** `AZDO_PAT`
     - **Value:** A Personal Access Token that can push to your Azure DevOps repository
     - **Keep this value secret:** Yes
   - Click **OK** and **Save**
   - The repository location comes from `AZDO_ORG`, `AZDO_PROJECT`, and `AZDO_REPO`, which are set in the `variables:` block of `azure-pipelines.yml`
     (the URL is built as `https://dev.azure.com/{organization}/{project}/_git/{repository}`)

### Step 3: Configure Permissions

The pipeline uses a Personal Access Token (the secret variable `AZDO_PAT`), sent as a Basic `http.extraheader`, to authenticate with Azure DevOps. You need to ensure the user that owns the PAT has permission to push to your repository:

1. **Grant Repository Permissions**
   - Go to **Project Settings** (bottom left in Azure DevOps)
   - Navigate to **Repositories** → Select your repository
   - Click on **Security** tab
   - Find the user that owns the PAT
   - Grant the following permissions:
     - ✅ **Contribute:** Allow
     - ✅ **Force Push:** Allow (required for sync)
     - ✅ **Create Branch:** Allow

2. **Keep the PAT Secret**
   - Mark `AZDO_PAT` as a secret variable (see Step 2)
   - Never put the PAT value in `azure-pipelines.yml` or commit it to the repository

### Step 4: Trigger Configuration

The pipeline is configured to:
- ✅ **Trigger on:** Any push to `master` branch
- ❌ **No path filters:** Changes to README.md and the .github/ directory are synced with everything else
- ✅ **PR trigger:** A `pr:` trigger on the `master` branch is also defined

To modify triggers (for example, to add path exclusions, which are not configured today), edit the `trigger` section in `azure-pipelines.yml`:

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

```bash
git config --global user.name "Azure Pipelines"
git config --global user.email "buildagent@azuredevops.local"
```

### Branch Mapping

To sync to a different branch in Azure DevOps, modify the push command:

```bash
# Current: pushes master to master
git push --force-with-lease azure master:master

# Example: push master to develop
git push --force-with-lease azure master:develop

# Example: push to same-named branch
git push --force-with-lease azure HEAD:$(Build.SourceBranchName)
```

### Force Push vs Regular Push

Current configuration uses `--force-with-lease` (a safer variant of `--force`) to ensure sync:
```bash
git push --force-with-lease azure master:master
```

For regular push (requires Azure DevOps to be in sync):
```bash
git push azure master:master
```

## 📊 Monitoring and Logs

### View Pipeline Runs

1. Go to **Pipelines** in Azure DevOps
2. Select your sync pipeline
3. View run history and logs

### Log Output Includes

- ✅ The Azure DevOps remote URL ("Azure remote set to:")
- ✅ Confirmation that the PAT header was prepared (the PAT itself is not printed)
- ✅ Git output for the fetch, pull, and push
- ✅ Success/failure status of each step
- ⚠️ A warning when `AZDO_PAT` is not set (the sync is skipped)

### Sync Verification

The pipeline has no separate verification step. Before pushing, it runs `git fetch azure master` to seed the lease, so the `--force-with-lease` push is rejected if Azure DevOps `master` changed since that fetch. To verify manually, compare the latest `master` commit SHA in GitHub and Azure DevOps.

## 🔐 Security Considerations

1. **Personal Access Token (`AZDO_PAT`)**
   - Stored as a secret pipeline variable
   - Sent as a Basic `http.extraheader` (written to `~/.azdo_header`, mode 600), never embedded in the URL
   - You create it in Azure DevOps and must renew it before it expires

2. **Repository Location Variables**
   - `AZDO_ORG`, `AZDO_PROJECT`, and `AZDO_REPO` are set in `azure-pipelines.yml` and are not secret
   - Only `AZDO_PAT` holds a secret

3. **Branch Protection**
   - Consider enabling branch policies on Azure DevOps
   - Protect against accidental overwrites

## 🛠️ Troubleshooting

### Common Issues

**1. Authentication Errors**
```
Error: Authentication failed
```
**Solution:** Ensure the `AZDO_PAT` secret variable is set, has not expired, and can push to the repository.

**2. Permission Denied**
```
Error: Permission denied (publickey/forbidden)
```
**Solution:** Grant the PAT owner "Contribute" and "Force Push" permissions on the repository.

**3. AZDO_PAT Not Set**
```
⚠️ AZDO_PAT is not set or not replaced. Skipping Azure DevOps configuration.
```
**Solution:** Add the `AZDO_PAT` secret variable in pipeline settings. The run still succeeds (the step exits 0) but nothing is synced.

**4. Push Rejected (stale info)**
```
! [rejected] master -> master (stale info)
```
**Solution:** This can happen if Azure DevOps has commits not in GitHub (the `--force-with-lease` check failed). Review both repositories and decide if you need to force sync.

### Debug Steps

1. **Check Pipeline Variables**
   ```
   Pipeline → Edit → Variables → Verify AZDO_PAT
   ```

2. **Verify PAT Owner Permissions**
   ```
   Project Settings → Repositories → Security → Check the PAT owner's permissions
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
    git push azure --mirror
  displayName: 'Mirror all branches and tags'
```

### 2. Selective Branch Sync
```yaml
- script: |
    # Sync multiple branches
    git push azure master:master
    git push azure develop:develop
    git push azure release/*:release/*
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
- Force push (with lease) keeps Azure DevOps in sync with GitHub unless Azure DevOps changed in the meantime
- The pipeline runs on master branch changes and on pull requests targeting master (`pr:` trigger)
- If `AZDO_PAT` is not set, the sync is skipped with a warning and the run still succeeds

## 🆘 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review Azure Pipeline logs for detailed error messages
3. Verify all prerequisites are met
4. Ensure the PAT owner has proper permissions
5. Test the Azure DevOps repository URL manually

---

**Created:** 2025
**Last Updated:** 2025-10-10
