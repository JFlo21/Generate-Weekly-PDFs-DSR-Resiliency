---
phase: 260812-isx
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - audit_billing_changes.py
  - tests/test_rate_sanity_audit.py
  - memory-bank/living-ledger.md
autonomous: true
requirements: [QUICK-260812-ISX]
user_setup: []

estimate:
  tokens: 65000
  raw_tokens: 45000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "A row with CU=SAA-DE-20, Work Type=Inst, Quantity=3, Units Total
       Price=341.04 is reported as a rate-sanity mismatch with
       expected_price 170.52 and delta 170.52."
    - "A row with CU=SAA-DE-20, Work Type=Inst, Quantity=1, Units Total
       Price=56.84 is NOT reported."
    - "Rows whose CU is absent from the rates table, whose Quantity is
       zero/missing/unparseable, whose Units Total Price is unparseable,
       or whose Work Type matches none of inst/rem/tran/xfr are counted
       as skipped and never reported as mismatches."
    - "The check never mutates row price, quantity, grouping, filenames,
       hashes, or upload behavior — audit_financial_data returns the same
       rows object it was handed and no pricing path is touched."
    - "Setting RATE_SANITY_AUDIT_ENABLED=false disables the check and
       returns the audit summary to its pre-change shape of counts."
    - "pytest tests/ -v passes with zero regressions."
  artifacts:
    - audit_billing_changes.py
    - tests/test_rate_sanity_audit.py
    - memory-bank/living-ledger.md
  key_links:
    - "audit_financial_data() -> _detect_rate_sanity_mismatches() ->
       audit_results['rate_sanity_mismatches']"
    - "_check_row_rate_sanity() -> lazily-imported generate_weekly_pdfs
       ._SUBCONTRACTOR_RATES (new_install/remove/transfer_price)"
    - "_generate_audit_summary() -> total_rate_sanity_mismatches ->
       risk_level escalation"
---

<objective>
Add a REPORT-ONLY rate-sanity check to the billing audit layer that flags
rows whose Smartsheet `Units Total Price` deviates from
`expected rate x Quantity`, using the New Rates columns of
`data/subcontractor_rates.csv` keyed by CU + Work Type.

Purpose: catch the class of defect proven by the 2026-08-12 incident —
WR 16881353 / Point 27 / CU SAA-DE-20 / Work Type Inst had Quantity
edited 6 -> 3 by the foreman, but the Smartsheet "Install Quantity"
formula cell kept the stale 6, so `Units Total Price` stayed
56.84 x 6 = $341.04 instead of 56.84 x 3 = $170.52. The primary variant
is a pass-through of the Smartsheet price by design, so the pipeline
rendered "3 units @ $341.04" and a $170.52 overbill shipped, caught only
by a foreman's email. The audit layer must detect this automatically.

Output: a new detector in `audit_billing_changes.py`, a new pytest file
with the SAA-DE-20 regression case, and a dated Living Ledger entry.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@.claude/rules/billing-pipeline-guardrails.md
@.claude/skills/investigate-price-anomaly/SKILL.md
@audit_billing_changes.py
@pipeline/pricing.py
@tests/test_subcontractor_pricing.py
</context>

<design_facts>
Verified against the repo before planning — do not re-derive:

1. `pipeline/pricing.py` already owns every primitive needed:
   - `parse_price(value) -> float` (strips `$` and thousands commas,
     coerces non-numeric to 0.0) at L132.
   - `_parse_quantity(value) -> float` (float-first, then decoration
     strip, so `'2 EA'` parses) at L91.
   - `_SUBCONTRACTOR_RATES: dict[str, dict]` at L499 — CU-keyed
     (uppercased), loaded once at module import from
     `SUBCONTRACTOR_RATES_CSV` (default `data/subcontractor_rates.csv`).
     Each value carries `new_install_price`, `new_remove_price`,
     `new_transfer_price` (plus the `reduced_*` trio and audit-only
     `cu_wbs` / `compatible_unit_group`).
   - Verified: `SAA-DE-20` -> group `SAA`, `new_install_price` 56.84,
     `new_remove_price` 17.72, `new_transfer_price` 48.12. This confirms
     the **New Rates** columns are the correct expected-rate source for
     the Smartsheet `Units Total Price` pass-through.
2. Work-type column selection uses the SHORTEST UNAMBIGUOUS PREFIX in
   the `A in B` substring direction, per the [2026-05-16 23:45] ledger
   rule and `pipeline/pricing.py` L667-673:
   `'inst' in wt` -> install, `'rem' in wt` -> remove,
   `'tran' in wt or 'xfr' in wt` -> transfer, else unknown.
   Reproduce this exact matcher; do not use `'install' in wt`.
3. `audit_billing_changes.py` already reads the canonical row keys
   `'Work Request #'`, `'Units Total Price'`, `'Quantity'`, `'CU'`
   in `_validate_data_consistency` (L201+), so the synonyms layer has
   already run by the time the audit sees rows. `'Work Type'` is the
   canonical key for the work-type token.
4. **Import-cycle constraint.** `generate_weekly_pdfs.py` L35 imports
   `audit_billing_changes` BEFORE it imports `pipeline.pricing` at
   L196-210. A module-level `from pipeline.pricing import ...` inside
   `audit_billing_changes.py` would pull the CSV-loading side effect
   earlier in the import order. Therefore the new code MUST use a
   function-local lazy import (`import generate_weekly_pdfs as _gwp`)
   exactly like `pipeline/pricing.py` L629-633 does. This also makes the
   rates table patchable by tests without any testability-driven API
   change.
5. Existing tests rebind the table via
   `generate_weekly_pdfs._SUBCONTRACTOR_RATES.clear()` +
   `.update({...})` in `setUp`, restoring the original in `tearDown`
   (`tests/test_subcontractor_pricing.py` L1861-1877). Mirror that.
6. `BillingAudit.__init__` reads/writes
   `generated_docs/audit_state.json`; `audit_financial_data` also
   appends to `generated_docs/risk_trend.json` and calls
   `_log_to_audit_sheet`. End-to-end tests must neutralize those I/O
   paths rather than let them write real files.
</design_facts>

<tasks>

<task type="tracer" tdd="true">
  <name>Task 1: End-to-end rate-sanity slice — one row, detector, audit result</name>
  <files>audit_billing_changes.py, tests/test_rate_sanity_audit.py</files>
  <behavior>
    - Test 1 (the incident regression): row
      `{'Work Request #': '16881353', 'CU': 'SAA-DE-20',
        'Work Type': 'Inst', 'Quantity': '3',
        'Units Total Price': '$341.04'}` against a patched rates table
      containing `SAA-DE-20` with `new_install_price` 56.84 produces
      exactly one mismatch record whose `expected_price` is 170.52,
      `actual_price` is 341.04, and `delta` is 170.52.
    - Test 2 (clean case): the same row with `Quantity` `'1'` and
      `Units Total Price` `'$56.84'` produces zero mismatch records.
    - Test 3 (end-to-end wiring): `audit_financial_data([], [incident_row])`
      returns a dict whose `rate_sanity_mismatches` list has length 1,
      with `_save_audit_state`, `_log_to_audit_sheet`, and the
      `risk_trend.json` write neutralized (patch the two methods and run
      with `cwd` pointed at a `tempfile.TemporaryDirectory`).
  </behavior>
  <action>
    Write the failing tests first in a NEW file
    `tests/test_rate_sanity_audit.py`, then implement until green.

    Test file shape: `unittest`-based to match the surrounding suite;
    `import generate_weekly_pdfs` at module top and
    `from audit_billing_changes import BillingAudit`. In `setUp`, snapshot
    `dict(generate_weekly_pdfs._SUBCONTRACTOR_RATES)`, `.clear()` it, then
    `.update()` it with a single `SAA-DE-20` entry carrying
    `new_install_price` 56.84, `new_remove_price` 17.72,
    `new_transfer_price` 48.12, `cu_code` `'SAA-DE-20'`,
    `compatible_unit_group` `'SAA'`; restore the snapshot in `tearDown`.
    Construct the audit under test as `BillingAudit(client=None,
    skip_cell_history=True)`. Mirror the setUp/tearDown pattern at
    `tests/test_subcontractor_pricing.py` L1861-1877.

    Implementation in `audit_billing_changes.py`, additive only:

    (a) Add a module-level constant block near the existing imports:
        `RATE_SANITY_ABS_TOLERANCE = 0.02` and
        `RATE_SANITY_PCT_TOLERANCE = 0.005`.

    (b) Add a private module-level function
        `_rate_sanity_expected_price(row: Dict) -> Optional[float]`.
        It performs the function-local lazy import
        `import generate_weekly_pdfs as _gwp` (see design_facts #4),
        reads `_gwp._SUBCONTRACTOR_RATES`, uppercases/strips
        `row.get('CU')`, and returns `None` when the CU is empty or
        absent from the table. It selects the rate column with the
        shortest-prefix matcher from design_facts #2 against
        `str(row.get('Work Type') or '').strip().lower()`, reading
        `new_install_price` / `new_remove_price` / `new_transfer_price`,
        and returns `None` for an unmatched work type. It parses
        quantity via `_gwp._parse_quantity(row.get('Quantity'))` and
        returns `None` when quantity is `<= 0` or the rate is `<= 0`.
        Otherwise it returns `rate * qty`.

    (c) Add a private module-level function
        `_rate_sanity_is_mismatch(expected: float, actual: float) -> bool`
        returning `abs(actual - expected) > max(RATE_SANITY_ABS_TOLERANCE,
        RATE_SANITY_PCT_TOLERANCE * expected)`.

    (d) Add the method
        `_detect_rate_sanity_mismatches(self, rows: List[Dict]) -> List[Dict]`
        to `BillingAudit`. Iterate rows; call
        `_rate_sanity_expected_price(row)`; skip the row silently when it
        returns `None`. Parse the actual price with
        `_gwp.parse_price(row.get('Units Total Price'))`; skip when the
        raw cell is empty/None (an unparseable cell coerces to 0.0 and
        must NOT be reported as a mismatch — treat a raw cell that is
        empty, None, or that `parse_price` maps to 0.0 from a non-zero
        looking string as a skip). When
        `_rate_sanity_is_mismatch(expected, actual)` is true, append a
        record shaped exactly:
        `{"type": "rate_sanity_mismatch", "work_request": <str>,
          "cu": <str>, "work_type": <str>, "quantity": <float>,
          "expected_price": <float rounded to 2>,
          "actual_price": <float rounded to 2>,
          "delta": <float rounded to 2>, "severity": "high",
          "description": <short summary string>}`.
        Wrap the whole body in `try/except Exception` that logs a
        `self.logger.warning` and returns whatever was collected — mirror
        the defensive shape of `_detect_price_anomalies` (L159-197) so a
        detector bug can never abort a production run.

    (e) Wire it into `audit_financial_data` as a new numbered step
        placed immediately after step 2 (`_validate_data_consistency`)
        and before step 3: seed
        `audit_results["rate_sanity_mismatches"] = []` alongside the
        other list keys in the initial dict, then extend it with the
        detector result. Do NOT touch steps 3-7, the pricing paths in
        `pipeline/`, or `generate_weekly_pdfs.py`.

    PEP 8 throughout: type hints on every new signature, PEP 257
    docstrings, lines <= 79 chars (the surrounding legacy code exceeds
    this — new code must not).
  </action>
  <verify>
    <automated>pytest tests/test_rate_sanity_audit.py -v</automated>
  </verify>
  <done>
    The incident row is reported with expected_price 170.52 and delta
    170.52; the clean row is not reported;
    `audit_financial_data` surfaces the record under
    `rate_sanity_mismatches`; `python -m py_compile
    audit_billing_changes.py` exits 0.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Skip semantics, tolerance edges, counters, and kill-switch</name>
  <files>audit_billing_changes.py, tests/test_rate_sanity_audit.py</files>
  <behavior>
    - Missing CU: row with `CU` = `'NOT-IN-TABLE'` -> zero mismatches,
      `rate_sanity_skipped` count 1.
    - Zero / missing / unparseable quantity (`'0'`, `''`, `None`,
      `'abc'`) -> zero mismatches, counted as skipped.
    - Unparseable / empty `Units Total Price` -> zero mismatches,
      counted as skipped (never reported as a $0 expected-vs-actual
      mismatch).
    - Unknown work type (`'Splice'`, `''`) -> zero mismatches, skipped.
    - Rounding tolerance: expected 170.52 vs actual 170.53 -> NOT
      flagged (within the $0.02 floor); expected 170.52 vs actual
      171.00 -> flagged (0.48 exceeds both $0.02 and 0.5% = $0.85...
      assert the correct branch: 0.5% of 170.52 is 0.8526, so 171.00 is
      within tolerance and NOT flagged; use expected 170.52 vs actual
      172.00 for the flagged large-drift case).
    - Decorated quantity `'3 EA'` parses to 3.0 and still flags the
      incident price.
    - `RATE_SANITY_AUDIT_ENABLED=false` -> detector returns an empty
      list, `rate_sanity_mismatches` is empty, and
      `total_rate_sanity_mismatches` is 0.
    - Summary: with one mismatch present, `summary
      ["total_rate_sanity_mismatches"]` is 1 and `summary["risk_level"]`
      is not `"LOW"`.
  </behavior>
  <action>
    Extend `tests/test_rate_sanity_audit.py` with the behaviors above,
    then extend the implementation.

    Implementation changes, all additive:

    (a) Kill-switch. Read the flag inside
        `_detect_rate_sanity_mismatches` (not at import time, so tests
        and operators can toggle it via `os.environ` without a reload):
        `if os.getenv("RATE_SANITY_AUDIT_ENABLED", "true").lower() !=
        "true": return []`. Default-on.

    (b) Skip accounting. Track an integer skip counter inside the
        detector and stash it on the instance as
        `self._rate_sanity_skipped` so `_generate_audit_summary` can
        read it. Skips are silent at row level — emit at most ONE
        aggregate `self.logger.info` line per run with the checked and
        skipped counts, never a per-row log.

    (c) Summary. In `_generate_audit_summary`, add
        `"total_rate_sanity_mismatches": len(audit_results.get(
        "rate_sanity_mismatches", []))` and
        `"rate_sanity_skipped": <counter>` to the returned dict, and
        include the mismatch count in the existing `total_issues` sum
        that drives `risk_level`. Append the recommendation string
        `"Rate-sanity mismatches detected: Smartsheet Units Total Price
        disagrees with rate x Quantity — check for a stale quantity
        formula cell upstream."` when the count is above zero. Leave
        every existing key, threshold, and message untouched.

    (d) Logging discipline. In `_log_audit_results`, add ONE line
        reporting the mismatch count alongside the existing
        `Anomalies:` line. Log counts and the CU code only. Never log
        `Units Total Price`, quantity values, foreman, or description
        text at INFO level — see the threat model below.
  </action>
  <verify>
    <automated>pytest tests/test_rate_sanity_audit.py -v</automated>
  </verify>
  <done>
    Every skip class returns zero mismatches and increments the skip
    counter; the tolerance boundary cases behave as specified;
    `RATE_SANITY_AUDIT_ENABLED=false` fully disables the check; the
    summary carries the two new counters and escalates `risk_level`
    when a mismatch exists.
  </done>
</task>

<task type="auto">
  <name>Task 3: Full-suite regression gate and Living Ledger entry</name>
  <files>memory-bank/living-ledger.md</files>
  <action>
    Run the full gate and confirm zero regressions in the existing
    suite — in particular `tests/test_billing_audit_shadow.py` and
    `tests/test_subcontractor_pricing.py`, which are the two files most
    likely to assert on audit summary shape or on the rates table. If
    any existing test fails, the correct fix is to adjust the NEW code,
    never to relax an existing assertion.

    Then append a dated entry to the BOTTOM of
    `memory-bank/living-ledger.md` per the "Autonomous Cloud Memory
    Injection" rule in `CLAUDE.md`. Use the `[YYYY-MM-DD HH:MM]` stamp
    format already used by the surrounding entries and record: the
    2026-08-12 SAA-DE-20 stale-quantity-formula incident and its
    $170.52 overbill; that the primary variant is a deliberate
    pass-through of the Smartsheet `Units Total Price`, which is why the
    engine could not catch it; the new report-only detector, its
    New-Rates + Work-Type keying, its `max($0.02, 0.5%)` tolerance, its
    skip classes, the `RATE_SANITY_AUDIT_ENABLED` kill-switch; and the
    hard rule that this check is diagnostic only and must never mutate
    price, quantity, grouping, filenames, hashes, or upload behavior.

    Do NOT edit `CLAUDE.md` itself.
  </action>
  <verify>
    <automated>pytest tests/ -v</automated>
  </verify>
  <done>
    `pytest tests/ -v` passes with no regressions versus the
    pre-change baseline, `python -m py_compile
    audit_billing_changes.py` exits 0, and
    `memory-bank/living-ledger.md` ends with the new dated entry.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Smartsheet rows -> audit detector | Operator-entered CU / Work Type / Quantity / price strings reach new parsing code |
| Audit logs -> Sentry / CI logs | Audit output can carry billing row content off-box |
| Rates CSV -> detector | Operator-maintained `data/subcontractor_rates.csv` supplies the expected rate |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-ISX-01 | Information Disclosure | `_detect_rate_sanity_mismatches` logging | medium | mitigate | Task 2(d): aggregate counts + CU code only at INFO; no price, quantity, foreman, or WR-level detail in log bodies. Complements the existing `before_send_log` sanitizer and the `SENTRY_ENABLE_LOGS=false` default |
| T-ISX-02 | Denial of Service | detector inside the production run loop | high | mitigate | Task 1(d): whole detector body wrapped in `try/except Exception` that logs a warning and returns partial results, mirroring `_detect_price_anomalies`; plus the `RATE_SANITY_AUDIT_ENABLED=false` kill-switch from Task 2(a) so it can be disabled without a deploy |
| T-ISX-03 | Tampering | billing pipeline pricing paths | high | mitigate | Report-only contract: no writes to row dicts, no changes to `pipeline/pricing.py`, `pipeline/grouping.py`, `pipeline/excel.py`, `pipeline/upload.py`, or `generate_weekly_pdfs.py`; `files_modified` is limited to the audit module, one new test file, and the ledger |
| T-ISX-04 | Tampering | supply chain | low | accept | No new package-manager installs — every primitive (`parse_price`, `_parse_quantity`, `_SUBCONTRACTOR_RATES`) already exists in `pipeline/pricing.py`; no `requirements.txt` change |
| T-ISX-05 | Repudiation | audit risk trend | low | accept | Escalating `risk_level` when a mismatch exists intentionally changes what `risk_trend.json` and the audit sheet record — that visibility is the point of the change and is reversible via the kill-switch |
</threat_model>

<verification>
1. `pytest tests/test_rate_sanity_audit.py -v` — new tests pass,
   including the SAA-DE-20 regression and the clean case.
2. `pytest tests/ -v` — full suite green, no regressions in
   `test_billing_audit_shadow.py` or `test_subcontractor_pricing.py`.
3. `python -m py_compile audit_billing_changes.py` — exits 0.
4. `git diff --stat` shows changes ONLY in `audit_billing_changes.py`,
   `tests/test_rate_sanity_audit.py`, and
   `memory-bank/living-ledger.md`. Any diff hunk in `pipeline/` or
   `generate_weekly_pdfs.py` is a contract violation — revert it.
5. Optional local smoke, read-only:
   `SKIP_UPLOAD=true WR_FILTER=16881353 python generate_weekly_pdfs.py`
   and confirm the audit section reports the mismatch without changing
   any generated price.
</verification>

<success_criteria>
- The 2026-08-12 SAA-DE-20 case (qty 3, price $341.04, expected
  $170.52) is flagged by the audit layer automatically.
- The clean case (qty 1, price $56.84) is not flagged.
- Missing CU, zero/missing/unparseable quantity, unparseable price, and
  unknown work type are skipped and counted, never flagged.
- Tolerance is `max($0.02, 0.5% of expected)`.
- Zero behavior change to pricing, grouping, hashing, filenames, or
  upload; `git diff` touches three files only.
- `RATE_SANITY_AUDIT_ENABLED=false` restores pre-change audit output.
- `pytest tests/ -v` passes.
- `memory-bank/living-ledger.md` carries a new dated entry.
</success_criteria>

<output>
Create `.planning/quick/260812-isx-add-report-only-rate-sanity-audit-check-/260812-isx-SUMMARY.md`
when done.
</output>
