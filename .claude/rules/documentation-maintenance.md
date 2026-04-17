# Documentation Maintenance Rules (Docusaurus Runbook)

Living documentation lives in `website/` (Docusaurus). These rules
govern how the runbook and its changelog are updated when code
changes ship.

## 1. Contextual Changelog Updates

**Rule.** Changelog entries must **synthesize** the *what*, *why*,
and *how* of a change in narrative form. They are **not** a dump of
commit subjects.

- For every merged change that affects operator-visible behavior
  (new scripts, new env vars, schedule changes, data contract
  changes, new guardrails), write a changelog entry that answers:
  - **What** changed? (feature, fix, refactor, schedule, contract)
  - **Why** did it change? (business need, bug, perf, compliance)
  - **How** does it affect operators? (new command, new env var,
    new failure mode, manual step required during rollout)
- Aggregate related commits into a single coherent entry — do **not**
  paste individual commit messages.
- Reference the tracking issue / PR number at the end of the entry
  so engineers can trace back to the full diff.
- Keep the tone instructional and in present tense. Write for the
  on-call engineer reading at 2 AM.
- The `docs-changelog.yml` GitHub Action appends a runbook changelog
  line on every merge to `master`. Treat that automated line as a
  *stub* — expand it into a proper synthesized entry before the next
  release.

## 2. Runbook Refactoring

**Rule.** When updating the runbook, **rewrite** affected pages; do
not append stale paragraphs that duplicate or contradict existing
content.

- Remove or merge outdated paragraphs in the same commit that adds
  new content. The runbook must stay **lean and instructional**.
- Organize pages around operator workflows (e.g. "Rerun a failed
  weekly job", "Force full regeneration", "Investigate a price
  anomaly"), not around code modules.
- **Hybrid ecosystem clarity.** Explicitly call out which tier of
  the stack handles each workflow:
  - **Python** (`generate_weekly_pdfs.py`, sibling scripts) — owns
    high-volume, batch-driven Smartsheet ⇄ Supabase synchronization
    and Excel generation. Runs on GitHub Actions cron.
  - **n8n** — owns **low-volume, event-driven** Notion syncs only.
    Reserved for AI orchestration and sporadic webhook work to
    avoid task-quota exhaustion.
  - Every runbook page that involves automation must state which
    tier owns the flow so operators never try to move a Python
    workload into n8n (or vice-versa).
- Validate docs locally before pushing:

  ```bash
  cd website
  npm run typecheck
  npm run build
  ```

- Do not introduce broken cross-links. If you rename or delete a
  page, update every referring page in the same commit.
