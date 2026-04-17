---
id: intro
title: Welcome
slug: /
sidebar_position: 1
---

# Weekly PDFs Runbook

This is the **living runbook** for the Smartsheet Weekly PDF Generator. It
documents what every moving part of the repo does and — more importantly —
records a changelog entry for every merge into `master` so operators can trace
"what did my code do after we last shipped?" without digging through git.

## What you'll find here

- **Runbook** — hand-maintained pages describing the Python entry points,
  GitHub Actions workflows, the Express/React portals, and operational
  procedures.
- **Change Log** — one auto-generated blog post per merge to `master`,
  summarizing the files that changed (grouped by area) plus the commit
  subjects that produced them.
- **Reference** — environment variables, secrets, and a short note on how
  the site itself is updated.

## How to read this runbook

1. Start with [Overview](./runbook/overview.md) if you're new — it explains
   what the system does end-to-end.
2. Drill into [Python modules](./runbook/python-modules.md) or
   [Workflows](./runbook/workflows.md) to understand a specific component.
3. Open the [Change Log](/blog) to see what landed recently and why.

:::tip
Every merge to `master` triggers `.github/workflows/docs-changelog.yml`, which
writes a new blog post under `website/blog/` and commits it. The site is then
rebuilt and redeployed by Vercel.
:::
