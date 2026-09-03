# Project Brief — Generate-Weekly-PDFs-DSR-Resiliency

_Refreshed 2026-09-02 (align-instruction-files run 1). Supersedes the retired
`memory-bank/projectbrief.md` / `productContext.md`; those are now pointer stubs._

## Why this repo exists

LineTec Services' Resiliency division performs utility construction work tracked in
Smartsheet. Each crew logs daily status report (DSR) rows: constructable units completed,
billing data, crew and foreman. Billing needs weekly Excel summaries per Work Request (WR)
for reconciliation, and producing them by hand was slow and error-prone. This repo automates
that on a GitHub Actions schedule.

## What it does (one line)

Smartsheet API → validate 13+ ProMax source sheets → fetch ~550 rows in parallel → group by
WR + week-ending + variant (primary / helper / VAC crew) + foreman/dept/job → skip unchanged
groups via a Supabase-backed content hash → generate styled Excel (`openpyxl`) → upload each
workbook back to the target Smartsheet row, replacing the prior attachment.

## Problems it solves

- Manual weekly billing summaries (now fully automated, roughly every 2 hours on weekdays).
- Redundant regeneration (hash-based change detection; only changed groups are rebuilt).
- Multi-crew attribution (helper crews and VAC crews get their own files; claim-time
  ownership is frozen per row so a mid-week foreman switch never overwrites the prior file).
- Contract-correct pricing (subcontractor vs original-contract rate tables).

## Surfaces

| Surface | Path | Owner of |
|---|---|---|
| Python billing engine (production) | `generate_weekly_pdfs.py` → `pipeline/`, `billing_audit/`, `pipeline_memory/` | The whole Smartsheet → Excel → Smartsheet flow |
| React dashboard | `portal-v2/` (Vite + TS + Supabase, Vercel) | Browsing published artifacts and run status |
| Operator runbook | `website/` (Docusaurus, Vercel) | How-to pages for on-call engineers |

Legacy Express `portal/` was removed 2026-06-02 (03153c3).

## Stakeholders

- **Repo owner** — sole approver for production, billing, attribution, Smartsheet-write and
  Supabase schema changes (`~/.claude/rules/production-guardrails.md`).
- **Review / QA support** — validates outputs and tracks issues; never holds production-change
  authority.
- **Resiliency foremen and billing** — consumers of the weekly workbooks attached in Smartsheet.

## Where to go next

`.claude/context-map.md` (read order) → `.claude/project-state.md` (status) → `docs/ai/`
(implementation truth) → `memory-bank/living-ledger.md` (dated history; grep, never load whole).
