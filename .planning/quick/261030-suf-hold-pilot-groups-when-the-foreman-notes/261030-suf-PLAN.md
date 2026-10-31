---
phase: quick-261030-suf
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - pipeline/foreman_notes.py
  - pipeline/observability.py
  - pipeline/orchestrate.py
  - tests/test_foreman_notes_gf_hold.py
  - tests/test_foreman_notes_state.py
  - tests/test_foreman_notes_sentry.py
  - docs/DECISIONS.md
  - docs/sentry-implementation.md
  - memory-bank/living-ledger.md
  - website/docs/runbook/foreman-notes-pilot.md
  - .planning/todos/pending/2026-10-30-wr-numbers-in-sentry-span-names.md
autonomous: true
requirements:
  - TODO-2026-10-30-foreman-notes-gf-lookup-failure-churns-pilot-groups

estimate:
  tokens: 130000
  raw_tokens: 130000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "After a good pilot run, a run whose General Foreman lookup fails regenerates and re-uploads NO pilot group (owner decision 2026-10-30, option 1)"
    - "During a failed-lookup run, non-pilot groups whose hash matches the stored hash skip exactly as today, including the attachment-missing repair path; forced groups whose hash still matches regenerate as forced"
    - "Scope off, scope all, empty allowlist and a good pilot lookup never enter the hold branch (gf_failed is False) - zero billing-output change"
    - "Held groups are carried as regeneration debt (never added to _mem_confirmed_skip_keys) and keep their stored hash and attachment"
    - "A failed lookup sends its own Sentry event (fingerprint foreman-notes / gf-lookup-failed / reason) naming the reason, exception class, redacted message, sheet and column IDs checked and remediation, even when no group is held"
    - "When groups are held, exactly one hold event per run (fingerprint foreman-notes / gf-hold) carries the held WR list in the structured foreman_notes context; GF names and note text never appear in any event"
    - "memory_write_blocked, style-fetch and notes-digest failures are visible in Sentry (scoped tags/fingerprints or one run-end warning) instead of failing silently"
    - "pipeline/change_detection.py, calculate_data_hash, pipeline/memory_candidate.py, pipeline_memory/schema.sql and .github/workflows are unchanged"
  artifacts:
    - path: "pipeline/foreman_notes.py"
      provides: "FnState.gf_failed / gf_fail_reason / gf_fail_exc / gf_fail_msg, load_gf_lookup(), gf_lookup_failed(), should_hold_group(), per-run failure counters, report_run_end()"
      contains: "gf_fail_reason"
    - path: "pipeline/observability.py"
      provides: "sentry_capture_foreman_notes() on sentry_sdk.new_scope(), foreman_notes_scope() context manager, set_foreman_notes_run_tags(), Foreman Notes PII breadcrumb keys"
      contains: "def sentry_capture_foreman_notes"
    - path: "pipeline/orchestrate.py"
      provides: "hold branch in main() after the no-target gate and before the billing-audit freeze; run-end _fn.report_run_end call; Foreman Notes counts in session_summary"
      contains: "_fn.should_hold_group("
    - path: "tests/test_foreman_notes_gf_hold.py"
      provides: "good run -> failed lookup -> recovery regression, accepted-cost case, AST ordering, hold-event payload, cleanup tolerance"
    - path: "tests/test_foreman_notes_sentry.py"
      provides: "event-payload tests for every Foreman Notes Sentry path (WR present only in context, GF alias absent, notes absent)"
  key_links:
    - from: "pipeline/foreman_notes.py initialize (lookup failed)"
      to: "pipeline/observability.py sentry_capture_foreman_notes"
      via: "lazy import, fingerprint foreman-notes/gf-lookup-failed/<reason>"
      pattern: "gf-lookup-failed"
    - from: "pipeline/orchestrate.py main group loop"
      to: "pipeline/foreman_notes.py should_hold_group"
      via: "_fn.gf_lookup_failed() gate then continue"
      pattern: "_fn.gf_lookup_failed()"
    - from: "pipeline/orchestrate.py after group loop"
      to: "pipeline/foreman_notes.py report_run_end -> hold / style / digest events"
      via: "_fn.report_run_end(held_groups=..., force_flags=...)"
      pattern: "_fn.report_run_end("
---

<objective>
Stop a failed Foreman Notes General Foreman (GF) lookup from regenerating and re-uploading pilot
workbooks in the legacy (no-notes) layout, and make every Foreman Notes failure visible in Sentry
with enough detail to audit and fix it.

Owner decisions (2026-10-30):
- Todo `2026-10-30-foreman-notes-gf-lookup-failure-churns-pilot-groups`, option 1: hold pilot
  groups for the run (no regeneration, no upload). Option 2 (reuse last known pilot WR set) is
  rejected and MUST NOT be built.
- APPROVED as planned: (1) the hold wins over force flags for at-risk groups. While the lookup
  has failed, each group's hash is compared with the stored hash regardless of force flags.
  Forced groups whose hash still matches regenerate as forced; pilot groups and changed groups
  are held, and this is logged. (2) Changed and new non-pilot groups wait one run while the
  lookup is failing. (3) The attachment cleanup check stands. (4) The outer handler sets
  `gf_failed` only when the effective scope is pilot and the configured allowlist is non-empty.
- WR policy exception (owner-approved): Foreman Notes Sentry events may carry WR numbers, but
  only inside a dedicated structured context `foreman_notes`. That context is set on a forked
  scope (`sentry_sdk.new_scope()`), never on the shared scope. The general
  `_redact_exception_message` WR redaction stays unchanged for all other events. GF names are
  never sent (counts only) and note text is never sent. The exception is recorded in
  docs/DECISIONS.md.
- Sentry gap closure C1-C6. C1: a GF lookup or initialize failure sends its own event, and
  `_breadcrumb` uses a distinct message on failure. C2: memory_write_blocked tags and
  fingerprint. C3: style-failure counters. C4: notes-digest failure counters. C5: run-level
  tags. C6: PII key/marker defence in depth.
- Out of scope: WR numbers already in existing span names. Recorded only as a follow-up todo.

Approach for the hold (261030-suf-RESEARCH.md, option (a)): nothing durable marks a group as
pilot. The only trace is the one-way `NOTES_FP=` suffix inside `content_hash`. So while the lookup
has failed, a group is HELD iff its freshly computed hash differs from the stored hash. Every pilot
group loses `NOTES_FP` and is therefore held. Unchanged non-pilot groups are untouched.

Purpose: this is the blocker for turning `FOREMAN_NOTES_UPLOAD` on. Production billing output
is unaffected today: no workflow sets `FOREMAN_NOTES_UPLOAD`, and the hold branch is inert
unless the lookup fails in an effective pilot scope.

Output: the hold, the Sentry instrumentation, three test files, the decision record, docs, and a
follow-up todo.

Context budget note for the executor: this plan is large (~130k projected). Run each task in a
fresh executor context if the runtime allows. Commit after every RED and GREEN step.
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

Interfaces the executor needs. These were verified at commit 0f5f825; re-grep line numbers
before editing.

- `pipeline/foreman_notes.py`
  - `__all__` ends at `"globals_component",` (~69).
  - `memory_write_blocked(kind)` (~160) logs ERROR once per kind. `LoggingIntegration(event_level=logging.ERROR)` turns that log into a Sentry event on the CURRENT scope.
  - `@dataclass(frozen=True) class FnState` (~197) has fields `scope`, `allowlist`, `pilot_wrs`, `gf_loaded`.
  - `reset_state()` (~218) clears `_BLOCKED_KINDS_LOGGED` and the style cache.
  - `load_gf_map(client, sheet_id, wr_col_id, gf_col_id)` (~264) returns `dict | None`. It returns None on: title mismatch (~283-290, expected titles `_GF_WR_TITLE` "Work Request #" and `_GF_TITLE` "General Foreman"); partial read (~293-301); any exception (~319). Tests call it directly 7 times and never patch it.
  - `_breadcrumb(**counts)` (~327) always sends message "initialized" at level info.
  - `initialize(client)` (~341) has the `gf_map is None` branch (~367) and an outer `except` (~393) that returns `FnState()`.
  - Style failures: chunk `except` (~630) and outer `attach_group_styles` `except` (~647).
  - Digest failures: `row_notes_component` (~679, returns None), `group_notes_token` (~713, returns ''), `globals_component` (~731, returns '').
  - `globals_component` serializes only scope/allowlist/pilot_wrs, so new FnState fields do not move the shadow fingerprint.
- `pipeline/observability.py`
  - `SENTRY_DSN` gate.
  - `_redact_exception_message(exc)` (~68). Do not change it.
  - `_notes_may_be_in_frames()` (~192) and `_scrub_sheet_drop_frame_vars(event)` (~205) strip frame vars from EVERY event while the notes mapping is on.
  - `sentry_capture_sheet_drop` (~221) is the model to follow: it uses `isolation_scope`, tags, a fingerprint and `capture_message`.
  - `_PII_LOG_MARKERS` (~381) uses SUBSTRING matching on log text.
  - `_PII_BREADCRUMB_DATA_KEYS` (~577) uses exact lowercase key match on breadcrumb `data` only. It never touches event `contexts`.
  - `sentry_before_breadcrumb` (~631).
  - `before_send_filter` is nested inside `init_sentry` (~801) and calls `_scrub_sheet_drop_frame_vars`.
  - Installed sentry-sdk is 2.63.0: `sentry_sdk.new_scope()` exists.
- `pipeline/orchestrate.py` `main()`
  - `_fn.initialize(client)` (~3059).
  - `_groups_skipped_no_target = 0` (~4089).
  - `_history_eligible_for_skip` (~4473).
  - `_hash_unchanged` comes from `_resolve_unchanged_for_skip(history_key, data_hash, _group_state_hashes, wr_num, week_iso, variant, identifier, billing_audit_writer=getattr(_gwp, "_billing_audit_writer", None))` (~4491).
  - The no-target gate ends with `continue` (~4559). Its dict values are `(wr_num, week_raw, variant)`.
  - The billing-audit freeze `if` has a test containing `_has_uncached_freeze_candidates` (~4567).
  - The unchanged skip adds `_mem_confirmed_skip_keys.add(group_key)` (~4962).
  - `_fn.attach_group_styles` is followed by `generate_excel` (~4977).
  - Post-loop "Group processing phase" log (~5166).
  - Site 2 builds `valid_wr_weeks` from `groups.items()` (~5849).
  - `sentry_sdk.set_context("session_summary", {...})` (~6354).
- `pipeline/change_detection.py:928` `_resolve_unchanged_for_skip`. With `SUPABASE_HASH_STORE_AUTHORITATIVE` off it compares `group_state_hashes[history_key]['hash']`. DO NOT EDIT.
- Tests:
  - `tests/test_foreman_notes_pipeline.py`: `_target_sheet`, `_Sheets`, `_Client`, `_group`, `_Base`; `TracerTests` (~119-183) is the template; AST helpers `_func`, `_calls`, `_uses_fn`, `ORCH_TREE`; `test_fn_references_confined_to_expected_functions` already allows `main`; `ZeroImpactTests` asserts `state == fn.FnState()` for scope off.
  - `tests/test_foreman_notes_state.py`: `InitializeTests._init(scope, allowlist, client)`, `_client(exc=...)`, `test_gf_failure_yields_no_pilot` (~296).
  - `tests/test_orphaned_primary_attachment.py:129` calls `cleanup_untracked_sheet_attachments` with a fake client.
  - No fake Sentry transport exists in tests/. `tests/test_sentry_log_sanitizer.py:787` shows real `sentry_sdk.init(dsn=None, ...)` usage, and `tests/test_sentry_frame_var_scrub.py` imports `_scrub_sheet_drop_frame_vars`.
- `docs/DECISIONS.md` is a stub that points to the living ledger as canonical. Per the owner, add a dated entry here anyway, linking the ledger.

Event-capture test pattern (all payload tests). Inside the test:
- Call real `sentry_sdk.init(dsn="https://public@o0.ingest.invalid/0", include_local_variables=True, attach_stacktrace=True, before_breadcrumb=observability.sentry_before_breadcrumb, before_send=<capture>)`. `<capture>` runs `observability._scrub_sheet_drop_frame_vars(event)`, appends the event to a list, and returns None, so nothing is ever sent.
- Patch `observability.SENTRY_DSN` to a non-empty string.
- On cleanup, call `sentry_sdk.init(dsn=None)`.
- Assert on `json.dumps(event, default=str)`.
</context>

<tasks>

<task type="tracer" tdd="true">
  <name>Task 1: Tracer - failed GF lookup after a good run holds pilot groups and sends one hold event</name>
  <files>tests/test_foreman_notes_gf_hold.py, tests/test_foreman_notes_state.py, pipeline/foreman_notes.py, pipeline/observability.py, pipeline/orchestrate.py</files>
  <behavior>
    - Good run (scope pilot, allowlist "GF-1"; target sheet maps WR 90003 to GF-1 and WR 90004 to GF-2): gf_loaded True, gf_failed False. Store both group hashes as group_state_hashes {history_key: {"hash": h}}.
    - Failed run (fn.reset_state(); the target-sheet get_sheet raises RuntimeError): gf_failed True, gf_fail_reason "exception", gf_fail_exc "RuntimeError", pilot_wrs empty. A titles mismatch gives "columns_mismatch". total_row_count above the returned row count gives "partial_read".
    - In the failed run, pilot group 90003: _resolve_unchanged_for_skip False and fn.should_hold_group(False) True. Unchanged 90004: unchanged True and should_hold_group(True) False. 90004 with a changed Quantity: held (approved cost).
    - Recovery: the next good run's 90003 hash equals the good-run stored hash, so nothing re-sends.
    - On a good lookup, scope off, scope all or an empty allowlist: gf_lookup_failed() False and should_hold_group(False) False. ZeroImpactTests still sees FnState() for scope off.
    - Outer handler (approved rule 4): fn.load_gf_lookup patched to raise, scope pilot, allowlist "GF-1" -> gf_failed True, gf_fail_reason "initialize_failed", scope "off". reset_style_cache raising with scope off, or with scope pilot and an empty allowlist -> state == fn.FnState().
    - Hold event: fn.report_run_end(held_groups=[("90003","081025","primary")], force_flags={...}) captures exactly ONE event:
      - level warning, fingerprint ["foreman-notes","gf-hold"], tags foreman_notes_scope and foreman_notes_reason;
      - contexts.foreman_notes holds reason, exception_class, exception_message, target_sheet_id, wr_column_id, gf_column_id, expected_titles, held_groups [{wr, week_ending, variant}], held_total, force_flags_active, remediation, and run_url when the GITHUB_* vars are set;
      - "90003" appears in contexts.foreman_notes; "GF-1", "GF-2" and the note sentinel text appear nowhere in the event;
      - zero events when held_groups is empty.
    - held_groups is capped at 200 entries, and held_total carries the full count (test with 205).
    - AST checks on main:
      - exactly one _fn.gf_lookup_failed() call, one _fn.should_hold_group( call and one _fn.report_run_end( call;
      - the hold If sits after the should_skip_no_target_row call, before the If whose test contains _has_uncached_freeze_candidates, and before generate_excel;
      - the hold body ends in continue and never references _mem_confirmed_skip_keys or generated_filenames, and never mutates groups.
  </behavior>
  <action>
RED first. Create tests/test_foreman_notes_gf_hold.py covering the sequence, the accepted-cost case, the recovery, the hold-event payload, the cap and the AST checks. Extend tests/test_foreman_notes_state.py InitializeTests with the gf_failed, reason and outer-handler cases. Run them, confirm they fail, and commit as test(quick-261030-suf).
- Fixtures: mirror _target_sheet, _Sheets, _Client and _group from tests/test_foreman_notes_pipeline.py, but use only the GF aliases GF-1 and GF-2. Never use a real name, and do not reuse the existing synthetic allowlist string.
- Patch fn.EFFECTIVE_SCOPE, config.FOREMAN_NOTES_PILOT_GFS and the GF column-id config exactly as TracerTests does, and wrap hashing in golden.pinned_env.
- Patch gwp.SUPABASE_HASH_STORE_AUTHORITATIVE to False so _resolve_unchanged_for_skip uses the dict path.
- Build history_key as the WR|week_iso|variant|identifier string main() builds.
- Use the event-capture pattern from the context section for the hold-event tests.

GREEN, pipeline/observability.py (per the owner's WR policy exception):
- Add foreman_notes_scope(tags, fingerprint), a context manager. It yields a sentry_sdk.new_scope() scope with the given tags and fingerprint, and yields None (no-op) when SENTRY_DSN is unset or the SDK raises.
- Add sentry_capture_foreman_notes(kind, level, reason, context, fingerprint). Model it on sentry_capture_sheet_drop, but use new_scope and never the shared scope:
  - return early without SENTRY_DSN;
  - inside foreman_notes_scope, set tags foreman_notes_scope (the effective scope) and foreman_notes_reason (reason);
  - call scope.set_context("foreman_notes", context);
  - capture_message with a fixed text per kind (for example "Foreman notes: GF lookup failed (reason)" or "Foreman notes: groups held after GF lookup failure"). The text never contains a WR number, a GF name or a note;
  - wrap the whole body in try/except Exception and pass.
- Add _github_run_url(), which returns GITHUB_SERVER_URL/GITHUB_REPOSITORY/actions/runs/GITHUB_RUN_ID only when all three are set, and None otherwise. Add a module constant FOREMAN_NOTES_REMEDIATION with three fixed steps:
  1. Check the General Foreman and Work Request # column titles and IDs on the pre-planned pricing (target) sheet against FOREMAN_NOTES_GF_COLUMN_ID / FOREMAN_NOTES_GF_WR_COLUMN_ID.
  2. Check the API token's sheet permissions.
  3. The next run with a working lookup self-heals from regeneration debt; no RESET_* is needed.

GREEN, pipeline/foreman_notes.py:
- Add load_gf_lookup(client, sheet_id, wr_col_id, gf_col_id). It returns a NamedTuple GfLookup(gf_map, reason, exc), with reason "" on success, "columns_mismatch", "partial_read" or "exception". Move the body of load_gf_map into it, keeping every existing log line. load_gf_map becomes a one-line wrapper returning .gf_map, so its contract and its 7 direct test callers are unchanged.
- Add these FnState fields, LAST and in this order, so FnState() equality holds for every existing caller: gf_failed: bool = False, gf_fail_reason: str = "", gf_fail_exc: str = "", gf_fail_msg: str = "". gf_fail_msg is the redacted message, from a lazy import of observability._redact_exception_message (fallback "").
- initialize calls load_gf_lookup. On failure it builds FnState(scope, allowlist, gf_failed=True, plus the reason fields).
- In the outer except, decide failed inside its own try/except (fallback False) as EFFECTIVE_SCOPE == "pilot" and bool(parse_allowlist(config.FOREMAN_NOTES_PILOT_GFS)). When failed, build FnState(gf_failed=True, gf_fail_reason="initialize_failed", gf_fail_exc=<class>, gf_fail_msg=<redacted>). Otherwise keep FnState() exactly.
- Add the predicates gf_lookup_failed() and should_hold_group(hash_matches_stored). The latter returns _STATE.gf_failed and not hash_matches_stored. Both never raise; they return False on error.
- Add report_run_end(held_groups, force_flags). It returns a counts-only dict, or {} when the scope is off. When held_groups is non-empty it:
  - logs one counts-only logging.warning that says the groups were held because the GF lookup failed and are carried as regeneration debt, and says whether force/regen flags were active and did not override the hold;
  - calls observability.sentry_capture_foreman_notes(kind="gf_hold", level="warning", reason=state.gf_fail_reason, fingerprint=["foreman-notes","gf-hold"]) with the full context listed in the behavior block. held_groups entries are dicts {wr, week_ending, variant}, capped at 200, with held_total. variant is the group variant enum only; never pass the identifier, a foreman name or a helper name.
- Add the new public names to __all__. Use lazy observability imports inside the functions; observability already lazily imports foreman_notes, so a top-level import would create a cycle.

GREEN, pipeline/orchestrate.py, main() only (the AST confinement test allows _fn there):
- Initialize _fn_held_groups = [] beside _groups_skipped_no_target = 0.
- Immediately after the no-target gate's continue, and BEFORE the billing-audit freeze if, add the hold. If _fn.gf_lookup_failed():
  - compute the stored-hash match: use _hash_unchanged when _history_eligible_for_skip is True; otherwise call _resolve_unchanged_for_skip with the same arguments as the _hash_unchanged expression (approved rule 1);
  - when _fn.should_hold_group(match) is True, append (wr_num, week_raw, variant) to _fn_held_groups and continue.
- In the hold branch, do NOT add to _mem_confirmed_skip_keys, and do not touch groups, generated_filenames, upload tasks or group_state. No per-group log.
- After the loop, beside the "Group processing phase" log (whose text stays unchanged), set _fn_run_report = _fn.report_run_end(held_groups=_fn_held_groups, force_flags=...). force_flags holds booleans only: FORCE_GENERATION, bool(REGEN_WEEKS), RESET_HASH_HISTORY, bool(RESET_WR_LIST).

Do not edit pipeline/change_detection.py, calculate_data_hash, pipeline/memory_candidate.py or pipeline_memory/schema.sql. Commit as fix(quick-261030-suf).
  </action>
  <verify>
    <automated>SMARTSHEET_API_TOKEN= PYTHONUTF8=1 python -m pytest tests/test_foreman_notes_gf_hold.py tests/test_foreman_notes_state.py tests/test_foreman_notes_pipeline.py -q</automated>
  </verify>
  <done>
    - The new tests fail before the change and pass after it.
    - test_foreman_notes_pipeline.py (the _fn confinement, attach-ordering and ZeroImpact tests) stays green.
    - grep -c "_fn.should_hold_group(" pipeline/orchestrate.py returns 1, and grep -c "def sentry_capture_foreman_notes" pipeline/observability.py returns 1 (both baselines 0).
    - git diff --exit-code 0f5f825 -- pipeline/change_detection.py pipeline/memory_candidate.py pipeline_memory/schema.sql .github/workflows exits 0.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Close the remaining Foreman Notes Sentry gaps (C1-C6) and prove cleanup tolerance</name>
  <files>tests/test_foreman_notes_sentry.py, tests/test_foreman_notes_gf_hold.py, pipeline/foreman_notes.py, pipeline/observability.py, pipeline/orchestrate.py</files>
  <behavior>
    - C1: a failed lookup (each reason: exception, columns_mismatch, partial_read, initialize_failed) captures exactly one event at initialize time, even if no group is later held:
      - fingerprint ["foreman-notes","gf-lookup-failed", reason], level warning;
      - contexts.foreman_notes holds reason, exception_class, exception_message, target_sheet_id, wr_column_id, gf_column_id, expected_titles, allowlist_count, remediation;
      - neither GF alias appears in the event.
      Scope off, scope all, an empty allowlist and a good lookup capture zero events. The failure breadcrumb message differs from "initialized" and has level "warning". The success breadcrumb is unchanged apart from the renamed allowlist_count key.
    - C2: in a dry-run pilot, memory_write_blocked("row_state") produces exactly one ERROR event with tags foreman_notes="1" and memory_kind="row_state" and fingerprint ["foreman-notes","memory-write-blocked","row_state"]. The next event captured outside it carries neither tag (scoped, not shared). The ERROR log text is unchanged.
    - C3: a style chunk failure and an attach_group_styles failure increment per-run counters (failed chunks, rows affected, exception class names). report_run_end then sends one warning event, fingerprint ["foreman-notes","style-fetch-failed"], whose context holds the counts, reason and exception classes. Zero failures send zero events.
    - C4: forced failures in row_notes_component, group_notes_token and globals_component increment per-function counters. report_run_end sends one warning event, fingerprint ["foreman-notes","notes-digest-failed"], with per-function counts and exception classes. Zero failures send zero events.
    - Counters reset in reset_state() and at the start of initialize(). report_run_end's returned dict carries every count, and main() adds it to session_summary under key foreman_notes only when it is non-empty.
    - C5: after initialize, the isolation scope carries the tags foreman_notes_scope (effective scope), foreman_notes_pilot_wrs (count) and gf_lookup (ok | failed | skipped), and a later captured event shows them.
    - C6:
      - _PII_BREADCRUMB_DATA_KEYS gains gf, gf_name, general_foreman, allowlist, note, notes, foreman_notes_text, so a breadcrumb with data {"gf": "GF-1", "notes": "x"} is stripped.
      - _PII_LOG_MARKERS gains only the narrow marker foreman_notes_text. Matching is substring, so "note" or "gf" would drop every counts-only "Foreman notes:" log.
      - A captured hold event still contains contexts.foreman_notes with its WR list after before_breadcrumb and the before_send frame scrub.
    - Leak test: while the mapping is on, capture a Foreman Notes event from inside an except block whose frame locals hold "GF-1" and a note sentinel string. The event contains neither string, while contexts.foreman_notes is present.
    - Cleanup tolerance (approved item 3): cleanup_untracked_sheet_attachments with dry_run=True deletes nothing for a held group's identity when valid_wr_weeks holds it the way Site 2 builds it from groups, exactly like an unchanged-skip identity. An AST check confirms the Site 2 loop iterates groups.items().
  </behavior>
  <action>
RED first. Create tests/test_foreman_notes_sentry.py for C1-C6 and the leak test, using the event-capture pattern from the context section. Add the cleanup tests to tests/test_foreman_notes_gf_hold.py, mirroring the fake client at tests/test_orphaned_primary_attachment.py:129. Run them, confirm they fail, and commit as test(quick-261030-suf).

GREEN:
- C1, in pipeline/foreman_notes.py initialize:
  - On every lookup failure, and in the outer-handler failed case, call observability.sentry_capture_foreman_notes(kind="gf_lookup_failed", level="warning", reason=..., fingerprint=["foreman-notes","gf-lookup-failed", reason]). Pass the lookup context: reason, exception class, redacted message, config.TARGET_SHEET_ID, the two FOREMAN_NOTES_GF_* column IDs, the expected titles _GF_WR_TITLE and _GF_TITLE, allowlist count, FOREMAN_NOTES_REMEDIATION and the run URL.
  - Change _breadcrumb to accept message and level parameters. Successful initialize keeps "initialized"/info. The empty-allowlist branch uses "pilot allowlist empty"/warning, and lookup failures use "gf lookup failed"/warning, with the reason in data.
  - Rename the count key from allowlist to allowlist_count, because C6 adds "allowlist" as a stripped key. Update any test that asserts the old key.
- C2: in memory_write_blocked, wrap the existing logging.error call in observability.foreman_notes_scope(tags={"foreman_notes": "1", "memory_kind": kind}, fingerprint=["foreman-notes","memory-write-blocked", kind]), so the event that LoggingIntegration builds from that log carries them. This gives one event, not two. If the scope helper fails, the plain logging.error still runs.
- C3 and C4: add a module-level per-run counter dict, reset by reset_state() and at the start of initialize(). Increment it in the style chunk except (failed chunks, rows affected = len(chunk), exception class), the attach_group_styles outer except, and the three digest excepts (per function name plus exception class).
  - Keep every existing return value and log line, so hashes and output are unchanged.
  - Counter updates must never raise.
  - Extend report_run_end to send the style and digest events through sentry_capture_foreman_notes (fixed fingerprints, counts and classes only), and to include all counts in its returned dict.
- C5: add observability.set_foreman_notes_run_tags(scope, pilot_wrs_count, gf_lookup), which sets the three tags on sentry_sdk.get_isolation_scope(). These are run-level by design, so they persist across the run. It is a no-op without SENTRY_DSN. Call it at the end of initialize (in both the normal and the outer-handler path) with ok, failed or skipped.
- C6: extend _PII_BREADCRUMB_DATA_KEYS and _PII_LOG_MARKERS exactly as listed in the behavior block, with a comment explaining the substring-matching reason. Do not touch _redact_exception_message or the frame-scrub gate.
- In pipeline/orchestrate.py main(), at the session_summary set_context, add "foreman_notes": _fn_run_report only when _fn_run_report is truthy. Scope-off runs then send a byte-identical session_summary. Use no new _fn reference outside main.

Then run the full suite and the 6-gate harness. If a pre-existing test asserts the exact contents of _PII_BREADCRUMB_DATA_KEYS or the breadcrumb key, update only that assertion and note it in the SUMMARY. Commit as fix(quick-261030-suf).
  </action>
  <verify>
    <automated>SMARTSHEET_API_TOKEN= PYTHONUTF8=1 python -m pytest tests/test_foreman_notes_gf_hold.py tests/test_foreman_notes_sentry.py tests/test_foreman_notes_state.py -q && SMARTSHEET_API_TOKEN= PYTHONUTF8=1 python -m pytest tests/ -q && bash scripts/run_6_gates.sh</automated>
  </verify>
  <done>
    - The C1-C6, leak and cleanup tests pass.
    - The full suite has zero new failures versus the 0f5f825 baseline.
    - run_6_gates.sh passes, and python -m py_compile generate_weekly_pdfs.py exits 0.
    - grep -c "gf-lookup-failed" pipeline/foreman_notes.py returns at least 1 (baseline 0).
  </done>
</task>

<task type="auto">
  <name>Task 3: Decision record, Sentry doc, ledger, runbook, and the span-name follow-up todo</name>
  <files>docs/DECISIONS.md, docs/sentry-implementation.md, memory-bank/living-ledger.md, website/docs/runbook/foreman-notes-pilot.md, .planning/todos/pending/2026-10-30-wr-numbers-in-sentry-span-names.md</files>
  <action>
- docs/DECISIONS.md: append a dated section "2026-10-30 - Foreman Notes Sentry WR exception (owner-approved)". It states:
  - WR numbers may appear only in the structured foreman_notes context of Foreman Notes events, set on a forked scope;
  - the general _redact_exception_message WR redaction is unchanged for all other events;
  - GF names (counts only) and note text are never sent;
  - why: the operator needs exactly what errored to audit and fix it.
  Link the matching living-ledger entry. Keep the stub's existing text.
- docs/sentry-implementation.md: add a short "Foreman Notes events" section under Privacy / Security. Include a table of fingerprints (foreman-notes/gf-lookup-failed/<reason>, foreman-notes/gf-hold, foreman-notes/memory-write-blocked/<kind>, foreman-notes/style-fetch-failed, foreman-notes/notes-digest-failed), the run tags (foreman_notes_scope, foreman_notes_pilot_wrs, gf_lookup), the context fields, and the WR exception with a pointer to DECISIONS.md.
- memory-bank/living-ledger.md: append ONE entry at the very bottom, header "## [2026-10-30 HH:MM] Foreman Notes: hold changed groups when the GF lookup fails; Sentry gap closure." Never edit earlier entries. The body covers:
  - the hold rule and its placement;
  - held groups are regeneration debt;
  - why there is no durable pilot marker, and that option 2 was rejected;
  - the four approved decisions (force flags, one-run delay, cleanup, outer handler);
  - the WR exception;
  - C1-C6 in one line each;
  - that it closes the open item in the 2026-10-30 13:50 entry;
  - evidence: the test files.
  No GF names and no production WR numbers.
- website/docs/runbook/foreman-notes-pilot.md: add a section "If the General Foreman lookup fails" after "When the pilot actually renders". Write it for the on-call operator and name the Python billing pipeline as the owner. It covers:
  - what they see: the gf-lookup-failed event with its reason, a gf-hold event listing the held WRs, the gf_lookup=failed run tag, and a run-summary warning;
  - what happens: pilot files are not re-sent, changed or new non-pilot groups wait one run, and force/regen flags do not override the hold for those groups;
  - what to do, per reason: columns_mismatch means check the column titles/IDs; partial_read or exception means check permissions or the API; afterwards the next good run self-heals from regeneration debt, with no RESET_* needed.
  Rewrite rather than append stale text, and keep cross-links valid. Use GF-1 style aliases in any example.
- .planning/todos/pending/2026-10-30-wr-numbers-in-sentry-span-names.md: a follow-up todo in the same frontmatter format as the existing 2026-10-30 todo (created, title, area: observability, severity: minor). It records that existing span names such as "Generate Excel for WR {wr_num}" embed WR numbers outside the approved foreman_notes context, and that this is out of scope for quick 261030-suf.
  </action>
  <verify>
    <automated>grep -c "foreman-notes" docs/sentry-implementation.md && grep -c "2026-10-30" docs/DECISIONS.md && tail -n 30 memory-bank/living-ledger.md | grep -c "gf_failed" && grep -c "gf-hold" website/docs/runbook/foreman-notes-pilot.md && test -f .planning/todos/pending/2026-10-30-wr-numbers-in-sentry-span-names.md && npm --prefix website run typecheck</automated>
  </verify>
  <done>
    - Every grep count is at least 1. The baselines are: foreman-notes in sentry-implementation.md 0, 2026-10-30 in DECISIONS.md 0, gf-hold in the runbook 0.
    - The todo file exists, and the website typecheck passes.
    - Commit as docs(quick-261030-suf).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Smartsheet target sheet -> pipeline | The GF lookup result (it may fail, mismatch or be partial) decides pilot membership |
| pipeline -> Smartsheet attachments | Regenerated billing workbooks are uploaded to the target sheet |
| pipeline -> Sentry / Actions logs | Event context, tags, breadcrumbs and frame vars leave the runner. WR numbers are now allowed only in the foreman_notes context; GF names and notes never leave |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-261030suf-01 | Tampering | orchestrate main() group loop | high | mitigate | A failed lookup can no longer replace pilot workbooks with no-notes versions. The hold sits before the billing-audit freeze, generate_excel and upload (Task 1 AST and sequence tests) |
| T-261030suf-02 | Information disclosure | sentry_capture_foreman_notes context | high | mitigate | WRs only in the structured foreman_notes context on a forked new_scope (owner-approved exception, recorded in DECISIONS.md). Payload tests assert no GF alias and no note text; context built from counts and IDs only; variant enum only, never the identifier |
| T-261030suf-03 | Information disclosure | frame locals on Foreman Notes events | high | mitigate | The existing _notes_may_be_in_frames scrub strips vars while the mapping is on. The Task 2 leak test captures inside an except whose locals hold GF-1 and a note sentinel |
| T-261030suf-04 | Information disclosure | shared Sentry scope | medium | mitigate | Per-event tags, context and fingerprint are set only inside new_scope. The C2 test asserts the next event does not inherit them. Only the three run-level counts/enum tags go on the isolation scope |
| T-261030suf-05 | Information disclosure | breadcrumbs and logs | medium | mitigate | C6 adds the PII breadcrumb keys and one narrow log marker. The allowlist count is renamed to allowlist_count so it survives |
| T-261030suf-06 | Denial of service | changed/new non-pilot groups during a failed run | low | accept | One-run delay carried as regeneration debt (approved). The per-run gf-lookup-failed event drives the fix |
| T-261030suf-07 | Repudiation | held groups and silent Foreman Notes failures | low | mitigate | Hold event with the WR list, gf_lookup run tag, style and digest run-end events, and session_summary counts |
| T-261030suf-08 | Tampering | attachment cleanup | medium | mitigate | Held identities stay in valid_wr_weeks (built from groups). Task 2 cleanup test |
| T-261030suf-SC | Tampering | npm/pip/cargo installs | high | mitigate | No package installs. sentry-sdk>=2.54.0 is already pinned (2.63.0 installed, new_scope present) |
</threat_model>

<verification>
Run from the repo root:
- SMARTSHEET_API_TOKEN= PYTHONUTF8=1 python -m pytest tests/test_foreman_notes_gf_hold.py tests/test_foreman_notes_sentry.py -q
- SMARTSHEET_API_TOKEN= PYTHONUTF8=1 python -m pytest tests/ -q
- bash scripts/run_6_gates.sh
- python -m py_compile generate_weekly_pdfs.py
- git diff --exit-code 0f5f825 -- pipeline/change_detection.py pipeline/memory_candidate.py pipeline_memory/schema.sql .github/workflows
- npm --prefix website run build (the docs rule requires typecheck and build before push)

Reviewer flags:
- `_shadow_group_hashes` still records the non-pilot-form hash for held groups. This affects parity only.
- A pilot group with a missing attachment is also held during a failed run.
- A group_notes_token failure inside a pilot group still drops NOTES_FP for that group. C4 now makes this visible, but it is not held. Possible follow-up.
- The C5 run tags are set on scope-off production runs too. This is Sentry metadata only and does not change billing output.
</verification>

<success_criteria>
- Good run, then failed lookup: no pilot group reaches generate_excel or upload, and the recovery run re-sends nothing.
- Scope off / all / empty allowlist / good lookup: gf_failed False, no Foreman Notes event, and session_summary unchanged. The full suite is green.
- Every Foreman Notes failure path has a tested Sentry signal. WRs appear only in contexts.foreman_notes. GF names and notes appear nowhere.
- DECISIONS.md, sentry-implementation.md, the ledger and the runbook are updated, the span-name follow-up todo exists, and the protected files are untouched.
</success_criteria>

<output>
Create `.planning/quick/261030-suf-hold-pilot-groups-when-the-foreman-notes/261030-suf-SUMMARY.md` when done
</output>
