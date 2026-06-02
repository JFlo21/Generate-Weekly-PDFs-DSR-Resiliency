---
status: partial
phase: 05-artifact-table-and-search
source: [05-VERIFICATION.md]
started: 2026-06-01T20:55:00-05:00
updated: 2026-06-01T20:55:00-05:00
---

## Current Test

[awaiting human testing]

## Tests

### 1. Live data smoke test
expected: The `/dashboard` table renders real rows from Supabase project
`poeyztlmsawfoqlanucc` (~2,383 artifacts) — actual Work Request #s and week-ending
dates, NOT placeholder/sample data. The "empty database" state shows only if the
table is genuinely empty for the signed-in role.
result: [pending]

### 2. Signed-URL download
expected: Clicking a row's Download button fetches a 5-minute (`createSignedUrl(path, 300)`)
signed URL from the private `excel-artifacts` bucket and downloads the `.xlsx`. On a
failed/expired URL, the error toast fires. No public bucket URLs appear anywhere.
result: [pending]

### 3. RLS pending-role isolation
expected: A user whose `profiles.role = 'pending'` sees ZERO artifact rows (role-aware
RLS JOIN on profiles enforces `role IN ('admin','billing')`). Only admin/billing roles
see data.
result: [pending]

### 4. Virtualized scroll under load (500+ rows)
expected: Scrolling through 500+ artifact rows stays smooth (row virtualization holds);
infinite scroll fetches the next page near the bottom without re-firing while a fetch is
in flight, and without the React render-phase warning (CR-01 fix).
result: [pending]

### 5. Search + filter + sort combine server-side
expected: Typing a search term (debounced 250ms), selecting one or more variant chips,
and clicking a column header to sort all produce a SINGLE combined PostgREST request
(`.or().in().order().range()`) — verifiable in the browser Network tab — not client-side
filtering. An apostrophe in the search (e.g. `O'Brien`) does NOT 400 (CR-02 fix).
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
