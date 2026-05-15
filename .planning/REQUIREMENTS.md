# Requirements: Generate-Weekly-PDFs-DSR-Resiliency

**Defined:** 2026-05-14
**Core Value:** The production Smartsheet → Excel → Smartsheet attachment
pipeline runs every 2 hours on weekdays and ships billing-grade Excel
reports without regression.

## v1 Requirements

Requirements for the v1.0 milestone. Each maps to exactly one roadmap
phase. v1.0 is structured around the **Subcontractor Rate Logic
Modification** (phase 1) and the **Railway → Render pre-migration ADR
deliverable** (phase 2). The migration execution itself and the
Artifact Explorer redesign are tracked as v1.1+ scope (kept here so
traceability is complete; they will be promoted in a subsequent
roadmap pass).

### Subcontractor Rate Logic

- [ ] **SUB-01**: A subcontractor work-request group whose
  `Snapshot Date >= 2026-04-12` produces an `_AEPBillable` variant
  Excel file priced via the 3%-increase column of
  `data/subcontractor_rates.csv` (one of `new_install_price`,
  `new_remove_price`, `new_transfer_price` keyed by CU code +
  work-type)
- [ ] **SUB-02**: Every subcontractor work-request group (regardless of
  `Snapshot Date`) produces a `_ReducedSub` variant Excel file priced
  via the 13%-reduced column of `data/subcontractor_rates.csv`
  (`reduced_install_price`, `reduced_remove_price`,
  `reduced_transfer_price`)
- [ ] **SUB-03**: `_AEPBillable` and `_ReducedSub` files for original-PPP
  groups attach to `TARGET_SHEET_ID=5723337641643908`; `_ReducedSub`
  files additionally attach to a new
  `SUBCONTRACTOR_PPP_SHEET_ID=8162920222379908` target sheet
  (configurable via env var, mirrors `TARGET_SHEET_ID` resolution
  pattern)
- [ ] **SUB-04**: `data/subcontractor_rates.csv` is the authoritative
  rate source — 9 numeric columns (reduced/original/new ×
  install/remove/transfer) keyed by CU code; load helper validates
  schema, logs missing CUs as WARNINGs with the exact CU code so
  operators can update the CSV before the next run
- [ ] **SUB-05**: When a foreman change occurs on a subcontractor WR
  (helper-foreman detected per existing `helper_dept`/`helper_foreman`
  rule), BOTH `_AEPBillable_Helper_<name>` AND `_ReducedSub_Helper_<name>`
  shadow files are generated for the prior foreman's claimed units —
  observable as two new files in `generated_docs/<week>/` per shadow
  event, each routed to its variant-appropriate target sheet
- [ ] **SUB-06**: No new subcontractor variant logic touches sheets in
  `ORIGINAL_CONTRACT_FOLDER_IDS` (`7644752003786628`, `8815193070299012`)
  or affects VAC crew variant detection / hashing / generation — the
  existing `is_subcontractor_sheet` / `_FOLDER_DISCOVERED_ORIG_IDS`
  flags gate every new code path
- [ ] **SUB-07**: `billing_audit.pipeline_run` attribution snapshot
  records the row's variant (`primary` / `helper` / `vac_crew` /
  `aep_billable` / `reduced_sub` / `aep_billable_helper` /
  `reduced_sub_helper`); schema change committed in
  `billing_audit/schema.sql` in the same PR as the writer change

### Migration Pre-Implementation

- [ ] **MIG-01**: A pre-migration ADR exists at
  `memory-bank/adr/0001-railway-to-render.md` (or equivalent path
  under `memory-bank/adr/`) capturing the locked decisions: Render
  Starter plan, in-memory LRU search index, v1 download = original
  `.xlsx` passthrough. Closes the
  `docs/railway-to-render-transition-plan.md` §5 Phase 0 step 3
  deliverable currently flagged as missing in
  `.planning/INGEST-CONFLICTS.md` INFO #8.

## v2 Requirements

Deferred to a later milestone. Tracked but not in the current
roadmap. Will be promoted by a future `gsd-new-project` /
`/gsd-plan-phase` cycle.

### Backend Migration Execution

- **REQ-railway-render-migration**: Disconnect Railway with zero
  user-visible downtime; host Express backend on Render Starter
  ($7/mo, Oregon, root `portal`, build `npm ci`, start
  `node server.js`, health `/health`, Node `>=20 <23`). Source:
  `docs/railway-to-render-transition-plan.md` §1, §9.
- **REQ-migration-staging-verification**: Stand up Render in
  parallel; every route in `portal/routes/api.js` returns expected
  shape on staging; session continuity verified
  (`linetec.sid` cross-origin); GitHub poller stays under 5k/hr;
  `pytest tests/` + `portal/tests/portal.test.js` pass against
  staging; `scripts/verify_post_migration.sh` exits zero. Source:
  same plan §5 Phases 0-3.
- **REQ-migration-decommission**: 48 h clean metrics post-cutover;
  Railway project deleted; `GITHUB_TOKEN` + `SESSION_SECRET`
  rotated; Railway-issued deploy keys revoked on GitHub;
  `memory-bank/activeContext.md` appended. Source: same plan §5
  Phase 5, §6.

### Artifact Explorer Redesign

- **REQ-artifact-explorer-v1**: Three-pane Artifact Explorer
  (filter bar / file tree / preview) in `portal-v2/`. xlsx preview
  loads <1 s warm / <3 s cold on Render Starter. Download button
  returns original `.xlsx`. Source: same plan §§7.1-7.5, §9.
- **REQ-excel-styled-renderer**: Hybrid Excel renderer —
  server-side `exceljs` styled HTML in sandboxed `<iframe srcdoc>`
  + `@tanstack/react-virtual` interactive table for sheets >2k
  rows. Preserves merged cells, column widths, row heights, frozen
  panes (`position: sticky`), number formats, fonts, fills,
  borders, alignment. Toggle persisted per-user in localStorage.
  Source: same plan §7.3.
- **REQ-cross-artifact-search**: Per-artifact filter bar (regex,
  type chips, size range, "has error logs") + `Cmd+K` palette
  (debounced 150 ms) returning `{run, artifact, file, sheet, cell,
  snippet}` hits. In-memory LRU index on Render; cache-busts on
  `artifact.expired === true`. No external search infra v1.
  Source: same plan §§7.5, 7.6.
- **REQ-backend-routes-for-explorer**: Five new Express routes —
  `GET /api/artifacts/:id/preview?file=&as=html`,
  `GET /api/artifacts/:id/preview?file=&as=json&page=&pageSize=`,
  `GET /api/artifacts/:id/search?q=`,
  `GET /api/search?q=&scope=runs|artifacts|contents`,
  `GET /api/runs/:id/jobs`. Existing `/download`, `/view`,
  `/files`, `/export?format=csv` preserved. Source: same plan §7.7.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Re-enabling CSV-side rate recalc on ORIG-folder sheets | Smartsheet now emits authoritative post-cutoff prices; sequential double-writes are a silent-corruption trap (`decisions.md` 2026-04-24 14:30) |
| Modifying the VAC crew variant workflow | Subcontractor Rate Logic Modification is folder-scoped; VAC crew must remain unchanged |
| Replacing `openpyxl` in `generate_weekly_pdfs.py` with `xlsxwriter` | Engine swap is a separate planning effort; mixing engines mid-pipeline is a corruption vector |
| Smartsheet `@cell` formulas in Python | UI-only construct, fails server-side |
| `PARALLEL_WORKERS > 8` | Smartsheet 300 req/min rate limit |
| `xlsxwriter` as a top-level `requirements.txt` dep | No consumer in the current pipeline; deferred to whichever new script first imports it |
| CSV per-sheet / all-sheets-zip / PDF / parsed-JSON downloads | Explicitly deferred from Artifact Explorer v1 (`requirements.md` deferred list, source `railway-to-render-transition-plan.md` §10) |
| Supabase-backed durable search index | In-memory LRU is the v1 design; Supabase search is a v2+ consideration |
| `RunCard` thumbnail previews | Explicitly deferred from v1 |
| Free-tier Render hosting | Spins down and breaks SSE + GitHub poller; Starter is the floor |

## Traceability

Which phases cover which requirements. Updated during roadmap
creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SUB-01 | Phase 1 | Implemented (pending operator verification) |
| SUB-02 | Phase 1 | Implemented (pending operator verification) |
| SUB-03 | Phase 1 | Implemented (pending operator verification) |
| SUB-04 | Phase 1 | Implemented (pending operator verification) |
| SUB-05 | Phase 1 | Implemented (pending operator verification) |
| SUB-06 | Phase 1 | Implemented (pending operator verification) |
| SUB-07 | Phase 1 | Implemented (pending operator verification) |
| MIG-01 | Phase 2 | Pending |

**Coverage:**
- v1 requirements: 8 total
- Mapped to phases: 8
- Unmapped: 0 ✓

v2 requirements (7 total — `REQ-railway-render-migration`,
`REQ-migration-staging-verification`, `REQ-migration-decommission`,
`REQ-artifact-explorer-v1`, `REQ-excel-styled-renderer`,
`REQ-cross-artifact-search`, `REQ-backend-routes-for-explorer`) are
acknowledged but not mapped — they ship in a subsequent milestone.

---
*Requirements defined: 2026-05-14*
*Last updated: 2026-05-14 after `gsd-new-project` bootstrap from
ingested intel*
