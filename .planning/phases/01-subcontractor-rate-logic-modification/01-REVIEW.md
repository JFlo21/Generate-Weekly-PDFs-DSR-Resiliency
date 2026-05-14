---
phase: 01-subcontractor-rate-logic-modification
reviewed: 2026-05-14T23:30:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - billing_audit/__init__.py
  - billing_audit/schema.sql
  - billing_audit/writer.py
  - generate_weekly_pdfs.py
  - tests/test_billing_audit_shadow.py
  - tests/test_security_audit_followup.py
  - tests/test_subcontractor_pricing.py
  - tests/test_vac_crew.py
  - tests/validate_production_safety.py
  - website/docs/reference/environment.md
  - website/docs/runbook/workflows.md
findings:
  critical: 3
  warning: 6
  info: 4
  total: 13
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-05-14T23:30:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 1 introduces a CSV-driven subcontractor pricing pipeline that fans
out two new Excel variants (`_AEPBillable`, `_ReducedSub`) plus their
helper-shadow twins for subcontractor-folder WR groups, routes
`_ReducedSub*` to a second target sheet (`SUBCONTRACTOR_PPP_SHEET_ID`),
and threads a `variant` attribution through `billing_audit.pipeline_run`
via Path B (writer-side coercion). The end-to-end shape is well
documented and tests cover most of the surface (537 passed per the
verifier run).

The adversarial review surfaces **three BLOCKER** defects in
`generate_weekly_pdfs.py:main()` that the existing test suite does not
catch because the tests exercise the helpers in isolation and not the
full main-loop attachment-identity / filter pipeline:

1. **`aep_billable_helper` / `reduced_sub_helper` attachment routing
   silently broken** — main-loop `else` branch derives `file_identifier`
   from `User` (always blank for shadow rows) instead of
   `__helper_foreman`, so `_has_existing_week_attachment` and
   `delete_old_excel_attachments` both miss the existing shadow
   attachment by identifier-mismatch on every run.
2. **`EXCLUDE_WRS` does not exclude the four new variant group keys** —
   operators trying to suppress a WR see the new variants still upload
   to TARGET_SHEET_ID + PPP. This runs in production (no TEST_MODE
   gate) and is wired to `vars.EXCLUDE_WRS` in the workflow.
3. **`WR_FILTER` does not include the four new variant group keys** —
   operator-targeted TEST_MODE diagnostic runs silently produce no
   `_AEPBillable` / `_ReducedSub` output for filtered WRs.

Six WARNING-level findings cover orphan attachment accumulation on
the PPP sheet, environment-doc / behavior drift, and minor
defense-in-depth gaps. Four INFO items are tracked.

The verified deliverables (CSV loader, fingerprint, _resolve_row_price,
variant emission, parser/round-trip, dual-target builder, writer kwarg
threading, schema migration, PII markers) all hold up under
adversarial review except where flagged below.

## Critical Issues

### CR-01: `aep_billable_helper` / `reduced_sub_helper` main-loop `file_identifier` derived from wrong field, breaking unchanged-skip and prior-attachment deletion

**File:** `generate_weekly_pdfs.py:5966-5983`

**Issue:**
The main-loop branch that derives `identifier` / `file_identifier`
per variant handles `helper` explicitly (uses `__helper_foreman`) and
`vac_crew` explicitly (empty), but the four new variants
(`aep_billable`, `reduced_sub`, `aep_billable_helper`,
`reduced_sub_helper`) fall through to the `else` branch:

```python
else:
    user_val = first_row.get('User')
    identifier = _RE_SANITIZE_IDENTIFIER.sub('_', user_val)[:50] if user_val else ''
    file_identifier = identifier
```

For `aep_billable` and `reduced_sub` (no helper foreman) this is
benign — the filename suffix carries no identifier so the `''`
identifier matches `build_group_identity`'s `''` output.

For `aep_billable_helper` and `reduced_sub_helper`, however, the
filename **does** carry a helper-name identifier (e.g.
`WR_X_WeekEnding_041926_123456_AEPBillable_Helper_Jane_Smith_HASH.xlsx`),
and `build_group_identity` correctly returns
`(wr, week, 'aep_billable_helper', 'Jane_Smith')` per the parser
tests in `tests/test_vac_crew.py::TestSubcontractorVariantGroupIdentityParsing`.
The main-loop logic builds `file_identifier=''` because `User` is
typically not populated for shadow rows. The downstream call
`_has_existing_week_attachment(..., variant='aep_billable_helper',
identifier='')` then matches `(ident_identifier or '') == (identifier or '')`
as `'Jane_Smith' == ''` → **False**, so the function reports "no
attachment exists" even when the file is right there on the row.

Two cascading effects, both real:

1. **Skip-unchanged optimization permanently broken for shadow
   variants.** Every scheduled run regenerates and re-uploads
   `_AEPBillable_Helper_*` and `_ReducedSub_Helper_*` files even when
   nothing changed. With ~7 weekday runs at 2-hour cadence × N
   helper-shadow groups × 2 (TARGET + PPP for `_ReducedSub_Helper_*`),
   this is meaningful Smartsheet API pressure (delete + attach calls
   per file per run).
2. **`delete_old_excel_attachments` matches no candidates by
   identifier**, so the prior attachment is not deleted on upload;
   the new one is added next to it. On `TARGET_SHEET_ID` the
   end-of-run `cleanup_untracked_sheet_attachments` mitigates by
   pruning all-but-newest by timestamp, but on
   `SUBCONTRACTOR_PPP_SHEET_ID` **there is no equivalent cleanup pass
   (see WR-04)**, so `_ReducedSub_Helper_*` attachments orphan
   permanently on the PPP sheet — every run adds another.

**Fix:**
Extend the variant branch in `main()` so the two helper-shadow
variants follow the same `file_identifier` derivation as `helper`:

```python
if variant in ('helper', 'aep_billable_helper', 'reduced_sub_helper'):
    helper_foreman = first_row.get('__helper_foreman', '')
    helper_dept = first_row.get('__helper_dept', '')
    helper_job = first_row.get('__helper_job', '')
    # identifier is the hash-history-tuple form (used in history_key only);
    # file_identifier is the filename-embedded form (used in attachment matching).
    identifier = f"{helper_foreman}|{helper_dept}|{helper_job}"
    file_identifier = (
        _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]
        if helper_foreman else ''
    )
elif variant == 'vac_crew':
    identifier = ''
    file_identifier = ''
else:
    user_val = first_row.get('User')
    identifier = _RE_SANITIZE_IDENTIFIER.sub('_', user_val)[:50] if user_val else ''
    file_identifier = identifier
```

The same pattern must also be applied in the **two** sister loops
that rebuild identity tuples after generation:

- `valid_wr_weeks` construction at L6660-6671 (cleanup-pruning
  identity set — falls into `else` for shadow variants, producing
  `(wr, week, 'aep_billable_helper', '')` tuples that don't match
  the parser's `(wr, week, 'aep_billable_helper', 'Jane_Smith')`).
- `current_keys` construction at L6716-6726 (hash-history prune key
  — same `else` issue; symptom is masked today because the
  hash-history entry was also written with `identifier=''`, so the
  two stay aligned by accident).

Add regression tests in `tests/test_subcontractor_pricing.py` that
exercise the full main-loop derivation for the helper-shadow
variants (e.g. assert that `file_identifier` derived for a
`aep_billable_helper` group matches the sanitized `__helper_foreman`
on `first_row`, and that an attachment named
`WR_X_WeekEnding_041926_123456_AEPBillable_Helper_Jane_Smith_<hash>.xlsx`
on the row returns `True` from `_has_existing_week_attachment`).

---

### CR-02: `EXCLUDE_WRS` does not match the 4 new variant group keys — operator exclusion is silently ignored for new variants

**File:** `generate_weekly_pdfs.py:4322-4351`

**Issue:**
`_key_matches_excluded_wr` only recognises four group-key suffixes:

```python
return (
    suffix == wr
    or suffix.startswith(f"{wr}_HELPER_")
    or suffix.startswith(f"{wr}_USER_")
    or suffix == f"{wr}_VACCREW"
)
```

The four new variant key shapes emitted by `group_source_rows` —
`MMDDYY_<WR>_REDUCEDSUB`, `MMDDYY_<WR>_AEPBILLABLE`,
`MMDDYY_<WR>_REDUCEDSUB_HELPER_<name>`,
`MMDDYY_<WR>_AEPBILLABLE_HELPER_<name>` — produce suffixes that match
NONE of these patterns. (`<WR>_REDUCEDSUB_HELPER_<name>` does not
`startswith(f"{WR}_HELPER_")`; the prefix is `<WR>_REDUCEDSUB_HELPER_`.)

`EXCLUDE_WRS` runs in production (no `TEST_MODE` gate — see L4322
comment "applies always, not just TEST_MODE") and is wired to
`vars.EXCLUDE_WRS` in `.github/workflows/weekly-excel-generation.yml`.
Consequence: when an operator excludes a WR (e.g. because billing is
disputed, or upstream Smartsheet data is wrong and they want to
prevent attachment churn), the primary / helper / vac_crew files are
correctly suppressed but the new `_AEPBillable*` / `_ReducedSub*`
files are still generated AND uploaded to TARGET_SHEET_ID + PPP.
This defeats the operator's intent and may upload prices the
operator deliberately marked as "do not bill yet."

**Fix:**
Extend the matcher to recognise the four new variant suffixes:

```python
def _key_matches_excluded_wr(k: str, wr: str) -> bool:
    try:
        suffix = k.split('_', 1)[1]
    except Exception:
        return False
    return (
        suffix == wr
        or suffix.startswith(f"{wr}_HELPER_")
        or suffix.startswith(f"{wr}_USER_")
        or suffix == f"{wr}_VACCREW"
        # Phase 1 subcontractor variants — same WR, different variant
        # suffix. Match the four new keys so EXCLUDE_WRS suppresses
        # the whole WR (primary + helper + vac_crew + aep_billable +
        # reduced_sub + their shadow-helper twins).
        or suffix == f"{wr}_REDUCEDSUB"
        or suffix == f"{wr}_AEPBILLABLE"
        or suffix.startswith(f"{wr}_REDUCEDSUB_HELPER_")
        or suffix.startswith(f"{wr}_AEPBILLABLE_HELPER_")
    )
```

Add a regression test asserting that `EXCLUDE_WRS={'12345'}` removes
all seven possible group keys for WR `12345`.

---

### CR-03: `WR_FILTER` does not match the 4 new variant group keys — TEST_MODE diagnostics for filtered WRs produce no subcontractor output

**File:** `generate_weekly_pdfs.py:4305-4320`

**Issue:**
Mirror of CR-02 for the TEST_MODE filter:

```python
return (
    suffix == wr
    or suffix.startswith(f"{wr}_HELPER_")
    or suffix == f"{wr}_VACCREW"
)
```

This matcher misses `<WR>_REDUCEDSUB`, `<WR>_AEPBILLABLE`,
`<WR>_REDUCEDSUB_HELPER_<name>`, `<WR>_AEPBILLABLE_HELPER_<name>`.
An operator running `TEST_MODE=true WR_FILTER=12345
SKIP_UPLOAD=true python generate_weekly_pdfs.py` to validate
subcontractor variant Excel generation for a specific WR will see
zero new-variant output because the filter drops those groups
before generation runs. This makes the documented operator
verification path in `01-VERIFICATION.md` "human_verification" item
2 ("Step B real-data price-write end-to-end") not actually
exercisable for a single WR.

The blast radius is smaller than CR-02 (TEST_MODE only, no
production data write), but the symptom is "operator runs the
documented diagnostic command and gets zero output," which makes
the kill-switch verification path itself unreliable.

**Fix:**
Same shape as CR-02:

```python
def _key_matches_wr(k: str, wr: str) -> bool:
    try:
        suffix = k.split('_', 1)[1]
    except Exception:
        return False
    return (
        suffix == wr
        or suffix.startswith(f"{wr}_HELPER_")
        or suffix == f"{wr}_VACCREW"
        or suffix == f"{wr}_REDUCEDSUB"
        or suffix == f"{wr}_AEPBILLABLE"
        or suffix.startswith(f"{wr}_REDUCEDSUB_HELPER_")
        or suffix.startswith(f"{wr}_AEPBILLABLE_HELPER_")
    )
```

Add a regression test asserting that `WR_FILTER={'12345'}` retains
all seven group keys for WR `12345` and excludes other WRs.

## Warnings

### WR-01: `SUBCONTRACTOR_PPP_SHEET_ID` has no end-of-run cleanup pass — orphan attachment accumulation guaranteed

**File:** `generate_weekly_pdfs.py:6672-6676`

**Issue:**
`cleanup_untracked_sheet_attachments(client, TARGET_SHEET_ID, ...)`
is the only cleanup pass run at end-of-session. It iterates all rows
of `TARGET_SHEET_ID`, groups attachments by `build_group_identity`
tuple, and prunes everything-but-newest per identity. There is no
equivalent invocation for `SUBCONTRACTOR_PPP_SHEET_ID`.

This means on the PPP sheet:

- `delete_old_excel_attachments` (called from `_upload_one` with
  `task['target_sheet_id']=PPP`) is the only pruning path.
- When that path misses (e.g. CR-01 helper-shadow identifier
  mismatch, OR any future identifier-derivation drift), the orphan
  attachment is never cleaned up — `cleanup_untracked` only acts on
  TARGET_SHEET_ID.
- Even when `delete_old_excel_attachments` works correctly, any
  variant whose timestamp drift causes the prior attachment's
  identity tuple to legitimately differ from the new one (none
  expected today, but a defensive cleanup pass would catch this)
  would orphan on PPP.

**Fix:**
Add a parallel cleanup invocation for the PPP sheet, gated on the
same kill-switch / same-sheet checks as the target_map build at
L5462-5490:

```python
if not TEST_MODE:
    with sentry_sdk.start_span(op="smartsheet.cleanup", name="..."):
        cleanup_untracked_sheet_attachments(
            client, TARGET_SHEET_ID, valid_wr_weeks, TEST_MODE,
            attachment_cache=_cleanup_cache,
            target_sheet=_target_sheet_obj,
        )
    if (SUBCONTRACTOR_RATE_VARIANTS_ENABLED
            and SUBCONTRACTOR_PPP_SHEET_ID
            and SUBCONTRACTOR_PPP_SHEET_ID != TARGET_SHEET_ID
            and _target_sheet_ppp_obj is not None):
        with sentry_sdk.start_span(op="smartsheet.cleanup_ppp", name="..."):
            cleanup_untracked_sheet_attachments(
                client, SUBCONTRACTOR_PPP_SHEET_ID, valid_wr_weeks,
                TEST_MODE, attachment_cache=None,
                target_sheet=_target_sheet_ppp_obj,
            )
```

Note `attachment_cache=None` because the prefetch only populates
TARGET_SHEET_ID rows. The PPP cleanup will issue per-row attachment
API calls; acceptable because the PPP sheet has far fewer rows than
TARGET_SHEET_ID (only the subset that needs `_ReducedSub*`).

---

### WR-02: `SUBCONTRACTOR_PPP_SHEET_ID=''` (empty string) silently falls back to default — env-doc claim "empty / 0 to disable dual routing" is half-true

**File:** `generate_weekly_pdfs.py:156-163` (helper); `generate_weekly_pdfs.py:432-435` (call site); `website/docs/reference/environment.md:76-79` (doc)

**Issue:**
`_coerce_sheet_id(raw_value, default)` returns the default whenever
`raw_value` is falsy (`if not raw_value: return default`). So
`SUBCONTRACTOR_PPP_SHEET_ID=''` returns `8162920222379908` (the
hardcoded default), not the operator's apparent intent of "disable
dual routing."

The behavior is asymmetric:
- `SUBCONTRACTOR_PPP_SHEET_ID=0` → coerces to `int(0)=0`, then
  `main()` check `and SUBCONTRACTOR_PPP_SHEET_ID` is False, so
  PPP map build is skipped. **Disable works.**
- `SUBCONTRACTOR_PPP_SHEET_ID=''` → coerces to default
  `8162920222379908`, **disable silently fails.**

`environment.md:76` advertises "empty / `0` to disable dual
routing" — the empty path does not match this.

**Fix:**
Either:
1. Adjust `_coerce_sheet_id` to honor empty-string-as-zero (special
   case in the call site only — don't change `_coerce_sheet_id`
   which is shared with `TARGET_SHEET_ID` where default-fallback is
   correct):

```python
SUBCONTRACTOR_PPP_SHEET_ID = _coerce_sheet_id(
    os.getenv('SUBCONTRACTOR_PPP_SHEET_ID', '8162920222379908'),
    8162920222379908,
)
# Per documented contract: empty string = disable, not "use default"
if not os.getenv('SUBCONTRACTOR_PPP_SHEET_ID', '8162920222379908'):
    SUBCONTRACTOR_PPP_SHEET_ID = 0
```

2. Or update the documentation to read "Valid values: integer
   sheet id, or `0` to disable. To disable, set the value to `0`
   (empty string falls back to the default)."

The first option matches operator intent better. Pair with a
startup banner line that names the resolved active value so
operators see at a glance whether PPP routing is on.

---

### WR-03: `aep_billable_helper` / `reduced_sub_helper` filename-suffix fallthrough on empty `__helper_foreman` would silently produce a primary-looking filename

**File:** `generate_weekly_pdfs.py:4510-4519`

**Issue:**

```python
elif variant == 'aep_billable_helper':
    helper_foreman = first_row.get('__helper_foreman', '')
    if helper_foreman:
        helper_sanitized = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]
        variant_suffix = f"_AEPBillable_Helper_{helper_sanitized}"
```

If `helper_foreman` is empty (defensive against future refactor /
unexpected row mutation), `variant_suffix` stays `""` — the
filename would NOT include the `_AEPBillable_Helper_<name>` suffix
at all. The resulting filename looks identical to a primary
variant file, `build_group_identity` would parse it as
`variant='primary'`, and attachment routing / cleanup would treat
it as a primary file (wrong target, wrong identity tuple).

Today this is defended against upstream — `group_source_rows`
L4202-4205 gates `_valid_helper_row` on `helper_foreman` being
truthy, so the helper-shadow group key is only added when
`helper_foreman` is non-empty. The row mutation at L4248-4253 is a
shallow `r.copy()` so `__helper_foreman` survives. But a defensive
guard at the variant_suffix construction site would loudly fail
rather than silently mis-label.

Same shape exists in the legacy `helper` branch at L4520-4526
(pre-existing behavior, not a Phase 1 regression).

**Fix:**
Either raise loudly or fall back to a marker-visible suffix:

```python
elif variant == 'aep_billable_helper':
    helper_foreman = first_row.get('__helper_foreman', '')
    if not helper_foreman:
        logging.error(
            f"⚠️ aep_billable_helper variant row missing __helper_foreman "
            f"for WR {wr_num} week {week_end_raw} — filename would be "
            f"ambiguous; raising to surface the data drift."
        )
        raise ValueError(
            f"aep_billable_helper requires __helper_foreman; got empty"
        )
    helper_sanitized = _RE_SANITIZE_HELPER_NAME.sub('_', helper_foreman)[:50]
    variant_suffix = f"_AEPBillable_Helper_{helper_sanitized}"
```

(The legacy `helper` branch should get the same treatment as
follow-up tech-debt cleanup, but is out of Phase 1 scope.)

---

### WR-04: Helper-shadow group-creation log bodies embed `Helper={helper_foreman}` and rely on the substring marker `HELPER GROUP CREATED` to scrub

**File:** `generate_weekly_pdfs.py:4218-4222`, `4239-4243`; `generate_weekly_pdfs.py:675-781` (`_PII_LOG_MARKERS`)

**Issue:**
The new helper-shadow group-creation INFO logs:

```
🔻 REDUCED SUB HELPER GROUP CREATED: WR=..., Week=..., Helper=<foreman>
💲 AEP BILLABLE HELPER GROUP CREATED: WR=..., Week=..., Helper=<foreman>
```

embed a helper foreman name. The PII sanitizer drops them via the
substring match on `"HELPER GROUP CREATED"` which is in
`_PII_LOG_MARKERS`. The match works today by accident — both new
log bodies happen to contain the substring `"HELPER GROUP CREATED"`
because the literal "HELPER GROUP CREATED" appears as part of
"REDUCED SUB HELPER GROUP CREATED" / "AEP BILLABLE HELPER GROUP
CREATED."

This is fragile:
- A future log rewording (e.g. "REDUCED SUB HELPER GROUP REGISTERED"
  or "REDUCED SUB HELPER GRP CREATED") breaks the match and leaks
  the foreman name to Sentry Logs.
- The 2026-04-20 12:00 ledger rule says "Either strip the PII from
  the message or extend `_PII_LOG_MARKERS` in the same PR so the
  sanitizer keeps up." The current marker set covers the
  GROUP-CREATED variant but does so via accident, not by an
  explicit marker.

**Fix:**
Add explicit markers for the two new log bodies so the substring
match is intentional and survives wording drift:

```python
_PII_LOG_MARKERS: tuple[str, ...] = (
    # ... existing markers ...
    "REDUCED SUB HELPER GROUP CREATED",
    "AEP BILLABLE HELPER GROUP CREATED",
    # ... existing markers ...
)
```

These join the existing `"AEP BILLABLE GROUP CREATED"` and
`"REDUCED SUB GROUP CREATED"` markers and lock in the
helper-shadow variant.

---

### WR-05: PPP target-row attachment cache miss is silent — per-row API calls go up on every reduced-sub upload

**File:** `generate_weekly_pdfs.py:5537-5543`; `generate_weekly_pdfs.py:6555` (consumer)

**Issue:**
`_fetch_row_attachments` hardcodes `TARGET_SHEET_ID` in its API call:

```python
def _fetch_row_attachments(row_item):
    _, target_row = row_item
    ...
    atts = client.Attachments.list_row_attachments(TARGET_SHEET_ID, target_row.id).data
```

The pre-fetched `attachment_cache` is therefore keyed on
TARGET_SHEET_ID row ids only. The `_upload_one` worker passes
`cached_attachments=attachment_cache.get(target_row.id)` to
`delete_old_excel_attachments`. For PPP target rows (different
sheet, different row ids), the cache returns `None` and the
delete-old path falls back to a per-row
`client.Attachments.list_row_attachments` call.

Behavior is correct (fallback works), but every `_ReducedSub` /
`_ReducedSub_Helper_*` upload to the PPP sheet pays an extra API
call. Pre-fetching the PPP sheet's row attachments alongside the
TARGET_SHEET_ID prefetch would amortize this. With CR-01 fixed and
WR-01 added, the helper-shadow PPP attachments stop accumulating;
without the prefetch they still cost N extra API calls per run.

**Fix:**
Extend the prefetch loop to consume both maps. Either:

1. Make `_fetch_row_attachments` accept a sheet_id parameter and
   submit two futures per row (one per sheet) — but that doubles
   the prefetch budget, and the PPP sheet has few rows so it's
   wasteful.

2. Add a separate, smaller prefetch pass for PPP rows after the
   primary pass succeeds (or runs out of budget):

```python
if target_map_ppp and not TEST_MODE and not _prefetch_budget_exceeded:
    # Smaller pass — PPP sheet typically has dozens of rows, not
    # hundreds. Reuses the same executor / cache.
    def _fetch_ppp_attachments(row_item):
        _, target_row = row_item
        atts = client.Attachments.list_row_attachments(
            SUBCONTRACTOR_PPP_SHEET_ID, target_row.id,
        ).data
        return (target_row.id, atts)
    # ... (similar shape to the primary prefetch)
```

This is a runtime / API-quota optimization and a defense against
operator surprise — not strictly a correctness defect — but the
WARNING classification matches the impact (sustained extra API
quota burn on every run).

---

### WR-06: `__source_sheet_id` vs `__sheet_id` divergent reads — silent regression risk if one field drifts

**File:** `generate_weekly_pdfs.py:3416,3424` (writer); `generate_weekly_pdfs.py:4134` (gate); `generate_weekly_pdfs.py:6406` (attribution)

**Issue:**
`_fetch_and_process_sheet` populates BOTH `__sheet_id` and
`__source_sheet_id` to the same value (L3416 and L3424). Phase 1's
new subcontractor gate reads `__source_sheet_id` (L4134); the
missing-CU attribution loop at L6406 reads `__sheet_id`. Both reads
work today because the writer populates both fields together, but a
future refactor that drops one or splits the meaning could create a
gate-vs-attribution divergence (e.g. the gate fires for a row, but
the attribution loop can't bucket the missing CU into a sheet, so
the WARNING is bucketed under sheet `-1` instead of the real sheet).

The L3417-3423 comment justifies the alias as "no existing consumer
of the legacy field name regresses." That's true for read-only
consumers, but the duplicate write is mild tech debt that could
mask future bugs.

**Fix:**
Pick one canonical field name and migrate the other read site.
Recommended: standardize on `__source_sheet_id` (the new name) and
deprecate `__sheet_id` by:

1. Update L6406 to read `__source_sheet_id`.
2. Update the comment at L3417-3423 to say "drop `__sheet_id` write
   in a future cleanup."
3. Add a brief regression test that asserts both names resolve to
   the same value at populate time so any future split surfaces.

Low priority — file behavior is correct today.

## Info

### IN-01: `_AEP_BILLABLE_CUTOFF` is a hardcoded module-level constant, not env-configurable

**File:** `generate_weekly_pdfs.py:445`

**Issue:**
`_AEP_BILLABLE_CUTOFF = datetime.date(2026, 4, 12)` is hardcoded as
the AEP rate-increase contract award date. If the contract is ever
re-negotiated or the cutoff needs adjustment (e.g. to honor a
retroactive billing decision), an operator can't change it via env
var — requires a code edit and redeploy.

The Phase 1 plan documents this as deliberate (matches the contract
award date, single source of truth) and the `RATE_CUTOFF_DATE` env
var is retired (per Living Ledger 2026-04-24 14:30), so reusing it
would be confusing. However, exposing `_AEP_BILLABLE_CUTOFF` as an
env-overridable value (default `2026-04-12`) would let operators
roll forward without a code change.

**Fix:**
Optional follow-up. If accepted:

```python
_aep_cutoff_env = os.getenv('AEP_BILLABLE_CUTOFF', '')
try:
    _AEP_BILLABLE_CUTOFF = (
        datetime.datetime.strptime(_aep_cutoff_env, '%Y-%m-%d').date()
        if _aep_cutoff_env else datetime.date(2026, 4, 12)
    )
except ValueError:
    logging.error(
        f"Invalid AEP_BILLABLE_CUTOFF format: '{_aep_cutoff_env}'; "
        f"expected YYYY-MM-DD. Falling back to default 2026-04-12."
    )
    _AEP_BILLABLE_CUTOFF = datetime.date(2026, 4, 12)
```

---

### IN-02: `_resolve_row_price`'s `qty_raw = row.get('Quantity') or 0` is subtly inconsistent

**File:** `generate_weekly_pdfs.py:1425`

**Issue:**
`row.get('Quantity') or 0` returns `0` (int) when `Quantity` is
`None`, empty string, `0`, or `0.0`. The subsequent `float(qty_raw)`
converts all of these to `0.0`. For `Quantity=0.0` (legitimate
data — a row with zero quantity), the `or 0` operator returns
the wrong-typed `0` (int), which is then re-converted to `0.0`.
Functionally correct but slightly opaque.

`row.get('Quantity', 0)` would be cleaner: `None` defaults to `0`,
present-but-falsy values (including legitimate `0.0`) pass
through unchanged.

**Fix:**

```python
qty_raw = row.get('Quantity', 0)
try:
    qty = float(qty_raw) if qty_raw not in (None, '') else 0.0
except (TypeError, ValueError):
    qty = 0.0
```

The fast path is identical; the slow path now explicitly handles
None / empty-string as zero without the truthy-or-fallback pattern.

---

### IN-03: Reference to `_txn = None` hoist (commit 7e4777c) — not penalized, pre-existing master bug fix

**File:** `generate_weekly_pdfs.py:5211`

**Issue:**
The `_txn = None` initialization at the top of `main()` was added
as a pre-existing master bug fix per Phase 6 SUMMARY. It is correct
and necessary (synthetic-mode `return` at L5311 and missing-token
`raise` at L5313 both short-circuit past the in-place
`start_transaction` block at L5320, leaving `_txn` unbound for the
`finally` clause).

**Fix:**
None. Reference only. Not a Phase 1 finding.

---

### IN-04: `SUBCONTRACTOR_RATE_VARIANTS_ENABLED` not pinned in `.github/workflows/weekly-excel-generation.yml`

**File:** `.github/workflows/weekly-excel-generation.yml`

**Issue:**
The retired env vars (`RATE_CUTOFF_DATE`, `NEW_RATES_CSV`,
`OLD_RATES_CSV`) are pinned to empty strings in the workflow per
the 2026-04-24 14:30 ledger rule. The new Phase 1 env vars
(`SUBCONTRACTOR_RATES_CSV`, `SUBCONTRACTOR_PPP_SHEET_ID`,
`SUBCONTRACTOR_RATE_VARIANTS_ENABLED`) are NOT pinned in the
workflow — they're read from environment defaults. That works
today (defaults are correct) but means:

- Operators reading the workflow can't see the active feature
  state at a glance.
- A repo-level Variable named one of these three could silently
  override the defaults without code review.
- The rollback path documented in `environment.md` (set
  `SUBCONTRACTOR_RATE_VARIANTS_ENABLED=0`) requires an env-block
  edit in the workflow rather than a repo-Variable flip.

**Fix:**
Pin all three with explicit defaults so the workflow is
self-documenting:

```yaml
env:
  # ... existing env block ...
  SUBCONTRACTOR_RATES_CSV: 'data/subcontractor_rates.csv'
  SUBCONTRACTOR_PPP_SHEET_ID: '8162920222379908'
  SUBCONTRACTOR_RATE_VARIANTS_ENABLED: '1'
```

Pair with a comment block explaining the kill-switch rollback path
(set the last value to `'0'` for immediate disable).

Low priority — defaults work; this is operational hygiene.

---

_Reviewed: 2026-05-14T23:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
