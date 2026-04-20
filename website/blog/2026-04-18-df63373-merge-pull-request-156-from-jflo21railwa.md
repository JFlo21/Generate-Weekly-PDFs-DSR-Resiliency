---
slug: df63373-merge-pull-request-156-from-jflo21railwa
title: "Merge pull request #156 from JFlo21/railway-disconnection-plan (df63373)"
authors: [runbook-bot]
tags: [configuration, portal, project]
date: 2026-04-18T05:45:27.277313+00:00
---

**Branch:** `master` &middot; **Commit:** [`df63373`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/df633730f25f3a22b60533c65a02e9284cccb2c0) &middot; **Pusher:** `JFlo21`
  
[View the workflow run](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/actions/runs/24598153892).

<!-- truncate -->

## Commits in this push

- [`df63373`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/df63373) — Merge pull request #156 from JFlo21/railway-disconnection-plan
- [`a9b06ac`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/a9b06ac) — fix(types): add optional event/actor to WorkflowRun to match backend and mock data
- [`07c6f48`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/07c6f48) — test: add route tests for new API endpoints and fix Sentry profiling load on Node.js v24
- [`3cbe89a`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/3cbe89a) — chore: establish plan for adding new API route tests
- [`775d825`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/775d825) — refactor: enhance Sidebar with Docs shortcut and external link support
- [`a5d9985`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/a5d9985) — fix: resolve stale HMR module crash in DashboardLayout
- [`defa47a`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/defa47a) — fix: resolve CORS and UX issues in dashboard
- [`8d6a56f`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/8d6a56f) — fix: resolve CORS and profile issues in v0 preview
- [`a2623c5`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/a2623c5) — fix: resolve data loading and redesign dashboard
- [`8b40896`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/8b40896) — feat: add mock data layer for v0 preview
- [`9dda535`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/9dda535) — fix: address root causes for app stability
- [`715cec3`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/715cec3) — fix: modernize "Failed to fetch" error styling in RunList
- [`b102ece`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/b102ece) — feat: full stack update with new backend blueprint, search index, API routes, and frontend explorer
- [`348e572`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/348e572) — feat: implement deployment config, backend routes, UI, and Cmd+K palette
- [`3e3fabe`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/3e3fabe) — add transition plan document and update project context
- [`e9ef32f`](https://github.com/JFlo21/Generate-Weekly-PDFs-DSR-Resiliency/commit/e9ef32f) — docs: replace Railway with Render across all files

## Changed files

### Portal (Express)

- `portal/lib/sentry.js`
- `portal/package-lock.json`
- `portal/package.json`
- `portal/routes/api.js`
- `portal/server.js`
- `portal/services/artifactCache.js`
- `portal/services/excelHtml.js`
- `portal/services/lruCache.js`
- `portal/services/searchIndex.js`
- `portal/tests/portal.test.js`

### Portal v2 (React)

- `portal-v2/.env.example`
- `portal-v2/README.md`
- `portal-v2/pnpm-lock.yaml`
- `portal-v2/src/components/auth/AuthGuard.tsx`
- `portal-v2/src/components/dashboard/ArtifactExplorer.tsx`
- `portal-v2/src/components/dashboard/ArtifactPanel.tsx`
- `portal-v2/src/components/dashboard/CommandPalette.tsx`
- `portal-v2/src/components/dashboard/DashboardPage.tsx`
- `portal-v2/src/components/dashboard/ExcelViewer.tsx`
- `portal-v2/src/components/dashboard/FilePreview.tsx`
- `portal-v2/src/components/dashboard/InteractiveExcelView.tsx`
- `portal-v2/src/components/dashboard/RunList.tsx`
- `portal-v2/src/components/dashboard/StatsGrid.tsx`
- `portal-v2/src/components/dashboard/StyledExcelView.tsx`
- `portal-v2/src/components/layout/DashboardLayout.tsx`
- `portal-v2/src/components/layout/Navbar.tsx`
- `portal-v2/src/components/layout/Sidebar.tsx`
- `portal-v2/src/components/ui/ErrorBoundary.tsx`
- `portal-v2/src/hooks/useArtifacts.ts`
- `portal-v2/src/hooks/useAuth.ts`
- `portal-v2/src/hooks/useCommandPalette.ts`
- `portal-v2/src/hooks/useRuns.ts`
- `portal-v2/src/lib/api.ts`
- `portal-v2/src/lib/mockData.ts`
- `portal-v2/src/lib/supabase.ts`
- `portal-v2/src/lib/types.ts`

### Project docs

- `docs/railway-to-render-transition-plan.md`
- `docs/sentry-implementation.md`
- `docs/update-log-v2-dashboard-fixes.md`
- `memory-bank/activeContext.md`

### Configuration

- `render.yaml`
