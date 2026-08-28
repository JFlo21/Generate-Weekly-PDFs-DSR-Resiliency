---
sidebar_position: 99
title: What's New
---

# What's New

_Last updated: August 28, 2026 (updated automatically)_

This page explains what each of our tools does and its recent updates, in everyday language.

<!-- runbook-repo: JFlo21/Generate-Weekly-PDFs-DSR-Resiliency -->
## Weekly Billing Reports (DSR Resiliency)

> ℹ️ **What this system does:** Production billing engine that turns Smartsheet field data into polished, audit-ready weekly Excel reports — automatically.

### 📋 Changelog — August 28, 2026

- ✅ Problem fixed: header metadata from the hash's canonical row, not arrival order
- 🔧 Behind-the-scenes maintenance to keep things running smoothly
- 📄 Help guides updated: Learn section — operator and engineer guides; overview refreshed
- ✅ Problem fixed: total-order sort tiebreaker in calculate&#95;data&#95;hash
- 📄 Help guides updated: fix run&#95;ledger column name in flip confirmation SQL; record flip live
- ✅ Problem fixed: compare against the uploaded set; RUN&#95;MEMORY&#95;SHADOW&#95;MAX&#95;MINUTES 10 -&gt; 25
- ✅ Problem fixed: build pipeline&#95;memory client with SyncClientOptions (post-flip AttributeError)
- • ops: enable RUN&#95;MEMORY&#95;WRITE&#95;ENABLED in weekly run

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/linetec-inspector-manifest-generator -->
## linetec-inspector-manifest-generator

> ℹ️ **What this system does:** Python CLI that generates inspector-facing manifest Excel workbooks of ProMax claimed units — one Work Request at a time. It is a visual sibling of the weekly billing Excel (LineTec logo, red banner, summary blocks) restyled for review: no pricing, no Monday-Sunday day blocks, one continuous list natural-sorted by Point Number, with inspector-editable approval columns.

### 📋 Changelog — August 28, 2026

- ✅ Problem fixed: schedule lane never mapped MANIFEST&#95;WORKFLOW&#95;EVENT&#95;LIVE&#95;WRITE — Workflow Events were silently dry-run (+ ledger batch 2026-08-28b)
- ✨ New capability: audit heal transitions C1/C2/C3 + Assigned GF roster fill (+ ledger batch 2026-08-28)
- 📄 Help guides updated: ledger — PR merged, hop 1 green, post-merge next steps
- ✅ Problem fixed: hand-entered Requests rows reach the GF Decision Register — manual-row seed, GF handoff stamp, Destination=both GF-first (BUG-015/016)
- ✅ Problem fixed: BUG-013 priced-queue partition cache + claims-pending skip; BUG-014 hop-1 workflow name glob (first live day of Phase 31.1)
- 📄 Help guides updated: 2026-08-27 holdup-triage write-back packet + resume delta
- • Phase 31.1: control-plane orchestration hardening — schedule split, workflow&#95;run chain, wake debounce, bounded reads, Requests-as-source, stage transitions
- ✅ Problem fixed: normalize the register Manifest Version before the staging billers heal (BUG-010)

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/JFlo21 -->
## JFlo21

> ℹ️ **What this system does:** &gt; 💡 The snake animation above is generated automatically by a GitHub Action — it eats your contribution tiles&#33;

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/smartsheet-auditor -->
## AI powered repository that will look back and check on my smartsheet to analyze for duplications of work requests line items

> ℹ️ **What this system does:** Automated read-only auditor for Smartsheet data that detects duplicate rows, learns patterns over time using machine learning, and publishes a professional audit dashboard to GitHub Pages every week.

### 📋 Changelog — August 28, 2026

- • 📊 Audit: 2026-08-24T06:44:27Z

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/claudeos -->
## ClaudeOS portable global config (skills, agents, hooks, launchers, bootstrap)

> ℹ️ **What this system does:** ClaudeOS portable global config (skills, agents, hooks, launchers, bootstrap)

### 📋 Changelog — August 28, 2026

- 📄 Help guides updated: claude-mem installer EPERM inside live session; deps restored, worker back
- 📄 Help guides updated: record memory-swap commit 8d292c2 + archive push in project-state
- ✨ New capability: switch ClaudeOS continuity layer from .remember to claude-mem
- 📄 Help guides updated: reconcile fable5 effort policy to owner-saved xhigh; record 08-23 gsd VERSION fix; plugin autoUpdate churn
- ✅ Problem fixed: junction guard mirrors plugin-cache version into gsd-core/VERSION
- 📄 Help guides updated: close handoff items 1+3 (push done, dormant GSD npm global removed)
- 🔧 Behind-the-scenes maintenance to keep things running smoothly
- ✅ Problem fixed: junction guard also heals stale gsd-core .build.lock (upstream acquireLock has no stale reclaim)

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/remember-continuity -->
## ClaudeOS .remember continuity store (session handoffs; no secrets by policy)

> ℹ️ **What this system does:** ClaudeOS .remember continuity store (session handoffs; no secrets by policy)

### 📋 Changelog — August 28, 2026

- • sync: continuity from JFLODESKTOP

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/smartsheet-bot -->
## smartsheet-bot

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

### 📋 Changelog — August 28, 2026

- 🔧 Behind-the-scenes maintenance to keep things running smoothly

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/notion-runbook-worker -->
## Runbook Automation

> ℹ️ **What this system does:** A Notion Worker that turns GitHub activity into a professional, living operations runbook. It gives nontechnical readers a concise current-state summary while preserving source links and technical evidence for engineers.

_Running steadily — no meaningful changes were detected in this period._ ✅

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

### 📋 Changelog — August 28, 2026

- • Phase 3: canary publisher — allowlisted repository&#95;dispatch to Runlog
- ✅ Problem fixed: Fix Greptile issue on PR 30: contender must not release an active publish claim
- 🔧 Behind-the-scenes maintenance to keep things running smoothly
- • Merge pull request from Linetec-Services-LLC/copilot/pr-30-fix-greptile-issue
- 📄 Help guides updated: clarify contention fallthrough and redelivery test intent
- ✅ Problem fixed: never roll back publish claim after dispatch is accepted
- ✅ Problem fixed: contender never mutates another consumer's publish claim
- • Merge remote-tracking branch 'origin/phase3-canary-publisher' into copilot/pr-30-fix-greptile-issue

<!-- /runbook-repo -->

<!-- runbook-repo: Linetec-Services-LLC/Todoist-gtd-ci-automations -->
## Todoist-gtd-ci-automations

> ℹ️ **What this system does:** Private, version-controlled execution infrastructure for Juan's guarded Todoist GTD system.

_Running steadily — no meaningful changes were detected in this period._ ✅

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

