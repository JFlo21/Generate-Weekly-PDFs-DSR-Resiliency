# Subcontractor Contract Rate File — Schema Capture

Captured 2026-05-14 from the operator-supplied file
`CU List - Corpus North & South.xlsx` (local-only, gitignored per
`.gitignore:93` `*.xlsx`). Source-of-truth for the upcoming Phase 1
Subcontractor Rate Logic Modification.

## File Identity

- **Local path:** repo root: `CU List - Corpus North & South.xlsx`
- **Size:** ~377 KB
- **Status:** gitignored (`*.xlsx`) — must NOT be committed; contains
  proprietary contract pricing
- **Sheets:** 2
  - `'CU List - Corpus North _ South'` — 4849 rows × 17 cols (header + 4848 data rows)
  - `'Comments'` — 1 row × 1 col (effectively empty; loader should ignore)

## Column Schema (17 columns, row 1 = header)

| # | Header                                | Role                              |
|---|---------------------------------------|-----------------------------------|
| 1 | `CU WBS #`                            | Sequential identifier (`CU-1`…`CU-4848`); audit-only |
| 2 | `CU`                                  | **CU code — the join key** (e.g. `ALB-6-AUR1`, `ADDITEM-ROW-PURCHASE`) |
| 3 | `Unit Of Measure`                     | Informational (e.g. `EA`) |
| 4 | `Description`                         | Informational |
| 5 | `Compatible Unit Group`               | Informational (e.g. `LB`, `MO`, `APL`, `XRD-NI`) |
| 6 | `Install Hours`                       | Labor estimate; not used for pricing |
| 7 | `Removal Hours`                       | Labor estimate; not used for pricing |
| 8 | `Transfer Hours`                      | Labor estimate; not used for pricing |
| 9 | **`Install Price (Subcontractor Rates)`** | **`_ReducedSub` variant — what Linetec pays subs (13% off New)** |
| 10 | **`Removal Price (Subcontractor Rates)`** | reduced |
| 11 | **`Transfer Price (Subcontractor Rates)`** | reduced |
| 12 | `Install Price (Old Rates)`           | Pre-2026-04-12 contract; reference/audit only |
| 13 | `Removal Price (Old Rates)`           | reference/audit |
| 14 | `Transfer Price (Old Rates)`          | reference/audit |
| 15 | **`Install Price (New Rates)`**       | **`_AEPBillable` variant — 3% increase, awarded 2026-04-12** |
| 16 | **`Removal Price (New Rates)`**       | new |
| 17 | **`Transfer Price (New Rates)`**      | new |

This **exactly matches** the design intent: 3 reduced + 3 original + 3
new = 9 priced columns, indexed by CU code. Plus 8 context columns
(WBS, description, UoM, group, hours) carried for operator clarity.

## Rate Math (Validated Across 4848 Rows)

| Metric                        | Median   | Min      | Max      | Notes |
|-------------------------------|----------|----------|----------|-------|
| `New / Old` (Install)         | 1.0300   | 1.0244   | 2.0725   | 3% increase holds for the bulk; **some CUs have non-3% deltas** |
| `Reduced / New` (Install)     | 0.8738   | 0.4343   | 0.8786   | ~12.6% off (≈ "13% reduction"); **some CUs are deeply discounted** |
| Rows with zero `Old Install`  | 1058 / 4848 (21.8%) — placeholder / inactive CUs |

### Implications for the loader

- **Do NOT compute `reduced = old × 0.87` in code.** ~5–10% of CUs have
  non-standard ratios (the min `Reduced/New = 0.4343` is a real outlier,
  not noise). Always read the literal values from the file.
- **Do NOT compute `new = old × 1.03` in code.** Same reason; the min
  `New/Old = 1.0244` shows per-CU variance.
- **Handle zero prices gracefully.** 21.8% of rows have zero `Old`
  pricing (e.g. `CU-4846 XRD-NI22` is all-zero). The loader MUST:
  - Skip zero-price CUs from the "missing CU" WARNING summary (they're
    legitimately blank in the contract, not loader gaps).
  - Never raise `ZeroDivisionError` on ratio computations (none should
    happen anyway given the "read literally" rule above).
- **Handle `N/A` hour values.** Row 2 (`ADDITEM-ROW-PURCHASE`) has
  string `'N/A'` in Install/Removal/Transfer Hours columns — the
  loader doesn't use those columns for pricing, but if a future code
  path tries to read them it must coerce safely.

## Loader Contract (Pre-Plan Specification)

The Phase 1 plan should specify a loader API roughly shaped like:

```python
# billing_rates_contract.py (new module — name TBD in plan-phase)

@dataclass(frozen=True)
class SubcontractorRateRow:
    cu_code: str           # column 2
    cu_wbs: str            # column 1 (audit-only)
    compatible_unit_group: str  # column 5 (audit-only)
    reduced_install: float    # column 9
    reduced_removal: float    # column 10
    reduced_transfer: float   # column 11
    new_install: float        # column 15
    new_removal: float        # column 16
    new_transfer: float       # column 17
    # Old prices intentionally NOT stored (reference-only; loading them
    # invites accidental code reuse and creates a 3rd authoritative
    # source of truth).

def load_subcontractor_rates(path: str) -> dict[str, SubcontractorRateRow]:
    """Return CU-code → rate row mapping. Skip rows with all-zero pricing."""
```

Open questions for `/gsd-discuss-phase 1`:

1. **Where does the file live?** Options:
   - Repo root (as today) — but it's gitignored, so CI/Actions runs
     can't see it. Would need to ingest via GitHub Secrets or an
     uploaded artifact. **Recommended: a non-XLSX format committed to
     the repo, since GitHub Actions needs the data.**
   - A CSV companion (`data/subcontractor_rates.csv`) auto-generated
     from the XLSX whenever the operator updates it — would let CI
     read it while keeping the original XLSX local-only.
   - Encrypted via `git-crypt` or `git-secret` and committed — adds
     ops complexity but gives auditable versioning.
   - Stored in a GCP/S3 bucket and fetched at workflow startup — best
     audit trail; requires bucket setup.
2. **Versioning / staleness detection.** Currently no version column
   in the file. Options:
   - Hash the loaded data into a `_RATES_FINGERPRINT_CONTRACT` value
     (replaces the retired `_RATES_FINGERPRINT`) — bump the discovery
     cache version on fingerprint change so column mappings re-validate.
   - Add a `Version` cell to the file (e.g. cell A1 or a metadata
     sheet) and surface it in the startup banner.
3. **`Old Rates` columns 12–14.** Keep loading them for audit logging
   (deltas in Sentry breadcrumbs), or omit entirely?
4. **Missing-CU WARNING summary.** When a Smartsheet row's CU isn't in
   the loaded table, fire the same per-sheet WARNING pattern used in
   the retired CSV-side recalc (2026-04-21 22:35 ledger). Threshold
   for log spam — `WARNING` per sheet (count + first-N CUs) vs every
   row?
5. **Cutoff column for `_AEPBillable`.** Confirmed: `Snapshot Date >=
   2026-04-12` per ledger 2026-04-21 22:35 guardrail. The
   `_AEPBillable` file ONLY exists for rows past that cutoff;
   `_ReducedSub` is cutoff-independent.

## Cross-References

- Project file inventory: `.planning/intel/context.md`
- Locked rules that bind the loader:
  `.planning/intel/decisions.md` (ledger entries 2026-04-21 22:35,
  2026-04-22 18:30, 2026-04-23 12:00, 2026-04-24 11:30, 2026-04-24
  14:30)
- Existing subcontractor pricing SPEC:
  `.github/instructions/subcontractor-pricing-folder-discovery.instructions.md`
- Constraints affecting the loader:
  `.planning/intel/constraints.md` (subcontractor pricing contract
  block; discovery-cache invariants; change-detection key composition)
- Variant routing (where the generated files land):
  `.planning/REQUIREMENTS.md` (SUB-01 through SUB-07)
