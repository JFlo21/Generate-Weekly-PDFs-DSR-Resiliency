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

**Merged:** PR #385 squash `26b3c4f` (2026-09-02 23:08 CDT) after a Greptile fix (`deac60e`) — CLAUDE.md,
`docs/ai/*`, and the config quick reference now state the D-11.1-01 registry-version skip gate instead of
"every sheet validated every run". Local `master` reset to `origin/master`; the branch is deleted.

## 2026-09-03 — Phase 12 wave 1: OWN-03 claim-time attribution backfill script (PR #387)
**What:** new standalone `scripts/backfill_claim_time_attribution.py` — dry-run by default; finds `Unknown Foreman`
sentinel rows in `billing_audit.attribution_snapshot` and proposes the historically correct claimer through a
week-scoped four-source ladder (row events/state → same-row role → artifact filenames → Supabase hash store);
writes a git-ignored JSON/CSV report; `--apply` is gated behind `--i-approved-this`, a backup-table probe, and the
owner-deployed `billing_audit.backfill_attribution` RPC (not deployed yet, plan 12-03). **Why:** the 2026-08-24
defect froze ~5,824 rows under the sentinel; repairing the frozen values lets the next cron regenerate files under
real names with no grouping change (D-12-A/B). **Operator impact:** none on the cron — nothing imports the script;
`--apply` exits 3 against any real environment until 12-03 lands. **Verified:** full suite 1,994 passed; 6-gate
harness; GSD wave-post gates; haiku rubric 10/10; an independent Opus production-risk review drove one fix round
(named-sentinel-only targeting default + `--include-blank-roles`, chunked reads, None-read → exit 7, `.order()`
determinism, RPC count reconciliation). **Open:** Juan confirms the targeting default before 12-06; waves 2–4 pending.

**Review fix (Greptile, same PR):** source 1 read every historical `row_event`/`row_state` for a `row_id` without
matching the row's own `week_ending` to the target week, so a row re-dated after a data correction could have an
earlier week's owner proposed (and, under `--apply`, written) for a later week — a D-12-A violation. The bulk query
now selects `week_ending` and `_in_target_week()` gates both loops; a NULL week is never in-week evidence (row stays
unresolved). Four cross-week tests added; full suite 1,998; commit `988680a`. Juan confirmed the named-sentinel-only targeting default
(2026-09-03); PR #386 closed because its commit rides in #387. **Lesson:** per-row history sources need a same-row
cross-week fixture in their contract tests — neither the rubric verifiers nor the Opus round exercised one.

## 2026-09-03 — Phase 12 wave 2 started (branch `feat/phase-12-wave-2`, in progress)
**What:** PR #387 merged to master (`e1b6302`); wave 2 dispatched from a fresh branch off `77a675b` via `/gsd-execute-phase 12`
(three Sonnet executors, harness worktrees). 12-02 landed the CR-01 sentinel-predicate narrowing (`_SANITIZED_ERROR_IDENTIFIERS`
allowlist, normalized like `is_sentinel_claimer`) and the WR-01 function-local `AttachmentParentType` import. The pre-merge Opus
production-risk review found that the narrowing had *widened* the sibling side of the sentinel-superseded delete gate (an unlisted
sanitized error spelling such as `_DATE_EXPECTED` would have counted as a real-name replacement and deleted a stale
`Unknown_Foreman` attachment); fix `98b5ea3` adds `_is_real_name_identifier` so leading-underscore tokens are neutral on both
sides, hardens the predicate against non-str/whitespace tokens, and logs once when the SDK import falls back. 12-03 authored the
owner-deployed backfill SQL + contract test and halted at its blocking-human decision; its review round (PII out of the RAISE,
full-whitespace `btrim`, `#variable_conflict use_column`, payload-key pins) landed on its branch. 12-04 authored
`scripts/backfill_cell_history_attribution.py` (source 5: `Cells.get_cell_history`, 0.5 s pacing, caps 3,000 req / 1,200 rows /
45 min, week window `week_ending - 6 days`, falsy→truthy transitions only, conflict on differing names, read failure = `error`
+ exit 7) and its 79-test suite, halted at its Task 3 decision; the Opus round fixed four HIGH + four MEDIUM (`101489d`). The
workflow YAML is NOT written until Juan decides. **Wave 2 merged to `feat/phase-12-wave-2`** through the manifest-scoped
`worktree.cleanup-wave` (13 files, +3,712/-21). **Operator impact:** none yet — nothing on master; the SQL is never applied by
automation and the cell-history script never passes `--apply`.
**Verified:** post-merge py_compile + full suite 2056 passed / 1 skipped / 386 subtests; schema-drift, codebase-drift and UI
gates clear. **Open:** Juan's decisions at the 12-03 (DDL apply) and 12-04 (workflow) checkpoints; carried to 12-06: backup-table
probe is same-UTC-day only, RPC runs SECURITY INVOKER with only EXECUTE granted in the file (verify UPDATE on
`attribution_snapshot` for the applying role), STEP 0 column check does not fail closed, NULL/stale-week `row_event` count
before `--apply`, confirm the `backfill_cell_history` provenance tag.

## 2026-09-03 — Phase 12 waves 2–3 complete, phase gates run, PR #388 open
**What:** wave 2 merged through the manifest-scoped `worktree.cleanup-wave` (12-02 cleanup narrowing + lazy import;
12-03 owner SQL + contract tests; 12-04 source-5 cell-history job + tests), then the two blocking-human decisions:
Juan `approve`d the one-way DDL (12-03 Task 3) and chose `approve-cron` (12-04 Task 3); the workflow was authored,
Opus-reviewed (FIX-FIRST → M2/M3/L6 fixed), and then **re-decided to dispatch-only** when the review showed the
backfill step can never reach a candidate list on a fresh runner (the sources-1-4 CLI requires `--wr` + `--weeks` by
design). Wave 3 (12-05) shipped the runbook page, four rewritten pages, 20 docs tests and the ledger entry. Phase
gates: Opus whole-branch integration review SHIP (2 MEDIUM fixed in the SQL: UNION dedup + STEP 0b duplicate-key
probe, STEP 2 VERIFY of the live CHECK), `/gsd-code-review 12` 0 critical / 3 warnings (WR-01 false-zero backlog on
a corrupt report and WR-02 silent filter ignore fixed), gsd-verifier human_needed 49/62 · 0 failed. Juan's live
STEP 1 42P01 (placeholder left in the GRANT) fixed in the file with a STEP 1 VERIFY query.
**Why:** OWN-03 needs the SQL objects, the source-5 resolver and the docs in place before the owner-run remediation
(12-06) can start; every write path stays behind a human.
**Operator impact:** none on the scheduled run (12-02 is strictly narrowing: decline-to-delete on every branch). New
manual-only workflow `cell-history-backfill.yml` (dispatch, never `--apply`). New runbook page
`website/docs/runbook/ownership-attribution.md`. The SQL is applied by hand once per environment.
**Verified:** full suite 2,093 passed / 1 skipped / 405 subtests; py_compile; Docusaurus typecheck + build; haiku
rubric PASS on each fix round. **Open:** PR #388 merge; 12-03 Task 4 answers; 12-06; a candidate source before any
cron; carried: NULL/stale-week `row_event` count, RPC UPDATE grant for the applying role, source-5 blank-role tally
naming (LOW-1). **Lesson:** parallel worktree plans need one integration review after the merge — the seams were
clean, but the workflow/CLI candidate-source mismatch was only visible with both plans in one tree.

**Addendum (same day, 19:30 UTC):** Juan applied `billing_audit/own03_backfill_attribution.sql` live and replied
`approved` — 12-03 Task 4 closed. Confirmed: backup table `attribution_snapshot_backup_20260903`; the live CHECK
accepts all five provenance tags. Two operator hiccups fixed in the file the same hour: the STEP 1 placeholder must
be substituted in BOTH statements (42P01), and the STEP 3/4 function blocks now carry SELECTION START/END markers
because the dashboard's run-under-cursor splits dollar-quoted bodies (42601 ×2). Unreported answers (STEP 0/0b,
counts, spot check, smoke test, UPDATE grant) are re-verified read-only in 12-06 Task 1.

**Greptile on PR #388 (`27c7ca5`):** three valid findings fixed — (1) the RPC wrote ROW-level provenance per ROLE update, so a
row filled by two sources/runs lost the first role's provenance: new `backfill_provenance JSONB` per-role map merged on every
write (owner re-runs STEP 2 + STEP 4, idempotent); (2) the source-5 apply ignored the report's `include_blank_roles` mode and
silently dropped blank-role proposals: mode now inherited from the report summary; (3) `max_requests=0` was a green no-op:
workflow rejects it, script exits 4. Suite 2,098. **Lesson:** a provenance column must have the same grain as the write — a
per-role write needs per-role provenance.

**Live re-apply (same evening, Supabase MCP after Juan's OAuth):** the Greptile STEP 2 (per-role provenance column) and
STEP 4 (new RPC) were applied on the billing project and every previously unreported answer was read back: STEP 0b 0
duplicate keys; live 220,236 vs backup 220,010 (the cron froze 226 rows in six hours — a dated backup is valid only on
its apply day, 12-06 re-creates it); spot check true/true/false; smoke test `skipped_no_row`; 0 backfilled rows.
Surprise: the RPC was executable by `anon`/`authenticated` because Postgres grants EXECUTE to PUBLIC by default —
STEP 5 now REVOKEs from PUBLIC/anon/authenticated before the service_role GRANT (`a227463`, contract test), verified
with `has_function_privilege` (service_role + postgres only). Owner item: `anon`/`authenticated` also hold full DML
on `attribution_snapshot` behind RLS. Ledger `[2026-09-03 15:55]`.

**Merged:** PR #388 squash-merged to master as `1f159bc` (2026-09-03 21:02 UTC); master workflows green: CI Checks, tests + coverage, lint, runbook changelog stub `a89e672` (expand before the next release), Notion sync. Next branch `feat/phase-12-remediation` for 12-06.

**Second brain (same evening):** durable lessons moved out of the ledger into the vault — new `wiki/tools/supabase-mcp.md`
(plugin rules: read-only by default, DDL only for named steps, `execute_sql` not `apply_migration` for owner-applied
files, untrusted results) and `Supabase PostgREST Integration Patterns` §3 (REVOKE before GRANT, verify with
`has_function_privilege`, dated backups expire, provenance grain = write grain); dashboard, index, current-state and the
project page now say "Phase 12 waves 1–3 merged; 12-06 open". Vault log `[2026-09-03n]`–`[2026-09-03p]`.

**2026-09-03 night — 12-06 dispatched, halted at Task 1:** the last Phase 12 plan is owner-run; the executor returned its blocking-human dry-run checkpoint without touching live systems. Plan text vs code: no full-scope dry-run mode exists (`--wr` + `--weeks` required, exit 8 otherwise) — use the runbook's scoped command. Backup must be re-created on the apply's UTC day. Tracking only; no code changed.

**2026-09-03 night — 12-06 Task 1 dry-run REJECTED (no apply):** Juan ran the full-scope dry-run (207 WRs × 54
weeks, exit 0, 5,829 rows). Source 3 proposed the literal "Unknown Foreman.xlsx" for 4,070 rows because
`public.artifacts.filename` is the stable hash-less attachment name and the parser only strips a `_<6hex>.xlsx`
tail; the RPC guard checks the current value only, so the apply would have frozen that string as a real name.
Only 692 source-1 proposals (7 WRs) are sound. Also: `#NO MATCH` rows (945) are invisible to targeting via the
lookup RPC, and the roadmap's sample WR 19073866 is a placeholder absent from Supabase. Root cause, gates that
missed it, and rules: ledger `[2026-09-03 17:30]`. Next: `/gsd:plan-phase 12 --gaps`. No code changed.

## 2026-09-03 — Phase 12 gap closure wave 1: 12-07 source-3 extension fix (branch `feat/phase-12-remediation`, in progress)
**What:** `/gsd-execute-phase 12 --gaps-only` (sequential; the worktree base-check degraded because the branch is
ahead of `origin/HEAD`) executed 12-07 in RED/GREEN pairs: `_extract_claimer_from_filename` now recognises the live
hash-less `public.artifacts` filename shape, strips exactly one trailing document extension before the single
`is_sentinel_claimer` call, and rejects any candidate still carrying one; the `_<6hex>.xlsx` hash-suffix path is
untouched; `_build_apply_payload` gained a `proposed_value` sentinel/extension guard beside the existing
`current_value` guard. Fixtures cover both filename shapes. Commits `8d27e36`…`f14aa5c`; `12-07-SUMMARY.md`.
**Why:** G-12-3 — the rejected 12-06 dry-run proposed the literal `Unknown Foreman.xlsx` for 4,070 of 4,762 rows
because the surviving extension defeated the sentinel classifier's normalisation.
**Operator impact:** none on the scheduled run (`generate_weekly_pdfs.py`, `pipeline/*` untouched). The backfill
script stays dry-run by default; `--apply` remains behind the owner RPC and the same-UTC-day backup probe.
**Verified:** file suite 60/60 (10 subtests); full suite 2,107 passed / 1 skipped / 416 subtests; py_compile;
diff confined to `scripts/backfill_claim_time_attribution.py` + `tests/test_backfill_claim_time_attribution.py`.
**Open:** 12-08 (Juan's `#NO MATCH` scope + SC3 sample decisions, blocking-human), 12-09 (owner-applied RPC
extension guard), 12-10 (Opus production-risk review of 12-07 + 12-09, fresh backup, zero-defect live dry-run),
then 12-06 re-entry. No PR until the Opus review passes (`.continue-here.md` blocking constraint).

## 2026-09-04 — Phase 12 gap closure wave 1 closed: 12-08 owner scope decisions D-12-C / D-12-D
**What:** the 12-08 executor stopped at its first `blocking-human` gate and returned both decision tables; Juan
answered in writing and a fresh continuation executor recorded them verbatim: **D-12-C `defer`** — the 945
`#NO MATCH` rows (935 primary + 10 helper, nulled by `lookup_attribution_bulk` before the script sees them) stay
out of OWN-03's live remediation, so 12-10's re-run carries no `--include-blank-roles`; **D-12-D
`substitute-89829163`** — ROADMAP success criterion 3 now names WR 89829163 (live-verified sentinel rows on WE
082425/083125/091425/092125) resolved via `backfill_artifacts`, replacing WR 19073866, which has zero rows in
every Supabase store. Runbook `ownership-attribution.md` states which sentinel populations OWN-03 remediates and
which it leaves alone; Living Ledger `[2026-09-04 10:05]`; option-aware docs tests. Commits `cf13670`…`e1c7ac8`.
**Why:** without a written scope answer 12-10 could not be invoked, and without a provable sample the phase had
no closable acceptance criterion.
**Operator impact:** none on the scheduled run; no code, SQL, or RPC changed in this plan. REQUIREMENTS.md keeps
OWN-03/OWN-04 Pending until the live backfill lands (12-09 / 12-10 / 12-06).
**Verified:** docs tests 25/25; Docusaurus typecheck + build; wave-close gate pytest 2,112 passed / 1 skipped /
416 subtests (37.8 s); py_compile; schema-drift, codebase-drift and UI wave-post gates clear.
**Open:** wave 2 = 12-09 (RPC STEP 4 extension guard + contract test; Juan applies STEP 4 + STEP 5 live), wave 3 =
12-10 (Opus production-risk review of 12-07 + 12-09, fresh same-UTC-day backup, zero-defect dry-run), then 12-06.

## 2026-09-04 — Phase 12 gap closure wave 2: 12-09 RPC extension guard (code done; live apply awaiting Juan)
**What:** `billing_audit/own03_backfill_attribution.sql` STEP 4 gains one more validation-loop guard: the RPC
raises before any UPDATE when a proposed `value` carries a document file extension (`xlsx|xlsm|xls|csv|pdf|json`,
case-insensitive), beside the existing sentinel guard. `tests/test_own03_backfill_sql_contract.py` pins that SQL
list to `scripts/backfill_claim_time_attribution.py::_FILENAME_DOC_EXTENSION_RE` so the two layers cannot drift;
`billing_audit/schema.sql` documents the amended two-ground refusal contract (comment-only change). Commits
`f6aa6d9`, `b51faa0`, `5baed30`.
**Why:** G-12-3's server-side half — `is_sentinel_value` never strips an extension, so `Unknown Foreman.xlsx`
passed the guard written to stop it. Widening `is_sentinel_value` itself was ruled out: it also drives the
per-role `UPDATE … WHERE` targeting.
**Operator impact:** the file must be re-applied by hand: run STEP 4 as one selection (it starts with `DROP
FUNCTION`), then the whole STEP 5 REVOKE/GRANT block (DROP resets the ACL), then `NOTIFY pgrst, 'reload schema'`;
do not re-run STEPs 1–3. Verify EXECUTE is held by `postgres` + `service_role` only, the guard appears in
`pg_get_functiondef`, and `backfill_run_id IS NOT NULL` still counts 0.
**Verified:** contract tests 25/25; full suite 2,117 passed / 1 skipped / 441 subtests; protected-construct and
comment-only diff gates exit 0. No agent, script, or MCP tool executed any SQL.
**Open:** 12-09 Task 3 (Juan's live apply + four read-backs), then wave 3 = 12-10, then 12-06 re-entry.
**Ledger commits this run:** `360fde7` (12-07), `27787cc` (wave 1 close), `f2765fc` (12-09 code); the orchestrator
paused at the 12-09 owner-apply checkpoint with a clean tracked tree.
**Live apply (2026-09-04 05:36–05:37 UTC):** Juan asked the main session to run STEP 4 for him; it applied STEP 4
(DROP + CREATE, the exact marker selection) and then STEP 5 + `NOTIFY pgrst` via the Supabase MCP on the billing
project, STEPs 1–3 untouched, no RPC call. Read-backs: EXECUTE held by `postgres` + `service_role` only (`proacl`
`{postgres=X/postgres,service_role=X/postgres}`, anon/authenticated false), extension guard present in
`pg_get_functiondef`, `backfill_run_id IS NOT NULL` = 0, snapshot 220,621 rows unchanged. Juan `approved`. Recorded
in 12-09-SUMMARY as an owner-authorized deviation from "Juan applies by hand".

## 2026-09-04 — Phase 12 gap closure: 12-09 closed; 12-10 independent review PASS
**What:** 12-09 closed (`f269f78` SUMMARY with the verbatim live read-backs, `786329b` STATE/ROADMAP; 9/10 Phase 12
summaries). Wave 2 close gate: pytest 2,117 passed / 1 skipped / 441 subtests, py_compile, drift + UI gates clear.
12-10 Task 1 — the independent production-risk review the `.continue-here.md` blocking constraint demands — ran as
an orchestrator-dispatched, read-only Opus `production-risk-reviewer` (the GSD executor has no Agent tool) over the
scoped diff `2c794a9..786329b` of the four fix files with the plan's 8-point rubric: **verdict `pass`, nothing
requiring a fix.** LOW notes: source-4 identifiers reach `_resolve_single_name` without the extension filter but
are sanitized name segments, never filenames; the new residual-extension reject sits on the shared tail, so the
hash-suffixed path is strictly narrower, never wider. Residual risks: closed extension set (widen all three layers
together if another writer appears); pre-existing `_FILENAME_HASH_SUFFIX_RE` eats a final six-hex-letter name
segment (e.g. `Facade`) → separate ticket; the 12-06 dry-run report is no longer a valid approval artifact.
**Why:** rubric verifiers passed 12-01 while an Opus review found real write-path defects; no attribution writer
ships to a PR without this gate.
**Operator impact:** none yet; the 12-06 apply must be re-approved on a fresh dry-run.
**Open:** 12-10 Task 2 (Juan: fresh `attribution_snapshot_backup_20260904`, same UTC day as the apply), Task 3
(scoped read-only dry-run with zero extension-bearing proposals, report outside the repo), then 12-06 re-entry.
**Task 2 done (2026-09-04 06:07:36 UTC):** at Juan's choice the main session ran STEP 1 via the Supabase MCP —
`attribution_snapshot_backup_20260904` created with 220,621 rows (= live), `service_role` SELECT granted, the
2026-09-03 table (220,010 rows) left in place. The table satisfies the `--apply` probe only for an apply before
2026-09-05 00:00 UTC; STEP 1 must be re-run if 12-06 slips past that.
**Task 3 done (same session):** read-only dry-run on the exact pre-fix scope (WR 89732091 × 7 weeks, no
`--include-blank-roles`, report in the system temp dir then deleted, tree clean, exit 0): 235 rows → 0 `proposed`
/ 235 `unresolved`, extension-bearing proposals 0 of 0 (was 235 of 235), sentinel-classified 0 of 0, no source
produced a candidate. The placeholder is gone; the zero is vacuous on this scope because no source holds a real
name for these rows — the full-population answer (how many of the 4,070 resolve via source 4) belongs to 12-06
Task 1. Juan replied `re-enter-12-06`; 12-06 resumes at its Task 1 with Tasks 2–4 still behind his verdict.

**2026-09-04 ~07:15 UTC — gaps-only run closed; 12-06 made re-entrant; code-quality pass.** What: wave 3 closed with
every gate green (pytest 2,117 / 1 skipped / 441 subtests, `py_compile`, schema-drift + codebase-drift + UI gates
`block: false`, 6-gate harness ALL PASSED). `5121c30` reverted the executor's premature OWN-02/OWN-03 "Complete" marks
(the shared-ID ready gate counted 12-06's halted SUMMARY; the live apply has not run) and moved OWN-03's sample to
WR 89829163 per D-12-D. `7ce962a` changed `12-06-SUMMARY.md` from `status: halted` to `status: blocked` — the only
SUMMARY state that returns a plan to the incomplete/runnable list — so `/gsd-execute-phase 12` resumes 12-06 at Task 1.
`verify_phase_goal` / `update_roadmap` were skipped on purpose because the phase is incomplete by design. `634d93b`
committed the advisory code-quality report (Opus `gsd-code-reviewer`, 7 files changed since `2c794a9`): 1 blocker,
9 warnings, 2 info. **CR-01 (verified):** `_FILENAME_HASH_SUFFIX_RE` matches a 6-hex tail while `pipeline/excel.py:412`
emits the 16-hex `hexdigest()[:16]` tail, so a hash-tailed placeholder would pass all three extension guards and be
written as a real name; a read-only count shows 0 of 116,906 live `public.artifacts` filenames carry any hash tail
(all rows post-date the 2026-05-28 `SUPABASE_HASH_STORE_AUTHORITATIVE=1` flip), so 12-06's apply is unaffected unless
that flag is reverted. **WR-01 (verified):** `tests/test_own04_documentation.py` pins D-12-C/D-12-D to the NEWEST
`living-ledger.md` entry, so the next bottom-append breaks the push-gating suite — no ledger entry was appended this
session; lessons went to the vault. Why: the gate is advisory, both findings are outside the `--gaps-only` scope, and
the parser regex is protected extraction behavior — they route through `/gsd-verify-work 12` as new gaps.
**Operator impact:** none live; 12-06 Task 1's dry-run report must now show 0 extension-bearing and 0 hash-tailed
proposals before Juan's apply decision; the `_20260904` backup expires for the probe at 2026-09-05 00:00 UTC.

## 2026-09-04 (evening) — no repo change; claude-mem continuity degraded since 2026-09-02 20:47 CDT (upstream #3857)
Status check only ("what's next" → resume 12-06 Task 1; the `_20260904` backup window closes 19:00 CDT, so the
`--apply` will need a fresh STEP 1 backup on apply day). Diagnosed why claude-mem is not capturing: the plugin
auto-updated to v13.24.0, which bumps only three manifest files and ships the unchanged 13.23.1 worker bundle, so
every hook event kills and respawns the worker (5,767 kills / 4,217 restarts logged since the update; this session
stored 2 prompts, 0 observations). Fix = relabel the four `"13.23.1"` literals in the marketplace
`worker-service.cjs` to `"13.24.0"` (script in the session scratchpad, backup taken); the auto-mode classifier refused
to run it, so Juan ran it himself at 19:03 CDT. Verified afterward: the hook recycled once onto the patched bundle,
the worker reports 13.24.0 with a stable pid and growing uptime, 0 mismatch kills / 0 restarts / 0 errors after the
patch, and capture resumed (first observation for this session stored). Cloud sync needed no extra env var: the hub's
503 `projection_busy` retries were an artifact of the restarts; after the fix the status endpoint reports hub
reachable, pending 0, dead-letter 0, head = projected = local cursor. **Operator impact:** treat claude-mem summaries
from 2026-09-02 evening to 2026-09-04 19:03 CDT as incomplete; the repo ledgers and `.planning/HANDOFF.json` are the
continuity source for Phase 12. The marketplace bundle is git-dirty until upstream ships a rebuilt one; revert it if
a plugin auto-update fails to pull.

## 2026-09-05 00:24Z (2026-09-04 19:24 CDT) — 12-06 Task 1 dry-run re-run clean; no repo change; awaiting Juan's verdict
`/gsd-execute-phase 12` resumed at plan 12-06 (the only runnable plan; `phase-plan-index` honors its `status: blocked`
even though `init.execute-phase` counts it complete by SUMMARY presence). The orchestrator ran Task 1's read-only
full-scope dry-run itself (no executor dispatched, nothing written to Supabase): scope enumerated by read-only SQL
(207 WRs × 54 weeks, 391 pairs, 6,764 named-sentinel rows, 0 backfilled), report kept in the session scratchpad
outside the repo, analysed in-sandbox as counts only. Exit 0; 5,829 rows → 1,758 proposed (artifacts 1,066 + live 692
over 30 WRs / 76 pairs / 24 names), 0 conflict, 4,071 unresolved; source 4 resolved nothing, and SQL confirms the 180
unresolved pairs hold only placeholder-named artifacts or none — the zero is genuine. All G-12-3 / CR-01 guards read 0
(extension-bearing, hash-tailed, sentinel-classified, blank). Every proposal agrees with its `public.artifacts`
filename (1,758/1,758). **Operator impact:** (1) the D-12-D sample WR 89829163 is unresolved on all four weeks
(placeholder-only artifacts and hash identifiers), so ROADMAP success criterion 3 needs a new sample — candidates
89746993 / 89841789 / 89848991 (artifacts) or 90851321 (live); (2) the UTC date rolled past the `_20260904` backup, so
Task 3's `--apply` needs a fresh STEP 1 backup (`_20260905`) on apply day; (3) Task 1 is parked at the blocking-human
checkpoint until Juan replies `approve` / `approve-with-scope` / `reject`. Evidence file:
session scratchpad `own03_dryrun/evidence_12-06_task1.md` (counts only).
**Update (same evening):** Juan replied `I approve`; recorded in `12-06-SUMMARY.md` and committed (`9fab1ab`). Task 2
(apply decision) is open. At Juan's request the session then probed `public.smartsheet_unified_history` read-only as a
possible source for the 4,071 unresolved rows: it is the audit change log of `smartsheet_unified` (captures begin
2025-11-04, after every affected week) with a derived foreman change-log table nobody had documented. It names a
"last foreman before the placeholder" for 3,987 rows — unambiguous for 2,306 rows (20 WRs), two candidates for 1,681
rows (22 WRs), none for 84 — but every capture is ≥30 days after the week, so it cannot show who held the row in-week
and is not admissible under D-12-A without a new decision. **Operator impact:** do not block the 12-06 apply on it;
the designed follow-up for the unresolved rows is source 5 (`scripts/backfill_cell_history_attribution.py`, now
viable via the populated `row_state` bridge, ~4 capped runs), with the history table as a cross-check. Evidence:
scratchpad `own03_dryrun/evidence_unified_history_probe.md`. No Supabase writes.

## 2026-09-05 03:45Z (2026-09-04 22:45 CDT) — OWN-03 live backfill APPLIED: 1,758 attribution rows repaired (12-06 Task 3)
**What changed (production data, not code):** at Juan's `apply-full` then `Run it`, the session created the same-UTC-day
backup `billing_audit.attribution_snapshot_backup_20260905` (221,276 rows, `service_role` SELECT granted; older backups
kept) and ran `scripts/backfill_claim_time_attribution.py --apply --i-approved-this` over the approved scope (207 WRs ×
54 weeks, no `--include-blank-roles`). Result: **1,758 `frozen_primary` values that were `Unknown Foreman` now hold the
historically evidenced real foreman** (1,066 from the `public.artifacts` filename, 692 from in-week completed-unit
events), across 30 work requests and 76 (WR, week) files; 0 skipped, 0 errors. **Why:** these files have been
regenerating every run as `_User_Unknown_Foreman` placeholders; OWN-03 repairs the frozen claimer in place so the
unchanged pipeline names them correctly. **Proof:** the 219,518 rows the apply did not touch are byte-identical to the
backup on all three role columns; every touched row was a sentinel before and a real name after; `backfill_source` /
`backfill_provenance` are set on all 1,758 (total = updated). **Operator impact:** (1) the next weekday run (Mon
2026-09-07) should regenerate those 76 files under real names and the sentinel-superseded gate should delete the
placeholder attachments — that is 12-06 Task 4's observation; (2) do not drop `_20260905` until Task 4 passes;
rollback is an `UPDATE … FROM` that table; (3) `backfill_run_id` is the empty string on these rows because a local run
has no `GITHUB_RUN_ID` — rows are still identifiable by `backfill_run_id IS NOT NULL` and the provenance jsonb; a
local-run identifier is a follow-up for verify-work; (4) 4,071 `Unknown Foreman` rows remain (no in-week evidence in any
Supabase store → source 5 cell history), plus 945 `#NO MATCH` rows deferred by D-12-C. Evidence: session scratchpad
`own03_apply/` (counts only). Summary: `12-06-SUMMARY.md` Task 3.

## 2026-09-05 07:35–07:55Z (02:35–02:55 CDT) — Phase 14 "Foreman Helper #2" opened in GSD (planning only; no code or production change)
**What changed (planning artifacts only):** Juan authorized GSD *planning* for a second Helping Foreman slot. The session
added Phase 14 to the v1.4 roadmap via `gsd phase.add`, wrote HLP-01..HLP-07 into `REQUIREMENTS.md` (+ traceability
rows), filled ROADMAP §Phase 14 with the three confirmed owner decisions (Intake ProMax 8 `2244739192541060` is
intentionally excluded and never a prerequisite or remediation target; missing optional Helper #2 columns mean
"capability unavailable — skip only the Helper #2 path", never a sheet rejection; extend the existing Helping Foreman
mechanics, no rebuild, no rule that one unit is billed twice), and recorded the behavior contract in `14-CONTEXT.md`
(D-14-01..12 decided from repository evidence; **O-14-A** — a row with BOTH helper completion boxes checked — left OPEN
for Juan, recommended option = hold the row with visibility). The still-uncommitted 2026-07 Helper #2 prototype found
in the sibling clone (`master` @ `d11f20f`, 448 insertions / 16 files) was snapshotted read-only into
`.planning/phases/14-foreman-helper-2/reference/helper2-prototype-2026-07/` as evidence, never as code to apply.
**Why:** the prior handoff (vault, 2026-08-23) left the generator side dormant and its code at risk on an unpushed
working tree; GSD now owns the audit, plan, and verification for the feature. **Operator impact:** none yet — nothing
touches `generate_weekly_pdfs.py`, Smartsheet, Supabase, or the workflow. Live read-only observation 2026-09-05 ~07:40Z:
Intake 8 sits in the scanned Intake folder `8815193070299012` with `Weekly Reference Logged Date` and full Helper #1
columns, so today's discovery accepts it; Helper #2 there is simply unavailable — Phase 14 does not change that either
way. Commits `57bcfc6`, `27ab07c`, `d1f244a` on `feat/phase-12-remediation`; `/gsd-plan-phase 14 --research` in
progress; stop point = implementation-approval checkpoint.

## 2026-09-06 01:30–02:50Z (2026-09-05 20:30–21:50 CDT) — Phase 14 "Foreman Helper #2" PLANNED via GSD; stopped at the planning-approval checkpoint (no code or production change)
**What changed (planning artifacts only):** `/gsd-plan-phase 14 --research` ran to completion. Researcher → `14-RESEARCH.md`
(`7b95fe4`; the bounded architecture audit lives here — affected-consumer disposition, three silent-gap sites: cleanup
orphan-supersede set, upload PPP dual-route gate, `freeze_row` all-sentinel tuple), Nyquist seed `14-VALIDATION.md` (`7e646e4`),
pattern map `14-PATTERNS.md` (`e5287a8`), then the planner wrote **10 plans in 6 waves** and the checker ran three times:
iteration 1 found 2 blockers — all 7 checkpoint tasks used the auto-task schema instead of the canonical
`<decision>/<options>/<resume-signal>` (or `<what-built>/<how-to-verify>/<resume-signal>`) children, and four owner
checkpoints lacked `gate="blocking-human"`, which GSD auto/chain mode resolves silently with the first option — plus 5 warnings;
the planner revision fixed all of them; iteration 2 returned 0 blockers / 4 warnings; the orchestrator applied three surgical
fixes (14-10 T2's live upload-suppressed rehearsal is now preconditioned on a dated owner authorization plus a code-verified
no-write/no-cleanup reading, never "run anyway"; `14-VALIDATION.md` attributes `test_helper2_family_parity.py` to 14-01-02;
14-01's vocabulary lock marks the `sheet_registry` marker shape as recommended, pending 14-07 T1); iteration 3 returned
0 blockers / 1 cosmetic tally line, fixed afterwards and re-validated with the deterministic checks (not re-run through the
checker). Gates: `verify.plan-structure` 10/10, verify-command probes 63/63 clean, decision coverage 12/12 (after `fd2d5af`
reflowed the D-14-10 bullet so the parser could read its title), requirements 7/7, plan:post gap analysis 19/19.
**Committed:** `af1221e` `docs(14): create phase plan` — 10 × PLAN.md, RESEARCH, VALIDATION, STATE, ROADMAP — on
`feat/phase-12-remediation`; nothing pushed. STATE.md now reads `current_phase: 14` / "READY TO EXECUTE" with `stopped_at`
naming the planning-approval checkpoint; the Phase 12 resume pointer stays in `.planning/HANDOFF.json`.
**Why it matters:** every production boundary in the plan set sits behind one of seven `blocking-human` checkpoints (live
column probe, `row_state` DDL, `sheet_registry` marker, O-14-A rule, attribution migration apply + read-back, rollout
decisions), Intake ProMax 8 has no remediation task, O-14-A stays Juan's call with only its dependent task blocked, and
Helper #1 / primary / VAC identities are byte-identical when Helper #2 is absent (14-01 T2 regression + family-parity test).
**Operator impact:** none — `generate_weekly_pdfs.py`, Smartsheet, Supabase, and the workflow are untouched;
`HELPER2_ENABLED` does not exist yet. **Next:** Juan reviews the plans, answers O-14-A and the per-slot two-files consequence,
then `/gsd-execute-phase 14` (not run by this session).

## 2026-09-06 17:20–20:20Z (12:20–15:20 CDT) — GSD tooling incident (global, no repo change): forbidden npm reinstall ran and was rolled back; plugin 1.13.0 bundle rebuilt

**What:** in this repo's session, `/gsd-core:gsd-update` executed `npx @opengsd/gsd-core@latest --claude --global` against
the ClaudeOS config dir — the path `~/.claude/lessons-learned.md` (2026-08-23) forbids, because the marketplace plugin
`gsd-core@gsd-core` is the engine and `~/.claude/gsd-core/*` are junctions into its cache. Root chain: the plugin had
auto-updated to 1.13.0 at session start but its tsc self-build was killed by a hook timeout at 41/213 lib files; its
"built" sentinel (`cli-exit.cjs`) is emitted early, so it never retried; the junction guard pinned VERSION to the newest
built tree (1.12.0); the statusline flagged a phantom update; the skill offered the reinstall and the model followed it
without consulting the lessons ledger. **Repaired the same session:** plugin bundle completed (tsc in the cache dir,
41→213 files, `runtime-identity` 1.13.0); every installer write reverted by its own manifest (168 files, 76 empty dirs),
`~/.claude/settings.json` restored from git HEAD hunks (14 duplicate hook entries, Serena workflow-guard matcher, two
timeouts, `permissions.allow`), `gsd-core/*` re-junctioned into the 1.13.0 plugin tree; verified 0 residue, 0 duplicate
registrations vs the plugin's hooks.json, `update-context` = 1.13.0 = latest, junction guard clean.
**Repo impact:** none — no file under this repo changed; `.planning/`, `pipeline/`, workflows, Smartsheet, Supabase all
untouched. Phase 14 remains at the planning-approval checkpoint. **Why it matters here:** GSD commands in this repo run
through the junctioned 1.13.0 runtime from the next session; the 1.13.0 changelog adds `workflow.code_review_point`,
per-lane reviewer timeouts, and the executor's refusal to commit on a protected branch (relevant to `feat/phase-12-remediation`
execution). **Durable record:** `~/.claude/project-state.md` 2026-09-06 entry; "Recurred 2026-09-06" addendum on the
2026-08-23 lesson; vault `current-state.md` correction + `log.md [2026-09-06e]`. **Next:** restart the session before any
GSD command; never accept the npm install prompt on this machine; optional upstream bug report on the build sentinel/lock.

## 2026-09-06 — Phase 14 execution started: Helper #2 tracer slice landed behind `HELPER2_ENABLED` (14-01; `feat/phase-12-remediation`, not pushed)
**What:** Juan invoked `/gsd-execute-phase 14` at 20:29Z; GSD ran sequentially on the main tree (#683 degrade — the branch
HEAD is 59 commits ahead of `origin/master`, so harness worktrees would fork the wrong base). Plan 14-01 (tracer) completed in
four commits `3d6bcfb` → `11a473d`: `HELPER2_ENABLED` (default `'0'`) in `pipeline/config.py`; `FORMULA_ERROR_VALUES` (11
Smartsheet error tokens) + `normalize_helper_value()` in `pipeline/types.py` (D-14-05 fabricated-claim guard; a separate
`_NON_CLAIM_LITERALS` check also rejects literal `NA`); six additive Helper #2 column synonyms in `pipeline/discovery.py`;
`sheet_has_helper2_columns` capability gate + extracted, unit-testable `_detect_helper2_row()` in `pipeline/fetch.py`;
`valid_helper2_row` + `helper2` group-key emission in `pipeline/grouping.py` (primary-emission gate extended with
`and not valid_helper2_row`); `HELPER2=`/`HELPER2_DEPT=`/`HELPER2_JOB=` hash meta and the `Helper2` reserved filename token in
`pipeline/change_detection.py`; a `derive_group_identity` helper2 branch in `pipeline/orchestrate.py`; `_Helper2_<name>`
suffix + REPORT DETAILS header branch in `pipeline/excel.py`. Every site is a parallel sibling block — no Helper #1 tuple or
frozenset widened, no facade change. Tests: new `tests/test_foreman_helper_2.py` (production-code E2E tracer + non-claim
fixture battery) and `tests/test_helper2_family_parity.py` (sibling-literal parity with a `KNOWN_DEFERRED` allowlist naming
14-06's two `excel.py` shadow branches); legacy identity/hash pins added to `test_group_identity_and_header_foreman.py` and
`test_change_detection_tiebreak.py`; three source-text-pinning assertions in `tests/test_subcontractor_pricing.py` /
`tests/test_subcontractor_helper_shadow_rescue.py` updated to the extended gate text (Rule 1 auto-fix, same commit). Suite:
2140 passed / 1 skipped. Evidence label: FIXTURE PASS only. `REQUIREMENTS.md` deliberately untouched (HLP-* ids are
cross-plan; the phase verifier reconciles them at the end).
**Why it matters:** with the flag unset the whole Helper #2 path is inert and every primary / Helper #1 / VAC key, hash, and
filename is pinned character-for-character (D-14-09), so production is unchanged until a later `blocking-human` checkpoint
enables the flag. No Smartsheet, Supabase, workflow, attachment, or push.
**14-02 (docs-only) reached its T3 checkpoint at 21:25Z:** Tasks 1–2 committed (`8dfea37`, `55e3428`) as
`14-PENDING-RESOLUTIONS.md` — A1/A2: a FIRST `helper2` generation cannot be suppressed (the `group_state` hash-skip is
keyed on the full `(wr, week_ending, variant, identifier)` tuple; the per-row attachment pre-seed still requires an exact
variant match downstream); the shadow-parity check is gated off in production and hash-value-opaque, so 14-04's
`HASH_FIELDS` decision is unaffected; A3: `pipeline/attribution.py` and `pipeline/pricing.py` need no change for plain
`helper2` (shadow-variant pricing assigned to 14-06), while `pipeline/observability.py` has a PII-marker gap — the new
`HELPER2 GROUP CREATED` INFO line embeds a raw name that no `_PII_LOG_MARKERS` entry catches (assigned to 14-07/14-08).
Task 3 is the `blocking-human` owner-run read-only live column probe (four questions; titles/ids/counts only); Juan
records it in `14-DECISIONS.md` with `LIVE-COLUMN-PROBE: ANSWERED`, then `/gsd-execute-phase 14` resumes wave 1 → 2.
**14-02 T3 probe executed 2026-09-06 ~23:20Z on Juan's instruction ("Run the probe read only"), through the Smartsheet
connector, read-only, zero writes** — the same owner-delegated shape as the Phase 12 read-backs. Every sheet in the
Intake folder (11) and the ProMax Database folder (105: Main, `(NEW)`, Backups 2–104) plus the Resource Analyst sheet
was read for column metadata only (117 sheets): 114 carry the full six-title Helper #2 set, 3 carry none (Intake
ProMax 8, Backup 2 — accepted D-14-01 state — and Resource Analyst, not a data source), and **no partial set exists**,
so 14-07's capability-unavailable fixture stays synthetic. Main ProMax still has all six titles with ids. The Resource
Analyst `Foreman Helper #2` column (`1589780186173316`) is blank on every row (an `IS_NOT_BLANK` filter projected onto
a checkbox column returned 0 of 576, so no name or value was read), which makes **plan 14-10's pilot fixture-only**.
No drift from the 2026-09-05 snapshot. Answers live in `14-DECISIONS.md` (titles/ids/counts only; picklist option
lists deliberately not recorded); the 14-02 continuation executor was resumed with "approved".
**14-02 complete (`41f14b1` Task 3, `34c2f56` closeout) and wave 1 closed green** (py_compile OK; 2140 passed /
1 skipped, unchanged from the 14-01 baseline because 14-02 touched only `.planning/`). The closeout's roadmap tooling
marked HLP-04, HLP-06, and HLP-07 Complete in `REQUIREMENTS.md`; that was premature (HLP-06 is still delivered by
14-03/14-04/14-05/14-09, HLP-07 by 14-10, HLP-04 by 14-07/14-10), so `32e8452` returns the three rows to Pending and
leaves requirement status to the phase verifier. Wave 2 (14-03, 14-04, 14-05; all depend only on 14-01) runs
sequentially on the main tree; the pre-wave key-links check found no prior-wave wiring gap. 14-04 will stop at its
Task 1 `blocking-human` decision (owner-applied additive `pipeline_memory.row_state` DDL and the D-14-08 `HASH_FIELDS`
inclusion), which is Juan's call; 14-03 and 14-05 are autonomous.
**14-03 complete (`7509709`, `5c44d49`, `58d73d2`; docs `4ecb76a`, `595fe70`):** `billing_audit/writer.py` now sends
`p_helper2` in the freeze payload and counts a Helper #2-only claimer as real in the all-sentinel gate; when the
deployed `freeze_attribution` RPC rejects the new parameter the client logs once, bumps `helper2_attribution_degraded`,
retries without it, and continues (D-14-07a); `helper2` joins `ROLE_BY_VARIANT` for `resolve_claimer`. Four Rule-1
deviations are recorded in its SUMMARY (separate `_HELPER2_SENTINEL_CLAIMERS` set to keep the SQL-twin parity test,
reuse of `billing_audit.client` error typing for mypy, three golden key-count pins 24→25, and the new counter mirrored
into both `pipeline/orchestrate.py` pre-seed dicts after an observed Gate 6 failure). Six gates green, 2156 passed.
Evidence is FIXTURE PASS only; no live RPC was called. 14-05 was dispatched next. **14-04's Task 1 decision was put to
Juan with live read-only numbers** from `poeyztlmsawfoqlanucc`: row_state 217,491 rows, row_event 218,931, 58 runs,
no `helper2_*` columns yet. The plan's premise that the hash churn is "shadow-mode only" is stale: the weekly workflow
has carried `RUN_MEMORY_WRITE_ENABLED: '1'` since PR #353 (2026-08-26), so including the four fields in `HASH_FIELDS`
would insert roughly one row_event per row_state row (~217k) on the first production run after deploy. The incremental
READ path is still off, so that burst changes no Excel output and triggers no regeneration; it is a write-volume and
run-time cost only. The 14-02 parity finding still holds (the comparator hashes within one run and never reads stored
hashes).
**14-05 complete (`9fd7ee4`, `4b7940b`, `3224982`, `a706b11`, `40365e2`; docs `dcf2406`):** `pipeline/cleanup.py`'s
orphan-supersede gate recognises a primary attachment superseded by a live Helper #2 claim (only the
`_HELPER_VARIANTS_FOR_ORPHAN_GATE` frozenset changed, 3→6 members; the one-time legacy-migration gates are
byte-identical), `scripts/publish_artifacts_to_supabase.py` parses the three Helper #2 filename tokens before the bare
AEP-billable / reduced-sub checks so `_Helper2_` never cross-matches `_Helper_` or normalises to `primary`, and
`portal-v2/src/lib/variantLabels.ts` gains three readable labels keyed on the snake_case tokens the publisher writes.
Suite 2172 passed / 1 skipped. One gap is recorded, not hidden: the portal typecheck could not run because
`portal-v2/node_modules` is not installed here, so the three-entry TypeScript addition is verified by inspection only
and flagged for a human or CI check with dependencies present. Wave 2 now waits only on Juan's 14-04 Task 1 decision.
**14-06 ran ahead of 14-04** because it depends only on 14-01, 14-03, and 14-05 and touches none of 14-04's files;
the wave-2 gate was re-run first (2172 passed). It landed as `b320e6b`, `321d503`, `fbaf085` (docs `33cdc27`): the
subcontractor Helper #2 shadow variants now partition in `pipeline/grouping.py` without ever emitting both a plain and
a shadow `helper2` key for one row (the 2026-05-19 duplicate-billing shape), render their own filename, header, and
hash sub-bucket in `pipeline/excel.py` / `pipeline/change_detection.py`, and pass the PPP dual-route gate in
`pipeline/upload.py`; the VAC-crew short-circuit, pricing math, and AEP-billable cutoff are untouched. Six gates green,
2196 passed / 1 skipped, the `HELPER2_ENABLED`-unset byte-identity fixture still passes, one Rule-1 mypy annotation
fix. Its closeout marked HLP-01, HLP-02, and HLP-05 complete; HLP-05 was returned to Pending (14-08 still delivers the
fabricated-claim guard and the O-14-A rule) while HLP-01/02 stay marked because every owner plan has landed.
**Juan answered 14-04 Task 1 with `include-now`.** The record `D-14-08-APPLIED` in `14-DECISIONS.md` names the four
additive nullable `row_state` columns, their membership in `HASH_FIELDS`, Juan as the person who applies the DDL in
`poeyztlmsawfoqlanucc` through the SQL Editor, the fact that it is not applied yet, the expected one-time churn
(~217k row_events, real production writes because the write flag is on while the read flag stays off), and that the
DDL timing is his call at rollout because either order must be safe and Task 2 has to prove both. The 14-04 executor
was resumed at Task 2 with that record; no DDL was executed from the session.
**14-04 complete (`c452f72`, `72dcd8d`, `c9739d7`; docs `3dd88b7`):** `pipeline_memory/schema.sql` carries the four
additive nullable `row_state` columns as DDL text for Juan to apply, `pipeline_memory/writer.py` sends them raw in the
payload and appends them to `HASH_FIELDS` (existing order untouched), and `scripts/mem04_passive_compare.py` mirrors
the same four fields split personnel / non-personnel like Helper #1. Both DDL orders are covered by tests, including
the PostgREST "column does not exist" shape. Suite 2206 passed / 1 skipped, six gates green. One Rule-3 deviation:
the Phase 11 blanket `git diff --exit-code` freeze on `schema.sql` in `tests/test_incremental_read.py` was replaced by
an additive-only invariant (zero removed or modified lines), the same precedent that file already uses for the
workflow YAML. Its closeout flipped HLP-06 to Complete; `f4e3c14` returns it to Pending because 14-09 still owns it.
**Orchestrator review found a cross-plan gap, recorded as O-14-B in `14-DECISIONS.md`:** the `upsert_rows_bulk` RPC
body in `schema.sql` (typed `jsonb_to_recordset`, INSERT, ON CONFLICT, and the row_event change JSON) still names only
the Helper #1 fields, so after the DDL the Helper #2 columns would stay NULL, the ~217k hash churn would be paid for
nothing, and no 42703 error would ever fire. 14-04's summary calls this "deferred to 14-09/14-10", but no plan,
context, or research file in Phase 14 mentions that RPC. Recommendation: a gap-closure plan after execution with the
RPC column-list update as owner-applied SQL text, a lockstep source-pin test, and the RPC and DDL applied together
before the code merge. Until then nothing may claim Helper #2 run memory persists.
**Wave 2 closed green (2206 passed / 1 skipped). Juan answered 14-07 Task 1 with `separate-column` and confirmed the
degrade direction ("slower but correct").** The record `D-14-10-APPLIED` names the column (`sheet_registry.
mapping_schema`, nullable TEXT), the marker value (`helper2-v1`, a constant in `pipeline/discovery.py` whose bump
forces exactly one more revalidation), the sixth skip-index admission gate, the unknown-column degrade (one warning,
full validation for every sheet, never admit from cache), the measured one-time cost (37.7 s of Phase 1 for 121 full
validations on the 11.1-04 canary, against runs of 32–55 min and a 165-min budget), and that Juan applies the DDL in
`poeyztlmsawfoqlanucc`, ideally in the same SQL session as the row_state DDL and the O-14-B RPC fix before the code
merge. Not applied yet; the 14-07 executor resumes at Task 2.
**Juan resolved O-14-A on 2026-09-07 with a rule outside the plan's four options: Helper #2 wins.** When both
helper slots claim one row, Helper #2 takes the production credit and Helper #1 does not; when Helper #1 and the
primary foreman both claim a row, it goes to Helper #1's file (existing behavior). The recorded precedence is
Helper #2 over Helper #1 over primary, applied to every flow (production credit, subcontractor shadow file, customer
billing) so the unit is billed exactly once, and the losing claim is dropped for that row only with a distinct log
reason, a run-summary count, and a Sentry event that carries no name or row value. The prototype's
abort-before-workbook behavior stays rejected. The per-slot file-duplication follow-up was not answered, so
D-14-06's two-files-per-slot consequence stands as documentation-only. 14-08 implements exactly this rule once
14-07 lands.

## 2026-09-08 — Phase 14 plan 14-07 closed (mapping-schema marker + four Helper #2 reasons); O-14-A committed; 14-08 dispatched

**What changed.** Plan 14-07 finished and was closed out on `feat/phase-12-remediation`: Task 3 landed as a
RED test commit (`ac38699`) and a GREEN feature commit (`e7aa054`) — `pipeline/fetch.py` now logs
`helper2_no_qualifying_completion` once per Helper #2-capable sheet that produced no qualifying row (distinct
from the 14-01 `helper2_capability_unavailable` reason), and the price-exclusion diagnostic tags a Helper #2-only
claim as a helper row through the same fabricated-claim guard as detection. Partial Helper #2 column sets,
the Intake ProMax 8-shaped fixture (HLP-04, fixture-only by docstring), and the untouched discovery
failed-validation path are pinned by named tests. `14-07-SUMMARY.md` was written and STATE/ROADMAP mark 7/10
plans (`af7d55f`). Juan's O-14-A decision (`helper2-wins`: Helper #2 > Helper #1 > primary foreman; losing claim
logged once, counted, sent to Sentry without PII; never aborts a run) was committed as `ede01a9`, which is plan
14-08 Task 1's deliverable. `/gsd-core:execute-phase 14` was resumed and the 14-08 executor dispatched as a
continuation at Task 2 (sequential on the main tree — the branch is ahead of `origin/master`, so worktree
isolation auto-degraded).

**Why.** Without the no-qualifying-completion reason an operator could not tell "this sheet lacks Helper #2
columns" from "nothing qualified this run"; 14-08's run-summary counters consume exactly these signals.

**Operator effect.** None in production yet — no DDL applied, no upload, no workflow change. Evidence at close:
helper suite 31 passed / 26 subtests; full suite 2222 passed / 1 skipped / 541 subtests; `bash
scripts/run_6_gates.sh` ALL 6 GATES PASSED. HLP-03 stays Pending until 14-08 lands, HLP-04 until 14-10.
Ledgers (`.claude/project-state.md`, this file) are updated but uncommitted while the executor holds the tree.

## 2026-09-08 — Plan 14-08 closed: helper2-wins conflict rule + four Helper #2 run-summary counters; TEST_MODE token footgun closed; 14-09 dispatched

**What changed.** The 14-08 executor (Sonnet, sequential on the main tree) implemented Juan's O-14-A rule:
a source row where BOTH helper slots are valid claims is now emitted for Helper #2 only, at the single
plain-leg and shadow-leg emission sites in `pipeline/grouping.py`, with the pre-pass exclusions agreeing, the
losing Helper #1 claim logged once with the locked conflict reason (PII-safe), counted, and surfaced to Sentry
with ids/counts only (`c1d096b` RED, `b3ae217` GREEN; plan 14-06's "takes no position" placeholder test is
replaced). `pipeline/orchestrate.py` now pre-seeds four Helper #2 counters on every run (capability-absent,
capability-present-but-idle, conflicted, generated) and `tests/golden/run_summary_baseline.json` grew from 25
to 29 keys in the same commit (`4aeea1e` RED, `bede1c0` GREEN). `30d7d8a` wrote 14-08-SUMMARY.md, marked
8/10 plans, and flipped HLP-03 and HLP-05 to Complete. Orchestrator gates after the plan: full suite 2230
passed / 1 skipped / 541 subtests, ALL 6 GATES PASSED, schema-drift and UI gates clear.

**Incident (read-only, closed).** Before finding the right invocation the executor ran a bare
`TEST_MODE=true python generate_weekly_pdfs.py`; python-dotenv loaded the real token from `.env` and the run
fetched 121 live source sheets / 217,741 rows over 18.8 min, ran the rate-sanity audit, and was killed by the
orchestrator before Excel generation or upload. No Smartsheet write occurred. `0203e27` changes the documented
synthetic dry run in `CLAUDE.md`, `.github/copilot-instructions.md`, and `docs/ai/safe-commands.md` to
`SMARTSHEET_API_TOKEN= TEST_MODE=true SKIP_UPLOAD=true PYTHONUTF8=1 python generate_weekly_pdfs.py` and
records the lesson in `memory-bank/living-ledger.md` (`[2026-09-08 10:20]`).

**Operator effect.** Nothing in production changed: no DDL, no upload, no workflow edit. The 14-09 executor is
authoring the owner-deployed attribution SQL and will stop at its `blocking-human` checkpoint for Juan to
choose the deployment order and quiet window; nothing is applied from an agent session.

## 2026-09-08 — Plan 14-09 Task 1: owner-deployed Helper #2 attribution SQL authored; stopped at the apply checkpoint; DEFAULT NULL fix

**What changed.** The 14-09 executor authored `billing_audit/helper2_attribution.sql` (`66924c0`): two additive
nullable columns on `billing_audit.attribution_snapshot`, a read-then-manual-splice procedure for
`freeze_attribution` (its body lives only in Supabase and is never fabricated in the repo), both lookup
functions recreated DROP-first so their return columns actually change (the 2026-05-27 silent non-deploy
lesson), GRANTs, a schema-cache reload, and read-back queries. `billing_audit/schema.sql` documents the new
contract and corrects the stale bulk-lookup comment; `tests/test_helper2_attribution_sql_contract.py` pins
drop-before-create, no plain create-or-replace, parameter/return-column parity with `billing_audit/writer.py`,
and no touch of the backfill function or provenance columns. The orchestrator then added `DEFAULT NULL` to the
two new freeze parameters, documented it, and pinned it in the contract test (`c786ec3`).

**Why the fix.** PostgREST resolves a named-argument RPC call only when every parameter without a default is
supplied. The currently deployed writer sends the 12 pre-Phase-14 parameters, so a 14-parameter function
without defaults would reject every freeze between the SQL apply and the code merge. With the defaults, both
deployment orders are safe.

**Operator effect.** Nothing applied. Plan 14-09 is stopped at its `blocking-human` Task 2 checkpoint: Juan
chooses `sql-first` / `code-first` / `defer`, a quiet window outside the cron schedule, applies the file by hand
in the Supabase SQL Editor, and records `D-14-07-APPLIED` before Task 3's read-back. Evidence on the fixed
tree (final rerun after `c786ec3`): contract test 19 passed; full suite 2249 passed / 1 skipped / 550 subtests;
ALL 6 GATES PASSED. The checkpoint panel went to Juan at 16:00Z and the session ended blocked on his answer.

## 2026-09-08 — Plan 14-09 Task 2 applied: Helper #2 attribution migration live in production (sql-first, owner-delegated); Task 3 read-back 3 of 4

**What changed.** Juan chose `sql-first` and delegated the apply to the session over the Supabase MCP
connection. The migration went in at 16:55:11Z as `20260908165511_helper2_attribution_columns_and_rpcs`,
one transaction on `poeyztlmsawfoqlanucc`: two nullable columns on `billing_audit.attribution_snapshot`,
`freeze_attribution` rebuilt from its live body with the two Helper #2 columns spliced into the INSERT and
the two parameters appended last with `DEFAULT NULL`, both lookup functions dropped and recreated with the
new return columns, grants restored to the exact pre-state, PostgREST reload. The pre-migration
definitions, grants, and rollback steps are parked in the vault `raw/` folder. Records: `D-14-07-APPLIED`,
`D-14-07-VERIFIED`, and the new open item `O-14-C` in `14-DECISIONS.md` (`3d6263a`).

**Why the deviations.** Reading the live definitions before dropping anything showed three things the
repo file had wrong or missing: Postgres requires every parameter after a defaulted one to carry a
default, so the template's mid-list placement could not have compiled; both lookups carry a pinned
`search_path` from the 2026-05-19 advisor remediation that the repo CREATEs omitted; and the deployed
freeze is per-row first-write-wins, not per-role. The repo SQL and `schema.sql` now match what is deployed.

**Operator effect.** The deployed writer (12 parameters) keeps resolving the RPC, proven by a 12-argument
named call on a synthetic row. Nothing changes for operators until the branch merges; after the merge the
first run writes Helper #2 attribution for newly frozen rows only. Rows frozen before the merge never gain
Helper #2 (O-14-C, Juan's call). The apply landed about 75 seconds into run 34253845749's job setup rather
than in a run-free gap; that run is the pending evidence for read-back check 4.

## 2026-09-08 — 14-09 read-back check 4 observed; plan 14-11 inserted to close O-14-C (per-role Helper #2 fill)

**What changed.** Run 34253845749, the first full run against the migrated functions, completed with 74
freeze calls and 6 bulk lookups all returning 200 and no PostgREST error codes; its 74 new rows carry a
primary and a null Helper #2, which is what the deployed 12-parameter writer must produce. That closes
`D-14-07-VERIFIED` check 4 for the deployed code; the Phase 14 degrade-warning check stays post-merge.
Juan then asked for O-14-C to be worked before 14-10, so plan `14-11-PLAN.md` was inserted in wave 6 and
14-10 moved to wave 7 behind it (ROADMAP, STATE, and 14-10's dependencies updated).

**Why a fill and not a backfill.** The deployed freeze is first-write-wins per row, and the pipeline never
re-sends an already-frozen row (the frozen-row cache skips 221,616 keys per run). A Helper #2 added to a
row after its first freeze therefore never reaches the snapshot. The plan mirrors the Phase 12 backfill
pattern inside the freeze function's conflict clause, for the Helper #2 role only: fill the two columns
when the existing value is null or a sentinel, never overwrite a real name, record a `live` provenance
entry, and let the pipeline re-send a frozen row only when it now carries a valid Helper #2 and the
prefetched snapshot says the role is empty. A historical backfill has nothing to fill today, because
Helper #2 is blank across production.

**Operator effect.** None yet. Tasks 1 and 2 are repository-only and inert against the deployed function.
Task 3 is the owner-gated apply of a same-signature CREATE OR REPLACE, with a synthetic-row read-back.

## 2026-09-08 — Plan 14-11 Tasks 1–2 landed: late Helper #2 admission, fill counter, and the fill migration file

**What changed.** The freeze loop now re-sends an already-frozen row only when the last bulk prefetch
reported that row's Helper #2 as empty, the row carries a real Helper #2 foreman and a dept, and the
Helper #2 flag is on (`helper2_fill_admits` in `pipeline/attribution.py`, keys published by
`pipeline/grouping.py`). `freeze_row` classifies a returned row as `snapshots_helper2_filled` only when the
database's `backfill_provenance.helper2.run_id` names the current run; the run summary grows to 30 keys.
`billing_audit/helper2_attribution_fill.sql` is the owner-gated migration: CREATE OR REPLACE on the deployed
14-parameter signature whose only change is `ON CONFLICT … DO UPDATE` of the two Helper #2 columns plus a
`live` provenance entry, gated by the sentinel predicate in both directions. Commits `57144a9`, `c30d8ed`,
`0bb018b`; contract test and schema.sql note included.

**Why it is safe to merge before the apply.** Against the currently deployed function a re-sent row hits
DO NOTHING and is counted already-frozen, exactly today's outcome. Against the migrated function without
this code, no row is ever re-sent. Either order is inert; only both together produce a fill.

**Operator effect.** None until Task 3. Two test files outside the plan's list were touched for direct
consequences: the counters pin in `tests/test_billing_audit_shadow.py` and the search window in
`tests/validate_production_safety.py`. Full suite 2284 passed; all 6 gates passed.

## 2026-09-08 — 14-09 closed on Juan's sign-off; 14-11 per-role Helper #2 fill applied to production and read back

**What changed.** Juan co-signed `D-14-07-VERIFIED` and chose apply-delegated for 14-11. Plan 14-09 closed
(`a2de0de`) with HLP-06 marked complete. The per-role fill went into production at 20:12:05Z as migration
`20260908201205_helper2_attribution_per_role_fill`, a same-signature CREATE OR REPLACE applied in a
run-free gap confirmed at the moment of applying. The pre-fill body is parked in the vault as the
rollback reference; rolling back is re-running it, no window needed. Records `O-14-C-APPLIED` and
`O-14-C-VERIFIED` are in the phase decisions file, and O-14-C is marked resolved.

**What was proven on production.** On synthetic rows deleted afterwards: the deployed writer's
12-argument call leaves Helper #2 null; a re-freeze carrying a Helper #2 with every other value different
fills only the two Helper #2 columns and stamps a `live` provenance entry, leaving every other column
byte-identical including the original freeze timestamp and run id; a second, different Helper #2 is
refused; a fresh insert carries Helper #2 with no provenance; both lookups return the filled values.

**Operator effect.** None until the branch merges: the deployed writer never satisfies the fill gate. After
the merge, a row frozen before a Helper #2 appeared on it is re-sent once, filled once, and counted as
`snapshots_helper2_filled` in the run summary. Watch that counter and the Helper #2 degrade warning on the
first post-merge run.

## 2026-09-08 — Plan 14-10 Tasks 1–2: Helper #2 runbook and environment docs shipped; pilot rehearsed to fixture and synthetic evidence; rollout decision open

**What changed.** A new runbook page, `website/docs/runbook/foreman-helper-2.md`, documents what Helper #2
is, the `HELPER2_ENABLED` flag and where it is consumed, the four run conditions and how to tell them apart
in a log, filenames and attachment placement, how a Helper #2 change is picked up, the two decision-born
operator notes (one person in two slots produces two files; the both-slots-checked row goes to Helper #2),
rollback, the proposed workflow wiring line (recorded, not applied), and the pilot procedure with its
comparison criteria and evidence labels. The environment reference, the operator quick reference, the
architecture doc, and the what's-new page were updated to match (`fe70b28`). The pilot was then rehearsed
in order: fixtures pass, synthetic dry run passes with the 30-key run summary and all six gates, the live
upload-suppressed step was not run because no dated owner authorization exists, and the controlled upload
is never run by an agent (`b080d59`, record `14-10-PILOT-REHEARSAL`).

**Why the live step stayed off.** Beyond the missing authorization, the rehearsal's flag-consumption reading
found that `SKIP_UPLOAD` suppresses uploads and attachment cleanup but never the `freeze_attribution` write,
which is gated only by `TEST_MODE`. An upload-suppressed run over live sheets therefore still writes
attribution rows to Supabase. That is now stated in the runbook so nobody treats that command as read-only.

**Operator effect.** Nothing changed in production. The feature ships flag-off and stays off until the
rollout decision `D-14-12-ROLLOUT` is recorded. Because the Resource Analyst Helper #2 column is blank on all
576 rows, the pilot evidence stops at fixtures and synthetic data by construction.

## 2026-09-08 — D-14-12-ROLLOUT recorded; branch merged with master, validated, and PR #389 opened for the documented-only rollout

**What changed.** Juan chose the documented-only rollout and asked for it to reach production immediately without
a pilot ("we can debug if something goes wrong"). The decision is recorded as `D-14-12-ROLLOUT` (`a3998f9`): the
Helper #2 feature ships with `HELPER2_ENABLED` defaulting to `'0'`, the GitHub Actions workflow stays unwired, and
the pilot's live steps are skipped. `origin/master` (five Notion-worker docs commits) was merged into
`feat/phase-12-remediation` (`6d8942c`); the one conflict, `website/docs/runbook/whats-new.md`, was resolved to a
single DSR block carrying the synthesized Helper #2 entry and the Sept 3 list once. The merged tree passed the full
suite (2284 passed, 1 skipped, 557 subtests), the six-gate harness, and the website typecheck and build. The branch
was pushed and PR #389 opened to master with the Objective / Changes Made / Production Safety Check body.

**Why.** Phase 14 is code-complete (14-01..14-11) and both attribution migrations are already live, so the only
production-visible change from merging is the dormant code path plus the run-memory hash now covering the helper2
fields. Merging now lets the scheduled runs prove the 14-parameter `freeze_attribution` call and the mapping-schema
revalidation in production while the flag stays off.

**Operator effect.** CI on #389: compile/test, coverage, lint, typecheck/build, CodeQL, Vercel, Cursor approval
PASS; `code/snyk` (quota) and the Azure DevOps mirror build FAIL as they did on merged PR #388 and are not required
(master has no branch protection). Expect on the first post-merge scheduled run: a one-time ~217k `row_event`
churn, a mapping-schema WARNING with full validation, no Helper #2 degrade warning, all Helper #2 counters 0.
Nothing in Excel output changes until `HELPER2_ENABLED` is set. See `memory-bank/living-ledger.md`
`[2026-09-08 18:55]`.

**Merged.** PR #389 squash-merged to master as `ba6eeaf` at 2026-09-09 01:37Z with the 14-10 closeout and these ledgers
inside it. The 01:00Z scheduled run had already started (01:27Z) on the previous master, so the first run on the merged code
is the Wednesday 13:00Z slot.

## 2026-09-09 — Plan 14-12: O-14-B closed in production, Helper #2 run-memory columns live, flag wired for enablement

**What changed.** `pipeline_memory.upsert_rows_bulk` now carries the four Helper #2 fields the writer has sent
since 14-04 (typed recordset, projection, `row_event.after_image`, `row_state` INSERT and ON CONFLICT lists), pinned
to `HASH_FIELDS` by a new lockstep contract test. The two long-pending additive DDLs (`row_state` helper2_* x4,
`sheet_registry.mapping_schema`) and the RPC were applied together as Supabase migration
`20260909022129_helper2_row_state_columns_marker_and_rpc` and read back with a synthetic insert / no-op resend /
update round-trip (`D-14-13-DDL-APPLIED`, `D-14-13-VERIFIED`). The scheduled workflow gains
`HELPER2_ENABLED: ${{ vars.HELPER2_ENABLED || '0' }}`; the repository variable becomes the on/off switch
(`D-14-14-ENABLE`). `.claude/project-state.md` was condensed to 94 lines after Greptile flagged its growth.

**Why.** Without the RPC change the first post-merge run would pay the ~217k `row_event` churn without persisting a
single Helper #2 value, and every run would re-validate every sheet for lack of the marker column. Juan approved both
DDLs, the O-14-B closure, O-14-A Follow-up 1, and enabling the flag once those landed.

**Operator effect.** `HELPER2_ENABLED` is set through the repo variable (`gh variable set HELPER2_ENABLED --body 1`
after PR #390 merges; `0` to roll back, no code change). The first scheduled run after the merge writes the
`mapping_schema` marker after one full validation per sheet and logs the Helper #2 counters; no `_Helper2_` workbook
appears until a crew records a second helper. See `memory-bank/living-ledger.md` `[2026-09-08 21:30]`.

**Enabled.** PR #390 squash-merged to master `661d6d3` at 2026-09-09 02:49:30Z; repo variable `HELPER2_ENABLED=1`
set at 02:49:58Z (`D-14-14-ENABLE` addendum). First enabled scheduled run = Wed 2026-09-09 13:00Z. Flag-off is an
emergency disable, not a billing-safe rollback once real Helper #2 claims exist (owner decision `O-14-D`).
Ledger `[2026-09-08 21:58]`. Records: PR #391.

**O-14-D resolved (2026-09-09).** Juan confirmed Helper #2 is a permanent capability, not a one-time backfill:
`HELPER2_ENABLED` stays `1` indefinitely and flag-off is an emergency kill switch only. Option (a) accepted — the
regroup-on-disable limitation stands, reconciled by hand if it ever happens; persisted-claim routing (option b)
and attachment retirement (option c) declined, no code change. Runbook, environment reference, project-state,
STATE.md, and `14-DECISIONS.md` updated. Ledger `[2026-09-09 08:45]`.
