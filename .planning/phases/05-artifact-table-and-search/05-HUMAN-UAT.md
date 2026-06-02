---
status: complete
phase: 05-artifact-table-and-search
source: [05-VERIFICATION.md]
started: 2026-06-01T20:55:00-05:00
updated: 2026-06-01T22:15:00-05:00
---

## Current Test

[testing complete]

## Tests

### 1. Live data smoke test
expected: The `/dashboard` table renders real rows from Supabase project
`poeyztlmsawfoqlanucc` (~2,383 artifacts) — actual Work Request #s and week-ending
dates, NOT placeholder/sample data. The "empty database" state shows only if the
table is genuinely empty for the signed-in role.
result: pass

### 2. Signed-URL download
expected: Clicking a row's Download button fetches a 5-minute (`createSignedUrl(path, 300)`)
signed URL from the private `excel-artifacts` bucket and downloads the `.xlsx`. On a
failed/expired URL, the error toast fires. No public bucket URLs appear anywhere.
result: pass
resolution: "Fixed in commit 2e134b2 (createSignedUrl { download } + de-Railway layout); re-verified in production — download now saves the .xlsx and the glitched 'sample data' banner is gone."
reported: "when i click download it takes me to the excel online app and opens the artifact; when it opens the online version of excel the site renders and a prompt heading appears from the top and it looks glitched"
severity: major
diagnosis: |
  createSignedUrl(path, 300) is called WITHOUT the { download } option, and the
  <a download=filename> attribute is ignored by browsers for cross-origin URLs
  (signed URL is on *.supabase.co). So the browser navigates to the URL instead of
  saving; the .xlsx is handed to the Excel Online viewer (the "glitched heading" is
  Excel Online's own banner, not the portal). Fix: createSignedUrl(path, 300,
  { download: filename }) → Content-Disposition: attachment forces a real download.

### 3. RLS pending-role isolation
expected: A user whose `profiles.role = 'pending'` sees ZERO artifact rows (role-aware
RLS JOIN on profiles enforces `role IN ('admin','billing')`). Only admin/billing roles
see data.
result: skipped
reason: "User skipped (no pending account handy); confident it works — backed by the role-aware RLS policy and the security audit (T-05-05). Recommended live re-check later."

### 4. Virtualized scroll under load (500+ rows)
expected: Scrolling through 500+ artifact rows stays smooth (row virtualization holds);
infinite scroll fetches the next page near the bottom without re-firing while a fetch is
in flight, and without the React render-phase warning (CR-01 fix).
result: pass

### 5. Search + filter + sort combine server-side
expected: Typing a search term (debounced 250ms), selecting one or more variant chips,
and clicking a column header to sort all produce a SINGLE combined PostgREST request
(`.or().in().order().range()`) — verifiable in the browser Network tab — not client-side
filtering. An apostrophe in the search (e.g. `O'Brien`) does NOT 400 (CR-02 fix).
result: pass

## Summary

total: 5
passed: 4
issues: 0
pending: 0
skipped: 1
blocked: 0

## Gaps

- truth: "Clicking a row's Download button downloads the .xlsx file to the user's machine"
  status: resolved  # commit 2e134b2, re-verified in production 2026-06-01
  reason: "User reported: download opens the artifact in Excel Online instead of saving the file; a glitched prompt heading appears from the top"
  severity: major
  test: 2
  artifacts: [portal-v2/src/hooks/useDownloadArtifact.ts]
  missing: ["createSignedUrl { download: filename } option to set Content-Disposition: attachment — cross-origin <a download> is ignored, so the browser opens the .xlsx in the Office viewer instead of downloading"]

- truth: "The Supabase-native dashboard makes NO calls to the removed Express/Railway backend, and shows no 'sample data / backend unreachable' banner when real data is present"
  status: resolved  # commit 2e134b2, re-verified in production 2026-06-01
  reason: "Incidental discovery during Test 2: production fires OPTIONS https://generate-weekly-pdfs-dsr-resiliency-production.up.railway.app/api/events → 404 (railway-edge, x-railway-fallback). DashboardLayout still mounts useRuns() which opens an EventSource to ${VITE_API_BASE_URL}/api/events and polls /api/runs on the dead Railway host, leaking the Supabase JWT cross-origin and flipping isSampleData=true → the false amber 'Showing sample data — backend unreachable' banner renders above the real Supabase table (likely the user's 'glitched heading')."
  severity: major
  test: incidental-during-2
  artifacts: [portal-v2/src/components/layout/DashboardLayout.tsx, portal-v2/src/hooks/useRuns.ts, portal-v2/src/components/layout/Navbar.tsx]
  missing: ["Remove useRuns()/EventSource run-polling + the isSampleData banner from DashboardLayout (D-02 'stop the legacy runs view'); simplify Navbar props; unset/repoint VITE_API_BASE_URL in Vercel prod (currently points at the dead Railway backend). Overlaps Phase 07 Express removal."]
