---
description: "Generate a release commit: run tests, summarize all changes, create commit message, and optionally push to master."
agent: "agent"
tools: [execute, search, read]
argument-hint: "Describe what changed in this release (or leave blank for auto-detect)"
---
Perform a release workflow for the Generate-Weekly-PDFs-DSR-Resiliency repository:

1. **Run tests** — Execute `python -m pytest tests/ -v` and confirm all pass. Stop if any fail.
2. **Detect changes** — Run `git diff --stat` and `git diff --name-only` to identify all modified files.
3. **Generate commit message** — Write a conventional commit message covering all changes:
   - Use the format: `feat: <summary>` or `fix: <summary>` as appropriate
   - List each changed file with a bullet describing what changed
   - Group by category (core engine, CI/CD, portal, docs)
4. **Stage and commit** — Run `git add -A` then `git commit` with the generated message.
5. **Confirm before push** — Ask the user to confirm before running `git push origin master`.

If the user provided a description of what changed, incorporate it into the commit message.
