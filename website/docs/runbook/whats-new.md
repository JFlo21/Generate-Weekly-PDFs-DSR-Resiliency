---
sidebar_position: 99
title: What's New
---

# What's New

_Last updated: September 18, 2026 (updated automatically)_

This page explains what each of our tools does and its recent updates, in everyday language.

<!-- runbook-repo: JFlo21/linetec-inspector-manifest-generator -->
## linetec-inspector-manifest-generator

> ℹ️ **What this system does:** Generates inspector-facing manifest Excel workbooks of ProMax claimed units for the AEP Texas Resiliency / LineTec program — one Work Request (WR) at a time — plus the review-loop variants (GF Review, priced GF, billers/DIF) that grew out of it.

### 📋 Changelog — September 17, 2026

- ✅ Problem fixed: BUG-055 -- never act on superseded Decision Register rows (+ BUG-056 registered)
- 📄 Help guides updated: 2026-09-16 evening -- PR merged, round 1, BUG-053/, re-merge + test port
- ✅ Problem fixed: BUG-053 -- the suite fails closed on any live Supabase client (scrub APP&#95;SUPABASE&#95;&#42;/dispatch&#95;claims.ENV&#95;&#42;, raise on dispatch&#95;claims.create&#95;client)
- ✅ Problem fixed: BUG-052 -- inspector-return content classifier compares against the system's own delivered copy (Requests-row workbook, then oldest native version)
- ✅ Problem fixed: ADC-2 -- As-Designed columns interleaved beside their claimed siblings, top-anchored summary block, row-fill extension
- 📄 Help guides updated: post-merge alignment (CLAUDE.md, docs/ai, brief, context-map, .lattice, ledgers) + pause-work handoff
- ✅ Problem fixed: ProMax-change detection baseline + native Smartsheet attachment versioning
- • Phase 34: AEP Offer Queue (Jessica) + Gen C-AEP + Offer Report (8/8 plans; gates off)

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/JFlo21 -->
## JFlo21

> ℹ️ **What this system does:** &gt; 💡 The snake animation above is generated automatically by a GitHub Action — it eats your contribution tiles&#33;

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Generate-Weekly-PDFs-DSR-Resiliency -->
## Weekly Billing Reports (DSR Resiliency)

> ℹ️ **What this system does:** Production billing engine that turns Smartsheet field data into polished, audit-ready weekly Excel reports — automatically.

### 📋 Changelog — September 17, 2026

- ✅ Problem fixed: USER-variant groups dropped from incremental candidate set
- 📄 Help guides updated: state pointers after PR merge
- ✅ Problem fixed: breaker half-open on probe success; keep&#95;historical deferred (D-14-FOLLOWUPS)
- 📄 Help guides updated: post-merge write-back for PR
- 📄 Help guides updated: final state pointers after PR
- 📄 Help guides updated: close Phase 12 — 12-06 Task 4, D-12-E, verify-work
- 📄 Help guides updated: post-merge write-back for PR
- ✅ Problem fixed: close code review CR-01/CR-02/WR-01..03 (#HLP-06)

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/smartsheet-auditor -->
## AI powered repository that will look back and check on my smartsheet to analyze for duplications of work requests line items

> ℹ️ **What this system does:** Automated read-only auditor for Smartsheet data that detects duplicate rows, learns patterns over time using machine learning, and publishes a professional audit dashboard to GitHub Pages every week.

### 📋 Changelog — September 17, 2026

- • 📊 Audit: 2026-09-14T07:07:48Z

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/claudeos -->
## ClaudeOS portable global config (skills, agents, hooks, launchers, bootstrap)

> ℹ️ **What this system does:** ClaudeOS portable global config (skills, agents, hooks, launchers, bootstrap)

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/remember-continuity -->
## ClaudeOS .remember continuity store (session handoffs; no secrets by policy)

> ℹ️ **What this system does:** ClaudeOS .remember continuity store (session handoffs; no secrets by policy)

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/smartsheet-bot -->
## smartsheet-bot

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/notion-runbook-worker -->
## Runbook Automation

> ℹ️ **What this system does:** A Notion Worker that turns GitHub activity into a professional, living operations runbook. It gives nontechnical readers a concise current-state summary while preserving source links and technical evidence for engineers.

### 📋 Changelog — September 18, 2026

- • Retry transient Notion failures and isolate per-system errors in the runbook publish path
- • Merge pull request from JFlo21/copilot/inspect-repository-issues
- ✅ Problem fixed: retry gateway&#95;timeout and prove committed writes survive timed-out responses
- 🔧 Behind-the-scenes maintenance to keep things running smoothly
- ✅ Problem fixed: retry transient Notion failures and isolate per-system publish errors

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Cognos-pdf-parser -->
## Parser that will offload grid format information from work request completed packets

> ℹ️ **What this system does:** Professional PDF/Excel Material Extractor for Linetec Services with web-based interface and desktop GUI.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/promax-field-log -->
## promax-field-log

> ℹ️ **What this system does:** Read-only-by-default field data layer with deterministic Check My Work rules.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/generate-job-numbers -->
## Job Number Generator

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/sync-master-schedule -->
## Master Schedule Sync

> ℹ️ **What this system does:** Automatically synchronize attachments between two Smartsheet sheets based on matching column criteria. Runs daily at 5:00 AM UTC via GitHub Actions.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/master-to-sibling-smartsheet-function -->
## Master-to-Sibling Sheet Sync

> ℹ️ **What this system does:** Automated Smartsheet synchronization system supporting multi-source snapshot tracking with historical backfill capabilities.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/lock_sheet_rows -->
## Weekly Sheet Locking

> ℹ️ **What this system does:** Locks sheet rows on smartsheet after each week ending date has been reached.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/smartsheet-sync-locators -->
## Locator Spreadsheet Sync

> ℹ️ **What this system does:** This code automatically synchronizes the locators spreadsheets with the spreadsheets on smartsheet for seemless integration

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Resiliency-pdf-restructure-ug-work -->
## Resiliency-pdf-restructure-ug-work

> ℹ️ **What this system does:** A comprehensive Python web application that processes PDF point material sheets to validate, filter, and redact Compatible Unit (CU) codes against a valid Underground (UG) product catalog.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Preplanned-Pricing-Sync -->
## "Daily sync: Supabase v&#95;wr&#95;pricing&#95;rollup → Smartsheet 'Master storms data' (1444139672489860)"

> ℹ️ **What this system does:** Daily sync from Supabase pricing.vwrpricingrollup → Smartsheet sheet 1444139672489860 ("Master storms data").

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/morpheus-second-brain -->
## Morpheus — LLM-maintained wiki second brain (shared across Hermes local+cloud and Claude Code)

> ℹ️ **What this system does:** Morpheus — LLM-maintained wiki second brain (shared across Hermes local+cloud and Claude Code)

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

### 📋 Changelog — September 17, 2026

- 🔧 Behind-the-scenes maintenance to keep things running smoothly

<!-- /runbook-repo -->

<!-- runbook-repo: Linetec-Services-LLC/Todoist-gtd-ci-automations -->
## Todoist-gtd-ci-automations

> ℹ️ **What this system does:** Private, version-controlled execution infrastructure for Juan's guarded Todoist GTD system.

### 📋 Changelog — September 17, 2026

- • Rebind control-source snapshot hash to current main
- • Rebind control-source snapshot hash to current main ()

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
