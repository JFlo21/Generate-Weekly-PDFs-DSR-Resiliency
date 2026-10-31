# Quick 261030-suf: Hold pilot groups when the Foreman Notes GF lookup fails - Research

**Researched:** 2026-10-30
**Mode:** read-only; no source edited
**Confidence:** HIGH on code facts (all read this session); MEDIUM on the "hold all changed groups" cost, which depends on how often a lookup fails.

## User Constraints (todo, owner decision 2026-10-30)

Option 1: hold pilot groups for that run (no regeneration, no upload), with a Sentry warning. Option 2 (reuse last known pilot WR set) is rejected. Fix lands before `FOREMAN_NOTES_UPLOAD` goes on. Regression test: good run, then failed lookup, assert no pilot group regenerates.

## Summary

Nothing durable records "this group was pilot". `pipeline_memory.group_state` stores only `content_hash`, `row_count`, `attachment_id/name`, `last_*_run`, `source`, `source_ref` (`pipeline_memory/schema.sql:229-247`). The only trace of pilot membership is inside `content_hash` (the `NOTES_FP=` suffix, `change_detection.py:408` and `:535`), which is one-way. So when `load_gf_map` returns `None` (`foreman_notes.py:367`) the pipeline cannot name the pilot WRs. A schema change is out of bounds (protected Supabase schema).

Smallest safe option is (a): while the lookup has failed, a group is held unless its hash matches the stored hash. This holds every pilot group (their hash lost `NOTES_FP`, so it differs). It also holds non-pilot groups that genuinely changed or are new, for one run. Non-pilot unchanged groups are unaffected, because the failure does not change their hash.

## Findings by question

### 1. Durable signal (the crux)

- **Hash is the only signal, and it cannot identify pilot.** Pilot groups hash with `NOTES_FP=<token>` appended only when `group_notes_token` is non-empty (`change_detection.py:404-408` legacy, `:530-535` extended). `group_notes_token` returns `""` when `is_pilot_group` is false (`foreman_notes.py:699-700`). With `pilot_wrs` empty (`:367-371`), `is_pilot_row` returns `wr in state.pilot_wrs` -> `False` (`:417-418`), so every pilot group's new hash differs from its stored hash.
- **Filename/attachment name:** embeds `{hash}` (CLAUDE.md pipeline flow), so it is the same one-way information as `content_hash`. No pilot marker.
- **`globals_component`:** not a per-group signal; see Q2.
- **Option (b) cached allowlist-matched set:** that is the rejected option 2. Do not build it.
- **Refinement tried and rejected:** recomputing each held group's hash as-if-pilot and comparing to stored only identifies *unchanged* pilot groups, which option (a) already holds. A *changed* group matches neither form, so pilot-ness stays unknowable. No precision is gained without a persisted marker (schema change).

**Recommendation: option (a).** When the pilot lookup failed, treat a group as HELD iff `not _hash_unchanged`.
- Pilot groups, unchanged or changed: held (hash lost `NOTES_FP`, so `_hash_unchanged` is False).
- Non-pilot groups, unchanged: `_hash_unchanged` True, so they skip exactly as today (including the attachment-missing repair path at `orchestrate.py:4967-4972`).
- **Cost to non-pilot groups:** a non-pilot group with a real data change, or a brand-new group with no stored hash, waits one run. It is carried as regeneration debt automatically (see "Held-group bookkeeping"). Nothing else changes for them.
- New groups with no stored hash are also held. Deliberate: a new group may be pilot and would otherwise ship without notes then churn.
- Force flags (`FORCE_GENERATION`, `REGEN_WEEKS`, `RESET_HASH_HISTORY`, `RESET_WR_LIST`) make `_history_eligible_for_skip` False so `_hash_unchanged` is False (`orchestrate.py:4473-4499`). Under a failed lookup these would regenerate pilot groups without notes. Recommend the hold wins (fail-safe). Surface as an Open Question for the owner.

### 2. Does `globals_component` feed every group's hash?

**No.** Its only consumer is `memory_candidate.group_hash_globals_fingerprint` (`memory_candidate.py:383-385`), appended only when non-empty. That fingerprint is read in two places: the Phase 11 shadow comparison (`orchestrate.py:1992-2003`, returns `would_fallback_full:group_hash_globals_changed`) and the run_ledger notes write (`orchestrate.py:5209-5214`). `calculate_data_hash` never calls it (confirmed: `change_detection.py` references `_fn` only at `:404` and `:530`, both `group_notes_token`).

Blast radius of a failed lookup:
- **Group hashes:** only pilot groups move (they lose `NOTES_FP`). Non-pilot groups: zero change.
- **Shadow fingerprint:** `pilot_wrs` goes empty so the fingerprint changes. It affects shadow/parity reporting only (never what is generated or uploaded), once on the failed run and once when the lookup recovers. No fix needed.

### 3. Narrowest hook point

Add one field to the frozen dataclass: `FnState.gf_failed: bool = False` (`foreman_notes.py:198-202`), set `True` only in the `gf_map is None` branch of `initialize` (`:367-371`). Do NOT reuse `gf_loaded == False`: that is also False for scope off, scope all, and the empty-allowlist branch (`:353-359`), where an operator intentionally changed config and regeneration is correct.

Add a pure predicate in `foreman_notes.py`:
`should_hold_group(hash_unchanged: bool) -> bool`, returning `state.gf_failed and not hash_unchanged` (never raises, same convention as the other predicates).

Call site: `orchestrate.py` `main()` group loop, immediately after the no-target gate's `continue` (`:4559`) and BEFORE the billing-audit freeze block (`:4561-4572`). Rationale: keeps billing_audit freeze and the aggregated `content_hash` fingerprint from recording a non-pilot-form hash for a pilot group. Mirrors the no-target precedent (`:4533-4559`). On hold: log (counts only, no WR text; note the registered PII marker convention at `:4528-4532`), `_groups_skipped += 1` is optional, then `continue`.

Byte-identical guarantee: `gf_failed` defaults False and is set only on the failure path, so scope off, scope all, empty allowlist, and a good pilot lookup never take the new branch. `calculate_data_hash`, `change_detection.py`, and Excel generation are untouched. The AST test `test_fn_references_confined_to_expected_functions` (`tests/test_foreman_notes_pipeline.py:285-292`) already lists `main` as an allowed `_fn` user, so a `_fn.should_hold_group(...)` call inside `main` keeps it green. Do not put a new `_fn` reference in another orchestrate function.

### Held-group bookkeeping (verified, do not add anything)

- Do NOT add the held group to `_mem_confirmed_skip_keys` (`:4962`). `_regen_debt_finish_kwargs` treats pairs not skip-confirmed, uploaded, withheld, or no-target as owed a regeneration and carries them as debt (`orchestrate.py:1850-1884`, doc at `:1888-1892`). That is the desired behaviour for a hold, identical to groups the time budget never reached (`:4373-4384`).
- A held group never reaches `generate_excel`, upload, `_deferred_group_state`, or the hash-store upsert, so the stored hash and attachment stay as last good. The existing unchanged-skip path produces the same no-new-file state, so attachment cleanup already tolerates it.
- `_shadow_group_hashes[group_key] = data_hash` (`:4393`) still records the non-pilot-form hash for held groups; parity-only, no production effect. Flag for the reviewer.

### 4. Existing tests to reuse

- `tests/test_foreman_notes_pipeline.py`: `_Base` (resets state, `pilot_patches()` patches `FOREMAN_NOTES_PILOT_GFS` + `EFFECTIVE_SCOPE`, `:104-115`), `_Client`/`_Sheets` (`:74-91`; `get_sheet` for `config.TARGET_SHEET_ID` returns `_target_sheet()` with `PILOT_WR` 90003 under GF "avery example" and `OTHER_WR` 90004), `_group(wr)` (`:94-101`), `golden.pinned_env`. `TracerTests` (`:119-183`) is the template: `fn.initialize(client)` then `cd.calculate_data_hash(rows)`.
- `tests/test_foreman_notes_state.py` `InitializeTests`: `_init(scope, allowlist, client)` and `_client(exc=RuntimeError('x'))` for the failing lookup; `test_gf_failure_yields_no_pilot` (`:296-300`) is the exact failure fixture. Extend it to assert `gf_failed` True there and False for empty-allowlist/off/all/good.
- `tests/test_foreman_notes_hash.py` `_StateCase`/`_pilot_state` (`:48-70`) for state set-up.
- Run sequence (no existing end-to-end `main()` driver for the group loop; the skip decision is inline in `main`): simulate with `cd._resolve_unchanged_for_skip(history_key, data_hash, group_state_hashes, wr, week_iso, variant, identifier, billing_audit_writer=None)` (`change_detection.py:928`), where `group_state_hashes = {history_key: {'hash': h}}` (shape per `orchestrate.py:4040-4042`; TEST_MODE/authoritative-off path reads only this dict, `:999-1000`). Usage precedent in `tests/test_subproject_e_hash_store.py`.

Regression test (new file, e.g. `tests/test_foreman_notes_gf_hold.py`):
1. Good run: initialize pilot with a good client, hash `_group(PILOT_WR)` and `_group(OTHER_WR)`, store as `group_state_hashes`.
2. Failed run: `fn.reset_state()`, initialize with `_client(exc=...)` (or `_Sheets` raising), recompute hashes.
3. Assert pilot group: `_resolve_unchanged_for_skip` False and `fn.should_hold_group(False)` True. Non-pilot unchanged: unchanged True, hold False.
4. Assert a non-pilot group with a changed row is held (documents the accepted cost), and a good-lookup run holds nothing.
5. AST test (pattern of `SeamOrderTests`, `:264-283`): in `main`, the `_fn.should_hold_group` call precedes `generate_excel` and the billing-audit freeze block.

### 5. Sentry

`pipeline/observability.py:253` `sentry_capture_message_with_context(message, level, context_name, context_data, tags)` exists, but it calls `scope.set_tag` on the CURRENT scope (`:260-267`), so tags persist onto later events in the run. The leak-safe model in the same file is `sentry_capture_sheet_drop` (`:221-247`): `with sentry_sdk.isolation_scope() as scope: scope.set_tag(...); scope.fingerprint = [...]; sentry_sdk.capture_message(..., level=...)`. `sentry-sdk>=2.54.0` (`requirements.txt:2`) supports it.

Recommendation: add a small `_warn_hold()` inside `foreman_notes.py`, next to `_breadcrumb` (`:327-339`), using the same lazy `import sentry_sdk` + `try/except Exception: pass`. Reasons: foreman_notes already lazy-imports sentry (avoids a new cycle; `observability.py:199` imports foreman_notes lazily), and the failure is known inside `initialize`. Emit once per run from the `gf_map is None` branch: `isolation_scope()`, tag `foreman_notes_hold="gf_lookup_failed"`, fingerprint `["foreman-notes-gf-lookup-hold"]`, `level="warning"`, message text with NO WR, GF name, or note content (counts only, e.g. allowlist size). Existing `logging.warning` calls in `load_gf_map` already log exception class only (`:319-323`).

## Pitfalls

- Do not key the hold on `gf_loaded` (also False for off/all/empty-allowlist).
- Keep the hold before the billing-audit freeze block, not after the skip decision at `:4973`, or non-pilot-form hashes reach billing_audit.
- `initialize`'s outer exception handler (`:393-399`) returns `FnState()` (scope off) and would not hold. Consider setting `gf_failed` there only when scope was pilot; mention to reviewer, low probability.
- PII: Actions/Sentry log text must avoid WR numbers and GF names; the project drops logs matching `_PII_LOG_MARKERS` (e.g. text starting "Work request ").
- Run `bash scripts/run_6_gates.sh` after editing `pipeline/` (facade-completeness and AST import-equality gates); `pytest tests/ -v` must pass before push.

## Assumptions Log

| # | Claim | Risk if wrong |
|---|-------|---------------|
| A1 | Holding a force-flagged regeneration during a failed lookup is acceptable to the owner | Operator cannot force-regen pilot groups during an outage; low impact |
| A2 | Holding brand-new groups (no stored hash) is acceptable | New non-pilot groups wait one run |
| A3 | Attachment cleanup tolerates a group with no new file this run (same as an unchanged skip) | Not traced in `pipeline/cleanup.py`; verify in the plan |

## Open Questions

1. Should `FORCE_GENERATION` / `RESET_*` override the hold? Recommended: no (hold wins), logged.
2. Is a one-run delay for changed non-pilot groups and new groups acceptable? It is the unavoidable cost of option 1 without a persisted marker.

## RECOMMENDED APPROACH and FILES TO TOUCH

1. `pipeline/foreman_notes.py`: add `FnState.gf_failed: bool = False`; set `True` in the `gf_map is None` branch of `initialize` and emit `_warn_hold()` (isolation-scope, warning, counts-only); add `should_hold_group(hash_unchanged)` and export it in `__all__` (the `"globals_component"` list at `:51-69`).
2. `pipeline/orchestrate.py` (`main()` group loop, after `:4559`, before `:4561`): `if _fn.should_hold_group(_hash_unchanged): log counts-only; continue` (no `_mem_confirmed_skip_keys` add).
3. New `tests/test_foreman_notes_gf_hold.py` (sequence regression, accepted-cost case, AST ordering) and extend `tests/test_foreman_notes_state.py::InitializeTests` for `gf_failed`.
4. Docs: dated entry at bottom of `memory-bank/living-ledger.md`; note in `docs/ai/implementation-truth.md` if it covers Foreman Notes. Do NOT touch `pipeline/change_detection.py`, `calculate_data_hash`, `memory_candidate.py`, or `pipeline_memory/schema.sql`.
