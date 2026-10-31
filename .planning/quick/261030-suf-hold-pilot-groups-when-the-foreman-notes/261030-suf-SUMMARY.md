---
phase: quick-261030-suf
plan: 01
status: complete
subsystem: billing-pipeline / foreman-notes / observability
tags: [foreman-notes, sentry, change-detection, pilot, hold]
requires:
  - Phase 15 Foreman Notes pilot (pipeline/foreman_notes.py)
provides:
  - FnState.gf_failed / gf_fail_reason / gf_fail_exc / gf_fail_msg
  - load_gf_lookup, gf_lookup_failed, should_hold_group, report_run_end
  - observability.foreman_notes_scope, sentry_capture_foreman_notes,
    set_foreman_notes_run_tags
affects:
  - pipeline/orchestrate.py main() group loop (hold branch) and session_summary
tech-stack:
  added: []
  patterns:
    - forked sentry_sdk.new_scope() for per-event tags/context/fingerprint
    - per-run failure counters reported once at run end
key-files:
  created:
    - tests/test_foreman_notes_gf_hold.py
    - tests/test_foreman_notes_sentry.py
    - .planning/todos/pending/2026-10-30-wr-numbers-in-sentry-span-names.md
  modified:
    - pipeline/foreman_notes.py
    - pipeline/observability.py
    - pipeline/orchestrate.py
    - tests/test_foreman_notes_state.py
    - docs/DECISIONS.md
    - docs/sentry-implementation.md
    - memory-bank/living-ledger.md
    - website/docs/runbook/foreman-notes-pilot.md
decisions:
  - Hold any group whose fresh hash differs from the stored hash while the GF lookup has failed (option 1; option 2 not built)
  - Hold wins over force/regen flags; forced groups whose hash still matches regenerate as forced
  - Outer initialize handler sets gf_failed only for effective scope pilot with a non-empty allowlist
  - WR numbers allowed only in the foreman_notes context of Foreman Notes events on a forked scope
metrics:
  duration: ~75 min
  completed: 2026-10-30
estimate:
  tokens: 130000
actuals:
  tokens: 25600   # includes the fix round (initial plan alone: 18200)
  tasks: 3
  commits: 12     # 5 plan commits + 7 fix-round commits
plan_head_before: 014366937c6f5160e22a91436d0157fc61958405
plan_head_after: 327d3af1d391e13f73af2359f0d8cb88d7e1e495
---

# Phase quick-261030-suf Plan 01: Hold pilot groups on GF-lookup failure Summary

If the Foreman Notes General Foreman lookup fails in an effective pilot scope, the run now sets `FnState.gf_failed` and holds every group whose hash has changed. A held group skips the billing-audit freeze, Excel generation and upload, and is carried as regeneration debt. Every Foreman Notes failure path now sends a Sentry signal. WR numbers appear only in the forked-scope `foreman_notes` context.

## Commits

| Task | Commit | Subject |
|------|--------|---------|
| 1 RED | 64857ee | test(quick-261030-suf): RED GF-lookup hold tests |
| 1 GREEN | 347d048 | fix(quick-261030-suf): hold groups on GF lookup fail |
| 2 RED | 1a24416 | test(quick-261030-suf): RED Foreman Notes Sentry gaps |
| 2 GREEN | 896def4 | fix(quick-261030-suf): close Foreman Notes Sentry gaps |
| 3 | 101db40 | docs(quick-261030-suf): GF-lookup hold + Sentry docs |

## Verification evidence

- RED confirmed before each GREEN step. Task 1 had 23 failures (missing `gf_failed`, `load_gf_lookup`, `report_run_end` and the hold call sites). Task 2 had 18 failures (C1-C6 plus session_summary).
- Full suite (`SMARTSHEET_API_TOKEN= PYTHONUTF8=1 python -m pytest tests/ -q`): **2825 passed, 3 skipped**, 856 subtests. The baseline at 0143669 was 2788 passed, 3 skipped, so this adds 37 tests and introduces no new failures.
- `bash scripts/run_6_gates.sh`: **ALL 6 GATES PASSED**. Baseline names 164/164, allowlist 101/101, mypy delta 70 -> 69, py_compile clean, run_summary structure 30 keys.
- `python -m py_compile generate_weekly_pdfs.py`: OK.
- `git diff 0f5f825 --stat -- pipeline/change_detection.py pipeline/memory_candidate.py pipeline_memory/schema.sql .github/workflows`: **empty**.
- `npm --prefix website run typecheck` passed. `cd website && npm run build` reported `[SUCCESS]`, with no broken-link warnings.
- PII guard: the base64 pattern grep on every staged diff printed `0`, and on the full `0143669..HEAD` diff it also printed `0`.
- Done greps:
  - `_fn.should_hold_group(` in orchestrate: 1.
  - `def sentry_capture_foreman_notes`: 1.
  - `gf-lookup-failed` in foreman_notes.py: 1.
  - Task 3 doc greps were all at least 1.

## Deviations from Plan

1. **[Rule 1 - Bug] mypy gate (70 -> 71) after Task 2.** The annotated locals `_fn_held_groups: list = []` and `_fn_run_report: dict = {}` inside the untyped `main()` produced `annotation-unchecked` notes. The fix drops the annotations, so they are now plain `= []` / `= {}`, and the gate reads 70 -> 69. Commit 896def4.
2. **[Rule 2] `_fn_run_report = {}` is initialised beside `_fn_held_groups`.** This keeps the session_summary guard from raising NameError on any path that skips the post-loop assignment. The session_summary dict is built into `_session_summary`, `foreman_notes` is added only when the report is truthy, and the dict is then passed to `set_context`. Scope-off payload is unchanged.
3. **`report_run_end` "scope off" check uses the module `EFFECTIVE_SCOPE`, not `state.scope`.** In the approved outer-handler case (rule 4), the state is `FnState(gf_failed=True)` with `scope="off"`. A `state.scope` check would have silently skipped the hold event, so the check uses the run's effective scope, which the plan also uses for the `foreman_notes_scope` tag.
4. **Test infrastructure.** `SentryCapture` also passes `transport=_NullTransport` on top of `before_send` returning None, as belt and braces so nothing can leave. It also clears the three C5 run tags and the breadcrumbs from the isolation scope on setup and cleanup, so the global scope does not leak between tests. `test_foreman_notes_sentry.py` imports the fixtures and `SentryCapture` from `test_foreman_notes_gf_hold.py` and does not duplicate them.
5. **Cleanup tolerance tests.** These cover `dry_run=True` as the plan asked, and add a stronger `dry_run=False` case with a recording MagicMock client: a held identity plus an unchanged-skip identity in `valid_wr_weeks` give zero deletes. They are characterization tests and pass before and after the change, as expected, because the hold never touches cleanup.
6. **C3/C4 event `reason`.** The fixed values are `style_fetch_failed` and `notes_digest_failed`. The digest context carries `failures` (per function), `total` and `exception_classes`. The report dict keys are `style_failed_chunks`, `style_rows_affected`, `style_attach_failures`, `digest_failures` and `digest_failures_by_function`, plus `scope`, `gf_lookup` and `held_total`.
7. **Module docstring of `pipeline/foreman_notes.py`** now records the lazy `pipeline.observability` import and the owner-approved WR exception, so the old "never emits a WR" statement is no longer stale.

No pre-existing test asserted the `allowlist` breadcrumb key or the exact contents of `_PII_BREADCRUMB_DATA_KEYS`, so no existing assertion needed changing.

## Unverified / open concerns

- The hold and events have not run live. All coverage is offline: fake Smartsheet clients and a real `sentry_sdk.init` against an `.invalid` DSN with a null transport. No production run sets `FOREMAN_NOTES_UPLOAD`, so production billing output is unchanged today.
- The plan's reviewer flags still stand:
  - `_shadow_group_hashes` records the non-pilot-form hash for held groups, which affects parity only.
  - A pilot group with a missing attachment is also held during a failed run.
  - A `group_notes_token` failure inside a pilot group still drops `NOTES_FP` for that group. C4 now makes it visible, but the group is not held.
  - C5 run tags are set on scope-off production runs too. This is Sentry metadata only.
- `.planning/HANDOFF.json` was already modified in the working tree before this run, and it was left untouched and uncommitted.

## Known Stubs

None.

## Threat Flags

None. No new endpoint or auth path. The new Sentry surface is the one in the plan's threat model (T-261030suf-02..05, -07).

## Self-Check: PASSED

- Files exist: tests/test_foreman_notes_gf_hold.py, tests/test_foreman_notes_sentry.py, .planning/todos/pending/2026-10-30-wr-numbers-in-sentry-span-names.md.
- Commits on HEAD: 64857ee, 347d048, 1a24416, 896def4, 101db40 (`git rev-list --count 0143669..HEAD` = 5).

## Fix round (2026-10-30, owner decisions D1/D2, findings F1-F8)

### Commits

| Item | Commit | Subject |
|------|--------|---------|
| D1, D2, F1 ctx, F4 RED | 0cb74f8 | test(quick-261030-suf): RED ERROR level, no dry-run hold |
| D1, D2 GREEN | 282ea77 | fix(quick-261030-suf): ERROR-level events, no dry-run hold |
| F1, F2, F3, F5, F8, D1 cron RED | 5365035 | test(quick-261030-suf): RED orchestrate hold wiring |
| F1, F2, F3, F5, F8, D1 cron GREEN | 56c7d93 | fix(quick-261030-suf): gate purge, cron, parity on hold |
| F6, F7 RED | 4eeef77 | test(quick-261030-suf): RED held-WR cleanup protection |
| F7 GREEN | ec99bae | fix(quick-261030-suf): keep held WR files in cleanup |
| Docs | 327d3af | docs(quick-261030-suf): fix round D1/D2 + F1-F8 docs |

### What changed

- **D1:**
  - `gf-lookup-failed` and `gf-hold` are now level `error` on a publishing run. They stay `warning` in TEST_MODE, through `_failure_level()`.
  - The cron check-in is ERROR when `_fn_held_groups` is non-empty. `_fn_held_groups`, `_fn_run_report` and `_fn_purge_skipped` are hoisted beside `_session_failed`, so the finally block can always read them.
  - The runbook now says "held every run until the GF read works" and that the error events repeat each run.
- **D2:**
  - `gf_lookup_failed()` and `should_hold_group()` return False in TEST_MODE.
  - `FnState.gf_failed` and the `gf-lookup-failed` event (at warning) still fire.
- **F1:**
  - The purge block moved verbatim into `_run_reset_purge(client, hold_active, *, test_mode)`. Its lines were rewrapped to 79 chars, and `TEST_MODE` is passed in so main()'s facade late-binding is preserved.
  - While the lookup has failed, the purge is skipped with one counts-only WARNING. The hold event and the report carry `reset_purge_skipped`.
- **F2:** `report_run_end` now runs after `_memory_candidate.group_hash_globals_fingerprint()`.
- **F3:** a new pure helper `fn.stored_hash_matches(eligible, hash_unchanged, resolve)` replaces the inline expression. An AST test pins its arguments, and a test covers a forced run during a failed lookup holding only the mismatched pilot group.
- **F4:** probe-event leak tests after the hold event and after the lookup-failed event. They passed before the fix (characterization), which confirms the forked scope does not leak.
- **F5:**
  - `_fn_held_groups` is now a dict keyed by group_key. `unobservable=set(_no_target_row_groups) | set(_fn_held_groups)`, formatted so the existing source-text test in `test_skip_no_target_row.py` still finds its literal.
  - **Finding:** `compare_shadow_parity` never treats candidate-only groups as a divergence (D-07 as refined 2026-08-27). Held groups therefore could not cause `fail`; they only appeared as `only_in_candidate` noise. The test pins that real effect.
- **F6:** CleanupToleranceTests were rebuilt.
  - The held identity is derived from the group rows exactly as Site 2 does (canonical first row, `norm_wr`, `derive_group_identity`), and it equals `build_group_identity` of the real `generate_excel` filename.
  - The live run (`dry_run=False`) uses a recording client: it prunes the older duplicate and keeps the held newest.
- **F7, verified real:**
  - Before the fix, two kinds of cleanup branch could delete a held WR's only file while its replacement was being held:
    - the legacy-scope branches (`primary_wr_scope`, and by the same structure `sub_wr_scope` / `vac_legacy_wr_scope`);
    - the helper-migration-orphan branch.
  - Fix: `cleanup_untracked_sheet_attachments` gains a trailing kwarg `held_wr_weeks` (default None, so runs without a hold behave exactly as before). A held (wr, week) only goes through the per-identity older-duplicate pruning. The per-sheet `variant_whitelist` gate still applies.
  - main() passes `_fn_held_wr_weeks` to both the TARGET and PPP cleanups.
- **F8:**
  - The `⚡ Group processing phase` log line gains `, N held (GF lookup failed)`, only when the count is non-zero.
  - A new run tag `foreman_notes_held` comes from `observability.set_foreman_notes_held_tag`.
  - No run_summary.json key was added; the 30-key gate passes.

### Verification

- The full suite gave **2848 passed, 3 skipped**, 856 subtests. That is 2825 before the fix round, plus 23 new tests.
- `bash scripts/run_6_gates.sh` reported **ALL 6 GATES PASSED**, with mypy 70 -> 69.
- `py_compile` passed. The protected-file diff against 0f5f825 is **empty**.
- The website typecheck and build passed with `[SUCCESS]`.
- The GF-name pattern grep printed 0 on every staged diff and on the full `0143669..HEAD` diff.

### Deviations in the fix round

1. **The cleanup.py edit was not in the original plan's files.** It is the minimal additive change F7 needed, and cleanup.py is not on the protected list. The signature contract test `tests/test_security_audit_followup.py::test_cleanup_function_signature_unchanged` was updated **in place**, following its own documented rule [2026-05-20 00:26] 2. The kwarg list is now v8, with a default-None assertion for `held_wr_weeks`.
2. **My own Task 1 assertion was relaxed.** It required exactly one `_fn.gf_lookup_failed()` call; it now expects two (the hold branch plus the F1 purge gate).
3. **Test infrastructure.**
   - `fn_env()` gained `test_mode` (default False), and both test `_Base` classes pin `config.TEST_MODE=False`, so the D2 predicate is deterministic.
   - `SentryCapture.RUN_TAGS` now also clears `foreman_notes_held`.

### Not fixed / open

- Nothing from D1, D2 or F1-F8 was left unfixed.
- F5 is cosmetic for the verdict (see the finding above). It removes noise only, because held groups could never have caused `fail`.
- All coverage is still offline: fake clients, and Sentry with a null transport. The ERROR cron check-in is AST-tested, not run end to end.
- The earlier reviewer flags stand:
  - `_shadow_group_hashes` still records the non-pilot hash for held groups. It is now harmless for the verdict, because those groups are excluded from parity.
  - A `group_notes_token` failure in a pilot group is visible in Sentry but not held.

## Self-Check (fix round): PASSED

- Commits on HEAD: 0cb74f8, 282ea77, 5365035, 56c7d93, 4eeef77, ec99bae, 327d3af (`git rev-list --count 0143669..HEAD` = 12).
