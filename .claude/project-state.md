# Project State — Generate-Weekly-PDFs-DSR-Resiliency

_Last updated: 2026-06-26 · **overwrite-in-place each session** (this is the
canonical "where the project stands" landing spot for the global Stop
write-back reminder). Keep it terse; link to history rather than duplicating it._

## Current milestone
**v1.3 — Engine Modularization & Hygiene** (Phase 09, **✅ COMPLETE — 7/7 waves done**).
Split the 10,476-line `generate_weekly_pdfs.py` into a 13-module `pipeline/` package
behind a **709-line thin facade**, zero behavior change, all 7 waves independently
6-gate-verified. Next: `/gsd-verify-work 09` → PR / milestone close; the ultimate proof
is the next 2h production cron running green on the package structure.
_Paused alongside:_ **v1.2 — smartsheet-python-sdk 4.0.0 migration** (Phase 08).
SDK pinned `<4.0.0` in `requirements.txt` as a CI import hotfix; the breaking
4.0.0 migration is not yet executed. **Phase 08 must NOT run concurrently with
Phase 09 — same file.**

## Active phase
**Phase 09 — engine-modularization-pipeline-package-split** (GSD, **EXECUTING ◆**). **7 plans /
7 waves** (leaf-first sequential chain 09-00→09-06). Running on `chore/claudeos-project-wiring`,
**sequential / no-worktree, Opus executors, wave-by-wave** (independent `run_6_gates.sh` +
human go between every wave).
- **Wave 0 (09-00) ✓ COMPLETE & verified.** 6-gate validation oracle built + frozen baselines
  + `pipeline/` scaffold; engine byte-for-byte unchanged since D-06. Commits
  `6266c17`/`3eb7018`/`f5df714`/`5c116c8`. Independent `run_6_gates.sh` = exit 0 (G1 177 names ·
  G2 105 facade names · G3 1088 pytest · G4 mypy 56→56 · G5 py_compile · G6 21-key run_summary).
- **Wave 1 (09-01) ✓ COMPLETE & verified.** config / utils / observability → `pipeline/`; gates
  green (177 names / 105 facade / 1091 pytest). PII `before_send_log` sanitizer + `init_sentry()`
  idempotency now test-guarded (added `test_sentry_log_sanitizer.py` + `test_sentry_init_idempotency.py`).
  Commits `cefb0c5`→`3deb5c0`.
- **Wave 2 (09-02) ✓ COMPLETE & verified.** pricing + change_detection → `pipeline/`; RATE_RECALC
  guard + change-detection key byte-for-byte. **D-06 closed:** `globals().get()` → explicit
  `billing_audit_writer` kwarg, facade `main()` injects writer immediately. Commits `deb1443`→`ac40297`.
  **+ Post-review HIGH fix** (silent-failure-hunter): the relocation left `_billing_audit_writer`
  unbound on `billing_audit` import failure → would crash prod; fixed (`baa9374`) + RED→GREEN
  regression test (`28509b4`, fills an oracle blind spot). Gate 3 = 1093.
- **Wave 3 (09-03) ✓ COMPLETE & verified.** Relocated `discover_source_sheets` → `pipeline/discovery.py`
  (664 ln) + the 795-line `get_all_source_rows` (owner of `_RATES_FINGERPRINT`) → `pipeline/fetch.py`
  (876 ln); the 4 runtime-rebound globals served via PEP-562 `__getattr__` live-proxy (D-01, no static
  bind — AST-confirmed). Both mandatory injections landed & verified: (1) `logging.warning` on the
  `_RATES_FINGERPRINT` `''` fallback (carry-forward closed); (2) `# type: ignore[import-not-found]`
  removed (noqa kept). Commits `84bc734`→`ec9dbfe`. **Independent `run_6_gates.sh` = exit 0**
  (177 · 105 · **1101 pytest** +130 subtests · mypy 56→56 · py_compile · 21-key run_summary). Two
  out-of-scope test files repointed grep-guards to the relocated source (legit, not weakening).
  **⏸ STOPPED for human go before Wave 4.**
  - **W3 pre-flight hygiene (DONE, 3 commits, gates GREEN @ 1095 pytest):** committed two orphaned
    correct edits found uncommitted in "verified" W1/W2 code, plus a regression test —
    `3efdc65` RED → `c23659a` `fix(09-01)` de-indent the `_cfg` import in `_set_sentry_session_tags`
    (Wave-1 relocation `0a945b7` mis-indented it UNDER `if not SENTRY_DSN: return` → unreachable →
    `UnboundLocalError` on the Sentry-CONFIGURED prod path, shielded by the facade call-site `try`,
    so session tags silently never applied; Gate 3 missed it — every prior Sentry test forces
    `SENTRY_DSN` empty). `3ba74b1` `chore(09-02)` type-ignore the not-yet-created `pipeline.fetch`.
    New test `tests/test_sentry_session_tags.py` closes that oracle blind spot.
- **Wave 4 (09-04) ✓ COMPLETE & verified.** grouping + excel → `pipeline/`: `group_source_rows`
  (1145 ln, highest-fan-in transform) + `validate_group_totals` → `grouping.py` (1225 ln); `safe_merge_cells`
  + `generate_excel` (627 ln) + 2 variant-suffix helpers → `excel.py` (786 ln). Facade 6613→4745 ln, re-exports
  all 6. Billing guards byte-for-byte: `(WR,week,variant,foreman,dept,job)` key, helper dual-checkbox exclusion,
  Job# synonyms; excel openpyxl-only (safe_merge_cells sole merge path, 0 `oddFooter.right.text` writes, no
  xlsxwriter). Discovery live-proxy globals read via `_discovery.NAME` (3-site, **W3→W4 carry-forward CLOSED**).
  Commits `a2827da`→`1820255`. **Independent `run_6_gates.sh` = exit 0** (177 · 105 · **1101 pytest** +130
  subtests · mypy 56→56 · py_compile · 21-key run_summary) + `excel-output-verifier` re-confirmed all 4 billing
  guards (no blocking findings). Deviation (behavior-preserving): config-name reads use the proven W3
  facade-prelude (suite rebinds RES_GROUPING_MODE / `*_CLAIM_ATTRIBUTION_ENABLED` / TEST_MODE / … on the
  facade), function bodies byte-for-byte. ✓ Human go given; Wave 5 executed.
- **Wave 5 (09-05) ✓ COMPLETE & verified.** cleanup + upload + attribution → `pipeline/` as THREE
  separate modules (D-02): `cleanup.py` (5 fns, 631 ln), `upload.py` (3 fns, 347 ln), `attribution.py`
  (17 symbols: 3 wr-scope builders + 4 hash-prune runners + `run_claimer_remediation` + 2 row-cache I/O
  + 4 `*_HASH_PRUNE_VERSION` + 2 row-cache consts + `_SUBCONTRACTOR_SCOPE_VARIANTS`, 819 ln). Facade
  4745→3190 ln, re-exports all 25. Billing guards byte-for-byte: delete-old-then-upload ORDER stays in
  the facade `_upload_one` worker (delete L2484→attach L2499); `@cell`=0/0/0; `PARALLEL_WORKERS≤8`; PII
  aggregate-only; `REMEDIATE_CLAIMERS`-OFF/`DRY_RUN`-ON defaults. Per-module empirical facade-read preludes
  (cleanup 3, upload 2 incl. facade-resident `SUBCONTRACTOR_PPP_SHEET_ID`, attribution 5); cleanup needed
  NO discovery live-proxy (AST: zero refs). Executed via background workflow (3 sequential `coder`
  relocation agents + abort-on-regression guard + parallel adversarial verify). Commits `8992725`→`8a81de9`.
  **Independent `run_6_gates.sh` = exit 0** (177 · 105 · **1101 pytest** +130 subtests · mypy 56→56 ·
  py_compile · 21-key run_summary). Adversarial verify: silent-failure PASS, PII PASS, billing-invariant
  CONCERN dispositioned (facade-read prelude + deferred circular import = locked W2-W4 pattern,
  behaviour-neutral; no code change). **⏸ STOPPED for human go before Wave 6.**
- **Wave 6 (09-06) ✓ COMPLETE & verified — PHASE 09 DONE.** `main()` (~2380 ln, un-decomposed D-05) + 2
  testmode helpers → `pipeline/orchestrate.py` (2748 ln); facade 3190 → **709 ln** FINAL thin form
  (D-04 import-time side-effects + 183-name re-exports + PEP-562 `__getattr__`/`__dir__` live-proxy +
  `__main__` → `pipeline.orchestrate.main`). **D-06 seam CLOSED:** `_resolve_unchanged_for_skip(...,
  billing_audit_writer=getattr(_gwp,'_billing_audit_writer',None))` at `orchestrate.py:1493` (live facade
  read; authoritative Supabase hash lookup NOT silently disabled). Commits `0fe0d83`→`e5061ed`.
  **Independent `run_6_gates.sh` = exit 0** (177 · 105 · **1101 pytest** +130 subtests · mypy 56→56 ·
  py_compile · 21-key run_summary) + **3 adversarial lenses ALL PASS** (architecture: no circular import,
  acyclic DAG, 709-ln facade justified/0 dead imports; billing-invariant: D-06 + change-key + @cell=0;
  silent-failure: error skeleton byte-identical). Facade 709 ln > ~300 target is JUSTIFIED (183 re-export
  surface, not debt). Workflow's FINAL StructuredOutput serialization failed but both commits had landed
  → recovered via ground-truth git + re-run gates + direct verify-agent dispatch (lesson: lean workflow
  schemas). Human checkpoint: Juan delegated "verify independently to close"; all close-out checks green.

Plans: `.planning/phases/09-…/09-0{0..6}-PLAN.md`; harness/how-to: `09-RESEARCH.md`; validation
map: `09-VALIDATION.md`; Wave summaries: `09-0N-SUMMARY.md`.

## Production health
`generate_weekly_pdfs.py` healthy on its GitHub Actions cron (≈ every 2h on
weekdays). Budgets: `TIME_BUDGET_MINUTES=165` / runner `timeout-minutes=180`.

## Active strands
- Claim attribution: Foundation A + Sub-projects B/C/D/E shipped.
- VAC-crew cross-sheet unit dedup (PR #274, merged).
- PDF export POC (per-day layout; prod PDF delivered for WR_90922617; WR 91029362 POC).

## Open blockers / risks
- SDK 4.0.0 breaking-change migration outstanding; `<4.0.0` pin must hold until done.
  **Phase 08 must NOT run concurrently with Phase 09 — same file.**
- **D-06 relocation hazard — RESOLVED in Wave 2** (explicit `billing_audit_writer` kwarg + immediate
  facade injection; post-review HIGH unbound-writer fix `baa9374`). Carry-forward: W6 must re-verify the
  injection survives the `main()`→`orchestrate.py` move.
- **Gate 6 is the weakest oracle gate** — `TEST_MODE` doesn't rewrite `run_summary.json`, so
  G6 is a structural snapshot + synthetic smoke, not full output equality. Flagged to
  strengthen in the W6 orchestrate plan.
- D-06 PR #279 left OPEN (intentional — fix is on-branch); merge later for mainline hygiene.
- ~13 uncommitted working files (planning docs, `poc/`, `.serena/`, debug notes) — executors
  use scoped commits; verified NOT swept into Wave-0 commits.

## Where history & decisions live
- `.planning/phases/09-…/09-CONTEXT.md` — **Phase 09 locked decisions** (read before planning/execute).
- `.planning/phases/09-…/09-RESEARCH.md` — verified symbol/module table, PEP-562 facade idiom, 6-gate harness, D-06 hazard.
- `.planning/phases/09-…/09-VALIDATION.md` — Nyquist validation strategy (harness gates + Wave-0 baselines).
- `memory-bank/living-ledger.md` — dated `[YYYY-MM-DD HH:MM]` ledger (history + decisions + incident root-causes).
- `.planning/STATE.md` — GSD front door (position, locked decisions, next step).
- `.remember/` — recent session continuity / handoff.
- Last commit at write: `e5061ed` (Wave 6 finalize thin facade; tip of W6 commits `0fe0d83`→`e5061ed`).
  **Phase 09 COMPLETE** — independently 6-gate-verified (exit 0) + 3-lens adversarial verify (all PASS),
  human checkpoint closed (Juan: "verify independently to close"). Docs commit follows.
