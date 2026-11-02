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
│   Auth: PAT (AZDO_PAT secret variable)                          │
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
│           └── git remote add azure <url>                        │
│                                                                   │
│   Step 4: Push to Azure DevOps                                  │
│           └── git push --force-with-lease azure master:master   │
│                                                                   │
│   Step 5: Optional (commented out): full mirror, diagnostics    │
│           └── Not run by default                                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ (3) Force push (with lease) with PAT
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
   ├── git config user.name "Azure Pipelines"
   └── git config user.email "buildagent@azuredevops.local"

5. Pipeline adds Azure DevOps remote
   ├── URL built from AZDO_ORG, AZDO_PROJECT, AZDO_REPO
   └── git remote add azure <url>

6. Pipeline authenticates
   ├── Uses PAT from secret variable AZDO_PAT
   └── http.extraheader="AUTHORIZATION: Basic <base64(:PAT)>"

7. Pipeline pushes to Azure DevOps
   ├── git push --force-with-lease azure master:master
   ├── Syncs all commits
   └── Overwrites Azure DevOps master

8. Pipeline ends after the push
   ├── No separate verification step
   └── A rejected push fails the job

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
       │ (1) Read secret variable AZDO_PAT
       ▼
┌──────────────────────────────┐
│  Pipeline secret variable    │
│                              │
│  Holds:                      │
│  AZDO_PAT                    │
└──────────┬───────────────────┘
           │
           │ (2) Encoded as Basic header
           │     (~/.azdo_header, mode 600)
           ▼
┌──────────────────────────────┐
│  Git Push Operation          │
│                              │
│  Authorization Header:       │
│  Basic <base64(:PAT)>        │
└──────────┬───────────────────┘
           │
           │ (3) Authenticated request
           ▼
┌──────────────────────────────┐
│  Azure DevOps Repository     │
│                              │
│  Validates PAT               │
│  Checks PAT owner perms      │
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

Is it a push to GitHub (or a PR targeting master)?
  ├── YES → Continue
  └── NO → Exit

Is the branch 'master'?
  ├── YES → Continue
  └── NO → Exit (other branches ignored)

Are changed files filtered?
  └── No paths filter → any change TRIGGERS PIPELINE ✅

Pipeline runs:
  └── Syncs master to Azure DevOps
```

## 🔧 Configuration Dependencies

```
Required Variables:
┌────────────────────────────────────────┐
│  Name: AZDO_PAT                        │
│  Value: (secret; never commit it)      │
│  Scope: Pipeline (secret variable)     │
│  Required: ✅ YES                      │
└────────────────────────────────────────┘

Required Permissions:
┌────────────────────────────────────────┐
│  PAT owner account:                    │
│    ✅ Contribute                       │
│    ✅ Force Push                       │
│    ✅ Create Branch                    │
│                                        │
│  Pipeline Variable:                    │
│    ✅ AZDO_PAT set as a secret         │
└────────────────────────────────────────┘

Git Configuration:
┌────────────────────────────────────────┐
│  user.name: "Azure Pipelines"          │
│  user.email: "buildagent@azuredevops.local"│
└────────────────────────────────────────┘
```

## 📈 Success Metrics

```
Sync Success Indicators:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Pipeline completes without errors
✅ Push operation succeeds
✅ Seed fetch of azure master succeeds
✅ Logs show: "Prepared PAT header for Azure DevOps pushes."
✅ Azure DevOps repo shows latest commit from GitHub
✅ Commit SHA matches exactly

Failure Indicators:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ Authentication errors
❌ Permission denied
❌ Variable not configured
❌ Push rejected
❌ AZDO_PAT not set (sync is skipped with a warning)
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
  git push --force-with-lease azure <source>:<target>
```

## 🔍 Monitoring Points

```
Key Log Checkpoints:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ✅ "Azure remote set to:" 
   └── Remote configured (URL printed below it)

2. ✅ "Prepared PAT header for Azure DevOps pushes." 
   └── PAT header ready

3. ✅ "Converting shallow clone to full clone..." 
   └── Only printed if the checkout was shallow

4. ⚠️ "AZDO_PAT is not set or not replaced. Skipping ..." 
   └── Sync was skipped (the step exits 0)

5. ✅ Step "Mirror GitHub → Azure DevOps (default branch, safer force)" completes 
   └── Push succeeded
```

---

**Architecture Version:** 1.0  
**Last Updated:** 2025-10-10  
**Status:** Production Ready
