---
id: how-this-site-updates
title: How this site updates
sidebar_position: 2
---

# How this site updates

This runbook is intentionally low-ceremony. Two moving parts keep it fresh.

## 1. Automatic change log entries

On every push to `master`, `.github/workflows/docs-changelog.yml` runs
`scripts/generate_runbook_entry.py`. That script:

1. Compares `${{ github.event.before }}` with `${{ github.sha }}`. On a
   manual `workflow_dispatch` (where `before` is empty), it falls back
   to diffing the HEAD commit against its first parent so merge
   commits are enumerated correctly.
2. Buckets the changed files into **Workflows & CI**, **GitHub config**,
   **Python — entry points / diagnostics / scripts/**, **Tests**,
   **Portal (Express)**, **Portal v2 (React)**, **Docs site**,
   **Project docs**, **Configuration**, **Data files**, and **Other**.
3. Lists commits in the push range with short SHA and subject.
4. Writes a Markdown post at
   `website/blog/YYYY-MM-DD-<short-sha>-<slug>.md` with frontmatter
   (title, authors, tags).

The workflow then opens a **pull request** via
[`peter-evans/create-pull-request`](https://github.com/peter-evans/create-pull-request)
on a branch named `runbook/log-<short-sha>`, scoped to only paths under
`website/blog/`. Reviewers merge it — that merge is the push Vercel picks
up to rebuild the Docusaurus site.

:::info Why a PR instead of a direct push?
Branch protection on `master` (required reviews, status checks, linear
history) would block a direct push from `github-actions[bot]`. Opening a
PR keeps the workflow compatible with any protection rules and lets a
human skim the entry before it ships.

The PR's own commit is tagged `[skip ci]`, and GitHub won't re-trigger
`push`/`pull_request` workflows from events authored by the default
`GITHUB_TOKEN`, so the act of opening the PR is safe. When the PR is
eventually merged into `master`, however, the resulting commit is a
normal human-authored push — `notion-sync`, `snyk-security`, and
`codecov` run as they would for any other merge, and this workflow may
generate a follow-up entry. The generator's own guards (skip markers
and the "only `website/blog/`" short-circuit) keep that from turning
into a feedback loop.
:::

## 2. Manual runbook edits

The `website/docs/` tree is hand-authored. When you add or change a
behavior that future operators need to know about, edit the relevant
page there — the "Edit this page" link in the footer will take you
straight to the file on GitHub.

## Why Docusaurus?

- MDX + Markdown — low friction for engineers.
- First-class blog feature — the change log is just posts.
- Ships with a decent default theme, search plugins, and
  `showLastUpdateTime` so pages display when they were last touched.
- Deployable anywhere static (Vercel in our case; `vercel.json` in
  `website/` drives the build).

## Local preview

```bash
cd website
npm install
npm run start
```

Then visit [http://localhost:3000](http://localhost:3000).

## Deployment target and base URL

The site now supports both Vercel and GitHub Pages without changing source:

- **Vercel (default):** `DOCS_DEPLOY_TARGET` unset, resulting in
  `url=https://weekly-pdfs-runbook.vercel.app` and `baseUrl=/`.
- **GitHub Pages:** set `DOCS_DEPLOY_TARGET=github-pages`, resulting in
  `url=https://jflo21.github.io` and
  `baseUrl=/generate-weekly-pdfs-dsr-resiliency/`.

If the homepage ever loads the Docusaurus "Page Not Found" shell with navbar
and footer, the first thing to verify is that deployment target / base URL
pairing above.

## Opting a commit out of the change log

Add `[skip docs]` anywhere in the commit message (or merge commit message)
to have `generate_runbook_entry.py` bail out without writing a post.
