# Deferred Items — Phase 11

Out-of-scope discoveries logged per the executor's SCOPE BOUNDARY rule
(fixed only when a plan's `files_modified` explicitly names the file).

## 11-08 (INC-05 retirement)

- **`.github/instructions/copilot-setup.instructions.md` is stale.** It still
  documents `USE_DISCOVERY_CACHE`, `DISCOVERY_CACHE_TTL_MIN`,
  `generated_docs/discovery_cache.json` and `generated_docs/hash_history.json`
  (lines ~31, ~39, ~108, ~176, ~224, ~226) as live configuration/artifacts.
  These were retired by 11-08 (INC-05). Plan 11-08's `files_modified` lists
  only `.github/prompts/configuration-environment.md` and `CLAUDE.md` for
  documentation — `copilot-setup.instructions.md` was not in scope for this
  plan. Needs its own doc-fix pass (or a follow-up plan) to bring it current.

- **`scripts/notion_sync.py:507` reads a now-permanently-absent
  `DISCOVERY_CACHE_VERSION = N` line out of `generate_weekly_pdfs.py` to
  populate a "Cache version" metrics field in Notion.** The regex simply
  never matches anymore (silent no-op — `cache_version` stays at its `1`
  default), it does not raise. Not in 11-08's `files_modified`; low-priority
  metrics drift in an external sync tool, not the billing pipeline. Follow-up:
  either drop the field or repoint it at a still-live version constant.

- **`tests/test_security_audit_followup.py`'s `TestDiscoveryCacheFastPathSkipsOnPartialCorruption`
  class (~line 927) is a self-contained truth-table test for the discovery-cache
  incremental fast path's `_partial_cache_corruption` gate — logic Task 3
  retired entirely from `pipeline/discovery.py`.** The test does not call any
  retired production function (it replicates the boolean truth table inline),
  so it stays green and does not block `pytest tests/ -q`; it is stale
  documentation of a gate that no longer exists, not a current defect. Not in
  11-08's `files_modified`. Follow-up: rewrite as a `test_..._retired`
  assertion (same pattern as the 31 tests 11-08 Task 3 did rewrite) or delete
  with a note, in a plan that actually touches this file.
