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

- **Learn** — two guided reads: [for operators](./learn/for-operators.md)
  (what the automation does, how to read a file, how to get a unit into the
  right Excel, when to ask for a manual run) and
  [for engineers](./learn/for-engineers.md) (the code map, how to diagnose
  a run, and how to change the pipeline without breaking billing).
- **Runbook** — hand-maintained pages describing the Python entry points,
  GitHub Actions workflows, the `portal-v2` web app, and operational
  procedures.
- **Change Log** — one auto-generated blog post per merge to `master`,
  summarizing the files that changed (grouped by area) plus the commit
  subjects that produced them.
- **Reference** — environment variables, secrets, and a short note on how
  the site itself is updated.

## How to read this runbook

1. New and non-technical? Read [For operators](./learn/for-operators.md).
   New and technical? Read [For engineers](./learn/for-engineers.md), then
   [Overview](./runbook/overview.md) for the system diagram.
2. Drill into [Python modules](./runbook/python-modules.md) or
   [Workflows](./runbook/workflows.md) to understand a specific component.
3. Open the [Change Log](/blog) to see what landed recently and why.

:::tip
Every merge to `master` triggers `.github/workflows/docs-changelog.yml`, which
writes a new blog post under `website/blog/` and commits it. The site is then
rebuilt and redeployed by Vercel.
:::
