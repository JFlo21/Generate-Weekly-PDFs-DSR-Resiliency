# Constraints

Synthesized from SPEC-equivalent content in the ingest set. Two
documents classified as SPEC; multiple DOC-class documents also
carry constraint-flavored content that is captured here so the
roadmapper has a single source of truth for hard limits, API
contracts, and operational invariants.

---

## Subcontractor pricing — current-state contract

> source: `.github/instructions/subcontractor-pricing-folder-discovery.instructions.md`
> type: api-contract / business-rule

- Subcontractor (Arrowhead) sheets carry `Units Total Price`
  values at a 10% reduced rate (original × 0.9). The Excel
  reports reflect that subcontractor pricing as-is. **No price
  reversion** is performed.
- Rate recalculation only applies to primary (non-subcontractor)
  sheets, and even there is currently retired at the workflow
  layer (see `decisions.md` 2026-04-24 14:30).
- `revert_subcontractor_price()` and the `_rate_new_arrowhead`
  tables exist and are precomputed, but are NOT called during
  row processing.
- The `is_subcontractor_sheet` flag in `get_all_source_rows()`
  identifies subcontractor sheets but does not trigger any
  price change.

## Folder-based discovery contract

> source: `.github/instructions/subcontractor-pricing-folder-discovery.instructions.md`
> type: api-contract

- `discover_folder_sheets()` reads each Smartsheet folder via
  `client.Folders.get_folder(folder_id)` and returns a set of
  sheet IDs. Sheets are merged into `base_sheet_ids` inside
  `discover_source_sheets()` after the `LIMITED_SHEET_IDS`
  check.
- Subcontractor folder IDs (env `SUBCONTRACTOR_FOLDER_IDS`):
  `4232010517505924`, `2588197684307844`.
- Original-contract folder IDs (env
  `ORIGINAL_CONTRACT_FOLDER_IDS`): `7644752003786628`,
  `8815193070299012`. Stored in `_FOLDER_DISCOVERED_ORIG_IDS`.
- All folder-discovered sheets go through the same
  `discover_source_sheets()` column-validation pipeline as
  every other sheet.
- Test contract: mock `client.Folders.get_folder()`; never
  call the real Smartsheet API in tests.

## Smartsheet API constraints

> source: `CLAUDE.md` (Smartsheet API & Integration Standards),
> `.claude/rules/smartsheet-python-optimization.md`
> type: nfr / protocol

- Rate limit: **300 req/min**. `PARALLEL_WORKERS` is capped at
  **8** to stay within quota.
- Rely on the SDK's built-in 429 retry handling; **do not**
  add custom retry loops around `client.Sheets.get_sheet`.
- For primary bulk extraction, use
  `smartsheet.Sheets.get_sheet(sheet_id)` and access
  `sheet.rows` directly. **Do not** paginate row-by-row.
- The Smartsheet `@cell` formula is UI-only and **fails
  server-side**. NEVER write or suggest it in Python scripts
  or API payloads.
- Column-name verification: always check against
  `_validate_single_sheet()` mappings. Verified synonyms
  include `Weekly Reference Logged Date`, `helper_dept`,
  `helper_foreman`, `Job #` (with `Job#` / `Job Number`
  variants).

## Excel generation constraints

> source: `CLAUDE.md` (Critical Pitfalls),
> `.claude/rules/smartsheet-python-optimization.md`
> type: api-contract

- For the existing `generate_weekly_pdfs.py` pipeline, continue
  to use `openpyxl` with `safe_merge_cells()` (overlap-
  detecting). **Do not** mix engines inside a single output
  file. **Do not** silently switch the existing engine to
  `xlsxwriter`.
- **Never** write `oddFooter.right.text` — known corruption
  vector.
- New scripts producing Excel SHOULD prefer
  `xlsxwriter(constant_memory=True)` or
  `pandas.to_excel(engine="xlsxwriter")`. Any new script that
  adopts this MUST add `XlsxWriter` to `requirements.txt` (and
  any relevant lockfile) in the same PR; the dep is not
  currently declared globally.
- Output filename shape:
  `WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}{variant_suffix}_{hash}.xlsx`
  with `variant_suffix ∈ {``, `_User_<foreman>`,
  `_Helper_<foreman>`, `_VacCrew`}`. The workflow's artifact
  organizer globs `WR_*_WeekEnding_*`.

## Change-detection key composition

> source: `CLAUDE.md` (Data Pipeline Architecture / Change-
> detection key), `memory-bank/systemPatterns.md`
> type: business-rule

- Change-detection key includes `foreman`, `dept`, and `job`.
  Helper Excel files regenerate when new rows are added for
  past weeks because the hash key includes these fields. **Do
  not** shorten the key back to
  `(WR, week, variant, foreman)`.
- Helper rows: require both `helper_dept` and `helper_foreman`
  (Job # optional). Rows with both `Helping Foreman Completed
  Unit?` and `Units Completed?` checkboxes checked appear
  **only** in helper Excel files, never the main file — that
  exclusion prevents double-counting when
  `RES_GROUPING_MODE ∈ {both, helper}`.

## Time-budget contract (weekly workflow)

> source: `CLAUDE.md` (GitHub Actions Workflow / runner timeouts,
> 2026-04-22 17:10)
> type: nfr

- `timeout-minutes: 195` is the hard Actions ceiling for the
  `core` job in `weekly-excel-generation.yml`.
- `TIME_BUDGET_MINUTES: 180` is the Python graceful-stop
  budget. Must always remain strictly less than
  `timeout-minutes` by ≥10–15 min so cache-save and artifact-
  upload tails complete.
- `ATTACHMENT_PREFETCH_MAX_MINUTES: 10` (phase sub-budget).
- `ATTACHMENT_PREFETCH_FUTURE_TIMEOUT_SEC: 45` (per-future
  consumer wait).
- `ATTACHMENT_PREFETCH_GENERATION_HEADROOM_MIN: 2` (preflight
  skip reserves this beyond the pre-fetch budget).

## Discovery-cache invariants

> source: `CLAUDE.md` (multiple Living Ledger entries:
> 2026-04-22 00:00, 2026-04-22 18:30, 2026-04-23 12:00,
> 2026-04-23 20:10)
> type: schema

- Path: `generated_docs/discovery_cache.json`.
- TTL: `DISCOVERY_CACHE_TTL_MIN`, default `10080` (7 days).
- Bump `DISCOVERY_CACHE_VERSION` whenever a fix would leave
  already-cached entries holding incorrect column mappings;
  the cache's `_new_from_folders` check only invalidates on
  NEW sheet IDs, not in-place column additions.
- `_valid_cached_sheets` filter requires each entry to be a
  dict with int `id`, dict `column_mapping`, and str `name`.
  All-dropped non-empty input raises `ValueError` so callers
  fall through to full rediscovery — never silent no-op.
- Fresh-cache fast path also requires
  `not _partial_cache_corruption`; any schema-filter drop
  forces incremental mode.

## Render service configuration

> source: `docs/railway-to-render-transition-plan.md` (§4)
> type: protocol / infra-contract

| Setting | Value |
|---|---|
| Service type | Web Service (NOT Static, NOT Background Worker) |
| Repo | `JFlo21/Generate-Weekly-PDFs-DSR-Resiliency` |
| Branch | `master` (auto-deploy on push) |
| Root Directory | `portal` |
| Build Command | `npm ci` |
| Start Command | `node server.js` |
| Node version | `engines.node` pinned `>=20 <23` in `portal/package.json` |
| Health Check Path | `/health` |
| Instance plan | **Starter** ($7/mo) — free tier breaks SSE + poller |
| Region | Oregon (closest to Vercel iad1/sfo1) |

## Render env vars (must mirror Railway at cutover)

> source: `docs/railway-to-render-transition-plan.md` (§4.1)
> type: api-contract

`GITHUB_TOKEN`, `GITHUB_OWNER`, `GITHUB_REPO`,
`GITHUB_WORKFLOW`, `GITHUB_BRANCH`, `SESSION_SECRET`,
`CORS_ORIGIN`, `CORS_ORIGINS` (optional), `SUPABASE_JWT_SECRET`
(required), `PORT` (unset — Render injects), `NODE_ENV=production`,
`POLL_INTERVAL_MS`, `PORTAL_SENTRY_DSN`,
`SENTRY_ENVIRONMENT=production`, `SENTRY_TRACES_SAMPLE_RATE`,
`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`.

`SENTRY_RELEASE` is set automatically from `RENDER_GIT_COMMIT`;
no manual wiring.

## Render service risks and mitigations

> source: `docs/railway-to-render-transition-plan.md` (§4.2)
> type: nfr

| Risk | Mitigation |
|---|---|
| Proxy idle timeout drops SSE | Keep heartbeat ≤30 s; verify in staging for 30+ min before cutover |
| GitHub rate limit during overlap | Temporarily raise `POLL_INTERVAL_MS` on Railway during the 48 h standby |
| Cold start after accidental plan downgrade | Lock plan to Starter; record requirement in `memory-bank/techContext.md` |
| Session cookie domain mismatch | Confirm `SameSite=None; Secure` and correct cookie domain once Render custom domain is attached |
| In-memory caches lost on restart | Caches are advisory; on restart the first request reparses from GitHub. No correctness impact. |

## Memory budget for in-memory caches

> source: `docs/railway-to-render-transition-plan.md` (§7.6)
> type: nfr

- `artifactCache`: `max: 50`, TTL 15 min, keyed by `artifactId`.
- `searchIndex`: `max: 200`, TTL 60 min. Lazily populated from
  `artifactCache`.
- Upper bound: 200 indexed artifacts × ~2 MB tokens ≈ 400 MB,
  well inside Render Starter's 512 MB.
- Cache-bust on `artifact.expired === true` (GitHub's field).
- Cold-restart behavior: first search rebuilds lazily; no
  correctness risk.

## Express backend constraints

> source: `CLAUDE.md` (Conventions / Node.js),
> `.github/instructions/nodejs-javascript-vitest.instructions.md`
> type: protocol

- `portal/` is **CommonJS** (`"type": "commonjs"`,
  `require()` / `module.exports`). Do NOT introduce
  `import`/`export` there.
- `portal-v2/` is ES2022+ ESM.
- `async`/`await` only (no callbacks).
- **Prefer `undefined` over `null`.**
- Prefer functions over classes; minimize external deps.
- Tests use Vitest. Never change production code to make it
  testable — write tests around the code as-is.

## Sentry tagging contract

> source: `CLAUDE.md` (Architecture Decisions / Sentry
> Telemetry; 2026-04-20 00:00 ledger entry),
> `docs/sentry-implementation.md`
> type: protocol

- Standardize `environment` and `release` tags across all
  scripts so alert routing stays consistent.
- `SENTRY_RELEASE` MUST be slash-free for `sentry-cli` to
  accept it. Compose via
  `${GITHUB_REPOSITORY//\//-}@${GITHUB_SHA}` in a "Compute
  Sentry release" step.
- `SENTRY_ENABLE_LOGS` default `false`. `before_send_log`
  sanitizer is mandatory.

## Attachment upload pattern

> source: `.claude/rules/smartsheet-python-optimization.md` (§3)
> type: api-contract

- Use `client.Attachments.attach_file_to_row(sheet_id,
  row_id, (file_name, file_stream, content_type))`.
- When replacing an existing attachment, **delete first,
  then upload** (mirrors the production pattern in
  `generate_weekly_pdfs.py`).
- Wrap in `sentry_sdk.start_span(op="smartsheet.attach_file",
  description=...)` + `try / capture_exception() / raise`.
- Never swallow exceptions silently.

## `advanced_options` parser contract

> source: `CLAUDE.md` (GitHub Actions Workflow / advanced_options)
> type: api-contract

- Packed format: `key:value,key:value`, parsed by `tr`/`cut`
  in `.github/workflows/weekly-excel-generation.yml`.
- Example:
  `max_groups:50,regen_weeks:081725;082425,reset_wr_list:WR123;WR456`.
- Do not delete this parser even if top-level input count is
  below GitHub's 10-input limit — several runbooks depend on
  this exact format.

## Schedule contract (weekly workflow)

> source: `CLAUDE.md` (GitHub Actions Workflow / Schedule)
> type: nfr

- Weekdays (Mon–Fri): 7 runs/day at UTC `13,15,17,19,21,23,01`.
- Weekends (Sat, Sun): 3 runs/day at UTC `15,19,23`.
- Weekly deep run: `0 5 * * 1` (UTC Monday 05:00 = Sunday
  23:00 CST / Monday 00:00 CDT Central). The `if: day==1 &&
  hour==23` Central-time guard inside the job flips the run
  into the "weekly comprehensive" branch.
- Container TZ inside the job: `America/Chicago`.

## Supabase / `billing_audit` schema contract

> source: `CLAUDE.md` (2026-04-25 12:00),
> `billing_audit/schema.sql`
> type: schema

- Any new Supabase table/column the pipeline reads or writes
  MUST have matching DDL in `billing_audit/schema.sql`
  committed in the same PR that adds the Python code.
- Reviewers MUST block merges that add
  `client.schema(...).table(...)` references against a column
  not present in `schema.sql`.
- Permanent SQLSTATE prefixes for the PostgREST retry
  classifier: `"22"`, `"23"`, `"42"` (length-gated to
  `len(code) == 5`).
- Retryable SQLSTATE classes (must stay transient): `08`,
  `40`, `53`, `57`.
- Global-kill PGRST codes: `PGRST106` (schema not exposed),
  `PGRST301`, `PGRST302` (JWT invalid/expired).
