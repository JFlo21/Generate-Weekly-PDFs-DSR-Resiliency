---
sidebar_position: 99
title: What's New
---

# What's New

_Last updated: July 29, 2026 (updated automatically)_

This page explains what each of our tools does and its recent updates, in everyday language.

<!-- runbook-repo: JFlo21/JFlo21 -->
## JFlo21

> ℹ️ **What this system does:** &gt; 💡 The snake animation above is generated automatically by a GitHub Action — it eats your contribution tiles&#33;

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Cognos-pdf-parser -->
## Parser that will offload grid format information from work request completed packets

> ℹ️ **What this system does:** Professional PDF/Excel Material Extractor for Linetec Services with web-based interface and desktop GUI.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/generate-job-numbers -->
## Job Number Generator

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

### 📋 Changelog — July 29, 2026

- 🔧 Behind-the-scenes maintenance to keep things running smoothly

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Generate-Weekly-PDFs-DSR-Resiliency -->
## Weekly Billing Reports (DSR Resiliency)

> ℹ️ **What this system does:** Automated billing system that generates weekly Excel reports from Smartsheet data.

### 📋 Changelog — July 29, 2026

- ✅ Problem fixed: break runbook push loop, filter Notion changelog noise, remove stale Render blueprint
- ✅ Problem fixed: stop CI failure emails + filter Linetec runlog to contextful entries
- ✅ Problem fixed: prevent Smartsheet API 4000 by correctly formatting column&#95;ids
- ✨ New capability: smartsheet-python-sdk 4.3.0 migration (Phase 08)
- 📄 Help guides updated: automated plain-language update from Notion Worker
- 📄 Help guides updated: log 70b71f8 &#91;skip ci&#93;
- ✅ Problem fixed: break runbook push loop, filter Notion changelog noise, remove stale Render blueprint ()
- 📄 Help guides updated: log 6af4ee3 &#91;skip ci&#93;

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/sync-master-schedule -->
## Master Schedule Sync

> ℹ️ **What this system does:** Automatically synchronize attachments between two Smartsheet sheets based on matching column criteria. Runs daily at 5:00 AM UTC via GitHub Actions.

### 📋 Changelog — July 29, 2026

- 🔧 Behind-the-scenes maintenance to keep things running smoothly

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/master-to-sibling-smartsheet-function -->
## Master-to-Sibling Sheet Sync

> ℹ️ **What this system does:** Automated Smartsheet synchronization system supporting multi-source snapshot tracking with historical backfill capabilities.

### 📋 Changelog — July 29, 2026

- 🔧 Behind-the-scenes maintenance to keep things running smoothly

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/lock_sheet_rows -->
## Weekly Sheet Locking

> ℹ️ **What this system does:** Locks sheet rows on smartsheet after each week ending date has been reached.

### 📋 Changelog — July 29, 2026

- 🔧 Behind-the-scenes maintenance to keep things running smoothly

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/smartsheet-sync-locators -->
## Locator Spreadsheet Sync

> ℹ️ **What this system does:** This code automatically synchronizes the locators spreadsheets with the spreadsheets on smartsheet for seemless integration

### 📋 Changelog — July 29, 2026

- 🔧 Behind-the-scenes maintenance to keep things running smoothly

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/linetec-inspector-manifest-generator -->
## linetec-inspector-manifest-generator

> ℹ️ **What this system does:** Python CLI that generates inspector-facing manifest Excel workbooks of ProMax claimed units — one Work Request at a time. It is a visual sibling of the weekly billing Excel (LineTec logo, red banner, summary blocks) restyled for review: no pricing, no Monday-Sunday day blocks, one continuous list natural-sorted by Point Number, with inspector-editable approval columns.

### 📋 Changelog — July 29, 2026

- ✨ New capability: plumb D-23 Week-Ending override into intake worker
- 📄 Help guides updated: capture Phase 15.1 (Bret GF Excel-edit revision loop) + Phase 15 debug-first gate
- ✅ Problem fixed: live admin role/ban recheck + sync banned-user skip (post-7.7 hardening)
- ✅ Problem fixed: scope filter tolerates base-scope ProMax rows (5-WR zero-row Parser Error incident)
- 📄 Help guides updated: full-autonomy master-schedule intake requirement (Phase 18 scope detail)
- ✨ New capability: optional version&#95;number input on generate-manifest workflow (manual regen of versioned rows)
- 📄 Help guides updated: Gen B go-live record (gate armed, recovery enqueue proven)
- 📄 Help guides updated: phase 14 post-merge ledger sync

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/notion-runbook-worker -->
## Runbook Automation

> ℹ️ **What this system does:** A Notion Worker that keeps your operations runbook up to date automatically:

### 📋 Changelog — July 29, 2026

- 🔒 Security improvement: Rename GITHUB&#95;&#42; secret/env names to GH&#95;&#42;
- • Replace dated runbook pages with per-system Runbooks database (in-place updates, archived history, humanized wording)
- 🔧 Behind-the-scenes maintenance to keep things running smoothly
- • Merge pull request from JFlo21/copilot/implement-worker-link-instructions
- 🔒 Security improvement: Rename GITHUB&#95;&#42; secret/env names to GH&#95;&#42; (GitHub secrets can't start with GITHUB&#95;)
- 📄 Help guides updated: update README for workers.json linking (remove obsolete &#96;ntn workers link&#96; wording)
- 📄 Help guides updated: remove stray code-fence attribute from workers.json example
- 📄 Help guides updated: replace nonexistent &#96;ntn workers link&#96; with workers.json linking per official Notion CLI reference

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/smartsheet-auditor -->
## AI powered repository that will look back and check on my smartsheet to analyze for duplications of work requests line items

> ℹ️ **What this system does:** Automated read-only auditor for Smartsheet data that detects duplicate rows, learns patterns over time using machine learning, and publishes a professional audit dashboard to GitHub Pages every week.

### 📋 Changelog — July 29, 2026

- • 📊 Audit: 2026-07-27T07:40:56Z

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/smartsheet-bot -->
## smartsheet-bot

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

### 📋 Changelog — July 29, 2026

- 🔧 Behind-the-scenes maintenance to keep things running smoothly

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Resiliency-pdf-restructure-ug-work -->
## Resiliency-pdf-restructure-ug-work

> ℹ️ **What this system does:** A comprehensive Python web application that processes PDF point material sheets to validate, filter, and redact Compatible Unit (CU) codes against a valid Underground (UG) product catalog.

### 📋 Changelog — July 29, 2026

- ✨ New capability: add self-service PDF batch interface
- • data: seed generated Work Request registry
- ✨ New capability: add PDF batch duplicate protection

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Preplanned-Pricing-Sync -->
## "Daily sync: Supabase v&#95;wr&#95;pricing&#95;rollup → Smartsheet 'Master storms data' (1444139672489860)"

> ℹ️ **What this system does:** Daily sync from Supabase pricing.vwrpricingrollup → Smartsheet sheet 1444139672489860 ("Master storms data").

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/claudeos -->
## ClaudeOS portable global config (skills, agents, hooks, launchers, bootstrap)

> ℹ️ **What this system does:** ClaudeOS portable global config (skills, agents, hooks, launchers, bootstrap)

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/morpheus-second-brain -->
## Morpheus — LLM-maintained wiki second brain (shared across Hermes local+cloud and Claude Code)

> ℹ️ **What this system does:** Morpheus — LLM-maintained wiki second brain (shared across Hermes local+cloud and Claude Code)

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/remember-continuity -->
## ClaudeOS .remember continuity store (session handoffs; no secrets by policy)

> ℹ️ **What this system does:** ClaudeOS .remember continuity store (session handoffs; no secrets by policy)

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Linetec-Resiliency-Promax -->
## Linetec-Resiliency-Promax

> ℹ️ **What this system does:** Linetec-Resiliency-Promax

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/supabase-smartsheet-promax-offload -->
## supabase-smartsheet-promax-offload

> ℹ️ **What this system does:** A Python script that automatically syncs data from multiple Smartsheet sheets to a Supabase database table. The script runs continuously and synchronizes data every 2 days (configurable).

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/promax-field-log -->
## promax-field-log

> ℹ️ **What this system does:** Read-only-by-default field data layer with deterministic Check My Work rules.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Cognos-pdf-parser-workspace -->
## Cognos-pdf-parser-workspace

> ℹ️ **What this system does:** This private repo holds the AI/GSD planning context for the Linetec PDF Uploader project — the "where I left off" brain that lets work resume on any machine. It does not contain the application source code.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/smartsheet-attachment-checker -->
## smartsheet-attachment-checker

> ℹ️ **What this system does:** Automated GitHub Actions workflow that syncs the "Is Attachment Present?" checkbox column on a Smartsheet based on whether each row actually has an attachment.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/smartsheet-bug-tracker -->
## smartsheet-bug-tracker

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/econex -->
## econex

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/vite-react -->
## vite-react

> ℹ️ **What this system does:** This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Destiny-Application-2 -->
## Destiny-Application-2

> ℹ️ **What this system does:** A Node.js application that fetches build crafting data from the Bungie API for Destiny 2.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/ai-data-analyst -->
## AI-powered Data Analyst Agent using Claude Sonnet 4.5

> ℹ️ **What this system does:** AI-powered Data Analyst system using Claude Sonnet 4.5 that syncs Smartsheet data, indexes codebases, correlates code issues with data problems, and generates actionable reports.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/cognos-parser -->
## cognos-parser

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/linetec-uploader-api -->
## linetec-uploader-api

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/smartsheet-integration-docs -->
## smartsheet-integration-docs

> ℹ️ **What this system does:** &gt; Comprehensive documentation for all Smartsheet integration repositories

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Destiny-Application -->
## Destiny-Application

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/robofriends -->
## robofriends

> ℹ️ **What this system does:** This project was bootstrapped with Create React App.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Smartsheet-supabase-sync -->
## Smartsheet-supabase-sync

> ℹ️ **What this system does:** This repo contains a scheduled job that syncs Smartsheet sheets into Supabase every 5 minutes.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/upr-report-mapping -->
## upr-report-mapping

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Linetec-uploader-pdf-parser -->
## new repository

> ℹ️ **What this system does:** new repository

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/verbose-enigma -->
## verbose-enigma

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Combine-data-resiliency-promax -->
## Combine-data-resiliency-promax

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/lintec-sidebar-navigator -->
## lintec-sidebar-navigator

> ℹ️ **What this system does:** URL: https://lovable.dev/projects/d8e2b683-db36-447d-b3fa-4c89ea12a4cb

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Dynamic-Project-List-Schedule -->
## Dynamic-Project-List-Schedule

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/lintec-sidebar-navigator-59 -->
## lintec-sidebar-navigator-59

> ℹ️ **What this system does:** URL: https://lovable.dev/projects/d8e2b683-db36-447d-b3fa-4c89ea12a4cb

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/linetec-DSR-project -->
## linetec-DSR-project

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Linetec -->
## Linetec

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/background-generator -->
## background-generator

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/startup-of-my-own -->
## startup-of-my-own

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/startup.github.io -->
## startup.github.io

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/JFlo21.github.io -->
## JFlo21.github.io

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: Linetec-Services-LLC/runlog-linetec -->
## Workflow runlog that explains the workflows &amp; coding workflows and changes at a lower level for users to understand

> ℹ️ **What this system does:** Internal Docusaurus 3.x runbook + changelog for the Linetec Resiliency platform.

### 📋 Changelog — July 29, 2026

- 🔧 Behind-the-scenes maintenance to keep things running smoothly

<!-- /runbook-repo -->

<!-- runbook-repo: Linetec-Services-LLC/Todoist-gtd-ci-automations -->
## Todoist-gtd-ci-automations

> ℹ️ **What this system does:** Private, version-controlled execution infrastructure for Juan's guarded Todoist GTD system.

### 📋 Changelog — July 29, 2026

- • Enforce daily Inbox and Capture routing
- • Align cloud Focus health with guard v4
- • Sync guard-v4 filter and rollover controls
- • Host Todoist runtime in an isolated Supabase schema
- 🔧 Behind-the-scenes maintenance to keep things running smoothly
- 🔧 Behind-the-scenes maintenance to keep things running smoothly
- ✨ New capability: sync Todoist guard v4
- ✅ Problem fixed: enforce daily inbox capture routing ()

<!-- /runbook-repo -->

<!-- runbook-repo: Linetec-Services-LLC/demo-repository -->
## A code repository designed to show the best GitHub has to offer.

> ℹ️ **What this system does:** The repo includes an index.html file (so it can render a web page), two GitHub Actions workflows, and a CSS stylesheet dependency.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: Linetec-Services-LLC/Preplanned-Pricing-Sync -->
## "Daily sync: Supabase v&#95;wr&#95;pricing&#95;rollup → Smartsheet 'Master storms data' (1444139672489860)"

> ℹ️ **What this system does:** "Daily sync: Supabase v&#95;wr&#95;pricing&#95;rollup → Smartsheet 'Master storms data' (1444139672489860)"

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

