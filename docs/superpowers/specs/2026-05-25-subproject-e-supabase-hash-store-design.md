# Sub-project E — Supabase Hash-Store Migration + Filename Token Stripping

**Status:** Implemented — shipped dormant (PR #229, 2026-05-25). Default OFF
(`SUPABASE_HASH_STORE_AUTHORITATIVE=0`); flip after the operator applies
`billing_audit/schema.sql` + reloads the PostgREST schema cache.
**Date:** 2026-05-25
**Sequence:** The final piece of the universal-claim-attribution / change-detection
modernization arc (Foundation A → Phase 1.1 → B → C → D → **E**).

## Goal

Move the **durable** change-detection hash store from the Smartsheet-attachment
*filename* (and the ephemeral local `hash_history.json`) into **Supabase**, then
strip the `_<timestamp>` and `_<hash>` tokens from generated Excel filenames so
the canonical filename becomes:

```
WR_{wr}_WeekEnding_{MMDDYY}{variant_suffix}.xlsx
```

(e.g. `WR_90773033_WeekEnding_041226_User_Jane_Smith.xlsx`,
`WR_90773033_WeekEnding_041226_VacCrew_Bob.xlsx`, or bare
`WR_90773033_WeekEnding_041226.xlsx`).

## Why this is the last sub-project (the dependency)

Change detection today has **two** signals:

1. **Primary, ephemeral:** `hash_history.json`, keyed
   `history_key = f"{wr}|{week}|{variant}|{identifier}"`, value
   `{'hash': <16-char sha>, 'timestamp': ...}`. Read in `main()` at the
   `_hash_unchanged` gate (`generate_weekly_pdfs.py` ~L8507-8530:
   `_prev_history_entry.get('hash') == data_hash`). **Ephemeral in CI** — reset
   each run unless restored from the Actions cache; `RESET_HASH_HISTORY=true`
   forces a full regen.
2. **Durable backstop:** the **hash embedded in the attachment filename**.
   `delete_old_excel_attachments` (~L3114) calls
   `extract_data_hash_from_filename(att.name)` (~L2536 — returns the last
   `_`-split token iff it is exactly 16 chars) and, when it equals the current
   `data_hash`, **skips regeneration & upload** (~L3169-3171). This is the only
   change-detection signal that survives a CI `hash_history.json` loss, because
   it lives on the Smartsheet attachment itself.

`build_group_identity` (~L2568, the earliest-reserved-token parser) matches
attachment **identity** `(wr, week, variant, identifier)` and **discards** the
timestamp/hash — it is used for cleanup/identity, not for the hash comparison.

**Therefore:** stripping the hash token from filenames removes signal #2. That is
safe **only** once a durable replacement exists. Supabase is that replacement.
Hence E is sequenced last and "depends on Supabase being the change-detection
source of truth."

## Approved decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | Durable hash store granularity | **New per-group table** `billing_audit.group_content_hash` keyed `(wr, week_ending, variant, identifier)` — matches the per-variant skip granularity. (The existing `pipeline_run.content_hash` is only per-`(wr, week)` aggregate and would lose per-variant precision.) |
| 2 | Authority model | **Supabase authoritative + `hash_history.json` as a local fast cache; dual-write.** On a Supabase outage → fall back to the json cache → then to "regenerate" (the safe default). The filename hash is retired only after the Supabase store is proven. |
| 3 | Filename tokens | **Strip BOTH** `_<timestamp>` and `_<hash>` → deterministic canonical name. |
| 4 | Rollout | **Ship dormant.** Shadow-write the Supabase store from day one; keep the authoritative-read **and** filename-stripping behind a default-OFF kill switch; flip ON after the store is validated in production. (Mirrors Foundation A's dormant-ship pattern.) |

## Architecture

### New Supabase table (`billing_audit/schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS billing_audit.group_content_hash (
    wr            TEXT        NOT NULL,
    week_ending   DATE        NOT NULL,
    variant       TEXT        NOT NULL,
    identifier    TEXT        NOT NULL DEFAULT '',  -- '' for bare primary/vac
    content_hash  TEXT        NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (wr, week_ending, variant, identifier)
);
```

- Composite PK on the 4-tuple = the same key as `history_key` (minus the `|`
  joins). `identifier` defaults to `''` to match the bare-primary / legacy
  shape (consistent with the existing `'{wr}|{week}|{variant}|'` json keys).
- `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` blocks for partial-deploy safety
  (the established schema.sql convention). OPERATOR applies the DDL + reloads
  the PostgREST schema cache; until then, lookups return `unavailable` and the
  pipeline runs exactly as today (fail-safe).

### New writer/reader (`billing_audit/writer.py`)

Mirror the existing `emit_run_fingerprint` / `freeze_row` patterns (shared
`with_retry`, per-op circuit breaker, run-global kill switch, `get_client()`
returning `None` when disabled — so all calls become silent no-ops):

- `upsert_group_hash(wr, week_ending, variant, identifier, content_hash) -> None`
  — best-effort UPSERT (ON CONFLICT on the PK → update `content_hash`,
  `updated_at`). **Fail-safe:** catches its own errors, never raises.
- `lookup_group_hash(wr, week_ending, variant, identifier) -> (hash: str | None, status)`
  where `status ∈ {success, no_row, fetch_failure, unavailable, disabled}`.
  Shares the existing retry/circuit-breaker; a genuine outage returns
  `fetch_failure` (distinct from `no_row`).

`billing_audit/` is otherwise unchanged. No attribution changes.

### Engine changes (`generate_weekly_pdfs.py`)

Two env flags (the dormant-ship contract):

- **`SUPABASE_HASH_STORE_WRITE_ENABLED`** (default `'1'` once shipped) — gates
  the **shadow write** (`upsert_group_hash`). Writing is harmless even while
  the store is not yet authoritative, so it populates the durable store during
  the dormant period.
- **`SUPABASE_HASH_STORE_AUTHORITATIVE`** (default `'0'`) — the master switch.
  When ON: (a) the skip decision reads the Supabase group hash, (b) filenames
  are generated WITHOUT the timestamp/hash tokens, (c)
  `delete_old_excel_attachments` stops relying on `extract_data_hash_from_filename`.
  When OFF: byte-identical to today (json + filename-hash backstop).

Both pinned in `.github/workflows/weekly-excel-generation.yml` and documented in
`website/docs/reference/environment.md`.

### Data flow (AUTHORITATIVE = ON)

```
group → calculate_data_hash → data_hash
   ↓
skip gate:  supabase_hash = lookup_group_hash(wr,week,variant,identifier)
   • success + supabase_hash == data_hash AND attachment present → SKIP
   • fetch_failure / unavailable → fall back to hash_history.json cache
       • json hash == data_hash AND attachment present → SKIP
       • else → REGENERATE (safe default)
   • no_row (new group) → REGENERATE
   ↓ (on generate)
generate_excel → deterministic clean filename (no timestamp/hash)
   ↓
delete_old_excel_attachments → identity match via build_group_identity
   (pairs old token-named attachments with the new clean one) → delete old
   ↓
upload clean-named file
   ↓
dual-write: upsert_group_hash(...) (Supabase, durable) + hash_history[key]=… (json cache)
```

When AUTHORITATIVE = OFF: the skip gate is exactly today's
(`hash_history.json` + the filename-hash backstop in
`delete_old_excel_attachments`), and `upsert_group_hash` still runs as a shadow
write (if `SUPABASE_HASH_STORE_WRITE_ENABLED`).

### Filename parsing with clean names (`build_group_identity`)

`build_group_identity` already locates `WeekEnding` by `parts.index(...)` and
dispatches on the earliest reserved token in the post-`WeekEnding` tail (D's
hardening). With a clean name the tail shrinks from
`[MMDDYY, timestamp, <variant tokens>, hash16]` to `[MMDDYY, <variant tokens>]`,
and a bare primary becomes `[MMDDYY]` only. The parser must still return the
correct identity for every shape. **This is a key risk surface** — the plan
covers it with round-trip tests for clean names of every variant
(`primary` bare, `_User_<name>`, `_Helper_<name>`, `_VacCrew[_<name>]`,
`_ReducedSub[_User_/_Helper_<name>]`, `_AEPBillable[...]`).

`extract_data_hash_from_filename` returns `None` for a clean name (the last
token is not 16 chars) — harmless: the filename-hash skip path simply no longer
fires when AUTHORITATIVE is ON (Supabase replaces it). It is left in place for
the OFF path and for matching legacy token-named attachments.

## Migration (no bulk backfill)

Existing attachments carry `_<timestamp>_<hash>` in their names. **No migration
pass is needed:**

- `build_group_identity` ignores the trailing tokens, so an old
  `WR_X_WeekEnding_Y_<ts>_User_Z_<hash>.xlsx` and a new
  `WR_X_WeekEnding_Y_User_Z.xlsx` parse to the **same** identity. Cleanup
  (`delete_old_excel_attachments`) therefore pairs them.
- On the first AUTHORITATIVE run, `lookup_group_hash` returns `no_row` for every
  group (the store is freshly populated) → each group **regenerates once** →
  uploads the clean-named file → deletes the old token-named one by identity →
  upserts the Supabase hash. A **one-time regeneration wave** (wasteful but
  safe — the engine's established "regenerate when uncertain" principle). The
  dormant-write period (flag #1 ON before flag #2) **shrinks this wave to zero**
  if the store was populated before the cutover, because the shadow writes have
  already recorded current hashes.

## Error handling / fail-safe

- A Supabase outage MUST NOT break billing. `lookup_group_hash` returning
  `fetch_failure`/`unavailable` → fall back to the json cache → then regenerate.
  Reuses the existing run-global kill switch (PGRST106 schema-not-exposed,
  PGRST301/302 auth, SQLSTATE classes) so a misconfigured store degrades to
  "regenerate everything," never to "skip everything."
- `ATTACHMENT_REQUIRED_FOR_SKIP` is preserved: a matching hash still regenerates
  when the attachment is missing. So a stale Supabase hash can never suppress a
  needed file when no attachment exists.
- `upsert_group_hash` is best-effort and never raises (mirrors `freeze_row`).
- `SUPABASE_HASH_STORE_AUTHORITATIVE=0` is the one-line master revert.

## Testing

- **Schema:** the new table in `schema.sql` (the existing `schema.sql`-presence
  test pattern).
- **Writer:** `upsert_group_hash` / `lookup_group_hash` — success, `no_row`,
  `fetch_failure`, retry short-circuit on permanent errors, fail-safe (never
  raises), run-global-kill no-op. (Postgrest-gated like the existing
  `PostgrestErrorClassificationTests`.)
- **Skip gate (both flag states):** OFF → byte-identical to today; ON → Supabase
  authoritative, json fallback on outage, regenerate on `no_row`, regenerate
  when attachment missing.
- **Filenames:** ON → clean deterministic name for every variant; OFF →
  token-bearing name unchanged.
- **`build_group_identity` round-trip** for clean names of every variant shape
  (the key risk surface).
- **`delete_old_excel_attachments` / cleanup:** ON → does not rely on
  `extract_data_hash_from_filename`; old token-named attachments are still
  matched + deleted by identity; the new clean-named file is kept.
- **Migration:** first-AUTHORITATIVE-run one-time regen; dormant-write shrinks
  the wave to zero; `extract_data_hash_from_filename` returns `None` for clean
  names and that path is handled.
- Full suite stays green at every checkpoint; ROADMAP byte-identical-hash
  invariants for the OFF path preserved.

## Scope

**In scope:** the new Supabase table + writer/reader, the dual-write shadow
store, the authoritative-read skip gate, deterministic clean filenames,
`build_group_identity` clean-name support, the two kill switches, workflow pin,
docs, Living Ledger.

**Out of scope:**
- Removing `hash_history.json` entirely — it is retained as the local fast
  cache + offline fallback.
- Changing `calculate_data_hash` / `_compute_aggregated_content_hash` (the hash
  *content* is unchanged; only where it is *stored* changes).
- Any attribution / `lookup_attribution` change.
- Reusing/altering `pipeline_run.content_hash` (left as the per-run aggregate it
  is today).

## Risks

- **Mass-skip (dangerous, stale billing):** mitigated by fail-safe-to-regenerate,
  `ATTACHMENT_REQUIRED_FOR_SKIP`, and the dormant default-OFF rollout.
- **Mass-regen (wasteful, safe):** the one-time cutover wave; shrunk by the
  dormant-write period.
- **`build_group_identity` clean-name parse:** covered by round-trip tests for
  every variant shape before the flag flips.
