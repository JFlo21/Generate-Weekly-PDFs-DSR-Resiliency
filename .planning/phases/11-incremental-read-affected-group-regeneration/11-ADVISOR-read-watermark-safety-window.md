# Phase 11 advisor research — Read watermark & safety window

> Output of a `gsd-advisor-researcher` (Sonnet, calibration `full_maturity`) dispatched during
> `/gsd-discuss-phase 11` on 2026-08-26 05:38Z. **Not a decision.** Preserved across the pause so
> the resumed discussion can present it without re-running the research. Juan has not picked yet.

**Verified against installed `smartsheet-python-sdk==4.3.0`:** `Sheets.get_sheet` maps
`if_version_after` → query param `ifVersionAfter` (int) and `rows_modified_since` →
`rowsModifiedSince` (ISO-8601). Official docs: if the version is still current, an abbreviated Sheet
with only `version` is returned; otherwise the complete Sheet. `scripts/mem04_experiment.py` already
exercises exactly this pair (abbreviated detection = `"rows" not in response`; `.version` present
either way). Documented API gap (community thread): `rowsModifiedSince` does **not** surface
deletions — which is why INC-03 scopes deletion/formula-only reconciliation to the weekly deep run.

| Option | Pros | Cons | Complexity | Recommendation |
|--------|------|------|------------|----------------|
| **Fixed 15-min SAFETY_WINDOW overlap, capture-time watermark** — read `rows_modified_since = last_read_at − 15 min`; persist `last_read_at` = timestamp captured immediately *before* issuing the read (NOT lagged by the window again at persist time, unlike the design-spec draft's `now − SAFETY_WINDOW`) | Matches the pattern already fixture-proven by MEM-04 (PASS with and without overlap); zero schema change — `sheet_registry.last_sheet_version` / `last_read_at` exist; server-side content-hash upsert makes any re-read of seen rows a free no-op, so overlap costs ~nothing against a 2 h cadence | A missed/delayed run (> 15 min beyond the prior cadence) can still lose rows unless the missed-run FULL-read trigger is wired in the same change — the window alone does not self-heal schedule gaps | No new tables; ~1 helper + 1 env var (`SAFETY_WINDOW_MINUTES`). Risk: watermark double-subtract bug if persist-time also lags by the window (compounds overlap run-over-run) | **Recommended default**, provided the "previous run failed" and "new sheet" FULL triggers ship in the same change |
| **Self-scaling one-interval overlap** — window = `max(floor, elapsed since last successful run × margin)`, capped (e.g. 6 h) beyond which a FULL read fires | Self-heals delayed/skipped runs, the weekend cadence, and manual reruns with one mechanism | Harder to reason about/test (window varies per run); couples watermark logic to a `run_ledger` "last successful run" query; a bad cap silently reads too little or too much | More branches/tests than a constant. Risk: cap miscalibration masks a real gap as "normal" | Only if the cadence is expected to change or operators rerun often — unnecessary here since D-07 locks the cadence |
| **Version-gated + full-sheet read on change; `modifiedAt` audit-only** — `if_version_after` only to skip unchanged sheets; on a version bump fetch the whole sheet (`level=2`, no `rows_modified_since`) | Eliminates the deleted-rows gap and any reliance on `modifiedAt` bumping for formula-only edits; simplest read-side logic | Forfeits the row-count savings INC-01/INC-04 exist to capture — a changed sheet (~1,776 rows avg) still costs a full parse; high-churn sheets converge back toward baseline | No SAFETY_WINDOW logic. Risk: none new, but no row-volume reduction on changed sheets | Fallback plan only if the INC-04 parity proof ever fails in production — not primary since MEM-04 passed |
| **Exact watermark, zero overlap** (`rows_modified_since = last_read_at`) — MEM-04's "T3b" no-overlap case | Simplest code; MEM-04 showed formula-only changes still visible without overlap | Zero margin for capture-vs-execution latency or Smartsheet write-visibility lag at the boundary — a silent row-loss class unacceptable for billing, to save a negligible number of rows | Trivial. Risk: unbounded tail risk with no cheap mitigation once shipped | **Not recommended** |

**Rationale (advisor):** Option 1 as the default, with the persistence rule made explicit: capture
`last_read_at` right before the `rows_modified_since` call, store it as-is (UTC-aware ISO-8601), and
apply the `SAFETY_WINDOW` subtraction only when constructing the query filter — the spec draft
persists `now − SAFETY_WINDOW` a second time, which compounds the overlap every run without adding
safety. Persist `last_sheet_version` from the response `.version` (present on abbreviated and full
responses) and `last_full_read_at` only when the completed read was `mode == 'full'`; no schema
change. The 15-min size guards capture-vs-execution latency and write-visibility lag (seconds), not
NTP skew (runners and Smartsheet are both UTC-accurate), so it has ample margin, and the server-side
hash compare makes accidental re-fetches a no-op.

**FULL-read escalation (all seven conditions, using data the schema already exposes):** no
`sheet_registry` row or `last_sheet_version IS NULL` → full read + insert; `column_mapping` drift
detected during validation → full read of that sheet + `column_mapping` refresh (never continue
against a stale mapping — misgrouping is a billing-integrity risk); Supabase/memory outage or
missing registry → whole run falls back to `mode='full'` on the existing code path (the one place
"fail-open toward Supabase" means doing *more* work); operator flags `RESET_HASH_HISTORY` /
`REGEN_WEEKS` / `RESET_WR_LIST` / `FORCE_GENERATION` → force full for the flagged scope, ignoring
the watermark entirely (trust-nothing-cached intent those flags already carry); Smartsheet 401/403
on a sheet → do not retry-as-full in a loop — isolate the sheet, alert via Sentry, leave
`last_read_at` / `last_sheet_version` unrefreshed so the registry rule forces a full read once access
returns; previous `run_ledger` row with `status != 'success'` or `finished_at IS NULL` → force
`mode='full'` for the whole run (a crashed run's partial watermark updates are not a clean baseline).

Files referenced (read-only): `pipeline_memory/schema.sql` (`sheet_registry` 53-80, `run_ledger`
212-241); `docs/superpowers/specs/2026-08-24-supabase-run-memory-design.md` 147-180;
`scripts/mem04_experiment.py` 313-360 (T2/T3a/T3b probes); `.planning/milestones/v1.4-REQUIREMENTS.md`
(INC-01..05); `.planning/STATE.md` (MEM-04 PASS); installed SDK `Sheets.get_sheet` source.
