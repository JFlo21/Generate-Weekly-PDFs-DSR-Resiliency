# Azure Pipeline Sync - Architecture & Flow

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         GitHub Repository                        │
│                                                                   │
│   JFlo21/Generate-Weekly-PDFs-DSR-Resiliency                    │
│                                                                   │
│   Branch: master                                                 │
│   Contains: azure-pipelines.yml                                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ (1) Push to master
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Azure Pipelines                            │
│                                                                   │
│   Trigger: master branch push                                    │
│   Agent: Ubuntu Latest                                           │
│   Auth: System.AccessToken (OAuth)                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ (2) Execute pipeline
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Pipeline Execution Steps                      │
│                                                                   │
│   Step 1: Checkout code (full history)                          │
│           ├── fetchDepth: 0                                     │
│           └── persistCredentials: true                          │
│                                                                   │
│   Step 2: Configure Git                                          │
│           ├── Set user.name                                     │
│           └── Set user.email                                    │
│                                                                   │
│   Step 3: Add Azure DevOps remote                               │
│           └── git remote add azure-devops <url>                 │
│                                                                   │
│   Step 4: Push to Azure DevOps                                  │
│           └── git push azure-devops master:master --force       │
│                                                                   │
│   Step 5: Verify sync                                            │
│           └── Compare commit SHAs                               │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ (3) Force push with OAuth
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Azure DevOps Git Repository                     │
│                                                                   │
│   URL: dev.azure.com/{org}/{project}/_git/{repo}                │
│   Branch: master (synced)                                        │
│   Status: ✅ In perfect sync with GitHub                        │
└─────────────────────────────────────────────────────────────────┘
```

## 🔄 Sync Flow Diagram

```
Developer Workflow:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Developer commits to GitHub master
   ├── git commit -m "Update feature"
   └── git push origin master

2. GitHub receives push
   └── Webhook triggers Azure Pipeline

3. Azure Pipeline starts
   ├── Clones GitHub repo
   ├── Gets latest master branch
   └── Full git history (fetchDepth: 0)

4. Pipeline configures Git
   ├── git config user.name "Azure Pipeline Sync Bot"
   └── git config user.email "pipeline-sync@azure-devops.com"

5. Pipeline adds Azure DevOps remote
   ├── URL from variable: AzureDevOpsRepoUrl
   └── git remote add azure-devops <url>

6. Pipeline authenticates
   ├── Uses System.AccessToken (OAuth)
   └── http.extraheader="AUTHORIZATION: bearer <token>"

7. Pipeline pushes to Azure DevOps
   ├── git push azure-devops master:master --force
   ├── Syncs all commits
   └── Overwrites Azure DevOps master

8. Pipeline verifies sync
   ├── Fetches Azure DevOps master
   ├── Compares commit SHAs
   └── Reports: ✅ Success or ⚠️ Warning

9. Azure DevOps master updated
   └── Same commits as GitHub master

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 🔐 Authentication Flow

```
┌──────────────┐
│  Azure       │
│  Pipeline    │
│  Agent       │
└──────┬───────┘
       │
       │ (1) Request OAuth token
       ▼
┌──────────────────────────────┐
│  Azure DevOps                │
│  OAuth Service               │
│                              │
│  Generates:                  │
│  System.AccessToken          │
└──────────┬───────────────────┘
           │
           │ (2) Token issued
           │     (limited scope: this pipeline)
           ▼
┌──────────────────────────────┐
│  Git Push Operation          │
│                              │
│  Authorization Header:       │
│  Bearer <System.AccessToken> │
└──────────┬───────────────────┘
           │
           │ (3) Authenticated request
           ▼
┌──────────────────────────────┐
│  Azure DevOps Repository     │
│                              │
│  Validates token             │
│  Checks Build Service perms  │
│  Allows push if authorized   │
└──────────────────────────────┘
```

## 📊 Data Flow

```
GitHub Commit Data:
┌─────────────────────────────────────────┐
│  Commit SHA: abc123...                  │
│  Author: John Doe                       │
│  Email: john@example.com                │
│  Date: 2025-10-10 21:30:00             │
│  Message: "Add new feature"             │
│  Files: [file1.py, file2.py]           │
└─────────────────────────────────────────┘
              │
              │ Pipeline sync preserves ALL data
              ▼
Azure DevOps Commit Data:
┌─────────────────────────────────────────┐
│  Commit SHA: abc123... ✅ SAME          │
│  Author: John Doe ✅ PRESERVED          │
│  Email: john@example.com ✅ PRESERVED   │
│  Date: 2025-10-10 21:30:00 ✅ PRESERVED │
│  Message: "Add new feature" ✅ PRESERVED│
│  Files: [file1.py, file2.py] ✅ SAME   │
└─────────────────────────────────────────┘
```

## 🎯 Trigger Logic

```
Event Evaluation:
────────────────────────────────────────────

Is it a push to GitHub?
  ├── YES → Continue
  └── NO → Exit

Is the branch 'master'?
  ├── YES → Continue
  └── NO → Exit (other branches ignored)

Are changed files excluded?
  ├── README.md → Skip (excluded)
  ├── .github/** → Skip (excluded)
  └── Other files → TRIGGER PIPELINE ✅

Pipeline runs:
  └── Syncs master to Azure DevOps
```

## 🔧 Configuration Dependencies

```
Required Variables:
┌────────────────────────────────────────┐
│  Name: AzureDevOpsRepoUrl              │
│  Value: https://dev.azure.com/...     │
│  Scope: Pipeline                       │
│  Required: ✅ YES                      │
└────────────────────────────────────────┘

Required Permissions:
┌────────────────────────────────────────┐
│  Build Service Account:                │
│    ✅ Contribute                       │
│    ✅ Force Push                       │
│    ✅ Create Branch                    │
│                                        │
│  Pipeline Setting:                     │
│    ✅ Allow OAuth token access         │
└────────────────────────────────────────┘

Git Configuration:
┌────────────────────────────────────────┐
│  user.name: "Azure Pipeline Sync Bot"  │
│  user.email: "pipeline-sync@..."       │
└────────────────────────────────────────┘
```

## 📈 Success Metrics

```
Sync Success Indicators:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Pipeline completes without errors
✅ Push operation succeeds
✅ Verification step shows matching commits
✅ Logs show: "Successfully synced to Azure DevOps!"
✅ Azure DevOps repo shows latest commit from GitHub
✅ Commit SHA matches exactly

Failure Indicators:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ Authentication errors
❌ Permission denied
❌ Variable not configured
❌ Push rejected
❌ Commits don't match in verification
```

## 🛠️ Maintenance Mode

```
To disable sync temporarily:
────────────────────────────────────────────
1. Go to Azure Pipeline
2. Edit → ⋯ → Settings
3. Disable triggers

To modify sync behavior:
────────────────────────────────────────────
1. Edit azure-pipelines.yml
2. Update trigger, branches, or paths
3. Commit to GitHub
4. Pipeline auto-updates

To sync different branch:
────────────────────────────────────────────
Change push command:
  git push azure-devops <source>:<target>
```

## 🔍 Monitoring Points

```
Key Log Checkpoints:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ✅ "Configuring Git..." 
   └── Git setup successful

2. ✅ "Source (GitHub): ..." 
   └── URLs configured correctly

3. ✅ "Syncing commit: SHA: abc123..." 
   └── Correct commit being synced

4. ✅ "Adding Azure DevOps remote..." 
   └── Remote configured

5. ✅ "Pushing to Azure DevOps repository..." 
   └── Push initiated

6. ✅ "Successfully synced to Azure DevOps!" 
   └── Sync completed

7. ✅ "Verification successful - commits match!" 
   └── Sync verified
```

---

**Architecture Version:** 1.0  
**Last Updated:** 2025-10-10  
**Status:** Production Ready
