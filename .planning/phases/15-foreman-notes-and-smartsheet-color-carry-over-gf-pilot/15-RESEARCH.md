# Phase 15: Foreman Notes and Smartsheet color carry-over (GF pilot) - Research

**Researched:** 2026-10-29
**Domain:** Production billing pipeline (Smartsheet SDK 4.3.0 -> openpyxl 3.1.5 -> Smartsheet attachment); change-detection hashing; Phase 11 shadow-parity fingerprint
**Confidence:** MEDIUM-HIGH (integration points and SDK mechanics verified against code; ONE blocking unknown: whether `conditionalFormat` is actually returned live - no token in this environment)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-15-01:** A scope switch with values `off` / `pilot` / `all`, default `pilot`, read via `os.getenv` in `pipeline/config.py` with the repo's env-var pattern. `off` = exact current behavior. `all` = every Excel file (future rollout). Reversibility: reversible - env flag.
- **D-15-02:** Pilot allowlist is a separate setting (comma-separated names), default GF-1, GF-2, GF-3 (aliases; superseded by the public-repo identifier rule: the code default is EMPTY and the real names are supplied via local `.env` / a GitHub Actions repository variable). Owner can change it without code edits.
- **D-15-03:** Dry run first. Uploading pilot-changed files to the pre-planned pricing sheet sits behind its own switch (off until the owner reviews dry-run output). Existing `SKIP_UPLOAD` / `TEST_MODE` semantics are unchanged.
- **D-15-04:** A WR's GF = the `General Foreman` column on the pre-planned pricing sheet (`TARGET_SHEET_ID`; verified 2026-10-29 via read-only `get_columns`: column `General Foreman`, formula-driven, returns `"NA"` on lookup miss), matched by `Work Request #`. `pipeline/upload.py` already reads this sheet's `Work Request #` column.
- **D-15-05:** Matching ignores case and collapses/trims whitespace. A WR whose GF is `NA`, blank, unmatched, or absent from the sheet - or any read failure of that sheet - is non-pilot and gets today's file unchanged (fail-closed to current behavior).
- **D-15-06:** Pilot files get a new column I header `Foreman Notes` in every day block; each CU row's note goes in column I of that same row (wrapped text, wider column I). Columns A-H keep their positions and meanings (Pricing stays H; G "N/A" untouched). Pilot day-header merge becomes A:I and the TOTAL row fills I red; all merges via `safe_merge_cells()`.
- **D-15-07:** Pilot files get landscape fit-to-page-width print setup (pilot-only) so the wider sheet prints on one page width. Never write `oddFooter.right.text`.
- **D-15-08:** Note source = the existing `Foreman Notes` column on the Resiliency ProMax database sheets (primary + helper foreman folders) and the intake sheets. Sheets without the column are fine (note blank). The column must be added to the `pipeline/discovery.py` synonym mapping so `column_ids` fetch filtering includes it.
- **D-15-09:** Copy background fill + font (text) color only. No bold/italic/underline/strikethrough.
- **D-15-10:** Effective style per cell: `conditionalFormat` slot when present, else static `format` slot. Each Excel column takes its own source cell's color: Pole #, CU, Work Type, CU Description, UOM, Quantity, and Pricing (from the `Units Total Price` cell). Headers, day headers and TOTAL rows keep `RED_FILL`. Any parse error / unknown palette index / empty descriptor -> today's plain `BODY_FONT`, no fill (fail-closed).
- **D-15-11:** A notes-only edit regenerates and re-uploads the pilot file. Implement as a pilot-gated meta token (pattern: `SUB_RATES_FP` in `pipeline/change_detection.py`), NOT by adding fields to `_extended_row_fields`. The same pilot predicate must fold the raw notes column into `pipeline/memory_candidate.py` `row_group_hash_fingerprint` / `GROUP_DERIVATION_KEYS` so Phase 11 shadow parity holds (G-11-37 lesson). Reversibility: costly.
- **D-15-12:** Color-only changes do NOT trigger regeneration. Colors refresh whenever the file regenerates for any reason. Turning the pilot on re-sends every pilot GF file once.
- **D-15-13:** Phase 15 is the next feature after Phase 11. Planning and coding may proceed in parallel on a branch off master; Phase 15 MERGES only after the 11-15 live parity reading closes Phase 11.

### Claude's Discretion
Env-var names, module placement (new `pipeline/foreman_notes.py` or similar owning module per `.claude/rules/python-module-architecture.md`; facade stays thin), palette caching strategy, column I width, test layout.

### Deferred Ideas (OUT OF SCOPE)
- Color-driven re-send (would need delta-visible color signals).
- Bold/italic/strikethrough carry-over.
- GF alias list (alternate spellings).
</user_constraints>

<phase_requirements>
## Phase Requirements

No requirement IDs were assigned. Proposed IDs (derive from CONTEXT; add as a new `## v1.5 Requirements` block in REQUIREMENTS.md):

| ID | Description | Research Support |
|----|-------------|------------------|
| FN-01 | Scope switch `off`/`pilot`/`all` (default `pilot`); `off` and every non-pilot group produce cell-identical workbooks and byte-identical hashes vs today (D-15-01) | Sections "Effective scope", "Test strategy" |
| FN-02 | Separate comma-separated pilot allowlist setting (D-15-02) | "Config surface" |
| FN-03 | GF resolved once per run from `General Foreman` on `TARGET_SHEET_ID` by `Work Request #`; case/whitespace-insensitive; fail-closed on NA/blank/miss/read failure/ambiguity (D-15-04/05) | "GF lookup" |
| FN-04 | `Foreman Notes` mapped by discovery and carried on both full-read and delta-read row dicts identically (D-15-08) | "Fetch design", "Mapping marker" |
| FN-05 | Pilot files: column I `Foreman Notes` per CU row, day header A:I, TOTAL fill I, via `safe_merge_cells` (D-15-06) | "Excel integration" |
| FN-06 | Pilot-only landscape fit-to-width print setup; never `oddFooter.right.text` (D-15-07) | "Excel integration" |
| FN-07 | Copy fill + font colour only, effective conditional-else-static, fail-closed to plain `BODY_FONT` (D-15-09/10) | "Style resolution" |
| FN-08 | Pilot-gated `NOTES_FP` meta token; non-pilot hash byte-identical (D-15-11) | "Change detection" |
| FN-09 | Pilot-gated notes component in `row_group_hash_fingerprint` + AST coverage test + globals-fingerprint inclusion; full vs delta parity (D-15-11) | "Phase 11 parity" |
| FN-10 | Colour-only edits never trigger regeneration (D-15-12) | "Style resolution" |
| FN-11 | Dry run first; pilot-file upload behind its own switch; `SKIP_UPLOAD`/`TEST_MODE` unchanged (D-15-03) | "Upload gating" |
| FN-12 | All output paths (primary, helper, Helper #2, VAC crew, subcontractor variants) covered via the single `generate_excel` | "Output paths" |
| FN-13 | Merge gated on Phase 11 closure (D-15-13) | process only (branch is stacked on PR #435) |
</phase_requirements>

## Summary

**Answer first (limits and blockers):** (1) The live probe could NOT be run: `SMARTSHEET_API_TOKEN` is not in this environment (checked via `env`; `.env` deliberately not opened). Whether `Cell.conditionalFormat` is populated is therefore UNVERIFIED and is a `[BLOCKING]` human-verify task; a ready-to-run read-only probe script is in "Probe script" below. The SDK side IS verified: `Cell` exposes `conditional_format` and `format_`, `Sheets.get_sheet` accepts `include`, `column_ids`, `row_ids`, and the `/serverinfo` palette is fetchable WITHOUT a token and was fetched live (42 entries, index 0 = `none`). (2) The biggest design findings that change the plan shape are in "Key design findings" below - read those before planning.

The change is architecturally small if the new logic lives in ONE owning module (`pipeline/foreman_notes.py`) with a handful of one-line, pilot-gated seams in `excel.py`, `change_detection.py`, `memory_candidate.py`, `discovery.py`, `orchestrate.py`. Every Excel file (primary, helper, Helper #2, VAC crew, subcontractor variants) is produced by the single `generate_excel` -> `write_day_block`; there is exactly one `openpyxl.Workbook(` in non-archive code.

**Primary recommendation:** Notes ride the normal mapped-column path (identical on full and delta reads by construction); colors do NOT go through the bulk fetch at all - they are fetched lazily, pilot-groups-only, via `get_sheet(include='format', column_ids=..., row_ids=...)` just before `generate_excel`. Gate the whole feature by an *effective scope* that is `off` on production (non-`SKIP_UPLOAD`) runs until the upload switch is on, which makes D-15-03 trivially safe and removes two hazards (stale billing on pilot WRs; a hash trap that would suppress the first real upload).

## Key design findings (read first)

1. **GF must be known BEFORE PHASE 2 - the existing target-sheet read is too late.** The Phase 11 memory write (`_run_memory_write_phase`, stamps `__mem_group_fp` via `row_group_hash_fingerprint`) runs right after PHASE 2 (full mode, ~orchestrate.py:3155-3165) or INSIDE PHASE 2a (incremental, ~2080). The target-sheet map (`create_target_sheet_map_with_quarantine`, a full-column `client.Sheets.get_sheet(sheet_id)`, upload.py:~75) is built much later (~orchestrate.py:3498). So the pilot predicate cannot reuse that read. Do ONE light column-filtered read of `TARGET_SHEET_ID` (`column_ids` = `Work Request #` + `General Foreman`) right after `smartsheet.Smartsheet(...)` / before PHASE 1, store an immutable module-level state, and use that SAME state for fingerprint, hash token, render and upload gate (single source of truth; avoids a mid-run GF edit making hash and render disagree). Cost: 1 extra API call per run, only when effective scope != `off`.
2. **Do not put `include=format` in the bulk fetch.** Pilot-only lazy enrichment is better: ~208k rows x 7 cells of descriptor strings would inflate every sheet response (the code base already documents Error 4000 on large sheets and a 165/180 min budget), non-pilot fetch stays byte-for-byte unchanged, and D-15-12 says colours are not hash inputs so the delta path never needs them. This also makes "identical on both paths" trivially true (neither path carries styles). CONTEXT lists `include=format` at the fetch lines as an integration point, not a locked decision; flag to owner (Open Question OQ-3).
3. **Adding the `Foreman Notes` synonym alone is NOT enough - bump the mapping-schema marker.** Frequent runs admit sheets from the `sheet_registry` skip index with their STORED column mapping; admission requires `watermark.mapping_schema == MAPPING_SCHEMA_MARKER` (discovery.py:72, sixth condition). Without a marker change, skip-admitted sheets never gain a `Foreman Notes` mapping until a deep run. Phase 14 used exactly this mechanism for Helper #2.
4. **Pilot-gate in `calculate_data_hash` must live outside the AST-scanned functions.** `tests/test_row_state_group_hash_domain.py::KeyCoverageDriftTests` AST-scans `_extended_row_fields`, `canonical_sorted_rows`, `_first_nonempty_foreman`, `calculate_data_hash` for `row.get('<key>')` reads and fails on any key that is not fingerprinted or excluded. Compute the notes digest in `foreman_notes.py` (receiver names / key hidden behind a function) and add a NEW dedicated coverage test, rather than adding `'Foreman Notes'` to `_FINGERPRINT_EXCLUSIONS` (which would be wrong - it IS a hash input for pilot rows).
5. **The globals fingerprint must include pilot scope/allowlist/WR-set (only when effective scope != off).** `memory_candidate.group_hash_globals_fingerprint` exists precisely because group-hash inputs that no row delta sees (G-11-37) otherwise cause `only_in_actual` shadow-parity failures. Changing the allowlist, scope or a GF assignment regenerates groups with zero row changes. Append the pilot element only when effective scope != off so the off-state fingerprint stays byte-identical (otherwise the stored fingerprint flips once for everyone).
6. **Formula injection.** Notes are free text from Smartsheet. openpyxl turns any string starting with `=` into a formula cell; verified locally: assigning `'=1+1'` yields `data_type 'f'` and survives save/reload as a formula. Force `cell.data_type = 's'` for note cells (verified: stays `'s'` after reload), strip `openpyxl.cell.cell.ILLEGAL_CHARACTERS_RE` matches, truncate to 32767 chars - and hash exactly the sanitized string that is written.
7. **Upload switch hazard.** The naive gate ("pilot group + switch off -> `skip_upload` in `_upload_one`") has two production hazards: (a) a pilot-GF WR that regenerates for an ordinary billing change would NOT upload while the switch is off (stale billing attachment for ~3 GFs), and (b) it regenerates every run forever (hash never advances on `skip_upload`). See "Upload gating" for the recommended effective-scope design.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| GF -> pilot WR set | Python pipeline (new `pipeline/foreman_notes.py`) | Smartsheet API (TARGET_SHEET_ID read) | Batch job; Smartsheet is the data source |
| Note text carry | Fetch/discovery (`pipeline/discovery.py`, `pipeline/fetch.py`) | — | Existing mapped-column path |
| Colour descriptors | Python pipeline (lazy enrichment, `foreman_notes.py`) | Smartsheet API `include=format` | Pilot-only, avoids bulk payload |
| Style -> openpyxl | `pipeline/excel.py` seam calling `foreman_notes` helpers | — | Excel rendering owner |
| Change detection token | `pipeline/change_detection.py` seam | `foreman_notes.py` digest | Hash owner |
| Phase 11 fingerprint | `pipeline/memory_candidate.py` seam | `foreman_notes.py` component | Fingerprint owner |
| Upload gate | `pipeline/orchestrate.py` (effective scope computed once) | `pipeline/config.py` env flags | Orchestrator owns run-level decisions |
| Portal / website | not touched | — | No Supabase/portal change |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| smartsheet-python-sdk | 4.3.0 (pinned; installed 4.3.0 [VERIFIED: `python -I -c "import smartsheet"`]) | `Sheets.get_sheet(include=, column_ids=, row_ids=)`, `Server.server_info()` | Repo-pinned exact; no change |
| openpyxl | 3.1.5 (installed [VERIFIED]) | `PatternFill`, `Font`, `PageSetupProperties(fitToPage=True)` | Repo standard; never switch engine in this repo path |

### Supporting
None. **No new packages** are needed (palette is a pinned in-repo tuple; no colour library). Package Legitimacy Audit: not applicable - no external packages added; `requirements.txt` unchanged.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pinned palette tuple + live drift test | Fetch `/serverinfo` each run | `/serverinfo` is unauthenticated (SDK sets `auth_settings = None`) so a runtime fetch is feasible, but adds a network dependency to every pilot run and a failure mode; pinned + drift test is deterministic and fail-closed (unknown index -> plain). Recommend pinned. |
| Lazy pilot-only style fetch | `include=format` on bulk fetch (CONTEXT canonical ref) | Bulk adds payload to all ~121 sheets / ~208k rows and every run; lazy touches only pilot-group rows. See OQ-3. |

**Installation:** none.

## Architecture Patterns

### System Architecture Diagram

```
 main() start (client created)
   |
   |-- compute effective_scope = f(FOREMAN_NOTES_SCOPE, SKIP_UPLOAD, FOREMAN_NOTES_UPLOAD, TEST_MODE)
   |-- if effective_scope == pilot: ONE get_sheet(TARGET_SHEET_ID, column_ids=[WR,GF]) -> {wr_key: gf_norm}
   |        fail / ambiguous / NA / not in allowlist  => WR not pilot (fail-closed)
   |-- foreman_notes.set_state(FnState(scope, pilot_wrs))     <-- immutable module state
   v
 PHASE 1 discovery  --(synonym 'Foreman Notes' + marker bump)--> column_mapping incl. notes col
   v
 PHASE 2 / 2a+2b fetch  (UNCHANGED call shape; 'Foreman Notes' arrives as ordinary mapped raw column)
   |   full path: fetch.py ~580 loop        delta path: map_delta_sheet_rows ~299   (same value/display_value fallback)
   v
 _run_memory_write_phase -> row['__mem_group_fp'] = row_group_hash_fingerprint(row)
   |      (+ foreman_notes.row_notes_component(row) iff is_pilot_row(row))
   v
 group_source_rows (per-group row COPIES) -> calculate_data_hash(group_rows)
   |      (+ meta_parts "NOTES_FP=<digest>" iff is_pilot_group(group_rows))
   v
 change-detection skip? --yes--> skip (unchanged)
   |no
   v
 [pilot group only] foreman_notes.attach_group_styles(client, group_rows)
   |      get_sheet(sheet_id, include='format', column_ids, row_ids chunk<=100) -> row['__fn_style']; cache by (sheet,row)
   v
 generate_excel -> write_day_block  (pilot: col I note + per-cell fill/font; else byte-for-byte today)
   v
 upload task -> _upload_one (SKIP_UPLOAD semantics unchanged)
```

### Recommended Project Structure
```
pipeline/
├── foreman_notes.py      # NEW owner: state, GF load, normalisers, palette, descriptor parse, style fetch, digests
├── config.py             # +3 env flags (scope, allowlist, upload switch); no facade re-export needed
├── discovery.py          # +1 synonym, marker bump (conditional on scope != off)
├── change_detection.py   # +1 pilot-gated meta token (3 lines)
├── memory_candidate.py   # +pilot-gated 3rd element in fingerprint, +globals fp element
├── excel.py              # +pilot branches in write_day_block / page setup / widths
└── orchestrate.py        # +state load (1 call), +style attach (1 call), no change to _upload_one if effective-scope design adopted
tests/
├── test_foreman_notes_state.py      # scope matrix, allowlist/GF normalisation, fail-closed
├── test_foreman_notes_hash.py       # byte-identity, NOTES_FP, tie-order, full-vs-delta parity
├── test_foreman_notes_excel.py      # cell-level identity vs golden; pilot cells; merges; formula-injection
├── test_foreman_notes_styles.py     # descriptor parser, palette, fail-closed; live drift test (opt-in)
└── fixtures/foreman_notes/golden_off_cells.json   # captured on the BASE commit in Wave 0
```

### Pattern 1: Effective scope (computed once, in `foreman_notes`)
**What:** `effective_scope = 'off'` if configured `off`, or `TEST_MODE`; `configured` if `SKIP_UPLOAD` (dry-run: render pilot output for review; nothing publishes and hash does not advance); `configured` if not `SKIP_UPLOAD` and `FOREMAN_NOTES_UPLOAD` on; else `'off'`.
**When:** every call site (`is_pilot_row/group`, GF load, style attach, globals fp) asks the module, never reads env itself.
**Why:** a production cron with the upload switch off behaves EXACTLY like today (no GF read, no hash token, no fingerprint change, no extra regeneration), satisfying D-15-03/D-15-01 `off` identity even though the configured default is `pilot`. The owner's dry run is the existing `SKIP_UPLOAD=true` local run. Flipping the upload switch on then changes pilot hashes once (D-15-12 "turning the pilot on re-sends every pilot GF file once") and uploads - no hash trap, because the "unchanged -> skip" comparison is against the pre-flip hash.
**Caveat:** a `SKIP_UPLOAD=true` run with prod Supabase creds still executes `_run_memory_write_phase` (gated on `RUN_MEMORY_WRITE_ENABLED and not TEST_MODE`), stamping pilot-component fingerprints into `row_state.content_hash`; the next prod run (effective off) re-stamps. Effect is only a wider Phase 11 candidate set once - note in the plan; the plan should state whether dry-run is run with creds unset (recommended: `RUN_MEMORY_WRITE_ENABLED` unset locally).
**Alternative (not recommended):** gate inside `_upload_one` (`task['group_key'] in pilot_keys and not switch` -> `'skip_upload'`). Hazards (a)/(b) in finding 7.

### Pattern 2: Pilot-gated hash token (mirror of `SUB_RATES_FP`)
**What:** in `calculate_data_hash` after the `SUB_RATES_FP` block add `tok = foreman_notes.group_notes_token(sorted_rows)`; `if tok: meta_parts.append(f"NOTES_FP={tok}")`. `group_notes_token` returns `''` unless `is_pilot_group(rows)`.
**Digest:** SHA-256[:16] over a SORTED list of `(row_identity_str, normalized_note)` pairs, JSON-encoded (not `'|'.join` - the pipe-collision is documented in `canonical_sorted_rows`). `row_identity_str = '|'.join(_cd._extended_row_fields(row, variant))` so two rows tied on the full sort key but with different notes still digest deterministically regardless of arrival order (the tiebreak lesson of PR #359). Sorting the pairs removes dependence on tie order.
**Normalisation (ONE function shared by hash, fingerprint, and Excel write):** `None` -> `''`; `str(v)`; remove `ILLEGAL_CHARACTERS_RE`; `.strip()`; truncate 32767. Write exactly that string.
**The token appears for pilot groups even when every note is blank** (so toggling pilot state on/off is detectable); decide in plan: recommended yes (token always present for pilot group; digest of all-blank is a constant).

### Pattern 3: Pilot-gated Phase 11 fingerprint
`row_group_hash_fingerprint` currently canonicalises `[fields, derivation]`. For pilot rows only, canonicalise `[fields, derivation, notes_component]`; for non-pilot rows the JSON stays `[fields, derivation]` (byte-identical). `is_pilot_row(row)` derives the WR with the SAME 3 steps as `orchestrate.derive_row_wr` (`str(raw).split('.')[0]`, `_RE_SANITIZE_HELPER_NAME.sub('_', ..)[:50]`) - copy via import-free duplicate in `foreman_notes` or move nothing; add a test that both agree. Delta rows carry raw `Work Request #` and `Foreman Notes`, so the component is identical on both read paths (the module docstring's mode-invariance rule: derived `__*` keys are excluded; `Foreman Notes` is a raw key).

### Anti-Patterns to Avoid
- **Adding `Foreman Notes` to `_extended_row_fields` / `GROUP_DERIVATION_KEYS` unconditionally** - changes every group's hash / every row's fingerprint (violates FN-01 and D-15-11).
- **Reading env inside excel.py/change_detection.py** - use the module state; keeps tests (which rebind facade attributes) simple.
- **Stashing styles on the shared row dicts used by the memory write** - `group_source_rows` makes per-group `r.copy()` (grouping.py:1585), so stash on the group copies only, key `__fn_style` (leading `__` skips the column sampler and is invisible to named-field hashing).
- **Using the target sheet's display text without sanitising** - see finding 6.
- **Re-encoding colour as bold/strike** - D-15-09 forbids.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Merged ranges | direct `ws.merge_cells` | `safe_merge_cells(ws, range)` (excel.py:48) | repo guardrail; overlap detection |
| WR key normalisation | new regex | same 3-step as `derive_row_wr` / `_build_target_sheet_map` (`str(x).split('.')[0]`, `_RE_SANITIZE_HELPER_NAME` (config.py:28), `[:50]`) | GF map keys must equal group-loop and target-map keys |
| SDK retry | custom loop | `smartsheet_call_with_retry(...)` (pipeline.retry; used for every fetch) | 429/4000 handling, bounded backoff |
| Query-param list encoding | manual join | SDK handles lists: [VERIFIED: `prepare_request` run locally -> `rowIds=11%2C22%2C33`]; existing code joins column ids to a string anyway - keep that style for `column_ids` |
| Colour palette | colour libs | pinned 42-tuple from `/serverinfo` + drift test | exact Smartsheet semantic |
| XML-illegal char stripping | custom regex | `openpyxl.cell.cell.ILLEGAL_CHARACTERS_RE` [VERIFIED: matches `\x01`] | library-owned |

**Key insight:** every hard part (retry, merge safety, WR key identity, hash tiebreak) already has an owner in this repo; the phase is plumbing plus two pure functions (descriptor parse, notes digest).

## Runtime State Inventory

Not a rename/refactor phase. Persistent-state notes that DO matter:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `pipeline_memory.sheet_registry.column_mapping` / `mapping_schema` (stored mapping lacks `Foreman Notes`); `row_state.content_hash` (pilot rows change once when effective scope turns on); `group_state` / durable group hash (pilot groups regenerate once) | marker bump (code); the regen is expected (D-15-11/12); no DDL (`HASH_ONLY_FIELDS` pattern, no new columns) |
| Live service config | Smartsheet `General Foreman` formula column on `TARGET_SHEET_ID` (read-only dependency); `Foreman Notes` column title on source sheets (unverified exact title) | human-verify column titles (probe) |
| OS-registered state | None - GitHub Actions cron only; workflow YAML needs NO change (flags default in code; do not touch `advanced_options` parser) | none |
| Secrets/env vars | New env names only (no secrets). Production env is not declared in the workflow, so defaults apply | none |
| Build artifacts | None | none |

## Common Pitfalls

### Pitfall 1: Stale stored mapping (no `Foreman Notes` on skip-admitted sheets)
**What goes wrong:** notes silently blank on frequent runs. **Why:** registry skip index returns stored `column_mapping`. **Avoid:** make `MAPPING_SCHEMA_MARKER` depend on effective-scope!=off (e.g. `"helper2-v1"` stays when off; `"helper2-v1+fn1"` when on) and add the synonym only when on, so `off` is exactly today's stored mapping and today's `column_ids` payload; one revalidation on enabling and on disabling (bounded 3-row reads since G-11.1-4). Check `tests/test_mapping_schema_marker_caller.py` and `tests/test_foreman_helper_2.py` (they import the symbol, not the literal; one asserts the literal `"helper2-v1"` at line ~777 for an explicit dict - unaffected). **Warning sign:** `_log_column_mapping_drift` WARNING on deep run.

### Pitfall 2: Exact-title synonym match
Discovery matches `c.title in synonyms` exactly (discovery.py:664). If a sheet titles it `Foreman notes` or has trailing space it silently will not map. Probe must list the exact titles across a sample of sheets (OQ-1); add the observed variants as extra synonyms (all -> `'Foreman Notes'`).

### Pitfall 3: Dual-fetch of same Smartsheet row for several groups
One source row feeds primary + helper + Helper #2 + VAC groups. Cache styles by `(sheet_id, row_id)` for the run so each row is fetched once; chunk `row_ids` at <=100 per call; sequential group loop keeps API volume tiny vs 300 req/min, but go through `smartsheet_call_with_retry`.

### Pitfall 4: Whitespace-only differences flip the digest
Hash and write the same sanitized+stripped string; never hash the raw value and write the stripped one.

### Pitfall 5: TOTAL row / day header merges
Pilot day header `A:{start_row}` -> `A:I`; TOTAL merge stays `A:G` and fills H (value) and I (red). Non-pilot unchanged (`excel.py:706`, `:772`). `safe_merge_cells` returns without merging on overlap - tests must assert merged-range lists equal expected exactly.

### Pitfall 6: Column I already has width 15 today
`column_widths` (excel.py:839) already includes `'I': 15`. Pilot sets I wider (recommend 45-60) ONLY in the pilot branch, so off-state `column_dimensions` stay identical. Also the report header area merges `D:I` at ~excel.py:522 - untouched.

### Pitfall 7: Colour semantics
Palette index `0` = `none`, `3` = `transparent` -> no fill/font colour (not white). `1` = `#000000`, `2` = `#FFFFFF` are real. Doc example hex values are stale (`4 = #FEEEF0` in the guide vs live `#FFEBEE`) - the live fetch below is authoritative.

### Pitfall 8: Perpetual regeneration when upload is off
Only if the naive `_upload_one` gate is used. The effective-scope design avoids it.

### Pitfall 9: Incremental mode (flag OFF in production) and pilot-set changes
`RUN_MEMORY_INCREMENTAL_ENABLED` is OFF today. When it is turned on, a changed allowlist/GF assignment produces no row delta, so affected groups would not be in the candidate set until the weekly deep run. This is the same class as the subcontractor-rates fingerprint; note as accepted/documented, plus the globals-fingerprint inclusion (finding 5) makes the shadow side honest.

## Detailed answers to the priority research items

### 1. Smartsheet `include=format` / `column_ids`, descriptor, palette, fetch design

- **SDK surface [VERIFIED: local introspection, SDK 4.3.0]:** `Cell.__init__` defines `self._conditional_format = String()` and `self._format_ = String()`; `Cell({'columnId':1,'value':'x','format':',,,,,,,,3,4,,,,,,,','conditionalFormat':',,,,,,,,5,6,,,,,,,'})` -> `.format_ == ',,,,,,,,3,4,,,,,,,'` and `.conditional_format == ',,,,,,,,5,6,,,,,,,'`; an absent key yields `None` for both. `Sheets.get_sheet(self, sheet_id, include=None, exclude=None, row_ids=None, row_numbers=None, column_ids=None, page_size=None, page=None, if_version_after=None, level=None, rows_modified_since=None, filter_id=None)`.
- **Doc [CITED: developers.smartsheet.com/api/smartsheet/guides/advanced-topics/cell-formatting]:** descriptor is 17 comma-separated positions, 0-based; verbatim rows: `| 8 | **color** (text) | 4 = #FEEEF0 | ",,,,,,,,4,,,,,,,," |` and `| 9 | **color** (background) | 8 = #E6F5FE | ",,,,,,,,,8,,,,,,," |`; `include=format` required; "A `format` property appears only when formatting differs from the defaults"; "Conditional formatting will be indicated by a `conditionalFormat` value" (Context7 `/websites/developers_smartsheet_api`). Cell schema lists both `conditionalFormat` and `format` string properties. The guide does not say how a conditional format merges with the static one per slot -> A2.
- **Palette [VERIFIED: live GET https://api.smartsheet.com/2.0/serverinfo, no auth, 2026-10-29]:** `formats.color` has **42** entries; verbatim: `['none', '#000000', '#FFFFFF', 'transparent', '#FFEBEE', '#FFF3DF', '#FFFEE6', '#E7F5E9', '#E2F2FE', '#F4E4F5', '#F2E8DE', '#FFCCD2', '#FFE1AF', '#FEFF85', '#C6E7C8', '#B9DDFC', '#EBC7EF', '#EEDCCA', '#E5E5E5', '#F87E7D', '#FFCD7A', '#FEFF00', '#7ED085', '#5FB3F9', '#D190DA', '#D0AF8F', '#BDBDBD', '#EA352E', '#FF8D00', '#FFED00', '#40B14B', '#1061C3', '#9210AD', '#974C00', '#757575', '#991310', '#EA5000', '#EBC700', '#237F2E', '#0B347D', '#61058B', '#592C00']`; `formats.defaults == '0,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0'`. Pin this tuple in `foreman_notes.py`; add an opt-in live drift test (`FN_PALETTE_LIVE=1`, unauthenticated GET, skipped offline).
- **Parser:** `parts = descriptor.split(',')`; require `len(parts) <= 17` (pad); `text = parts[8]`, `bg = parts[9]`; each must be `''` or a base-10 int in `range(len(PALETTE))`; any other -> that slot invalid -> fail-closed to "no colour" for the WHOLE cell (D-15-10: "Any parse error / unknown palette index / empty descriptor -> today's plain BODY_FONT, no fill"). Entry `'none'`/`'transparent'` -> no colour. Hex entries -> 6-digit `RRGGBB`.
- **Effective style:** per slot `conditional if non-empty/non-zero else static` (assumption A2 - verify in probe whether a conditional rule that sets only background leaves static text colour intact in the API output). Font: `Font(name='Calibri', size=11, color=hex)` (never copy bold/italic/underline/strike). Fill: `PatternFill(start_color=hex, end_color=hex, fill_type='solid')` (same constructor style as `RED_FILL`).
- **Fetch design (recommended):** new `foreman_notes.attach_group_styles(client, group_rows)` called only when `is_pilot_group(group_rows)` immediately before `generate_excel` (orchestrate.py ~4694; also the synthetic TEST_MODE call at ~586 is irrelevant - state is OFF there). Steps: collect `(__source_sheet_id, __row_id)` for rows lacking cache entries; per sheet, chunk row ids <=100; `smartsheet_call_with_retry(client.Sheets.get_sheet, sheet_id, include='format', column_ids=<comma string of ids for Pole #, CU, Work Type, CU Description, Unit of Measure, Quantity, Units Total Price>, row_ids=chunk, label=...)`; map `cell.column_id` -> logical column using the source's `column_mapping` (available from `source_sheets`; pass a `{sheet_id: column_mapping}` dict to the module, built once from `source_sheets`); store `row['__fn_style'] = {'Pole #': (fill_hex|None, font_hex|None), ...}`. Any exception, missing row, or `format_`/`conditional_format` both None -> no entry -> plain. Pole # synonyms: mapping already collapses `Point #`/`Point Number` to `Pole #`; CU description likewise; read the logical names from the mapping, not the raw titles.
- **Both-path identity of NOTES:** full path row build (fetch.py ~680-690: `raw_val = getattr(cell,'value',None); if raw_val is None: raw_val = getattr(cell,'display_value',None); row_data[mapped_name] = raw_val`) and `map_delta_sheet_rows` (fetch.py ~299, identical lines) are the same rule [VERIFIED: read both]. Once `Foreman Notes` is in `column_mapping` (so in `column_ids_param` at fetch.py:227-228 / 568-574) both paths attach it identically; no fetch.py edit is required for notes. Add one test asserting both paths produce equal `Foreman Notes` for the same fake sheet.
- **Fallback if the probe shows `conditionalFormat` is NOT returned** (CONTEXT specific: "stop and bring options back to the owner"): options for the owner - (i) static `format` only (rule-driven colours missing), (ii) read the rule via `GET /sheets/{id}/conditional-formatting`?? NOT verified, do not plan on it - leave to owner, (iii) descope colour. Plan must carry a `checkpoint:human-verify` and a documented stop.

### 2. GF lookup

- **What exists [VERIFIED: read upload.py:36-78]:** `_build_target_sheet_map(client, sheet_id)` does `client.Sheets.get_sheet(sheet_id)` (all columns, no `column_ids`), finds the `Work Request #` column by title, builds `{sanitized_wr: row}` with collision quarantine; main() calls it at ~3498. It returns `(target_map, target_sheet, quarantined_keys)`; the `target_sheet` object has `columns` and `rows` and COULD supply GF - but only after the memory write has already run (finding 1).
- **Recommended:** `foreman_notes.load_gf_map(client, sheet_id)`: one `smartsheet_call_with_retry(client.Sheets.get_sheet, sheet_id, column_ids="5180541294563204,2159630534528900")` (ids from CONTEXT/owner verification 2026-10-29; make them config defaults overridable by env), then VERIFY by title on `sheet.columns` (`Work Request #`, `General Foreman`); if either title missing/mismatched -> empty state (fail-closed). Cell value: `value` if not None else `display_value` (WR uses `display_value` in the existing map; use the same `str(...).split('.')[0]` + sanitizer so keys equal group-loop keys). GF normalise: `' '.join(str(x).split()).casefold()`; `'na'`/`''` -> no GF. Duplicate WR rows with DIFFERENT normalised GFs -> ambiguous -> non-pilot (fail-closed); identical GFs fine. Allowlist normalised the same way (split on `,`; allowlist names containing commas unsupported - state it). Pilot WR set = `{wr for wr,gf in map if gf in allowlist_norm}`. Any exception / empty sheet -> empty set, log one WARNING, Sentry breadcrumb (counts only; never names/values in Sentry - CLAUDE.md PII note).
- **Scope `all`:** no GF read; `is_pilot_*` returns True for any row with a WR.
- Pagination: repo rule is single bulk `get_sheet`; if `len(sheet.rows) < getattr(sheet,'total_row_count', len(sheet.rows))` log WARNING (unknown WRs are non-pilot = safe direction).

### 3. Integration points (all line refs read this session)

- **discovery.py:** `synonyms = {` at 615 (inside `_validate_single_sheet`), match at 664 `if c.title in synonyms and synonyms[c.title] not in mapping:`; `MAPPING_SCHEMA_MARKER = "helper2-v1"` at 72. Add `'Foreman Notes':'Foreman Notes'` (plus observed variants) into the dict conditionally (`if foreman_notes.mapping_enabled()`), and make the marker `"helper2-v1"` when disabled, a distinct string when enabled. Marker is read at call time by `_build_discovery_skip_index` and by `_compute_registry_marker_sheets` (orchestrate ~2547) via `_discovery.MAPPING_SCHEMA_MARKER`, so it must be resolved BEFORE discovery runs (state set at main() start) - make it a function-or-module-attribute set by `set_state`, or compute at import from config (scope+SKIP_UPLOAD+upload env are all import-time env, so an import-time constant works and keeps tests simple; tests for effective scope should still go through `foreman_notes.compute_effective_scope(...)` pure function).
- **change_detection.py:** `calculate_data_hash` meta tokens at 458-497; `SUB_RATES_FP` block ends 495-497; hasher.update of `"\n".join(meta_parts)`. Insert the `NOTES_FP` block after the `SUB_RATES_FP` block. [VERIFIED quote: `meta_parts.append(f"ROWCOUNT={len(sorted_rows)}")` at 464; `f"SUB_RATES_FP={_SUBCONTRACTOR_RATES_FINGERPRINT}"` at 495.] Do NOT touch `_extended_row_fields` (48-97). `sorted_rows` is already canonical there. `_compute_aggregated_content_hash` calls `calculate_data_hash` per variant so billing-audit `content_hash` follows automatically (expected one-time change for pilot).
- **memory_candidate.py:** `GROUP_DERIVATION_KEYS: tuple[str, ...]` at 48 (leave unchanged); `derivation = [str(row.get(k) or "") for k in GROUP_DERIVATION_KEYS]` at 121; canonical JSON at 122-125. Add pilot-only third element. `group_hash_globals_fingerprint` payload `[bool(extended), str(cutoff), str(sub_fp), str(rates_fp)]` (~335-345): append `foreman_notes.globals_component()` ONLY when it returns non-empty.
- **AST coverage test:** `tests/test_row_state_group_hash_domain.py` (KeyCoverageDriftTests at ~565; receivers set `_ROW_RECEIVERS` ~528). The new reads in `foreman_notes.py` are outside the scanned file/functions. Add a NEW test: assert `foreman_notes.NOTES_KEY == 'Foreman Notes'`; assert it is NOT in `GROUP_DERIVATION_KEYS`/`_extended_row_fields` (non-pilot byte-identity guard); assert `row_group_hash_fingerprint` (AST) references `foreman_notes.row_notes_component`; assert `calculate_data_hash` (AST) references `foreman_notes.group_notes_token`.
- **excel.py:** page setup 493-499 (`ws.page_setup.orientation = 'landscape'`, `paperSize = 9`, margins) - already landscape, so the pilot-only addition is `ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True); ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0` [VERIFIED: survives save/reload: fitToWidth=1, fitToHeight=0, fitToPage=True]. `write_day_block` 698-788: day-header merge 706 (`A{start_row}:H{start_row}`), `headers` list 716, row loop writes `row_values` + `cell.font = BODY_FONT` ~754-760, currency format col 8 at 766, TOTAL merge 772 (`A:G`), TOTAL value col 8 at 778-784. `column_widths` at 839 (includes `'I': 15`). `generate_excel` resolves `__resolved_price` once at 550 (`_row['__resolved_price'] = _resolve_row_price(...)`) - Pricing colour still comes from the source `Units Total Price` cell, not the resolved price. Compute `pilot = foreman_notes.is_pilot_group(group_rows)` once near `first_row` (excel.py ~170) and thread into `write_day_block` via closure.
- **Where the predicate is evaluated per group:** `group_key` -> the group's rows -> WR (`derive_group_wr` semantics, orchestrate.py:~335) -> `pilot_wrs` membership. Same function in hash, render and attach so they cannot disagree.

### 4. Output paths

`grep` of non-archive, non-test, non-script code: exactly one `openpyxl.Workbook(` (excel.py:473) and two `generate_excel(` callers (orchestrate.py:586 synthetic TEST_MODE; :4694 production). [VERIFIED] Primary, helper, Helper #2, VAC crew, `aep_billable`/`reduced_sub` and their helper shadows all flow through `generate_excel` -> `write_day_block`. Variant only affects pricing (`_resolve_row_price`) and header/filename. One gate covers all. Add one test per variant family asserting the pilot column I appears (primary, helper, helper2, vac_crew, aep_billable, reduced_sub, aep_billable_helper, reduced_sub_helper, +helper2 shadows).

### 5. Upload gating (today and minimal additive gate)

- Today: `SKIP_UPLOAD` (config.py:56, `os.getenv('SKIP_UPLOAD','false').lower() == 'true'`) -> `_upload_one` passes `dry_run=SKIP_UPLOAD` to `delete_old_excel_attachments` and returns `'skip_upload'` instead of attaching (orchestrate ~5290); results `'skip_upload'` do NOT advance durable hash or group_state (documented at ~5358-5369), `TEST_MODE` has no upload phase. Workflow `weekly-excel-generation.yml` has no `SKIP_UPLOAD` wiring [VERIFIED: grep], so a dry run is a LOCAL run (`SKIP_UPLOAD=true python generate_weekly_pdfs.py`, token required, files in `generated_docs/`).
- **Minimal additive gate (recommended):** the effective-scope design (Pattern 1) - no change to `_upload_one`, no change to upload task dicts. New flag: `FOREMAN_NOTES_UPLOAD` (default off). Existing semantics untouched.
- **Do NOT** add keys to `run_summary.json`: Gate 6 golden (`tests/golden/run_summary_baseline.json` via `scripts/check_run_summary_structure.py`) is structural. Log pilot counts only (counts, not names).

### 6. Test strategy

Baseline: `pytest --co` = 2498 tests collected; 1 pre-existing collection ERROR in `tests/test_audit_findings.py` (ImportError in this environment; not Phase 15 - record, do not fix).
- **Wave 0:** capture `tests/fixtures/foreman_notes/golden_off_cells.json` from the BASE commit BEFORE any code edit: for a fixed fixture (primary, helper, helper2, vac_crew, aep_billable, reduced_sub; several rows incl. non-ASCII text) call `generate_excel` with `OUTPUT_FOLDER` -> temp dir (pattern: `tests/test_group_identity_and_header_foreman.py` ~322-393 rebinds `generate_weekly_pdfs.OUTPUT_FOLDER` and `load_workbook`) and dump per-cell `(coordinate, value, number_format, font.b/color/size, fill.fgColor.rgb, alignment)`, `merged_cells.ranges` sorted, `column_dimensions` widths, `page_setup.*`, `sheet_properties.pageSetUpPr`. Exclude the "Report Generated On" timestamp cell and filename timestamp. Also capture golden `calculate_data_hash` digests for the same row sets.
- **FN-01 identity:** with state forced `off` AND with state `pilot` but non-pilot WR: workbook dump == golden; `calculate_data_hash` == golden digest; `row_group_hash_fingerprint` == value computed from a frozen copy of the pre-change algorithm (inline reference implementation in the test).
- **Pilot content:** note lands in `I{crow}` of its own CU row; header `Foreman Notes` at `I{start_row+1}`; day header merged `A:I`; TOTAL fill at I; merged ranges list exactly as expected; `oddFooter.right.text` untouched (assert footer attrs empty); note cell `data_type == 's'` for `=cmd` text; illegal char stripped; blank/None note -> blank cell; colours applied per column; unknown palette index/short descriptor/garbage -> plain `BODY_FONT`, no fill.
- **Hash:** token present only for pilot groups; notes-only edit flips hash; notes edit on non-pilot WR does NOT; row order permutation (including full-key ties with different notes) -> same digest; whitespace-only change hashes the same as written.
- **Full vs delta parity:** feed the same fake `Sheet` through the `get_all_source_rows` row-building closure path and `map_delta_sheet_rows`; assert `row_group_hash_fingerprint` equality (patterned on `tests/test_incremental_read.py`, and the existing parity tests that assert mode invariance).
- **GF:** mapping of fake target sheet -> pilot set: case/whitespace variants match, `NA`/blank/absent -> non-pilot, exception -> empty (fail-closed), duplicate WR with conflicting GF -> non-pilot, title mismatch -> empty.
- **Mapping marker:** `off` -> synonyms and marker identical to today; `on` -> marker differs and a stored `helper2-v1` watermark is NOT admitted from the skip index.
- **Gates:** `bash scripts/run_6_gates.sh` (AST import equality, facade completeness, pytest, mypy delta, py_compile, golden run_summary). New orchestrate imports of `pipeline.foreman_notes` must keep Gate 1/4 green; do not add facade re-exports unless Gate 2 demands.
- Quick command: `python -m pytest tests/test_foreman_notes_*.py -q -x`; full: `python -m pytest tests/ -q`.

### 7. Owning module (python-module-architecture.md)

`pipeline/orchestrate.py` is 6,278 lines and `pipeline/excel.py` 867 - do not grow them beyond seams. New `pipeline/foreman_notes.py` (est. 300-450 lines, one responsibility: "pilot-scoped Foreman Notes + colour carry-over"). Import rules: imports `pipeline.config` (flags, `_RE_SANITIZE_HELPER_NAME`) and `pipeline.retry`; must NOT import `pipeline.change_detection`/`excel`/`memory_candidate` at module import (they import it) - take `_extended_row_fields` via a lazy import inside the digest function or accept the identity string as a parameter. Update `docs/ai/architecture.md` module map and the ledger (`memory-bank/living-ledger.md` entry) in the same PR. Config: add to `pipeline/config.py` following the HELPER2 pattern (config.py:49-51): `FOREMAN_NOTES_SCOPE` (`os.getenv('FOREMAN_NOTES_SCOPE','pilot').strip().lower()`, invalid value -> `off` + WARNING, i.e. fail-closed), `FOREMAN_NOTES_PILOT_GFS` (code default EMPTY - real names via env / repository variable only, public-repo identifier rule; aliases GF-1..GF-3 in prose), `FOREMAN_NOTES_UPLOAD` (`('1','true','yes','on')`, default off).

## Proposed Probe script (READ-ONLY, human-verify; token NEVER printed)

Run locally by the owner (token in env), from the repo root, e.g. `python -I probe_fn.py <sheet_id>` where `<sheet_id>` is any Resiliency ProMax database sheet that has a `Foreman Notes` column (ids come from folder discovery; not hard-coded in `pipeline/discovery.py` - `discover_folder_sheets` enumerates folders). Do not commit it.
```python
import os, sys, collections
import smartsheet
c = smartsheet.Smartsheet(os.environ["SMARTSHEET_API_TOKEN"])   # never print
c.errors_as_exceptions(True)
sid = int(sys.argv[1])
cols = c.Sheets.get_columns(sid, include_all=True).data
by = {x.title: x.id for x in cols}
want = [t for t in ("Foreman Notes","Pole #","CU","Work Type","CU Description","Unit of Measure","Quantity","Units Total Price") if t in by]
print("titles with 'note':", [t for t in by if "note" in t.lower()])
sh = c.Sheets.get_sheet(sid, include="format", column_ids=",".join(str(by[t]) for t in want),
                        row_numbers=list(range(1, 21)))
n = collections.Counter()
for r in sh.rows:
    for cell in r.cells:
        n["cells"] += 1
        if cell.format_: n["static_format"] += 1
        if cell.conditional_format: n["conditional_format"] += 1
for r in sh.rows[:5]:
    for cell in r.cells:
        if cell.conditional_format or cell.format_:
            print(cell.column_id, repr(cell.format_), repr(cell.conditional_format))   # descriptors only, no cell values
print(dict(n))
```
Pass criteria: `conditional_format` count > 0 on at least one sheet known to have a rule-coloured cell, AND for a cell where a rule sets only the background, the static `format_` text colour (slot 8) is still present in `format_` (resolves A2). Fail -> stop and return to owner (CONTEXT).

## Code Examples

### Notes digest + normaliser (shared)
```python
# Source: this research; mirrors canonical JSON pattern of memory_candidate.row_group_hash_fingerprint
import hashlib, json
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

NOTES_KEY = 'Foreman Notes'
_MAX = 32767

def norm_note(v) -> str:
    if v is None:
        return ''
    s = ILLEGAL_CHARACTERS_RE.sub('', str(v)).strip()
    return s[:_MAX]

def group_notes_token(sorted_rows, variant_fields_fn) -> str:
    if not is_pilot_group(sorted_rows):
        return ''
    pairs = sorted(
        ('|'.join(variant_fields_fn(r)), norm_note(r.get(NOTES_KEY))) for r in sorted_rows
    )
    return hashlib.sha256(json.dumps(pairs, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()[:16]
```

### Pilot cell write (inside `write_day_block`)
```python
# Source: this research; formula-injection mitigation verified with openpyxl 3.1.5
if pilot:
    note_cell = ws.cell(row=crow, column=9)
    note_cell.value = norm_note(row_data.get(NOTES_KEY))
    note_cell.data_type = 's'                      # never a formula
    note_cell.font = BODY_FONT
    note_cell.alignment = Alignment(wrap_text=True, vertical='top')
    style = row_data.get('__fn_style') or {}
    for col_num, logical in ((1,'Pole #'),(2,'CU'),(3,'Work Type'),(4,'CU Description'),(5,'Unit of Measure'),(6,'Quantity'),(8,'Units Total Price')):
        fill, font_hex = style.get(logical, (None, None))
        cell = ws.cell(row=crow, column=col_num)
        if fill: cell.fill = PatternFill(start_color=fill, end_color=fill, fill_type='solid')
        if font_hex: cell.font = Font(name='Calibri', size=11, color=font_hex)
```

### Descriptor parser (fail-closed)
```python
def parse_slots(desc, palette=PALETTE):
    if not desc: return None
    parts = desc.split(',')
    if len(parts) > 17: return None
    parts += [''] * (17 - len(parts))
    out = []
    for raw in (parts[8], parts[9]):
        if raw == '': out.append(None); continue
        if not raw.isdigit() or int(raw) >= len(palette): return None
        hexv = palette[int(raw)]
        out.append(hexv[1:] if hexv.startswith('#') else None)   # 'none'/'transparent' -> None
    return tuple(out)   # (text_hex|None, bg_hex|None)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Guide example palette (`4 = #FEEEF0`) | Live `/serverinfo` (`4 = #FFEBEE`, 42 entries) | verified 2026-10-29 | do not copy doc hex values |
| Unconditional synonym adds | Marker bump forces one revalidation (Phase 14 pattern) | Phase 14 | required here |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Source sheets title the column exactly `Foreman Notes` (no case/space variants) | Pitfall 2, item 1 | notes silently blank on some sheets; cheap fix by adding synonyms once probe lists titles |
| A2 | Per-slot merge: conditionalFormat slot if non-empty else static slot (CONTEXT D-15-10 ambiguous between per-cell and per-slot) | Style resolution | wrong text colour where a rule sets only background; resolve in probe + confirm with owner |
| A3 | `conditionalFormat` is populated on `get_sheet(include='format')` cells for rule-coloured cells (community report says it can be null) | item 1 | colour feature for rule-driven cells infeasible; owner decision (BLOCKING) |
| A4 | `row_ids` with `include='format'` returns the same per-cell format data as the full-sheet call | Fetch design | enrichment returns blanks; probe should use `row_ids` form too (add to script if time) |
| A5 | Effective-scope design ("pilot output only on `SKIP_UPLOAD` runs until upload switch on") matches owner intent for D-15-03 | Upload gating | owner may want pilot rendering in prod runs with upload blocked; see OQ-2 |
| A6 | Allowlist names never contain commas; GF cell holds one name | GF lookup | multi-GF cells would be non-pilot (safe direction) |
| A7 | `General Foreman` / `Work Request #` column ids from CONTEXT are current | GF lookup | title verification on the response makes a wrong id fail-closed |

## Open Questions

1. **OQ-1 Exact `Foreman Notes` titles across the ~121 source sheets and intake sheets?** Unknown without token. Recommendation: probe lists titles containing "note"; plan carries a `checkpoint:human-verify`. **(RESOLVED: Live Probe Result, 2026-10-29 - both probed sheets title the column exactly `Foreman Notes`; exact-title synonym used, no extra variants.)**
2. **OQ-2 Upload switch semantics.** Recommend effective-scope design (production unchanged until `FOREMAN_NOTES_UPLOAD=1`; dry run = local `SKIP_UPLOAD=true`). Alternative: render pilot files in prod but suppress upload for pilot groups (hazards 7a/7b). Owner confirm; also whether a CI dry-run path (new `advanced_options` key) is wanted - that is a GitHub Actions change needing explicit approval, so default no. **(RESOLVED: Live Probe Result dispositions - effective-scope design adopted as an orchestrator technical decision, reported to the owner on 2026-10-29, owner did not object. Tightened in plan revision round 1: pilot rendering only when TEST_MODE is true with every pipeline_memory write flag off, or when FOREMAN_NOTES_UPLOAD=1; SKIP_UPLOAD alone keeps the scope off; a code guard blocks any pipeline_memory write during a dry-run pilot. No CI dry-run path and no YAML change. Confirmation point: the owner dry-run checkpoint in 15-07.)**
3. **OQ-3 Bulk `include=format` (as listed in CONTEXT canonical refs) vs lazy pilot-only enrichment (recommended).** Confirm owner accepts the deviation; rationale is payload/time-budget and non-pilot fetch immutability. **(RESOLVED: Live Probe Result dispositions - lazy pilot-only enrichment adopted as an orchestrator technical decision, reported to the owner on 2026-10-29, owner did not object. This is an explicit DEVIATION from CONTEXT's canonical-ref note to add `include=format` to the bulk fetch at `pipeline/fetch.py` ~234/~270/~580: the bulk fetch is left unchanged and colours are fetched per pilot group with `row_ids` chunks. Confirmation point: the owner dry-run checkpoint in 15-07.)**
4. **OQ-4 NOTES_FP present for a pilot group with all-blank notes?** Recommend yes (deterministic constant); flipping pilot membership then always changes the hash. **(RESOLVED: Live Probe Result dispositions - yes, deterministic constant; implemented in 15-02 Task 3.)**
5. **OQ-5 Column I width** (Claude's discretion): recommend 50, wrap, top alignment. **(RESOLVED: Live Probe Result dispositions - width 50, wrap, top alignment; implemented in 15-04.)**

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | all | yes | 3.11.15 | — |
| smartsheet-python-sdk | fetch/enrichment | yes | 4.3.0 | — |
| openpyxl | excel | yes | 3.1.5 | — |
| pytest | tests | yes | 9.0.3 | — |
| `SMARTSHEET_API_TOKEN` | live probe, local dry run | NO (not in env; `.env` not opened by policy) | — | owner runs probe + dry run; mark `[BLOCKING]` human-verify |
| Internet to `api.smartsheet.com/2.0/serverinfo` | palette drift test | yes (unauthenticated) | — | pinned tuple |
| `gh` | PR context | yes (PR #435 OPEN, base `master`, head `plan/phase-13`) | — | — |

**Missing with no fallback:** live probe of `conditionalFormat` (blocking for the colour half; notes half is unaffected and can proceed).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 (unittest-style classes common) |
| Config file | none (repo root `tests/`); 6-gate harness `scripts/run_6_gates.sh` |
| Quick run command | `python -m pytest tests/test_foreman_notes_*.py -q -x` |
| Full suite command | `bash scripts/run_6_gates.sh` (includes `python -m pytest tests/ -q`) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FN-01 | off/non-pilot cell + hash identity vs golden | unit | `pytest tests/test_foreman_notes_excel.py tests/test_foreman_notes_hash.py -x` | Wave 0 |
| FN-02/03 | allowlist + GF normalisation, fail-closed | unit | `pytest tests/test_foreman_notes_state.py -x` | Wave 0 |
| FN-04 | notes identical full vs delta | unit | `pytest tests/test_foreman_notes_hash.py::test_full_vs_delta_parity -x` | Wave 0 |
| FN-05/06 | column I, merges, TOTAL, print setup, footer untouched | unit | `pytest tests/test_foreman_notes_excel.py -x` | Wave 0 |
| FN-07/10 | descriptor parse, fail-closed, no colour-triggered regen | unit | `pytest tests/test_foreman_notes_styles.py -x` | Wave 0 |
| FN-08/09 | NOTES_FP, fingerprint, globals fp, AST coverage | unit | `pytest tests/test_foreman_notes_hash.py tests/test_row_state_group_hash_domain.py -x` | Wave 0 / exists |
| FN-11 | effective-scope matrix incl. SKIP_UPLOAD/TEST_MODE | unit | `pytest tests/test_foreman_notes_state.py -x` | Wave 0 |
| FN-12 | every variant renders column I | unit | `pytest tests/test_foreman_notes_excel.py -k variants -x` | Wave 0 |
| live | palette drift / conditionalFormat probe | manual/opt-in | `FN_PALETTE_LIVE=1 pytest tests/test_foreman_notes_styles.py -k live` | Wave 0 (opt-in) |

### Sampling Rate
- Per task commit: quick run command. Per wave merge: full harness. Phase gate: 6 gates green + owner dry-run review before upload switch.

### Wave 0 Gaps
- [ ] `tests/fixtures/foreman_notes/golden_off_cells.json` + golden digests - MUST be captured from the BASE commit before any edit
- [ ] the four `tests/test_foreman_notes_*.py` files
- [ ] new coverage test additions in `tests/test_row_state_group_hash_domain.py` (or a sibling file)
- [ ] `[BLOCKING]` human-verify: live probe (script above) and exact column titles (OQ-1)

## Security Domain

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2/V3 Authentication/Session | no | token only via env (existing) |
| V4 Access Control | partial | pilot predicate fail-closed; no new write surface |
| V5 Input Validation | yes | note sanitisation: `ILLEGAL_CHARACTERS_RE`, 32767 cap, forced string type (CWE-1236 CSV/formula injection) |
| V6 Cryptography | no | SHA-256 for digests (stdlib) |
| V8 Data Protection | yes | notes/GF names are PII-adjacent: never in Sentry events/logs (counts only); `SENTRY_ENABLE_LOGS` stays false |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Formula/DDE injection via note text | Tampering | `data_type='s'` + strip; test with `=1+1`, `+cmd`, `@SUM`, `-2+3` |
| GF-name spoof / ambiguous WR -> wrong file shape | Spoofing | ambiguity -> non-pilot; title verification of columns |
| Secret exposure in probe | Info disclosure | token never printed; probe prints descriptors only |
| Large note DoS (cell > 32767) | DoS | truncate |

## Sources

### Primary (HIGH confidence)
- Repo files read this session: `pipeline/{fetch,discovery,change_detection,memory_candidate,excel,upload,orchestrate,config}.py`, `tests/test_row_state_group_hash_domain.py`, `scripts/run_6_gates.sh`, `.github/workflows/weekly-excel-generation.yml`
- SDK 4.3.0 local introspection (`Cell`, `Sheets.get_sheet`, `Server.server_info`, `prepare_request` URL encoding)
- Live `GET https://api.smartsheet.com/2.0/serverinfo` (unauthenticated) 2026-10-29
- Context7 `/websites/developers_smartsheet_api` (cell formatting, Cell schema)

### Secondary (MEDIUM)
- https://developers.smartsheet.com/api/smartsheet/guides/advanced-topics/cell-formatting (table quoted; some inconsistent labels noted by the fetch)

### Tertiary (LOW)
- Community report that `conditionalFormat` can be null (from CONTEXT; unverified)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - nothing new
- Architecture/integration points: HIGH - every site read this session
- Colour (conditionalFormat) behaviour: LOW until probe
- Pitfalls: HIGH for hash/marker/parity (code-verified); MEDIUM for upload-switch intent (A5)

**Research date:** 2026-10-29
**Valid until:** 2026-11-28 (repo moves fast; re-check line numbers against PR #435 head before executing)

## Project Constraints (from CLAUDE.md)
- Production billing; additive, surgical changes only; facade stays thin (new behavior in an owning `pipeline/*` module).
- Never shorten change-detection key `(WR, week_ending, variant, foreman, dept, job)`; helper rows need both `helper_dept` and `helper_foreman`.
- Excel: `safe_merge_cells()` always; never write `oddFooter.right.text`.
- Never use the Smartsheet `@cell` formula in Python/API payloads.
- `PARALLEL_WORKERS` <= 8; rely on SDK 429 retries; paginate properly; token only via env; never guess column names (verify against `_validate_single_sheet()` mappings in `pipeline/discovery.py`).
- Keep the `advanced_options` `key:value,key:value` parser untouched; `TIME_BUDGET_MINUTES` (165) < `timeout-minutes` (180).
- Sentry: `SENTRY_ENABLE_LOGS` false; log counts not row/PII data.
- Validation: `pytest tests/ -v` must pass before push; `python -m py_compile generate_weekly_pdfs.py`; `bash scripts/run_6_gates.sh` after any module move; local dry run with `SMARTSHEET_API_TOKEN=` blank + `TEST_MODE=true SKIP_UPLOAD=true PYTHONUTF8=1`.
- Conventional Commits (subject <= 50 chars); PR sections Objective / Changes Made / Production Safety Check; append a `[YYYY-MM-DD HH:MM]` entry to `memory-bank/living-ledger.md`; update `docs/ai/architecture.md` after structural change; Phase 15 MERGES only after Phase 11 closes (D-15-13); branch stacked on PR #435.

## Live Probe Result (2026-10-29, orchestrator, READ-ONLY; token loaded in-process from .env, never printed)

Sheets: Intake Promax `3756603854507908` (2000 rows), Resiliency Promax Database 16 `2582148201533316` (1860 rows).
`get_sheet(include='format', column_ids=<mapped cols>)` — full sheet, no writes.

- **OQ-1 resolved:** both sheets title the column exactly `Foreman Notes`.
- **Conditional formatting IS returned — at ROW level, not cell level.** `Row.conditional_format`
  populated (2000/2000 rows on Intake; 947/1860 on DB 16). `Cell.conditional_format` was empty on
  every cell read (0 cells). The sheets' rules are "apply to entire row" rules.
- Row-level descriptors observed (background slot 9 only; no text colour, no bold):
  `',,,,,,,,,21,,,,,,,'` → bg `#FEFF00` (yellow); `',,,,,,,,,30,,,,,,,'` → bg `#40B14B` (green);
  `',,,,,,,,,28,,,,,,,'` → bg `#FF8D00` (orange); `None` → no colour (913 rows on DB 16).
- Static cell `format_` is alignment/number-format only (`',,,,,,2,,,,,,,,,,'`, `',,,,,,2,,,,,13,2,1,2,,'`);
  no static colours seen. `Row.format_` was None everywhere.
- `column_ids` + `include='format'` coexist (A4 partially resolved: column-filtered full-sheet call works).
- No non-blank `Foreman Notes` on these two sheets today (expected: pilot GFs' sheets will have them).

**Planning consequence (A2 resolved):** effective style for an Excel CU row, per slot (text 8, bg 9):
`cell.conditional_format` > `row.conditional_format` > `cell.format_` > `row.format_` > none.
In practice today: row-level background applied to every Smartsheet-sourced column (A–H) of that CU
row (Pricing H included, per D-15-10); text colour applied when a descriptor carries slot 8.
Fallback (none/unparseable) = today's BODY_FONT, no fill.

**Orchestrator dispositions of open questions (technical, consistent with CONTEXT):**
- OQ-2: adopt the effective-scope design — pilot rendering is active only on `SKIP_UPLOAD=true`
  (dry-run) runs until `FOREMAN_NOTES_UPLOAD=1`; production cron output unchanged until then. No
  GitHub Actions YAML change.
- OQ-3: adopt lazy pilot-only `include=format` enrichment (row_ids chunks); bulk fetch unchanged.
- OQ-4: yes — deterministic NOTES_FP constant for pilot groups with all-blank notes.
- OQ-5: column I width 50, wrap, top alignment.
