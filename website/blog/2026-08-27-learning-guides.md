---
slug: learning-guides
title: "New Learn section: guides for operators and for engineers; overview refreshed"
authors: [runbook-bot]
tags: [docs, project]
date: 2026-08-27T23:30:00+00:00
---

**Component:** this Docusaurus runbook (`website/`). **Change type:**
documentation only — no pipeline, workflow or schema change.

<!-- truncate -->

## What changed

- A new **Learn** section (sidebar + navbar) with two guided reads:
  - **For operators (non-technical)** — what the automation does in one
    paragraph and one diagram; when it runs; where the files are and how to
    read a file name; the layout of the *Work Report* sheet; why you don't
    "build" an Excel file but feed it (which Smartsheet fields must be
    filled for a unit to appear, and in which week's file); a table of the
    common "my unit is missing / in the wrong file" causes; how to ask for
    a manual run and which inputs to use; a what-to-do-when-it-looks-wrong
    checklist; a glossary.
  - **For engineers** — the code map (every `pipeline/` module with size,
    responsibility and "touch it when…"); the anatomy of a run with the
    log markers to grep for; how to diagnose with `gh run view`, the
    Supabase `pipeline_memory` / `billing_audit` queries, and a local
    `SKIP_UPLOAD=true` reproduction; the never-do table with the incident
    behind each rule; the change workflow (branch → test first → full suite
    → known-good validation → three-section PR → ledger + changelog); a
    "where to make common changes" table; the run-memory layer in two
    minutes.
- **System overview** rewritten: the diagram now shows the Supabase
  `billing_audit` and `pipeline_memory` layers and the PPP second target;
  the removed Express portal is gone from the table; the data contract
  states the regeneration rule.
- **Welcome** page points newcomers to the right guide.

## Why

Today's work (PRs #355, #356, #358, #359) made the run-memory layer real in
production and surfaced several rules that only existed in the living
ledger and in PR threads. Operators had no page that explained, in their
terms, why a unit lands where it does or how to get a file rebuilt, and
engineers had no single entry point that says where to look and what must
never be changed without validation.

## What operators will see

Nothing changes in the files or the schedule. The site gains a **Learn**
entry in the navigation; the operator guide is the page to send to anyone
who asks "where is my Excel?" or "why is this unit missing?".
