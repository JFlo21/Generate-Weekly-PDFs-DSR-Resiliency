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

1. Compares `${{ github.event.before }}` with `${{ github.sha }}`.
2. Buckets the changed files into **Python**, **Workflows**, **Portal**,
   **Docs**, **Scripts**, and **Other**.
3. Lists commits in the push range with short SHA and subject.
4. Writes a Markdown post at
   `website/blog/YYYY-MM-DD-<short-sha>-<slug>.md` with frontmatter
   (title, authors, tags).
5. Commits the new file with `[skip ci]` on `master`.

Vercel is connected to the repo, so the commit triggers a rebuild of the
Docusaurus site.

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

Then visit <http://localhost:3000>.

## Opting a commit out of the change log

Add `[skip docs]` anywhere in the commit message (or merge commit message)
to have `generate_runbook_entry.py` bail out without writing a post.
