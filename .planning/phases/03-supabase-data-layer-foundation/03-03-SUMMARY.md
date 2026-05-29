---
phase: 03-supabase-data-layer-foundation
plan: "03"
subsystem: ci-workflow
tags: [github-actions, supabase, artifacts, fail-isolation]
dependency_graph:
  requires: [03-02]
  provides: [DATA-03]
  affects: [.github/workflows/weekly-excel-generation.yml]
tech_stack:
  added: []
  patterns: [continue-on-error isolation, step-scoped env secrets]
key_files:
  created: []
  modified:
    - .github/workflows/weekly-excel-generation.yml
decisions:
  - "Step placed AFTER Generate artifact manifest and BEFORE Save hash history cache so cache-save always runs regardless of publish outcome"
  - "continue-on-error: true on publish step — Supabase outage cannot fail billing run or block hash_history persistence (D-06)"
  - "Step-scoped env block required because step envs are not inherited across steps; reuses existing SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY secrets (D-12, no new secret)"
  - "if: always() && steps.exec.outputs.should_run == 'true' mirrors manifest/organize gate so publish runs exactly when billing ran"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-29"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
---

# Phase 03 Plan 03: Wire Publish Artifacts to Supabase Step — Summary

One additive, fail-isolated `Publish artifacts to Supabase` step inserted into
the production `weekly-excel-generation.yml` workflow, completing DATA-03: every
CI billing run now publishes its Excel artifacts to Supabase Storage without any
risk of failing the billing run, cache saves, or `hash_history.json` persistence.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Insert additive Publish artifacts to Supabase step | `4444a43` | `.github/workflows/weekly-excel-generation.yml` |

## What Was Done

Inserted a single 13-line YAML step into `.github/workflows/weekly-excel-generation.yml`
at line 581 (after "Generate artifact manifest" ends, before "Organize artifacts by
Work Request" begins):

- **Step name:** `Publish artifacts to Supabase` (id: `publish_supabase`)
- **Placement:** line 581; manifest step at 550; cache-save at 752 — ordering verified
- **`continue-on-error: true`** — a Supabase outage fails the step loudly but never
  fails the billing run or blocks the `if: always()` cache-save block
- **Step-scoped `env:`** re-exposes `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`
  from the existing GitHub Actions secrets (same names as in the "Generate reports"
  step; no new secret added, D-12 enforced)
- **Run command:** `python scripts/publish_artifacts_to_supabase.py generated_docs`
  (matches the script's documented argv contract)
- **No other step modified:** manifest, organize, cache-save, and all other steps
  are byte-for-byte identical to before

## Verification Results

| Gate | Result |
|------|--------|
| Plan verify Python script (ordering + continue-on-error + secrets + run) | OK |
| YAML `yaml.safe_load()` | Valid |
| `grep -A3 'Publish artifacts to Supabase' \| grep continue-on-error` | Match |
| `pytest tests/ -v` | 1016 passed, 16 pre-existing failures, 0 new failures |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — the step is fully wired. The publish script (`scripts/publish_artifacts_to_supabase.py`)
was implemented in Plan 02 and is invoked with the correct argv.

## Threat Surface Scan

The inserted step re-exposes `SUPABASE_SERVICE_ROLE_KEY` to the step env. This was
explicitly modeled in the plan's threat register (T-03-secret-scope) and is the
required pattern. The verify gate asserts no `VITE_` variable appears on the step,
confirming the service_role key stays CI-only (never on Vercel).

No new threat surface beyond what the plan's threat model covers.

## Self-Check

- [x] `.github/workflows/weekly-excel-generation.yml` modified — confirmed
- [x] Commit `4444a43` exists — confirmed
- [x] Publish step at line 581, after manifest (550), before cache-save (752) — confirmed
- [x] YAML valid, all acceptance criteria met
