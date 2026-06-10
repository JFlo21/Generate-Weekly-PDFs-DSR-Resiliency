# Living Ledger (Auto-Updated Context)

> Archived out of `CLAUDE.md` on 2026-05-28 to keep that file lean (the ledger had grown to
> ~3,500 lines / ~56K tokens and was loaded into every context window). **This is the
> authoritative, complete history** — referenced from `CLAUDE.md`, read on demand.
>
> **Claude: append new repo-specific learnings, architectural decisions, and established
> standards to the BOTTOM of this file. Always prepend each entry with a date + timestamp in
> `[YYYY-MM-DD HH:MM]` format. Do NOT move this content back into `CLAUDE.md`.**

---

## Living Ledger (Auto-Updated Context)

*(Claude: Append new repo-specific learnings, architectural decisions, and established standards below this line. Always prepend each entry with a date + timestamp in `[YYYY-MM-DD HH:MM]` format.)*

- [2026-04-17 15:26] Initialized Claude Code workspace layout: added
  `.claude/rules/smartsheet-python-optimization.md` (scope: new scripts
  only — `generate_weekly_pdfs.py` stays on `openpyxl`) and
  `.claude/rules/documentation-maintenance.md` (Docusaurus runbook +
  changelog synthesis, Python/n8n tier boundaries); seeded
  `.claude/commands/` with a `.gitkeep`; prepended `## Project Summary
  — Generate to Excel & Data Sync` block to `CLAUDE.md` (tech stack,
  architecture, conventions, guardrails, validation commands — with
  `uv` flagged aspirational and `pytest tests/ -v` kept authoritative)
  while preserving every pre-existing section verbatim.
- [2026-04-20 00:00] Sentry release naming in GitHub Actions: release
  versions must be slash-free or `sentry-cli releases new` fails with
  `Invalid release version`. Standardized on composing
  `SENTRY_RELEASE` via a "Compute Sentry release" step that exports
  `${GITHUB_REPOSITORY//\//-}@${GITHUB_SHA}` into `$GITHUB_ENV`, then
  reusing that single value for both the Python process and the
  `sentry-cli` release step. Applied in
  `.github/workflows/weekly-excel-generation.yml` and
  `.github/workflows/system-health-check.yml`. Any new workflow that
  creates a Sentry release or tags events with `SENTRY_RELEASE` MUST
  follow this same pattern — do not reintroduce the raw
  `${{ github.repository }}@${{ github.sha }}` form.
- [2026-04-20 12:00] Sentry Logs support wired for the Python
  billing engine, **gated opt-in + defense-in-depth sanitizer**.
  `sentry_sdk.init(...)` in `generate_weekly_pdfs.py` sets
  `enable_logs=` from a new `SENTRY_ENABLE_LOGS` env var (truthy
  values: `1`, `true`, `yes`, `on`; default `false`) AND registers a
  `before_send_log` hook that drops records whose body matches any
  entry in `_PII_LOG_MARKERS` (row-sample diagnostics, cell dumps,
  helper / vac-crew detection logs, rate-recalc traces, foreman
  assignment logs, `Removing …` / `Unchanged (…` / `FORCE
  GENERATION for …` lines — all known INFO paths that embed WR /
  dept / job / foreman / cell / price data). Requires
  `sentry-sdk>=2.35.0`, already pinned in `requirements.txt`.
  Rationale: the engine has INFO-level debug paths
  (`PER_CELL_DEBUG_ENABLED`, row-sample logs, helper / vac-crew
  diagnostics) that can emit billing-row PII; per
  `docs/sentry-implementation.md` "Privacy / Security", that data is
  *intentionally not captured* in Sentry, so forwarding INFO logs by
  default would regress an existing privacy guarantee. New rules:
  (1) Any new Python script that initializes Sentry in this repo
  must route `enable_logs` through the same `SENTRY_ENABLE_LOGS` env
  gate — do not hard-code `True`. (2) Adding a new INFO log that
  embeds row content? Either strip the PII from the message or
  extend `_PII_LOG_MARKERS` in the same PR so the sanitizer keeps
  up. Never rely on the env gate alone. (3) Before flipping
  `SENTRY_ENABLE_LOGS=true` in any environment, audit log call sites
  and keep `PER_CELL_DEBUG_ENABLED` and row-sample debug flags off
  in production. (4) For direct-to-Sentry sends, prefer the existing
  `sentry_capture_message_with_context(...)` helper over the
  upstream `sentry_sdk.logger.*` API, which is less established in
  this codebase and depends on SDK internals that may shift.
  Issue-creation behavior is unchanged regardless of the gate
  (`event_level=logging.ERROR`, so only ERROR+ creates issues;
  INFO/WARNING were already breadcrumbs and become searchable Logs
  only when the gate is on and the sanitizer lets them through).
- [2026-04-21 22:35] VAC crew post-cutoff pricing lag was a *silent
  fall-through* in `recalculate_row_price()`, not a cutoff-column
  bug. **Context:** The cutoff rule is correctly keyed on
  `Snapshot Date >= RATE_CUTOFF_DATE` at
  `generate_weekly_pdfs.py:2127`; Weekly Reference Logged Date is
  the wrong column for this check and must NOT be substituted —
  operators depend on Snapshot Date semantics. **Real root cause:**
  `build_cu_to_group_mapping()` reads the old CSV's
  `Compatible Unit Group` column, which mixes short codes (e.g.
  `ANC-M`, `CPD-SW`) with verbose names (e.g. `Vacuum Switch`,
  `Overhead Switching"`, `Softswitch Type K"`, `1200 KVAR Switched
  Bank`). The new contract CSV keys rates ONLY by short codes. So
  any CU whose old-CSV group is a verbose name that isn't a key in
  the new rates table (heavily concentrated on VAC crew specialty
  work — vacuum switches, softswitches, switched banks) hit the
  "group not in rates_dict" branch in `recalculate_row_price` and
  returned the SmartSheet price unchanged with only a
  `logging.debug` — invisible in production logs. **Fix (additive,
  production-safe):** (1) In `recalculate_row_price` at the
  "group not in rates_dict" branch, fall back to a direct CU-code
  lookup in `rates_dict` before giving up; only activates on exact
  match so it cannot mis-apply a rate. (2) When even the direct CU
  lookup misses, elevate the log to WARNING with CU, mapped group,
  qty, and work type so operators see it immediately. (3) Track
  `{'recalculated', 'skipped'}` counters and a top-CU Counter per
  sheet inside `_fetch_and_process_sheet`, and emit a per-sheet
  WARNING summary when any skips happened — this surfaces the list
  of CU codes the data team needs to add to
  `NEW_RATES_CSV` / `New Contract Rates copy regenerated again.csv`
  (the usual actual resolution). **New rules:** (1) When adding a
  new CU classification (VAC crew, subcontractor variant, etc.),
  verify at least one end-to-end row produces a WARNING-free rate
  recalc before going to production — if the per-sheet summary
  logs `N skipped`, those CUs are missing from the new rates CSV.
  (2) Do NOT change the cutoff column from `Snapshot Date` to
  `Weekly Reference Logged Date` — that was an earlier speculative
  fix and was rolled back; the business rule is explicitly
  snapshot-keyed. (3) Never promote recalc fall-through logs back
  to DEBUG without adding an alternate visibility path — silent
  price retention directly drives billing inaccuracy. Regression
  tests:
  `tests/test_subcontractor_pricing.py::TestRecalculateRowPrice`
  now covers both the CU-direct fallback
  (`test_cu_direct_fallback_when_mapped_group_absent_from_new_rates`)
  and the safety guard that still retains SmartSheet price when
  neither group nor CU is in new rates
  (`test_silent_fallthrough_when_neither_group_nor_cu_in_new_rates`).
- [2026-04-22 00:00] VAC crew Excel files silently not regenerating
  when a non-first-sorted row's VAC crew fields change. **Root
  cause:** `calculate_data_hash()` built `vac_crew` variant
  metadata (VACCREW / VACCREW_DEPT / VACCREW_JOB) from
  `sorted_rows[0]` only — mirroring the helper pattern — but the
  `vac_crew` group key (`{week}_{wr}_VACCREW`, created in
  `group_source_rows`) does NOT split per foreman the way helper
  groups do (`{week}_{wr}_HELPER_{helper}`). A single VAC crew
  group therefore contains every VAC crew member for that
  WR+week. Editing the dept/job/name on a member that didn't sort
  first left the hash unchanged, the "unchanged + attachment
  exists" skip path fired, and no Excel regenerated even though
  the row fully met VAC crew criteria (dept #, name, both
  `Vac Crew Completed Unit?` and `Units Completed?` checked).
  Adding a row already regenerated (ROWCOUNT changed), so only
  *modifications* to existing rows were silently lost. **Fix:**
  include `__vac_crew_name`, `__vac_crew_dept`, `__vac_crew_job`
  directly in the per-row `row_str` that feeds the hash (scoped
  to the `vac_crew` variant so primary/helper hash stability is
  preserved). Per-row inclusion is strictly more sensitive than
  aggregating values into `meta_parts` and avoids two review-caught
  pitfalls of set-based aggregation: **set dedup** (depts
  `{500, 500, 600}` + editing one row 500→600 leaves the set
  unchanged) and **delimiter collision** (`','.join` on free-text
  names cannot distinguish `['A,B','C']` from `['A','B,C']`).
  Helper metadata was left on `sorted_rows[0]` because helper
  groups already partition by foreman and every row in a helper
  group shares identical helper info. **Secondary fix:** bumped
  `DISCOVERY_CACHE_VERSION` from 2 → 3 so any discovery cache
  created before VAC crew columns were added to a particular
  existing sheet in Smartsheet is re-validated on the next run
  rather than waiting up to `DISCOVERY_CACHE_TTL_MIN` (default 7
  days) for the mapping to refresh. **New rules:** (1) Whenever a
  group key variant does NOT include a disambiguating identifier
  (the way `_VACCREW` doesn't include the VAC crew name the way
  `_HELPER_<name>` does), the corresponding hash MUST capture
  per-row field changes at the row level — a set-based
  `meta_parts` aggregation of free-text values is a two-way
  silent-skip trap (dedup + delimiter collision). (2) When fixing
  a bug that could leave existing discovery caches with incorrect
  column mappings, bump `DISCOVERY_CACHE_VERSION` so the fix takes
  effect immediately instead of eventually. (3) Living-ledger
  entries and code comments in this codebase must refer to
  functions / group-key formats / env-var names — not hard-coded
  line numbers — because line numbers drift as the file grows.
  Regression tests:
  `tests/test_vac_crew.py::TestVacCrewHashAggregation` covers
  dept-edit and name-edit on non-first rows, the set-dedup
  collision case (`{500, 500, 600}` with a 500→600 edit), the
  delimiter-collision case (commas in free-text names), and
  hash stability when nothing changes. The test class pins
  `EXTENDED_CHANGE_DETECTION`, `RATE_CUTOFF_DATE`, and
  `_RATES_FINGERPRINT` in `setUp`/`tearDown` so developer env-var
  overrides don't destabilize the suite.
- [2026-04-22 16:05] Production incident: a scheduled run finished
  with **0 Excel files generated, 0 uploaded** despite completing
  discovery, row fetch, and grouping (1910 groups identified). Root
  cause was the attachment pre-fetch phase — a `ThreadPoolExecutor`
  + `as_completed` consumer loop around
  `client.Attachments.list_row_attachments` — stalling for ~16
  minutes on the last ~14 of 539 target rows after 4
  `RemoteDisconnected` retries on the Smartsheet `/attachments`
  endpoint. The consumer used a blocking `future.result()` with no
  per-future timeout, so one stuck HTTP worker serialized the tail
  of the batch. Combined with the preceding discovery + row fetch,
  total elapsed hit 82.4 min **before** the group-processing loop
  ran its first iteration; the existing `TIME_BUDGET_MINUTES=80`
  guard then exited immediately with "1910 group(s) remaining" and
  no generation occurred. **Fix (additive, production-safe):**
  (1) Introduced `ATTACHMENT_PREFETCH_MAX_MINUTES` (default 10) and
  `ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC` (default 45) env vars.
  (2) Pre-flight guard: if `session elapsed` already leaves less
  than `ATTACHMENT_PREFETCH_MAX_MINUTES` of the session budget,
  skip the pre-fetch entirely — per-row fallback paths in
  `_has_existing_week_attachment` and `delete_old_excel_attachments`
  already handle a missing cache entry transparently.
  (3) Phase sub-budget is enforced on the **wait itself**:
  `as_completed(futures, timeout=ATTACHMENT_PREFETCH_MAX_MINUTES*60)`.
  The iterator raises `FuturesTimeoutError` if no further future
  completes inside that window — this is the only timeout that can
  break out of a stall. An earlier revision of this fix put the
  timeout on `future.result(timeout=...)` alone, which was dead
  code: `as_completed` only yields futures that are already done,
  so their `.result(timeout=...)` returns immediately and the
  timeout branch can never fire.
  (4) Non-blocking executor shutdown. The pre-fetch must NOT use
  `with ThreadPoolExecutor(...)` — that forces `shutdown(wait=True)`
  on exit, which still blocks on stuck in-flight threads and
  defeats the whole point of the sub-budget. The code uses
  explicit `executor.shutdown(wait=False, cancel_futures=True)` in
  `finally`; queued-but-not-started futures are cancelled and
  still-running threads are abandoned to the background (SDK retry
  backoff is bounded; the workflow's `timeout-minutes: 195` is the
  hard ceiling).
  (5) Counters reflect reality: the log / Sentry span report
  `cancelled` (futures where `f.cancel() == True`) and
  `still_running` (in-flight futures we abandoned) separately
  instead of conflating them via `not f.done()` — which overcounts
  abandons because `cancel()` returns `False` once a task has
  started.
  **New rules:** (1) Any pre-flight / pre-processing phase that
  shares `TIME_BUDGET_MINUTES` with the main generation loop MUST
  have its own sub-budget sized well below the session budget. A
  pre-flight phase burning the entire session budget with zero
  output is an existential bug, not a performance bug — treat it
  as P0. (2) When timing out a `ThreadPoolExecutor.submit` +
  `as_completed` consumer hitting an external API, the timeout
  MUST be on `as_completed(..., timeout=...)` (or an equivalent
  `wait(..., timeout=...)`) — the iterator is where blocking
  happens, not `future.result()`. Relying on the upstream SDK's
  HTTP timeout is insufficient because urllib3 retries can
  multiply it. (3) Also never use `with ThreadPoolExecutor(...)`
  for such a consumer: the context manager's implicit
  `shutdown(wait=True)` will re-block on whatever the timeout was
  meant to escape. Always manage the executor explicitly and call
  `shutdown(wait=False, cancel_futures=True)` when time-boxing.
  (4) When skipping an optimization on a budget-exceeded path,
  verify the fallback path still works end-to-end — partial /
  skipped pre-fetch here is safe *only* because both attachment
  consumers already accept `cached_attachments=None`; adding a new
  consumer that assumes the cache is populated would reintroduce
  this class of bug. (5) `Future.cancel()` returns `True` only for
  queued futures — running threads cannot be cancelled. Account
  for this in any abandoned/cancelled metric or the number will
  mislead Sentry. (6) **Three things block interpreter exit for
  a non-daemon worker and ALL THREE must be addressed to actually
  bound a stall:** (a) `concurrent.futures.thread._python_exit`
  (registered via `threading._register_atexit`) joins every worker
  in `_threads_queues`; (b) `threading._shutdown` joins every
  tstate lock in `_shutdown_locks` — non-daemon threads add
  themselves there via `_set_tstate_lock` at startup; (c) the
  executor's own `shutdown(wait=True)` joins all workers on
  `with`-block exit. The pre-fetch defeats all three by (a)
  popping from `_threads_queues` on the budget-exceeded path (see
  `_detach_from_atexit_registry`), (b) using
  `_DaemonThreadPoolExecutor` — a subclass that creates
  `daemon=True` workers, so `_set_tstate_lock` skips adding them
  to `_shutdown_locks` — and (c) explicit
  `shutdown(wait=False, cancel_futures=True)` instead of `with`.
  Empirical note: an earlier revision did only (a) and still hung
  ~5s at interpreter exit in a repro; (a)+(b)+(c) exits in ~0.05s.
  This trifecta is safe ONLY because the pre-fetch cache is an
  optimization with an always-available per-row fallback. Do NOT
  copy this pattern onto a `ThreadPoolExecutor` whose workers
  produce results the main flow depends on (generation, upload,
  hash_history) — the atexit join is what guarantees those
  workers' side effects are flushed before `return 0` is visible
  to the shell.
  (7) The pre-flight skip condition must reserve
  *generation headroom* beyond the pre-fetch budget
  (`ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN`, default 2
  minutes). Without it, a setup with remaining ==
  `ATTACHMENT_PREFETCH_MAX_MINUTES` would still run pre-fetch and
  leave zero time for the generation loop — recreating the
  original incident's zero-output failure mode.
  (8) Test files that `importlib.reload(generate_weekly_pdfs)`
  MUST patch `SENTRY_DSN=""` + `sentry_sdk.init` around the
  reload (see `_safe_reload_gwp` in
  `tests/test_performance_optimizations.py`); otherwise a dev
  shell with a real `SENTRY_DSN` causes each reload to fire a
  live Sentry init during test runs. Mirrors the pattern in
  `tests/test_sentry_log_sanitizer.py`. Regression tests:
  `tests/test_performance_optimizations.py::TestAttachmentPrefetchBudget`
  locks in the new constants (with env-isolated `patch.dict` +
  `importlib.reload` so a developer's local env doesn't leak into
  the assertions) and the `FuturesTimeoutError` import.
- [2026-04-22 17:10] Raised weekly-workflow session time budget from
  `TIME_BUDGET_MINUTES=80` → `180` (3h) and the matching runner
  `timeout-minutes` from `90` → `195`. Rationale: even with the
  pre-fetch sub-budget landed earlier today, the main generation
  loop still needs enough headroom to process the full group set
  (1910 groups on the incident run) in a single session rather
  than always relying on backlog catch-up. **Rule:** the workflow
  `timeout-minutes` value must always exceed `TIME_BUDGET_MINUTES`
  by the length of the post-job cache-save + artifact-upload
  steps (~10-15min). Today's cushion is 15min. Never raise
  `TIME_BUDGET_MINUTES` without also raising `timeout-minutes` by
  at least as much, or Actions hard-kills the job before the
  graceful stop fires and the `save_hash_history` / Sentry flush
  / attachment upload tails are lost. Code changes were
  additive-only (config values + comments + one dead-variable
  cleanup — the unused `wr_num` unpack in `_fetch_row_attachments`
  became `_, target_row = row_item` since only `target_row.id` is
  referenced inside the closure). No behavioral change to
  discovery, row fetch, grouping, hashing, generation, or upload.
- [2026-04-22 18:30] Silent VAC crew detection failure when a
  folder-discovered sheet's VAC Crew column titles drift from the
  exact strings in the `synonyms` dict of `_validate_single_sheet`.
  **Context:** Sheet ID `1413438401105796` in folder
  `8815193070299012` (an `ORIGINAL_CONTRACT_FOLDER_IDS` entry) was
  correctly discovered via `discover_folder_sheets` and merged into
  `base_sheet_ids`, but its VAC Crew columns carried subtle title
  variants (whitespace / case / punctuation drift) that the
  exact-string loop at the `if c.title in synonyms and
  synonyms[c.title] not in mapping:` gate could not absorb. With
  the two key columns (`VAC Crew Helping?` and
  `Vac Crew Completed Unit?`) missing from `column_mapping`,
  `sheet_has_vac_crew_columns` in `_fetch_and_process_sheet`
  evaluated `False`, the row-level detection block was skipped
  wholesale, and every VAC crew row for that sheet — including
  a foreman's whose production data the reporter surfaced to us —
  flowed through the primary variant and never produced a
  `_VacCrew` Excel. (Foreman name redacted: billing-row foreman
  names are PII and must not be committed to this repository per
  the Sentry Logs sanitizer rule earlier in this ledger.) The deceptive part: the diagnostic
  log `"🚐 VAC Crew columns found in sheet: [...]"` still fired
  because it uses a broader substring check
  (`'Vac Crew' in c.title or 'VAC Crew' in c.title`), so operators
  tailing logs saw the columns "found" even though the actual
  mapping had silently failed. **Fix (additive, production-safe):**
  (1) Introduced `_normalize_column_title_for_vac_crew(t)` —
  lowercases, collapses whitespace runs, strips trailing `?`/`#`
  with optional surrounding spaces. Scoped narrowly (name
  explicitly mentions `vac_crew`) so primary/helper exact-match
  behaviour is unchanged. (2) Added a fuzzy fallback pass inside
  `_validate_single_sheet` that runs AFTER the exact-match loop:
  for each canonical VAC Crew name in `_vac_crew_fuzzy_canonicals`
  that isn't already in `mapping`, scan remaining columns using
  the normalized comparison and assign the first match. Already-
  mapped column IDs are excluded so the fuzzy pass cannot clobber
  an exact match. When a fuzzy match fires, log a WARNING with
  the raw title so operators can promote it to an explicit synonym
  if the variant is permanent. (3) Broadened the substring
  detector for `vac_crew_columns_found` to be case-insensitive and
  to catch `'vac-crew'` variants, so the summary log and the
  follow-up warning both surface all-lowercase sheets. (4) After
  the fuzzy pass, if `vac_crew_columns_found` is non-empty but the
  two key mappings (`VAC Crew Helping?`, `Vac Crew Completed
  Unit?`) are still absent, emit an actionable WARNING with the
  raw titles so operators know detection will be disabled for that
  sheet. (5) Bumped `DISCOVERY_CACHE_VERSION` from 3 → 4 so
  existing caches (which may have persisted a stale mapping
  without VAC Crew columns) are invalidated on the next run
  instead of waiting up to `DISCOVERY_CACHE_TTL_MIN` (7 days).
  **New rules:** (1) Any column-mapping synonyms dict that accepts
  only a small, hard-coded set of case variants is a silent-skip
  trap whenever the downstream detection uses the mapped keys as
  an on/off gate. When the gate controls a whole variant's
  generation (VAC crew here, helper previously), add a fuzzy
  fallback pass and an operator-visible WARNING if the key
  columns still don't resolve. Do NOT rely on substring-match
  diagnostic logs alone — they can falsely advertise success.
  (2) Fuzzy fallback must be scoped by naming and by canonical
  list — do NOT broaden matching for primary/helper columns
  without a documented production incident driving it. Helper and
  primary flows have stable exact-match history; an unscoped
  normalizer risks colliding unrelated column titles (e.g. a
  primary `Foreman` column fuzzy-matching a helper `Foreman
  Helping?` with the `?` stripped). (3) When a bug could leave
  `generated_docs/discovery_cache.json` holding an incorrect
  `column_mapping` for an existing (already-discovered) sheet,
  bump `DISCOVERY_CACHE_VERSION` — the `_new_from_folders` check
  in `discover_source_sheets` only invalidates on NEW sheet IDs,
  so in-place column additions inside an already-cached sheet do
  NOT trigger a refresh on their own. Regression tests:
  `tests/test_vac_crew.py::TestVacCrewColumnTitleNormalizer` and
  `tests/test_vac_crew.py::TestVacCrewColumnFuzzyFallback` cover
  whitespace / case / punctuation drift, exact-match preservation
  when both forms are present, and the cache-version bump.
- [2026-04-23 00:00] Current-week VAC crew Excel files silently not
  generating because the pre-acceptance rate recalc required a
  populated `Snapshot Date`. **Reported symptom:** VAC crew
  attachments produced for week ending 04/12/26 but nothing for
  week ending 04/19/26, despite operators confirming the usual
  criteria (VAC Crew Helping? populated, Vac Crew Completed Unit?
  and Units Completed? both checked) on those current-week rows.
  **Root cause:** The recalc block in `_fetch_and_process_sheet`
  was gated strictly on `Snapshot Date >= RATE_CUTOFF_DATE`. For
  rows freshly logged in the most recent week, Smartsheet's
  snapshot automation has not yet populated `Snapshot Date`, so
  the outer `if snapshot_raw_pre:` short-circuited and recalc was
  entirely skipped. The row's `Units Total Price` therefore
  retained whatever SmartSheet had — which for VAC crew specialty
  CUs is often 0 or blank because the upstream Smartsheet price
  formula itself depends on the CU being present in the legacy
  rates map. The downstream `has_price` gate then evaluated
  False and the row was dropped before VAC crew detection or
  grouping could run. WE 04/12 rows escaped the trap only because
  they'd been on the sheet long enough for the snapshot
  automation to fire. **Fix (additive, production-safe):**
  (1) Introduced `RATE_RECALC_WEEKLY_FALLBACK` env var (default
  `true`; truthy values `1`/`true`/`yes`/`on`) that enables a
  Weekly-Ref-Date fallback path when `Snapshot Date` is blank or
  unparseable. (2) Extracted the recalc gating into a new helper
  `_resolve_rate_recalc_cutoff_date(row_data, cutoff_date, *,
  weekly_fallback_enabled=True) -> (effective_cutoff_date,
  used_fallback)`. The helper returns the snapshot date when that
  is populated and `>= cutoff` (primary rule, unchanged); it
  falls back to `Weekly Reference Logged Date` only when the
  snapshot value is blank/unparseable AND the weekly date parses
  AND the weekly date is `>= cutoff`. Rows with a populated
  snapshot date that is *pre-cutoff* still return `None` — the
  fallback does NOT override the snapshot-keyed business rule.
  (3) Added `fallback_applied` counter alongside the existing
  `recalculated` / `skipped` counters and surfaced it in the
  per-sheet "Rate recalc summary" log. (4) Updated the per-row
  "Dropped VAC/helper row" WARNING's `_recalc_note` to distinguish
  three cases for operators: recalc ran with `missing_rate`,
  recalc ran via Weekly-Ref-Date fallback with `missing_rate`,
  and recalc skipped because the fallback was disabled AND
  `Snapshot Date` was blank (points operators at the env var
  instead of at `NEW_RATES_CSV`). **New rules:** (1) The ledger
  guardrail from 2026-04-21 — "Do NOT change the cutoff column
  from `Snapshot Date` to `Weekly Reference Logged Date`" —
  stands. A *fallback* when Snapshot Date is missing is
  explicitly NOT the same as replacing the primary column; the
  snapshot rule still controls every row that has a snapshot
  value. Any future broadening of the recalc gate (e.g. allowing
  the fallback to trump a pre-cutoff snapshot date) would
  violate the guardrail and must be rejected without a documented
  production-incident justification. (2) Any new pre-acceptance /
  pre-`has_price` data transformation tied to a business cutoff
  MUST degrade gracefully when the driving column is blank.
  Silent skip-on-blank is a current-week failure trap: the
  freshly entered rows operators expect to see on Monday morning
  are exactly the rows most likely to have blank
  automation-populated columns. (3) When a config env var's
  default changes observable production behaviour (here:
  `RATE_RECALC_WEEKLY_FALLBACK=1` rescues rows that previously
  silently dropped), the `if RATE_CUTOFF_DATE:` boot-up log block
  MUST print the fallback's resolved state so operators grepping
  the startup banner can tell at a glance whether the rescue is
  active. Regression tests:
  `tests/test_subcontractor_pricing.py::TestWeeklyRefDateFallbackCutoff`
  covers the env constant's presence, the snapshot-post-cutoff
  primary path (no fallback), the snapshot-pre-cutoff guardrail
  (fallback must NOT override), the incident case (blank
  Snapshot + post-cutoff Weekly → fallback triggers), the
  all-blank and pre-cutoff-Weekly no-op cases, the
  `weekly_fallback_enabled=False` legacy-behaviour preservation
  path, unparseable-Snapshot fallthrough, the `cutoff=None`
  defensive guard, and an end-to-end check that drives
  `_resolve_rate_recalc_cutoff_date` → `recalculate_row_price`
  and asserts the row's `Units Total Price` is updated in-place
  so the downstream `has_price` gate will accept it.
- [2026-04-23 12:00] Security-tightening audit on
  `generate_weekly_pdfs.py`. Two real attack surfaces fixed, plus
  a hygiene cleanup. **(1) Path traversal via `wr_num` in Excel
  filenames.** `wr_num` is derived from the row's
  `Work Request #` column at two sites (inside `generate_excel`
  and in the main group-processing loop) and embedded directly
  into `os.path.join(week_output_folder, output_filename)` →
  `workbook.save(final_output_path)`. Realistic production WR#s
  are numeric, so normal data is unaffected, but a malicious
  `1234/../evil` value would have escaped `generated_docs/<week>/`.
  Fix: apply `_RE_SANITIZE_HELPER_NAME.sub('_', wr_num)[:50]`
  at BOTH derivation sites — in-place numeric WR#s pass through
  unchanged (`\w` includes 0-9), and sanitizing consistently at
  both sites keeps `history_key`, `_has_existing_week_attachment`
  prefix matching, and the actual on-disk filename all lined up
  (sanitizing only one site would break attachment matching).
  **(2) PII leakage via Sentry `context_data['error_message']`.**
  Five `sentry_capture_with_context(...)` call sites passed
  `str(e)` straight into `context_data`, which is attached as
  Sentry event context — bypassing the `before_send_log` hook
  (that hook only scrubs logging records, not `event['contexts']`).
  Fix: new helper `_redact_exception_message(exc, *, max_len=240)`
  strips WR identifiers (`WR=<redacted>`), dollar amounts
  (`$<redacted>`), emails (`<email>`), and
  `customer=`/`foreman=`/`dept=`/`snapshot=`/`cu=`/`job=` key-
  value pairs, prefixes the exception class name for event-
  grouping stability, collapses whitespace, and truncates.
  All five sites now use it. **(3) Discovery cache schema guard.**
  `cache.get('sheets', [])` was trusted blindly — a malformed
  entry without `column_mapping` would crash
  `_fetch_and_process_sheet` later with a KeyError.
  Fix: filter to `_valid_cached_sheets` (requires dict with
  int `id` and dict `column_mapping`), log an operator WARNING
  when entries are dropped with a pointer to delete
  `DISCOVERY_CACHE_PATH` for a clean rediscovery. **(4) Hygiene:**
  removed unused `import inspect`. **Legacy-code note:**
  `VAC_CREW_SHEET_IDS` / `VAC_CREW_FOLDER_IDS` at line ~319-320
  are intentionally retained — the line 318 comment correctly
  flags them as test-only, and they're read exclusively by
  `tests/test_vac_crew.py::TestVacCrewSheetIdsConfig` (4 tests).
  No production code path touches them. Removing the pair is a
  separate coordinated change with those tests; it is not a
  conflict risk in its current form. **New rules:**
  (1) Any user-controllable string (row field, Smartsheet cell
  value, env-var-derived identifier) that flows into
  `os.path.join(...)` / `workbook.save(...)` / any `open(path,
  'w')` MUST pass through a filesystem-safety sanitizer at each
  derivation site — not just at the final filename assembly —
  so downstream comparisons (history keys, attachment prefix
  matching) stay consistent. Reuse `_RE_SANITIZE_HELPER_NAME`
  (`[^\w\-]`) or a tighter pattern; do not invent new ones
  per-site. (2) Never pass raw `str(exc)` into
  `sentry_capture_with_context(...)`'s `context_data` payload.
  That dict lands in `event['contexts']` and bypasses the
  `before_send_log` sanitizer. Use
  `_redact_exception_message(e)` so row PII stays out of the
  Sentry dashboard. (3) Any JSON file loaded from disk into a
  typed shape (discovery cache, hash history, future caches)
  MUST guard each entry with `isinstance(...)` checks before
  trusting `entry['id']` / `entry['column_mapping']` / similar
  — a corrupt cache should WARN and drop the bad entries, not
  crash the whole run. Regression tests:
  `tests/test_security_audit_followup.py` covers WR#
  sanitization (regex, no-op for numeric, cannot-escape-
  OUTPUT_FOLDER, filename shape), `_redact_exception_message`
  (WR / money / customer+foreman tokens / email / class prefix
  / truncation / unrepresentable exception / None / realistic
  end-to-end), the discovery-cache schema guard (kept / dropped
  variants, matches-production-filter comprehension), and the
  `inspect` import removal.
- [2026-04-23 18:05] PR #176 review-driven tightening on top of the
  2026-04-23 12:00 security audit. Three follow-ups addressed:
  **(1) Cache `name` field guard.** The original
  `_valid_cached_sheets` filter validated `id` and `column_mapping`
  but not `name` — `_fetch_and_process_sheet` accesses
  `source['name']` directly in several log lines / Sentry
  breadcrumbs and would KeyError on a cached entry missing the
  field. Filter now also requires `isinstance(s.get('name'), str)`.
  **(2) All-dropped → forced rediscovery (P1).** With the new
  filter in place, a cache where *every* entry was malformed would
  have made the fresh-cache path return `[]`, silently turning the
  run into a no-op. Added a guard: when `_raw_cached_sheets` is
  non-empty but `_valid_cached_sheets` is empty, raise `ValueError`
  so the outer `except Exception as e:
  logging.info("Cache load failed, refreshing discovery: {e}")`
  handler catches it and falls through to full rediscovery from
  `base_sheet_ids` — same failure mode as the existing
  schema-outdated / unreadable-cache paths. Partial-drop cases
  (some valid, some malformed) still succeed with the valid
  subset.
  **(3) `_recalc_note` branch handles unparseable Snapshot Date.**
  The fallback-disabled drop warning previously keyed on
  `not row_data.get('Snapshot Date')`, which treats a present but
  unparseable cell (e.g. `'not-a-date'`) as "populated" and
  suppresses the note — yet
  `_resolve_rate_recalc_cutoff_date` treats unparseable Snapshot
  Date *the same* as blank (skipping recalc). The condition now
  reuses `excel_serial_to_date(row_data.get('Snapshot Date')) is
  None`, so the note fires consistently with the recalc gate. The
  warning text also updated to read
  "Snapshot Date is blank or unparseable". **New rules:**
  (1) Any filter that drops untrusted data structures MUST also
  handle the all-dropped case — either by forcing the calling
  path to rediscover or by failing loudly. A filter that returns
  an empty list through a success path is a silent-no-op trap.
  (2) Operator-facing "why was this dropped?" notes MUST be
  based on the *parsed/derived* state (the same helper used by
  the business-logic gate), not on raw cell truthiness. Keying
  on raw cells drifts as parser behaviour evolves and produces
  misleading guidance when the cell is malformed. Regression
  tests: new classes in `tests/test_security_audit_followup.py`
  — `TestDiscoveryCacheSchemaGuard` (extended for the `name`
  field), `TestDiscoveryCacheAllDroppedForcesRediscovery`
  (all-malformed raises, partial-drop preserves valid subset,
  empty-cache is not miscategorised), and
  `TestRecalcNoteHandlesUnparseableSnapshotDate` (blank /
  unparseable / valid Snapshot Date behaviour of the note's
  condition).
- [2026-04-23 18:25] PR #176 P2 follow-up: the `wr_num`
  sanitization landed earlier today was inconsistent across the
  upload/delete pipeline. The main loop sanitized `wr_num` at
  derivation (line ~4138) and `generate_excel` sanitized its
  local copy before filename construction, but the upload-task
  builder was reading `wr_numbers[0]` from `generate_excel`'s
  raw return tuple — and `create_target_sheet_map` populated
  `target_map` with *unsanitized* WR# keys pulled straight from
  the target sheet's cells. For any WR whose value gets rewritten
  by `_RE_SANITIZE_HELPER_NAME` (the path-traversal test case
  being the motivating example), the pipeline disagreed with
  itself: the skip-check at line 4283 looked up a sanitized key
  in a raw-keyed map and missed, the upload path at line 4321
  looked up a raw key that diverged from the sanitized filename
  actually on disk, and `delete_old_excel_attachments` received
  a raw WR that did NOT match the sanitized filename prefix of
  the prior run's attachment — causing repeated regeneration and
  orphaned duplicate attachments over time. **Fix:**
  (1) Sanitize target_map keys at populate time inside
  `create_target_sheet_map` using the same
  `_RE_SANITIZE_HELPER_NAME.sub('_', wr_num)[:50]` expression as
  every other site. For realistic numeric WR#s this is a no-op,
  so production data is unaffected. (2) Build the upload task
  from the main-loop sanitized `wr_num` instead of reading
  `wr_numbers[0]` from `generate_excel`'s raw return. The "not
  found in target sheet" warning now also reports the sanitized
  identifier so logs are internally consistent. **New rule:**
  When a sanitizer is added at a derivation site, EVERY
  downstream consumer of that identifier — target-sheet maps
  populated from cells, upload-task dicts, hash-history keys,
  attachment prefix matches, delete-old-attachment filters —
  MUST consume the sanitized value. Sanitization that's only
  applied to ONE path creates a silent split-brain where some
  lookups succeed and others fail, which is worse than no
  sanitization at all. Helper audit: `_RE_SANITIZE_HELPER_NAME`
  is idempotent (applying it twice gives the same result), so
  it's safe to apply at both producer and consumer sites without
  having to reason about which one "owns" the canonicalisation.
  Regression tests: new
  `TestWrIdentifierConsistencyAcrossUploadPath` class in
  `tests/test_security_audit_followup.py` locks in numeric
  no-op behaviour, sanitizer idempotence, sanitized
  source-row + sanitized target_map match, and the inverse
  property that a raw WR must NOT match a sanitized target_map
  (guards against regressing to the P2 bug).
- [2026-04-23 18:50] PR #176 round-3 Copilot review follow-ups.
  Three targeted refinements on top of the security-tightening
  audit: **(1) Misleading operator note.** The
  fallback-disabled `_recalc_note` fired whenever Snapshot Date
  was blank/unparseable, regardless of the row's Weekly Reference
  Logged Date. For rows whose weekly date is also blank,
  unparseable, or pre-cutoff, flipping
  `RATE_RECALC_WEEKLY_FALLBACK=1` would NOT rescue the row — the
  note was sending operators on a false lead. Fix: new helper
  `_weekly_would_trigger_fallback(weekly_raw, cutoff_date) -> bool`
  mirrors the secondary branch of
  `_resolve_rate_recalc_cutoff_date` exactly, and the
  `_recalc_note` gate now requires it to return True before
  suggesting the env var. Wording clarified to
  "Weekly Reference Logged Date is >= RATE_CUTOFF_DATE so setting
  the env var…". **(2) Invisible per-sheet summary.** The summary
  only logged when `skipped > 0` or `recalculated > 0`. If
  fallback rows all hit non-reportable outcomes
  (`invalid_quantity` / `zero_rate`), `fallback_applied` could be
  non-zero while both other counters were zero — zero log output,
  zero visibility into whether the fallback ever fired. Fix:
  added an `elif fallback_applied:` branch that logs a neutral
  `0 recalculated, 0 skipped (N via Weekly-Ref-Date fallback)`
  line. **(3) Misleading type hint.**
  `_redact_exception_message(exc: Exception, …)` actually accepts
  `None` (tests cover that branch as intentional API surface).
  Changed the annotation to `BaseException | None` so callers and
  future refactorers aren't misled. **New rules:** (1) Any
  operator-directed "enable env var X" drop note MUST gate on the
  condition that the env var would actually change this row's
  outcome — otherwise the note is a false lead that wastes
  on-call time. When the gating logic is non-trivial, extract it
  to a helper so the note-gate and the code-gate cannot drift.
  (2) Any counter that tracks an independent code-path dimension
  (`fallback_applied` independent of recalc outcome) MUST have a
  log branch that fires on that dimension alone, or it's a write-
  only metric. (3) Type annotations MUST match what the function
  actually accepts. `exc: Exception` on a function that also
  takes `None` is drift that accumulates (IDE warnings, caller
  refactors, new contributors "fixing" the `None` handling
  because it "shouldn't be possible"). Regression tests:
  `tests/test_security_audit_followup.py` gains
  `TestWeeklyWouldTriggerFallback` (post-cutoff / pre-cutoff /
  blank / unparseable / None-cutoff), `TestRateRecalcSummaryCoversFallbackOnly`
  (decision-surface table showing all three counters gate the
  log), and `TestRedactExceptionMessageSignature` (annotation
  must mention None + behaviour regression guard).
- [2026-04-23 19:15] PR #176 round-4 Codex follow-ups. Two
  findings flagged after the note-gate fix: **(P1) Weekly-Ref-Date
  fallback would re-price whole legacy sheets that never map a
  Snapshot Date column.** The fallback activates whenever
  `row_data.get('Snapshot Date') is None`. On sheets whose
  `column_mapping` doesn't include `Snapshot Date` at all, every
  row has `None` for that field, and the fallback silently
  changed the cutoff basis for the entire sheet instead of
  rescuing current-week automation-lag rows. Fix: compute
  `sheet_has_snapshot_date_column = 'Snapshot Date' in
  column_mapping` once per sheet alongside the existing
  `sheet_has_vac_crew_columns` probe, and pass
  `weekly_fallback_enabled=RATE_RECALC_WEEKLY_FALLBACK and
  sheet_has_snapshot_date_column` into
  `_resolve_rate_recalc_cutoff_date`. Legacy sheets preserve the
  pre-fix "no recalc when Snapshot is absent" behaviour exactly.
  **(P2) `target_map` sanitization could collapse distinct WR#
  cell values to the same key.** Two raw values that differ only
  in stripped characters (`1234/evil` vs `1234\\evil`) or whose
  first 50 chars happen to match yield the same key, and the
  later row silently overwrote the earlier — retargeting uploads
  / deletes at the wrong target-sheet row. Fix: track the raw
  value that first produced each sanitized key and, on
  collision, log a WARNING and keep the first-seen mapping
  (deterministic across runs). Realistic numeric WR#s cannot
  collide, so production data is unaffected. **New rules:**
  (1) Any "rescue" fallback tied to a column's absence MUST be
  gated on the column actually being mapped, not on the row's
  field being falsy — otherwise the rescue becomes a blanket
  re-evaluation on sheets that never had the column. The gate
  belongs at the call site (where `column_mapping` is in scope)
  and should reuse the existing per-sheet flag pattern
  (`sheet_has_<column>_<label>`). (2) When using a lossy
  sanitizer (regex + truncation) as a dict key, collisions MUST
  be detected and surfaced, not silently overwrite. Keep the
  first-seen mapping for determinism and log a WARNING that
  includes BOTH raw values so operators can audit the source.
  Regression tests: new
  `TestWeeklyFallbackGatedOnSnapshotColumn` (3 cases covering
  sheet-has-column rescues row / sheet-lacks-column preserves
  legacy / call-site boolean truth table) and
  `TestTargetMapWrKeyCollisionDetection` (sanitizer produces
  collisions for crafted `/` vs `\\`, truncation collisions at
  the 50-char boundary, first-seen is kept, repeated raw WR#
  doesn't inflate the counter) in
  `tests/test_security_audit_followup.py`.
- [2026-04-23 19:40] PR #176 round-5 Codex P2: `_RE_REDACT_WR` was
  too narrow — it only matched digit-only WR tokens
  (`\bWR\s*[#:=]?\s*\d+`), which caused two leaks into Sentry
  `context_data`: (1) alphanumeric identifiers like
  `WR=ABCD-123` passed through unredacted entirely; and (2)
  path-traversal suffixes like `WR=1234/../evil` redacted only
  the `1234`, leaving `/../evil` in the payload. Fix: broadened
  to `\bWR(?![a-zA-Z])\s*[#:=]?\s*[\w/\\\-.]+`. The negative
  lookahead `(?![a-zA-Z])` prevents over-matching English words
  that start with `WR` (`WRITE`, `WRAP`, `WRITTEN`), and the
  identifier char class includes word chars plus `/ \ . -` so
  decorated, alphanumeric, or path-traversal tokens are captured
  in full. The `+` stops at the first whitespace/delimiter so
  only the identifier itself is redacted, leaving surrounding
  prose intact. **New rule:** When writing a redaction regex for
  an identifier, do NOT assume the identifier shape (digits vs
  alphanumerics vs decorated). The identifier body should accept
  any non-delimiter character and stop at a clear terminator
  (whitespace, comma, quote, paren). Overly-restrictive bodies
  leak attacker-controlled suffixes; the negative lookahead
  guards against over-matching natural-language words. Regression
  tests: `TestRedactExceptionMessage` gains `test_redacts_alphanumeric_wr_identifier`,
  `test_redacts_path_traversal_wr_fully`,
  `test_redact_wr_does_not_swallow_english_prose`, and
  `test_redact_wr_handles_backslash_paths`.
- [2026-04-23 20:10] PR #176 round-6 Codex follow-ups. Two
  correctness gaps promoted by the previous fixes themselves:
  **(P1) target_map collision detection was advisory, not
  protective.** The earlier fix logged a WARNING on sanitized-WR#
  collisions but kept the first-seen mapping and left the key
  usable — a later code path could still upload/delete
  attachments on the wrong target-sheet row when the two WRs
  differed only by stripped characters or shared the first 50
  chars. Fix: on collision, `del target_map[key]` AND add the
  key to a `_quarantined_keys` set. Subsequent re-collisions for
  the same key are also counted and logged. Downstream
  `if wr_num in target_map:` check returns False for BOTH
  (or ALL) ambiguous WRs, so the existing "not found in target
  sheet" warning fires for each, uploads are skipped, and
  operators know to deduplicate the target sheet. A loud
  not-found failure is strictly safer than a silent
  wrong-row upload. **(P2) Fresh-cache fast path could return a
  reduced sheet list on partial cache corruption.** The only
  gate was `_new_from_folders`; a malformed cached entry that
  belonged to a static base sheet (not in
  `_all_folder_discovered_ids`) wouldn't flag new_from_folders,
  so the function returned `_valid_cached_sheets` with one sheet
  silently missing — and it stayed missing until
  `DISCOVERY_CACHE_TTL_MIN` (default 7 days). Fix: introduce
  `_partial_cache_corruption = bool(_raw_cached_sheets) and
  len(_valid_cached_sheets) != len(_raw_cached_sheets)` and add
  `and not _partial_cache_corruption` to the fast-path gate.
  Any drop now forces incremental mode, which re-validates
  base_sheet_ids and rediscovers the dropped sheet on this run.
  A dedicated log line announces the revalidation so the cause
  is visible. **New rules:** (1) A collision-detection guard
  that logs but still returns a value is advisory, not
  protective. If an ambiguous key could drive a side-effecting
  downstream operation (upload, delete, state mutation), the
  guard MUST remove/reject the key, not merely note that it's
  ambiguous. Use "quarantine sets" to guarantee the ambiguity
  cannot leak. (2) Cache fresh-path gates must consider ALL
  failure modes of the preceding validation step, not just the
  externally-visible ones. If a schema filter could have
  dropped an entry that belongs to a statically-required set
  (base_sheet_ids here), the fast path cannot trust its own
  cached output — force incremental/full rediscovery instead.
  Regression tests updated:
  `TestTargetMapWrKeyCollisionDetection::test_collision_quarantines_both_rows`
  (replaces the keep-first-seen test),
  `test_third_colliding_row_is_also_rejected`, and the existing
  `test_identical_raw_wrs_do_not_register_as_collision` now
  asserts the quarantine set stays empty. New class
  `TestDiscoveryCacheFastPathSkipsOnPartialCorruption` covers
  the truth-table of the new gate and the
  `_partial_cache_corruption` detection boolean (empty-cache,
  no-drops, one-dropped, all-dropped).
- [2026-04-23 20:40] PR #176 round-7 Codex follow-ups. Two
  companion issues to the round-6 sanitizer work:
  **(P2) ``build_group_identity`` broke on sanitized WR tokens
  containing underscores.** The parser assumed
  ``parts[2] == 'WeekEnding'`` and extracted ``wr = parts[1]``,
  which is only valid when the WR token has zero underscores.
  But ``_RE_SANITIZE_HELPER_NAME`` converts any non-word / non-
  dash character to ``_``, so an input like ``1234/../evil``
  produces a filename ``WR_1234____evil_WeekEnding_...`` and the
  parser returned ``None``. Downstream attachment-identity flows
  (``_has_existing_week_attachment``,
  ``delete_old_excel_attachments``, stale-variant cleanup) then
  failed to match prior runs' files on disk, causing repeated
  regeneration and orphaned attachment accumulation on any WR#
  whose raw value was sanitization-sensitive. Fix: the parser
  now locates ``WeekEnding`` via ``parts.index(...)`` and joins
  ``parts[1:we_idx]`` for the WR token. Variant-marker detection
  (``Helper`` / ``VacCrew`` / ``User``) is scoped to the
  post-``WeekEnding`` tail so a sanitized WR that happens to
  contain one of those literal tokens cannot false-positive the
  variant. Realistic numeric WR#s still parse identically via
  the same code path. **(P1) Source-side WR# collisions across
  groups.** The main loop uses the sanitized WR as the canonical
  key for ``history_key``, ``target_map`` lookups, and Excel
  filenames. If two source groups have raw WR# values that fold
  to the same sanitized key (within the same week + variant),
  one group's hash history overwrites the other's and both
  groups target the same target-sheet row. Fix: pre-scan
  ``groups.items()`` once before the main loop, build a
  ``defaultdict(set)`` keyed by ``(sanitized_wr, week, variant)``,
  and flag any key mapped by more than one distinct raw WR as
  a ``_quarantined_source_wr_keys`` entry. The per-group skip
  is gated on that set immediately after the main loop's
  sanitization step — a quarantined group is skipped with an
  operator-visible WARNING before touching ``history_key``,
  ``target_map``, or ``generate_excel``. **New rules:**
  (1) Any filename parser that splits on a character and
  asserts a fixed-position marker is fragile if the filename's
  components can legitimately contain that character. Use
  ``list.index(marker)`` + span-joins so the parser degrades
  gracefully rather than returning ``None`` silently — a
  silent-return-None from an attachment-identity parser is a
  repeated-regeneration trap. (2) Whenever a sanitizer collapses
  the keyspace (regex + truncation), the pre-pass that detects
  same-key collisions must run at BOTH endpoints of the key —
  the place the key is constructed (source side, here
  ``groups.items()``) AND the place the key is consumed (target
  side, here ``target_map``). Round-6 fixed the target side;
  this round adds the source side. The symmetry is what keeps
  hash history, upload tasks, and target-row lookups from ever
  being driven by the same ambiguous key. Regression tests:
  new ``TestBuildGroupIdentityWithUnderscoresInWr`` (5 cases —
  plain numeric, sanitized-underscore WR round-trip, VacCrew
  filename, Helper filename, no-``WeekEnding`` fails, WR that
  is literally ``Helper`` but variant stays ``primary``) and
  ``TestSourceWrCollisionQuarantine`` (3 cases — slash/backslash
  collision detected, noise-free on realistic numeric WRs,
  scoped by week AND variant tuple).
- [2026-04-23 21:00] PR #176 round-9 Codex P1: the round-7
  source-collision pre-scan was too narrowly scoped. Keying on
  ``(sanitized_wr, week, variant)`` missed cross-week and
  cross-variant collisions, which still reach ``target_map``
  because downstream routing uses the sanitized WR alone — not
  the tuple. Attack surface: if the target sheet has WR A but
  not WR B (both folding to sanitized K), the target-side
  quarantine at ``create_target_sheet_map`` doesn't fire
  (only one raw seen), and B's source group resolves
  ``target_map[K]`` to A's row, uploading B's Excel to A's
  target-sheet row → cross-WR data corruption. Fix: broaden
  the source-side quarantine key from
  ``(sanitized_wr, week, variant)`` to the sanitized WR alone.
  Any pair of distinct raw WRs folding to the same sanitized
  key anywhere in the run is a collision, and every affected
  group is skipped — regardless of week or variant — with a
  WARNING listing all raw values. Realistic numeric WR#s still
  can't collide (same numeric WR across multiple weeks is
  ONE raw, not a collision), so production remains zero-impact.
  **New rule:** When a sanitizer collapses a keyspace and the
  sanitized key drives downstream routing (target_map,
  attachment identity, filename), collision detection MUST be
  keyed on the sanitized value ALONE — not on any tuple that
  includes context the router doesn't use. Otherwise
  cross-context collisions can slip past the quarantine and
  corrupt routing. The per-context variables (``week``,
  ``variant``) are still part of the *downstream* key that
  disambiguates properly-distinct entries; they are NOT part of
  the collision-detection key because that key tracks "can two
  raws masquerade as one" and is a pure sanitizer-level
  property. Regression tests updated: existing
  ``test_pre_scan_scoped_by_week_and_variant`` removed
  (asserted the old, unsafe invariant); new
  ``test_pre_scan_catches_cross_week_collisions`` and
  ``test_pre_scan_catches_cross_variant_collisions`` lock in
  the broader quarantine. A reusable ``_run_pre_scan`` test
  helper mirrors the production pre-scan so the test drift
  between case-setups is eliminated.
- [2026-04-24 10:50] Production incident: the billing_audit
  attribution-snapshot integration spammed the session log with
  repeated retries against Supabase — HTTP 406 Not Acceptable on
  every call to ``feature_flag``, ``freeze_attribution``,
  ``pipeline_run_select``, and ``pipeline_run_upsert``. Each op
  burned the full 4-attempt × (1.5 + 2.5 + 4.5s) backoff budget
  before each op's circuit breaker tripped independently at 3
  exhaustions. **Root cause:** ``billing_audit/client.py``'s
  ``with_retry`` treated EVERY ``postgrest.APIError`` as
  transient. A 406 from PostgREST is actually a PERMANENT
  rejection — in this case code ``PGRST106`` ("The schema must
  be one of the following: public"), which means the
  ``billing_audit`` schema is not in Supabase's exposed-schemas
  list. No amount of retrying can fix a server-side
  schema-exposure configuration. **Fix (additive,
  production-safe):** (1) New ``_classify_postgrest_error(exc)
  -> (is_transient, is_global_kill, reason_code)`` helper
  inspects ``APIError.code``: codes starting with ``PGRST1`` /
  ``PGRST2`` / ``PGRST3`` and HTTP ``4xx`` stringified codes
  are classified permanent (bail after first attempt); codes
  in ``_PGRST_GLOBAL_KILL_CODES`` (``PGRST106`` schema not
  exposed, ``PGRST301`` / ``PGRST302`` JWT invalid/expired)
  additionally flip a run-global kill switch
  (``_global_disable_reason``). An APIError with no code
  (exotic body-parse failure) and HTTP ``5xx`` codes stay
  transient. (2) ``get_client()`` now returns ``None`` when the
  kill switch is set, so every downstream writer path
  (``freeze_row``, ``emit_run_fingerprint``,
  ``any_flag_enabled``) silently no-ops for the rest of the
  run — identical to the "missing credentials" and ``TEST_MODE``
  paths. Preserves the existing fail-safe contract: a
  misconfigured billing_audit integration must never break the
  billing pipeline itself. (3) New ``_disable_for_run`` emits
  exactly ONE operator-facing WARNING on first trip, naming the
  reason code and pointing at the concrete fix — for PGRST106,
  "Supabase: Project Settings → API → Data API Settings →
  'Exposed schemas': add 'billing_audit', save, and reload the
  schema cache". For PGRST301/302, points at
  ``SUPABASE_SERVICE_ROLE_KEY`` rotation. (4) Non-global
  permanent errors (generic PGRST1xx from a malformed payload,
  etc.) still increment the per-op circuit breaker counter but
  do NOT poison unrelated ops — the existing per-op breaker
  isolation contract is preserved. **New rules:** (1) When
  wrapping a library exception type (``APIError``,
  ``ClientError``) in a retry helper, classify by the
  exception's carried metadata (``code``, ``status_code``,
  SQLSTATE), not by the class itself. Treating a class as
  uniformly transient burns retry budget on permanent errors
  and spams operator logs. The classifier is the single place
  to teach the retry helper which codes are worth retrying.
  (2) When a failure is INTEGRATION-WIDE (schema exposure,
  auth key), a per-op circuit breaker alone is insufficient —
  it measures N endpoints to a schema all failing, which is
  already known from the first failure. Ship a run-global kill
  switch that flips ``get_client()`` to ``None`` on detection
  so the rest of the run skips ALL integration work at the
  zero-network cost. (3) Permanent-error WARNINGs must tell
  operators WHERE TO FIX IT, not just WHAT HAPPENED. For every
  code in ``_PGRST_GLOBAL_KILL_CODES`` the disable message
  names the exact Supabase Dashboard path or env-var to check
  — a 2 AM on-call engineer should not have to read the
  PostgREST docs to understand what to do. (4) The kill
  switch is test-reset-sensitive: ``reset_cache_for_tests``
  MUST clear ``_global_disable_reason`` and
  ``_global_disable_logged`` or one test's tripped state leaks
  into unrelated tests in the same pytest run. Regression
  tests: new
  ``tests/test_billing_audit_shadow.py::PostgrestErrorClassificationTests``
  (11 tests) — classifier contract (global-kill for PGRST106 /
  PGRST301, op-permanent for generic PGRST1xx, permanent for
  HTTP 4xx, transient for HTTP 5xx / missing code), retry
  short-circuit (one attempt on permanent APIError, no
  ``time.sleep`` backoff), global kill (one WARNING with
  "Exposed schemas" text, ``get_client()`` returns None after
  trip, other ops fast-fail without fn invocation), and
  ``reset_cache_for_tests`` resets both new state variables.
  Zero changes to group-processing, Excel-generation, upload,
  or hash-history paths — the billing pipeline itself is
  untouched by this fix.
- [2026-04-24 11:30] Production over-pricing risk on the two
  original-contract folders. Operators report Smartsheet has now
  implemented the post-cutoff rates natively inside each sheet's
  ``Units Total Price`` column for sheets in folders
  ``7644752003786628`` and ``8815193070299012``
  (``ORIGINAL_CONTRACT_FOLDER_IDS``) whenever ``Snapshot Date >=
  2026-04-12`` and ``Units Completed? = true``. The Python-side
  pre-acceptance rate recalc in ``_fetch_and_process_sheet`` was
  still firing on those sheets (the existing gate only excluded
  subcontractor sheets), so for every post-cutoff row the
  Smartsheet-authoritative price was being overwritten in-place
  by ``rate × qty`` from ``NEW_RATES_CSV`` via
  ``recalculate_row_price``. Where the CSV and Smartsheet's
  formula agreed this was a no-op; where they disagreed (CU
  naming drift, work-type parsing edge cases, quantity
  interpretation), the row shipped with an over- or under-billed
  ``Units Total Price``. Root cause, not a symptom — running two
  pricing systems sequentially on the same row is the bug;
  fixing Smartsheet's formula or the CSV individually would not
  have closed the hole. **Fix (additive, production-safe):**
  (1) New env var ``RATE_RECALC_SKIP_ORIGINAL_CONTRACT``
  (default ``'1'`` / True; accepts ``1``/``true``/``yes``/``on``)
  wired into the startup banner alongside
  ``RATE_RECALC_WEEKLY_FALLBACK`` so its resolved state is
  visible on every run. (2) New per-sheet flag
  ``is_original_contract_sheet = source['id'] in
  _FOLDER_DISCOVERED_ORIG_IDS`` computed once alongside
  ``is_subcontractor_sheet`` in ``_fetch_and_process_sheet``;
  ``_FOLDER_DISCOVERED_ORIG_IDS`` is populated unconditionally
  by ``discover_folder_sheets`` at the top of
  ``discover_source_sheets`` on every run (before the
  discovery-cache branch), so the membership test is reliable
  even when the cache is served warm. (3) Composite
  short-circuit ``_skip_recalc_original_contract`` fires only
  when ``RATE_CUTOFF_DATE`` is set AND the env var is on AND
  the sheet is in the ORIG folder AND the sheet is NOT a
  subcontractor sheet — preserving the existing subcontractor
  exclusion as primary (a sheet misconfigured into both sets
  still skips via the subcontractor path and the ORIG skip log
  never duplicates). (4) One ``🛡️`` info log per sheet when the
  guard fires; the row-level gate adds ``and not
  _skip_recalc_original_contract`` to short-circuit at zero
  cost per row without spamming logs. (5) Per-sheet "Rate
  recalc summary" is suppressed on skipped sheets (all counters
  are zero by construction — the summary would be noise). The
  single 🛡️ info log is the authoritative per-sheet signal.
  (6) The "Dropped VAC/helper row" warning's fallback-disabled
  ``_recalc_note`` branch gains ``and not
  _skip_recalc_original_contract`` so operators are not told
  to flip ``RATE_RECALC_WEEKLY_FALLBACK=1`` on sheets where
  doing so would not change anything (recalc is skipped by
  design). **What stays unchanged:** ``recalculate_row_price``,
  ``_resolve_rate_recalc_cutoff_date``,
  ``build_cu_to_group_mapping``, ``load_rate_versions``, the
  Weekly-Ref-Date fallback, the snapshot-keyed primary cutoff
  rule, subcontractor (Arrowhead) sheets' existing "keep
  SmartSheet price" behaviour, and every test currently locking
  in recalc behaviour for non-ORIG sheets. The fix is purely
  additive. **New rules:** (1) When an external system
  (Smartsheet here, any SaaS with server-side formulas) starts
  emitting authoritative values for a column we also compute
  locally, add a per-sheet / per-scope guard that short-circuits
  the local computation rather than trying to reconcile two
  independent sources row-by-row. Sequential double-writes on
  the same field are a silent-corruption trap: where the two
  systems agree, it's a no-op and no one notices; where they
  disagree, the last write wins and the disagreement ships to
  production unaudited. (2) Any such guard MUST be env-gated
  with a default-ON kill switch
  (``RATE_RECALC_SKIP_ORIGINAL_CONTRACT=0`` here) so operators
  can restore pre-fix behaviour if the external system's
  authoritative source breaks, without shipping a code change.
  (3) Log the guard's active state in the startup banner and
  emit one info log per sheet when it fires. Do NOT spam the
  row-level gate with a log — use the per-sheet flag as the
  single announcement surface. (4) Any follow-up operator note
  that suggests an env-var flip (e.g. "set
  ``RATE_RECALC_WEEKLY_FALLBACK=1`` to rescue this row") MUST
  gate on whether the flip would actually change this sheet's
  behaviour. On skipped sheets, tell the operator the correct
  story (or stay silent) — a false lead wastes on-call time.
  Regression tests:
  ``tests/test_subcontractor_pricing.py::TestOriginalContractFolderSkipsRateRecalc``
  (8 tests) covers the env-var wiring (exists + is ``bool``),
  the default folder-ID list (contains ``7644752003786628`` and
  ``8815193070299012``), the truth-table of the guard (fires on
  ORIG + cutoff + env on; does NOT fire on non-ORIG; does NOT
  fire with env off; does NOT fire without cutoff; does NOT
  fire on subcontractor sheets — subcontractor exclusion stays
  primary), and an isolation test that ``recalculate_row_price``
  itself is unchanged by the guard (callers invoking the helper
  directly still get the full recalc behaviour regardless of
  env vars).
- [2026-04-24 14:30] Retired the Python CSV-side rate recalc
  feature in production. Follow-up to the 11:30 entry above:
  rather than rely solely on the per-sheet
  ``RATE_RECALC_SKIP_ORIGINAL_CONTRACT`` guard to protect the
  two original-contract folders, operators decided that since
  Smartsheet's native pricing is now authoritative for those
  folders, the entire CSV-side recalc path should be treated as
  legacy across the production workflow — there is no remaining
  production sheet that needs Python-side post-cutoff rate
  recalculation. **Change:** ``.github/workflows/weekly-excel-
  generation.yml`` now hardcodes ``RATE_CUTOFF_DATE: ''``,
  ``NEW_RATES_CSV: ''``, ``OLD_RATES_CSV: ''`` (was
  ``${{ vars.<NAME> || '' }}``) with a prominent LEGACY comment
  block explaining the retirement and revert path. A repo
  Variable that re-introduces a value is now ignored by the
  workflow — pinning the value at the workflow layer makes the
  decision code-reviewable through git history rather than
  hidden in GitHub Actions UI. **Defense-in-depth on the Python
  side:** ``generate_weekly_pdfs.py`` now emits a WARNING in the
  startup banner whenever ``RATE_CUTOFF_DATE`` is detected,
  pointing operators at this ledger entry. This catches local
  dev shells, ad-hoc scripts, or future workflows that might
  re-introduce the env var by accident. **What stays:** every
  recalc helper (``recalculate_row_price``,
  ``_resolve_rate_recalc_cutoff_date``,
  ``build_cu_to_group_mapping``, ``load_rate_versions``), the
  ``RATE_RECALC_SKIP_ORIGINAL_CONTRACT`` guard from the prior
  commit on this branch, and every existing test. The code is
  retained intentionally so re-enablement is a one-line workflow
  revert (restore the three ``${{ vars.<NAME> || '' }}`` lines)
  rather than a code rewrite. **Docs:** ``website/docs/reference/
  environment.md`` "Rate contract versioning" section now leads
  with a Docusaurus ``:::caution LEGACY`` admonition pointing
  at this entry, and each row in the variable table is prefixed
  with ``(LEGACY)``. **New rules:** (1) When an external system
  takes over a column we used to compute locally AND there is no
  remaining local consumer that benefits from the local
  computation, retire the local feature in the workflow layer
  — do NOT just leave it env-gated. Workflow pinning is
  enforceable through git history; repo-Variable defaults are
  not. (2) Retire vs. delete: keep the code paths intact behind
  the workflow pin if the underlying business problem (post-
  cutoff billing) could realistically come back (rate contract
  renegotiation, new subcontractor, Smartsheet formula
  regression). The marginal carrying cost of retained code +
  tests is much lower than the cost of rewriting the recalc
  pipeline from scratch under incident pressure. (3) When
  retiring an env-var-gated feature, ALSO emit a runtime
  WARNING when the env var is detected — silent retirement is
  a footgun for any developer running locally with stale
  ``.env`` files. The WARNING must point at the ledger entry
  that explains why, not just say "deprecated". (4) Any future
  un-retire of this feature MUST be paired with explicit
  verification that the rows being re-priced are NOT already
  Smartsheet-priced for the same column. The
  ``RATE_RECALC_SKIP_ORIGINAL_CONTRACT`` guard remains the
  default-on protection for the two folders documented in the
  11:30 entry above; if a future engineer disables the guard
  without confirming Smartsheet's formula has been removed
  first, the same silent-corruption trap reopens. No new tests
  are added for this retirement — existing tests in
  ``tests/test_subcontractor_pricing.py``, ``tests/test_vac_crew.py``,
  and ``tests/test_security_audit_followup.py`` already cover
  the retained code paths because they explicitly set
  ``RATE_CUTOFF_DATE`` in setUp/tearDown for isolation. Verified
  via ``pytest tests/`` (393 passed / 17 skipped) post-change.
- [2026-04-25 12:00] Production incident: every WR group in the
  2026-04-24 16:55 weekly run logged paired warnings for
  ``billing_audit[pipeline_run_select]`` (4 retries, "exhausted
  retries") and ``billing_audit[pipeline_run_upsert]`` (1 attempt,
  "immediate failures"), eventually tripping each per-op circuit
  breaker after 3 calls. The ``freeze_attribution`` RPC kept
  returning HTTP 200 OK throughout, isolating the failure to
  the ``pipeline_run`` table. **Two compounding root causes:**
  **(1) Schema drift, P0.** The ``pipeline_run`` reader/writer
  in ``billing_audit/writer.py`` (``emit_run_fingerprint``) was
  introduced on 2026-04-23 in commits ``56ec20a`` / ``1f8213a``
  / ``c44df3d``, but the matching ``CREATE TABLE
  billing_audit.pipeline_run`` was never committed and never
  applied to the deployed Supabase project. PostgREST therefore
  rejected every SELECT/UPSERT with PostgreSQL SQLSTATE ``42P01``
  (undefined_table) — or ``42703`` (undefined_column) on
  partial-deploy environments — surfaced as HTTP 400.
  **(2) Classifier blind spot, P1.**
  ``_classify_postgrest_error`` in ``billing_audit/client.py``
  recognised PGRST1xx/2xx/3xx prefixes and stringified HTTP 4xx
  codes, but did NOT recognise PostgreSQL SQLSTATE codes — even
  though the file's own preamble (``"or a SQLSTATE"`` at the
  ``APIError.code`` comment) acknowledged they were possible.
  When PostgREST returns ``{"code":"42703",...}``, that string
  fell through every check and landed in the catch-all transient
  branch, burning the full 4-attempt × (1.5+2.5+4.5s) backoff
  budget per call before each per-op breaker tripped. The
  asymmetry between SELECT (4 retries) and UPSERT (1 attempt)
  in the log is exactly this: the SELECT 400 carried a parseable
  ``code="42P01"`` (no PGRST/HTTP match → transient), the UPSERT
  400 carried ``code="400"`` from
  ``generate_default_error_message`` (HTTP-permanent match →
  bail). **Fix (additive, production-safe):** (1) Added
  ``billing_audit/schema.sql`` with canonical DDL for
  ``feature_flag``, ``pipeline_run``, and the
  ``freeze_attribution`` RPC parameter contract; ``ALTER TABLE
  … ADD COLUMN IF NOT EXISTS`` blocks let operators apply the
  fix to a partial pipeline_run without dropping data. (2) Added
  ``_PG_SQLSTATE_PERMANENT_PREFIXES = ("22", "23", "42")`` to
  ``billing_audit/client.py`` and a length-gated check in
  ``_classify_postgrest_error`` (only 5-char codes match,
  preventing false-positives against a hypothetical short PGRST
  code). (3) Updated ``billing_audit/__init__.py`` to point at
  ``schema.sql`` from the package docstring. (4) Five new tests
  in ``tests/test_billing_audit_shadow.py::PostgrestErrorClassificationTests``
  cover ``42P01``, ``42703``, classes 22/23 representative codes,
  the retryable SQLSTATE classes (``08``/``40``/``53``/``57``)
  that must NOT be added to the permanent list, and the
  ``len(code) == 5`` guard against short novel codes.
  **What stays unchanged:** the per-op circuit breaker, the
  run-global kill switch (``_disable_for_run``), the
  ``freeze_attribution`` RPC path, every existing classifier
  test, and the billing pipeline itself (Excel generation,
  Smartsheet upload, hash history are all unaffected by
  pipeline_run failures by design — see the 2026-04-24 10:50
  ledger entry's "fail-safe" rule). **New rules:**
  (1) Any new Supabase table or column the pipeline reads/writes
  MUST be defined in ``billing_audit/schema.sql`` in the same
  PR that adds the Python code. The repo cannot have a writer
  whose matching DDL exists only in a Supabase Dashboard
  somebody else's hands. Reviewers MUST block merges that add
  ``client.schema(...).table(...)`` references against a column
  not present in ``schema.sql``. (2) When a retry-classification
  helper accepts an exception type whose ``code`` field is
  documented as multi-source (PGRST codes, HTTP statuses, AND
  SQLSTATEs in our case), every documented source MUST have
  explicit handling AND a regression test. The pre-fix behaviour
  was correct for two of three sources — that's not "good
  enough", that's a silent-degradation trap. (3) When extending
  a code-prefix list (here: SQLSTATE classes), gate the prefix
  check on the format's known length (``len(code) == 5`` for
  SQLSTATEs) so a future PostgREST code that happens to start
  with the same digits cannot be accidentally swept into the
  permanent classification. (4) When adding entries to a
  permanent-prefix list, ALSO add a regression test that
  asserts the *retryable* siblings are NOT included — for
  SQLSTATEs that means ``08`` / ``40`` / ``53`` / ``57``
  classes must remain transient. Otherwise the next PR
  widening the list has no guard against suppressing the very
  conditions the retry loop exists for. Verified via
  ``pytest tests/test_billing_audit_shadow.py::PostgrestErrorClassificationTests -v``
  (22 passed, 54 subtests passed) post-fix.
- [2026-04-25 14:00] Production runtime regression: weekly workflow
  crept from ~1h baseline to 2-3h, often timing out before
  ``TIME_BUDGET_MINUTES=180`` allowed Excel generation to start.
  Operator burned through GitHub Actions minutes on runs that
  produced zero output. **Root cause:** the 2026-04-23 ``freeze_row``
  integration (commits ``56ec20a`` / ``1f8213a`` / ``c44df3d``) added
  a per-row Supabase RPC call inside the main group-processing loop
  in ``generate_weekly_pdfs.py`` (``for _row in group_rows:
  _billing_audit_writer.freeze_row(_row, ...)``) with NO parallelism.
  At ~120ms per ``freeze_attribution`` HTTP round-trip, a busy WR
  group with 30-150 rows costs 3.6-18 seconds purely on serial
  Supabase latency. Across 1900+ groups in a typical run, that
  compounded into ~2 hours of NEW wall-clock time on top of the
  pre-billing_audit ~1h baseline. The 2026-04-24 16:55-17:04
  production log confirmed it directly: ~8 ``freeze_attribution``
  POSTs per second sustained between WR group markers, hundreds in
  a row before each ``Skip (unchanged + attachment exists)`` line.
  **Fix (additive, production-safe):** wrap the ``freeze_row`` loop
  in a ``ThreadPoolExecutor(max_workers=min(PARALLEL_WORKERS,
  len(group_rows)))`` (cap 8, matching every other parallel I/O
  loop in the codebase). Single-row groups skip the executor to
  avoid setup overhead. Future-result iteration via
  ``as_completed`` swallows any unexpected exception per-row with a
  defensive ``logging.exception`` (including the sanitized
  ``__row_id`` so one bad row in a 100-row group can be pinpointed)
  so one bad row cannot kill the group's billing_audit work —
  ``freeze_row`` is fail-safe (catches its own errors). Expected
  speedup: 5-8× on the per-row RPC phase, restoring runtime to
  ~1.2h for a typical run with ~80% completed-row coverage.
  **Thread-safety analysis (the property the parallelization
  relies on, corrected after Copilot review feedback on PR #189):**
  (1) ``_counters`` writes go through ``_bump_counter`` which takes
  ``_counters_lock``. The bare ``dict[k] += 1`` is a multi-bytecode
  read-modify-write (``BINARY_SUBSCR`` → ``BINARY_ADD`` →
  ``STORE_SUBSCR``); the GIL holds each bytecode atomic but a
  thread can be preempted between them, so without the lock two
  threads can both read the counter at N, both compute N+1, and
  both store N+1 — losing one increment. The lock makes counter
  writes exact under any contention level; ``get_counters()``
  also takes the lock so the snapshot is internally consistent.
  (2) ``with_retry`` writes to ``_consecutive_failures`` /
  ``_open_circuits`` are NOT lock-protected today. Without
  protection a worker could observe the counter at 2 and another
  at 3 simultaneously, both classifying "below threshold" and
  producing one extra retry attempt before the breaker trips.
  **The 2026-04-25 inter-attempt re-check** ensures workers that
  started before the breaker opened will exit at the next retry
  boundary (``time.sleep(backoff)`` followed by a re-check of
  ``_open_circuits`` and ``_global_disable_reason``), bounding
  the worst-case retry storm to one extra round per in-flight
  worker. This addresses Codex P1 review feedback that
  parallelization without the inter-attempt check would let an
  outage generate up to 8 workers × 4 attempts = 32 doomed RPCs
  per op before the breaker engaged.
  Acceptable for a fail-safe metrics path. (3) ``get_client()``
  is memoized via ``_client_cache`` so concurrent ``freeze_row``
  callers share the same ``supabase.Client`` instance; the
  upstream library documents thread-safety for HTTP calls.
  **What stays unchanged:** ``freeze_row`` itself (signature,
  return value, error semantics), ``emit_run_fingerprint``
  (already once-per-group via dedup), every existing ``freeze_row``
  test, ``TIME_BUDGET_MINUTES``, ``PARALLEL_WORKERS`` env-var
  contract, and the budget-check at the top of the per-group loop
  (the parallelized inner block STILL counts against the budget;
  the budget guard simply fires on the next iteration). **New
  rules:** (1) Any new per-row I/O call inside the main group
  loop (``for _row in group_rows: api.foo(_row)``) MUST be
  parallelized via ``ThreadPoolExecutor(max_workers=
  min(PARALLEL_WORKERS, len(group_rows)))`` from the start, not
  added serial-first and parallelized later. The cost compounds
  across ~1900 groups × dozens of rows per group; serial-by-default
  is a P0 latency trap. Single-row guard (``if len(group_rows)
  <= 1``) avoids ThreadPoolExecutor setup overhead for the common
  helper / vac_crew variant case. (2) ``ThreadPoolExecutor``
  invocations of fail-safe writers MUST still wrap
  ``f.result()`` in ``try/except Exception`` with
  ``logging.exception`` — if the writer ever regresses and
  raises, the parallel iteration must not poison the rest of
  the group's writes. (3) When extending the per-group
  billing_audit block, also bump
  ``tests/validate_production_safety.py``
  ``validate_per_group_try_catches_all`` window cap to match
  the new block size — the validator scans a fixed character
  window from the block header to confirm the broad
  ``except Exception as _audit_err:`` is still present.
  Regression tests:
  ``tests/test_billing_audit_shadow.py::FreezeRowConcurrencyTests``
  covers (a) 50 concurrent ``freeze_row`` calls produce exactly
  50 counter outcomes (no silent drops, no exceptions) and
  (b) mixed completed / skipped rows under concurrent invocation
  preserve counter accuracy. Verified via ``pytest tests/`` →
  417 passed / 54 subtests passed post-fix (was 415 before; +2
  new concurrency tests).
- [2026-05-15 12:00] Phase 01 (Subcontractor Rate Logic Modification) gap-closure round:
  post-merge code review (``/gsd-code-review 01``) surfaced
  **3 BLOCKER + 6 WARNING + 4 INFO findings (13 total)**
  against the freshly-shipped Phase 1
  variant infrastructure. All 12 actionable findings (excluding
  the reference-only IN-03 ``_txn`` hoist) closed by additive
  plans 01-07 through 01-14. **Root causes** clustered around
  three classes of bug that the upstream unit-test suite did not
  catch because tests exercised helpers in isolation rather than
  the full main-loop attachment-identity / filter pipeline.
  **(1) Identity-tuple drift across the three main-loop sites**
  (CR-01): the per-group ``identifier`` / ``file_identifier``
  construction, the ``valid_wr_weeks`` cleanup-tuple builder, and
  the ``current_keys`` hash-history-prune key all build the same
  identity tuple from row data and must stay in lockstep.
  Pre-fix the new ``aep_billable_helper`` /
  ``reduced_sub_helper`` variants fell through to the legacy
  ``User``-derived ``else`` branch at ALL THREE sites — masked
  by accident because two of the three wrongs (``identifier=''``
  everywhere) cancelled out for hash-history, but the third
  (``file_identifier=''`` versus parsed ``'Jane_Smith'``)
  silently broke ``_has_existing_week_attachment`` matching and
  ``delete_old_excel_attachments`` deletion for every
  helper-shadow attachment on every 2h cron run. Result:
  permanent regeneration churn + orphan accumulation on
  ``SUBCONTRACTOR_PPP_SHEET_ID`` (which had no end-of-run
  cleanup pre-WR-01). **(2) Filter matchers missed the four new
  variant suffix shapes** (CR-02, CR-03): the production
  ``EXCLUDE_WRS`` matcher (no TEST_MODE gate) and the TEST_MODE
  ``WR_FILTER`` matcher each carried four hard-coded suffix
  patterns (``WR``, ``WR_HELPER_*``, ``WR_USER_*``,
  ``WR_VACCREW``) and missed the four new shapes
  (``WR_REDUCEDSUB``, ``WR_AEPBILLABLE``,
  ``WR_REDUCEDSUB_HELPER_*``, ``WR_AEPBILLABLE_HELPER_*``).
  Operator excluding a WR silently uploaded the new variants to
  BOTH target sheets; operator running the documented Step B
  diagnostic command saw zero new-variant output. **(3) PPP
  sheet had no symmetric end-of-run cleanup pass** (WR-01) AND
  **no attachment-prefetch participation** (WR-05): every
  ``_ReducedSub*`` upload to PPP paid an extra per-row
  ``list_row_attachments`` API call, and any identity-drift past
  the per-row delete path silently orphaned attachments
  permanently. Plus six smaller findings: env-var resolution
  asymmetry on ``SUBCONTRACTOR_PPP_SHEET_ID=''`` (WR-02),
  defensive raises on the new helper-shadow filename-suffix
  branches (WR-03), explicit PII markers for the new
  helper-shadow GROUP CREATED logs (WR-04), missing-CU
  attribution loop standardization on ``__source_sheet_id``
  (WR-06), workflow env-var pinning (IN-04), env-overridable
  ``AEP_BILLABLE_CUTOFF`` (IN-01), and explicit ``Quantity``
  coercion (IN-02). **Fix (additive, production-safe across 8
  plans):** all changes are surgical — no existing test
  regresses, ROADMAP Phase 1 success criterion 5
  (byte-identical primary / helper / vac_crew / ORIG-folder
  hashes) preserved. **New rules:**
  (1) **Three-site identity-consistency invariant for new variants.** Extends
  the 2026-04-22 16:05 hash-history rule (per-row fields must
  reach the hash for partition-less variants) and the
  2026-04-23 round-6 ``target_map`` quarantine rule (sanitizer
  endpoints must symmetrize). When adding a new variant whose
  filename embeds an identifier (helper foreman name, vac crew
  name, USER name, future variant), the identity-tuple
  construction MUST be applied at ALL THREE main-loop sites in
  sync: (a) the per-group ``identifier`` / ``file_identifier``
  construction immediately before
  ``history_key = f"{wr_num}|{week_raw}|{variant}|{identifier}"``,
  (b) the ``valid_wr_weeks.add(...)`` cleanup-tuple builder that
  feeds ``cleanup_untracked_sheet_attachments``, AND (c) the
  ``current_keys`` set construction inside the
  ``if history_updates: ... if not _time_budget_exceeded:``
  hash-history-prune block. The three are siblings that ALL
  rebuild the same logical identity tuple; drift between any of
  them silently breaks attachment-identity matching or
  hash-history persistence. Adding a fourth variant in the
  future MUST apply the fix at all three sites simultaneously,
  and the existing source-level grep test in
  ``TestHelperShadowVariantFileIdentifier::test_production_valid_wr_weeks_and_current_keys_carry_shadow_variant_gate``
  is the regression guard.
  (2) **Mirror-matcher invariant for variant-aware filter functions.** Extends the 2026-04-23
  round-7 (and round-9) source-side WR collision-quarantine
  rule: where a sanitizer-driven keyspace requires
  pre-scan-at-both-endpoints symmetry, a variant-driven
  keyspace requires matcher symmetry. Whenever a new variant
  emits a new group-key suffix shape from ``group_source_rows``,
  the ``_key_matches_wr`` AND ``_key_matches_excluded_wr``
  matchers (nested inside ``group_source_rows``) MUST both be
  extended with the new suffix pattern. They are siblings;
  drift between them produces "operator excluded the WR but
  new variants still uploaded" (CR-02) or "operator filtered
  the WR but TEST_MODE produced no new-variant output" (CR-03).
  Existing tests: ``TestExcludeWrsMatchesAllVariants`` +
  ``TestWrFilterMatchesAllVariants``.
  (3) **Explicit PII markers for new INFO-level group-creation logs.** Refines
  the 2026-04-20 12:00 sanitizer rule: that rule said "extend
  ``_PII_LOG_MARKERS`` in the same PR." This round caught a
  fragile-by-accident case where the new helper-shadow GROUP
  CREATED logs matched the substring ``"HELPER GROUP CREATED"``
  only by string containment of the legacy marker. The new
  rule refines: when a new log shares a substring with an
  existing marker, add an EXPLICIT marker for the new text
  body — relying on accidental substring containment is
  fragile to future wording rewordings. WR-04 added explicit
  ``"REDUCED SUB HELPER GROUP CREATED"`` and
  ``"AEP BILLABLE HELPER GROUP CREATED"`` markers.
  (4) **Defensive raise scope discipline.** New rule. When adding a
  defensive ``raise ValueError`` to a NEW branch (e.g., a new
  variant filename-suffix builder), do NOT broaden the raise
  to pre-existing branches with the same code shape — even if
  the legacy branch carries the identical silent-fallthrough
  bug. Legacy branches have a longer test history and unknown
  downstream consumers; broadening the raise risks production
  regression. Add a TODO comment ABOVE the legacy branch
  instead, scoped as follow-up tech-debt cleanup. WR-03's
  regression test
  (``TestHelperShadowSuffixDefensiveRaise::test_legacy_helper_branch_does_not_raise_on_empty_foreman``)
  is the immutability guard.
  (5) **Dual-target cleanup invocation pattern.** Extends the 2026-04-22 16:05 cleanup
  contract (which assumed a single target sheet). When a phase
  adds a SECOND attachment target sheet (Phase 1's
  ``SUBCONTRACTOR_PPP_SHEET_ID``), every defense-in-depth
  layer that operates on TARGET_SHEET_ID MUST be replicated
  for the new sheet: (a) target_map / collision quarantine
  (Plan 04 already), (b) attachment prefetch (Plan 12 /
  WR-05), AND (c) end-of-run
  ``cleanup_untracked_sheet_attachments`` pass (Plan 13 /
  WR-01). Skipping any layer creates an orphan-accumulation
  trap because the per-row ``delete_old_excel_attachments`` is
  correctness-critical but not exception-safe; the end-of-run
  cleanup is the belt-and-suspenders defense and is REQUIRED
  for every target sheet.
  (6) **Env-var override safe-parse pattern.** Extends the 2026-04-23 12:00 env-var hygiene
  rules and the 2026-04-24 14:30 ``RATE_CUTOFF_DATE``
  retirement rule (workflow pinning makes the active feature
  state code-reviewable). When exposing a previously hardcoded
  module constant via an env var (IN-01's
  ``AEP_BILLABLE_CUTOFF``), the resolution MUST: (a) accept
  empty-string as unset (use default), (b) wrap the
  ``strptime`` / ``int`` / ``parse`` call in
  ``try / except (ValueError, TypeError):`` with
  fallback-to-default + error log, (c) name the resolved value
  in the startup banner, AND (d) document the format +
  invalid-value-fallback contract in
  ``website/docs/reference/environment.md``. Operators should
  NEVER be able to crash the loader's module-import with a
  malformed env-var value.
  (7) **Workflow pinning for new feature env vars.** Extends 2026-04-24 14:30 (retired
  CSV-side recalc vars at the workflow layer). Every new
  operator-facing kill switch or feature-default env var MUST
  be pinned in ``.github/workflows/weekly-excel-generation.yml``
  with an explicit default. Workflow pinning makes the active
  feature state code-reviewable through git history; a
  repo-Variable that re-introduces a value can no longer
  silently override the default. Phase 1 added three pinned
  vars (``SUBCONTRACTOR_RATES_CSV``,
  ``SUBCONTRACTOR_PPP_SHEET_ID``,
  ``SUBCONTRACTOR_RATE_VARIANTS_ENABLED``); the optional
  ``AEP_BILLABLE_CUTOFF`` is documented as intentionally unset
  with the override pattern. Regression tests: 8 new classes
  across ``tests/test_subcontractor_pricing.py``
  (TestHelperShadowVariantFileIdentifier,
  TestSubcontractorPppSheetIdEmptyStringDisable,
  TestHelperShadowSuffixDefensiveRaise,
  TestAepBillableCutoffEnvVarOverride,
  TestResolveRowPriceQuantityCoercion,
  TestPhase1GapClosureLedgerEntryPresent) plus
  ``tests/test_security_audit_followup.py``
  (TestExcludeWrsMatchesAllVariants,
  TestWrFilterMatchesAllVariants,
  TestPiiLogMarkersIncludeSubcontractorVariants
  extended +2 methods, TestSourceSheetIdFieldConsistency,
  TestPppCleanupUntrackedAttachments) and
  ``tests/test_performance_optimizations.py``
  (TestPppAttachmentPrefetchBudget). Total: ~55-65 new tests;
  ``pytest tests/`` continues to exit 0 at every
  plan-completion checkpoint.
- [2026-05-16 23:45] **P0 production hotfix — ``_resolve_row_price``
  substring-direction bug.** First post-merge scheduled GHA run
  after Phase 01 shipped (run id 25975684465, 2026-05-16 23:23 UTC)
  produced ``_AEPBillable`` and ``_ReducedSub`` Excel files that
  were **byte-identical** for the same WR+week (verified via SHA256:
  all 8 of 8 AEP+ReducedSub file pairs matched). Total Amount and
  per-row Pricing values were identical across the two variants —
  defeats the entire Phase 1 pricing-divergence contract.
  **Root cause:** ``_resolve_row_price`` at the Work-Type-matching
  block did ``if 'install' in work_type_raw``. This is a substring
  containment check that succeeds when ``work_type_raw == 'install'``
  (full canonical form) but FAILS when it equals ``'inst'`` (the
  4-char abbreviation Smartsheet operators commonly enter) because
  the search string ``'install'`` (7 chars) is NOT contained in the
  shorter ``'inst'`` (4 chars). Same direction error on ``'remov'``
  vs ``'rem'`` and ``'transfer'`` vs ``'trans'``. When all three
  branches missed, the helper fell through to the safety floor:
  ``return parse_price(row.get('Units Total Price'))``. The
  fallback returns the SmartSheet-computed price unchanged, and
  THAT price is the SAME value regardless of which variant called
  the helper — hence byte-identical AEP and ReducedSub files. The
  unique data_hash suffix in each filename (different per variant)
  masked the bug from filename inspection; only byte-comparison or
  content inspection caught it.
  **Why tests missed it:**
  ``TestResolveRowPriceCanonicalColumnNames`` (Plan 03) used
  ``'Install'`` / ``'Removal'`` / ``'Transfer'`` (full canonical
  forms) in every test row. The substring direction is correct for
  the full form. The bug only manifests on abbreviations, which the
  test corpus never exercised. Coverage gap: the test corpus did
  not mirror the actual Smartsheet operator-entered values.
  **Fix (additive, surgical):** in ``_resolve_row_price``, change
  the three substring checks from ``'install'`` / ``'remov'`` /
  ``'transfer'`` to the shorter forms ``'inst'`` / ``'rem'`` /
  ``'tran'`` (with ``'xfr'`` as a second clause for the
  transfer category, mirroring ``recalculate_row_price`` at
  L1655's existing pattern: ``elif 'tran' in work_type_raw or
  'xfr' in work_type_raw``). The shorter prefixes match BOTH the
  abbreviated AND full canonical forms — operator drift in
  either direction stays bug-free.
  **New rule — Substring direction discipline for abbreviation-
  tolerant matchers.** When a string matcher needs to accept BOTH
  abbreviated and full forms of an operator-entered value, the
  ``A in B`` substring check must use the SHORTEST UNAMBIGUOUS
  PREFIX as ``A``. ``'install' in 'inst'`` is False (the search
  string is longer than the haystack); ``'inst' in 'install'`` is
  True. The matcher must search FOR the prefix WITHIN the
  user-entered value, not the other way around. This rule
  generalises across the codebase: any future categoriser that
  needs to handle Smartsheet operator-entered abbreviations
  (e.g., column-type detection, work-type categorisation, status
  matching) MUST use the prefix-as-A direction. The existing
  ``recalculate_row_price`` and
  ``recalculate_row_price_using_original_rate_columns`` patterns
  at L1655 and L1705 are the correct analogs — copy their shape.
  **Corollary — test corpus must mirror production data shape.**
  When adding regression tests for a parser/matcher that consumes
  Smartsheet column data, the test rows MUST include the
  abbreviated forms operators actually enter (``'Inst'``,
  ``'Rem'``, ``'Trans'``, ``'Xfr'``), not just the canonical
  full forms. Full-form-only test coverage on a substring matcher
  is a silent-pass trap: the test corpus runs through the
  matcher's happy path while real production data never does.
  Regression test class
  ``TestResolveRowPriceAbbreviatedWorkType`` in
  ``tests/test_subcontractor_pricing.py`` (14 methods) covers
  the abbreviated forms (``'Inst'``, ``'Rem'``, ``'Trans'``,
  ``'Xfr'``) for both AEP and ReducedSub variants plus helper-
  shadow variants, includes regression guards for the full forms,
  AND has an explicit ``test_unknown_work_type_falls_through_to_smartsheet``
  test that locks in the safety-floor behaviour for truly unknown
  work types so the fix does not over-broaden. ``pytest tests/``
  now reports **623 passed / 22 skipped / 58 subtests** (was
  609 / 22 / 58 pre-fix; +14 net, zero regressions).
- [2026-05-20 00:26] Phase 1.1 (Subcontractor Helper-Shadow Rescue +
  Variant Partition + Claim-History Attribution) closure: post-PR
  #203 + PR #206 operator report surfaced THREE production bugs
  latent in Phase 01 plus ONE new feature requirement (claim-history
  attribution for subcontractor helper line items). The 2-cycle
  ``/gsd-debug`` session (cycle 1 surfaced two wrong hypotheses
  F1 / F2; cycle 2 operator-evidence-driven correction identified
  the four real failure modes) drove a 5-plan / 5-wave gap-closure
  phase. **Root causes:**
  **(1) Bug A — Pre-acceptance helper-row rescue gap.** Subcontractor
  helper rows drop at the row-acceptance gate at
  ``_fetch_and_process_sheet`` because ``has_price=False`` (operator
  workflow leaves ``Units Total Price`` blank/zero while helper work
  is awaiting acceptance). Phase 01's ``_resolve_row_price`` lives
  downstream inside ``generate_excel`` and cannot rescue these rows.
  Fix (Plan 01.1-01): extended the [2026-04-23 00:00] VAC-crew
  pre-acceptance rescue pattern to subcontractor sheets via a NEW
  ``_subcontractor_rescue_price`` helper + an additive
  ``if is_subcontractor_sheet and SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED
  and price_val <= 0:`` branch alongside the existing primary-rate
  gate. The ``_SUBCONTRACTOR_RATES`` dict (Phase 1 plan 01-01) is
  the rate source — no CSV re-read. Kill switch
  ``SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED`` default ``'1'``;
  workflow-pinned per IN-04.
  **(2) Bug B1 — Variant tagging is additive, not partitioning, for
  subcontractor rows.** ``group_source_rows`` was appending THREE
  keys to ``keys_to_add`` for every non-helper subcontractor row:
  legacy ``primary`` AND ``reduced_sub`` AND (when post-cutoff)
  ``aep_billable``. The legacy primary file shipped to
  TARGET_SHEET_ID was a byte-equivalent duplicate of the
  ``_ReducedSub`` file (because SmartSheet pricing on sub sheets is
  operator-configured to match reduced-sub CSV rates). Fix (Plan
  01.1-02): hoist ``is_subcontractor_row`` to the top of the per-row
  loop and add ``not is_subcontractor_row`` to the primary-emission
  gate; subcontractor non-helper rows now emit ONLY variant keys
  (partitioning, not additive). Plan 01-03 Test 1's "additive"
  assertion is overridden — see rule (b) below.
  **(3) Bug B2 — Stale primary-shape file on SUBCONTRACTOR_PPP_SHEET_ID.**
  A historical attachment from a pre-Phase-01-routing-matrix period
  was being legitimized every run by Bug B1's ``valid_wr_weeks``
  contribution. Bug B1's structural fix self-resolves the source
  side; Plan 01.1-03 adds belt-and-suspenders defense-in-depth at
  the cleanup site: ``cleanup_untracked_sheet_attachments`` accepts
  an optional ``variant_whitelist: set[str] | None = None`` kwarg;
  the PPP call site passes ``{'reduced_sub', 'reduced_sub_helper'}``.
  Any other variant on PPP is unconditionally deleted regardless of
  ``valid_wr_weeks`` state and ``KEEP_HISTORICAL_WEEKS``. TARGET
  cleanup passes ``None`` to preserve byte-identical legacy behaviour.
  **(4) Bug C — Per-row claim-history attribution (NEW feature).**
  Helper files for a subcontractor WR previously contained the full
  row set regardless of WHICH helper actually claimed each row.
  Plan 01.1-04 partitions helper file row sets by per-row attribution
  from ``billing_audit.attribution_snapshot`` via a NEW
  ``lookup_attribution(p_wr, p_week_ending, p_smartsheet_row_id)``
  RPC. Each row appears ONLY in the helper file of whoever was the
  active ``Foreman Helping?`` at the moment that row's
  ``Helping Foreman Completed Unit?`` was first observed checked
  (first-write-wins per ``freeze_attribution`` semantics). D-12
  fall-back-to-current-helper preserves Phase 1 behavior on reader
  failure with operator-facing per-WR WARNINGs naming the reason
  (``no_history`` / ``fetch_failure`` / ``disabled``). Kill switch
  ``SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED`` default ``'1'``;
  workflow-pinned per IN-04. Scoped to subcontractor rows ONLY per
  D-15 — the legacy ``_HELPER_<name>`` flow continues to use the
  current Smartsheet ``Foreman Helping?`` value unchanged. Plan
  01.1-05 adds the SUB-12 idempotent hash-history one-time prune
  (drops orphan subcontractor primary entries left by pre-Bug-B1
  runs via the ``PHASE_1_1_HASH_PRUNE_VERSION`` constant + ``_phase_prune_version``
  sentinel persisted into ``hash_history.json``), the true
  end-to-end integration test suite, the D-22 Plan 01-03 Test 1
  rewrite, the ``TestLookupAttribution`` unit class, and this
  Living Ledger entry.
  **New rules:**
  (1) **2-cycle ``/gsd-debug`` methodology.** When a ``/gsd-debug``
  session produces a Root Cause Report, the FIRST cycle's
  hypotheses are NOT authoritative until operator evidence
  confirms them. For Phase 1.1 the cycle-1 hypotheses F1 / F2
  were wrong (they posited a Smartsheet column-mapping drift and
  a variant-tagging-disabled state); cycle-2 operator evidence
  (the actual TARGET sheet contents + operator narrative about
  blank ``Units Total Price``) identified the four real failure
  modes. Future debug sessions on row-flow or attachment-flow
  bugs MUST close the cycle by re-validating the hypothesis
  against operator-visible evidence — DO NOT ship a fix on
  cycle-1 hypotheses alone, even when they look plausible. The
  cost of a wrong fix is a new ledger entry + an additional
  release cycle; the cost of one extra round of operator-evidence
  validation is a half-hour delay.
  (2) **Plan 01-03 Test 1 design-intent override.** Plan 01-03's
  test ``test_kill_switch_disables_new_variant_emission`` was
  authored under the additive contract — subcontractor rows
  produced ``_AEPBILLABLE`` + ``_REDUCEDSUB`` IN ADDITION TO the
  legacy primary key. Phase 1.1 Bug B1 inverts this for
  subcontractor rows only: they now produce ONLY the variant
  keys (partitioning, not additive). The test was rewritten IN
  PLACE in Plan 01.1-05 (preserving the test method name + class
  to retain git-blame-traceability) with an explicit docstring
  citing this Living Ledger entry. A new
  ``test_partitioning_contract_for_subcontractor_non_helper_rows``
  method was added alongside to assert the post-Phase-1.1
  invariant directly. The override is SCOPED to subcontractor
  rows — primary / original-contract / vac_crew rows continue to
  emit the legacy primary key unchanged. Future plans that
  invert a Phase-N test contract MUST: (a) rewrite the test
  in place (preserve class + method names for git-blame), (b)
  add a docstring citing the new Living Ledger entry, (c) add a
  sibling test method asserting the new invariant directly so the
  rewrite is auditable as "extending the contract" rather than
  "weakening the contract".
  (3) **Pre-acceptance-rescue-generalization rule.** Any future
  feature that introduces a NEW pricing surface — CSV-driven,
  RPC-driven, formula-driven, whatever the source — that diverges
  from the legacy ``Units Total Price`` column MUST include a
  parallel pre-acceptance rescue path OR explicitly document why
  the rows it serves never have blank ``Units Total Price``. The
  acceptance gate at ``_fetch_and_process_sheet`` is the single
  point where blank-price rows drop; a new pricing surface that
  doesn't rescue there is silently invisible to downstream variant
  emission. The VAC-crew Weekly-Ref-Date fallback
  ([2026-04-23 00:00]) was the first instance of this rule; the
  Bug A subcontractor rescue (Plan 01.1-01) is the second.
  Generalize the rule to NEW pricing surfaces going forward —
  document the rescue path in the same PR as the new pricing
  surface, not as a follow-up. The rescue MUST be env-gated with
  a default-ON kill switch (clone the
  ``SUBCONTRACTOR_RATE_RECALC_PREACCEPTANCE_ENABLED`` pattern) so
  operators can revert to pre-fix dropping behaviour without
  shipping a code change.
  (4) **Test-methodology rule.** Any plan that fixes a row-flow
  bug — acceptance gate, ``group_source_rows``, ``generate_excel``
  — MUST add at least one true end-to-end test driving the full
  pipeline. Static mirror classes (the
  ``TestHelperShadowVariantFileIdentifier`` pattern at
  ``tests/test_subcontractor_pricing.py``) DO NOT count — they
  pass even when the upstream classifier or acceptance gate is
  broken (exactly the failure mode that allowed Phase 1 to ship
  with Bugs A and B1 latent in production). Plan 01.1-05 added
  ``tests/test_subcontractor_helper_shadow_rescue.py`` containing
  ``TestEndToEndPipeline`` (drives ``group_source_rows`` on
  synthetic Smartsheet rows with mocked ``lookup_attribution`` and
  asserts on emitted group keys), ``TestBugB2WhitelistE2E``
  (drives ``cleanup_untracked_sheet_attachments`` with the
  whitelist kwarg and asserts on
  ``client.Attachments.delete_attachment`` call shape),
  ``TestHashPruneIdempotency`` (drives
  ``_run_phase_1_1_hash_prune`` directly with synthetic
  ``hash_history`` + ``groups`` dicts and asserts the version
  gate + scope discipline + log discipline), and
  ``TestProductionCodeSiteInvariants`` (source-level grep guards
  for the four upstream production fixes, the hash-prune constant,
  and the new PII marker registration). Future row-flow bug fixes MUST
  include the same shape of end-to-end coverage; reviewers MUST
  block PRs that don't.
  Regression tests: 4 new test classes in
  ``tests/test_subcontractor_helper_shadow_rescue.py``
  (TestEndToEndPipeline / TestBugB2WhitelistE2E /
  TestHashPruneIdempotency / TestProductionCodeSiteInvariants —
  28 test methods total covering SUB-08..SUB-12 through real
  production code paths); ``TestLookupAttribution`` added to
  ``tests/test_billing_audit_shadow.py`` (14 test methods
  covering the Plan 01.1-04 reader's documented behaviors
  INCLUDING the op-isolation invariant + PGRST106 global-kill
  behavior — 4 of those 14 are skipped on dev environments
  without ``postgrest`` installed, mirroring
  ``PostgrestErrorClassificationTests``); D-22 rewrite of
  ``TestSubcontractorVariantKillSwitchAndScope::test_kill_switch_disables_new_variant_emission``
  alongside a new ``test_partitioning_contract_for_subcontractor_non_helper_rows``
  in ``tests/test_subcontractor_pricing.py`` (~43 net new tests
  total across the three test files). ``pytest tests/`` exits 0
  with **682 passed / 26 skipped / 58 subtests** post-Phase-1.1
  closure (was 643 / 22 / 58 at Wave 4 baseline; gain of 39 net
  passing and 4 net skipped on the postgrest-gated APIError tests).
- [2026-05-19 22:00] **Phase 01.1 Plan 06 — SUB-09 helper-path
  partition gap-closure.** UAT-confirmed duplicate-billing artifact
  (live run 26138204743): WR_90773033 wk 041226 foreman Chris_Lopez
  produced BOTH a legacy ``_Helper_Chris_Lopez.xlsx`` on TARGET_SHEET_ID
  AND the correct ``_ReducedSub_Helper_Chris_Lopez.xlsx`` on PPP. The
  Phase 01.1-02 Bug-B1 fix applied ``not is_subcontractor_row`` to the
  **primary** emission path in ``group_source_rows`` but forgot to apply
  the same guard to the **legacy helper** emission path at
  ``keys_to_add.append(('helper', helper_key, helper_foreman))``.
  **Root cause — D-09 helper-path asymmetry.** The legacy-helper block
  and the primary-key block sit in different branches of the per-row
  loop; Bug-B1's ``is_subcontractor_row`` hoist was in scope at the
  legacy-helper block but the guard was never applied there, so every
  subcontractor helper row continued to emit the legacy helper key
  unconditionally. **Symmetric fix (additive, surgical):** wrapped the
  ``keys_to_add.append(('helper', ...))`` call in
  ``if not is_subcontractor_row:`` with an operator-visible INFO log
  inside; added an ``else:`` DEBUG log (body ``"EXCLUDING from main
  Excel (subcontractor legacy helper): ..."`` — covered by existing
  ``"EXCLUDING from main Excel"`` PII marker). Three-site identity
  invariant: Sites 2 (``valid_wr_weeks``) and 3 (``current_keys``)
  self-heal because both derive from ``groups/__variant``; the producer
  fix removes the subcontractor ``'helper'`` group from ``groups`` so
  neither site emits the orphan key. **Cleanup of pre-existing
  duplicate attachments** via ``cleanup_untracked_sheet_attachments``:
  new optional params ``sub_wr_scope: set[str] | None`` and
  ``sub_offcontract_variants: set[str] | None`` let the TARGET call site
  pass the subcontractor WR set + ``{'helper', 'primary'}`` as
  off-contract variants; any TARGET attachment for a subcontractor WR
  with a ``helper`` or ``primary`` filename variant is unconditionally
  deleted regardless of ``valid_wr_weeks`` or ``KEEP_HISTORICAL_WEEKS``.
  Kill switch ``SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED`` (default
  ``'1'``; workflow-pinned in ``weekly-excel-generation.yml``) gates the
  destructive scope-building step — when off, TARGET cleanup reverts to
  pre-SUB-09 behaviour exactly. **6-part-key hash-prune trap.** The
  existing ``_run_phase_1_1_hash_prune`` (v1) had a fatal
  ``if len(_parts) != 4: continue`` guard that silently skipped ALL
  helper hash keys — helper keys are 6-part pipe-separated
  (``wr|week|helper|foreman|dept|job``), not 4-part. Bumped
  ``PHASE_1_1_HASH_PRUNE_VERSION = 1`` → ``= 2``; the v2 prune uses
  ``< 4`` as the minimum-length guard and index-accesses
  ``_parts[0]``/``_parts[2]`` so 4-part, 5-part, and 6-part keys all
  parse correctly; orphan condition extended to
  ``or _hk_variant == 'helper'`` so subcontractor legacy helper entries
  are pruned in one pass alongside primary orphans. **WR-sharing
  prune edge case.** ``_build_subcontractor_wr_scope(groups)`` was
  extracted as a module-level shared helper and used by BOTH the
  cleanup call site AND ``_run_phase_1_1_hash_prune`` to prevent scope
  drift. The scope set is the union of WR numbers seen in any
  subcontractor variant group (``reduced_sub``, ``aep_billable``,
  ``reduced_sub_helper``, ``aep_billable_helper``) so a WR that has
  subcontractor rows but whose hash history entry happens to share a WR
  number with a non-subcontractor group still gets pruned correctly.
  **New rules:**
  (1) **Helper-path partitioning must mirror primary-path partitioning.**
  Whenever a partition guard (``not is_X_row``) is added to the primary
  emission block in ``group_source_rows``, the SAME guard MUST be applied
  to the legacy helper emission block in the same commit. The two blocks
  are siblings that both feed ``keys_to_add``; omitting the guard from
  one while applying it to the other produces a byte-duplicate on
  TARGET_SHEET_ID for every row of the gated type. Code-review checklist:
  grep ``keys_to_add.append(('helper'`` and verify every
  ``if not is_X_row:`` guard that protects the primary emission also
  wraps the helper emission.
  (2) **Multi-part hash-key parsers must use minimum-length guards, not
  exact-length guards.** ``!= N`` silently drops every key whose part
  count differs from N. Use ``< M`` where M is the minimum number of
  parts needed for a valid parse, then index-access only the parts you
  use. This applies to any future hash-history, attachment-identity, or
  group-key parser that encounters keys from multiple variants with
  different part counts.
  (3) **Shared scope-builders prevent cleanup/prune drift.** When both
  ``cleanup_untracked_sheet_attachments`` and ``_run_phase_1_1_hash_prune``
  need to agree on which WRs are "in scope for subcontractor cleanup",
  extract a single ``_build_subcontractor_wr_scope(groups)`` helper and
  call it from both sites. Two inline loop copies will silently diverge
  as variant names change. The shared helper is the single source of
  truth; add a regression test that asserts both call sites agree.
  (4) **Kill switches for destructive cleanup paths.** Any new
  ``cleanup_untracked_sheet_attachments`` call that deletes attachments
  from TARGET_SHEET_ID based on a VARIANT-CLASS criterion (not just
  stale-week pruning) MUST be env-gated with a default-ON kill switch
  following the ``SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED`` pattern.
  Workflow-pin the switch per the IN-04 / 2026-04-24 14:30 rules.
  Regression tests: ``TestEndToEndPipeline`` in
  ``tests/test_subcontractor_helper_shadow_rescue.py`` gains 2 methods
  (``test_subcontractor_helper_row_does_not_emit_legacy_helper_key`` and
  ``test_subcontractor_helper_row_pre_cutoff_emits_only_reducedsub_helper``);
  new class ``TestLegacyHelperTargetCleanupE2E`` (2 methods) validates
  sub-WR cleanup vs. non-sub WR preservation; ``TestHashPruneIdempotency``
  gains 2 methods for v2 6-part-key pruning + idempotency; 3 v1-contract
  tests rewritten in-place (citing this ledger entry per [2026-05-20
  00:26] rule 2). ``TestProductionCodeSiteInvariants``
  hash-prune-version regex updated from ``= 1`` → ``= 2``.
  ``TestPppCleanupUntrackedAttachments.test_cleanup_function_signature_unchanged``
  in ``tests/test_security_audit_followup.py`` updated for the two new
  params. ``pytest tests/`` exits 0 with **688 passed / 26 skipped /
  58 subtests** (was 682 at Phase 1.1 close; +6 net tests).
- [2026-05-19 23:45] Plan 01.1-06 post-merge code-review follow-up
  (WARNING WR-01 + INFO IN-01) on the SUB-09 helper-dimension TARGET
  cleanup landed earlier this session. **WR-01 (data-loss / churn
  loop, fixed):** the new TARGET ``cleanup_untracked_sheet_attachments``
  off-contract gate keys its in-scope set (``sub_wr_scope``, built by
  ``_build_subcontractor_wr_scope`` from this run's ``_REDUCEDSUB``
  group keys) on the WR# ALONE, but ``is_subcontractor_row`` is decided
  PER-ROW by source-sheet membership in ``_FOLDER_DISCOVERED_SUB_IDS``.
  Grouping in ``group_source_rows`` is global across all discovered
  sheets, so a single WR# can legitimately have helper rows on a
  subcontractor sheet (→ ``_ReducedSub_Helper_`` ⇒ WR enters
  ``sub_wr_scope``) AND on a NON-subcontractor sheet (→ a legitimate
  live ``_Helper_<name>.xlsx`` on TARGET, variant ``'helper'``). The
  gate appended such an attachment to ``off_contract_attachments`` and
  ``continue``d BEFORE reaching the ``valid_wr_weeks`` keep-newest
  logic, so it deleted the live file unconditionally — every 2h cron
  run: delete → regenerate → re-upload → delete, with a data-absent
  window on TARGET between cleanup and the next upload. **Fix
  (surgical, additive):** add ``and ident not in valid_wr_weeks`` to
  the SUB-09 gate condition. The 4-tuple ``ident``
  (``wr, week, variant, identifier``) parsed by ``build_group_identity``
  matches the ``valid_wr_weeks`` tuple shape exactly, so a genuinely
  orphaned legacy sub-helper file — which Task 1 stopped emitting and
  is therefore NEVER in ``valid_wr_weeks`` — is still deleted, while a
  live non-sub artifact for an overlapping WR is preserved. **IN-01
  (benign, documented not tightened):** the ``_run_phase_1_1_hash_prune``
  helper clause ``or _hk_variant == 'helper'`` matches a ``'helper'``
  key at any part count, broader than the documented 6-part production
  shape (``wr|week|helper|foreman|dept|job`` — 6 parts because the
  helper ``identifier`` is itself ``f"{foreman}|{dept}|{job}"`` at
  ``generate_weekly_pdfs.py`` ``history_key`` construction). Left broad
  on purpose: the prune is one-time (version-sentinel gated) and only
  DROPS a hash-history entry — forcing at most one benign regeneration,
  never a file deletion — so the same cross-sheet-overlap case is
  harmless on the prune path. Only the comment was aligned. **New
  rules:** (1) **Scope-set granularity must match the routing key.**
  When a cleanup/prune scope set is keyed on a coarser dimension than
  the decision it gates (here: WR# alone vs. the per-row, per-sheet
  ``is_subcontractor_row``), any consumer that DELETES based on that set
  MUST exempt identities the current run validated (``valid_wr_weeks``
  membership, or the live-key equivalent). The coarse scope set is a
  necessary-not-sufficient condition; the live-identity check is what
  prevents a legitimate same-key artifact in the other dimension from
  being destroyed. (2) **Distinguish delete-paths from drop-paths when
  triaging a cross-key-collision finding.** A path that DELETES a
  Smartsheet attachment (every-run TARGET cleanup) is a P1 data-loss
  surface and needs the live-identity exemption; a path that only DROPS
  a local hash-history key (the version-gated prune) self-heals via
  regeneration and is benign — do NOT over-engineer a live-key
  exemption onto a drop-path one-time migration when the file is never
  deleted. Per [2026-04-22] the safe default everywhere in this engine
  is "regenerate", so a dropped hash key costs one rebuild, not data.
  Regression test:
  ``tests/test_subcontractor_helper_shadow_rescue.py::TestLegacyHelperTargetCleanupE2E::test_target_cleanup_exempts_live_helper_for_overlapping_sub_wr``
  drives ``cleanup_untracked_sheet_attachments`` with an in-scope WR
  carrying BOTH a live ``_Helper_`` (identity in ``valid_wr_weeks`` —
  asserted NOT deleted) and a stale orphan ``_Helper_`` (identity
  absent — asserted deleted). ``pytest tests/`` → **689 passed / 26
  skipped / 58 subtests** (was 688; +1).
- [2026-05-20 13:45] Foundation A (claim-attribution read layer +
  HOLD contract) shipped — sub-project A of the "universal per-line-item
  claim attribution" effort (every Excel file partitioned by the FROZEN
  foreman who claimed each line item, across primary / helper / vac_crew
  on both the primary and subcontractor workflows). A is the read +
  contract foundation ONLY: **zero production behaviour change**
  (``generate_weekly_pdfs.py`` is NOT modified; nothing consumes the new
  contract yet). Spec: ``docs/superpowers/specs/2026-05-20-claim-
  attribution-foundation-design.md``; plan: ``docs/superpowers/plans/
  2026-05-20-claim-attribution-foundation.md``. **What landed:**
  (1) The Supabase ``lookup_attribution`` RPC contract in
  ``billing_audit/schema.sql`` now returns ALL frozen roles
  (``primary_foreman, helper, helper_dept, vac_crew, source_run_id``)
  with per-role ``#NO MATCH``/blank → ``NULL`` normalization centralized
  in the SQL (``CASE WHEN s.frozen_* LIKE '#%' OR btrim(...) = '' THEN
  NULL``). OPERATOR must apply the ``CREATE OR REPLACE`` + reload the
  PostgREST schema cache (``NOTIFY pgrst, 'reload schema';``) for the
  feature to be live; adding columns is backward-compatible with the
  prior helper-only consumer. (2) ``billing_audit/writer.py`` gains
  ``_lookup_attribution_all(wr, week_ending, row_id) -> (row, status)``
  (status ∈ ``success`` / ``no_row`` / ``fetch_failure`` /
  ``unavailable``) sharing the existing ``with_retry(op=
  "lookup_attribution")`` retry/circuit-breaker; the public
  ``lookup_attribution`` was refactored to a thin helper-gated wrapper
  over it with **external behaviour preserved** (guarded by the
  pre-existing 14-test ``TestLookupAttribution`` suite — the regression
  proof for the refactor). (3) ``resolve_claimer(variant, current_value,
  *, wr, week_ending, row_id, enabled) -> ResolveOutcome`` + a module
  ``ROLE_BY_VARIANT`` map are the shared decision contract B/C/D will
  call. The six-row decision table: ``enabled`` False → use current
  (``disabled``); client-None-not-outage → use current (``disabled``);
  ``fetch_failure`` (outage / run-global kill / retries exhausted) →
  **HOLD**; ``no_row`` or blank role on the frozen row → use current
  (``no_history``); role present → use **frozen**. (4) A dormant hold
  counter (``record_attribution_hold`` + ``summarize_attribution_holds``,
  ``attribution_rows_held`` pre-seeded in ``_counters`` for a stable
  schema) emits ONE PII-safe aggregate WARNING (counts + sanitized WR
  only) so a Supabase outage that suppresses files is loud, not silent.
  **New rules / contracts for the downstream sub-projects (B/C/D/E):**
  (1) **Correctness over availability.** When attribution can't be
  trusted, HOLD the affected rows (don't emit a possibly mis-attributed
  billing file) rather than fall back. ``HOLD`` is returned ONLY on a
  genuine ``fetch_failure`` outage — a brand-new claim is ``no_history``
  and uses the CURRENT foreman (this run is what freezes it), NOT a
  HOLD. The precision win over the prior sub-helper heuristic: a
  transient outage that exhausts retries is now ``fetch_failure`` →
  HOLD (the call object came back ``None``), distinct from "the call
  succeeded with zero rows" (``no_row`` → use current). Any consumer
  acting on ``resolve_claimer`` MUST defer the row when
  ``outcome.action == 'hold'`` and call ``summarize_attribution_holds``
  once at end-of-run. (2) **Claimer-file coexistence & no-cross-delete
  invariant (governs B/C/D).** Each file holds ONLY one foreman's
  claimed line items, named after that foreman; attribution is
  **frozen first-write-wins per row**. A foreman switch within the SAME
  week-ending period produces a SECOND file (new foreman's name, only
  their rows) and the prior foreman's file MUST remain — the two must
  NEVER cross-delete. This holds because the foreman name is part of
  the identity tuple ``(wr, week, variant, identifier=foreman)``; two
  claimers on the same WR+week+variant are distinct identities → the
  attachment cleanup keeps both (it only prunes older copies WITHIN the
  same identity). Every variant rollout (B/C/D) MUST carry a regression
  test proving two same-week claimers coexist. (3) **The freeze side
  already captures all roles** — ``freeze_row`` writes
  ``frozen_primary``/``frozen_helper``/``frozen_vac_crew`` for every
  completed row across all sheets; B/C/D do NOT need new capture, only
  to consume ``resolve_claimer`` + extend grouping/filenames + handle
  the existing-attachment migration. (4) **Sequencing:** A → B
  (subcontractor primary ReducedSub/AEPBillable by ``frozen_primary``)
  → C (VAC crew by ``frozen_vac_crew``) → D (primary-workflow primary
  foreman; highest blast radius — changes core primary grouping +
  largest attachment migration; deliberately last) → E (Supabase
  hash-store migration + stripping ``_<hash>``/``_<timestamp>`` tokens
  from filenames, which depends on Supabase being the change-detection
  source of truth). Sub-helper shadow (Phase 1.1) is already done and
  was operationally unblocked 2026-05-20 when the data team deployed the
  ``lookup_attribution`` RPC. (5) **A does NOT own a kill-switch flag**
  — ``resolve_claimer`` takes ``enabled`` as a parameter; each consumer
  passes its own flag (the existing
  ``SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED`` is untouched).
  B/C/D decide whether to share one universal flag or per-variant flags.
  Executed via subagent-driven-development (6 atomic TDD tasks, each
  with spec-compliance + code-quality review). Regression tests added in
  ``tests/test_billing_audit_shadow.py``:
  ``TestLookupAttributionAll`` (9), ``TestResolveClaimer`` (8),
  ``TestAttributionHoldSummary`` (4) — plus ``CountersTests`` updated for
  the pre-seeded counter. ``pytest tests/`` → **710 passed / 26 skipped
  / 58 subtests** (was 689 at the Phase 1.1 close; +21 net).
- [2026-05-21 09:21] Subproject B (subcontractor PRIMARY claim
  attribution) shipped — the first consumer of Foundation A's
  ``resolve_claimer`` + HOLD contract ([2026-05-20 13:45]). The
  subcontractor primary variants (``reduced_sub`` / ``aep_billable``)
  are now re-partitioned by the FROZEN primary claimer
  (``primary_foreman`` from ``billing_audit.attribution_snapshot``)
  instead of shipping one bare file per WR. Each file holds only one
  claimer's completed line items and is named
  ``_ReducedSub_User_<name>`` / ``_AEPBillable_User_<name>`` (the
  reserved ``_User_`` token, parser-unambiguous vs ``_Helper_``).
  Spec: ``docs/superpowers/specs/2026-05-20-subproject-b-subcontractor-primary-claim-attribution-design.md``;
  plan: ``docs/superpowers/plans/2026-05-20-subproject-b-subcontractor-primary-claim-attribution.md``.
  **The five operator-approved decisions (the contract):** (1)
  **Partition model = fallback-to-current** — rows with a frozen
  claimer group under that claimer; rows with no frozen claimer yet
  (``no_history``) fall back to the current ``effective_user`` (all
  rows reaching the variant block are ``Units Completed?``-checked).
  (2) **Attribution kill switch = reuse**
  ``SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED`` (default on) —
  its documented scope is broadened to gate primary partitioning too;
  no new attribution flag. (3) **Filename** =
  ``_ReducedSub_User_<name>`` / ``_AEPBillable_User_<name>``. (4)
  **Migration** = explicit forced cleanup of legacy unpartitioned
  attachments + a one-time version-sentinel hash prune, gated by the
  NEW default-on kill switch ``SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED``
  (destructive-cleanup-needs-its-own-switch rule [2026-05-19 22:00]
  #4). (5) **Outage = HOLD** — on ``resolve_claimer`` ``fetch_failure``
  the row is deferred (``record_attribution_hold``), no primary file
  is emitted that run, and ``summarize_attribution_holds()`` fires
  once at end-of-run. **Accepted asymmetry:** the primary path HOLDs
  on a Supabase outage (correctness over availability — a possibly
  mis-attributed billing file is worse than a late one), while the
  unchanged Phase 1.1 helper-shadow path still falls back to the
  current ``Foreman Helping?`` and generates. B is the FIRST HOLD
  consumer; the helper-shadow path predates the HOLD machinery and is
  deliberately left as-is. **Wiring = Approach A (parallel pre-pass).**
  ``group_source_rows`` resolves every completed subcontractor row's
  claimer in a bounded ``ThreadPoolExecutor`` (``min(PARALLEL_WORKERS,
  n)``, single-row groups skip the executor) into a
  ``{__row_id: ResolveOutcome}`` map BEFORE the grouping loop — no
  per-row Supabase round-trip inside the hot loop (the [2026-04-25
  14:00] per-row-latency lesson). A row absent from the map
  (attribution disabled, pre-pass skipped, missing ``__row_id``, or an
  unexpected per-row error) resolves to use-current at emission —
  NEVER HOLD — so a plumbing fault can never silently suppress a
  billing file; only ``resolve_claimer``'s own ``fetch_failure`` HOLDs.
  ``billing_audit/`` was NOT modified (everything B needs shipped in
  Foundation A). **CR-01 three-site lockstep extended:** the new
  variants' identity tuple (``identifier`` = sanitized claimer) is
  built in lockstep at all three main-loop sites — the per-group
  ``identifier`` / ``file_identifier``, the ``valid_wr_weeks`` cleanup
  builder, and the ``current_keys`` hash-prune set — plus the
  ``build_group_identity`` parser, so attachment-identity matching and
  hash-history persistence stay consistent ([2026-05-15] CR-01).
  **New migration plumbing:** ``cleanup_untracked_sheet_attachments``
  gained a ``sub_legacy_primary_variants: set[str] | None`` param + a
  gate that deletes empty-identifier ``_ReducedSub`` / ``_AEPBillable``
  attachments for in-scope sub WRs (TARGET gets
  ``{'reduced_sub','aep_billable'}``, PPP gets ``{'reduced_sub'}`` —
  ``aep_billable`` never routes to PPP) with a ``valid_wr_weeks``
  live-identity exemption so a current per-claimer file is never
  deleted; the ``_sub_scope`` builder is now shared by the SUB-09
  helper cleanup and this primary cleanup (byte-identical TARGET
  behaviour preserved when only ``SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED``
  is on). The new ``_run_subproject_b_hash_prune`` (constant
  ``SUBPROJECT_B_HASH_PRUNE_VERSION = 1``, sentinel
  ``_subproject_b_prune_version`` — DISTINCT from Phase 1.1's
  ``_phase_prune_version``) idempotently drops legacy blank-identifier
  ``reduced_sub`` / ``aep_billable`` hash orphans on first run; the
  prune is benign (a dropped hash costs at most one regeneration, never
  data loss) so it carries no live-identity exemption, and its PII
  marker ``"Subproject B hash-history prune"`` is registered in
  ``_PII_LOG_MARKERS``. ``SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED``
  is workflow-pinned to ``'1'`` in
  ``.github/workflows/weekly-excel-generation.yml`` and documented in
  ``website/docs/reference/environment.md`` (which also broadens the
  attribution-flag scope note). **New rules:** (1) **HOLD is for
  genuine outages only.** A consumer of ``resolve_claimer`` must HOLD
  (defer + ``record_attribution_hold`` + end-of-run
  ``summarize_attribution_holds``) ONLY on ``action == 'hold'``
  (``fetch_failure``); ``no_history`` and ``disabled`` use the current
  foreman and generate normally. A map-miss / plumbing fault must
  resolve to use-current, never HOLD — a HOLD suppresses a billing
  file, so it must require a real Supabase failure, not an internal
  bug. (2) **Per-row attribution I/O goes in a pre-pass, never the hot
  loop.** Any future variant that resolves a per-row claimer (C =
  vac_crew, D = primary-workflow primary) MUST follow Approach A — a
  bounded ``ThreadPoolExecutor`` pre-pass into a ``{__row_id:
  outcome}`` map before ``group_source_rows``' grouping loop, with the
  single-row-skips-executor guard — extending the [2026-04-25 14:00]
  rule from ``freeze_row`` to attribution reads. (3) **A new claimer
  filename token requires the CR-01 four-site update** (parser + three
  identity sites) in the same change; the source-grep guards in
  ``TestSubprojectBProductionInvariants`` are the regression net
  against a silent revert. (4) **Sequencing for the remaining
  sub-projects is unchanged:** C (VAC crew by ``frozen_vac_crew``) →
  D (primary-workflow primary; highest blast radius, last) → E
  (Supabase hash-store migration + filename token stripping). Executed
  via superpowers subagent-driven-development (Tasks 1–11; fresh
  implementer per task + two-stage spec-then-code-quality review for
  complex/destructive tasks, controller verification for
  mechanical/inert ones). Regression tests: new file
  ``tests/test_subcontractor_primary_claim_attribution.py`` —
  ``TestBuildGroupIdentityParsesPrimaryUserToken``,
  ``TestLegacyPrimaryCleanupKillSwitch``,
  ``TestPrimaryVariantSuffixHelper``, ``TestPrePassEmission``,
  ``TestThreeIdentitySitesCarryClaimer``, ``TestHoldSummaryWiredIntoMain``,
  ``TestMigrationCleanup``, ``TestSubprojectBHashPrune``,
  ``TestNonSubVariantsPreserved``, ``TestPrePassConcurrency``,
  ``TestSubprojectBProductionInvariants``. ``pytest tests/`` →
  **751 passed / 26 skipped / 58 subtests** (was 710 at the Foundation
  A close; +41 net). After this branch lands, sub-helper Phase 1.1 +
  Foundation A + Subproject B together cover the subcontractor
  workflow's helper and primary claim attribution; the primary-workflow
  (non-sub) primary partitioning is still Sub-project D, not yet
  shipped.
- [2026-05-21 10:30] Production hotfix (PR #216, merged to master) +
  carried into Subproject B (PR #215): **helper-COMPLETED subcontractor
  rows were being credited to the PRIMARY ``_ReducedSub`` /
  ``_AEPBillable`` files.** When a helper claims a line item they check
  BOTH ``Units Completed?`` AND ``Helping Foreman Completed Unit?`` (with
  ``Foreman Helping?`` set) — on Smartsheet that credits the HELPER, so
  the row must go SOLELY to the helper-shadow files
  (``_ReducedSub_Helper_<helper>`` / ``_AEPBillable_Helper_<helper>``).
  Instead the subcontractor primary emission in ``group_source_rows``
  fired for EVERY accepted subcontractor row, so the helper-completed
  row landed in BOTH the primary and the helper file — double-counted
  and wrongly credited to the primary foreman. **Root cause:** the
  subcontractor primary emission block (``if is_subcontractor_row and
  SUBCONTRACTOR_RATE_VARIANTS_ENABLED:``) never replicated the
  ``valid_helper_row`` exclusion that the legacy main-file
  primary-vs-helper cascade has had all along (the ``elif
  valid_helper_row:`` "EXCLUDING from main Excel" branch). Pre-existing
  since Phase 1 (``SUBCONTRACTOR_RATE_VARIANTS_ENABLED`` is pinned on in
  production); NOT a Subproject B regression — B preserved the behavior
  and only renamed the keys to ``_USER_<claimer>``. **Fix:** compute a
  local ``_sub_is_valid_helper_row`` (mirrors the helper-shadow block's
  recompute — ``not is_vac_crew_row and RES_GROUPING_MODE in
  ('helper','both') and is_helper_row and helper_foreman and
  helper_dept``) and gate the primary emission on it. On master the
  bare ``_REDUCEDSUB``/``_AEPBILLABLE`` emission is wrapped in ``if not
  _sub_is_valid_helper_row:``; in Subproject B ``_b_primary_claimer``
  defaults to ``None`` and is only resolved for non-helper rows, so the
  existing ``if _b_primary_claimer is not None`` gate suppresses the
  ``_USER_`` emission and skips recording a HOLD for helper rows.
  ``_snap_for_cutoff`` is hoisted above the guard because the unchanged
  helper-shadow block depends on it. **New rules:** (1) Any NEW
  subcontractor variant emission path that produces a per-WR PRIMARY
  file (the ``reduced_sub`` / ``aep_billable`` variants today, and any
  future primary-side variant) MUST replicate the ``valid_helper_row``
  exclusion — a helper-completed row belongs solely to the
  helper-shadow files. This is the variant-side analog of the legacy
  main-file exclusion noted in the CLAUDE.md "Helper rows" section.
  (2) The coverage gap that let this ship for ~two phases: the existing
  helper-row tests asserted the shadow keys were PRESENT and the legacy
  ``_HELPER_`` key was ABSENT, but NEVER asserted the bare primary
  key's ABSENCE. Any test for an emission path that EXCLUDES a row
  class MUST assert the excluded key is absent, not merely that the
  expected keys are present — "present" assertions alone are blind to
  over-emission. Regression tests:
  ``tests/test_subcontractor_helper_shadow_rescue.py::TestEndToEndPipeline::test_subcontractor_helper_row_excluded_from_primary_variant_files``
  (master, merged into B) and
  ``tests/test_subcontractor_primary_claim_attribution.py::TestPrePassEmission::test_helper_completed_row_excluded_from_primary_user_variants``
  (B's ``_USER_`` variant — asserts no primary key even when the
  parallel pre-pass resolves a claimer for the helper row). Verified
  TDD red→green; ``pytest tests/`` → 712 on master, 753 on the merged
  Subproject B branch.
- [2026-05-21 12:35] Operator-reported defect (subcontractor helper
  Excel files): **subcontractor helper-shadow files showed the PRIMARY
  ``Dept #`` and ``Job #`` instead of the helper's.** Requirement: in
  subcontractor Excel files HELPER files must show **Helper Dept #** and
  PRIMARY files must show **Dept #**, on BOTH reduced-sub and
  aep-billable. **Root cause:** ``generate_excel``'s REPORT DETAILS
  display-value selector gated the helper display on the BARE variant
  via ``if variant == 'helper':`` (exact match), then ``elif variant ==
  'vac_crew':``, then an ``else`` primary branch. The two subcontractor
  helper-shadow variants ``reduced_sub_helper`` / ``aep_billable_helper``
  (assigned to ``__variant`` at the ``keys_to_add`` site, no
  normalization) matched NONE of the gates and fell through to the
  ``else`` (primary) branch, which set ``display_dept =
  first_row.get('Dept #', '')`` and ``display_job = job_number`` (the
  primary ``Job #`` column variants). Every OTHER site in the file that
  distinguishes helper from primary already uses the grouped form
  ``variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper')``
  (the hash-meta block, and the two CR-01 identity sites at the
  ``identifier`` / ``valid_wr_weeks`` / ``current_keys`` construction) —
  ``generate_excel``'s display selector was the lone exact-match
  outlier. The displayed **Foreman was already CORRECT** even via the
  ``else`` branch, because for sub-helper rows ``__current_foreman`` is
  set to the ATTRIBUTED helper (``_attributed_helper``, the file's
  partition key) at the ``keys_to_add`` tuple — so ``display_foreman =
  current_foreman`` already resolved to the right name. That is exactly
  why the naive "just add the two variants to the ``if variant ==
  'helper'`` branch" fix is WRONG: that branch sources foreman from
  ``__helper_foreman`` (the current ``Foreman Helping?`` value), which
  can diverge from the frozen attribution under Phase 1.1 claim
  attribution and would have REGRESSED the displayed foreman. **Fix
  (additive, surgical):** added a dedicated ``elif variant in
  ('reduced_sub_helper', 'aep_billable_helper'):`` branch BETWEEN the
  ``helper`` and ``vac_crew`` branches that sources ``display_dept`` /
  ``display_job`` from ``__helper_dept`` / ``__helper_job`` while keeping
  ``display_foreman = current_foreman`` (the attributed helper). Sub
  PRIMARY variants (``reduced_sub`` / ``aep_billable`` / the Subproject
  B ``_User_`` partitions) correctly remain in the ``else`` branch
  (primary ``Dept #``, claimer foreman) — matching the requirement that
  primary files show ``Dept #``; no change to them, to legacy
  ``primary`` / ``helper`` / ``vac_crew``, or to filenames / grouping /
  hashing / upload. **Coverage gap that let this ship through Phase 1 +
  1.1:** the only generate_excel tests for the new variants
  (``TestSubcontractorVariantFilenameSuffixes``,
  ``TestSubcontractorVariantPriceSubstitution``) asserted FILENAME
  suffixes and PRICE values — never the REPORT DETAILS cell CONTENT
  (Dept # / Job # / Foreman). The display-value branch was untested for
  content. **New rules:** (1) **Variant-display-site lockstep — a
  FOURTH site.** ``generate_excel``'s REPORT DETAILS display-value
  selector is a fourth variant-aware site that MUST stay in lockstep
  with the three CR-01 identity sites ([2026-05-15] / [2026-05-21
  09:21] rules): the per-group ``identifier`` / ``file_identifier``
  construction, the ``valid_wr_weeks`` cleanup builder, and the
  ``current_keys`` hash-prune set. Any NEW helper-class variant added in
  the future MUST be added to the display selector's helper branch (or a
  sibling branch) in the SAME change, and the selector MUST use the
  membership form ``variant in (...)`` — never a bare ``== 'helper'``
  exact match that silently drops sibling variants into the primary
  ``else`` branch. (2) **Display source ≠ identity source for
  attributed helpers.** When a variant's file is partitioned by an
  ATTRIBUTED identity (frozen claimer / frozen helper via Foundation A),
  the REPORT DETAILS foreman MUST come from ``current_foreman``
  (== the partition key) — NOT from the current Smartsheet ``Foreman
  Helping?`` / ``__helper_foreman`` field, which can diverge from the
  frozen attribution. Do NOT fold an attributed-helper variant into the
  legacy ``helper`` branch (which sources ``__helper_foreman``); give it
  its own branch that pairs helper dept/job with ``current_foreman``.
  (3) **Test the rendered cell, not just the filename.** Any test for a
  ``generate_excel`` variant behaviour that affects RENDERED content
  (Dept #, Job #, Foreman, totals) MUST open the produced workbook and
  assert on the cell value, not merely the filename suffix or the price
  helper in isolation. Filename-only assertions are blind to
  display-branch routing bugs — exactly the gap that hid this defect for
  two phases. Regression tests:
  ``tests/test_subcontractor_pricing.py::TestSubcontractorHelperVariantDeptJobDisplay``
  (4 methods + a 2-variant subTest) drives the real ``generate_excel``,
  reopens the workbook, and asserts the REPORT DETAILS ``Dept #:`` /
  ``Job #:`` / ``Foreman:`` cells for both sub-helper variants
  (helper dept ``123`` / helper job ``J-2`` shown, not primary
  ``500`` / ``J-1``), the foreman-stays-attributed-helper regression
  guard, and the sub-primary-keeps-primary-dept/job guard. Verified TDD
  red→green (RED: ``'500' != '123'``); ``pytest tests/`` → **757 passed
  / 26 skipped / 60 subtests** (was 753 / 26 / 58 at the Subproject B
  close; +4 methods, +2 subtests, zero regressions).
- [2026-05-21 13:20] PR #215 pre-merge AI code-review pass (Copilot +
  Codex) on Subproject B surfaced 4 real bugs + 1 hardening item; all
  verified against the code and fixed TDD red→green before merge.
  **(#4, Codex P1 — High) Empty claimer crashed primary file
  generation.** ``_subcontractor_primary_variant_suffix`` raises
  ``ValueError`` on an empty claimer (a deliberate data-drift backstop),
  but the emission gate at ``group_source_rows`` was ``if
  _b_primary_claimer is not None`` — and the claimer could be ``''``: a
  whitespace-only ``Foreman Assigned?`` makes ``str(foreman_assigned).
  strip()`` (the ``if foreman_assigned:`` branch is truthy for
  whitespace) yield ``__effective_user = ''``, which flows through
  ``resolve_claimer``'s use/no_history (returns the empty current value)
  to ``_b_primary_claimer = ''``. That passed ``is not None``, created a
  ``_REDUCEDSUB_USER_`` key with an empty identifier, then crashed
  ``generate_excel`` at the suffix raise → the WR's subcontractor primary
  file silently failed to generate. Fix: fall back to ``'Unknown
  Foreman'`` (``_b_outcome.name or effective_user or 'Unknown Foreman'``
  on the use branch; ``effective_user or 'Unknown Foreman'`` on the
  else branch), so the row's billing still ships in a clearly-flagged
  file and the suffix raise stays a true backstop. **(#3, Codex P2 —
  Med) ``build_group_identity`` scanned ``Helper`` before ``User``.** In
  the ``AEPBillable`` / ``ReducedSub`` branches the ``if 'Helper' in
  post_*`` check ran before the ``post_*[0] == 'User'`` check, so a
  primary-claimer filename whose CLAIMER NAME contains the ``Helper``
  token (e.g. a foreman named ``Pat Helper`` → ``_…_User_Pat_Helper_
  <hash>``) misparsed as ``…_helper`` with an empty identifier — breaking
  the identity round-trip and causing attachment-cleanup / hash-skip
  churn for those claimers. Fix: check the reserved ``User`` token FIRST
  in both branches; helper-shadow files (``post_*[0] == 'Helper'``) and
  legacy unpartitioned files are unaffected. **(#5, Codex P2 — Low)
  One-time hash-prune sentinel lost on no-update runs.** Both
  ``_run_phase_1_1_hash_prune`` and ``_run_subproject_b_hash_prune``
  mutate ``hash_history`` (drop orphans + advance the version sentinel),
  but ``save_hash_history`` was gated solely by ``if history_updates:``.
  On a run where every group is skipped (``history_updates == 0``) the
  save never fired, so the prune re-ran every such execution
  (idempotent + self-healing, hence Low — but non-deterministic). Fix:
  both prunes now return a ``bool`` (``True`` when the body path ran /
  sentinel advanced, ``False`` on the no-op idempotent early-return); the
  call sites OR the results into ``_hash_history_migration_dirty``; and a
  new ``elif _hash_history_migration_dirty: save_hash_history(...)`` branch
  persists the migration on a no-update run WITHOUT running the stale-key
  prune (groups weren't fully processed, so ``current_keys`` would be
  incomplete and could delete freshly-skipped live entries). **(#1,
  Copilot — Low) ``record_attribution_hold`` typed ``date`` got a
  ``datetime``.** The HOLD call passed the ``datetime`` ``week_ending_date``,
  so the hold-bucket key embedded ``…T00:00:00`` (and would split buckets
  if any caller passed a pure ``date``). Fix: normalize to
  ``week_ending_date.date()`` at the call site (matching the pre-pass's
  normalization for ``resolve_claimer``). **(#2, Copilot — hardening, not
  a live bug) Suffix helper accepted unknown variants.**
  ``_subcontractor_primary_variant_suffix`` mapped any non-``aep_billable``
  variant to ``_ReducedSub``; call sites only pass the two valid variants,
  but per the [2026-05-15 12:00] rule-4 defensive-raise convention for new
  variant-identity helpers it now raises ``ValueError`` on an unexpected
  variant. **New rules:** (1) **Reserved-token parse order.** When a
  filename grammar has a reserved disambiguating token (``User`` for
  primary claimers) AND a free-text identifier that can itself contain
  another grammar token (``Helper`` inside a foreman name), the reserved
  token MUST be matched BEFORE any substring/membership scan for the
  other token. Membership checks (``'Helper' in parts``) are positional-
  agnostic and will false-positive on identifier content; the reserved
  token is positional (``parts[0]``) and unambiguous. (2) **Non-empty
  claimer invariant for ``_USER_`` emission.** Any emission gate that
  feeds a value into a filename-identity helper which raises on empty
  MUST guarantee the value is non-empty BEFORE the gate — gate on
  truthiness or coerce to a sentinel (``'Unknown Foreman'``), never gate
  on ``is not None`` while the producer can yield ``''``.
  ``__effective_user`` specifically can be ``''`` (whitespace ``Foreman
  Assigned?``); treat it as possibly-empty everywhere it seeds an
  identifier. (3) **One-time migrations must persist independently of
  ``history_updates``.** A version-sentinel migration that mutates
  ``hash_history`` must report whether it mutated, and the save path must
  honor that signal even when no groups changed — otherwise the sentinel
  never persists on a quiet run and the migration is non-deterministic.
  The migration-save path must NOT trigger the stale-key prune (that
  prune requires fully-processed ``current_keys``). Regression tests
  (all TDD red→green): ``tests/test_subcontractor_primary_claim_attribution.py``
  gains ``TestBuildGroupIdentityParsesPrimaryUserToken`` +2 (claimer
  named ``…_Helper`` parses as primary for both variants),
  ``TestPrimaryVariantSuffixHelper::test_unknown_variant_raises``,
  ``TestPrePassEmission::test_empty_claimer_falls_back_to_unknown_foreman``
  + ``test_hold_records_date_only_week_key``, and
  ``TestSubprojectBHashPrune`` +4 (prune return-value contract +
  migration-dirty save-gate source guard). ``pytest tests/`` → **766
  passed / 26 skipped / 60 subtests** (was 757; +9, zero regressions).
- [2026-05-21 14:15] **Sub-project C (VAC crew claim attribution)
  shipped** — third consumer of Foundation A's ``resolve_claimer`` +
  HOLD contract ([2026-05-20 13:45]), mirroring Subproject B
  ([2026-05-21 09:21]). VAC crew Excel files are now re-partitioned
  by the FROZEN vac-crew claimer (``frozen_vac_crew`` from
  ``billing_audit.attribution_snapshot``) rather than shipping one
  bare ``_VacCrew`` file per WR+week. Each file holds only one
  claimer's completed line items and is named ``_VacCrew_<name>``
  (e.g. ``WR_90773033_WeekEnding_051226_VacCrew_Jane_Smith_<hash>.xlsx``).
  Hash-in-filename retained (E does the strip). ``billing_audit/``
  NOT modified — everything C needs shipped in Foundation A.
  Spec: ``docs/superpowers/specs/2026-05-21-subproject-c-vac-crew-
  claim-attribution-design.md``; plan: ``docs/superpowers/plans/
  2026-05-21-subproject-c-vac-crew-claim-attribution.md``.
  **Operator-approved decisions:** (1) **ALL-sheets scope** — vac_crew
  rows span both subcontractor-folder sheets AND original-contract-
  folder sheets; C uses its own dedicated kill switches
  (``VAC_CREW_CLAIM_ATTRIBUTION_ENABLED`` + ``VAC_CREW_LEGACY_CLEANUP_ENABLED``)
  rather than reusing ``SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED``,
  enabling independent rollback. (2) **Filename** ``_VacCrew_<name>``
  (the reserved ``_VacCrew_`` prefix is parser-unambiguous vs.
  ``_Helper_`` and ``_User_``). (3) **Fallback-to-current on
  ``no_history``** — rows with no frozen claimer yet fall back to the
  current Smartsheet vac-crew name; this run's ``freeze_row`` call is
  what writes the first freeze. (4) **Two new default-on
  workflow-pinned kill switches** (``VAC_CREW_CLAIM_ATTRIBUTION_ENABLED``
  + ``VAC_CREW_LEGACY_CLEANUP_ENABLED``) following the
  [2026-05-19 22:00] destructive-cleanup-needs-its-own-switch rule.
  (5) **HOLD on ``resolve_claimer`` ``fetch_failure``** (correctness
  over availability) — ``record_attribution_hold('vac_crew')`` per
  row, end-of-run ``summarize_attribution_holds()`` WARNING reports
  the count.
  **Wiring — Approach A parallel pre-pass.** ``group_source_rows``
  resolves every completed vac-crew row's claimer into a
  ``_vac_crew_claimer_map`` via a bounded
  ``ThreadPoolExecutor(max_workers=min(PARALLEL_WORKERS, n))`` BEFORE
  the grouping loop — no per-row Supabase I/O in the hot loop (per
  the [2026-04-25 14:00] per-row-latency rule). Single-row groups
  skip the executor to avoid setup overhead. The emission partitions
  the legacy flat key ``{week}_{wr}_VACCREW`` into per-claimer keys
  ``{week}_{wr}_VACCREW_{sanitized_claimer}``. A row absent from the
  map (attribution disabled, pre-pass skipped, missing
  ``__row_id``, unexpected per-row error) resolves to use-current —
  NEVER HOLD — so a plumbing fault cannot silently suppress a billing
  file.
  **CR-01 lockstep — the key lesson from this sub-project.** The vac
  claimer identifier must be carried IDENTICALLY at FOUR sites that
  must agree byte-for-byte or attachments churn / hash-skip breaks:
  (1) the main-loop ``identifier`` / ``file_identifier`` /
  ``history_key`` construction immediately before the group-emit
  block, (2) the ``valid_wr_weeks.add(...)`` cleanup-tuple builder,
  (3) the ``current_keys`` set construction inside the
  hash-history-prune block, AND (4) the ``build_group_identity``
  parser — which was reordered so ``VacCrew`` is checked BEFORE
  ``Helper`` in the token scan, preventing a vac-crew claimer whose
  name contains the string ``Helper`` from being misparsed as a
  helper-shadow variant (the [2026-05-21 09:21] reserved-token
  parse-order rule). All four are gated on
  ``VAC_CREW_CLAIM_ATTRIBUTION_ENABLED`` so the kill-switch-OFF path
  reproduces the EXACT legacy ``''``-identifier / bare ``_VacCrew``
  shape — otherwise disabling the flag would itself cause attachment
  churn.
  **Two bugs the two-stage code review caught.** (a) The plan
  initially missed the main-loop Site 1 ``identifier`` /
  ``history_key`` construction (distinct from the
  ``group_source_rows`` emission group-key). Had this shipped, the
  main loop would write ``...|vac_crew|`` (blank identifier) to
  ``hash_history`` while ``current_keys`` held the claimer name →
  the hash-history pruner would have marked every vac-crew entry
  stale on each run → permanent regeneration churn with no operator-
  visible signal. (b) The disabled-mode (kill-switch OFF) path
  initially still resolved the claimer and produced
  ``_VacCrew_<name>`` filenames + non-empty identifiers in
  ``valid_wr_weeks`` / ``current_keys``, violating the "exact legacy
  behavior" contract — the OFF path would have generated files the
  old cleanup code couldn't match and itself caused churn. Fixed by
  gating all four identity surfaces on the flag so OFF literally
  reproduces the pre-C state.
  **Migration plumbing.** TARGET-only legacy ``_VacCrew``
  (empty-identifier) cleanup via a new
  ``_build_vac_crew_wr_scope(groups)`` shared helper (referenced by
  both ``cleanup_untracked_sheet_attachments`` and
  ``_run_vac_crew_hash_prune`` — the [2026-05-19 22:00] shared-scope-
  builder rule). The deletion gate carries the ``valid_wr_weeks``
  live-identity exemption per [2026-05-19 23:45] (scope-set
  granularity must match the routing key). A one-time idempotent
  hash prune ``_run_vac_crew_hash_prune`` with a DISTINCT
  ``VAC_CREW_HASH_PRUNE_VERSION`` / ``_vac_crew_prune_version``
  sentinel (separate from ``_phase_prune_version`` and
  ``_subproject_b_prune_version``) drops blank-identifier
  ``vac_crew`` hash orphans; returns a ``bool`` ORed into
  ``_hash_history_migration_dirty`` so the prune persists even on a
  no-update run (per the [2026-05-21 10:30] one-time-migration rule).
  PII marker ``"Vac crew hash-history prune"`` registered in
  ``_PII_LOG_MARKERS``.
  **New rule:** Any new variant whose group key embeds a claimer
  identifier MUST carry that identifier identically at all four CR-01
  sites AND gate every one of them on the variant's kill switch so
  the OFF path reproduces exact legacy behavior. The main-loop
  ``identifier`` / ``history_key`` site (Site 1) is EASY TO MISS
  because it is distinct from the ``group_source_rows`` emission
  group-key — the two live in different scopes and both construct the
  identity tuple from the same logical fields. Sub-project C's
  two-stage code review caught exactly this omission; future
  sub-project implementers MUST explicitly cross-reference all four
  sites before marking a task complete. Additionally, when adding a
  new reserved filename token to the ``build_group_identity`` parser,
  the new token MUST be checked BEFORE any free-text substring scan
  for other tokens — free-text identifier content can contain any
  token string and will false-positive the scan (e.g. a vac-crew
  member named ``Pat Helper`` contains the ``Helper`` substring).
  Regression tests: new file
  ``tests/test_vac_crew_claim_attribution.py`` —
  ``TestVacCrewConfigFlags`` (env-var wiring + default values),
  ``TestVacCrewSuffixAndParser`` (filename suffix helper + 4-site
  identity round-trip including ``_VacCrew_<name>`` parse-before-
  helper ordering), ``TestVacCrewPrePassConcurrency`` (50 concurrent
  pre-pass calls preserve counter accuracy, no silent drops),
  ``TestVacCrewEmission`` (group-key emission with attribution on/off
  + HOLD propagation), ``TestVacCrewIdentitySitesAndDisplay``
  (all four CR-01 sites carry the claimer; OFF path produces legacy
  empty-identifier shape at all four sites),
  ``TestVacCrewLegacyCleanup`` (empty-identifier files deleted;
  live per-claimer files exempted via ``valid_wr_weeks``; non-vac WRs
  untouched), ``TestVacCrewHashPrune`` (idempotency, version-sentinel
  persistence, returns-bool contract wired into migration-dirty path),
  ``TestVacCrewEndToEnd`` (full ``group_source_rows`` → grouping →
  key-shape assertion with mocked pre-pass),
  ``TestVacCrewProductionInvariants`` (source-grep guards for all
  four CR-01 sites, kill-switch pins, PII marker, parser token
  order). Two legacy contract-override rewrites in existing files:
  ``tests/test_vac_crew.py::test_vac_crew_key_format`` + sibling
  (rewritten in-place per [2026-05-20 00:26] rule 2 citing this
  entry), ``tests/test_subcontractor_primary_claim_attribution.py::
  test_vac_crew_row_unaffected`` (updated to reflect partitioned
  emission keys). ``pytest tests/`` → **807 passed / 26 skipped /
  60 subtests** (was 766 at Subproject B review-fixes close; +41
  net). After this branch lands, Foundation A + Subproject B +
  Sub-project C together cover subcontractor-primary, sub-helper,
  and vac-crew claim attribution; the primary-workflow primary
  foreman partitioning remains Sub-project D (highest blast radius —
  changes core primary grouping across all sheets, deliberately last
  before E).
- [2026-05-25 12:40] PR #219 (Sub-project C) pre-merge AI code-review
  pass (Copilot + Codex) surfaced 3 real bugs + 3 doc nits; all fixed
  TDD red→green before merge. **(Codex P1 — WR matchers blind to the
  per-claimer key.)** ``_key_matches_wr`` (WR_FILTER) and
  ``_key_matches_excluded_wr`` (EXCLUDE_WRS) matched vac_crew via
  ``suffix == f"{wr}_VACCREW"`` (exact), so C's new
  ``{wr}_VACCREW_<claimer>`` keys (attribution on, the default) slipped
  past both — an EXCLUDE_WRS'd WR would still produce/upload vac files
  and a WR_FILTER run would drop them. This is the exact CR-02/CR-03
  mirror-matcher rule the matcher comments themselves cite: a new
  variant key shape MUST extend BOTH matchers. Fix: added
  ``or suffix.startswith(f"{wr}_VACCREW_")`` to both (legacy bare +
  per-claimer both covered). **(Codex P2 — prune deletes valid history
  when the kill switch is off.)** ``_run_vac_crew_hash_prune`` drops
  blank-identifier ``wr|week|vac_crew|`` keys, but blank-identifier is
  the ACTIVE legacy format when ``VAC_CREW_CLAIM_ATTRIBUTION_ENABLED=0``
  — so the first disabled-mode run would delete valid current history
  and force regeneration churn, breaking the exact-legacy contract. Fix:
  early-return ``False`` from the prune when the flag is off, WITHOUT
  advancing the sentinel (so the one-time migration still runs if
  attribution is later enabled). **(Copilot — vac_crew row double-emits
  on subcontractor sheets.)** ``__is_vac_crew`` is set by column
  presence, not sheet membership, so a vac_crew row can come from a
  subcontractor-folder sheet; the subcontractor variant block was gated
  only on ``is_subcontractor_row and SUBCONTRACTOR_RATE_VARIANTS_ENABLED``
  (not ``not is_vac_crew_row``) and the vac block doesn't ``continue``,
  so such a row emitted VACCREW **and** REDUCEDSUB/AEPBILLABLE and a vac
  ``hold`` was bypassed. Pre-existing since Phase 1; fixed by adding
  ``not is_vac_crew_row`` to the subcontractor block gate (a ``continue``
  would skip the ``keys_to_add`` processing that actually creates the
  vac group, so the gate — not a short-circuit — is the correct fix).
  Doc nits: env.md filename example now includes the ``<timestamp>``
  token; the "exact legacy" note clarifies the PARSER is read-only /
  not flag-gated (only the three identity-CONSTRUCTION sites revert);
  the ``group_source_rows`` docstring now documents both vac key shapes.
  **New rule:** the [2026-05-15] mirror-matcher rule (EXCLUDE_WRS /
  WR_FILTER) and the variant-vs-vac double-emit guard both extend to
  EVERY new variant key shape — when a sub-project adds a
  ``{wr}_<VARIANT>[_<id>]`` group key, it MUST (a) extend BOTH WR
  matchers (prefix-match the id form), (b) ensure the row's other
  applicable emission blocks are mutually exclusive with the new variant
  (gate on ``not is_<other>_row``), and (c) gate any one-time hash-prune
  on the variant's kill switch so the OFF path doesn't delete the
  now-active legacy keys. Regression tests:
  ``tests/test_vac_crew_claim_attribution.py::TestVacCrewReviewFixes``
  (EXCLUDE_WRS drops the per-claimer key, WR_FILTER retains it, prune
  skipped when disabled / runs when enabled, vac-on-sub row emits only
  VACCREW). ``pytest tests/`` → **814 passed / 26 skipped / 60
  subtests** (was 809; +5).
- [2026-05-25 16:30] Sub-project D (primary-workflow primary claim
  attribution) shipped — the fourth and final consumer of Foundation
  A's ``resolve_claimer`` + HOLD contract ([2026-05-20 13:45]).
  Production (non-subcontractor) primary Excel files are now
  partitioned by the FROZEN primary claimer (``primary_foreman`` from
  ``billing_audit.attribution_snapshot``, surfaced via Foundation A's
  ``ROLE_BY_VARIANT['primary'] = 'primary_foreman'`` mapping) instead
  of one bare file per WR+week. Each file is named
  ``_User_<claimer>`` (the same reserved ``_User_`` token as
  Subproject B's per-claimer primary files, parser-unambiguous vs
  ``_Helper_``). A WR+week claimed by two foremen yields two
  coexistent files (distinct identity tuples — ``(wr, week,
  'primary', claimer_a)`` vs ``(wr, week, 'primary', claimer_b)``)
  that never cross-delete: the attachment-cleanup path only prunes
  older copies WITHIN the same identity, so a foreman switch within
  the same week produces a second file rather than destroying the
  first. Only Sub-project E (Supabase hash-store migration + filename
  ``_<hash>``/``_<timestamp>`` token stripping) remains in the
  universal-claim-attribution sequence (A → Phase 1.1 → B → C → D
  → E).
  **No-HOLD operator decision (the key D-vs-B distinction).** Unlike
  Subproject B (which HOLDs subcontractor primary on a Supabase
  outage), D's core primary path NEVER holds. On ``resolve_claimer``
  returning ``fetch_failure`` (outage, run-global kill, retries
  exhausted), ``no_history``, ``disabled``, or a ``_primary_claimer_map``
  miss, D falls back to the CURRENT ``effective_user`` and still
  generates the primary file. Rationale: D covers EVERY
  non-subcontractor WR in every run; HOLDing on a Supabase outage
  would suppress ALL primary billing output for that session — a
  data-absent outcome strictly worse than a possibly-late
  attribution. ``record_attribution_hold`` is never called for the
  primary path; the HOLD machinery from Foundation A is reserved for
  Subproject B's subcontractor-primary flow. A ``no_history`` row is
  the common new-claim case: the current ``effective_user`` is the
  correct partition key (this run IS what freezes the claim via
  ``freeze_row``).
  **Approach A (parallel pre-pass).** ``_primary_claimer_map`` is
  resolved in a bounded ``ThreadPoolExecutor(min(PARALLEL_WORKERS,
  n))`` BEFORE the ``group_source_rows`` grouping loop, scoped to
  completed (``Units Completed?`` checked) non-vac-crew
  non-subcontractor rows (per-row ``is_vac_crew_row`` /
  ``is_subcontractor_row`` checks). Single-row groups skip the
  executor to avoid setup overhead. This follows the
  [2026-04-25 14:00] rule (per-row attribution I/O must live in a
  pre-pass, never the hot loop) and the [2026-05-21 09:21] Subproject
  B wiring pattern. Zero changes to ``billing_audit/`` — Foundation A
  already exposes ``_lookup_attribution_all`` + ``resolve_claimer``
  for the ``'primary'`` role.
  **CR-01 four-site lockstep (extended to a fifth-and-sixth site).**
  The claimer identifier is byte-identical at: (1) the per-group
  main-loop ``identifier`` / ``file_identifier`` construction that
  feeds ``history_key = f"{wr_num}|{week_raw}|{variant}|{identifier}"``;
  (2) the ``valid_wr_weeks.add(...)`` cleanup-tuple builder; (3) the
  ``current_keys`` hash-prune set construction; (4) the
  ``build_group_identity`` parser (already supported ``_User_<name>``
  from Subproject B — zero parser change required); (5) the
  ``generate_excel`` filename-suffix branch; and (6) the
  ``_key_matches_wr`` (WR_FILTER) mirror-matcher. ALL construction
  sites are gated on ``PRIMARY_CLAIM_ATTRIBUTION_ENABLED``; when OFF,
  the identifier is ``''`` and the history key is the legacy bare
  ``{wr}|{week}|primary|`` form, reproducing exact pre-D behavior
  byte-for-byte.
  **Corrected design finding (generate_excel filename surface).**
  The original D spec assumed ``generate_excel`` needed no change
  because the primary variant's filename branch was "bare." In
  practice that branch set ``variant_suffix = ''`` UNCONDITIONALLY —
  without a gated fix, every per-claimer primary group would produce
  the same bare filename (``WR_{wr}_WeekEnding_{mmddyy}_{ts}_{hash}.xlsx``),
  causing every group after the first to clobber the prior file on
  disk and producing a single-file output regardless of claimer count.
  D added a gated branch in the ``elif variant == 'primary':`` arm:
  ``_pf = first_row.get('__current_foreman', '')`` then
  ``if PRIMARY_CLAIM_ATTRIBUTION_ENABLED and _pf: variant_suffix =
  f"_User_{_RE_SANITIZE_IDENTIFIER.sub('_', _pf)[:50]}"`` (else bare
  ``''``) — mirroring the vac_crew ``_User_`` branch added by Subproject
  C. The suffix derives from the attributed claimer (``__current_foreman``,
  the partition key), sanitized via ``_RE_SANITIZE_IDENTIFIER`` exactly as
  the four identity sites do, so each claimer's file has a distinct on-disk
  name and round-trips through ``build_group_identity``.
  **Mirror-matcher rule applied.** ``_key_matches_wr`` (the WR_FILTER
  matcher, used in TEST_MODE diagnostic runs) gained the
  ``or suffix.startswith(f"{wr}_USER_")`` clause for D's per-claimer
  primary keys; ``_key_matches_excluded_wr`` (EXCLUDE_WRS) already
  carried the ``_USER_`` clause from Subproject B — zero change
  needed there. Both matchers revert to the bare ``suffix == wr``
  exact-match when ``PRIMARY_CLAIM_ATTRIBUTION_ENABLED`` is off, so
  the filter semantics are identical to the pre-D legacy contract.
  **Migration (gated on default-on ``LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED``).** Two
  components: (a) forced bare-primary attachment cleanup on
  TARGET_SHEET_ID for in-scope WRs via a new ``primary_wr_scope``
  parameter to ``cleanup_untracked_sheet_attachments``. The scope is
  built by a shared ``_build_primary_wr_scope(groups)`` helper (union
  of WR numbers from all non-sub non-vac primary groups — deliberately
  excludes Subproject B's ``_REDUCEDSUB`` / ``_AEPBILLABLE`` ``_USER_``
  keys to prevent scope overlap). The safety-critical
  ``ident not in valid_wr_weeks`` live-identity exemption
  ([2026-05-19 23:45] rule 1) is applied so a current per-claimer
  attachment is never deleted as collateral cleanup. TARGET-only: PPP
  is never touched by D (primary variants never route to PPP).
  (b) One-time ``_run_subproject_d_hash_prune`` drops legacy
  blank-identifier ``{wr}|{week}|primary|`` orphans from
  ``hash_history.json``. Uses a DISTINCT ``_subproject_d_prune_version``
  sentinel and ``SUBPROJECT_D_HASH_PRUNE_VERSION = 1`` constant
  (separate from Phase 1.1's ``_phase_prune_version`` and Subproject
  B's ``_subproject_b_prune_version`` sentinels). The prune is gated
  on ``PRIMARY_CLAIM_ATTRIBUTION_ENABLED`` — when OFF the bare key IS
  the active legacy key; pruning it would force unnecessary
  regeneration churn on every quiet run. The prune returns a ``bool``
  (``True`` when the sentinel was advanced) wired into
  ``_hash_history_migration_dirty`` per the [2026-05-21 13:20] rule 3
  (one-time migrations must persist independently of
  ``history_updates``). The ``_build_primary_wr_scope`` helper is
  shared by both the cleanup call site and the prune (prevents scope
  drift — the [2026-05-19 22:00] rule 3).
  **Test-contract reconciliation (new rule).** D's change to the
  non-subcontractor primary emission contract inverted the assertions
  in three prior B/B1-era isolation tests (which asserted a
  non-subcontractor non-helper row emits the BARE primary key
  ``{wr}_{week}`` with no claimer suffix) and one stale WR-filter
  mirror test (``test_user_variant_intentionally_not_matched``, which
  asserted WR_FILTER did NOT match the ``_USER_`` clause for
  non-subcontractor rows). Per the [2026-05-20 00:26] rule 2
  (test-contract override), the three isolation tests were pinned to
  ``PRIMARY_CLAIM_ATTRIBUTION_ENABLED=False`` in their
  ``setUp``/``tearDown`` (preserving their B/B1-isolation purpose
  exactly — they test B's subcontractor rows under the D-off
  contract); D's new partitioning behavior is covered end-to-end by
  the D suite. The stale mirror test's obsolete assertion was inverted
  to match the post-D reality (WR_FILTER now DOES match per-claimer
  primary keys) and its docstring updated to cite this ledger entry.
  **New rule — test-contract reconciliation discipline.** When a new
  universal-attribution sub-project changes a shared emission contract
  (here: D changes the non-sub primary key shape from bare to
  ``_User_<claimer>``), the implementer MUST audit prior sub-projects'
  isolation tests and mirror tests for the inverted assumption before
  the branch is pushed. Reconcile in the same branch by: (a) pinning
  now-orthogonal feature flags to ``False`` in the prior tests'
  setUp/tearDown (preserves their isolation purpose), or (b) inverting
  + citing the ledger entry when the prior assertion was testing the
  exact behavior D is changing. Do not let the full-suite gate be the
  first discovery of the conflict — that requires a red-to-green
  repair cycle on a branch that should have been green from the start.
  **Two new default-on kill switches** — ``PRIMARY_CLAIM_ATTRIBUTION_ENABLED``
  and ``LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED`` — are workflow-pinned
  to ``'1'`` in ``.github/workflows/weekly-excel-generation.yml``
  with prominent LEGACY-style comments explaining their revert paths,
  surfaced in the startup banner alongside all prior sub-project flags,
  and documented in ``website/docs/reference/environment.md`` (the
  "Primary foreman claim attribution" section). Regression tests: new
  file ``tests/test_primary_claim_attribution.py`` covering
  ``TestBuildGroupIdentityParsesUserToken`` (primary ``_User_``
  round-trip), ``TestPrimaryClaimAttributionKillSwitch`` (OFF reverts
  to bare key, ON emits ``_User_<claimer>``),
  ``TestPrimaryClaimerPrePassEmission`` (pre-pass resolves claimer,
  no-history falls back to current user, outage falls back not HOLDs),
  ``TestThreeIdentitySitesCarryPrimaryClaimer`` (history_key /
  valid_wr_weeks / current_keys lockstep), ``TestFilenameVariantSuffix``
  (gated ``_User_`` suffix in generate_excel),
  ``TestMirrorMatcherPrimaryUser`` (WR_FILTER matches per-claimer key
  on, OFF reverts), ``TestMigrationCleanupPrimary`` (scope excludes
  sub WRs, live-identity exemption preserved),
  ``TestSubprojectDHashPrune`` (prune gate on flag, sentinel distinct,
  return-bool wired to dirty-flag, idempotent), and
  ``TestNonSubNonVacPrimaryPreserved`` (vac and sub rows unaffected).
  Plus reconciled prior tests: B/B1 isolation tests pinned to
  ``PRIMARY_CLAIM_ATTRIBUTION_ENABLED=False``; stale WR-filter mirror
  assertion inverted. ``pytest tests/`` → **854 passed / 26 skipped /
  61 subtests** (was 814 / 26 / 60 at Sub-project C close; +40 net
  passing, +1 subtest).
- [2026-05-25 17:50] Sub-project D PR #223 pre-merge review hardening
  (Opus final whole-implementation review + Codex/Copilot bot pass on the
  PR). Two code fixes + doc reconciliation; all on the
  ``feat/subproject-d-primary-claim-attribution`` branch BEFORE merge.
  **(1) Parser earliest-reserved-token dispatch (final-review Issue #1,
  commit 9489310).** ``build_group_identity`` dispatched variants by a
  FIXED order (``if 'AEPBillable' in tail: elif 'ReducedSub' ... elif
  'VacCrew' ... elif 'Helper' ... elif 'User'``), so a bare
  ``_User_<claimer>`` primary file whose CLAIMER NAME contains a reserved
  token (e.g. a foreman literally named "Pat Helper" →
  ``_User_Pat_Helper_<hash>``) misparsed as ``helper`` — breaking the
  identity round-trip (regeneration churn + orphan attachments). Fix:
  dispatch on the EARLIEST reserved-token POSITION in the tail
  (``min(_reserved_positions, key=...)``). Because ``generate_excel``
  always emits the structural marker FIRST in ``variant_suffix`` (tail[0]
  is the marker), the earliest-position token is ALWAYS the true variant —
  so this is byte-equivalent to the old order for every PRODUCED filename
  AND strictly more correct for reserved-token-in-name cases (an Opus
  equivalence harness found 15 divergences, all bug fixes incl. latent
  B-shape bugs like ``_ReducedSub_User_AEPBillable_Sue``). Generalizes the
  [2026-05-21 13:20] reserved-token-parse-order rule (which fixed the
  two-level ``_ReducedSub_User_`` shape) to the bare ``_User_`` /
  ``_VacCrew`` / ``_Helper`` shapes. Branch bodies + tail-scoping
  unchanged. Regression class
  ``TestBuildGroupIdentityReservedTokenInClaimerName`` (11 tests).
  **(2) Scope-builder authoritative-``__variant`` dispatch (Codex PR #223
  P1).** ``_build_primary_wr_scope`` decided "is this a partitioned
  primary group" by substring-matching the group KEY
  (``'_USER_' in _key and '_REDUCEDSUB' not in _key and '_AEPBILLABLE'
  not in _key``). Same fragility class: a helper NAMED "USER" →
  ``..._HELPER_USER_...`` (key contains ``_USER_``) was mis-bucketed as a
  primary, and a primary claimer named "REDUCEDSUB"/"AEPBILLABLE" was
  wrongly excluded. Since the scope feeds the DESTRUCTIVE bare-primary
  attachment cleanup AND the hash prune, a false positive could (in the
  worst case, narrowed by the ``ident not in valid_wr_weeks`` exemption)
  delete a legacy bare-primary attachment for a WR that never produced a
  primary ``_User_`` group. Fix: gate on the authoritative ``__variant``
  field (set at emission, ``r_copy['__variant'] = variant``):
  ``_g_rows[0].get('__variant') == 'primary' and '_USER_' in _key``. The
  ``__variant`` gate excludes helper/vac/sub groups regardless of NAME;
  the ``'_USER_' in _key`` clause then distinguishes a partitioned primary
  from a bare one (both call sites gate on
  ``PRIMARY_CLAIM_ATTRIBUTION_ENABLED``, so in production ``'both'`` mode
  every primary group is partitioned). Regression test
  ``TestBuildPrimaryWrScope::test_reserved_token_in_name_does_not_false_positive``.
  **New rule — variant detection MUST use the authoritative ``__variant``
  field (or the positional ``build_group_identity`` parse), never a key
  substring scan.** A claimer/helper/vac NAME — or a pathological WR token
  — can itself contain any reserved word (``USER``/``HELPER``/``VACCREW``/
  ``REDUCEDSUB``/``AEPBILLABLE``), so substring presence in a group key is
  not a reliable variant signal. This applies to the parser dispatch
  (fixed) and to ``_build_primary_wr_scope`` (fixed). NOTE: the sibling
  ``_build_subcontractor_wr_scope`` (``'_REDUCEDSUB' in _key``) and
  ``_build_vac_crew_wr_scope`` (``'_VACCREW' in _key``) carry the SAME
  latent substring pattern; their tokens are uppercase-unique so the
  realistic-data risk is nil (an all-caps "REDUCEDSUB"/"VACCREW" foreman
  name is required to trigger, and the effect is benign — a skipped
  migration / a no-op cleanup on a non-matching WR). They were left as-is
  to keep PR #223 scoped to D + the flagged P1; converting all three to
  ``__variant`` is a clean separate consistency-pass follow-up.
  **(3) Doc/comment reconciliation (Copilot nits, no behavior change):**
  (a) two D code comments said bare-primary "parsed identifier == ''" —
  corrected to ``identifier=None`` (``build_group_identity`` returns
  ``None`` for a bare primary with no ``_User_`` token; the ``not
  _identifier`` gate handles both None and ''; B/C legacy shapes DO parse
  to '' so their comments were left unchanged); (b) ``environment.md``
  ``LEGACY_PRIMARY_PARTITION_CLEANUP_ENABLED`` clarified that the companion
  hash prune is gated on ``PRIMARY_CLAIM_ATTRIBUTION_ENABLED`` (not this
  cleanup flag) — the CODE was always correct (mirrors C); only the doc
  was misleading; (c) this ledger entry's [2026-05-25 16:30] filename-suffix
  description + the design-spec finding #3 ("ZERO parser changes") + the
  plan's Task 11 intro ("No production code change") were updated to note
  the post-review parser hardening. ``pytest tests/`` → **866 passed / 26
  skipped / 61 subtests** (was 854 at the D close; +12: 11 reserved-token
  parser tests + 1 scope-builder regression). CI on PR #223 was fully
  green pre-fix (CodeQL, tests+coverage, codecov, Snyk, Semgrep, Vercel).
- [2026-05-25 18:15] Sub-project D PR #223 follow-up — Codex P1
  "partition primary groups in primary mode too": grouping-vs-identity
  inconsistency in ``RES_GROUPING_MODE == 'primary'``. **Finding (valid).**
  D's primary emission in ``group_source_rows`` correctly stays bare in
  primary mode — ``if RES_GROUPING_MODE == 'primary': keys_to_add.append(
  ('primary', f"{week}_{wr}", None))`` — lumping every non-helper/non-sub
  foreman's rows into ONE workbook per WR+week (the pre-pass at the
  ``_primary_claimer_map`` block is also already gated on
  ``RES_GROUPING_MODE in ('helper', 'both')``). But the FOUR consuming
  identity/filename surfaces gated ONLY on ``PRIMARY_CLAIM_ATTRIBUTION_ENABLED``
  (default on), NEVER on the mode: (1) ``generate_excel``'s primary
  ``variant_suffix`` branch, (2) Site 1 main-loop ``history_key`` /
  ``file_identifier``, (3) Site 2 ``valid_wr_weeks`` builder, (4) Site 3
  ``current_keys`` builder. ``__current_foreman`` is set on every row
  (``r_copy['__current_foreman'] = current_foreman or effective_user``),
  so in primary mode these surfaces derived ``_User_<first-sorted
  foreman>`` for a MERGED multi-foreman workbook — mislabeling it under one
  foreman and letting row-sort-order changes flip the filename / history
  key / attachment identity between runs (regeneration churn + orphan
  accumulation). Operator-reachable: the production schedule pins
  ``RES_GROUPING_MODE='both'`` (unaffected), but a manual
  ``workflow_dispatch`` with ``res_grouping_mode: primary`` hits it.
  **Codex's proposed remedy ("partition in primary mode too") is REJECTED**
  — the design spec (§Scope / Out of scope) documents that primary mode
  lumps helper + subcontractor rows into one file per WR where
  "partitioning by ``primary_foreman`` would be semantically wrong"; it
  must "stay bare/legacy." **Fix (the spec-aligned remedy):** gate all
  four consuming surfaces on ``PRIMARY_CLAIM_ATTRIBUTION_ENABLED and
  RES_GROUPING_MODE in ('helper', 'both')`` so primary mode is
  *consistently* bare at every surface — matching the already-mode-gated
  pre-pass + emission. In primary mode the surfaces now fall through to the
  legacy ``User``-field identifier path (``User`` "is never populated in
  production" per the spec → identifier ``''`` → bare key/filename,
  byte-identical to pre-D primary-mode behaviour). ``both`` / ``helper``
  production behaviour is unchanged (the mode predicate is True there). The
  Site 2/3 inner ``if (PRIMARY_CLAIM_ATTRIBUTION_ENABLED and _pf)`` ternary
  re-checks were left unchanged (they sit inside the now-mode-gated outer
  block, so they are unreachable in primary mode anyway). **New rule —
  emission-mode gates must be mirrored at every consuming identity/filename
  surface.** Extends the CR-01 four-site lockstep ([2026-05-15] /
  [2026-05-21 09:21]): when a variant's GROUP-KEY emission is gated on a
  grouping-mode predicate (``RES_GROUPING_MODE in (...)``), EVERY surface
  that later derives an identifier from that variant's rows — the
  ``generate_excel`` filename suffix AND all three identity sites
  (``history_key``/``file_identifier``, ``valid_wr_weeks``,
  ``current_keys``) — MUST carry the SAME mode predicate, not just the
  kill switch. A kill-switch-only gate on the consumers while the emission
  also gates on mode is a split-brain: the grouping says "bare/merged" but
  the filename/identity say "partitioned," and whichever row sorts first
  silently decides the (wrong) identity. The lesson generalizes the
  long-standing rule that the identity tuple must be built identically at
  every site — "identically" now explicitly includes the gating predicate,
  not only the value expression. Coverage gap that let it ship: the D test
  suite drove every ``group_source_rows`` / ``generate_excel`` case in
  ``both`` mode and had ZERO ``RES_GROUPING_MODE == 'primary'`` coverage
  for the identity/filename surfaces; the Sites A/B/C source-regex guards
  asserted the kill-switch gate but not the mode gate. Regression tests:
  new ``TestPrimaryModeStaysBare`` in
  ``tests/test_primary_claim_attribution.py`` (5 methods) — a BEHAVIORAL
  test that drives the real ``generate_excel`` in primary mode and asserts
  the produced filename has NO ``_User_`` suffix, a ``both``-mode positive
  control that asserts it DOES keep ``_User_<claimer>`` (guards against
  over-fixing), and three source-regex guards that the filename suffix +
  Sites 1/2/3 all carry the ``RES_GROUPING_MODE in ('helper', 'both')``
  predicate. Two prior filename-suffix source guards
  (``TestPrimaryFilenameSuffix.test_primary_branch_builds_user_suffix_gated``
  and ``TestSubprojectDProductionInvariants.test_filename_suffix_user_gated``)
  were reconciled in-place (regex widened to tolerate the interposed mode
  clause, citing this entry) per the [2026-05-25 16:30] test-contract
  reconciliation rule. ``pytest tests/`` → **871 passed / 26 skipped / 61
  subtests** (was 866; +5, zero regressions).
- [2026-05-25 18:35] Sub-project D PR #223 second review round
  (Copilot on ``f7ac747``). One correctness fix + one cosmetic rename;
  the perf fix was landed by the Codex bot in parallel (commit
  ``9d300f7``, integrated); Codex's P2 on the same commit was
  evaluated and REJECTED (see below).
  **(1) WR-matcher gap — production EXCLUDE_WRS silently fails for
  subcontractor per-claimer primary files (correctness, fixed).**
  Sub-project B emits subcontractor PRIMARY GROUP KEYS as
  ``{week}_{wr}_REDUCEDSUB_USER_<claimer>`` /
  ``{week}_{wr}_AEPBILLABLE_USER_<claimer>`` (the GROUP KEY, not just
  the filename) whenever attribution is on — the production default.
  But both ``_key_matches_wr`` (WR_FILTER, TEST_MODE) and
  ``_key_matches_excluded_wr`` (EXCLUDE_WRS, **production-active**)
  carried only the exact ``suffix == f"{wr}_REDUCEDSUB"`` /
  ``== f"{wr}_AEPBILLABLE"`` clauses plus the ``_HELPER_`` prefixes —
  no ``_REDUCEDSUB_USER_`` / ``_AEPBILLABLE_USER_`` prefix clause. The
  bare-exact clauses match only the attribution-OFF shape, so with
  attribution ON an operator excluding a subcontractor WR still
  generated AND uploaded its per-claimer primary files (the
  "do-not-bill-yet" intent silently failed), and a TEST_MODE
  ``WR_FILTER`` of such a WR dropped them. This is a latent
  Sub-project B ([2026-05-21 09:21]) violation of the mirror-matcher
  rule ([2026-05-15] CR-02/CR-03) — B added the new group-key shape
  but did not extend the two matchers. Fixed here (carried in the D
  PR because the matchers are the same functions D already modified):
  added ``or suffix.startswith(f"{wr}_REDUCEDSUB_USER_")`` and
  ``or suffix.startswith(f"{wr}_AEPBILLABLE_USER_")`` to BOTH matchers
  + updated the shape-list comment headers ("eleven shapes"). The
  ``_VACCREW_<claimer>`` clause — present in production but missing
  from the EXCLUDE-side test MIRROR (``_exclude_matches``) — was also
  synced. **(2) Pre-pass resolves wasted primary claimers for helper
  rows (perf, fixed by the Codex bot in ``9d300f7``, integrated).**
  The Sub-project D ``_primary_claimer_map`` pre-pass scoped rows by
  completed + non-vac + non-sub but did NOT exclude ``valid_helper_row``
  rows — which the emission later routes to the ``_Helper_<name>``
  shadow file and NEVER to a primary ``_USER_`` group (the emission
  gate is ``not valid_helper_row``). So every completed helper row
  cost a wasted ``resolve_claimer('primary', …)`` Supabase RPC. The
  bot added ``if _r.get('__is_helper_row') and
  _r.get('__helper_foreman') and _r.get('__helper_dept'): continue``
  to the pre-pass scope (helper_mode is guaranteed by the outer
  ``RES_GROUPING_MODE in ('helper','both')`` gate; helper_job is
  optional, matching the emission). It skips ONLY rows the emission
  would exclude from primary anyway, so attribution for genuine
  primary rows is unaffected — extends the [2026-04-25 14:00]
  per-row-RPC-latency rule (a pre-pass must mirror emission
  eligibility, not just variant type). Two behavioral regression
  tests were added on top of the bot's fix. **(3) Cosmetic:**
  ``test_all_{seven,eight}_variants_{retained,excluded}_for_target_wr``
  → ``test_all_variants_*`` (the shape count has grown past eight).
  **Codex P2 (REJECTED) — "Resolve primary claimers in primary
  grouping mode."** Codex argued primary mode "silently skips frozen
  attribution." That is INTENTIONAL: the [2026-05-25 18:15] fix made
  every D surface consistently bare in ``RES_GROUPING_MODE ==
  'primary'`` because the spec documents primary-mode partitioning as
  "semantically wrong" (it lumps helper + sub rows into one file).
  Codex's premise ("identity/filename logic still consumes
  ``__current_foreman``") is stale — all four surfaces are now
  mode-gated. No action; rationale posted to the PR.
  **New rule — a new group-key shape requires BOTH a matcher update
  AND a test-mirror update in the same change.** The mirror-matcher
  rule ([2026-05-15]) is necessary but not sufficient: the
  ``test_security_audit_followup.py`` matcher tests use LOCAL MIRROR
  copies (``_filter_matches`` / ``_exclude_matches``) of the
  production matcher bodies, tied to production only by the
  ``test_production_function_body_contains_all_*_clauses`` source-grep
  guards. When adding a variant key shape you MUST (a) extend both
  production matchers, (b) extend both test mirrors, AND (c) add the
  new clause's f-string needle to the source-grep guards — otherwise
  the mirror tests pass against a stale copy while production stays
  broken (exactly how B's gap survived two phases of green suites).
  Regression tests: ``tests/test_security_audit_followup.py`` — the
  renamed ``test_all_variants_{retained,excluded}_for_target_wr`` gain
  the ``_REDUCEDSUB_USER_`` / ``_AEPBILLABLE_USER_`` (+ ``_VACCREW_``)
  keys, the filter-side source guard now requires both new needles in
  BOTH matchers (``count >= 2``);
  ``tests/test_primary_claim_attribution.py::TestPrimaryPrePass``
  gains ``test_prepass_skips_valid_helper_row`` (resolve_claimer not
  called) and ``test_prepass_resolves_primary_only_skipping_helper``
  (called exactly once for a primary+helper pair). ``pytest tests/``
  → **873 passed / 26 skipped / 69 subtests** (was 871; +2, zero
  regressions).
- [2026-05-25 19:55] Scope-builder ``__variant`` consistency follow-up
  (standalone PR off master, the deferred item from PR #223's
  [2026-05-25 17:50] entry). Converted the two sibling scope builders
  ``_build_subcontractor_wr_scope`` and ``_build_vac_crew_wr_scope`` from
  key-substring detection (``'_REDUCEDSUB' in _key`` / ``'_VACCREW' in
  _key``) to the authoritative ``__variant`` field gate, completing the
  rule established by Subproject D's ``_build_primary_wr_scope`` fix
  ([2026-05-25 17:50]): **variant detection MUST use the ``__variant``
  field (or a positional ``build_group_identity`` parse), never a key
  substring scan.** ``_build_subcontractor_wr_scope`` now gates on
  ``__variant in {'reduced_sub','aep_billable','reduced_sub_helper',
  'aep_billable_helper'}`` (new module frozenset
  ``_SUBCONTRACTOR_SCOPE_VARIANTS``); ``_build_vac_crew_wr_scope`` gates
  on ``__variant == 'vac_crew'``. **Why it matters:** both scopes feed
  DESTRUCTIVE attachment-cleanup + hash-prune paths, and the substring
  scan had two latent defects: (1) a non-sub/non-vac group whose
  claimer/helper NAME is an all-caps reserved token (``REDUCEDSUB`` /
  ``VACCREW`` — e.g. a helper named "VACCREW" → key ``..._HELPER_VACCREW``)
  false-positived into the destructive scope (the ``valid_wr_weeks``
  live-identity exemption is the only thing that prevented an actual
  deletion); (2) ``_build_subcontractor_wr_scope``'s ``'_REDUCEDSUB'``
  substring silently MISSED ``_AEPBILLABLE``-only keys — it produced the
  correct WR set only by relying on the invariant that every sub WR also
  emits a ``reduced_sub`` group. The ``__variant`` gate is both robust
  (no pathological-name false positives) and strictly more complete
  (catches every subcontractor variant directly). **Behavior-preserving
  for production data:** realistic WR#s and foreman names produce the
  identical WR scope set under either approach, so this is a robustness
  hardening, not a behavior change. The realistic-data risk of the old
  substring approach was nil (an all-caps reserved-word foreman name is
  required to trigger, and the live-identity exemption blunts the
  blast), which is why this was deferred from PR #223 to keep that PR
  scoped — but the three sibling scope builders are now consistent, and
  the rule has a regression net at all three. **Test-fixture
  reconciliation** ([2026-05-20 00:26] rule 2): six hash-prune tests
  across Subprojects A/B/C built synthetic ``groups`` dicts whose rows
  omitted ``__variant`` (production always sets it at the
  ``group_source_rows`` emission site); their fixtures
  (``_make_groups_with_reducedsub``, the two ``_groups`` helpers, and
  two inline group dicts) were updated to carry ``__variant`` — the same
  fixture update D applied to ``TestBuildPrimaryWrScope`` /
  ``TestSubprojectDHashPrune``. Regression tests:
  ``tests/test_vac_crew_claim_attribution.py`` gains
  ``test_scope_builder_rejects_pathological_vaccrew_name`` (a helper
  named "VACCREW" must NOT enter the vac scope) and updates the three
  existing vac-scope tests to the ``__variant`` contract;
  ``tests/test_subcontractor_helper_shadow_rescue.py`` gains
  ``TestSubcontractorWrScopeVariantGate`` (4 methods — collects all four
  sub variants incl. ``_AEPBILLABLE``-only, excludes non-sub variants,
  rejects a primary claimer named "REDUCEDSUB", empty-groups). ``pytest
  tests/`` → **878 passed / 26 skipped / 69 subtests** (was 873 on
  master; +5, zero regressions). NOTE for future variants: when adding
  a new variant whose group key embeds a reserved token, the scope
  builder (if any) MUST gate on ``__variant``, and synthetic prune/
  cleanup test fixtures MUST set ``__variant`` on their rows.
- [2026-05-25 20:55] **Sub-project E (Supabase durable change-detection
  hash store + filename token stripping) shipped — DORMANT.** The final
  piece of the universal-claim-attribution + change-detection
  modernization sequence (A → Phase 1.1 → B → C → D → E). E moves the
  DURABLE per-group change-detection hash off the attachment FILENAME
  (and off the ephemeral local ``hash_history.json``) into a new Supabase
  table ``billing_audit.group_content_hash`` keyed on the SAME 4-tuple as
  the engine's ``history_key`` (``wr | week_ending | variant |
  identifier``), then — once authoritative — strips the ``_<timestamp>``
  and ``_<hash>`` tokens from generated filenames so the canonical name
  becomes ``WR_{wr}_WeekEnding_{MMDDYY}{variant_suffix}.xlsx`` (identity
  only). Spec:
  ``docs/superpowers/specs/2026-05-25-subproject-e-supabase-hash-store-design.md``;
  plan:
  ``docs/superpowers/plans/2026-05-25-subproject-e-supabase-hash-store.md``.
  **Four operator-approved decisions (the contract):** (1) NEW per-group
  table ``group_content_hash`` (NOT the existing ``pipeline_run.content_hash``,
  which is only a per-(wr,week) aggregate and lacks the per-variant skip
  granularity). (2) Supabase authoritative + ``hash_history.json`` as a
  local fast cache / offline fallback; dual-write. A Supabase outage
  degrades to "use json cache → regenerate", NEVER a silent skip. (3)
  Strip BOTH the timestamp and the hash → deterministic canonical name.
  (4) Ship DORMANT — shadow-write from day one, keep the authoritative
  read + filename stripping behind a default-OFF kill switch, flip ON
  after validation (mirrors Foundation A's dormant-ship).
  **Two flags** (``generate_weekly_pdfs.py``, startup-banner-logged,
  workflow-pinned): ``SUPABASE_HASH_STORE_WRITE_ENABLED`` (default ``'1'``
  — shadow-write the per-group hash every run; harmless while not
  authoritative) and ``SUPABASE_HASH_STORE_AUTHORITATIVE`` (default ``'0'``
  — when ON, the skip gate reads Supabase, filenames go clean, and
  ``delete_old_excel_attachments`` stops relying on the filename hash).
  **Reader/writer** (``billing_audit/writer.py``, both fail-safe, sharing
  the existing ``with_retry`` / per-op circuit breaker / run-global kill
  switch via DISTINCT op identifiers so a hash-store outage cannot cascade
  into disabling the attribution/pipeline_run writers): ``lookup_group_hash
  (wr, week_ending, variant, identifier) -> (hash|None, status)`` with
  status ∈ ``success`` / ``no_row`` / ``fetch_failure`` / ``unavailable``,
  and ``upsert_group_hash(...)`` best-effort UPSERT on the 4-tuple PK
  (``updated_at`` omitted from the payload — the column ``DEFAULT NOW()``
  applies, avoiding any supabase-py literal-``now()`` rejection).
  **Skip gate** extracted to a pure, unit-testable helper
  ``_resolve_unchanged_for_skip(history_key, data_hash, hash_history,
  wr_num, week_iso, variant, identifier)``: when authoritative it reads
  ``lookup_group_hash`` (``success`` → compare; ``no_row`` → False /
  regenerate — the safe migration default that makes the first
  authoritative run rebuild everything once and populate the store;
  ``fetch_failure`` / ``unavailable`` / ``disabled`` → fall back to the
  ``hash_history.json`` cache). ``_history_eligible_for_skip``
  (FORCE_GENERATION / REGEN_WEEKS / RESET_* gating) and the
  ``ATTACHMENT_REQUIRED_FOR_SKIP`` guard are UNCHANGED — a matching hash
  with a missing attachment still regenerates. Shadow-write is wired right
  after the ``hash_history[history_key]`` json write, gated on
  ``SUPABASE_HASH_STORE_WRITE_ENABLED and BILLING_AUDIT_AVAILABLE and not
  TEST_MODE``, using a single ``week_iso`` (ISO ``YYYY-MM-DD`` from the
  group's ``__week_ending_date``, normalized exactly like the existing
  ``_week_snap`` the freeze/fingerprint calls use) so the reader and
  writer agree on the DATE-typed key.
  **KEY RISK — ``build_group_identity`` clean-name parsing (the one to
  remember).** The parser's tail-extraction used to UNCONDITIONALLY strip
  the last ``_``-split token as the 16-char hash and assume a leading
  6-digit timestamp. A clean (token-less) name has NEITHER, so the
  unconditional strip ate the last identifier segment (e.g.
  ``_User_Jane_Smith`` → identifier ``'Jane'``). The fix discriminates
  legacy vs clean by the **leading 6-digit ``HHMMSS`` timestamp at
  ``tail[0]``**: a legacy variant name ALWAYS carries it (immediately
  after the week) AND a trailing hash; a clean name NEVER does
  (``tail[0]`` is always a variant marker — alphabetic — or ``tail`` is
  empty). So strip BOTH decorations ONLY when the leading timestamp is
  present, then the identifier is everything after the marker (the five
  dispatch slices changed from ``[start:-1]`` to ``[start:]``). The first
  attempt — strip a trailing token only if it is exactly 16-hex — was
  REJECTED because the existing test corpus uses short placeholder hashes
  (``abc123``, ``ab12cd34ef``) that the 16-hex rule would have left in the
  identifier; the timestamp-discriminator preserves all legacy-name
  parsing AND handles clean names. The leftmost-weak ``WeekEnding``
  candidate selection + the D earliest-reserved-token dispatch are
  unchanged, so a pathological clean identifier that sanitizes to
  ``WeekEnding_<6digits>`` still round-trips. Legacy token-bearing names
  and clean names COEXIST on Smartsheet during migration; the parser reads
  either.
  **Cleanup:** ``delete_old_excel_attachments`` gates its legacy
  filename-hash short-circuit on ``not SUPABASE_HASH_STORE_AUTHORITATIVE``
  (clean names return ``None`` from ``extract_data_hash_from_filename``
  anyway) — forcing always wins, and the identity-based replacement loop
  still runs so a fresh clean file supersedes any prior (token-named or
  clean) attachment for the same identity. Return shape
  ``(deleted_count, skipped_due_to_same_data)`` preserved.
  **No bulk migration / self-healing cutover:** the first authoritative
  run sees an empty store (``no_row`` everywhere) and regenerates each
  group once, which the shadow-write then records; subsequent runs skip.
  **OPERATOR PREREQUISITE (blocks activation — not code):** before
  ``SUPABASE_HASH_STORE_AUTHORITATIVE`` can ever be flipped (and for
  shadow writes to land at all), the operator MUST apply
  ``billing_audit/schema.sql`` (the new ``group_content_hash`` table) to
  the live Supabase project AND reload the PostgREST schema cache
  (``NOTIFY pgrst, 'reload schema';``). Until then ``lookup_group_hash``
  returns ``unavailable`` and the pipeline behaves exactly as today
  (fail-safe). Default OFF = ZERO production behavior change.
  **New rules:** (1) **The durable change-detection hash lives in
  ``billing_audit.group_content_hash``; filenames are IDENTITY-ONLY (no
  hash/timestamp) when authoritative; a Supabase outage degrades to
  regenerate, never skip.** Any future change to the filename grammar or
  the skip gate MUST preserve: clean filenames round-trip through
  ``build_group_identity`` (both clean and legacy shapes), the json cache
  remains the offline fallback, and ``no_row`` / a cache miss regenerates.
  (2) **Filename-shape discrimination uses the leading 6-digit timestamp,
  not the trailing token's hex-ness.** When a parser must read both a
  legacy ``..._{HHMMSS}_<marker>_<id>_<hash>`` shape and a clean
  ``..._<marker>_<id>`` shape, key the strip on the leading-timestamp
  discriminator (a structural signal both formats agree on) rather than
  on the trailing token's content — placeholder / edge-case hashes make a
  content-based hash detector brittle (the rejected first attempt). (3)
  **Any new Supabase reader/writer MUST use a DISTINCT ``with_retry`` op
  identifier** (``lookup_group_hash`` / ``upsert_group_hash`` here) so its
  circuit breaker is isolated and a hash-store outage cannot disable the
  correctness-critical attribution / pipeline_run writers (extends the
  [2026-04-25 14:00] op-isolation rule). Executed via TDD (Tasks 2–11,
  each red→green→commit). Regression tests:
  ``tests/test_subproject_e_hash_store.py`` (``TestConfigFlags``,
  ``TestSchemaHasGroupContentHash``, ``TestBuildGroupIdentityCleanNames``,
  ``TestCleanFilename``, ``TestShadowWrite``, ``TestAuthoritativeSkipGate``,
  ``TestDeleteOldCleanNames``, ``TestMigrationCutover``,
  ``TestWorkflowPinned``, ``TestProductionInvariants``) plus
  ``LookupGroupHashTests`` + ``UpsertGroupHashTests`` in
  ``tests/test_billing_audit_shadow.py``. ``pytest tests/`` →
  **944 passed / 26 skipped / 69 subtests** (was 882 at the E-branch base;
  +62 net, zero regressions). E ships dormant; after it is validated in
  production, flip ``SUPABASE_HASH_STORE_AUTHORITATIVE=1`` (one-line
  workflow change, revertable).
- [2026-05-26 01:45] **Production timeout incident: the per-row
  ``lookup_attribution`` pre-pass resolved ~137k Supabase RPCs/run,
  blowing the workflow time budget.** Scheduled weekly runs began hitting
  the GitHub Actions ``timeout-minutes`` hard cap ("maximum execution time
  of 1h50m0s" → 110min) and getting cancelled mid-generation. Root cause
  (NOT Sub-project E — E's ``upsert_group_hash`` was only ~1,264
  calls/~2min, and a PRE-E run timed out too): the claim-attribution
  pre-passes added by Foundation A / B / C / D — three per-variant
  pre-passes in ``group_source_rows`` (``_sub_primary_claimer_map`` /
  ``_vac_crew_claimer_map`` / ``_primary_claimer_map``) PLUS the Phase 1.1
  subcontractor-helper path's direct ``lookup_attribution`` call inside
  the grouping loop — each call the ``lookup_attribution`` RPC once per
  completed row. Run UNBOUNDED, they resolve EVERY completed row across
  ALL historical weeks. The canceled-run log showed **136,960 successful
  ``POST /rpc/lookup_attribution`` + 8,044 ``RemoteProtocolError`` retries**
  (98% of all Supabase traffic), with "Skip (unchanged + attachment
  exists)" spanning weeks from Nov 2025 (``112325``) through Mar 2026
  (``032226``) — i.e. the pre-pass eagerly resolved attribution for tens
  of thousands of OLD rows whose groups change-detection then SKIPPED
  (so the resolved claimer was never even used). The cost scaled with
  ACCUMULATED HISTORY, not active work, and crossed the ~95min
  ``TIME_BUDGET_MINUTES`` as data grew (a 00:43 run took 73min; a 01:44
  run jumped to 122+ and was killed). **Diagnosed via systematic-debugging
  (Phase 1 evidence: workflow config 110/95 — NOT the documented 195/180;
  ``gh run`` durations; ``gh run view --log`` HTTP-endpoint breakdown).
  Fix (operator-chosen): recent-week scope.** New env var
  ``ATTRIBUTION_RESOLUTION_WEEKS`` (default ``8``, workflow-pinned, safe-
  parsed) + two module helpers ``_attribution_resolution_cutoff()`` /
  ``_attribution_week_in_scope(week_ending)`` (cutoff = ``date.today() -
  timedelta(weeks=N)``; ``N<=0`` disables scoping; ``None``/unparseable
  date → in-scope fail-safe). All FOUR resolve sites gate row collection
  on ``_attribution_week_in_scope`` so resolution cost tracks the recent
  edit horizon, not total history. **Correctness:** an out-of-scope row
  resolves to use-current at emission, but its group is either (1)
  unchanged + attachment exists → skipped, claimer unused (zero impact),
  or (2) the rare edit to a ``>N``-week-old row → regenerated with the
  current foreman (the SAME legacy/no_history fallback the feature already
  documents). Critically, the **freeze (write) side is UNTOUCHED** —
  ``freeze_row`` still freezes every completed row during generation — so
  the durable ``attribution_snapshot`` stays complete; only the wasteful
  READ-backs of old skipped weeks are eliminated. Also raised
  ``timeout-minutes`` 110→180 and ``TIME_BUDGET_MINUTES`` 95→165 (per
  operator request) for headroom; with scoping, normal runs return to
  ~recent-work runtime well under the cron interval (concurrency is
  queue-mode, ``cancel-in-progress: false``). **New rules:** (1) **Any
  per-row external I/O (Supabase RPC, HTTP, etc.) in a path that iterates
  ALL source rows MUST be scoped to the work that will actually be
  emitted/regenerated — never run eagerly over full accumulated history.**
  The [2026-04-25 14:00] rule ("per-row I/O goes in a bounded
  ThreadPoolExecutor pre-pass, not the hot loop") made the calls PARALLEL
  but did NOT bound their COUNT; parallelism hides an O(all-history) call
  count until the dataset grows enough to blow the budget. A pre-pass that
  resolves data for rows whose groups will be skipped by change-detection
  is pure waste — scope it (recent-week window here) so cost tracks active
  work. (2) **A read-side optimization that skips resolution for some rows
  MUST preserve the write/freeze side and degrade to the documented
  fallback** (use-current here), never to a crash or a silent wrong value.
  (3) **A new test module that calls ``_ensure_smartsheet_mocked()`` at
  import MUST guard it behind ``try: import smartsheet except
  ImportError:``** — calling it unconditionally at top level installs a
  bare ``smartsheet`` MagicMock stub into ``sys.modules`` during pytest
  COLLECTION, and if that module sorts alphabetically before suites that
  need the REAL SDK (e.g. ``TestDiscoverFolderSheets`` doing ``from
  smartsheet.models.sheet import Sheet``), it shadows the real package and
  breaks them with "'smartsheet' is not a package". Use the real SDK when
  installed; only stub when it is genuinely absent. Regression tests:
  ``tests/test_attribution_resolution_scope.py`` —
  ``TestAttributionResolutionWeeksConfig`` (env + banner),
  ``TestAttributionWeekInScope`` (recent/old/boundary/disabled/datetime/
  None decision table), ``TestPrePassRespectsWeekScope`` (behavioral:
  ``group_source_rows`` does NOT call ``resolve_claimer`` for a 30-week-old
  row but DOES for a 1-week-old row), ``TestResolveSitesGatedOnScope``
  (source-grep: >=4 ``_attribution_week_in_scope`` gates). ``pytest tests/``
  → **955 passed / 26 skipped / 69 subtests** (was 945; +10, zero
  regressions). Separately noted (not the cause, benign): the "Node.js 20
  is deprecated" Actions warning — a future maintenance item to bump
  ``actions/checkout`` / ``actions/cache`` / ``actions/setup-python`` /
  ``actions/upload-artifact`` to Node-24 versions.
- [2026-05-26 14:55] **Phase 2 — Attribution Bulk-Prefetch + Historical
  Claimer Remediation.** Closes the emergent interaction between the
  [2026-05-26 01:45] `ATTRIBUTION_RESOLUTION_WEEKS=8` scope hotfix and
  Sub-project E's `SUPABASE_HASH_STORE_AUTHORITATIVE=1` activation
  (commit `67539ec`). **Root cause:** the scope hotfix gated group-KEY /
  filename formation (not merely skipping), so E's `no_row -> regenerate`
  wave for historical groups resolved claimers from the scoped pre-pass
  (empty for out-of-scope weeks) → `_User__NO_MATCH` (131 files) /
  `_User_Unknown_Foreman` (241 files) uploaded over real historical
  attachments in run 26439205107 (372 of 1,116 generated files affected).
  `attribution_snapshot.frozen_primary` was ~99% populated with real names
  back to mid-2025 — the data existed; the read side never loaded it for
  old weeks. Immediate mitigation: reverted `SUPABASE_HASH_STORE_AUTHORITATIVE`
  to `0` (commit `46cd05d`). **Fix (read-side only — three plans, TDD):**
  **(Plan 02-01)** Added `lookup_attribution_bulk` Supabase RPC
  (`billing_audit/schema.sql`, `jsonb_to_recordset` bulk join, CASE
  blocks copied verbatim from `lookup_attribution`, `GRANT EXECUTE TO
  service_role`). Added `prefetch_attribution(pairs)` bulk reader (chunked
  at 500 pairs/RPC, fail-safe, op id `lookup_attribution_bulk` — distinct
  from all existing ops). Updated `resolve_claimer(prefetched_map=)` with
  a new keyword parameter for O(1) map reads (default `None` calls the
  prior per-row path byte-identically). D-04 contract: on `fetch_failure`
  the CALLER constructs `ResolveOutcome('hold', ...)` directly — zero
  additional Supabase RPCs on total outage.
  **(Plan 02-02)** Replaced all four per-variant `ThreadPoolExecutor`
  pre-passes (sub-primary B, vac-crew C, primary D, sub-helper Phase 1.1)
  with a single shared `_attr_map` built by one `prefetch_attribution()`
  call before `group_source_rows`. Each consumer block does an O(1)
  `resolve_claimer(prefetched_map=_attr_map)` map read — no per-row RPC
  in the hot loop. B and C apply the D-04 direct-HOLD contract on
  `fetch_failure`; D uses-current (no HOLD — correctness tradeoff, per
  design). `ATTRIBUTION_RESOLUTION_WEEKS` removed entirely from code,
  workflow pin, `environment.md`, and all 4 gate sites — the exact-set
  bulk load makes recency-gating obsolete and eliminates the footgun that
  caused the incident. `tests/test_attribution_resolution_scope.py`
  deleted (13 tests against now-deleted helpers); `TestHistoricalClaimerRegression`
  added.
  **(Plan 02-03)** New default-OFF, dry-run-first, isolated
  `run_claimer_remediation(client, dry_run, window_weeks, valid_wr_weeks=None)`
  that sweeps `*_NO_MATCH*` / `*_Unknown_Foreman*` attachments across
  TARGET and PPP within a configurable window (default 26 weeks).
  `build_group_identity()` parses each filename (battle-hardened parser,
  not a new regex); live-identity exemption preserves correct files
  ([2026-05-19 23:45] rule); isolated dispatch returns before any Excel
  generation. Three env vars workflow-pinned: `REMEDIATE_CLAIMERS='0'`,
  `REMEDIATION_DRY_RUN='1'`, `REMEDIATION_WINDOW_WEEKS='26'`.
  **Sequencing / gate (D-09/D-10/D-11):** the fix ships with
  `SUPABASE_HASH_STORE_AUTHORITATIVE=0`. The flip to `1` is a SEPARATE,
  human-gated operator action after an evidence-based validation run (zero
  garbage names; O(chunks) attribution HTTP; runtime <=165 min; pytest
  green) — explicitly NOT auto-committed in the fix PR; the human gate
  preserves the separation that the premature `67539ec` flip skipped.
  Remediation runs AFTER E activation so regenerated files are clean-named
  (no double-churn). Operator procedure documented in
  `website/docs/runbook/operations.md` (D-01 RPC deploy + reload, D-10
  validation gate, D-11 separate flip, D-08 dry-run-first sweep).
  **New rules:**
  (1) **A recency/scope gate must NEVER sit on group-KEY / filename
  formation — only on skip optimizations.** If a value (claimer name,
  foreman, dept) participates in the identity tuple used for
  `history_key`, `file_identifier`, `valid_wr_weeks`, or the on-disk
  filename, it must be resolved for EVERY group that generates — not
  just for the "recent" subset. The exact-set bulk load is the correct
  pattern: collect all `(wr, week_ending, row_id)` triples that will
  actually generate, load them in one round-trip, read O(1) from the
  map. Extends [2026-05-26 01:45]: parallelism hides O(all-history)
  call counts; the fix is BULK load (eliminate per-row network cost
  entirely), not merely parallelize or scope.
  (2) **Any new `billing_audit` reader must use `with_retry` + the
  per-op circuit breaker with a DISTINCT op id** (op-isolation, extends
  [2026-04-25 14:00]). Per-row external I/O over all source rows must be
  ELIMINATED via bulk load, not merely parallelized (extends [2026-05-26
  01:45]). On a bulk total-failure (`fetch_failure`) the CALLER applies
  the per-variant fallback DIRECTLY — HOLD for B/C (correctness over
  availability), use-current for D (availability over strict correctness
  for the universal primary path) — with ZERO re-invocation of the
  per-row RPC path. Never route a bulk-failure through the individual
  `_lookup_attribution_all` path as a fallback: that would re-introduce
  O(N) calls on the exact outage scenario the bulk load is meant to
  eliminate.
  (3) **A go-live flip that depends on a separate code fix must be a
  documented, human-gated operator action — never bundled into the fix
  PR.** The `SUPABASE_HASH_STORE_AUTHORITATIVE=1` flip is the canonical
  example: E shipped dormant (correct), the premature flip (`67539ec`)
  triggered the incident, the fix (Phase 2) restores correctness, and
  the re-flip is a separate PR with a documented validation gate. Any
  future dormant feature whose activation depends on a data contract
  (Supabase RPC deploy, schema change, backfill) must follow this
  pattern: fix ships at `FEATURE=0`; operator validates with evidence;
  flip is a one-line commit in its own PR citing the validation run.
  **Regression tests (all TDD red->green):**
  `tests/test_billing_audit_shadow.py`: `PrefetchAttributionTests` (8),
  `ResolveClaimerMapAwareTests` (7), `LookupGroupHashTests` (previously
  shipped by E). `tests/test_primary_claim_attribution.py`:
  `TestHistoricalClaimerRegression`. `tests/test_claimer_remediation.py`
  (new file, 9 tests — `TestDryRunNeverDeletes`, `TestExecuteDeletesOnlyGarbage`,
  `TestLiveIdentityExemption`, `TestIsolationPathValidWrWeeksNone`,
  `TestWindowFilter`, `TestBothSheetsSwepped`, `TestUnparseableFilesIgnored`,
  `TestPppDisabledOnlyTargetSwept`). `tests/test_attribution_resolution_scope.py`
  deleted (13 tests, helpers removed). `pytest tests/` after Plan 02-03:
  **973 passed / 26 skipped / 69 subtests** (was 955 at Phase 2 start;
  net +18 new, -13 deleted = +5 net passing). Plan 02-04 (this entry)
  is documentation-only; no additional test delta.
- [2026-05-26 22:45] **Phase 2 gap-closure round — 10 review findings
  closed (1 BLOCKER + 5 WARNING + 4 INFO) across Plans 02-05 and 02-06.**
  The post-Phase-2 code review (`02-REVIEW.md`) surfaced correctness, safety,
  and observability issues in the remediation mode and the bulk-prefetch
  attribution wiring shipped by Plans 02-01 through 02-04. All 10 were closed
  additively and surgically; the billing pipeline (Excel generation, upload,
  hash history) is untouched.
  **CR-01 (BLOCKER) — deployment-ordering hazard: a missing
  ``lookup_attribution_bulk`` RPC (PGRST202) previously HELD all B/C/sub-helper
  billing files** every run until an operator deployed the RPC. Fix (Plan
  02-05): ``prefetch_attribution`` now emits a distinct ``rpc_missing`` status
  (via a bounded one-call classification probe on the already-failed
  ``with_retry`` path) vs the transient ``fetch_failure``. A new default-ON
  workflow-pinned ``ATTRIBUTION_BULK_PREFETCH_FALLBACK`` kill switch degrades
  ``rpc_missing`` to the deployed per-row ``lookup_attribution`` path (same
  frozen data, slower — NOT a D-04 violation because frozen data is still
  loaded), while a genuine transient outage still HOLDs B/C (D-04 preserved).
  The merge no longer depends on deploy ordering. Fail-safe default: only a
  provably-PGRST202 probe exception yields ``rpc_missing``; everything else
  stays ``fetch_failure``.
  **WR-01 — WR-sanitization split-brain in ``resolve_claimer``'s prefetched-map
  lookup.** The map key was sanitized (``_WR_SANITIZE``) at build time but the
  lookup key was raw, so a sanitization-sensitive WR# silently fell back to
  use-current instead of resolving the frozen claimer. Fix (Plan 02-05):
  sanitize the lookup key identically to the map key ([2026-04-23 18:25]
  consumer-consistency rule). Numeric WR#s are a no-op.
  **WR-02 — documented remediation activation path was unreachable.** The
  operations.md Step 4 showed dedicated ``workflow_dispatch`` input keys that
  don't exist (GitHub Actions 10-input limit is already exceeded), and the
  Python defaults were overridden by literal step-``env:`` pins that silently
  masked the ``$GITHUB_ENV`` path. Fix (Plan 02-06): three new case branches
  in the ``advanced_options`` parser (``remediate_claimers``,
  ``remediation_dry_run``, ``remediation_window_weeks``) export to
  ``$GITHUB_ENV``; the three literal pins were removed so the parser path wins;
  Python defaults (OFF/dry-run/26wk) supply the safe cron-run defaults when
  ``advanced_options`` is unset. Docs rewritten to show the real activation path.
  **WR-03 — misleading D-consumer comment (no ``action='disabled'``).** The
  comment incorrectly stated a disabled ``resolve_claimer`` result carries
  ``action='disabled'``; the actual value is ``'use'`` (disabled returns
  use-current). Fixed inline (Plan 02-05).
  **WR-04 — isolated EXECUTE sweep deleted a valid ``_Unknown_Foreman`` file.**
  ``_Unknown_Foreman`` is a legitimate current sentinel emitted when
  ``effective_user`` / ``Foreman Assigned?`` is blank. In the isolated path
  (``valid_wr_weeks=None``) there is no live-identity set to protect it, so an
  EXECUTE sweep would create a data-absent window until the next cron. Fix
  (Plan 02-06): add ``_ALWAYS_GARBAGE_PATTERNS = ('_NO_MATCH',)`` (the
  always-garbage subset) and select the active pattern set in
  ``run_claimer_remediation`` by ``valid_wr_weeks is not None``. The isolated
  path now deletes only ``_NO_MATCH`` (a pure Smartsheet ``#NO MATCH`` error
  token, never a real filename component); the non-isolated path is unchanged
  (both tokens eligible, subject to the live-identity exemption).
  **WR-05 — sub-helper outage path dropped the per-WR fetch_failure WARNING.**
  The ``_attr_status`` thread was not carried into the sub-helper block after
  the CR-01 wiring, silencing the observability path. Fix (Plan 02-05):
  thread ``_attr_status`` so the per-WR ``reason=fetch_failure`` WARNING fires
  again.
  **IN-01 through IN-04:** dead ``_resolve_claimer_bulk`` / ``_ResolveOutcome``
  imports removed (IN-01); ``out_of_window`` reordered to count only garbage
  files (IN-02); operations.md dry-run quote aligned to the real summary-line
  format (IN-03); shadowing local ``import datetime as _dt`` removed from
  ``run_claimer_remediation`` (IN-04).
  **New rules:**
  (1) **A hard-runtime RPC dependency MUST distinguish "not deployed"
  (permanent — degrade gracefully) from "transient outage" (preserve strict
  HOLD policy).** When ``with_retry`` collapses an APIError to ``None``,
  re-probe once on the already-failed path to recover the reason_code.
  The degrade path MUST be a default-ON workflow-pinned kill switch
  (``ATTRIBUTION_BULK_PREFETCH_FALLBACK``) so deploy ordering can never suppress
  billing; a transient outage must still HOLD (D-04) so the degrade never
  becomes a back-door around correctness guarantees. Fail-safe: only a
  provably-PGRST202 probe exception yields ``rpc_missing``; unknown errors stay
  ``fetch_failure``.
  (2) **An attachment-deleting sweep with no live-identity set (isolated path)
  MUST restrict its garbage set to tokens that are NEVER a legitimate filename
  component.** ``_NO_MATCH`` (Smartsheet ``#NO MATCH`` error) is always garbage.
  ``_Unknown_Foreman`` is a legitimate current sentinel for blank foreman rows
  and must NOT be deleted in the isolated path — a data-absent window until the
  next cron is worse than leaving an ambiguous file in place. Only the
  non-isolated path (``valid_wr_weeks`` provided, live-identity exemption active)
  may sweep both tokens.
  (3) **A rarely-used destructive operator control is wired through the
  ``advanced_options`` parser, never a new top-level input (10-input limit), and
  a literal step-``env:`` pin will silently mask the parser.** Remove the literal
  pin so ``$GITHUB_ENV`` wins; Python module defaults supply the safe no-op
  values when ``advanced_options`` is absent (OFF / dry-run-first / bounded
  window). Verify the masking is gone by asserting the literal pin no longer
  appears in the step ``env:`` block.
  (4) **A counter that gates operator decisions about destructive scope
  (``out_of_window``) MUST count only entities in scope for the gate.** Moving
  the garbage check before the window filter is the correct fix; a label-only
  rename would still mis-count. Apply the same reorder discipline to any future
  filter pipeline with a scope-counting metric.
  Regression tests (Plans 02-05 + 02-06): ``tests/test_billing_audit_shadow.py``
  gains ``PrefetchAttributionTests`` + ``ResolveClaimerMapAwareTests``;
  ``tests/test_subcontractor_helper_shadow_rescue.py`` gains
  ``TestRpcMissingGracefulDegradation`` (6 tests);
  ``tests/test_claimer_remediation.py`` gains
  ``TestIsolatedPathUnknownForemanProtection`` (3 tests) +
  ``TestOutOfWindowCountsOnlyGarbage`` (2 tests). ``pytest tests/`` →
  **986 passed / 29 skipped / 69 subtests** (was 981 at Plan 02-05 close;
  +5 net passing).
- [2026-05-27 14:45] **Production incident: stale Supabase
  ``billing_audit`` schema — claim attribution silently degraded to the
  current foreman, and the missing bulk RPC recreated the ~137k per-row
  explosion.** Operator reported that every subcontractor
  (``_ReducedSub`` / ``_AEPBillable``) and primary file was named after
  the SAME (current) foreman regardless of which week/foreman actually
  worked the WR, and recent scheduled runs were timing out at ~3h.
  **Root cause (TWO contract drifts in the deployed DB, NOT a code
  bug):** the live Supabase project (``poeyztlmsawfoqlanucc`` —
  "Smarthsheet-Resiliency-Offloaded-Data") was never updated to the
  current ``billing_audit/schema.sql``. (1) ``lookup_attribution_bulk``
  was **not deployed at all** → ``prefetch_attribution`` returned
  ``rpc_missing`` → with ``ATTRIBUTION_BULK_PREFETCH_FALLBACK=1`` the run
  degraded to per-row ``lookup_attribution`` and fired **138,478**
  per-row RPCs (the exact pre-Phase-2 [2026-05-26 01:45] explosion),
  pushing scheduled runs to the 3h cancel ceiling. (2) The deployed
  ``lookup_attribution`` was the **stale Phase-01.1 helper-only version**
  returning only ``(helper, helper_dept, source_run_id)`` — it did NOT
  return ``primary_foreman`` / ``vac_crew``. The reader
  ``_lookup_attribution_all`` (and ``ROLE_BY_VARIANT['primary'] =
  'primary_foreman'``) therefore read ``primary_foreman`` as absent →
  ``resolve_claimer`` fell back to use-current for EVERY primary/vac row,
  while HELPER attribution kept working (the deployed RPC still returned
  ``frozen_helper``). That asymmetry — correct ``_Helper_<name>`` but
  wrong/current ``_User_<name>`` — is the fingerprint. The
  ``attribution_snapshot`` data was fine all along (142,806 rows, 49
  weeks back to 2025-06, 99.3% real ``frozen_primary``; e.g. WR
  90727774 correctly froze Mark Diaz for the March/early-May weeks and
  Wade Watson for May 17/24 — but every file shipped as Wade Watson).
  **Why the deploy silently never took (the latent ``schema.sql``
  defect):** ``schema.sql`` instructed operators to "apply this CREATE
  OR REPLACE", but Postgres ``CREATE OR REPLACE FUNCTION`` **cannot
  change a function's return columns** (3 → 5). Running it over the
  helper-only version errors with "cannot change return type of existing
  function", so the multi-role contract never installed and no one
  noticed (the error was in a manual SQL-editor step, not CI). **Fix:**
  (1) Applied a migration to ``poeyztlmsawfoqlanucc`` that
  ``DROP FUNCTION IF EXISTS billing_audit.lookup_attribution(TEXT, DATE,
  BIGINT)`` then re-creates the 5-column version, creates
  ``lookup_attribution_bulk``, grants EXECUTE to ``service_role``, and
  ``NOTIFY pgrst, 'reload schema'``. Verified: per-row + bulk now resolve
  ``primary_foreman='Mark Diaz'`` for WR 90727774 wk 2026-03-01 (was
  Wade Watson). (2) Patched ``billing_audit/schema.sql`` to add the
  ``DROP FUNCTION IF EXISTS`` before the ``lookup_attribution`` create
  and corrected the misleading "adding columns is backward-compatible"
  comment. **New rules:** (1) **A ``CREATE OR REPLACE FUNCTION`` that
  changes ``RETURNS TABLE`` columns is NOT a valid in-place upgrade** —
  it errors against any previously-deployed version with a different
  output shape. Any ``schema.sql`` function whose return columns change
  over time MUST carry a ``DROP FUNCTION IF EXISTS
  <fully-qualified>(argtypes)`` immediately before its ``CREATE``.
  Reviewers MUST flag a return-shape change that lacks a preceding DROP.
  (2) **A Supabase RPC contract is a deployment artifact, not just a repo
  file** — shipping the ``schema.sql`` change is necessary but NOT
  sufficient; the DDL must be applied to the live project AND the
  PostgREST cache reloaded, THEN verified by calling the function and
  asserting the new columns return real data. The Foundation A / Phase 2
  "operator must apply schema.sql + NOTIFY pgrst" gates are load-bearing;
  treat an un-applied attribution schema as a P1 because the code
  degrades SILENTLY (graceful fallback to current foreman — no crash, no
  HOLD, wrong billing attribution). (3) **When attribution looks wrong,
  compare ``attribution_snapshot`` (truth) against the deployed
  function's ``pg_get_function_result`` FIRST** — the snapshot being
  correct while files are wrong points at the read-path RPC shape, not
  the freeze/write path. (4) The clean-filename flip
  (``SUPABASE_HASH_STORE_AUTHORITATIVE=1``) MUST stay deferred until a
  post-fix run is validated (correct per-week claimers + O(chunks)
  attribution HTTP + runtime well under ``TIME_BUDGET_MINUTES``); the
  persistent hash/timestamp tokens in filenames are EXPECTED while E is
  dormant and are NOT part of this bug. No Python code changed — the
  engine was correct; the database was stale. No new pytest tests (the
  fix is a DB migration + a ``schema.sql`` deploy-safety correction;
  existing ``LookupGroupHashTests`` / ``PrefetchAttributionTests`` /
  ``TestLookupAttribution`` already lock the Python contract).
- [2026-05-28 11:59] **Reverted misdiagnosed legacy-hash cross-claimer
  cleanup** (``e68be29`` → ``cc968a8``). The 2026-05-27 16:45 fix
  matched on ``(wr, week, variant)`` and deliberately IGNORED claimer,
  so it would delete a hash-named file just because a clean-named file
  existed for the same WR+week+variant under a (possibly) different
  claimer. That directly violates the Foundation A no-cross-delete
  invariant ([2026-05-20 13:45] rule 2): legitimate different claimers
  for the same WR+week+variant must BOTH survive — the whole point of
  the per-claimer billing_audit file model (track who claimed what per
  week-ending date). The misdiagnosis treated a legitimate-different-
  claimer file as a "wrong-claimer duplicate." **The actual goal is
  met without any new code:** ``delete_old_excel_attachments``
  ([generate_weekly_pdfs.py 3473-3513]) matches prior attachments on
  the FULL identity including claimer (line 3476), and when
  ``SUPABASE_HASH_STORE_AUTHORITATIVE=1`` the E-gated short-circuit at
  line 3494 lets the identity-based replacement loop run — a fresh
  clean file supersedes any prior (token-named or clean) attachment
  for the SAME identity, while different claimers remain distinct
  identities and are preserved. Flipping E + ``RESET_HASH_HISTORY=1``
  achieves the clean-filename goal directly. Reverted:
  ``_is_legacy_hash_named``, ``legacy_hash_cleanup`` param + cleanup
  block in ``cleanup_untracked_sheet_attachments``,
  ``LEGACY_HASH_CLAIMER_CLEANUP_ENABLED`` env var + startup banner +
  workflow ``advanced_options`` parser branch, ``removed_legacy_hash``
  counter + PII marker, and 14 tests in
  ``tests/test_legacy_hash_claimer_cleanup.py``. The
  ``test_security_audit_followup.py`` signature guard reverted in
  lockstep. **New rule — the per-claimer file IS the data model, not
  noise to dedupe across.** A "duplicate" requires identity match
  INCLUDING claimer (``wr, week, variant, claimer``). Any future
  cleanup that crosses claimers MUST consult ``attribution_snapshot``
  to verify the lost claimer has zero frozen rows for that
  week+variant — NEVER a format-only heuristic (hash vs clean).
  **Residual orphans acknowledged:** wrong-claimer files written by
  the broken pre-2026-05-27 read-path RPC (current foreman written
  into the partition slot for historical weeks where the real
  attribution belongs to someone else) linger as different-identity
  orphans after the E + reset regen. Safe cleanup requires the
  attribution-snapshot-aware sweep above. ``pytest tests/`` post-revert
  → **986 passed / 29 skipped / 69 subtests** (was 1000 with the
  now-removed 14 cleanup tests).
- [2026-05-28 12:09] **Sub-project E activated —
  ``SUPABASE_HASH_STORE_AUTHORITATIVE`` flipped to ``'1'`` after the
  runbook gate cleared.** Closes the E re-activation runbook
  (``website/docs/runbook/operations.md`` Step 3) after two prior
  premature-flip incidents — ``67539ec`` on 2026-05-26 (reverted
  ``46cd05d``, PR #234, 372 ``_NO_MATCH`` / ``_Unknown_Foreman``
  clean-named files over real historical attachments) and ``7077471``
  on 2026-05-27 (reverted ``2b890af``, preceded the stale-RPC contract
  discovery). **Preconditions verified at flip time (the audit trail
  for this third — and intended-final — flip):**
  (1) Supabase ``billing_audit`` schema current — 5-column
  ``lookup_attribution`` (returns ``primary_foreman, helper,
  helper_dept, vac_crew, source_run_id``) + ``lookup_attribution_bulk``
  RPC deployed 2026-05-27 via ``DROP FUNCTION IF EXISTS`` + ``CREATE``
  pattern (per the [2026-05-27 14:45] return-shape rule), validated by
  direct call returning real ``frozen_primary='Mark Diaz'`` for
  WR 90727774 wk 2026-03-01 (was silently returning current foreman
  Wade Watson pre-fix).
  (2) ``billing_audit.group_content_hash`` table deployed + populated
  with 2,285 rows by Sub-project E shadow writes since the 2026-05-25
  dormant ship — confirms ``upsert_group_hash`` has been succeeding
  through the dormant period.
  (3) ``attribution_snapshot`` healthy — 143,236 rows, 99.3% valid
  ``frozen_primary``, coverage back to mid-2025.
  (4) Post-revert (``cc968a8``) test suite green — 986 passed / 29
  skipped / 69 subtests.
  **Operator dispatch:** first post-push run MUST be triggered via
  ``workflow_dispatch`` with ``reset_hash_history: true`` for the
  one-time full clean + correct regen (regenerates every group with
  the correct frozen claimer AND populates the durable hash store
  across the active window). Subsequent cron runs use Supabase
  ``group_content_hash`` as the change-detection authority and emit
  clean (token-less) filenames
  ``WR_{wr}_WeekEnding_{MMDDYY}{variant_suffix}.xlsx``.
  ``delete_old_excel_attachments`` supersedes prior same-claimer
  attachments in-place (line 3494's E-gated short-circuit is bypassed
  when authoritative — see [2026-05-25 20:55] rule 1); different
  claimers remain distinct and preserved (Foundation A no-cross-
  delete invariant, reinforced by the [2026-05-28 11:59] revert).
  **Residual orphans (acknowledged, NOT auto-cleaned by this flip):**
  historical wrong-claimer hash-named files written by the pre-fix
  broken RPC. Safe cleanup requires the attribution-snapshot-aware
  sweep documented in [2026-05-28 11:59] — explicitly NOT a
  format-based heuristic.
  **Revert path:** set back to ``'0'`` per operations.md Roll-back
  notes; token-named filenames resume, shadow writes continue, no
  data loss.
  **New rule — three-incident gate for AUTHORITATIVE re-flips.** The
  2026-05-26 and 2026-05-27 premature flips established a hard
  procedural gate: AUTHORITATIVE may only be flipped to ``'1'`` AFTER
  all four preconditions above are verified by direct evidence
  (Supabase MCP table list, RPC sample-call result with real data,
  ``attribution_snapshot`` row count, green test suite). The runbook
  Step 3 enforces this via the human gate (separate commit). Any
  future AUTHORITATIVE re-flip after a revert MUST cite this entry
  and re-verify the four preconditions in the commit message.


[2026-06-02 11:31] Variant-migration orphan attachment: primary superseded by helper

**Incident:** A dual-checkbox helper row with blank `helper_dept` on Run 1
fails helper qualification and falls back to the primary foreman group,
uploading a primary Excel attachment to the TARGET Smartsheet row. After the
operator corrects `helper_dept` and re-runs, the row migrates to the helper
variant — the primary group disappears from `groups` entirely, its identity
is never added to `valid_wr_weeks`, and the stale primary attachment survives
every subsequent run (silent, no exception, double-crediting the primary foreman).

**Root cause:** `cleanup_untracked_sheet_attachments` has no mechanism to detect
a primary attachment whose group disappeared because the row migrated to a
helper variant. The variant-pruning loop only removes OLDER DUPLICATES of each
identity; a lone orphaned primary has no duplicate, so it is never deleted.

**Fix:** Added a "variant-migration orphan gate" in
`cleanup_untracked_sheet_attachments` (generate_weekly_pdfs.py) immediately
before the `identity_groups[ident].append(att)` fallthrough. The gate fires
when ALL three conditions hold:
  1. `variant == 'primary'`
  2. The attachment identity `(wr, week, 'primary', identifier)` is NOT in
     `valid_wr_weeks` (so a legitimately live primary is never touched).
  3. At least one helper-family variant (`helper`, `aep_billable_helper`,
     `reduced_sub_helper`) for the SAME `(wr, week)` IS live in
     `valid_wr_weeks` this run (confirming the migration occurred — prevents
     over-eager deletion when a primary is simply out-of-scope for other
     reasons like WR_FILTER or time-budget cutoff).

Matching attachments are routed into `off_contract_attachments` for
unconditional deletion with Sentry scope tag
`cleanup.reason=variant_migration_orphan`.

**Test:** tests/test_orphaned_primary_attachment.py —
TestOrphanedPrimaryAttachmentOnHelperMigration (5 tests, RED before fix, all
GREEN after). Full suite: 1025 passed, 29 skipped, 0 failures.

**Rule:** Any future change to `cleanup_untracked_sheet_attachments` or
`valid_wr_weeks` population must verify that this gate still fires for the
variant-migration scenario. The confirming-signal condition (helper-family live
for same wr+week) is load-bearing — removing it would cause over-eager
deletion of primaries that are simply not in scope on a given run.

---

## [2026-06-03 11:45] AuthGuard authorization-resolution gate (SEC-04 HIGH-03) + gsd-security-auditor writes to the WRONG SECURITY.md

**Context:** Phase 07 plan 07-04 (milestone-gating SEC-04 audit). Two reusable
rules surfaced.

**1. Client-side auth guards must gate on "authorization resolved", not just
`loading`.** `useAuth` (portal-v2) resolves the *session* (`getSession()` →
`setLoading(false)`) and the *profile/role* (`fetchProfile()`) in TWO separate
async steps. `AuthGuard` previously rendered children once `loading===false`,
so in the window where `user` is set but `profile` is still `null`, a `pending`
user transiently rendered the dashboard shell before the `/pending` redirect
fired (SEC-04 HIGH-03). Data was never exposed (Supabase RLS via
`current_user_role()` returns 0 rows for pending), but the client gate was
wrong.

**Fix:** `const resolving = loading || (Boolean(user) && !profile);` — use
`resolving` for both the effect's early-return and the render guard. A logged-in
user always has a `profiles` row (the `handle_new_user` trigger creates it
atomically), so `user && !profile` reliably means "fetch in flight", not "no
profile". RED→GREEN test in `AuthGuard.test.tsx`. Commit `515837b`.

**Rule:** Any auth/role guard in `portal-v2` must treat `user && !profile` (or
`user && role===null`) as still-resolving and block the protected render — never
pass the guard on `!loading` alone. The DB RLS layer (`current_user_role()`
reads `profiles.role` LIVE per query) is the real data boundary; `getSession()`
is for UI state only (locked decision). HIGH-01 (`getSession` bootstrap) and
HIGH-02 (`profiles_admin_all FOR ALL`) were correctly accepted-with-rationale
for the same reason: no non-admin escalation path exists (non-admins have NO
profiles UPDATE policy) and revoked roles take effect server-side immediately.

**2. `gsd-security-auditor` writes its output to the repo-root `SECURITY.md`,
clobbering the public GitHub vulnerability-disclosure policy.** The subagent has
Write access and defaults to `./SECURITY.md`. During 07-04 it overwrote the
standard `# Security Policy` template with phase-audit tables.

**Rule:** After running `gsd-secure-phase {N}` / spawning `gsd-security-auditor`,
ALWAYS verify `git status` for an unintended root `SECURITY.md` modification and
`git checkout HEAD -- SECURITY.md` if found. The authoritative phase audit doc
is `.planning/phases/{NN}-*/{NN}-SECURITY.md` (authored by the orchestrator) —
the repo-root `SECURITY.md` is the public disclosure policy and must stay
untouched.

---

## [2026-06-03 16:48] Rate CSVs now optional: benign skip replaces recurring Sentry ERROR

**What changed:** `load_contract_rates` and `build_cu_to_group_mapping` in
`generate_weekly_pdfs.py` gained an `os.path.isfile()` existence guard at the
top of each function body, before the `try:/open()` path. When the resolved
path does not exist, the loaders now emit `logging.info("Rate CSV not present,
skipping load: ...")` and a `sentry_add_breadcrumb(level="info")` with
`data={"path_present": False}`, then return the empty dict — no `logging.error`,
no Sentry event. The `except Exception` block is preserved for genuinely
present-but-malformed files, now fingerprinted
`["rate-csv-load-failure", "<fn_name>"]` via `sentry_capture_with_context` with
`_redact_exception_message(e)` in `context_data` (never raw `str(e)`).

**Root cause:** `OLD_RATES_CSV` resolves to its uncommitted default
`'CU List - Corpus North & South.csv'` on every run. The production workflow
pins `OLD_RATES_CSV: ''` in `weekly-excel-generation.yml`, but
`_sanitize_csv_path` treats an empty string as "use the default", so the pin
never disables the load. Both loaders caught the resulting `FileNotFoundError`
into `logging.error(...)`, and because `LoggingIntegration(event_level=ERROR)`
is configured, each `logging.error` fired a Sentry event on every cron run.
Billing blast radius confirmed ZERO: `RATE_CUTOFF_DATE` is pinned empty
(gating `load_rate_versions` and the entire recalc path since 2026-04-24), and
`revert_subcontractor_price` — the only consumer of `load_contract_rates` output
— has no call sites. The net effect was pure operational noise.

**Why NOT to point the default at a tracked CSV:** Semantically incorrect and
against the 2026-04-24 retirement decision. See ledger entry [2026-04-24 14:30].
The uncommitted default and workflow pin are left in place as the documented
one-line revert path.

**Also corrected in this commit:**
- Sentry cron `monitor_config` was stale (`"30 17 * * 1"` / `America/Phoenix` /
  `max_runtime 120`); corrected to the real production weekday schedule
  (`"0 13,15,17,19,21,23,1 * * 1-5"` / `America/Chicago` / `max_runtime 180`
  aligned with `timeout-minutes: 180` in the workflow).
- Added PII-safe run-mode Sentry tags alongside the existing tag block:
  `res_grouping_mode` (fixed enum), `wr_filter_active` (`str(bool(WR_FILTER))` —
  a True/False string, **never the WR list**), `force_generation` (bool).
  `set_tag` bypasses `before_send_log`; WR numbers are row-PII and must never
  appear in tags/contexts/attachments.
- Closed a pre-existing PII leak: `set_context("configuration")` was sending the
  raw `WR_FILTER` list to Sentry (list of WR strings = row-PII; `set_context`
  also bypasses `before_send_log`). Replaced `"wr_filter": WR_FILTER` with
  `"wr_filter_active": bool(WR_FILTER)` + `"wr_filter_count": len(WR_FILTER)`.

**Guardrails preserved:** `_sanitize_csv_path` untouched; `:408` default string
untouched; workflow pinned-empty rate vars untouched (one-line revert intact);
empty-dict return contract preserved; `sentry-sdk>=2.35.0` floor unchanged;
`SENTRY_ENABLE_LOGS` stays OFF by default.

**Tests:** Two new `assertNoLogs(level="ERROR")` tests (TDD RED then GREEN) in
`tests/test_subcontractor_pricing.py` — one per loader — confirm the benign
branch emits no ERROR-level log. Existing `:43`/`:759` `test_missing_file_returns_empty`
tests continue to pass (empty-dict contract preserved). Full suite: all passed.

---

## [2026-06-03 17:21] Deferred Sentry telemetry upgrades: run-level KPIs, failure attachment, structured-log milestone calls

**What changed (research #5/#6/#7):** Three additive Sentry telemetry enhancements wired into `generate_weekly_pdfs.py`'s `main()`:

- **#6 Root-transaction KPIs (success path):** Immediately before `_txn.set_status("ok")`, a loop calls `_build_run_kpis(...)` and sets each numeric KPI on the root Sentry transaction via `_txn.set_data(k, v)`. KPIs include `files_generated`, `groups_total`, `groups_skipped`, `groups_generated`, `groups_uploaded`, `groups_errored`, `duration_seconds`, `sheets_discovered`, `rows_fetched`, `api_calls`, and a derived `groups_per_minute` throughput. All values are `int | float` — no strings — so there is zero risk of PII leakage via `set_data`.

- **#5 Failure-path PII-safe attachment:** Inside `except Exception as e:`, in the `if SENTRY_DSN:` block, before the existing `sentry_capture_with_context(...)` call, `_build_run_context_snapshot(...)` builds a counts/booleans dict (success flag, duration, group counts, error class name only) which is JSON-serialised and attached via `scope.add_attachment(bytes=..., filename="run-context.json", content_type="application/json")`. The entire block is wrapped in `try/except: pass` so a telemetry failure can NEVER mask the real exception.

- **#7 Milestone structured logs:** `_sentry_log_event(...)` is called at two non-PII checkpoints only — run start (after `_txn` init, passing `test_mode` and `github_actions` booleans) and run complete (after the #6 KPI loop, passing aggregate counts). No calls inside per-group loops. The helper no-ops unless `SENTRY_ENABLE_LOGS=true` (default OFF in production).

**PII-safety enforcement via TDD:** `add_attachment` and `sentry_sdk.logger` both bypass `before_send_log`. To make the PII guarantee test-enforced rather than review-only, three pure/guarded helpers were written TDD-style (RED → GREEN, 16 new assertions in `TestSentryTelemetryHelpers`):
- `_build_run_kpis(...)` — pure; tests assert every value is `int | float` (no strings = no PII leakage path).
- `_build_run_context_snapshot(...)` — pure; tests assert no WR token, no `$`, no foreman name in serialised JSON; values are counts/booleans/None/error class name only.
- `_sentry_log_event(level, message, **attributes)` — guarded wrapper; tests assert no-op without `SENTRY_DSN`, no-op without `sentry_sdk.logger` attr (older SDK), swallows all internal errors (never propagates).

**sentry-sdk floor bump:** `requirements.txt` raised from `sentry-sdk>=2.35.0` to `sentry-sdk>=2.54.0`. The `sentry_sdk.logger` structured-log API was stabilised in 2.54.0. Strictly 2.x — no 3.x APIs (`set_attribute`, OTel) used. `set_measurement` intentionally NOT used (deprecated since 2.28.0); `_txn.set_data` is the correct 2.x pattern.

**Guardrails preserved:** Additive only — billing/grouping/hashing/filename/upload paths untouched; `_sanitize_csv_path` untouched; plan-01 edits untouched; `SENTRY_ENABLE_LOGS` default stays `false` (milestone logs are no-ops in prod until an operator explicitly enables them). `if _txn:` guard preserved on all transaction calls.

**Tests:** Full suite 1043 passed, 0 failed; `python -m py_compile generate_weekly_pdfs.py` clean.

---

## [2026-06-05 16:15] Sentry Crons monitor timezone MUST be UTC (GitHub Actions crons are UTC) — fixes perpetual false "missed check-in"

**Root cause (Sentry issue `GENERATE-WEEKLY-EXCEL-6V`, 130 events, last seen
the day of this fix):** the Sentry Crons `monitor_config` in
`_sentry_cron_checkin_start()` carried `"timezone": "America/Chicago"` while its
`schedule` value (`0 13,15,17,19,21,23,1 * * 1-5`) is the **weekday GitHub
Actions cron** — and GitHub Actions evaluates every `schedule:` cron in **UTC**.
Labeling the monitor `America/Chicago` made Sentry expect each check-in 5–6h
later than the job actually checks in, so every weekday slot was flagged as a
missed check-in (an `outage`-category issue). The earlier PR #261 correction
(Phoenix → Chicago) fixed the schedule string + max_runtime but introduced this
tz mismatch; the correct value is **UTC**.

**RULE (operative, locked):** The Sentry cron `monitor_config.timezone` MUST
equal the timezone GitHub Actions uses to evaluate the workflow `schedule:`
cron — which is always **UTC**. Never set it to a local zone
(`America/Chicago`, `America/Phoenix`) just because the *job's* internal
`TZ` env is Central. The monitor `schedule.value` MUST also stay byte-for-byte
identical to the weekday cron in `.github/workflows/weekly-excel-generation.yml`.

**What changed (`generate_weekly_pdfs.py`):** Extracted a pure, testable
`_build_cron_monitor_config()` helper (+ module constant `_CRON_MONITOR_SCHEDULE`)
out of `_sentry_cron_checkin_start()`; flipped `timezone` `America/Chicago` → `UTC`.
Behavior otherwise identical (`checkin_margin:5`, `max_runtime:180`,
`failure_issue_threshold:1`, `recovery_threshold:1`). No billing/grouping/upload
path touched — monitoring config only. `-6V` left unresolved in Sentry; it
auto-recovers (`recovery_threshold:1`) on the first correctly-timed check-in
after deploy.

**Tests (TDD RED→GREEN):** New `tests/test_cron_monitor_config.py` (5 tests):
asserts `timezone == "UTC"` and never a local zone (the regression guard), the
schedule/runtime shape, AND that `_CRON_MONITOR_SCHEDULE` matches the workflow's
weekday cron parsed live from `weekly-excel-generation.yml` (locks out the whole
drift class). RED confirmed on `America/Chicago` first, then GREEN. Full suite:
1048 passed, 29 skipped, 0 failed; `py_compile` clean.

**Sentry hygiene (same session, 2026-06-05):** Triaged all 61 unresolved issues
across `generate-weekly-excel` + `generate-weekly-excel-frontend` (the two
deleted Express projects had 0). Resolved 34 verified-fixed (rates-CSV `-72`
post-PR#261; the 29 `KeyError 'refId'` issues — that code path no longer exists
in `get_all_source_rows`, all stopped 2026-03-18; 4 frontend errors from the
broken 2026-04-18 deploy: `USE_MOCK`/`DOCS_URL`/React-queue). Ignored 27 transient
infra / third-party (Smartsheet `ApiError 0/1278/4000/503`, `JSONDecodeError`;
3 `str+None` TypeErrors raised *inside the Smartsheet SDK's* error formatter,
`handled:yes`; 2 frontend third-party — a browser-extension `Range` error and a
`getItem` null inside Sentry's own `feedback/instrument.js`).

---

[2026-06-08 10:45] **Pin transport-critical SDK dependencies with an upper bound — smartsheet-python-sdk 4.0.0 import crash**

**What:** Pinned `smartsheet-python-sdk` to `>=3.1.0,<4.0.0` in `requirements.txt`. The
previous spec (`>=3.1.0`, no ceiling) caused GitHub Actions to silently pull the breaking
4.0.0 major on its publish day (2026-06-08), crashing `generate_weekly_pdfs.py` at line 28
(`import smartsheet.exceptions as ss_exc`) before any billing work could run.

**Why:** SDK 4.0.0 is a backward-incompatible major that removed `smartsheet.exceptions`
entirely, removed `Folders.get_folder` and `Folders.list_folders`, removed the `Templates`
endpoint, and changed pagination — all surfaces the billing pipeline depends on. CI runs a
fresh `pip install -r requirements.txt` on every workflow execution; an open `>=` lower-bound
on a rapidly evolving SDK is equivalent to an unpinned dependency in a fresh-install
environment.

**Root cause pattern:** A transport-critical library (one whose import or API surfaces are
called unconditionally at the top of the production script) was given only a lower bound in
`requirements.txt`. When the library published a breaking major, the next CI run resolved
to that major, crashing before a single row was processed. The failure was silent until the
scheduled run fired — no local developer environment surfaced the issue.

**Rule established:** Transport-critical / production-pipeline dependencies — any package
whose import or API is called unconditionally by `generate_weekly_pdfs.py` or
`audit_billing_changes.py` — MUST carry an upper bound that excludes the next major version.
Format: `>=CURRENT_MAJOR.MINOR.PATCH,<NEXT_MAJOR.0.0`. A deliberate major-version migration
(e.g., adopting smartsheet-python-sdk 4.x) is a separate planned effort with explicit
compatibility testing — it must never arrive as a transitive auto-upgrade on publish day.
Apply this rule to: `smartsheet-python-sdk`, `openpyxl`, `sentry-sdk`, `supabase`, and any
future SDK added as a direct import in the billing engine.

**Fix:** Single-line change in `requirements.txt`; zero change to `generate_weekly_pdfs.py`,
`ss_exc` usage, or the SDK retry-exception re-export workaround. Fully reversible by removing
`,<4.0.0`. Dry-run confirmed `smartsheet-python-sdk 3.7.2` resolves correctly post-pin.

---

[2026-06-09 00:10] **VAC-crew completed units go ONLY to the VAC crew, never the primary/helper foreman — cross-sheet, UNIT-level de-duplication**

**What:** A unit is credited to the VAC crew when `Vac Crew Completed Unit?` is checked (with a
named `VAC Crew Helping?` crew) AND `Units Completed?` is checked. Such a unit is excluded from
BOTH the primary-foreman (`_User_`) AND helping-foreman (`_Helper_`) sheets — line items AND
totals — with NO duplication. This is the same dominance the dual-checkbox helper rule already
has over the primary. The fix is a UNIT-LEVEL cross-row reconciliation pre-pass in
`group_source_rows` plus a new `_PII_LOG_MARKERS` entry (`"EXCLUDING from foreman/helper"`).
NO change to the detection conjunction, the acceptance gates, or the billing-audit attribution
machinery (see "Reverted" below).

**Why:** Operator reported the same unit (WR 90922617, Point 11 `ANC-DSC-16-96-D1`, Point 11
`PLA-HDIG`, Point 15 `ANC-`) appearing on BOTH the foreman's `_User_` Excel and Hugo Garcia's
`_VacCrew_` Excel — double-crediting/double-billing.

**Root cause:** MULTI-SHEET DUPLICATION. A WR spans multiple source sheets — a
foreman/original-contract sheet (no VAC columns) AND a VAC-crew sheet (VAC columns). The SAME
physical unit exists as TWO rows; only the VAC-sheet copy carries the VAC claim, so the foreman
copy (no VAC signal on its row) routes to the foreman and the unit appears on both files. The
clean one-row→one-group `if/else` routing in `group_source_rows` is correct but irrelevant —
the duplication is across two rows on two sheets, so no row-local check can catch it.

**Rule established:** VAC-crew exclusion is PER-UNIT, keyed on `(WR, week_ending, Pole #, CU)`
— NOT per-pole. A pre-pass over all rows collects the `(wr, week, point, cu)` of every row
flagged `__is_vac_crew`; in the per-row loop, any NON-VAC row whose unit identity is in that set
is dropped (`continue`) from ALL non-VAC variants (primary, helper, subcontractor). Per-unit,
not per-pole, so the foreman's OTHER units on the same pole are retained (a pole-level dedup
would wrongly strip the foreman's legitimately-completed units). Column identity uses the
codebase convention: `CU`/`Billable Unit Code` and `Pole #`/`Point #`/`Point Number` (verified
against `_validate_single_sheet` synonyms; never invent names). The dual-checkbox helper rule is
untouched; VAC dominates both primary and helper.

**Operator decision — VAC billing requires `Units Completed?`:** When the VAC crew completes a
unit, `Units Completed?` is also checked in practice (the production `_VacCrew_` files only exist
because the pre-existing detection required it). So VAC billing keeps requiring `Units
Completed?` — same as the foreman/helper. This keeps the billing-audit attribution subsystem's
"billable = Units Completed? checked" invariant intact across ALL its stages (bulk prefetch,
claimer-freeze prepass, freeze-write) with zero changes there.

**Reverted (do NOT reintroduce without re-opening the attribution work):** An earlier attempt
ALSO widened admission so VAC claims billed even when `Units Completed?` was unchecked (a
`_is_vac_crew_excluded_row` predicate, detection de-coupled from units, and BOTH acceptance
gates + the claimer-freeze prepass widened). Codex review correctly showed this required
propagating the widened "billable" definition through the entire Subproject-C attribution chain
(Phase-02 bulk prefetch `_prefetch_pairs`, `_vac_crew_claimer_map` resolve, and the
`freeze_row` write path / `billing_audit.writer`) or those rows would silently miss
frozen-claimer / HOLD attribution. Per the operator decision above, the unchecked case does not
occur, so the whole widening was REVERTED rather than chased through the billing-audit internals
— keeping the change surgical (dedup + log marker only) and the attribution subsystem untouched.

**Fix:** `generate_weekly_pdfs.py` (cross-row reconciliation pre-pass + per-row `continue`; the
`EXCLUDING from foreman/helper` log marker added to `_PII_LOG_MARKERS`), new TDD
`tests/test_vac_crew_exclusion_leak.py`, and a sanitizer test in
`tests/test_sentry_log_sanitizer.py`. Verified by a read-only `SKIP_UPLOAD` dry run against real
WR 90922617 (week 060726): Chris's `_User_` total dropped $30,023.63→$26,098.52 (exactly the 3
VAC-claimed units, −$3,925.11), Hugo's `_VacCrew_` total unchanged ($11,419.29), zero
cross-sheet duplicates, all 26 of Chris's own Point 11 units retained. Suite 1055 passed / 0
failures; `py_compile` OK. Hash key NOT shortened (dropping a leaked row changes the affected
`_User_`/`_VacCrew_` group hashes → expected regeneration, not a regression). No `@cell`;
`safe_merge_cells`/`oddFooter`/`PARALLEL_WORKERS` untouched. PR #274.

---

## [2026-06-10 01:20] SIGTERM must unwind through main()'s finally — fixes Sentry "timeout check-in detected" (PYTHON-6V)

**Root cause (Sentry issue `PYTHON-6V`, GitHub issue #127):** when GitHub
Actions cancels a run or hits `timeout-minutes`, it delivers SIGINT → SIGTERM
→ SIGKILL. Python's **default SIGTERM action terminates the process without
unwinding the stack**, so the terminal Sentry cron check-in in `main()`'s
`finally` never fired — the `in_progress` check-in stayed open until Sentry
flagged "a timeout check-in was detected". Two secondary defects compounded
it: (1) the terminal status logic (`_cron_ok = '_groups_errored' not in dir()
or _groups_errored == 0`) closed interrupted/early-failed sessions as **OK**,
and (2) the terminal check-in sat in the SDK queue until the trailing
`flush(timeout=10)` — longer than the runner's SIGTERM→SIGKILL grace window.

**RULE (operative):** Any process that opens a Sentry cron `in_progress`
check-in MUST (a) install a SIGTERM handler that raises `SystemExit` so
`finally`-based cleanup runs (`_install_sigterm_finalizer()`), (b) compute the
terminal status with `_resolve_cron_final_status(session_failed,
exc_in_flight, groups_errored)` — handled failures set `_session_failed`,
propagating `SystemExit`/`KeyboardInterrupt` are detected via
`sys.exc_info()` inside `finally` — and (c) `sentry_sdk.flush(timeout=5)`
immediately after the terminal `capture_checkin` so it escapes the
termination grace window. Never close the monitor OK on an interrupted
session.

**Tests:** new `tests/test_cron_checkin_lifecycle.py` (7 tests: status
matrix + SIGTERM-raises-SystemExit + finally-unwind contract). Manually
verified: sending a real SIGTERM to the process → `finally` runs, exit
code 143. Full suite 1091 passed / 0 failed; `py_compile` clean.
Monitoring-only change — no billing/grouping/upload path touched.
