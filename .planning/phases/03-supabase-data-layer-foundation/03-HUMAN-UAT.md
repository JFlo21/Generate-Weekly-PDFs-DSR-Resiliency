---
status: partial
phase: 03-supabase-data-layer-foundation
source: [03-VERIFICATION.md]
started: 2026-05-29
updated: 2026-05-29
---

## Current Test

End-to-End CI Publish Proof (post-merge / live-run observable).

## Gaps

### GAP-1: CI publish lands a row + file
- **status:** pending
- **requirements:** DATA-01, DATA-02, DATA-03 (ROADMAP SC1 + SC4)
- **why deferred:** Inherently post-merge — the additive publish step only runs
  when `weekly-excel-generation.yml` next executes from `origin`. All code-side
  facts are verified; this is the live observation.
- **how to verify:**
  1. Push `master` to `origin` so the workflow includes the new
     "Publish artifacts to Supabase" step.
  2. Let the next scheduled run fire (every ~2h on weekdays) OR manually
     `workflow_dispatch` the run.
  3. In Supabase: `SELECT count(*) FROM public.artifacts;` returns > 0, and the
     `excel-artifacts` bucket lists ≥ 1 file.
  4. Confirm the workflow run SUCCEEDS and the publish step did NOT block the
     billing run, Smartsheet upload, cache-save, or `hash_history` persistence
     (continue-on-error isolation). If Supabase were down, the step shows a
     failure + a `$GITHUB_STEP_SUMMARY` line but the run still succeeds.

## Operator-Confirmed (already passed)

- Schema applied to the live Supabase project; `public` exposed (no PGRST106).
- Private `excel-artifacts` bucket created.
- `billing` + `pending` test profiles seeded.
- Anonymous `GET /rest/v1/artifacts` returns `[]` (RLS blocks public reads).

## Deferred to Phase 05 (not Phase 03 gaps)

- DATA-04 portal-v2 supabase-js read path (TABLE-01/02).
- DATA-05 client-side `createSignedUrl` download (TABLE-04). The enabling
  `storage.objects` SELECT policy is already committed in this phase.
