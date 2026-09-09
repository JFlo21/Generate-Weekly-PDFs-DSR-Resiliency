# Phase 14 Plan 02: Pending Resolutions

Evidence-backed answers to the four gaps `14-RESEARCH.md` marked
"pending — resolve in execution task." Every verdict below cites the file
plus the line range actually read this session, per the plan's own contract.
Evidence label: every citation in this document is **DOCUMENTED EVIDENCE**
(a repository read against current `HEAD`) — never a dry-run pass and never a
production observation. The one item this task cannot answer (the live
Smartsheet column state) is deferred to Task 3 / `14-DECISIONS.md`.

## A1

**Verdict: CONFIRMED SAFE**

**Question:** Is the `pipeline_memory.group_state` hash-skip keyed on the full
`(wr, week_ending, variant, identifier)` tuple, so a variant with no stored
row falls through to regenerate?

**Evidence:**
- `pipeline/change_detection.py:843-915` (`_resolve_unchanged_for_skip`) —
  two independent lookup paths, both keyed on the full tuple:
  - Supabase-authoritative path (`SUPABASE_HASH_STORE_AUTHORITATIVE` on):
    calls `_writer.lookup_group_hash(wr_num, week_iso, variant, identifier or
    '')` (`:907-908`). A `no_row` status — never durably stored — returns
    `False` (regenerate), confirmed at `:911-912`.
  - Non-authoritative / fallback path: `group_state_hashes.get(history_key)`
    where `history_key` is documented (`:871-873`) as the SAME
    `f"{wr_num}|{week_raw}|{variant}|{identifier}"` string used at the call
    site. A missing key returns `None` → `bool(_prev and ...)` → `False`
    (regenerate), confirmed at `:914-915`.
- `pipeline/orchestrate.py:3148-3184` — confirms the caller builds
  `_group_state_hashes` (the `group_state_hashes` argument) keyed EXACTLY by
  `f"{_wr}|{_week_ending_iso}|{_entry.get('variant') or ''}|
  {_entry.get('identifier') or ''}"` (`:3166-3171`), from
  `pipeline_memory.reader.get_group_state_content_hashes_by_wr` — a per-WR
  Supabase query that returns `(week_ending, variant, identifier,
  content_hash)` rows and skips any row missing `content_hash`
  (`pipeline_memory/reader.py:504-594`, doc at `:518-520`: "the caller's skip
  decision must treat it as CHANGED (regenerate), never as an unconfirmed
  match"). Also `pipeline/orchestrate.py:3588`
  (`history_key = f"{wr_num}|{week_iso}|{variant}|{identifier}"`) — the exact
  same format constructed at the call site, confirming no key-format drift
  between producer and consumer.

**Conclusion:** A brand-new `helper2` variant group has no stored
`group_state` row on its first appearance for any (WR, week). Both lookup
paths structurally read that absence as CHANGED, never as a false skip. The
mechanism cannot suppress a first Helper #2 generation.

**Consequence:** No later plan needs to add a suppression guard for this
mechanism. This closes Assumption A1 for plan 14-04 (HASH_FIELDS decision)
and plan 14-06 (subcontractor Helper #2 shadow variants) — both introduce
new group_state-tracked identities that inherit this same safe first-run
behavior with no additional code change.

## A2

**Verdict: CONFIRMED SAFE**

**Question:** Does the `_live_row_attachments` pre-seed key on the full
identity tuple or on something coarser — and if coarser, can a primary
attachment's presence be mistaken for a helper2 attachment's presence?

**Evidence:**
- `pipeline/orchestrate.py:1212-1242` (`_live_row_attachments`) — memoized
  strictly by `row_id` (`if memo is not None and row_id in memo: return
  memo[row_id]`, `:1232-1233`), i.e. the physical Smartsheet target-sheet
  row for a WR — coarser than the 4-tuple, confirming the research's
  suspicion.
- `pipeline/orchestrate.py:1343-1442`
  (`_preseed_live_attachment_listings`) — the Phase 11.1 bulk pre-seed
  buckets EVERY attachment on a row by `parent_id` (`:1423-1426`), so one
  `row_id` bucket can contain the primary AND helper AND (once shipped)
  helper2 attachments for the same WR, all mixed together in one list.
  Confirms the coarser keying: this pre-seed is per-row, not per-variant.
- `pipeline/cleanup.py:770-798` (`_has_existing_week_attachment`) — the
  actual identity check performed against that mixed per-row listing.
  Every candidate attachment's filename is parsed via `build_group_identity`
  (`:784`) and the function returns `True` ONLY when `ident_wr`, `ident_week`,
  `ident_variant`, AND `ident_identifier` ALL match the requested identity
  (`:792-796`, `and` of all four conditions). A primary attachment's filename
  parses to `ident_variant == 'primary'`, which fails the `ident_variant ==
  variant` check for a `variant='helper2'` lookup — it cannot register as a
  match.
- `pipeline/change_detection.py:827-833` — `build_group_identity` already
  has an explicit `elif _first_marker == 'Helper2':` branch (added by plan
  14-01), parsing the `helper2` variant and its identifier from the
  `_Helper2_<name>` filename token, distinct from the `'Helper'` branch
  immediately above it (comment: "'Helper2' and 'Helper' are distinct
  underscore-split tokens and never collide").

**Conclusion:** The pre-seed's row-level (coarser) keying does not create a
false-positive risk. The coarse cache only determines WHICH attachments are
candidates for inspection; `_has_existing_week_attachment`'s per-attribute
filename-identity match is what decides existence, and that match already
requires `ident_variant == 'helper2'` specifically. A row that has a primary
or Helper #1 attachment but no Helper #2 attachment yet will correctly
report "no existing attachment" for a `helper2` lookup and force
regeneration.

**Consequence:** No guard needed. This closes Assumption A2 for plan 14-06:
the two subcontractor Helper #2 shadow variants must route through the same
`build_group_identity` / `_has_existing_week_attachment` pattern (standard
sibling-branch cloning, already the established pattern for every other
variant family member), not a new risk introduced by this pre-seed.

## Parity sub-finding (feeds A1/A2 item 3)

**Verdict: NOT A LIVE CONCERN TODAY — plan 14-04's hash decision is
UNAFFECTED.**

**Question:** Does `pipeline/parity.py` consume `content_hash` values or
`row_event` volume in a way that a one-time mass hash change would disturb a
parity streak?

**Evidence:**
- `pipeline/orchestrate.py:4309-4314` — the entire shadow-parity block
  (`compare_shadow_parity` + `run_shadow_delta_reads` +
  `combine_verdicts`) executes ONLY when `_resolved_mode == 'full' AND
  RUN_MEMORY_WRITE_ENABLED AND not RUN_MEMORY_INCREMENTAL_ENABLED AND not
  TEST_MODE`.
- `pipeline/config.py:494-496` and `:527-529` — both
  `RUN_MEMORY_WRITE_ENABLED` and `RUN_MEMORY_INCREMENTAL_ENABLED` default to
  `'0'` (parsed via `os.getenv(..., '0')`), and `PROJECT.md`/`STATE.md`
  confirm `RUN_MEMORY_WRITE_ENABLED` "stays OFF in production" as of the
  most recent Phase 10/11 status. The shadow-parity block therefore does not
  execute on any production run today.
- `pipeline/parity.py:85-204` (`compare_shadow_parity`) — even when active,
  this function compares TWO hash maps computed within the SAME run
  (`candidate_group_hashes` from the D-04 affected-pair filter,
  `actual_group_hashes` from this run's own actually-regenerated groups),
  both produced fresh by `calculate_data_hash()` this run. It never reads a
  PRIOR run's stored `group_state.content_hash`, so it has no dependency on
  which fields compose the hash (`HASH_FIELDS`) — it treats both hash values
  opaquely and only asks whether they are equal for a shared group key.
- `pipeline_memory/reader.py:597-729` (`get_parity_streak`) — derives the
  D-09 five-consecutive-pass streak from `run_ledger.notes.parity_verdict`
  rows. This streak's ONE consumer (the INC-05 retirement authorization gate)
  was already exercised and closed: `STATE.md`'s Phase 11 history records
  "11-08 INC-05 retirement shipped" — the gate's decision has already been
  made and does not re-open for Phase 14.

**Conclusion:** A Helper #2 rollout's mass wave of new `helper2` group
hashes cannot disturb the parity streak because the shadow-parity mechanism
that would compute a verdict is not running in production
(`RUN_MEMORY_WRITE_ENABLED=0`), and even if it were, it is structurally
insensitive to which fields feed the hash. Plan 14-04's HASH_FIELDS decision
is unaffected by `pipeline/parity.py`.

## A3

**Question:** What do `pipeline/attribution.py`, `pipeline/pricing.py`, and
`pipeline/observability.py` — touched by the 2026-07 prototype but not read
by the original research pass — need for Helper #2?

### pipeline/attribution.py — Verdict: NO CHANGE NEEDED

**Evidence:** The only role/variant vocabulary enumerated in this module is
`_SUBCONTRACTOR_SCOPE_VARIANTS` (`pipeline/attribution.py:118-121`, currently
`{'reduced_sub', 'aep_billable', 'reduced_sub_helper',
'aep_billable_helper'}`), consumed by `_build_subcontractor_wr_scope`
(`:124-157`). Its only two call sites are:
1. Four one-time migration hash-prune functions (`_run_phase_1_1_hash_prune`,
   `_run_subproject_b_hash_prune`, `_run_vac_crew_hash_prune`,
   `_run_subproject_d_hash_prune`) — confirmed DEAD in production per
   `pipeline/orchestrate.py:3135-3143`'s own comment: "the four one-time
   migration prunes ... operated on the retired hash_history dict and are
   removed ... no longer invoked here" (INC-05 retirement, Phase 11-08).
2. The LIVE legacy-format cleanup gate at `pipeline/orchestrate.py:4908-4964`
   — builds a WR-level (not variant-level) subcontractor scope to delete
   PRE-migration bare/`_Helper_<name>` attachments on `TARGET_SHEET_ID`,
   gated behind default-off kill switches
   (`SUBCONTRACTOR_LEGACY_HELPER_CLEANUP_ENABLED`,
   `SUBCONTRACTOR_LEGACY_PRIMARY_CLEANUP_ENABLED`).

**Justification:** A subcontractor WR always emits at least one primary-
family subcontractor group (`reduced_sub`/`aep_billable`) independent of
whether it also has a Helper #2 completion — WR-level scope detection does
not depend on every variant string being enumerated. Helper #2 never
existed in the pre-migration legacy format this cleanup targets (there is
no legacy `_Helper2_<name>` shape to migrate away), so
`_SUBCONTRACTOR_SCOPE_VARIANTS` needs no `helper2`/`aep_billable_helper2`/
`reduced_sub_helper2` entries for correctness, now or after plan 14-06 ships
the two new subcontractor shadow variants.

### pipeline/pricing.py — Verdict: NO CHANGE NEEDED for the plain `helper2`
variant; **CHANGE NEEDED, assigned to plan 14-06** for the two future
subcontractor Helper #2 shadow variants

**Evidence:** `_resolve_row_price(row, variant, missing_cus)`
(`pipeline/pricing.py:564-709`) is the single variant-aware pricing
dispatcher. Its "legacy variants short-circuit" guard (`:636-639`) is:
```python
if variant not in (
    'aep_billable', 'reduced_sub',
    'aep_billable_helper', 'reduced_sub_helper',
):
    return parse_price(row.get('Units Total Price'))
```
`'helper2'` is not in that tuple, so it falls through to the SAME
`parse_price(row.get('Units Total Price'))` passthrough as `primary`/
`helper`/`vac_crew` — the identical code path, not merely an assumed
equivalent one.

**Justification (this is itself a load-bearing finding, per the task's own
framing):** Pricing is variant-agnostic for the plain `helper2` variant BY
CODE, confirming D-14-03 ("Helper #2 inherits Helper #1 pricing untouched")
is true, not assumed. However, once plan 14-06 creates the
`aep_billable_helper2` / `reduced_sub_helper2` subcontractor shadow variants,
TWO branches in this same function must be extended with the new variant
strings or those shadow files will silently price via raw SmartSheet values
instead of the correct rate-table calculation:
1. The exclusion tuple at `:636-639` — the two new variants must be ADDED
   (like their siblings `aep_billable_helper`/`reduced_sub_helper`), not
   left out, or they will incorrectly take the passthrough branch.
2. The rate-column family selector at `:678-681`
   (`if variant in ('aep_billable', 'aep_billable_helper'): ... else: #
   reduced_sub / reduced_sub_helper`) — both branches need the corresponding
   new Helper #2 shadow variant string added to select the correct
   `new_*_price` / `reduced_*_price` rate column.

This is assigned to **plan 14-06** as a required task, not a discretionary
one — omitting it would be a real, latent billing-pricing correctness bug
for the two shadow variants specifically.

### pipeline/observability.py — Verdict: **CHANGE NEEDED, assigned to plan
14-07** (fixtures) **and plan 14-08** (per the plan's own cross-reference)

**Evidence:** `pipeline/grouping.py:785` (added by plan 14-01) emits:
```python
logging.info(f"🔧 HELPER2 GROUP CREATED: WR={wr_key}, Week={week_end_for_key}, Helper2={helper2_foreman}, Dept={helper2_dept}, Job={helper2_job}")
```
at INFO level, embedding the raw Helper #2 foreman's name directly in the
message body (mirroring the existing `HELPER GROUP CREATED` line at
`pipeline/grouping.py:748` exactly, sibling-branch style). A second line at
`pipeline/grouping.py:787-789` (debug level) embeds the same raw name in an
exclusion diagnostic.

`pipeline/observability.py`'s `_PII_LOG_MARKERS` module-level tuple (first
defined at `pipeline/observability.py:357`) is the exact constant a new
Helper #2 log line must route through — it is what
`sentry_before_send_log`/the breadcrumb sanitizer scan for before allowing a
log body to reach Sentry (`pipeline/observability.py:597`, `:648`). Its
current Helper #1-shaped entries are: `"HELPER GROUP CREATED"` (`:364`),
`"_HELPER_"` (`:412`), `"_AEPBILLABLE_HELPER_"` (`:460`),
`"_REDUCEDSUB_HELPER_"` (`:461`), among others. NONE of these is a substring
of the new Helper #2 literals — `"HELPER2 GROUP CREATED"` does not contain
`"HELPER GROUP CREATED"` (the inserted `"2"` breaks the match at the
character immediately after `"HELPER"`), and `"_HELPER2_"` does not contain
`"_HELPER_"` for the same reason. This is confirmed NOT an accidental-match
case like the one `pipeline/observability.py:472-478`'s own comment
documents for `"REDUCED SUB HELPER GROUP CREATED"` (which DOES accidentally
contain `"HELPER GROUP CREATED"`) — the Helper #2 token shape breaks every
existing substring, deliberately or not.

**Justification:** `CLAUDE.md`'s own rule states: "Adding a new INFO log
that embeds row content requires either stripping PII or extending
`_PII_LOG_MARKERS` in the same PR." Today this is a dormant risk only
(`SENTRY_ENABLE_LOGS` defaults `false`, so `before_send_log` never runs in
production), but it is a real gap in the second of the three
defense-in-depth layers PROJECT.md documents, and per this plan's own text
must be handed to plans 14-07 and 14-08. The exact constant to extend:
`_PII_LOG_MARKERS` in `pipeline/observability.py` (module-level tuple,
`:357`). The specific new literals needed, mirroring every existing Helper
#1 entry: `"HELPER2 GROUP CREATED"`, `"_HELPER2_"`, and a `"Helper2="`
name-bearing token equivalent to the existing Helper #1 coverage.

### Prototype fixture-shape review

Skimmed (fixture shapes only, per this task's scope) —
`test_helper2_formula_generation.py.txt` (482 lines) and
`test_weekly_excel_helper_split.py.txt` (303 lines).

`test_helper2_formula_generation.py.txt` is almost entirely about the
prototype's Smartsheet column-formula-cloning/provisioning tool — rejected
scope per D-14-12 (Phase 14 is generation-only; no column-provisioning
script). No reusable row-processing fixture shapes found in this file.

`test_weekly_excel_helper_split.py.txt` is directly relevant to Phase 14's
actual row-processing work:

- **Reusable shape:** the base row fixture `_row(**overrides)`
  (`test_weekly_excel_helper_split.py.txt:23-42`) — a dict of canonical
  column keys (`Work Request #`, `Weekly Reference Logged Date`, `Snapshot
  Date`, `Units Completed?`, `Units Total Price`, `Quantity`, `CU`,
  `Foreman`, `Dept #`, `Job #`) plus pipeline-internal keys
  (`__effective_user`, `__assignment_method`, `__source_sheet_id`,
  `__row_id`, `__is_helper_row`) — matches `group_source_rows`'s actual
  input contract and is directly reusable as a base fixture for future
  Helper #2 tests. The Helper #2 INPUT field names used in overrides
  (`__is_helper2_row`, `__helper2_foreman`, `__helper2_dept`,
  `__helper2_job`, `test_weekly_excel_helper_split.py.txt:88-95`) also match
  the CURRENT shipped `pipeline/fetch.py`/`pipeline/grouping.py` field names
  exactly (confirmed against `pipeline/grouping.py:486-487, 772-776`).
- **Stale assertion:** `test_helper2_only_emits_a_separate_role`
  (`test_weekly_excel_helper_split.py.txt:88-103`) asserts the OUTPUT row
  uses a UNIFIED `__helper_foreman` / `__helper_role == 2` shape (a single
  shared "role" field distinguishing Helper #1 from Helper #2). This is
  NOT how the shipped implementation works: 14-01 chose sibling-branch
  cloning (D-14-11) — the output row carries a DISTINCT `__helper2_foreman`
  key, and no `__helper_role` field exists anywhere in the current
  codebase. Any test copied from this prototype file MUST be rewritten
  against the sibling-key shape, never the unified-role shape. The
  prototype's `__helper2_email` field is similarly stale — no email
  surfacing exists in the shipped implementation (D-14-04 marks `Foreman
  Helper #2 Email` as non-gating optional metadata, not currently wired
  anywhere).
- The filename shape asserted in
  `test_helper2_filename_identity_round_trips`
  (`test_weekly_excel_helper_split.py.txt:235-245`) —
  `WR_90001_WeekEnding_080226_120000_Helper2_Helper_Two_abc.xlsx` — matches
  the shipped `_Helper2_<name>` token exactly (confirmed against
  `pipeline/change_detection.py:827-833`). The two subcontractor shadow
  filename shapes in the same test (`AEPBillable_Helper2_...` /
  `AEPBillable_Helper_..._Helper2_...`) are candidate fixture shapes for
  plan 14-06, but MUST be re-validated against whatever token order
  `pipeline/excel.py`/`pipeline/orchestrate.py` actually produce once that
  plan ships — they do not exist in the current codebase to compare against.
