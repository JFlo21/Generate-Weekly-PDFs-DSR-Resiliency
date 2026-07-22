# Project State — Generate-Weekly-PDFs-DSR-Resiliency

_Last updated: 2026-07-22 · **overwrite-in-place each session** (this is the
canonical "where the project stands" landing spot for the global Stop
write-back reminder). Keep it terse; link to history rather than duplicating it._

## Latest work (2026-07-22) — Phase 08 SDK 4.3.0 migration EXECUTED (both plans)
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
4. **In flight at session close:** phase code-review agent (08-REVIEW.md)
   + gsd-verifier (08-VERIFICATION.md) then phase-complete roadmap update;
   security note: `/gsd:secure-phase 08` not yet run. Next after close:
   PR per D-06 (weekday daytime merge after green cron + one watched
   canary dispatch). Also: Juan's `.env` line-1 token surfaced in an editor
   selection into chat — rotation recommended.

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
