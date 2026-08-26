# Phase 11 advisor research — Rollout, kill switch & retirement order

> Output of a `gsd-advisor-researcher` (Sonnet, calibration `full_maturity`) dispatched during
> `/gsd-discuss-phase 11` on 2026-08-26 05:38Z. **Not a decision.** Preserved across the pause so
> the resumed discussion can present it without re-running the research. Juan has not picked yet.
> Files it inspected: `.github/workflows/weekly-excel-generation.yml` (execution-type step
> 194-209, cache restore/save 159-192 and 771-793, env block), `pipeline/config.py`
> (`RUN_MEMORY_*`, `ATTACHMENT_PREFETCH_*`), `pipeline_memory/schema.sql` (`run_ledger.mode`
> CHECK), `pipeline_memory/writer.py`, `.planning/todos/pending/2026-08-25-run-memory-review-followups.md`.

| Option | Pros | Cons | Complexity | Recommendation |
|--------|------|------|------------|----------------|
| **A — Separate operator-gated pre-flight PR for `RUN_MEMORY_WRITE_ENABLED`; Phase 11 builds on a proven write path** | Isolates the write-path blast radius (WR-01 numeric-cast bug, WR-04 `sheets_changed`, IN-01 attachment-preservation proof) from the read/incremental blast radius — a regression is attributable to one PR; matches the repo's flag-family pattern (`SUPABASE_HASH_STORE_AUTHORITATIVE`, `SNAPSHOT_DRIFT_HOLD_ENABLED`): one-line master revert, proven in isolation before the next flag depends on it; the pending todo already scopes WR-01/WR-04/IN-01 as pre-flip fixes | Two GitHub Actions PRs (both protected-area, both need owner approval); risk of the write-flip PR stalling and blocking the phase | 2 workflow edits across 2 PRs; `pipeline_memory/writer.py` + `pipeline/config.py` touched in PR 1 only. Risk: sequencing drift if Phase 11 is planned assuming PR 1 landed | **Recommended** — keep the flip a separate operator-gated PR that Phase 11 *depends on*, gated on WR-01 fix + regression test, WR-04 fix, a `SKIP_UPLOAD` dry run plus one low-activity real-upload comparator run for IN-01 |
| **B — Bundle the write-flip into Phase 11's first plan/PR** | Fewer PRs, one coherent narrative and review pass; no half-shipped phase waiting on a separate PR | Combines two independently-risky changes (writer correctness + incremental-read correctness) in one protected-area diff; root-causing a production break is harder; contradicts the todo's own framing of WR-01/WR-03 as flag-flip preconditions | 1 larger PR touching the workflow, `writer.py`, `orchestrate.py`, `config.py`. Risk: mixed blast radius, one revert undoes both | Only if the owner prefers fewer review cycles over isolation |
| **C — Manual-dispatch-only opt-in first (via `advanced_options`), promote to scheduled crons after N clean manual runs** | Cheapest blast radius for the first live incremental run — no cron can pick it up until an explicit `workflow_dispatch`; reuses the battle-tested `key:value,key:value` parser (no new top-level input); a bad run affects one manual execution | Slower to reach steady-state coverage; needs an explicit, documented promotion criterion | 1 new `advanced_options` key (e.g. `run_memory_incremental:1`) + the `EXECUTION_TYPE` gate. Risk: forgotten manual override; informal promotion criterion | If the owner wants the very first incremental run to be a deliberate, single, observable event |
| **D — Frequent-only cron scope; silent-but-logged fallback via `run_ledger.mode`; INC-05 retirement as its own follow-up PR gated on INC-04's ≥5-run parity** | Narrowest cron surface (`production_frequent` weekdays only); `weekend_maintenance` and `weekly_comprehensive` stay full (D-07) and act as a standing full-mode safety net; fallback visibility reuses `run_ledger.mode` (`CHECK (mode IN ('incremental','full','targeted'))`) — no touch to the frozen 21-key `run_summary.json` (Gate 6); retirement PR keeps `hash_history.json`, `discovery_cache.json`, `billing_audit_frozen_rows.json`, the two attachment-prefetch budgets and the three `actions/cache/save@v4 if: always()` steps as a live rollback path through the burn-in | Slowest path to full coverage; INC-05 cannot land same-phase | Small `EXECUTION_TYPE`-keyed conditional in the workflow + `orchestrate.py`; later retirement PR removes 3 cache steps + 2 config constants + prefetch code. Risk: two protected-area PRs; `run_ledger.mode` must be trustworthy before anything alerts on it | **Recommended, pairs with A** |

**Rationale (advisor):** Treat the `RUN_MEMORY_WRITE_ENABLED` flip as a separate, operator-gated PR
that Phase 11 depends on — the todo already frames WR-01 (decorated numerics fail the NUMERIC cast
and fail-open drops whole 500-row chunks) and WR-04 as literal preconditions, and IN-01 needs an
upload-enabled control run only a dedicated dry-run PR can stage. Once `pipeline_memory` is
populated in production, `RUN_MEMORY_INCREMENTAL_ENABLED` defaults OFF and starts scoped to
`production_frequent` only (weekend + Monday deep run stay full per D-07, no cron/timeout change),
giving a standing full-mode safety net during the INC-04 parity window. Automatic fallback to full
(memory outage, missing registry, previous `run_ledger` row `status IN ('failed','running')`, any
`REGEN_WEEKS`/`RESET_*` flag) stays out of the frozen `run_summary.json` and is recorded in
`run_ledger.mode`. INC-05 retirement lands as its own PR strictly after parity — the
`actions/cache/save@v4 if: always()` steps exist precisely so a failed run keeps cache state, which
is the rollback property to preserve until incremental mode has proven itself.
