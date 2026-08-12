# Project State — Generate-Weekly-PDFs-DSR-Resiliency

_Last updated: 2026-08-12 · **overwrite-in-place each session** (this is the
canonical "where the project stands" landing spot for the global Stop
write-back reminder). Keep it terse; link to history rather than duplicating it._

## Latest work (2026-08-12) — SAA-DE-20 overbill root-caused (upstream data, not code) + Snapshot Date automation defect proven + quick task 260812-isx in flight
1. **Field-reported wrong pricing solved:** WR 91916464 / Point 27 /
   SAA-DE-20 showed 3 EA @ $341.04 (should be 3 × $56.84 = $170.52).
   Root cause: stale Smartsheet `Install Quantity` formula cell on
   "Resiliency Promax Database Backup 86" (Quantity edited 6→3 on
   2026-08-06, formula never recalculated). Contract rate and Python
   pipeline both verified CORRECT (primary variant is pass-through by
   design). Juan re-saved the row → now $170.52; next cron regenerates
   the WE 080926 file via hash change. Full evidence chain in
   `memory-bank/living-ledger.md` `[2026-08-12 13:40]`.
2. **Snapshot Date automation defect proven via cell history:** the
   per-sheet "record a date" automation uses a row-change trigger with
   "Units Completed? is checked" as a condition, so ANY edit (even
   same-value saves and bulk touches) re-stamps Snapshot Date to today
   → units jump billing weeks → audit errors. Fix is UI-side per sheet:
   field-scoped trigger ("Units Completed? changes to Checked") +
   "Snapshot Date is blank" write-once condition; fix the template
   sheet so backup copies inherit it. Recommendation delivered to Juan;
   NOT yet applied (his action).
3. **SESSION HANDOFF (2026-08-12 ~16:35 CDT) — resume points:**
   - **PR #329 Greptile fixes DONE + PUSHED** (`64d7249`/`e003124`/
     `8802e98`, suite 1230+130). Latent quirk untouched:
     risk_trend.json write no-ops on fresh generated_docs/.
   - **Quick task 260812-jqx EXECUTED (reviews in flight):** branch
     `feat/260812-jqx-snapshot-drift-audit` stacked on isx tip
     `3f7be82`. Commits: `8db2845` (planning docs), `55329a1` (drift
     detection, zero extra API calls: pipeline/snapshot_drift.py +
     billing_audit/snapshot_store.py + additive schema.sql + config +
     orchestrate seam), `c58a9bd` (cell-history classifier, 40-row cap
     ~2s pacing sub-budget), `0a68aeb` (hold-prior-week override +
     audit risk wiring + post-seam Sentry capture on holds), `0b5051a`
     (SUMMARY docs). Full suite **1257 passed + 132 subtests** (27 new
     tests), zero regressions; grouping/excel zero hunks; orchestrate
     2 hunks. Deviations: test-only budget-boundary flake fix;
     plan-check Sentry warning honored. Locked decisions held: hold
     gate default OFF, never hold manual edits, fail-open gating/
     fail-closed logging, no AUDIT_SHEET_ID mutation, DDL manual-apply.
     **Reviews DONE:** gsd-verifier 8/8 zero gaps; haiku rubric 10/10
     PASS; code review 2 Critical / 5 Warning / 7 Info → fix round
     `a56190c` (CR-01 upsert gated on fetch status — no baseline
     rebase on failed read), `81da106` (CR-02 null-prior-date holds
     skipped), `7a58c62` (WR-01 unparseable ts → unclassified;
     window env-tunable SNAPSHOT_DRIFT_UNITS_WINDOW_MINUTES default
     15; WR-04 test pacing zeroed). Suite **1262 + 132 subtests**
     (~13s). Deferred to PR follow-ups: WR-02 (bulk .in_ → RPC),
     WR-03 (RLS on new tables — Juan's DDL call), WR-05 (direct
     snapshot_store tests), info nits. Next: closeout docs commit,
     push + PR stacked on #329 (base = isx branch).
   - **A1/A4 VERIFIED LIVE (WINDOWS #1 closed):** read-only probes
     with Juan's token proved newest-first history + automation
     identity, captured the full Point 27 drift-and-revert chain, and
     CORRECTED the signature: automation batches stamps (legit writes
     up to 4m22s after the check → 15-min window), and Weekly
     Reference Logged Date is automation-WRITTEN (repair must revert
     it too). Ledger `[2026-08-12 17:05]`. Backup 86 scanned clean
     (no stamps ≥ 08-08). Note: Juan's `.env` names the token
     `SMARTSHEET_API_KEY`; the pipeline reads `SMARTSHEET_API_TOKEN`.
   - **Juan's own actions pending:** Smartsheet automation trigger fix
     in UI per living-ledger [2026-08-12 13:40] (field-scoped trigger
     + "Snapshot Date is blank" condition, per sheet + template) —
     REQUIRED before any snapshot-date repair sweep (writes would be
     re-stamped); run the remediation prompt with a Smartsheet-capable
     AI; review/merge PR #329; later: apply jqx DDL (2 blocks in
     billing_audit/schema.sql), verify A1/A4, enable hold gate after
     burn-in.
4. **Quick task 260812-isx (GSD quick) COMPLETE → PR #329 OPEN:**
   report-only rate-sanity audit check (Units Total Price vs expected
   New-Rates rate × Quantity via `_SUBCONTRACTOR_RATES`, kill-switch
   `RATE_SANITY_AUDIT_ENABLED`). Commits a7f5d77/2cb9897/ad3fa19 +
   docs c61bacb on branch `feat/260812-isx-rate-sanity-audit`
   (local master reset to origin/master — nothing pushed to main).
   Full suite 1228 passed + 130 subtests, 0 regressions; independent
   haiku-verifier PASS 8/8 (report-only, no hunks in pipeline/ or
   generate_weekly_pdfs.py). Next: Juan reviews/merges PR #329; apply
   the Snapshot Date automation UI fix per living-ledger
   `[2026-08-12 13:40]`.

## Previous work (2026-07-22) — Phase 08 SDK 4.3.0 migration EXECUTED (both plans)
1. **Phase 08 executed via `/gsd-execute-phase 08`** on branch
   `feat/phase-08-sdk-430-migration` (unpushed; no PR yet). Wave 1 (08-01,
   merge `6334531`): SDK 4.3.0 installed (env upgrade 3.9.0→4.3.0), dead
   27-line 3.x re-export shim removed from `generate_weekly_pdfs.py`, Gate 1
   baseline 178→177 (`_exc_name`), six gates ALL PASSED + full suite green.
   Wave 2 (08-02, merge `72f72ef`): `requirements.txt` pin lifted to exact
   `smartsheet-python-sdk==4.3.0`, Living Ledger entries added, D-06/D-07
   rollout+rollback runbooks captured in `08-02-SUMMARY.md`.
2. **D-05 live read-only probe: APPROVED by Juan** (bounded
   `SKIP_UPLOAD=true WR_FILTER=... MAX_GROUPS=5` run, real transport, 2,771
   groups validated, 5 Excel generated, zero SDK error-shape drift).
   **Finding:** `SKIP_UPLOAD=true` is NOT fully read-only — the
   delete-old-attachment step still ran (WR 89881161 weeks 072025/081725
   deleted; hash withheld → next weekday cron regenerates + re-uploads
   automatically; Juan chose wait-for-cron). Logged in phase
   `deferred-items.md` + Living Ledger; follow-up fix candidate: gate the
   delete on SKIP_UPLOAD too.
3. **Test hermeticity fix (`4aa19ff`):**
   `tests/test_entrypoint_no_double_import.py` now sets
   `SMARTSHEET_API_TOKEN=''` (was `pop()`) — the engine's `load_dotenv()`
   re-injected the token from Juan's new repo-root `.env`, flipping the
   banner test into a real multi-minute API fetch (180s timeout). Empty
   string survives dotenv (no override) and stays falsy → synthetic path.
   Post-merge gate green: 1164 passed + 130 subtests.
4. **Security gate CLEARED (2026-07-22 PM): `/gsd:secure-phase 08` run.**
   gsd-security-auditor verified 5/6 threats closed; the 6th (T-08-03,
   `SKIP_UPLOAD=true` still ran the attachment DELETE — materialized in
   the D-05 probe) was **fixed same-session, Juan-approved**: `dry_run`
   param on `delete_old_excel_attachments` /
   `cleanup_untracked_sheet_attachments` / `purge_existing_hashed_outputs`
   (`pipeline/cleanup.py`), wired `dry_run=SKIP_UPLOAD` at all 5 mutating
   call sites in `pipeline/orchestrate.py`. New invariant (ledger
   `[2026-07-22 14:37]`): SKIP_UPLOAD=true ⇒ zero Smartsheet mutations.
   TDD'd (`tests/test_skip_upload_delete_gating.py`, 7 tests; signature
   pin → v6); full suite **1171 passed + 130 subtests**. Threat register:
   `.planning/phases/08-*/08-SECURITY.md` (6/6 closed, threats_open: 0).
   Deferred item "SKIP_UPLOAD deletes prior attachments" marked RESOLVED.
5. **Nyquist gate CLEARED (2026-07-22 PM): `/gsd:validate-phase 08` run.**
   0 gaps; all 6 task commands re-run live and green (six gates PASSED —
   note: gate run took ~35 min because TEST_MODE + `.env` token does real
   reads; unset the token for local gate runs). New automated row
   08-SEC-T1 covers the SKIP_UPLOAD zero-mutation invariant. Commits
   `fa80b48` (validation), `8777246` (security docs), `442cb92` (fix).
6. **UAT COMPLETE (2026-07-22 ~16:30 CDT): `/gsd-verify-work 08` — 6/6
   passed, 0 issues** (commit `d78e7d5`). Full-UAT in
   `.planning/phases/08-*/08-UAT.md`; the old 1-test `08-HUMAN-UAT.md`
   closed (its attachment-loss check = Test 5, Juan-confirmed: WR
   89881161 self-healed via cron, WR 89708709/90093002 intact).
   `08-VERIFICATION.md` flipped `human_needed` → `passed` (the human
   gate it awaited was exactly Test 5). Roadmap/STATE/PROJECT transition
   had already run in the prior session — no re-transition.
7. **PR #286 OPEN** (branch pushed 2026-07-22 ~16:40 CDT). **Review fix
   shipped (quick task 260722-nst, ~17:35 CDT):** the 6th mutating call
   site — `run_claimer_remediation` in the isolated REMEDIATE_CLAIMERS
   branch (`pipeline/orchestrate.py` ~452) — now uses
   `dry_run=REMEDIATION_DRY_RUN or SKIP_UPLOAD` (test `458d7e5`, fix
   `60d0473`, docs `1b6ff9a`; TestRemediationGatesOnSkipUpload pins it;
   8/8 gating tests green; haiku-verifier PASS 4/4). SKIP_UPLOAD=true ⇒
   zero mutations now covers ALL 6 call sites. **Next per D-06:** merge
   in a weekday daytime window right after a green scheduled run, then
   fire ONE watched `workflow_dispatch` canary; then
   `/gsd-verify-work 09`. Also: Juan's `.env` line-1 token
   surfaced in an editor selection into chat — rotation recommended.
   Carry-forward WARNING for next phase's register: `TEST_MODE=true` with
   a real token still performs real Smartsheet reads.

## Current milestone
**v1.3.1 — Smartsheet API resilience & silent-failure hardening** (follow-up to
Phase 09, **✅ COMPLETE & MERGED, PR #281 → `8c51a3c`** on 2026-07-01 UTC).
Shipped from `fix/api-resilience-silent-failures` (cut fresh from
`origin/master`; branch deleted on merge). Three change areas, all TDD'd, all 6
gates green, PII scrubs dummy-transport-verified:
1. **Transient-retry resilience (the API errors).** New `pipeline/retry.py`
   `smartsheet_call_with_retry()` — retries the transients the SDK does NOT
   itself drive to success (generic `ApiError` **code 4000**, server timeout,
   rate limit, network drops), **bounded total sleep** so it can't blow
   `ATTACHMENT_PREFETCH_MAX_MINUTES` / `TIME_BUDGET_MINUTES`, **raises on
   exhaust**. Applied to the hot bare call sites (`fetch.py` per-sheet
   `get_sheet`, `discovery.py` folder browse + validate `get_sheet`); the
   discovery drop handler (was silent `return None`) now **escalates via
   `observability.sentry_capture_sheet_drop`** — a SANITIZED `capture_message`
   (NOT `capture_exception`, which would attach `include_local_variables`
   frames holding sampled billing-row PII) that TAGS the event
   `error_location=discovery_sheet_drop`; the global `before_send` hook
   (`_scrub_sheet_drop_frame_vars`) then strips every frame's data-bearing
   fields from that tagged event (a scope event-processor runs too early —
   `attach_stacktrace` appends the thread stacktrace after scope processors
   run) — so a dropped source sheet (= missing billing) is loud without
   exfiltrating row data. The 3 duplicate inline
   retry blocks in `orchestrate.py` (target/PPP attachment prefetch + upload)
   were **consolidated** into the helper. The upload worker is **behavior-
   preserving** vs the original inline loop (passes the prefetch cache every
   attempt). Codex flagged a retry idempotency gap in `SUPABASE_HASH_STORE_
   AUTHORITATIVE` clean-filename mode (ON in prod), but it is **not solvable by
   attachment inspection** (clean names carry no timestamp/hash, so a freshly
   committed file is indistinguishable from a stale same-identity one — both
   delete-then-reupload and preserve-on-identity are unsafe). Kept the safe
   baseline (benign self-healing duplicate on a rare retry, reconciled next
   run); the proper fix (upload-then-delete-by-attachment-age) changes the
   delete→upload guardrail and is **deferred to a dedicated PR**. Now-dead
   `time` / `ss_exc` imports removed.
2. **F1 (pre-existing deferred finding) fixed.** `grouping.py` sub-helper
   `no_history` fallback was silent — `resolve_claimer` returns
   `('use', current, 'current', 'no_history')` and the `action=='use'` branch
   zeroed the reason, so the per-WR WARNING never fired. One-line propagate-
   the-reason fix + reason-branched remediation (`no_history` vs `fetch_failure`
   vs `unavailable`); the 2 dead-path tests (mocked an impossible `action`)
   rewritten to the **real** `resolve_claimer` contract (red-first proven).
3. **Sentry PII hardening across all THREE data planes** (review-driven).
   Row PII (WR/week/foreman/dept/job/price) must never reach Sentry. Closed:
   (a) **event frames** → `before_send` `_scrub_sheet_drop_frame_vars` (a scope
   event-processor runs too early — `attach_stacktrace` appends thread frames
   after it); (b) **breadcrumb `message`** → `before_breadcrumb` drops any crumb
   whose message hits `_PII_LOG_MARKERS` (`LoggingIntegration(level=INFO)` turns
   every INFO/WARNING into a breadcrumb *unconditionally*, independent of the
   `SENTRY_ENABLE_LOGS` gate); (c) **breadcrumb `data`** → same hook strips
   row-identifier keys via the new `_PII_BREADCRUMB_DATA_KEYS` registry (manual
   crumbs carry PII in `data` under a benign message — e.g. the skip/regenerate
   crumbs). All three empirically verified with a real `sentry_sdk.Client` +
   dummy transport.

**Deferred (dedicated PR):** the retry-idempotency gap in
`SUPABASE_HASH_STORE_AUTHORITATIVE` clean-filename mode is **not solvable by
attachment inspection** (clean names carry no timestamp/hash, so a freshly
committed file is indistinguishable from a stale same-identity one). Kept the
safe behavior-preserving baseline (benign self-healing duplicate on a rare
retry, reconciled next run); the proper fix (upload-then-delete-by-attachment-
age) changes the delete→upload guardrail.

**Status:** MERGED. `run_6_gates.sh` exit 0 at merge (G1 178 names · G2 108
facade · **G3 1149 pytest** +130 subtests · G4 mypy 56→56 · G5 py_compile · G6
21-key TEST_MODE run). **All findings across 8 reviewer passes resolved**
(4 real Codex fixes: before_send frame scrub · attribution `unavailable`≠
`no_history` · breadcrumb message-scrub · breadcrumb data-scrub; 2 sys.path
test bootstraps; 3 Copilot doc-accuracy nits incl. the retry.py 4000-vs-
InternalServerError contract). 0 unresolved review threads; final Copilot
review generated no new comments. Production guardrails UNCHANGED (change-key,
delete→upload order, `@cell`=0, `PARALLEL_WORKERS≤8`, filename/attachment). See
`memory-bank/living-ledger.md` (newest entries) for the full what/why/rules.

## Active work
**🔧 WR 90968595 missing-rows bug: ROOT CAUSE CONFIRMED, fix in PR (2026-07-06).**
Not attribution/filtering — a crash-consistency bug in the Sub-project E hash
store: failed run 28752355941 (7/5, runner lost) upserted the new group hash
during emission but died before the upload phase, so under authoritative clean
filenames the skip gate deadlocks ("unchanged + attachment exists") and the 7/5
ProMax rows never publish; regen can't recover. Fix: `orchestrate.py` defers hash
upserts and flushes ONLY after the group's upload legs succeed (withhold on
error/dry-run → regenerate next run). 4 regression tests; suite 1153 passed +130
subtests. **Pending:** merge fix PR (stacked on #282) → one-time remediation
`workflow_dispatch` `advanced_options=regen_weeks:070526` → verify the 7/5 rows in
the regenerated file → archive debug session `wr-90968595-rows-not-pulled` +
apply the held second-brain write-back packet. Full rule: newest
`memory-bank/living-ledger.md` entry.

## History pointer
**Phase 09 — engine modularization (✅ COMPLETE & MERGED, PR #280 → `889ca2e`).**
10,476-line `generate_weekly_pdfs.py` → 13-module `pipeline/` package behind a
709-line thin facade, zero behavior change, 7 waves each 6-gate-verified. Full
wave-by-wave history in `memory-bank/living-ledger.md`.

_Paused alongside:_ **v1.2 — smartsheet-python-sdk 4.0.0 migration** (Phase 08).
SDK pinned `<4.0.0` in `requirements.txt` as a CI import hotfix; the breaking
4.0.0 migration is not yet executed. **Now unblocked** (Phase 09 merged) but
still touches the same engine — coordinate before starting.
