# Phase 1: Subcontractor Rate Logic Modification - Context

**Gathered:** 2026-05-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Additive change to `generate_weekly_pdfs.py` that generates **two new
computed-from-CSV Excel variants** for every subcontractor-folder WR
group, on top of the existing primary / helper / VAC-crew outputs:

- **`_AEPBillable`** — priced via `data/subcontractor_rates.csv` `new_*`
  columns (3% increase, what Linetec bills AEP). Generated only when
  `Snapshot Date >= 2026-04-12`. Routed to original PPP
  `TARGET_SHEET_ID=5723337641643908` only.
- **`_ReducedSub`** — priced via `data/subcontractor_rates.csv`
  `reduced_*` columns (13% reduction from new contract, what Linetec
  pays subcontractors). Generated unconditionally. Routed to BOTH
  `TARGET_SHEET_ID=5723337641643908` AND new
  `SUBCONTRACTOR_PPP_SHEET_ID=8162920222379908`.

Both variants extend to shadow-foreman / helper events: a foreman
change on a subcontractor WR produces both
`_AEPBillable_Helper_<name>` and `_ReducedSub_Helper_<name>` shadow
files for the prior foreman's claimed units.

**Strict scope:** subcontractor-folder sheets only
(`SUBCONTRACTOR_FOLDER_IDS`-discovered, gated by
`is_subcontractor_sheet` at `generate_weekly_pdfs.py:2791`).
Original-contract folders (`7644752003786628`, `8815193070299012`)
and the VAC-crew workflow are not touched.

</domain>

<decisions>
## Implementation Decisions

### CSV delivery (user-discussed)

- **D-01:** The operator-provided `CU List - Corpus North & South.csv`
  (4848 data rows, 17 columns, currency-formatted prices, mirrors the
  XLSX schema captured in `.planning/intel/contract-schema.md`) is the
  authoritative rate source for the new variants. The XLSX itself
  remains gitignored; only the CSV is checked into the repo.
- **D-02:** The CSV moves from repo root to **canonical path
  `data/subcontractor_rates.csv`** via `git mv` in the execution plan.
  REQUIREMENTS.md SUB-04 already points at this canonical path — the
  rename closes the gap without doc rework.
- **D-03:** The loader path is configurable via a new env var
  `SUBCONTRACTOR_RATES_CSV` (default `data/subcontractor_rates.csv`),
  mirroring the retired `NEW_RATES_CSV` / `OLD_RATES_CSV` ergonomics
  per `decisions.md` 2026-04-24 14:30.
- **D-04:** The loader handles coercion — no operator burden to
  reformat the CSV:
  - Read with `encoding='utf-8-sig'` (handles potential BOM)
  - Strip `$` and thousands-separator commas from price cells, parse
    to `float`
  - Skip rows whose all six priced columns are zero (`$0.00` placeholder
    CUs — 1058 of 4848 in the supplied file); these do NOT count as
    "missing" CUs
  - `'N/A'` in Hours columns is tolerated (hours are not loaded — see
    D-06)

### CSV column shape (Claude's discretion — defaulted per intel)

- **D-05:** The CSV file on disk retains all 17 columns (operator-facing
  human-readable format with currency strings). The loader extracts
  only 9 fields per row:
  - `cu_code` ← column 2 `CU` (join key for Smartsheet row CU lookups)
  - `cu_wbs` ← column 1 `CU WBS #` (audit-only, surfaced in WARNINGs)
  - `compatible_unit_group` ← column 5 (audit-only)
  - `reduced_install_price` ← column 9 `Install Price (Subcontractor Rates)`
  - `reduced_remove_price` ← column 10 `Removal Price (Subcontractor Rates)`
  - `reduced_transfer_price` ← column 11 `Transfer Price (Subcontractor Rates)`
  - `new_install_price` ← column 15 `Install Price (New Rates)`
  - `new_remove_price` ← column 16 `Removal Price (New Rates)`
  - `new_transfer_price` ← column 17 `Transfer Price (New Rates)`
- **D-06:** Old Rates columns (12–14) and Hours columns (6–8) are NOT
  loaded into the in-memory rate dict. Rationale (per
  `intel/contract-schema.md`): loading the old rates invites accidental
  code reuse and creates a third source of truth alongside the retired
  ORIG-folder rule (`decisions.md` 2026-04-24 14:30). The XLSX/CSV file
  retains them for human audit only.
- **D-07:** Per-CU rate variance is real (median New/Old = 1.0300, min
  = 1.0244; median Reduced/New = 0.8738, min = 0.4343). The loader
  reads **literal values** from each row — code MUST NOT compute
  `reduced = old × 0.87` or `new = old × 1.03` as a shortcut.

### Variant naming, ordering, hash key, parser (locked via REQUIREMENTS.md + Claude's discretion)

- **D-08:** Variant suffix tokens are **`_AEPBillable`** and
  **`_ReducedSub`** (matches REQUIREMENTS.md SUB-01..05 exactly).
- **D-09:** Ordering relative to existing helper suffix:
  variant-first, helper-second — `_AEPBillable_Helper_<name>` and
  `_ReducedSub_Helper_<name>`. Matches REQUIREMENTS.md SUB-05 wording.
  Filename template stays:
  `WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}_{variant_suffix}_{hash}.xlsx`
  where `variant_suffix ∈ { '_AEPBillable', '_ReducedSub',
  '_AEPBillable_Helper_<name>', '_ReducedSub_Helper_<name>' }`
- **D-10:** `build_group_identity()`
  (`generate_weekly_pdfs.py:1706`) is extended to recognize
  `_AEPBillable` and `_ReducedSub` as first-class variant markers in
  the same span-join logic introduced by round-7
  (`decisions.md` 2026-04-23 20:40). Recognized variant strings
  produced: `aep_billable`, `reduced_sub`, `aep_billable_helper`,
  `reduced_sub_helper`. Tests must include the cross-variant
  filename round-trip case to lock in non-collision with the
  existing `Helper` / `VacCrew` / `User` literal-token detection
  (`generate_weekly_pdfs.py:667`).
- **D-11:** Hash key uses the **existing shared bucket** with the
  variant token distinguishing entries —
  `meta_parts.append(f"VARIANT={variant}")` at
  `generate_weekly_pdfs.py:1569` accepts the four new variant
  strings. NO new hash buckets per variant. Rationale: matches the
  existing pattern (helper/vac_crew already share buckets keyed on
  variant token); minimizes hash_history churn; pricing changes
  flow through naturally because the per-row hash captures price
  cells. NOT shortened — `(WR, week, variant, foreman, dept, job)`
  composition stays per `decisions.md` 2026-04-22 00:00 +
  2026-04-22 silent-skip rule.

### Routing + env vars

- **D-12:** New env var `SUBCONTRACTOR_PPP_SHEET_ID` (default
  `8162920222379908`) routes `_ReducedSub` files to the second target
  sheet. The existing `TARGET_SHEET_ID` (`5723337641643908`) continues
  to receive both variants. Resolution pattern mirrors `TARGET_SHEET_ID`
  exactly: `int(os.getenv('SUBCONTRACTOR_PPP_SHEET_ID',
  '8162920222379908'))`.
- **D-13:** New default-on kill-switch env var
  `SUBCONTRACTOR_RATE_VARIANTS_ENABLED` (default `'1'`, truthy values
  `1`/`true`/`yes`/`on`). When the operator flips it off, the entire
  new code path short-circuits and the pipeline reverts to pre-change
  behavior on subcontractor sheets. Pattern mirrors
  `RATE_RECALC_SKIP_ORIGINAL_CONTRACT` (`decisions.md` 2026-04-24
  11:30) and `RATE_RECALC_WEEKLY_FALLBACK` (`decisions.md` 2026-04-23
  00:00). State is logged in the startup banner.

### Coexistence with existing rules (Claude's discretion — defaulted)

- **D-14:** The existing **primary** subcontractor Excel file
  (`WR_xxx_WeekEnding_<date>_<hash>.xlsx`, no variant suffix) **continues
  to generate** for every subcontractor WR group, unchanged. The new
  `_AEPBillable` and `_ReducedSub` files are **additive** —
  3 files per qualifying subcontractor WR + week (primary +
  _AEPBillable + _ReducedSub when post-cutoff; primary + _ReducedSub
  when pre-cutoff). Rationale: SUB-06 says "no new subcontractor
  variant logic affects" existing flows, which forbids changing the
  primary file's behavior. The subcontractor pricing SPEC
  (`subcontractor-pricing-folder-discovery.instructions.md`) "keep
  SmartSheet pricing as-is — no rate recalculation" rule continues to
  govern the primary file; the new variants are NEW files that don't
  overwrite SmartSheet `Units Total Price` cells.
- **D-15:** Helper / VAC-crew variant generation behavior on
  subcontractor sheets stays unchanged — the existing
  `_Helper_<foreman>` / `_VacCrew` files continue at SmartSheet
  pricing. The NEW `_AEPBillable_Helper_<name>` and
  `_ReducedSub_Helper_<name>` shadow files generate **in addition to**
  them.

### Missing-CU surfacing (Claude's discretion — defaulted per ledger 2026-04-21)

- **D-16:** When the loader encounters a Smartsheet row whose CU code
  is not in `data/subcontractor_rates.csv`, the row's pricing falls
  through to the existing SmartSheet `Units Total Price` value
  (safety net — never zero-out, never error). The CU code is
  tracked in a per-sheet `missing_cus: Counter()`.
- **D-17:** At end of each subcontractor sheet's processing, fire ONE
  `WARNING`-level log line if `missing_cus` is non-empty:
  ```
  Subcontractor rates CSV missing {N} CU code(s) on sheet {sheet_id}:
  {first_10_codes}{ "..." if N > 10 else "" }.
  Add to data/subcontractor_rates.csv to enable rate recalc for
  these rows. Sheet rows fell through to SmartSheet pricing.
  ```
  Mirrors the 2026-04-21 22:35 ledger pattern; threshold = 10 CU codes
  shown to bound log line length.

### billing_audit attribution (Claude's discretion — defaulted per ledger 2026-04-25)

- **D-18:** `billing_audit.pipeline_run` gains a `variant TEXT NULL`
  column via idempotent DDL in `billing_audit/schema.sql`:
  ```sql
  ALTER TABLE billing_audit.pipeline_run
    ADD COLUMN IF NOT EXISTS variant TEXT;
  ```
  TEXT (not enum / CHECK constraint) for forward compatibility. NULL
  on existing pre-change rows. New writer values:
  `primary | helper | vac_crew | aep_billable | reduced_sub |
  aep_billable_helper | reduced_sub_helper`. Schema DDL + writer
  change ship in the **same PR** (SUB-07 acceptance criterion).
- **D-19:** `freeze_row()` parallelization
  (`decisions.md` 2026-04-25 14:00) is preserved — the
  `ThreadPoolExecutor(max_workers=min(PARALLEL_WORKERS,
  len(group_rows)))` wrapper continues to wrap the per-row
  `freeze_row` loop; new variant attribution is passed as a `variant`
  kwarg into the writer and recorded inside the worker fn.

### CSV staleness fingerprint (Claude's discretion — defaulted)

- **D-20:** A new module-level `_SUBCONTRACTOR_RATES_FINGERPRINT` is
  computed at loader startup:
  ```python
  fp = hashlib.sha256(
      json.dumps(rates_dict, sort_keys=True, default=str).encode()
  ).hexdigest()[:16]
  ```
  - Logged in the startup banner alongside the existing config
    summary so operators can diff fingerprints across runs
  - Embedded in `calculate_data_hash()` `meta_parts` for the new
    variants only (so a CSV edit forces regen of every
    `_AEPBillable` / `_ReducedSub` file but doesn't touch primary /
    helper / vac_crew hashes — preserves byte-identical guarantee in
    success criterion 5)
  - Replaces the retired `_RATES_FINGERPRINT` semantically (different
    name, scoped to subcontractor variants only)
- **D-21:** `DISCOVERY_CACHE_VERSION` does **NOT** bump for this
  change. Rationale: discovery cache stores per-sheet column
  mappings, and no Smartsheet column mappings change in this phase
  (we're producing new files from existing rows, not reading new
  columns). The fingerprint above handles CSV-staleness regen
  independently. If plan-phase discovers a column-mapping change is
  needed, bump in that plan.

### Operational guardrails (locked from ledger — listed for completeness)

- **D-22:** All locked rules from `.planning/intel/decisions.md`
  apply unchanged. Specifically and non-exhaustively:
  - `_RE_SANITIZE_HELPER_NAME` regex applied at every WR# and
    foreman-name derivation site, including the new variant code
    paths (`decisions.md` 2026-04-23 rounds 1-9). The Helper name in
    `_AEPBillable_Helper_<name>` and `_ReducedSub_Helper_<name>`
    MUST be sanitized at producer AND consumer sites.
  - `target_map` collision quarantine extends to the new variants —
    a WR# folding to the same sanitized key on either the source or
    target side under a new variant is quarantined and skipped
    (`decisions.md` 2026-04-23 rounds 6, 7, 9).
  - PostgREST SQLSTATE classification applies to any new
    `billing_audit` schema interactions (`decisions.md` 2026-04-25
    12:00).
  - `_redact_exception_message` must be used for every new
    `sentry_capture_with_context` call introduced by this phase
    (`decisions.md` 2026-04-23 12:00).
  - `_PII_LOG_MARKERS` is extended if any new INFO-level log line
    embeds subcontractor pricing or CU codes (loader logs included).
  - `SENTRY_ENABLE_LOGS` gate + `before_send_log` sanitizer continue
    to apply to all new logs.
  - Subcontractor sheets still respect the existing "keep SmartSheet
    pricing for the primary file" rule
    (`subcontractor-pricing-folder-discovery.instructions.md`); the
    new variants are additive files only.
  - `_skip_recalc_original_contract` gate remains primary — no
    subcontractor logic runs on ORIG folder sheets even if a folder
    is misconfigured into both `SUBCONTRACTOR_FOLDER_IDS` AND
    `ORIGINAL_CONTRACT_FOLDER_IDS`.
  - `tests/validate_production_safety.py` per-group-block window cap
    bumps as needed if the inner try/except block grows
    (`decisions.md` 2026-04-25 14:00 rule 3).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning (this milestone)

- `.planning/PROJECT.md` — locked decisions, tech stack, out-of-scope items
- `.planning/REQUIREMENTS.md` — SUB-01..SUB-07 (acceptance criteria
  + traceability table)
- `.planning/ROADMAP.md` — Phase 1 success criteria (5 numbered
  items), Phase 2 (DEFERRED)
- `.planning/STATE.md` — current GSD state

### Synthesized intel (from /gsd-ingest-docs)

- `.planning/intel/decisions.md` — every locked rule the new code
  must respect (read entirely before planning)
- `.planning/intel/constraints.md` — 15 constraint blocks: pricing
  contract, folder-discovery API, Smartsheet protocol, Excel
  generation, change-detection key, time budget, billing_audit
  schema, etc.
- `.planning/intel/contract-schema.md` — full schema of the
  CU List XLSX/CSV including the gitignored-XLSX delivery issue
  (now resolved per D-01), per-CU rate variance, zero-price
  placeholder rows, and the 5 loader gaps that this CONTEXT.md
  resolves
- `.planning/INGEST-CONFLICTS.md` — single WARNING (Living Ledger
  ADR extraction) was acknowledged during ingest

### Codebase-resident specs and rules

- `CLAUDE.md` — Living Ledger (~30 dated locked rules); the
  authoritative project memory
- `.github/instructions/subcontractor-pricing-folder-discovery.instructions.md`
  — existing SPEC governing subcontractor primary-file behavior
  ("keep SmartSheet pricing as-is, no rate recalc"). Phase 1
  does NOT modify this rule for the primary file; the new variants
  are additive
- `.github/instructions/python.instructions.md` — PEP 8, type
  hinting, docstrings
- `.github/instructions/performance-optimization.instructions.md`
  — parallelism cap (`PARALLEL_WORKERS ≤ 8`), time-budget
  proportions, attachment pre-fetch sub-budget
- `.github/instructions/github-actions-ci-cd-best-practices.instructions.md`
  — workflow conventions
- `.claude/rules/smartsheet-python-optimization.md` — Smartsheet
  API contract; `openpyxl` engine policy for the existing
  pipeline; `xlsxwriter` is for NEW scripts only (this phase stays
  on `openpyxl`)
- `.claude/rules/documentation-maintenance.md` — runbook
  changelog policy; Docusaurus typecheck + build before push

### Authoritative rate source

- `CU List - Corpus North & South.csv` (repo root, **will move to
  `data/subcontractor_rates.csv` per D-02**) — 4848 rows, 17 cols,
  currency-formatted prices, the operator-managed source of truth
  for both new variants' pricing

### Code integration map (`generate_weekly_pdfs.py`)

- L75 `_RE_SANITIZE_HELPER_NAME` — sanitization regex; apply at
  every new producer/consumer site
- L329 `SUBCONTRACTOR_FOLDER_IDS` — env-var gate; the folder set
  whose sheets get the new variants
- L339-340 `_FOLDER_DISCOVERED_SUB_IDS` / `_FOLDER_DISCOVERED_ORIG_IDS`
  — populated by `discover_folder_sheets`; primary subcontractor-vs-
  ORIG distinction
- L661-667 helper / vac_crew variant marker constants; new variants
  must not collide with these literal tokens
- L1421 `calculate_data_hash()` — extension point for the new
  variants' meta_parts and the CSV fingerprint
- L1569 `meta_parts.append(f"VARIANT={variant}")` — variant token
  injection
- L1706 `build_group_identity()` — filename round-trip parser;
  must learn `_AEPBillable` and `_ReducedSub` markers
- L1845+ `cleanup_untracked_sheet_attachments`,
  `delete_old_excel_attachments` — variant-aware cleanup must
  cover new variants
- L2791 `is_subcontractor_sheet = source['id'] in SUBCONTRACTOR_SHEET_IDS`
  — the gate that enables new variant generation
- L2799 `is_original_contract_sheet = source['id'] in
  _FOLDER_DISCOVERED_ORIG_IDS` — the gate that DISABLES recalc on
  ORIG sheets (must stay primary)

### billing_audit shadow

- `billing_audit/schema.sql` — add idempotent `ALTER TABLE
  pipeline_run ADD COLUMN IF NOT EXISTS variant TEXT`
- `billing_audit/writer.py` — `freeze_row()` gains a `variant`
  kwarg; writer records it in the `pipeline_run` upsert payload
- `billing_audit/client.py` — `with_retry` and
  `_classify_postgrest_error` apply unchanged; no new SQLSTATE
  categories needed
- `billing_audit/fingerprint.py` — `emit_run_fingerprint`
  unchanged; per-run dedup logic already once-per-group

### Test integration

- `tests/test_subcontractor_pricing.py` — existing subcontractor
  rate tests; pattern for new variant regression tests
- `tests/test_vac_crew.py` — parallel reference for
  variant-specific generation tests
- `tests/test_security_audit_followup.py` — sanitization,
  `target_map` quarantine, `build_group_identity` round-trip; add
  cases for `_AEPBillable` / `_ReducedSub`
- `tests/test_billing_audit_shadow.py` — `freeze_row` writer
  tests; add cases for `variant` attribution
- `tests/validate_production_safety.py` — production-safety
  validator; bump per-group-block window if necessary

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`_RE_SANITIZE_HELPER_NAME` regex** (`generate_weekly_pdfs.py:75`)
  — idempotent sanitizer; safe to apply at every new producer AND
  consumer site without canonicalization confusion
- **`discover_folder_sheets()`** + `_FOLDER_DISCOVERED_SUB_IDS` — the
  folder-discovery flow that drives `is_subcontractor_sheet` already
  populates everything we need; no changes required to discovery
- **`build_group_identity()` span-join parser**
  (`generate_weekly_pdfs.py:1706`) — already round-7-hardened against
  underscores in WR tokens. The extension for new variant markers
  follows the same pattern (extract variant from post-`WeekEnding`
  tail using `list.index()` + variant token detection)
- **`calculate_data_hash()`** (`generate_weekly_pdfs.py:1421`) —
  variant-aware hash composition is already in place via
  `meta_parts.append(f"VARIANT={variant}")`; new variant strings
  flow through naturally
- **`ThreadPoolExecutor(max_workers=min(PARALLEL_WORKERS,
  len(group_rows)))` pattern** for `freeze_row` parallelization
  (`decisions.md` 2026-04-25 14:00) — reuse identically for any new
  per-row I/O loop the variants introduce
- **Existing kill-switch env-var pattern**
  (`RATE_RECALC_SKIP_ORIGINAL_CONTRACT` /
  `RATE_RECALC_WEEKLY_FALLBACK`) — clone for
  `SUBCONTRACTOR_RATE_VARIANTS_ENABLED`

### Established Patterns

- **Filename template invariance**: every variant share the prefix
  `WR_{wr}_WeekEnding_{MMDDYY}_{timestamp}` and end with
  `_{hash}.xlsx`; suffix is purely between those two anchors. The
  span-join parser relies on the `WeekEnding` literal token as the
  anchor — DO NOT change that
- **Default-on kill-switch env vars** — every operator-facing
  feature toggle defaults to ON, truthy values `1`/`true`/`yes`/`on`,
  state logged in the startup banner. Operator can flip to disabled
  in emergency without a code change
- **Sanitize at every site** rule (`decisions.md` 2026-04-23 18:25)
  — any identifier that flows into a filename or target_map key must
  be sanitized at producer AND consumer sites; sanitization is
  idempotent so double-applying is safe
- **Collision quarantine over keep-first-seen** — sanitized-key
  collisions delete both keys and add to `_quarantined_*_keys`;
  downstream lookups fail-not-found rather than silently routing to
  the wrong row (`decisions.md` 2026-04-23 round-6, round-9)
- **Schema DDL idempotency** — `ALTER TABLE ... ADD COLUMN IF NOT
  EXISTS` so existing deployed Supabase pipeline_run tables
  upgrade in-place; matches `decisions.md` 2026-04-25 12:00 P0 rule
- **Operator-actionable WARNINGs** — every WARNING that surfaces a
  data gap names the file/path the operator needs to fix; the new
  missing-CU WARNING (D-17) follows this pattern

### Integration Points

- **Entry point for new variants:** inside `_fetch_and_process_sheet`,
  immediately after the existing primary/helper/vac_crew variant
  detection block, gated by `is_subcontractor_sheet` AND
  `SUBCONTRACTOR_RATE_VARIANTS_ENABLED` (truthy)
- **Loader call site:** `data/subcontractor_rates.csv` is loaded once
  at session startup (before the main group-processing loop), the
  resulting dict is captured into a module-level
  `_SUBCONTRACTOR_RATES` along with `_SUBCONTRACTOR_RATES_FINGERPRINT`.
  Loading inside the per-group loop would re-read the CSV ~1900 times
  per run — unacceptable.
- **Excel generation extension:** `generate_excel()` accepts the
  variant string and, for `aep_billable` / `reduced_sub` variants,
  substitutes `Units Total Price` cells with `rate × qty` computed
  from the loaded CSV BEFORE the workbook is written. Primary,
  helper, vac_crew variants continue to use the existing path
  (SmartSheet `Units Total Price` value as-is)
- **Routing extension:** `create_target_sheet_map` and the upload-task
  builder accept a second target sheet (`SUBCONTRACTOR_PPP_SHEET_ID`)
  for `reduced_sub` and `reduced_sub_helper` variants; ALL other
  variants stay on `TARGET_SHEET_ID`
- **freeze_row attribution:** `_billing_audit_writer.freeze_row()`
  gets `variant=<variant_string>` kwarg; writer records it in the
  `pipeline_run` upsert. Schema DDL ships in the same PR per SUB-07.

</code_context>

<specifics>
## Specific Ideas

- **Operator-provided CSV is the loader contract** — the user
  manually converted the XLSX to CSV at repo root and explicitly
  chose the canonical `data/subcontractor_rates.csv` path. The
  operator commits the CSV; the loader reads it. No
  XLSX-conversion script in the production path. (A throwaway
  helper script for the operator's local sync could be added by
  the planner if scope permits, but is not required.)
- **Audit columns are first-class on disk, not first-class in
  code** — the file keeps all 17 columns for human review; the
  loader only loads 9 fields per row. This is deliberate: the
  human-readable file format and the machine-readable runtime dict
  are different shapes by design.
- **"13% reduction" framing means Reduced ≈ New × 0.87** — NOT
  Reduced ≈ Old × 0.87. Median Reduced/New = 0.8738 across 3688
  priced rows. (Per-CU outliers go down to 0.4343, so always read
  literal values.)
- **"3% increase" framing means New = Old × 1.03** — median
  New/Old = 1.0300. Per-CU outliers up to 2.0725 exist
  (rare; specialty CUs); the loader reads literal values.

</specifics>

<deferred>
## Deferred Ideas

- **Splitting CLAUDE.md Living Ledger into per-entry ADR files**
  (`memory-bank/adr/*.md`) — would close the WARNING from
  `.planning/INGEST-CONFLICTS.md` but is out of v1.0 scope per the
  user's "Subcontractor only" milestone choice. Promote in a
  future milestone if stricter ADR contract enforcement is
  desired.
- **Replacing the existing primary subcontractor file with
  `_ReducedSub`** — current decision (D-14) is additive: 3 files
  per qualifying WR group. If operator workflow proves the primary
  file is redundant on subcontractor sheets, a future phase can
  consolidate. Capturing here so we don't lose the option.
- **Per-variant separate hash buckets** — current decision (D-11)
  is shared bucket with variant token. If operators want
  independent regen control per variant (e.g., regen only
  `_ReducedSub` without touching `_AEPBillable`), a future phase
  can split. Trade-off noted: separate buckets = more state in
  `hash_history.json`, harder to audit.
- **Auto-derived CSV from XLSX (workflow step)** — Smartsheet
  attachment or OneDrive Graph fetch options would eliminate the
  operator's manual CSV-convert step but require external auth
  setup. Out of v1.0; revisit if the manual sync proves a friction
  point.
- **DISCOVERY_CACHE_VERSION bump** — D-21 defers this to plan-phase.
  If the planner determines that subcontractor column-mapping logic
  must change (e.g., new column synonyms recognized), bump in that
  plan. Currently expected NOT needed.
- **Encrypted commit of CSV (git-crypt)** — if the team's
  visibility policy on the CSV changes (e.g., contract data must be
  encrypted at rest in git history), git-crypt is the obvious
  retrofit. Out of v1.0; current policy allows plaintext commit.
- **Phase 2 (DEFERRED) Railway → Render pre-migration ADR** —
  already captured as Phase 2 in ROADMAP.md, does not gate v1.0.

</deferred>

---

*Phase: 1-Subcontractor Rate Logic Modification*
*Context gathered: 2026-05-14*
