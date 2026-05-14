# Phase 1: Subcontractor Rate Logic Modification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or
> execution agents. Decisions are captured in `01-CONTEXT.md` — this log
> preserves the alternatives considered and the rationale for what wasn't
> chosen.

**Date:** 2026-05-14
**Phase:** 01-subcontractor-rate-logic-modification
**Areas discussed:** CSV delivery from XLSX (user-picked)
**Areas defaulted by Claude:** Variant naming + ordering; Primary file
fate on subcontractor sheets; Missing-CU WARNING + CSV column shape

---

## Gray Areas Presented

The user was offered four phase-specific gray areas (multi-select):

| Area | Description (abridged) | User selected |
|------|------------------------|---------------|
| CSV delivery from XLSX | Gitignored XLSX vs CI-visible CSV; commit script / Smartsheet attachment / OneDrive fetch / git-crypt | ✓ |
| Variant naming + ordering | `_AEPBillable` / `_ReducedSub` strings + position relative to `_Helper_<name>`; parser implications | Deferred to defaults |
| Primary file fate on subcontractor sheets | Coexistence of new variants with the existing "keep SmartSheet pricing" primary file | Deferred to defaults |
| Missing-CU WARNING + CSV column shape | Operator-facing log format + which columns ship to the on-disk CSV | Deferred to defaults |

User explicitly opted into the discussion-only-what-I-want model:
*"Anything you don't pick, I'll default per the intel + ledger and note
it as 'Claude's discretion' in DISCUSSION-LOG.md for you to review"* — and
that's what this section does.

---

## CSV delivery from XLSX (user-discussed)

### Turn 1 — Source flow

| Option | Description (abridged) | Selected |
|--------|-------------------------|----------|
| Operator script + commit CSV | `scripts/sync_subcontractor_rates.py` reads local XLSX, writes `data/subcontractor_rates.csv`, operator commits | |
| Smartsheet attachment fetch | Workflow downloads via Smartsheet API at startup | |
| OneDrive / Sharepoint fetch | Workflow pulls via Microsoft Graph API | |
| Encrypted commit (git-crypt) | Commit XLSX encrypted, key via GitHub secret | |
| **(Other — user-supplied)** | **User manually converted XLSX → CSV and placed at repo root** | **✓** |

**User's choice:** Other — *"i actually provided the same file but i just
converted it into a .csv format for readability i have attached it to the
codebase and here is the path: `C:\Users\juflores\dev\Generate-Weekly-PDFs-DSR-Resiliency\CU List - Corpus North & South.csv`"*

**Verified:**
- File exists at `CU List - Corpus North & South.csv` (738 KB, 4849
  lines including header, 4848 data rows)
- Not gitignored (only `*.xlsx` is excluded; CSV is repo-committable
  and CI can read it)
- Schema matches the XLSX exactly: 17 columns, same currency-formatted
  prices, same `N/A` hour placeholders for inactive CUs, same 1058
  zero-price placeholder rows
- Encoding tolerates `utf-8-sig` (BOM-safe) reading

**Notes:** User implicitly rejected automated workflow-side conversion
(Smartsheet / OneDrive / git-crypt) in favor of manual operator-managed
CSV commits. This matches the ledger convention from the retired
`NEW_RATES_CSV` / `OLD_RATES_CSV` (`decisions.md` 2026-04-24 14:30) —
operator owns rate updates, git history = audit trail. Locked as D-01.

### Turn 2 — CSV path

| Option | Description (abridged) | Selected |
|--------|-------------------------|----------|
| Keep at root, loader reads it there | `SUBCONTRACTOR_RATES_CSV` defaults to root path | |
| **Move to `data/subcontractor_rates.csv` (Recommended)** | Canonical snake_case path matching REQUIREMENTS.md SUB-04, mirrors retired CSV naming | **✓** |
| Keep at root + rename only | Rename to `subcontractor_rates.csv` at root, no `data/` subdir | |

**User's choice:** Move to `data/subcontractor_rates.csv` (Recommended).

**Notes:** Plan-phase will schedule the `git mv` as a discrete task.
Loader env var `SUBCONTRACTOR_RATES_CSV` defaults to the new path
(`data/subcontractor_rates.csv`). Locked as D-02 + D-03.

**Discussion satisfied** — CSV delivery topic is fully resolved (source,
location, format coercion strategy). No further turns needed.

---

## Claude's Discretion

### Variant naming + ordering

**Defaulted to:** Variant tokens `_AEPBillable` and `_ReducedSub`,
ordered as variant-first then helper-second
(`_AEPBillable_Helper_<name>` and `_ReducedSub_Helper_<name>`).

**Why this default:** REQUIREMENTS.md SUB-01, SUB-02, and SUB-05 already
specify these exact strings and this exact ordering. The user previously
authorized this naming in the handoff prompt: *"_AEPBillable (3%-increase
rates, what Linetec bills AEP) and _ReducedSub (13%-reduced rates...)"*.
This is more a confirmation than a discretionary call.

**Alternative considered, rejected:**
- Reverse ordering (`_Helper_<name>_AEPBillable`) — would require parser
  changes and complicate the existing variant marker detection at
  `generate_weekly_pdfs.py:667`. No operator-facing value.
- Shorter tokens (`_AEP` / `_Sub`) — less self-documenting on the target
  sheet's row attachment panel, and `_AEP` could collide with future
  AEP-specific variants. Rejected.

**Override mechanism:** the user can flip the variant strings in
plan-phase by editing CONTEXT.md D-08 / D-09 before `/gsd-plan-phase 1`
runs. Filename parser tests will then cover the new tokens.

### Primary file fate on subcontractor sheets

**Defaulted to:** The existing primary `WR_xxx_WeekEnding_<date>_<hash>.xlsx`
continues to generate for subcontractor sheets, unchanged.
`_AEPBillable` and `_ReducedSub` are **additive** files — 3 files per
qualifying subcontractor WR + week (primary, _AEPBillable when post-cutoff,
_ReducedSub always).

**Why this default:**
- REQUIREMENTS.md SUB-06 forbids the new variant logic from touching
  existing flows — replacing primary would be a "touching" change.
- The existing subcontractor pricing SPEC
  (`.github/instructions/subcontractor-pricing-folder-discovery.instructions.md`)
  is silent on whether the primary file should be replaced; "keep
  SmartSheet pricing as-is — no rate recalc" applies to whatever file
  carries that data, and currently that's the primary file.
- Additive is reversible — if operator workflow proves the primary
  file is redundant for subcontractor sheets, a future phase can
  consolidate. Replacing now would be hard to undo without code
  archaeology.

**Alternative considered, rejected:**
- `_ReducedSub` replaces primary on subcontractor sheets — 2 files per
  WR (cleaner output dir), but irreversible without resurfacing the
  primary code path. Rejected; flagged as a deferred idea in
  CONTEXT.md `<deferred>` so it's not lost.

### Missing-CU WARNING + CSV column shape

**Defaulted to:**
- Loader extracts 9 fields per row into the in-memory dict (`cu_code`,
  `cu_wbs`, `compatible_unit_group`, 6 priced columns). Old Rates
  columns (12–14) and Hours columns (6–8) are NOT loaded.
- On disk, the CSV keeps all 17 columns for human review.
- Missing-CU rows fall through to existing SmartSheet `Units Total
  Price` (safety net, never zero-out).
- One `WARNING`-level log per sheet at end of processing, format
  follows the 2026-04-21 22:35 ledger pattern: top-10 CU codes + count
  of any remainder.

**Why this default:**
- The "load only what code needs" rule is a hedge against accidental
  three-source-of-truth pricing (per `decisions.md` 2026-04-24 14:30
  rationale on the retired ORIG-folder recalc — having both Smartsheet
  AND a local rate file write to the same column creates a silent
  corruption trap).
- Missing-CU fallthrough preserves the existing safety net behavior
  identical to the retired CSV-side recalc loop.
- Per-sheet WARNING with top-N CU codes is the proven ledger pattern;
  no novelty needed.

**Override mechanism:** The user can request the loader to also load
old rates (audit logging in Sentry breadcrumbs) or to zero-out missing
CUs instead of falling through. Flag for plan-phase review.

### CSV staleness fingerprint scheme

**Defaulted to:** Module-level
`_SUBCONTRACTOR_RATES_FINGERPRINT` = SHA256 of
`json.dumps(rates_dict, sort_keys=True)` truncated to 16 hex chars;
logged in startup banner; embedded in `calculate_data_hash` for the
new variants only.

**Why this default:** Replaces the retired `_RATES_FINGERPRINT`
semantically but scoped to subcontractor variants. Keeps primary /
helper / vac_crew hashes byte-identical (success criterion 5
guarantee). SHA256 truncation matches the existing pattern in
`build_cu_to_group_mapping` fingerprint computation.

**Alternative considered, rejected:**
- File-modification-time fingerprint — fragile under git checkout
  workflows where mtimes don't reflect content changes
- CSV content hash directly (no JSON normalization) — order-of-rows
  sensitivity would cause spurious cache misses if the operator
  re-sorts the CSV

### Hash key shape

**Defaulted to:** Shared bucket — `meta_parts.append(f"VARIANT={variant}")`
accepts the four new variant strings (`aep_billable`, `reduced_sub`,
`aep_billable_helper`, `reduced_sub_helper`). NO new buckets.

**Why this default:** Matches the existing helper/vac_crew shared-bucket
pattern, minimizes `hash_history.json` churn, and per-row pricing
changes propagate naturally because the per-row hash captures price
cells. Splitting buckets would force a `DISCOVERY_CACHE_VERSION` bump
and double the hash_history footprint.

**Alternative considered, rejected:**
- Per-variant separate hash buckets — preserves regen-independence
  (regen only `_ReducedSub` without touching `_AEPBillable`). Rejected
  for current scope; flagged as a deferred idea in CONTEXT.md.

### `billing_audit.pipeline_run` schema payload

**Defaulted to:** `ALTER TABLE billing_audit.pipeline_run ADD COLUMN
IF NOT EXISTS variant TEXT;` — TEXT column, NULL on existing rows, no
CHECK constraint. Writer values:
`primary | helper | vac_crew | aep_billable | reduced_sub |
aep_billable_helper | reduced_sub_helper`.

**Why this default:** Idempotent DDL pattern matches the
`decisions.md` 2026-04-25 12:00 rule (P0 — every new Supabase column
defined in `schema.sql` in the same PR as the writer). TEXT (not enum)
matches the `feature_flag` / `pipeline_run` precedent — adding a new
variant string later doesn't require a migration. No CHECK constraint
gives forward compatibility room (operator can extend variant taxonomy
without DDL).

**Alternative considered, rejected:**
- Enum / CHECK constraint — would require ALTER TYPE / DROP+ADD
  CONSTRAINT to add new variant strings later. Trade-off rejected;
  loose typing is fine for an audit-only column.
- Separate `pipeline_run_variant` lookup table — over-engineering for
  what is essentially a single string per row.

### `DISCOVERY_CACHE_VERSION` bump

**Defaulted to:** NO bump.

**Why this default:** The discovery cache stores per-sheet column
mappings, and this phase doesn't change Smartsheet column mappings.
The fingerprint (D-20) handles CSV-staleness regen independently. If
plan-phase discovers that a column-mapping change IS needed (e.g.,
new column synonyms recognized), the bump happens in that plan.

**Override mechanism:** Plan-phase can override if column synonyms
need to be added.

---

## Deferred Ideas

(See CONTEXT.md `<deferred>` for the canonical list. Repeated here
for the discussion-log audit trail.)

- Split CLAUDE.md Living Ledger into per-entry ADR files under
  `memory-bank/adr/`
- Replace existing primary subcontractor file with `_ReducedSub`
  (currently additive)
- Per-variant separate hash buckets
- Auto-derived CSV from XLSX via Smartsheet attachment or OneDrive Graph
- `DISCOVERY_CACHE_VERSION` bump (deferred to plan-phase if needed)
- Encrypted commit of CSV (git-crypt) — only if visibility policy changes
- Phase 2 Railway → Render pre-migration ADR (already captured as
  ROADMAP.md Phase 2 DEFERRED)

---

*Discussion logged: 2026-05-14*
