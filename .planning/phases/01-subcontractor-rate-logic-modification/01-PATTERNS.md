# Phase 1: Subcontractor Rate Logic Modification — Pattern Map

**Mapped:** 2026-05-14
**Files analyzed:** 10 (4 new/renamed, 6 modified)
**Analogs found:** 10 / 10

This document tells the planner exactly which lines of existing code each
new code path must mirror. Concrete excerpts replace abstract guidance:
every "Copy from..." pointer carries file path + line range, and the
analog selection is driven by the role + data-flow ranking criteria in
the GSD mapper spec (variant-aware helper / VAC-crew code is the closest
analog for every new code path in this phase, per CONTEXT D-09/D-10/D-11).

---

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `data/subcontractor_rates.csv` (renamed via `git mv` from `CU List - Corpus North & South.csv`) | data | file-I/O (input) | `New Contract Rates copy regenerated again.csv` (legacy CSV) | exact (operator-managed contract CSV) |
| `generate_weekly_pdfs.py` § new loader (`load_subcontractor_rates`) | utility | file-I/O / transform | `load_contract_rates()` L909-933, `_compute_rates_fingerprint()` L997-1003 | exact (CSV → CU-keyed rate dict + SHA256 fingerprint) |
| `generate_weekly_pdfs.py` § new env-var block (`SUBCONTRACTOR_RATES_CSV`, `SUBCONTRACTOR_PPP_SHEET_ID`, `SUBCONTRACTOR_RATE_VARIANTS_ENABLED`) | config | startup | `RATE_RECALC_WEEKLY_FALLBACK` L383-385 + `RATE_RECALC_SKIP_ORIGINAL_CONTRACT` L399-401 + `TARGET_SHEET_ID` L165 | exact (default-on kill switch + startup-banner state log) |
| `generate_weekly_pdfs.py` § `group_source_rows()` variant tagging extension | transform | grouping | L3534-3581 (helper / vac_crew variant branches in `group_source_rows`) | exact (variant tagging emits new group keys) |
| `generate_weekly_pdfs.py` § `calculate_data_hash()` extension | transform | hashing | L1564-1605 (meta_parts.append + VARIANT token + RATES_FP append) | exact (meta_parts injection) |
| `generate_weekly_pdfs.py` § `build_group_identity()` extension | parser | filename round-trip | L1818-1841 (variant marker detection in tail) | exact (literal-token detection after WeekEnding anchor) |
| `generate_weekly_pdfs.py` § `generate_excel()` variant-suffix + price substitution | transform | output | L3841-3863 (variant_suffix construction) | exact (variant-aware filename + price overwrite hook) |
| `generate_weekly_pdfs.py` § routing extension (second `target_map` for `_ReducedSub`) | controller | request-response | L4180-4290 (`create_target_sheet_map`) + L5375-5388 (upload-task dict) | role-match (single → dual target sheet) |
| `billing_audit/schema.sql` § `variant` column DDL | config | schema migration | L89-95 (existing idempotent `ALTER TABLE ADD COLUMN IF NOT EXISTS`) | exact (idempotent column-add) |
| `billing_audit/writer.py` § `freeze_row(variant=...)` kwarg + payload field | service | RPC writer | L362-483 `freeze_row` (params dict, with_retry, counter bump) | exact (writer signature + payload) |
| `tests/test_subcontractor_pricing.py` § new loader regression class | test | unit | `TestLoadContractRates` L13-130 | exact (CSV loader test pattern) |
| `tests/test_vac_crew.py` § new variant generation regression class | test | integration | `TestVacCrewGroupingLogic` L136-225 + `TestVacCrewGroupIdentityParsing` L94-135 | exact (variant grouping + filename round-trip) |
| `tests/test_security_audit_followup.py` § new `_AEPBillable`/`_ReducedSub` filename + collision cases | test | unit | `TestBuildGroupIdentityWithUnderscoresInWr` L907-1025 + `TestSourceWrCollisionQuarantine` L1165-1264 + `TestTargetMapWrKeyCollisionDetection` L721-848 | exact (parser + quarantine reproduction harnesses) |
| `tests/test_billing_audit_shadow.py` § new `variant` attribution test class | test | unit | `FreezeRowTests` L287-440 + `FreezeRowConcurrencyTests` L714-826 | exact (mocked Supabase client + payload assertion) |
| `tests/validate_production_safety.py` § window cap bump | test | validator | L124-145 `validate_per_group_try_catches_all` (window-cap on broad except) | exact (window-cap bump after block grows) |

---

## Pattern Assignments

### 1. `data/subcontractor_rates.csv` (data, file-I/O input)

**Analog source:** existing operator-managed CSV ergonomics; canonical
path documented in `REQUIREMENTS.md` SUB-04 and locked by D-02.

**Path-rename pattern:** `git mv` (preserves history) from repo root
`CU List - Corpus North & South.csv` → `data/subcontractor_rates.csv`.
The XLSX stays gitignored per `.gitignore:93` (intel/contract-schema.md
File Identity block).

**Loader contract** (mirrors the dataclass sketch in
`.planning/intel/contract-schema.md` L74-94):

```python
# 9 fields per row; old-rates columns 12-14 and hours columns 6-8
# intentionally NOT loaded (D-05/D-06).
{
    'cu_code': str,           # column 2 'CU' — join key
    'cu_wbs': str,            # column 1 (audit-only)
    'compatible_unit_group': str,  # column 5 (audit-only)
    'reduced_install_price': float,   # column 9
    'reduced_remove_price': float,
    'reduced_transfer_price': float,
    'new_install_price': float,       # column 15
    'new_remove_price': float,
    'new_transfer_price': float,
}
```

---

### 2. `generate_weekly_pdfs.py` § new loader (utility, file-I/O / transform)

**Analog:** `load_contract_rates()` at `generate_weekly_pdfs.py:909-933`.

**Import / preamble pattern** (the new loader belongs near
`load_contract_rates` so it sits in the rate-loading section):

```python
# generate_weekly_pdfs.py:909-933 (load_contract_rates — exact analog)
def load_contract_rates(filepath):
    """Loads contract rates into a fast lookup dictionary."""
    rates = {}
    REQUIRED_HEADERS = {'CU', 'Install Price', 'Removal Price', 'Transfer Price'}
    try:
        with open(filepath, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or not REQUIRED_HEADERS.issubset(set(reader.fieldnames)):
                missing = REQUIRED_HEADERS - set(reader.fieldnames or [])
                logging.error(f"CSV {filepath} missing required headers: {missing}")
                return rates
            for row in reader:
                cu = str(row.get('CU', '')).strip().upper()
                if not cu:
                    continue

                rates[cu] = {
                    'install': parse_price(row.get('Install Price', 0)),
                    'removal': parse_price(row.get('Removal Price', 0)),
                    'transfer': parse_price(row.get('Transfer Price', 0))
                }
        logging.info(f"Loaded {len(rates)} CU rates from {filepath}")
    except Exception as e:
        logging.error(f"Failed to load rates from {filepath}: {e}")
    return rates
```

**Patterns to copy:**
- `encoding='utf-8-sig'` (handles BOM) — D-04 requires this.
- `parse_price(...)` (defined elsewhere in `generate_weekly_pdfs.py`) for `$1,234.56` currency-string coercion — D-04 explicitly delegates "strip `$` and thousands-separator commas, parse to float" to this helper.
- `cu.strip().upper()` so the join key is normalized (CONTEXT D-04 + `intel/contract-schema.md` ratio analysis was done on uppercased keys).
- Empty-CU skip: `if not cu: continue` — pattern for D-04's "skip zero-priced placeholder rows" (extend predicate to "if not cu or all six priced columns are 0: continue").
- One INFO log line at end with row count — startup-banner discipline.
- Try/except returns `{}` on failure — never raises into caller. Matches `subcontractor-pricing-folder-discovery.instructions.md` "fail-safe" contract. **Do NOT** add Sentry capture inside the loader; surface failures via the return-empty + WARNING pattern.

**Fingerprint pattern (D-20):** `_compute_rates_fingerprint` at L997-1003 is the exact analog:

```python
# generate_weekly_pdfs.py:997-1003
def _compute_rates_fingerprint(rates_dict):
    """Compute a short SHA256 fingerprint of a rates dictionary for hash invalidation."""
    h = hashlib.sha256()
    for code in sorted(rates_dict.keys()):
        r = rates_dict[code]
        h.update(f"{code}:{r['install']:.2f},{r['removal']:.2f},{r['transfer']:.2f}\n".encode())
    return h.hexdigest()[:12]
```

**Adapt for subcontractor rates:** the new fingerprint must include all 6 price fields (3 reduced + 3 new) and use `[:16]` per D-20. Reuse `hashlib.sha256` and `sorted(rates_dict.keys())` — these guarantee stable fingerprint across runs.

**Loader call site:** module-level invocation at startup (after env vars are resolved, before main()), captured into module-level `_SUBCONTRACTOR_RATES` and `_SUBCONTRACTOR_RATES_FINGERPRINT`. The legacy ledger reference is `load_rate_versions()` at L1006 (called once at startup) — same pattern.

---

### 3. `generate_weekly_pdfs.py` § new env-var block (config, startup)

**Analogs (all in one section):**

```python
# generate_weekly_pdfs.py:165 — TARGET_SHEET_ID resolution pattern
TARGET_SHEET_ID = _coerce_sheet_id(_target_sheet_id_env, 5723337641643908)
```

```python
# generate_weekly_pdfs.py:383-385 — RATE_RECALC_WEEKLY_FALLBACK (default-on kill switch)
RATE_RECALC_WEEKLY_FALLBACK = os.getenv(
    'RATE_RECALC_WEEKLY_FALLBACK', '1'
).lower() in ('1', 'true', 'yes', 'on')
```

```python
# generate_weekly_pdfs.py:399-401 — RATE_RECALC_SKIP_ORIGINAL_CONTRACT (default-on kill switch)
RATE_RECALC_SKIP_ORIGINAL_CONTRACT = os.getenv(
    'RATE_RECALC_SKIP_ORIGINAL_CONTRACT', '1'
).lower() in ('1', 'true', 'yes', 'on')
```

```python
# generate_weekly_pdfs.py:425-436 — startup banner state log for kill switches
if RATE_RECALC_WEEKLY_FALLBACK:
    logging.info(
        "📊 Rate recalc Weekly-Ref-Date fallback ENABLED ..."
    )
else:
    logging.info("📊 Rate recalc Weekly-Ref-Date fallback DISABLED (RATE_RECALC_WEEKLY_FALLBACK=false)")
if RATE_RECALC_SKIP_ORIGINAL_CONTRACT:
    logging.info(
        "📊 Rate recalc ORIGINAL_CONTRACT folder skip ENABLED ..."
    )
else:
    logging.info(
        "📊 Rate recalc ORIGINAL_CONTRACT folder skip DISABLED ..."
    )
```

**Patterns to copy for each new env var:**
- `SUBCONTRACTOR_PPP_SHEET_ID`: clone L165 — `int(os.getenv('SUBCONTRACTOR_PPP_SHEET_ID', '8162920222379908'))`. Use `_coerce_sheet_id` helper (L156-163) for parse-error fallback. Log resolved value (matches L168-171 pattern: `"🎯 Using subcontractor PPP sheet id: ..."`).
- `SUBCONTRACTOR_RATE_VARIANTS_ENABLED`: clone L383-385 exact form (default `'1'`, truthy set `{'1','true','yes','on'}`).
- `SUBCONTRACTOR_RATES_CSV`: clone the `_sanitize_csv_path` helper used at L371-372 (`NEW_RATES_CSV = _sanitize_csv_path(...)`) — this protects against directory traversal AND symlink escape from the env var, satisfying CodeQL taint analysis (see `_sanitize_csv_path` L357-368).

**Banner log (D-13 — startup-banner discipline):** add a block immediately after the existing kill-switch banner that prints `SUBCONTRACTOR_RATE_VARIANTS_ENABLED`, `SUBCONTRACTOR_RATES_CSV` resolved path, `SUBCONTRACTOR_PPP_SHEET_ID` resolved id, **and** `_SUBCONTRACTOR_RATES_FINGERPRINT` (D-20 wants the fingerprint logged for run-over-run diff visibility).

---

### 4. `generate_weekly_pdfs.py` § `group_source_rows()` variant tagging extension (transform, grouping)

**Analog:** L3526-3604 (the existing variant branching cascade).

**Core pattern** (L3534-3545 — vac_crew branch is structurally simplest):

```python
# generate_weekly_pdfs.py:3534-3545
if is_vac_crew_row:
    vac_crew_key = f"{week_end_for_key}_{wr_key}_VACCREW"
    vac_crew_foreman = r.get('__vac_crew_name') or effective_user
    keys_to_add.append(('vac_crew', vac_crew_key, vac_crew_foreman))
    if vac_crew_key not in groups:
        logging.info(f"🏗️ VAC CREW GROUP CREATED: WR={wr_key}, Week={week_end_for_key}")
    else:
        logging.debug(f"Adding row to existing VAC Crew group: WR={wr_key}, Week={week_end_for_key}")
```

```python
# generate_weekly_pdfs.py:3574-3583 — helper variant (the shadow-helper pattern)
if valid_helper_row and helper_mode_enabled:
    helper_dept = r.get('__helper_dept', '')
    helper_job = r.get('__helper_job', '')
    helper_sanitized = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]
    helper_key = f"{week_end_for_key}_{wr_key}_HELPER_{helper_sanitized}"
    keys_to_add.append(('helper', helper_key, helper_foreman))
    logging.info(f"🔧 HELPER GROUP CREATED: WR={wr_key}, Week={week_end_for_key}, Helper={helper_foreman}, Dept={helper_dept}, Job={helper_job}")
```

**Variant attribution at end of loop** (L3594-3601):

```python
for variant, key, current_foreman in keys_to_add:
    r_copy = r.copy()
    r_copy['__variant'] = variant
    r_copy['__current_foreman'] = current_foreman or effective_user
    r_copy['__week_ending_date'] = week_ending_date
    r_copy['__grouping_key'] = key
    groups[key].append(r_copy)
```

**Patterns to copy for `_AEPBillable` / `_ReducedSub` variant tagging:**
- Build group keys: per D-09 ordering, new keys are `f"{week_end_for_key}_{wr_key}_AEPBILLABLE"` and `f"{week_end_for_key}_{wr_key}_REDUCEDSUB"`. Helper shadow variants: `f"{week_end_for_key}_{wr_key}_AEPBILLABLE_HELPER_{helper_sanitized}"` and `f"{week_end_for_key}_{wr_key}_REDUCEDSUB_HELPER_{helper_sanitized}"`. **Match the existing UPPERCASE_TOKEN naming** (`VACCREW`, `HELPER`) — the group-key prefix is used by the `_PII_LOG_MARKERS` list at L660-668.
- Gate the new branches on `is_subcontractor_sheet AND SUBCONTRACTOR_RATE_VARIANTS_ENABLED` so the kill switch fully short-circuits.
- Use `_RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]` for any helper name in the new variant keys (D-22 — sanitize at producer site).
- Tag `r_copy['__variant'] = 'aep_billable'` / `'reduced_sub'` / `'aep_billable_helper'` / `'reduced_sub_helper'` (D-10) — these are exactly the variant strings the writer (D-18) and the hash (D-11) expect.
- One INFO-level "GROUP CREATED" log per new group key (mirrors L3543, L3583). **Do NOT** log every row addition at INFO — only the first time the key is seen (the L3540-3545 pattern).
- D-22 / `_PII_LOG_MARKERS`: extend the marker list at L660-668 (group-keys section) with `"_AEPBILLABLE"`, `"_REDUCEDSUB"`, `"_AEPBILLABLE_HELPER_"`, `"_REDUCEDSUB_HELPER_"`, `"AEP BILLABLE GROUP CREATED"`, `"REDUCED SUB GROUP CREATED"` so the `before_send_log` sanitizer drops new INFO-level group-creation lines.

**Snapshot Date cutoff gate for `_AEPBillable` (D-01, SUB-01):** the `_AEPBillable` branch must also gate on `Snapshot Date >= 2026-04-12`. The locked rule from ledger 2026-04-21 22:35 (decisions.md "Do NOT change the cutoff column from `Snapshot Date` to `Weekly Reference Logged Date`") still binds — the cutoff is snapshot-keyed, NOT weekly-keyed, even though Weekly-Ref fallback exists for recalc. For variant generation here, snapshot is authoritative; use `excel_serial_to_date(r.get('Snapshot Date'))` (the same helper L3513 uses for Weekly Reference Logged Date parsing) and compare to a new module constant `_AEP_BILLABLE_CUTOFF = datetime.date(2026, 4, 12)`. `_ReducedSub` has no cutoff gate (D-01 + SUB-02 — generated unconditionally).

---

### 5. `generate_weekly_pdfs.py` § `calculate_data_hash()` extension (transform, hashing)

**Analog:** L1564-1605 (the meta_parts append block + RATE_CUTOFF guard).

**Core pattern** (L1564-1599):

```python
# generate_weekly_pdfs.py:1564-1599
meta_parts = []
meta_parts.append(f"FOREMAN={group_foreman or ''}")

# Variant-specific hash tokens (replaces activity log USER= token)
variant = group_variant
meta_parts.append(f"VARIANT={variant}")

if variant == 'helper':
    _first = sorted_rows[0] if sorted_rows else {}
    helper_foreman = _first.get('__helper_foreman', '')
    helper_dept = _first.get('__helper_dept', '')
    helper_job = _first.get('__helper_job', '')
    # ... validation warnings ...
    meta_parts.append(f"HELPER={helper_foreman}")
    meta_parts.append(f"HELPER_DEPT={helper_dept}")
    meta_parts.append(f"HELPER_JOB={helper_job}")
# vac_crew has NO meta_parts block (per-row vac_crew fields are
# captured inside row_str above to defeat set-dedup collisions —
# see L1536-1553)

meta_parts.append(f"DEPTS={','.join(unique_depts)}")
meta_parts.append(f"TOTAL={total_price:.2f}")
meta_parts.append(f"ROWCOUNT={len(sorted_rows)}")
if RATE_CUTOFF_DATE:
    meta_parts.append(f"RATE_CUTOFF={RATE_CUTOFF_DATE.isoformat()}")
    if _RATES_FINGERPRINT:
        meta_parts.append(f"RATES_FP={_RATES_FINGERPRINT}")
```

**Patterns to copy:**
- D-11: **shared bucket, variant-token-distinguished.** The `meta_parts.append(f"VARIANT={variant}")` line at L1569 is the single discrimination point — it accepts any string. New variant strings (`'aep_billable'`, `'reduced_sub'`, `'aep_billable_helper'`, `'reduced_sub_helper'`) flow through naturally. **No new code is needed at L1569 itself.**
- D-09 + D-22: when `variant in ('aep_billable_helper', 'reduced_sub_helper')`, copy the L1571-1587 helper meta block verbatim (the new shadow variants must capture the same helper foreman / dept / job triple). The 2026-04-22 ledger rule binds: helper groups are partitioned per foreman, so reading from `sorted_rows[0]` is safe — the existing helper branch already proved this.
- D-20 fingerprint embedding: copy the L1596-1599 `if RATE_CUTOFF_DATE: ... if _RATES_FINGERPRINT:` pattern to add an analogous block scoped to **subcontractor variants only**:

```python
# NEW pattern to add (analog L1596-1599)
if variant in ('aep_billable', 'reduced_sub',
               'aep_billable_helper', 'reduced_sub_helper'):
    if _SUBCONTRACTOR_RATES_FINGERPRINT:
        meta_parts.append(
            f"SUB_RATES_FP={_SUBCONTRACTOR_RATES_FINGERPRINT}"
        )
```

This satisfies D-20's "CSV edit forces regen of every `_AEPBillable` / `_ReducedSub` file but does NOT touch primary / helper / vac_crew hashes" requirement — preserves the byte-identical guarantee in ROADMAP success criterion 5.

**Critical guardrail (ledger 2026-04-22 00:00):** the hash key MUST stay `(WR, week, variant, foreman, dept, job)` — D-11 explicitly forbids shortening. The shadow helper variants automatically satisfy this because they reuse the existing helper meta block.

---

### 6. `generate_weekly_pdfs.py` § `build_group_identity()` extension (parser, filename round-trip)

**Analog:** L1818-1841 (variant marker detection in the post-`WeekEnding` tail).

**Core pattern** (L1822-1841):

```python
# generate_weekly_pdfs.py:1822-1841
variant = 'primary'
identifier = None
tail = parts[we_idx + 2:]

if 'Helper' in tail:
    variant = 'helper'
    helper_idx_rel = tail.index('Helper')
    if helper_idx_rel + 1 < len(tail):
        identifier = '_'.join(tail[helper_idx_rel + 1:-1])
elif 'VacCrew' in tail:
    variant = 'vac_crew'
    identifier = ''  # No sub-identifier for VAC Crew
elif 'User' in tail:
    variant = 'primary'
    user_idx_rel = tail.index('User')
    if user_idx_rel + 1 < len(tail):
        identifier = '_'.join(tail[user_idx_rel + 1:-1])

return (wr, week, variant, identifier)
```

**Patterns to copy for `_AEPBillable` / `_ReducedSub` parser extension:**
- D-10: the new variant markers are `'AEPBillable'` and `'ReducedSub'`. Critical: matched against the **tail span**, not against the WR portion (the WeekEnding-anchor mechanism at L1740-1810 already isolates the tail). The scoped check forbids false-positives if a sanitized WR somehow contains `AEPBillable` / `ReducedSub` literally.
- D-09 ordering: variant-first, helper-second. Filename example: `WR_91467680_WeekEnding_041926_123456_AEPBillable_Helper_Jane_Smith_ab12cd34ef.xlsx`. So the parser must detect `AEPBillable` FIRST, then look forward in the tail for an optional `Helper` marker that flips the variant to `aep_billable_helper` (and captures the identifier between `Helper` and the final hash).
- The four target variant strings the parser MUST produce: `'aep_billable'`, `'reduced_sub'`, `'aep_billable_helper'`, `'reduced_sub_helper'` — these are the exact tokens the rest of the pipeline uses (hash key, freeze_row variant kwarg, attachment-identity match). DO NOT introduce capitalized versions.
- The parser must respect the round-7 / round-9 collision-quarantine semantics — but since the parser is *read-only* (filename → tuple), it has no upload-side surface; the producer/consumer collision pre-scans at L4760-4789 (source) and L4223-4275 (target) already guard the routing. The parser just needs to not be confused by the new variant tokens.
- Ledger guardrail: variant detection priority must be deterministic. The new variants should be checked BEFORE `Helper` / `VacCrew` / `User` so `_AEPBillable_Helper_<name>` parses as `aep_billable_helper` not `helper` (otherwise `aep_billable_helper` hash-bucket loses cohesion).

**Suggested ordering:**
1. `if 'AEPBillable' in tail:` → if `Helper` also follows → `variant = 'aep_billable_helper'`, identifier = helper name; else → `variant = 'aep_billable'`, identifier = `''`.
2. `elif 'ReducedSub' in tail:` → mirror item 1 with `reduced_sub` / `reduced_sub_helper`.
3. `elif 'Helper' in tail:` (existing — unchanged).
4. `elif 'VacCrew' in tail:` (existing — unchanged).
5. `elif 'User' in tail:` (existing — unchanged).

**Span-join discipline:** identifier extraction must use `'_'.join(tail[idx + 1:-1])` (per L1832 / L1840) — preserves underscores in sanitized helper names like `Jane_Smith`. Round-7 ledger rule applies (decisions.md 2026-04-23 21:00).

---

### 7. `generate_weekly_pdfs.py` § `generate_excel()` variant-suffix + price substitution (transform, output)

**Analog:** L3841-3863 (variant-aware filename construction).

**Core pattern** (L3841-3863):

```python
# generate_weekly_pdfs.py:3841-3863
variant = first_row.get('__variant', 'primary')
variant_suffix = ""

if variant == 'helper':
    helper_foreman = first_row.get('__helper_foreman', '')
    if helper_foreman:
        helper_sanitized = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]
        variant_suffix = f"_Helper_{helper_sanitized}"
elif variant == 'vac_crew':
    variant_suffix = '_VacCrew'
elif variant == 'primary':
    variant_suffix = ''

if data_hash:
    output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}_{timestamp}{variant_suffix}_{data_hash}.xlsx"
else:
    output_filename = f"WR_{wr_num}_WeekEnding_{week_end_raw}_{timestamp}{variant_suffix}.xlsx"
final_output_path = os.path.join(week_output_folder, output_filename)
```

**Patterns to copy:**
- Add new branches BEFORE the existing `if variant == 'helper':` so the variant-first ordering (D-09) is preserved:

```python
# NEW branches to add to generate_excel (analog L3844-3856)
if variant == 'aep_billable':
    variant_suffix = '_AEPBillable'
elif variant == 'reduced_sub':
    variant_suffix = '_ReducedSub'
elif variant == 'aep_billable_helper':
    helper_foreman = first_row.get('__helper_foreman', '')
    if helper_foreman:
        helper_sanitized = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]
        variant_suffix = f"_AEPBillable_Helper_{helper_sanitized}"
elif variant == 'reduced_sub_helper':
    helper_foreman = first_row.get('__helper_foreman', '')
    if helper_foreman:
        helper_sanitized = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]
        variant_suffix = f"_ReducedSub_Helper_{helper_sanitized}"
# (existing helper / vac_crew / primary branches follow)
```

- Sanitize helper names at producer site (mirrors L3849) — D-22 / ledger 2026-04-23 18:25.

**Price substitution hook:** at the row-iteration block inside `generate_excel` (search for `parse_price(row.get('Units Total Price'))` — multiple sites, e.g. L3940), introduce a per-row pricing function that, for `aep_billable*` / `reduced_sub*` variants, returns `rate × qty` from `_SUBCONTRACTOR_RATES` instead of `Units Total Price`. The closest existing analog is `recalculate_row_price()` (referenced in decisions.md 2026-04-21 22:35 — fall-through to SmartSheet price on missing CU). **Apply the same fall-through safety net per D-16:** if `cu_code not in _SUBCONTRACTOR_RATES`, retain `Units Total Price` (NEVER zero-out) and surface via the per-sheet `missing_cus: Counter`.

**Missing-CU WARNING pattern (D-17):** copy the per-sheet WARNING-summary structure from the 2026-04-21 22:35 ledger entry (recalc skipped CUs). Specifically the per-sheet log at the bottom of `_fetch_and_process_sheet`:

```python
# Suggested message body (D-17 verbatim):
logging.warning(
    f"Subcontractor rates CSV missing {N} CU code(s) on sheet {sheet_id}: "
    f"{first_10_codes}{ '...' if N > 10 else '' }. "
    f"Add to data/subcontractor_rates.csv to enable rate recalc for "
    f"these rows. Sheet rows fell through to SmartSheet pricing."
)
```

The 10-CU truncation bounds log line length. Threshold of `first_10_codes` mirrors the existing rate-recalc per-sheet summary pattern.

**openpyxl rule (CLAUDE.md / `.claude/rules/smartsheet-python-optimization.md`):** keep using `openpyxl` for these new variant files. **Do NOT** switch to `xlsxwriter` — the rule explicitly applies to NEW scripts only; existing `generate_weekly_pdfs.py` stays on `openpyxl`. Use `safe_merge_cells()` (L3916, L3922, L3928, L3934 examples). **Never** write `oddFooter.right.text`.

---

### 8. `generate_weekly_pdfs.py` § routing extension (controller, request-response)

**Analog:** L4180-4290 (`create_target_sheet_map`) and L5375-5388 (upload-task dict).

**Existing dual-route problem:** the codebase today resolves a single `target_map` against `TARGET_SHEET_ID`. The phase needs a SECOND `target_map` against `SUBCONTRACTOR_PPP_SHEET_ID` so `_ReducedSub*` variants attach to BOTH sheets (SUB-03).

**Pattern to copy:** L4180-4286 `create_target_sheet_map(client)` — call it a SECOND time with the new sheet ID. The existing function is parameterless on the sheet ID side (it reads `TARGET_SHEET_ID` directly at L4188), so extract a sheet-id parameter or wrap with a new helper `create_target_sheet_map_for(client, sheet_id)` that takes the id as an argument and returns the same `(target_map, target_sheet)` tuple. **Preserve** the entire L4204-4283 sanitization + collision quarantine block (D-22 / ledger 2026-04-23 20:10 round-6) — every new target_map MUST repeat the `_RE_SANITIZE_HELPER_NAME` + `_quarantined_keys` discipline.

**Upload-task dict pattern** (L5375-5388):

```python
# generate_weekly_pdfs.py:5375-5388
if not TEST_MODE and target_map and wr_num:
    if wr_num in target_map:
        _upload_tasks.append({
            'excel_path': excel_path,
            'filename': filename,
            'wr_num': wr_num,
            'target_row': target_map[wr_num],
            'variant': variant,
            'identifier': identifier,
            'file_identifier': file_identifier,
            'data_hash': data_hash,
            'week_raw': week_raw,
            'group_key': group_key,
        })
    else:
        logging.warning(f"⚠️ Work request {wr_num} not found in target sheet")
```

**Patterns to copy for dual-routing:**
- Add a `'target_sheet_id'` field to the task dict (default `TARGET_SHEET_ID` for non-reducedsub variants). For `'reduced_sub'` / `'reduced_sub_helper'` variants, append the task TWICE — once with `target_sheet_id = TARGET_SHEET_ID` and once with `target_sheet_id = SUBCONTRACTOR_PPP_SHEET_ID`. Both lookups must use the second `target_map` for the second sheet (so collision quarantine still applies independently).
- In `_upload_one` worker (L5443-5507), reference `task['target_sheet_id']` instead of the global `TARGET_SHEET_ID` (L5453, L5468). The existing `delete_old_excel_attachments(client, TARGET_SHEET_ID, ...)` call (L5452-5458) and `attach_file_to_row(TARGET_SHEET_ID, ...)` call (L5467-5471) become `task['target_sheet_id']`-keyed.
- Attachment-cache prefetch (referenced indirectly via `cached_attachments=attachment_cache.get(target_row.id)` at L5457): the existing cache covers only `TARGET_SHEET_ID`'s rows. The PPP target sheet's rows need their own cache entry — extend the attachment-prefetch phase (L2774-2787 budget constants + the executor block elsewhere) to ALSO prefetch attachments for the second target sheet. **Apply the 2026-04-22 16:05 ledger rule:** the prefetch must use `ATTACHMENT_PREFETCH_MAX_MINUTES` / `_FUTURE_TIMEOUT_SEC` budget, `as_completed(futures, timeout=...)`, and `executor.shutdown(wait=False, cancel_futures=True)` — NEVER `with ThreadPoolExecutor(...)`. Per-row fallback path stays unchanged (cache=None → per-row lookup).
- Source WR collision quarantine (L4760-4789) and target_map collision quarantine (L4223-4275) need NO modification — both already key on sanitized WR alone, which is what the new variants also use. Sanity-check by running the existing pre-scan against a manufactured groups dict that mixes `_AEPBillable` + `_ReducedSub` variants.

---

### 9. `billing_audit/schema.sql` § `variant` column DDL (config, schema migration)

**Analog:** L89-95 (existing idempotent ALTER TABLE).

**Core pattern** (L89-95):

```sql
-- billing_audit/schema.sql:89-95
ALTER TABLE billing_audit.pipeline_run
    ADD COLUMN IF NOT EXISTS content_hash    TEXT,
    ADD COLUMN IF NOT EXISTS assignment_fp   TEXT,
    ADD COLUMN IF NOT EXISTS completed_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_count     INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS release         TEXT,
    ADD COLUMN IF NOT EXISTS created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW();
```

**Pattern to copy for D-18:**

```sql
-- ── Phase 1 SUB-07: variant attribution ─────────────────────
-- TEXT (not enum / CHECK constraint) for forward compatibility;
-- new variants can be introduced by the writer without a
-- second schema migration. NULL on existing pre-change rows.
ALTER TABLE billing_audit.pipeline_run
    ADD COLUMN IF NOT EXISTS variant TEXT;
```

**Patterns to copy:**
- Idempotent `ADD COLUMN IF NOT EXISTS` (the entire L89-95 block follows this rule — partial-deploy environments upgrade in place).
- Position the new ALTER **AFTER** the existing `CREATE TABLE` and **BEFORE** the `CREATE INDEX` (per L80-88 commentary — Supabase SQL Editor halts on first error, so column-additions must precede index creation).
- TEXT (not enum) per D-18 — `'primary' | 'helper' | 'vac_crew' | 'aep_billable' | 'reduced_sub' | 'aep_billable_helper' | 'reduced_sub_helper'` is the writer's contract surface, but the schema does NOT constrain it (decisions.md 2026-04-25 12:00 — "every column referenced in writer.py MUST appear here" but format is not constrained by the SQL — the constraint lives in the writer code).
- **Add an inline comment block above the ALTER** matching the existing schema.sql comment style (every change refers to a Living Ledger date or PR for context).
- Do NOT add a CHECK constraint enumerating variant values — D-18 explicitly forbids it ("for forward compatibility").

**Per `decisions.md` 2026-04-25 12:00 (SQLSTATE classification):** no new SQLSTATE categories are needed for this column. Reading/writing TEXT NULL columns goes through existing `with_retry` → `_classify_postgrest_error` paths in `billing_audit/client.py`; the existing transient/permanent classification covers it.

---

### 10. `billing_audit/writer.py` § `freeze_row(variant=...)` kwarg + payload field (service, RPC writer)

**Analog:** L362-483 `freeze_row` (entire function — params dict construction, with_retry call, counter bump).

**Core pattern** (L419-454):

```python
# billing_audit/writer.py:419-454
params = {
    "p_wr": wr,
    "p_week_ending": week_ending.isoformat(),
    "p_smartsheet_row_id": row_id,
    "p_primary": (
        row.get("__effective_user")
        or row.get("Foreman")
        or None
    ),
    "p_helper": row.get("__helper_foreman"),
    "p_helper_dept": row.get("__helper_dept"),
    "p_vac_crew": row.get("__vac_crew_name"),
    "p_pole": (
        row.get("Pole #")
        or row.get("Point #")
        or row.get("Point Number")
    ),
    "p_cu": row.get("CU") or row.get("Billable Unit Code"),
    "p_work_type": row.get("Work Type"),
    "p_release": release,
    "p_run_id": run_id,
}

def _invoke():
    return (
        client.schema("billing_audit")
        .rpc("freeze_attribution", params)
        .execute()
    )

result = with_retry(_invoke, op="freeze_attribution")
```

**Patterns to copy:**

D-18 requires the writer to record variant. There are two surfaces:

1. **`freeze_row(...)` signature gets a `variant: str | None = None` kwarg.** Default `None` keeps the function call-compatible from the existing main-loop call sites at L5132-5168 — pass through unchanged where the variant is `primary` and the existing call passes nothing. Then upgrade those call sites in `generate_weekly_pdfs.py` to pass `variant=row.get('__variant', 'primary')` so the new variants flow through.

2. **`emit_run_fingerprint(...)` adds `variant: str | None = None`** at L486-491. The upsert payload at L547-556 grows a `"variant": variant or None` field. Critical: the `on_conflict` key at L562 (`"wr,week_ending,run_id"`) is **unchanged** — variant is NOT part of the PK (D-18 explicit). This means multiple variants for the same `(wr, week, run_id)` will overwrite each other; the **first** variant emitted wins (via the `_emitted_run_keys` dedup at L518-519). Document this in the writer's docstring.

**Counter discipline (ledger 2026-04-25 14:00):** the new `variant` kwarg flows through the parallelized `freeze_row` path at `generate_weekly_pdfs.py:5132-5198`. Counter writes still go through `_bump_counter` under `_counters_lock` (L91-99) — no new lock needed because variant doesn't add a new counter, just a payload field.

**Per-row PII discipline (`writer.py` docstring L10-14):** the new `variant` parameter is NOT PII — it's a categorical token. Safe to log in aggregate counter summaries. **DO NOT** add INFO-level "freezing variant=X row=Y" logs — those would carry row identifiers and violate the writer's PII contract.

**Sentry capture pattern (decisions.md 2026-04-23 12:00):** if any new exception-handling sites in the writer or `generate_weekly_pdfs.py` call `sentry_capture_with_context(...)`, the `context_data['error_message']` field MUST use `_redact_exception_message(exc)` (L504-535). DO NOT pass raw `str(e)`. The existing main-loop pattern at L5407-5427 is the analog:

```python
# generate_weekly_pdfs.py:5407-5427
sentry_capture_with_context(
    exception=e,
    context_name="group_processing_error",
    context_data={
        "group_key": group_key,
        # ...
        "error_message": _redact_exception_message(e),
        "traceback": traceback.format_exc(),
    },
    # ...
)
```

---

### 11. `tests/test_subcontractor_pricing.py` § new loader regression class (test, unit)

**Analog:** `TestLoadContractRates` at `tests/test_subcontractor_pricing.py:13-130`.

**Core pattern** (L16-39):

```python
# tests/test_subcontractor_pricing.py:16-39
def test_loads_valid_csv(self):
    """Test loading a well-formed CSV returns correct rate dictionary."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'CU WBS #', 'CU', 'Unit Of Measure', 'Description',
            'Compatible Unit Group', 'Install Hours', 'Removal Hours',
            'Transfer Hours', 'Install Price', 'Removal Price', 'Transfer Price'
        ])
        writer.writerow(['100', 'ABC123', 'EA', 'Test Unit', 'Group1', '1', '0.5', '0.3', '$150.00', '$75.00', '$50.00'])
        tmp_path = f.name

    try:
        rates = generate_weekly_pdfs.load_contract_rates(tmp_path)
        self.assertEqual(len(rates), 2)
        self.assertIn('ABC123', rates)
        self.assertAlmostEqual(rates['ABC123']['install'], 150.0)
    finally:
        os.unlink(tmp_path)
```

**Patterns to copy:**
- `tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='')` + try/finally + `os.unlink(tmp_path)` — the per-test CSV fixture pattern. Avoids contaminating the repo and survives Windows/POSIX file-locking semantics.
- Each test starts with a CSV writer producing exactly the 17-column header (D-05 explicit). Tests must verify:
  - `test_loads_subcontractor_csv_with_currency_strings`: `$150.00`, `$1,234.56` → 150.0, 1234.56 (D-04 currency coercion).
  - `test_loads_subcontractor_csv_with_utf8_bom`: BOM-prefixed file loads identically (D-04 `encoding='utf-8-sig'`).
  - `test_skips_all_zero_price_rows`: row whose all 6 priced cells are 0 is excluded from the dict AND NOT counted in any "missing CU" telemetry (D-04 — 1058 / 4848 zero-priced placeholder rows).
  - `test_tolerates_na_in_hours_columns`: `'N/A'` in hours columns doesn't break the loader (D-04 — hours not loaded).
  - `test_per_cu_rate_variance_preserved`: a CSV with `New/Old = 2.0725` outlier and `Reduced/New = 0.4343` outlier loads literal values, NOT computed shortcuts (D-07).
  - `test_old_rates_columns_not_loaded`: column 12-14 values present in CSV are NOT in the returned dict (D-06).
  - `test_subcontractor_rates_fingerprint_deterministic`: same CSV → same `_SUBCONTRACTOR_RATES_FINGERPRINT` across reloads (D-20).
  - `test_subcontractor_rates_fingerprint_changes_on_edit`: editing one price changes the fingerprint (D-20).
- All assertion shapes mirror `assertEqual(len(rates), N)`, `assertIn(cu, rates)`, `assertAlmostEqual(rates[cu]['install'], 150.0)` — keep the test style consistent.

---

### 12. `tests/test_vac_crew.py` § new variant generation regression class (test, integration)

**Analog:** `TestVacCrewGroupingLogic` L136-225 and `TestVacCrewGroupIdentityParsing` L94-135.

**Core pattern** (L97-115 — filename round-trip):

```python
# tests/test_vac_crew.py:97-115
def test_vac_crew_filename_parsed_as_vac_crew_variant(self):
    """A VAC Crew filename must round-trip through build_group_identity."""
    ident = generate_weekly_pdfs.build_group_identity(
        'WR_90093002_WeekEnding_041926_123456_VacCrew_ab12cd34ef.xlsx'
    )
    self.assertIsNotNone(ident)
    wr, week, variant, identifier = ident
    self.assertEqual(wr, '90093002')
    self.assertEqual(week, '041926')
    self.assertEqual(variant, 'vac_crew')
    self.assertEqual(identifier, '')

def test_primary_filename_not_affected(self):
    """A primary filename must NOT be mis-detected as VAC Crew."""
    ident = generate_weekly_pdfs.build_group_identity(
        'WR_90093002_WeekEnding_041926_123456_ab12cd34ef.xlsx'
    )
    self.assertIsNotNone(ident)
    wr, week, variant, identifier = ident
    self.assertEqual(variant, 'primary')
```

**Patterns to copy:**
- `TestVacCrewGroupIdentityParsing` (L94-135) is the **exact** structural analog for `TestAEPBillableGroupIdentityParsing` and `TestReducedSubGroupIdentityParsing` — every test method maps one-to-one. Add:
  - `test_aep_billable_filename_parsed_as_aep_billable_variant` — `_AEPBillable_<hash>.xlsx` → `variant='aep_billable'`, `identifier=''`.
  - `test_reduced_sub_filename_parsed_as_reduced_sub_variant` — `_ReducedSub_<hash>.xlsx` → `variant='reduced_sub'`.
  - `test_aep_billable_helper_filename` — `_AEPBillable_Helper_<name>_<hash>.xlsx` → `variant='aep_billable_helper'`, `identifier=<name>`.
  - `test_reduced_sub_helper_filename` — `_ReducedSub_Helper_<name>_<hash>.xlsx` → `variant='reduced_sub_helper'`.
  - `test_primary_filename_does_not_match_new_variants` (negative case, mirrors L108-115).
  - `test_helper_filename_does_not_match_new_variants` (negative case — pure `_Helper_<name>_<hash>` must still parse as `helper`, not `aep_billable_helper`).
  - `test_aep_billable_does_not_collide_with_helper_variant_only` — `_AEPBillable_Helper_<name>` must NOT parse as `helper` with `aep_billable` lost; it must parse as `aep_billable_helper`.

- `TestVacCrewHashAggregation` (L227-419) is the analog for the new hash-key regression class. The CONTEXT note D-11 (existing shared bucket) means the new test must:
  - `test_hash_changes_when_variant_token_changes` — same row set with `__variant='primary'` vs `__variant='aep_billable'` produces DIFFERENT hashes (L1569 VARIANT token discrimination).
  - `test_hash_changes_when_subcontractor_rates_fingerprint_changes` — same row set, mutated `_SUBCONTRACTOR_RATES_FINGERPRINT` produces different hash ONLY for new-variant rows (D-20 scoping).
  - `test_hash_stable_for_primary_when_subcontractor_fingerprint_changes` — primary rows are NOT affected by `_SUBCONTRACTOR_RATES_FINGERPRINT` (D-20 byte-identical guarantee, ROADMAP success criterion 5).
  - `test_hash_aep_billable_helper_captures_helper_metadata` — mirrors `test_hash_changes_when_non_first_row_vac_crew_dept_edited` (L276 et seq.) but for shadow helper variants.

- `TestVacCrewHashAggregation.setUp / tearDown` (L227-275) pins `EXTENDED_CHANGE_DETECTION`, `RATE_CUTOFF_DATE`, `_RATES_FINGERPRINT` to test-isolated values. The new test class MUST do the same for `_SUBCONTRACTOR_RATES_FINGERPRINT` to avoid developer-env leaks (decisions.md 2026-04-22 16:05 corollary on test isolation).

---

### 13. `tests/test_security_audit_followup.py` § new `_AEPBillable`/`_ReducedSub` filename + collision cases (test, unit)

**Analogs:** `TestBuildGroupIdentityWithUnderscoresInWr` L907-1025 + `TestSourceWrCollisionQuarantine` L1165-1264 + `TestTargetMapWrKeyCollisionDetection` L721-848.

**Core pattern from `TestBuildGroupIdentityWithUnderscoresInWr`** (L1005-1017):

```python
# tests/test_security_audit_followup.py:1005-1017
def test_wr_containing_literal_helper_token_no_false_variant(self):
    """A sanitized WR containing ``Helper`` must NOT be read as
    the helper variant. The marker search is scoped to the tail
    after ``WeekEnding <week>`` so the WR portion is ignored.
    """
    ident = generate_weekly_pdfs.build_group_identity(
        'WR_Helper_WeekEnding_041926_123456_ab12cd34ef.xlsx'
    )
    self.assertIsNotNone(ident)
    wr, week, variant, identifier = ident
    self.assertEqual(wr, 'Helper')
    self.assertEqual(variant, 'primary')
    self.assertIsNone(identifier)
```

**Patterns to copy:**
- `test_wr_containing_literal_aep_billable_token_no_false_variant` — `WR_AEPBillable_WeekEnding_041926_123456_<hash>.xlsx` must parse as `wr='AEPBillable'`, `variant='primary'` (NOT `aep_billable`). The variant marker MUST be tail-scoped per the round-7/8 parser hardening.
- `test_wr_containing_literal_reduced_sub_token_no_false_variant` (mirror).
- `test_aep_billable_helper_filename_with_underscored_wr_parses` — analog of `test_helper_filename_with_underscored_wr_parses` (L951-960). Use sanitized WR `'1234____evil'` and verify the new variant + identifier extraction is robust.
- `test_pre_scan_catches_aep_billable_cross_variant_collision` — clone `test_pre_scan_catches_cross_variant_collisions` (L1251-1264). Use a `groups` dict where one group has `__variant='aep_billable'` and another has `__variant='reduced_sub'` with sanitization-colliding WR# values. The pre-scan must quarantine both per the round-9 broader-key rule (decisions.md 2026-04-23 21:00).
- `test_target_map_dual_sheet_quarantine_independent` — a NEW test that verifies the two target_maps (TARGET_SHEET_ID's and SUBCONTRACTOR_PPP_SHEET_ID's) maintain INDEPENDENT collision quarantines. If sheet A has a duplicate WR# but sheet B doesn't, sheet B's target_map is unaffected. Use the L755-794 `test_collision_quarantines_both_rows` structural template.

---

### 14. `tests/test_billing_audit_shadow.py` § new `variant` attribution test class (test, unit)

**Analog:** `FreezeRowTests` L287-440 + `FreezeRowConcurrencyTests` L714-826.

**Core pattern** (L338-369 — argument-asserting test):

```python
# tests/test_billing_audit_shadow.py:338-369
def test_freeze_row_uses_effective_user_for_primary(self):
    from billing_audit import writer as ba_writer
    client = _make_fake_supabase_client()
    client.schema.return_value.rpc.return_value.execute.return_value = (
        _fake_rpc_response("run-x")
    )
    row = self._valid_row()
    row["__effective_user"] = "Xavier Override"
    with mock.patch(
        "billing_audit.writer.get_client", return_value=client
    ), mock.patch(
        "billing_audit.writer.get_flag", return_value=True
    ):
        ba_writer.freeze_row(row, release="r", run_id="run-x")
    _, params = client.schema.return_value.rpc.call_args.args
    self.assertEqual(
        params["p_primary"], "Xavier Override",
        ...
    )
```

**Patterns to copy:**
- `test_freeze_row_passes_variant_kwarg_to_rpc` — call `freeze_row(row, release='r', run_id='run-x', variant='aep_billable')` and assert `params['p_variant'] == 'aep_billable'` (or whatever name the D-18 writer surface chooses; planner should default to `p_variant` for naming consistency with the existing `p_*` parameter convention).
- `test_freeze_row_defaults_variant_to_primary_when_unset` — calling without the kwarg must default to `'primary'` (default for back-compat with existing call sites).
- `test_freeze_row_records_helper_variant` / `test_freeze_row_records_vac_crew_variant` / `test_freeze_row_records_aep_billable_helper_variant` / `test_freeze_row_records_reduced_sub_helper_variant` — pass each variant string and assert it lands in the payload.
- `test_emit_run_fingerprint_records_variant_in_upsert_payload` — call `emit_run_fingerprint(...)` with the new `variant` kwarg and assert `client.schema().table().upsert.call_args.args[0]['variant'] == 'aep_billable'`.
- `test_emit_run_fingerprint_first_variant_wins_on_dedup` — call twice with same `(wr, week, run_id)` but different variants; second call MUST no-op (the L518-519 dedup) and the stored variant stays the first one.
- `FreezeRowConcurrencyTests` L777-825 is the analog for the concurrency regression: `test_freeze_row_parallel_invocation_with_variants_preserves_counters` — 50 concurrent invocations across all 7 variant strings produce exactly 50 counter outcomes, no race.

**Helper / fixture pattern (`_valid_row()` at L297-310, `_make_fake_supabase_client()` referenced throughout):** reuse the existing helpers verbatim — they already produce a row that meets `freeze_row` eligibility (`__row_id`, `__week_ending_date`, `Units Completed?`). The new tests just pass additional kwargs.

**Setup/teardown (`_reset_all()` at L289+):** the new tests use the same `_reset_all` to clear `_counters` and the executor singleton between tests. **DO NOT** introduce new global state for variants — the writer is already thread-safe under `_counters_lock`.

---

### 15. `tests/validate_production_safety.py` § window cap bump (test, validator)

**Analog:** `validate_per_group_try_catches_all` at L124-145.

**Core pattern** (L124-145):

```python
# tests/validate_production_safety.py:124-145
def validate_per_group_try_catches_all() -> None:
    name = "Claim 3: per-group try/except catches arbitrary writer exceptions"
    src = Path(REPO_ROOT / "generate_weekly_pdfs.py").read_text(encoding="utf-8")
    idx = src.find("# ── Billing audit snapshot: freeze personnel")
    if idx < 0:
        _record(name, False, "could not locate billing_audit block header")
        return
    # Search window capped at 18kB ...
    window = src[idx:idx + 18000]
    has_broad_except = "except Exception as _audit_err:" in window
    _record(name, has_broad_except, ...)
```

**Patterns to copy:**
- The 18000-character window cap (L140) is the surface the planner needs to monitor. The phase will ADD additional code inside the per-group billing_audit block (new variant tagging passed into `freeze_row(variant=...)`). If the block grows beyond 18000 chars, the regex `has_broad_except` check fails and the validator regresses.
- **Action for the planner:** after counting the new code's character footprint, raise the window cap proportionally (e.g., `idx + 21000`) and document the bump in the inline comment (the L137-139 pattern). Decisions.md 2026-04-25 14:00 corollary rule 3 explicitly binds this requirement.
- **Do NOT** remove the cap entirely — it's a forward-compatibility guard against unrelated code displacing the broad-except clause.

---

## Shared Patterns

These cross-cutting patterns apply to MULTIPLE new files. Reference them
in every plan that touches a relevant file.

### Sanitize-at-every-site (`_RE_SANITIZE_HELPER_NAME`)

**Source:** `generate_weekly_pdfs.py:75` definition + `decisions.md` 2026-04-23 12:00 / 18:25 / round-6 / round-7 / round-9 ledger entries.

**Apply to:** every site that derives a WR# or helper-foreman string in the new code:
- The new loader (no WR sanitization needed — it's keyed on CU codes).
- The new variant branches in `group_source_rows()` (helper names — L3579 pattern).
- The new variant branches in `generate_excel()` (helper names — L3849 pattern).
- The new variant branches in the parser (no sanitization — read-only).
- The new `target_map` for `SUBCONTRACTOR_PPP_SHEET_ID` (WR# sanitization at populate time — L4230 pattern).
- The new upload-task variants in the main loop (sanitized `wr_num` from the main loop — L4951 pattern).

```python
# generate_weekly_pdfs.py:75
_RE_SANITIZE_HELPER_NAME = re.compile(r'[^\w\-]')
```

```python
# Producer + consumer sanitization pattern (idempotent regex)
wr_num = _RE_SANITIZE_HELPER_NAME.sub('_', wr_num)[:50]
helper_sanitized = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]
```

**Why idempotent matters:** double-applying produces the same string, so producer and consumer sites can both apply without canonicalization confusion.

---

### Collision quarantine (target_map + source-side)

**Source:** `generate_weekly_pdfs.py:4223-4275` (target-side) + `:4760-4789` (source-side) + decisions.md 2026-04-23 rounds 6, 7, 9.

**Apply to:** both `target_map` instances (TARGET_SHEET_ID and SUBCONTRACTOR_PPP_SHEET_ID — independent quarantine sets) and the source-side WR pre-scan (single set covers all variants per round-9).

**Critical guardrail:** when a sanitized key collides, delete from `target_map` AND add to `_quarantined_keys` — DO NOT keep first-seen. Loud not-found is strictly safer than silent wrong-row upload (decisions.md round-6 P1).

---

### Default-on kill switch env var

**Source:** `generate_weekly_pdfs.py:399-401` + the matching startup-banner log at L431-442.

**Apply to:** `SUBCONTRACTOR_RATE_VARIANTS_ENABLED` (D-13). Default `'1'`, truthy set `{'1','true','yes','on'}`. State logged in the startup banner so operators grepping the run header can tell at a glance.

---

### `_redact_exception_message` for new Sentry sites

**Source:** `generate_weekly_pdfs.py:504-535` definition + L5407-5427 call-site pattern.

**Apply to:** every new `sentry_capture_with_context(...)` site introduced by this phase. Use `_redact_exception_message(e)` for the `context_data['error_message']` field. NEVER pass raw `str(e)` — `event['contexts']` bypasses `before_send_log` (decisions.md 2026-04-23 12:00 decision (2)).

---

### `_PII_LOG_MARKERS` extension

**Source:** `generate_weekly_pdfs.py:660-668` (group-key markers section).

**Apply to:** every new INFO-level log line introduced by this phase that embeds subcontractor pricing or CU codes or variant group keys. Extend with new tokens (`"_AEPBILLABLE"`, `"_REDUCEDSUB"`, `"_AEPBILLABLE_HELPER_"`, `"_REDUCEDSUB_HELPER_"`, `"AEP BILLABLE GROUP CREATED"`, `"REDUCED SUB GROUP CREATED"`, `"Subcontractor rates CSV missing"`). Decisions.md 2026-04-20 12:00 rule binds: adding a new INFO log that embeds row content requires extending `_PII_LOG_MARKERS` in the same PR.

---

### Idempotent schema DDL

**Source:** `billing_audit/schema.sql:89-95` pattern.

**Apply to:** the new `ALTER TABLE pipeline_run ADD COLUMN IF NOT EXISTS variant TEXT` migration. Position after CREATE TABLE, before CREATE INDEX. Decisions.md 2026-04-25 12:00 rule binds: any new Supabase table/column the pipeline reads or writes MUST have matching DDL in schema.sql committed in the same PR.

---

### `with_retry` + PostgREST classification

**Source:** `billing_audit/client.py` (`with_retry`, `_classify_postgrest_error`, `_PG_SQLSTATE_PERMANENT_PREFIXES`).

**Apply to:** the new `variant` column reads/writes go through the existing `with_retry` wrapper at writer.py L463 and L539 / L566 — NO changes needed to client.py. The TEXT NULL column type is fully covered by the existing SQLSTATE classifier. Decisions.md 2026-04-25 12:00 retryable / permanent prefixes are unchanged.

---

### Time-budget / pre-fetch sub-budget

**Source:** `generate_weekly_pdfs.py` constants `ATTACHMENT_PREFETCH_MAX_MINUTES` / `_FUTURE_TIMEOUT_SEC` / `_GENERATION_HEADROOM_MIN` + decisions.md 2026-04-22 16:05.

**Apply to:** any extension to the attachment-prefetch phase that adds a second target sheet (SUBCONTRACTOR_PPP_SHEET_ID prefetch). The new prefetch MUST share the same sub-budget — `as_completed(futures, timeout=...)`, `executor.shutdown(wait=False, cancel_futures=True)`, NEVER `with ThreadPoolExecutor(...)`. Per-row fallback path stays unchanged.

---

### `_skip_recalc_original_contract` precedence

**Source:** `generate_weekly_pdfs.py:2799-2811`.

**Apply to:** the new variant generation gate. D-22 + D-14 + REQUIREMENTS.md SUB-06 bind: new variant logic runs ONLY on `is_subcontractor_sheet=True` sheets. ORIG-folder skip (L2799-2811) MUST stay primary — if a sheet is misconfigured into BOTH `SUBCONTRACTOR_FOLDER_IDS` and `ORIGINAL_CONTRACT_FOLDER_IDS`, the existing subcontractor-exclusion-is-primary check at L2804 (`and not is_subcontractor_sheet`) preserves correct behavior. Verify via a new regression test in `test_subcontractor_pricing.py` mirroring `TestOriginalContractFolderSkipsRateRecalc` (referenced in CLAUDE.md 2026-04-24 11:30).

---

### openpyxl + safe_merge_cells

**Source:** `.claude/rules/smartsheet-python-optimization.md` §2 + CLAUDE.md "Critical Pitfalls" section + decisions.md 2026-04-17 15:26.

**Apply to:** all new Excel generation paths in `generate_excel()`. **DO NOT** switch to `xlsxwriter` — the rule applies to NEW scripts only; `generate_weekly_pdfs.py` stays on `openpyxl`. Use `safe_merge_cells()` (overlap-detecting helper, examples at L3916/L3922/L3928/L3934). **NEVER** write `oddFooter.right.text` — known corruption vector.

---

## No Analog Found

None. Every new code path in this phase has a direct or close analog in the existing codebase. The helper / vac_crew / build_group_identity / target_map / freeze_row patterns cover every responsibility this phase introduces (CONTEXT D-09/D-10/D-11 anticipates this — the variant infrastructure is the established pattern; the phase EXTENDS it rather than introducing a parallel mechanism).

---

## Metadata

**Analog search scope:**
- `generate_weekly_pdfs.py` (3100+ lines — read targeted line ranges only)
- `billing_audit/{writer,schema}.py` / `schema.sql`
- `tests/test_subcontractor_pricing.py`, `tests/test_vac_crew.py`, `tests/test_security_audit_followup.py`, `tests/test_billing_audit_shadow.py`, `tests/validate_production_safety.py`
- `.github/instructions/subcontractor-pricing-folder-discovery.instructions.md`
- `.planning/intel/{decisions,constraints,contract-schema}.md`

**Files scanned:** 10 deeply, ~5 surface
**Pattern extraction date:** 2026-05-14

---

*Phase: 1-Subcontractor Rate Logic Modification*
*Patterns mapped: 2026-05-14*
