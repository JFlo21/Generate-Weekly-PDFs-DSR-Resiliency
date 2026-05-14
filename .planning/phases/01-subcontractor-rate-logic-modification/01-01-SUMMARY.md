---
phase: 01-subcontractor-rate-logic-modification
plan: 01
subsystem: python-billing-engine
tags: [python, csv-loader, env-vars, fingerprint, subcontractor, openpyxl, smartsheet]

# Dependency graph
requires: []
provides:
  - "data/subcontractor_rates.csv at canonical path (17 columns, 4848 rows, currency-formatted, history preserved via git mv)"
  - "load_subcontractor_rates(filepath) -> dict[str, dict] — CU-keyed loader with currency / BOM / zero-row / N/A tolerance"
  - "_compute_subcontractor_rates_fingerprint(dict) -> str — deterministic 16-char SHA256 prefix"
  - "Module-level _SUBCONTRACTOR_RATES and _SUBCONTRACTOR_RATES_FINGERPRINT populated once at import"
  - "SUBCONTRACTOR_RATES_CSV env var (default data/subcontractor_rates.csv, _sanitize_csv_path resolved)"
  - "SUBCONTRACTOR_PPP_SHEET_ID env var (default 8162920222379908, _coerce_sheet_id parsed)"
  - "SUBCONTRACTOR_RATE_VARIANTS_ENABLED default-on kill switch"
  - "_AEP_BILLABLE_CUTOFF = datetime.date(2026, 4, 12) module constant"
  - "Startup banner emits ENABLED / DISABLED state + loaded-CU count + fingerprint"
  - "TestLoadSubcontractorRates regression class (8 tests covering D-04..D-07 + D-20)"
affects:
  - "01-02-PLAN.md (parser extension) — reads _SUBCONTRACTOR_RATES + _AEP_BILLABLE_CUTOFF; mixes _SUBCONTRACTOR_RATES_FINGERPRINT into the hash key for the two new variants"
  - "01-03-PLAN.md (variant emission) — reads _SUBCONTRACTOR_RATES to compute Units Total Price for _AEPBillable / _ReducedSub rows; gates _AEPBillable emission on _AEP_BILLABLE_CUTOFF"
  - "01-04-PLAN.md (dual routing) — reads SUBCONTRACTOR_PPP_SHEET_ID to route _ReducedSub uploads to the second target sheet"
  - "01-05-PLAN.md (shadow helper) — same _SUBCONTRACTOR_RATES dict drives _AEPBillable_Helper_<name> and _ReducedSub_Helper_<name>"
  - "01-06-PLAN.md (billing_audit attribution) — variant string emitted to billing_audit.pipeline_run includes aep_billable / reduced_sub / aep_billable_helper / reduced_sub_helper"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "operator-managed CSV with _sanitize_csv_path env-var resolution (mirrors retired NEW_RATES_CSV ergonomics)"
    - "module-init rate loader + 16-char sha256 fingerprint (mirrors load_rate_versions + _compute_rates_fingerprint)"
    - "fail-safe loader contract (returns {} on any error, never raises into caller)"
    - "default-on kill switch with startup-banner state log (mirrors RATE_RECALC_SKIP_ORIGINAL_CONTRACT and RATE_RECALC_WEEKLY_FALLBACK)"

key-files:
  created:
    - "data/subcontractor_rates.csv"
  modified:
    - "generate_weekly_pdfs.py — env-var block (L429-445), startup banner (L495-507), loader + fingerprint + module-level invocation (L1059-1307), _AEP_BILLABLE_CUTOFF module constant"
    - "tests/test_subcontractor_pricing.py — TestLoadSubcontractorRates regression class + canonical SUBCONTRACTOR_HEADERS module constant"

key-decisions:
  - "Loader carries csv.DictReader(f, skipinitialspace=True) — required because the operator-supplied CSV has space-padded fields that break Python's csv quote recognition without it"
  - "Header matching strips whitespace via _strip_csv_fieldnames so the operator's padded headers (' CU                       ') map to the canonical 'CU' key"
  - "Rename + content overhaul split into two commits (chore(01-01) git mv, then feat(01-01) content + env vars) so git log --follow traces through both — single-commit overhaul would have fallen below git's rename-similarity threshold and lost history"
  - "Loader's INFO log emits only an integer count + filepath, not row content — no _PII_LOG_MARKERS extension required per D-22"
  - "Module-level _SUBCONTRACTOR_RATES is empty when SUBCONTRACTOR_RATE_VARIANTS_ENABLED is false — every downstream consumer must short-circuit on the empty-dict path to behave identically to pre-Phase-1"

patterns-established:
  - "skipinitialspace=True is the canonical fix for operator-padded CSVs — any future loader reading this file format must also set it"
  - "_strip_csv_fieldnames helper for tolerant header matching — reusable for any future loader on the same CSV"
  - "Two-commit rename pattern when a file's content changes >95% in the same logical step (commit 1: pure rename for --follow; commit 2: content overhaul)"
  - "Module-level rate-table + fingerprint pair, gated by a kill-switch env var, with startup-banner state log"

requirements-completed: [SUB-04, SUB-06]

# Metrics
duration: ~30min
completed: 2026-05-14
---

# Phase 01 Plan 01: Subcontractor Rate Logic Modification — Foundation Summary

**Subcontractor rate matrix loader + env-var scaffolding lands the 17-column CSV at `data/subcontractor_rates.csv`, exposes `load_subcontractor_rates()` + 16-char fingerprint helper at module init, and wires `SUBCONTRACTOR_RATES_CSV` / `SUBCONTRACTOR_PPP_SHEET_ID` / `SUBCONTRACTOR_RATE_VARIANTS_ENABLED` env vars so Plans 2-6 can build on a tested foundation.**

## Performance

- **Duration:** ~30 min (first commit 14:21:56 CDT, final task commit 14:28:06 CDT, SUMMARY commit after)
- **Started:** 2026-05-14T19:20Z (UTC, derived from first task commit + repo timezone)
- **Completed:** 2026-05-14T19:28Z (final task commit; SUMMARY commit immediately after)
- **Tasks:** 3 (all autonomous, TDD discipline applied)
- **Files modified:** 3 (`generate_weekly_pdfs.py`, `tests/test_subcontractor_pricing.py`, `data/subcontractor_rates.csv` renamed + content-replaced)

## Accomplishments

- **17-column subcontractor rates CSV at `data/subcontractor_rates.csv`** — 4848 data rows, currency-formatted prices, `git log --follow` traces back through the legacy `CU List - Corpus North & South.csv` history at the old repo-root path.
- **`load_subcontractor_rates(filepath)` loader** — produces a CU-keyed dict of 9 literal fields per row from the real CSV. Successfully loads **3691 priced CUs** from the operator-supplied file (close to the plan's "~3790" estimate; difference is the all-zero placeholder rows that the D-04 zero-skip rule excludes). Fail-safe: returns `{}` on any error.
- **`_compute_subcontractor_rates_fingerprint(rates_dict)` helper** — deterministic 16-char SHA256 prefix over the six priced fields of every CU; sorted-keys discipline guarantees byte-identical output for byte-identical input regardless of dict insertion order.
- **Module-level `_SUBCONTRACTOR_RATES` + `_SUBCONTRACTOR_RATES_FINGERPRINT`** — populated once at import time so the downstream variant pipeline (Plans 2-6) can read them directly without re-parsing the CSV per WR group. Real fingerprint emitted on import: `e4941a5e86c4f8ce`.
- **Three new env vars wired and logged** in the startup banner: `SUBCONTRACTOR_RATES_CSV`, `SUBCONTRACTOR_PPP_SHEET_ID`, `SUBCONTRACTOR_RATE_VARIANTS_ENABLED`. `_AEP_BILLABLE_CUTOFF = 2026-04-12` exposed as a module constant for Plans 2 + 3.
- **`TestLoadSubcontractorRates` regression class** — 8 tests covering D-04 (currency, BOM, zero-skip, N/A in hours), D-06 (no Old-Rates keys leak), D-07 (literal per-CU values, no `× 0.87` / `× 1.03` shortcuts), D-20 (fingerprint determinism + sensitivity). All 8 pass; total suite is 426 passed / 22 skipped.

## Task Commits

Each task was committed atomically. Task 1 produced two commits because the rename + 11→17 column content overhaul fell below git's rename-similarity threshold when combined; splitting preserved `git log --follow` traversal.

1. **Task 1a: git mv legacy CSV to canonical path** — `d25fb07` (chore)
2. **Task 1b: seed 17-column subcontractor CSV content + env-var block + `_AEP_BILLABLE_CUTOFF`** — `f3e3d2c` (feat)
3. **Task 2: `load_subcontractor_rates` + `_compute_subcontractor_rates_fingerprint` + module-level invocation** — `6a0973a` (feat)
4. **Task 3: `TestLoadSubcontractorRates` regression class (8 tests)** — `eb4216e` (test)

**Plan metadata:** committed alongside this SUMMARY.

## Files Created/Modified

- `data/subcontractor_rates.csv` — 17-column subcontractor rate matrix (4848 data rows + header). Replaces the legacy 11-column `CU List - Corpus North & South.csv` at the old repo-root location. Git history preserved via two-commit rename pattern.
- `generate_weekly_pdfs.py`:
  - **Env-var block (L429-445):** `SUBCONTRACTOR_RATES_CSV`, `SUBCONTRACTOR_PPP_SHEET_ID`, `SUBCONTRACTOR_RATE_VARIANTS_ENABLED`, plus `_AEP_BILLABLE_CUTOFF = datetime.date(2026, 4, 12)`.
  - **Startup banner (L495-507):** new INFO log line stating the resolved state of the three env vars.
  - **Loader section (L1059-1307):** `_SUBCONTRACTOR_RATES_REQUIRED_HEADERS` frozenset, `_strip_csv_fieldnames` helper, `load_subcontractor_rates` loader, `_compute_subcontractor_rates_fingerprint` helper, module-level `_SUBCONTRACTOR_RATES` + `_SUBCONTRACTOR_RATES_FINGERPRINT` invocation, and a follow-up banner line emitting the loaded CU count + fingerprint.
- `tests/test_subcontractor_pricing.py`:
  - **`SUBCONTRACTOR_HEADERS` module constant (L155-172):** canonical 17-column header pinned for all fixtures.
  - **`TestLoadSubcontractorRates` class (L175-432):** 8 tests covering D-04..D-07 + D-20.

## Decisions Made

- **Two-commit rename pattern (Task 1).** The 11→17 column overhaul is too large for git's default rename detection (the new content is <5% similar to the old). Splitting Task 1 into a pure `git mv` commit (`d25fb07`) followed by the content + env-var commit (`f3e3d2c`) preserves `git log --follow` traversal back to the original `d9e3603 Add dual-contract CSV rate files` commit, satisfying the plan's acceptance criterion for preserved history.
- **`skipinitialspace=True` on the CSV reader (Task 2).** The operator-supplied CSV is space-padded in every field. Without `skipinitialspace=True`, the leading space before quoted descriptions (` "Additional Item, Right of Way, Purchase"`) breaks Python's csv quote recognition and silently 2-column-shifts every value to the right. See Deviations section for full incident detail.
- **`_strip_csv_fieldnames` helper (Task 2).** The operator's padded headers (`' CU                       '`) require whitespace stripping before they can match the canonical `'CU'` key in the REQUIRED set. Encapsulated in a small helper so a future loader on the same file format can reuse the same stripped-form → raw-form mapping pattern.
- **Module-level loader invocation gated by `SUBCONTRACTOR_RATE_VARIANTS_ENABLED` (Task 2).** When the kill switch is off, `_SUBCONTRACTOR_RATES` is the empty dict and `_SUBCONTRACTOR_RATES_FINGERPRINT` is the empty string. Every downstream consumer in Plans 2-6 MUST short-circuit on the empty-dict path so the pipeline behaves identically to pre-Phase-1 when operators flip the switch off in an emergency.
- **Loader's INFO log emits no row content.** Just an integer count + filepath. Per D-22 / Living Ledger 2026-04-20 12:00 (`SENTRY_ENABLE_LOGS` sanitizer): no `_PII_LOG_MARKERS` extension required, no privacy regression risk.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added `skipinitialspace=True` to the CSV reader in `load_subcontractor_rates`**

- **Found during:** Task 2 (loader implementation) — initial smoke test against the real `data/subcontractor_rates.csv` returned wrong values for `ALB-6-AUR1` (`reduced_install_price=0.176` instead of the literal `$45.95`).
- **Issue:** The plan's loader template did not specify `skipinitialspace=True`. The operator-supplied CSV is space-padded in every field (`CU-1    , ADDITEM-ROW-PURCHASE     , EA             , "Additional Item, Right of Way, Purchase"   , ...`). Without `skipinitialspace=True`, Python's csv module does NOT recognize the `"` as a quote delimiter (because of the leading space before it), so the description's internal commas are treated as field separators. This silently 2-column-shifts every value to the right for every row whose Description contains a comma. The symptom seen was every priced cell containing the wrong column's data — a direct silent-corruption trap for the billing pipeline if downstream plans had consumed `_SUBCONTRACTOR_RATES` as-is.
- **Fix:** Added `csv.DictReader(f, skipinitialspace=True)` to the loader and documented the rationale in a long inline comment so a future reviewer doesn't strip the flag thinking it's cosmetic.
- **Files modified:** `generate_weekly_pdfs.py` (loader internals).
- **Verification:** Re-ran the smoke test against the real CSV; `ALB-6-AUR1` now correctly resolves to `reduced_install_price=45.95`, `reduced_remove_price=33.33`, `reduced_transfer_price=106.54`, `new_install_price=52.58`, `new_remove_price=38.14`, `new_transfer_price=121.93` — matches the raw CSV row exactly. Loader count went from 4028 (corrupted) to 3691 (correct, after the all-zero placeholder skip rule applies cleanly to properly-parsed rows).
- **Committed in:** `6a0973a` (Task 2 commit).

**2. [Rule 2 - Missing Critical] Added `_strip_csv_fieldnames` helper for whitespace-tolerant header matching**

- **Found during:** Task 2 (loader implementation) — the operator's CSV headers are space-padded (`' CU                       '`) so a strict-equality match in the loader's REQUIRED set check would fail.
- **Issue:** The plan's loader template used `if missing := REQUIRED - fieldnames: ...` against the raw fieldnames. Without whitespace tolerance, the header check would always fail on the real CSV and the loader would return `{}`, silently disabling the entire downstream variant pipeline.
- **Fix:** Added `_strip_csv_fieldnames(fieldnames) -> dict[str, str]` returning a stripped-form → raw-form mapping. The loader does the REQUIRED check against the stripped keys, then uses the raw form to actually fetch each cell value via `row.get(raw)`.
- **Files modified:** `generate_weekly_pdfs.py` (loader internals).
- **Verification:** All 8 new tests in `TestLoadSubcontractorRates` pass (using unpadded headers via `csv.writer`), and the real CSV now loads 3691 CUs correctly.
- **Committed in:** `6a0973a` (Task 2 commit, same as deviation #1).

**3. [Rule 1 - Bug] Two-commit split for Task 1 (rename + content)**

- **Found during:** Task 1 — staging the rename + 17-column content overhaul as a single commit caused `git diff --cached --stat` to show `delete + create` instead of `rename`, because the new file content is <5% similar to the legacy 11-column CSV. Git's rename detection threshold is not satisfied.
- **Issue:** The plan's acceptance criterion mandates `git log --follow data/subcontractor_rates.csv` showing pre-rename history. A combined commit would have broken `--follow` traversal, defeating the entire "preserve git history" intent.
- **Fix:** Split Task 1 into two commits:
  - `d25fb07 chore(01-01): git mv subcontractor rates CSV to canonical path` — pure rename (99% similar, detected by git).
  - `f3e3d2c feat(01-01): seed subcontractor rates CSV content and env-var block` — content overhaul + env-var block.
- **Verification:** `git log --follow --oneline data/subcontractor_rates.csv` now correctly shows `f3e3d2c → d25fb07 → d9e3603 (original CSV add)`.
- **Committed in:** `d25fb07` + `f3e3d2c` (Task 1's two commits).

---

**Total deviations:** 3 auto-fixed (2 Rule 1 bugs, 1 Rule 2 missing-critical).
**Impact on plan:** All three were essential to satisfy the plan's own acceptance criteria. The `skipinitialspace` + `_strip_csv_fieldnames` pair are correctness requirements without which the loader silently produces wrong data on the real operator file — both are exactly the kind of "missing critical functionality" Rule 1 / Rule 2 exist to auto-fix. The two-commit Task 1 split is the only path to satisfy the `--follow` acceptance criterion given the 11→17 column content overhaul. No scope creep.

## Issues Encountered

- **Operator CSV format quirks.** The `CU List - Corpus North & South.csv` file is space-padded in every field AND has unquoted leading spaces before quoted descriptions, which together break standard Python `csv.DictReader` parsing. Resolved via `skipinitialspace=True` + `_strip_csv_fieldnames`. Both are documented inline so a future reviewer doesn't strip them.
- **IDE language-server cache lag on test file.** After adding `TestLoadSubcontractorRates`, the Pylance/Pyright language server flagged `generate_weekly_pdfs.load_subcontractor_rates` and `_compute_subcontractor_rates_fingerprint` as "not a known attribute" — false positive due to stale module index. Runtime imports (`pytest`) succeed; all 8 new tests pass.

## User Setup Required

None — no external service configuration required. All changes are local to the repo (`data/subcontractor_rates.csv` is committed; env vars have sensible defaults that work without operator action).

## Known Stubs

None — every artifact this plan delivered is wired up. `_SUBCONTRACTOR_RATES` is populated from the real CSV at module init, `_SUBCONTRACTOR_RATES_FINGERPRINT` is computed deterministically, and the env vars are read at startup. The downstream consumers (parser extension in Plan 2, variant emission in Plan 3, dual routing in Plan 4) do not yet exist — but that's expected, they're the next plans on the wave.

## Threat Surface Notes

No new threat surface beyond what the plan's `<threat_model>` already enumerated:

- **T-01-01 Tampering (CSV).** Mitigated by git tracking; loader's fail-safe contract caps blast radius if a malformed CSV is committed (returns `{}` → downstream short-circuits).
- **T-01-02 Information Disclosure.** Mitigated; loader's INFO log emits only `len(rates)` + filepath. No `_PII_LOG_MARKERS` extension required.
- **T-01-03 Path traversal via `SUBCONTRACTOR_RATES_CSV`.** Mitigated by `_sanitize_csv_path` (resolved through the same helper as the retired `NEW_RATES_CSV`).
- **T-01-04 DoS via memory footprint.** Accepted; CSV is ~377 KB, in-memory dict is ~3691 entries × 9 fields = bounded.
- **T-01-05 Spoofing via `SUBCONTRACTOR_PPP_SHEET_ID`.** Mitigated by `_coerce_sheet_id` parse-error fallback.

## Next Phase Readiness

- **Plan 01-02 (parser extension) is unblocked.** It can now read `_SUBCONTRACTOR_RATES` directly and reference `_AEP_BILLABLE_CUTOFF` for the hash-key gating; the per-variant fingerprint mix-in (D-20) can mix `_SUBCONTRACTOR_RATES_FINGERPRINT` into the hash key for `_AEPBillable` / `_ReducedSub` variants without bumping `DISCOVERY_CACHE_VERSION` (D-21).
- **Plans 01-03 (variant emission) and 01-04 (dual routing) are unblocked.** They can read `SUBCONTRACTOR_PPP_SHEET_ID` and `_SUBCONTRACTOR_RATES` directly.
- **No blockers.** The downstream parser / generator / routing plans now have a tested, documented foundation to build on.

## Self-Check

Performed inline before writing this section:
- `data/subcontractor_rates.csv` exists at canonical path: **FOUND**
- `CU List - Corpus North & South.csv` removed from repo root: **CONFIRMED**
- `d25fb07` (Task 1a rename commit) exists in `git log --all`: **FOUND**
- `f3e3d2c` (Task 1b content commit) exists in `git log --all`: **FOUND**
- `6a0973a` (Task 2 loader commit) exists in `git log --all`: **FOUND**
- `eb4216e` (Task 3 test commit) exists in `git log --all`: **FOUND**
- `load_subcontractor_rates` is callable on imported module: **CONFIRMED**
- `_compute_subcontractor_rates_fingerprint` is callable on imported module: **CONFIRMED**
- `_SUBCONTRACTOR_RATES` populated with 3691 entries: **CONFIRMED**
- `_SUBCONTRACTOR_RATES_FINGERPRINT == 'e4941a5e86c4f8ce'`: **CONFIRMED**
- `_AEP_BILLABLE_CUTOFF.isoformat() == '2026-04-12'`: **CONFIRMED**
- `SUBCONTRACTOR_RATES_CSV` ends with `subcontractor_rates.csv`: **CONFIRMED**
- `SUBCONTRACTOR_PPP_SHEET_ID == 8162920222379908`: **CONFIRMED**
- `SUBCONTRACTOR_RATE_VARIANTS_ENABLED is True`: **CONFIRMED**
- `pytest tests/test_subcontractor_pricing.py -v` shows 100 passed (92 existing + 8 new): **CONFIRMED**
- `pytest tests/` shows 426 passed / 22 skipped / 0 failed: **CONFIRMED**
- `python -m py_compile generate_weekly_pdfs.py` exits 0: **CONFIRMED**

## Self-Check: PASSED

---

*Phase: 01-subcontractor-rate-logic-modification*
*Plan: 01*
*Completed: 2026-05-14*
