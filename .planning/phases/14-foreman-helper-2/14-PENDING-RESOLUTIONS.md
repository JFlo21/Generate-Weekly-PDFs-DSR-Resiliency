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
