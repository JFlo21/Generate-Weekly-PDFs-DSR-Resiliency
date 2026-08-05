---
id: how-this-site-updates
title: How this site updates
sidebar_position: 2
---

# How this site updates

This runbook is intentionally low-ceremony. Three moving parts keep it
fresh: the change-log generator, the Vercel deployment hook, and manual
edits.

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

The workflow then **commits the post directly to `master`** with a
`docs(runbook): log <short-sha> [skip ci]` message, staging only paths
under `website/blog/`. A rebase-retry loop (5 attempts) absorbs
concurrent pushes; each entry is a unique new file, so the rebase never
conflicts. That commit is the push Vercel picks up to rebuild the site.

:::info Why a direct commit instead of a PR?
An earlier version of this workflow opened a pull request per push via
`peter-evans/create-pull-request`. The PRs were never auto-merged and
piled up unbounded (36 stale stubs were closed on 2026-06-06), so the
workflow now commits straight to `master`. Loop protection is layered:
the job-level `if: github.actor != 'github-actions[bot]'` guard, GitHub's
rule that `GITHUB_TOKEN`-authored pushes never re-trigger `push`
workflows, and the generator's own short-circuit when a push touches only
bot-maintained paths (`website/blog/`, `whats-new.md`).
:::

## 2. Vercel deployment (repo → live site)

The runbook deploys to Vercel from this repository. The wiring is:

| Setting | Value | Where |
|---------|-------|-------|
| Connected Git repository | `JFlo21/Generate-Weekly-PDFs-DSR-Resiliency` | Vercel project → Settings → Git |
| Production branch | `master` | Vercel project → Settings → Git |
| Root Directory | `website` | Vercel project → Settings → Build & Output |
| Framework preset | Docusaurus (v2+) | pinned by `website/vercel.json` (`"framework": "docusaurus-2"` — the correct preset slug for Docusaurus 2/3) |
| Build command / output | `npm run build` → `build/` | pinned by `website/vercel.json` |
| Install command | `npm ci` | pinned by `website/vercel.json` |
| Node.js version | 20.x | matches `engines.node` in `website/package.json` |

Because every meaningful push to `master` produces a `website/blog/`
commit (section 1), Vercel rebuilds and redeploys the site shortly after
**every** repo change — the change log entry and the deploy ride the same
commit. `[skip ci]` in the bot commit message suppresses GitHub Actions,
not Vercel, so the deploy still fires.

`website/vercel.json` also sets `cleanUrls: true` and
`trailingSlash: false`, which **must** stay in sync with
`trailingSlash: false` in `docusaurus.config.ts` — if they disagree, the
router emits canonical URLs Vercel 308-redirects away from, and client
navigation lands on "Page Not Found."

**Healthy signal:** after a merge to `master`, the Vercel deployments
list shows a new production build for the `docs(runbook): log …` commit,
and the Change Log front page shows the matching entry.

CI safety net: `.github/workflows/docs-site-build.yml` builds and
typechecks the site on every PR that touches `website/`, so a broken
config or MDX error is caught before Vercel ever sees it.

## 3. Manual runbook edits

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

## Opting a commit out of the change log

Add `[skip docs]` anywhere in the commit message (or merge commit message)
to have `generate_runbook_entry.py` bail out without writing a post.
