# Project State — Generate-Weekly-PDFs-DSR-Resiliency

_Last updated: 2026-06-30 · **overwrite-in-place each session** (this is the
canonical "where the project stands" landing spot for the global Stop
write-back reminder). Keep it terse; link to history rather than duplicating it._

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

## History pointer
**Phase 09 — engine modularization (✅ COMPLETE & MERGED, PR #280 → `889ca2e`).**
10,476-line `generate_weekly_pdfs.py` → 13-module `pipeline/` package behind a
709-line thin facade, zero behavior change, 7 waves each 6-gate-verified. Full
wave-by-wave history in `memory-bank/living-ledger.md`.

_Paused alongside:_ **v1.2 — smartsheet-python-sdk 4.0.0 migration** (Phase 08).
SDK pinned `<4.0.0` in `requirements.txt` as a CI import hotfix; the breaking
4.0.0 migration is not yet executed. **Now unblocked** (Phase 09 merged) but
still touches the same engine — coordinate before starting.
