---
sidebar_position: 99
title: What's New
---

# What's New

_Last updated: November 23, 2026 (updated automatically)_

This page explains what each of our tools does and its recent updates, in everyday language.

<!-- runbook-repo: JFlo21/linetec-inspector-manifest-generator -->
## linetec-inspector-manifest-generator

> ℹ️ **What this system does:** Generates inspector-facing manifest Excel workbooks of ProMax claimed units for the AEP Texas Resiliency / LineTec program — one Work Request (WR) at a time — plus the review-loop variants (GF Review, priced GF, billers/DIF) that grew out of it.

### 📋 Changelog — November 23, 2026

- ✨ New capability: add the default-off switch MANIFEST&#95;WEB&#95;PRICED&#95;PUBLISH&#95;LIVE&#95;WRITE (BUG-234)
- ✅ Problem fixed: refuse a retry after the completion date changed, and a SCOPE&#95;NA id beside a real scope (BUG-234)
- ✅ Problem fixed: correction form keeps its answer during a slow upload; drop prompt wording (BUG-235)
- ✅ Problem fixed: a web priced build is the WR's next priced version (BUG-234)
- ✨ New capability: an admin can correct a GF return on a finished GF review (BUG-235)
- ✅ Problem fixed: a failed GF Return on My Activity links to the Return page's GF lane (BUG-236)
- ✅ Problem fixed: Billers/DIF and AEP main-grid header reads "As Designed Description" (BUG-232 follow-up)
- ✅ Problem fixed: an expired inspector-assignment wait tells its requester once (BUG-230 follow-up)

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/JFlo21 -->
## JFlo21

> ℹ️ **What this system does:** &gt; 💡 The snake animation above is generated automatically by a GitHub Action — it eats your contribution tiles&#33;

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Generate-Weekly-PDFs-DSR-Resiliency -->
## Weekly Billing Reports (DSR Resiliency)

> ℹ️ **What this system does:** Production billing engine that turns Smartsheet field data into polished, audit-ready weekly Excel reports — automatically.

### 📋 Changelog — November 23, 2026

- 📄 Help guides updated: automated plain-language update from Notion Worker

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Preplanned-Pricing-Sync -->
## "Daily sync: Supabase v&#95;wr&#95;pricing&#95;rollup → Smartsheet 'Master storms data' (1444139672489860)"

> ℹ️ **What this system does:** Daily sync from Supabase pricing.vwrpricingrollup → Smartsheet sheet 1444139672489860 ("Master storms data").

### 📋 Changelog — November 23, 2026

- ✨ New capability: price planned + actual totals from the Corpus CU List (proposed, not deployed)
- 📄 Help guides updated: Claude Code context layer + verified implementation truth
- • Merge pull request from JFlo21/fix/corpus-cu-rate-rule
- ✅ Problem fixed: extension check skips the price comparison for unpriced sub rows
- 📄 Help guides updated: record the PR review-fix apply to Supabase
- ✅ Problem fixed: PR review findings (blank AEP date, partial-edition extension, paging snapshot, CU completeness)
- 📄 Help guides updated: record the Corpus rule deploy, dry-run results and the API timeout
- ✨ New capability: withheld-share guard in both rollup RPCs; record decisions 1-5 as approved

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Cognos-pdf-parser -->
## Parser that will offload grid format information from work request completed packets

> ℹ️ **What this system does:** Professional PDF/Excel Material Extractor for Linetec Services with web-based interface and desktop GUI.

### 📋 Changelog — November 23, 2026

- ✨ New capability: only the owner reopens an account the owner closed (owner&#95;closed)
- ✨ New capability: account administration API and store writes (access pull request 3b)
- ✨ New capability: backend page gates (access pull request 3a)
- ✅ Problem fixed: Linetec saved stores the rows saved, not the last page of 100
- ✅ Problem fixed: a nav that does not fit takes its own header row
- ✅ Problem fixed: sign-in and sign-out drop session-check replies that started earlier
- ✨ New capability: frontend access layer (access pull request 2 of 5)
- 📄 Help guides updated: add the docs/ai implementation-truth layer, decisions log and project brief

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/vercel-ai-chatbot-with-supabase -->
## vercel-ai-chatbot-with-supabase

> ℹ️ **What this system does:** - Next.js App Router - React Server Components (RSCs), Suspense, and Server Actions - Vercel AI SDK for streaming chat UI - Support for OpenAI (default), Anthropic, Hugging Face, or custom AI chat models and/or LangChain - Edge runtime-ready - shadcn/ui - Styling with Tailwind CSS - Radix UI for headless component primitives - Icons from Phosphor Icons - Chat History with Supabase Postgres DB - Supabase Auth for authentication

### 📋 Changelog — November 23, 2026

- • Initial commit

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/linetec-uploader-api -->
## linetec-uploader-api

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

### 📋 Changelog — November 23, 2026

- ✅ Problem fixed: report every inserted row, not the last page of 100
- • Merge pull request from JFlo21/fix/upload-count-all-pages
- ✅ Problem fixed: report every inserted row, not the last page of 100

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/sync-master-schedule -->
## Master Schedule Sync

> ℹ️ **What this system does:** Copies file attachments from Project List rows to the matching, already-existing rows of two target sheets, matched by Work Request #: all files to the Master Schedule, and PDF files only to Project List - Blank Copy. Runs daily at 5:00 AM UTC via GitHub Actions.

### 📋 Changelog — November 23, 2026

- • Attachment sync: keep the Master Schedule sync and add a PDF-only sync to Project List - Blank Copy
- • Attachment sync: keep the Master Schedule sync and add a PDF-only sync to Project List - Blank Copy ()

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/smartsheet-auditor -->
## AI powered repository that will look back and check on my smartsheet to analyze for duplications of work requests line items

> ℹ️ **What this system does:** Automated read-only auditor for Smartsheet data that detects duplicate rows, learns patterns over time using machine learning, and publishes a professional audit dashboard to GitHub Pages every week.

### 📋 Changelog — November 23, 2026

- • 📊 Audit: 2026-11-16T06:58:53Z

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/claudeos -->
## ClaudeOS portable global config (skills, agents, hooks, launchers, bootstrap)

> ℹ️ **What this system does:** ClaudeOS portable global config (skills, agents, hooks, launchers, bootstrap)

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/docs -->
## docs

> ℹ️ **What this system does:** Use the starter kit to get your docs deployed and ready to customize.

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

<!-- runbook-repo: JFlo21/Smartsheet-configurator-manifest -->
## Smartsheet-configurator-manifest

> ℹ️ **What this system does:** This system does not have a published overview yet. Use the repository link for source documentation.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/Destiny-Application-2 -->
## Destiny-Application-2

> ℹ️ **What this system does:** A Node.js application that fetches build crafting data from the Bungie API for Destiny 2.

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

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: JFlo21/remember-continuity -->
## ClaudeOS .remember continuity store (session handoffs; no secrets by policy)

> ℹ️ **What this system does:** ClaudeOS .remember continuity store (session handoffs; no secrets by policy)

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

### 📋 Changelog — November 23, 2026

- 🔧 Behind-the-scenes maintenance to keep things running smoothly

<!-- /runbook-repo -->

<!-- runbook-repo: Linetec-Services-LLC/Todoist-gtd-ci-automations -->
## Todoist-gtd-ci-automations

> ℹ️ **What this system does:** Private, version-controlled execution infrastructure for Juan's guarded Todoist GTD system.

_Running steadily — no meaningful changes were detected in this period._ ✅

<!-- /runbook-repo -->

<!-- runbook-repo: Linetec-Services-LLC/bookish-parakeet -->
## bookish-parakeet

> ℹ️ **What this system does:** This template repository makes it easy for enterprise owners to get started with and establish settings for their agents by providing: The basic file structure necessary for custom agents An example agent profile in the agents directory An empty managed-settings.json file, which defines governance and extensibility settings in clients

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

