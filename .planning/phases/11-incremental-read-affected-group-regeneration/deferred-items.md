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
