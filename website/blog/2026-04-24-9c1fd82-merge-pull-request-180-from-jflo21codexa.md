---
slug: 9c1fd82-merge-pull-request-180-from-jflo21codexa
title: "Merge pull request #180 from JFlo21/codex/analyze-docusaurus-and-vercel-integration (9c1fd82)"
authors: [runbook-bot]
tags: [configuration, portal, project]
date: 2026-04-24T09:13:54.984827+00:00
---

**Branch:** `master` &middot; **Commit:** [`9c1fd82`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/9c1fd821e2fca2c7f2fa2de74ea25aa883dd42ac) &middot; **Pusher:** `JFlo21`
  
[View the workflow run](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/actions/runs/24881867146).

<!-- truncate -->

## Commits in this push

- [`9c1fd82`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/9c1fd82) — Merge pull request #180 from JFlo21/codex/analyze-docusaurus-and-vercel-integration
- [`08f836e`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/08f836e) — fix: address latest copilot review hardening
- [`93b240a`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/93b240a) — fix: stream artifact downloads when bearer auth is absent
- [`aff810a`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/aff810a) — fix: require authenticated Supabase user JWTs
- [`99ab008`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/99ab008) — fix: fetch artifact URLs with bearer auth
- [`0c4ba79`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/0c4ba79) — fix: match portal events update names
- [`798f5cb`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/798f5cb) — fix: support bearer auth for portal events
- [`2687f1d`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/2687f1d) — fix: complete bearer cors review feedback
- [`3baf810`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/3baf810) — fix: avoid regex in bearer auth parsing
- [`eb2e30f`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/eb2e30f) — fix: secure render api with supabase auth
- [`efe4c2b`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/efe4c2b) — fix: address api auth and cors review feedback
- [`834e396`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/834e396) — fix(portal): align Render/Vercel integration and API contracts

## Changed files

### Portal (Express)

- `portal/.env.example`
- `portal/config/default.js`
- `portal/middleware/auth.js`
- `portal/middleware/security.js`
- `portal/routes/api.js`
- `portal/server.js`
- `portal/tests/portal.test.js`

### Portal v2 (React)

- `portal-v2/.env.example`
- `portal-v2/src/components/dashboard/FilePreview.tsx`
- `portal-v2/src/components/dashboard/StyledExcelView.tsx`
- `portal-v2/src/hooks/useRuns.ts`
- `portal-v2/src/lib/api.ts`

### Project docs

- `docs/railway-to-render-transition-plan.md`

### Configuration

- `render.yaml`
