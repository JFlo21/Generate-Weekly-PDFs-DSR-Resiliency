---
slug: docusaurus-3-10-faster-upgrade-and-build-guardrail
title: "feat(docs): Docusaurus 3.10.2 + Faster upgrade, docs build guardrail (#296)"
authors: [runbook-bot]
tags: [docs, workflows, meta]
---

**Branch:** `master` &middot; **PR:** [#296](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/pull/296)

The runbook's build tooling and deployment pipeline were upgraded and
hardened. This entry is hand-authored because the change alters
operator-visible behavior beyond what the auto-generated file list can
convey.

<!-- truncate -->

## What changed

- **Docusaurus upgraded `3.7` → `3.10.2`** with the
  [`@docusaurus/faster`](https://docusaurus.io/blog/releases/3.6#docusaurus-faster)
  Rspack/SWC bundler enabled (`future.faster: true`) and the v4 future
  flags opted in individually. Site builds are faster; output and URLs
  are unchanged.
- **New CI guardrail:** `.github/workflows/docs-site-build.yml`
  typechecks and builds the site on every PR that touches `website/`,
  mirroring the Vercel production build.
- **Three runbook pages restored to navigation** — *Auth & RBAC
  bootstrap*, *Vercel deployment*, and *What's New* existed but were
  missing from `sidebars.ts` and unreachable from the sidebar.
- **[How this site updates](/docs/reference/how-this-site-updates)
  rewritten** — it still described the retired PR-based changelog flow;
  it now documents the actual direct-commit flow and includes a Vercel
  wiring reference table (root directory, production branch, framework
  preset, `trailingSlash` sync rule).

## Why

Vercel was previously the **only** place the runbook was built — a bad
config, sidebar entry, or MDX error could merge to `master` unnoticed
and silently stop the site from updating. The new workflow catches that
on the PR instead. The version bump keeps the site on the current
Docusaurus line so future upgrades stay painless.

## Operator impact

- PRs touching `website/**` now require the **Docs Site Build** check
  to pass before merge.
- Nothing changes for the change-log automation: entries are still
  committed directly to `master` by `docs-changelog.yml`, and Vercel
  still redeploys on every push.
- **Guardrail (recorded in the Living Ledger):** MDX v1 compat
  (`mdx1CompatDisabledByDefault: false`) must stay enabled — the
  change-log generator and the Notion runbook worker continuously emit
  HTML comments that MDX rejects once compat is disabled.
