---
slug: inc05-cache-retirement
title: "Local JSON caches retired — Supabase run-memory is now the sole change-detection and discovery state (PR #373)"
authors: [runbook-bot]
tags: [github, project, python, workflows]
date: 2026-08-31T22:00:00+00:00
---

**Component:** Python billing pipeline (`generate_weekly_pdfs.py` →
`pipeline/orchestrate.py`, `pipeline/discovery.py`,
`pipeline/change_detection.py`) and the `weekly-excel-generation.yml`
GitHub Actions workflow. **Change type:** infrastructure retirement — no
change to what a run generates, prices or uploads. **PR:** #373 (Phase 11
Plan 08, INC-05).

<!-- truncate -->

## What changed

Three local JSON caches, the two bulk Smartsheet attachment pre-fetch
phases, and the six GitHub Actions cache restore/save steps that carried
those caches across runs are all retired:

1. **`generated_docs/hash_history.json`** (change-detection skip gate) —
   removed along with `load_hash_history`, `save_hash_history`, and the
   one-time hash-prune helpers that targeted it. Supabase
   `pipeline_memory.group_state.content_hash` is now the sole
   change-detection skip gate (the fallback beneath
   `SUPABASE_HASH_STORE_AUTHORITATIVE`, and the sole decision source when
   that flag is off).
2. **`generated_docs/discovery_cache.json`** (sheet discovery TTL cache) —
   removed. `discover_source_sheets()` now validates every candidate
   sheet in full, every run. Cross-run sheet identity lives solely in
   Supabase `pipeline_memory.sheet_registry`.
3. **`generated_docs/billing_audit_frozen_rows.json`** (billing-audit row
   cache) — removed. The in-run `billing_audit_row_cache` set now starts
   empty every run instead of warm-starting from a persisted file;
   `freeze_row` / `freeze_attribution` are already idempotent
   (first-write-wins), so the only cost is a few redundant, safe RPC
   calls per run.
4. **The two bulk attachment pre-fetch phases** (target sheet + PPP
   sheet) and their sub-budget constants
   (`ATTACHMENT_PREFETCH_MAX_MINUTES`, `ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC`)
   — removed. Attachment identity for delete-then-upload now resolves
   from `pipeline_memory.group_state` (the `attachment_id` /
   `attachment_name` this pipeline itself uploaded last time it flushed
   that group). A miss — cold state, a Supabase outage, or a group that
   has never flushed — falls back to a per-row, on-demand Smartsheet
   attachment listing, memoized per row for the rest of the run.
5. **Six `actions/cache/restore` + `actions/cache/save` steps** in
   `weekly-excel-generation.yml` — removed. The `pip` dependency cache
   (keyed on `requirements.txt`'s hash) is the only `actions/cache` step
   left in the job.

`USE_DISCOVERY_CACHE` and `DISCOVERY_CACHE_TTL_MIN` are now no-ops (there
is no cache left to honor or age out). `FORCE_REDISCOVERY` is kept
defined for operator-runbook / backward-compat reasons but is also a
no-op — there is no cache left to bypass.

## Why

Phase 11's run-memory work (`pipeline_memory.group_state`,
`pipeline_memory.sheet_registry`) already had to durably record
everything the local JSON caches were tracking, as the foundation for the
still-dormant incremental read. Once the shadow-parity comparator had
strung together five consecutive `pass` verdicts on scheduled
`production_frequent` runs — the same D-09 evidence gate that authorizes
the incremental read itself — the local caches were provably redundant:
Supabase was already correctly tracking the same state on every run, in
parallel with the files. Carrying three JSON files and six cache
steps that duplicate data already durably stored in Supabase was pure
maintenance surface with no remaining benefit, so INC-05 removed them.

The incremental read itself (`RUN_MEMORY_INCREMENTAL_ENABLED`) is a
**separate, still-unflipped** flag — this retirement only removes the
local caches; it does not change *when* a group regenerates or *what*
gets read each run.

## What operators need to know

- **The four retired env vars are silent no-ops**, not errors. If they
  are still set in a workflow dispatch or a local `.env`, nothing breaks
  — they simply do nothing now.
- **Force-regeneration flags are unchanged.** `RESET_HASH_HISTORY`,
  `REGEN_WEEKS`, `RESET_WR_LIST`, and `FORCE_GENERATION` still force full
  regeneration exactly as before — they now escalate via D-02 trigger 5
  against `pipeline_memory.group_state` instead of invalidating a local
  file, but the operator-facing behavior (and the `advanced_options`
  `key:value` syntax) is identical.
- **A manually deleted attachment recovers on the next run.** Because the
  skip gate confirms attachment *existence* against a live per-row
  Smartsheet listing (memoized per row per run) rather than trusting a
  cached identity, a report that someone deleted from the target sheet by
  hand is regenerated and re-uploaded on the next run, not silently
  skipped.
- **There is no local cache to restore or reset anymore.** The
  `RESET_HASH_HISTORY=true` / "hash history is ephemeral in CI" guidance
  from before this PR is obsolete — there is no file for a CI run to lose
  or an operator to clear.
- **Runtime headroom, not a regression.** The three `production_frequent`
  runs measured immediately before this retirement landed (2026-08-31)
  already ran 54.9–59.5 minutes — well under the 94-minute baseline this
  work was benchmarked against — so the pre-fetch/JSON-cache path being
  retired was not this run's bottleneck. The after-retirement figure is
  still pending the first scheduled run against the merged change; either
  way, both are well inside the 165-minute session budget.

## Rollback

Revert PR #373. There is no cache state to restore — the retirement
removed the cache files and their GitHub Actions steps outright, so
rollback is a code revert, not a cache operation. Nothing in production
billing output, attachment naming, or upload behavior changes either way.
