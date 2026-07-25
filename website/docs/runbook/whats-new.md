---
sidebar_position: 99
title: What's New
---

# What's New

_Last updated: July 25, 2026 (updated automatically)_

This page explains what each of our tools does and its recent updates, in everyday language.

## Weekly Billing Reports (DSR Resiliency)

> ℹ️ **What this system does:** Automated billing system that generates weekly Excel reports from Smartsheet data.

### 📋 Changelog — July 25, 2026

- ✅ Problem fixed: prevent Smartsheet API 4000 by correctly formatting column_ids
- ✨ New capability: smartsheet-python-sdk 4.3.0 migration (Phase 08)
- 📄 Help guides updated: log 26dba31 [skip ci]
- 🔧 Behind-the-scenes maintenance to keep things running smoothly
- 📄 Help guides updated: log 2ab0e00 [skip ci]
- ✅ Problem fixed: prevent Smartsheet API 4000 by correctly formatting column_ids ()
- 📄 Help guides updated: log a5b1b50 [skip ci]
- ✨ New capability: smartsheet-python-sdk 4.3.0 migration (Phase 08) ()

## linetec-inspector-manifest-generator

> ℹ️ **What this system does:** Python CLI that generates inspector-facing manifest Excel workbooks of ProMax claimed units — one Work Request at a time. It is a visual sibling of the weekly billing Excel (LineTec logo, red banner, summary blocks) restyled for review: no pricing, no Monday-Sunday day blocks, one continuous list natural-sorted by Point Number, with inspector-editable approval columns.

### 📋 Changelog — July 25, 2026

- ✨ New capability: optional version_number input on generate-manifest workflow (manual regen of versioned rows)
- 📄 Help guides updated: Gen B go-live record (gate armed, recovery enqueue proven)
- 📄 Help guides updated: phase 14 post-merge ledger sync
- ✅ Problem fixed: Gen B enqueue must not write formula-owned 'Inspector Ready?' cell
- • Phase 14: Approved-with-Modifications + Gen B regen-on-approval lifecycle
- 📄 Help guides updated: PR  review fixes + milestone v1.2 Lifecycle Automation planning
- 📄 Help guides updated: lifecycle design v2 — DV auto-hide, Revisions Made status, manager oversight (item 8)
- 📄 Help guides updated: ledger sync — PR  merged, post-merge protocol done

## JFlo21

> ℹ️ **What this system does:** > 💡 The snake animation above is generated automatically by a GitHub Action — it eats your contribution tiles!

_No changes this period — running steadily._ ✅

## notion-runbook-worker

> ℹ️ **What this system does:** A Notion Worker that keeps your operations runbook up to date automatically:

### 📋 Changelog — July 25, 2026

- 🔒 Security improvement: Rename GITHUB_* secret/env names to GH_*
- • Replace dated runbook pages with per-system Runbooks database (in-place updates, archived history, humanized wording)
- • Merge pull request  from JFlo21/copilot/implement-worker-link-instructions
- 🔒 Security improvement: Rename GITHUB_* secret/env names to GH_* (GitHub secrets can't start with GITHUB_)
- 📄 Help guides updated: update README for workers.json linking (remove obsolete `ntn workers link` wording)
- 🔧 Behind-the-scenes maintenance to keep things running smoothly
- 📄 Help guides updated: remove stray code-fence attribute from workers.json example
- 📄 Help guides updated: replace nonexistent `ntn workers link` with workers.json linking per official Notion CLI reference

## Parser that will offload grid format information from work request completed packets

> ℹ️ **What this system does:** Professional PDF/Excel Material Extractor for Linetec Services with web-based interface and desktop GUI.

_No changes this period — running steadily._ ✅

## Resiliency-pdf-restructure-ug-work

> ℹ️ **What this system does:** A comprehensive Python web application that processes PDF point material sheets to validate, filter, and redact Compatible Unit (CU) codes against a valid Underground (UG) product catalog.

### 📋 Changelog — July 25, 2026

- ✨ New capability: add self-service PDF batch interface
- • data: seed generated Work Request registry
- ✨ New capability: add PDF batch duplicate protection

## smartsheet-bot

### 📋 Changelog — July 25, 2026

- 🔧 Behind-the-scenes maintenance to keep things running smoothly

## "Daily sync: Supabase v_wr_pricing_rollup → Smartsheet 'Master storms data' (1444139672489860)"

> ℹ️ **What this system does:** Daily sync from Supabase pricing.vwrpricingrollup → Smartsheet sheet 1444139672489860 ("Master storms data").

### 📋 Changelog — July 25, 2026

- ✅ Problem fixed: Fix Sentry run-health evidence for pricing sync
- • Merge PR : verify Sentry positive run health
- 📄 Help guides updated: align Sentry setup with verified project
- ✅ Problem fixed: remove rejected legacy Sentry metrics
- ✅ Problem fixed: verify exact Sentry check-in in _test_sentry_run_health.py
- ✅ Problem fixed: verify exact Sentry check-in in verify_sentry_checkin.py
- ✅ Problem fixed: verify exact Sentry check-in in sync_pricing.py
- ✅ Problem fixed: verify exact Sentry check-in in daily-pricing-sync.yml

## ClaudeOS portable global config (skills, agents, hooks, launchers, bootstrap)

> ℹ️ **What this system does:** ClaudeOS portable global config (skills, agents, hooks, launchers, bootstrap)

### 📋 Changelog — July 25, 2026

- • Ledger: context-rot defense entry (compact-handoff loop, 40c981d)
- • Add automatic compact-handoff loop + context compaction protocol skill
- • checkpoint: 2026-07-21 audit fixes + debugging mastery + /doctor cleanup

## AI powered repository that will look back and check on my smartsheet to analyze for duplications of work requests line items

> ℹ️ **What this system does:** Automated read-only auditor for Smartsheet data that detects duplicate rows, learns patterns over time using machine learning, and publishes a professional audit dashboard to GitHub Pages every week.

### 📋 Changelog — July 25, 2026

- • 📊 Audit: 2026-07-20T07:38:23Z

## Morpheus — LLM-maintained wiki second brain (shared across Hermes local+cloud and Claude Code)

> ℹ️ **What this system does:** Morpheus — LLM-maintained wiki second brain (shared across Hermes local+cloud and Claude Code)

### 📋 Changelog — July 25, 2026

- • state: session-close ledger — reconciliation complete, next-session candidates
- • merge: fork reconciliation complete + approved schema changes + morpheus-sync hardening
- • lint: fold audit + web-standards reports into synthesis — recall-eval set, staleness flags, Sakana Fugu Ultra rename (9 links restored)
- • upgrade: second-brain architecture audit — git-health preflight, compounding enforcement, multi-device runbook, vault-health metrics, agentic-AI source ingested
- • repair: finish stranded rebase — recover 8 commits (Jun24–Jul17), resolve index/project-page conflicts, re-home desktop-line chronicle to Build History
- • auto-sync: local vault changes (2026-07-17 16:37)
- • wiki: manifest-generator 2026-07-06 — 7.5+7.6 complete, 7.7 registered, Supabase SMTP/captcha lessons
- • log: Generate-Weekly-PDFs v1.3.1 merged (PR  -> 8c51a3c)

## ClaudeOS .remember continuity store (session handoffs; no secrets by policy)

> ℹ️ **What this system does:** ClaudeOS .remember continuity store (session handoffs; no secrets by policy)

_No changes this period — running steadily._ ✅

## Linetec-Resiliency-Promax

> ℹ️ **What this system does:** Linetec-Resiliency-Promax

_No changes this period — running steadily._ ✅

## supabase-smartsheet-promax-offload

> ℹ️ **What this system does:** A Python script that automatically syncs data from multiple Smartsheet sheets to a Supabase database table. The script runs continuously and synchronizes data every 2 days (configurable).

_No changes this period — running steadily._ ✅

## Locator Spreadsheet Sync

> ℹ️ **What this system does:** This code automatically synchronizes the locators spreadsheets with the spreadsheets on smartsheet for seemless integration

_No changes this period — running steadily._ ✅

## Master Schedule Sync

> ℹ️ **What this system does:** Automatically synchronize attachments between two Smartsheet sheets based on matching column criteria. Runs daily at 5:00 AM UTC via GitHub Actions.

_No changes this period — running steadily._ ✅

## Master-to-Sibling Sheet Sync

> ℹ️ **What this system does:** Automated Smartsheet synchronization system supporting multi-source snapshot tracking with historical backfill capabilities.

_No changes this period — running steadily._ ✅

## promax-field-log

> ℹ️ **What this system does:** Read-only-by-default field data layer with deterministic Check My Work rules.

_No changes this period — running steadily._ ✅

## Cognos-pdf-parser-workspace

> ℹ️ **What this system does:** This private repo holds the AI/GSD planning context for the Linetec PDF Uploader project — the "where I left off" brain that lets work resume on any machine. It does not contain the application source code.

_No changes this period — running steadily._ ✅

## smartsheet-attachment-checker

> ℹ️ **What this system does:** Automated GitHub Actions workflow that syncs the "Is Attachment Present?" checkbox column on a Smartsheet based on whether each row actually has an attachment.

_No changes this period — running steadily._ ✅

## smartsheet-bug-tracker

_No changes this period — running steadily._ ✅

## econex

_No changes this period — running steadily._ ✅

## vite-react

> ℹ️ **What this system does:** This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

_No changes this period — running steadily._ ✅

## Destiny-Application-2

> ℹ️ **What this system does:** A Node.js application that fetches build crafting data from the Bungie API for Destiny 2.

_No changes this period — running steadily._ ✅

## Job Number Generator

_No changes this period — running steadily._ ✅

## AI-powered Data Analyst Agent using Claude Sonnet 4.5

> ℹ️ **What this system does:** AI-powered Data Analyst system using Claude Sonnet 4.5 that syncs Smartsheet data, indexes codebases, correlates code issues with data problems, and generates actionable reports.

_No changes this period — running steadily._ ✅

## cognos-parser

_No changes this period — running steadily._ ✅

## linetec-uploader-api

_No changes this period — running steadily._ ✅

## smartsheet-integration-docs

> ℹ️ **What this system does:** > Comprehensive documentation for all Smartsheet integration repositories

_No changes this period — running steadily._ ✅

## Destiny-Application

_No changes this period — running steadily._ ✅

## robofriends

> ℹ️ **What this system does:** This project was bootstrapped with Create React App.

_No changes this period — running steadily._ ✅

## Smartsheet-supabase-sync

> ℹ️ **What this system does:** This repo contains a scheduled job that syncs Smartsheet sheets into Supabase every 5 minutes.

_No changes this period — running steadily._ ✅

## Weekly Sheet Locking

> ℹ️ **What this system does:** Locks sheet rows on smartsheet after each week ending date has been reached.

_No changes this period — running steadily._ ✅

## upr-report-mapping

_No changes this period — running steadily._ ✅

## new repository

> ℹ️ **What this system does:** new repository

_No changes this period — running steadily._ ✅

## verbose-enigma

_No changes this period — running steadily._ ✅

## Combine-data-resiliency-promax

_No changes this period — running steadily._ ✅

## lintec-sidebar-navigator

> ℹ️ **What this system does:** URL: https://lovable.dev/projects/d8e2b683-db36-447d-b3fa-4c89ea12a4cb

_No changes this period — running steadily._ ✅

## Dynamic-Project-List-Schedule

_No changes this period — running steadily._ ✅

## lintec-sidebar-navigator-59

> ℹ️ **What this system does:** URL: https://lovable.dev/projects/d8e2b683-db36-447d-b3fa-4c89ea12a4cb

_No changes this period — running steadily._ ✅

## linetec-DSR-project

_No changes this period — running steadily._ ✅

## Linetec

_No changes this period — running steadily._ ✅

## background-generator

_No changes this period — running steadily._ ✅

## startup-of-my-own

_No changes this period — running steadily._ ✅

## startup.github.io

_No changes this period — running steadily._ ✅

## JFlo21.github.io

_No changes this period — running steadily._ ✅

