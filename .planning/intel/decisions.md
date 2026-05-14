# Decisions

Synthesized from classified ADR-equivalent rules in the ingest set.

No source document is a canonical ADR (`type: ADR`), but the
`CLAUDE.md` Living Ledger contains ~30 dated entries that bind future
behavior with explicit "New rule:" clauses. Per the classifier's
note, those entries are extracted here as **operative locked rules**.
Two SPECs also contribute decisions; they are recorded for
completeness with `locked: false`.

Each entry preserves its date. Downstream consumers (the Subcontractor
Rate Logic phase, in particular) MUST respect every entry below or
surface a conflict.

---

## ADR-equivalent rules from `CLAUDE.md` Living Ledger

> source: `CLAUDE.md` (Living Ledger section)
> status: locked (operative — the ledger is append-only and each
> entry's "New rule:" clause governs future code changes)

### [2026-04-17 15:26] Initialize Claude Code workspace layout

- scope: `.claude/rules/`, `.claude/commands/`, `CLAUDE.md`
- decision: `.claude/rules/smartsheet-python-optimization.md`
  applies to **new scripts only**; `generate_weekly_pdfs.py`
  stays on `openpyxl`. Validation command remains
  `pytest tests/ -v`; `uv` migration is aspirational.

### [2026-04-20 00:00] Sentry release naming guardrail (slash-free)

- scope: every GitHub Actions workflow that creates a Sentry
  release or sets `SENTRY_RELEASE`
- decision: compose `SENTRY_RELEASE` as
  `${GITHUB_REPOSITORY//\//-}@${GITHUB_SHA}` via a "Compute
  Sentry release" step and export to `$GITHUB_ENV`. **Do not**
  use the raw `${{ github.repository }}@${{ github.sha }}` form
  — `sentry-cli releases new` fails on slashes.

### [2026-04-20 12:00] `SENTRY_ENABLE_LOGS` gate + `before_send_log` sanitizer

- scope: `generate_weekly_pdfs.py`, any new Python script that
  calls `sentry_sdk.init(...)`
- decision: route `enable_logs` through the `SENTRY_ENABLE_LOGS`
  env var (default `false`) AND register `before_send_log` that
  drops log records matching `_PII_LOG_MARKERS`. Never
  hard-code `enable_logs=True`. Adding a new INFO log that
  embeds row content requires either stripping PII or extending
  `_PII_LOG_MARKERS` in the same PR.
- requires: `sentry-sdk>=2.35.0`.
- preferred helper: `sentry_capture_message_with_context(...)`
  over `sentry_sdk.logger.*`.

### [2026-04-21 22:35] VAC crew CU-direct fallback + WARNING summary

- scope: `recalculate_row_price()`, `_fetch_and_process_sheet`
  per-sheet rate-recalc summary
- decision: on the "group not in `rates_dict`" branch, fall back
  to a direct CU-code lookup in `rates_dict`. On miss, log
  WARNING. Track `{recalculated, skipped, fallback_applied}`
  counters per sheet and emit a per-sheet WARNING summary when
  skips occurred. **Do NOT** change the cutoff column from
  `Snapshot Date` to `Weekly Reference Logged Date` — the
  business rule is snapshot-keyed. **Do NOT** promote recalc
  fall-through logs back to DEBUG without an alternate
  visibility path.

### [2026-04-22 00:00] Hash key MUST capture per-row VAC crew fields

- scope: `calculate_data_hash()` for the `vac_crew` variant,
  `DISCOVERY_CACHE_VERSION`
- decision: include `__vac_crew_name`, `__vac_crew_dept`,
  `__vac_crew_job` in per-row `row_str` (scoped to `vac_crew`
  variant). Helper metadata stays on `sorted_rows[0]` because
  helper groups partition by foreman. When a group key does
  NOT include a disambiguating identifier, the corresponding
  hash MUST capture per-row field changes at the row level —
  a set-based `meta_parts` aggregation is a two-way
  silent-skip trap (dedup + delimiter collision).
- corollary: bump `DISCOVERY_CACHE_VERSION` whenever column
  mappings of already-cached sheets need invalidation.
- corollary: ledger entries and comments must refer to
  function / group-key / env-var names — never hard-coded line
  numbers.

### [2026-04-22 16:05] Attachment pre-fetch sub-budget + non-blocking executor shutdown

- scope: target-row attachment pre-fetch phase in
  `_fetch_and_process_sheet`'s entry path
- decision: introduce `ATTACHMENT_PREFETCH_MAX_MINUTES`
  (default 10) and `ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC`
  (default 45). Pre-flight skip if remaining session budget
  is < `ATTACHMENT_PREFETCH_MAX_MINUTES` +
  `ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN` (default 2).
  Time-bound on `as_completed(futures, timeout=...)` — NOT on
  `future.result(timeout=...)`. Use **explicit**
  `executor.shutdown(wait=False, cancel_futures=True)`; **do
  NOT** use `with ThreadPoolExecutor(...)` here. Count
  `cancelled` and `still_running` separately.
- general rule: any pre-processing phase sharing
  `TIME_BUDGET_MINUTES` with the main loop MUST have its own
  sub-budget far smaller than the session budget.
- corollary: any consumer that depends on the pre-fetch cache
  must accept `cached_attachments=None` and fall back to
  per-row lookup.
- daemon-worker note: copying this pattern onto an executor
  whose workers produce results the main flow depends on
  (generation, upload, hash_history) is **forbidden** — the
  atexit-detach trifecta is safe ONLY for an
  optimization-with-always-available-fallback.

### [2026-04-22 17:10] Time-budget proportions

- scope: `.github/workflows/weekly-excel-generation.yml`
- decision: `TIME_BUDGET_MINUTES=180`, `timeout-minutes=195`.
  `timeout-minutes` MUST always exceed `TIME_BUDGET_MINUTES`
  by the length of the cache-save + artifact-upload tail
  (~10–15 min). Never raise `TIME_BUDGET_MINUTES` without
  raising `timeout-minutes` by at least as much.

### [2026-04-22 18:30] Fuzzy column-title fallback for VAC crew

- scope: `_validate_single_sheet()`,
  `_normalize_column_title_for_vac_crew()`,
  `_vac_crew_fuzzy_canonicals`
- decision: after the exact-match synonyms loop, run a fuzzy
  fallback pass scoped to VAC crew canonical names only.
  Already-mapped column IDs are excluded so fuzzy cannot
  clobber exact. Emit WARNING on fuzzy match so operators can
  promote it to an explicit synonym. **Do NOT** broaden fuzzy
  matching to primary/helper columns without a documented
  production-incident driver. Bump
  `DISCOVERY_CACHE_VERSION` (here 3 → 4) when a bug could
  leave existing caches with incorrect mappings.

### [2026-04-23 00:00] `RATE_RECALC_WEEKLY_FALLBACK` env var (now LEGACY)

- scope: `_resolve_rate_recalc_cutoff_date()`,
  `_fetch_and_process_sheet`
- decision: introduce env var (default `true`) that enables a
  Weekly-Ref-Date fallback when Snapshot Date is blank or
  unparseable. Snapshot Date populated AND pre-cutoff still
  returns `None` — the fallback does NOT override the
  snapshot-keyed business rule. Add `fallback_applied`
  counter and a neutral "0 recalculated, 0 skipped (N via
  fallback)" log branch.
- general rule: any new pre-`has_price` transformation tied
  to a business cutoff MUST degrade gracefully when its
  driving column is blank.
- general rule: when an env var's default changes observable
  production behavior, the startup banner MUST print the
  resolved state.

### [2026-04-23 12:00] Security-tightening audit (path traversal, PII)

- scope: `generate_weekly_pdfs.py`,
  `_RE_SANITIZE_HELPER_NAME`,
  `_redact_exception_message(exc, *, max_len=240)`,
  `_valid_cached_sheets` filter
- decision (1) — Path traversal: any user-controllable string
  flowing into `os.path.join` / `workbook.save` / `open` MUST
  pass through `_RE_SANITIZE_HELPER_NAME.sub('_', wr_num)[:50]`
  at **every derivation site** (not just final assembly). For
  numeric WR#s this is a no-op.
- decision (2) — Sentry PII: NEVER pass raw `str(exc)` into
  `sentry_capture_with_context(...)`'s `context_data` payload.
  Use `_redact_exception_message(e)` (strips
  `WR=<redacted>`, `$<redacted>`, `<email>`, and
  `customer=`/`foreman=`/`dept=`/`snapshot=`/`cu=`/`job=`
  key-value pairs; prefixes the exception class for grouping
  stability; collapses whitespace; truncates to 240 chars).
  `event['contexts']` bypasses `before_send_log`.
- decision (3) — Cache schema guard: any JSON file loaded
  into a typed shape MUST guard each entry with
  `isinstance(...)` checks before trusting fields. Corrupt
  caches WARN and drop bad entries, never crash the run.

### [2026-04-23 18:05] PR #176 round-2 follow-ups

- scope: discovery cache schema filter,
  `_recalc_note` branch keys
- decision: `_valid_cached_sheets` also requires
  `isinstance(s.get('name'), str)`. All-dropped case (filter
  empties non-empty raw input) raises `ValueError` to force
  full rediscovery — empty success path is a silent-no-op
  trap. Operator-facing "why was this dropped?" notes MUST
  key on the parsed/derived state (the same helper used by
  the business-logic gate), not on raw cell truthiness.

### [2026-04-23 18:25] WR# sanitization at every consumer

- scope: `create_target_sheet_map()`, the upload-task
  builder, `delete_old_excel_attachments()`,
  `_has_existing_week_attachment()`,
  `history_key` derivation
- decision: sanitize target_map keys at populate time using
  the same `_RE_SANITIZE_HELPER_NAME.sub('_', wr_num)[:50]`
  expression. Build the upload task from the main-loop
  sanitized `wr_num` instead of the raw `generate_excel`
  return tuple. **Every downstream consumer** of a sanitized
  identifier MUST consume the sanitized value — partial
  sanitization is a silent split-brain. `_RE_SANITIZE_HELPER_NAME`
  is idempotent, so applying it at both producer and consumer
  is safe.

### [2026-04-23 18:50] PR #176 round-3 (note-gate + counter visibility + type hint)

- scope: `_weekly_would_trigger_fallback()`,
  per-sheet rate-recalc summary,
  `_redact_exception_message` type annotation
- decision (1): the "set `RATE_RECALC_WEEKLY_FALLBACK=1` to
  rescue this row" operator note MUST gate on whether the
  env var would actually change this row's outcome (use
  `_weekly_would_trigger_fallback`). False leads waste
  on-call time.
- decision (2): per-sheet summary log gains an
  `elif fallback_applied:` branch so the counter is never
  write-only.
- decision (3): `_redact_exception_message`'s parameter is
  annotated `BaseException | None` to match what the function
  accepts.
- general rule: any counter that tracks an independent
  code-path dimension MUST have a log branch that fires on
  that dimension alone.

### [2026-04-23 19:15] PR #176 round-4 (Snapshot column gate, target_map collisions)

- scope: `sheet_has_snapshot_date_column` gate,
  `target_map` collision tracking
- decision (1): weekly-fallback activation gated on
  `'Snapshot Date' in column_mapping` — sheets that never
  map Snapshot Date preserve their pre-fix "no recalc when
  Snapshot is absent" behavior.
- decision (2): `target_map` tracks the raw value that first
  produced each sanitized key; on collision, log a WARNING
  with BOTH raw values for operator audit.
- general rule: "rescue" fallbacks tied to a column's absence
  MUST be gated on the column actually being mapped, not on
  the row's field being falsy. Lossy-sanitizer dict keys
  MUST surface collisions, not silently overwrite.

### [2026-04-23 19:40] PR #176 round-5 (broader `_RE_REDACT_WR`)

- scope: `_RE_REDACT_WR` regex inside
  `_redact_exception_message`
- decision: pattern is
  `\bWR(?![a-zA-Z])\s*[#:=]?\s*[\w/\\\-.]+`. Negative
  lookahead prevents over-matching `WRITE`/`WRAP`. Identifier
  body accepts non-delimiter chars (word + `/ \ . -`) so
  alphanumeric or path-traversal tokens are captured in
  full.
- general rule: identifier-redaction regexes MUST not assume
  identifier shape; the body should accept any non-delimiter
  character and stop at a clear terminator.

### [2026-04-23 20:10] PR #176 round-6 (target_map quarantine + fast-path gate)

- scope: `_quarantined_keys` set on `target_map`, discovery
  cache fresh-path gate
- decision (1): on `target_map` sanitized-key collision,
  `del target_map[key]` AND add to `_quarantined_keys`.
  Downstream lookups for ambiguous keys return False; the
  existing "not found in target sheet" warning fires for each
  raw WR. A loud not-found is strictly safer than silent
  wrong-row upload.
- decision (2): fresh-cache fast path gate also requires
  `not _partial_cache_corruption`. Any schema-filter drop
  forces incremental mode.
- general rule: collision-detection guards that log-only
  are advisory; if the ambiguous key drives side effects,
  remove/reject the key (quarantine set).

### [2026-04-23 21:00] PR #176 round-7 (filename parser + source-WR collision quarantine)

- scope: `build_group_identity()`, source-side WR collision
  pre-scan in the main group loop
- decision (1): `build_group_identity` locates `WeekEnding`
  via `parts.index(...)` and joins `parts[1:we_idx]` for the
  WR token. Variant-marker detection (`Helper`/`VacCrew`/
  `User`) is scoped to the post-`WeekEnding` tail.
- decision (2): pre-scan `groups.items()` and build a
  `defaultdict(set)` keyed by `(sanitized_wr, week, variant)`
  to flag groups whose sanitized key is shared across raw
  WRs. Quarantined groups skip with WARNING before touching
  `history_key`, `target_map`, or `generate_excel`.
  **(Superseded by [2026-04-23 21:00]-round-9 below.)**
- general rule: filename parsers MUST locate markers by
  `list.index(...)` not by fixed position, or sanitized
  components silently break attachment identity.

### [2026-04-23 21:00] PR #176 round-9 (broaden source-WR collision key)

- scope: source-side WR collision quarantine key
- decision: broaden the source-side quarantine key from
  `(sanitized_wr, week, variant)` to **the sanitized WR
  alone**. Cross-week and cross-variant collisions also
  count. Realistic numeric WR#s cannot collide so production
  remains zero-impact.
- general rule: when a sanitizer collapses a keyspace and
  the sanitized value drives downstream routing,
  collision-detection MUST be keyed on the sanitized value
  alone — not on any tuple that includes context the router
  doesn't use.
- supersedes: [2026-04-23 21:00] round-7 source-collision
  key tuple.

### [2026-04-24 10:50] Supabase PostgREST permanent-error classification + run-global kill switch

- scope: `billing_audit/client.py`,
  `_classify_postgrest_error()`,
  `_PGRST_GLOBAL_KILL_CODES`,
  `_disable_for_run()`
- decision: classify by `APIError.code` (not class).
  Codes starting `PGRST1`/`PGRST2`/`PGRST3` and stringified
  HTTP 4xx are permanent (bail after first attempt). Codes
  in `_PGRST_GLOBAL_KILL_CODES` (`PGRST106`, `PGRST301`,
  `PGRST302`) additionally flip a run-global kill switch.
  Permanent-error WARNINGs name the concrete fix (Supabase
  Dashboard path or env-var).
  `reset_cache_for_tests` MUST clear
  `_global_disable_reason` and `_global_disable_logged`.
- general rule: when wrapping a library exception type
  whose `code` is multi-source, classify by metadata, not
  by class. Integration-wide failures need a run-global
  kill switch, not just per-op circuit breakers.

### [2026-04-24 11:30] `RATE_RECALC_SKIP_ORIGINAL_CONTRACT` guard

- scope: `_fetch_and_process_sheet`,
  `_FOLDER_DISCOVERED_ORIG_IDS`
- decision: new env var (default `true`) that, combined with
  `RATE_CUTOFF_DATE` set, skips CSV-side recalc for any
  sheet in `ORIGINAL_CONTRACT_FOLDER_IDS`
  (`7644752003786628`, `8815193070299012`) that is not
  already excluded as a subcontractor sheet. One 🛡️ info log
  per skipped sheet; the row-level gate adds
  `and not _skip_recalc_original_contract`.
- general rule: when an external system starts emitting
  authoritative values for a column we also compute, add a
  per-sheet/per-scope guard that short-circuits the local
  computation. Sequential double-writes on the same field
  are a silent-corruption trap.

### [2026-04-24 14:30] CSV-side rate recalc retired at workflow layer (LEGACY)

- scope: `.github/workflows/weekly-excel-generation.yml`,
  startup-banner warning in `generate_weekly_pdfs.py`,
  `website/docs/reference/environment.md` "Rate contract
  versioning" admonition
- decision: hardcode `RATE_CUTOFF_DATE: ''`,
  `NEW_RATES_CSV: ''`, `OLD_RATES_CSV: ''` in the weekly
  workflow with a prominent LEGACY comment. Any repo
  Variable that re-introduces a value is ignored.
  `generate_weekly_pdfs.py` emits a startup WARNING whenever
  `RATE_CUTOFF_DATE` is detected, pointing operators at this
  ledger entry.
- retention policy: every recalc helper
  (`recalculate_row_price`, `_resolve_rate_recalc_cutoff_date`,
  `build_cu_to_group_mapping`, `load_rate_versions`) and
  the `RATE_RECALC_SKIP_ORIGINAL_CONTRACT` guard are
  retained so re-enablement is a one-line workflow revert.
- un-retire pre-condition: future un-retire MUST be paired
  with explicit verification that the rows being re-priced
  are NOT already Smartsheet-priced for the same column.
- general rule: workflow pinning is enforceable through
  git history; repo-Variable defaults are not. Always emit
  a runtime WARNING when a retired env var is detected.

### [2026-04-25 12:00] PostgREST SQLSTATE classification

- scope: `billing_audit/client.py`,
  `_classify_postgrest_error()`,
  `_PG_SQLSTATE_PERMANENT_PREFIXES`
- decision: add `_PG_SQLSTATE_PERMANENT_PREFIXES = ("22",
  "23", "42")` with a length-gated check
  (`len(code) == 5`). `42P01` (undefined_table) and `42703`
  (undefined_column) are permanent. SQLSTATE classes
  `08`/`40`/`53`/`57` MUST remain transient.
- decision (companion): any new Supabase table or column
  the pipeline reads/writes MUST be defined in
  `billing_audit/schema.sql` in the same PR that adds the
  Python code. Reviewers MUST block merges that add
  `client.schema(...).table(...)` references against a
  column not present in `schema.sql`.
- general rule: when a retry-classification helper accepts
  an exception type whose `code` field is multi-source,
  every documented source MUST have explicit handling AND
  a regression test.

### [2026-04-25 14:00] `freeze_row` parallelization

- scope: per-row `freeze_row()` loop in the main group
  processing block of `generate_weekly_pdfs.py`,
  `billing_audit/client.py` `with_retry` inter-attempt
  re-check, `tests/validate_production_safety.py`
- decision: wrap the `freeze_row` loop in
  `ThreadPoolExecutor(max_workers=min(PARALLEL_WORKERS,
  len(group_rows)))`. Cap 8. Single-row groups skip the
  executor. `f.result()` is wrapped in
  `try/except Exception` with `logging.exception` and the
  sanitized `__row_id`. `_counters` writes go through
  `_bump_counter` under `_counters_lock`. The inter-attempt
  re-check on `_open_circuits` / `_global_disable_reason`
  bounds worst-case retry storm to one extra round per
  in-flight worker.
- general rule: any new per-row I/O call inside the main
  group loop MUST be parallelized via
  `ThreadPoolExecutor(max_workers=min(PARALLEL_WORKERS,
  len(group_rows)))` from the start; serial-by-default is
  a P0 latency trap.
- corollary: ThreadPoolExecutor invocations of fail-safe
  writers MUST still wrap `f.result()` in
  `try/except Exception` with `logging.exception`.
- corollary: when extending the per-group billing_audit
  block, also bump the
  `validate_per_group_try_catches_all` window cap in
  `tests/validate_production_safety.py`.

---

## SPEC-level decisions

### Subcontractor pricing: keep SmartSheet pricing as-is

- source: `.github/instructions/subcontractor-pricing-folder-discovery.instructions.md`
- decision: subcontractor (Arrowhead) sheets always keep their
  SmartSheet pricing as-is — no rate recalculation, regardless
  of `RATE_CUTOFF_DATE`. `revert_subcontractor_price()` exists
  but is **not called** during row processing.
- precondition for change: a future subcontractor cutoff date
  and subcontractor new-rate enablement.
- function policy:
  - `discover_folder_sheets()` — new function, modify with care
  - `load_contract_rates()` — do not touch
  - `revert_subcontractor_price()` — do not call
  - `discover_source_sheets()` — append IDs only
  - `get_all_source_rows()` — do not touch
- env-var defaults:
  - `SUBCONTRACTOR_FOLDER_IDS = 4232010517505924,2588197684307844`
  - `ORIGINAL_CONTRACT_FOLDER_IDS = 7644752003786628,8815193070299012`
  - `SUBCONTRACTOR_SHEET_IDS = (empty; folder-discovered IDs
    are merged in at runtime)`

### Folder-based discovery as the primary path

- source: `.github/instructions/subcontractor-pricing-folder-discovery.instructions.md`
- decision: subcontractor and original-contract sheets live in
  stable Smartsheet folders. New sheets added to those folders
  are auto-picked up via `discover_folder_sheets()`. Manual
  `SUBCONTRACTOR_SHEET_IDS` overrides are still supported but
  not required.
- testing: mock `client.Folders.get_folder()`; do not call the
  real Smartsheet API.

### Identity-mismatch (`None` vs `''`) compatibility fix

- source: `.github/instructions/subcontractor-pricing-folder-discovery.instructions.md`
  (Hash Change Detection Fixes, Bug 1)
- decision: all identity comparisons in
  `delete_old_excel_attachments()` and
  `_has_existing_week_attachment()` use
  `(ident_identifier or '') == (identifier or '')`.

### Hash extended-mode field coverage

- source: `.github/instructions/subcontractor-pricing-folder-discovery.instructions.md`
  (Hash Change Detection Fixes, Bug 2)
- decision: `calculate_data_hash()` extended mode includes
  Customer Name, Job #, Work Order #, CU Description, Unit of
  Measure, and Area.

### `hash_history.json` persistence in GitHub Actions

- source: `.github/instructions/subcontractor-pricing-folder-discovery.instructions.md`
  (Hash Change Detection Fixes, Bug 3)
- decision: the weekly workflow caches `hash_history.json` via
  `actions/cache@v4` keyed `hash-history-{branch}`.

### Railway → Render migration target

- source: `docs/railway-to-render-transition-plan.md` (§3, §4)
- status: **approved plan, pre-implementation**
- decision: Express backend (`portal/`) hosts on Render Web
  Service, Starter plan ($7/mo, Oregon region), root
  directory `portal`, build `npm ci`, start `node server.js`,
  health check `/health`, Node `>=20 <23`. Free tier is
  rejected because it spins down and breaks SSE + poller.
- env-var contract: the variable list in §4.1 is the
  source-of-truth migration manifest.
- corollary: `SENTRY_RELEASE` on Render is set automatically
  from `RENDER_GIT_COMMIT`.

### In-memory LRU artifact + search caches (v1)

- source: `docs/railway-to-render-transition-plan.md` (§7.6)
- decision: artifact parse cache (`max: 50`, TTL 15 min) and
  search index (`max: 200`, TTL 60 min) live in memory on the
  Render process. No Supabase search table, no Upstash, no
  external search infra in v1.
- memory budget: 200 × ~2 MB ≈ 400 MB upper bound, inside
  Render Starter 512 MB.

### Artifact Explorer download surface (v1)

- source: `docs/railway-to-render-transition-plan.md` (§7.4)
- decision: v1 ships **only** original `.xlsx` passthrough.
  CSV / all-sheets zip / PDF / parsed-JSON are deferred to
  v2+. `DownloadMenu.tsx` is structured as a split-button so
  adding formats later is a one-line array change.

### Migration rollback contract

- source: `docs/railway-to-render-transition-plan.md` (§5, §6)
- decision: Railway stays warm for 48 h post-cutover so
  rollback is an env-var flip on Vercel
  (`VITE_API_BASE_URL`), not a redeploy. Each rollback row in
  §6 names a trigger, action, and max recovery time.
