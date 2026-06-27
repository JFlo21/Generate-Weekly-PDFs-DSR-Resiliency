# Project Brief

> **Canonical brief:** [`memory-bank/projectbrief.md`](../memory-bank/projectbrief.md)
> plus the detailed project summary in [`/CLAUDE.md`](../CLAUDE.md). This stub
> satisfies the global Default-Startup step that reads `docs/PROJECT_BRIEF.md`.

**In one line:** a Python billing-automation pipeline (`generate_weekly_pdfs.py`)
that pulls billing data from Smartsheet, groups it by Work Request + week-ending,
generates styled Excel workbooks (`openpyxl`), and uploads them back to Smartsheet
as attachments — on a GitHub Actions cron. Two app surfaces (`portal/` Express,
`portal-v2/` React+Supabase) and a Docusaurus runbook (`website/`) sit alongside it.

For routing to everything else, see [`.claude/context-map.md`](../.claude/context-map.md).
