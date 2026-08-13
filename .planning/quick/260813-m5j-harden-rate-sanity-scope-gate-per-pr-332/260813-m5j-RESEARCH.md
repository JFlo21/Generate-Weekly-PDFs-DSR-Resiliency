# Quick Task 260813-m5j: Harden rate-sanity scope gate (PR #332 review) — Research

**Researched:** 2026-08-13
**Domain:** In-repo billing-audit scoping (`audit_billing_changes._rate_sanity_in_scope`)
**Confidence:** HIGH (all findings are in-repo, read this session with file:line + verbatim quotes)

## Summary

**F2 as literally written must NOT be implemented.** The SAA-DE-20 incident sheet
("Resiliency Promax Database Backup 86", id `1824542300262276`) is **NOT** a
subcontractor-folder sheet. Restricting rate-sanity scope to subcontractor membership
would drop 110 of 115 discovered sheets — including the one sheet the detector was built
to catch — leaving the audit blind to the exact defect class it exists for.

F2's *underlying* concern is real but has **inverted polarity**. The wrong-basis rows are
the **subcontractor** rows, not the original-contract rows: `new_*_price` in
`data/subcontractor_rates.csv` is the *New Rates* (AEP/prime) column, which is the basis
the Smartsheet ProMax sheets bill under post-cutoff; subcontractor-folder rows carry a
`Units Total Price` at the *Subcontractor Rates* basis (`reduced_*_price`, ~$49.66 vs
$56.84 for SAA-DE-20 = a systematic 12.6% false delta, far beyond the 0.5% tolerance).
So the correct gate **excludes `__is_subcontractor` rows**, keeps everything else.

**F1 is a real but currently-latent hole** — 0 of 115 discovered sheets lack a
`Snapshot Date` column mapping today, so no production row is mis-classified right now.
The fix is cheap, mirrors the production caller exactly, and fails closed.

**Primary recommendation:** change `_rate_sanity_in_scope` to (1) return out-of-scope for
`row['__is_subcontractor']`, (2) gate `weekly_fallback_enabled` on the row's sheet
actually mapping a `Snapshot Date` column — sourced from the `source_sheets`
`column_mapping` metadata the audit already receives. Both inputs already exist per-row /
per-call; **no new plumbing into fetch/grouping/pricing is required.**

---

## Q1 (CRITICAL) — Folder family of the SAA-DE-20 incident sheet

**The incident sheet is NOT a subcontractor sheet.**

`generated_docs/discovery_cache.json` (schema v4, timestamp `2026-08-12T18:20:12.855207`,
115 sheets) queried this session
[VERIFIED: generated_docs/discovery_cache.json, queried 2026-08-13]:

```
Backup86 has Snapshot Date: True
Backup86 sub member: False
sub sheets: [(3386072353427332, 'Intake Promax'),
             (6733767264653188, 'Arrowhead Resiliency Promax Database 4'),
             (6894278950211460, 'Arrowhead Resiliency Promax Database Backup 1'),
             (8099347251023748, 'Arrowhead Resiliency Promax Database 2'),
             (8766162968989572, 'Arrowhead Resiliency Promax Database 3')]
MATCH {'id': 1824542300262276, 'name': 'Resiliency Promax Database Backup 86'} in_subids False
```

Only **5 of 115** cached sheets are subcontractor members; the remaining 110 are
`Resiliency Promax Database [Backup N]` / `Intake Promax N` sheets. The incident row
(WR 91916464 / Point 27) lives on one of those 110
[VERIFIED: memory-bank/living-ledger.md:5228-5229 — *"on \"Resiliency Promax Database
Backup 86\" the row's `Quantity` was loaded as 6 on 2026-07-07"*].

The cached `subcontractor_sheet_ids` field is written from the post-merge
`SUBCONTRACTOR_SHEET_IDS` set
[VERIFIED: pipeline/discovery.py:679-680 — `'sheets': discovered,` /
`'subcontractor_sheet_ids': sorted(SUBCONTRACTOR_SHEET_IDS),`], which is
`env ∪ _FOLDER_DISCOVERED_SUB_IDS`
[VERIFIED: pipeline/discovery.py:213 — `SUBCONTRACTOR_SHEET_IDS = SUBCONTRACTOR_SHEET_IDS | _FOLDER_DISCOVERED_SUB_IDS`],
i.e. a **superset** of the `_FOLDER_DISCOVERED_SUB_IDS` set F2 proposes gating on.
Backup 86 is outside the superset, therefore outside the subset. **Proof complete.**

**Verdict: F2's proposed restriction is rejected as written.** Implementing it would
regress the detector to zero coverage of the incident class.

## Q2 — Rate basis per sheet family

| CSV column (`data/subcontractor_rates.csv`) | Loaded key | Consumer |
|---|---|---|
| `Install Price (Subcontractor Rates)` | `reduced_install_price` | `reduced_sub*` variants + pre-acceptance rescue |
| `Install Price (New Rates)` | `new_install_price` | `aep_billable*` variants + **the rate-sanity detector** |

[VERIFIED: pipeline/pricing.py:403-413, 437-441 — `_cell(row, 'Install Price (Subcontractor Rates)', 0))` → `'reduced_install_price': reduced_install,`; `_cell(row, 'Install Price (New Rates)', 0))` → `'new_install_price': new_install,`]

SAA-DE-20 row, verbatim
[VERIFIED: data/subcontractor_rates.csv:2748]:
`CU-2747 , SAA-DE-20 , EA , "SAA,DE Clamp #4-2/0" , SAA , 0.2720 , 0.1600 , 0.4000 , $49.66 , $15.48 , $42.05 , $55.18 , $17.20 , $46.72 , $56.84 , $17.72 , $48.12`
→ Subcontractor `$49.66` · Old `$55.18` · **New `$56.84`**.

The ledger states the correct incident price was `3 × $56.84 = $170.52`, from
*"Resiliency Pricing Contract - Corpus/Laredo/Rio, group SAA new install = 56.84"*
[VERIFIED: memory-bank/living-ledger.md:5226-5235]. **The Smartsheet-native
original-contract price for a post-cutoff ProMax row equals the CSV New Rates column.**
That equality is the detector's whole premise and it holds for the incident row.

**Group-code-keyed `NEW_RATES_CSV` path is INACTIVE in production**
[VERIFIED: .github/workflows/weekly-excel-generation.yml:314-316]:
```yaml
          RATE_CUTOFF_DATE: ''
          NEW_RATES_CSV: ''
          OLD_RATES_CSV: ''
```
With `RATE_CUTOFF_DATE` empty, `recalculate_row_price` never runs and
`RATE_RECALC_SKIP_ORIGINAL_CONTRACT` is moot
[VERIFIED: pipeline/fetch.py:375-379 — `if (RATE_CUTOFF_DATE and _rate_new_primary and not is_subcontractor_sheet and not _skip_recalc_original_contract):`].
So the CU-keyed `_SUBCONTRACTOR_RATES` table is the **only** live New-Rates basis, and the
Q2 note in the brief ("Smartsheet emits authoritative Units Total Price natively for
ORIGINAL_CONTRACT post-cutoff rows") resolves to: **at New Rates** — same basis the
detector uses. Correct pairing.

**Subcontractor rows are the wrong-basis population.** `_resolve_row_price` passes
`Units Total Price` straight through for every legacy variant
[VERIFIED: pipeline/pricing.py:636-641 — `if variant not in ('aep_billable', 'reduced_sub', 'aep_billable_helper', 'reduced_sub_helper',): return parse_price(row.get('Units Total Price'))`],
and on subcontractor sheets that pass-through value is the sub-rate price — or is
**overwritten in place** with `reduced_* × qty`
[VERIFIED: pipeline/fetch.py:472-481 — `_rescued = _subcontractor_rescue_price(row_data)` … `row_data['Units Total Price'] = _rescued`;
pipeline/pricing.py:545 — `rate = rate_row.get('reduced_install_price', 0.0)`].
Comparing those against `new_*_price` is a guaranteed false mismatch.

## Q3 — How grouping gates `_AEPBillable`, and availability at the audit call site

[VERIFIED: pipeline/grouping.py:521-525]
```python
            _row_sheet_id = r.get('__source_sheet_id')
            is_subcontractor_row = (
                _row_sheet_id is not None
                and _row_sheet_id in _discovery._FOLDER_DISCOVERED_SUB_IDS
            )
```
[VERIFIED: pipeline/grouping.py:766]
`            if is_subcontractor_row and not is_vac_crew_row and SUBCONTRACTOR_RATE_VARIANTS_ENABLED:`
with the date half at [VERIFIED: pipeline/grouping.py:876] —
`                        and _snap_for_cutoff.date() >= _AEP_BILLABLE_CUTOFF`.

**The audit runs BEFORE grouping** [VERIFIED: pipeline/orchestrate.py:554 —
`                    audit_results = audit_system.audit_financial_data(source_sheets, all_rows)`].
`_FOLDER_DISCOVERED_SUB_IDS` *is* populated by then (folder discovery runs unconditionally
at the top of `discover_source_sheets`, before cache load
[VERIFIED: pipeline/discovery.py:211-217]), so importing it would technically work — **but
it is not needed.** Two cleaner, already-present sources exist:

1. **Per-row flags, set on every accepted row** [VERIFIED: pipeline/fetch.py:624-625]:
```python
                            row_data['__is_vac_crew'] = is_vac_crew_row
                            row_data['__is_subcontractor'] = is_subcontractor_sheet
```
   where `is_subcontractor_sheet = source['id'] in SUBCONTRACTOR_SHEET_IDS`
   [VERIFIED: pipeline/fetch.py:190] — the **superset** of `_FOLDER_DISCOVERED_SUB_IDS`,
   so using it excludes at least as much as grouping's gate (fails safe for exclusion).
   Rows also carry `__source_sheet_id` [VERIFIED: pipeline/fetch.py:330-331 —
   `row_data['__source_sheet_id'] = source['id']` / `row_data['__row_id'] = row.id`].

2. **`source_sheets` entries**, already passed to `audit_financial_data`
   [VERIFIED: audit_billing_changes.py:213 —
   `    def audit_financial_data(self, source_sheets: List[Dict], current_rows: List[Dict]) -> Dict:`]
   and already consumed by `_detect_suspicious_changes(source_sheets)`
   [VERIFIED: audit_billing_changes.py:257]. Each entry is exactly
   [VERIFIED: pipeline/discovery.py:615]:
   `                return {'id': sid,'name': sheet.name,'column_mapping': mapping}`
   — **id + name + column_mapping. No folder-family field.** This is the right source for
   the F1 half (column presence), not for folder family.

## Q4 — F1: the production caller pattern, and how the audit can replicate it

Production caller [VERIFIED: pipeline/fetch.py:276]:
`                sheet_has_snapshot_date_column = 'Snapshot Date' in column_mapping`
[VERIFIED: pipeline/fetch.py:389-402]
```python
                            effective_cutoff_date, _recalc_via_fallback = (
                                _resolve_rate_recalc_cutoff_date(
                                    row_data,
                                    RATE_CUTOFF_DATE,
                                    weekly_fallback_enabled=(
                                        RATE_RECALC_WEEKLY_FALLBACK
                                        and sheet_has_snapshot_date_column
                                    ),
                                )
                            )
```
The audit currently omits the kwarg entirely, defaulting to `True`
[VERIFIED: audit_billing_changes.py:101-104]:
```python
    effective_date, _used_fallback = _resolve_rate_recalc_cutoff_date(
        row, _gwp._AEP_BILLABLE_CUTOFF
    )
    return effective_date is not None
```
against [VERIFIED: pipeline/utils.py:77-82] `weekly_fallback_enabled: bool = True,` and
[VERIFIED: pipeline/utils.py:119] `    if snap_date is None and weekly_fallback_enabled:`.

**Key omission confirmed:** `row_data` only ever receives keys for *mapped* columns
[VERIFIED: pipeline/fetch.py:307-313]:
```python
                    for cell in row.cells:
                        mapped_name = reverse_column_map.get(cell.column_id)
                        if mapped_name:
                            raw_val = getattr(cell, 'value', None)
                            if raw_val is None:
                                raw_val = getattr(cell, 'display_value', None)
                            row_data[mapped_name] = raw_val
```
So a sheet with no `Snapshot Date` mapping produces rows with the key **absent**
(`.get()` → `None`), exactly as F1 describes.

**How the audit can know:** build `{sheet_id: 'Snapshot Date' in column_mapping}` from
`source_sheets` and look it up by `row['__source_sheet_id']`.

**Current live exposure: ZERO.** All 115 cached sheets map `Snapshot Date`
[VERIFIED: generated_docs/discovery_cache.json, queried 2026-08-13 —
`sheets WITHOUT Snapshot Date mapping: 0`]. F1 is a **latent** defect: it activates the
moment a legacy sheet without that column enters discovery. Fix it anyway — it is 3 lines
and it fails closed.

## Q5 — VAC rows

VAC detection is **row-level by column presence**, not folder membership
[VERIFIED: pipeline/fetch.py:602-607 — `if sheet_has_vac_crew_columns:` … `is_vac_crew_row = bool(vac_crew_name and vac_crew_completed_checked and units_completed_checked)`],
surfaced as `row_data['__is_vac_crew']` [VERIFIED: pipeline/fetch.py:624]. `VAC_CREW_FOLDER_IDS`
is retired/empty [VERIFIED: pipeline/config.py:299 —
`VAC_CREW_FOLDER_IDS = _parse_sheet_ids(os.getenv('VAC_CREW_FOLDER_IDS', ''))`, preceded by
`# VAC Crew detection is now row-level (column-presence-based, no folder/sheet ID config needed).`].

**VAC rows do NOT bill under `_SUBCONTRACTOR_RATES`.** `vac_crew` is not in the four
subcontractor-variant names, so it takes the pass-through branch
[VERIFIED: pipeline/pricing.py:636-641, quoted above]. A VAC row on a non-subcontractor
ProMax sheet therefore carries the **same Smartsheet-native New-Rates price as a primary
row** — same basis, same stale-formula exposure.

Grouping's `not is_vac_crew_row` exclusion at line 766 is a **double-emission guard**, not
a basis statement [VERIFIED: pipeline/grouping.py:761-765 —
*"without this gate it would be DOUBLE-emitted (VACCREW + REDUCEDSUB/AEPBILLABLE)"*].
Importing it into a report-only detector would lose real coverage.

**Recommendation: keep non-subcontractor VAC rows IN scope.** VAC rows on subcontractor
sheets are excluded automatically by the `__is_subcontractor` gate. Confidence MEDIUM —
this is the one judgment call; pin it with an explicit regression test either way.

---

## Recommended design (ONE gate, no new plumbing)

```python
def _rate_sanity_snapshot_column_index(
    source_sheets: Optional[List[Dict]],
) -> Dict[int, bool]:
    """Map sheet id -> whether that sheet maps a 'Snapshot Date' column.

    Mirrors the production recalc caller's ``sheet_has_snapshot_date_column``
    (pipeline/fetch.py:276) using the ``column_mapping`` already carried by
    every ``source_sheets`` entry (pipeline/discovery.py:615).
    """
    index: Dict[int, bool] = {}
    for source in source_sheets or []:
        sheet_id = source.get('id')
        mapping = source.get('column_mapping') or {}
        if isinstance(sheet_id, int):
            index[sheet_id] = 'Snapshot Date' in mapping
    return index


def _rate_sanity_in_scope(
    row: Dict,
    snapshot_column_index: Optional[Dict[int, bool]] = None,
) -> Tuple[bool, str]:
    """Return (in_scope, out_of_scope_reason).

    Reason is '' when in scope; otherwise one of
    'subcontractor_basis' | 'pre_cutoff_or_undated'.
    """
    import generate_weekly_pdfs as _gwp                       # noqa: PLC0415
    from pipeline.utils import _resolve_rate_recalc_cutoff_date  # noqa: PLC0415

    # F2 (correct polarity): subcontractor-sheet rows bill at the
    # Subcontractor-Rates basis (reduced_*_price / rescue overwrite at
    # pipeline/fetch.py:477), NOT the New-Rates basis this detector
    # compares against. Checking them is a guaranteed false mismatch.
    # NOTE: this deliberately does NOT restrict scope TO subcontractor
    # sheets — the SAA-DE-20 incident sheet is a non-subcontractor
    # ProMax sheet and MUST stay in scope.
    if row.get('__is_subcontractor'):
        return (False, 'subcontractor_basis')

    # F1: the Weekly-Ref-Date fallback is only meaningful on sheets that
    # actually map Snapshot Date (pipeline/fetch.py:276, 398-400).
    # Fail closed: unknown sheet / no metadata -> snapshot-only.
    sheet_id = row.get('__source_sheet_id')
    weekly_fallback_enabled = bool(
        snapshot_column_index and snapshot_column_index.get(sheet_id, False)
    )

    effective_date, _used_fallback = _resolve_rate_recalc_cutoff_date(
        row,
        _gwp._AEP_BILLABLE_CUTOFF,
        weekly_fallback_enabled=weekly_fallback_enabled,
    )
    if effective_date is None:
        return (False, 'pre_cutoff_or_undated')
    return (True, '')
```

Wiring (audit-only, report-only preserved):

- `_detect_rate_sanity_mismatches(self, rows, source_sheets=None)` — optional kwarg keeps
  the ~30 existing direct-call tests compiling; `audit_financial_data` passes its own
  `source_sheets` at the call site [audit_billing_changes.py:248-250].
- Build the index **once per call**, before the row loop (O(115), not O(200k)).
- Counter semantics **extended, never removed**: keep `self._rate_sanity_out_of_scope`
  as the running total (and the `"rate_sanity_out_of_scope"` summary key at
  audit_billing_changes.py:557) exactly as-is; add
  `self._rate_sanity_out_of_scope_by_reason: Dict[str, int]` and include the two reason
  counts in the single aggregate INFO line at audit_billing_changes.py:487-492.
- Untouched: `RATE_SANITY_AUDIT_ENABLED` kill-switch read at line 430; out-of-scope-before-
  skip precedence at lines 439-441; the risk ladder; grouping / pricing / upload / fetch.

**Why not a new `row_data['__sheet_has_snapshot_date']` flag in fetch.py:** it would put a
pipeline-behavior edit inside a report-only audit task. (For the record, it would *not*
break change detection — `calculate_data_hash` uses an explicit field whitelist, not
`row.keys()` [VERIFIED: pipeline/change_detection.py:44-130] — but the audit-only route is
strictly smaller blast radius and is preferred.)

## Provable incident-row survival

The incident row is in scope under the recommended gate:
`__is_subcontractor` = `False` (Backup 86 ∉ the 5-member sub set, Q1) →
sheet maps `Snapshot Date` = `True` (Q1 output) → snapshot branch, not fallback →
`Snapshot Date 2026-08-09 >= _AEP_BILLABLE_CUTOFF` (`datetime.date(2026, 4, 12)`
[VERIFIED: generate_weekly_pdfs.py:278-284], unset in the workflow
[VERIFIED: .github/workflows/weekly-excel-generation.yml:509-511 — *"AEP_BILLABLE_CUTOFF is
intentionally UNSET in the workflow"*]) → **in scope**, and
`3 × $56.84 = $170.52 vs $341.04` still trips
`_rate_sanity_is_mismatch` [audit_billing_changes.py:107-118].

## Required regression tests

Existing suite: `tests/test_rate_sanity_audit.py` (496 lines, ~32 tests; scope tests at
L403-472). Add to that file, same `RateSanityTestBase` fixture pattern.

| # | Case | Row fixture | Expect |
|---|---|---|---|
| R1 | **Incident row survives F2 fix** (anti-regression) | incident row + `__is_subcontractor: False`, `__source_sheet_id: 1824542300262276`, `Snapshot Date: '2026-08-09'`, index `{1824542300262276: True}` | 1 mismatch, expected 170.52 |
| R2 | Subcontractor-sheet row, sub-rate price | `__is_subcontractor: True`, `Units Total Price: '$49.66'`, qty 1, post-cutoff | 0 mismatches; `out_of_scope == 1`, reason `subcontractor_basis` |
| R3 | Subcontractor-sheet row that *would* mismatch | `__is_subcontractor: True`, `$341.04`, qty 3, post-cutoff | 0 mismatches (proves the gate, not the tolerance, does the work) |
| R4 | **VAC row on non-sub sheet stays IN scope** | `__is_vac_crew: True`, `__is_subcontractor: False`, incident numbers | 1 mismatch (pins the Q5 decision) |
| R5 | VAC row on sub sheet | `__is_vac_crew: True`, `__is_subcontractor: True` | 0 mismatches, out-of-scope |
| R6 | **No-snapshot-column sheet** (F1) | no `Snapshot Date` key, `Weekly Reference Logged Date: '2026-08-09'`, index `{sid: False}` | 0 mismatches; out-of-scope `pre_cutoff_or_undated` |
| R7 | Snapshot-column sheet, fallback preserved | same row, index `{sid: True}` | 1 mismatch (fallback still rescues automation-lag rows) |
| R8 | Unknown / missing `__source_sheet_id` | blank snapshot + post-cutoff weekly, sid absent from index | out-of-scope (fail-closed) |
| R9 | Legacy call `source_sheets=None` | snapshot-dated post-cutoff row | still flagged (snapshot branch needs no index) |
| R10 | Counter contract | mixed batch | `summary['rate_sanity_out_of_scope']` present, unchanged key name, == sum of reason breakdown |

**Existing test that must be updated:** `test_blank_snapshot_with_post_cutoff_weekly_is_in_scope`
(tests/test_rate_sanity_audit.py:416) relies on the default-`True` fallback and will fail
under fail-closed defaults — supply `source_sheets` metadata (this becomes R7). Audit the
other L403-472 scope tests for the same dependency before coding.

## Constraints honored

- Report-only: no row mutation, no writes to pricing/grouping/excel/upload/fetch.
- `RATE_SANITY_AUDIT_ENABLED` kill-switch untouched (audit_billing_changes.py:430).
- `rate_sanity_out_of_scope` counter + summary key extended, never removed.
- PEP 8 / ≤79 cols / full type hints (`Optional[List[Dict]]`, `Dict[int, bool]`, `Tuple[bool, str]`).
- Scope stays coupled to `AEP_BILLABLE_CUTOFF` per the standing ledger rule
  [VERIFIED: memory-bank/living-ledger.md:5506-5510 — *"Do not re-point the scope at a new
  env var."*]. No new env var.

## Open questions

1. **VAC-on-non-sub inclusion (MEDIUM).** Evidence says same basis → keep in scope. If the
   operator prefers conservatism, exclude with reason `vac_crew_variant` and pin R4
   inverted — either way the decision must be a test, not a default.
2. **Arrowhead 10% discount.** `ARROWHEAD_DISCOUNT = 0.90` [pipeline/pricing.py:48] applies
   only to the group-keyed table that is inactive in production; not a factor for the
   `_SUBCONTRACTOR_RATES` path. No action, noted so the planner does not re-derive it.

## Sources

- Primary (HIGH): `audit_billing_changes.py`, `pipeline/{utils,fetch,grouping,pricing,discovery,config,change_detection,orchestrate}.py`, `generate_weekly_pdfs.py`, `data/subcontractor_rates.csv`, `generated_docs/discovery_cache.json`, `.github/workflows/weekly-excel-generation.yml`, `tests/test_rate_sanity_audit.py` — all read this session.
- Primary (HIGH): `memory-bank/living-ledger.md` entries [2026-08-12 13:40], [2026-08-12 14:05], [2026-08-13 15:30].
- No external sources used; no packages added.
