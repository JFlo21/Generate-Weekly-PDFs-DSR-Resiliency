---
phase: 01-subcontractor-rate-logic-modification
plan: 03
subsystem: python-billing-engine
tags: [python, variants, group-tagging, excel-generation, missing-cu, openpyxl, smartsheet]

# Dependency graph
requires:
  - phase: 01-subcontractor-rate-logic-modification (Plan 01)
    provides: "_SUBCONTRACTOR_RATES module dict, _AEP_BILLABLE_CUTOFF, SUBCONTRACTOR_RATE_VARIANTS_ENABLED kill switch, _FOLDER_DISCOVERED_SUB_IDS / _FOLDER_DISCOVERED_ORIG_IDS sets"
  - phase: 01-subcontractor-rate-logic-modification (Plan 02)
    provides: "build_group_identity round-trip for 4 new filenames, calculate_data_hash SUB_RATES_FP mix-in, _PII_LOG_MARKERS extensions (incl. 'Subcontractor rates CSV missing'), source-side WR-collision pre-scan compatibility"
provides:
  - "group_source_rows emits 4 new group key formats on subcontractor-sheet rows when kill-switch is enabled: {week}_{wr}_REDUCEDSUB (unconditional), {week}_{wr}_AEPBILLABLE (snapshot>=2026-04-12), {week}_{wr}_REDUCEDSUB_HELPER_<sanitized>, {week}_{wr}_AEPBILLABLE_HELPER_<sanitized>"
  - "Per-row gate via row.get('__source_sheet_id') in _FOLDER_DISCOVERED_SUB_IDS — group_source_rows signature stays (rows) (Blocker 3 contract)"
  - "_fetch_and_process_sheet now populates row_data['__source_sheet_id'] alongside the legacy '__sheet_id' field"
  - "_resolve_row_price(row, variant, missing_cus) — module-level helper that reads ONLY canonical keys ('CU', 'Work Type', 'Quantity', 'Units Total Price') and returns rate × qty for the 4 new variants or SmartSheet price for legacy variants / missing CUs (Blocker 2 contract)"
  - "generate_excel produces 4 new variant_suffix filenames (_AEPBillable, _ReducedSub, _AEPBillable_Helper_<sanitized>, _ReducedSub_Helper_<sanitized>) BEFORE the legacy helper / vac_crew / primary branches (D-09 variant-first ordering)"
  - "generate_excel return is now a 5-tuple (excel_path, filename, wr_numbers, customer_name, missing_cus) — Plan 04 Task 2 absorbs the new fields (Blocker 4 cross-plan contract)"
  - "Main loop accumulates per-sheet missing CUs via _missing_cus_by_sheet[int → Counter] and emits exactly ONE WARNING per affected sheet at end of group-processing (D-17), embedding the 'Subcontractor rates CSV missing' marker so _PII_LOG_MARKERS drops the line from Sentry"
  - "5 new test classes pinning the behaviour: TestSubcontractorVariantGrouping (8), TestResolveRowPriceCanonicalColumnNames (9), TestSubcontractorVariantFilenameSuffixes (4), TestSubcontractorVariantPriceSubstitution (4), TestGenerateExcelReturnTupleShape (1), TestSubcontractorMissingCUWarning (1), TestSubcontractorVariantOpenpyxlCompliance (2), TestSubcontractorVariantKillSwitchAndScope (4)"
affects:
  - "01-04-PLAN.md (dual routing) — MUST unpack the new 5-tuple at the upload-task builder; uses customer_name; uses missing_cus only if not consumed earlier (it is, via _missing_cus_by_sheet)"
  - "01-05-PLAN.md (shadow helper) — helper-shadow variants are already wired in group_source_rows and generate_excel; Plan 05's responsibilities concentrate on the upload routing for the shadow files"
  - "01-06-PLAN.md (billing_audit attribution) — variant strings 'aep_billable' / 'reduced_sub' / 'aep_billable_helper' / 'reduced_sub_helper' now flow through __variant tagging and reach billing_audit.pipeline_run when freeze_row(variant=...) is called"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-row gate evaluated against row metadata (__source_sheet_id) instead of threading a sheet-id kwarg through a function whose caller has already merged rows from many sheets — preserves the existing (rows) signature and avoids per-call leakage of variant emission across sheets"
    - "Module-level _resolve_row_price helper invoked exactly ONCE per row via row['__resolved_price'] stash; both the summary and write_day_block iterations read from the stash so the per-call missing_cus Counter is not double-incremented across iterations"
    - "5-tuple return for generate_excel with the new trailing fields (customer_name, missing_cus) appended to the legacy 3-tuple — non-breaking forward extension, both call sites updated in the same commit"
    - "Per-sheet WARNING aggregation pattern: collect missing CUs into dict[sheet_id → Counter], emit exactly ONE WARNING per affected sheet after the group-processing loop (D-17), mirroring the per-sheet 'Rate recalc summary' shape from Living Ledger 2026-04-21 22:35 / 2026-04-23 18:50"
    - "Canonical-column-key-only discipline in _resolve_row_price (Blocker 2): the helper reads ONLY 'CU', 'Work Type', 'Quantity', 'Units Total Price' — synonym mapping is the single responsibility of _validate_single_sheet"

key-files:
  created: []
  modified:
    - "generate_weekly_pdfs.py:
       (a) _resolve_row_price (~L1324-1444): new module-level helper; reads canonical keys only;
       (b) _fetch_and_process_sheet (~L3424): populates row_data['__source_sheet_id'] alongside legacy '__sheet_id';
       (c) group_source_rows (~L3987-4163): new 4-variant emission block inside per-row loop, gated PER-ROW on __source_sheet_id ∈ _FOLDER_DISCOVERED_SUB_IDS AND SUBCONTRACTOR_RATE_VARIANTS_ENABLED; helper-shadow variants gated on the same valid_helper_row + helper_mode_enabled inputs the legacy helper key uses;
       (d) generate_excel (~L4498-4544): 4 new variant_suffix branches BEFORE legacy ones (D-09 variant-first); missing_cus Counter initialized;
       (e) generate_excel (~L4624-4640): per-row price resolution via _resolve_row_price stashed on row['__resolved_price'];
       (f) write_day_block (~L4773-4782): reads stashed __resolved_price (defensive fallback to parse_price for legacy callers);
       (g) generate_excel return (~L4894): new 5-tuple (excel_path, filename, wr_numbers, customer_name, missing_cus);
       (h) main() synthetic call site (~L5099-5114): 5-tuple unpack;
       (i) main loop call site (~L6110-6141): 5-tuple unpack + per-sheet missing-CU attribution into _missing_cus_by_sheet;
       (j) main() per-group init (~L5484-5497): _missing_cus_by_sheet defaultdict;
       (k) main() end-of-group-loop (~L6220-6235): per-sheet WARNING (D-17)"
    - "tests/test_subcontractor_pricing.py:
       TestSubcontractorVariantGrouping (8 tests),
       TestResolveRowPriceCanonicalColumnNames (9 tests),
       TestSubcontractorVariantFilenameSuffixes (4 tests),
       TestSubcontractorVariantPriceSubstitution (4 tests),
       TestGenerateExcelReturnTupleShape (1 test),
       TestSubcontractorMissingCUWarning (1 test),
       TestSubcontractorVariantOpenpyxlCompliance (2 tests),
       TestSubcontractorVariantKillSwitchAndScope (4 tests)"

key-decisions:
  - "Committed Blocker 3 plumbing: group_source_rows signature stays (rows). Per-row gate uses r.get('__source_sheet_id') ∈ _FOLDER_DISCOVERED_SUB_IDS so a single call mixing rows from many sheets cannot accidentally inherit variant emission across rows. The plan's '__source_sheet_id' field was not previously populated by the upstream fetcher — landed as part of Task 1 alongside the legacy '__sheet_id' (no consumer regression)."
  - "Committed Blocker 4 cross-plan contract: generate_excel returns a 5-tuple (excel_path, filename, wr_numbers, customer_name, missing_cus). Both existing call sites (synthetic at L5099-5114 and production at L6110-6121) updated to unpack the new shape so a tuple-shape drift surfaces loudly rather than silently dropping fields."
  - "Committed Blocker 2 canonical-column-name lock-in: _resolve_row_price reads ONLY 'CU', 'Work Type', 'Quantity', 'Units Total Price' — the canonical keys produced by _validate_single_sheet's synonyms layer. Negative-grep regression test asserts the executable body (docstring stripped) does not call row.get(...) against any synonym surface name. Future synonyms MUST be added in _validate_single_sheet."
  - "Per-row price resolution stashed on row['__resolved_price'] so the helper is invoked EXACTLY ONCE per row across the summary + write_day_block iterations. Double-calling the helper would double-increment the missing_cus Counter and inflate the WARNING's CU count by 2×."
  - "Snapshot Date cutoff comparison uses _snap_for_cutoff.date() >= _AEP_BILLABLE_CUTOFF because excel_serial_to_date returns a datetime.datetime but _AEP_BILLABLE_CUTOFF is a datetime.date (RED-phase iteration surfaced the TypeError). Two sites in group_source_rows need this conversion — both fixed."
  - "Per-sheet WARNING emission lives in main() at the end of the group-processing loop, NOT in _fetch_and_process_sheet (where the plan's prose suggested). generate_excel is called from the main loop, not from the fetcher; the sheet attribution must therefore happen at the call site that owns the missing_cus Counter. The WARNING text 'Subcontractor rates CSV missing N CU code(s) on sheet {sid}' matches the stable marker in _PII_LOG_MARKERS so Sentry sanitization is preserved."
  - "Per-sheet attribution falls back to bucket -1 when a row lacks __sheet_id metadata — defensive guard so a malformed row cannot crash the WARNING loop. Realistic rows always have __sheet_id (set by _fetch_and_process_sheet), so this is a safety floor, not a normal path."

patterns-established:
  - "Per-row gate via row metadata: when a feature must be scoped to a subset of sheets but the gating function processes rows already merged across sheets, expose the sheet id on each row (here __source_sheet_id) and gate per-row inside the existing loop. Do NOT change the function's signature to add a per-call sheet-id kwarg — that gates wrongly when the row set is mixed."
  - "Pre-resolve per-row computed values into a row metadata field (here __resolved_price) when the value is consumed by multiple downstream iterators inside the same function call. Eliminates double-counting in any per-call accumulator (here missing_cus Counter) and keeps the workbook's summary in sync with its per-row cells."
  - "5-tuple over 3-tuple for forward-compatible return-shape extension: append new trailing fields rather than refactoring callers to a dict / dataclass mid-phase. The unpack at call sites surfaces drift loudly; downstream plans absorb the new fields by re-naming the placeholders."
  - "Per-sheet aggregator dict[int → Counter] at the loop scope that owns the bookkeeping data — emit ONE summary line per affected sheet at end-of-loop. Mirrors the per-sheet 'Rate recalc summary' WARNING pattern from 2026-04-21 22:35 / 2026-04-23 18:50."

requirements-completed: [SUB-01, SUB-02, SUB-04, SUB-05, SUB-06]

# Metrics
duration: ~13min
completed: 2026-05-14
---

# Phase 01 Plan 03: Variant Emission + Pricing Substitution Summary

**`group_source_rows()` now emits four new subcontractor variant group keys per-row gated on `__source_sheet_id ∈ _FOLDER_DISCOVERED_SUB_IDS` and the kill switch; `generate_excel()` constructs the `_AEPBillable` / `_ReducedSub` / `_AEPBillable_Helper_<sanitized>` / `_ReducedSub_Helper_<sanitized>` filename suffixes and substitutes `rate × qty` from `_SUBCONTRACTOR_RATES` into the workbook via the new module-level `_resolve_row_price` helper that reads ONLY canonical column keys (Blocker 2). The return shape extended to a 5-tuple ending in `(customer_name, missing_cus)` per the Blocker 4 cross-plan contract; the main loop aggregates missing CUs into `_missing_cus_by_sheet` and emits exactly ONE per-sheet WARNING at end-of-group-processing carrying the `'Subcontractor rates CSV missing'` marker so Sentry's `_PII_LOG_MARKERS` sanitizer drops the line before send. ROADMAP success criterion 5 (existing primary / helper / vac_crew outputs byte-identical) is preserved because the legacy variants short-circuit in `_resolve_row_price` and the legacy variant_suffix branches remain unchanged.**

## Performance

- **Duration:** ~13 min (first commit 14:57:19 CDT, final task commit 15:09:47 CDT; SUMMARY commit immediately after)
- **Started:** 2026-05-14T19:57Z (UTC)
- **Completed:** 2026-05-14T20:09Z (UTC)
- **Tasks:** 3 (all autonomous, TDD discipline applied — RED commit before GREEN for the two implementation tasks; Task 3 is regression-only, so GREEN-on-first-run is the expected outcome)
- **Files modified:** 2 (`generate_weekly_pdfs.py`, `tests/test_subcontractor_pricing.py`)
- **Tests added:** 33 net new (full suite: 492 passed / 22 skipped — was 459 / 22 before Plan 03)

## Accomplishments

### Task 1 — `group_source_rows()` extended with per-row variant emission (commits `5306d10` RED + `4fcd561` GREEN)

The new variant block sits immediately after the existing helper-foreman validation branch and before the `for variant, key, current_foreman in keys_to_add:` row-tagging loop. Gate evaluation is PER-ROW on `r.get('__source_sheet_id') in _FOLDER_DISCOVERED_SUB_IDS AND SUBCONTRACTOR_RATE_VARIANTS_ENABLED`. Four group keys are emitted per qualifying row, where applicable:

| Variant token | Group key format | Emission gate |
|---|---|---|
| `reduced_sub` | `{week}_{wr}_REDUCEDSUB` | unconditional on sub row + kill on (D-08 / SUB-02) |
| `aep_billable` | `{week}_{wr}_AEPBILLABLE` | `Snapshot Date >= 2026-04-12` (D-08 / SUB-01) |
| `reduced_sub_helper` | `{week}_{wr}_REDUCEDSUB_HELPER_<sanitized>` | `valid_helper_row AND helper_mode_enabled` shadow on a sub row |
| `aep_billable_helper` | `{week}_{wr}_AEPBILLABLE_HELPER_<sanitized>` | helper-shadow + snapshot cutoff |

Helper names are sanitized via `_RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]` at the producer site (D-22). The idempotent regex permits the consumer in `generate_excel` to re-apply safely. Snapshot cutoff comparison uses `.date()` conversion (`_snap_for_cutoff.date() >= _AEP_BILLABLE_CUTOFF`) because `excel_serial_to_date` returns `datetime.datetime` while `_AEP_BILLABLE_CUTOFF` is `datetime.date`.

One INFO log per first-time emission of each new variant key (`🔻 REDUCED SUB GROUP CREATED` / `💲 AEP BILLABLE GROUP CREATED` / matching HELPER variants) — mirrors the existing `_VACCREW` / `_HELPER` discipline.

`_fetch_and_process_sheet` now populates `row_data['__source_sheet_id'] = source['id']` (~L3424) alongside the legacy `'__sheet_id'` so the new gate has a populated field to read. The legacy field is preserved; no consumer regresses.

`group_source_rows`'s signature stays `(rows)` exactly per Blocker 3 — no caller-side changes at the two existing call sites (synthetic at L5067, main at L5660).

**Test coverage (8 tests in `TestSubcontractorVariantGrouping`):**

1. Post-cutoff sub row → both `_AEPBILLABLE` + `_REDUCEDSUB` keys.
2. Pre-cutoff sub row → `_REDUCEDSUB` only (no `_AEPBILLABLE` — D-08).
3. Helper-foreman event on post-cutoff sub WR → both `_HELPER_<name>` shadow keys.
4. Non-sub sheet row → no new variant keys (per-row gate proof).
5. Kill switch off → no new variant keys (D-13).
6. `__variant` tagging uses the canonical lowercase strings (`'reduced_sub'`, `'aep_billable'`, etc).
7. Helper name with `'` is sanitized to `Jane_O_Brien` before key embedding.
8. Per-row gate does NOT bleed across rows in the same call (regression guard against accidental per-CALL gating).

### Task 2 — `generate_excel()` extended with variant suffixes + price substitution + 5-tuple return (commits `be78852` RED + `80660a3` GREEN)

**Module-level `_resolve_row_price(row, variant, missing_cus) -> float`** at L1324-1444 reads ONLY the four canonical column keys (`'CU'`, `'Work Type'`, `'Quantity'`, `'Units Total Price'`). For `primary` / `helper` / `vac_crew`, returns the row's SmartSheet `Units Total Price` unchanged via `parse_price` (D-14/D-15 byte-identical invariant). For the four subcontractor variants:

- CU lookup in `_SUBCONTRACTOR_RATES`; if absent, the per-call `missing_cus[cu] += 1` AND the helper returns `parse_price(row.get('Units Total Price'))` (D-16 — NEVER zero-out, NEVER raise).
- Work-Type-keyed column selection: `'install' in work_type_raw` / `'remov' in ...` / `'transfer' in ...` (case-insensitive substring match per D-05).
- AEP-Billable variants use `new_{install|remove|transfer}_price`; Reduced-Sub variants use `reduced_*_price`.
- `qty = float(row.get('Quantity') or 0)`; for degenerate `qty <= 0` or `rate <= 0`, fall through to SmartSheet (safety floor).
- Returns `rate × qty`.

**Variant suffix branches in `generate_excel` at L4506-4521** are inserted BEFORE the legacy `helper` / `vac_crew` / `primary` branches per the D-09 variant-first ordering — a `..._AEPBillable_Helper_<name>_<hash>.xlsx` filename parses as `aep_billable_helper`, not as plain `helper` with the AEPBillable token silently dropped.

**Per-row pricing stashed on `row['__resolved_price']`** at L4639 BEFORE the summary aggregation and BEFORE `write_day_block` iterates. Both the workbook's "Total Billed Amount" cell and the per-row Pricing cells in column H read from the stash so they agree, AND the per-call `missing_cus` Counter is incremented exactly once per row.

**Return tuple extended to 5-tuple at L4894:**
```python
return final_output_path, output_filename, wr_numbers, customer_name, missing_cus
```
where `customer_name = first_row.get('Customer Name', '') or ''`. Both existing call sites (synthetic main() path at L5099-5114; production main-loop at L6110-6121) unpack the new shape. Plan 04 Task 2 will absorb the new fields at the upload-task builder.

**Per-sheet WARNING at end-of-group-processing (D-17)** — initialized at L5484 as `_missing_cus_by_sheet: dict[int, collections.Counter]`. Each `generate_excel` call's returned `missing_cus` Counter is attributed to every contributing sheet (via `row['__sheet_id']`); a row with no `__sheet_id` falls back to bucket `-1` so the loop never crashes on malformed metadata. After the per-group loop completes, exactly ONE WARNING per affected sheet (L6224-6235), formatted as:

```
Subcontractor rates CSV missing {N} CU code(s) on sheet {sid}: {first_10_alphabetical}{...}.
Add to {SUBCONTRACTOR_RATES_CSV} to enable rate recalc for these rows.
Sheet rows fell through to SmartSheet pricing.
```

The `'Subcontractor rates CSV missing'` token is the stable marker Plan 02 added to `_PII_LOG_MARKERS`, so the Sentry sanitizer drops these lines from `before_send_log`.

**Test coverage (21 tests across 6 classes):**

- `TestResolveRowPriceCanonicalColumnNames` (9 tests): callable surface; canonical-key Install / Removal / Transfer paths for both AEP-Billable and Reduced-Sub variants; missing-CU fall-through; missing-CU Counter recording; primary/helper/vac_crew variants unchanged regardless of CU presence; the Test-10 negative case where `'Units Completed'` (wrong key) is NOT read as quantity; negative-grep invariant on the executable body for forbidden synonym key reads.
- `TestSubcontractorVariantFilenameSuffixes` (4 tests): each of the 4 new variants produces the expected filename token; helper variants embed sanitized helper names; workbook written to disk verifies.
- `TestSubcontractorVariantPriceSubstitution` (4 tests): workbook column H Pricing cells contain `rate × qty` for sub variants; missing CU keeps SmartSheet price and surfaces in the 5-tuple's `missing_cus`; primary variant unchanged (D-14).
- `TestGenerateExcelReturnTupleShape` (1 test): 5-tuple, `customer_name` populated, `missing_cus` is a `Counter`.
- `TestSubcontractorMissingCUWarning` (1 test): WARNING template embeds the `'Subcontractor rates CSV missing'` marker.
- `TestSubcontractorVariantOpenpyxlCompliance` (2 tests): no `xlsxwriter` import; no `oddFooter.right.text` assignment (only the existing NOTE comment is allowed).

### Task 3 — kill-switch + ORIG-folder no-op regression coverage (commit `60cb4a8`)

Pure regression coverage for invariants Tasks 1 + 2 already satisfy. Four tests passed on first run:

1. `test_kill_switch_disables_new_variant_emission` — `SUBCONTRACTOR_RATE_VARIANTS_ENABLED=False` → no new variant keys (D-13).
2. `test_orig_folder_sheet_emits_no_new_variants` — row with `__source_sheet_id ∈ _FOLDER_DISCOVERED_ORIG_IDS` only → no new variant keys (SUB-06; per-row gate proof).
3. `test_dual_folder_membership_subcontractor_precedence` — sheet misconfigured into BOTH folder sets → per-row gate fires on SUB membership, emits new variants. Documents the cross-reference to Living Ledger 2026-04-24 11:30 (the subcontractor-exclusion check in `_fetch_and_process_sheet` keeps subcontractor flow primary when both sets contain the same id).
4. `test_unparseable_snapshot_date_does_not_emit_aep_billable` — defensive: `excel_serial_to_date('not-a-date')` returns `None`, AEP-Billable cutoff evaluates False, `_REDUCEDSUB` still unconditional.

setUp/tearDown snapshot `SUBCONTRACTOR_RATE_VARIANTS_ENABLED`, `_FOLDER_DISCOVERED_SUB_IDS`, `_FOLDER_DISCOVERED_ORIG_IDS` for test isolation per the 2026-04-22 16:05 ledger rule.

The existing `TestOriginalContractFolderSkipsRateRecalc` regression class (8 tests covering the legacy recalc-skip flow) was re-verified — no regression.

## Task Commits

Five commits in TDD order (RED test commit → GREEN feature commit per implementation task; Task 3 is one test commit since the implementation already satisfied the invariants):

1. **Task 1 RED — failing variant-grouping tests** — `5306d10` (test)
2. **Task 1 GREEN — group_source_rows variant emission** — `4fcd561` (feat)
3. **Task 2 RED — failing generate_excel + price substitution tests** — `be78852` (test)
4. **Task 2 GREEN — _resolve_row_price + variant_suffix + 5-tuple return + per-sheet WARNING** — `80660a3` (feat)
5. **Task 3 — kill-switch + scope regression coverage** — `60cb4a8` (test)

**Plan metadata:** committed alongside this SUMMARY.

## Files Created/Modified

- **`generate_weekly_pdfs.py`** (composite of all changes):
  - **`_resolve_row_price` (new, L1324-1444):** module-level helper that reads canonical column keys only; legacy variants short-circuit; new variants compute `rate × qty` from `_SUBCONTRACTOR_RATES`; missing CU falls through to SmartSheet + records in Counter.
  - **`_fetch_and_process_sheet` (L3424):** populate `row_data['__source_sheet_id']` alongside the legacy `'__sheet_id'`.
  - **`group_source_rows` (L3987-4163):** per-row gate + 4 new variant emission branches inside the existing per-row loop; helper-shadow branches piggyback on the existing `valid_helper_row + helper_mode_enabled` gates.
  - **`generate_excel` (L4498-4521):** 4 new `variant_suffix` branches BEFORE legacy ones (D-09 variant-first).
  - **`generate_excel` (L4540, L4624-4640):** `missing_cus` Counter init + per-row price resolution stashed on `row['__resolved_price']`.
  - **`write_day_block` (L4773-4782):** reads stashed `__resolved_price` (defensive fallback to `parse_price` retained for safety).
  - **`generate_excel` return (L4894):** 5-tuple including `customer_name` and `missing_cus`.
  - **main() synthetic call site (L5099-5114):** 5-tuple unpack.
  - **main() per-group init (L5484-5497):** `_missing_cus_by_sheet: dict[int, collections.Counter]`.
  - **main loop call site (L6110-6141):** 5-tuple unpack + per-sheet missing-CU attribution.
  - **main() end-of-group-loop (L6224-6235):** ONE WARNING per affected sheet (D-17).

- **`tests/test_subcontractor_pricing.py`** — 8 new test classes / 33 net new tests:
  - `TestSubcontractorVariantGrouping` (8): per-row gate / cutoff / kill-switch / sanitization / per-row leak guard.
  - `TestResolveRowPriceCanonicalColumnNames` (9): helper callable + canonical key reads + missing-CU paths + legacy variants unchanged + Blocker 2 negative-grep invariant.
  - `TestSubcontractorVariantFilenameSuffixes` (4): the 4 new filename suffix tokens.
  - `TestSubcontractorVariantPriceSubstitution` (4): workbook on-disk Pricing cells use `rate × qty`; missing CU keeps SmartSheet price; primary unchanged.
  - `TestGenerateExcelReturnTupleShape` (1): 5-tuple contract.
  - `TestSubcontractorMissingCUWarning` (1): WARNING marker present.
  - `TestSubcontractorVariantOpenpyxlCompliance` (2): no xlsxwriter / no oddFooter assignment.
  - `TestSubcontractorVariantKillSwitchAndScope` (4): kill-switch / ORIG-folder / dual-membership / unparseable snapshot.

## Decisions Made

- **Blocker 3 plumbing (committed):** `group_source_rows` keeps its `(rows)` signature; the gate is per-row via `r.get('__source_sheet_id') in _FOLDER_DISCOVERED_SUB_IDS`. The upstream fetcher `_fetch_and_process_sheet` now populates `'__source_sheet_id'` alongside the legacy `'__sheet_id'` so no consumer regresses.
- **Blocker 4 cross-plan contract (committed):** 5-tuple return for `generate_excel`. Both existing call sites updated to unpack the new shape so a future drift surfaces loudly.
- **Blocker 2 canonical-key lock-in (committed):** `_resolve_row_price` reads ONLY `'CU'`, `'Work Type'`, `'Quantity'`, `'Units Total Price'`. The synonym layer is `_validate_single_sheet`'s single responsibility. The negative-grep regression test scans the executable body (docstring stripped) for `row.get('forbidden_key')` patterns so CODE COMMENTS mentioning the synonym set don't false-positive the invariant.
- **Per-row stash for `__resolved_price`.** The pricing helper is invoked EXACTLY ONCE per row across `generate_excel`'s summary + write_day_block iterations. A naive call-twice would double-increment `missing_cus` and inflate the per-sheet WARNING's CU count.
- **`.date()` conversion on the snapshot cutoff comparison.** `excel_serial_to_date` returns `datetime.datetime` but `_AEP_BILLABLE_CUTOFF` is `datetime.date`. Without the conversion, the comparison raises `TypeError`. Caught during RED-phase iteration on Test 1.
- **Per-sheet WARNING lives in `main()`, not `_fetch_and_process_sheet`.** The plan's prose suggested adding the WARNING in the fetcher, but `generate_excel` is called from the main loop after the fetcher returns. The missing-CU bookkeeping data flows back via the 5-tuple, so the sheet-attribution loop must live at the main-loop scope. Each group's missing CUs are attributed to all contributing source sheets via `row['__sheet_id']`. Bucket `-1` is a defensive catch-all for rows without metadata (cannot occur in production with the existing fetcher).
- **Helper-shadow gate re-evaluated locally in the new sub block.** `helper_mode_enabled` and `valid_helper_row` are defined inside the legacy `else:` branch of the `if is_vac_crew_row` cascade. The new variant block lives at the row-loop scope (outside the cascade), so it re-evaluates the same inputs (`is_helper_row`, `helper_foreman`, `__helper_dept`, `RES_GROUPING_MODE`) locally. Mirrors the legacy gate exactly to keep the rule single-sourced in intent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Populate `row_data['__source_sheet_id']` in the upstream fetcher**

- **Found during:** Task 1 (variant emission implementation).
- **Issue:** The plan's `<interfaces>` section declared "The `__source_sheet_id` field is populated by the upstream fetcher (`_fetch_and_process_sheet`) on every row" — but the existing code populated only `row_data['__sheet_id']`, not `__source_sheet_id`. Without the field, the per-row gate would never trigger and the entire new variant pipeline would be a no-op.
- **Fix:** Added `row_data['__source_sheet_id'] = source['id']` immediately after the existing `row_data['__sheet_id'] = source['id']` assignment (~L3424). Kept the legacy `__sheet_id` unchanged so no existing consumer regresses.
- **Files modified:** `generate_weekly_pdfs.py`.
- **Verification:** `TestSubcontractorVariantGrouping::test_non_subcontractor_sheet_emits_no_new_variants` and the corresponding positive-case tests both pass; the per-row gate now fires correctly.
- **Committed in:** `4fcd561` (Task 1 GREEN).

**2. [Rule 1 - Bug] `_snap_for_cutoff.date()` conversion on cutoff comparison**

- **Found during:** Task 1 RED → GREEN iteration. Initial GREEN implementation compared `_snap_for_cutoff >= _AEP_BILLABLE_CUTOFF` directly; `excel_serial_to_date` returns `datetime.datetime` but `_AEP_BILLABLE_CUTOFF` is `datetime.date`, raising `TypeError: '>=' not supported between instances of 'datetime.datetime' and 'datetime.date'`.
- **Issue:** The TypeError caused `group_source_rows` to log a WARNING and skip the row entirely (the outer `try/except (parser.ParserError, TypeError)` swallows it). On a synthetic row in the RED-phase iteration, this caused all tests requiring the gate to fail with empty group dicts.
- **Fix:** Use `_snap_for_cutoff.date() >= _AEP_BILLABLE_CUTOFF` in BOTH sites inside `group_source_rows` (the unconditional ReducedSub block's helper-shadow nested if, and the AEPBillable top-level cutoff check). Confirmed the conversion is idempotent (calling `.date()` on a `datetime.datetime` returns a clean `datetime.date`).
- **Files modified:** `generate_weekly_pdfs.py`.
- **Verification:** All 8 `TestSubcontractorVariantGrouping` tests pass after the fix.
- **Committed in:** `4fcd561` (Task 1 GREEN).

**3. [Rule 1 - Bug] `_resolve_row_price` body scan must strip docstring**

- **Found during:** Task 2 RED → GREEN iteration. The initial negative-invariant test scanned `inspect.getsource(_resolve_row_price)` directly, but the function's docstring intentionally documents the synonym set ("synonyms 'CU' and 'Billable Unit Code' BOTH map to row['CU']..."). The substring `'Billable Unit Code'` appearing in the docstring tripped the negative invariant.
- **Issue:** Without doc-stripping, the test was false-positive on the docstring — but the executable body was correct.
- **Fix:** Strip the function's docstring from the scanned source (via `inspect.getdoc` line-by-line removal), then look for `row.get('forbidden_key')` call patterns specifically (not substring matches that catch comments). A CODE COMMENT mentioning a forbidden token is also acceptable (e.g., `# Canonical 'Quantity' ONLY — never 'Units Completed'`) — the test now only flags actual `row.get(...)` calls.
- **Files modified:** `tests/test_subcontractor_pricing.py`.
- **Verification:** `TestResolveRowPriceCanonicalColumnNames::test_helper_body_does_not_reference_forbidden_keys` passes.
- **Committed in:** `80660a3` (Task 2 GREEN).

**4. [Rule 1 - Bug] Test fixture `__week_ending_date` type must match production**

- **Found during:** Task 2 RED → GREEN iteration on the `TestSubcontractorVariantPriceSubstitution` tests. Initial fixtures set `'__week_ending_date': dt.date(2026, 4, 19)`, but `generate_excel`'s downstream comparison `week_start_date <= dt <= week_end_date` (where `dt` is a `datetime.datetime` from `excel_serial_to_date(snap)` and `week_end_date = week_ending_date`) raised `TypeError` when `week_ending_date` is a `date`.
- **Issue:** Production code at `group_source_rows` L4251 sets `r_copy['__week_ending_date'] = week_ending_date` where `week_ending_date = excel_serial_to_date(log_date_str)` — i.e. a `datetime.datetime`, NOT a `date`. The test fixtures had the wrong type.
- **Fix:** Updated all test fixtures to `__week_ending_date': dt.datetime(2026, 4, 19)` matching the production type. (No production code change needed — this was a test-fixture error.)
- **Files modified:** `tests/test_subcontractor_pricing.py`.
- **Verification:** All 4 `TestSubcontractorVariantPriceSubstitution` tests now pass with the workbook day-block rows populated.
- **Committed in:** `80660a3` (Task 2 GREEN).

**5. [Rule 1 - Bug] `test_no_oddFooter_right_text` was too strict**

- **Found during:** Task 2 RED phase. Initial test rejected ANY occurrence of `'oddFooter.right.text'` in the source, but the existing code already contains a single NOTE comment ("Footer attributes (oddFooter.right.text, etc.) can create malformed XML…") as a forward-compatibility guardrail.
- **Issue:** The acceptance criterion's intent is to ban the *assignment* (the XML corruption vector), not the comment.
- **Fix:** Renamed the test to `test_no_oddFooter_right_text_assignment` and use a regex `r'\.oddFooter\.right\.text\s*='` to ban only the assignment pattern. The comment is preserved.
- **Files modified:** `tests/test_subcontractor_pricing.py`.
- **Verification:** Test passes.
- **Committed in:** `be78852` (Task 2 RED).

---

**Total deviations:** 5 auto-fixed (4 Rule 1 bugs caught during RED→GREEN iteration; 1 Rule 3 blocking — missing `__source_sheet_id` plumbing).

**Impact on plan:** All five auto-fixes were essential to satisfy the plan's own success criteria. Deviation #1 (`__source_sheet_id` population) was the only deviation that crossed the test/production-code boundary — the rest were RED→GREEN iteration corrections inside the same tasks. No scope creep.

## Issues Encountered

- **Plan prose vs. actual scope for the per-sheet WARNING.** The plan's Change 3 ("In `_fetch_and_process_sheet`, after the per-group loop completes…") was descriptively inaccurate — `_fetch_and_process_sheet` does NOT have a per-group loop; it has a per-row loop that builds `sheet_rows`, and `generate_excel` is called from the main loop after the fetcher returns. Resolved by following the plan's INTENT (one WARNING per sheet at end-of-sheet processing) implemented at the architecturally-correct scope (main loop end-of-group-processing phase, where `missing_cus` Counters actually flow back from `generate_excel`).
- **Worktree path confusion at startup.** The worktree's initial HEAD was `8090069` (master tip), but `5d178649` (the phase-01 base) was on a different branch. Per the prompt's `<worktree_branch_check>` step, ran `git reset --hard 5d178649e3a3226ea75691729098cdebc9bfb6ca` to align with the expected base. After that, `.planning/` and all plan files were present and the work proceeded normally.

## User Setup Required

None — Plan 03 changes are entirely internal to `generate_weekly_pdfs.py` and the test suite. No env vars added (Plan 01 already wired `SUBCONTRACTOR_RATE_VARIANTS_ENABLED` and the rates CSV); no operator action required for the variant emission itself.

## Known Stubs

None — every artifact this plan delivered is wired up and exercised by tests:

- The new variant group keys are emitted by `group_source_rows` and round-trip through `build_group_identity` (Plan 02 verified).
- The new variant filenames are written to disk by `generate_excel` with correctly-priced workbook cells (verified by the on-disk workbook inspection in `TestSubcontractorVariantPriceSubstitution`).
- The per-sheet WARNING fires when missing CUs accumulate (verified by the marker presence + the architecturally-tested aggregation path).

The new variant Excel files will only show up in `generated_docs/` on a production-like run with actual subcontractor sheets and the kill switch on. Plan 04 (dual routing) and Plan 05 (shadow helper specifics) absorb the rest of the new tuple-shape and routing decisions.

## Threat Surface Notes

No new threat surface beyond what the plan's `<threat_model>` already enumerated. The 9 STRIDE entries (T-03-01 through T-03-09) are all mitigated:

- **T-03-01 Tampering (filename path traversal in helper names):** `_RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]` applied at both `group_source_rows` (producer) and `generate_excel` (consumer); idempotent.
- **T-03-02 Tampering (price corruption via missing CU):** `_resolve_row_price` fall-through to SmartSheet price (never zero-out, never raise).
- **T-03-03 Information Disclosure (row PII in WARNING):** `'Subcontractor rates CSV missing'` marker already in `_PII_LOG_MARKERS` (Plan 02 commit `25cd303`).
- **T-03-04 DoS (log spam):** Exactly ONE WARNING per sheet, 10-CU truncation bounds log line length.
- **T-03-05 Spoofing (kill switch bypass):** Same env-var surface as existing `RATE_RECALC_*` switches; accepted.
- **T-03-06 Repudiation (variant attribution loss):** Plan 02 round-trip tests cover all 4 new filenames.
- **T-03-07 Tampering (ORIG-folder bleed):** Per-row gate `__source_sheet_id ∈ _FOLDER_DISCOVERED_SUB_IDS AND SUBCONTRACTOR_RATE_VARIANTS_ENABLED`; locked by `TestSubcontractorVariantKillSwitchAndScope::test_orig_folder_sheet_emits_no_new_variants`.
- **T-03-08 Tampering (workbook corruption):** `safe_merge_cells` reused; no new raw `.merge_cells(` calls in `generate_excel`; no `oddFooter.right.text` assignment.
- **T-03-09 Tampering (silent column-name drift):** `_resolve_row_price` reads only canonical keys; `TestResolveRowPriceCanonicalColumnNames::test_helper_body_does_not_reference_forbidden_keys` locks the invariant via doc-stripped body scan + `row.get(...)` call-pattern matching.

## Next Phase Readiness

- **Plan 01-04 (dual routing) is unblocked.** It can now:
  - Unpack `generate_excel`'s 5-tuple at the upload-task builder call site (the production main-loop site at L6110-6121 already does this — Plan 04 will modify the same site to add the second target sheet routing for `_ReducedSub` variants).
  - Use `customer_name` directly from the tuple (no second `first_row.get(...)` lookup needed).
  - Note: `missing_cus` is already consumed in main() at the end-of-group-loop WARNING site — Plan 04 should NOT consume it again or the per-sheet attribution would double-count.
- **Plan 01-05 (shadow helper) is largely unblocked.** The helper-shadow variants are already wired in `group_source_rows` and `generate_excel`; Plan 05's responsibilities concentrate on the dual-target upload routing for the shadow files.
- **Plan 01-06 (billing_audit attribution) is unblocked.** Variant strings `'aep_billable'` / `'reduced_sub'` / `'aep_billable_helper'` / `'reduced_sub_helper'` flow through `__variant` tagging and reach the existing `freeze_row` call sites in the main loop; Plan 06 will extend `freeze_row` with the `variant` kwarg + schema column.
- **No blockers.** Three downstream plans now have the variant-emission + pricing + per-sheet WARNING foundation they need.

## Self-Check

Performed inline before writing this section:

- `git log --oneline 5d178649e3a3226ea75691729098cdebc9bfb6ca..HEAD` shows 5 commits in TDD order: **FOUND** (`5306d10`, `4fcd561`, `be78852`, `80660a3`, `60cb4a8`)
- `grep -nE "_REDUCEDSUB|_AEPBILLABLE" generate_weekly_pdfs.py` returns ≥4 lines (group-key fmt strings + log markers): **FOUND** (~12 lines)
- `grep -nE "REDUCED SUB GROUP CREATED|AEP BILLABLE GROUP CREATED" generate_weekly_pdfs.py` returns ≥2 INFO log lines: **FOUND** (4 lines: 2 in code, 2 in `_PII_LOG_MARKERS`)
- `grep -nE "reduced_sub_helper|aep_billable_helper" generate_weekly_pdfs.py` returns ≥2 `keys_to_add.append` lines: **FOUND** (≥10 lines including parser branches + tagging)
- `grep -nE "is_subcontractor_row and SUBCONTRACTOR_RATE_VARIANTS_ENABLED" generate_weekly_pdfs.py` returns exactly 1 gate: **CONFIRMED** (L4139)
- `grep -nE "variant == 'aep_billable'|variant == 'reduced_sub'|variant == 'aep_billable_helper'|variant == 'reduced_sub_helper'" generate_weekly_pdfs.py` returns ≥4 lines inside `generate_excel`: **CONFIRMED** (L4506, L4508, L4510, L4515)
- `grep -nE "_AEPBillable|_ReducedSub" generate_weekly_pdfs.py` returns ≥4 lines: **CONFIRMED** (≥15 lines)
- `grep -nE "_resolve_row_price|missing_cus\[" generate_weekly_pdfs.py` returns ≥2 hits: **CONFIRMED** (≥5 hits)
- Canonical-column-name positive invariant: `row.get('CU')`, `row.get('Quantity')`, `row.get('Work Type')`, `row.get('Units Total Price')` all present in `_resolve_row_price`: **CONFIRMED**
- Canonical-column-name negative invariant (body, docstring stripped): no `row.get('Billable Unit Code')` / `row.get('Units Completed')` / `row.get('Qty')` / `row.get('# Units')` / `row.get('Total Price')` / `row.get('Redlined Total Price')`: **CONFIRMED**
- `grep -nE "Subcontractor rates CSV missing" generate_weekly_pdfs.py` returns exactly one WARNING-level log line + one `_PII_LOG_MARKERS` entry: **CONFIRMED** (L781 marker + L6232 WARNING)
- `grep -c "xlsxwriter" generate_weekly_pdfs.py` returns 0: **CONFIRMED**
- `grep -c "oddFooter.right.text" generate_weekly_pdfs.py` returns 1 (NOTE comment only; no assignment): **CONFIRMED** (comment-only; the assertion negative-grep is on the `\.oddFooter\.right\.text\s*=` ASSIGNMENT pattern which returns 0 occurrences)
- Return shape: `grep -nE "return final_output_path, output_filename, wr_numbers, customer_name, missing_cus" generate_weekly_pdfs.py` returns exactly 1 match: **CONFIRMED** (L4894)
- `python -c "import inspect, generate_weekly_pdfs as g; sig = inspect.signature(g.group_source_rows); params = list(sig.parameters); assert params == ['rows']"` exits 0: **CONFIRMED** (Blocker 3 signature unchanged)
- `python -m py_compile generate_weekly_pdfs.py` exits 0: **CONFIRMED**
- `pytest tests/test_subcontractor_pricing.py::TestSubcontractorVariantGrouping -v` reports 8 passed: **CONFIRMED**
- `pytest tests/test_subcontractor_pricing.py::TestResolveRowPriceCanonicalColumnNames tests/test_subcontractor_pricing.py::TestSubcontractorVariantFilenameSuffixes tests/test_subcontractor_pricing.py::TestSubcontractorVariantPriceSubstitution tests/test_subcontractor_pricing.py::TestGenerateExcelReturnTupleShape tests/test_subcontractor_pricing.py::TestSubcontractorMissingCUWarning tests/test_subcontractor_pricing.py::TestSubcontractorVariantOpenpyxlCompliance` reports 21 passed: **CONFIRMED**
- `pytest tests/test_subcontractor_pricing.py::TestSubcontractorVariantKillSwitchAndScope -v` reports 4 passed: **CONFIRMED**
- `pytest tests/test_subcontractor_pricing.py::TestOriginalContractFolderSkipsRateRecalc -v` exits 0 (no regression on existing class): **CONFIRMED**
- `pytest tests/test_vac_crew.py::TestVacCrewGroupingLogic -v` exits 0 (no regression on legacy variant tagging): **CONFIRMED** (5 passed)
- `pytest tests/` full suite reports 492 passed / 22 skipped / 0 failed: **CONFIRMED**

## Self-Check: PASSED

## TDD Gate Compliance

The two implementation tasks followed the RED/GREEN cycle with separate commits; Task 3 is regression-only:

| Task | RED commit (test) | GREEN commit (feat) |
|------|-------------------|---------------------|
| 1 (variant emission) | `5306d10 test(01-03): add failing variant-grouping tests for subcontractor` | `4fcd561 feat(01-03): emit subcontractor variant group keys in group_source_rows` |
| 2 (variant suffix + price substitution + 5-tuple) | `be78852 test(01-03): add failing tests for generate_excel variant + price substitution` | `80660a3 feat(01-03): substitute subcontractor rates in generate_excel + 5-tuple return` |
| 3 (regression-only — invariants already satisfied by Tasks 1+2) | `60cb4a8 test(01-03): pin kill-switch + ORIG-folder no-op + dual-membership invariants` | n/a (no new behaviour; tests pass on first run) |

Each RED commit was verified to FAIL the new tests (6/2 for Task 1; 18/3 for Task 2) before the corresponding GREEN commit was made. Task 3's 4 tests passed on first run because Tasks 1 + 2 already implement the kill-switch / per-row-gate / dual-folder-precedence / unparseable-snapshot semantics correctly.

---

*Phase: 01-subcontractor-rate-logic-modification*
*Plan: 03*
*Completed: 2026-05-14*
