# Phase 15: Foreman Notes and Smartsheet color carry-over (GF pilot) - Context

**Gathered:** 2026-10-29
**Status:** Ready for planning (execution/merge gated — see D-15-13)

<domain>
## Phase Boundary

Weekly WR Excel files (the "ProMax" files the pipeline attaches to the pre-planned pricing
sheet, `TARGET_SHEET_ID` 5723337641643908) gain two things, for pilot general foremen only:

1. The row's `Foreman Notes` text on the same Excel row as its CU line.
2. The Smartsheet applied cell colors (conditional + static format) on every Excel CU-line
   column that is sourced from Smartsheet.

Applies to every output path (primary, helper, Helper #2, VAC crew, subcontractor variants).
Guarded by a scope switch so it can later apply to every Excel file. Non-pilot output, and all
output with the switch off, must stay unchanged (cell-level identical; hash byte-identical).

Not in scope: new Smartsheet columns or sheets, Smartsheet writes other than the existing
attachment upload, Excel output for other report types, changing header/TOTAL styling.

</domain>

<decisions>
## Implementation Decisions

### Guard rail (owner decisions carried from 2026-10-29 session)
- **D-15-01:** A scope switch with values `off` / `pilot` / `all`, default `pilot`, read via
  `os.getenv` in `pipeline/config.py` with the repo's env-var pattern. `off` = exact current
  behavior. `all` = every Excel file (future rollout). — **Reversibility:** reversible — env flag.
- **D-15-02:** Pilot allowlist is a separate setting (comma-separated names) holding the three
  pilot general foremen (aliases GF-1, GF-2, GF-3). Public-repo identifier rule (living ledger
  `[2026-08-27 21:10]` / `[2026-08-28 18:45]`): real names never appear in tracked files or PR
  text, so the allowlist has NO name default in code; it is supplied via env (local `.env` for
  dry runs; a GitHub Actions repository variable at rollout — amended 2026-10-29: a repository
  SECRET instead, so names are masked in public run logs). Empty allowlist = no pilot groups
  (fail-closed). Owner changes it without code edits.
- **D-15-03:** Dry run first. Uploading pilot-changed files to the pre-planned pricing sheet sits
  behind its own switch (off until the owner reviews dry-run output). Existing `SKIP_UPLOAD` /
  `TEST_MODE` semantics are unchanged.

### GF identification
- **D-15-04:** A WR's GF = the `General Foreman` column on the pre-planned pricing sheet
  (`TARGET_SHEET_ID`; verified 2026-10-29 via read-only `get_columns`: column `General Foreman`,
  formula-driven, returns `"NA"` on lookup miss), matched by `Work Request #`. `pipeline/upload.py`
  already reads this sheet's `Work Request #` column.
- **D-15-05:** Matching ignores case and collapses/trims whitespace. A WR whose GF is `NA`, blank,
  unmatched, or absent from the sheet — or any read failure of that sheet — is non-pilot and
  gets today's file unchanged (fail-closed to current behavior).

### Note placement
- **D-15-06:** Pilot files get a new column I header `Foreman Notes` in every day block; each CU
  row's note goes in column I of that same row (wrapped text, wider column I). Columns A–H keep
  their positions and meanings (Pricing stays H; G "N/A" untouched). Pilot day-header merge
  becomes A:I and the TOTAL row fills I red; all merges via `safe_merge_cells()`.
- **D-15-07:** Pilot files get landscape fit-to-page-width print setup (pilot-only) so the wider
  sheet prints on one page width. Never write `oddFooter.right.text`.
- **D-15-08:** Note source = the existing `Foreman Notes` column on the Resiliency ProMax database
  sheets (primary + helper foreman folders) and the intake sheets. Sheets without the column
  are fine (note blank). The column must be added to the `pipeline/discovery.py` synonym mapping
  so `column_ids` fetch filtering includes it.

### Styling
- **D-15-09:** Copy background fill + font (text) color only. No bold/italic/underline/
  strikethrough (strikethrough on a billing line can read as "voided").
- **D-15-10:** Effective style per cell: `conditionalFormat` slot when present, else static
  `format` slot. Each Excel column takes its own source cell's color: Pole #, CU, Work Type,
  CU Description, UOM, Quantity, and Pricing (from the `Units Total Price` cell). Headers, day
  headers and TOTAL rows keep `RED_FILL`. Any parse error / unknown palette index / empty
  descriptor → today's plain `BODY_FONT`, no fill (fail-closed).

### Change detection / re-send
- **D-15-11:** A notes-only edit regenerates and re-uploads the pilot file. Implement as a
  pilot-gated meta token (pattern: `SUB_RATES_FP` in `pipeline/change_detection.py`), NOT by
  adding fields to `_extended_row_fields` (that would change every group's hash). The same
  pilot predicate must fold the raw notes column into `pipeline/memory_candidate.py`
  `row_group_hash_fingerprint` / `GROUP_DERIVATION_KEYS` so Phase 11 shadow parity holds
  (G-11-37 lesson). — **Reversibility:** costly — hash/fingerprint change triggers one
  regeneration of every pilot group when enabled and again on a pilot→all flip.
- **D-15-12:** Color-only changes do NOT trigger regeneration (rule-driven colors change without
  edits and are invisible to incremental delta reads). Colors refresh whenever the file
  regenerates for any reason. Turning the pilot on re-sends every pilot GF file once.

### Sequencing
- **D-15-13:** Owner (2026-10-29): Phase 15 is the next feature after Phase 11. Planning and
  coding may proceed in parallel on a branch off master; Phase 15 MERGES only after the 11-15
  live parity reading closes Phase 11.

### Claude's Discretion
- Env-var names, module placement (new `pipeline/foreman_notes.py` or similar owning module per
  `.claude/rules/python-module-architecture.md`; facade stays thin), palette caching strategy,
  column I width, test layout.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Guardrails
- `CLAUDE.md` — production safety, change-detection key, `safe_merge_cells`, footer, `@cell`, API limits
- `.claude/rules/python-module-architecture.md` — owning-module rule, 6-gate harness
- `.claude/rules/smartsheet-python-optimization.md` — fetch + attachment rules
- `memory-bank/living-ledger.md` — grep `[2026-10-29 15:10]` (G-11-37) and Helper #2 entries

### Code integration points
- `pipeline/excel.py` — `generate_excel` (152), page setup (493-499), `write_day_block` (~698-788), column widths (839)
- `pipeline/fetch.py` — `get_sheet` calls with `column_ids` at ~234-240, ~270-276, ~580-585 (add `include=format`)
- `pipeline/discovery.py` — synonym mapping (~616) for `Foreman Notes`
- `pipeline/change_detection.py` — `_extended_row_fields` (48-97), meta_parts / `SUB_RATES_FP` (465-500)
- `pipeline/memory_candidate.py` — `GROUP_DERIVATION_KEYS` (48-70), `row_group_hash_fingerprint` (102-132)
- `pipeline/upload.py` — target-sheet `Work Request #` read (~75-84)
- `pipeline/config.py` — `TARGET_SHEET_ID` (75), env-flag patterns

### External API
- https://developers.smartsheet.com/api/smartsheet/guides/advanced-topics/cell-formatting — 17-slot format descriptor (text color slot 8, background slot 9)
- https://developers.smartsheet.com/api/smartsheet/openapi/serverinfo — `formats.color` palette (resolve live or pinned copy with drift test; doc examples are stale)
- SDK 4.3.0 (`requirements.txt`): `Cell.conditional_format`, `Cell.format_`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `safe_merge_cells()`, `RED_FILL`, `BODY_FONT` in `pipeline/excel.py`
- `__resolved_price` row-dict stash pattern — same path to carry note text and resolved styles into `write_day_block`
- `SUB_RATES_FP` gated meta token — template for a pilot-only `NOTES_FP`

### Established Patterns
- Column synonyms resolved in discovery; fetch filters by `column_ids`
- Raw columns only in Phase 11 fingerprint (delta path attaches no derived `__*` keys)

### Integration Points
- Fetch (format include) → row dict (note + style descriptors) → grouping (unchanged key) → hash (gated token) → excel (pilot column I + styles) → upload (own switch)

</code_context>

<specifics>
## Specific Ideas

- Research task #1 (before building): read-only probe of one Resiliency ProMax database sheet
  with `include=format` + `column_ids` to confirm `conditionalFormat` is actually returned
  (a community report says it can come back null). If it is not returned, stop and bring
  options back to the owner.
- Tests: switch `off` and non-pilot groups produce cell-level identical workbooks and identical
  hashes vs today; pilot note lands on its CU row; merges safe; notes digest identical across
  full-read and delta-read paths; style fail-closed on bad descriptors.

</specifics>

<deferred>
## Deferred Ideas

- Color-driven re-send (would need delta-visible color signals) — revisit after Phase 11 flag flip.
- Bold/italic/strikethrough carry-over — only if operators use them as status signals.
- GF alias list (alternate spellings) — add if a pilot GF is missed due to spelling.

### Reviewed Todos (not folded)
- `2026-10-29-inc02-incremental-globals-fallback-trigger.md` — Phase 11 scope (keyword match only).
- `2026-08-25-harden-check-mypy-delta-followups.md` — scripts/Gate 4 scope (keyword match only).

</deferred>
