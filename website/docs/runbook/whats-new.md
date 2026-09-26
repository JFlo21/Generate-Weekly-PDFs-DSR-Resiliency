---
sidebar_position: 99
title: What's New
---

# What's New

_Last updated: September 26, 2026 (updated automatically)_

This page explains what each of our tools does and its recent updates, in everyday language.

<!-- runbook-repo: JFlo21/linetec-inspector-manifest-generator -->
## linetec-inspector-manifest-generator

> ℹ️ **What this system does:** Generates inspector-facing manifest Excel workbooks of ProMax claimed units for the AEP Texas Resiliency / LineTec program — one Work Request (WR) at a time — plus the review-loop variants (GF Review, priced GF, billers/DIF) that grew out of it.

### 📋 Changelog — September 26, 2026

- ✅ Problem fixed: Gen B post-approval mint keeps the GF approval mirror (BUG-125, WR 91783054)
- ✅ Problem fixed: addition-row Units Claimed mirror canonicalises Unicode whitespace (PR round 5)
- ✅ Problem fixed: null-safety and type-narrowing guards across 17 control&#95;plane modules
- ✅ Problem fixed: BUG-064 follow-ups -- phase-2 deadline, admission rotation, derived budget
- • Phase 35: Duplicate decisions -&gt; ProMax zero-out + Billing Dup Audit (gated OFF)
- ✅ Problem fixed: ';' note delimiter in Inspector/GF Approved Qty (WR 90855336, BUG-123)
- 🔧 Behind-the-scenes maintenance to keep things running smoothly
- 📄 Help guides updated: BUG-071 pre-tick dry-run evidence + BUG-053 live remediation record (no code change)

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/JFlo21 -->
## JFlo21

> ℹ️ **What this system does:** &gt; 💡 The snake animation above is generated automatically by a GitHub Action — it eats your contribution tiles&#33;

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Destiny-Application-2 -->
## Destiny-Application-2

> ℹ️ **What this system does:** A Node.js application that fetches build crafting data from the Bungie API for Destiny 2.

### 📋 Changelog — September 26, 2026

- 🚀 New version released: Destiny 2 Buildcraft Data data-2026-09-25
- • Transform Excel export into a Destiny 2 Buildcraft Compendium workbook
- • Merge pull request from JFlo21/copilot/transform-excel-export-again
- • Union seasonHash and current-artifact signals in season mod selection
- • Filter artifact/champion mods to current seasonal artifact plugs
- ✅ Problem fixed: Fix greptile issues: season-filter champion mods, pin action SHAs, slot-restricted weapon dropdowns
- • Update README with compendium tour, Build Planner guide, CLI flags
- • Part 5: CI workflow, ESLint/Prettier, node --test suites, release upload

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/smartsheet-bot -->
## smartsheet-bot

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

### 📋 Changelog — September 26, 2026

- 🔧 Behind-the-scenes maintenance to keep things running smoothly

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Generate-Weekly-PDFs-DSR-Resiliency -->
## Weekly Billing Reports (DSR Resiliency)

> ℹ️ **What this system does:** Production billing engine that turns Smartsheet field data into polished, audit-ready weekly Excel reports — automatically.

### 📋 Changelog — September 26, 2026

- 📄 Help guides updated: automated plain-language update from Notion Worker

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/supabase-smartsheet-promax-offload -->
## supabase-smartsheet-promax-offload

> ℹ️ **What this system does:** A Python script that automatically syncs data from multiple Smartsheet sheets to a Supabase database table. The script runs continuously and synchronizes data every 2 days (configurable).

### 📋 Changelog — September 26, 2026

- ✨ New capability: gated delete propagation for rows removed in Smartsheet (prune, default off)
- ✨ New capability: gated delete propagation for rows removed in Smartsheet (prune, default off) ()

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/claudeos -->
## ClaudeOS portable global config (skills, agents, hooks, launchers, bootstrap)

> ℹ️ **What this system does:** ClaudeOS portable global config (skills, agents, hooks, launchers, bootstrap)

### 📋 Changelog — September 26, 2026

- • config(routing): Opus 5.5 worker adoption -- agent pins, policy text, gsd-graph registration fix ledger
- 📄 Help guides updated: 2026-09-21 -- baseline pushed on approval; effort setting resolved to high; dispatch-path findings fixed on PR
- 📄 Help guides updated: record the local commit hashes of the 2026-09-21 baseline
- 🔧 Behind-the-scenes maintenance to keep things running smoothly
- ✅ Problem fixed: drop the false "parent session/runtime cache" claim; tighten verifier verdicts; packet at the dispatch point
- 📄 Help guides updated: instruction-maintenance contract, integrity check, LSP-first routing, lessons
- ✨ New capability: precompact-handoff v1.1.2 and continuity-on-compact v1.2.1 with tests
- ✨ New capability: edit-target guard, bulk-edit guard, launcher and tests (baseline)

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/smartsheet-auditor -->
## AI powered repository that will look back and check on my smartsheet to analyze for duplications of work requests line items

> ℹ️ **What this system does:** Automated read-only auditor for Smartsheet data that detects duplicate rows, learns patterns over time using machine learning, and publishes a professional audit dashboard to GitHub Pages every week.

### 📋 Changelog — September 26, 2026

- • 📊 Audit: 2026-09-21T07:07:12Z

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Preplanned-Pricing-Sync -->
## "Daily sync: Supabase v&#95;wr&#95;pricing&#95;rollup → Smartsheet 'Master storms data' (1444139672489860)"

> ℹ️ **What this system does:** Daily sync from Supabase pricing.vwrpricingrollup → Smartsheet sheet 1444139672489860 ("Master storms data").

### 📋 Changelog — September 26, 2026

- • Add read-only kpi schema; ProMax authoritative for claimed units
- • Merge pull request from JFlo21/claude/project-thread-e2lw4y

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/notion-runbook-worker -->
## Runbook Automation

> ℹ️ **What this system does:** A Notion Worker that turns GitHub activity into a professional, living operations runbook. It gives nontechnical readers a concise current-state summary while preserving source links and technical evidence for engineers.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/remember-continuity -->
## ClaudeOS .remember continuity store (session handoffs; no secrets by policy)

> ℹ️ **What this system does:** ClaudeOS .remember continuity store (session handoffs; no secrets by policy)

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

### 📋 Changelog — September 26, 2026

- 🔧 Behind-the-scenes maintenance to keep things running smoothly

<!-- /runbook-repo -->

<!-- runbook-repo: Linetec-Services-LLC/bookish-parakeet -->
## bookish-parakeet

> ℹ️ **What this system does:** This template repository makes it easy for enterprise owners to get started with and establish settings for their agents by providing: The basic file structure necessary for custom agents An example agent profile in the agents directory An empty managed-settings.json file, which defines governance and extensibility settings in clients

_Running steadily — no meaningful changes were detected in this period._ ✅

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

