# Changelog Context

> **Canonical change ledger: [`memory-bank/living-ledger.md`](../memory-bank/living-ledger.md).**
> Append dated `[YYYY-MM-DD HH:MM]` entries there — this repo keeps the *what changed
> and why* narrative in the Living Ledger, not split across separate files.
>
> This stub exists so the global context-continuity write-back order (which names
> `docs/CHANGELOG_CONTEXT.md`) resolves to a real path. The Stop hook
> (`require_context_update_on_stop.js`) recognizes **both** this file and the Living
> Ledger, so updating either satisfies it.

## 2026-08-27 — pipeline_memory client init fixed for supabase-py sync options (PR #356)
First run after the `RUN_MEMORY_WRITE_ENABLED` flip wrote no run memory: the base
`ClientOptions` passed by the WR-02 timeout wiring lacks `.storage`, which supabase-py
2.31's sync `create_client` reads. `pipeline_memory/client.py` now builds
`SyncClientOptions`, falls back to a bare client if the SDK rejects options, and logs the
exception message; a real-SDK construction test guards it. Billing was never affected.
See `memory-bank/living-ledger.md` `[2026-08-27 11:51]`.

## 2026-08-28 — one identity definition for Sites 1/2/3; header foreman = hash rule; deterministic legacy header (PR #362)
The three inline identity chains in `pipeline.orchestrate.main` (history key, attachment-cleanup
tuple, prune key) are now one module-level `derive_group_identity()` called with switches bound once,
so the CR-01 drift shape is no longer expressible and the sites are behaviourally tested for both
arrival orders. The primary workbook header's foreman is the hash's `FOREMAN=` rule (`canonical_foreman()`,
first non-empty claimer in canonical order) — owner-approved and reachable in production
(a whitespace-only `Foreman Assigned?` yields a blank `__current_foreman`; such a primary group used to
show a blank header foreman while its hash named a later row's), gated on `variant == 'primary'` —
helper, helper-shadow, vac_crew and subcontractor primary headers keep their partition key; hashes and identity
keys are byte-identical (golden digests). `canonical_first_row()` now
uses the extended total order in legacy mode too, so the legacy header is deterministic while the
legacy hash is untouched. Closes the three threads left open on #361.
See `memory-bank/living-ledger.md` `[2026-08-28 12:05]`. PR #362.

## 2026-08-27 — identity row = canonical row: Excel header + orchestrate Sites 1/2/3 (PR #361)
A helper group can hold rows from two departments (its key carries no dept/job). #359 made
the hash order-stable, but the workbook header and the three orchestrate identity sites
(main-loop `history_key`, `valid_wr_weeks`, `current_keys` prune) still read arrival-order
`group_rows[0]`, so a stable hash was looked up under an unstable key and the group could
regenerate every run. All of them now read `canonical_first_row()`; the sort key also carries
every Job # alias the header accepts and the legacy identity `User` (hash-neutral: both sit
after the hashed-field string). Round 3 (2026-08-28) appends the unjoined hashed fields
(`|`-serialization collisions) and the raw `Work Order #` as further hash-neutral tiebreakers, and
makes `header_job_number()` the single Job # alias resolver for both the Excel header and the sort
key (same aliases, same precedence, raw value preserved for the cell).
Hashes are byte-identical to master; any group whose identity row changes — helper groups with
mixed dept/job metadata AND primary groups with mixed `User`/claimer values — gets one final
regeneration (same hash, attachment replaced once), then stays stable. In legacy mode
(`EXTENDED_CHANGE_DETECTION=0`) the header/identity row is now the 5-key-sorted row instead of
the arrival-order row, so the same one-time effect applies there.
Declined: legacy-mode header determinism (rollback sort is frozen). Deferred to Juan: aligning
the header's foreman with the hash's first-nonempty `FOREMAN=` token (billing-output change), and
a behavioural Sites 1–3 test, which needs the three inline `main()` identity blocks extracted into
one shared helper (production refactor) — both done in the 2026-08-28 follow-up above.
See `memory-bank/living-ledger.md` `[2026-08-27 20:20]`.

## 2026-08-27 — Learn guides corrected against pipeline behaviour (PR #360 review round)
The new operator / engineer guides and the system overview copied several claims that the
code contradicts: the acceptance gate (WR + weekly date + Units Completed? + price > 0 in
`fetch.py:837`; CU / quantity / foreman do not gate), the group key (`(WR, week, variant,
claimer)` — dept/job never split a file), `wr_filter` (test-mode only, never attaches),
`reset_wr_list` (destructive and global), the real CDT/CST schedule windows and run times,
and where attribution freezes. All corrected with line anchors; `CLAUDE.md`'s six-field
grouping description carries the same drift and is a separate follow-up.
Rounds 3–18 (Copilot auto-reviews every push) added: Snapshot Date day-block filter, reset
purge scope (`WR_*.xlsx` on the target sheet only), `TEST_MODE` gates Supabase writes while
`SKIP_UPLOAD` alone does not, explicit-EMPTY env values (never "unset" — `load_dotenv()`
refills absent ones, `SENTRY_DSN` included), Sunday = 4 normal runs, frozen
`_Unknown_Foreman` attribution, filename-only attachment check, and — the open item — the
repository is PUBLIC while ~284 WR-like ids and ~20 personnel names sit in 106 tracked files
(committed `generated_docs/*.json`, tests, `.planning/`, blog); only the lines these rounds
touched are aliased. **Owner decision pending:** scrub tracked files / make the repo private /
rewrite history (#360 thread 3877686166).
See `memory-bank/living-ledger.md` `[2026-08-27 21:10]`.

## 2026-08-28 — sheet_registry upsert no longer 400s; RPC failures name their PostgREST code (PR #363)
Every frequent run since 2026-08-27 18:20Z failed the `pipeline_memory.sheet_registry` upsert:
registered sheets omit `column_mapping` while a newly discovered sheet carries it, postgrest-py
sends `columns=` as the union of the payload's keys, and PostgREST NULLed the `NOT NULL` column
on the UPDATE half (23502 → HTTP 400, never self-healing once the registry was one sheet
behind discovery). The writer now issues one upsert per key-set, so every request is
key-homogeneous and a registered row's stored mapping is left untouched as intended; the deep
run's homogeneous payload is still a single identical request. `with_retry` now logs
`code=<SQLSTATE/PGRST>` on the final failure and the message only for structural code classes
(the Actions logs are public; `details`/`hint` never). Billing output untouched; fail-open path.
See `memory-bank/living-ledger.md` `[2026-08-28 15:05]` (root cause) and `[2026-08-28 16:05]`;
PR #363.

## 2026-08-28 — billing_audit kill switch no longer logs server text (PR #364)
Twin of the #363 fix: `billing_audit/client.py::_disable_for_run` (PGRST106/301/302) used to put the
PostgREST `message` and `hint` into the public Actions warning and the Sentry breadcrumb. Those
fields are untrusted diagnostic text that can echo request or database data. The warning now
carries the code, the error type and the locally authored operator guidance only; nothing about
when the kill switch trips or what it disables changed. See `memory-bank/living-ledger.md`
`[2026-08-28 17:10]`; PR #364.

## 2026-08-28 — groups whose WR has no target-sheet row are not generated; listed as an error (PR #365)
Owner decision: a Work Request with no row on the target sheet is a data-entry error on the source
sheet, not a matching problem. Such groups (154 group-weeks per run) used to regenerate on every run
— "can't verify the attachment, safer to regenerate" — and then fail to upload; measured on a
like-for-like run pair, that cost ~13–15 minutes per run, almost all of it in the upload phase (the
generation itself was cheap). They are now skipped before the billing-audit snapshot and the hash decision, so
they are neither tracked in Supabase nor generated. Guards: the target map must be populated, the WR
must not be a target-sheet collision (quarantined keys keep the old "not found" outcome), `TEST_MODE`
and `SKIP_UPLOAD` dry runs are exempt, and a circuit breaker disables the skip for the whole run
(`🛑` ERROR, fall back to generate-and-warn) when more than `NO_TARGET_ROW_MAX_MISS_RATIO` (default
`0.5`, must be in `[0, 1]`) of the distinct WR values across all fetched source rows are absent from
the map — a populated-but-partial read must never become "never generate". Reported once per run as
an ERROR line with the counts (never the values — ERROR logs reach Sentry) followed by a WARNING line
with the offending values (capped at 25) — those two lines are the audit trail for the data owner.
The rule converges by itself when a row is added. Verified on the first post-merge scheduled run
(33219619070): 154 not generated, 0 not-found upload warnings, run 42 min vs 55 (PR #365 had estimated
~45 min from the generation cost alone; the corrected figure and its evidence are in
`memory-bank/living-ledger.md` `[2026-08-28 19:00]`, PR #368). Parity treats never-generated groups like withheld
ones; `run_summary.json` gains `groups_skipped_no_target_row` (22-key contract, golden updated).
Operators: expect `… N not generated (no target-sheet row)` in the phase summary, one `❌` line and
one `Work request values with no target-sheet row: …` line; the per-group `Work request … not found
in target sheet` upload warnings disappear. See `memory-bank/living-ledger.md` `[2026-08-28 18:05]`;
PR #365.

## 2026-08-28 — real identifiers aliased in the public tip; generated manifest/hash files untracked (PR #366)
The repository is public. Every real Work Request number and real crew name in tracked files is
now a consistent fictional alias, and `generated_docs/artifact_manifest.json` / `hash_history.json`
— runtime state CI regenerates every run — are no longer tracked. No production code path changed;
operators will notice only that ledger/runbook examples use `1xxxxxxx`-style WRs. Two real WRs
remain by owner choice: the `pipeline/excel.py` WR-keyed log line, the startup banner that names
them, and one `.github/prompts/testing-and-validation.md` fixture key. See
`memory-bank/living-ledger.md` `[2026-08-28 18:20]`; PR #366.

## 2026-08-28 — Notion gets the no-target-row counter (opt-in property); last real WR ids removed from the tree
The weekly workflow now exports `groups_skipped_no_target_row` to the Notion run sync, which writes it to the
Pipeline Runs database as the Number property `Groups No Target Row` **only if that property exists with type
Number** (a same-named property of any other type is logged and skipped) — add it in Notion to opt in; nothing
changes until you do (Notion would otherwise reject the page). The startup banner and
`pipeline/excel.py` no longer name two historical Work Requests (the per-WR branch was a log line with no
behaviour). No pipeline behaviour change. See `memory-bank/living-ledger.md` `[2026-08-28 20:15]`; PR #369.

## 2026-09-01 — `<WR-D>` "Thursday total ≠ rows" diagnosed as a hand-edited copy; claimer-correction gap re-confirmed (diagnosis only)
No code change. The workbook the operator inspected was re-saved in Excel by a person after generation:
the Friday block was folded under Thursday and two Point 29 rows (524.51) were deleted, leaving the literal
Thursday TOTAL stale. The pipeline's own attachment on the target row is internally consistent (72 rows =
10,478.74). Operator rule: diff a suspect workbook against the target-row attachment and read its
`docProps/core.xml` before touching the generator; keep totals as literals (tamper evidence). Separately,
the "fix the foreman in Smartsheet and the next run should regenerate" expectation is not met because
`resolve_claimer` honours any non-blank frozen claimer, grouping partitions by that frozen value, and no
reset lever touches `attribution_snapshot`; the `Unknown Foreman` sentinel is frozen verbatim (5,829 rows /
94 WRs today, growing). This is Phase 12 (OWN-01..04), still gated on the owner's spec §8 #1 / #5
decisions. See `memory-bank/living-ledger.md` `[2026-09-01 17:55]`.

## 2026-09-01 — A frozen placeholder claimer is never honoured again (Phase 12 first slice, OWN-02, owner policy A)
Operators no longer need `RESET_HASH_HISTORY` to get a file regenerated under the right foreman after a
Work Request that had no assigned foreman at first generation is finally assigned. `resolve_claimer`
now reads a frozen `Unknown Foreman` / `#NO MATCH` (and the `Unknown` / `Unknown Helper` /
`Unknown VAC Crew` family) as "no history" and uses the current Smartsheet value, and `freeze_row`
never stores those placeholders — it nulls them and, when no role holds a real name, skips the
Supabase call entirely so the first real person can still be frozen first-write-wins. Real frozen
names still win exactly as before. Two new run-summary counters make it visible:
`sentinel_claimers_ignored` and `sentinel_freezes_deferred` (golden run_summary refrozen 22→24
keys). What is still NOT automatic: removing the old `*_Unknown_Foreman*` attachment. Neither
the scheduled run nor the isolated `REMEDIATE_CLAIMERS` sweep (which only removes `_NO_MATCH`)
deletes it — dispatch `reset_wr_list:<WR>` in `advanced_options` for that WR or delete it by hand,
knowing that any non-empty reset list puts the whole run in full mode (every group regenerates,
not only the listed WRs) and purges only the target sheet (a stale reduced-sub PPP identity on the
subcontractor PPP sheet needs a manual delete).
See `memory-bank/living-ledger.md` `[2026-09-01 18:05]`; PR #375 (merged `8325bc8`).

## 2026-09-01 — Frozen helper claims now honoured on the subcontractor-helper path; #375 review fixes (PR #376)
The subcontractor-helper path in `pipeline/grouping.py` passed a `datetime` week to `resolve_claimer`
while the prefetched attribution map is keyed by `date`, so that lookup always missed and the row
silently took the current Smartsheet helper — a frozen helper name was never honoured there, and
the #375 sentinel rule could not fire on that path. `resolve_claimer` now coerces the week itself,
so a helper frozen earlier beats a later Smartsheet edit exactly as it already does for primary,
VAC, and pre-pass helper rows. Operators: expect helper files for such WRs to regenerate once under
the frozen name after the first run. The same PR corrects the `REMEDIATE_CLAIMERS` guidance above
and replaces real identifiers in the ledgers with the `<WR-D>` / `<FOREMAN-D>` aliases. See
`memory-bank/living-ledger.md` `[2026-09-01 18:05]` (review-round bullet); PR #376.

## 2026-09-01 — Stale placeholder attachments clean themselves up; `reset_wr_list` regenerates only the listed WRs
Two owner-approved changes to the every-run cleanup and the reset lever. First, a
`_User_Unknown_Foreman` / `_Helper_Unknown_Helper` / `_VacCrew_Unknown_VAC_Crew` / `__NO_MATCH`
attachment that a run did not produce is now deleted once a real-name file for the same Work
Request, same week-ending, and same variant is live in that run — the case that arises when a WR
is assigned after its placeholder file was uploaded and the sentinel rule regenerates it under the
real name. It never fires across weeks or roles, never on a placeholder still being produced, and
a nameless bare primary does not count as a real name. Second, `reset_wr_list` now regenerates only
the listed WRs instead of disabling the unchanged-group skip for the whole run; the full read of
every sheet is kept on purpose so the purged WR can always be rebuilt. `WR`-prefixed tokens are
accepted. Operators: watch for `🔄 Sentinel-superseded attachment detected` log lines in the first
run after merge, and expect per-WR resets to be short. See `memory-bank/living-ledger.md`
`[2026-09-01 20:20]`; PR #377.

## 2026-09-02 — Group phase no longer re-freezes every row: the frozen-row cache is warm-started from the attribution prefetch

**What.** INC-05 (PR #373) retired the persisted frozen-row cache, and with it the warm start
of the in-run dedupe set that decides whether a completed row is sent to the
`billing_audit.freeze_attribution` RPC. The set started empty every run, so every completed row
(~214k) was re-sent to the first-write-wins RPC on every run, and because every group then had
"uncached" rows, the per-WR-week `pipeline_run` fingerprint select+upsert fired for every group
too. The grouping phase already fetches every frozen row for every WR-week through
`lookup_attribution_bulk` under the same eligibility rule, so the set is now seeded from that
map before the group loop starts (`pipeline/attribution.py` `warm_billing_audit_row_cache`,
`pipeline/grouping.py` `get_prefetched_frozen_row_keys`). Zero extra requests; nothing about
grouping, hashing, filenames, attribution values, or Supabase writes changes.

**Why.** The first run with the Phase 11.1 fix (33570018457) spent 84.6 of its 106 group-phase
minutes inside `freeze_attribution` (214,215 calls) and 13 more in `pipeline_run` (5,446 calls);
the fast pre-INC-05 profile was 18,257 and 732. Discovery is fixed; this closes the rest.

**How it affects operators.** Expect the `🧊 Frozen-row cache warm-started from the attribution
prefetch: N row(s) already frozen` INFO line before the group loop and a group phase back near
the pre-INC-05 duration (about 12 minutes at steady state on top of the ~20-minute fetch). If
the line is absent the bulk prefetch failed or the attribution flags are off, and the run
behaves exactly as before this change (every completed row frozen, slower but correct).
`snapshots_already_frozen` in the run summary drops toward zero for warm-started rows because
they never reach the RPC. See `memory-bank/living-ledger.md` `[2026-09-01 22:40]`; PR #378.

## 2026-09-02 — INC-06: abandoned shadow-parity probe workers no longer hold interpreter exit (PR #379)
**What.** The Phase 11 shadow-parity block runs its per-sheet Smartsheet delta probes on the
daemonised `_DaemonThreadPoolExecutor` and abandons any probe that overruns
`RUN_MEMORY_SHADOW_RPC_TIMEOUT_SEC` with `shutdown(wait=False, cancel_futures=True)`. That
covered two of the three exit blockers the executor's own docstring lists: the abandoned workers
stayed registered in `concurrent.futures`' atexit join registry, so the interpreter waited for
them at exit. `_DaemonThreadPoolExecutor.detach()` now removes them (`pipeline/config.py`) and
the parity `finally:` calls it after the abandon shutdown (`pipeline/parity.py`).

**Why.** Run 33579406295 finished every phase — generation, upload, cleanup, audit — by 05:37Z
and then sat 42 minutes in interpreter shutdown while three stuck `get_sheet` probe reads waited
for Smartsheet to close their sockets (~16 minutes each, then a retry). The job crossed
`timeout-minutes: 180` during its last artifact steps and is recorded as cancelled although no
billing output was lost. `TIME_BUDGET_MINUTES` cannot see this: it governs the group loop, not
interpreter shutdown.

**How it affects operators.** One new line closes the parity block: INFO `🧵 Shadow parity: no
probe still running; released N worker(s) from the interpreter-exit join (INC-06)` on a healthy
run, or WARNING `🧵 Shadow parity: M probe(s) still stuck in Smartsheet reads; N worker(s)
detached from the interpreter-exit join so exit will not wait (INC-06)`. Nothing else changes: probe results were always
discardable (D-07: the shadow compares and reports, never acts), escalation counts and the
parity verdict are computed exactly as before, and no billing, grouping, hashing, attachment,
workflow or env behaviour is touched. The bounded read timeout for the probe path is a separate
follow-up because the Smartsheet SDK exposes no per-request timeout and a session-wide one would
touch the production fetch path. See `memory-bank/living-ledger.md` `[2026-09-02 01:35]`
(diagnosis) and `[2026-09-02 02:50]` (fix); PR #379.

## 2026-09-02 — Discovery validation reads three rows instead of the whole sheet (PR #384, G-11.1-4 residual b)

**What.** `_validate_single_sheet` in `pipeline/discovery.py` now asks Smartsheet for a
sheet with `row_numbers=[1, 2, 3]` (the same bounded read the sample-value fallback already
used) instead of `include='columns'`, and reuses that response's rows as the date-column
sample set. The `include=` keyword selects optional response elements and never limited the
row payload, so the old call downloaded every row of every source sheet to read only
`sheet.columns` and `sheet.name`. `column_ids=` is deliberately not used: the column mapping
needs every column title. Three tests pin the new shape (`DiscoveryBoundedValidationReadTests`:
one call per sheet, `row_numbers` present and `include` absent, and a comment-stripped source
pin that builds the forbidden literal at runtime); the one expected-call literal in
`DiscoveryRegistrySkipTests` was updated and nothing else in that class changed.

**Why.** When the D-11.1-01 registry-version skip misses (skip index 0/121 on runs
33634833356 and 33647771644), discovery spent 3,214–4,999 s downloading 121 sheets at
26–41 s each, pushing the Python `Duration` to 96 and 129.7 min against the ~75-min SC-1
target. A skip hit (run 33659869696, 118/121) already met SC-1 at 30.8 min. Bounding the read
makes a miss cost seconds, so SC-1 no longer depends on whether upstream recalcs moved every
sheet version since the last registry write. Fix candidate (b), a column-set-hash skip key, is
deferred: a cheap miss removes its motivation.

**How it affects operators.** No new env var, cache file, TTL, Actions cache step, or
`*_MAX_MINUTES` / `*_TIMEOUT_SEC` constant (D-11.1-03). The request count per sheet drops
from two to one when the sheet has rows; a sheet with zero rows still takes the lazy fallback
read exactly as before. The D-11.1-01 skip fast path, every column title/type matching rule,
the `{'id','name','column_mapping'}` contract, the fail-closed `RuntimeError` on a validation
exception, `PARALLEL_WORKERS_DISCOVERY = 8`, and the retry wrapper are unchanged. Judge the
fix on the first post-merge scheduled **skip-MISS** run: `⚡ Phase 1 complete` should be low
single-digit minutes and the Python `• Duration:` line under ~75 min (never the Actions job
clock). See `memory-bank/living-ledger.md` `[2026-09-02 14:35]` and
`.planning/debug/11.1-discovery-full-validation-cost.md`.

**Outcome (2026-09-02, 17:45 CDT).** #384 merged as `13e8e76`; the first scheduled run on a
build containing it (33683979474, a genuine skip-MISS: 0/121 registry skips, 121 fully
validated) finished discovery in 37.7 s instead of 3,214–4,999 s, processed all 3,178 groups
at ~0.52 s/group with no `TIME_BUDGET` stop, and reported `• Duration: 0:50:47`. SC-1 is met
on the worst-case path and G-11.1-4 is closed; Phase 11.1 is sealed and GSD is at Phase 12.
Ledger `[2026-09-02 17:45]`.

## 2026-09-02 — Phase 12 (Ownership) PLANNED: 6 plans / 4 waves, checker passed, two owner decisions

`/gsd-plan-phase 12` ran end-to-end without a CONTEXT.md (owner chose to plan from the OWN-03
design spec and the 2026-09-01/02 ledger decisions). Research `7191676`, validation seed
`fbf2bf8`, pattern map, plans `f0ed36c` + revision `ed49ab4` (+ `34cac0d`), closeout `f6ff88e`.
Plan checker: iteration 1 = 0 blockers / 4 warnings, iteration 2 = 0 / 1 (validation-map row,
fixed inline). Requirements coverage 4/4; STATE.md is "Ready to execute".

**Why it matters for operators.** Two owner decisions change what Phase 12 builds: **D-12-A** —
no `wr_week_ownership` table; the ownership ladder is `attribution_snapshot` + `resolve_claimer`
plus new `backfill_source` / `backfill_run_id` columns (table deferred to Phase 13). **D-12-B** —
backfill source 4 reads the Supabase hash store (`billing_audit.group_content_hash` and
`pipeline_memory.group_state`) instead of the retired `hash_history.json`. Nothing in production
changed; every live step in the plans (owner SQL apply, `--apply` backfill, source-5 cron enable,
attachment replacement) is a blocking human checkpoint. See `memory-bank/living-ledger.md`
`[2026-09-02 18:15]` and `.planning/phases/12-ownership-last-known-foreman-as-of-the-week/`.

## 2026-09-02 — Instruction files aligned (run 1 of `align-instruction-files`)
**What:** CLAUDE.md 369 → 150 lines (rules + pointers; deep sections moved to `docs/ai/architecture.md`,
`.github/prompts/configuration-environment.md` § Operator quick reference, `docs/ai/safe-commands.md`);
`.github/copilot-instructions.md` regenerated; `.claude/project-state.md` 1,555 → 95 lines; six
`memory-bank/*` pages → pointer stubs; `docs/PROJECT_BRIEF.md` rewritten; GSD health HEALTHY (inserted
Phase 01.1 now declared). **Why:** four drifting copies of the same rules were being loaded into every
session. **Operator impact:** none on the pipeline (docs-only PR from `docs/align-instruction-files`);
the env-var catalog now lives in the configuration prompt, the cron schedule in `docs/ai/architecture.md`.
**Verified:** gsd-doc-verifier fact-checked the docs a fresh session reads (numbers in the ledger
`[2026-09-02 22:05]`); WR-01's wrong discovery.py comparison corrected. **Blocked:** `AGENTS.md` freeze —
the harness-boundary hook denies ClaudeOS writes; owner pastes the header by hand.

