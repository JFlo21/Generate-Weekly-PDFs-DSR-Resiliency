# Phase 14: Foreman Helper #2 - Pattern Map

**Mapped:** 2026-09-05
**Files analyzed:** 20 (17 existing files to modify, 1 optional stub to fill, ~1-2 new test files, N existing test files gaining new cases)
**Analogs found:** 20 / 20 — every touched file's analog is the Helper #1 (or VAC-crew capability-gate) branch **inside the same file**, per D-14-03 ("same stages, same modules"). This phase is a sibling-branch clone, not a new-component build, so "closest analog" below almost always cites a line range in the target file itself.

**How to use this document:** 14-RESEARCH.md already did the file:line impact mapping (Affected Consumers table) — this document supplies the actual code text at each site so the planner can write "copy lines X-Y, change these tokens" instructions instead of re-deriving the code. Every excerpt below was read this session directly from `HEAD`. Do not re-derive line numbers from memory — if more than a few days have elapsed, re-open the cited file before trusting the line numbers.

## File Classification

| File | Role | Data Flow | Analog (same-file line range unless noted) | Match Quality | Disposition (from RESEARCH) |
|---|---|---|---|---|---|
| `pipeline/discovery.py` | service (column discovery) | transform | `synonyms` dict (self, ~555-579); `_build_discovery_skip_index` (self, 190-297) | exact | CHANGE |
| `pipeline/fetch.py` | service (row ingestion) | transform | `sheet_has_vac_crew_columns` capability gate (self, 566-570); Helper #1 row detection (self, 851-885) | exact | CHANGE |
| `pipeline/grouping.py` | service (business logic / grouping) | transform | Helper #1 pre-pass exclusion (self, 372-379); main-loop exclusion + key emission (self, 614-745); subcontractor shadow partition (self, 785-1188) | exact | CHANGE |
| `pipeline/change_detection.py` | service (hashing / identity) | transform | variant-gated meta block (self, 417-437); aggregated hash sub-bucketing (self, 520-538); filename reserved-token dispatch (self, 751-814) | exact | CHANGE (3 sites) / NO CHANGE (`_extended_row_fields`, 48-90) |
| `pipeline/excel.py` | output (workbook renderer) | file I/O | filename-suffix `elif` chain (self, 271-374); REPORT DETAILS header dispatch (self, 545-582) | exact | CHANGE |
| `pipeline/orchestrate.py` | service (single dispatch chokepoint) | transform | `derive_group_identity` (self, 460-534) | exact | CHANGE — single highest-leverage, lowest-risk site |
| `pipeline/cleanup.py` | service (attachment lifecycle) | batch | `_HELPER_VARIANTS_FOR_ORPHAN_GATE` (self, 518-520) | exact | CHANGE (new finding, not in original audit scope) |
| `pipeline/upload.py` | service (upload routing) | request-response | PPP dual-route gate (self, 343) | exact | CHANGE (new finding) |
| `billing_audit/writer.py` | service (Supabase writer) | CRUD | `_SENTINEL_CLAIMERS`/`is_sentinel_claimer` (self, 96-115); `freeze_row` all-sentinel gate (self, 625-655); `ROLE_BY_VARIANT`/`resolve_claimer` (self, 1047-1140) | exact | CHANGE — one CRITICAL (freeze_row) |
| `billing_audit/schema.sql` | migration (Supabase RPC) | CRUD | `freeze_attribution` param doc (self, 180-201); `lookup_attribution` DROP-first (self, 336-373); `lookup_attribution_bulk` (self, 375-414+) | exact | PROTECTED — `checkpoint:decision` |
| `pipeline_memory/schema.sql` | migration | CRUD | `row_state` helper columns (self, 100-126) | exact | CHANGE (additive) |
| `pipeline_memory/writer.py` | service (Supabase writer) | CRUD | `HASH_FIELDS` tuple (self, 615-632); payload builder (self, 786-809) | exact | CHANGE (columns) / PLANNER DECISION (hash inclusion) |
| `scripts/publish_artifacts_to_supabase.py` | script (batch publisher) | batch/transform | `_CANONICAL_VARIANTS` + `normalize_variant` precedence chain (self, 85-141) | exact | CHANGE |
| `portal-v2/src/lib/variantLabels.ts` | utility (frontend label map) | transform | `VARIANT_LABELS`/`getVariantLabel` (self, whole 22-line file) | exact | ADDITIVE |
| `portal-v2/src/components/artifacts/VariantFilterBar.tsx` | component | transform | consumes `getVariantLabel()` only, no direct variant-string logic (per RESEARCH grep) | n/a | ADDITIVE, likely no change |
| `pipeline/types.py` | model/types stub | n/a | current 24-line empty stub (self, whole file) | n/a — optional landing spot | Claude's Discretion (dataclass shape) |
| `pipeline/config.py` | config | n/a | `SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED` flag idiom (self, 368-370) | exact | CHANGE (new `HELPER2_ENABLED` flag, D-14-12) |
| `tests/test_foreman_helper_2.py` (new) | test | n/a | `tests/test_group_identity_and_header_foreman.py` header/fixture style (1-60); prototype's renamed `.txt` tests for fixture shapes | role-match | NEW FILE (Wave 0 gap) |
| `tests/test_group_identity_and_header_foreman.py`, `tests/test_change_detection_tiebreak.py`, `tests/test_billing_audit_shadow.py`, `tests/test_pipeline_memory_shadow.py`, `tests/test_publish_artifacts_to_supabase.py`, `tests/test_subcontractor_helper_shadow_rescue.py` (new cases) | test | n/a | existing Helper #1 test cases in the same files (byte-identity regression pattern) | exact | ADD CASES, no new file |
| `tests/test_vac_crew.py`, `test_vac_crew_claim_attribution.py`, `test_vac_crew_exclusion_leak.py` | test | n/a | existing, unchanged | n/a | REGRESSION-TEST-ONLY (run, don't edit) |

---

## Pattern Assignments

### `pipeline/discovery.py` (service, transform)

**Analog:** same file — `synonyms` dict and `_build_discovery_skip_index`

**Synonyms dict — add 6 entries here** (`pipeline/discovery.py:555-579`, read this session):
```python
synonyms = {
    'Foreman':'Foreman','Work Request #':'Work Request #', ...
    'Job #':'Job #','Units Completed?':'Units Completed?','Units Completed':'Units Completed?',
    # Helper variant columns (exact names with brackets as authoritative)
    'Helper Job [#]':'Helper Job #',  # Exact spelling with brackets
    'Helper Job':'Helper Job #',      # Fallback synonym
    'Helper Job #':'Helper Job #',    # Ensure direct exact match is captured
    'Helper Dept #':'Helper Dept #',
    'Foreman Helping?':'Foreman Helping?',
    'Helping Foreman Completed Unit?':'Helping Foreman Completed Unit?',
    # VAC Crew variant columns (row-level detection — mirrors helper pattern)
    'VAC Crew Helping?':'VAC Crew Helping?',
    ...
}
```
Add the Helper #2 mirror (D-14-10's 6 exact titles), following the SAME bracket-handling idiom used for `Helper Job [#]` → canonical `Helper Job #`:
```python
'Foreman Helping? #2':'Foreman Helping? #2',
'Foreman Helper #2 Active?':'Foreman Helper #2 Active?',
'Helping Foreman #2 Completed Unit?':'Helping Foreman #2 Completed Unit?',
'Helper #2 Dept #':'Helper #2 Dept #',
'Helper #2 Job [#]':'Helper #2 Job #',   # bracket form -> canonical, mirrors Helper Job [#]
'Foreman Helper #2 Email':'Foreman Helper #2 Email',
```

**Skip-index admission — mapping-schema-marker gap (D-14-10)** (`pipeline/discovery.py:190-297`, read this session, full function body). Key excerpt — the exact condition set that admits a cached mapping WITHOUT re-deriving synonyms:
```python
for sid in candidate_ids:
    watermark = watermarks.get(sid)
    if watermark is None:
        continue
    live_version = live_versions.get(sid)
    if live_version is None:
        continue
    if watermark.get('last_sheet_version') != live_version:
        continue
    mapping = watermark.get('column_mapping')
    if not mapping or 'Weekly Reference Logged Date' not in mapping:
        continue
    name = watermark.get('name')
    if not name:
        continue
    index[sid] = {'id': sid, 'name': name, 'column_mapping': mapping}
```
The docstring (190-219) explicitly enumerates the "ALL of" conditions for admission — this is the exact spot to add a 6th condition: a mapping-schema marker so a pre-Helper-#2 cached `column_mapping` (written before these 6 synonyms existed) falls through to full validation once. **Never weaken the existing 5 conditions** — only add a 6th `continue`-gate.

**Acceptance gate (NO CHANGE — confirm only)** (`pipeline/discovery.py:668-681`):
```python
if 'Weekly Reference Logged Date' in mapping:
    ...
    return {'id': sid,'name': sheet.name,'column_mapping': mapping}
else:
    logging.warning(f"❌ Skipping sheet {sheet.name} (ID {sid}) - Weekly Reference Logged Date not found (strict mode)")
    return None
```
This is the ONLY strict-mode gate — Helper #2 columns never enter it. Confirmed this is why Intake 8 (D-14-01) is still accepted today.

**Failed-read handling (NO CHANGE — Helper #2 must never route through this)** (`pipeline/discovery.py:682-697`):
```python
except Exception as e:
    logging.warning(f"⚡ Failed to validate sheet {sid}: {e}")
    sentry_capture_sheet_drop(sid, e)
    _failed_validation_sids.append(sid)
    return None
```
"No Helper #2 columns" is a legitimate mapping outcome (return the mapping, log a capability-unavailable reason) — it must NEVER raise into this `except` block.

---

### `pipeline/fetch.py` (service, transform)

**Analog:** same file — `sheet_has_vac_crew_columns` (capability gate to MIRROR) + Helper #1 row detection (eligibility formula to SLOT-SHIFT)

**Capability gate — D-14-04 explicitly picks THIS pattern over Helper #1's own log-only check** (`pipeline/fetch.py:553-570`):
```python
# HELPER DETECTION LOGGING: Check if helper columns are present
helper_columns = ['Foreman Helping?', 'Helping Foreman Completed Unit?', 'Helper Dept #', 'Helper Job #']
found_helper_cols = [col for col in helper_columns if col in column_mapping]
if found_helper_cols:
    logging.info(f"🔧 Helper columns found in {source['name']}: {found_helper_cols}")
    if len(found_helper_cols) == 4:
        logging.info(f"✅ All 4 helper columns present - helper detection will be active for this sheet")
    else:
        missing = [col for col in helper_columns if col not in column_mapping]
        logging.warning(f"⚠️ Missing helper columns in {source['name']}: {missing}")
else:
    logging.info(f"ℹ️ No helper columns found in {source['name']} - helper detection disabled for this sheet")

# VAC CREW DETECTION: Check if VAC Crew columns are present (row-level detection)
vac_crew_columns = ['VAC Crew Helping?', 'Vac Crew Completed Unit?', 'VAC Crew Dept #', 'Vac Crew Job #']
found_vac_crew_cols = [col for col in vac_crew_columns if col in column_mapping]
# Sheet has VAC Crew capability if at least the two key columns are mapped
sheet_has_vac_crew_columns = 'VAC Crew Helping?' in column_mapping and 'Vac Crew Completed Unit?' in column_mapping
```
Helper #2's capability gate is a **hard boolean** modeled on `sheet_has_vac_crew_columns`, not the log-only `found_helper_cols` pattern:
```python
sheet_has_helper2_columns = (
    'Foreman Helping? #2' in column_mapping
    and 'Helping Foreman #2 Completed Unit?' in column_mapping
    and 'Helper #2 Dept #' in column_mapping
)
```
(name + completed + dept — the three key columns per D-14-04; `Active?`/`Email` never gate.)

**Row detection — the exact formula to slot-shift** (`pipeline/fetch.py:851-885`):
```python
# Helper row detection (before foreman assignment)
# Helper criteria: Foreman Helping? non-blank AND both checkboxes checked
# Handle None values safely with defensive str() conversion to prevent float/strip errors
foreman_helping_val = row_data.get('Foreman Helping?')
helper_name = str(foreman_helping_val).strip() if foreman_helping_val else ''
helping_foreman_completed = row_data.get('Helping Foreman Completed Unit?')
helping_foreman_completed_checked = is_checked(helping_foreman_completed)

is_helper_row = bool(helper_name and helping_foreman_completed_checked and units_completed_checked)

...
if is_helper_row:
    # Populate helper metadata (with safe None handling and defensive str() conversion)
    row_data['__is_helper_row'] = True
    row_data['__helper_foreman'] = helper_name
    helper_dept_val = row_data.get('Helper Dept #')
    helper_job_val = row_data.get('Helper Job #')
    row_data['__helper_dept'] = str(helper_dept_val).strip() if helper_dept_val else ''
    row_data['__helper_job'] = str(helper_job_val).strip() if helper_job_val else ''
else:
    row_data['__is_helper_row'] = False
```
**Deviation required by D-14-05** (fabricated-claim guard, day-one, unlike Helper #1's inherited `"NA"` quirk): route `helper2_name` through a formula-error guard before the truthiness check, e.g. the prototype's `normalize_helper_value()` shape (see Shared Patterns below) instead of the bare `str(...).strip()` Helper #1 uses. Slot-shifted field names: `Foreman Helping? #2` → `__is_helper2_row` / `__helper2_foreman` / `__helper2_dept` / `__helper2_job`. `Foreman Helper #2 Active?` / `Foreman Helper #2 Email` are read nowhere in the gating formula — confirmed Helper #1 ignores its own `Active?`/`Email` columns the same way.

**Dual-checkbox diagnostic recompute (optional clone or fold-in)** (`pipeline/fetch.py:974-981`):
```python
_vc_helping = str(row_data.get('VAC Crew Helping?') or '').strip()
_vc_completed = is_checked(row_data.get('Vac Crew Completed Unit?'))
_fh_helping = str(row_data.get('Foreman Helping?') or '').strip()
_fh_completed = is_checked(row_data.get('Helping Foreman Completed Unit?'))
_is_specialized = (
    (bool(_vc_helping) and _vc_completed)
    or (bool(_fh_helping) and _fh_completed)
)
```
This only affects a log tag on the price-exclusion diagnostic path (non-functional). Either clone with `_fh2_*` variables or fold into `_is_specialized`'s `or` chain — planner's call.

---

### `pipeline/grouping.py` (service, transform)

**Analog:** same file — Helper #1's pre-pass exclusion, main-loop exclusion + key emission, and subcontractor shadow partition

**Pre-pass exclusion (billing_audit primary-claimer resolution)** (`pipeline/grouping.py:370-379`):
```python
if _r.get('__is_vac_crew'):
    continue
# Valid helper rows are excluded from the primary emission
# path, so resolving their primary claimer is pure overhead.
if (
    _r.get('__is_helper_row')
    and _r.get('__helper_foreman')
    and _r.get('__helper_dept')
):
    continue
```
Add the identical guard for Helper #2 (`__is_helper2_row` / `__helper2_foreman` / `__helper2_dept`), same position, same short-circuit logic. Note VAC-crew exclusion comes FIRST — preserve ordering.

**Main-loop exclusion + key emission (D-14-06's core mirror site)** (`pipeline/grouping.py:614-742`):
```python
helper_mode_enabled = RES_GROUPING_MODE in ('helper', 'both')

valid_helper_row = False
if helper_mode_enabled and is_helper_row and helper_foreman:
    helper_dept = r.get('__helper_dept', '')
    helper_job = r.get('__helper_job', '')
    # Validate helper row: helper_dept is required, helper_job is OPTIONAL
    if helper_dept:
        valid_helper_row = True

if RES_GROUPING_MODE == 'primary':
    ...
elif RES_GROUPING_MODE in ('helper', 'both'):
    if not is_subcontractor_row and not valid_helper_row:
        ...  # primary emission
    elif is_subcontractor_row and not valid_helper_row:
        logging.debug(f"➖ EXCLUDING from main Excel (subcontractor row): ...")
    elif valid_helper_row:
        logging.info(f"➖ EXCLUDING from main Excel: WR={wr_key}, Week={week_end_for_key} (Helper row with both checkboxes)")

# Helper variant - ONLY created when mode allows it
if valid_helper_row and helper_mode_enabled:
    helper_dept = r.get('__helper_dept', '')
    helper_job = r.get('__helper_job', '')
    helper_sanitized = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]
    helper_key = f"{week_end_for_key}_{wr_key}_HELPER_{helper_sanitized}"
    if not is_subcontractor_row:
        keys_to_add.append(('helper', helper_key, helper_foreman))
        logging.info(f"🔧 HELPER GROUP CREATED: WR={wr_key}, Week={week_end_for_key}, Helper={helper_foreman}, Dept={helper_dept}, Job={helper_job}")
    else:
        logging.debug(f"➖ EXCLUDING from main Excel (subcontractor legacy helper): ...")
elif is_helper_row and not helper_mode_enabled:
    logging.info(f"ℹ️ Helper row found but RES_GROUPING_MODE={RES_GROUPING_MODE} - including in main Excel")
elif is_helper_row:
    logging.warning(f"⚠️ Helper row for WR {wr_key} missing required Helper Dept # (Job: '{helper_job}') - including in main Excel")
```
**Pitfall 2 warning (real `[2026-05-19 22:00]` incident):** the `if not is_subcontractor_row: keys_to_add.append(...) else: <debug log>` guard at the `('helper', ...)` emission site MUST be copied verbatim onto the new `('helper2', ...)` emission site — this exact class of miss (guard on one branch, forgotten on its sibling) produced a live duplicate-billing artifact. `RES_GROUPING_MODE` is the SAME kill switch for both slots — do not add a second env var.

**Subcontractor shadow partition — primary leg gate** (`pipeline/grouping.py:800-820`):
```python
# a helper-COMPLETED subcontractor row (``Units Completed?`` AND
# ``Helping Foreman Completed Unit?`` both checked, with a valid
# ``Foreman Helping?`` + helper dept) belongs SOLELY to the
# helper-shadow files below
_sub_is_valid_helper_row = (
    not is_vac_crew_row
    and RES_GROUPING_MODE in ('helper', 'both')
    and is_helper_row
    and bool(helper_foreman)
    and bool(r.get('__helper_dept', ''))
)
```
Helper #2 needs `_sub_is_valid_helper2_row` computed the identical way from `__is_helper2_row` / `__helper2_foreman` / `__helper2_dept`.

**Subcontractor shadow variant emission — the exact shape to clone for `reduced_sub_helper2`/`aep_billable_helper2`** (`pipeline/grouping.py:1146-1188`):
```python
_helper_sanitized = (
    _RE_SANITIZE_HELPER_NAME.sub('_', _attributed_helper)[:50]
)
rs_helper_key = (
    f"{week_end_for_key}_{wr_key}_REDUCEDSUB_HELPER_"
    f"{_helper_sanitized}"
)
keys_to_add.append(
    ('reduced_sub_helper', rs_helper_key, _attributed_helper)
)
if rs_helper_key not in groups:
    logging.info(f"🔻 REDUCED SUB HELPER GROUP CREATED: ...")
if (
    _snap_for_cutoff is not None
    and _snap_for_cutoff.date() >= _AEP_BILLABLE_CUTOFF
):
    aep_helper_key = (
        f"{week_end_for_key}_{wr_key}_AEPBILLABLE_HELPER_"
        f"{_helper_sanitized}"
    )
    keys_to_add.append(
        ('aep_billable_helper', aep_helper_key, _attributed_helper)
    )
```
`_attributed_helper` here is resolved via `resolve_claimer('helper', ...)` earlier in the same block (grep `resolve_claimer\(` in `grouping.py` for the exact call site — lines ~1007-1130 build `_attribution_reason`/`_remediation` and the `_bug_c_warning_seen` per-WR dedupe set). Helper #2's shadow leg calls `resolve_claimer('helper2', ...)` once `ROLE_BY_VARIANT` (billing_audit/writer.py) knows that variant — reuse the `_bug_c_warning_seen` set and remediation-text branching verbatim, just key on the Helper #2 tuple too.

---

### `pipeline/change_detection.py` (service, transform)

**Analog:** same file — variant-gated meta block (mirror), aggregated hash sub-bucketing (mirror, new finding), filename dispatch (extend), base fields (leave alone)

**Base hash fields — NO CHANGE, confirm variant-agnostic** (`pipeline/change_detection.py:60-78`, `_extended_row_fields`): 16 fields (WR, snapshot date, CU, quantity, price, pole, work type, dept, scope, completed, customer, job, work order, CU description, UOM, area) — no helper fields. Do not add Helper #2 fields here.

**Variant-gated meta — THE pattern that makes HLP-06 byte-identity hold** (`pipeline/change_detection.py:410-437`):
```python
meta_parts = []
meta_parts.append(f"FOREMAN={group_foreman or ''}")

variant = group_variant
meta_parts.append(f"VARIANT={variant}")

if variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):
    _first = sorted_rows[0] if sorted_rows else {}
    helper_foreman = _first.get('__helper_foreman', '')
    helper_dept = _first.get('__helper_dept', '')
    helper_job = _first.get('__helper_job', '')
    if not helper_foreman or not helper_dept:
        logging.warning(f"⚠️ Helper variant missing required fields: foreman={helper_foreman}, dept={helper_dept}")
    if not helper_job:
        logging.info(f"ℹ️ Helper variant without Job #: foreman={helper_foreman}, dept={helper_dept} (proceeding anyway)")
    meta_parts.append(f"HELPER={helper_foreman}")
    meta_parts.append(f"HELPER_DEPT={helper_dept}")
    meta_parts.append(f"HELPER_JOB={helper_job}")
```
Add a **sibling** block: `if variant in ('helper2', 'aep_billable_helper2', 'reduced_sub_helper2'): meta_parts.append(f"HELPER2={helper2_foreman}") ...`. **Never widen the existing tuple** — that would collapse Helper #1/#2 hash-meta shape and violate HLP-02.

**Aggregated hash sub-bucketing — NEW FINDING this session, must be replicated** (`pipeline/change_detection.py:512-541`, `_compute_aggregated_content_hash`):
```python
by_variant: dict[str, list[dict]] = {}
for r in rows:
    v = r.get('__variant', 'primary')
    by_variant.setdefault(v, []).append(r)

parts: list[str] = []
for v in sorted(by_variant.keys()):
    variant_rows = by_variant[v]
    if v == 'helper':
        sub: dict[tuple[str, str, str], list[dict]] = {}
        for r in variant_rows:
            sk = (
                str(r.get('__helper_foreman', '')),
                str(r.get('__helper_dept', '')),
                str(r.get('__helper_job', '')),
            )
            sub.setdefault(sk, []).append(r)
        sub_parts = [
            f"{sk}={calculate_data_hash(sub[sk])}"
            for sk in sorted(sub.keys())
        ]
        variant_hash = hashlib.sha256(
            "|".join(sub_parts).encode('utf-8')
        ).hexdigest()[:16]
    else:
        variant_hash = calculate_data_hash(variant_rows)
    parts.append(f"{v}={variant_hash}")
```
Copy the `if v == 'helper':` branch's exact shape for `v == 'helper2'` (sub-bucket by `(__helper2_foreman, __helper2_dept, __helper2_job)`) — WITHOUT this, a `helper2` bucket aggregating rows from 2+ distinct Helper #2 foremen silently depends on row sort order (Pitfall 5).

**Filename reserved-token dispatch — extend the earliest-position scan** (`pipeline/change_detection.py:751-814`):
```python
_reserved_positions = {
    _tok: tail.index(_tok)
    for _tok in ('AEPBillable', 'ReducedSub', 'VacCrew', 'Helper', 'User')
    if _tok in tail
}
_first_marker = (
    min(_reserved_positions, key=lambda _t: _reserved_positions[_t])
    if _reserved_positions else None
)
if _first_marker == 'AEPBillable':
    aep_idx_rel = tail.index('AEPBillable')
    post_aep = tail[aep_idx_rel + 1:]
    if post_aep and post_aep[0] == 'User':
        variant = 'aep_billable'
        identifier = '_'.join(post_aep[1:])
    elif 'Helper' in post_aep:
        variant = 'aep_billable_helper'
        helper_idx_rel = post_aep.index('Helper')
        if helper_idx_rel + 1 < len(post_aep):
            identifier = '_'.join(post_aep[helper_idx_rel + 1:])
    else:
        variant = 'aep_billable'
        identifier = ''
elif _first_marker == 'ReducedSub':
    ...  # identical shape, 'reduced_sub' / 'reduced_sub_helper'
elif _first_marker == 'VacCrew':
    ...
elif _first_marker == 'Helper':
    variant = 'helper'
    helper_idx_rel = tail.index('Helper')
    if helper_idx_rel + 1 < len(tail):
        identifier = '_'.join(tail[helper_idx_rel + 1:])
elif _first_marker == 'User':
    ...
```
Add `'Helper2'` to the `_reserved_positions` tuple, add `elif _first_marker == 'Helper2':` mirroring the `'Helper'` branch, AND add a nested `elif 'Helper2' in post_aep:` / `elif 'Helper2' in post_rs:` check inside the AEPBillable/ReducedSub branches (checked BEFORE the bare `Helper` check inside those branches, since a real filename could theoretically contain both tokens as adjacent list elements — verify with a negative test). `tail` is a list of underscore-split tokens, so `"Helper2"` and `"Helper"` are distinct list elements and never collide — confirmed this session.

---

### `pipeline/excel.py` (output, file I/O)

**Analog:** same file — three separate `elif` branches (filename) + two-branch header dispatch

**Filename suffix — THREE SEPARATE exact-match `elif` branches, not a tuple check** (`pipeline/excel.py:282-344`):
```python
elif variant == 'aep_billable_helper':
    helper_foreman = first_row.get('__helper_foreman', '')
    if not helper_foreman:
        logging.error(f"⚠️ aep_billable_helper variant row missing __helper_foreman for WR {wr_num} week {week_end_raw}; filename would be ambiguous — raising to surface data drift.")
        raise ValueError(f"aep_billable_helper requires __helper_foreman; got empty for WR={wr_num} week={week_end_raw}")
    helper_sanitized = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]
    variant_suffix = f"_AEPBillable_Helper_{helper_sanitized}"
elif variant == 'reduced_sub_helper':
    helper_foreman = first_row.get('__helper_foreman', '')
    if not helper_foreman:
        logging.error(f"⚠️ reduced_sub_helper variant row missing __helper_foreman ...")
        raise ValueError(f"reduced_sub_helper requires __helper_foreman; got empty for WR={wr_num} week={week_end_raw}")
    helper_sanitized = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]
    variant_suffix = f"_ReducedSub_Helper_{helper_sanitized}"
elif variant == 'helper':
    helper_foreman = first_row.get('__helper_foreman', '')
    if helper_foreman:
        helper_sanitized = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]
        variant_suffix = f"_Helper_{helper_sanitized}"
```
Add THREE new sibling `elif` branches for `aep_billable_helper2` / `reduced_sub_helper2` / `helper2`, reading `__helper2_foreman`, producing `_AEPBillable_Helper2_<name>` / `_ReducedSub_Helper2_<name>` / `_Helper2_<name>`. **Do not fold into the existing branches** — this is exact-match `elif`, so a missed branch falls through toward `primary`/`vac_crew` (Pitfall 1, the real `[2026-05-21 12:35]` incident class). The two shadow branches defensively `raise ValueError` on empty foreman; the plain `helper` branch silently no-ops (documented, deliberately out-of-scope legacy gap) — mirror the shadow branches' defensive raise for the Helper #2 shadow pair too (D-14-05 wants day-one guards).

**REPORT DETAILS header dispatch — preserve the `current_foreman`-vs-`__helper_foreman` asymmetry** (`pipeline/excel.py:545-566`):
```python
if variant == 'helper':
    display_foreman = first_row.get('__helper_foreman', 'Unknown Helper')
    display_dept = first_row.get('__helper_dept', '')
    display_job = first_row.get('__helper_job', '')
elif variant in ('reduced_sub_helper', 'aep_billable_helper'):
    # the line items belong to the helper, so Dept # / Job # MUST come
    # from the helper fields ... the displayed Foreman, however, stays
    # `current_foreman`: for these variants that is the ATTRIBUTED
    # helper (the file's partition key), NOT `__helper_foreman` (the
    # current "Foreman Helping?" value, which can diverge from the
    # frozen attribution under Phase 1.1).
    display_foreman = current_foreman
    display_dept = first_row.get('__helper_dept', '')
    display_job = first_row.get('__helper_job', '')
```
Mirror both branches for `helper2` / `{aep_billable,reduced_sub}_helper2`, preserving the EXACT `current_foreman`-vs-`__helper2_foreman` distinction — this asymmetry is intentional (ledger `[2026-05-21 12:35]`), do not "fix" it into consistency for Helper #2 either.

---

### `pipeline/orchestrate.py` (service, single dispatch chokepoint — HIGHEST LEVERAGE FILE)

**Analog:** same file — `derive_group_identity`, full function read this session (`pipeline/orchestrate.py:460-534`):
```python
def derive_group_identity(
    first_row: dict,
    *,
    primary_claim_enabled: bool,
    vac_crew_claim_enabled: bool,
    res_grouping_mode: str,
) -> tuple[str, str]:
    variant = first_row.get('__variant', 'primary')
    if variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):
        helper_foreman = first_row.get('__helper_foreman', '')
        helper_dept = first_row.get('__helper_dept', '')
        helper_job = first_row.get('__helper_job', '')
        identifier = f"{helper_foreman}|{helper_dept}|{helper_job}"
        file_identifier = (
            _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]
            if helper_foreman else ''
        )
        return identifier, file_identifier
    if variant == 'vac_crew':
        ...
    if variant in ('reduced_sub', 'aep_billable'):
        ...
    if primary_claim_enabled and res_grouping_mode in ('helper', 'both'):
        ...
    # Legacy primary identity: the row's ``User`` field.
    user_val = first_row.get('User')
    identifier = (
        _RE_SANITIZE_IDENTIFIER.sub('_', user_val)[:50] if user_val else ''
    )
    return identifier, identifier
```
Because of this extraction, Helper #2 needs exactly **ONE** new branch here (mirroring the first `if`), which automatically feeds all 3 call sites (main-loop identifier/file_identifier/history_key; `valid_wr_weeks` cleanup tuple; `current_keys` hash-history prune) — this is the single lowest-risk, highest-leverage site in the whole change. `tests/test_group_identity_and_header_foreman.py` already pins this function's contract per-branch — extend it with a Helper #2 case, not a new test file for this one function.

---

### `pipeline/cleanup.py` (service, batch lifecycle)

**Analog:** same file — `_HELPER_VARIANTS_FOR_ORPHAN_GATE` (NEW FINDING, not in original audit-scope anchor list)

(`pipeline/cleanup.py:490-549`, full context read this session):
```python
_HELPER_VARIANTS_FOR_ORPHAN_GATE = frozenset({
    'helper', 'aep_billable_helper', 'reduced_sub_helper'
})
if (
    variant == 'primary'
    and ident not in valid_wr_weeks
    and any(
        _vw[0] == wr
        and _vw[1] == week
        and _vw[2] in _HELPER_VARIANTS_FOR_ORPHAN_GATE
        for _vw in valid_wr_weeks
    )
):
    ...
    off_contract_attachments.append(att)
    logging.info(f"🔄 Variant-migration orphan detected: primary attachment {att.name!r} superseded by live helper for WR {wr} week {week}. Queued for deletion.")
    continue
```
**MUST add** `'helper2'` / `'aep_billable_helper2'` / `'reduced_sub_helper2'` to this frozenset — otherwise a primary attachment superseded ONLY by a Helper #2 claim is never flagged as a migration orphan (stale-file risk per the docstring at 490-517, describing the exact `[2026-06-02]` defect this gate was written to catch). One-time legacy-migration gates elsewhere in this file (198-293, 385-470) and the sentinel-superseded gate (89-196, 548-611) are variant-string-scoped to KNOWN existing identities and correctly need NO code change — regression test only.

---

### `pipeline/upload.py` (service, request-response)

**Analog:** same file — PPP dual-route gate, `pipeline/upload.py:343` (NEW FINDING, not in original audit-scope anchor list which cited only `upload.py:42`, a docstring):
```python
# Second leg — only for reduced_sub variants per D-12 / SUB-03.
if variant in ('reduced_sub', 'reduced_sub_helper'):
    if primary_present and wr_num in target_map_ppp:
        upload_tasks.append({
            'excel_path': excel_path,
            'filename': filename,
            'wr_num': wr_num,
            'target_row': target_map_ppp[wr_num],
            'target_sheet_id': SUBCONTRACTOR_PPP_SHEET_ID,
            'variant': variant,
            ...
        })
```
**MUST add** `'reduced_sub_helper2'` to this tuple — the prototype's equivalent patch hunk (read this session) does exactly this:
```python
if variant in (
    'reduced_sub',
    'reduced_sub_helper',
    'reduced_sub_helper2',
):
```
Without it, a subcontractor Helper #2 shadow file uploads to `TARGET_SHEET_ID` only and the subcontractor never sees it on the PPP sheet — silent routing gap, not a crash, so it would not surface in a smoke test that only checks "did a file get produced."

---

### `billing_audit/writer.py` (service, CRUD — Supabase writer)

**Analog:** same file — `_SENTINEL_CLAIMERS`, `freeze_row`'s all-sentinel gate (CRITICAL), `ROLE_BY_VARIANT`/`resolve_claimer`

**Sentinel claimers (ADDITIVE only if Excel introduces a new placeholder string)** (`billing_audit/writer.py:96-115`):
```python
_SENTINEL_CLAIMERS: frozenset[str] = frozenset({
    "unknown foreman",
    "unknown",
    "unknown helper",
    "unknown vac crew",
    "no match",
})

def is_sentinel_claimer(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text or text.startswith("#"):
        return True
    normalized = " ".join(text.replace("_", " ").split()).casefold()
    return normalized in _SENTINEL_CLAIMERS
```
If Helper #2's Excel display fallback introduces `'Unknown Helper 2'` (mirroring `excel.py`'s `'Unknown Helper'` fallback), add its normalized form here — the casefold+`_`→space normalization already treats `Unknown_Helper_2` and `unknown helper 2` identically once added.

**`freeze_row` all-sentinel short-circuit — CRITICAL, silent-drop risk** (`billing_audit/writer.py:625-655`):
```python
p_primary = _null_if_named_sentinel(
    row.get("__effective_user")
    or row.get("Foreman")
    or None
)
p_helper = _null_if_named_sentinel(row.get("__helper_foreman"))
p_vac_crew = _null_if_named_sentinel(row.get("__vac_crew_name"))
if all(
    is_sentinel_claimer(v) for v in (p_primary, p_helper, p_vac_crew)
):
    _bump_counter("sentinel_freezes_deferred")
    return False

params = {
    "p_wr": wr,
    "p_week_ending": week_ending.isoformat(),
    "p_smartsheet_row_id": row_id,
    "p_primary": p_primary,
    "p_helper": p_helper,
    "p_helper_dept": row.get("__helper_dept"),
    "p_vac_crew": p_vac_crew,
    "p_pole": (row.get("Pole #") or row.get("Point #") or row.get("Point Number")),
    "p_cu": row.get("CU") or row.get("Billable Unit Code"),
    "p_work_type": row.get("Work Type"),
    "p_release": release,
    "p_run_id": run_id,
}
```
**MUST**: compute `p_helper2 = _null_if_named_sentinel(row.get("__helper2_foreman"))` AND add `p_helper2` to the `all(is_sentinel_claimer(v) for v in (...))` tuple in the SAME edit — otherwise a row where Helper #2 is the ONLY real claimer (primary/helper/vac_crew all sentinel) is misclassified as fully-sentinel and `freeze_attribution` is never called: no error, no distinguishable log, and the Helper #2 freeze silently never happens (Pitfall 4). Add `p_helper2`/`p_helper2_dept` to the `params` dict too, once the schema.sql migration lands (see PROTECTED section below) — plan for the "column doesn't exist yet" fallback per D-14-07.

**`ROLE_BY_VARIANT` / `resolve_claimer`** (`billing_audit/writer.py:1047-1140`):
```python
ROLE_BY_VARIANT: dict[str, str] = {
    "primary": "primary_foreman",
    "reduced_sub": "primary_foreman",
    "aep_billable": "primary_foreman",
    "helper": "helper",
    "reduced_sub_helper": "helper",
    "aep_billable_helper": "helper",
    "vac_crew": "vac_crew",
}
```
Add:
```python
"helper2": "helper2",
"reduced_sub_helper2": "helper2",
"aep_billable_helper2": "helper2",
```
The `"helper2"` role key only resolves to a real value once the RPC actually returns a `helper2` column (see schema.sql PROTECTED section). `resolve_claimer`'s decision table (1058-1140: `disabled` → use current; `fetch_failure` → hold; `no_row` → use current/no_history; frozen sentinel → treat as no-history) needs zero structural changes — it's already variant-generic via `ROLE_BY_VARIANT.get(variant, "primary_foreman")`.

---

### `billing_audit/schema.sql` (migration, CRUD — PROTECTED, `checkpoint:decision` required)

**Analog:** same file — the DROP-first pattern documented for `lookup_attribution`

**`freeze_attribution` RPC contract (params doc only, body lives in Supabase)** (`billing_audit/schema.sql:180-201`):
```sql
--   PARAMETERS (all named, p_<name>):
--     p_wr               TEXT
--     p_week_ending      DATE
--     p_smartsheet_row_id BIGINT
--     p_primary          TEXT  (resolved foreman, may be NULL)
--     p_helper           TEXT  (helper foreman, NULL on primary rows)
--     p_helper_dept      TEXT
--     p_vac_crew         TEXT
--     p_pole             TEXT
--     p_cu               TEXT
--     p_work_type        TEXT
--     p_release          TEXT
--     p_run_id           TEXT
```
Add `p_helper2 TEXT`, `p_helper2_dept TEXT` — but the FUNCTION BODY is deployed directly in Supabase (not in this repo), so this migration needs an operator step outside repo-only changes, sequenced behind its own `checkpoint:decision` per D-14-07.

**`lookup_attribution` — the exact DROP-first idiom to copy for the Helper #2 return columns** (`billing_audit/schema.sql:332-373`):
```sql
-- The DROP is REQUIRED: an earlier helper-only version of this function
-- returned (helper, helper_dept, source_run_id). Postgres CREATE OR
-- REPLACE FUNCTION cannot change a function's return columns, so a bare
-- CREATE OR REPLACE over the helper-only version fails with "cannot
-- change return type of existing function" — which is why the multi-role
-- contract silently never deployed (incident 2026-05-27). DROP FUNCTION
-- IF EXISTS first, then create the 5-column version below.
DROP FUNCTION IF EXISTS billing_audit.lookup_attribution(TEXT, DATE, BIGINT);

CREATE FUNCTION billing_audit.lookup_attribution(
    p_wr                TEXT,
    p_week_ending       DATE,
    p_smartsheet_row_id BIGINT
)
RETURNS TABLE (
    primary_foreman TEXT,
    helper          TEXT,
    helper_dept     TEXT,
    vac_crew        TEXT,
    source_run_id   TEXT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        CASE WHEN s.frozen_primary LIKE '#%' OR btrim(s.frozen_primary) = '' THEN NULL ELSE s.frozen_primary END AS primary_foreman,
        CASE WHEN s.frozen_helper  LIKE '#%' OR btrim(s.frozen_helper)  = '' THEN NULL ELSE s.frozen_helper  END AS helper,
        ...
    FROM billing_audit.attribution_snapshot AS s
    WHERE s.wr = p_wr AND s.week_ending = p_week_ending AND s.smartsheet_row_id = p_smartsheet_row_id
    LIMIT 1;
$$;
```
Add `helper2`/`helper2_dept` columns to the `RETURNS TABLE`, prepend the SAME `DROP FUNCTION IF EXISTS billing_audit.lookup_attribution(TEXT, DATE, BIGINT);` line before `CREATE FUNCTION` (not `CREATE OR REPLACE`).

**`lookup_attribution_bulk` — Pitfall 6, the comment here is STALE and must be corrected in the same migration** (`billing_audit/schema.sql:375-414`):
```sql
-- OPERATOR: apply this CREATE OR REPLACE in the Supabase SQL Editor, ...
CREATE OR REPLACE FUNCTION billing_audit.lookup_attribution_bulk(
    p_wr_weeks jsonb
)
RETURNS TABLE (
    wr TEXT, week_ending DATE, smartsheet_row_id BIGINT,
    primary_foreman TEXT, helper TEXT, helper_dept TEXT, vac_crew TEXT, source_run_id TEXT
)
LANGUAGE sql STABLE
AS $$
    SELECT s.wr, s.week_ending, s.smartsheet_row_id,
        CASE WHEN s.frozen_primary LIKE '#%' OR btrim(s.frozen_primary) = '' THEN NULL ELSE s.frozen_primary END,
        ...
    FROM jsonb_to_recordset(p_wr_weeks) AS q(wr TEXT, week_ending DATE)
    JOIN billing_audit.attribution_snapshot AS s ...
```
This function has the IDENTICAL `RETURNS TABLE` restriction as `lookup_attribution` — `CREATE OR REPLACE` will NOT let you add `helper2`/`helper2_dept` columns despite what the comment says. Apply `DROP FUNCTION IF EXISTS billing_audit.lookup_attribution_bulk(jsonb);` first, exactly like the single-row RPC, and correct the stale "apply this CREATE OR REPLACE" comment in the same migration. Verify via `NOTIFY pgrst, 'reload schema';` and a post-migration read-back for both RPCs.

---

### `pipeline_memory/schema.sql` + `pipeline_memory/writer.py` (migration + service, CRUD)

**Analog:** same files — `row_state` DDL and `HASH_FIELDS`/payload builder

**`row_state` helper columns (additive target)** (`pipeline_memory/schema.sql:100-126`):
```sql
CREATE TABLE IF NOT EXISTS pipeline_memory.row_state (
    ...
    foreman_observed    TEXT,
    helper_observed     TEXT,
    helper_completed    BOOLEAN,
    helper_dept         TEXT,
    helper_job          TEXT,
    vac_crew_observed   TEXT,
    vac_completed       BOOLEAN,
    row_modified_at     TIMESTAMPTZ,
    content_hash        TEXT        NOT NULL,
    ...
    PRIMARY KEY (sheet_id, row_id)
);
```
Add `helper2_observed TEXT, helper2_completed BOOLEAN, helper2_dept TEXT, helper2_job TEXT` — additive columns, no PK/index change needed.

**`HASH_FIELDS` — fixed tuple, D-14-08's decision point** (`pipeline_memory/writer.py:615-632`):
```python
HASH_FIELDS: tuple[str, ...] = (
    "wr", "week_ending", "snapshot_date", "cu", "pole", "work_type",
    "quantity", "units_total_price", "units_completed",
    "foreman_observed", "helper_observed", "helper_completed",
    "helper_dept", "helper_job", "vac_crew_observed", "vac_completed",
)
```
Adding `helper2_*` to this tuple changes `content_hash` for every row once (a one-time `row_event` per row, 10-RESEARCH Pitfall 3). Since `RUN_MEMORY_INCREMENTAL_ENABLED` is OFF in production, this is a shadow-mode-only cost today, not a live regression — but the planner must record the choice explicitly (columns are additive regardless of the hash decision).

**Payload builder — the exact per-field extraction shape to slot-shift** (`pipeline_memory/writer.py:786-808`):
```python
payload: dict[str, Any] = {
    "row_id": row_id,
    "wr": _sanitized_wr(row_data),
    "week_ending": _coerce_date(week_ending),
    "snapshot_date": _coerce_date(snapshot_date),
    "cu": cu,
    "pole": pole,
    "work_type": row_data.get("Work Type") or None,
    "quantity": row_data.get("__mem_quantity"),
    "units_total_price": row_data.get("__mem_units_total_price"),
    "units_completed": _is_checked(row_data.get("Units Completed?")),
    "foreman_observed": row_data.get("Foreman") or None,
    "helper_observed": row_data.get("Foreman Helping?") or None,
    "helper_completed": _is_checked(row_data.get("Helping Foreman Completed Unit?")),
    "helper_dept": row_data.get("Helper Dept #") or None,
    "helper_job": row_data.get("Helper Job #") or None,
    "vac_crew_observed": row_data.get("VAC Crew Helping?") or None,
    "vac_completed": _is_checked(row_data.get("Vac Crew Completed Unit?")),
    "row_modified_at": row_data.get("__row_modified_at"),
}
payload["content_hash"] = compute_content_hash(payload)
```
Add `helper2_observed`/`helper2_completed`/`helper2_dept`/`helper2_job` reading `Foreman Helping? #2` / `Helping Foreman #2 Completed Unit?` / `Helper #2 Dept #` / `Helper #2 Job #` — same field-extraction idiom (`.get(...) or None`, `_is_checked(...)`).

---

### `scripts/publish_artifacts_to_supabase.py` (script, batch/transform)

**Analog:** same file — `_CANONICAL_VARIANTS` + `normalize_variant`'s 7-way precedence chain (`scripts/publish_artifacts_to_supabase.py:85-141`):
```python
_CANONICAL_VARIANTS: frozenset[str] = frozenset({
    "primary", "helper", "vac_crew",
    "aep_billable", "reduced_sub",
    "aep_billable_helper", "reduced_sub_helper",
})

def normalize_variant(filename: str) -> str:
    """
    Precedence mirrors generate_weekly_pdfs.py L2834:
        AEPBillable -> ReducedSub -> VacCrew -> Helper -> User
    Most-specific tokens checked first to prevent _AEPBillable_Helper_
    matching _Helper_ alone (the two hybrid forms must outrank their
    component forms).
    """
    if "_AEPBillable_Helper_" in filename:
        return "aep_billable_helper"
    if "_ReducedSub_Helper_" in filename:
        return "reduced_sub_helper"
    if "_AEPBillable" in filename:
        return "aep_billable"
    if "_ReducedSub" in filename:
        return "reduced_sub"
    if "_VacCrew" in filename:
        return "vac_crew"
    if "_Helper_" in filename:
        return "helper"
    return "primary"
```
Add 3 entries to `_CANONICAL_VARIANTS` and insert, IN PRECEDENCE ORDER (most-specific first, BEFORE the bare `_AEPBillable`/`_ReducedSub` checks):
```python
if "_AEPBillable_Helper2_" in filename:
    return "aep_billable_helper2"
if "_ReducedSub_Helper2_" in filename:
    return "reduced_sub_helper2"
...  # existing _AEPBillable / _ReducedSub / _VacCrew checks unchanged
if "_Helper2_" in filename:
    return "helper2"
if "_Helper_" in filename:
    return "helper"
```
Verified this session: `"_Helper2_"` and `"_Helper_"` are mutually exclusive substrings of any real filename (no collision with a `_Helper_2Pac`-style name). An unrecognized token today only logs a WARNING and does not fail the publish step — a missed branch here is a portal-metadata-quality gap, not a pipeline outage, but still must be added.

---

### `portal-v2/src/lib/variantLabels.ts` (utility, ADDITIVE — not required for correctness)

**Analog:** same file, full 22-line file read this session:
```typescript
export const VARIANT_LABELS: Record<string, string> = {
  '': 'Primary',
  helper: 'Helper',
  vac_crew: 'VAC Crew',
  _AEPBillable: 'AEP Billable (Sub)',
  _ReducedSub: 'Reduced Sub',
};

export function getVariantLabel(variant: string): string {
  if (variant in VARIANT_LABELS) return VARIANT_LABELS[variant];
  if (variant.startsWith('_AEPBillable_Helper')) return 'AEP Billable · Helper';
  if (variant.startsWith('_ReducedSub_Helper')) return 'Reduced Sub · Helper';
  return variant.replace(/^_/, '').replace(/_/g, ' ');
}
```
A bare `helper2` token falls through to the generic fallback and displays as literal `"helper2"` (functional, just unpolished) unless `helper2: 'Helper 2'` is added to `VARIANT_LABELS`. Note the pre-existing key-convention inconsistency (`helper`/`vac_crew` snake_case vs `_AEPBillable`/`_ReducedSub` underscore-capitalized) predates Phase 14 — do not "fix" it as part of this change; just follow whichever convention the planner confirms `public.artifacts.variant` actually stores (A5 in RESEARCH's Assumptions Log — unresolved, non-blocking). `VariantFilterBar.tsx` only consumes `getVariantLabel()` — no direct edit expected there.

---

### `pipeline/types.py` (model/types stub — optional landing spot, Claude's Discretion)

**Analog:** same file, current full 24-line stub:
```python
"""pipeline.types — shared type shapes for the billing pipeline.
...
Phase-09 Wave 0 ships this as a STUB. No shared dataclasses/TypedDicts
exist in the current engine to relocate ...
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - reserved for future shared shapes
    pass
```
Confirmed unchanged since the prototype's base (2026-07-22) — the prototype's hunk applies cleanly here if the planner chooses that shape. See Shared Patterns below for the reusable `FORMULA_ERROR_VALUES`/`normalize_helper_value` pieces (recommended) vs. the rejected pieces (`HelperAssignmentConflictError`, import-time gates).

---

### Test files

**Analog for the new Helper #2 test module** (`tests/test_group_identity_and_header_foreman.py:1-60`, header/fixture style):
```python
"""Follow-up to PR #361 ...
"""
from __future__ import annotations
import datetime, inspect, re, sys, unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import generate_weekly_pdfs  # noqa: E402
import pipeline.orchestrate  # noqa: E402
from pipeline import change_detection  # noqa: E402
from pipeline.config import (
    _RE_SANITIZE_HELPER_NAME,
    _RE_SANITIZE_IDENTIFIER,
)
from pipeline.orchestrate import derive_group_identity  # noqa: E402

GOLDEN_MIXED_PRIMARY = '4f5d44a9fe2ba3f4'
...

def _row(**extra):
    row = {
        'Work Request #': '90003',
        'Snapshot Date': '2026-07-30',
        ...
    }
```
This repo's test style: `unittest`-style classes, `sys.path` bootstrap for the repo root, a `_row(**overrides)` fixture builder, and golden-hash pinning for regression tests. Use this shape (not pytest fixtures/parametrize-only style) for `tests/test_foreman_helper_2.py`.

The prototype's renamed (`.txt`, non-collected) test files are a secondary reference for fixture SHAPES only — `.planning/phases/14-foreman-helper-2/reference/helper2-prototype-2026-07/test_weekly_excel_helper_split.py.txt` uses the same `_row(**overrides)` idiom with `Foreman Helping? #2`-shaped fixtures; re-validate every assertion against current code (its base predates Phases 10-12).

---

## Shared Patterns

### Pattern A — Variant-tuple/frozenset membership dispatch (apply everywhere)
**Source:** repeated verbatim at `change_detection.py:417`, `cleanup.py:518-520` (as a frozenset), `upload.py:343`, `orchestrate.py:499`, `excel.py:282/310/338` (as separate `elif`s).
```python
if variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):
    ...  # Helper #1-family — DO NOT WIDEN THIS TUPLE
if variant in ('helper2', 'aep_billable_helper2', 'reduced_sub_helper2'):
    ...  # Helper #2-family — NEW sibling block, never merged into the above
```
**Apply to:** every CHANGE row in the File Classification table above. **Pitfall 3** (new finding): there is no single shared constant for "the helper-family variant strings" — at least 4 independent call sites enumerate it as an inline literal. Grep for every occurrence of `'aep_billable_helper'` and `'reduced_sub_helper'` repo-wide as the definitive checklist before considering Helper #2 complete (this session's grep found 2 sites — `cleanup.py:518-520`, `upload.py:343` — that the original audit-scope's anchor list had missed).

### Pattern B — Guard applied to one branch of a per-row loop must be copied to its sibling
**Source:** `pipeline/grouping.py:721/733` (`if not is_subcontractor_row: keys_to_add.append(...) else: <debug log>`), the exact site that caused the real `[2026-05-19 22:00]` duplicate-billing incident when its Helper #1 sibling lacked the guard once.
**Apply to:** every new `keys_to_add.append(('helper2', ...))` / `('aep_billable_helper2', ...)` / `('reduced_sub_helper2', ...)` site in `grouping.py` — copy the guard structure verbatim from the adjacent Helper #1 site, never re-derive it.

### Pattern C — Formula-error / fabricated-claim guard (Helper #2 only, D-14-05)
**Source:** prototype's `pipeline/types.py` hunk (`.planning/phases/14-foreman-helper-2/reference/helper2-prototype-2026-07/helper2_prototype_vs_d11f20f.patch`, read this session) — no equivalent exists today for helper name fields (only for `CU`, `fetch.py:842`'s `'NO MATCH' in cu_text` check):
```python
FORMULA_ERROR_VALUES = frozenset({
    '#BLOCKED', '#CALCULATING', '#CIRCULAR REFERENCE',
    '#INVALID COLUMN VALUE', '#INVALID DATA TYPE', '#INVALID OPERATION',
    '#INVALID REF', '#INVALID VALUE', '#NO MATCH', '#REF', '#UNPARSEABLE',
})

def normalize_helper_value(value: object) -> str:
    """Return a safe helper value, treating Smartsheet errors as blank."""
    if value is None:
        return ''
    normalized = str(value).strip()
    if normalized.upper() in FORMULA_ERROR_VALUES:
        return ''
    return normalized
```
**Apply to:** `pipeline/fetch.py`'s Helper #2 row-detection block — route `helper2_name` (and dept/job) through this guard BEFORE the truthiness check, unlike Helper #1's bare `str(...).strip()` (the deferred "NA" quirk). Reuse verbatim if the planner lands this in `pipeline/types.py`; otherwise inline the same token set/logic directly in `fetch.py`.

**Rejected pieces from the same prototype file (do not reuse):**
```python
class HelperAssignmentConflictError(RuntimeError):
    """Raised when one unit is completed by both helper roles."""
```
Explicitly rejected by D-14-12/O-14-A — CONTEXT.md calls aborting the run on one bad row "too blunt"; the recommended O-14-A resolution is HOLD-with-visibility (mirrors Subproject B's HOLD semantics), stubbed pending Juan's decision, never an exception that stops workbook generation.

### Pattern D — Filename/identifier sanitization (reuse, never reinvent)
**Source:** `pipeline/config.py:28`, `_RE_SANITIZE_HELPER_NAME = re.compile(r'[^\w\-]')` (confirmed via RESEARCH's Security Domain section) — already imported and used at every helper-key/filename-suffix site shown above (`grouping.py`, `excel.py`, `orchestrate.py`).
**Apply to:** every new Helper #2 identifier/filename construction site — never build a `helper2` identifier string without passing it through this sanitizer first (STRIDE: Tampering mitigation, per RESEARCH's Security Domain section).

### Pattern E — Sentinel/placeholder name detection (one source of truth)
**Source:** `billing_audit/writer.py:96-115` (`is_sentinel_claimer`), already consumed by `pipeline/cleanup.py`'s `_is_sentinel_identifier`.
**Apply to:** any new Helper #2 "no real claimer" check — do not write a second `is_sentinel_claimer`-like function scoped to Helper #2; import and reuse this one everywhere the family needs it (freeze_row, cleanup, resolve_claimer).

### Pattern F — Feature flag idiom (for `HELPER2_ENABLED`, D-14-12)
**Source:** `pipeline/config.py:368-370`, one of ~12 boolean env-flag definitions in this module:
```python
SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED = os.getenv(
    'SUBCONTRACTOR_HELPER_CLAIM_ATTRIBUTION_ENABLED', '1'
).strip().lower() in ('1', 'true', 'yes', 'on')
```
**Apply to:** the new `HELPER2_ENABLED` flag — same `.strip().lower() in (...)` idiom, but note D-14-12 requires **default OFF** (`'0'`), unlike this analog's default-ON `'1'` — copy the parsing idiom, not the default value. Do NOT reintroduce the prototype's `HELPER2_SOURCE_PROVEN`/`HELPER2_JOB_PRODUCER_PROVEN` import-time fail-closed gate (rejected, D-14-12) — those are runbook/pilot-checklist items, not code gates.

### Pattern G — PII-safe logging for any new Helper #2 name field
**Source:** `pipeline/observability.py`'s `_redact_exception_message` (confirmed imported by `pipeline/upload.py:30` per RESEARCH) and the existing `_PII_LOG_MARKERS` pattern.
**Apply to:** any new log line naming a Helper #2 person — do not log a raw helper name outside markers already vetted for PII scrubbing (STRIDE: Information Disclosure mitigation, RESEARCH Security Domain).

---

## No Analog Found

None. Every file in scope has an exact same-file (sibling-branch) analog because D-14-03 explicitly scopes this phase as "same stages, same modules, same business rules as Helper #1" — there is no new component, service, or architectural layer to build from scratch. The three PROTECTED Supabase RPC/schema items (`freeze_attribution` params, `lookup_attribution`, `lookup_attribution_bulk`) have a documented in-file analog (the DROP-first pattern) but require an operator-executed migration outside the repo's own source control — flag this to the planner as a `checkpoint:decision`-gated task, not a missing pattern.

## Metadata

**Analog search scope:** `pipeline/`, `billing_audit/`, `pipeline_memory/`, `scripts/publish_artifacts_to_supabase.py`, `portal-v2/src/lib/`, `tests/`, plus the Phase 14 prototype reference bundle (`.planning/phases/14-foreman-helper-2/reference/helper2-prototype-2026-07/`) — every path already named with file:line in 14-RESEARCH.md's Impact Map and Affected Consumers tables.
**Files scanned:** 17 production files + 1 stub + 2 reference bundle files (patch + one prototype test) + 1 existing test file (style reference) — all read directly this session via `Read`/`Grep` against `HEAD`, not reconstructed from RESEARCH.md's quotes alone.
**Pattern extraction date:** 2026-09-05
**Source of the file list:** 14-CONTEXT.md `<decisions>`/`<canonical_refs>`/`<code_context>` sections + 14-RESEARCH.md's Affected Consumers Disposition Summary table (the authoritative per-file CHANGE/ADDITIVE/NO CHANGE/PROTECTED list) — no files were invented independently of those two documents.

## PATTERN MAPPING COMPLETE
