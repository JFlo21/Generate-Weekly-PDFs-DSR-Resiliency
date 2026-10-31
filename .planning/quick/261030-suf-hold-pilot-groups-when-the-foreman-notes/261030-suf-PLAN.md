---
phase: quick-261030-suf
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - pipeline/foreman_notes.py
  - pipeline/orchestrate.py
  - tests/test_foreman_notes_gf_hold.py
  - tests/test_foreman_notes_state.py
  - memory-bank/living-ledger.md
  - website/docs/runbook/foreman-notes-pilot.md
autonomous: true
requirements:
  - TODO-2026-10-30-foreman-notes-gf-lookup-failure-churns-pilot-groups

estimate:
  tokens: 70000
  raw_tokens: 70000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "After a good pilot run, a run whose General Foreman lookup fails regenerates and re-uploads NO pilot group (owner decision 2026-10-30, option 1)"
    - "During a failed-lookup run, non-pilot groups whose hash matches the stored hash skip exactly as today, including the attachment-missing repair path"
    - "Scope off, scope all, empty allowlist and a good pilot lookup never enter the hold branch (gf_failed is False) - zero behaviour change"
    - "Held groups are carried as regeneration debt (never added to _mem_confirmed_skip_keys) and keep their stored hash and attachment"
    - "A failed-lookup run emits exactly one Sentry warning with no WR number, GF name or note text"
    - "pipeline/change_detection.py, pipeline/memory_candidate.py and pipeline_memory/schema.sql are unchanged"
  artifacts:
    - path: "pipeline/foreman_notes.py"
      provides: "FnState.gf_failed, gf_lookup_failed(), should_hold_group(), _warn_hold()"
      contains: "gf_failed"
    - path: "pipeline/orchestrate.py"
      provides: "hold branch in main() group loop, after the no-target gate, before the billing-audit freeze"
      contains: "_fn.should_hold_group("
    - path: "tests/test_foreman_notes_gf_hold.py"
      provides: "good-run -> failed-lookup -> recovery regression, accepted-cost case, AST ordering, cleanup tolerance"
  key_links:
    - from: "pipeline/foreman_notes.py initialize (gf_map is None branch)"
      to: "FnState(gf_failed=True) + _warn_hold()"
      via: "set_state"
      pattern: "gf_failed=True"
    - from: "pipeline/orchestrate.py main group loop"
      to: "pipeline/foreman_notes.py should_hold_group"
      via: "_fn.gf_lookup_failed() gate then continue"
      pattern: "_fn.gf_lookup_failed()"
---

<objective>
Stop a failed Foreman Notes General Foreman (GF) lookup from regenerating and re-uploading pilot
workbooks in the legacy (no-notes) layout. Per the owner decision of 2026-10-30 (todo
`2026-10-30-foreman-notes-gf-lookup-failure-churns-pilot-groups`, option 1): when the lookup fails
in a pilot-scope run, hold pilot groups for that run (no regeneration, no upload) and send one
Sentry warning. Option 2 (reuse last known pilot WR set) is rejected and MUST NOT be built.

Approach (from 261030-suf-RESEARCH.md, option (a)): nothing durable marks a group as pilot (the
only trace is the one-way `NOTES_FP=` suffix inside `content_hash`), so while the lookup has
failed a group is HELD iff its freshly computed hash differs from the stored hash. Every pilot
group loses `NOTES_FP`, so every pilot group is held. Unchanged non-pilot groups are untouched.

Purpose: this is the blocker for turning `FOREMAN_NOTES_UPLOAD` on. Production is unaffected
today (no workflow sets `FOREMAN_NOTES_UPLOAD`), and the new branch is inert unless the lookup
fails in an effective pilot scope.

Output: the hold (two modules), a TDD regression file, extended state tests, a living-ledger
entry, and a runbook note.

## Owner sign-off items (recommendations; flag these in the SUMMARY and PR, do not hide them)

1. **Force flags vs hold - recommend: hold wins for at-risk groups, logged.** Under
   `FORCE_GENERATION`, `REGEN_WEEKS`, `RESET_HASH_HISTORY` or `RESET_WR_LIST`, `_hash_unchanged`
   is forced False for every affected group. Using it directly would hold EVERY forced group,
   turning a force run into a no-op. The plan instead compares the hash to the stored hash
   independently of the force flags, only while the lookup has failed. Result: forced non-pilot
   groups whose hash still matches regenerate as the operator asked; pilot groups and changed
   groups are held. The run summary warning says the force flags did not override the hold.
   Cost: an operator cannot force-regenerate pilot groups until the lookup works again.
2. **One-run delay for changed or new NON-pilot groups - stated plainly.** While the lookup has
   failed, the pipeline cannot tell a changed pilot group from a changed non-pilot group, so
   every group with a real data change, and every brand-new group with no stored hash, is held
   for that run and carried as regeneration debt. It regenerates on the next run whose lookup
   succeeds. If the lookup keeps failing, those groups keep waiting; the per-run Sentry warning
   is the signal to fix the lookup. This is the unavoidable cost of option 1 without a persisted
   pilot marker (a schema change, which is out of bounds).
3. **Attachment cleanup tolerates a held group - verified, plus a test.** `valid_wr_weeks` is
   built from `groups` (all groups, `pipeline/orchestrate.py` Site 2 loop near line 5849), not
   from generated files, so a held group's identity stays live and its existing Smartsheet
   attachment is never pruned. `cleanup_stale_excels` only sees local files; a held group writes
   none, exactly like an unchanged skip. Task 2 adds a test.
4. **initialize's outer exception handler - recommend: set `gf_failed` only when the effective
   scope is pilot AND the configured allowlist is non-empty.** That handler currently returns
   `FnState()` (scope off), which would re-send pilot groups without notes. With the
   recommendation it returns `FnState(gf_failed=True)` (scope stays off, so notes stay inert,
   but the hold applies) and emits the same Sentry warning. Scope off/all or an empty allowlist
   keep today's `FnState()`.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md
@.planning/quick/261030-suf-hold-pilot-groups-when-the-foreman-notes/261030-suf-RESEARCH.md
@.planning/todos/pending/2026-10-30-foreman-notes-gf-lookup-failure-churns-pilot-groups.md

Interfaces the executor needs (verified at commit 0f5f825; re-grep line numbers before editing):

- `pipeline/foreman_notes.py`: `__all__` list ends at `"globals_component",` (~line 69);
  `@dataclass(frozen=True) class FnState` fields `scope`, `allowlist`, `pilot_wrs`, `gf_loaded`
  (~line 197); `_breadcrumb(**counts)` (~line 327, lazy `import sentry_sdk`, `try/except
  Exception: pass`); `initialize(client)` (~line 341) with the `gf_map is None` branch (~line 367)
  and the outer `except Exception` handler (~line 393); predicates `is_pilot_row` /
  `is_pilot_group` read module `_STATE` and never raise.
  `globals_component()` serializes only `scope`, `allowlist`, `pilot_wrs` explicitly, so a new
  FnState field does not move the shadow fingerprint.
- `pipeline/orchestrate.py` `main()` group loop: `_groups_skipped_no_target = 0` init (~line
  4089); `_history_eligible_for_skip` (~4473); `_hash_unchanged` via
  `_resolve_unchanged_for_skip(history_key, data_hash, _group_state_hashes, wr_num, week_iso,
  variant, identifier, billing_audit_writer=getattr(_gwp, "_billing_audit_writer", None))`
  (~4491); no-target gate ending in `continue` (~4559); billing-audit freeze `if` whose test
  contains `_has_uncached_freeze_candidates` (~4567); unchanged-skip adds
  `_mem_confirmed_skip_keys.add(group_key)` (~4962); `_fn.attach_group_styles` then
  `generate_excel` (~4977); post-loop summary `logging.info(f"⚡ Group processing phase: ...")`
  (~5166).
- `pipeline/change_detection.py:928` `_resolve_unchanged_for_skip(...)` - with
  `SUPABASE_HASH_STORE_AUTHORITATIVE` off it returns `group_state_hashes.get(history_key)['hash']
  == data_hash`; reads run-mode flags from the `generate_weekly_pdfs` facade. DO NOT EDIT.
- Tests: `tests/test_foreman_notes_pipeline.py` (`_target_sheet`, `_Sheets`, `_Client`, `_group`,
  `_Base.pilot_patches`, `TracerTests` ~119-183 as the initialize-then-hash template; AST helpers
  `_func`, `_calls`, `_uses_fn`, `ORCH_TREE`; `test_fn_references_confined_to_expected_functions`
  already allows `main`). `tests/test_foreman_notes_state.py` `InitializeTests._init(scope,
  allowlist, client)`, `_client(exc=...)`, `test_gf_failure_yields_no_pilot` (~296).
  `tests/test_orphaned_primary_attachment.py:129` shows how to call
  `cleanup_untracked_sheet_attachments` with a fake client.
</context>

<tasks>

<task type="tracer" tdd="true">
  <name>Task 1: Tracer - good run, then failed GF lookup, holds every pilot group in main()</name>
  <files>tests/test_foreman_notes_gf_hold.py, pipeline/foreman_notes.py, pipeline/orchestrate.py</files>
  <behavior>
    - Good run (scope pilot, allowlist "GF-1", target sheet maps WR 90003 to GF-1 and 90004 to GF-2): state.gf_loaded True, state.gf_failed False; store both group hashes as group_state_hashes {history_key: {"hash": h}}.
    - Failed run (fn.reset_state(), target-sheet get_sheet raises RuntimeError): state.gf_failed True, pilot_wrs empty.
    - Pilot group 90003: recomputed hash differs from stored, _resolve_unchanged_for_skip returns False, fn.should_hold_group(False) is True.
    - Non-pilot group 90004 unchanged: _resolve_unchanged_for_skip True, fn.should_hold_group(True) False.
    - Accepted cost (owner item 2): 90004 with one changed Quantity is held during the failed run.
    - Recovery: a following good run recomputes the 90003 hash equal to the good-run stored hash, so nothing re-sends after the outage.
    - Good lookup run: fn.gf_lookup_failed() False and fn.should_hold_group(False) False.
    - AST: in main, exactly one _fn.gf_lookup_failed() and one _fn.should_hold_group( call; the hold If sits after the should_skip_no_target_row call and before the If whose test contains _has_uncached_freeze_candidates and before generate_excel; its body ends in continue and never references _mem_confirmed_skip_keys, groups mutation, or generated_filenames.
  </behavior>
  <action>
RED first: create tests/test_foreman_notes_gf_hold.py covering the behavior block, run it, confirm it fails (AttributeError on gf_failed / should_hold_group), and commit as test(quick-261030-suf). Build fixtures by mirroring the _target_sheet / _Sheets / _Client / _group shapes from tests/test_foreman_notes_pipeline.py, but use only GF aliases GF-1, GF-2 (never a real name; do not reuse the existing synthetic allowlist string). Patch fn.EFFECTIVE_SCOPE, config.FOREMAN_NOTES_PILOT_GFS and the GF column-id config exactly as TracerTests does, wrap hashing in golden.pinned_env like TracerTests, and patch gwp.SUPABASE_HASH_STORE_AUTHORITATIVE False so _resolve_unchanged_for_skip uses the dict path. Build history_key as the WR|week_iso|variant|identifier string main() uses. Reset fn state in setUp and via addCleanup.

GREEN, pipeline/foreman_notes.py (per owner decision 2026-10-30 option 1): add field gf_failed: bool = False as the LAST FnState field (keeps positional order and FnState() equality for every existing caller). In initialize's gf_map-is-None branch build FnState(scope=scope, allowlist=allowlist, gf_failed=True) and call a new _warn_hold(allowlist_count). Add _warn_hold next to _breadcrumb: lazy import sentry_sdk, then inside sentry_sdk.isolation_scope() set tag foreman_notes_hold to gf_lookup_failed, fingerprint ["foreman-notes-gf-lookup-hold"], and capture_message at level warning with fixed text such as "Foreman notes: GF lookup failed; changed groups held this run"; the allowlist count may go in a tag or extra; never a WR, GF name or note; whole body in try/except Exception: pass (same never-raises convention; mirror sentry_capture_sheet_drop in pipeline/observability.py for the isolation-scope shape). Add two predicates after is_pilot_group, both never raise and return False on error: gf_lookup_failed() returns _STATE.gf_failed; should_hold_group(hash_matches_stored) returns _STATE.gf_failed and not hash_matches_stored. Append "gf_lookup_failed" and "should_hold_group" to __all__.

GREEN, pipeline/orchestrate.py main() only (the AST confinement test allows _fn only in main and four memory functions): initialize _groups_held_gf = 0 beside _groups_skipped_no_target = 0. Immediately after the no-target gate's continue and BEFORE the billing-audit freeze if, add: if _fn.gf_lookup_failed(): compute the stored-hash match as _hash_unchanged when _history_eligible_for_skip is True, otherwise call _resolve_unchanged_for_skip with the same arguments the _hash_unchanged expression uses (owner item 1: force flags do not override the hold for at-risk groups; this extra lookup happens only in failed-lookup runs). If _fn.should_hold_group(that match) is True, increment _groups_held_gf and continue. Do NOT add the group to _mem_confirmed_skip_keys (so _regen_debt_finish_kwargs carries it as debt), do not touch groups, generated_filenames, upload tasks or group_state, and do not log WR text per group. After the loop, beside the existing "Group processing phase" log (leave that line's text unchanged), emit logging.warning only when _groups_held_gf is non-zero: counts only, stating the groups were held because the Foreman Notes GF lookup failed and are carried as regeneration debt, and appending a note that force/regen flags did not override the hold when FORCE_GENERATION, REGEN_WEEKS, RESET_HASH_HISTORY or RESET_WR_LIST is set. Do not edit pipeline/change_detection.py, calculate_data_hash, pipeline/memory_candidate.py or pipeline_memory/schema.sql. Commit as fix(quick-261030-suf).
  </action>
  <verify>
    <automated>SMARTSHEET_API_TOKEN= PYTHONUTF8=1 python -m pytest tests/test_foreman_notes_gf_hold.py tests/test_foreman_notes_pipeline.py -q</automated>
  </verify>
  <done>New test file fails before the change and passes after; test_foreman_notes_pipeline.py (including the _fn confinement and attach-ordering AST tests) stays green; grep -c "_fn.should_hold_group(" pipeline/orchestrate.py returns 1 (baseline 0); git diff --exit-code 0f5f825 -- pipeline/change_detection.py pipeline/memory_candidate.py pipeline_memory/schema.sql exits 0.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Edge cases - zero-change scopes, outer handler, Sentry PII, cleanup tolerance</name>
  <files>tests/test_foreman_notes_state.py, tests/test_foreman_notes_gf_hold.py, pipeline/foreman_notes.py</files>
  <behavior>
    - InitializeTests: gf_failed False for scope off, scope all, empty allowlist, and a good lookup; True in test_gf_failure_yields_no_pilot.
    - Outer handler (owner item 4): fn.load_gf_map patched to raise, scope pilot, allowlist "GF-1" -> state.gf_failed True, state.scope "off", pilot_wrs empty, one Sentry warning. reset_style_cache patched to raise with scope off -> state == fn.FnState() (gf_failed False). Same with scope pilot and an empty allowlist -> gf_failed False.
    - Sentry: on a failed lookup sentry_sdk.capture_message is called exactly once, level "warning", and its message plus any tags/extras contain no "GF-1", "GF-2", "90003", "90004"; a good lookup and scope off call it zero times.
    - Predicates never raise: should_hold_group and gf_lookup_failed return False when _STATE is replaced by a non-FnState object.
    - Cleanup tolerance (owner item 3): cleanup_untracked_sheet_attachments in dry_run with valid_wr_weeks containing the held group's identity (as Site 2 builds it from groups) deletes nothing for that identity - identical to an unchanged-skip identity; plus an AST check that the Site 2 valid_wr_weeks loop iterates groups.items().
  </behavior>
  <action>
RED first: add the behavior tests (state tests in tests/test_foreman_notes_state.py InitializeTests; outer-handler, Sentry, predicate-robustness and cleanup tests in tests/test_foreman_notes_gf_hold.py), run, confirm the outer-handler test fails, commit as test(quick-261030-suf).

GREEN, pipeline/foreman_notes.py initialize outer except handler (owner item 4 recommendation): after logging the exception class, decide failed inside its own try/except (fallback False) as EFFECTIVE_SCOPE == "pilot" and bool(parse_allowlist(config.FOREMAN_NOTES_PILOT_GFS)); when failed, build FnState(gf_failed=True) and call _warn_hold with the allowlist count; otherwise keep FnState() exactly. This reads config directly, so it is correct wherever inside the try the exception was raised. Scope off/all and empty allowlist keep today's state, so ZeroImpactTests.test_off_scope_makes_zero_calls_and_leaves_rows_unchanged (asserts state == fn.FnState()) stays green.

For the Sentry test patch sentry_sdk.capture_message (the lazy import resolves the module attribute) and inspect call args; keep the real isolation_scope. For cleanup, mirror the fake-client call pattern at tests/test_orphaned_primary_attachment.py:129 with dry_run=True; build the identity tuple the same way the orchestrate Site 2 loop does. If the behavioural cleanup test cannot be built without driving main(), keep the AST assertion and document in the SUMMARY that held and unchanged-skip groups present identical inputs to both cleanup functions (no new file, identity in valid_wr_weeks). Commit as fix(quick-261030-suf).

Then run the full suite and the 6-gate harness (facade-completeness and AST import-equality gates cover pipeline/ edits). If a pre-existing test asserts a full FnState equality on the failure path, update that assertion to include gf_failed=True and note it in the SUMMARY; do not weaken any other assertion.
  </action>
  <verify>
    <automated>SMARTSHEET_API_TOKEN= PYTHONUTF8=1 python -m pytest tests/test_foreman_notes_gf_hold.py tests/test_foreman_notes_state.py -q && SMARTSHEET_API_TOKEN= PYTHONUTF8=1 python -m pytest tests/ -q && bash scripts/run_6_gates.sh</automated>
  </verify>
  <done>All new edge tests pass; full suite passes with zero new failures versus the 0f5f825 baseline; run_6_gates.sh passes; python -m py_compile generate_weekly_pdfs.py exits 0.</done>
</task>

<task type="auto">
  <name>Task 3: Living-ledger entry and runbook note for the hold</name>
  <files>memory-bank/living-ledger.md, website/docs/runbook/foreman-notes-pilot.md</files>
  <action>
Append ONE dated entry at the very bottom of memory-bank/living-ledger.md, header format "## [2026-10-30 HH:MM] Foreman Notes: hold changed groups when the GF lookup fails." (match the existing header style; never edit earlier entries). Body, concise: rule (pilot scope + non-empty allowlist + failed GF lookup sets FnState.gf_failed; main() holds every group whose hash differs from the stored hash, after the no-target gate and before the billing-audit freeze; held groups are regeneration debt, never confirmed skips); why (no durable pilot marker; NOTES_FP is one-way; schema change out of bounds; option 2 rejected); costs and owner sign-off items 1, 2 and 4 from this plan's objective; that the open item recorded in the 2026-10-30 13:50 entry is now closed by quick 261030-suf; evidence = the new test file. No GF names, no WR numbers from production.

In website/docs/runbook/foreman-notes-pilot.md add a short section "If the General Foreman lookup fails" (place it after "When the pilot actually renders" or inside "Rollout" - whichever reads better), written for the on-call operator and stating the owning component is the Python billing pipeline: what the operator sees (one Sentry warning tagged foreman_notes_hold=gf_lookup_failed; a run-summary warning with a held-group count), what happens (pilot files are not re-sent; changed or new non-pilot groups also wait one run; force/regen flags do not override the hold for these groups), and what to do (fix the target-sheet GF column access; the next good run regenerates the held groups from regeneration debt; no RESET_* needed). Rewrite, do not append stale text; keep cross-links valid. Use GF-1 style aliases if any example is needed.
  </action>
  <verify>
    <automated>tail -n 20 memory-bank/living-ledger.md | grep -c "gf_failed" && grep -c "foreman_notes_hold" website/docs/runbook/foreman-notes-pilot.md && npm --prefix website run typecheck</automated>
  </verify>
  <done>Ledger tail contains the new entry (grep count >= 1, baseline 0); runbook has the new section (grep count >= 1, baseline 0); website typecheck passes; commit as docs(quick-261030-suf).</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Smartsheet target sheet -> pipeline | GF lookup result (may fail or be unreadable) decides pilot membership |
| pipeline -> Smartsheet attachments | regenerated billing workbooks uploaded to the target sheet |
| pipeline -> Sentry / Actions logs | warning text and tags leave the runner; WR numbers and GF names are PII-adjacent |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-261030suf-01 | Tampering | orchestrate main() group loop | high | mitigate | Failed lookup can no longer replace pilot workbooks with no-notes versions: hold before billing-audit freeze, generate_excel and upload (Task 1 AST + sequence tests) |
| T-261030suf-02 | Information disclosure | foreman_notes._warn_hold, run-summary warning | medium | mitigate | Fixed message text, counts only, isolation_scope so tags never leak onto later events; Task 2 test asserts no alias or WR appears in message/tags |
| T-261030suf-03 | Denial of service | changed/new non-pilot groups during a failed run | low | accept | One-run delay, carried as regeneration debt; owner sign-off item 2; per-run Sentry warning drives the fix |
| T-261030suf-04 | Repudiation | held groups | low | mitigate | Run-summary held count + Sentry fingerprint foreman-notes-gf-lookup-hold + debt carry make every hold visible |
| T-261030suf-05 | Tampering | attachment cleanup | medium | mitigate | Held identities stay in valid_wr_weeks (built from groups); Task 2 cleanup test |
| T-261030suf-SC | Tampering | npm/pip/cargo installs | high | mitigate | No package installs in this plan; no new dependency (sentry-sdk>=2.54.0 already pinned) |
</threat_model>

<verification>
Run from repo root:
- SMARTSHEET_API_TOKEN= PYTHONUTF8=1 python -m pytest tests/test_foreman_notes_gf_hold.py -q
- SMARTSHEET_API_TOKEN= PYTHONUTF8=1 python -m pytest tests/ -q
- bash scripts/run_6_gates.sh
- python -m py_compile generate_weekly_pdfs.py
- git diff --exit-code 0f5f825 -- pipeline/change_detection.py pipeline/memory_candidate.py pipeline_memory/schema.sql
- npm --prefix website run build (docs rule: typecheck + build before push)
Reviewer flags: `_shadow_group_hashes` still records the non-pilot-form hash for held groups (parity-only, no production effect); a pilot group with a missing attachment is also held during a failed run (repairs on the next good run).
</verification>

<success_criteria>
- Good run -> failed lookup: no pilot group reaches generate_excel or upload; recovery run re-sends nothing.
- Scope off / all / empty allowlist / good lookup: gf_failed False and the hold branch is never entered; full suite green.
- One Sentry warning per failed-lookup run, PII-free.
- Owner sign-off items 1-4 listed in the SUMMARY and PR description.
- Ledger and runbook updated; protected files untouched.
</success_criteria>

<output>
Create `.planning/quick/261030-suf-hold-pilot-groups-when-the-foreman-notes/261030-suf-SUMMARY.md` when done
</output>
