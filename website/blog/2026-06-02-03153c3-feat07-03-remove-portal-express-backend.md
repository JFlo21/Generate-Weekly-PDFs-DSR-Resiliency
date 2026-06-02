---
slug: 03153c3-feat07-03-remove-portal-express-backend
title: "feat(07-03): remove portal/ Express backend + flip CSP to enforcing (03153c3)"
authors: [runbook-bot]
tags: [portal]
date: 2026-06-02T22:37:56.689190+00:00
---

**Branch:** `master` &middot; **Commit:** [`03153c3`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/03153c353ab8a1bf807e7ceaaa994c2d50c6f56e) &middot; **Pusher:** `JFlo21`
  
[View the workflow run](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/actions/runs/26852172281).

<!-- truncate -->

## Commits in this push

- [`03153c3`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/03153c3) — feat(07-03): remove portal/ Express backend + flip CSP to enforcing
- [`a84f0ad`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/a84f0ad) — refactor(07-03): sever portal-v2 Express coupling

## Changed files

### Portal (Express)

- `portal/.env.example`
- `portal/config/default.js`
- `portal/lib/sentry.js`
- `portal/middleware/auth.js`
- `portal/middleware/security.js`
- `portal/package-lock.json`
- `portal/package.json`
- `portal/public/assets/logo.png`
- `portal/public/css/styles.css`
- `portal/public/dashboard.html`
- `portal/public/index.html`
- `portal/public/js/app.js`
- `portal/public/js/auth.js`
- `portal/public/js/dashboard-app.js`
- `portal/public/js/excel-viewer.js`
- `portal/routes/api.js`
- `portal/routes/auth.js`
- `portal/routes/health.js`
- `portal/scripts/generate-secrets.js`
- `portal/server.js`
- `portal/services/artifactCache.js`
- `portal/services/excel.js`
- `portal/services/excelHtml.js`
- `portal/services/github.js`
- `portal/services/lruCache.js`
- `portal/services/poller.js`
- `portal/services/searchIndex.js`
- `portal/tests/portal.test.js`
- `portal/vitest.config.mjs`

### Portal v2 (React)

- `portal-v2/.env.example`
- `portal-v2/src/components/dashboard/ArtifactExplorer.tsx`
- `portal-v2/src/components/dashboard/ArtifactPanel.tsx`
- `portal-v2/src/components/dashboard/CommandPalette.tsx`
- `portal-v2/src/components/dashboard/FilePreview.tsx`
- `portal-v2/src/components/dashboard/InteractiveExcelView.tsx`
- `portal-v2/src/components/dashboard/StyledExcelView.tsx`
- `portal-v2/src/hooks/useRuns.ts`
- `portal-v2/src/lib/api.ts`
- `portal-v2/src/lib/mockData.ts`
- `portal-v2/vercel.json`
- `portal-v2/vite.config.ts`
