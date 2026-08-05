<div align="center">

<img src="https://github.com/user-attachments/assets/6f99f3d6-a519-47d8-bbf0-7cf8b356e773" alt="LineTec Services — A Centuri Company" width="360">

# Security Policy

**LineTec Services — Weekly Billing Automation**

</div>

---

This repository powers a **production billing pipeline** that handles
real financial data flowing between Smartsheet, Excel reports, and
Supabase. Security issues here can directly impact billing accuracy
and data confidentiality, so we take reports seriously.

## Supported Versions

This project is continuously deployed from the `master` branch via
GitHub Actions. Only the latest code on `master` is supported with
security updates.

| Version | Supported |
| ------- | --------- |
| `master` (latest) | :white_check_mark: |
| Archived scripts (`archive/`) | :x: |

## Reporting a Vulnerability

**Please do not open a public issue for security vulnerabilities.**

1. Use GitHub's **[private vulnerability reporting](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/security/advisories/new)**
   ("Report a vulnerability" under the repository's **Security** tab).
2. Include a description of the issue, steps to reproduce, affected
   files or workflows, and potential impact (e.g., data exposure,
   billing manipulation).
3. You can expect an initial acknowledgment within **5 business days**
   and a status update at least every **14 days** until resolution.
4. If the report is accepted, a fix will be prioritized based on
   severity and deployed through the normal CI/CD pipeline. If it is
   declined, we will explain why.

## Scope

Reports are welcome for any part of this repository, including:

- **Python billing engine** (`generate_weekly_pdfs.py`, `pipeline/`,
  `audit_billing_changes.py`, `billing_audit/`) — injection via
  Smartsheet data, path traversal outside `generated_docs/`, unsafe
  deserialization, secrets leakage in logs or Sentry events.
- **React dashboard** (`portal-v2/`) — auth bypass, Supabase RLS
  policy gaps, XSS, exposed keys.
- **CI/CD workflows** (`.github/workflows/`) — secret exfiltration,
  script injection through workflow inputs, artifact tampering.
- **Utility scripts** (`scripts/`) — Notion/Supabase integrations.

## Secret & Credential Handling

- **Never commit secrets.** All credentials (`SMARTSHEET_API_TOKEN`,
  `SENTRY_DSN`, Supabase keys, Notion tokens) are supplied via
  environment variables locally (`.env`, gitignored) and **GitHub
  repository secrets** in CI.
- `.env.example` and `.env.template` contain placeholders only.
- Sentry telemetry is sanitized: log capture is off by default
  (`SENTRY_ENABLE_LOGS=false`) and a `before_send_log` scrubber
  removes row-level PII as defense in depth.
- Generated output is confined to `generated_docs/`; file paths are
  sanitized to prevent traversal.

## Automated Security Controls

| Control | Where |
|---------|-------|
| Snyk dependency & code scanning | `.github/workflows/snyk-security.yml` |
| Secret scanning & push protection | GitHub repository settings |
| Lint / test gates on every PR | `.github/workflows/ci-checks.yml`, `python-lint.yml` |
| System health monitoring | `.github/workflows/system-health-check.yml` |
| Error monitoring with PII scrubbing | Sentry (Python + Node + React) |
| Financial audit trail | `audit_billing_changes.py` risk-level detection |

## Hardening Guidelines for Contributors

- Validate all Smartsheet-sourced input before using it in file names,
  formulas, or queries.
- Keep parallelism at or below 8 workers — abuse of the Smartsheet API
  rate limit (300 req/min) can cause denial of service to production
  billing runs.
- Rotate your Smartsheet API token if you suspect exposure, and update
  the corresponding GitHub secret.
- Follow the guardrails in `AGENTS.md` / `CLAUDE.md` before changing
  grouping, hashing, filename, or attachment-cleanup code — these are
  billing-critical paths.

---

<div align="center">

**LineTec Services** · *A Centuri Company*

</div>
