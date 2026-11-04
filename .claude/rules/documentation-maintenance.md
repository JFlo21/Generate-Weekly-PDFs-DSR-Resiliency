---
paths:
  - "website/**"
  - ".github/workflows/docs-changelog.yml"
---
# Documentation Maintenance Rules (Docusaurus Runbook)

Living documentation lives in `website/` (Docusaurus). These rules govern how the
runbook and its changelog are updated when code changes ship. This file is path-scoped;
the always-loaded reminder that every operator-visible change needs a changelog entry,
even from a code-only session, is `CLAUDE.md` § Conventions.

## 1. Contextual Changelog Updates

**Rule.** Changelog entries **synthesize** the *what*, *why* and *how* of a change in
narrative form. They are **not** a dump of commit subjects.

- For every merged change that affects operator-visible behavior (new scripts, new env
  vars, schedule changes, data-contract changes, new guardrails), write an entry that
  answers: **What** changed (feature, fix, refactor, schedule, contract)? **Why**
  (business need, bug, perf, compliance)? **How** does it affect operators (new command,
  new env var, new failure mode, manual step required during rollout)?
- Aggregate related commits into a single coherent entry — never paste commit messages.
- End the entry with the tracking issue / PR number so engineers can trace the full diff.
- Instructional tone, present tense. Write for the on-call engineer reading at 2 AM.
- The `docs-changelog.yml` GitHub Action appends a runbook changelog line on every merge
  to `master`. Treat that automated line as a *stub* — expand it into a proper
  synthesized entry before the next release.

## 2. Runbook Refactoring

**Rule.** When updating the runbook, **rewrite** affected pages; never append stale
paragraphs that duplicate or contradict existing content.

- Remove or merge outdated paragraphs in the same commit that adds new content. The
  runbook stays **lean and instructional**.
- Organize pages around operator workflows ("Rerun a failed weekly job", "Force full
  regeneration", "Investigate a price anomaly"), not around code modules.
- **Hybrid ecosystem clarity.** Every runbook page that involves automation states which
  component owns the flow, so operators route changes and incident response correctly:
  - **Python billing pipeline** (`generate_weekly_pdfs.py`, sibling scripts) — batch
    Smartsheet processing: row filtering, WR grouping, Excel generation, attachment
    upload; runs on the GitHub Actions cron.
  - **Notion sync** (`scripts/notion_sync.py` via GitHub Actions) — Notion synchronization.
  - **Supabase web app tier** (`portal-v2/`) — application backend/data layer, separate
    from the Python billing pipeline.
- Validate docs locally before pushing: `cd website && npm run typecheck && npm run build`.
- No broken cross-links: renaming or deleting a page updates every referring page in the
  same commit.
